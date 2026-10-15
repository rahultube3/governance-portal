import sqlite3

from portal.auth import has
from portal.constants import CRITICAL, FINAL_STATUSES, LOW, TIER_LABELS
from portal.db import get_db

APPROVALS = ["APPROVED", "APPROVED_WITH_CONDITIONS"]
SEND_BACK = ["CHANGES_REQUESTED", "REJECTED"]
CHIEF = "CHIEF_ARCHITECTURE_REVIEW"
# Admin-added statuses are pause steps: a reviewer moves a request into one from these statuses, and out of it
# back to where it came from, or to Changes Requested / Rejected.
PAUSE_FROM = ["IN_REVIEW", "SCHEDULED", CHIEF]
MISSING_PERMISSION = {
    "request:review": "You do not have permission to review requests",
    "request:schedule": "You do not have permission to schedule ARB meetings",
    "request:signoff": "Only the Chief Architect can decide a Critical-risk request",
}


def status_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("SELECT code, label, active, builtin FROM request_statuses ORDER BY position, code").fetchall()


# The built-in route for a tier, each move with the permission it needs. A Low request reaches In Review only
# when agent validation fails, and a reviewer decides it there; Medium, High and Critical need an ARB meeting;
# Critical then goes to the Chief Architect.
def route_moves(status: str, tier: int | None) -> dict[str, str]:
    if status == "SUBMITTED":
        targets = ["IN_REVIEW", *SEND_BACK]
    elif status == "IN_REVIEW":
        targets = [*(APPROVALS if tier == LOW else ["SCHEDULED"]), *SEND_BACK]
    elif status == "SCHEDULED":
        targets = ["SCHEDULED", *([CHIEF] if tier == CRITICAL else APPROVALS), *SEND_BACK]
    elif status == CHIEF:
        return {to: "request:signoff" for to in [*APPROVALS, *SEND_BACK]}
    else:
        return {}
    return {to: "request:schedule" if to == "SCHEDULED" else "request:review" for to in targets}


# The status a paused request returns to: the one it was moved into the pause step from.
def paused_from(db: sqlite3.Connection, r: sqlite3.Row) -> str:
    row = db.execute("SELECT from_status FROM status_history WHERE request_id = ? AND to_status = ? "
                     "AND from_status IS NOT to_status ORDER BY id DESC LIMIT 1", (r["id"], r["status"])).fetchone()
    return row["from_status"] if row and row["from_status"] in PAUSE_FROM else "IN_REVIEW"


# Every move out of the request's status, deactivated targets included. Pausing or resuming a request that is
# (or was) with the Chief Architect needs sign-off, like any other move out of Chief Architecture Review.
def all_moves(db: sqlite3.Connection, r: sqlite3.Row) -> dict[str, str]:
    pauses = [s["code"] for s in status_rows(db) if not s["builtin"]]
    frm = r["status"]
    if frm in pauses:
        origin = paused_from(db, r)
        perm = "request:signoff" if origin == CHIEF else "request:review"
        return {to: perm for to in [origin, *SEND_BACK]}
    moves = route_moves(frm, r["risk_tier"])
    if frm in PAUSE_FROM:
        moves.update({p: "request:signoff" if frm == CHIEF else "request:review" for p in pauses})
    return moves


def review_moves(r: sqlite3.Row) -> dict[str, str]:
    db = get_db()
    active = {s["code"] for s in status_rows(db) if s["active"]}
    return {to: perm for to, perm in all_moves(db, r).items() if to in active}


# Why the caller can't make this review move, or None when they can. Ownership is checked by the route.
def review_block(r: sqlite3.Row, to: str) -> str | None:
    db = get_db()
    rows = status_rows(db)
    labels = {s["code"]: s["label"] for s in rows}
    frm = r["status"]
    moves = all_moves(db, r)
    if to in moves and to not in {s["code"] for s in rows if s["active"]}:
        return f"{labels[to]} is deactivated"
    if to not in moves:
        if frm in FINAL_STATUSES:
            return f"{labels.get(frm, frm)} is a final decision"
        risk = f"A {TIER_LABELS[r['risk_tier']]}-risk request" if r["risk_tier"] else "A request"
        return f"{risk} can't move from {labels.get(frm, frm)} to {labels.get(to, to)}"
    if not has(moves[to]):
        return MISSING_PERMISSION[moves[to]]
    return None


def next_steps(r: sqlite3.Row) -> list[dict[str, str | None]]:
    order = [s["code"] for s in status_rows(get_db())]
    moves = review_moves(r)
    return [{"status": to, "blocked": None if has(perm) else MISSING_PERMISSION[perm]}
            for to, perm in sorted(moves.items(), key=lambda m: order.index(m[0]))]
