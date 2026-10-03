from flask import Blueprint, Response, jsonify

from portal.constants import ARTIFACT_TYPES, PDLC_CHECKPOINTS
from portal.db import get_db, now_iso
from portal.serializers import audit_fields

bp = Blueprint("meta", __name__)


@bp.get("/meta")
def meta() -> Response:
    return jsonify({
        "artifactTypes": ARTIFACT_TYPES,
        "pdlcCheckpoints": PDLC_CHECKPOINTS,
    })


@bp.get("/request-statuses")
def request_statuses() -> Response:
    rows = get_db().execute("SELECT * FROM request_statuses ORDER BY position").fetchall()
    return jsonify([{
        "code": r["code"], "label": r["label"], "meaning": r["meaning"], "whoActs": r["who_acts"],
        "position": r["position"], **audit_fields(r),
    } for r in rows])


@bp.get("/health")
def health() -> Response:
    return jsonify({"status": "ok", "time": now_iso()})
