import re
import sqlite3
from datetime import date

from flask import Blueprint, Response, g, jsonify, request
from flask.typing import ResponseReturnValue

from portal.auth import forbidden, has, require_permission
from portal.constants import ARTIFACT_TYPES
from portal.db import get_db, now_iso
from portal.serializers import request_to_dict

bp = Blueprint("requests", __name__)

# Fields only reviewers/admins decide; stripped unless the caller holds request:edit:all.
REVIEW_FIELDS = {"status", "dateReviewed", "approvalDate", "meetingDate", "meetingTime", "comments"}
MEETING_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
OWNER_EDITABLE_STATUSES = {"DRAFT", "SUBMITTED", "CHANGES_REQUESTED"}
NEW_REQUEST_STATUSES = {"DRAFT", "SUBMITTED"}
APPROVED_STATUSES = {"APPROVED", "APPROVED_WITH_CONDITIONS"}

FIELD_MAP = {
    "arbTitle": "arb_title", "summary": "summary", "artifactLink": "artifact_link",
    "pr": "pr", "appId": "app_id", "appName": "app_name", "trackitId": "trackit_id",
    "solutionArchitect": "solution_architect", "saContributors": "sa_contributors",
    "artifactType": "artifact_type", "pdlcCheckpoint": "pdlc_checkpoint",
    "dateSubmitted": "date_submitted", "dateReviewed": "date_reviewed",
    "buGovReviewer": "bu_gov_reviewer", "eaGovReviewer": "ea_gov_reviewer",
    "status": "status", "approvalDate": "approval_date", "meetingDate": "meeting_date", "meetingTime": "meeting_time",
    "comments": "comments",
}


def owns(r: sqlite3.Row) -> bool:
    return r["created_by"] == g.user["id"]


def status_codes(db: sqlite3.Connection) -> list[str]:
    return [r["code"] for r in db.execute("SELECT code FROM request_statuses ORDER BY position")]


# Drafts are private to their author, even for callers who can view every request.
def visibility_filter() -> tuple[str, list[int]]:
    if has("request:view:all"):
        return "(status != 'DRAFT' OR created_by = ?)", [g.user["id"]]
    return "created_by = ?", [g.user["id"]]


# Requests the caller may not view look like 404s so IDs don't leak which requests exist.
def find_visible_request(req_id: int) -> sqlite3.Row | None:
    r = get_db().execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    if not r or (r["status"] == "DRAFT" and not owns(r)):
        return None
    if has("request:view:all") or (has("request:view:own") and owns(r)):
        return r
    return None


def record_history(db: sqlite3.Connection, req_id: int, from_status: str | None,
                   to_status: str, note: str | None, ts: str) -> None:
    db.execute(
        "INSERT INTO status_history (request_id, from_status, to_status, note, "
        "created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?)",
        (req_id, from_status, to_status, note, ts, g.user["id"], ts, g.user["id"])
    )


# A Scheduled request is booked for an ARB meeting, so it needs the meeting's date (YYYY-MM-DD) and
# time (HH:MM, the meeting's local time).
def meeting_error(status: str, meeting_date: str | None, meeting_time: str | None) -> tuple[Response, int] | None:
    if meeting_time and not MEETING_TIME.fullmatch(meeting_time):
        return jsonify({"error": "meetingTime must be a 24-hour HH:MM time"}), 400
    if meeting_time and not meeting_date:
        return jsonify({"error": "meetingTime needs a meetingDate"}), 400
    if meeting_date:
        try:
            date.fromisoformat(meeting_date)
        except (TypeError, ValueError):
            return jsonify({"error": "meetingDate must be a YYYY-MM-DD date"}), 400
    if status == "SCHEDULED" and not (meeting_date and meeting_time):
        return jsonify({"error": "meetingDate and meetingTime are required to schedule a request"}), 400
    return None


def fetch_request(db: sqlite3.Connection, req_id: int) -> sqlite3.Row:
    return db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()


@bp.get("/requests")
@require_permission("request:view:own", "request:view:all")
def list_requests() -> Response:
    q = "SELECT * FROM requests"
    visible, params = visibility_filter()
    filters = [visible]

    status = request.args.get("status")
    artifact_type = request.args.get("artifactType")
    search = request.args.get("search")

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

    q += " WHERE " + " AND ".join(filters) + " ORDER BY updated_at DESC"

    rows = get_db().execute(q, params).fetchall()
    return jsonify([request_to_dict(r) for r in rows])


@bp.get("/requests/<int:req_id>")
def get_request(req_id: int) -> ResponseReturnValue:
    r = find_visible_request(req_id)
    if not r:
        return jsonify({"error": "Not found"}), 404
    data = request_to_dict(r)
    hist = get_db().execute(
        "SELECT from_status, to_status, note, created_at, created_by FROM status_history "
        "WHERE request_id = ? ORDER BY id ASC", (req_id,)
    ).fetchall()
    data["history"] = [dict(h) for h in hist]
    return jsonify(data)


@bp.post("/requests")
@require_permission("request:create")
def create_request() -> ResponseReturnValue:
    data = request.get_json(force=True) or {}
    status = data.get("status") or "SUBMITTED"
    if not has("request:edit:all"):
        if status not in NEW_REQUEST_STATUSES:
            return forbidden("New requests can only be saved as DRAFT or SUBMITTED")
        data = {k: v for k, v in data.items() if k not in REVIEW_FIELDS}

    if not data.get("arbTitle"):
        return jsonify({"error": "arbTitle is required"}), 400
    if data.get("artifactType") not in ARTIFACT_TYPES:
        return jsonify({"error": "Valid artifactType is required"}), 400

    db = get_db()
    if status not in status_codes(db):
        return jsonify({"error": f"status must be one of {status_codes(db)}"}), 400

    bad_meeting = meeting_error(status, data.get("meetingDate"), data.get("meetingTime"))
    if bad_meeting:
        return bad_meeting

    ts = now_iso()
    date_submitted = data.get("dateSubmitted") or date.today().isoformat()

    cur = db.execute("""
        INSERT INTO requests (
            arb_title, summary, artifact_link, pr, app_id, app_name, trackit_id,
            solution_architect, sa_contributors, artifact_type, pdlc_checkpoint,
            date_submitted, date_reviewed, bu_gov_reviewer, ea_gov_reviewer,
            status, approval_date, meeting_date, meeting_time, comments, created_at, updated_at, created_by, updated_by
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("arbTitle"), data.get("summary"), data.get("artifactLink"),
        data.get("pr"), data.get("appId"), data.get("appName"),
        data.get("trackitId"), data.get("solutionArchitect"),
        data.get("saContributors"), data.get("artifactType"),
        data.get("pdlcCheckpoint"), date_submitted, data.get("dateReviewed"),
        data.get("buGovReviewer"), data.get("eaGovReviewer"), status,
        data.get("approvalDate"), data.get("meetingDate") or None, data.get("meetingTime") or None, data.get("comments"), ts, ts, g.user["id"], g.user["id"]
    ))
    req_id = cur.lastrowid
    record_history(db, req_id, None, status, "Created", ts)
    db.commit()
    return jsonify(request_to_dict(fetch_request(db, req_id))), 201


@bp.put("/requests/<int:req_id>")
@require_permission("request:edit:own", "request:edit:all")
def update_request(req_id: int) -> ResponseReturnValue:
    data = request.get_json(force=True) or {}
    existing = find_visible_request(req_id)
    if not existing:
        return jsonify({"error": "Not found"}), 404
    if not has("request:edit:all"):
        if not owns(existing):
            return forbidden("You can only edit your own requests")
        if existing["status"] not in OWNER_EDITABLE_STATUSES:
            return forbidden("Requests can only be edited while DRAFT, SUBMITTED or CHANGES_REQUESTED")
        data = {k: v for k, v in data.items() if k not in REVIEW_FIELDS}
    if "status" in data and data["status"] != existing["status"] and owns(existing):
        return forbidden("You cannot change the status of a request you submitted")

    if "artifactType" in data and data["artifactType"] not in ARTIFACT_TYPES:
        return jsonify({"error": "Invalid artifactType"}), 400
    db = get_db()
    if "status" in data and data["status"] not in status_codes(db):
        return jsonify({"error": f"status must be one of {status_codes(db)}"}), 400
    for key in ("meetingDate", "meetingTime"):
        if key in data:
            data[key] = data[key] or None
    bad_meeting = meeting_error(data.get("status", existing["status"]), data.get("meetingDate", existing["meeting_date"]),
                                data.get("meetingTime", existing["meeting_time"]))
    if bad_meeting:
        return bad_meeting

    sets, params = [], []
    for k, col in FIELD_MAP.items():
        if k in data:
            sets.append(f"{col} = ?")
            params.append(data[k])

    ts = now_iso()
    sets += ["updated_at = ?", "updated_by = ?"]
    params += [ts, g.user["id"], req_id]
    db.execute(f"UPDATE requests SET {', '.join(sets)} WHERE id = ?", params)

    if "status" in data and data["status"] != existing["status"]:
        record_history(db, req_id, existing["status"], data["status"], data.get("comments"), ts)

    db.commit()
    return jsonify(request_to_dict(fetch_request(db, req_id)))


# Owners move their own request through these steps; every other change is a review decision.
OWNER_TRANSITIONS = {
    ("DRAFT", "SUBMITTED"): "request:create",
    ("CHANGES_REQUESTED", "SUBMITTED"): "request:resubmit",
    ("DRAFT", "WITHDRAWN"): "request:withdraw:own",
    ("SUBMITTED", "WITHDRAWN"): "request:withdraw:own",
}


@bp.patch("/requests/<int:req_id>/status")
def change_status(req_id: int) -> ResponseReturnValue:
    data = request.get_json(force=True) or {}
    new_status = data.get("status")
    db = get_db()
    if new_status not in status_codes(db):
        return jsonify({"error": f"status must be one of {status_codes(db)}"}), 400

    existing = find_visible_request(req_id)
    if not existing:
        return jsonify({"error": "Not found"}), 404

    ts = now_iso()
    owner_perm = OWNER_TRANSITIONS.get((existing["status"], new_status))
    if owner_perm and owns(existing) and has(owner_perm):
        # Submitting a draft is when the request is actually submitted.
        submitted = date.today().isoformat() if existing["status"] == "DRAFT" else existing["date_submitted"]
        db.execute("UPDATE requests SET status = ?, date_submitted = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                   (new_status, submitted, ts, g.user["id"], req_id))
    else:
        if new_status == "SCHEDULED" and not has("request:schedule"):
            return forbidden("You do not have permission to schedule ARB meetings")
        if new_status != "SCHEDULED" and not has("request:review"):
            return forbidden("You do not have permission to review requests")
        if owns(existing):
            return forbidden("You cannot review a request you submitted")
        if new_status == "DRAFT":
            return forbidden("Only the requestor can keep a request as a draft")
        # Sending meetingDate (re)schedules; other moves keep the last meeting.
        if data.get("meetingDate"):
            meeting_date, meeting_time = data["meetingDate"], data.get("meetingTime") or None
        else:
            meeting_date, meeting_time = existing["meeting_date"], existing["meeting_time"]
        bad_meeting = meeting_error(new_status, meeting_date, meeting_time)
        if bad_meeting:
            return bad_meeting
        approval_date = existing["approval_date"]
        if new_status in APPROVED_STATUSES and not approval_date:
            approval_date = date.today().isoformat()
        db.execute(
            "UPDATE requests SET status = ?, approval_date = ?, meeting_date = ?, meeting_time = ?, date_reviewed = ?, "
            "updated_at = ?, updated_by = ? WHERE id = ?",
            (new_status, approval_date, meeting_date, meeting_time, data.get("dateReviewed") or date.today().isoformat(),
             ts, g.user["id"], req_id)
        )
    record_history(db, req_id, existing["status"], new_status, data.get("note"), ts)
    db.commit()
    return jsonify(request_to_dict(fetch_request(db, req_id)))


# Requestors withdraw by status (PATCH .../status to WITHDRAWN); deleting is an admin action.
@bp.delete("/requests/<int:req_id>")
@require_permission("request:delete:all")
def delete_request(req_id: int) -> ResponseReturnValue:
    if not find_visible_request(req_id):
        return jsonify({"error": "Not found"}), 404
    db = get_db()
    db.execute("DELETE FROM requests WHERE id = ?", (req_id,))
    db.commit()
    return jsonify({"deleted": req_id})


@bp.get("/stats")
@require_permission("request:view:own", "request:view:all")
def stats() -> Response:
    db = get_db()
    visible, params = visibility_filter()
    where = f"WHERE {visible}"
    by_status = {row["status"]: row["c"] for row in db.execute(
        f"SELECT status, COUNT(*) c FROM requests {where} GROUP BY status", params)}
    by_type = {row["artifact_type"]: row["c"] for row in db.execute(
        f"SELECT artifact_type, COUNT(*) c FROM requests {where} GROUP BY artifact_type", params)}
    total = db.execute(f"SELECT COUNT(*) c FROM requests {where}", params).fetchone()["c"]
    return jsonify({
        "total": total,
        "byStatus": {s: by_status.get(s, 0) for s in status_codes(db)},
        "byType": {t: by_type.get(t, 0) for t in ARTIFACT_TYPES},
    })
