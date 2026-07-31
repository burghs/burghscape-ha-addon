# Database schema

PostgreSQL is authoritative for Platform application state. SQLAlchemy models define fresh-database shape; chronological SQL files in `backend/migrations` define production upgrades. `Base.metadata.create_all` does not replace migrations.

## Core tenant and operations tables

| Table | Purpose and key relationships |
|---|---|
| `clients` | Tenant/account, contact, subdomain, plan/support presentation. Parent for users, instances, tokens, backups, assignments, and feature state. |
| `client_users` | Portal identities and password/TOTP flags; belongs to one client. |
| `subscription_tokens` | Unique Agent token records scoped to a client; active/expiry/last-used state. |
| `ha_instances` | Home Assistant telemetry and online/last-seen state; application behavior maintains one reporting instance per client, but legacy schema has no unique `client_id` constraint. |
| `alerts`, `metric_snapshots` | Instance monitoring history. |
| `support_tickets` | Existing support cases, resolution, time, status, and priority. Campaign interest does not write here. |
| `backups`, `backup_operations` | Managed backup objects and one-shot operation state. |
| `client_onboarding_states` | Unique client-user/onboarding-version state, progress, terminal/replay timestamps. |

## HA user inventory

- `ha_user_inventories`: one row per client (`client_id UNIQUE`); capability/report time, JSON user list, last successful refresh, sanitized last error.
- `ha_user_inventory_requests`: client-bound random request ID, pending/claimed/completed/failed state, expiry/claim/completion timestamps, sanitized error.
- Client deletion cascades both tables. A failed refresh never clears the last successful JSON inventory.

## Client Guides

- `client_guides`: title, description, category, generated/original file names, MIME/size, explicit `visibility_mode`, published/featured flags, display order, timestamps.
- `client_guide_assignments`: composite `(guide_id, client_id)` assignment for selected visibility.
- Guide deletion cascades assignments; client deletion removes only that client’s assignments. File bytes live in protected `/guide-media`, not PostgreSQL. Browser-local New/spotlight acknowledgement has no database table.

## Campaigns and analytics

- `campaigns`: content, type, CTA, media reference, draft/published/unpublished/archived state, audience mode, schedule, priority, popup behavior, revision/resend audit fields.
- `campaign_targets`: composite campaign/client selected audience.
- `campaign_read_states`: unique campaign/user/revision read record.
- `campaign_popup_events`: revision/occurrence event facts for displayed, snoozed, dismissed, opened, and action clicked.
- `campaign_popup_states`: unique campaign/user/revision current delivery state, snooze and acknowledgement.

Campaign and target/read/event/state rows cascade according to their foreign keys. Revision fields preserve historical analytics across deliberate resend.

## Campaign Leads

- `campaign_leads`: campaign and client are required with `ON DELETE RESTRICT`; submitting user is optional after deletion (`ON DELETE SET NULL`). Stores comments, preferred contact method/time, status, free-text staff assignment, internal notes, and timestamps.
- `campaign_lead_history`: required lead FK with `ON DELETE CASCADE`; previous/new status, administrator/client actor identifier, note, and timestamp.
- Database checks constrain contact method to `email`, `phone`, or `whatsapp`, and status to the seven documented CRM states.
- Indexes support status/submission, client/submission, campaign/submission, assignee, and chronological history queries.

The restricted campaign/client foreign keys intentionally preserve sales-lead attribution. Deleting a lead removes its history; no normal UI currently exposes lead deletion.

## Client TOTP and audit

`client_users` has additive TOTP fields. `two_factor_recovery_codes`, `two_factor_pending_enrollments`, and `two_factor_challenges` store hashed/encrypted or ephemeral factor state. `security_audit_events` records administrator/security and Client Guides audit metadata without storing secrets.

## Migrations and production order

The deployment script applies the current additive migrations in chronological order, ending with:

1. `20260723_add_client_totp.sql`
2. `20260730_add_ha_user_inventory.sql`
3. `20260731_add_client_guides.sql`
4. `20260731_add_campaign_leads.sql`

Each deployment first creates a PostgreSQL dump and runs `psql` with `ON_ERROR_STOP`. Current feature migrations use `IF NOT EXISTS` where applicable and do not destructively rewrite existing customer data.

## Backup and restore

A database dump alone is insufficient for file-backed features. Restore PostgreSQL together with `/home/kenny/backups`, `/home/kenny/guides/client-guides`, configuration, and the matching persistent `TOTP_ENCRYPTION_KEY`. Rollbacks retain additive schema and customer data.
