# Fidelity Governance Portal — UI (Angular 17)

Smart, self-service front end for the Architecture Governance process.

## Run (dev)

```bash
cd ui
npm install
npm start        # ng serve with proxy -> http://localhost:4200
```

`npm start` uses `proxy.conf.json` to forward `/api/*` to the Flask API on
`http://localhost:5000`, so start the API first (see `../api/README.md`).

## Build (prod)

```bash
npm run build    # outputs to dist/governance-portal-ui/browser
```

## Screens
- **Dashboard** — lifecycle rail with live counts per stage, breakdown by
  artifact type, and recent activity.
- **Requests** — filterable/searchable queue (status, type, free text).
- **New / Edit intake** — full metadata form covering every governance field.
- **Request detail** — metadata, a lifecycle-transition control that records a
  note, and a status history timeline.

## Architecture
Standalone components + Angular Router. `GovernanceService` wraps the REST API;
`models/request.model.ts` holds the typed contract. Design tokens live in
`src/styles.css` (blueprint-console theme: Space Grotesk / IBM Plex Sans / Mono).

## Point at a different API
Edit the `target` in `proxy.conf.json` (dev) or set `base` in
`src/app/services/governance.service.ts`.
