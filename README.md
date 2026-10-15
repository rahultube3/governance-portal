# Governance Portal

Self-service portal for submitting and reviewing architecture governance requests — solution architecture,
ADRs, event-driven, AI/ML, API and data designs, patterns, certifications and due diligence — from draft to decision, with ARB meeting
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
with 315 sample requests and 9 demo users; skip it to keep existing data.

## Governance lifecycle

`Draft → Submitted → In Review → Scheduled → (Chief Architecture Review) → Approved / Approved with Conditions / Rejected`,
with `Changes Requested` sending a request back to its author and `Withdrawn` for requests the author cancels.
Scheduled requests carry an ARB meeting date and time and appear on the Calendar. The statuses live in the
`request_statuses` table (`GET /api/v1/request-statuses`). Approved, Approved with Conditions, Rejected and
Withdrawn are final. Admins can add pause steps (e.g. On Hold) that reviewers move a request into and back out
of, and can deactivate the optional outcomes; see Reference data below.

## Risk tiers

The requestor rates each intake against the risk-based framework before submitting it. The tier decides
the route, which is fixed in code (`api/portal/workflow.py`):

| Tier | Route |
|---|---|
| Low | A Claude validation agent checks the intake against the standards when it is submitted. A pass approves it with no human review; a fail, or no verdict, puts it In Review and a reviewer decides |
| Medium | In Review, then an ARB meeting (Scheduled); a reviewer decides |
| High | In Review, then an ARB meeting (Scheduled); a reviewer decides |
| Critical | In Review, then an ARB meeting, then Chief Architecture Review; only the Chief Architect decides |

After submission only a reviewer changes the tier, with a reason. Any reviewer can raise it; only the Chief
Architect can lower it. The agent uses the model in `CHAT_MODEL` and needs `ANTHROPIC_API_KEY` on the API
server; without it every Low request goes to a reviewer.

## Reference data

Admins manage the lists behind the intake form on **Administration → Reference Data** (`reference:manage`):
Review Types, PDLC Checkpoints, Architecture Reference Link names (and which review types require each one),
Reviewers, and the text of the Lifecycle Statuses. Entries can be added, renamed, reordered where order
matters, activated, deactivated, and removed while no request uses them. A new database starts with the
defaults in `api/portal/schema.py`, including these review types: Solution Architecture (SAD), Architecture
Decision Records (ADR), Event-Driven Architecture Design, AI/ML Solution Architecture, API Contract & Design,
Architecture Patterns & Standards, Data Architecture & Modeling, Architecture Certification and Architecture
Due Diligence.

## Access

Each role (Requestor, Reviewer, Chief Architect, Admin, plus any an admin creates) is granted to members of an Azure AD
group, and holds a set of permissions edited on the Roles & permissions page. The demo sign-in stands in
for SSO; replace it with Azure AD / Entra ID before real use.

See [`api/README.md`](api/README.md) and [`ui/README.md`](ui/README.md) for details.
