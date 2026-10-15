import json
import sqlite3
from pathlib import Path

from portal.constants import PERMISSION_CATALOG, REQUEST_STATUSES
from portal.db import now_iso

# Defaults for the reference data tables, inserted only when a table is empty; after that the lists belong to
# the admins (Reference Data page).
DEFAULT_REVIEW_TYPES = [
    "Solution Architecture (SAD)",
    "Architecture Decision Records (ADR)",
    "Event-Driven Architecture Design",
    "AI/ML Solution Architecture",
    "API Contract & Design",
    "Architecture Patterns & Standards",
    "Data Architecture & Modeling",
    "Architecture Certification",
    "Architecture Due Diligence",
]

DEFAULT_PDLC_CHECKPOINTS = ["Inception", "Elaboration", "Construction", "Delivery"]

# (code, label, review types that must carry this reference before the request leaves DRAFT)
DEFAULT_ARTIFACT_NAMES = [
    ("SAD",           "SAD",                  ["Solution Architecture (SAD)", "Architecture Decision Records (ADR)",
                                              "Event-Driven Architecture Design", "Data Architecture & Modeling",
                                              "Architecture Certification"]),
    ("ADR",           "ADR",                  ["Architecture Decision Records (ADR)"]),
    ("PATTERNS",      "Patterns & Standards", ["Architecture Patterns & Standards"]),
    ("DUE_DILIGENCE", "Due Diligence",        ["Architecture Due Diligence"]),
    ("API_SPEC",      "API Specification",    ["API Contract & Design"]),
    ("DATA_DESIGN",   "Data Design",          []),
    ("OTHER",         "Others",               []),
]

# The reviewers a new database starts with: role -> names.
DEFAULT_REVIEWERS = {
    "BU":  ["J. Rivera", "D. Fox", "H. Bello", "N. Osei", "C. Weiss"],
    "FAE": ["S. Kaplan", "V. Iyer", "B. O'Neil", "F. Marchetti", "E. Sato"],
    "ECS": ["G. Haddad", "T. Lindqvist", "Y. Okafor", "I. Moreau", "K. Tanaka"],
}

DEFAULT_ROLES = [
    ("REQUESTOR", "Requestor", "AAD-GovPortal-Requestors", "Submits intakes and tracks their own requests.",
     ["request:create", "request:view:own", "request:edit:own", "request:withdraw:own", "request:resubmit",
      "calendar:view"]),
    ("REVIEWER", "Reviewer", "AAD-GovPortal-Reviewers", "Reviews the queue and moves requests through the lifecycle.",
     ["request:view:all", "request:review", "request:schedule", "board:card:edit", "calendar:view", "insights:view"]),
    ("CHIEF_ARCHITECT", "Chief Architect", "AAD-GovPortal-ChiefArchitects",
     "Reviews the queue and approves Critical-risk requests in Chief Architecture Review.",
     ["request:view:all", "request:review", "request:schedule", "request:signoff", "board:card:edit",
      "calendar:view", "insights:view"]),
    ("ADMIN", "Admin", "AAD-GovPortal-Admins", "Full access, including users and permissions.",
     [code for code, *_ in PERMISSION_CATALOG]),
]

# Every table carries created_at/created_by/updated_at/updated_by. A NULL *_by means the system
# wrote the row (seeding or a catalog sync), not a signed-in user. architecture/sql/schema.sql mirrors this.
SCHEMA = """
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
"""

SEED_USERS = [
    ("A. Nguyen",   "a.nguyen@example.com",  "REQUESTOR"),
    ("L. Gomez",    "l.gomez@example.com",   "REQUESTOR"),
    ("M. Cho",      "m.cho@example.com",     "REQUESTOR"),
    ("P. Shah",     "p.shah@example.com",    "REQUESTOR"),
    ("R. Patel",    "r.patel@example.com",   "REQUESTOR"),
    ("C. Weiss",    "c.weiss@example.com",   "REVIEWER"),
    ("B. O'Neil",   "b.oneil@example.com",   "REVIEWER"),
    ("S. Kaplan",   "s.kaplan@example.com",  "CHIEF_ARCHITECT"),
    ("Portal Admin", "admin@example.com",    "ADMIN"),
]


def init_db(db_path: Path) -> None:
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)
    add_missing_columns(db)
    seed_users(db)
    sync_permissions(db)
    sync_request_statuses(db)
    seed_reference_data(db)
    seed_roles(db)
    seed_board_defaults(db)
    seed_reviewers(db)
    db.close()


# Columns added after release: CREATE TABLE IF NOT EXISTS leaves an existing table as it was.
ADDED_COLUMNS = [
    ("requests", "risk_tier", "INTEGER"),
    ("requests", "agent_review", "TEXT"),
    ("requests", "artifacts", "TEXT"),
    ("requests", "intelea_capability_link", "TEXT"),
    ("requests", "solution_id", "TEXT"),
    ("requests", "bu_gov_reviewers", "TEXT"),
    ("requests", "ea_gov_reviewers", "TEXT"),
    ("requests", "ecs_reviewers", "TEXT"),
    ("artifact_names", "active", "INTEGER NOT NULL DEFAULT 1"),
    ("request_statuses", "active", "INTEGER NOT NULL DEFAULT 1"),
    ("request_statuses", "builtin", "INTEGER NOT NULL DEFAULT 0"),
]


def add_missing_columns(db: sqlite3.Connection) -> None:
    for table, column, decl in ADDED_COLUMNS:
        if column not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    db.commit()


def seed_users(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return
    ts = now_iso()
    db.executemany(
        "INSERT INTO users (name, email, role, created_at, updated_at) VALUES (?,?,?,?,?)",
        [(n, e, r, ts, ts) for n, e, r in SEED_USERS]
    )
    db.commit()


# A permission added to the catalog after roles exist gets the grants DEFAULT_ROLES lists for it, once;
# after that the matrix is the admins' to change.
def sync_permissions(db: sqlite3.Connection) -> None:
    ts = now_iso()
    known = {r[0] for r in db.execute("SELECT code FROM permissions")}
    for pos, (code, category, label, desc) in enumerate(PERMISSION_CATALOG):
        db.execute(
            "INSERT INTO permissions (code, category, label, description, position, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(code) DO UPDATE SET category = excluded.category, label = excluded.label, "
            "description = excluded.description, position = excluded.position, updated_at = excluded.updated_at "
            "WHERE category IS NOT excluded.category OR label IS NOT excluded.label "
            "OR description IS NOT excluded.description OR position IS NOT excluded.position",
            (code, category, label, desc, pos, ts, ts)
        )
    if known:
        for role_code, _, _, _, perms in DEFAULT_ROLES:
            db.executemany(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_code, created_at, updated_at) "
                "SELECT id, ?, ?, ? FROM roles WHERE code = ?",
                [(p, ts, ts, role_code) for p in perms if p not in known]
            )
    codes = [c for c, *_ in PERMISSION_CATALOG]
    marks = ",".join("?" * len(codes))
    db.execute(f"DELETE FROM role_permissions WHERE permission_code NOT IN ({marks})", codes)
    db.execute(f"DELETE FROM permissions WHERE code NOT IN ({marks})", codes)
    db.commit()


# Built-in status codes come from code (the review route depends on them); their text and active flag are the
# admins' once inserted. Admin-added statuses (builtin = 0) sort after the built-ins and are left alone.
def sync_request_statuses(db: sqlite3.Connection) -> None:
    ts = now_iso()
    db.executemany(
        "INSERT INTO request_statuses (code, label, meaning, who_acts, position, builtin, created_at, updated_at) "
        "VALUES (?,?,?,?,?,1,?,?) ON CONFLICT(code) DO UPDATE SET position = excluded.position, builtin = 1 "
        "WHERE position IS NOT excluded.position OR builtin IS NOT 1",
        [(code, label, meaning, who_acts, pos, ts, ts) for pos, (code, label, meaning, who_acts) in enumerate(REQUEST_STATUSES)])
    codes = [c for c, *_ in REQUEST_STATUSES]
    db.execute(f"DELETE FROM request_statuses WHERE builtin = 1 AND code NOT IN ({','.join('?' * len(codes))})", codes)
    db.commit()


def seed_reference_data(db: sqlite3.Connection) -> None:
    ts = now_iso()
    if not db.execute("SELECT COUNT(*) FROM review_types").fetchone()[0]:
        db.executemany("INSERT INTO review_types (name, created_at, updated_at) VALUES (?,?,?)",
                       [(n, ts, ts) for n in DEFAULT_REVIEW_TYPES])
    if not db.execute("SELECT COUNT(*) FROM pdlc_checkpoints").fetchone()[0]:
        db.executemany("INSERT INTO pdlc_checkpoints (name, position, created_at, updated_at) VALUES (?,?,?,?)",
                       [(n, pos, ts, ts) for pos, n in enumerate(DEFAULT_PDLC_CHECKPOINTS)])
    if not db.execute("SELECT COUNT(*) FROM artifact_names").fetchone()[0]:
        db.executemany(
            "INSERT INTO artifact_names (code, label, required_for, position, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            [(c, label, json.dumps(req), pos, ts, ts) for pos, (c, label, req) in enumerate(DEFAULT_ARTIFACT_NAMES)])
    db.commit()


def seed_roles(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM roles").fetchone()[0]:
        return
    ts = now_iso()
    for code, name, ad_group, desc, perms in DEFAULT_ROLES:
        cur = db.execute(
            "INSERT INTO roles (code, name, ad_group, description, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (code, name, ad_group, desc, ts, ts)
        )
        db.executemany(
            "INSERT INTO role_permissions (role_id, permission_code, created_at, updated_at) VALUES (?,?,?,?)",
            [(cur.lastrowid, p, ts, ts) for p in perms]
        )
    db.commit()


def seed_reviewers(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM reviewers").fetchone()[0]:
        return
    ts = now_iso()
    db.executemany(
        "INSERT INTO reviewers (name, role, created_at, updated_at) VALUES (?,?,?,?)",
        [(name, role, ts, ts) for role, names in DEFAULT_REVIEWERS.items() for name in names])
    db.commit()


def seed_board_defaults(db: sqlite3.Connection) -> None:
    existing = db.execute("SELECT COUNT(*) c FROM board_fields").fetchone()[0]
    if existing:
        return
    ts = now_iso()
    defaults = [
        ("title",    "Title",    "text",     None,                                                 0, 1, 0),
        ("team",     "Team",     "select",   json.dumps(["Platform","Data","AI/ML","Security","Frontend"]), 1, 0, 0),
        ("owner",    "Owner",    "text",     None,                                                 2, 0, 0),
        ("status",   "Status",   "select",   json.dumps(["Backlog","In Progress","Blocked","Done"]),3, 0, 1),
        ("priority", "Priority", "select",   json.dumps(["Low","Medium","High","Urgent"]),         4, 0, 0),
        ("dueDate",  "Due Date", "date",     None,                                                 5, 0, 0),
        ("notes",    "Notes",    "text",     None,                                                 6, 0, 0),
    ]
    db.executemany(
        "INSERT INTO board_fields (key,label,type,options,position,is_title,is_group,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)", [(*d, ts, ts) for d in defaults]
    )
    samples = [
        {"title": "Draft ARB template v2",   "team": "Platform", "owner": "Alice",   "status": "In Progress", "priority": "High",   "dueDate": "2026-09-05", "notes": "Add PDLC alignment section"},
        {"title": "Fraud model retrain",     "team": "AI/ML",    "owner": "Ravi",    "status": "Backlog",     "priority": "Medium", "dueDate": "2026-09-20", "notes": ""},
        {"title": "Zero-trust segmentation", "team": "Security", "owner": "Priya",   "status": "Blocked",     "priority": "Urgent", "dueDate": "2026-08-30", "notes": "Waiting on network review"},
        {"title": "Portal dark mode polish", "team": "Frontend", "owner": "Sam",     "status": "Done",        "priority": "Low",    "dueDate": "2026-08-15", "notes": ""},
    ]
    for pos, s in enumerate(samples):
        db.execute(
            "INSERT INTO board_cards (data, position, created_at, updated_at) VALUES (?,?,?,?)",
            (json.dumps(s), pos, ts, ts)
        )
    db.commit()
