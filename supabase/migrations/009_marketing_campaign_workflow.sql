-- Dova Kitchen — Migrasi 009: consent, campaign review, dan idempotent outbox
-- Campaign tidak mengirim pesan sendiri. Queue hanya membuat outbox PENDING.

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS marketing_opt_in_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS marketing_campaigns (
    campaign_id                 TEXT PRIMARY KEY,
    campaign_type               TEXT NOT NULL CHECK (campaign_type IN ('WINBACK')),
    status                      TEXT NOT NULL DEFAULT 'DRAFT'
                                CHECK (status IN ('DRAFT', 'APPROVED', 'QUEUED', 'CANCELLED', 'COMPLETED')),
    channel                     TEXT NOT NULL CHECK (channel IN ('whatsapp', 'telegram')),
    data_mode                   TEXT NOT NULL CHECK (data_mode IN ('live', 'simulation')),
    source                      TEXT NOT NULL,
    calculation_version         TEXT NOT NULL,
    source_calculation_version  TEXT NOT NULL,
    source_as_of                DATE,
    data_age_days               INTEGER CHECK (data_age_days >= 0),
    audience_count              INTEGER NOT NULL CHECK (audience_count >= 0),
    excluded_count              INTEGER NOT NULL DEFAULT 0 CHECK (excluded_count >= 0),
    created_by                  TEXT NOT NULL REFERENCES customers(customer_id),
    approved_by                 TEXT REFERENCES customers(customer_id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at                 TIMESTAMPTZ,
    queued_at                   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_marketing_campaigns_status_created
    ON marketing_campaigns (status, created_at DESC);

CREATE TABLE IF NOT EXISTS marketing_campaign_recipients (
    id                  BIGSERIAL PRIMARY KEY,
    campaign_id         TEXT NOT NULL REFERENCES marketing_campaigns(campaign_id) ON DELETE CASCADE,
    customer_id         TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    recipient_name      TEXT NOT NULL,
    recipient_phone     TEXT NOT NULL,
    recipient_chat_id   BIGINT,
    risk_band           TEXT NOT NULL CHECK (risk_band IN ('HIGH', 'MEDIUM')),
    reason_codes        JSONB NOT NULL DEFAULT '[]',
    message             TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDING_REVIEW'
                        CHECK (status IN ('PENDING_REVIEW', 'QUEUED', 'SENT', 'FAILED', 'SKIPPED')),
    idempotency_key     TEXT NOT NULL UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    queued_at           TIMESTAMPTZ,
    sent_at             TIMESTAMPTZ,
    UNIQUE (campaign_id, customer_id)
);

CREATE INDEX IF NOT EXISTS idx_marketing_recipients_campaign_status
    ON marketing_campaign_recipients (campaign_id, status);

ALTER TABLE notification_outbox
    ADD COLUMN IF NOT EXISTS campaign_id TEXT REFERENCES marketing_campaigns(campaign_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT NOT NULL DEFAULT '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_outbox_idempotency
    ON notification_outbox (idempotency_key)
    WHERE idempotency_key <> '';

ALTER TABLE marketing_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketing_campaign_recipients ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "deny_public_marketing_campaigns" ON marketing_campaigns;
CREATE POLICY "deny_public_marketing_campaigns"
    ON marketing_campaigns FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "deny_public_marketing_campaign_recipients" ON marketing_campaign_recipients;
CREATE POLICY "deny_public_marketing_campaign_recipients"
    ON marketing_campaign_recipients FOR ALL TO anon, authenticated USING (false);
