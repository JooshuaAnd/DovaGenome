-- Phase 8: status-based delivery dispatch. GPS is intentionally out of scope.

BEGIN;

ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_role_check;
ALTER TABLE customers
    ADD CONSTRAINT customers_role_check
    CHECK (role IN ('customer', 'kitchen', 'admin', 'supplier', 'courier'));

ALTER TABLE order_items
    ADD COLUMN IF NOT EXISTS meal_slot TEXT NOT NULL DEFAULT 'lunch'
    CHECK (meal_slot IN ('breakfast', 'lunch', 'dinner'));

CREATE TABLE IF NOT EXISTS delivery_stops (
    stop_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id         TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    customer_id      TEXT REFERENCES customers(customer_id),
    customer_name    TEXT NOT NULL DEFAULT '',
    service_date     DATE NOT NULL,
    meal_slot        TEXT NOT NULL CHECK (meal_slot IN ('breakfast', 'lunch', 'dinner')),
    address_snapshot TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'PLANNED'
                     CHECK (status IN ('PLANNED', 'ASSIGNED', 'PICKED_UP', 'OUT_FOR_DELIVERY', 'DELIVERED', 'FAILED', 'CANCELLED')),
    courier_id       TEXT REFERENCES customers(customer_id),
    proof_ref        TEXT NOT NULL DEFAULT '',
    notes            TEXT NOT NULL DEFAULT '',
    assigned_at      TIMESTAMPTZ,
    picked_up_at     TIMESTAMPTZ,
    delivered_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (order_id, service_date, meal_slot)
);

CREATE INDEX IF NOT EXISTS idx_delivery_stops_dispatch
    ON delivery_stops (service_date, meal_slot, status);
CREATE INDEX IF NOT EXISTS idx_delivery_stops_courier
    ON delivery_stops (courier_id, service_date, status);

CREATE TABLE IF NOT EXISTS delivery_events (
    delivery_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stop_id           UUID NOT NULL REFERENCES delivery_stops(stop_id) ON DELETE CASCADE,
    status            TEXT NOT NULL,
    idempotency_key   TEXT NOT NULL UNIQUE,
    actor_id          TEXT NOT NULL REFERENCES customers(customer_id),
    proof_ref         TEXT NOT NULL DEFAULT '',
    note              TEXT NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
