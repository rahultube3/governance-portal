from flask import Blueprint, Response, g, jsonify, request, session
from flask.typing import ResponseReturnValue

from portal.auth import session_payload
from portal.db import get_db
from portal.serializers import user_to_dict

# Demo sign-in (pick a user, no password) backed by a signed session cookie.
bp = Blueprint("auth", __name__)


@bp.get("/auth/users")
def auth_directory() -> Response:
    rows = get_db().execute("SELECT * FROM users ORDER BY role, name").fetchall()
    return jsonify([user_to_dict(r) for r in rows])



# Public so the sign-in page can group the directory by role before anyone is signed in.
@bp.get("/auth/roles")
def auth_roles() -> Response:
    rows = get_db().execute("SELECT code, name, description FROM roles ORDER BY id").fetchall()
    return jsonify([{"code": r["code"], "name": r["name"], "description": r["description"] or ""} for r in rows])

@bp.post("/auth/login")
def auth_login() -> ResponseReturnValue:
    data = request.get_json(force=True) or {}
    r = get_db().execute("SELECT * FROM users WHERE id = ?", (data.get("userId"),)).fetchone()
    if not r:
        return jsonify({"error": "Unknown user"}), 400
    session.clear()
    session["uid"] = r["id"]
    return jsonify(session_payload(r))


@bp.post("/auth/logout")
def auth_logout() -> Response:
    session.clear()
    return jsonify({"ok": True})


@bp.get("/auth/me")
def auth_me() -> Response:
    r = get_db().execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    return jsonify(session_payload(r))
