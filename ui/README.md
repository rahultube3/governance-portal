# Governance Portal — UI (Angular 17)

Self-service front end for the Architecture Governance process.

## Run (dev)

```bash
cd ui
npm install
npm start        # ng serve with proxy -> http://localhost:4200
```

`npm start` uses `proxy.conf.json` to forward `/api/*` to the Flask API on `http://127.0.0.1:5001`
(the API lives under `/api/v1`), so start the API first (see `../api/README.md`).

## Build (prod)

```bash
npm run build    # outputs to dist/governance-portal-ui/browser
```

## Screens

What each user sees depends on their permissions (see the permission catalog in `../api/README.md`).

- **Sign in** — demo sign-in: pick a user, grouped by role.
- **Dashboard** — counts per request status, breakdown by review type, and recent activity.
- **Requests** — filterable, searchable queue (status, review type, free text).
- **New / Edit intake** — full metadata form; requestors can save a draft or submit.
- **Request detail** — metadata, status history, and the actions the user is allowed: submit a draft,
  resubmit after changes, withdraw, review (with ARB meeting date and time when scheduling), delete.
- **Board** — shared Team Board with user-defined fields and lanes.
- **Kanban Board** — governance requests by review stage, filterable by month, quarter or year.
- **Calendar** — month view of requests on their ARB meeting date, with an agenda for the month.
- **Insights** — intake, throughput and completion by review type, with CSV export.
- **Help** — FAQs, standards links and an assistant chat.
- **Users** and **Roles & permissions** — user management, the permission matrix, and new roles.

## Architecture

Standalone components with the Angular Router (`app.routes.ts`); routes declare the permissions they need
and `core/auth.guard.ts` enforces them. Services in `services/` wrap the REST API, and `models/` holds the
typed contract. `RequestStatusService` loads the status lookup (labels, order, who acts) from
`GET /api/v1/request-statuses`. Design tokens live in `src/styles.css` (IBM Plex Sans, dark and light
themes).

## Point at a different API

Edit the `target` in `proxy.conf.json`.
