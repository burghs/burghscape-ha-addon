# Launch Status

| Launch-critical subsystem | Status |
|---|---|
| Authoritative Platform source and branch | COMPLETE |
| Independent Agent source and version policy | COMPLETE |
| Immutable Platform build provenance | COMPLETE |
| RC1.4.3 database migration | COMPLETE |
| RC1.4.3 backend deployment | COMPLETE |
| RC1.4.3 frontend deployment | COMPLETE |
| Read-only HA Users Platform deployment | COMPLETE |
| Client Guides, assignments, featured panel, and spotlight | COMPLETE |
| Campaign Leads CRM, emails, and dashboard metrics | COMPLETE |
| Authentication and client isolation | COMPLETE |
| Campaign lifecycle, What’s New, analytics, and dedicated Campaign Leads | COMPLETE |
| Popup notification engine: corrected coordinator, CTA, resend, cache busting, SSE plus 15-second fallback | IN PROGRESS |
| Onboarding start/resume/skip/complete/replay | COMPLETE |
| Existing-user onboarding backfill | COMPLETE |
| Theme and responsive component behavior | IN PROGRESS |
| Backup/storage/tunnel/support regression | IN PROGRESS |
| Subscription tokens and tier/support presentation | COMPLETE |
| Automated billing and self-service subscription changes | BLOCKED |
| Clean Home Assistant deployment validation | IN PROGRESS |
| First real-client validation and sign-off | IN PROGRESS |
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
- COMPLETE — campaign-interest CTA opens the dedicated lead modal and never creates a Support Ticket
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
- IN PROGRESS — authenticated Account Security and administrator reset UI corrected; awaiting live Jackie browser acceptance
- IN PROGRESS — controlled live client/API validation
- BLOCKED — COMPLETE status until real authenticator enrollment/login and recovery-code acceptance are signed off

## Agent first-heartbeat correction

- COMPLETE — generic first heartbeat creates one online instance and repeated heartbeats update it, protected by generated-client regression coverage
- COMPLETE — optional backup timestamps accept valid Unix values and tolerate absent or malformed optional values
- COMPLETE — unsupported managed-backup command polling removed in Agent 0.2.56 and retained by 0.2.57; full command-queue architecture remains deferred
- COMPLETE — production Younus recovery and disposable-client first/second-heartbeat acceptance created one online instance with no duplicate; existing-client reporting remained functional
- COMPLETE — Platform deployment used the backup-first release script and is rollbackable without deleting client, token, instance, or backup data
- COMPLETE — Agent 0.2.57 is published for normal Home Assistant update; existing installations require no reinstall or token replacement

## Read-only Home Assistant user inventory

- COMPLETE — deployed isolated Management Portal inventory, client-bound request queue, last-good cache, refresh timestamp, and sanitized failure states
- COMPLETE — Agent 0.2.57 source uses existing HA-token WebSocket authentication and `config/auth/list` without new add-on permissions
- COMPLETE — older Agents remain compatible and continue heartbeat/reporting with the Users interface marked Not supported
- COMPLETE — no password, user mutation, session, MFA, or last-login controls are present
- COMPLETE — focused Agent, Platform, and frontend tests pass; Platform regression suite and production build passed at release validation
- COMPLETE — Platform deployment provenance, schema, routes, unsupported older-Agent state, and Agent 0.2.57 compatibility verified


## Client Guides & Help

- COMPLETE — management upload/edit/replace/publish/feature/order/delete workflow for PNG/JPEG/WebP/PDF
- COMPLETE — explicit all-client and selected-client assignment with tenant-bound metadata/file authorization
- COMPLETE — client card list, full-size image/PDF viewers, conditional featured dashboard panel, and protected downloads
- COMPLETE — browser-local New indicator and dismissible Guides spotlight; completed historical onboarding is not reset
- COMPLETE — persistent `/guide-media` mount, additive migration, tests, production deployment, and rollback documentation

## Campaign Leads

- COMPLETE — authenticated Campaign Interest modal captures optional comments and preferred contact method/time
- COMPLETE — dedicated lead/history persistence; no Support Ticket is created and existing Support Tickets are unaffected
- COMPLETE — management CRM list/details, seven statuses, assignment, notes, history, search, and filtering
- COMPLETE — immediate sales notification and client acknowledgement email attempt after persistence
- COMPLETE — dashboard New/Open/Won/Lost/conversion metrics and retained campaign delivery analytics
- COMPLETE — focused/backend/frontend tests, additive migration, production deployment, provenance, and health verification
