-- Remove false display impressions recorded before the fixed popup overlay was deployed.
-- Dismissals and action clicks remain authoritative and are not changed.
DELETE FROM campaign_popup_events
WHERE event_type = 'displayed'
  AND occurred_at < TIMESTAMP '2026-07-22 18:18:31';
