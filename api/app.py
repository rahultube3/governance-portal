"""
Governance Portal REST API
Flask + SQLite backend for architecture governance artifact intake & review.
"""
import json
import os
import secrets
import sqlite3
from datetime import datetime, date
from functools import wraps
from typing import Any, Callable

from flask import Flask, Response, request, jsonify, g, session, stream_with_context
from flask_cors import CORS

import anthropic

from knowledge import SYSTEM_PROMPT

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "governance.db")
SECRET_KEY_PATH = os.path.join(APP_DIR, ".secret_key")


def load_secret_key() -> bytes:
    env = os.environ.get("GOV_PORTAL_SECRET_KEY")
    if env:
        return env.encode()
    try:
        fd = os.open(SECRET_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    with open(SECRET_KEY_PATH, "rb") as f:
        return f.read()


app = Flask(__name__)
app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
CORS(app)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
ARTIFACT_TYPES = [
    "Architecture Review Board (ARB) Intake Request",
    "Data Architecture Intake Request",
    "Architecture Decision Record (ADR) Submission",
    "Messaging & Streaming Architecture Intake Request",
    "AI/ML Architecture Intake Request",
]

# Governance lifecycle statuses
LIFECYCLE = ["PENDING", "APPROVED FB", "APPROVED EA", "FOLLOW UP", "REWORK"]

PDLC_CHECKPOINTS = [
    "Inception", "Elaboration", "Construction", "Delivery"
]

# The API enforces these codes, so the catalog lives in code and is synced into the
# `permissions` table on startup; which role holds which permission lives only in the DB.
PERMISSION_CATALOG = [
    ("request:create",       "Requests",       "Create requests",            "Submit new intake requests."),
    ("request:view:own",     "Requests",       "View own requests",          "See requests you submitted."),
    ("request:view:all",     "Requests",       "View all requests",          "See every request in the portal."),
    ("request:edit:own",     "Requests",       "Edit own requests",          "Edit your own request while PENDING or in REWORK. Review fields excluded."),
    ("request:edit:all",     "Requests",       "Edit any request",           "Edit any request, including status, review dates and comments."),
    ("request:withdraw:own", "Requests",       "Withdraw own requests",      "Delete your own request while it is PENDING."),
    ("request:delete:all",   "Requests",       "Delete any request",         "Permanently delete any request."),
    ("request:resubmit",     "Review",         "Resubmit after rework",      "Move your own REWORK request back to PENDING."),
    ("request:review",       "Review",         "Review requests",            "Approve, reject or send back other people's requests."),
    ("board:card:edit",      "Team Board",     "Edit board cards",           "Add, edit, move and delete Team Board cards."),
    ("board:field:manage",   "Team Board",     "Manage board fields",        "Add, rename and delete Team Board fields and lanes."),
    ("insights:view",        "Insights",       "View insights",              "Open the Insights scorecard."),
    ("insights:export",      "Insights",       "Export insights",            "Download Insights data as CSV."),
    ("user:manage",          "Administration", "Manage users",               "Add, rename and delete users and set their group."),
    ("role:assign",          "Administration", "Assign permissions",         "Edit this permission matrix and the AD group mapping."),
]

DEFAULT_ROLES = [
    ("REQUESTOR", "Requestor", "AAD-GovPortal-Requestors", "Submits intakes and tracks their own requests.",
     ["request:create", "request:view:own", "request:edit:own", "request:withdraw:own", "request:resubmit"]),
    ("REVIEWER", "Reviewer", "AAD-GovPortal-Reviewers", "Reviews the queue and moves requests through the lifecycle.",
     ["request:view:all", "request:review", "board:card:edit", "insights:view"]),
    ("ADMIN", "Admin", "AAD-GovPortal-Admins", "Full access, including users and permissions.",
     [code for code, *_ in PERMISSION_CATALOG]),
]

# Fields only reviewers/admins decide; stripped unless the caller holds request:edit:all.
REVIEW_FIELDS = {"status", "dateReviewed", "approvalDate", "comments"}
REQUESTOR_EDITABLE_STATUSES = {"PENDING", "REWORK"}

# Every table carries created_at/created_by/updated_at/updated_by. A NULL *_by means the system
# wrote the row (seeding or the permission catalog sync), not a signed-in user.
AUDITED_TABLES = [
    "requests", "status_history", "users", "roles",
    "permissions", "role_permissions", "board_fields", "board_cards",
]

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

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            arb_title               TEXT NOT NULL,
            summary                 TEXT,
            artifact_link           TEXT,
            pr                      TEXT,
            app_id                  TEXT,
            app_name                TEXT,
            trackit_id              TEXT,
            solution_architect      TEXT,
            sa_contributors         TEXT,
            artifact_type           TEXT NOT NULL,
            pdlc_checkpoint         TEXT,
            date_submitted          TEXT NOT NULL,
            date_reviewed           TEXT,
            bu_gov_reviewer         TEXT,
            ea_gov_reviewer         TEXT,
            status                  TEXT NOT NULL DEFAULT 'PENDING',
            approval_date           TEXT,
            comments                TEXT,
            created_at              TEXT NOT NULL,
            updated_at              TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id   INTEGER NOT NULL,
            from_status  TEXT,
            to_status    TEXT NOT NULL,
            note         TEXT,
            created_at   TEXT NOT NULL,
            FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL UNIQUE,
            role        TEXT NOT NULL CHECK (role IN ('REQUESTOR', 'REVIEWER', 'ADMIN')),
            created_at  TEXT NOT NULL
        )
    """)
    # Kanban board tables (dynamic schema)
    db.execute("""
        CREATE TABLE IF NOT EXISTS board_fields (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            key       TEXT NOT NULL UNIQUE,
            label     TEXT NOT NULL,
            type      TEXT NOT NULL,
            options   TEXT,
            position  INTEGER NOT NULL DEFAULT 0,
            is_title  INTEGER NOT NULL DEFAULT 0,
            is_group  INTEGER NOT NULL DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS board_cards (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            data        TEXT NOT NULL,
            position    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            code         TEXT NOT NULL UNIQUE,
            name         TEXT NOT NULL,
            ad_group     TEXT,
            description  TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            code         TEXT PRIMARY KEY,
            category     TEXT NOT NULL,
            label        TEXT NOT NULL,
            description  TEXT,
            position     INTEGER NOT NULL DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id          INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_code  TEXT NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
            created_at       TEXT NOT NULL,
            created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
            PRIMARY KEY (role_id, permission_code)
        )
    """)
    rename_column_if_present(db, "status_history", "changed_at", "created_at")
    rename_column_if_present(db, "status_history", "changed_by", "created_by")
    user_fk = "INTEGER REFERENCES users(id) ON DELETE SET NULL"
    for table in AUDITED_TABLES:
        add_column_if_missing(db, table, "created_at", "TEXT")
        add_column_if_missing(db, table, "created_by", user_fk)
        add_column_if_missing(db, table, "updated_at", "TEXT")
        add_column_if_missing(db, table, "updated_by", user_fk)
    db.commit()
    seed_board_defaults(db)
    seed_users(db)
    backfill_request_owners(db)
    sync_permissions(db)
    seed_roles(db)
    backfill_audit_timestamps(db)
    db.close()


def add_column_if_missing(db: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def rename_column_if_present(db: sqlite3.Connection, table: str, old: str, new: str) -> None:
    cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    if old in cols and new not in cols:
        db.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")


# Rows that predate an audit column get the migration time as created_at; updated_at falls back to it.
def backfill_audit_timestamps(db: sqlite3.Connection) -> None:
    ts = now_iso()
    for table in AUDITED_TABLES:
        db.execute(f"UPDATE {table} SET created_at = ? WHERE created_at IS NULL", (ts,))
        db.execute(f"UPDATE {table} SET updated_at = created_at WHERE updated_at IS NULL")
    db.commit()


def seed_users(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    db.executemany(
        "INSERT INTO users (name, email, role, created_at, updated_at) VALUES (?,?,?,?,?)",
        [(n, e, r, ts, ts) for n, e, r in SEED_USERS]
    )
    db.commit()


def sync_permissions(db: sqlite3.Connection) -> None:
    ts = now_iso()
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
    codes = [c for c, *_ in PERMISSION_CATALOG]
    marks = ",".join("?" * len(codes))
    db.execute(f"DELETE FROM role_permissions WHERE permission_code NOT IN ({marks})", codes)
    db.execute(f"DELETE FROM permissions WHERE code NOT IN ({marks})", codes)
    db.commit()


def seed_roles(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM roles").fetchone()[0]:
        return
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
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


# Requests predating user accounts have no owner; match them to a requestor by architect name.
def backfill_request_owners(db: sqlite3.Connection) -> None:
    db.execute("""
        UPDATE requests SET created_by = (
            SELECT u.id FROM users u
            WHERE u.role = 'REQUESTOR' AND u.name = requests.solution_architect
        )
        WHERE created_by IS NULL
    """)
    db.commit()


def seed_board_defaults(db):
    existing = db.execute("SELECT COUNT(*) c FROM board_fields").fetchone()[0]
    if existing:
        return
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
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
        "INSERT INTO board_fields (key,label,type,options,position,is_title,is_group) "
        "VALUES (?,?,?,?,?,?,?)", defaults
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


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def row_to_dict(r):
    return {
        "id": r["id"],
        "arbTitle": r["arb_title"],
        "summary": r["summary"],
        "artifactLink": r["artifact_link"],
        "pr": r["pr"],
        "appId": r["app_id"],
        "appName": r["app_name"],
        "trackitId": r["trackit_id"],
        "solutionArchitect": r["solution_architect"],
        "saContributors": r["sa_contributors"],
        "artifactType": r["artifact_type"],
        "pdlcCheckpoint": r["pdlc_checkpoint"],
        "dateSubmitted": r["date_submitted"],
        "dateReviewed": r["date_reviewed"],
        "buGovReviewer": r["bu_gov_reviewer"],
        "eaGovReviewer": r["ea_gov_reviewer"],
        "status": r["status"],
        "approvalDate": r["approval_date"],
        "comments": r["comments"],
        "createdBy": r["created_by"],
        "updatedBy": r["updated_by"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ---------------------------------------------------------------------------
# Auth: demo sign-in (pick a user, no password) backed by a signed session cookie
# ---------------------------------------------------------------------------
PUBLIC_ENDPOINTS = {"/api/health", "/api/auth/users", "/api/auth/login", "/api/auth/logout"}


def user_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"]}


def audit_fields(r: sqlite3.Row) -> dict[str, Any]:
    return {"createdAt": r["created_at"], "createdBy": r["created_by"],
            "updatedAt": r["updated_at"], "updatedBy": r["updated_by"]}


# Demo sign-in stands in for Azure AD: a user's `role` column plays the part of their AD group
# membership. With Entra ID SSO, return the token's `groups` claim (saved in the session at login).
def ad_groups_for(user: sqlite3.Row) -> list[str]:
    r = get_db().execute("SELECT ad_group FROM roles WHERE code = ?", (user["role"],)).fetchone()
    return [r["ad_group"]] if r and r["ad_group"] else []


def resolve_access(groups: list[str]) -> tuple[list[str], set[str]]:
    if not groups:
        return [], set()
    rows = get_db().execute(
        "SELECT r.code, rp.permission_code FROM roles r "
        "LEFT JOIN role_permissions rp ON rp.role_id = r.id "
        f"WHERE r.ad_group IN ({','.join('?' * len(groups))})", groups
    ).fetchall()
    return sorted({row["code"] for row in rows}), {row["permission_code"] for row in rows if row["permission_code"]}


def session_payload(user: sqlite3.Row) -> dict[str, Any]:
    groups = ad_groups_for(user)
    roles, perms = resolve_access(groups)
    names = {r["code"]: r["name"] for r in get_db().execute("SELECT code, name FROM roles")}
    return {
        **user_to_dict(user), "adGroups": groups, "roles": roles,
        "roleNames": [names[c] for c in roles], "permissions": sorted(perms),
    }


@app.before_request
def load_user() -> Any:
    g.user = None
    g.permissions = set()
    uid = session.get("uid")
    if uid is not None:
        r = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if r:
            g.user = user_to_dict(r)
            g.permissions = resolve_access(ad_groups_for(r))[1]
        else:
            session.clear()
    if (request.path.startswith("/api/") and request.method != "OPTIONS"
            and request.path not in PUBLIC_ENDPOINTS and g.user is None):
        return jsonify({"error": "Sign in required"}), 401
    return None


def has(*perms: str) -> bool:
    return any(p in g.permissions for p in perms)


def require_permission(*perms: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not has(*perms):
                return jsonify({"error": "You do not have permission for this action"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco


def forbidden(msg: str) -> tuple[Response, int]:
    return jsonify({"error": msg}), 403


def owns(r: sqlite3.Row) -> bool:
    return r["created_by"] == g.user["id"]


# Requests the caller may not view look like 404s so IDs don't leak which requests exist.
def find_visible_request(req_id: int) -> sqlite3.Row | None:
    r = get_db().execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    if r and (has("request:view:all") or (has("request:view:own") and owns(r))):
        return r
    return None


@app.get("/api/auth/users")
def auth_directory() -> Response:
    rows = get_db().execute("SELECT * FROM users ORDER BY role, name").fetchall()
    return jsonify([user_to_dict(r) for r in rows])


@app.post("/api/auth/login")
def auth_login() -> Any:
    data = request.get_json(force=True) or {}
    r = get_db().execute("SELECT * FROM users WHERE id = ?", (data.get("userId"),)).fetchone()
    if not r:
        return jsonify({"error": "Unknown user"}), 400
    session.clear()
    session["uid"] = r["id"]
    return jsonify(session_payload(r))


@app.post("/api/auth/logout")
def auth_logout() -> Response:
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def auth_me() -> Response:
    r = get_db().execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    return jsonify(session_payload(r))


# ---------------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------------
def role_codes(db: sqlite3.Connection) -> list[str]:
    return [r["code"] for r in db.execute("SELECT code FROM roles ORDER BY id")]


# Mirrors resolve_access for every demo user: anyone whose group maps to a role holding role:assign.
def assign_holders(db: sqlite3.Connection) -> int:
    return db.execute("""
        SELECT COUNT(DISTINCT u.id) FROM users u
        JOIN roles ur ON ur.code = u.role
        JOIN roles er ON er.ad_group = ur.ad_group
        JOIN role_permissions rp ON rp.role_id = er.id AND rp.permission_code = 'role:assign'
        WHERE COALESCE(ur.ad_group, '') != ''
    """).fetchone()[0]


def commit_unless_locked_out(db: sqlite3.Connection) -> tuple[Response, int] | None:
    if assign_holders(db) == 0:
        db.rollback()
        return jsonify({"error": "This change would leave nobody able to assign permissions"}), 400
    db.commit()
    return None


@app.get("/api/roles")
@require_permission("user:manage", "role:assign")
def list_roles() -> Response:
    rows = get_db().execute("SELECT code, name, ad_group FROM roles ORDER BY id").fetchall()
    return jsonify([{"code": r["code"], "name": r["name"], "adGroup": r["ad_group"] or ""} for r in rows])


@app.get("/api/users")
@require_permission("user:manage")
def list_users() -> Response:
    rows = get_db().execute("SELECT * FROM users ORDER BY role, name").fetchall()
    return jsonify([{**user_to_dict(r), **audit_fields(r)} for r in rows])


@app.post("/api/users")
@require_permission("user:manage")
def create_user() -> Any:
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = data.get("role")
    db = get_db()
    if not name or "@" not in email:
        return jsonify({"error": "name and a valid email are required"}), 400
    if role not in role_codes(db):
        return jsonify({"error": f"role must be one of {role_codes(db)}"}), 400
    try:
        ts = now_iso()
        cur = db.execute(
            "INSERT INTO users (name, email, role, created_at, created_by, updated_at, updated_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (name, email, role, ts, g.user["id"], ts, g.user["id"])
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "a user with that email already exists"}), 400
    db.commit()
    r = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({**user_to_dict(r), **audit_fields(r)}), 201


@app.patch("/api/users/<int:uid>")
@require_permission("user:manage")
def update_user(uid: int) -> Any:
    data = request.get_json(force=True) or {}
    db = get_db()
    r = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404
    sets, params = [], []
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        sets.append("name = ?"); params.append(name)
    if "role" in data:
        if data["role"] not in role_codes(db):
            return jsonify({"error": f"role must be one of {role_codes(db)}"}), 400
        sets.append("role = ?"); params.append(data["role"])
    if sets:
        sets += ["updated_at = ?", "updated_by = ?"]
        params += [now_iso(), g.user["id"], uid]
        db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)
        locked = commit_unless_locked_out(db)
        if locked:
            return locked
    r = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return jsonify({**user_to_dict(r), **audit_fields(r)})


@app.delete("/api/users/<int:uid>")
@require_permission("user:manage")
def delete_user(uid: int) -> Any:
    if uid == g.user["id"]:
        return jsonify({"error": "you cannot delete your own account"}), 400
    db = get_db()
    if not db.execute("SELECT id FROM users WHERE id = ?", (uid,)).fetchone():
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM users WHERE id = ?", (uid,))
    locked = commit_unless_locked_out(db)
    if locked:
        return locked
    return jsonify({"deleted": uid})


# ---------------------------------------------------------------------------
# Roles, AD group mapping and the permission matrix
# ---------------------------------------------------------------------------
def rbac_snapshot() -> Response:
    db = get_db()
    perms = [{"code": r["code"], "category": r["category"], "label": r["label"], "description": r["description"]}
             for r in db.execute("SELECT * FROM permissions ORDER BY position")]
    grants: dict[int, dict[str, dict[str, Any]]] = {}
    for r in db.execute("SELECT role_id, permission_code, created_at, created_by FROM role_permissions"):
        grants.setdefault(r["role_id"], {})[r["permission_code"]] = {
            "grantedAt": r["created_at"], "grantedBy": r["created_by"]}
    members = {r["role"]: r["c"] for r in db.execute("SELECT role, COUNT(*) c FROM users GROUP BY role")}
    roles = [{
        "id": r["id"], "code": r["code"], "name": r["name"], "adGroup": r["ad_group"] or "",
        "description": r["description"], "permissions": sorted(grants.get(r["id"], {})),
        "grants": grants.get(r["id"], {}), "memberCount": members.get(r["code"], 0), **audit_fields(r),
    } for r in db.execute("SELECT * FROM roles ORDER BY id")]
    return jsonify({"permissions": perms, "roles": roles})


@app.get("/api/rbac")
@require_permission("role:assign")
def rbac_get() -> Response:
    return rbac_snapshot()


@app.put("/api/rbac/grants")
@require_permission("role:assign")
def rbac_set_grants() -> Any:
    grants = (request.get_json(force=True) or {}).get("grants")
    if not isinstance(grants, dict):
        return jsonify({"error": "grants must be an object of role code -> permission codes"}), 400
    db = get_db()
    roles = {r["code"]: r["id"] for r in db.execute("SELECT id, code FROM roles")}
    known = {r["code"] for r in db.execute("SELECT code FROM permissions")}
    for code, perms in grants.items():
        if code not in roles:
            return jsonify({"error": f"unknown role {code}"}), 400
        if not isinstance(perms, list) or not set(perms) <= known:
            return jsonify({"error": f"unknown permission for role {code}"}), 400

    ts, uid = now_iso(), g.user["id"]
    for code, perms in grants.items():
        role_id = roles[code]
        current = {r[0] for r in db.execute(
            "SELECT permission_code FROM role_permissions WHERE role_id = ?", (role_id,))}
        added, removed = set(perms) - current, current - set(perms)
        if not added and not removed:
            continue
        db.executemany(
            "INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by) "
            "VALUES (?,?,?,?,?,?)",
            [(role_id, p, ts, uid, ts, uid) for p in sorted(added)]
        )
        db.executemany(
            "DELETE FROM role_permissions WHERE role_id = ? AND permission_code = ?",
            [(role_id, p) for p in removed]
        )
        db.execute("UPDATE roles SET updated_at = ?, updated_by = ? WHERE id = ?", (ts, uid, role_id))
    locked = commit_unless_locked_out(db)
    return locked or rbac_snapshot()


@app.patch("/api/rbac/roles/<code>")
@require_permission("role:assign")
def rbac_update_role(code: str) -> Any:
    data = request.get_json(force=True) or {}
    db = get_db()
    if not db.execute("SELECT id FROM roles WHERE code = ?", (code,)).fetchone():
        return jsonify({"error": "Not found"}), 404
    sets, params = [], []
    if "adGroup" in data:
        ad_group = (data["adGroup"] or "").strip()
        if len(ad_group) > 256:
            return jsonify({"error": "adGroup is too long"}), 400
        sets.append("ad_group = ?"); params.append(ad_group or None)
    for key, col in (("name", "name"), ("description", "description")):
        if key in data:
            value = (data[key] or "").strip()
            if key == "name" and not value:
                return jsonify({"error": "name cannot be empty"}), 400
            sets.append(f"{col} = ?"); params.append(value)
    if sets:
        sets += ["updated_at = ?", "updated_by = ?"]
        params += [now_iso(), g.user["id"], code]
        db.execute(f"UPDATE roles SET {', '.join(sets)} WHERE code = ?", params)
        locked = commit_unless_locked_out(db)
        if locked:
            return locked
    return rbac_snapshot()


# ---------------------------------------------------------------------------
# Reference endpoints
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def meta():
    return jsonify({
        "artifactTypes": ARTIFACT_TYPES,
        "lifecycle": LIFECYCLE,
        "pdlcCheckpoints": PDLC_CHECKPOINTS,
    })


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": now_iso()})


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------
@app.get("/api/requests")
@require_permission("request:view:own", "request:view:all")
def list_requests():
    db = get_db()
    q = "SELECT * FROM requests"
    params = []
    filters = []

    status = request.args.get("status")
    artifact_type = request.args.get("artifactType")
    search = request.args.get("search")

    if not has("request:view:all"):
        filters.append("created_by = ?")
        params.append(g.user["id"])
    if status:
        filters.append("status = ?")
        params.append(status)
    if artifact_type:
        filters.append("artifact_type = ?")
        params.append(artifact_type)
    if search:
        filters.append("(arb_title LIKE ? OR summary LIKE ? OR app_name LIKE ? OR trackit_id LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like, like])

    if filters:
        q += " WHERE " + " AND ".join(filters)
    q += " ORDER BY updated_at DESC"

    rows = db.execute(q, params).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


def record_history(db: sqlite3.Connection, req_id: int, from_status: str | None,
                   to_status: str, note: str | None, ts: str) -> None:
    db.execute(
        "INSERT INTO status_history (request_id, from_status, to_status, note, "
        "created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?)",
        (req_id, from_status, to_status, note, ts, g.user["id"], ts, g.user["id"])
    )


@app.get("/api/requests/<int:req_id>")
def get_request(req_id):
    db = get_db()
    r = find_visible_request(req_id)
    if not r:
        return jsonify({"error": "Not found"}), 404
    data = row_to_dict(r)
    hist = db.execute(
        "SELECT from_status, to_status, note, created_at, created_by FROM status_history "
        "WHERE request_id = ? ORDER BY id ASC", (req_id,)
    ).fetchall()
    data["history"] = [dict(h) for h in hist]
    return jsonify(data)


@app.post("/api/requests")
@require_permission("request:create")
def create_request():
    data = request.get_json(force=True) or {}
    if not has("request:edit:all"):
        data = {k: v for k, v in data.items() if k not in REVIEW_FIELDS}

    if not data.get("arbTitle"):
        return jsonify({"error": "arbTitle is required"}), 400
    if data.get("artifactType") not in ARTIFACT_TYPES:
        return jsonify({"error": "Valid artifactType is required"}), 400

    status = data.get("status", "PENDING")
    if status not in LIFECYCLE:
        return jsonify({"error": f"status must be one of {LIFECYCLE}"}), 400

    ts = now_iso()
    date_submitted = data.get("dateSubmitted") or date.today().isoformat()

    db = get_db()
    cur = db.execute("""
        INSERT INTO requests (
            arb_title, summary, artifact_link, pr, app_id, app_name, trackit_id,
            solution_architect, sa_contributors, artifact_type, pdlc_checkpoint,
            date_submitted, date_reviewed, bu_gov_reviewer, ea_gov_reviewer,
            status, approval_date, comments, created_at, updated_at, created_by, updated_by
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("arbTitle"), data.get("summary"), data.get("artifactLink"),
        data.get("pr"), data.get("appId"), data.get("appName"),
        data.get("trackitId"), data.get("solutionArchitect"),
        data.get("saContributors"), data.get("artifactType"),
        data.get("pdlcCheckpoint"), date_submitted, data.get("dateReviewed"),
        data.get("buGovReviewer"), data.get("eaGovReviewer"), status,
        data.get("approvalDate"), data.get("comments"), ts, ts, g.user["id"], g.user["id"]
    ))
    req_id = cur.lastrowid
    record_history(db, req_id, None, status, "Created", ts)
    db.commit()
    r = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    return jsonify(row_to_dict(r)), 201


@app.put("/api/requests/<int:req_id>")
@require_permission("request:edit:own", "request:edit:all")
def update_request(req_id):
    data = request.get_json(force=True) or {}
    db = get_db()
    existing = find_visible_request(req_id)
    if not existing:
        return jsonify({"error": "Not found"}), 404
    if not has("request:edit:all"):
        if not owns(existing):
            return forbidden("You can only edit your own requests")
        if existing["status"] not in REQUESTOR_EDITABLE_STATUSES:
            return forbidden("Requests can only be edited while PENDING or in REWORK")
        data = {k: v for k, v in data.items() if k not in REVIEW_FIELDS}
    if "status" in data and data["status"] != existing["status"] and owns(existing):
        return forbidden("You cannot change the status of a request you submitted")

    field_map = {
        "arbTitle": "arb_title", "summary": "summary", "artifactLink": "artifact_link",
        "pr": "pr", "appId": "app_id", "appName": "app_name", "trackitId": "trackit_id",
        "solutionArchitect": "solution_architect", "saContributors": "sa_contributors",
        "artifactType": "artifact_type", "pdlcCheckpoint": "pdlc_checkpoint",
        "dateSubmitted": "date_submitted", "dateReviewed": "date_reviewed",
        "buGovReviewer": "bu_gov_reviewer", "eaGovReviewer": "ea_gov_reviewer",
        "status": "status", "approvalDate": "approval_date", "comments": "comments",
    }

    if "artifactType" in data and data["artifactType"] not in ARTIFACT_TYPES:
        return jsonify({"error": "Invalid artifactType"}), 400
    if "status" in data and data["status"] not in LIFECYCLE:
        return jsonify({"error": f"status must be one of {LIFECYCLE}"}), 400

    sets, params = [], []
    for k, col in field_map.items():
        if k in data:
            sets.append(f"{col} = ?")
            params.append(data[k])

    ts = now_iso()
    sets += ["updated_at = ?", "updated_by = ?"]
    params += [ts, g.user["id"], req_id]
    db.execute(f"UPDATE requests SET {', '.join(sets)} WHERE id = ?", params)

    # record status transition
    if "status" in data and data["status"] != existing["status"]:
        record_history(db, req_id, existing["status"], data["status"], data.get("comments"), ts)

    db.commit()
    r = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    return jsonify(row_to_dict(r))


@app.patch("/api/requests/<int:req_id>/status")
def change_status(req_id):
    data = request.get_json(force=True) or {}
    new_status = data.get("status")
    if new_status not in LIFECYCLE:
        return jsonify({"error": f"status must be one of {LIFECYCLE}"}), 400

    db = get_db()
    existing = find_visible_request(req_id)
    if not existing:
        return jsonify({"error": "Not found"}), 404

    ts = now_iso()
    resubmit = (existing["status"] == "REWORK" and new_status == "PENDING"
                and owns(existing) and has("request:resubmit"))
    if resubmit:
        db.execute("UPDATE requests SET status = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                   (new_status, ts, g.user["id"], req_id))
    else:
        if not has("request:review"):
            return forbidden("You do not have permission to review requests")
        if owns(existing):
            return forbidden("You cannot review a request you submitted")
        approval_date = existing["approval_date"]
        if new_status in ("APPROVED FB", "APPROVED EA") and not approval_date:
            approval_date = date.today().isoformat()
        db.execute(
            "UPDATE requests SET status = ?, approval_date = ?, date_reviewed = ?, "
            "updated_at = ?, updated_by = ? WHERE id = ?",
            (new_status, approval_date, data.get("dateReviewed") or date.today().isoformat(),
             ts, g.user["id"], req_id)
        )
    record_history(db, req_id, existing["status"], new_status, data.get("note"), ts)
    db.commit()
    r = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    return jsonify(row_to_dict(r))


@app.delete("/api/requests/<int:req_id>")
@require_permission("request:withdraw:own", "request:delete:all")
def delete_request(req_id):
    db = get_db()
    r = find_visible_request(req_id)
    if not r:
        return jsonify({"error": "Not found"}), 404
    if not (has("request:delete:all") or (owns(r) and r["status"] == "PENDING")):
        return forbidden("You can only withdraw your own requests while they are PENDING")
    db.execute("DELETE FROM requests WHERE id = ?", (req_id,))
    db.commit()
    return jsonify({"deleted": req_id})


# ---------------------------------------------------------------------------
# Chat with the governance documents (streams SSE)
# ---------------------------------------------------------------------------
CHAT_MODEL = os.environ.get("CHAT_MODEL", "claude-sonnet-4-6")
CHAT_MAX_TURNS = 40
CHAT_MAX_CHARS = 4000


def validate_chat_messages(raw: object) -> tuple[list[dict[str, str]] | None, str | None]:
    if not isinstance(raw, list) or not raw:
        return None, "messages must be a non-empty list"
    if len(raw) > CHAT_MAX_TURNS:
        raw = raw[-CHAT_MAX_TURNS:]
    out: list[dict[str, str]] = []
    for m in raw:
        if not isinstance(m, dict):
            return None, "each message must be an object"
        role, content = m.get("role"), m.get("content")
        if role not in ("user", "assistant"):
            return None, "role must be 'user' or 'assistant'"
        if not isinstance(content, str) or not content.strip():
            return None, "content must be a non-empty string"
        out.append({"role": role, "content": content[:CHAT_MAX_CHARS]})
    if out[0]["role"] != "user":
        return None, "first message must be from the user"
    return out, None


@app.post("/api/chat")
def chat() -> Response:
    data = request.get_json(force=True) or {}
    messages, err = validate_chat_messages(data.get("messages"))
    if err:
        return jsonify({"error": err}), 400

    client = anthropic.Anthropic()

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def generate():
        try:
            with client.messages.stream(
                model=CHAT_MODEL,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield sse({"text": text})
            yield sse({"done": True})
        # SDK raises TypeError when no api_key/auth_token/credentials resolve
        except TypeError:
            yield sse({"error": "Chat is not configured. Set ANTHROPIC_API_KEY on the API server."})
        except anthropic.AuthenticationError:
            yield sse({"error": "Chat is misconfigured: the API key was rejected."})
        except anthropic.APIStatusError as e:
            yield sse({"error": f"Assistant unavailable ({e.status_code}). Try again shortly."})
        except anthropic.APIConnectionError:
            yield sse({"error": "Could not reach the assistant. Check the API server's network."})
        except Exception:
            yield sse({"error": "Assistant failed unexpectedly. Try again."})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/stats")
@require_permission("request:view:own", "request:view:all")
def stats():
    db = get_db()
    where, params = ("", ()) if has("request:view:all") else ("WHERE created_by = ?", (g.user["id"],))
    by_status = {row["status"]: row["c"] for row in db.execute(
        f"SELECT status, COUNT(*) c FROM requests {where} GROUP BY status", params)}
    by_type = {row["artifact_type"]: row["c"] for row in db.execute(
        f"SELECT artifact_type, COUNT(*) c FROM requests {where} GROUP BY artifact_type", params)}
    total = db.execute(f"SELECT COUNT(*) c FROM requests {where}", params).fetchone()["c"]
    return jsonify({
        "total": total,
        "byStatus": {s: by_status.get(s, 0) for s in LIFECYCLE},
        "byType": {t: by_type.get(t, 0) for t in ARTIFACT_TYPES},
    })


# ---------------------------------------------------------------------------
# Kanban Board (dynamic schema)
# ---------------------------------------------------------------------------
BOARD_FIELD_TYPES = {"text", "number", "date", "select", "checkbox"}


def field_to_dict(r):
    return {
        "id": r["id"],
        "key": r["key"],
        "label": r["label"],
        "type": r["type"],
        "options": json.loads(r["options"]) if r["options"] else [],
        "position": r["position"],
        "isTitle": bool(r["is_title"]),
        "isGroup": bool(r["is_group"]),
        **audit_fields(r),
    }


def card_to_dict(r):
    return {
        "id": r["id"],
        "data": json.loads(r["data"] or "{}"),
        "position": r["position"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
        "createdBy": r["created_by"],
        "updatedBy": r["updated_by"],
    }


def slugify_key(label: str, existing: set) -> str:
    base = "".join(c if c.isalnum() else "_" for c in label.strip().lower()).strip("_") or "field"
    key, i = base, 2
    while key in existing:
        key = f"{base}_{i}"
        i += 1
    return key


@app.get("/api/board")
def board_get_all():
    db = get_db()
    fields = [field_to_dict(r) for r in db.execute(
        "SELECT * FROM board_fields ORDER BY position ASC, id ASC")]
    cards = [card_to_dict(r) for r in db.execute(
        "SELECT * FROM board_cards ORDER BY position ASC, id ASC")]
    return jsonify({"fields": fields, "cards": cards})


@app.post("/api/board/fields")
@require_permission("board:field:manage")
def board_create_field():
    data = request.get_json(force=True) or {}
    label = (data.get("label") or "").strip()
    ftype = data.get("type")
    if not label:
        return jsonify({"error": "label is required"}), 400
    if ftype not in BOARD_FIELD_TYPES:
        return jsonify({"error": f"type must be one of {sorted(BOARD_FIELD_TYPES)}"}), 400

    db = get_db()
    existing_keys = {r["key"] for r in db.execute("SELECT key FROM board_fields")}
    key = data.get("key") or slugify_key(label, existing_keys)
    if key in existing_keys:
        return jsonify({"error": "key already exists"}), 400

    options = data.get("options") or []
    if ftype != "select":
        options = []
    pos_row = db.execute("SELECT COALESCE(MAX(position), -1) + 1 AS p FROM board_fields").fetchone()
    pos = data.get("position", pos_row["p"])
    is_title = 1 if data.get("isTitle") else 0
    is_group = 1 if data.get("isGroup") else 0
    uid, ts = g.user["id"], now_iso()
    if is_title:
        db.execute("UPDATE board_fields SET is_title = 0, updated_at = ?, updated_by = ? "
                   "WHERE is_title = 1", (ts, uid))
    if is_group:
        db.execute("UPDATE board_fields SET is_group = 0, updated_at = ?, updated_by = ? "
                   "WHERE is_group = 1", (ts, uid))

    cur = db.execute(
        "INSERT INTO board_fields (key,label,type,options,position,is_title,is_group,"
        "created_at,created_by,updated_at,updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (key, label, ftype, json.dumps(options) if options else None, pos, is_title, is_group, ts, uid, ts, uid)
    )
    db.commit()
    r = db.execute("SELECT * FROM board_fields WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(field_to_dict(r)), 201


@app.patch("/api/board/fields/<int:fid>")
@require_permission("board:field:manage")
def board_update_field(fid):
    data = request.get_json(force=True) or {}
    db = get_db()
    r = db.execute("SELECT * FROM board_fields WHERE id = ?", (fid,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404

    sets, params = [], []
    if "label" in data:
        sets.append("label = ?"); params.append((data["label"] or "").strip() or r["label"])
    if "options" in data:
        opts = data["options"] or []
        sets.append("options = ?"); params.append(json.dumps(opts) if opts else None)
    if "position" in data:
        sets.append("position = ?"); params.append(int(data["position"]))
    uid, ts = g.user["id"], now_iso()
    if "isTitle" in data:
        if data["isTitle"]:
            db.execute("UPDATE board_fields SET is_title = 0, updated_at = ?, updated_by = ? "
                       "WHERE is_title = 1 AND id != ?", (ts, uid, fid))
        sets.append("is_title = ?"); params.append(1 if data["isTitle"] else 0)
    if "isGroup" in data:
        if data["isGroup"]:
            db.execute("UPDATE board_fields SET is_group = 0, updated_at = ?, updated_by = ? "
                       "WHERE is_group = 1 AND id != ?", (ts, uid, fid))
        sets.append("is_group = ?"); params.append(1 if data["isGroup"] else 0)

    if sets:
        sets += ["updated_at = ?", "updated_by = ?"]
        params += [ts, uid, fid]
        db.execute(f"UPDATE board_fields SET {', '.join(sets)} WHERE id = ?", params)
        db.commit()
    r = db.execute("SELECT * FROM board_fields WHERE id = ?", (fid,)).fetchone()
    return jsonify(field_to_dict(r))


@app.delete("/api/board/fields/<int:fid>")
@require_permission("board:field:manage")
def board_delete_field(fid):
    db = get_db()
    r = db.execute("SELECT * FROM board_fields WHERE id = ?", (fid,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404
    if r["is_title"] or r["is_group"]:
        return jsonify({"error": "cannot delete the title or grouping field; reassign first"}), 400
    key = r["key"]
    db.execute("DELETE FROM board_fields WHERE id = ?", (fid,))
    # strip the key from every card's data blob
    for c in db.execute("SELECT id, data FROM board_cards"):
        d = json.loads(c["data"] or "{}")
        if key in d:
            del d[key]
            db.execute("UPDATE board_cards SET data = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                       (json.dumps(d), now_iso(), g.user["id"], c["id"]))
    db.commit()
    return jsonify({"deleted": fid})


@app.post("/api/board/cards")
@require_permission("board:card:edit")
def board_create_card():
    payload = request.get_json(force=True) or {}
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return jsonify({"error": "data must be an object"}), 400
    db = get_db()
    ts = now_iso()
    pos_row = db.execute("SELECT COALESCE(MAX(position), -1) + 1 AS p FROM board_cards").fetchone()
    pos = payload.get("position", pos_row["p"])
    cur = db.execute(
        "INSERT INTO board_cards (data, position, created_at, updated_at, created_by, updated_by) "
        "VALUES (?,?,?,?,?,?)",
        (json.dumps(data), pos, ts, ts, g.user["id"], g.user["id"])
    )
    db.commit()
    r = db.execute("SELECT * FROM board_cards WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(card_to_dict(r)), 201


@app.patch("/api/board/cards/<int:cid>")
@require_permission("board:card:edit")
def board_update_card(cid):
    payload = request.get_json(force=True) or {}
    db = get_db()
    r = db.execute("SELECT * FROM board_cards WHERE id = ?", (cid,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404

    current = json.loads(r["data"] or "{}")
    if "data" in payload and isinstance(payload["data"], dict):
        current.update(payload["data"])
    ts = now_iso()
    position = payload.get("position", r["position"])
    db.execute(
        "UPDATE board_cards SET data = ?, position = ?, updated_at = ?, updated_by = ? WHERE id = ?",
        (json.dumps(current), position, ts, g.user["id"], cid)
    )
    db.commit()
    r = db.execute("SELECT * FROM board_cards WHERE id = ?", (cid,)).fetchone()
    return jsonify(card_to_dict(r))


@app.delete("/api/board/cards/<int:cid>")
@require_permission("board:card:edit")
def board_delete_card(cid):
    db = get_db()
    r = db.execute("SELECT id FROM board_cards WHERE id = ?", (cid,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM board_cards WHERE id = ?", (cid,))
    db.commit()
    return jsonify({"deleted": cid})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
