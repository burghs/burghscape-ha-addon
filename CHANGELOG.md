# Platform Changelog

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
