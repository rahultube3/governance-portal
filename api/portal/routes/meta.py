import json
import sqlite3
from typing import Any

from flask import Blueprint, Response, jsonify

from portal.constants import DEACTIVATABLE_STATUSES, FINAL_STATUSES, MAX_ARTIFACTS, REVIEWER_ROLES, RISK_TIERS
from portal.db import get_db, now_iso
from portal.serializers import audit_fields

bp = Blueprint("meta", __name__)


@bp.get("/meta")
def meta() -> Response:
    db = get_db()
    return jsonify({
        # Every list includes inactive entries (flagged) so forms can still show the value an older request holds.
        "artifactTypes": [{"id": r["id"], "name": r["name"], "active": bool(r["active"])}
                          for r in db.execute("SELECT * FROM review_types ORDER BY name COLLATE NOCASE")],
        "artifactNames": [{"code": r["code"], "label": r["label"], "requiredFor": json.loads(r["required_for"]),
                           "active": bool(r["active"])}
                          for r in db.execute("SELECT * FROM artifact_names ORDER BY position, code")],
        "maxArtifacts": MAX_ARTIFACTS,
        "reviewerRoles": [{"code": c, "label": label, "field": field} for c, label, field, _ in REVIEWER_ROLES],
        "reviewers": [{"id": r["id"], "name": r["name"], "role": r["role"], "active": bool(r["active"])}
                      for r in db.execute("SELECT * FROM reviewers ORDER BY role, name COLLATE NOCASE")],
        "pdlcCheckpoints": [{"id": r["id"], "name": r["name"], "active": bool(r["active"])}
                            for r in db.execute("SELECT * FROM pdlc_checkpoints ORDER BY position, id")],
        "riskTiers": RISK_TIERS,
        "finalStatuses": FINAL_STATUSES,
    })


@bp.get("/request-statuses")
def request_statuses() -> Response:
    db = get_db()
    return jsonify([status_to_dict(r, status_usage(db))
                    for r in db.execute("SELECT * FROM request_statuses ORDER BY position, code")])


def status_usage(db: sqlite3.Connection) -> dict[str, int]:
    return {r[0]: r[1] for r in db.execute("SELECT status, COUNT(*) FROM requests GROUP BY status")}


# `builtin` statuses come from code and the review route depends on them; admin-added ones are pause steps.
# `deactivatable` says whether admins may switch the status off; `inUse` counts requests currently in it.
def status_to_dict(r: sqlite3.Row, usage: dict[str, int]) -> dict[str, Any]:
    builtin = bool(r["builtin"])
    return {"code": r["code"], "label": r["label"], "meaning": r["meaning"], "whoActs": r["who_acts"],
            "position": r["position"], "active": bool(r["active"]), "builtin": builtin,
            "deactivatable": not builtin or r["code"] in DEACTIVATABLE_STATUSES, "inUse": usage.get(r["code"], 0),
            **audit_fields(r)}


@bp.get("/health")
def health() -> Response:
    return jsonify({"status": "ok", "time": now_iso()})
