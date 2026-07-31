# Burghscape / MyBeacon Platform

MyBeacon is Burghscape’s managed Home Assistant platform. It combines a React management portal, a server-rendered client portal, a FastAPI backend, PostgreSQL persistence, Redis-backed operational services, managed Cloudflare tunnels, backup handling, client onboarding, campaigns, protected guides, support, and an independently released Home Assistant Agent.

## Current production baseline

- Platform: `1.4.3-rc`, production commit `b6899de4058687156e8b293c426be52541c31526` on `origin/master`.
- Compatible Agent: `0.2.57` on the Agent repository’s `origin/main` branch.
- Management: `https://manage.mybeacon.co.za`.
- Client portal: `https://client.mybeacon.co.za/portal`.
- API/backend: FastAPI behind the production Cloudflare/API route.

The Platform and Agent are separate products and releases. Updating one does not deploy the other.

## Implemented features

- Client accounts, portal users, subscription tokens, Home Assistant instances, health/online state, tunnels, telemetry, alerts, support-hour presentation, and support tickets.
- Safe first-heartbeat onboarding: one instance is created for a new client and subsequent reports update it transactionally.
- Managed/native backup telemetry, protected uploads/downloads, storage monitoring, and confirmation-gated managed-backup deletion.
- Optional client TOTP with encrypted secrets, recovery codes, audit events, and administrator reset.
- Read-only Home Assistant user inventory through Agent 0.2.57 and Home Assistant `config/auth/list`, with capability detection and last-good caching.
- Client Guides publishing with protected PNG/JPEG/WebP/PDF storage, all-client or selected-client assignments, featured dashboard guides, browser-local New indicators, and a one-time Guides spotlight.
- Campaign lifecycle, targeting, media, What’s New, popup delivery, revision-aware analytics, and dedicated Campaign Leads with sales/client acknowledgement emails.
- Dashboard summaries for client/instance/backup/support state and campaign-lead New/Open/Won/Lost/conversion metrics.

Not implemented: billing/payment automation, self-service subscription changes, Home Assistant user mutation, managed-backup command polling/queueing, or campaign lead automation beyond the documented workflow.

## Documentation map

- [Project source of truth](PROJECT_SOURCE_OF_TRUTH.md)
- [Production architecture](ARCHITECTURE.md)
- [API reference](API.md)
- [Database schema](DATABASE_SCHEMA.md)
- [Agent reporting contract](AGENT_REPORTING_CONTRACT.md)
- [HA Users](HA_USER_INVENTORY.md)
- [Client Guides](CLIENT_GUIDES.md)
- [Campaign delivery and analytics](CAMPAIGN_NOTIFICATION_BEHAVIOUR.md)
- [Campaign Leads](CAMPAIGN_LEADS.md)
- [Client TOTP](TWO_FACTOR_AUTHENTICATION.md)
- [Release notes](CHANGELOG.md)
- [Launch status](LAUNCH_STATUS.md)

## Development and validation

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'

cd ../frontend
node --test tests/*.test.mjs
npm run build
```

Use `git diff --check` before committing. Preserve unrelated dirty files and stage explicit files only.

## Deployment

Platform production deployment is permitted only through:

```bash
cd /home/kenny/burghscape/platform
./deploy/scripts/deploy_platform.sh
```

The script requires `master`, records the exact commit/version, validates the persistent TOTP key, creates a PostgreSQL dump, applies ordered additive migrations, builds backend/frontend from `git archive`, recreates only those services, and verifies backend/frontend provenance plus expected schema. See [ARCHITECTURE.md](ARCHITECTURE.md) for rollback and storage details.
