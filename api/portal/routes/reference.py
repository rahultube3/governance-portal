import json
import re
import sqlite3
from typing import Any

from flask import Blueprint, Response, g, jsonify, request
from flask.typing import ResponseReturnValue

from portal.auth import require_permission
from portal.constants import DEACTIVATABLE_STATUSES, REVIEWER_ROLES
from portal.db import get_db, now_iso
from portal.routes.meta import status_to_dict, status_usage
from portal.serializers import audit_fields

# The Reference Data admin page: review types, PDLC checkpoints, Architecture Reference Link names and reviewers
# (add, edit, order, activate, deactivate, remove), plus the text of the fixed lifecycle statuses.
# Requests store names (codes for reference links), so a rename is carried onto the requests that use it, and
# anything a request uses can be deactivated but not removed.
bp = Blueprint("reference", __name__)

ROLE_COLUMNS = {code: column for code, _, _, column in REVIEWER_ROLES}
MAX_NAME = 120
Error = tuple[Response, int]


def bad(message: str, status: int = 400) -> Error:
    return jsonify({"error": message}), status


def body() -> dict[str, Any]:
    data = request.get_json(force=True, silent=True)
    return data if isinstance(data, dict) else {}


def clean_name(value: object, what: str = "name") -> tuple[str, Error | None]:
    name = value.strip() if isinstance(value, str) else ""
    if not name or len(name) > MAX_NAME:
        return "", bad(f"{what} is required (at most {MAX_NAME} characters)")
    return name, None


def clean_active(data: dict[str, Any]) -> Error | None:
    if "active" in data and not isinstance(data["active"], bool):
        return bad("active must be true or false")
    return None


def in_use(count: int, what: str) -> Error:
    noun = "request uses" if count == 1 else "requests use"
    return bad(f"{count} {noun} {what}, so it can't be removed. Deactivate it instead.", 409)


def stamp() -> tuple[str, int]:
    return now_iso(), g.user["id"]


# Sets `position` from the order the ids are listed in; the list must name every row exactly once.
def reorder(db: sqlite3.Connection, table: str, key: str, keys: object) -> Error | None:
    existing = {r[0] for r in db.execute(f"SELECT {key} FROM {table}")}
    if not isinstance(keys, list) or len(keys) != len(existing) or set(keys) != existing:
        return bad(f"order must list every {key} exactly once")
    ts, uid = stamp()
    db.executemany(f"UPDATE {table} SET position = ?, updated_at = ?, updated_by = ? WHERE {key} = ?",
                   [(pos, ts, uid, k) for pos, k in enumerate(keys)])
    db.commit()
    return None


# ---- Review types ---------------------------------------------------------------------------------------------

def type_usage(db: sqlite3.Connection) -> dict[str, int]:
    return {r[0]: r[1] for r in db.execute("SELECT artifact_type, COUNT(*) FROM requests GROUP BY artifact_type")}


def review_type_to_dict(r: sqlite3.Row, usage: dict[str, int]) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "active": bool(r["active"]), "inUse": usage.get(r["name"], 0),
            **audit_fields(r)}


def fetch(db: sqlite3.Connection, table: str, row_id: object, key: str = "id") -> sqlite3.Row | None:
    return db.execute(f"SELECT * FROM {table} WHERE {key} = ?", (row_id,)).fetchone()


def name_taken(db: sqlite3.Connection, table: str, name: str, row_id: int | None = None) -> bool:
    return db.execute(f"SELECT 1 FROM {table} WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
                      (name, row_id)).fetchone() is not None


# Review type names appear in artifact_names.required_for; `rename` maps old -> new (None drops it).
def rewrite_required_for(db: sqlite3.Connection, old: str, new: str | None, ts: str, uid: int) -> None:
    for r in db.execute("SELECT code, required_for FROM artifact_names").fetchall():
        types = json.loads(r["required_for"])
        if old in types:
            types = [new if t == old else t for t in types if t != old or new]
            db.execute("UPDATE artifact_names SET required_for = ?, updated_at = ?, updated_by = ? WHERE code = ?",
                       (json.dumps(types), ts, uid, r["code"]))


@bp.get("/review-types")
@require_permission("reference:manage")
def list_review_types() -> Response:
    db = get_db()
    usage = type_usage(db)
    rows = db.execute("SELECT * FROM review_types ORDER BY name COLLATE NOCASE").fetchall()
    return jsonify([review_type_to_dict(r, usage) for r in rows])


@bp.post("/review-types")
@require_permission("reference:manage")
def create_review_type() -> ResponseReturnValue:
    name, err = clean_name(body().get("name"))
    if err:
        return err
    db = get_db()
    if name_taken(db, "review_types", name):
        return bad(f"{name} already exists", 409)
    ts, uid = stamp()
    cur = db.execute("INSERT INTO review_types (name, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?)",
                     (name, ts, uid, ts, uid))
    db.commit()
    return jsonify(review_type_to_dict(fetch(db, "review_types", cur.lastrowid), type_usage(db))), 201


@bp.patch("/review-types/<int:type_id>")
@require_permission("reference:manage")
def update_review_type(type_id: int) -> ResponseReturnValue:
    data = body()
    db = get_db()
    row = fetch(db, "review_types", type_id)
    if not row:
        return bad("Not found", 404)
    err = clean_active(data)
    if err:
        return err
    ts, uid = stamp()
    if "name" in data:
        name, err = clean_name(data["name"])
        if err:
            return err
        if name_taken(db, "review_types", name, type_id):
            return bad(f"{name} already exists", 409)
        if name != row["name"]:
            db.execute("UPDATE requests SET artifact_type = ? WHERE artifact_type = ?", (name, row["name"]))
            rewrite_required_for(db, row["name"], name, ts, uid)
            db.execute("UPDATE review_types SET name = ? WHERE id = ?", (name, type_id))
    if "active" in data:
        db.execute("UPDATE review_types SET active = ? WHERE id = ?", (int(data["active"]), type_id))
    db.execute("UPDATE review_types SET updated_at = ?, updated_by = ? WHERE id = ?", (ts, uid, type_id))
    db.commit()
    return jsonify(review_type_to_dict(fetch(db, "review_types", type_id), type_usage(db)))


@bp.delete("/review-types/<int:type_id>")
@require_permission("reference:manage")
def delete_review_type(type_id: int) -> ResponseReturnValue:
    db = get_db()
    row = fetch(db, "review_types", type_id)
    if not row:
        return bad("Not found", 404)
    count = type_usage(db).get(row["name"], 0)
    if count:
        return in_use(count, row["name"])
    ts, uid = stamp()
    rewrite_required_for(db, row["name"], None, ts, uid)
    db.execute("DELETE FROM review_types WHERE id = ?", (type_id,))
    db.commit()
    return jsonify({"deleted": type_id})


# ---- PDLC checkpoints -----------------------------------------------------------------------------------------

def pdlc_usage(db: sqlite3.Connection) -> dict[str, int]:
    return {r[0]: r[1] for r in db.execute("SELECT pdlc_checkpoint, COUNT(*) FROM requests GROUP BY pdlc_checkpoint")}


def pdlc_to_dict(r: sqlite3.Row, usage: dict[str, int]) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "position": r["position"], "active": bool(r["active"]),
            "inUse": usage.get(r["name"], 0), **audit_fields(r)}


@bp.get("/pdlc-checkpoints")
@require_permission("reference:manage")
def list_pdlc() -> Response:
    db = get_db()
    usage = pdlc_usage(db)
    return jsonify([pdlc_to_dict(r, usage) for r in db.execute("SELECT * FROM pdlc_checkpoints ORDER BY position, id")])


@bp.post("/pdlc-checkpoints")
@require_permission("reference:manage")
def create_pdlc() -> ResponseReturnValue:
    name, err = clean_name(body().get("name"))
    if err:
        return err
    db = get_db()
    if name_taken(db, "pdlc_checkpoints", name):
        return bad(f"{name} already exists", 409)
    ts, uid = stamp()
    position = db.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM pdlc_checkpoints").fetchone()[0]
    cur = db.execute("INSERT INTO pdlc_checkpoints (name, position, created_at, created_by, updated_at, updated_by) "
                     "VALUES (?,?,?,?,?,?)", (name, position, ts, uid, ts, uid))
    db.commit()
    return jsonify(pdlc_to_dict(fetch(db, "pdlc_checkpoints", cur.lastrowid), pdlc_usage(db))), 201


@bp.put("/pdlc-checkpoints/order")
@require_permission("reference:manage")
def order_pdlc() -> ResponseReturnValue:
    db = get_db()
    err = reorder(db, "pdlc_checkpoints", "id", body().get("order"))
    return err or list_pdlc()


@bp.patch("/pdlc-checkpoints/<int:pdlc_id>")
@require_permission("reference:manage")
def update_pdlc(pdlc_id: int) -> ResponseReturnValue:
    data = body()
    db = get_db()
    row = fetch(db, "pdlc_checkpoints", pdlc_id)
    if not row:
        return bad("Not found", 404)
    err = clean_active(data)
    if err:
        return err
    if "name" in data:
        name, err = clean_name(data["name"])
        if err:
            return err
        if name_taken(db, "pdlc_checkpoints", name, pdlc_id):
            return bad(f"{name} already exists", 409)
        db.execute("UPDATE requests SET pdlc_checkpoint = ? WHERE pdlc_checkpoint = ?", (name, row["name"]))
        db.execute("UPDATE pdlc_checkpoints SET name = ? WHERE id = ?", (name, pdlc_id))
    if "active" in data:
        db.execute("UPDATE pdlc_checkpoints SET active = ? WHERE id = ?", (int(data["active"]), pdlc_id))
    db.execute("UPDATE pdlc_checkpoints SET updated_at = ?, updated_by = ? WHERE id = ?", (*stamp(), pdlc_id))
    db.commit()
    return jsonify(pdlc_to_dict(fetch(db, "pdlc_checkpoints", pdlc_id), pdlc_usage(db)))


@bp.delete("/pdlc-checkpoints/<int:pdlc_id>")
@require_permission("reference:manage")
def delete_pdlc(pdlc_id: int) -> ResponseReturnValue:
    db = get_db()
    row = fetch(db, "pdlc_checkpoints", pdlc_id)
    if not row:
        return bad("Not found", 404)
    count = pdlc_usage(db).get(row["name"], 0)
    if count:
        return in_use(count, row["name"])
    db.execute("DELETE FROM pdlc_checkpoints WHERE id = ?", (pdlc_id,))
    db.commit()
    return jsonify({"deleted": pdlc_id})


# ---- Architecture Reference Link names ------------------------------------------------------------------------

def artifact_usage(db: sqlite3.Connection) -> dict[str, int]:
    return {r[0]: r[1] for r in db.execute(
        "SELECT json_extract(j.value, '$.code'), COUNT(DISTINCT requests.id) "
        "FROM requests, json_each(requests.artifacts) j GROUP BY 1")}


def artifact_name_to_dict(r: sqlite3.Row, usage: dict[str, int]) -> dict[str, Any]:
    return {"code": r["code"], "label": r["label"], "requiredFor": json.loads(r["required_for"]),
            "active": bool(r["active"]), "position": r["position"], "inUse": usage.get(r["code"], 0),
            **audit_fields(r)}


def clean_required_for(db: sqlite3.Connection, value: object) -> tuple[list[str], Error | None]:
    types = {r[0] for r in db.execute("SELECT name FROM review_types")}
    if not isinstance(value, list) or not all(isinstance(t, str) and t in types for t in value):
        return [], bad("requiredFor must be a list of review type names")
    return list(dict.fromkeys(value)), None


# A new entry's code is derived from its label, e.g. "Threat Model" -> THREAT_MODEL (THREAT_MODEL_2 if taken).
def new_code(db: sqlite3.Connection, table: str, label: str) -> str:
    base = re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")[:30] or "CODE"
    code, n = base, 1
    while fetch(db, table, code, "code"):
        n += 1
        code = f"{base}_{n}"
    return code


@bp.get("/artifact-names")
@require_permission("reference:manage")
def list_artifact_names() -> Response:
    db = get_db()
    usage = artifact_usage(db)
    return jsonify([artifact_name_to_dict(r, usage)
                    for r in db.execute("SELECT * FROM artifact_names ORDER BY position, code")])


@bp.post("/artifact-names")
@require_permission("reference:manage")
def create_artifact_name() -> ResponseReturnValue:
    data = body()
    label, err = clean_name(data.get("label"), "label")
    if err:
        return err
    db = get_db()
    required_for, err = clean_required_for(db, data.get("requiredFor", []))
    if err:
        return err
    if db.execute("SELECT 1 FROM artifact_names WHERE label = ? COLLATE NOCASE", (label,)).fetchone():
        return bad(f"{label} already exists", 409)
    ts, uid = stamp()
    code = new_code(db, "artifact_names", label)
    position = db.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM artifact_names").fetchone()[0]
    db.execute("INSERT INTO artifact_names (code, label, required_for, position, created_at, created_by, updated_at, "
               "updated_by) VALUES (?,?,?,?,?,?,?,?)", (code, label, json.dumps(required_for), position, ts, uid, ts, uid))
    db.commit()
    return jsonify(artifact_name_to_dict(fetch(db, "artifact_names", code, "code"), artifact_usage(db))), 201


@bp.put("/artifact-names/order")
@require_permission("reference:manage")
def order_artifact_names() -> ResponseReturnValue:
    db = get_db()
    err = reorder(db, "artifact_names", "code", body().get("order"))
    return err or list_artifact_names()


@bp.patch("/artifact-names/<code>")
@require_permission("reference:manage")
def update_artifact_name(code: str) -> ResponseReturnValue:
    data = body()
    db = get_db()
    if not fetch(db, "artifact_names", code, "code"):
        return bad("Not found", 404)
    err = clean_active(data)
    if err:
        return err
    sets: list[str] = []
    params: list[Any] = []
    if "label" in data:
        label, err = clean_name(data["label"], "label")
        if err:
            return err
        if db.execute("SELECT 1 FROM artifact_names WHERE label = ? COLLATE NOCASE AND code != ?",
                      (label, code)).fetchone():
            return bad(f"{label} already exists", 409)
        sets.append("label = ?")
        params.append(label)
    if "requiredFor" in data:
        required_for, err = clean_required_for(db, data["requiredFor"])
        if err:
            return err
        sets.append("required_for = ?")
        params.append(json.dumps(required_for))
    if "active" in data:
        sets.append("active = ?")
        params.append(int(data["active"]))
    ts, uid = stamp()
    db.execute(f"UPDATE artifact_names SET {', '.join([*sets, 'updated_at = ?', 'updated_by = ?'])} WHERE code = ?",
               [*params, ts, uid, code])
    db.commit()
    return jsonify(artifact_name_to_dict(fetch(db, "artifact_names", code, "code"), artifact_usage(db)))


@bp.delete("/artifact-names/<code>")
@require_permission("reference:manage")
def delete_artifact_name(code: str) -> ResponseReturnValue:
    db = get_db()
    row = fetch(db, "artifact_names", code, "code")
    if not row:
        return bad("Not found", 404)
    count = artifact_usage(db).get(code, 0)
    if count:
        return in_use(count, row["label"])
    db.execute("DELETE FROM artifact_names WHERE code = ?", (code,))
    db.commit()
    return jsonify({"deleted": code})


# ---- Reviewers -------------------------------------------------------------------------------------------------

# How many requests name each (role, reviewer name).
def reviewer_usage(db: sqlite3.Connection) -> dict[tuple[str, str], int]:
    usage = {}
    for role, column in ROLE_COLUMNS.items():
        for name, count in db.execute(f"SELECT j.value, COUNT(*) FROM requests, json_each(requests.{column}) j GROUP BY 1"):
            usage[(role, name)] = count
    return usage


def reviewer_to_dict(r: sqlite3.Row, usage: dict[tuple[str, str], int]) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "role": r["role"], "active": bool(r["active"]),
            "inUse": usage.get((r["role"], r["name"]), 0), **audit_fields(r)}


def reviewer_taken(db: sqlite3.Connection, role: str, name: str, row_id: int | None = None) -> bool:
    return db.execute("SELECT 1 FROM reviewers WHERE role = ? AND name = ? COLLATE NOCASE AND id IS NOT ?",
                      (role, name, row_id)).fetchone() is not None


@bp.get("/reviewers")
@require_permission("reference:manage")
def list_reviewers() -> Response:
    db = get_db()
    usage = reviewer_usage(db)
    rows = db.execute("SELECT * FROM reviewers ORDER BY role, name COLLATE NOCASE").fetchall()
    return jsonify([reviewer_to_dict(r, usage) for r in rows])


@bp.post("/reviewers")
@require_permission("reference:manage")
def create_reviewer() -> ResponseReturnValue:
    data = body()
    name, err = clean_name(data.get("name"))
    if err:
        return err
    role = data.get("role")
    if role not in ROLE_COLUMNS:
        return bad(f"role must be one of {list(ROLE_COLUMNS)}")
    db = get_db()
    if reviewer_taken(db, role, name):
        return bad(f"{name} is already a {role} reviewer", 409)
    ts, uid = stamp()
    cur = db.execute("INSERT INTO reviewers (name, role, created_at, created_by, updated_at, updated_by) "
                     "VALUES (?,?,?,?,?,?)", (name, role, ts, uid, ts, uid))
    db.commit()
    return jsonify(reviewer_to_dict(fetch(db, "reviewers", cur.lastrowid), reviewer_usage(db))), 201


@bp.patch("/reviewers/<int:reviewer_id>")
@require_permission("reference:manage")
def update_reviewer(reviewer_id: int) -> ResponseReturnValue:
    data = body()
    db = get_db()
    row = fetch(db, "reviewers", reviewer_id)
    if not row:
        return bad("Not found", 404)
    err = clean_active(data)
    if err:
        return err
    if "name" in data:
        name, err = clean_name(data["name"])
        if err:
            return err
        if reviewer_taken(db, row["role"], name, reviewer_id):
            return bad(f"{name} is already a {row['role']} reviewer", 409)
        column = ROLE_COLUMNS[row["role"]]
        for r in db.execute(f"SELECT id, {column} FROM requests WHERE EXISTS "
                            f"(SELECT 1 FROM json_each(requests.{column}) j WHERE j.value = ?)", (row["name"],)).fetchall():
            names = [name if n == row["name"] else n for n in json.loads(r[column])]
            db.execute(f"UPDATE requests SET {column} = ? WHERE id = ?", (json.dumps(names), r["id"]))
        db.execute("UPDATE reviewers SET name = ? WHERE id = ?", (name, reviewer_id))
    if "active" in data:
        db.execute("UPDATE reviewers SET active = ? WHERE id = ?", (int(data["active"]), reviewer_id))
    db.execute("UPDATE reviewers SET updated_at = ?, updated_by = ? WHERE id = ?", (*stamp(), reviewer_id))
    db.commit()
    return jsonify(reviewer_to_dict(fetch(db, "reviewers", reviewer_id), reviewer_usage(db)))


@bp.delete("/reviewers/<int:reviewer_id>")
@require_permission("reference:manage")
def delete_reviewer(reviewer_id: int) -> ResponseReturnValue:
    db = get_db()
    row = fetch(db, "reviewers", reviewer_id)
    if not row:
        return bad("Not found", 404)
    count = reviewer_usage(db).get((row["role"], row["name"]), 0)
    if count:
        return in_use(count, row["name"])
    db.execute("DELETE FROM reviewers WHERE id = ?", (reviewer_id,))
    db.commit()
    return jsonify({"deleted": reviewer_id})


# ---- Lifecycle statuses ----------------------------------------------------------------------------------------
# Built-in statuses: text editable, and the optional outcomes (DEACTIVATABLE_STATUSES) can be deactivated.
# Admin-added statuses are pause steps (portal/workflow.py): editable, deactivatable, and removable while no
# request is in one or has ever been.

STATUS_TEXT = {"label": ("label", 60), "meaning": ("meaning", 200), "whoActs": ("who_acts", 120)}


def clean_status_text(data: dict[str, Any], required: bool) -> tuple[dict[str, str], Error | None]:
    out = {}
    for key, (column, limit) in STATUS_TEXT.items():
        if key not in data and not required:
            continue
        value = data.get(key).strip() if isinstance(data.get(key), str) else ""
        if not value or len(value) > limit:
            return {}, bad(f"{key} is required (at most {limit} characters)")
        out[column] = value
    return out, None


def status_json(db: sqlite3.Connection, code: str) -> Response:
    return jsonify(status_to_dict(fetch(db, "request_statuses", code, "code"), status_usage(db)))


@bp.post("/request-statuses")
@require_permission("reference:manage")
def create_status() -> ResponseReturnValue:
    text, err = clean_status_text(body(), required=True)
    if err:
        return err
    db = get_db()
    if db.execute("SELECT 1 FROM request_statuses WHERE label = ? COLLATE NOCASE", (text["label"],)).fetchone():
        return bad(f"{text['label']} already exists", 409)
    ts, uid = stamp()
    code = new_code(db, "request_statuses", text["label"])
    position = db.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM request_statuses").fetchone()[0]
    db.execute("INSERT INTO request_statuses (code, label, meaning, who_acts, position, builtin, created_at, created_by, "
               "updated_at, updated_by) VALUES (?,?,?,?,?,0,?,?,?,?)",
               (code, text["label"], text["meaning"], text["who_acts"], position, ts, uid, ts, uid))
    db.commit()
    return status_json(db, code), 201


@bp.patch("/request-statuses/<code>")
@require_permission("reference:manage")
def update_status(code: str) -> ResponseReturnValue:
    data = body()
    db = get_db()
    row = fetch(db, "request_statuses", code, "code")
    if not row:
        return bad("Not found", 404)
    text, err = clean_status_text(data, required=False)
    if err:
        return err
    err = clean_active(data)
    if err:
        return err
    if "label" in text and db.execute("SELECT 1 FROM request_statuses WHERE label = ? COLLATE NOCASE AND code != ?",
                                      (text["label"], code)).fetchone():
        return bad(f"{text['label']} already exists", 409)
    if "active" in data and row["builtin"] and code not in DEACTIVATABLE_STATUSES:
        return bad(f"{row['label']} is part of the review route and can't be deactivated")
    sets = [f"{column} = ?" for column in text]
    params: list[Any] = list(text.values())
    if "active" in data:
        sets.append("active = ?")
        params.append(int(data["active"]))
    if not sets:
        return bad("send label, meaning, whoActs and/or active")
    ts, uid = stamp()
    db.execute(f"UPDATE request_statuses SET {', '.join(sets)}, updated_at = ?, updated_by = ? WHERE code = ?",
               [*params, ts, uid, code])
    db.commit()
    return status_json(db, code)


@bp.delete("/request-statuses/<code>")
@require_permission("reference:manage")
def delete_status(code: str) -> ResponseReturnValue:
    db = get_db()
    row = fetch(db, "request_statuses", code, "code")
    if not row:
        return bad("Not found", 404)
    if row["builtin"]:
        return bad(f"{row['label']} is part of the review route and can't be removed")
    count = status_usage(db).get(code, 0)
    if count:
        return in_use(count, row["label"])
    if db.execute("SELECT 1 FROM status_history WHERE from_status = ? OR to_status = ?", (code, code)).fetchone():
        return bad(f"{row['label']} appears in request history, so it can't be removed. Deactivate it instead.", 409)
    db.execute("DELETE FROM request_statuses WHERE code = ?", (code,))
    db.commit()
    return jsonify({"deleted": code})
