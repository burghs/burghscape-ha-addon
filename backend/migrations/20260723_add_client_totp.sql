-- Optional client TOTP two-factor authentication (Phase 1).
-- Additive and backward compatible: every existing client user remains disabled.
BEGIN;
ALTER TABLE client_users ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE client_users ADD COLUMN IF NOT EXISTS encrypted_totp_secret TEXT;
ALTER TABLE client_users ADD COLUMN IF NOT EXISTS two_factor_enabled_at TIMESTAMP WITHOUT TIME ZONE;

CREATE TABLE IF NOT EXISTS two_factor_recovery_codes (
    id SERIAL PRIMARY KEY,
    client_user_id INTEGER NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    code_hash VARCHAR(255) NOT NULL,
    used_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_two_factor_recovery_codes_user ON two_factor_recovery_codes(client_user_id);

CREATE TABLE IF NOT EXISTS two_factor_pending_enrollments (
    id SERIAL PRIMARY KEY,
    client_user_id INTEGER NOT NULL UNIQUE REFERENCES client_users(id) ON DELETE CASCADE,
    encrypted_secret TEXT NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_two_factor_pending_user ON two_factor_pending_enrollments(client_user_id);

CREATE TABLE IF NOT EXISTS two_factor_challenges (
    id SERIAL PRIMARY KEY,
    client_user_id INTEGER NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    used_at TIMESTAMP WITHOUT TIME ZONE,
    invalidated_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_two_factor_challenges_user ON two_factor_challenges(client_user_id);
CREATE INDEX IF NOT EXISTS ix_two_factor_challenges_token ON two_factor_challenges(token_hash);

CREATE TABLE IF NOT EXISTS security_audit_events (
    id SERIAL PRIMARY KEY,
    administrator VARCHAR(255),
    client_user_id INTEGER REFERENCES client_users(id) ON DELETE SET NULL,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    reason TEXT,
    ip_address VARCHAR(64),
    user_agent VARCHAR(500),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_security_audit_user ON security_audit_events(client_user_id);
CREATE INDEX IF NOT EXISTS ix_security_audit_client ON security_audit_events(client_id);
CREATE INDEX IF NOT EXISTS ix_security_audit_action ON security_audit_events(action);
COMMIT;
