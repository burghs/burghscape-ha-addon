# Campaign Leads

Campaign Leads is the dedicated sales workflow for authenticated client responses to published, visible campaigns. It replaces the former campaign-to-Support-Ticket behavior; existing Support Tickets and support APIs remain unchanged.

## Client workflow

A campaign configured with **Create campaign lead** renders **I’m Interested**. The client modal accepts optional comments and requires preferred contact method (`email`, `phone`, or `whatsapp`) and preferred contact time. Submission is authorized from the portal session and the backend resolves both client and visible campaign server-side.

A successful request persists a `new` lead plus its first status-history record before returning. It then immediately attempts:

- Sales email to `sales@burghscape.co.za`, subject `New Campaign Interest – {Campaign Title}`, containing client/contact/company/campaign/submission/comments/preference data and the management link.
- Client acknowledgement, subject `We've received your request`, confirming that Burghscape will make contact.

Email errors are isolated from the committed lead and logged without exposing credentials. Campaign interest does not create, update, or link a Support Ticket.

## Management workflow

Management → **Campaign Leads** provides search plus status/assignee filtering, a CRM table, and full lead details. Administrators can update status, assign a staff name/email, maintain internal notes, and append a history note. Statuses are New, Contacted, Quoted, Scheduled, Won, Lost, and Cancelled.

Dashboard and lead-page metrics show New, Open (New/Contacted/Quoted/Scheduled), Won, Lost, and conversion rate. Conversion is `Won / (Won + Lost)` and is zero when there are no decided leads.

Campaign popup/read analytics remain separate: impressions, snoozes, dismissals, opens, and CTA actions are stored by campaign delivery revision. Lead creation is the sales conversion record.

## Security and retention

Client identity and campaign visibility are derived from the authenticated portal session. Management endpoints require administrator authentication. Responses contain contact/lead data needed by management but no password, token, or storage secret. Campaign/client deletion is restricted when a lead depends on it, preserving attribution; deleting a submitting portal user retains the lead and sets its user reference to null.

## Tests and deployment

`backend/tests/test_campaign_leads.py` covers creation, both emails, zero Support Ticket creation, status/history, assignment, search/filter, authentication, and validation. `frontend/tests/campaign-leads.test.mjs` covers the CRM navigation and UI contract. The legacy CTA regression confirms previously stored `support` campaign CTAs are compatibility-mapped to the lead flow.

Migration: `backend/migrations/20260731_add_campaign_leads.sql`. Deployment and rollback use `deploy/scripts/deploy_platform.sh`; rollback retains the additive lead tables and data.
