# Phase 9 — CRM/RFM Customer Analytics Report

Tanggal evidence: 2026-10-27

## Status

**IN PROGRESS — live quantile RFM, snapshot contract, dan segment movement sudah
diimplementasikan; eksekusi snapshot live masih ditahan oleh freshness data.**

## Implementasi

- `backend/app/services/rfm_service.py` menjadi source of truth RFM baru.
- Cohort hanya mengambil order `PAID` dan `status <> 'CANCELLED'`.
- Recency, Frequency, dan Monetary diberi skor quantile 1–5 berbasis cohort.
- Output memiliki `data_mode`, `source`, `calculation_version`, tanggal
  evidence, tanggal order terbaru, umur data, `freshness_status`, dan warnings.
- Tidak ada fallback customer sintetis atau default segment `Champions`.
- `/api/customers/rfm` hanya boleh meminta data customer yang sedang login.
- `/api/admin/analytics/rfm-crm` sekarang membutuhkan role admin.
- Nama legacy `calculate_crm_rfm_segments` mendelegasikan ke service strict.
- `persist_rfm_report()` menulis ke `rfm_snapshots` secara idempotent hanya jika
  report live berasal dari Supabase dan freshness maksimal 7 hari.
- `build_segment_movement()` membandingkan cohort saat ini dengan snapshot prior
  terbaru dan memberi status `CHANGED`, `UNCHANGED`, atau `NO_PREVIOUS`.
- Admin memiliki endpoint snapshot/movement dan tombol snapshot yang disabled
  saat RFM stale.

## Live smoke evidence

| Field | Nilai |
|---|---:|
| status | `OK` |
| data mode | `live` |
| source | `supabase_postgres` |
| calculation version | `rfm_quantile_v1` |
| customer dianalisis | `58` |
| order terbaru | `2026-10-12` |
| umur data | `15 hari` |
| freshness | `STALE_DATA` (threshold 7 hari) |
| Champions | `12` |
| Loyal Customers | `11` |
| Potential Loyalists | `5` |
| At Risk | `13` |
| Hibernating | `13` |
| New Customers | `4` |

Smoke test hanya membaca agregat; tidak ada data yang ditulis.

## Test evidence

- `cd backend; python -m pytest -q` — **123 passed**, 1 warning cache pytest
  Windows.
- Test baru di `backend/tests/test_rfm_service.py` dan
  `backend/tests/test_rfm_router.py` mencakup quantile scoring,
  paid/non-cancelled query, no-fallback saat database offline, freshness gate,
  idempotent snapshot provenance, movement, dan router status.
- `cd backend; python -m compileall -q app tests` — berhasil.
- `cd frontend; npm.cmd run build` — berhasil; masih ada warning bundle >500 kB.

## Batasan

- Snapshot dan movement sudah memiliki contract, tetapi snapshot live belum
  ditulis karena order paid terbaru stale 15 hari; route mengembalikan `409` dan
  UI menahan tombol.
- Migration `005_core_architecture.sql` sudah menyediakan tabel
  `rfm_snapshots`; belum ada bukti write live yang sukses karena gate freshness
  bekerja sesuai desain.
- Angka segment tetap live dan provenance-labelled, tetapi jangan dipakai
  sebagai klaim aktivitas terkini tanpa refresh data.
- Fungsi legacy internal pada `analytics_ml_service.py` masih disimpan untuk
  transitional reference, tetapi public wrapper dan caller aktif memakai
  `rfm_service` strict.
