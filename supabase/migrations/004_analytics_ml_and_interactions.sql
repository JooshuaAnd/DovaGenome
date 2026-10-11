-- ==============================================================================
-- 004: Analytics ML, 1000 Transactions Dataset, Likes, and Cart History
-- ==============================================================================

-- 1. Tambah kolom analitik finansial & rating pada orders jika belum ada
ALTER TABLE orders ADD COLUMN IF NOT EXISTS rating NUMERIC(4, 2) DEFAULT 7.0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(12, 2) DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cogs NUMERIC(12, 2) DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS gross_income NUMERIC(12, 2) DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 2;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS unit_price NUMERIC(12, 2) DEFAULT 42000;

-- 2. Tambah kolom harga & kuantitas pada order_items
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS unit_price NUMERIC(12, 2) DEFAULT 42000;
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1;
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS subtotal NUMERIC(12, 2) DEFAULT 42000;

-- 3. Tabel customer_likes (Like / Favorit hidangan)
CREATE TABLE IF NOT EXISTS customer_likes (
    id SERIAL PRIMARY KEY,
    customer_id TEXT NOT NULL,
    menu_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_customer_menu_like UNIQUE (customer_id, menu_id)
);

-- 4. Tabel cart_history (Riwayat keranjang & cart abandonment)
CREATE TABLE IF NOT EXISTS cart_history (
    id SERIAL PRIMARY KEY,
    customer_id TEXT NOT NULL,
    menu_id TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    action TEXT DEFAULT 'add', -- 'add', 'remove', 'checkout', 'abandon'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index performa query
CREATE INDEX IF NOT EXISTS idx_orders_customer_date ON orders(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_customer_likes_customer ON customer_likes(customer_id);
CREATE INDEX IF NOT EXISTS idx_cart_history_customer ON cart_history(customer_id, created_at DESC);
