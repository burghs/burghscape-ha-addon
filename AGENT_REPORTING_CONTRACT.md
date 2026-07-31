# Agent Reporting Contract

## Heartbeat lifecycle

The authenticated Agent reports telemetry with `POST /api/agent/report` and a client subscription token. The token resolves exactly one active client. A first heartbeat is a normal, supported onboarding state: while holding a transaction lock on that client row, the Platform finds the client’s existing `HomeAssistantInstance` or creates one online instance when absent. The request flushes the instance before returning and the existing database dependency commits the transaction. Later heartbeats update that same most-recent instance and preserve offline-to-online notification behavior.

The Platform currently models one active reporting instance per client in application behavior, but the legacy schema does not enforce `ha_instances.client_id` uniqueness. Client-row serialization is therefore the backward-compatible duplicate guard for concurrent first heartbeats; no destructive migration or cleanup is required. Token-scoped lookup prevents one client from updating another client’s instance. Successful requests commit and failed requests roll back through the existing database dependency, so retrying a transiently failed first heartbeat is safe and does not require manual database correction, token replacement, or Agent reinstall.

## Optional telemetry

Heartbeat fields not required by the base report remain optional. `backup_status.last_backup`, when supplied, is interpreted as the existing Unix timestamp representation and stored as the instance backup time. Missing values preserve the current stored value. Invalid, out-of-range, or unsupported timestamp values are ignored and do not reject otherwise valid monitoring telemetry. Tunnel-running and onboarding status telemetry are retained in the live Agent report cache used by management representations.

## Managed backup command status

The Platform does not currently define an Agent command-queue endpoint or a complete contract for `GET /api/backups/command`. Agent 0.2.57 retains the 0.2.56 correction and does not poll that route. Administrator-triggered command polling remains deferred until queue persistence, authentication, claiming, idempotency, expiry, acknowledgement, and retry semantics are designed and tested together. This does not change backup inventory telemetry, configuration, manual one-shot backups, operation-state reporting, uploads, downloads, or retention limitations.

## Regression and rollback

`backend/tests/test_agent_first_heartbeat.py` covers generated-client first and repeated heartbeats, exactly-one-instance creation, management online representation, existing offline-instance recovery, token and cross-client isolation, valid/missing/malformed backup timestamps, transaction rollback, and safe retry. `tests/test_backup_command_polling.py` in the Agent repository ensures the unsupported polling method and main-loop call cannot silently return while the manual backup workflow remains available.

Platform rollback uses the standard release workflow: check out or revert to the recorded prior Platform commit, then run `./deploy/scripts/deploy_platform.sh`. Agent rollback uses the prior documented add-on release through Home Assistant’s normal add-on update/rebuild workflow. Neither rollback deletes or rewrites client, token, instance, or backup records.
