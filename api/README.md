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

`governance.db` is created on first run. On every start, `init_db()` creates any missing tables, applies
column migrations, seeds the demo users, roles and board, syncs the permission catalog and backfills audit
timestamps. All of this is safe to repeat.

The Angular dev server proxies `/api` to `http://127.0.0.1:5001` (see `ui/proxy.conf.json`), so the browser
calls the API on the same origin.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5001` | Port the API listens on |
| `GOV_PORTAL_SECRET_KEY` | contents of `api/.secret_key` (generated on first run, git-ignored) | Signs the session cookie. Set it explicitly in any shared environment |
| `ANTHROPIC_API_KEY` | — | Required for `/api/chat` |
| `CHAT_MODEL` | `claude-sonnet-4-6` | Model used by `/api/chat` |

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

**Sign-in (demo).** `POST /api/auth/login` takes a user ID with no password and sets a signed session
cookie (HttpOnly, `SameSite=Lax`). This must be replaced with Azure AD / Entra ID SSO before real use.

**Access resolution.** It runs on every request:

1. The user's Azure AD groups. In the demo, these are the `ad_group` of the role in `users.role`. With
   SSO they come from the token's `groups` claim (`ad_groups_for()` in `app.py`).
2. Every role whose `ad_group` is one of those groups.
3. The combined set of permissions granted to those roles (`role_permissions`).

All endpoints except `/api/health`, `/api/auth/users`, `/api/auth/login` and `/api/auth/logout` return
`401` without a session. Endpoints marked with permissions below need **at least one** of them. Several
also apply ownership and status rules, which are described with each endpoint.

**Permission catalog.** Defaults can be changed on the Permissions page or with `PUT /api/rbac/grants`.

| Permission | Allows | Requestor | Reviewer | Admin |
|---|---|:-:|:-:|:-:|
| `request:create` | Submit new requests | ✓ | | ✓ |
| `request:view:own` | See requests you submitted | ✓ | | ✓ |
| `request:view:all` | See every request | | ✓ | ✓ |
| `request:edit:own` | Edit your own request while `PENDING` or `REWORK`; review fields excluded | ✓ | | ✓ |
| `request:edit:all` | Edit any request, including status, review dates and comments | | | ✓ |
| `request:withdraw:own` | Delete your own request while `PENDING` | ✓ | | ✓ |
| `request:delete:all` | Delete any request | | | ✓ |
| `request:resubmit` | Move your own `REWORK` request back to `PENDING` | ✓ | | ✓ |
| `request:review` | Change the status of other people's requests | | ✓ | ✓ |
| `board:card:edit` | Add, edit, move and delete Team Board cards | | ✓ | ✓ |
| `board:field:manage` | Add, rename and delete Team Board fields and lanes | | | ✓ |
| `insights:view` | Open Insights (enforced by the UI; it reads `/api/requests`) | | ✓ | ✓ |
| `insights:export` | Export Insights as CSV (enforced by the UI) | | | ✓ |
| `user:manage` | Manage users | | | ✓ |
| `role:assign` | Edit the permission matrix and AD group mapping | | | ✓ |

**Separation of duties.** Nobody, including admins, can change the status of a request they submitted.
The only exception is resubmitting their own `REWORK` request.

## Endpoint index

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/health`](#get-apihealth) | public |
| GET | [`/api/meta`](#get-apimeta) | signed in |
| GET | [`/api/auth/users`](#get-apiauthusers) | public |
| POST | [`/api/auth/login`](#post-apiauthlogin) | public |
| POST | [`/api/auth/logout`](#post-apiauthlogout) | public |
| GET | [`/api/auth/me`](#get-apiauthme) | signed in |
| GET | [`/api/requests`](#get-apirequests) | `request:view:own` / `request:view:all` |
| GET | [`/api/requests/:id`](#get-apirequestsid) | `request:view:own` / `request:view:all` |
| POST | [`/api/requests`](#post-apirequests) | `request:create` |
| PUT | [`/api/requests/:id`](#put-apirequestsid) | `request:edit:own` / `request:edit:all` |
| PATCH | [`/api/requests/:id/status`](#patch-apirequestsidstatus) | `request:review`, or `request:resubmit` for your own |
| DELETE | [`/api/requests/:id`](#delete-apirequestsid) | `request:withdraw:own` / `request:delete:all` |
| GET | [`/api/stats`](#get-apistats) | `request:view:own` / `request:view:all` |
| POST | [`/api/chat`](#post-apichat) | signed in |
| GET | [`/api/board`](#get-apiboard) | signed in |
| POST | [`/api/board/fields`](#post-apiboardfields) | `board:field:manage` |
| PATCH | [`/api/board/fields/:id`](#patch-apiboardfieldsid) | `board:field:manage` |
| DELETE | [`/api/board/fields/:id`](#delete-apiboardfieldsid) | `board:field:manage` |
| POST | [`/api/board/cards`](#post-apiboardcards) | `board:card:edit` |
| PATCH | [`/api/board/cards/:id`](#patch-apiboardcardsid) | `board:card:edit` |
| DELETE | [`/api/board/cards/:id`](#delete-apiboardcardsid) | `board:card:edit` |
| GET | [`/api/users`](#get-apiusers) | `user:manage` |
| POST | [`/api/users`](#post-apiusers) | `user:manage` |
| PATCH | [`/api/users/:id`](#patch-apiusersid) | `user:manage` |
| DELETE | [`/api/users/:id`](#delete-apiusersid) | `user:manage` |
| GET | [`/api/roles`](#get-apiroles) | `user:manage` / `role:assign` |
| GET | [`/api/rbac`](#get-apirbac) | `role:assign` |
| PUT | [`/api/rbac/grants`](#put-apirbacgrants) | `role:assign` |
| PATCH | [`/api/rbac/roles/:code`](#patch-apirbacrolescode) | `role:assign` |

---

## Reference

### `GET /api/health`
Liveness check. Public.

```json
{ "status": "ok", "time": "2026-10-03T03:43:03Z" }
```

### `GET /api/meta`
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
  "lifecycle": ["PENDING", "APPROVED FB", "APPROVED EA", "FOLLOW UP", "REWORK"],
  "pdlcCheckpoints": ["Inception", "Elaboration", "Construction", "Delivery"]
}
```

## Authentication

### `GET /api/auth/users`
The demo sign-in directory, which the UI also uses to turn `*By` IDs into names. Public.

```json
[{ "id": 8, "name": "Portal Admin", "email": "admin@example.com", "role": "ADMIN" }]
```

### `POST /api/auth/login`
Signs in as a user and sets the session cookie. Public. Body: `{ "userId": 8 }`.
Returns the session user, the same as [`GET /api/auth/me`](#get-apiauthme). `400` for an unknown user.

### `POST /api/auth/logout`
Clears the session. Public. Returns `{ "ok": true }`.

### `GET /api/auth/me`
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
| `buGovReviewer`, `eaGovReviewer` | string \| null | |
| `status` | string | One of `meta.lifecycle`; review field; defaults to `PENDING` |
| `comments` | string \| null | Review field |
| `createdAt`, `createdBy`, `updatedAt`, `updatedBy` | audit | `createdBy` is the request's owner |

*Review fields* (`status`, `dateReviewed`, `approvalDate`, `comments`) are silently dropped from create
and update bodies unless the caller holds `request:edit:all`.

**Visibility.** With `request:view:all` you see everything. With only `request:view:own` you see requests
you created. Other people's requests return `404`.

### `GET /api/requests`
Lists visible requests, most recently updated first.

| Query | Effect |
|---|---|
| `status` | Exact match, e.g. `PENDING` |
| `artifactType` | Exact match |
| `search` | Substring match on title, summary, app name or TrackIT ID |

Returns an array of request objects.

### `GET /api/requests/:id`
One request plus its status history, oldest first.

```json
{
  "id": 3, "arbTitle": "Zero-Trust Network Segmentation (202601-03)", "status": "APPROVED FB", "...": "...",
  "history": [
    { "from_status": null, "to_status": "FOLLOW UP", "note": "Seeded",
      "created_at": "2026-07-26T01:52:44Z", "created_by": null },
    { "from_status": "FOLLOW UP", "to_status": "APPROVED FB", "note": "",
      "created_at": "2026-07-26T02:24:56Z", "created_by": 6 }
  ]
}
```

### `POST /api/requests`
Creates a request owned by the caller and records a `Created` history entry. Body: any request fields;
`arbTitle` and a valid `artifactType` are required. Returns `201` with the request.
`400` for a missing title, an invalid artifact type or an invalid status.

### `PUT /api/requests/:id`
Partial update; only the fields sent are changed.

- Without `request:edit:all`, you must own the request and it must be `PENDING` or `REWORK` (`403`
  otherwise), and review fields are dropped.
- A status change made here is recorded in the history (with `comments` as the note). It is refused (`403`)
  if you own the request.

### `PATCH /api/requests/:id/status`
Moves a request through the lifecycle. Body: `{ "status": "APPROVED EA", "note": "optional", "dateReviewed": "optional YYYY-MM-DD" }`.

- **Review** (needs `request:review`, and you must not own the request). This sets `dateReviewed`
  (default today), and sets `approvalDate` to today the first time the request reaches `APPROVED FB` or
  `APPROVED EA`.
- **Resubmit** (needs `request:resubmit`). This applies when you own the request and it goes from
  `REWORK` to `PENDING`. Review dates are left unchanged.

Every change adds a history entry. Returns the updated request. `400` for an unknown status; `403` when
neither path applies.

### `DELETE /api/requests/:id`
Deletes the request and its history. With `request:delete:all` this works on any request. With
`request:withdraw:own` it only works on your own request while it is `PENDING`. Returns `{ "deleted": 3 }`.

### `GET /api/stats`
Counts over the requests the caller can see.

```json
{
  "total": 175,
  "byStatus": { "PENDING": 34, "APPROVED FB": 36, "APPROVED EA": 36, "FOLLOW UP": 34, "REWORK": 35 },
  "byType": { "Architecture Review Board (ARB) Intake Request": 35, "...": 35 }
}
```

## Assistant

### `POST /api/chat`
Streams an answer about the governance standards (`knowledge.py`) as Server-Sent Events.
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

### `GET /api/board`
Returns `{ "fields": [Field], "cards": [Card] }`, both sorted by position.

### `POST /api/board/fields`
Body: `{ "label": "Priority", "type": "select", "options": ["Low", "High"], "isTitle": false, "isGroup": false }`.
`key` is generated from the label unless given. Setting `isTitle` or `isGroup` moves that role away from
the field that had it. Returns `201` with the field. `400` for a missing label, an unknown type or a
duplicate key.

### `PATCH /api/board/fields/:id`
Partial update of `label`, `options`, `position`, `isTitle` or `isGroup`. Returns the field.

### `DELETE /api/board/fields/:id`
Deletes the field and removes its key from every card's `data`. The title and grouping fields can't be
deleted (`400`); assign those roles to another field first. Returns `{ "deleted": 4 }`.

### `POST /api/board/cards`
Body: `{ "data": { "title": "Draft ARB template", "status": "Backlog" }, "position": 0 }`. `position`
defaults to the end. Returns `201` with the card.

### `PATCH /api/board/cards/:id`
Body: `{ "data": { ... }, "position": 3 }`, both optional. `data` is **merged** into the existing values.
Returns the card.

### `DELETE /api/board/cards/:id`
Returns `{ "deleted": 1 }`.

## Users

**Managed user object:** `id`, `name`, `email`, `role` (`REQUESTOR` | `REVIEWER` | `ADMIN`), and the audit
fields. In the demo, `role` is the user's AD group membership. With SSO, membership comes from Azure AD.

### `GET /api/users`
Returns all users, sorted by role then name.

### `POST /api/users`
Body: `{ "name": "Jane Doe", "email": "jane@company.com", "role": "REVIEWER" }`. The email is stored
lowercase and must be unique. Returns `201` with the user. `400` for a missing name, an invalid email, an
unknown role or a duplicate email.

### `PATCH /api/users/:id`
Partial update of `name` or `role`. Returns the user. `400` if the change would leave nobody holding
`role:assign`.

### `DELETE /api/users/:id`
Deletes a user. Their audit references become `null`, and requests they own lose their owner. You can't
delete yourself, and you can't remove the last person holding `role:assign` (`400`).
Returns `{ "deleted": 9 }`.

## Roles and permissions

### `GET /api/roles`
A lightweight role list for pickers.

```json
[{ "code": "REQUESTOR", "name": "Requestor", "adGroup": "AAD-GovPortal-Requestors" }]
```

### `GET /api/rbac`
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

### `PUT /api/rbac/grants`
Replaces the permission set of each role in the body. Roles you leave out are unchanged.
Body: `{ "grants": { "REVIEWER": ["request:view:all", "request:review", "board:card:edit"] } }`.

- New grants record who granted them and when.
- Unchanged grants keep their original audit data.

Returns the [`GET /api/rbac`](#get-apirbac) snapshot. `400` for an unknown role or permission, or if the
change would leave nobody holding `role:assign`.

### `PATCH /api/rbac/roles/:code`
Updates a role's `adGroup` (an Azure AD group name or object ID; empty unmaps it), `name` or
`description`. Returns the snapshot. `400` if the change would leave nobody holding `role:assign`.

---

## Governance lifecycle

`PENDING`, `APPROVED FB`, `APPROVED EA`, `FOLLOW UP`, `REWORK`. The UI's Kanban Board groups them as:

| Kanban column | Statuses |
|---|---|
| Pending | `PENDING` |
| Pending Chief Architecture Review | `FOLLOW UP` |
| Approved | `APPROVED FB`, `APPROVED EA` |
| Rejected | `REWORK` |

Every status change is written to `status_history` with who made it.

## Data model

Eight SQLite tables:

| Area | Tables |
|---|---|
| Governance requests | `requests`, `status_history` |
| Identity and access | `users`, `roles`, `permissions`, `role_permissions` |
| Team Board | `board_fields`, `board_cards` |

Every table has `created_at`, `created_by`, `updated_at` and `updated_by`.

- Diagram: [`architecture/er-diagram.puml`](../architecture/er-diagram.puml)
- Schema script: [`architecture/sql/schema.sql`](../architecture/sql/schema.sql)
- Ready-made queries: [`architecture/sql/queries.sql`](../architecture/sql/queries.sql)
