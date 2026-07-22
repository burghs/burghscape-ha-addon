-- RC1.4.2 login promotion popups and interaction tracking.
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS call_to_action_url VARCHAR(1000);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS popup_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS popup_summary VARCHAR(500);

CREATE TABLE IF NOT EXISTS campaign_popup_events (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    client_user_id INTEGER NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL,
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_campaign_popup_events_campaign_id ON campaign_popup_events(campaign_id);
CREATE INDEX IF NOT EXISTS ix_campaign_popup_events_client_user_id ON campaign_popup_events(client_user_id);
CREATE INDEX IF NOT EXISTS ix_campaign_popup_events_event_type ON campaign_popup_events(event_type);
CREATE INDEX IF NOT EXISTS ix_campaign_popup_user_event
    ON campaign_popup_events(client_user_id, campaign_id, event_type);
