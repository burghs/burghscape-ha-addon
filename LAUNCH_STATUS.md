# Launch Status

| Launch-critical subsystem | Status |
|---|---|
| Authoritative Platform source and branch | COMPLETE |
| Independent Agent source and version policy | COMPLETE |
| Immutable Platform build provenance | COMPLETE |
| RC1.4.3 database migration | COMPLETE |
| RC1.4.3 backend deployment | COMPLETE |
| RC1.4.3 frontend deployment | COMPLETE |
| Authentication and client isolation | COMPLETE |
| Campaign lifecycle and What’s New | COMPLETE |
| Popup notification engine: corrected coordinator, CTA, resend, cache busting, SSE plus 15-second fallback | IN PROGRESS |
| Onboarding start/resume/skip/complete/replay | COMPLETE |
| Existing-user onboarding backfill | COMPLETE |
| Theme and responsive component behavior | IN PROGRESS |
| Backup/storage/tunnel/support regression | IN PROGRESS |
| Subscription tokens and tier/support presentation | COMPLETE |
| Automated billing and self-service subscription changes | BLOCKED |
| Clean Home Assistant deployment validation | IN PROGRESS |
| First real-client validation and sign-off | BLOCKED |
| v1.0 release | BLOCKED |

## Campaign notification engagement upgrade

- COMPLETE — revision-scoped popup lifecycle and historical analytics preservation
- COMPLETE — temporary close versus permanent dismissal semantics
- COMPLETE — next-login/delayed/until-acknowledged/show-once reminder policies
- IN PROGRESS — authenticated SSE availability notification with 15-second polling fallback; awaiting real-browser sign-off
- COMPLETE — intentional resend action with administrator/time audit fields
- COMPLETE — revision-aware unread/read state
- IN PROGRESS — responsive, keyboard-accessible popup and Getting Started layout; awaiting desktop/mobile manual sign-off
- COMPLETE — migration included in backup-first documented deployment
- IN PROGRESS — final real-client browser sign-off across supported Home Assistant webviews

## Production-blocking manual acceptance

- IN PROGRESS — actual desktop popup visibility after publish
- IN PROGRESS — actual mobile/webview popup visibility and controls
- IN PROGRESS — support CTA opens and prepopulates the live ticket workflow
- IN PROGRESS — resend produces one visible modal and one new-revision impression
- IN PROGRESS — Getting Started desktop/mobile visual sign-off
- COMPLETE — safe browser diagnostics and commit-versioned campaign assets
- BLOCKED — final notification/Getting Started completion status until the user completes the manual checklist

## Getting Started production-readiness

- COMPLETE — ten-stage content and navigation audit
- COMPLETE — nine empty screenshot slots replaced with responsive instructional illustrations
- COMPLETE — mobile horizontal stage navigation and persistent stage actions
- COMPLETE — responsive text, list, code, table, image, safe-area, and reduced-motion contracts
- COMPLETE — visual replacement inventory in `GETTING_STARTED_VISUALS.md`
- IN PROGRESS — desktop and 768/1024px manual visual acceptance
- IN PROGRESS — 320/360/375/390/414px portrait acceptance
- IN PROGRESS — iPhone Safari, Android Chrome, landscape, and Home Assistant webview acceptance
- BLOCKED — Getting Started COMPLETE status until manual visual acceptance is recorded

## Client two-factor authentication — Phase 1

- COMPLETE — optional RFC 6238 enrollment, encrypted secret storage, and local QR generation
- COMPLETE — database-backed pre-authentication challenge and rotated portal session
- COMPLETE — salted single-use recovery-code storage and verification
- COMPLETE — password-plus-factor client self-disable
- COMPLETE — reason/confirmation-gated administrator reset and audit history
- COMPLETE — additive disabled-by-default migration and deployment key gate
- COMPLETE — authenticated Account Security status, enrollment, recovery regeneration, and disable UI wiring
- IN PROGRESS — controlled live client/API validation
- BLOCKED — COMPLETE status until real authenticator enrollment/login and recovery-code acceptance are signed off
