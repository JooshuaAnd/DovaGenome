# Phase 13 — Marketing / Win-back / Notifications

Tanggal implementasi lokal: 2026-10-27

## Status

**PARTIAL — workflow campaign sudah memiliki kontrak backend, state machine,
control group, dan callback delivery bertanda tangan; migration 009/011 belum
diterapkan ke database live dan tidak ada provider pengiriman yang dipanggil.**

## Implementasi

- `marketing_service.py` membuat draft win-back hanya dari baseline churn
  `BASELINE_ONLY` dengan `data_mode=live` dan `source=supabase_postgres`.
- Data stale (`freshness_status != FRESH` atau umur > 7 hari) menghasilkan
  `BLOCKED_STALE_DATA`; tidak ada audience atau pesan yang dipersist.
- Target hanya risk band `HIGH`/`MEDIUM`; `UNKNOWN` dan `LOW` tidak ditargetkan.
- Consent harus eksplisit melalui `customers.marketing_opt_in=true`.
- Kanal Telegram juga membutuhkan `telegram_verified` dan `telegram_chat_id`;
  WhatsApp membutuhkan nomor telepon.
- Migration `009_marketing_campaign_workflow.sql` menambah consent,
  `marketing_campaigns`, `marketing_campaign_recipients`, serta idempotency key
  pada `notification_outbox`.
- State machine backend: `DRAFT → APPROVED → QUEUED`; cancellation tersedia
  untuk `DRAFT`/`APPROVED`. Queue hanya membuat outbox berstatus `PENDING`.
- Control group ditentukan deterministik dari `customer_id` dan tanggal sumber;
  anggota control group dipersist sebagai `SKIPPED`, bukan dimasukkan ke outbox.
- `rate_limit_per_minute` dipersist sebagai kebijakan dispatch yang wajib dibaca
  worker; queue tidak mengaku sudah mengirim dan tidak menjalankan provider.
- `POST /admin/marketing/delivery-webhook` hanya menerima callback `SENT` atau
  `FAILED` yang HMAC-signed, mengubah outbox secara idempotent, dan menyimpan
  provider event/message id serta alasan gagal.
- Endpoint `/admin/marketing/campaigns/*` membutuhkan role admin.
- Pesan manual lama `/admin/notifications/send` sekarang juga hanya queue
  `PENDING`, bukan mengklaim `SENT`; provider worker belum ada.

## Acceptance tests lokal

- `backend/tests/test_marketing_service.py`: consent, channel verification,
  stale gate, non-live gate, control group deterministik, HMAC callback, no
  eligible audience, dan input validation.
- Targeted run: **9 passed**, 1 warning cache pytest Windows.
- Full backend suite terbaru setelah hardening forecast/Langflow dan Phase 13:
  **180 passed**, 1 warning cache pytest Windows.
- `python -m compileall -q backend/app backend/tests`: berhasil.
- Frontend service contract menambahkan list/create/approve/queue/cancel campaign;
  UI campaign penuh belum dibuat.

## Live boundary

- Migration 009 dan migration 011 **belum diverifikasi/diterapkan** pada
  Supabase live.
- Live churn terakhir yang tersedia berumur 15 hari (`STALE_DATA`), sehingga
  campaign win-back live saat ini harus ditahan.
- Tidak ada provider WhatsApp/Telegram yang dipanggil oleh queue; status
  `QUEUED`/`PENDING` bukan bukti pesan terkirim.
- Worker provider, enforcement rate limit di sisi dispatcher, dan UI campaign
  admin penuh masih menjadi gate berikutnya. Callback delivery sudah tersedia
  sebagai kontrak backend, tetapi belum dapat dibuktikan tanpa provider.
