# Governance Portal

Self-service portal for submitting and reviewing architecture governance requests — ARB intakes, ADRs,
Data / Messaging & Streaming / AI-ML architecture requests — from draft to decision, with ARB meeting
scheduling, a Team Board, insights, an assistant chat, and role-based access driven by Azure AD groups.

```
governance-portal/
├── api/            Python + Flask + SQLite   REST API under /api/v1   (port 5001)
├── ui/             Angular 17                Web UI                   (port 4200)
└── architecture/   ER diagram (PlantUML) and SQL: schema, reference data, sample queries
```

## Quick start

Terminal 1 — API:
```bash
cd api && pip install -r requirements.txt && python seed.py && python app.py
```

Terminal 2 — UI:
```bash
cd ui && npm install && npm start
```

Open http://localhost:4200 and pick a demo user to sign in as. `python seed.py` recreates the database
with 175 sample requests and 8 demo users; skip it to keep existing data.

## Governance lifecycle

`Draft → Submitted → In Review → (Scheduled / Chief Architecture Review) → Approved / Approved with Conditions / Rejected`,
with `Changes Requested` sending a request back to its author and `Withdrawn` for requests the author cancels.
Scheduled requests carry an ARB meeting date and time and appear on the Calendar. The statuses live in the
`request_statuses` table (`GET /api/v1/request-statuses`).

## Review types

- Architecture Review Board (ARB) Intake Request
- Data Architecture Intake Request
- Architecture Decision Record (ADR) Submission
- Messaging & Streaming Architecture Intake Request
- AI/ML Architecture Intake Request

## Access

Each role (Requestor, Reviewer, Admin, plus any an admin creates) is granted to members of an Azure AD
group, and holds a set of permissions edited on the Roles & permissions page. The demo sign-in stands in
for SSO; replace it with Azure AD / Entra ID before real use.

See [`api/README.md`](api/README.md) and [`ui/README.md`](ui/README.md) for details.
