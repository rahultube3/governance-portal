import sqlite3
from functools import wraps
from typing import Any, Callable

from flask import Response, g, jsonify, request, session
from flask.typing import ResponseReturnValue

from portal.config import API_PREFIX
from portal.db import get_db
from portal.serializers import user_to_dict

PUBLIC_ENDPOINTS = {f"{API_PREFIX}{p}" for p in ("/health", "/auth/users", "/auth/roles", "/auth/login", "/auth/logout")}


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


def load_user() -> ResponseReturnValue | None:
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
    if (request.path.startswith(f"{API_PREFIX}/") and request.method != "OPTIONS"
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
