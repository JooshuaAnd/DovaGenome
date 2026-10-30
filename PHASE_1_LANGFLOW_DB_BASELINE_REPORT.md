# Phase 1 — Langflow readiness dan Supabase baseline

Tanggal: 2026-10-30  
Status: **SELESAI SECARA LOKAL — checkpoint berikutnya menunggu approval**

## Hasil implementasi

- Supabase/PostgreSQL ditetapkan sebagai `database_source` tunggal: `supabase_postgres`.
- Health check sekarang memisahkan `supabase_connected` dari field kompatibilitas
  `astra_connected`. Astra tidak dipakai oleh API aktif dan selalu dilaporkan
  sebagai `OFFLINE_LEGACY`.
- Health check membaca status migration secara read-only sebagai `verified`,
  `missing_or_incomplete`, atau `offline`.
- Dashboard admin menggunakan `supabase_connected`, sehingga Supabase yang hidup
  tidak lagi tampil sebagai Astra atau sebagai database offline.
- Langflow memiliki state eksplisit `CONNECTED`, `DEGRADED`, `OFFLINE`,
  `MISCONFIGURED`, dan `MOCK`.
- `GET /api/health/langflow` hanya menguji reachability platform secara default.
  `GET /api/health/langflow?probe=true` menjalankan probe flow opt-in dan
  mengembalikan `trace_id`, `flow_id`, `latency_ms`, `reason_code`, serta
  `flow_execution_proven` tanpa mengembalikan credential atau output model.
- Response `POST /api/ai/consult` sekarang membawa trace metadata yang aman;
  fallback diberi label provider/state yang jelas dan tidak menjadi bukti flow
  Langflow live.

## Bukti runtime lokal

### Supabase

`GET http://localhost:8000/api/health` mengembalikan:

- `status=ok`
- `db_connected=true`
- `supabase_connected=true`
- `database_source=supabase_postgres`
- `migration_status=verified`
- `astra_connected=false`
- `astra_state=OFFLINE_LEGACY`

Counts ringkas yang terbaca: packages 3, allergens 8, menus 18, customers 66,
orders 884. Nilai ini adalah observasi runtime lokal saat audit, bukan angka
target bisnis.

### Langflow

- Probe platform default: HTTP 200, versi `1.12.3`, state `CONNECTED`, tetapi
  `flow_execution_proven=false` dengan reason `platform_reachable_flow_unprobed`.
- Probe flow opt-in: HTTP 200 dari endpoint health, tetapi flow provider
  mengembalikan HTTP 500; state `DEGRADED`, reason `flow_http_error`, sehingga
  eksekusi flow/model belum diklaim stabil.

Kesimpulan: jaringan ke Langflow hidup, tetapi model/provider atau graph masih
perlu diperbaiki sebelum readiness produksi dinyatakan `CONNECTED`.

## Verifikasi kode

- `python -m pytest -q` — **200 passed**, 1 warning cache pytest Windows.
- `python -m compileall -q backend/app backend/tests` — berhasil.
- `npm.cmd run build` di `frontend` — berhasil; tetap ada warning ukuran bundle
  JavaScript di atas 500 kB.

## Database recovery gate

Belum ada migration baru, perubahan data, migrasi Astra, backup produksi, atau
restore produksi yang dijalankan pada Phase 1. Backup terenkripsi dan drill
restore tetap menjadi gate operasional terpisah sebelum perubahan schema shared
atau production.

## Stop gate

Phase 1 berhenti di sini sesuai aturan checkpoint master prompt. Phase 2 yang
direncanakan berikutnya adalah import recipe/material master dari PDF, XLSX,
CSV, atau text sebagai draft private, lalu nutrition/BOM review admin. Belum
dikerjakan pada checkpoint ini.
