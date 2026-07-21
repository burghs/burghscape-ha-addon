# Platform Changelog

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
