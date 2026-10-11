-- ============================================================
-- Dova Kitchen — Migrasi 003: Supplier, PO, Outbox & Ops
-- ============================================================

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id     TEXT PRIMARY KEY DEFAULT 'sup_' || gen_random_uuid()::TEXT,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'Bahan Segar',
    phone           TEXT NOT NULL DEFAULT '',
    email           TEXT NOT NULL DEFAULT '',
    address         TEXT NOT NULL DEFAULT '',
    rating          NUMERIC(3,2) NOT NULL DEFAULT 4.8,
    lead_time_days  INTEGER NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS supplier_items (
    id              BIGSERIAL PRIMARY KEY,
    supplier_id     TEXT NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    unit            TEXT NOT NULL DEFAULT 'kg',
    price_per_unit  INTEGER NOT NULL DEFAULT 0,
    moq             INTEGER NOT NULL DEFAULT 1,
    lead_time_days  INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id           TEXT PRIMARY KEY DEFAULT 'PO-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || SUBSTRING(gen_random_uuid()::TEXT, 1, 6),
    supplier_id     TEXT NOT NULL REFERENCES suppliers(supplier_id),
    status          TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'PARTIAL', 'RECEIVED', 'CLOSED')),
    total_amount    INTEGER NOT NULL DEFAULT 0,
    need_by_date    DATE NOT NULL DEFAULT CURRENT_DATE + INTERVAL '1 day',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS po_items (
    id              BIGSERIAL PRIMARY KEY,
    po_id           TEXT NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
    item_name       TEXT NOT NULL,
    qty             NUMERIC(10,2) NOT NULL DEFAULT 1.0,
    unit            TEXT NOT NULL DEFAULT 'kg',
    unit_price      INTEGER NOT NULL DEFAULT 0,
    subtotal        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notification_outbox (
    id              BIGSERIAL PRIMARY KEY,
    recipient_type  TEXT NOT NULL CHECK (recipient_type IN ('customer', 'supplier', 'admin')),
    recipient_phone TEXT NOT NULL,
    recipient_name  TEXT NOT NULL DEFAULT '',
    channel         TEXT NOT NULL DEFAULT 'whatsapp' CHECK (channel IN ('whatsapp', 'telegram')),
    event_type      TEXT NOT NULL,
    message         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'SENT' CHECK (status IN ('PENDING', 'SENT', 'FAILED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory_stocks (
    id              BIGSERIAL PRIMARY KEY,
    ingredient_name TEXT NOT NULL UNIQUE,
    current_stock   NUMERIC(10,2) NOT NULL DEFAULT 0,
    min_stock       NUMERIC(10,2) NOT NULL DEFAULT 5,
    unit            TEXT NOT NULL DEFAULT 'kg',
    status          TEXT NOT NULL DEFAULT 'AMBIL_AMAN' CHECK (status IN ('AMBIL_AMAN', 'MENIPIS', 'HABIS')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
