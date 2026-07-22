# Client onboarding (RC1.4.3)

## Status and architecture

RC1.4.3 is the final planned feature release before launch validation. The Client Portal remains server-rendered. `ClientOnboardingState` is the authoritative per-user/per-version record; browser storage is not used by the tour. The coordinator in `/static/onboarding.js` owns loading, step navigation, focus, target fallback, completion, skip, replay, and promotion readiness.

The current version is `rc1.4.3`. States are `not_started`, `in_progress`, `completed`, and `skipped`, with current step and start/completion/skip/replay timestamps. Completion history remains intact during replay.

## API

- `GET /api/portal/onboarding` — current user state and `should_start`.
- `POST /api/portal/onboarding/start` — idempotently starts initial onboarding.
- `PATCH /api/portal/onboarding/step` with `{"current_step": 0..7}` — persists progress.
- `POST /api/portal/onboarding/skip` — skips initial onboarding or ends a replay.
- `POST /api/portal/onboarding/complete` — completes initial onboarding or a replay.
- `POST /api/portal/onboarding/replay` — preserves terminal history and records replay time.

All endpoints use the authenticated portal session and derive the user server-side; callers cannot supply a client or user identifier.

## Upgrade and fresh installation

Apply campaign migrations first, then `backend/migrations/20260722_add_versioned_onboarding.sql`. Its insert marks every user already present at migration time as skipped for this version. This deterministic backfill prevents existing clients being forced through onboarding. Users created after migration have no current-version row and start automatically after login/password change. `Base.metadata.create_all` creates the table on a fresh database; the SQL migration must still be recorded/applied by the deployment workflow.

## Promotion coordination

The portal loads onboarding state before requesting a login promotion. The backend also suppresses promotion selection while the current record is absent, active, or replaying and does not consume the once-per-session evaluation marker. No displayed/dismissed event is written. Skip or completion emits readiness and normal campaign targeting/dismissal rules resume.

## Client experience and accessibility

The eight-step tour covers portal home, Home Assistant status, backups, support, What’s New, account/theme controls, and Getting Started. Missing or mobile-hidden targets use a centered explanation and never block progress. The dialog traps focus, restores prior focus, locks background input, supports keyboard controls, uses visible focus, and honors reduced motion. Escape focuses Skip so it cannot silently complete or discard progress.

The Getting Started page contains installation guidance, token terminology, remote URL/mobile setup, support guidance, and the replay action. Screenshot assets may be added to this directory using the existing documented filenames; missing images retain accessible explanatory cards.

## Testing

Run `cd backend && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p "test_*.py"`, `cd frontend && npm run build`, and `cd frontend && node --test tests/*.test.mjs`. Full live validation follows `LAUNCH_VALIDATION_RC143.md`.
