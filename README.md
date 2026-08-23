# Governance Portal

Self-service portal for submitting and reviewing architecture governance
artifacts — ARB intakes, ADRs, Data / Messaging & Streaming / AI-ML architecture
requests — across the governance lifecycle.

Two independent workspaces:

```
governance-portal/
├── api/    Python + Flask + SQLite   REST API        (port 5000)
└── ui/     Angular 17                Smart UI         (port 4200)
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

Open http://localhost:4200.

## Governance lifecycle
`PENDING → APPROVED FB → APPROVED EA → FOLLOW UP → REWORK`

## Artifact types
- Architecture Review Board (ARB) Intake Request
- Data Architecture Intake Request
- Architecture Decision Record (ADR) Submission
- Messaging & Streaming Architecture Intake Request
- AI/ML Architecture Intake Request

See each workspace's README for details.
