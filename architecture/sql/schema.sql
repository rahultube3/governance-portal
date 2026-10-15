-- Governance Portal — database schema (SQLite)
--
-- The same tables init_db() in api/portal/schema.py creates, so a database built from this script is
-- interchangeable with one the API created. Usage:
--   sqlite3 governance.db < architecture/sql/schema.sql
--   sqlite3 governance.db < architecture/sql/reference-data.sql
--
-- Audit columns: every table has created_at / created_by / updated_at / updated_by.
-- *_by references users(id) and is NULL when the system (seeding or a catalog sync) wrote the row.

PRAGMA foreign_keys = ON;

BEGIN;

-- Demo sign-in users. `role` stands in for Azure AD group membership: the user belongs to the
-- AD group mapped to roles.ad_group for that role code.
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    role        TEXT NOT NULL,  -- roles.code; validated by the API since admins can add roles
    created_at  TEXT NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Each role is granted to members of one Azure AD group.
CREATE TABLE IF NOT EXISTS roles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    ad_group     TEXT,
    description  TEXT,
    created_at   TEXT NOT NULL,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at   TEXT NOT NULL,
    updated_by   INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Permission catalog. The API enforces these codes and re-syncs this table from code on startup.
CREATE TABLE IF NOT EXISTS permissions (
    code         TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    label        TEXT NOT NULL,
    description  TEXT,
    position     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at   TEXT NOT NULL,
    updated_by   INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Permission matrix: one row per (role, permission) grant.
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id          INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_code  TEXT NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
    created_at       TEXT NOT NULL,
    created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at       TEXT NOT NULL,
    updated_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (role_id, permission_code)
);

-- Request status lookup. The API re-syncs this table from REQUEST_STATUSES on startup.
CREATE TABLE IF NOT EXISTS request_statuses (
    code         TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    meaning      TEXT NOT NULL,
    who_acts     TEXT NOT NULL,
    position     INTEGER NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1,  -- 0: no new moves into it (DEACTIVATABLE_STATUSES and admin-added ones)
    builtin      INTEGER NOT NULL DEFAULT 0,  -- 1: from REQUEST_STATUSES; 0: added by an admin as a pause step
    created_at   TEXT NOT NULL,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at   TEXT NOT NULL,
    updated_by   INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    arb_title           TEXT NOT NULL,
    summary             TEXT,
    pr                  TEXT,
    app_id              TEXT,
    app_name            TEXT,
    trackit_id          TEXT,
    solution_architect  TEXT,
    sa_contributors     TEXT,
    artifact_type       TEXT NOT NULL,
    pdlc_checkpoint     TEXT,
    date_submitted      TEXT NOT NULL,
    date_reviewed       TEXT,
    bu_gov_reviewers    TEXT,     -- JSON list of BU reviewers' names (reviewers.name)
    ea_gov_reviewers    TEXT,     -- JSON list of FAE Governance reviewers' names
    ecs_reviewers       TEXT,     -- JSON list of ECS (Security) reviewers' names
    status              TEXT NOT NULL DEFAULT 'SUBMITTED' REFERENCES request_statuses(code),
    approval_date       TEXT,
    meeting_date        TEXT,  -- ARB meeting (YYYY-MM-DD); required by the API while SCHEDULED
    meeting_time        TEXT,  -- ARB meeting time (HH:MM, local); required by the API while SCHEDULED
    comments            TEXT,
    artifacts           TEXT,     -- JSON [{code, link}], up to 5 Architecture Reference Links; link is free text
    intelea_capability_link TEXT,
    solution_id         TEXT,
    risk_tier           INTEGER,  -- 1 Low, 2 Medium, 3 High, 4 Critical; picked by the requestor, required outside DRAFT
    agent_review        TEXT,     -- JSON {passed, summary, findings, checkedAt} from the Low-risk validation agent
    created_at          TEXT NOT NULL,
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at          TEXT NOT NULL,
    updated_by          INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Append-only log of status transitions; rows are never edited, so updated_* mirrors created_*.
CREATE TABLE IF NOT EXISTS status_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id   INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    from_status  TEXT,
    to_status    TEXT NOT NULL,
    note         TEXT,
    created_at   TEXT NOT NULL,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at   TEXT NOT NULL,
    updated_by   INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Architecture Reference Link names (the reference dropdown), managed on the Reference Data page.
CREATE TABLE IF NOT EXISTS artifact_names (
    code          TEXT PRIMARY KEY,
    label         TEXT NOT NULL,
    required_for  TEXT NOT NULL DEFAULT '[]',  -- JSON list of review types (requests.artifact_type) that must carry it outside DRAFT
    active        INTEGER NOT NULL DEFAULT 1,  -- 0 hides it from new selections; requests that use it keep it
    position      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    created_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at    TEXT NOT NULL,
    updated_by    INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Review types (requests.artifact_type holds the name). Renaming one renames it on requests and in
-- artifact_names.required_for; one in use can be deactivated but not removed.
CREATE TABLE IF NOT EXISTS review_types (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- PDLC checkpoints in lifecycle order (requests.pdlc_checkpoint holds the name).
CREATE TABLE IF NOT EXISTS pdlc_checkpoints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    position    INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- People who can be named as a request's BU, FAE or ECS reviewers. Requests store the names, so deactivating
-- a reviewer leaves past requests as they were.
CREATE TABLE IF NOT EXISTS reviewers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,  -- BU, FAE or ECS (REVIEWER_ROLES); validated by the API
    active      INTEGER NOT NULL DEFAULT 1,  -- 0 hides it from new selections; requests that name it keep it
    created_at  TEXT NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (role, name)
);

-- Team Board: user-defined fields; card values live in board_cards.data keyed by board_fields.key.
CREATE TABLE IF NOT EXISTS board_fields (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    type        TEXT NOT NULL,
    options     TEXT,
    position    INTEGER NOT NULL DEFAULT 0,
    is_title    INTEGER NOT NULL DEFAULT 0,
    is_group    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS board_cards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    data        TEXT NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
);

COMMIT;
