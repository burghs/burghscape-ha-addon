-- RC1.4.1 Campaign Framework: campaigns, selected-client targeting, and per-user read state.
CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    internal_name VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    subtitle VARCHAR(500),
    campaign_type VARCHAR(50) NOT NULL,
    body_content TEXT NOT NULL,
    price_text VARCHAR(100),
    regular_price_text VARCHAR(100),
    call_to_action_label VARCHAR(100),
    image_reference VARCHAR(255),
    image_content_type VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    priority INTEGER NOT NULL DEFAULT 0,
    starts_at TIMESTAMP,
    ends_at TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255) NOT NULL,
    updated_by VARCHAR(255) NOT NULL,
    target_all_clients BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_campaigns_type ON campaigns(campaign_type);
CREATE INDEX IF NOT EXISTS ix_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS ix_campaign_visibility ON campaigns(status, starts_at, ends_at, priority);
CREATE TABLE IF NOT EXISTS campaign_targets (
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    PRIMARY KEY (campaign_id, client_id)
);
CREATE INDEX IF NOT EXISTS ix_campaign_targets_client ON campaign_targets(client_id);
CREATE TABLE IF NOT EXISTS campaign_read_states (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    client_user_id INTEGER NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_campaign_read_user UNIQUE(campaign_id, client_user_id)
);
CREATE INDEX IF NOT EXISTS ix_campaign_reads_campaign ON campaign_read_states(campaign_id);
CREATE INDEX IF NOT EXISTS ix_campaign_reads_user ON campaign_read_states(client_user_id);
