# Phase 5 continuation — inventory lot & FEFO

Status: **implemented locally; migration 018 pending Supabase backup/restore gate**.

Pemakaian bahan kitchen sekarang dapat mencatat lot secara audit-able. Saat
seluruh tabel/kolom extension tersedia, service:

- mengunci lot `AVAILABLE` yang unitnya sama dengan kartu stok;
- memilih lot dengan expiry paling dekat terlebih dahulu (FEFO), lalu
  `received_at` sebagai tie-breaker;
- menurunkan `stock_lots.quantity_on_hand` dan saldo agregat dalam transaksi
  yang sama;
- membuat `inventory_lot_allocations` agar satu pemakaian yang melintasi dua
  lot tetap dapat direkonsiliasi;
- mengembalikan alokasi lot pada response kitchen dan menjaga idempotency.
- jalur manual production-batch weigh memakai allocator FEFO yang sama; jika
  operator mengirim `lot_id`, lot itu harus tersedia dan unitnya harus cocok.

Jika migration 018 belum diterapkan, endpoint tidak mengakses tabel lot dan
tetap menggunakan `inventory_stocks` + `inventory_movements` yang sudah ada.
Dengan demikian staged rollout Supabase tidak berubah menjadi klaim lot live.

Artefak:

- `supabase/migrations/018_inventory_fefo_allocations.sql`
- `backend/app/services/inventory_operations_service.py`
- `backend/app/repositories/supabase.py`
- `backend/app/schemas/internal.py`

Evidence lokal: `python -m pytest -q` — **222 passed**; compile backend dan
production build frontend juga passed.

Batas: stock count, waste reason, unit conversion lintas satuan, dan reservasi
per batch masih perlu data/master policy yang disetujui. Bluetooth tetap
ditunda sesuai keputusan pengguna.
