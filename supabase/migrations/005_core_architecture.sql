-- ============================================================================
-- DovaGenome — Phase 1: core architecture foundations
--
-- Scope:
--   * canonical ingredient identity + recipe provenance/versioning
--   * supplier account mapping for server-side RBAC
--   * payment-attempt and kitchen-ticket boundaries
--   * inventory movement/reservation ledger foundations
--   * RFM/forecast snapshots and audit request metadata
--
-- This migration intentionally does not change existing order/payment status
-- transitions or create business records automatically. Those belong to the
-- payment, KDS, recipe, and inventory phases after contract tests exist.
-- It is written to be rerunnable against the current repository schema.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- --------------------------------------------------------------------------
-- 1. Role and identity foundations
-- --------------------------------------------------------------------------

ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_role_check;
ALTER TABLE customers
    ADD CONSTRAINT customers_role_check
    CHECK (role IN ('customer', 'kitchen', 'admin', 'supplier'));

CREATE TABLE IF NOT EXISTS supplier_accounts (
    supplier_account_id BIGSERIAL PRIMARY KEY,
    customer_id        TEXT NOT NULL UNIQUE REFERENCES customers(customer_id) ON DELETE CASCADE,
    supplier_id        TEXT NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    status             TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active', 'inactive')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, supplier_id)
);

CREATE INDEX IF NOT EXISTS idx_supplier_accounts_supplier
    ON supplier_accounts (supplier_id, status);

-- --------------------------------------------------------------------------
-- 2. Canonical ingredient identity and recipe provenance
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id       TEXT PRIMARY KEY DEFAULT 'ing_' || gen_random_uuid()::TEXT,
    name                TEXT NOT NULL,
    normalized_name     TEXT NOT NULL UNIQUE,
    default_unit        TEXT NOT NULL DEFAULT 'kg',
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
                        CHECK (verification_status IN ('UNVERIFIED', 'VERIFIED', 'RETIRED')),
    provenance_status   TEXT NOT NULL DEFAULT 'UNKNOWN'
                        CHECK (provenance_status IN ('UNKNOWN', 'OPERATOR', 'SUPPLIER', 'IMPORTED')),
    source_ref          TEXT NOT NULL DEFAULT '',
    metadata            JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingredients_verification
    ON ingredients (verification_status, normalized_name);

-- Backfill the identity table from names already present in the legacy tables.
INSERT INTO ingredients (name, normalized_name, default_unit, provenance_status, source_ref)
SELECT DISTINCT ON (normalized_name)
    source_name,
    normalized_name,
    source_unit,
    source_type,
    source_ref
FROM (
    SELECT
        TRIM(mi.nama) AS source_name,
        LOWER(REGEXP_REPLACE(TRIM(mi.nama), '\\s+', ' ', 'g')) AS normalized_name,
        'kg' AS source_unit,
        'IMPORTED' AS source_type,
        'menu_ingredients' AS source_ref
    FROM menu_ingredients mi
    WHERE NULLIF(TRIM(mi.nama), '') IS NOT NULL
    UNION ALL
    SELECT
        TRIM(si.ingredient_name),
        LOWER(REGEXP_REPLACE(TRIM(si.ingredient_name), '\\s+', ' ', 'g')),
        COALESCE(NULLIF(TRIM(si.unit), ''), 'kg'),
        'SUPPLIER',
        'supplier_items'
    FROM supplier_items si
    WHERE NULLIF(TRIM(si.ingredient_name), '') IS NOT NULL
    UNION ALL
    SELECT
        TRIM(ist.ingredient_name),
        LOWER(REGEXP_REPLACE(TRIM(ist.ingredient_name), '\\s+', ' ', 'g')),
        COALESCE(NULLIF(TRIM(ist.unit), ''), 'kg'),
        'IMPORTED',
        'inventory_stocks'
    FROM inventory_stocks ist
    WHERE NULLIF(TRIM(ist.ingredient_name), '') IS NOT NULL
) AS sources
ORDER BY normalized_name, source_ref
ON CONFLICT (normalized_name) DO NOTHING;

ALTER TABLE menu_ingredients
    ADD COLUMN IF NOT EXISTS ingredient_id TEXT,
    ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::JSONB;

ALTER TABLE supplier_items
    ADD COLUMN IF NOT EXISTS ingredient_id TEXT;

ALTER TABLE inventory_stocks
    ADD COLUMN IF NOT EXISTS ingredient_id TEXT;

UPDATE menu_ingredients mi
SET ingredient_id = i.ingredient_id
FROM ingredients i
WHERE mi.ingredient_id IS NULL
  AND i.normalized_name = LOWER(REGEXP_REPLACE(TRIM(mi.nama), '\\s+', ' ', 'g'));

UPDATE supplier_items si
SET ingredient_id = i.ingredient_id
FROM ingredients i
WHERE si.ingredient_id IS NULL
  AND i.normalized_name = LOWER(REGEXP_REPLACE(TRIM(si.ingredient_name), '\\s+', ' ', 'g'));

UPDATE inventory_stocks ist
SET ingredient_id = i.ingredient_id
FROM ingredients i
WHERE ist.ingredient_id IS NULL
  AND i.normalized_name = LOWER(REGEXP_REPLACE(TRIM(ist.ingredient_name), '\\s+', ' ', 'g'));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_menu_ingredients_ingredient'
    ) THEN
        ALTER TABLE menu_ingredients
            ADD CONSTRAINT fk_menu_ingredients_ingredient
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_supplier_items_ingredient'
    ) THEN
        ALTER TABLE supplier_items
            ADD CONSTRAINT fk_supplier_items_ingredient
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_inventory_stocks_ingredient'
    ) THEN
        ALTER TABLE inventory_stocks
            ADD CONSTRAINT fk_inventory_stocks_ingredient
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS recipe_versions (
    recipe_version_id TEXT PRIMARY KEY DEFAULT 'recipe_' || gen_random_uuid()::TEXT,
    menu_id           TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE CASCADE,
    version_no        INTEGER NOT NULL CHECK (version_no > 0),
    status            TEXT NOT NULL DEFAULT 'DRAFT'
                      CHECK (status IN ('DRAFT', 'PENDING_VERIFICATION', 'VERIFIED', 'RETIRED')),
    source            TEXT NOT NULL DEFAULT '',
    source_ref        TEXT NOT NULL DEFAULT '',
    yield_quantity    NUMERIC(12, 4) NOT NULL DEFAULT 1 CHECK (yield_quantity > 0),
    yield_unit        TEXT NOT NULL DEFAULT 'portion',
    cross_contact_risk TEXT NOT NULL DEFAULT 'UNKNOWN'
                      CHECK (cross_contact_risk IN ('UNKNOWN', 'LOW', 'MEDIUM', 'HIGH')),
    verified_by       TEXT REFERENCES customers(customer_id),
    verified_at       TIMESTAMPTZ,
    notes             TEXT NOT NULL DEFAULT '',
    metadata          JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (menu_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_recipe_versions_menu_status
    ON recipe_versions (menu_id, status, version_no DESC);

CREATE TABLE IF NOT EXISTS recipe_components (
    recipe_component_id BIGSERIAL PRIMARY KEY,
    recipe_version_id   TEXT NOT NULL REFERENCES recipe_versions(recipe_version_id) ON DELETE CASCADE,
    ingredient_id       TEXT REFERENCES ingredients(ingredient_id),
    child_recipe_version_id TEXT REFERENCES recipe_versions(recipe_version_id),
    quantity            NUMERIC(12, 4) NOT NULL CHECK (quantity > 0),
    unit                TEXT NOT NULL,
    preparation         TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
                        CHECK (verification_status IN ('UNVERIFIED', 'VERIFIED', 'RETIRED')),
    source              TEXT NOT NULL DEFAULT '',
    sort_order          INTEGER NOT NULL DEFAULT 0,
    metadata            JSONB NOT NULL DEFAULT '{}'::JSONB,
    CHECK ((ingredient_id IS NOT NULL) <> (child_recipe_version_id IS NOT NULL)),
    CHECK (child_recipe_version_id IS NULL OR child_recipe_version_id <> recipe_version_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_components_recipe
    ON recipe_components (recipe_version_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_recipe_components_ingredient
    ON recipe_components (ingredient_id);

CREATE TABLE IF NOT EXISTS recipe_verification_events (
    event_id          BIGSERIAL PRIMARY KEY,
    recipe_version_id TEXT NOT NULL REFERENCES recipe_versions(recipe_version_id) ON DELETE CASCADE,
    action            TEXT NOT NULL CHECK (action IN ('CREATED', 'SUBMITTED', 'VERIFIED', 'REJECTED', 'RETIRED')),
    verifier_id       TEXT REFERENCES customers(customer_id),
    evidence          JSONB NOT NULL DEFAULT '{}'::JSONB,
    notes             TEXT NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- --------------------------------------------------------------------------
-- 3. Payment and kitchen operational boundaries
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS payment_attempts (
    payment_attempt_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id                TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    provider                TEXT NOT NULL,
    provider_payment_id     TEXT NOT NULL DEFAULT '',
    provider_event_id       TEXT,
    idempotency_key         TEXT NOT NULL UNIQUE,
    status                  TEXT NOT NULL DEFAULT 'INITIATED'
                            CHECK (status IN ('INITIATED', 'REQUIRES_ACTION', 'SUCCEEDED', 'FAILED', 'EXPIRED', 'REFUNDED')),
    amount                  BIGINT NOT NULL CHECK (amount >= 0),
    currency                TEXT NOT NULL DEFAULT 'IDR',
    expires_at              TIMESTAMPTZ,
    signature_verified      BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at             TIMESTAMPTZ,
    provider_payload_redacted JSONB NOT NULL DEFAULT '{}'::JSONB,
    failure_code            TEXT NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_event_id)
);

CREATE INDEX IF NOT EXISTS idx_payment_attempts_order_status
    ON payment_attempts (order_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_attempts_expiry
    ON payment_attempts (expires_at) WHERE status IN ('INITIATED', 'REQUIRES_ACTION');

CREATE TABLE IF NOT EXISTS kitchen_tickets (
    kitchen_ticket_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id           TEXT NOT NULL UNIQUE REFERENCES orders(order_id) ON DELETE CASCADE,
    payment_attempt_id UUID REFERENCES payment_attempts(payment_attempt_id),
    status             TEXT NOT NULL DEFAULT 'QUEUED'
                       CHECK (status IN ('QUEUED', 'PREPARING', 'READY', 'COMPLETED', 'CANCELLED')),
    allergy_snapshot   JSONB NOT NULL DEFAULT '{}'::JSONB,
    recipe_snapshot    JSONB NOT NULL DEFAULT '{}'::JSONB,
    released_at        TIMESTAMPTZ,
    started_at         TIMESTAMPTZ,
    ready_at           TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kitchen_tickets_status
    ON kitchen_tickets (status, created_at);

-- --------------------------------------------------------------------------
-- 4. Inventory ledger foundations
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS inventory_movements (
    movement_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id      TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    ingredient_name_snapshot TEXT NOT NULL,
    movement_type      TEXT NOT NULL
                       CHECK (movement_type IN ('RECEIPT', 'CONSUMPTION', 'ADJUSTMENT', 'RESERVATION', 'RELEASE')),
    quantity           NUMERIC(14, 4) NOT NULL CHECK (quantity <> 0),
    unit               TEXT NOT NULL,
    order_id           TEXT REFERENCES orders(order_id),
    po_id              TEXT REFERENCES purchase_orders(po_id),
    idempotency_key    TEXT NOT NULL UNIQUE,
    actor_id           TEXT REFERENCES customers(customer_id),
    note               TEXT NOT NULL DEFAULT '',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_ingredient_time
    ON inventory_movements (ingredient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_movements_order
    ON inventory_movements (order_id);

CREATE TABLE IF NOT EXISTS inventory_reservations (
    reservation_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id           TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    ingredient_id      TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    quantity           NUMERIC(14, 4) NOT NULL CHECK (quantity > 0),
    unit               TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'RESERVED'
                       CHECK (status IN ('RESERVED', 'CONSUMED', 'RELEASED', 'CANCELLED')),
    idempotency_key    TEXT NOT NULL UNIQUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (order_id, ingredient_id, status)
);

CREATE INDEX IF NOT EXISTS idx_inventory_reservations_active
    ON inventory_reservations (ingredient_id, status)
    WHERE status = 'RESERVED';

-- --------------------------------------------------------------------------
-- 5. Analytics snapshots and audit metadata
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rfm_snapshots (
    snapshot_id        BIGSERIAL PRIMARY KEY,
    customer_id        TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    snapshot_date      DATE NOT NULL,
    recency_days       INTEGER NOT NULL CHECK (recency_days >= 0),
    frequency          INTEGER NOT NULL CHECK (frequency >= 0),
    monetary           NUMERIC(14, 2) NOT NULL CHECK (monetary >= 0),
    recency_score      SMALLINT CHECK (recency_score BETWEEN 1 AND 5),
    frequency_score    SMALLINT CHECK (frequency_score BETWEEN 1 AND 5),
    monetary_score     SMALLINT CHECK (monetary_score BETWEEN 1 AND 5),
    segment            TEXT NOT NULL DEFAULT '',
    data_mode          TEXT NOT NULL DEFAULT 'live' CHECK (data_mode IN ('live', 'simulation')),
    source             TEXT NOT NULL DEFAULT '',
    calculation_version TEXT NOT NULL DEFAULT '',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, snapshot_date, calculation_version)
);

CREATE INDEX IF NOT EXISTS idx_rfm_snapshots_date_segment
    ON rfm_snapshots (snapshot_date, segment);

CREATE TABLE IF NOT EXISTS forecast_snapshots (
    forecast_snapshot_id BIGSERIAL PRIMARY KEY,
    series_key           TEXT NOT NULL,
    target_type          TEXT NOT NULL CHECK (target_type IN ('MENU', 'INGREDIENT', 'SUPPLIER')),
    target_date          DATE NOT NULL,
    forecast_quantity    NUMERIC(14, 4) NOT NULL CHECK (forecast_quantity >= 0),
    unit                 TEXT NOT NULL,
    method               TEXT NOT NULL,
    lower_bound          NUMERIC(14, 4),
    upper_bound          NUMERIC(14, 4),
    data_mode            TEXT NOT NULL DEFAULT 'live' CHECK (data_mode IN ('live', 'simulation')),
    source               TEXT NOT NULL DEFAULT '',
    calculation_version  TEXT NOT NULL DEFAULT '',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (series_key, target_type, target_date, method, calculation_version)
);

CREATE INDEX IF NOT EXISTS idx_forecast_snapshots_target_date
    ON forecast_snapshots (target_date, target_type, series_key);

ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS actor_role TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS request_id TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_audit_log_request_id
    ON audit_log (request_id) WHERE request_id <> '';

-- --------------------------------------------------------------------------
-- 6. Updated-at triggers and deny-by-default public access
-- --------------------------------------------------------------------------

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'supplier_accounts', 'ingredients', 'recipe_versions',
        'payment_attempts', 'kitchen_tickets', 'inventory_reservations'
    ] LOOP
        EXECUTE format(
            'CREATE OR REPLACE TRIGGER trg_%I_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
            t, t
        );
    END LOOP;
END
$$;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'supplier_accounts', 'ingredients', 'recipe_versions',
        'recipe_components', 'recipe_verification_events',
        'payment_attempts', 'kitchen_tickets', 'inventory_movements',
        'inventory_reservations', 'rfm_snapshots', 'forecast_snapshots'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', 'deny_public_' || t, t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)',
            'deny_public_' || t, t
        );
    END LOOP;
END
$$;
