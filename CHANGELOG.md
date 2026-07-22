## 2026-07-22 — RC1.4.3 versioned client onboarding

- Final planned feature release before launch validation. Added authenticated, per-client-user, versioned server-side onboarding with start, resume, skip, complete, and replay transitions.
- Added an accessible responsive portal tour, stable spotlight targets, missing-target fallback, Getting Started replay, theme support, focus management, and reduced-motion handling.
- Added deterministic upgrade backfill: users present when the migration runs are skipped for `rc1.4.3`; users created afterward have no row and receive onboarding.
- Coordinated login promotions through onboarding readiness and backend eligibility so suppressed campaigns record no impression or dismissal; normal eligibility resumes after skip/completion.
- Added `backend/migrations/20260722_add_versioned_onboarding.sql`, onboarding API/state tests, release documentation, and a fresh Home Assistant launch-validation runbook.
- RC1.4.3 is implemented and automated-test validated. Clean deployment validation, a real-client onboarding rehearsal, final fixes, and v1.0 remain pending.

# Platform Changelog

## 2026-07-22 — RC1.4.2 Login Promotion Popups

- Extended the existing campaign framework with optional login-popup enablement, popup summary text, and validated internal/HTTPS call-to-action destinations.
- Added server-side active-window, client-targeting, dismissal, completed-action, priority, and newest-start-date eligibility rules with one popup evaluation per authenticated session.
- Added per-user display, dismissal, detail-open, and primary-action event tracking; display does not mark a campaign read, while detail and primary actions do.
- Added administrator popup metrics and confirmation-gated dismissal reset while preserving completed-action exclusions.
- Added a responsive, theme-compatible Client Portal popup with image, summary, optional primary action, details navigation, accessible close control, Escape handling, and keyboard focus trapping.
- Added migration `backend/migrations/20260722_add_campaign_login_popups.sql`; existing campaigns default to popup disabled and retain their current What’s New behavior.
- Subscription changes, billing, onboarding tours, email/push campaigns, popup carousels, and complex marketing analytics were not added.

## 2026-07-22 — RC1.4.1 Campaign Framework

- Added administrator-managed campaigns with draft, published, unpublished, archived, preview, selected-client targeting, priority, effective dates, and draft-only confirmed deletion workflows.
- Added announcement, promotion, new service, maintenance notice, tip, featured project, and important notice campaign types using plain-text content and theme-compatible presentation.
- Added persistent per-client-user read state, server-calculated unread counts, and an authenticated Client Portal “What’s New” section that excludes draft, archived, future, expired, and untargeted campaigns.
- Added optional JPEG, PNG, and WebP campaign media with configurable `CAMPAIGN_MEDIA_ROOT` and `CAMPAIGN_MAX_IMAGE_BYTES`, MIME/extension/signature/size validation, generated filenames, and controlled replacement/removal.
- Added additive migration `backend/migrations/20260722_create_campaign_framework.sql` for campaigns, client targeting, read state, indexes, and foreign keys.
- Campaign media defaults to `/backups/campaign-media` inside the backend, using the existing persistent `/backups` mount; the maximum image size defaults to 5 MiB and both values are environment-configurable.
- First-login onboarding, login promotional popups, campaign-interest support tickets, subscription change/cancellation requests, and campaign analytics beyond read/unread state remain deferred.

## 2026-07-21 — RC1.3.2 backup storage monitoring and safe cleanup

- Added authenticated backup-storage capacity, filesystem-used, available, percentage-used, and managed/platform file-usage monitoring using the configured backup roots.
- Added Healthy, Attention, Warning, and Critical thresholds at 70%, 85%, and 95%, plus a compact Management Dashboard storage card.
- Added per-client managed-backup storage totals, counts, oldest/newest dates, and usage-descending grouping.
- Added two-step administrator-only deletion of one managed client backup with tenant-key validation, configured-root containment, traversal/symlink/directory rejection, rollback recovery, and immediate summary refresh.
- Platform backup deletion, client-side deletion controls, automatic retention, bulk deletion, restore, notifications, PWA work, and Agent changes were not added.
- RC1.3.2 completes feature scope for the current release; feature freeze and isolated clean-environment release validation follow.

## 2026-07-21 — RC1.3.1 authenticated portal themes

- Added shared Dark, Light, and System modes to the authenticated Management and Client portals while preserving the existing dark visual identity and portal layouts.
- Stored the validated preference under the shared browser key `mybeacon-theme`; missing or invalid values fall back to System.
- Applied the resolved theme before authenticated portal rendering and track live `prefers-color-scheme` changes only while System mode is active.
- Added accessible, responsive theme controls to Management Settings and the Client Account area.
- Kept both login pages visually isolated and unchanged.
- Added no backend API/schema, Agent, notification/PWA, or backup-storage changes.

## 2026-07-21 — RC1.2.1 Management Portal cleanup

- Replaced the misleading page-level remaining-hours metric with aggregate ticket-derived support time logged.
- Omitted unavailable HA database/IP fields, emphasized the latest available stored managed-backup date, and removed developer-facing backup wording.
- Grouped Platform Server Backups under an expandable Burghscape Platform summary while preserving existing authenticated downloads.
- Grouped Support Tickets by client with ticket counts and included/logged/remaining/potentially-billable support summaries.
- Added explicitly authenticated, confirmation-gated deletion of one support ticket with scoped database deletion, controlled failures, identifier-only logging, and totals recalculated from remaining tickets.
- Added no schema changes, backup deletion, Agent changes, Client Portal redesign, billing, or remote-control features.

## 2026-07-21 — RC1.2 Management Portal refinement

- Added responsive Management Portal client cards, portal-user cards, operational HA instance cards, grouped Home Assistant backups, separate Platform Server Backups, support ticket detail/resolution workflow, and safe Settings health summary.
- Fixed the Token action with masked Show/Copy and separately confirmed regeneration; opening the dialog does not rotate credentials.
- Added ticket-derived per-client included, logged, remaining, and potentially billable support visibility.
- Added nullable `support_tickets.resolution` through `20260721_add_support_ticket_resolution.sql`; resolutions are stored separately from descriptions and escaped in the existing client ticket view.
- Disabled client deletion completion because existing cascades and external tunnel lifecycle do not provide a safe coordinated delete workflow.
- Preserved backup download authorization/filtering and did not add deletion, restore, retention, scheduling, billing, remote-control actions, Agent changes, or a Client Portal redesign.

## 2026-07-21 — RC1.1.1 Support hours calculation and plan behaviour

- Corrected Client Portal support-hour aggregation by summing existing `SupportTicket.hours_used` values instead of displaying the unsynchronized `Client.hours_used_this_month` field.
- Separated included support, actual support time logged, remaining included support, and potentially billable time using plan-compatible calculations; no billing was implemented.
- Added a non-blocking Basic-plan notice before ticket submission while preserving ticket creation for clients with zero included hours.
- Preserved all ticket records, statuses, priorities, submission behavior, and support-plan billing rules.

## 2026-07-21 — RC1.1 Client Portal UX and mobile refinement

- Reorganized the Client Portal into a compact instance header, System Overview, Environment & Updates, consolidated Backup Protection, and Account & Support.
- Moved setup values into a mobile-scrollable Setup Details modal while preserving masked token Show/Copy, URL Copy/Open, Getting Started, account, logout, report, and support-ticket actions.
- Consolidated managed and reliable native backup information, retained client-scoped downloads, and used instance/date/size labels instead of internal archive filenames.
- Added a release-information modal preserving Home Assistant release-note and breaking-change links.
- Added mobile navigation, touch-sized actions, responsive stacking, focus indicators, Escape/backdrop modal closing, and body-scroll locking.
- No managed scheduling, retention, restore, Agent, Management Portal, authentication, ownership, or transport changes were made.

## 2026-07-21 — Backup presentation and native telemetry correction

- Made client and Home Assistant instance ownership prominent in Management Portal backup entries and generated sanitized client-instance-local-time attachment names.
- Made Client Portal history compact: latest successful backup first, three initially visible, with a simple Show all backups action.
- Excluded completed records from portal lists when they are known synthetic/transport-validation artefacts, zero-byte, or have no available stored object; no records were deleted.
- Distinguished Burghscape managed scheduling from native Home Assistant backup inventory and displayed backup times in Africa/Johannesburg.
- Native schedule and encryption status remain Unknown when the supported Supervisor inventory cannot provide them; encryption keys are never requested or handled.
- Restore, retention, deletion, and managed automatic scheduling remain outside scope.

## 2026-07-21 — Managed backup downloads

- Added authenticated administrator listing and download of completed managed backups on Management Portal → Backups.
- Added authenticated client-scoped listing and download of completed managed backups in the Client Portal managed-backup section.
- Reused the existing storage backend and file response with server-side ownership, completed-state, object-availability, and attachment-filename checks.
- Delete, Restore, and Retention remain outside this release.
- Validated focused authorization and storage tests, existing backup transport tests, client portal rendering, and the management frontend production build.
