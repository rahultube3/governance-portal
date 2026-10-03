import re
import sqlite3
from typing import Any

from flask import Blueprint, Response, g, jsonify, request
from flask.typing import ResponseReturnValue

from portal.auth import commit_unless_locked_out, require_permission
from portal.db import get_db, now_iso
from portal.serializers import audit_fields

# Roles and the permission matrix.
bp = Blueprint("rbac", __name__)

ROLE_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,31}")


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


@bp.get("/rbac")
@require_permission("role:assign")
def rbac_get() -> Response:
    return rbac_snapshot()


@bp.put("/rbac/grants")
@require_permission("role:assign")
def rbac_set_grants() -> ResponseReturnValue:
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



@bp.post("/rbac/roles")
@require_permission("role:assign")
def rbac_create_role() -> ResponseReturnValue:
    data = request.get_json(force=True) or {}
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    ad_group = (data.get("adGroup") or "").strip()
    description = (data.get("description") or "").strip()
    perms = data.get("permissions", [])
    if not ROLE_CODE.fullmatch(code):
        return jsonify({"error": "code must be 2-32 letters, digits or underscores, starting with a letter"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400
    if len(ad_group) > 256:
        return jsonify({"error": "adGroup is too long"}), 400
    db = get_db()
    known = {r["code"] for r in db.execute("SELECT code FROM permissions")}
    if not isinstance(perms, list) or not set(perms) <= known:
        return jsonify({"error": "permissions must be a list of known permission codes"}), 400

    ts, uid = now_iso(), g.user["id"]
    try:
        cur = db.execute(
            "INSERT INTO roles (code, name, ad_group, description, created_at, created_by, updated_at, updated_by) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (code, name, ad_group or None, description, ts, uid, ts, uid)
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": f"a role with code {code} already exists"}), 400
    db.executemany(
        "INSERT INTO role_permissions (role_id, permission_code, created_at, created_by, updated_at, updated_by) "
        "VALUES (?,?,?,?,?,?)",
        [(cur.lastrowid, p, ts, uid, ts, uid) for p in sorted(set(perms))]
    )
    db.commit()
    return rbac_snapshot(), 201
