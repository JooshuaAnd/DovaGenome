-- Phase 4: make per-menu demand quantity explicit.
-- Existing rows are conservatively backfilled as one portion per order item;
-- this is an auditable legacy default, not an invented historical multiplier.

ALTER TABLE order_items
    ADD COLUMN IF NOT EXISTS quantity NUMERIC(12, 4) NOT NULL DEFAULT 1;

ALTER TABLE order_items
    ADD COLUMN IF NOT EXISTS unit TEXT NOT NULL DEFAULT 'portion';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'order_items_quantity_positive'
          AND conrelid = 'order_items'::regclass
    ) THEN
        ALTER TABLE order_items
            ADD CONSTRAINT order_items_quantity_positive CHECK (quantity > 0);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_order_items_menu_date_quantity
    ON order_items (menu_id, order_id, quantity);

COMMENT ON COLUMN order_items.quantity IS
    'Demand quantity for this menu line; legacy rows default to one portion.';
COMMENT ON COLUMN order_items.unit IS
    'Demand unit; current contract is portion.';
