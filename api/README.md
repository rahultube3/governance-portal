# Governance Portal — API (Python / Flask / SQLite)

REST API behind the Architecture Governance self-service portal: governance requests and their review
lifecycle, a Team Board, an assistant chat, and role-based access driven by Azure AD groups.

## Run

```bash
cd api
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
python seed.py        # optional: recreates governance.db with 315 sample requests and 9 demo users
python app.py         # http://localhost:5001 (debug mode, auto-reloads on file changes)
```

`governance.db` is created on first run. On every start, `init_db()` creates any missing tables, seeds the
demo users, roles and board when they are empty, and syncs the permission catalog and request statuses from
`portal/constants.py`. All of this is safe to repeat.

There are no schema migrations: after a schema change, recreate the database with `python seed.py`.

The Angular dev server proxies `/api` to `http://127.0.0.1:5001` (see `ui/proxy.conf.json`), so the browser
calls the API on the same origin.

### Layout

```
app.py                  entry point: builds the app, runs init_db(), serves on PORT
seed.py                 demo data loader
portal/
  __init__.py           create_app(): config, CORS, session auth hook, blueprint registration
  config.py             paths, secret key, environment settings
  constants.py          status codes, requestor steps, risk tiers, reviewer roles, permission catalog
  db.py                 per-request SQLite connection
  schema.py             tables, catalog sync, default users/roles/board and reference data
  auth.py               access resolution, require_permission, lockout guard
  workflow.py           the review route: which moves the caller may make, given status, tier and permissions
  validation_agent.py   Claude check of Low-risk intakes; a pass auto-approves
  serializers.py        row -> JSON shapes
  knowledge.py          document corpus for the chat assistant
  routes/               one blueprint per resource, all mounted under /api/v1
    auth.py  users.py  rbac.py  requests.py  board.py  chat.py  meta.py  reference.py (Reference Data)
```

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5001` | Port the API listens on |
| `GOV_PORTAL_SECRET_KEY` | contents of `api/.secret_key` (generated on first run, git-ignored) | Signs the session cookie. Set it explicitly in any shared environment |
| `ANTHROPIC_API_KEY` | — | Required for `/api/v1/chat` |
| `CHAT_MODEL` | `claude-sonnet-4-6` | Model used by `/api/v1/chat` |

## Conventions

- **Format.** Request and response bodies are JSON. Fields are camelCase (`arbTitle`, `createdBy`),
  except status-history entries, which keep the column names (`from_status`, `created_at`).
- **Errors.** Every error is `{"error": "<message>"}` with one of these codes:

  | Code | Meaning |
  |---|---|
  | `400` | Invalid input, or a change that would lock everyone out of permission management |
  | `401` | Not signed in |
  | `403` | Signed in but missing the permission, or a business rule refuses the action |
  | `404` | Not found, including requests you aren't allowed to see |

- **Timestamps** are ISO-8601 UTC strings (`2026-10-03T03:43:03Z`). Business dates such as
  `dateSubmitted` are `YYYY-MM-DD`.
- **Audit fields.** Every record carries `createdAt`, `createdBy`, `updatedAt` and `updatedBy`. The
  `*By` values are user IDs. `null` means the system wrote the row (seeding or the permission sync), or
  that the author has since been deleted.

## Authentication and permissions

**Sign-in (demo).** `POST /api/v1/auth/login` takes a user ID with no password and sets a signed session
cookie (HttpOnly, `SameSite=Lax`). This must be replaced with Azure AD / Entra ID SSO before real use.

**Access resolution.** It runs on every request:

1. The user's Azure AD groups. In the demo, these are the `ad_group` of the role in `users.role`. With
   SSO they come from the token's `groups` claim (`ad_groups_for()` in `portal/auth.py`).
2. Every role whose `ad_group` is one of those groups.
3. The combined set of permissions granted to those roles (`role_permissions`).

All endpoints except `/api/v1/health`, `/api/v1/auth/users`, `/api/v1/auth/roles`, `/api/v1/auth/login` and `/api/v1/auth/logout` return
`401` without a session. Endpoints marked with permissions below need **at least one** of them. Several
also apply ownership and status rules, which are described with each endpoint.

**Permission catalog.** Defaults can be changed on the Permissions page or with `PUT /api/v1/rbac/grants`.
A permission added to the catalog later is granted to the built-in roles listed for it in `DEFAULT_ROLES`
(`portal/schema.py`) on the next startup, once; after that only admins change it.
Admins can add roles there too (`POST /api/v1/rbac/roles`), but the permissions themselves are fixed in
`PERMISSION_CATALOG` because the API checks each code.

| Permission | Allows | Requestor | Reviewer | Chief Architect | Admin |
|---|---|:-:|:-:|:-:|:-:|
| `request:create` | Submit new requests | ✓ | | | ✓ |
| `request:view:own` | See requests you submitted | ✓ | | | ✓ |
| `request:view:all` | See every request | | ✓ | ✓ | ✓ |
| `request:edit:own` | Edit your own request while `DRAFT`, `SUBMITTED` or `CHANGES_REQUESTED`; review fields excluded | ✓ | | | ✓ |
| `request:edit:all` | Edit any request, including status, review dates and comments | | | | ✓ |
| `request:withdraw:own` | Withdraw your own request while `DRAFT` or `SUBMITTED` | ✓ | | | ✓ |
| `request:delete:all` | Delete any request | | | | ✓ |
| `request:resubmit` | Send your own `CHANGES_REQUESTED` request back to `SUBMITTED` | ✓ | | | ✓ |
| `request:review` | Make every review move except scheduling and deciding a Critical request, and raise a risk tier | | ✓ | ✓ | ✓ |
| `request:schedule` | Move requests to `SCHEDULED` and set or change the ARB meeting date and time | | ✓ | ✓ | ✓ |
| `request:signoff` | Decide Critical requests in `CHIEF_ARCHITECTURE_REVIEW` and lower a risk tier | | | ✓ | ✓ |
| `board:card:edit` | Add, edit, move and delete Team Board cards | | ✓ | ✓ | ✓ |
| `board:field:manage` | Add, rename and delete Team Board fields and lanes | | | | ✓ |
| `calendar:view` | Open the ARB Calendar (enforced by the UI; it reads `/api/v1/requests`) | ✓ | ✓ | ✓ | ✓ |
| `insights:view` | Open Insights (enforced by the UI; it reads `/api/v1/requests`) | | ✓ | ✓ | ✓ |
| `insights:export` | Export Insights as CSV (enforced by the UI) | | | | ✓ |
| `user:manage` | Manage users | | | | ✓ |
| `reference:manage` | Manage [Reference Data](#reference-data): add, edit, order, activate, deactivate and remove review types, PDLC checkpoints, reference link names and reviewers; edit status text | | | | ✓ |
| `role:assign` | Edit the permission matrix and create roles | | | | ✓ |

The Chief Architect role is created with a fresh database (`python seed.py`). On an existing database,
`request:signoff` goes to Admin only until an admin creates the role or grants it.

**Separation of duties.** Nobody, including admins, can change the status of a request they submitted.
The exceptions are the owner's own steps: submitting a draft, resubmitting after `CHANGES_REQUESTED`, and
withdrawing.

## Endpoint index

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/v1/health`](#get-apiv1health) | public |
| GET | [`/api/v1/meta`](#get-apiv1meta) | signed in |
| GET | [`/api/v1/request-statuses`](#get-apiv1request-statuses) | signed in |
| GET | [`/api/v1/auth/users`](#get-apiv1authusers) | public |
| GET | [`/api/v1/auth/roles`](#get-apiv1authroles) | public |
| POST | [`/api/v1/auth/login`](#post-apiv1authlogin) | public |
| POST | [`/api/v1/auth/logout`](#post-apiv1authlogout) | public |
| GET | [`/api/v1/auth/me`](#get-apiv1authme) | signed in |
| GET | [`/api/v1/requests`](#get-apiv1requests) | `request:view:own` / `request:view:all` |
| GET | [`/api/v1/requests/:id`](#get-apiv1requestsid) | `request:view:own` / `request:view:all` |
| POST | [`/api/v1/requests`](#post-apiv1requests) | `request:create` |
| PUT | [`/api/v1/requests/:id`](#put-apiv1requestsid) | `request:edit:own` / `request:edit:all` |
| PATCH | [`/api/v1/requests/:id/status`](#patch-apiv1requestsidstatus) | `request:review` / `request:schedule` / `request:signoff`, or an owner step |
| PATCH | [`/api/v1/requests/:id/tier`](#patch-apiv1requestsidtier) | `request:review` |
| DELETE | [`/api/v1/requests/:id`](#delete-apiv1requestsid) | `request:delete:all` |
| GET | [`/api/v1/stats`](#get-apiv1stats) | `request:view:own` / `request:view:all` |
| POST | [`/api/v1/chat`](#post-apiv1chat) | signed in |
| GET | [`/api/v1/board`](#get-apiv1board) | signed in |
| POST | [`/api/v1/board/fields`](#post-apiv1boardfields) | `board:field:manage` |
| PATCH | [`/api/v1/board/fields/:id`](#patch-apiv1boardfieldsid) | `board:field:manage` |
| DELETE | [`/api/v1/board/fields/:id`](#delete-apiv1boardfieldsid) | `board:field:manage` |
| POST | [`/api/v1/board/cards`](#post-apiv1boardcards) | `board:card:edit` |
| PATCH | [`/api/v1/board/cards/:id`](#patch-apiv1boardcardsid) | `board:card:edit` |
| DELETE | [`/api/v1/board/cards/:id`](#delete-apiv1boardcardsid) | `board:card:edit` |
| GET | [`/api/v1/users`](#get-apiv1users) | `user:manage` |
| POST | [`/api/v1/users`](#post-apiv1users) | `user:manage` |
| PATCH | [`/api/v1/users/:id`](#patch-apiv1usersid) | `user:manage` |
| DELETE | [`/api/v1/users/:id`](#delete-apiv1usersid) | `user:manage` |
| GET, POST | [`/api/v1/review-types`](#reference-data) | `reference:manage` |
| PATCH, DELETE | [`/api/v1/review-types/:id`](#reference-data) | `reference:manage` |
| GET, POST | [`/api/v1/pdlc-checkpoints`](#reference-data) | `reference:manage` |
| PUT | [`/api/v1/pdlc-checkpoints/order`](#reference-data) | `reference:manage` |
| PATCH, DELETE | [`/api/v1/pdlc-checkpoints/:id`](#reference-data) | `reference:manage` |
| GET, POST | [`/api/v1/artifact-names`](#reference-data) | `reference:manage` |
| PUT | [`/api/v1/artifact-names/order`](#reference-data) | `reference:manage` |
| PATCH, DELETE | [`/api/v1/artifact-names/:code`](#reference-data) | `reference:manage` |
| GET, POST | [`/api/v1/reviewers`](#reference-data) | `reference:manage` |
| PATCH, DELETE | [`/api/v1/reviewers/:id`](#reference-data) | `reference:manage` |
| POST | [`/api/v1/request-statuses`](#reference-data) | `reference:manage` |
| PATCH, DELETE | [`/api/v1/request-statuses/:code`](#reference-data) | `reference:manage` |
| GET | [`/api/v1/roles`](#get-apiv1roles) | `user:manage` / `role:assign` |
| GET | [`/api/v1/rbac`](#get-apiv1rbac) | `role:assign` |
| PUT | [`/api/v1/rbac/grants`](#put-apiv1rbacgrants) | `role:assign` |
| POST | [`/api/v1/rbac/roles`](#post-apiv1rbacroles) | `role:assign` |

---

## Reference

### `GET /api/v1/health`
Liveness check. Public.

```json
{ "status": "ok", "time": "2026-10-03T03:43:03Z" }
```

### `GET /api/v1/meta`
Reference lists used by the forms and filters. Review types, PDLC checkpoints, reference link names and
reviewers come from the [Reference Data](#reference-data) tables and include inactive entries (`active: false`)
so a form can still show a value an older request holds; offer only active ones for new choices. `riskTiers`
are the four fixed tiers with their routes, and `finalStatuses` lists the statuses with no way out.

```json
{
  "artifactTypes": [{ "id": 1, "name": "AI/ML Solution Architecture", "active": true }, "..."],
  "artifactNames": [
    { "code": "SAD", "label": "SAD", "requiredFor": ["Solution Architecture (SAD)", "Architecture Decision Records (ADR)", "Event-Driven Architecture Design", "Data Architecture & Modeling", "Architecture Certification"], "active": true },
    { "code": "ADR", "label": "ADR", "requiredFor": ["Architecture Decision Records (ADR)"], "active": true },
    { "code": "PATTERNS", "label": "Patterns & Standards", "requiredFor": ["Architecture Patterns & Standards"], "active": true },
    "..."
  ],
  "maxArtifacts": 5,
  "reviewerRoles": [
    { "code": "BU", "label": "BU Governance Reviewer", "field": "buGovReviewers" },
    { "code": "FAE", "label": "FAE Governance Reviewer", "field": "eaGovReviewers" },
    { "code": "ECS", "label": "ECS (Security) Reviewer", "field": "ecsReviewers" }
  ],
  "reviewers": [{ "id": 1, "name": "J. Rivera", "role": "BU", "active": true }, "..."],
  "pdlcCheckpoints": [{ "id": 1, "name": "Inception", "active": true }, "..."],
  "riskTiers": [
    { "tier": 1, "label": "Low", "route": "Agent validation: auto-approved when it passes, otherwise a reviewer decides." },
    { "tier": 2, "label": "Medium", "route": "..." },
    { "tier": 3, "label": "High", "route": "..." },
    { "tier": 4, "label": "Critical", "route": "Reviewer assessment, an ARB meeting, then Chief Architect approval." }
  ],
  "finalStatuses": ["APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED", "WITHDRAWN"]
}
```

### `GET /api/v1/request-statuses`
The request status lookup (`request_statuses` table), in lifecycle order. See
[Governance lifecycle](#governance-lifecycle).

```json
[
  { "code": "DRAFT", "label": "Draft", "meaning": "Saved, not submitted", "whoActs": "Requestor", "position": 0,
    "createdAt": "2026-10-03T17:28:53Z", "createdBy": null, "updatedAt": "2026-10-03T17:28:53Z", "updatedBy": null },
  "..."
]
```

## Authentication

### `GET /api/v1/auth/users`
The demo sign-in directory, which the UI also uses to turn `*By` IDs into names. Public.

```json
[{ "id": 8, "name": "Portal Admin", "email": "admin@example.com", "role": "ADMIN" }]
```

### `GET /api/v1/auth/roles`
Every role's code, name and description, so the sign-in page can group the directory. Public.

```json
[{ "code": "ADMIN", "name": "Admin", "description": "Full access, including users and permissions." }]
```

### `POST /api/v1/auth/login`
Signs in as a user and sets the session cookie. Public. Body: `{ "userId": 8 }`.
Returns the session user, the same as [`GET /api/v1/auth/me`](#get-apiv1authme). `400` for an unknown user.

### `POST /api/v1/auth/logout`
Clears the session. Public. Returns `{ "ok": true }`.

### `GET /api/v1/auth/me`
The signed-in user and their resolved access.

```json
{
  "id": 8, "name": "Portal Admin", "email": "admin@example.com", "role": "ADMIN",
  "adGroups": ["AAD-GovPortal-Admins"],
  "roles": ["ADMIN"],
  "roleNames": ["Admin"],
  "permissions": ["board:card:edit", "request:create", "role:assign", "..."]
}
```

## Governance requests

**Request object** (returned by every endpoint below):

| Field | Type | Notes |
|---|---|---|
| `id` | number | Shown in the UI as `ARB-<id>` |
| `arbTitle` | string | Required |
| `summary`, `pr`, `appId`, `appName`, `trackitId` | string \| null | |
| `artifacts` | `{ code, link }[]` | Architecture Reference Links: up to 5 (`meta.maxArtifacts`), stored as JSON on the request. `code` is an `artifact_names` code (`meta.artifactNames`); `link` is free text up to 2,000 characters (the UI makes `http(s)` values clickable). Responses add each `label`. Sending it replaces the whole list. Outside `DRAFT`, the request must carry every active reference whose `requiredFor` lists its review type. An inactive code is refused unless the request already had it |
| `intelEaCapabilityLink` | string \| null | Free text; required outside `DRAFT` |
| `solutionId` | string \| null | Free text |
| `solutionArchitect`, `saContributors` | string \| null | |
| `artifactType` | string | Required; an active review type name (or the one the request already has) |
| `pdlcCheckpoint` | string \| null | An active PDLC checkpoint name (or the one the request already has) |
| `dateSubmitted` | `YYYY-MM-DD` | Set by the system: today when the request is created, and again when a draft is submitted. Ignored in request bodies |
| `dateReviewed`, `approvalDate` | `YYYY-MM-DD` \| null | Review field |
| `meetingDate` | `YYYY-MM-DD` \| null | ARB meeting date; review field; required while `SCHEDULED` |
| `meetingTime` | `HH:MM` \| null | ARB meeting time (24-hour, the meeting's local time); review field; required while `SCHEDULED`; needs `meetingDate` |
| `buGovReviewers`, `eaGovReviewers`, `ecsReviewers` | string[] | BU Governance, FAE Governance and ECS (Security) reviewer names, any number per role (empty list for none). Each name must be an active [reviewer](#reviewers) of that role (`BU`, `FAE`, `ECS`) or one the request already has; duplicates are dropped. The intake form starts a new request with every active reviewer ticked |
| `status` | string | A `request_statuses` code; review field (see `POST` for drafts); defaults to `SUBMITTED` |
| `comments` | string \| null | Review field |
| `riskTier` | 1–4 \| null | 1 Low, 2 Medium, 3 High, 4 Critical (see `meta.riskTiers`). Set by the requestor; required outside `DRAFT`. After submission only [`PATCH .../tier`](#patch-apiv1requestsidtier) changes it |
| `agentReview` | object \| null | The validation agent's verdict on a Low request: `{ passed, summary, findings, checkedAt }`. Read-only |
| `createdAt`, `createdBy`, `updatedAt`, `updatedBy` | audit | `createdBy` is the request's owner |

*Review fields* (`status`, `dateReviewed`, `approvalDate`, `meetingDate`, `meetingTime`, `comments`) are silently dropped from create
and update bodies unless the caller holds `request:edit:all`.

**Visibility.** With `request:view:all` you see everything. With only `request:view:own` you see requests
you created. Other people's requests return `404`. Drafts are only visible to their owner, whatever
the caller's permissions.

### `GET /api/v1/requests`
Lists visible requests, most recently updated first.

| Query | Effect |
|---|---|
| `status` | Exact match, e.g. `SUBMITTED` |
| `artifactType` | Exact match |
| `search` | Substring match on title, summary, app name or TrackIT ID |

Returns an array of request objects.

### `GET /api/v1/requests/:id`
One request plus its status history, oldest first. For a reviewer who doesn't own the request,
`nextSteps` lists every review move from the current status, each with `blocked`: `null` if the caller
can make it, otherwise the reason they can't. It is empty for owners and final statuses.

```json
{
  "id": 3, "arbTitle": "Zero-Trust Network Segmentation (202601-03)", "status": "APPROVED", "...": "...",
  "history": [
    { "from_status": null, "to_status": "CHIEF_ARCHITECTURE_REVIEW", "note": "Seeded",
      "created_at": "2026-07-26T01:52:44Z", "created_by": null },
    { "from_status": "CHIEF_ARCHITECTURE_REVIEW", "to_status": "APPROVED", "note": "",
      "created_at": "2026-07-26T02:24:56Z", "created_by": 6 }
  ]
}
```

### `POST /api/v1/requests`
Creates a request owned by the caller and records a `Created` history entry. Body: any request fields;
`arbTitle` and a valid `artifactType` are required. Without `request:edit:all`, `status` may only be
`DRAFT` (save a draft) or `SUBMITTED` (the default); anything else is `403`. Returns `201` with the request.
`400` for a missing title, an invalid review type, an invalid status, or a missing or invalid `riskTier`
outside `DRAFT`, invalid `artifacts`, or a missing required artifact or `intelEaCapabilityLink` outside `DRAFT`. A Low request submitted here goes straight to [agent validation](#agent-validation).

### `PUT /api/v1/requests/:id`
Partial update; only the fields sent are changed.

- Without `request:edit:all`, you must own the request and it must be `DRAFT`, `SUBMITTED` or
  `CHANGES_REQUESTED` (`403`
  otherwise), and review fields are dropped.
- A status change made here follows the same review rules as `PATCH .../status` and is recorded in the
  history (with `comments` as the note). It is refused (`403`) if you own the request.
- `riskTier` can change only while the request is `DRAFT` (`403` otherwise).

### `PATCH /api/v1/requests/:id/status`
Moves a request through the lifecycle. Body: `{ "status": "APPROVED", "note": "optional", "dateReviewed": "optional YYYY-MM-DD" }`.

- **Owner steps** apply when you own the request. Review dates are left unchanged.

  | From | To | Needs |
  |---|---|---|
  | `DRAFT` | `SUBMITTED` (also sets `dateSubmitted` to today; needs a `riskTier`, an `intelEaCapabilityLink` and any required artifact) | `request:create` |
  | `CHANGES_REQUESTED` | `SUBMITTED` | `request:resubmit` |
  | `DRAFT` or `SUBMITTED` | `WITHDRAWN` | `request:withdraw:own` |

  Submitting or resubmitting a Low request runs [agent validation](#agent-validation) before the response.

- **Review** (you must not own the request). This sets `dateReviewed` (default today), and sets
  `approvalDate` to today the first time the request reaches `APPROVED` or `APPROVED_WITH_CONDITIONS`.
  The moves depend on the risk tier (`portal/workflow.py`). "Decide" means `APPROVED` or
  `APPROVED_WITH_CONDITIONS`; `CHANGES_REQUESTED` and `REJECTED` are open from every review status.

  | From | Low | Medium, High | Critical |
  |---|---|---|---|
  | `SUBMITTED` | `IN_REVIEW` | `IN_REVIEW` | `IN_REVIEW` |
  | `IN_REVIEW` | decide | `SCHEDULED` | `SCHEDULED` |
  | `SCHEDULED` | decide, reschedule | decide, reschedule | `CHIEF_ARCHITECTURE_REVIEW`, reschedule |
  | `CHIEF_ARCHITECTURE_REVIEW` | decide | decide | decide |

  A move to `SCHEDULED` needs `request:schedule`; any move out of `CHIEF_ARCHITECTURE_REVIEW` needs
  `request:signoff`; every other move needs `request:review`. A Low request is normally decided by the
  agent and reaches `IN_REVIEW` only when validation fails.
- **Scheduling.** Moving to `SCHEDULED` needs `meetingDate` (`YYYY-MM-DD`) and `meetingTime` (`HH:MM`) in
  the body. Sending `SCHEDULED` again with both reschedules. Later moves keep the last meeting.

Every change adds a history entry. Returns the updated request. `400` for an unknown status, a missing
or invalid `meetingDate` or `meetingTime`, or submitting without a risk tier; `403` with the reason
when the move isn't allowed.

### `PATCH /api/v1/requests/:id/tier`
Changes the risk tier. Needs `request:review`; you must not own the request, and it must be in review
(not `DRAFT` or final). Body: `{ "tier": 4, "reason": "Touches the payments ledger" }`; a reason is required.
Lowering the tier needs `request:signoff`, so one reviewer can't route a request around the ARB or the
Chief Architect. Changing the tier never re-runs agent validation. Adds a history entry and returns the
updated request. `400` for an invalid tier or a missing reason.

### `DELETE /api/v1/requests/:id`
Permanently deletes the request and its history. Needs `request:delete:all`. Requestors withdraw instead,
which keeps the request (see the owner steps above). Returns `{ "deleted": 3 }`.

### `GET /api/v1/stats`
Counts over the requests the caller can see. `byStatus` has every status code.

```json
{
  "total": 315,
  "byStatus": { "DRAFT": 0, "SUBMITTED": 34, "IN_REVIEW": 0, "...": 0, "APPROVED": 72 },
  "byType": { "Solution Architecture (SAD)": 35, "...": 35 }
}
```

## Reference Data

The lists behind the intake form live in the database and are managed on **Administration → Reference Data**.
On first start the API fills an empty table with defaults (`DEFAULT_*` in `portal/schema.py`); after that the
data is the admins' and restarts never overwrite it. Every list endpoint needs `reference:manage`.

| List | Table | Key | Order | Requests store |
|---|---|---|---|---|
| Review types | `review_types` | `id` | by name | the name, in `artifact_type` |
| PDLC checkpoints | `pdlc_checkpoints` | `id` | `position` | the name, in `pdlc_checkpoint` |
| Reference link names | `artifact_names` | `code` | `position` | the code, in the `artifacts` JSON |
| Reviewers | `reviewers` | `id` | role, then name | names, in the three reviewer JSON lists |
| Lifecycle statuses | `request_statuses` | `code` | lifecycle, then pause steps | the code, in `status` |

Rules shared by the editable lists:

- **Names are unique** (ignoring case; reviewers per role). A clash is `409`. Names are 1–120 characters.
- **Deactivate** (`{ "active": false }`) hides an entry from new choices; requests that already use it keep it
  and can still be edited. A deactivated reference link name also stops counting as required.
- **Remove** (`DELETE`) works only while no request uses the entry; otherwise `409` with the count, e.g.
  `"35 requests use Architecture Certification, so it can't be removed. Deactivate it instead."`
- **Rename** (`{ "name": "..." }`) carries over to the requests that use the entry. Renaming a review type also
  renames it in every reference link's `requiredFor`; removing one drops it from there.
- **List responses** add `inUse`, the number of requests using each entry, and the audit fields.

| Endpoint | Body | Notes |
|---|---|---|
| `GET /review-types` | | `{ id, name, active, inUse }` by name |
| `POST /review-types` | `{ "name" }` | `201` |
| `PATCH /review-types/:id` | `{ "name"?, "active"? }` | |
| `DELETE /review-types/:id` | | `{ "deleted": id }` |
| `GET /pdlc-checkpoints` | | `{ id, name, position, active, inUse }` in order |
| `POST /pdlc-checkpoints` | `{ "name" }` | added last |
| `PUT /pdlc-checkpoints/order` | `{ "order": [ids] }` | must list every id once; returns the list |
| `PATCH`, `DELETE /pdlc-checkpoints/:id` | as review types | |
| `GET /artifact-names` | | `{ code, label, requiredFor, position, active, inUse }` in order |
| `POST /artifact-names` | `{ "label", "requiredFor"?: [review type names] }` | the code is made from the label, e.g. `THREAT_MODEL` |
| `PUT /artifact-names/order` | `{ "order": [codes] }` | |
| `PATCH /artifact-names/:code` | `{ "label"?, "requiredFor"?, "active"? }` | |
| `DELETE /artifact-names/:code` | | |
| `GET /reviewers` | | `{ id, name, role, active, inUse }` by role and name |
| `POST /reviewers` | `{ "name", "role": "BU" \| "FAE" \| "ECS" }` | |
| `PATCH /reviewers/:id` | `{ "name"?, "active"? }` | |
| `DELETE /reviewers/:id` | | |
| `POST /request-statuses` | `{ "label", "meaning", "whoActs" }` | adds a pause step (see below); the code is made from the label, e.g. `ON_HOLD` |
| `PATCH /request-statuses/:code` | `{ "label"?, "meaning"?, "whoActs"?, "active"? }` | `active` only on pause steps and the optional built-ins (`deactivatable: true`) |
| `DELETE /request-statuses/:code` | | pause steps only, while no request is in it or has ever been (`409` otherwise) |

Lifecycle statuses differ from the other lists because the review route depends on them:

- **Built-in** statuses (`builtin: true`) always exist. Draft, Submitted, In Review, Scheduled, Chief Architecture
  Review and Approved are the route's backbone and always stay active. Approved with Conditions, Changes
  Requested, Rejected and Withdrawn can be deactivated: nobody can move a request into a deactivated status
  (`403 "Withdrawn is deactivated"`), and requests already in it can still leave.
- **Pause steps** are the statuses admins add, e.g. On Hold. A reviewer can move a request into one from In Review,
  Scheduled or Chief Architecture Review, and out of it back to that status or to Changes Requested or Rejected.
  Pausing or resuming at Chief Architecture Review needs `request:signoff`. They sort after the built-ins.
- `GET /request-statuses` returns `active`, `builtin`, `deactivatable` and `inUse` (requests in it now) with each status.

## Agent validation

When a Low request is submitted (on create, submit or resubmit), `portal/validation_agent.py` sends its
intake fields and the governance standards (`portal/knowledge.py`) to Claude (`CHAT_MODEL`) and asks for a
structured verdict. The request is updated after the submit is committed, before the API responds:

| Verdict | Result |
|---|---|
| Pass | `APPROVED`, with `approvalDate` set; the history note starts "Auto-approved by agent validation" |
| Fail | `IN_REVIEW` with the agent's summary and findings in `agentReview`; a reviewer decides |
| None (no `ANTHROPIC_API_KEY`, API error, refusal) | `IN_REVIEW`; a reviewer decides |

History entries the agent writes have `created_by: null`. The agent can't open the artifact link, and the
prompt treats every intake field as data, not instructions.

## Assistant

### `POST /api/v1/chat`
Streams an answer about the governance standards (`portal/knowledge.py`) as Server-Sent Events.
Body: `{ "messages": [{ "role": "user", "content": "How do I submit an ADR?" }] }`. Each `role` is
`user` or `assistant`, content must be non-empty, and the first message must be from `user`. Only the last 40 turns are kept, and each message is
cut to 4,000 characters. `400` for a malformed body.

The stream sends `data:` lines with one of three payloads:

| Payload | Meaning |
|---|---|
| `{"text": "..."}` | One chunk of the answer; append chunks in order |
| `{"done": true}` | The answer is complete |
| `{"error": "..."}` | Something failed, for example a missing or rejected `ANTHROPIC_API_KEY`, the service being unavailable or a network failure |

## Team Board

**Field object:** `id`, `key` (unique), `label`, `type` (`text` | `number` | `date` | `select` |
`checkbox`), `options` (array, select fields only), `position`, `isTitle`, `isGroup`, and the audit fields.
At most one field is the title, and at most one is the grouping field (its options are the board's lanes).

**Card object:** `id`, `data` (an object keyed by field `key`), `position`, and the audit fields.

### `GET /api/v1/board`
Returns `{ "fields": [Field], "cards": [Card] }`, both sorted by position.

### `POST /api/v1/board/fields`
Body: `{ "label": "Priority", "type": "select", "options": ["Low", "High"], "isTitle": false, "isGroup": false }`.
`key` is generated from the label unless given. Setting `isTitle` or `isGroup` moves that role away from
the field that had it. Returns `201` with the field. `400` for a missing label, an unknown type or a
duplicate key.

### `PATCH /api/v1/board/fields/:id`
Partial update of `label`, `options`, `position`, `isTitle` or `isGroup`. Returns the field.

### `DELETE /api/v1/board/fields/:id`
Deletes the field and removes its key from every card's `data`. The title and grouping fields can't be
deleted (`400`); assign those roles to another field first. Returns `{ "deleted": 4 }`.

### `POST /api/v1/board/cards`
Body: `{ "data": { "title": "Draft ARB template", "status": "Backlog" }, "position": 0 }`. `position`
defaults to the end. Returns `201` with the card.

### `PATCH /api/v1/board/cards/:id`
Body: `{ "data": { ... }, "position": 3 }`, both optional. `data` is **merged** into the existing values.
Returns the card.

### `DELETE /api/v1/board/cards/:id`
Returns `{ "deleted": 1 }`.

## Users

**Managed user object:** `id`, `name`, `email`, `role` (`REQUESTOR` | `REVIEWER` | `ADMIN`), and the audit
fields. In the demo, `role` is the user's AD group membership. With SSO, membership comes from Azure AD.

### `GET /api/v1/users`
Returns all users, sorted by role then name.

### `POST /api/v1/users`
Body: `{ "name": "Jane Doe", "email": "jane@company.com", "role": "REVIEWER" }`. The email is stored
lowercase and must be unique. Returns `201` with the user. `400` for a missing name, an invalid email, an
unknown role or a duplicate email.

### `PATCH /api/v1/users/:id`
Partial update of `name` or `role`. Returns the user. `400` if the change would leave nobody holding
`role:assign`.

### `DELETE /api/v1/users/:id`
Deletes a user. Their audit references become `null`, and requests they own lose their owner. You can't
delete yourself, and you can't remove the last person holding `role:assign` (`400`).
Returns `{ "deleted": 9 }`.

## Roles and permissions

### `GET /api/v1/roles`
A lightweight role list for pickers.

```json
[{ "code": "REQUESTOR", "name": "Requestor", "adGroup": "AAD-GovPortal-Requestors" }]
```

### `GET /api/v1/rbac`
The full permission matrix.

```json
{
  "permissions": [
    { "code": "request:create", "category": "Requests", "label": "Create requests",
      "description": "Submit new intake requests." }
  ],
  "roles": [
    {
      "id": 1, "code": "REQUESTOR", "name": "Requestor", "adGroup": "AAD-GovPortal-Requestors",
      "description": "Submits intakes and tracks their own requests.",
      "permissions": ["request:create", "request:edit:own", "..."],
      "grants": { "request:create": { "grantedAt": "2026-10-03T02:55:54Z", "grantedBy": null } },
      "memberCount": 2,
      "createdAt": "...", "createdBy": null, "updatedAt": "...", "updatedBy": null
    }
  ]
}
```

### `PUT /api/v1/rbac/grants`
Replaces the permission set of each role in the body. Roles you leave out are unchanged.
Body: `{ "grants": { "REVIEWER": ["request:view:all", "request:review", "board:card:edit"] } }`.

- New grants record who granted them and when.
- Unchanged grants keep their original audit data.

Returns the [`GET /api/v1/rbac`](#get-apiv1rbac) snapshot. `400` for an unknown role or permission, or if the
change would leave nobody holding `role:assign`.

### `POST /api/v1/rbac/roles`
Creates a role. Body:
`{ "code": "SECURITY_REVIEWER", "name": "Security Reviewer", "adGroup": "AAD-GovPortal-Security", "description": "...", "permissions": ["request:view:all", "request:review"] }`.

- `code` is upper-cased and must be 2–32 letters, digits or underscores, starting with a letter. It can't be changed later.
- `adGroup` and `description` are optional. A role without an AD group is granted to nobody.
- Grants record the creator as `grantedBy`.

Returns `201` with the snapshot. `400` for a duplicate or invalid code, a missing name, or an unknown permission.

---

## Governance lifecycle

Statuses live in the `request_statuses` lookup, which the API syncs from `REQUEST_STATUSES` in
`portal/constants.py` on startup. `requests.status` is a foreign key to it.

| Code | Label | Meaning | Who acts |
|---|---|---|---|
| `DRAFT` | Draft | Saved, not submitted | Requestor |
| `SUBMITTED` | Submitted | Waiting for a reviewer to pick it up | Reviewer |
| `IN_REVIEW` | In Review | Reviewer is assessing it | Reviewer |
| `CHANGES_REQUESTED` | Changes Requested | Sent back for changes | Requestor |
| `SCHEDULED` | Scheduled | Booked for an Architecture Review Board meeting | Admin / Chief Architect / Reviewer |
| `CHIEF_ARCHITECTURE_REVIEW` | Chief Architecture Review | Escalated for final architecture sign-off | Chief Architect |
| `APPROVED` | Approved | Final approval | Admin / Chief Architect / Reviewer |
| `APPROVED_WITH_CONDITIONS` | Approved with Conditions | Approved, with conditions attached | Admin / Chief Architect / Reviewer |
| `REJECTED` | Rejected | Final rejection | Admin / Chief Architect / Reviewer |
| `WITHDRAWN` | Withdrawn | Cancelled by the Requestor | Requestor |

`who_acts` is descriptive; permissions decide who can actually move a request. The UI's Kanban Board
groups them as:

| Kanban column | Statuses |
|---|---|
| Submitted | `SUBMITTED` |
| In Review | `IN_REVIEW`, `SCHEDULED` |
| Changes Requested | `CHANGES_REQUESTED` |
| Chief Architecture Review | `CHIEF_ARCHITECTURE_REVIEW` |
| Approved | `APPROVED`, `APPROVED_WITH_CONDITIONS` |
| Rejected | `REJECTED` |

Drafts and withdrawn requests have no column.

Every status change is written to `status_history` with who made it.

## Data model

Nine SQLite tables:

| Area | Tables |
|---|---|
| Governance requests | `requests`, `status_history`, `request_statuses` (status lookup) |
| Identity and access | `users`, `roles`, `permissions`, `role_permissions` |
| Team Board | `board_fields`, `board_cards` |

Every table has `created_at`, `created_by`, `updated_at` and `updated_by`.

- Diagram: [`architecture/er-diagram.puml`](../architecture/er-diagram.puml)
- Schema script: [`architecture/sql/schema.sql`](../architecture/sql/schema.sql) (mirrors `SCHEMA` in `portal/schema.py`)
- Reference data: [`architecture/sql/reference-data.sql`](../architecture/sql/reference-data.sql) (roles, permissions, grants, request statuses)
- Ready-made queries: [`architecture/sql/queries.sql`](../architecture/sql/queries.sql)
