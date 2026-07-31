BEGIN;
CREATE TABLE IF NOT EXISTS client_guides (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description VARCHAR(1000) NOT NULL DEFAULT '',
    category VARCHAR(100) NOT NULL,
    stored_file_name VARCHAR(255) NOT NULL UNIQUE,
    original_file_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,
    visibility_mode VARCHAR(20) NOT NULL DEFAULT 'all',
    published BOOLEAN NOT NULL DEFAULT FALSE,
    featured BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_client_guides_visibility CHECK (visibility_mode IN ('all','selected')),
    CONSTRAINT ck_client_guides_file_size CHECK (file_size > 0)
);
CREATE INDEX IF NOT EXISTS ix_client_guides_published_order ON client_guides(published, display_order, updated_at);
CREATE TABLE IF NOT EXISTS client_guide_assignments (
    guide_id INTEGER NOT NULL REFERENCES client_guides(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    PRIMARY KEY (guide_id, client_id)
);
CREATE INDEX IF NOT EXISTS ix_client_guide_assignments_client ON client_guide_assignments(client_id, guide_id);
COMMIT;
