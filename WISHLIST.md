# DovaGenome Wishlist

Daftar pekerjaan lanjutan yang tidak boleh dianggap selesai hanya karena data
demo atau transaksi sintetis berhasil dibuat.

## P0 — Buka jalur transaksi live yang sah

- [x] Ganti tombol simulasi di `frontend/src/pages/OrderPage.tsx` dengan alur
  `ordersService.create` memakai payload server-side.
- [x] Tambahkan client untuk `POST /api/payments/orders/{order_id}/intent`.
- [ ] Hubungkan provider pembayaran sandbox/nyata dan webhook bertanda tangan;
  jangan menandai order `PAID` dari browser.
- [ ] Pastikan order baru hanya dibuat jika recipe/menu lolos
  `ELIGIBLE`/verification gate; jangan melewati Allergy Guard untuk kebutuhan
  demo.
- [ ] Jalankan satu transaksi paid yang benar-benar dibuat melalui alur di atas,
  lalu ulangi forecast live dan snapshot freshness gate.

Catatan dependency live: recipe existing masih `PENDING_VERIFICATION`, sehingga
`POST /orders` seharusnya menolak order baru melalui safety gate. Jangan
menyiasatinya dengan insert SQL atau mengganti status safety secara manual.

## P0 — Freshness dan provenance forecast

- [x] Tambahkan indikator `latest_paid_date`, jumlah order paid, dan umur data ke
  dashboard admin.
- [ ] Pertahankan `STALE_DATA` sebagai status operasional; jangan menurunkan
  threshold hanya untuk membuat snapshot terlihat berhasil.
- [x] Implementasikan snapshot write-gate: hanya setelah status `OK`, freshness
  valid, dan provenance `live` terbukti. Eksekusi live masih menunggu transaksi
  paid baru karena data saat ini `STALE_DATA`.

## P1 — Dependency analytics berikutnya

- [ ] Selesaikan verifikasi recipe/BOM sebelum menghitung forecast bahan baku,
  safety stock, ROP, atau ROQ.
- [x] Tambahkan kontrak `inventory-replenishment` fail-closed; status live tetap
  `REQUIRES_VERIFICATION` bila BOM atau forecast belum memenuhi gate.
- [x] Tambahkan evaluator backtest stockout/fill-rate/excess-stock yang strict
  terhadap histori policy eksplisit; evidence live tetap menunggu histori
  SS/ROP harian yang belum ada.
- [x] Buat churn baseline dengan reason codes dan provenance serta backtest
  label-observasi dengan temporal split dan metrik baseline.
- [ ] Latih/evaluasi supervised churn model hanya setelah label, horizon,
  coverage, dan time-split data memenuhi kontrak; baseline tidak boleh disebut
  probabilitas.
- [x] Selaraskan RFM endpoint dan tambahkan evidence quantile, freshness,
  snapshot idempotent, serta segment movement; write live tetap menunggu data
  fresh.
- [x] Hapus/ubah endpoint analytics legacy demand dan supply-chain yang memiliki
  fallback demo; sekarang fail-closed atau unavailable sampai kontrak live siap.
- [x] Jadikan `AI_MODE=required_langflow` default; fallback RAG hanya aktif pada
  `allow_explicit_fallback` dan selalu diberi label degraded/source.
- [ ] Pulihkan quota/provider Langflow lalu ulangi smoke run sampai flow/model
  stabil, bukan hanya berhasil satu trace.
- [x] Tambahkan supplier sourcing score transparan berbasis harga, lead time,
  dan rating; hasil live tetap diblokir bila inventory/BOM/forecast belum siap.
- [x] Tambahkan request key/idempotency, approval admin, audit event, dan
  persist draft `purchase_orders`/`po_items`; jangan membuat PO dari preview
  sourcing. Migration/live verification dan provider delivery masih terbuka.
- [x] Tambahkan inbox approval PO di Telegram untuk chat admin yang di-allowlist;
  tombol `Approve` dan `Kirim ke supplier` tetap dipisah, sedangkan `Minta edit`
  mempertahankan status `DRAFT`.
- [x] Tambahkan campaign state `DRAFT → APPROVED → QUEUED`, consent eksplisit,
  server-side eligibility, dan idempotent notification outbox; queue tetap
  `PENDING` sampai provider worker tersedia.
- [x] Tambahkan kontrak control group deterministik, policy rate-limit per menit,
  callback delivery HMAC, dan audit status outbox; provider worker serta
  enforcement rate-limit runtime masih terbuka.

## Current evidence

- Migration `008_order_item_quantity_contract.sql` sudah diterapkan ke live.
- Forecast v2 live berhasil menghitung 18/18 series dan 1.054 holdout points setelah time boundary per-series.
- Data paid/non-cancelled terakhir adalah 2026-10-12; status forecast
  `STALE_DATA`, sehingga snapshot operasional ditolak.
- Web checkout sudah membuat order dan payment intent server-side, tetapi
  provider QRIS/VA dan signed webhook sandbox/nyata belum terhubung sehingga
  belum menghasilkan transaksi `PAID` live baru.
- Semua recipe live yang diperiksa masih `PENDING_VERIFICATION`; verifikasi
  recipe adalah prasyarat sebelum transaksi customer yang sah dapat dibuat.
- Churn baseline live sudah tersedia, tetapi statusnya `BASELINE_ONLY` dan
  `STALE_DATA`; belum boleh dipresentasikan sebagai model churn tervalidasi.
- Phase 11 live report sudah diuji: 18 menu forecast, 0 BOM verified, 6 item
  inventory, 8 mapping supplier; output SS/ROP kosong dan ROQ/EOQ `UNAVAILABLE`.
- Phase 12 live smoke tetap `REQUIRES_VERIFICATION`, `items=[]`, dan
  `draft_po=BLOCKED`; tidak ada PO yang dibuat.
- Langflow FastAPI context HTTP 200, tetapi provider `gemma-4-31b-it` terkena
  Google `429 RESOURCE_EXHAUSTED` karena quota input-token free tier. Pulihkan
  quota/provider sebelum mengklaim Chef BOB live.
- Phase 13 campaign workflow dan delivery-control contract tersedia lokal,
  tetapi migration 009/011 belum live dan churn stale 15 hari membuat draft
  win-back live tetap ditahan.

## P1 — Product experience & omnichannel operations

- [x] Customer web memakai service-week live sebagai sumber tanggal menu; kartu
  tidak lagi menampilkan rating/kalori/harga contoh sebagai fakta operasional.
- [x] Chef BOB memiliki quick actions web untuk menu, Dietary Passport, dan
  pesanan, serta menampilkan mode/model response secara eksplisit.
- [x] Telegram bot memiliki jalur approval procurement dengan allowlist chat,
  internal token, audit actor admin, dan delivery queue terpisah.
- [ ] Lengkapi metadata menu terverifikasi (harga, BOM gram, nutrisi, tags) di
  schema Supabase dan endpoint catalog; UI hanya akan menampilkan field yang
  benar-benar berasal dari sumber live.
- [ ] Tambahkan form edit PO Telegram percakapan atau deep-link dashboard;
  saat ini tombol `Minta edit` mencatat permintaan dan mengarahkan admin ke
  dashboard agar quantity/item dapat diubah secara terkontrol.
