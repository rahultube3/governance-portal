# Governance Portal — API (Python / Flask / SQLite)

REST API behind the Architecture Governance self-service portal: governance requests and their review
lifecycle, a Team Board, an assistant chat, and role-based access driven by Azure AD groups.

## Run

```bash
cd api
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
python seed.py        # optional: recreates governance.db with 175 sample requests and 8 demo users
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
  constants.py          review types, request statuses, PDLC checkpoints, permission catalog
  db.py                 per-request SQLite connection
  schema.py             tables, catalog sync, default users/roles/board
  auth.py               access resolution, require_permission, lockout guard
  serializers.py        row -> JSON shapes
  knowledge.py          document corpus for the chat assistant
  routes/               one blueprint per resource, all mounted under /api/v1
    auth.py  users.py  rbac.py  requests.py  board.py  chat.py  meta.py
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

| Permission | Allows | Requestor | Reviewer | Admin |
|---|---|:-:|:-:|:-:|
| `request:create` | Submit new requests | ✓ | | ✓ |
| `request:view:own` | See requests you submitted | ✓ | | ✓ |
| `request:view:all` | See every request | | ✓ | ✓ |
| `request:edit:own` | Edit your own request while `DRAFT`, `SUBMITTED` or `CHANGES_REQUESTED`; review fields excluded | ✓ | | ✓ |
| `request:edit:all` | Edit any request, including status, review dates and comments | | | ✓ |
| `request:withdraw:own` | Withdraw your own request while `DRAFT` or `SUBMITTED` | ✓ | | ✓ |
| `request:delete:all` | Delete any request | | | ✓ |
| `request:resubmit` | Send your own `CHANGES_REQUESTED` request back to `SUBMITTED` | ✓ | | ✓ |
| `request:review` | Change the status of other people's requests (except to `SCHEDULED`) | | ✓ | ✓ |
| `request:schedule` | Move other people's requests to `SCHEDULED` and set or change the ARB meeting date and time | | ✓ | ✓ |
| `board:card:edit` | Add, edit, move and delete Team Board cards | | ✓ | ✓ |
| `board:field:manage` | Add, rename and delete Team Board fields and lanes | | | ✓ |
| `calendar:view` | Open the ARB Calendar (enforced by the UI; it reads `/api/v1/requests`) | ✓ | ✓ | ✓ |
| `insights:view` | Open Insights (enforced by the UI; it reads `/api/v1/requests`) | | ✓ | ✓ |
| `insights:export` | Export Insights as CSV (enforced by the UI) | | | ✓ |
| `user:manage` | Manage users | | | ✓ |
| `role:assign` | Edit the permission matrix and create roles | | | ✓ |

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
| PATCH | [`/api/v1/requests/:id/status`](#patch-apiv1requestsidstatus) | `request:review` / `request:schedule`, or an owner step |
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
Reference lists used by the forms and filters.

```json
{
  "artifactTypes": [
    "Architecture Review Board (ARB) Intake Request",
    "Data Architecture Intake Request",
    "Architecture Decision Record (ADR) Submission",
    "Messaging & Streaming Architecture Intake Request",
    "AI/ML Architecture Intake Request"
  ],
  "pdlcCheckpoints": ["Inception", "Elaboration", "Construction", "Delivery"]
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
| `summary`, `artifactLink`, `pr`, `appId`, `appName`, `trackitId` | string \| null | |
| `solutionArchitect`, `saContributors` | string \| null | |
| `artifactType` | string | Required; one of `meta.artifactTypes` |
| `pdlcCheckpoint` | string \| null | One of `meta.pdlcCheckpoints` |
| `dateSubmitted` | `YYYY-MM-DD` | Defaults to today |
| `dateReviewed`, `approvalDate` | `YYYY-MM-DD` \| null | Review field |
| `meetingDate` | `YYYY-MM-DD` \| null | ARB meeting date; review field; required while `SCHEDULED` |
| `meetingTime` | `HH:MM` \| null | ARB meeting time (24-hour, the meeting's local time); review field; required while `SCHEDULED`; needs `meetingDate` |
| `buGovReviewer`, `eaGovReviewer` | string \| null | |
| `status` | string | A `request_statuses` code; review field (see `POST` for drafts); defaults to `SUBMITTED` |
| `comments` | string \| null | Review field |
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
One request plus its status history, oldest first.

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
`400` for a missing title, an invalid review type or an invalid status.

### `PUT /api/v1/requests/:id`
Partial update; only the fields sent are changed.

- Without `request:edit:all`, you must own the request and it must be `DRAFT`, `SUBMITTED` or
  `CHANGES_REQUESTED` (`403`
  otherwise), and review fields are dropped.
- A status change made here is recorded in the history (with `comments` as the note). It is refused (`403`)
  if you own the request.

### `PATCH /api/v1/requests/:id/status`
Moves a request through the lifecycle. Body: `{ "status": "APPROVED", "note": "optional", "dateReviewed": "optional YYYY-MM-DD" }`.

- **Owner steps** apply when you own the request. Review dates are left unchanged.

  | From | To | Needs |
  |---|---|---|
  | `DRAFT` | `SUBMITTED` (also sets `dateSubmitted` to today) | `request:create` |
  | `CHANGES_REQUESTED` | `SUBMITTED` | `request:resubmit` |
  | `DRAFT` or `SUBMITTED` | `WITHDRAWN` | `request:withdraw:own` |

- **Review** (needs `request:review`, or `request:schedule` to move to `SCHEDULED`; you must not own the
  request). Any status except `DRAFT`. This
  sets `dateReviewed` (default today), and sets `approvalDate` to today the first time the request reaches
  `APPROVED` or `APPROVED_WITH_CONDITIONS`.
- **Scheduling.** Moving to `SCHEDULED` needs `meetingDate` (`YYYY-MM-DD`) and `meetingTime` (`HH:MM`) in
  the body. Sending `SCHEDULED` again with both reschedules. Later moves keep the last meeting.

Every change adds a history entry. Returns the updated request. `400` for an unknown status or a missing
or invalid `meetingDate` or `meetingTime`; `403` when neither path applies.

### `DELETE /api/v1/requests/:id`
Permanently deletes the request and its history. Needs `request:delete:all`. Requestors withdraw instead,
which keeps the request (see the owner steps above). Returns `{ "deleted": 3 }`.

### `GET /api/v1/stats`
Counts over the requests the caller can see. `byStatus` has every status code.

```json
{
  "total": 175,
  "byStatus": { "DRAFT": 0, "SUBMITTED": 34, "IN_REVIEW": 0, "...": 0, "APPROVED": 72 },
  "byType": { "Architecture Review Board (ARB) Intake Request": 35, "...": 35 }
}
```

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
