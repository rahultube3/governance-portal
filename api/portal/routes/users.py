import sqlite3

from flask import Blueprint, Response, g, jsonify, request
from flask.typing import ResponseReturnValue

from portal.auth import commit_unless_locked_out, require_permission, role_codes
from portal.db import get_db, now_iso
from portal.serializers import audit_fields, user_to_dict

bp = Blueprint("users", __name__)


@bp.get("/roles")
@require_permission("user:manage", "role:assign")
def list_roles() -> Response:
    rows = get_db().execute("SELECT code, name, ad_group FROM roles ORDER BY id").fetchall()
    return jsonify([{"code": r["code"], "name": r["name"], "adGroup": r["ad_group"] or ""} for r in rows])


@bp.get("/users")
@require_permission("user:manage")
def list_users() -> Response:
    rows = get_db().execute("SELECT * FROM users ORDER BY role, name").fetchall()
    return jsonify([{**user_to_dict(r), **audit_fields(r)} for r in rows])


@bp.post("/users")
@require_permission("user:manage")
def create_user() -> ResponseReturnValue:
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


@bp.patch("/users/<int:uid>")
@require_permission("user:manage")
def update_user(uid: int) -> ResponseReturnValue:
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


@bp.delete("/users/<int:uid>")
@require_permission("user:manage")
def delete_user(uid: int) -> ResponseReturnValue:
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
