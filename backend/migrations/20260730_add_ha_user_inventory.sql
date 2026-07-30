-- Read-only Home Assistant user inventory cache and short-lived request queue.
CREATE TABLE IF NOT EXISTS ha_user_inventories (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL UNIQUE REFERENCES clients(id) ON DELETE CASCADE,
    ha_users_read BOOLEAN NOT NULL DEFAULT FALSE,
    capability_reported_at TIMESTAMP,
    users JSON NOT NULL DEFAULT '[]'::json,
    last_error_code VARCHAR(50),
    refreshed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_ha_user_inventories_client_id ON ha_user_inventories(client_id);
CREATE TABLE IF NOT EXISTS ha_user_inventory_requests (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    request_id VARCHAR(64) NOT NULL UNIQUE,
    state VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_code VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claimed_at TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    CONSTRAINT ck_ha_user_inventory_request_state CHECK (state IN ('pending','claimed','completed','failed'))
);
CREATE INDEX IF NOT EXISTS ix_ha_user_inventory_requests_client_id ON ha_user_inventory_requests(client_id);
CREATE INDEX IF NOT EXISTS ix_ha_user_inventory_requests_request_id ON ha_user_inventory_requests(request_id);
CREATE INDEX IF NOT EXISTS ix_ha_user_inventory_requests_state ON ha_user_inventory_requests(state);
