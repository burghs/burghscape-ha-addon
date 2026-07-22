# Project Source of Truth

> Mandatory reading before every Platform RC, Agent release, migration, or deployment.

## Product boundary and architecture

Burghscape/MyBeacon has two independently released products:

1. **Platform** — management frontend, Client Portal, API, PostgreSQL schema, Redis-backed/in-memory services, campaign system, backups, support, tunnels, themes, and client onboarding.
2. **Agent** — the Home Assistant add-on installed on client systems. It reports telemetry, authenticates with a subscription token, coordinates backups, and configures the managed tunnel.

They integrate over authenticated Platform APIs but are not the same deployable. Platform release `1.4.3-rc` and Agent release `0.2.55` are both valid at the same time.

## Authoritative repositories and branches

| Product | Local source | GitHub remote/branch | Version source |
|---|---|---|---|
| Platform | `/home/kenny/burghscape/platform` | `origin/master` | `backend/app/config.py` |
| Agent | `/home/kenny/burghscape/ha-agent-addon` | `origin/main` | `burghscape_agent/config.yaml` |

`/home/kenny/burghscape-deploy/platform` is a detached deployment worktree and is not an authoring location. `/home/kenny/burghscape/ha-add-on` is legacy Agent material and is not a release source. Never copy from either into an authoritative checkout.

The shared GitHub repository currently carries two product branches. Branch names are product boundaries: `master` is Platform; `main` is Agent. A commit on one branch is not contained in, released by, or installed from the other branch unless explicitly cherry-picked for shared API compatibility.

## Long-term release strategy

**Independent products and independent versions (Option A) is authoritative.** Platform uses product RC versions such as `1.4.3-rc` and eventually stable `1.0.0`. Agent uses semantic add-on versions such as `0.2.55`. Neither version implies the other. Compatibility changes must be documented in both release notes, but unrelated releases do not receive artificial matching bumps.

## Dependency map

```text
GitHub origin/master -> Platform source -> clean Git archive build -> backend/frontend images
                                      -> ordered PostgreSQL migration
                                      -> Compose project burghscape
                                      -> mybeacon-backend / mybeacon-frontend
                                      -> Cloudflare API/admin/portal tunnels

GitHub origin/main   -> Agent repository metadata -> Home Assistant repository refresh
                                      -> Agent 0.2.55 add-on image/build
                                      -> client Home Assistant
                                      -> Platform Agent/tunnel/backup APIs

PostgreSQL <-> Platform backend; Redis <-> Platform backend/monitoring
```

## Docker and deployment flow

The only Platform Compose project is `burghscape`, defined by `/home/kenny/burghscape/docker-compose.yml`. It owns PostgreSQL, Redis, backend, frontend, monitoring, and three Cloudflare tunnel containers.

Production-like Platform releases must use `deploy/scripts/deploy_platform.sh`. The script:

- reads the exact `master` HEAD and Platform version;
- creates a pre-deployment PostgreSQL dump;
- applies the additive RC1.4.3 onboarding migration with stop-on-error;
- builds backend and frontend from clean `git archive` contexts, excluding protected/uncommitted files;
- embeds the exact commit and version in both artifacts;
- uses `deploy/releases/docker-compose.platform.yml` to remove the development `/app` source bind and pin commit-tagged images;
- recreates only backend and frontend;
- verifies backend health, frontend `version.json`, and onboarding schema.

Do not deploy with a bare `docker compose up` from a dirty development tree. Do not infer deployment from `git push`, file mtimes, bind-mounted source, image creation time, or a successful Home Assistant update.

## Platform release procedure

1. Read this document and capture `git status`, branch, HEAD, and protected changes.
2. Require `master`; review and test the exact staged Platform change.
3. Update Platform changelog/status and migrations. Never silently rely on `create_all` for upgrades.
4. Commit and push `master`.
5. Run `./deploy/scripts/deploy_platform.sh` from the authoritative Platform checkout.
6. Verify `/health` returns the intended version and exact commit.
7. Verify `http://127.0.0.1:3000/version.json` returns the same version and commit.
8. Verify expected routes in live OpenAPI and expected tables/columns in PostgreSQL.
9. Exercise authenticated Client Portal and management workflows. Record results in `LAUNCH_STATUS.md` and release notes.

A Platform push does not trigger a build or deployment. No GitHub workflow currently performs this process. A Git tag is not currently required; stable v1.0 should introduce a signed/annotated Platform tag only after launch validation.

## Agent release procedure

1. Work only in `/home/kenny/burghscape/ha-agent-addon` on `main` and preserve its dirty tree.
2. Update and test Agent code independently.
3. Bump `burghscape_agent/config.yaml`; update Agent changelog and docs to the same version.
4. Commit and push `main`.
5. Refresh the custom repository in Home Assistant, confirm the advertised version, install/update on a disposable validation system, and verify logs/telemetry/tunnel/backup compatibility.

Home Assistant Update installs only the Agent. It never migrates PostgreSQL, rebuilds Docker, restarts the Platform, or installs a Platform RC.

## Version verification commands

```bash
git -C /home/kenny/burghscape/platform rev-parse master origin/master
git -C /home/kenny/burghscape/ha-agent-addon rev-parse main origin/main
sed -n '1,8p' /home/kenny/burghscape/ha-agent-addon/burghscape_agent/config.yaml
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:3000/version.json
docker inspect mybeacon-backend --format '{{.Config.Image}} {{.State.StartedAt}}'
docker inspect mybeacon-frontend --format '{{.Config.Image}} {{.State.StartedAt}}'
docker exec -i mybeacon-db psql -U burghscape -d burghscape -c "SELECT to_regclass('public.client_onboarding_states');"
```

The Platform is verified only when GitHub `origin/master`, local `master`, backend health commit, frontend version commit, commit-tagged container images, live routes, and schema all agree.

## Current functional scope

Implemented Platform subscription functionality consists of client tiers, included-support-hour presentation, subscription-token creation/rotation/deactivation, and Agent authentication. Automated billing, payment collection, self-service plan changes/cancellation, invoices, and entitlement enforcement are not implemented and must not be represented as complete.

Implemented campaign functionality includes admin lifecycle, targeting, client What’s New/read state, popup eligibility, CTA, metrics, dismissal reset, and onboarding suppression. Scheduled future campaigns are intentionally absent from client APIs.

## Common mistakes and things never to assume

- Never assume `main` and `master` describe the same product.
- Never assume the highest visible number is the Platform version.
- Never assume Agent 0.2.55 contains Platform 1.4.3.
- Never assume GitHub push deployed Docker.
- Never assume bind-mounted files were reloaded by a non-reloading Uvicorn worker.
- Never assume `Base.metadata.create_all` upgraded an existing table/schema.
- Never assume a published campaign is currently effective; check status, publication timestamp, start, end, audience, client activity, popup flag, dismissals, and onboarding.
- Never assume a Promotion campaign is a login popup; `popup_enabled` is independent.
- Never use the detached deployment worktree or legacy `ha-add-on` as source.
- Never deploy broad dirty directories; build from an exact clean commit.
- Never expose credentials while auditing container environment.
- Never claim billing, notifications, restore, retention, or launch validation without code and test evidence.

## Manual audit record (2026-07-22)

- Platform source: `master` at RC1.4.3 commit `5df566c` before consolidation changes.
- Supported Agent: `main` at `7ee936c`, version `0.2.55`, native-backup telemetry correction.
- Legacy Agent metadata: `/home/kenny/burghscape/ha-add-on/config.yaml`, version `0.1.0`, unsupported.
- Compose project: one project named `burghscape`, eight running containers.
- Automated release workflows/tags: none.
- Previous Platform runtime: RC1.4.2-era worker because migration/restart had not occurred.
