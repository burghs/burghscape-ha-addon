# Agent read-only Home Assistant user inventory

Agent 0.2.57 advertises `ha_users_read` and runs inventory as a separate worker. It authenticates to the local Home Assistant `/api/websocket` endpoint with the existing configured HA token, requires administrator permission, and sends only `config/auth/list`.

The Agent strictly validates user ID, optional display name and local username, owner, active, `local_only`, `system_generated`, group IDs, and credential-provider types. It derives administrator as owner or active `system-admin` membership. It returns no group IDs, tokens, passwords, raw Home Assistant errors, MFA, last-login, or mutation controls to the Platform.

Unsupported commands, insufficient permission, rejected authentication, malformed responses, timeouts, and connection failures become sanitized capability/result states. No `.storage`, SSH, database, Supervisor auth backend, or internal Home Assistant Python interface is used. The add-on manifest permissions are unchanged.

Inventory errors are caught inside the worker and cannot fail heartbeat, onboarding, tunnel/entity telemetry, or backups. Older Platform versions produce no inventory work and do not affect the existing reporting loop.

Install/update through the normal Home Assistant custom-repository flow without reinstalling or replacing tokens. Roll back to 0.2.56 through that same workflow; rollback does not delete Platform or Home Assistant data.
