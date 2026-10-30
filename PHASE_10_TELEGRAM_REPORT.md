# Phase 10 — Tiga Telegram Bot dan omnichannel bridge

Status: **LOCAL IMPLEMENTED — live bot tokens/provider worker belum dikonfigurasi.**

## Yang sekarang tersedia

- `telegram_bot.py` adalah Customer Bot dan memakai
  `TELEGRAM_CUSTOMER_BOT_TOKEN` (fallback nama legacy hanya untuk kompatibilitas).
- `telegram_admin_bot.py` memakai token serta allowlist Admin sendiri.
- `telegram_supplier_bot.py` memakai token Supplier sendiri dan setiap request
  di-resolve melalui `supplier_accounts` dari chat Telegram.
- Ketiga bot hanya memanggil FastAPI. Tidak ada import `astrapy` atau koneksi
  database langsung pada proses bot.
- Admin Bot memiliki status Supabase/migration/Langflow, stok kritis, forecast,
  batch produksi, daftar draft PO, approve/reject/send PO, invoice supplier,
  dan queue alert stok harian. Saat proses Admin Bot online, daemon internal
  menjalankan queue sekali per hari WIB pada `ADMIN_STOCK_ALERT_HOUR_WIB`.
- Supplier Bot memiliki daftar/detail PO, terima/tolak PO, pengajuan perubahan,
  goods receipt, upload invoice berbasis data terstruktur, dan status tagihan.

## Guard yang dipertahankan

- Admin action memerlukan `DOVAGENOME_INTERNAL_TOKEN`, chat ID yang ada di
  `TELEGRAM_ADMIN_CHAT_IDS`, serta `TELEGRAM_ADMIN_CUSTOMER_ID` untuk audit.
- Supplier action memerlukan chat yang tertaut ke customer ber-role supplier dan
  supplier account aktif; query PO selalu dibatasi `supplier_id` tenant tersebut.
- Approve/reject/send, receipt, invoice, dan alert memakai service layer yang
  sama dengan web admin/supplier. Bot tidak dapat melewati safety, idempotency,
  atau state machine.
- Alert stok memakai key `stock-alert:<tanggal>:<chat_id>` dan hanya masuk
  `notification_outbox` berstatus `PENDING`; worker/provider pengiriman belum
  diklaim aktif.

## Verifikasi

- OpenAPI live memuat semua route bridge Admin/Supplier.
- `python -m compileall -q backend/app backend/tests telegram_bot.py telegram_admin_bot.py telegram_supplier_bot.py` — PASS.
- `python -m pytest -q` — **217 passed** setelah test alert idempotency dan
  planner batch idempotency.
- `/api/health` live — Supabase terhubung, `database_source=supabase_postgres`,
  Astra `OFFLINE_LEGACY`.

## Gate eksternal

Migration outbox idempotency, goods receipt, billing, dan delivery masih
`core_verified_phase_extensions_pending` di target live. Token bot, linking
akun supplier/admin, webhook/worker Telegram, dan provider delivery harus diisi
serta diuji di lingkungan yang dituju; tidak ada token yang ditambahkan ke repo.
