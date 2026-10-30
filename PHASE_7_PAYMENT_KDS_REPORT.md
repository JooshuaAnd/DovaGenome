# Phase 7 — Payment, webhook, dan paid-only KDS

Tanggal checkpoint: 2026-10-27

## Status

**IN PROGRESS — kontrak backend dan checkout client sudah tersambung secara fail-closed; provider nyata dan migration 007 belum diverifikasi live.**

## Yang sekarang ditegakkan oleh kode

- `POST /api/payments/orders/{order_id}/intent` memakai total order yang tersimpan di server, bukan nominal dari client.
- `idempotency_key` mencegah intent dibuat dua kali untuk request yang sama.
- `POST /api/payments/webhooks/{provider}` menolak signature kosong/salah dan memverifikasi HMAC-SHA256.
- Event webhook dicatat dengan `provider_event_id`; pengiriman ulang event diperlakukan sebagai duplicate.
- Nominal dan currency webhook harus sama dengan payment attempt.
- Event sukses mengubah order menjadi `PAID` dan membuat `kitchen_tickets` dalam transaksi database yang sama.
- `/api/kitchen/board` hanya membaca order dengan `payment_status = PAID`.
- Transisi `PENDING → PREPARING` ditolak jika order belum `PAID`.
- endpoint admin POS/KDS kini memerlukan staff auth; endpoint tidak lagi mengembalikan fixture demo saat database gagal.
- konfirmasi manual admin menggunakan payment attempt `manual` dan jalur ticket release yang sama.
- checkout customer memanggil `/api/orders` lalu `/api/payments/orders/{order_id}/intent`; UI memakai `package.price`/`PaymentIntent.amount` dari server dan tidak punya tombol simulasi sukses.

## Evidence lokal

- `cd backend; python -m pytest -q` — **180 passed**, 1 warning pytest cache Windows.
- `cd backend; python -m compileall -q app tests scripts` — berhasil.
- `cd frontend; npm.cmd run build` — berhasil; masih ada warning ukuran bundle >500 kB.

## Belum boleh diklaim selesai

- `supabase/migrations/007_payment_kitchen_workflow.sql` belum diaplikasikan pada target live dalam checkpoint ini.
- Provider payment nyata, secret webhook, callback signature, expiry job, dan retry provider belum diuji terhadap sandbox provider.
- Provider payment belum mengembalikan QRIS/VA runtime dan belum ada polling status; modal hanya menampilkan payment intent dan mengarahkan pelanggan ke daftar pesanan.
- Data recipe/BOM masih `PENDING_VERIFICATION`, jadi payment sukses belum berarti MRP/inventory sudah siap.
