-- Phase 11/12: production batch, planned BOM issue, and weigh-event ledger.
-- Apply only after the Supabase backup/restore checkpoint.

CREATE TABLE IF NOT EXISTS production_batches (
    batch_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_date        DATE NOT NULL,
    meal_slot           TEXT NOT NULL DEFAULT 'lunch'
                        CHECK (meal_slot IN ('breakfast', 'lunch', 'dinner', 'snack')),
    site_code           TEXT NOT NULL DEFAULT 'main-kitchen',
    recipe_version_id   TEXT NOT NULL REFERENCES recipe_versions(recipe_version_id),
    planned_portions    INTEGER NOT NULL CHECK (planned_portions > 0),
    status              TEXT NOT NULL DEFAULT 'DRAFT'
                        CHECK (status IN ('DRAFT', 'OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    notes               TEXT NOT NULL DEFAULT '',
    created_by          TEXT NOT NULL REFERENCES customers(customer_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (service_date, meal_slot, site_code, recipe_version_id, status)
);

CREATE INDEX IF NOT EXISTS idx_production_batches_service
    ON production_batches (service_date, meal_slot, status);

CREATE TABLE IF NOT EXISTS production_batch_requirements (
    requirement_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID NOT NULL REFERENCES production_batches(batch_id) ON DELETE CASCADE,
    ingredient_id       TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    ingredient_name     TEXT NOT NULL,
    planned_quantity    NUMERIC(14, 4) NOT NULL CHECK (planned_quantity > 0),
    unit                TEXT NOT NULL,
    issued_quantity     NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (issued_quantity >= 0),
    variance_quantity   NUMERIC(14, 4) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, ingredient_id, unit)
);

CREATE INDEX IF NOT EXISTS idx_batch_requirements_batch
    ON production_batch_requirements (batch_id, ingredient_name);

CREATE TABLE IF NOT EXISTS stock_lots (
    lot_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id       TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    supplier_id         TEXT REFERENCES suppliers(supplier_id),
    lot_code            TEXT NOT NULL DEFAULT '',
    barcode_value       TEXT NOT NULL DEFAULT '',
    received_at         DATE,
    expiry_at           DATE,
    location            TEXT NOT NULL DEFAULT 'main-kitchen',
    quantity_on_hand    NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    unit                TEXT NOT NULL,
    cost_per_unit       NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (cost_per_unit >= 0),
    status              TEXT NOT NULL DEFAULT 'AVAILABLE'
                        CHECK (status IN ('AVAILABLE', 'QUARANTINED', 'EXPIRED', 'CLOSED')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_lots_ingredient_expiry
    ON stock_lots (ingredient_id, expiry_at, status);

CREATE TABLE IF NOT EXISTS weigh_events (
    weigh_event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID NOT NULL REFERENCES production_batches(batch_id) ON DELETE CASCADE,
    requirement_id      UUID NOT NULL REFERENCES production_batch_requirements(requirement_id),
    ingredient_id       TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    lot_id              UUID REFERENCES stock_lots(lot_id),
    planned_grams       NUMERIC(14, 4) NOT NULL CHECK (planned_grams > 0),
    tare_grams          NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (tare_grams >= 0),
    actual_net_grams    NUMERIC(14, 4) NOT NULL CHECK (actual_net_grams > 0),
    scale_source        TEXT NOT NULL DEFAULT 'manual'
                        CHECK (scale_source IN ('manual', 'bluetooth')),
    device_id           TEXT NOT NULL DEFAULT '',
    operator_id         TEXT NOT NULL REFERENCES customers(customer_id),
    idempotency_key     TEXT NOT NULL UNIQUE,
    status              TEXT NOT NULL DEFAULT 'POSTED'
                        CHECK (status IN ('POSTED', 'VOIDED')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weigh_events_batch
    ON weigh_events (batch_id, created_at DESC);

ALTER TABLE inventory_movements
    ADD COLUMN IF NOT EXISTS production_batch_id UUID REFERENCES production_batches(batch_id),
    ADD COLUMN IF NOT EXISTS weigh_event_id UUID REFERENCES weigh_events(weigh_event_id);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_batch
    ON inventory_movements (production_batch_id, created_at DESC);

