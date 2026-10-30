-- Phase 7: payment -> paid-only kitchen release.
--
-- Migration 005 already creates the payment_attempts and kitchen_tickets
-- tables. This migration only adds the indexes needed by the webhook and
-- operational queue. It is intentionally safe to run repeatedly.

CREATE INDEX IF NOT EXISTS idx_payment_attempts_provider_payment
    ON payment_attempts (provider, provider_payment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kitchen_tickets_order_status
    ON kitchen_tickets (order_id, status);

COMMENT ON TABLE payment_attempts IS
    'Signed provider payment attempts; one provider event is idempotent.';
COMMENT ON TABLE kitchen_tickets IS
    'Paid-order kitchen tickets; created only after payment verification.';
