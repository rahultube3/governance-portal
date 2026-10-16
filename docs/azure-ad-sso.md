# Azure AD (Microsoft Entra ID) SSO for the Governance Portal

This guide replaces the demo sign-in with Microsoft Entra ID single sign-on. The design:

- **The API signs users in** with the OpenID Connect authorization-code flow (with PKCE), using Microsoft's
  `msal` Python library. The browser never handles tokens; after sign-in the API keeps using its existing
  session cookie.
- **App Roles carry permissions.** You define four App Roles on the app registration and assign Entra groups to
  them. Each user's ID token then has a short `roles` claim (e.g. `["Portal.Reviewer"]`), which the portal maps
  to its roles through the existing `roles.ad_group` column. Nothing else in the permission code changes.
- **Demo sign-in stays for local development only**, behind `DEMO_LOGIN=1`, off by default.

Steps 1–6 happen in Entra (an admin with *Application Administrator* or *Cloud Application Administrator* runs
them). Steps 7–9 are the portal changes. Step 10 is the runtime flow, call by call, for reference and debugging.

> **Licence note:** assigning *groups* to an app's roles needs Microsoft Entra ID P1 or P2. On the free tier you
> can assign individual users to the roles instead (step 5 works the same with a user's object ID).

---

## Values you'll collect

| Name | Where it comes from | Used as |
|---|---|---|
| Tenant ID | `az account show --query tenantId -o tsv` | `AZURE_TENANT_ID` |
| Application (client) ID | step 2 | `AZURE_CLIENT_ID` |
| Client secret | step 3 | `AZURE_CLIENT_SECRET` (Key Vault in production) |
| Service principal object ID | step 4 | step 5 only |
| App role IDs | step 1 | step 5 only |
| Redirect URI | you choose | `AZURE_REDIRECT_URI` |

Redirect URIs used below:

- Local: `http://localhost:4200/api/v1/auth/sso/callback` (through the Angular dev proxy, so the session cookie is
  set for the same origin as the UI)
- Production: `https://governance.example.com/api/v1/auth/sso/callback` (replace with your host)

---

## Step 1 — Define the App Roles

Create `app-roles.json`. Each role needs its own GUID (`uuidgen` on macOS/Linux, `[guid]::NewGuid()` in
PowerShell). Keep the file: the IDs are needed in step 5.

```json
[
  { "id": "<guid-1>", "value": "Portal.Requestor", "displayName": "Requestor",
    "description": "Submits intakes and tracks their own requests.",
    "allowedMemberTypes": ["User"], "isEnabled": true },
  { "id": "<guid-2>", "value": "Portal.Reviewer", "displayName": "Reviewer",
    "description": "Reviews the queue and moves requests through the lifecycle.",
    "allowedMemberTypes": ["User"], "isEnabled": true },
  { "id": "<guid-3>", "value": "Portal.ChiefArchitect", "displayName": "Chief Architect",
    "description": "Approves Critical-risk requests in Chief Architecture Review.",
    "allowedMemberTypes": ["User"], "isEnabled": true },
  { "id": "<guid-4>", "value": "Portal.Admin", "displayName": "Admin",
    "description": "Full access, including users, permissions and reference data.",
    "allowedMemberTypes": ["User"], "isEnabled": true }
]
```

## Step 2 — Register the application

```bash
az login --tenant <tenant-id>

az ad app create \
  --display-name "Governance Portal" \
  --sign-in-audience AzureADMyOrg \
  --web-redirect-uris "http://localhost:4200/api/v1/auth/sso/callback" \
                      "https://governance.example.com/api/v1/auth/sso/callback" \
  --app-roles @app-roles.json \
  --query "{appId: appId, objectId: id}"
```

`appId` is the **client ID**. `AzureADMyOrg` keeps sign-in to your tenant only.

The same call through Microsoft Graph, if you prefer raw HTTP:

```http
POST https://graph.microsoft.com/v1.0/applications
Authorization: Bearer <token for an admin with Application.ReadWrite.All>
Content-Type: application/json

{
  "displayName": "Governance Portal",
  "signInAudience": "AzureADMyOrg",
  "web": { "redirectUris": ["http://localhost:4200/api/v1/auth/sso/callback",
                            "https://governance.example.com/api/v1/auth/sso/callback"] },
  "appRoles": [ ...the four roles from app-roles.json... ]
}
```

## Step 3 — Create a client secret

```bash
az ad app credential reset --id <client-id> --append \
  --display-name "governance-portal-api" --years 1 \
  --query password -o tsv
```

The secret is shown **once**. Put it straight into your secret store (Azure Key Vault in production). `--append`
keeps any existing secrets, so you can rotate without downtime. Set a reminder to rotate before it expires; a
certificate credential is the stronger option for production if your platform supports it.

## Step 4 — Create the service principal and require assignment

The service principal is the "Enterprise application" that users are assigned to.

```bash
az ad sp create --id <client-id> --query id -o tsv          # prints the service principal object ID
az ad sp update --id <client-id> --set appRoleAssignmentRequired=true
```

With assignment required, someone with no App Role can't sign in at all; Entra stops them before the portal
sees them.

## Step 5 — Assign Entra groups to the App Roles

Look up each group's object ID:

```bash
az ad group show --group "AAD-GovPortal-Reviewers" --query id -o tsv
```

Then assign it to the matching App Role (repeat for each group and role):

```bash
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/<sp-object-id>/appRoleAssignedTo" \
  --body '{
    "principalId": "<group-object-id>",
    "resourceId":  "<sp-object-id>",
    "appRoleId":   "<app-role-id from app-roles.json>"
  }'
```

| Entra group | App Role value | Portal role |
|---|---|---|
| AAD-GovPortal-Requestors | `Portal.Requestor` | Requestor |
| AAD-GovPortal-Reviewers | `Portal.Reviewer` | Reviewer |
| AAD-GovPortal-ChiefArchitects | `Portal.ChiefArchitect` | Chief Architect |
| AAD-GovPortal-Admins | `Portal.Admin` | Admin |

Check the assignments:

```bash
az rest --method GET \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/<sp-object-id>/appRoleAssignedTo" \
  --query "value[].{who: principalDisplayName, role: appRoleId}"
```

Only *direct* members of an assigned group get the role; nested groups don't pass it on.

## Step 6 — Check the tenant's OpenID configuration

```bash
curl -s https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration \
  | python3 -m json.tool | grep -E '"(issuer|authorization_endpoint|token_endpoint|end_session_endpoint)"'
```

`msal` reads this document itself; checking it confirms the tenant ID is right and the endpoints are reachable
from the API server.

---

## Step 7 — Configure the portal

API environment (never commit these values):

```bash
AZURE_TENANT_ID=<tenant-id>
AZURE_CLIENT_ID=<client-id>
AZURE_CLIENT_SECRET=<from your secret store>
AZURE_REDIRECT_URI=http://localhost:4200/api/v1/auth/sso/callback
UI_BASE_URL=http://localhost:4200          # where to send the browser after sign-in and sign-out
DEMO_LOGIN=0                               # 1 only on a developer machine
SESSION_COOKIE_SECURE=1                    # production (HTTPS); leave unset for http://localhost
```

The redirect URI is set explicitly rather than built from the request: behind the Angular proxy (and later a
load balancer) Flask sees an internal host, and Entra rejects any URI that doesn't match the registration exactly.

Point each portal role at its App Role value (Admin Settings → Permissions → edit role, or SQL):

```sql
UPDATE roles SET ad_group = 'Portal.Requestor'      WHERE code = 'REQUESTOR';
UPDATE roles SET ad_group = 'Portal.Reviewer'       WHERE code = 'REVIEWER';
UPDATE roles SET ad_group = 'Portal.ChiefArchitect' WHERE code = 'CHIEF_ARCHITECT';
UPDATE roles SET ad_group = 'Portal.Admin'          WHERE code = 'ADMIN';
```

`roles.ad_group` keeps its column name but now holds an App Role value. The portal already resolves permissions
from that column, so `resolve_access()` in `portal/auth.py` is unchanged.

## Step 8 — API changes

| File | Change |
|---|---|
| `api/requirements.txt` | add `msal` (install it, then pin the exact version you got) |
| `api/portal/config.py` | read the variables from step 7 |
| `api/portal/__init__.py` | `SESSION_COOKIE_SECURE` from config |
| `api/portal/schema.py` | `users.aad_oid TEXT UNIQUE` (the Entra object ID); seed demo users only when `DEMO_LOGIN=1` |
| `api/portal/routes/auth.py` | new `GET /auth/sso/login` and `GET /auth/sso/callback`; `POST /auth/logout` returns the Entra sign-out URL; `/auth/users` and `/auth/login` respond only when `DEMO_LOGIN=1` |
| `api/portal/auth.py` | `ad_groups_for()` returns `session["roles"]` (the token's `roles` claim) for SSO users and keeps the demo lookup for demo users; add the two SSO routes to `PUBLIC_ENDPOINTS` |
| `api/portal/routes/users.py` | user add/rename/role-change stay for demo mode only; with SSO, people and their roles are managed in Entra, so the Users page lists who has signed in |
| `api/portal/auth.py` (`assign_holders`) | the "don't lock everyone out of Assign permissions" check counts roles that are mapped to an App Role and hold `role:assign`, instead of counting demo users |

The two new routes, in outline:

```python
import msal
from flask import redirect, request, session

def entra() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        CLIENT_ID, client_credential=CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}")

@bp.get("/auth/sso/login")
def sso_login():
    # state, nonce and PKCE are generated and kept in the session until the callback.
    session["auth_flow"] = entra().initiate_auth_code_flow(scopes=["User.Read"], redirect_uri=REDIRECT_URI)
    session["next"] = safe_next(request.args.get("next"))       # only same-site paths, e.g. "/requests"
    return redirect(session["auth_flow"]["auth_uri"])

@bp.get("/auth/sso/callback")
def sso_callback():
    result = entra().acquire_token_by_auth_code_flow(session.pop("auth_flow", {}), request.args)
    if "error" in result:                                       # bad state, user cancelled, consent denied...
        return redirect(f"{UI_BASE_URL}/login?error=sso")
    claims = result["id_token_claims"]                          # oid, tid, name, preferred_username, roles
    user_id = upsert_user(oid=claims["oid"], name=claims.get("name"), email=claims.get("preferred_username"))
    session.clear()                                             # new session id after sign-in
    session.update(uid=user_id, roles=claims.get("roles", []))
    return redirect(f"{UI_BASE_URL}{session.pop('next', '/')}")
```

`acquire_token_by_auth_code_flow` checks `state` and `nonce` and the token's issuer, audience and expiry. It
doesn't verify the ID token's signature itself: the token comes straight from Microsoft's token endpoint over
TLS, which OpenID Connect Core (§3.1.3.7) accepts in place of a signature check.

Keep `SESSION_COOKIE_SAMESITE="Lax"` (already set). Entra returns to the callback with a top-level `GET`
(`response_mode=query`, msal's default), and Lax cookies are sent on that request, so the stored `auth_flow` is
there. Don't switch to `response_mode=form_post`: Lax cookies are not sent on cross-site POSTs.

## Step 9 — UI changes

| File | Change |
|---|---|
| `ui/src/app/components/login/*` | one "Sign in with Microsoft" button: `window.location.href = '/api/v1/auth/sso/login?next=' + encodeURIComponent(returnUrl)`; show "Sign-in failed, try again" when the URL has `?error=sso`; show the demo user picker only when the API reports demo mode |
| `ui/src/app/services/auth.service.ts` | `logout()` calls `POST /api/v1/auth/logout`, clears local state, then `window.location.href = logoutUrl` |
| `ui/src/app/core/auth.interceptor.ts` | a `401` sends the user to `/login` (already the behaviour) |

Everything else, including route guards, `auth.can()` and the role names in the sidebar, keeps working: `GET
/api/v1/auth/me` returns the same shape as before.

---

## Step 10 — The sign-in flow, call by call

```text
Browser                         Portal API                          Microsoft Entra ID
   │  1. GET /api/v1/auth/sso/login?next=/requests
   │ ───────────────────────────────▶ │
   │                                  │ builds state, nonce, PKCE verifier; saves them in the session
   │  2. 302 Location: https://login.microsoftonline.com/<tenant>/oauth2/v2.0/authorize?...
   │ ◀─────────────────────────────── │
   │  3. GET /oauth2/v2.0/authorize?client_id=<client-id>&response_type=code
   │        &redirect_uri=<callback>&scope=User.Read openid profile offline_access
   │        &state=...&nonce=...&code_challenge=...&code_challenge_method=S256
   │ ──────────────────────────────────────────────────────────────────────▶ │
   │                                       user signs in (MFA, conditional access)
   │  4. 302 Location: <callback>?code=...&state=...
   │ ◀────────────────────────────────────────────────────────────────────── │
   │  5. GET /api/v1/auth/sso/callback?code=...&state=...
   │ ───────────────────────────────▶ │
   │                                  │  6. POST /oauth2/v2.0/token
   │                                  │     grant_type=authorization_code&code=...&redirect_uri=<callback>
   │                                  │     &client_id=...&client_secret=...&code_verifier=...
   │                                  │ ─────────────────────────────────────▶ │
   │                                  │  7. 200 { id_token, access_token, ... }
   │                                  │ ◀───────────────────────────────────── │
   │                                  │ checks state/nonce/claims, upserts the user by oid,
   │                                  │ session = { uid, roles }
   │  8. 302 Location: http://localhost:4200/requests   (Set-Cookie: session=...)
   │ ◀─────────────────────────────── │
   │  9. GET /api/v1/auth/me  → { id, name, email, roles, roleNames, permissions, adGroups }
   │ ───────────────────────────────▶ │
```

Sign-out:

```text
POST /api/v1/auth/logout
  → 200 { "logoutUrl": "https://login.microsoftonline.com/<tenant>/oauth2/v2.0/logout
                         ?post_logout_redirect_uri=http://localhost:4200/login" }
Browser navigates to logoutUrl → Entra ends its session → back to /login
```

The `post_logout_redirect_uri` must also be registered on the app (Authentication → Front-channel logout URL, or
add it to the redirect URIs).

An ID token's useful claims, decoded:

```json
{
  "aud": "<client-id>",
  "iss": "https://login.microsoftonline.com/<tenant-id>/v2.0",
  "oid": "6f1c…",                       // stable user ID in this tenant → users.aad_oid
  "tid": "<tenant-id>",
  "name": "Priya Shah",
  "preferred_username": "priya.shah@contoso.com",
  "roles": ["Portal.Reviewer"],
  "nonce": "…", "exp": 1760000000
}
```

Roles are read at sign-in. If an admin changes someone's role assignment in Entra, it takes effect the next time
they sign in; to make that sooner, shorten `PERMANENT_SESSION_LIFETIME` (for example 8 hours).

## Testing checklist

1. A user in each group signs in and gets the matching portal role (sidebar shows it; `GET /auth/me` lists the
   permissions).
2. A user with no App Role is stopped by Entra ("not assigned to a role for the application").
3. Removing a user from a group takes effect after they sign out and in again.
4. Tampering with `state` in the callback URL sends the user back to `/login?error=sso`.
5. Sign-out returns to `/login`, and the next sign-in asks Entra again.
6. With `DEMO_LOGIN=0`, `GET /api/v1/auth/users` and `POST /api/v1/auth/login` return `404`.

## Production checklist

- HTTPS only; `SESSION_COOKIE_SECURE=1`; the production redirect URI registered exactly.
- Client secret in Key Vault, read at start-up; rotation date tracked (or use a certificate credential).
- `DEMO_LOGIN` unset.
- Keep the Flask `SECRET_KEY` stable across instances (it signs the session cookie); share it through Key Vault
  if you run more than one API instance.
- Conditional Access and MFA are configured in Entra, not in the portal.
