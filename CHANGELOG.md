# Platform Changelog

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
