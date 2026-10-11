-- ============================================================
-- DovaGenome — nomor telepon sebagai pengenal unik pelanggan
-- Jalankan setelah 001_schema.sql:
--   psql "$DATABASE_URL" -f supabase/migrations/002_customer_phone_unique.sql
-- Idempoten: pakai CREATE UNIQUE INDEX IF NOT EXISTS.
--
-- Partial index: hanya nomor non-kosong yang unik, sehingga akun staf
-- (phone = '') boleh banyak dan tidak saling bentrok.
-- ============================================================

-- CATATAN: bila sudah ada pelanggan dengan nomor sama dalam format berbeda,
-- samakan dulu (mis. UPDATE ... SET phone = '+62...') sebelum indeks dibuat.
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_phone_unique
    ON customers (phone)
    WHERE phone <> '';
