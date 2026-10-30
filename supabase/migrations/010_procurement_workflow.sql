-- Dova Kitchen — Migrasi 010: workflow PO yang dapat diaudit
--
-- Draft PO hanya boleh dibuat dari report sourcing live. Approval dan queue
-- dipisahkan dari delivery provider; status outbox PENDING tidak berarti
-- supplier sudah menerima pesan.

BEGIN;

ALTER TABLE purchase_orders
    DROP CONSTRAINT IF EXISTS purchase_orders_status_check;

ALTER TABLE purchase_orders
    ADD CONSTRAINT purchase_orders_status_check
    CHECK (status IN (
        'DRAFT', 'APPROVED', 'SENT', 'ACCEPTED', 'REJECTED', 'PARTIAL',
        'RECEIVED', 'CLOSED'
    ));

ALTER TABLE purchase_orders
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS created_by TEXT REFERENCES customers(customer_id),
    ADD COLUMN IF NOT EXISTS approved_by TEXT REFERENCES customers(customer_id),
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS calculation_version TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS supplier_estimated_delivery DATE;

ALTER TABLE purchase_orders
    ALTER COLUMN need_by_date DROP NOT NULL,
    ALTER COLUMN need_by_date DROP DEFAULT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_orders_idempotency_key
    ON purchase_orders (idempotency_key)
    WHERE idempotency_key IS NOT NULL AND idempotency_key <> '';

ALTER TABLE notification_outbox
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_outbox_idempotency_key
    ON notification_outbox (idempotency_key)
    WHERE idempotency_key IS NOT NULL AND idempotency_key <> '';

COMMIT;
