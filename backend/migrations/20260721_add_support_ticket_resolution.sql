-- RC1.2: persist administrator-entered ticket resolutions without altering existing tickets.
ALTER TABLE support_tickets
    ADD COLUMN IF NOT EXISTS resolution TEXT;
