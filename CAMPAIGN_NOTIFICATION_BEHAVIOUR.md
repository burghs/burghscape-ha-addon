# Campaign notification behaviour

This document defines the production campaign delivery contract for Platform RC1.4.3.

## Channels and delivery

Every published, currently eligible campaign appears in What’s New. Popup notification is an optional second channel. Publishing or resending a popup campaign emits an authenticated Server-Sent Event wake-up; an eligible visible portal normally checks within 2–5 seconds. A 30-second poll and a visibility-change check remain the recovery path. The event contains no campaign or client data: the authenticated popup-selection API performs all audience, schedule, onboarding, and state checks.

## Popup lifecycle

Each popup delivery has a campaign `delivery_revision`. A visible modal writes one idempotent `displayed` impression using a unique occurrence ID. Display is analytics only unless the administrator explicitly selected **Show once only**.

- **Remind me later**, the close icon, backdrop click, and Escape write `snoozed`. They do not mark the campaign read.
- **Dismiss** writes `dismissed`, acknowledges the current revision, and marks it read.
- A primary CTA writes `action_clicked`, acknowledges the current revision, and marks it read.
- Opening full details writes `opened` and follows the existing read/acknowledgement rule.

Reminder policies are: show until acknowledged (one-hour safe pause after a close), remind on next login (current portal session only), remind after 1/4/24/72 hours, and show once only. A modal already open is never duplicated.

## Resend and analytics

Unpublish/republish preserves acknowledgement for the same revision. **Resend popup notification** is the intentional resend operation: it increments the delivery revision and records the administrator and time. Old events/read state remain linked to their previous revision. The new revision is unread and eligible clients may receive it again.

Metrics distinguish impressions, temporary closes, permanent dismissals, detail opens, and CTA actions by revision. Temporary close is never counted as dismissal.

## CTA safety

The API records an explicit CTA action type and only accepts approved portal routes, HTTPS, `mailto:`, and `tel:` destinations. User-info HTTPS URLs, HTTP, protocol-relative, JavaScript, data, newline, and backslash destinations are rejected. Supported administrator action types are no action, What’s New details, portal destination, support, WhatsApp, email, phone, external website, and custom URL. Existing label/URL campaigns remain compatible.

## Operational verification

Verify `/api/portal/promotions/events` returns an authenticated event stream, `/api/portal/promotions/login-popup` returns only the current revision, and `campaign_popup_states`, event `delivery_revision`, and read-state `delivery_revision` exist after deployment. The deployment script backs up PostgreSQL before applying the idempotent migration.

## Production browser correction (2026-07-23)

Manual browser validation found that the popup coordinator could remain locally suppressed when it missed the one-shot onboarding-ready event. The coordinator now starts eligible to check, while the authenticated backend remains the authoritative onboarding guard. It checks immediately on load and visibility, uses authenticated SSE as the fast wake-up, and polls every 15 seconds as the authoritative recovery mechanism. Normal SSE delivery remains a few seconds; the documented fallback maximum is approximately 15 seconds while the tab is visible.

Portal HTML is returned with `Cache-Control: no-store`. Campaign, onboarding, and What’s New scripts include the exact Platform build commit in their query string, preventing the four-hour Cloudflare browser-cache setting from retaining an older coordinator after deployment. There is no service worker.

The popup and What’s New detail views render campaign type, image, title, summary/body, prices, and a configured primary CTA. Support CTAs open the existing dashboard support-ticket form and prepopulate a campaign/revision reference. Popup close, Escape, and backdrop remain temporary snooze actions; **Dismiss / Mark as read** is permanent for that revision.

Client-side diagnostics are available in the authenticated dashboard console without secrets:

```js
window.MyBeaconCampaignDiagnostics.getState()
window.MyBeaconCampaignDiagnostics.checkNow()
```

The state reports script version, Platform build commit, SSE connection state, last SSE event, last poll, latest popup API result/suppression reason, last JavaScript error, and modal visibility.

Archived campaigns are retained for audit and hidden from the default active management list. Only drafts may be permanently deleted. Published/unpublished campaigns must be archived; resend creates a revision and cannot be double-submitted within five seconds.

Email notification is deferred until after v1. Existing SMTP helpers do not provide revision-scoped queued delivery, per-user outcome tracking, or failure isolation adequate for launch. Email is not a substitute for portal delivery.

## Manual acceptance checklist

1. Hard-refresh the authenticated dashboard once after deployment and confirm `getState().buildCommit` matches `/health`.
2. Publish an immediate popup campaign while the visible portal remains open.
3. Confirm the modal appears within a few seconds through SSE or no later than 15 seconds through polling.
4. Confirm campaign type, image, price, summary, CTA, Remind me later, Dismiss / Mark as read, and close icon are visible.
5. Close temporarily and confirm unread remains; test the configured reminder policy.
6. Use the support CTA and confirm the dashboard support form opens with campaign/revision context.
7. Dismiss and confirm the unread count falls and the same revision does not return.
8. Resend from admin, confirm the displayed revision increments, and confirm one new modal/impression appears.
9. Repeat at desktop, tablet, iPhone/Android width, and Home Assistant webview width.
10. Review every Getting Started stage with no horizontal page scrolling and usable bottom navigation.
