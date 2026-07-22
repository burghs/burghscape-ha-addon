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
