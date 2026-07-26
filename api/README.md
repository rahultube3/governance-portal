# Governance Portal — API (Python / Flask / SQLite)

REST API backing the Architecture Governance self-service portal.

## Run

```bash
cd api
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
python seed.py        # creates governance.db with 5 sample records (optional)
python app.py         # serves on http://localhost:5000
```

The SQLite file `governance.db` is created automatically on first run.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | Liveness check |
| GET  | `/api/meta` | Artifact types, lifecycle statuses, PDLC checkpoints |
| GET  | `/api/stats` | Totals by status and by artifact type |
| GET  | `/api/requests` | List (filters: `?status=`, `?artifactType=`, `?search=`) |
| GET  | `/api/requests/:id` | One request + status history |
| POST | `/api/requests` | Create (requires `arbTitle`, valid `artifactType`) |
| PUT  | `/api/requests/:id` | Update any fields |
| PATCH| `/api/requests/:id/status` | Transition status (body: `{status, note}`) — auto-sets approval/review dates |
| DELETE | `/api/requests/:id` | Delete request + history |

## Governance lifecycle
`PENDING → APPROVED FB → APPROVED EA → FOLLOW UP → REWORK`

Every status change is written to `status_history` and surfaced on the detail view.

## Data model (`requests`)
arb_title, summary, artifact_link, pr, app_id, app_name, trackit_id,
solution_architect, sa_contributors, artifact_type, pdlc_checkpoint,
date_submitted, date_reviewed, bu_gov_reviewer, ea_gov_reviewer,
status, approval_date, comments, created_at, updated_at
