import json
import sqlite3
from typing import Any

from portal.constants import REVIEWER_ROLES


def audit_fields(r: sqlite3.Row) -> dict[str, Any]:
    return {"createdAt": r["created_at"], "createdBy": r["created_by"],
            "updatedAt": r["updated_at"], "updatedBy": r["updated_by"]}


def user_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"]}


# `labels` maps artifact_names codes to labels, so each artifact carries the label the dropdown shows.
def request_to_dict(r: sqlite3.Row, labels: dict[str, str]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "arbTitle": r["arb_title"],
        "summary": r["summary"],
        "intelEaCapabilityLink": r["intelea_capability_link"],
        "solutionId": r["solution_id"],
        "artifacts": [{**a, "label": labels.get(a["code"], a["code"])} for a in json.loads(r["artifacts"] or "[]")],
        "pr": r["pr"],
        "appId": r["app_id"],
        "appName": r["app_name"],
        "trackitId": r["trackit_id"],
        "solutionArchitect": r["solution_architect"],
        "saContributors": r["sa_contributors"],
        "artifactType": r["artifact_type"],
        "pdlcCheckpoint": r["pdlc_checkpoint"],
        "dateSubmitted": r["date_submitted"],
        "dateReviewed": r["date_reviewed"],
        **{field: json.loads(r[column] or "[]") for _, _, field, column in REVIEWER_ROLES},
        "status": r["status"],
        "approvalDate": r["approval_date"],
        "meetingDate": r["meeting_date"],
        "meetingTime": r["meeting_time"],
        "comments": r["comments"],
        "riskTier": r["risk_tier"],
        "agentReview": json.loads(r["agent_review"]) if r["agent_review"] else None,
        **audit_fields(r),
    }


def field_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": r["id"],
        "key": r["key"],
        "label": r["label"],
        "type": r["type"],
        "options": json.loads(r["options"]) if r["options"] else [],
        "position": r["position"],
        "isTitle": bool(r["is_title"]),
        "isGroup": bool(r["is_group"]),
        **audit_fields(r),
    }


def card_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": r["id"],
        "data": json.loads(r["data"] or "{}"),
        "position": r["position"],
        **audit_fields(r),
    }
