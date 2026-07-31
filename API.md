# Platform API reference

This is the maintained contract map for current production features. FastAPI OpenAPI remains the field-level runtime reference. All responses use sanitized errors; credentials, passwords, HA tokens, subscription-token values, and internal file paths must not be returned.

## Authentication classes

| Class | Used by | Enforcement |
|---|---|---|
| Management administrator | Management React portal | Existing admin session and `get_current_admin` |
| Client portal user | Server-rendered client portal | `portal_token`, active `ClientUser`, tenant derived server-side |
| Agent | Installed Home Assistant add-on | Active subscription token scoped to one client |
| Public/health | Health/login assets only | No customer data |

## Core Agent and operations

- `POST /api/agent/report` — heartbeat/telemetry; creates the first client instance or updates the existing instance transactionally.
- `GET /api/agent/config`, `GET /api/agent/status`, `GET /api/agent/validate` — Agent configuration/status validation.
- `/api/backups/config`, upload initiation/parts/completion/direct/abort, list, authorized download, and managed deletion — existing backup contract.
- There is no `GET /api/backups/command` contract or command queue.
- `/api/tunnels` — authenticated management create/list/config/disable/delete operations.

## Home Assistant Users

Mounted under `/api/ha-users`:

- `POST /agent/capabilities` — Agent advertises `ha_users_read`.
- `GET /agent/requests/next` — the matching Agent claims a pending request.
- `POST /agent/requests/{request_id}/result` — completed normalized inventory or one supported sanitized error.
- `GET /clients/{client_id}` — management reads capability, last-good inventory, refresh time/error, and latest request state.
- `POST /clients/{client_id}/refresh` — management creates or reuses a client-bound 45-second request.

No endpoint mutates Home Assistant users.

## Client Guides

Management administrator:

- `GET/POST /api/admin/client-guides`
- `GET/PUT/DELETE /api/admin/client-guides/{guide_id}`
- `POST /api/admin/client-guides/{guide_id}/file` — replace managed file.
- `GET /api/admin/client-guides/{guide_id}/file[?download=true]` — protected preview/download.

Client portal:

- `GET /api/portal/guides` and `/featured`
- `GET /api/portal/guides/{guide_id}`
- `GET /api/portal/guides/{guide_id}/file[?download=true]`
- `GET /portal/guides` — authenticated Guides & Help page.

Only published guides with `all` visibility or a matching assignment are returned. Featured selects the first visible featured guide by display order/update ordering.

## Campaigns, analytics, and leads

Campaign management includes list/get/create/update, publish, unpublish, archive, resend-popup, image upload/removal/read, and draft deletion under `/api/admin/campaigns`. Client campaign listing/details/read/image use `/api/portal/campaigns`; `/portal/whats-new` renders the client UI.

Popup APIs under `/api/portal/promotions` select the current eligible revision, stream authenticated availability events, and record idempotent `displayed`, `snoozed`, `dismissed`, `opened`, and `action-clicked` events. `GET /api/admin/campaign-popup-stats` returns current-revision analytics.

Campaign Leads:

- `POST /api/portal/campaigns/{campaign_id}/interest` — creates a `new` lead for the authenticated client with optional comments and required preferred contact method/time; sends sales and client acknowledgement emails after persistence.
- `GET /api/admin/campaign-leads` — CRM list with `search`, `status`, and `assigned_to` filters.
- `GET /api/admin/campaign-leads/metrics` — New, Open, Won, Lost, conversion rate.
- `GET /api/admin/campaign-leads/{lead_id}` — full client/campaign/contact/comments/notes/history details.
- `PUT /api/admin/campaign-leads/{lead_id}` — status, staff assignment, internal notes, optional history note.

Lead statuses are `new`, `contacted`, `quoted`, `scheduled`, `won`, `lost`, and `cancelled`. Campaign interest never creates a Support Ticket.

## Onboarding, authentication, and support

- `/api/portal/onboarding` plus start/step/skip/complete/replay — per-user versioned onboarding state.
- `/api/portal/security/two-factor` plus enroll/verify/cancel/recovery/disable — client TOTP.
- `/api/portal/auth/two-factor/verify` — database-backed login challenge completion.
- Management TOTP audit/reset endpoints are under `/api/portal/admin`.
- `/api/support` — existing management Support Ticket workflow; independent from Campaign Leads.
- `/api/dashboard/summary` — client, instance, backup, alert, support, and Campaign Lead headline metrics.
