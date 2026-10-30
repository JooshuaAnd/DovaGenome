-- Phase 7: supplier goods receipt and stock posting.
-- Apply only after the Supabase backup/restore checkpoint.

BEGIN;

ALTER TABLE po_items
    ADD COLUMN IF NOT EXISTS ingredient_id TEXT REFERENCES ingredients(ingredient_id),
    ADD COLUMN IF NOT EXISTS received_qty NUMERIC(14, 4) NOT NULL DEFAULT 0;

UPDATE po_items pi
SET ingredient_id = i.ingredient_id
FROM ingredients i
WHERE pi.ingredient_id IS NULL
  AND i.normalized_name = LOWER(REGEXP_REPLACE(TRIM(pi.item_name), '\\s+', ' ', 'g'));

CREATE INDEX IF NOT EXISTS idx_po_items_ingredient
    ON po_items (ingredient_id);

CREATE TABLE IF NOT EXISTS goods_receipts (
    receipt_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_id            TEXT NOT NULL REFERENCES purchase_orders(po_id),
    supplier_id      TEXT NOT NULL REFERENCES suppliers(supplier_id),
    received_by      TEXT NOT NULL REFERENCES customers(customer_id),
    status           TEXT NOT NULL DEFAULT 'POSTED'
                     CHECK (status IN ('POSTED', 'VOIDED')),
    idempotency_key  TEXT NOT NULL UNIQUE,
    notes            TEXT NOT NULL DEFAULT '',
    received_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_goods_receipts_po
    ON goods_receipts (po_id, received_at DESC);

CREATE TABLE IF NOT EXISTS goods_receipt_items (
    receipt_item_id  BIGSERIAL PRIMARY KEY,
    receipt_id       UUID NOT NULL REFERENCES goods_receipts(receipt_id) ON DELETE CASCADE,
    po_item_id       BIGINT NOT NULL REFERENCES po_items(id),
    ingredient_id    TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    stock_lot_id     UUID REFERENCES stock_lots(lot_id),
    quantity         NUMERIC(14, 4) NOT NULL CHECK (quantity > 0),
    unit             TEXT NOT NULL,
    unit_price       NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    UNIQUE (receipt_id, po_item_id)
);

CREATE INDEX IF NOT EXISTS idx_goods_receipt_items_ingredient
    ON goods_receipt_items (ingredient_id, receipt_id);

COMMIT;
