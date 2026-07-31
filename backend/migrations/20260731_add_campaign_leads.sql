BEGIN;
CREATE TABLE IF NOT EXISTS campaign_leads (
 id SERIAL PRIMARY KEY,
 campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE RESTRICT,
 client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
 client_user_id INTEGER REFERENCES client_users(id) ON DELETE SET NULL,
 comments TEXT,
 preferred_contact_method VARCHAR(30) NOT NULL,
 preferred_contact_time VARCHAR(255) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'new',
 assigned_to VARCHAR(255),
 internal_notes TEXT,
 submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT ck_campaign_lead_status CHECK (status IN ('new','contacted','quoted','scheduled','won','lost','cancelled')),
 CONSTRAINT ck_campaign_lead_contact CHECK (preferred_contact_method IN ('email','phone','whatsapp'))
);
CREATE INDEX IF NOT EXISTS ix_campaign_leads_status ON campaign_leads(status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS ix_campaign_leads_client ON campaign_leads(client_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS ix_campaign_leads_campaign ON campaign_leads(campaign_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS ix_campaign_leads_assigned ON campaign_leads(assigned_to);
CREATE TABLE IF NOT EXISTS campaign_lead_history (
 id SERIAL PRIMARY KEY,
 lead_id INTEGER NOT NULL REFERENCES campaign_leads(id) ON DELETE CASCADE,
 from_status VARCHAR(20),
 to_status VARCHAR(20) NOT NULL,
 changed_by VARCHAR(255) NOT NULL,
 note TEXT,
 changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_campaign_lead_history_lead ON campaign_lead_history(lead_id, changed_at);
COMMIT;
