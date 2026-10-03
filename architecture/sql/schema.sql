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
    created_at   TEXT NOT NULL,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at   TEXT NOT NULL,
    updated_by   INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    arb_title           TEXT NOT NULL,
    summary             TEXT,
    artifact_link       TEXT,
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
    bu_gov_reviewer     TEXT,
    ea_gov_reviewer     TEXT,
    status              TEXT NOT NULL DEFAULT 'SUBMITTED' REFERENCES request_statuses(code),
    approval_date       TEXT,
    meeting_date        TEXT,  -- ARB meeting (YYYY-MM-DD); required by the API while SCHEDULED
    meeting_time        TEXT,  -- ARB meeting time (HH:MM, local); required by the API while SCHEDULED
    comments            TEXT,
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
