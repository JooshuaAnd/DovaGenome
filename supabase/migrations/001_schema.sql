-- ============================================================
-- DovaGenome — migrasi awal Fase 0
-- Jalankan: psql "$DATABASE_URL" -f supabase/migrations/001_schema.sql
-- Atau via Supabase SQL Editor (paste seluruh file).
-- Idempoten: pakai CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- ============================================================

-- Extension uuid
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── 1. packages ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS packages (
    code        TEXT PRIMARY KEY,          -- mis. "pkg_full"
    name        TEXT NOT NULL,
    days        TEXT[] NOT NULL DEFAULT '{}',
    description TEXT NOT NULL DEFAULT '',
    price       INTEGER,                   -- IDR, NULL = belum diset
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_packages_active ON packages (active);

ALTER TABLE packages ENABLE ROW LEVEL SECURITY;
-- service_role bypass RLS secara default di Supabase; policy ini hanya
-- mematikan akses anon/authenticated yang mungkin mencoba langsung.
DROP POLICY IF EXISTS "deny_public_packages" ON packages;
CREATE POLICY "deny_public_packages"
    ON packages FOR ALL TO anon, authenticated USING (false);

-- ── 2. allergens ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS allergens (
    code        TEXT PRIMARY KEY,          -- mis. "alg_gluten"
    label       TEXT NOT NULL,
    risiko      TEXT NOT NULL DEFAULT '',
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    category    TEXT NOT NULL DEFAULT 'allergy'
                CHECK (category IN ('allergy','intolerance','medical','preference')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_allergens_active ON allergens (active);

ALTER TABLE allergens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_allergens" ON allergens;
CREATE POLICY "deny_public_allergens"
    ON allergens FOR ALL TO anon, authenticated USING (false);

-- ── 3. menus ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS menus (
    menu_id         TEXT PRIMARY KEY,      -- deterministik: "menu_senin_ayam-..."
    hari            TEXT NOT NULL
                    CHECK (hari IN ('Senin','Selasa','Rabu','Kamis','Jumat','Sabtu')),
    nama_menu       TEXT NOT NULL,
    deskripsi       TEXT NOT NULL DEFAULT '',
    alat_dapur_steril TEXT[] NOT NULL DEFAULT '{}',
    published       BOOLEAN NOT NULL DEFAULT TRUE,
    package_codes   TEXT[] NOT NULL DEFAULT '{}', -- kosong = semua paket
    option_index    INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_menus_hari         ON menus (hari);
CREATE INDEX IF NOT EXISTS idx_menus_published    ON menus (published);
CREATE INDEX IF NOT EXISTS idx_menus_option_index ON menus (hari, option_index);

ALTER TABLE menus ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_menus" ON menus;
CREATE POLICY "deny_public_menus"
    ON menus FOR ALL TO anon, authenticated USING (false);

-- ── 4. menu_ingredients ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS menu_ingredients (
    id                  BIGSERIAL PRIMARY KEY,
    menu_id             TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE CASCADE,
    nama                TEXT NOT NULL,
    sumber              TEXT NOT NULL DEFAULT '',
    potensi_alergen     TEXT NOT NULL DEFAULT '',
    is_critical_allergen BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order          INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_menu_ingredients_menu_id ON menu_ingredients (menu_id);

ALTER TABLE menu_ingredients ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_menu_ingredients" ON menu_ingredients;
CREATE POLICY "deny_public_menu_ingredients"
    ON menu_ingredients FOR ALL TO anon, authenticated USING (false);

-- ── 5. customers ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    customer_id             TEXT PRIMARY KEY DEFAULT 'cust_' || gen_random_uuid()::TEXT,
    username                TEXT NOT NULL UNIQUE,
    display_name            TEXT NOT NULL DEFAULT '',
    phone                   TEXT NOT NULL DEFAULT '',
    role                    TEXT NOT NULL DEFAULT 'customer'
                            CHECK (role IN ('customer','kitchen','admin')),
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','inactive','banned')),
    password_hash           TEXT,
    telegram_chat_id        BIGINT UNIQUE,
    telegram_verified       BOOLEAN NOT NULL DEFAULT FALSE,
    telegram_username       TEXT NOT NULL DEFAULT '',
    telegram_link_code      TEXT,
    telegram_link_code_expires_at TIMESTAMPTZ,
    telegram_linked_at      TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_username         ON customers (username);
CREATE INDEX IF NOT EXISTS idx_customers_telegram_chat_id ON customers (telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_customers_role             ON customers (role);
CREATE INDEX IF NOT EXISTS idx_customers_status           ON customers (status);
CREATE INDEX IF NOT EXISTS idx_customers_link_code        ON customers (telegram_link_code)
    WHERE telegram_link_code IS NOT NULL;

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_customers" ON customers;
CREATE POLICY "deny_public_customers"
    ON customers FOR ALL TO anon, authenticated USING (false);

-- ── 6. dietary_passports ───────────────────────────────────────────────────
-- Satu baris per customer; data terstruktur disimpan sebagai JSONB.
CREATE TABLE IF NOT EXISTS dietary_passports (
    customer_id         TEXT PRIMARY KEY REFERENCES customers(customer_id) ON DELETE CASCADE,
    allergies           JSONB NOT NULL DEFAULT '[]',
    intolerances        JSONB NOT NULL DEFAULT '[]',
    medical             JSONB NOT NULL DEFAULT '[]',
    preferences         JSONB NOT NULL DEFAULT '[]',
    avoided_ingredients TEXT[] NOT NULL DEFAULT '{}',
    avoided_times       TEXT[] NOT NULL DEFAULT '{}',
    medical_notes       TEXT NOT NULL DEFAULT '',
    safety_notes        TEXT NOT NULL DEFAULT '',
    emergency_notes     TEXT NOT NULL DEFAULT '',
    emergency_contact   JSONB NOT NULL DEFAULT '{}',
    -- kolom legacy — fallback baca dari profil Telegram lama
    legacy_dietary_profile TEXT NOT NULL DEFAULT '',
    structured          BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE dietary_passports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_dietary_passports" ON dietary_passports;
CREATE POLICY "deny_public_dietary_passports"
    ON dietary_passports FOR ALL TO anon, authenticated USING (false);

-- ── 7. orders ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            TEXT NOT NULL UNIQUE,        -- "ORD-20261001-ABC123"
    customer_id         TEXT REFERENCES customers(customer_id),
    customer_name       TEXT NOT NULL DEFAULT '—',
    chat_id             BIGINT,
    package_code        TEXT NOT NULL DEFAULT '' REFERENCES packages(code),
    subscription_type   TEXT NOT NULL DEFAULT '',    -- label paket saat pesan
    selected_allergens  TEXT[] NOT NULL DEFAULT '{}',
    dietary_profile     TEXT NOT NULL DEFAULT 'Tidak ada',
    kitchen_notes       TEXT NOT NULL DEFAULT '',
    customer_note       TEXT NOT NULL DEFAULT '',
    delivery_address    TEXT NOT NULL DEFAULT '',
    avoided_times       TEXT[] NOT NULL DEFAULT '{}',
    meal_count          INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','PREPARING','READY','COMPLETED','CANCELLED')),
    invoice_number      TEXT NOT NULL DEFAULT '',
    subtotal            INTEGER NOT NULL DEFAULT 0,
    discount            INTEGER NOT NULL DEFAULT 0,
    total               INTEGER NOT NULL DEFAULT 0,
    payment_status      TEXT NOT NULL DEFAULT 'UNPAID'
                        CHECK (payment_status IN ('UNPAID','PENDING','PAID','REFUNDED')),
    payment_reference   TEXT NOT NULL DEFAULT '',
    schema_version      TEXT NOT NULL DEFAULT 'v3',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_order_id     ON orders (order_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id  ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_chat_id      ON orders (chat_id);
CREATE INDEX IF NOT EXISTS idx_orders_status       ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at   ON orders (created_at);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_orders" ON orders;
CREATE POLICY "deny_public_orders"
    ON orders FOR ALL TO anon, authenticated USING (false);

-- ── 8. order_items (schedule_days + menu_selections dipecah jadi baris) ────
CREATE TABLE IF NOT EXISTS order_items (
    id          BIGSERIAL PRIMARY KEY,
    order_id    TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    hari        TEXT NOT NULL
                CHECK (hari IN ('Senin','Selasa','Rabu','Kamis','Jumat','Sabtu')),
    menu_id     TEXT REFERENCES menus(menu_id),  -- NULL = pilihan otomatis (primary)
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_hari     ON order_items (hari);

ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_order_items" ON order_items;
CREATE POLICY "deny_public_order_items"
    ON order_items FOR ALL TO anon, authenticated USING (false);

-- ── 9. order_status_events (timeline audit) ────────────────────────────────
CREATE TABLE IF NOT EXISTS order_status_events (
    id          BIGSERIAL PRIMARY KEY,
    order_id    TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    status      TEXT NOT NULL,
    actor       TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_order_status_events_order_id ON order_status_events (order_id);

ALTER TABLE order_status_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_order_status_events" ON order_status_events;
CREATE POLICY "deny_public_order_status_events"
    ON order_status_events FOR ALL TO anon, authenticated USING (false);

-- ── 10. customer_feedback ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_feedback (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id TEXT REFERENCES customers(customer_id),
    order_id    TEXT REFERENCES orders(order_id),
    rating      SMALLINT CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_feedback_customer_id ON customer_feedback (customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_feedback_order_id    ON customer_feedback (order_id);

ALTER TABLE customer_feedback ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_customer_feedback" ON customer_feedback;
CREATE POLICY "deny_public_customer_feedback"
    ON customer_feedback FOR ALL TO anon, authenticated USING (false);

-- ── 11. audit_log (disiapkan, diisi Fase berikutnya) ──────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    TEXT,
    action      TEXT NOT NULL,
    table_name  TEXT NOT NULL DEFAULT '',
    record_id   TEXT NOT NULL DEFAULT '',
    before_val  JSONB,
    after_val   JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor_id   ON audit_log (actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_table_name ON audit_log (table_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_audit_log" ON audit_log;
CREATE POLICY "deny_public_audit_log"
    ON audit_log FOR ALL TO anon, authenticated USING (false);

-- ── updated_at otomatis ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'packages','allergens','menus','customers','orders'
    ] LOOP
        EXECUTE format(
            'CREATE OR REPLACE TRIGGER trg_%I_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
            t, t
        );
    END LOOP;
END;
$$;
