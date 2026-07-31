# Production architecture

## System boundary

```text
Management browser ─┐
                    ├─ Cloudflare routes ─ Frontend/Nginx ─ FastAPI ─ PostgreSQL
Client browser ─────┘                              │          │
                                                   │          ├─ Redis/monitoring
Home Assistant ─ Agent 0.2.57 ─ authenticated API ─┘          ├─ managed backup storage
          └─ local HA WebSocket                              ├─ campaign media
                                                             └─ protected guide media
```

The Platform never connects directly to a customer’s Home Assistant API. The locally installed Agent is the authenticated boundary for telemetry, tunnel state, backups, and optional read-only user inventory.

## Runtime services

The single Compose project `burghscape` owns PostgreSQL 16, Redis 7, FastAPI backend, Nginx/React frontend, monitoring, and Cloudflare tunnel containers for API, management, and client portal traffic. PostgreSQL and Redis use host-backed persistent data directories. Backend and frontend production images are pinned to the exact Platform commit.

Nginx serves the management SPA and proxies `/api`, `/static`, and `/portal` to FastAPI. Client portal pages are server-rendered under `/portal`; management routes such as `/campaign-leads`, `/client-guides`, and `/ha-users` use the React SPA.

## Authentication and isolation

Management APIs use the existing administrator session dependency. Client APIs/pages use the HttpOnly portal session and derive the client from the authenticated `ClientUser`; client-controlled IDs never authorize access. Agent APIs use active subscription tokens scoped to one client. TOTP adds a database-backed pre-authentication challenge to client password authentication.

Guide files, campaign media, backup objects, HA inventory requests, and campaign leads repeat authorization/tenant checks at the serving or mutation endpoint. Secrets and internal storage paths are not included in client responses.

## Feature execution paths

- Heartbeat: Agent → `POST /api/agent/report` → client-scoped instance create/update transaction.
- HA Users: management refresh → client-bound database request → Agent claim → HA `/api/websocket` `config/auth/list` → sanitized last-good cache.
- Guides: management upload → signature validation → random managed filename + metadata/assignments → authorized client listing/view/download.
- Campaigns: management publish → targeted What’s New and optional popup; SSE wakes online browsers, with visible-tab polling fallback; events persist revision-aware analytics.
- Campaign Leads: client Interest modal → dedicated lead/history transaction → sales and client emails → management CRM status/assignment workflow. Support tickets are not involved.

Failures in HA user inventory, campaign email delivery, guide rendering, or popup delivery do not alter Agent heartbeat online state.

## Current operational limitations

Portal sessions and campaign SSE subscriber queues are process-memory state in the current single-backend deployment. PostgreSQL-backed onboarding, HA inventory requests, guides, leads, analytics, and TOTP challenges survive backend recreation, but active portal sessions and live SSE connections do not; clients reconnect or authenticate again. Redis is deployed for monitoring/operational use but is not yet the portal-session authority. Horizontal backend scaling therefore requires a shared session and event-distribution design.

Campaign Lead staff assignment is currently a validated free-text name/email, not a separate staff-directory foreign key. Lead emails use the configured SMTP service and are attempted synchronously after the lead transaction commits; there is no durable email queue or per-message delivery-state table.

## Persistent storage

- PostgreSQL: application records, feature state, assignments, analytics, request queues, TOTP/audit data.
- `/home/kenny/guides/client-guides` mounted at `/guide-media`: protected guide files.
- `/home/kenny/backups` mounted at `/backups`: backup data and persistent campaign media under current configuration.
- `/home/kenny/burghscape/.env`: production secrets including the persistent TOTP encryption key; never committed.

A complete restore must pair PostgreSQL with managed file storage and required secrets.

## Deployment and rollback

`deploy/scripts/deploy_platform.sh` is the only production workflow. It creates `/home/kenny/backups/platform-predeploy-<commit>-<timestamp>.sql`, applies chronological idempotent/additive migrations with `ON_ERROR_STOP`, builds clean commit-tagged images, recreates backend/frontend, checks `/health`, `version.json`, and expected tables.

Rollback is application-first: revert or check out the recorded prior Platform commit on `master`, then run the same deployment script. Retain additive tables and files unless a separately approved destructive data migration exists. Never delete client, instance, token, guide, lead, inventory, backup, or audit data merely to roll back application code.
