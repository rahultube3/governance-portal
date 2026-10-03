import json

from flask import Blueprint, Response, g, jsonify, request
from flask.typing import ResponseReturnValue

from portal.auth import require_permission
from portal.db import get_db, now_iso
from portal.serializers import card_to_dict, field_to_dict

# Kanban board with a user-defined field schema.
bp = Blueprint("board", __name__)

BOARD_FIELD_TYPES = {"text", "number", "date", "select", "checkbox"}


def slugify_key(label: str, existing: set[str]) -> str:
    base = "".join(c if c.isalnum() else "_" for c in label.strip().lower()).strip("_") or "field"
    key, i = base, 2
    while key in existing:
        key = f"{base}_{i}"
        i += 1
    return key


@bp.get("/board")
def board_get_all() -> Response:
    db = get_db()
    fields = [field_to_dict(r) for r in db.execute(
        "SELECT * FROM board_fields ORDER BY position ASC, id ASC")]
    cards = [card_to_dict(r) for r in db.execute(
        "SELECT * FROM board_cards ORDER BY position ASC, id ASC")]
    return jsonify({"fields": fields, "cards": cards})


@bp.post("/board/fields")
@require_permission("board:field:manage")
def board_create_field() -> ResponseReturnValue:
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


@bp.patch("/board/fields/<int:fid>")
@require_permission("board:field:manage")
def board_update_field(fid: int) -> ResponseReturnValue:
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


@bp.delete("/board/fields/<int:fid>")
@require_permission("board:field:manage")
def board_delete_field(fid: int) -> ResponseReturnValue:
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


@bp.post("/board/cards")
@require_permission("board:card:edit")
def board_create_card() -> ResponseReturnValue:
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


@bp.patch("/board/cards/<int:cid>")
@require_permission("board:card:edit")
def board_update_card(cid: int) -> ResponseReturnValue:
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


@bp.delete("/board/cards/<int:cid>")
@require_permission("board:card:edit")
def board_delete_card(cid: int) -> ResponseReturnValue:
    db = get_db()
    r = db.execute("SELECT id FROM board_cards WHERE id = ?", (cid,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM board_cards WHERE id = ?", (cid,))
    db.commit()
    return jsonify({"deleted": cid})
