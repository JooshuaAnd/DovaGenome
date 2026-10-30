# Phase 10 — Churn Risk Baseline Report

Tanggal evidence: 2026-10-27

## Status

**IN PROGRESS — baseline rule-based live dan backtest label-observasi tersedia;
model supervised belum eligible karena belum ada kontrak training/validasi yang
disetujui.**

## Implementasi

- `backend/app/services/churn_service.py` menjadi source of truth baseline churn.
- Cohort hanya memakai order `PAID` dan `status <> 'CANCELLED'`.
- Cadence dihitung dari median interval antar-order per customer.
- Output memuat `risk_band`, `risk_index` non-probabilistik, reason codes,
  threshold, recommended action, freshness, source, dan calculation version.
- Status output selalu `BASELINE_ONLY`; `model_validated=false`.
- Data tidak cukup (<2 order paid) diberi `UNKNOWN`, bukan dipaksa masuk risk band.
- `/api/admin/analytics/churn-risk` membutuhkan role admin.
- UI admin menampilkan evidence baseline dan menahan angka bila data live belum tersedia.
- `build_churn_backtest()` menambahkan label observasi berbasis jendela 30 hari,
  cutoff historis, temporal train/test split, dan metrik precision/recall/F1/ROC-AUC.
- Endpoint admin `/analytics/churn-backtest` dan panel admin menampilkan hasil
  backtest sebagai historical evidence; `model_validated=false` dan
  `operational_eligibility=false` tetap dipertahankan.

## Live smoke evidence

| Field | Nilai |
|---|---:|
| status | `BASELINE_ONLY` |
| data mode | `live` |
| source | `supabase_postgres` |
| calculation version | `churn_rule_baseline_v1` |
| methodology | `rule_based_baseline` |
| model validated | `false` |
| customer dianalisis | `58` |
| UNKNOWN | `4` |
| MEDIUM | `32` |
| HIGH | `22` |
| order terbaru | `2026-10-12` |
| umur data | `15 hari` |
| freshness | `STALE_DATA` |

Smoke test hanya membaca agregat; tidak ada data yang ditulis.

## Test evidence

- Targeted churn/backtest/router tests: **11 passed**; full backend suite
  terbaru **180 passed**, 1 warning cache pytest Windows.
- `cd frontend; npm.cmd run build` — berhasil; masih ada warning bundle >500 kB.
- Test baru: `backend/tests/test_churn_service.py` mencakup klasifikasi low/
  medium/high/unknown, freshness, paid/non-cancelled query, dan no-fallback
  saat database offline. Backtest dan route tests menambah **11 targeted tests**
  pada verifikasi sesi ini.

## Batasan dan gate berikutnya

- `risk_index` bukan probabilitas dan baseline ini bukan model tervalidasi.
- Label observasi, horizon 30 hari, temporal split, dan metrik baseline sudah
  tersedia; ini belum menjadi supervised model dan tidak boleh diklaim demikian.
- Evidence live endpoint backtest belum diambil dari workspace karena koneksi
  langsung PostgreSQL diblokir oleh network sandbox; jalankan melalui backend
  FastAPI yang sudah memiliki akses database.
- Data paid terbaru stale 15 hari; hasil hanya historical signal sampai transaksi
  paid baru tersedia.
- Marketing action masih draft/review; service tidak mengirim pesan otomatis.
