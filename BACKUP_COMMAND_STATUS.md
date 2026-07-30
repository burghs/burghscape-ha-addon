# Managed Backup Command Status

Agent 0.2.56 does not poll `GET /api/backups/command` because the Platform has no documented or implemented command-queue contract. Administrator-triggered polling is deferred until persistence, claiming, idempotency, expiry, acknowledgement, and retry behavior are implemented as one tested contract.

This change does not affect heartbeat reporting, backup inventory telemetry, backup configuration, manual one-shot execution, operation-state reporting, archive upload, or download. Existing installations update through the normal Home Assistant add-on update flow; no reinstall or subscription-token replacement is required. Rollback is the prior documented add-on release through the same normal update/rebuild flow.
