# RC1.4.3 Launch Validation

Status: RC1.4.3 Platform features are deployed and provenance-verified through commit `b6899de4058687156e8b293c426be52541c31526`; broader v1.0 real-client and cross-device sign-off remains pending. Do not tag v1.0 until every item below has evidence and sign-off.

## Release baseline

- RC1.3.1: Dark, Light, and System authenticated portal themes.
- RC1.3.2: backup-storage monitoring and safe single managed-backup cleanup.
- RC1.4.1: campaign lifecycle, targeting, media, read state, and admin/client interfaces.
- RC1.4.2: single eligible login promotion, CTA, impression/open/click/dismiss metrics, and reset.
- RC1.4.3: versioned per-user onboarding, guided tour, Getting Started replay, and popup coordination.

Not implemented: subscriptions/billing, general notifications, popup carousels, automatic retention/restore, or production launch certification.

## Phase A — Fresh deployment

1. Start from a clean supported Home Assistant installation with Supervisor/App support, working DNS/TLS, outbound network access, and a current backup.
2. Add `https://github.com/burghs/burghscape-ha-addon` under Home Assistant Settings → Apps → repositories and install Burghscape Agent.
3. Configure the Agent with its Home Assistant long-lived access token and Burghscape subscription token. Never paste tokens into tickets or this record.
4. Configure platform secrets outside Git: `DATABASE_URL`, `SECRET_KEY`, admin credentials, SMTP variables when email is required, Cloudflare credentials/domain, backup roots and R2 credentials when R2 is used, and optional `CAMPAIGN_MEDIA_ROOT`/`CAMPAIGN_MAX_IMAGE_BYTES`.
5. Start database, Redis, backend, and frontend using the established deployment definitions. Confirm persistent mounts for database, backups, and campaign media.
6. Apply migrations in chronological order through `20260731_add_campaign_leads.sql` using `deploy/scripts/deploy_platform.sh`. Record migration output. Do not rerun a destructive database initialization.
7. Confirm `/api/health` reports service/database and accurately reports storage/email availability; open management login and client login over HTTPS.
8. Confirm the backend reports version `1.4.3-rc`, static theme/onboarding assets load, and no startup tracebacks occur.

## Phase B — New client creation

1. In Management → Clients, create the client with correct name, email, subdomain, active status, and currently supported plan/support-hour fields.
2. Create the portal user through the existing credential/welcome flow; transmit temporary credentials through an approved private channel.
3. Associate the Home Assistant instance and subscription token with the same client; verify cross-client identifiers are never exposed.
4. Confirm the first login requires password change when configured, then reaches the portal.

## Phase C — First-login experience

1. Verify authentication/session cookies, correct client identity, and the selected System/Light/Dark theme.
2. Confirm a post-migration new user has no `rc1.4.3` row and onboarding begins without a promotion flash.
3. Exercise Welcome, Home Assistant status, Backups, Support, What’s New, Account/theme, Getting Started, and Finish. Test Back, Next, keyboard-only operation, focus trap/restoration, Escape, zoom, portrait/landscape, and narrow Home Assistant webview.
4. Refresh mid-tour and verify the persisted current step resumes. Hide a target/mobile navigation item and verify centered fallback can continue.
5. Skip with the explicit control; sign out/in and verify it stays skipped. Replay from Getting Started and verify completion/skip history is not reset.
6. Complete with Finish; sign out/in and verify no automatic replay. Verify Getting Started remains discoverable and setup terminology is accurate.

## Phase D — Campaign and popup tests

1. Create a normal draft campaign, preview it, target all or a selected client, publish it, and verify visibility, unread badge, read state, unpublish/archive, and dates.
2. Create a login popup campaign with summary, optional validated image, CTA label and allowed HTTPS or safe portal URL; preview and publish.
3. Verify eligible client targeting, priority selection, one evaluation per session, displayed impression only after visible display, details open/read state, CTA click, dismissal, and admin metrics.
4. Verify reset removes dismissal eligibility only as documented and metrics remain internally consistent.
5. With initial onboarding and replay active, verify no popup, flash, displayed event, or dismissal. Finish/skip and verify normal popup eligibility immediately resumes.

## Phase E — Platform regression tests

1. Verify dashboard, client/instance state and staleness, agent reporting, tunnels/remote URL, authentication expiry/logout/password change, and access isolation.
2. Verify managed and native backup presentation/downloads, RC1.3.2 storage capacity/thresholds/grouping, and confirmation-gated managed-backup deletion against a disposable archive only.
3. Verify support ticket create/list/resolution/deletion rules and plan-hour presentation; no billing claim should appear.
4. Verify client administration, campaign administration, themes, keyboard focus, tablet/mobile layouts, browser zoom, and light/dark contrast.
5. Run backend suite, frontend Node tests, and production build; attach exact commands, versions, results, and any accepted pre-existing failure.

## Phase F — Real-client readiness

1. Review data minimization, client isolation, logs, campaign audience, credential storage/transport, TLS, cookie security, database/media/backup permissions, and restore evidence.
2. Perform and document a real backup download and restore rehearsal; verify support contact details and client-facing terminology with the client.
3. Record client, validator, environment/version, timestamps, deviations, screenshots without secrets, test evidence, defects, owners, and retest results.
4. Obtain technical, privacy/security, support, and client-experience sign-off. Then make final fixes, rerun all phases, create the v1.0 release record, tag, and deploy through the established safe workflow.

## Upgrade notes and known limitations

The onboarding migration is additive. Existing users at migration time are inserted as skipped for `rc1.4.3`; later users are new. A future version uses a separate row and policy decision. In-memory portal sessions remain a known operational limitation and require process/session architecture validation before scaling. Spotlight targets explain unavailable UI rather than opening mobile navigation automatically. Localization is not implemented; layouts are designed for wrapping text.

## Sign-off record

| Area | Validator | Date/time | Evidence | Result/defects |
|---|---|---|---|---|
| Fresh deployment | | | | |
| New client | | | | |
| Onboarding | | | | |
| Campaigns/popups | | | | |
| Regression/security | | | | |
| Real client | | | | |
## Agent reporting acceptance

For a generated client created through the normal management path, confirm the first authenticated heartbeat returns success, creates exactly one online `HomeAssistantInstance`, and appears Online in management. Send a second heartbeat and confirm the same instance ID is updated. Repeat transaction-failure/retry and token-isolation regression tests. Agent 0.2.57 must not call `/api/backups/command`; update an existing add-on through the normal Home Assistant update flow without reinstalling or replacing its token. Platform deployment and rollback must use `deploy/scripts/deploy_platform.sh` and preserve client data.


## Phase G — Current feature acceptance

1. HA Users: verify older-Agent Not supported behavior; with Agent 0.2.57 verify capability, one refresh, normalized roles/status/provider fields, last-success timestamp, sanitized failures, and heartbeat isolation.
2. Client Guides: upload image/PDF, all/selected assignment, publish/feature/order, management and client preview/download, dashboard featured selection, spotlight dismissal, replacement cleanup, and authorization denial across clients.
3. Campaign Leads: submit Interest with each contact method, confirm no Support Ticket, verify sales/client emails, CRM details, all seven statuses, assignment, notes/history, search/filter, dashboard metrics, and legacy CTA compatibility.
4. Confirm `/health` and frontend `version.json` match the intended commit; verify `ha_user_inventories`, `ha_user_inventory_requests`, `client_guides`, `client_guide_assignments`, `campaign_leads`, and `campaign_lead_history` exist.
