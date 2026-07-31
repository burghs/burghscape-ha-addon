# Read-only Home Assistant user inventory

## Scope

Phase 1 is read-only. It lists Home Assistant user identifiers, display names, local usernames when present, owner and derived administrator status, active state, `local_only`, `system_generated`, and credential-provider types. It does not expose MFA, last-login data, passwords, password controls, session controls, or any create, update, delete, enable, disable, or role-change operation.

`local_only` is presented independently from credential provider type. A local username exists only when Home Assistant returns one; external-provider users retain a null username. Owner and administrator remain distinct, and administrator status is derived as owner or active membership in Home Assistant's `system-admin` group.

## Architecture and isolation

The path is `Management Portal -> Platform -> Agent -> Home Assistant`. The Platform never connects directly to customer Home Assistant APIs.

Agent 0.2.57 advertises `ha_users_read` through a separate subscription-token-authenticated endpoint and runs a separately supervised inventory worker. The worker authenticates to Home Assistant's local `/api/websocket` endpoint with the existing HA token and sends `config/auth/list`. No add-on manifest permission was added. The heartbeat payload, first-heartbeat onboarding, `HomeAssistantInstance` lifecycle, tunnel/entity telemetry, backups, and TOTP are unchanged.

Management refresh creates a client-bound request with a 45-second expiry. The matching Agent claims it using its existing subscription token and returns either a strictly validated user list or one sanitized error code. Request IDs are random, tenant-bound, single-use, and terminal after success, failure, or expiry. Refresh requests are serialized on the client row to prevent concurrent duplicates.

## Management interface and API

Management → **HA Users** selects a client, reports capability/permission/unavailable state, displays the last successful refresh timestamp, and supports one manual refresh. The Platform endpoints are mounted at `/api/ha-users`; management uses `/clients/{client_id}` and `/refresh`, while Agent capability/claim/result endpoints use the Agent token. Older Agents show Not supported with refresh disabled. Agent 0.2.57 shows supported after capability advertisement even before the first inventory result.

## Capability and compatibility

Older Agents do not advertise `ha_users_read`; the interface displays Not supported and their existing reporting continues normally. Capability presence does not imply that the configured HA token is an administrator. Home Assistant permission errors are reported as `permission_required`.

Supported sanitized failures are authentication required/rejected, permission required, unsupported command, malformed response, timeout, and unavailable. Home Assistant response messages, HA tokens, Supervisor tokens, subscription tokens, and passwords are not stored or returned.

## Cache behavior

The Platform keeps the last successful user list and its `refreshed_at` timestamp. A later failure updates only the sanitized error state and does not erase the last good list. Cached data is historical, not authoritative current state; the portal always shows the last successful refresh time and provides a manual refresh action.

## Deployment and rollback

The Platform schema and management UI are deployed in production. Agent 0.2.57 is compatible; each installation advertises capability only after its normal update/startup.


`backend/migrations/20260730_add_ha_user_inventory.sql` adds only the inventory cache and request queue. The standard `deploy/scripts/deploy_platform.sh` applies it after creating the normal pre-deployment database backup.

Platform rollback uses the prior Platform commit through the same deployment script. The additive tables may remain unused and do not affect older code. Agent rollback uses the prior documented add-on release through Home Assistant's normal repository update/rebuild workflow. Neither rollback deletes client, instance, token, backup, or Home Assistant user data.

## Regression coverage

- `backend/tests/test_ha_user_inventory.py`: management authentication, Agent authentication, client isolation, capability compatibility, success/failure/timeout behavior, strict payload rejection, read audit metadata, and last-good-data preservation.
- `tests/test_ha_user_inventory.py` in the Agent repository: WebSocket authentication, `config/auth/list`, local/external/inactive/system users, role derivation, permission and unsupported handling, malformed responses, timeout sanitization, secret-safe logging, and heartbeat-loop isolation.
- `frontend/tests/ha-users.test.mjs`: supported and unavailable presentation, role/status labels, missing usernames, system users, last-good state behavior, and absence of destructive controls.
