"""
Fidelity Governance Portal REST API
Flask + SQLite backend for architecture governance artifact intake & review.
"""
import json
import os
import sqlite3
from datetime import datetime, date
from flask import Flask, Response, request, jsonify, g, stream_with_context
from flask_cors import CORS

import anthropic

from knowledge import SYSTEM_PROMPT

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "governance.db")

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
ARTIFACT_TYPES = [
    "Architecture Review Board (ARB) Intake Request",
    "Data Architecture Intake Request",
    "Architecture Decision Record (ADR) Submission",
    "Messaging & Streaming Architecture Intake Request",
    "AI/ML Architecture Intake Request",
]

# Governance lifecycle statuses
LIFECYCLE = ["PENDING", "APPROVED FB", "APPROVED EA", "FOLLOW UP", "REWORK"]

PDLC_CHECKPOINTS = [
    "Inception", "Elaboration", "Construction", "Delivery"
]

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            arb_title               TEXT NOT NULL,
            summary                 TEXT,
            artifact_link           TEXT,
            pr                      TEXT,
            app_id                  TEXT,
            app_name                TEXT,
            trackit_id              TEXT,
            solution_architect      TEXT,
            sa_contributors         TEXT,
            artifact_type           TEXT NOT NULL,
            pdlc_checkpoint         TEXT,
            date_submitted          TEXT NOT NULL,
            date_reviewed           TEXT,
            bu_gov_reviewer         TEXT,
            ea_gov_reviewer         TEXT,
            status                  TEXT NOT NULL DEFAULT 'PENDING',
            approval_date           TEXT,
            comments                TEXT,
            created_at              TEXT NOT NULL,
            updated_at              TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id   INTEGER NOT NULL,
            from_status  TEXT,
            to_status    TEXT NOT NULL,
            note         TEXT,
            changed_at   TEXT NOT NULL,
            FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
        )
    """)
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def row_to_dict(r):
    return {
        "id": r["id"],
        "arbTitle": r["arb_title"],
        "summary": r["summary"],
        "artifactLink": r["artifact_link"],
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
        "buGovReviewer": r["bu_gov_reviewer"],
        "eaGovReviewer": r["ea_gov_reviewer"],
        "status": r["status"],
        "approvalDate": r["approval_date"],
        "comments": r["comments"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ---------------------------------------------------------------------------
# Reference endpoints
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def meta():
    return jsonify({
        "artifactTypes": ARTIFACT_TYPES,
        "lifecycle": LIFECYCLE,
        "pdlcCheckpoints": PDLC_CHECKPOINTS,
    })


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": now_iso()})


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------
@app.get("/api/requests")
def list_requests():
    db = get_db()
    q = "SELECT * FROM requests"
    params = []
    filters = []

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

    if filters:
        q += " WHERE " + " AND ".join(filters)
    q += " ORDER BY updated_at DESC"

    rows = db.execute(q, params).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.get("/api/requests/<int:req_id>")
def get_request(req_id):
    db = get_db()
    r = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404
    data = row_to_dict(r)
    hist = db.execute(
        "SELECT from_status, to_status, note, changed_at FROM status_history "
        "WHERE request_id = ? ORDER BY id ASC", (req_id,)
    ).fetchall()
    data["history"] = [dict(h) for h in hist]
    return jsonify(data)


@app.post("/api/requests")
def create_request():
    data = request.get_json(force=True) or {}

    if not data.get("arbTitle"):
        return jsonify({"error": "arbTitle is required"}), 400
    if data.get("artifactType") not in ARTIFACT_TYPES:
        return jsonify({"error": "Valid artifactType is required"}), 400

    status = data.get("status", "PENDING")
    if status not in LIFECYCLE:
        return jsonify({"error": f"status must be one of {LIFECYCLE}"}), 400

    ts = now_iso()
    date_submitted = data.get("dateSubmitted") or date.today().isoformat()

    db = get_db()
    cur = db.execute("""
        INSERT INTO requests (
            arb_title, summary, artifact_link, pr, app_id, app_name, trackit_id,
            solution_architect, sa_contributors, artifact_type, pdlc_checkpoint,
            date_submitted, date_reviewed, bu_gov_reviewer, ea_gov_reviewer,
            status, approval_date, comments, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("arbTitle"), data.get("summary"), data.get("artifactLink"),
        data.get("pr"), data.get("appId"), data.get("appName"),
        data.get("trackitId"), data.get("solutionArchitect"),
        data.get("saContributors"), data.get("artifactType"),
        data.get("pdlcCheckpoint"), date_submitted, data.get("dateReviewed"),
        data.get("buGovReviewer"), data.get("eaGovReviewer"), status,
        data.get("approvalDate"), data.get("comments"), ts, ts
    ))
    req_id = cur.lastrowid
    db.execute(
        "INSERT INTO status_history (request_id, from_status, to_status, note, changed_at) "
        "VALUES (?,?,?,?,?)",
        (req_id, None, status, "Created", ts)
    )
    db.commit()
    r = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    return jsonify(row_to_dict(r)), 201


@app.put("/api/requests/<int:req_id>")
def update_request(req_id):
    data = request.get_json(force=True) or {}
    db = get_db()
    existing = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Not found"}), 404

    field_map = {
        "arbTitle": "arb_title", "summary": "summary", "artifactLink": "artifact_link",
        "pr": "pr", "appId": "app_id", "appName": "app_name", "trackitId": "trackit_id",
        "solutionArchitect": "solution_architect", "saContributors": "sa_contributors",
        "artifactType": "artifact_type", "pdlcCheckpoint": "pdlc_checkpoint",
        "dateSubmitted": "date_submitted", "dateReviewed": "date_reviewed",
        "buGovReviewer": "bu_gov_reviewer", "eaGovReviewer": "ea_gov_reviewer",
        "status": "status", "approvalDate": "approval_date", "comments": "comments",
    }

    if "artifactType" in data and data["artifactType"] not in ARTIFACT_TYPES:
        return jsonify({"error": "Invalid artifactType"}), 400
    if "status" in data and data["status"] not in LIFECYCLE:
        return jsonify({"error": f"status must be one of {LIFECYCLE}"}), 400

    sets, params = [], []
    for k, col in field_map.items():
        if k in data:
            sets.append(f"{col} = ?")
            params.append(data[k])

    ts = now_iso()
    sets.append("updated_at = ?")
    params.append(ts)
    params.append(req_id)

    if sets:
        db.execute(f"UPDATE requests SET {', '.join(sets)} WHERE id = ?", params)

    # record status transition
    if "status" in data and data["status"] != existing["status"]:
        db.execute(
            "INSERT INTO status_history (request_id, from_status, to_status, note, changed_at) "
            "VALUES (?,?,?,?,?)",
            (req_id, existing["status"], data["status"], data.get("comments"), ts)
        )

    db.commit()
    r = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    return jsonify(row_to_dict(r))


@app.patch("/api/requests/<int:req_id>/status")
def change_status(req_id):
    data = request.get_json(force=True) or {}
    new_status = data.get("status")
    if new_status not in LIFECYCLE:
        return jsonify({"error": f"status must be one of {LIFECYCLE}"}), 400

    db = get_db()
    existing = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Not found"}), 404

    ts = now_iso()
    approval_date = existing["approval_date"]
    if new_status in ("APPROVED FB", "APPROVED EA") and not approval_date:
        approval_date = date.today().isoformat()

    db.execute(
        "UPDATE requests SET status = ?, approval_date = ?, date_reviewed = ?, "
        "updated_at = ? WHERE id = ?",
        (new_status, approval_date, data.get("dateReviewed") or date.today().isoformat(),
         ts, req_id)
    )
    db.execute(
        "INSERT INTO status_history (request_id, from_status, to_status, note, changed_at) "
        "VALUES (?,?,?,?,?)",
        (req_id, existing["status"], new_status, data.get("note"), ts)
    )
    db.commit()
    r = db.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
    return jsonify(row_to_dict(r))


@app.delete("/api/requests/<int:req_id>")
def delete_request(req_id):
    db = get_db()
    r = db.execute("SELECT id FROM requests WHERE id = ?", (req_id,)).fetchone()
    if not r:
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM requests WHERE id = ?", (req_id,))
    db.commit()
    return jsonify({"deleted": req_id})


# ---------------------------------------------------------------------------
# Chat with the governance documents (streams SSE)
# ---------------------------------------------------------------------------
CHAT_MODEL = os.environ.get("CHAT_MODEL", "claude-sonnet-4-6")
CHAT_MAX_TURNS = 40
CHAT_MAX_CHARS = 4000


def validate_chat_messages(raw: object) -> tuple[list[dict[str, str]] | None, str | None]:
    if not isinstance(raw, list) or not raw:
        return None, "messages must be a non-empty list"
    if len(raw) > CHAT_MAX_TURNS:
        raw = raw[-CHAT_MAX_TURNS:]
    out: list[dict[str, str]] = []
    for m in raw:
        if not isinstance(m, dict):
            return None, "each message must be an object"
        role, content = m.get("role"), m.get("content")
        if role not in ("user", "assistant"):
            return None, "role must be 'user' or 'assistant'"
        if not isinstance(content, str) or not content.strip():
            return None, "content must be a non-empty string"
        out.append({"role": role, "content": content[:CHAT_MAX_CHARS]})
    if out[0]["role"] != "user":
        return None, "first message must be from the user"
    return out, None


@app.post("/api/chat")
def chat() -> Response:
    data = request.get_json(force=True) or {}
    messages, err = validate_chat_messages(data.get("messages"))
    if err:
        return jsonify({"error": err}), 400

    client = anthropic.Anthropic()

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def generate():
        try:
            with client.messages.stream(
                model=CHAT_MODEL,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield sse({"text": text})
            yield sse({"done": True})
        # SDK raises TypeError when no api_key/auth_token/credentials resolve
        except TypeError:
            yield sse({"error": "Chat is not configured. Set ANTHROPIC_API_KEY on the API server."})
        except anthropic.AuthenticationError:
            yield sse({"error": "Chat is misconfigured: the API key was rejected."})
        except anthropic.APIStatusError as e:
            yield sse({"error": f"Assistant unavailable ({e.status_code}). Try again shortly."})
        except anthropic.APIConnectionError:
            yield sse({"error": "Could not reach the assistant. Check the API server's network."})
        except Exception:
            yield sse({"error": "Assistant failed unexpectedly. Try again."})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/stats")
def stats():
    db = get_db()
    by_status = {row["status"]: row["c"] for row in db.execute(
        "SELECT status, COUNT(*) c FROM requests GROUP BY status")}
    by_type = {row["artifact_type"]: row["c"] for row in db.execute(
        "SELECT artifact_type, COUNT(*) c FROM requests GROUP BY artifact_type")}
    total = db.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"]
    return jsonify({
        "total": total,
        "byStatus": {s: by_status.get(s, 0) for s in LIFECYCLE},
        "byType": {t: by_type.get(t, 0) for t in ARTIFACT_TYPES},
    })


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
