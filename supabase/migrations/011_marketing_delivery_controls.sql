-- Dova Kitchen — Phase 13 delivery controls.
-- Depends on 009_marketing_campaign_workflow.sql.
-- This migration adds policy/audit fields only; it never calls a provider.

ALTER TABLE marketing_campaigns
    ADD COLUMN IF NOT EXISTS control_group_percent SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rate_limit_per_minute INTEGER NOT NULL DEFAULT 20;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'marketing_campaigns_control_group_percent_check'
    ) THEN
        ALTER TABLE marketing_campaigns
            ADD CONSTRAINT marketing_campaigns_control_group_percent_check
            CHECK (control_group_percent BETWEEN 0 AND 50);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'marketing_campaigns_rate_limit_per_minute_check'
    ) THEN
        ALTER TABLE marketing_campaigns
            ADD CONSTRAINT marketing_campaigns_rate_limit_per_minute_check
            CHECK (rate_limit_per_minute BETWEEN 1 AND 600);
    END IF;
END $$;

ALTER TABLE marketing_campaign_recipients
    ADD COLUMN IF NOT EXISTS is_control_group BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS failure_reason TEXT;

ALTER TABLE notification_outbox
    ADD COLUMN IF NOT EXISTS provider_message_id TEXT,
    ADD COLUMN IF NOT EXISTS provider_event_id TEXT,
    ADD COLUMN IF NOT EXISTS failure_reason TEXT,
    ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_callback_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_outbox_provider_event
    ON notification_outbox (provider_event_id)
    WHERE provider_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_notification_outbox_campaign_status
    ON notification_outbox (campaign_id, status, created_at DESC);
