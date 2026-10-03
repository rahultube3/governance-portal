import json
import sqlite3
from pathlib import Path

from portal.constants import PERMISSION_CATALOG, REQUEST_STATUSES
from portal.db import now_iso

DEFAULT_ROLES = [
    ("REQUESTOR", "Requestor", "AAD-GovPortal-Requestors", "Submits intakes and tracks their own requests.",
     ["request:create", "request:view:own", "request:edit:own", "request:withdraw:own", "request:resubmit",
      "calendar:view"]),
    ("REVIEWER", "Reviewer", "AAD-GovPortal-Reviewers", "Reviews the queue and moves requests through the lifecycle.",
     ["request:view:all", "request:review", "request:schedule", "board:card:edit", "calendar:view", "insights:view"]),
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
"""

SEED_USERS = [
    ("A. Nguyen",   "a.nguyen@example.com",  "REQUESTOR"),
    ("L. Gomez",    "l.gomez@example.com",   "REQUESTOR"),
    ("M. Cho",      "m.cho@example.com",     "REQUESTOR"),
    ("P. Shah",     "p.shah@example.com",    "REQUESTOR"),
    ("R. Patel",    "r.patel@example.com",   "REQUESTOR"),
    ("C. Weiss",    "c.weiss@example.com",   "REVIEWER"),
    ("B. O'Neil",   "b.oneil@example.com",   "REVIEWER"),
    ("Portal Admin", "admin@example.com",    "ADMIN"),
]


def init_db(db_path: Path) -> None:
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)
    seed_users(db)
    sync_permissions(db)
    sync_request_statuses(db)
    seed_roles(db)
    seed_board_defaults(db)
    db.close()


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


def sync_request_statuses(db: sqlite3.Connection) -> None:
    ts = now_iso()
    for pos, (code, label, meaning, who_acts) in enumerate(REQUEST_STATUSES):
        db.execute(
            "INSERT INTO request_statuses (code, label, meaning, who_acts, position, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(code) DO UPDATE SET label = excluded.label, meaning = excluded.meaning, "
            "who_acts = excluded.who_acts, position = excluded.position, updated_at = excluded.updated_at "
            "WHERE label IS NOT excluded.label OR meaning IS NOT excluded.meaning "
            "OR who_acts IS NOT excluded.who_acts OR position IS NOT excluded.position",
            (code, label, meaning, who_acts, pos, ts, ts)
        )
    codes = [c for c, *_ in REQUEST_STATUSES]
    db.execute(f"DELETE FROM request_statuses WHERE code NOT IN ({','.join('?' * len(codes))})", codes)
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
