-- Phase 5 continuation: lot-aware FEFO consumption.
-- Apply only after the Supabase backup/restore checkpoint.

ALTER TABLE inventory_movements
    ADD COLUMN IF NOT EXISTS lot_id UUID REFERENCES stock_lots(lot_id);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_lot
    ON inventory_movements (lot_id, created_at DESC);

CREATE TABLE IF NOT EXISTS inventory_lot_allocations (
    allocation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movement_id UUID NOT NULL REFERENCES inventory_movements(movement_id) ON DELETE CASCADE,
    lot_id UUID NOT NULL REFERENCES stock_lots(lot_id),
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    quantity NUMERIC(14, 4) NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (movement_id, lot_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_lot_allocations_lot
    ON inventory_lot_allocations (lot_id, created_at DESC);
