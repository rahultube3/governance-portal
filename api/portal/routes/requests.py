import json
import re
import sqlite3
from datetime import date
from typing import Any

from flask import Blueprint, Response, g, jsonify, request
from flask.typing import ResponseReturnValue

from portal import validation_agent
from portal.auth import forbidden, has, require_permission
from portal.constants import (APPROVED_STATUSES, FINAL_STATUSES, LOW, MAX_ARTIFACTS, OWNER_TRANSITIONS, REVIEWER_ROLES,
                              TIER_LABELS)
from portal.db import get_db, now_iso
from portal.serializers import request_to_dict
from portal.workflow import next_steps, review_block

bp = Blueprint("requests", __name__)

# Fields only reviewers/admins decide; stripped unless the caller holds request:edit:all.
REVIEW_FIELDS = {"status", "dateReviewed", "approvalDate", "meetingDate", "meetingTime", "comments"}
MEETING_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
MAX_TEXT = 2000
OWNER_EDITABLE_STATUSES = {"DRAFT", "SUBMITTED", "CHANGES_REQUESTED"}
NEW_REQUEST_STATUSES = {"DRAFT", "SUBMITTED"}
NO_TIER = "Choose a risk tier before submitting"
NO_CAPABILITY = "IntelEA Capability Link is required"

FIELD_MAP = {
    "arbTitle": "arb_title", "summary": "summary",
    "pr": "pr", "appId": "app_id", "appName": "app_name", "trackitId": "trackit_id",
    "solutionArchitect": "solution_architect", "saContributors": "sa_contributors",
    "artifactType": "artifact_type", "pdlcCheckpoint": "pdlc_checkpoint",
    "dateReviewed": "date_reviewed",
    "status": "status", "approvalDate": "approval_date", "meetingDate": "meeting_date", "meetingTime": "meeting_time",
    "comments": "comments", "riskTier": "risk_tier",
    "intelEaCapabilityLink": "intelea_capability_link", "solutionId": "solution_id",
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


# Rows the validation agent writes have no user, so they show as the system's.
def record_history(db: sqlite3.Connection, req_id: int, from_status: str | None,
                   to_status: str, note: str | None, ts: str, by_agent: bool = False) -> None:
    user_id = None if by_agent else g.user["id"]
    db.execute(
        "INSERT INTO status_history (request_id, from_status, to_status, note, "
        "created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?)",
        (req_id, from_status, to_status, note, ts, user_id, ts, user_id)
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


# A draft may leave the tier unset; a request outside DRAFT needs one.
def tier_error(tier: object, status: str) -> tuple[Response, int] | None:
    if tier is None:
        return (jsonify({"error": NO_TIER}), 400) if status != "DRAFT" else None
    if type(tier) is not int or tier not in TIER_LABELS:
        return jsonify({"error": f"riskTier must be one of {sorted(TIER_LABELS)}"}), 400
    return None


# Reference links are free text; the UI makes only http(s) values clickable. A deactivated name is refused
# unless the request already had it (`kept`), so editing an older request doesn't force it out.
def clean_artifacts(db: sqlite3.Connection, raw: object,
                    kept: frozenset[str] = frozenset()) -> tuple[list[dict[str, str]], tuple[Response, int] | None]:
    def bad(msg: str) -> tuple[list[dict[str, str]], tuple[Response, int]]:
        return [], (jsonify({"error": msg}), 400)
    if not isinstance(raw, list):
        return bad("artifacts must be a list of {code, link}")
    if len(raw) > MAX_ARTIFACTS:
        return bad(f"A request can have at most {MAX_ARTIFACTS} Architecture Reference Links")
    labels = artifact_labels(db)
    active = {r["code"] for r in db.execute("SELECT code FROM artifact_names WHERE active = 1")}
    out = []
    for a in raw:
        if not isinstance(a, dict) or a.get("code") not in labels:
            return bad(f"Each reference code must be one of {sorted(labels)}")
        if a["code"] not in active and a["code"] not in kept:
            return bad(f"{labels[a['code']]} is deactivated; choose another reference")
        link = a.get("link")
        if not isinstance(link, str) or not link.strip() or len(link.strip()) > MAX_TEXT:
            return bad(f"The {labels[a['code']]} reference needs a link or text of at most {MAX_TEXT} characters")
        out.append({"code": a["code"], "link": link.strip()})
    return out, None


def artifact_labels(db: sqlite3.Connection) -> dict[str, str]:
    return {r["code"]: r["label"] for r in db.execute("SELECT code, label FROM artifact_names")}


# Some review types need particular active references (artifact_names.required_for) before leaving DRAFT.
def missing_artifact(db: sqlite3.Connection, artifact_type: str, codes: set[str]) -> tuple[Response, int] | None:
    rows = db.execute("SELECT code, label, required_for FROM artifact_names WHERE active = 1 ORDER BY position")
    missing = [r["label"] for r in rows if artifact_type in json.loads(r["required_for"]) and r["code"] not in codes]
    if not missing:
        return None
    if len(missing) == 1:
        what = f"{'an' if missing[0][0].lower() in 'aeiou' else 'a'} {missing[0]} reference link"
    else:
        what = f"{' and '.join(missing)} reference links"
    return jsonify({"error": f"{artifact_type} requests need {what}."}), 400


# Each reviewer field is a list of names of active reviewers in that role. Names a request already holds are
# kept even if those reviewers have since been deactivated. Returns the JSON for each column that was sent.
def clean_reviewers(db: sqlite3.Connection, data: dict[str, Any], existing: sqlite3.Row | None = None
                    ) -> tuple[dict[str, str], tuple[Response, int] | None]:
    out = {}
    for role, label, field, column in REVIEWER_ROLES:
        if field not in data:
            continue
        names = data[field]
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            return {}, (jsonify({"error": f"{field} must be a list of names"}), 400)
        kept = json.loads(existing[column] or "[]") if existing else []
        names = list(dict.fromkeys(n.strip() for n in names if n.strip()))
        for name in names:
            if name in kept:
                continue
            if not db.execute("SELECT 1 FROM reviewers WHERE role = ? AND name = ? AND active = 1",
                              (role, name)).fetchone():
                return {}, (jsonify({"error": f"{name} is not an active {label}"}), 400)
        out[column] = json.dumps(names)
    return out, None


# Review type and PDLC checkpoint must name an active entry of their Reference Data list, or keep the value the
# request already has (it may since have been deactivated). The PDLC checkpoint may be left empty.
def lookup_error(db: sqlite3.Connection, data: dict[str, Any], existing: sqlite3.Row | None = None
                 ) -> tuple[Response, int] | None:
    checks = [("artifactType", "artifact_type", "review_types", "review type"),
              ("pdlcCheckpoint", "pdlc_checkpoint", "pdlc_checkpoints", "PDLC checkpoint")]
    for key, column, table, what in checks:
        if key not in data or (existing and data[key] == existing[column]):
            continue
        if key == "pdlcCheckpoint" and not data[key]:
            continue
        if not db.execute(f"SELECT 1 FROM {table} WHERE name = ? AND active = 1", (data[key],)).fetchone():
            return jsonify({"error": f"{data[key]!r} is not an active {what}"}), 400
    return None


def fetch_request(db: sqlite3.Connection, req_id: int) -> sqlite3.Row:
    return db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()


def request_json(db: sqlite3.Connection, req_id: int) -> dict[str, Any]:
    return request_to_dict(fetch_request(db, req_id), artifact_labels(db))


# A Low-risk request goes to the validation agent as soon as it is submitted: a pass approves it, a fail
# (or no verdict) puts it In Review for a reviewer. Runs after the submit is committed, since the agent call
# takes seconds and shouldn't hold the database lock.
def validate_if_low(db: sqlite3.Connection, req_id: int) -> None:
    r = fetch_request(db, req_id)
    if r["status"] != "SUBMITTED" or r["risk_tier"] != LOW:
        return
    result = validation_agent.validate(r, request_json(db, req_id)["artifacts"])
    ts = now_iso()
    today = date.today().isoformat()
    if result and result["passed"]:
        status, approval_date, note = "APPROVED", today, f"Auto-approved by agent validation: {result['summary']}"
    elif result:
        status, approval_date, note = "IN_REVIEW", None, f"Agent validation failed, so a reviewer decides: {result['summary']}"
    else:
        status, approval_date, note = "IN_REVIEW", None, "Agent validation was unavailable, so a reviewer decides"
    review = json.dumps({**result, "checkedAt": ts}) if result else None
    db.execute("UPDATE requests SET status = ?, approval_date = ?, date_reviewed = ?, agent_review = ?, "
               "updated_at = ?, updated_by = NULL WHERE id = ?", (status, approval_date, today, review, ts, req_id))
    record_history(db, req_id, "SUBMITTED", status, note, ts, by_agent=True)
    db.commit()


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

    db = get_db()
    rows = db.execute(q, params).fetchall()
    labels = artifact_labels(db)
    return jsonify([request_to_dict(r, labels) for r in rows])


@bp.get("/requests/<int:req_id>")
def get_request(req_id: int) -> ResponseReturnValue:
    r = find_visible_request(req_id)
    if not r:
        return jsonify({"error": "Not found"}), 404
    data = request_json(get_db(), req_id)
    hist = get_db().execute(
        "SELECT from_status, to_status, note, created_at, created_by FROM status_history "
        "WHERE request_id = ? ORDER BY id ASC", (req_id,)
    ).fetchall()
    data["history"] = [dict(h) for h in hist]
    reviewer = has("request:review", "request:schedule", "request:signoff") and not owns(r)
    data["nextSteps"] = next_steps(r) if reviewer else []
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
    if not data.get("artifactType"):
        return jsonify({"error": "artifactType is required"}), 400

    db = get_db()
    bad_lookup = lookup_error(db, data)
    if bad_lookup:
        return bad_lookup
    if status not in status_codes(db):
        return jsonify({"error": f"status must be one of {status_codes(db)}"}), 400

    bad_meeting = meeting_error(status, data.get("meetingDate"), data.get("meetingTime"))
    if bad_meeting:
        return bad_meeting
    bad_tier = tier_error(data.get("riskTier"), status)
    if bad_tier:
        return bad_tier
    if status != "DRAFT" and not (data.get("intelEaCapabilityLink") or "").strip():
        return jsonify({"error": NO_CAPABILITY}), 400
    reviewers, bad_reviewer = clean_reviewers(db, data)
    if bad_reviewer:
        return bad_reviewer
    artifacts, bad_artifacts = clean_artifacts(db, data.get("artifacts", []))
    if bad_artifacts:
        return bad_artifacts
    if status != "DRAFT":
        missing = missing_artifact(db, data["artifactType"], {a["code"] for a in artifacts})
        if missing:
            return missing

    ts = now_iso()
    # Set by the system: today on creation, and again when a draft is submitted (PATCH .../status).
    date_submitted = date.today().isoformat()

    cur = db.execute("""
        INSERT INTO requests (
            arb_title, summary, artifacts, intelea_capability_link, solution_id, pr, app_id, app_name, trackit_id,
            solution_architect, sa_contributors, artifact_type, pdlc_checkpoint,
            date_submitted, date_reviewed, bu_gov_reviewers, ea_gov_reviewers, ecs_reviewers,
            status, approval_date, meeting_date, meeting_time, comments, risk_tier,
            created_at, updated_at, created_by, updated_by
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("arbTitle"), data.get("summary"), json.dumps(artifacts),
        data.get("intelEaCapabilityLink") or None, data.get("solutionId") or None,
        data.get("pr"), data.get("appId"), data.get("appName"),
        data.get("trackitId"), data.get("solutionArchitect"),
        data.get("saContributors"), data.get("artifactType"),
        data.get("pdlcCheckpoint"), date_submitted, data.get("dateReviewed"),
        *(reviewers.get(column, "[]") for *_, column in REVIEWER_ROLES), status,
        data.get("approvalDate"), data.get("meetingDate") or None, data.get("meetingTime") or None, data.get("comments"),
        data.get("riskTier"), ts, ts, g.user["id"], g.user["id"]
    ))
    req_id = cur.lastrowid
    record_history(db, req_id, None, status, "Created", ts)
    db.commit()
    validate_if_low(db, req_id)
    return jsonify(request_json(db, req_id)), 201


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
    status_change = "status" in data and data["status"] != existing["status"]
    if status_change and owns(existing):
        return forbidden("You cannot change the status of a request you submitted")

    db = get_db()
    bad_lookup = lookup_error(db, data, existing)
    if bad_lookup:
        return bad_lookup
    if "status" in data and data["status"] not in status_codes(db):
        return jsonify({"error": f"status must be one of {status_codes(db)}"}), 400
    for key in ("meetingDate", "meetingTime"):
        if key in data:
            data[key] = data[key] or None
    bad_meeting = meeting_error(data.get("status", existing["status"]), data.get("meetingDate", existing["meeting_date"]),
                                data.get("meetingTime", existing["meeting_time"]))
    if bad_meeting:
        return bad_meeting
    if status_change:
        block = review_block(existing, data["status"])
        if block:
            return forbidden(block)
    # After submission the tier is a reviewer's call, made with a reason (PATCH .../tier).
    if "riskTier" in data and data["riskTier"] != existing["risk_tier"]:
        if existing["status"] != "DRAFT":
            return forbidden("After submission, only a reviewer can change the risk tier")
        bad_tier = tier_error(data["riskTier"], "DRAFT")
        if bad_tier:
            return bad_tier

    if "artifacts" in data:
        kept = frozenset(a["code"] for a in json.loads(existing["artifacts"] or "[]"))
        artifacts, bad_artifacts = clean_artifacts(db, data["artifacts"], kept)
        if bad_artifacts:
            return bad_artifacts
    else:
        artifacts = json.loads(existing["artifacts"] or "[]")
    if data.get("status", existing["status"]) != "DRAFT" and {"artifacts", "artifactType", "status"} & data.keys():
        missing = missing_artifact(db, data.get("artifactType", existing["artifact_type"]), {a["code"] for a in artifacts})
        if missing:
            return missing
    reviewers, bad_reviewer = clean_reviewers(db, data, existing)
    if bad_reviewer:
        return bad_reviewer
    capability = data.get("intelEaCapabilityLink", existing["intelea_capability_link"])
    if data.get("status", existing["status"]) != "DRAFT" and {"intelEaCapabilityLink", "status"} & data.keys() \
            and not (capability or "").strip():
        return jsonify({"error": NO_CAPABILITY}), 400

    sets, params = [], []
    for k, col in FIELD_MAP.items():
        if k in data:
            sets.append(f"{col} = ?")
            params.append(data[k])
    if "artifacts" in data:
        sets.append("artifacts = ?")
        params.append(json.dumps(artifacts))
    for column, value in reviewers.items():
        sets.append(f"{column} = ?")
        params.append(value)
    ts = now_iso()
    sets += ["updated_at = ?", "updated_by = ?"]
    params += [ts, g.user["id"], req_id]
    db.execute(f"UPDATE requests SET {', '.join(sets)} WHERE id = ?", params)

    if status_change:
        record_history(db, req_id, existing["status"], data["status"], data.get("comments"), ts)

    db.commit()
    return jsonify(request_json(db, req_id))


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
    target = db.execute("SELECT label, active FROM request_statuses WHERE code = ?", (new_status,)).fetchone()
    if not target["active"]:
        return forbidden(f"{target['label']} is deactivated")

    ts = now_iso()
    owner_perm = OWNER_TRANSITIONS.get((existing["status"], new_status))
    if owner_perm and owns(existing) and has(owner_perm):
        if new_status == "SUBMITTED":
            if existing["risk_tier"] is None:
                return jsonify({"error": NO_TIER}), 400
            if not (existing["intelea_capability_link"] or "").strip():
                return jsonify({"error": NO_CAPABILITY}), 400
            codes = {a["code"] for a in json.loads(existing["artifacts"] or "[]")}
            missing = missing_artifact(db, existing["artifact_type"], codes)
            if missing:
                return missing
        # Submitting a draft is when the request is actually submitted.
        submitted = date.today().isoformat() if existing["status"] == "DRAFT" else existing["date_submitted"]
        db.execute("UPDATE requests SET status = ?, date_submitted = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                   (new_status, submitted, ts, g.user["id"], req_id))
    else:
        if owns(existing):
            return forbidden("You cannot review a request you submitted")
        block = review_block(existing, new_status)
        if block:
            return forbidden(block)
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
    validate_if_low(db, req_id)
    return jsonify(request_json(db, req_id))


# Raising a tier is any reviewer's call; lowering one is the Chief Architect's, so one reviewer can't route a
# Critical request around the Chief Architect or a Medium one into the fast track.
@bp.patch("/requests/<int:req_id>/tier")
@require_permission("request:review")
def set_tier(req_id: int) -> ResponseReturnValue:
    data = request.get_json(force=True) or {}
    existing = find_visible_request(req_id)
    if not existing:
        return jsonify({"error": "Not found"}), 404
    if owns(existing):
        return forbidden("You cannot set the risk tier of a request you submitted")
    if existing["status"] == "DRAFT" or existing["status"] in FINAL_STATUSES:
        return forbidden("The risk tier can only change while a request is in review")

    tier = data.get("tier")
    reason = (data.get("reason") or "").strip()
    if type(tier) is not int or tier not in TIER_LABELS:
        return jsonify({"error": f"tier must be one of {sorted(TIER_LABELS)}"}), 400
    if not reason:
        return jsonify({"error": "A reason is required to change the risk tier"}), 400
    before = existing["risk_tier"]
    if before and tier < before and not has("request:signoff"):
        return forbidden("Only the Chief Architect can lower a risk tier")

    db = get_db()
    ts = now_iso()
    db.execute("UPDATE requests SET risk_tier = ?, updated_at = ?, updated_by = ? WHERE id = ?",
               (tier, ts, g.user["id"], req_id))
    was = TIER_LABELS[before] if before else "none"
    record_history(db, req_id, existing["status"], existing["status"],
                   f"Risk tier changed from {was} to {TIER_LABELS[tier]}: {reason}", ts)
    db.commit()
    return jsonify(request_json(db, req_id))


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
        "byType": {r["name"]: by_type.get(r["name"], 0)
                   for r in db.execute("SELECT name FROM review_types ORDER BY name COLLATE NOCASE")},
    })
