# Phase 11 — BOM, Inventory, Safety Stock, ROP, dan ROQ

Tanggal evidence: 2026-10-27

## Keputusan implementasi

Phase 11 sekarang memiliki kontrak backend `inventory_service.py` yang fail-closed.
Service tidak mengambil angka dari fixture lama dan tidak memakai asumsi default
untuk lead time atau konsumsi bahan.

Endpoint baru:

```text
GET /api/admin/analytics/inventory-replenishment
```

Endpoint hanya mengembalikan report live dengan provenance
`supabase_postgres`. Bila readiness belum cukup, `items` kosong dan status
`REQUIRES_VERIFICATION`, `STALE_DATA`, atau `NO_DATA`; tidak ada angka SS/ROP
palsu.

## Kontrak readiness

Perhitungan numerik baru boleh berjalan bila seluruh syarat berikut terpenuhi:

1. Recipe version terbaru untuk menu yang memiliki forecast berstatus `VERIFIED`.
2. Component dan canonical ingredient berstatus `VERIFIED`.
3. Yield recipe dapat dipetakan ke `portion`.
4. Quantity/unit recipe dan stok dapat dikonversi ke unit massa yang sama.
5. Inventory memakai `ingredient_id` canonical dan memiliki current stock.
6. Supplier aktif memiliki lead time untuk setiap bahan hasil BOM.
7. Forecast paid/non-cancelled berstatus `OK` dan belum melewati freshness gate.

Nested BOM yang belum diexplode dan unit yang tidak dikenal masuk ke daftar
`unresolved_bom`; tidak digabung diam-diam.

## Formula yang diizinkan

Untuk setiap bahan, demand harian diexplode dari forecast menu melalui quantity
component per portion:

```text
Safety Stock = 1.65 × stddev(demand harian) × sqrt(lead time hari)
ROP          = mean(demand harian) × lead time hari + Safety Stock
Target       = mean(demand harian) × (lead time + horizon) + Safety Stock
Shortage     = max(0, Target - stok saat ini)
```

`Target` dan `Shortage` adalah target replenishment, bukan ROQ/EOQ. ROQ/EOQ
ditandai `UNAVAILABLE` sampai ordering cost, holding cost, dan pack-size
constraint tersedia. Sistem tidak membuat PO otomatis.

## Evidence live

Smoke read-only terhadap Supabase menghasilkan:

| Field | Nilai |
|---|---:|
| Published menu | 18 |
| Forecast menu | 18 |
| Latest recipe | 18 |
| BOM siap | 0 |
| Inventory item | 6 |
| Supplier mapping | 8 |
| Forecast status | `STALE_DATA` |
| Forecast age | 15 hari |
| Report status | `REQUIRES_VERIFICATION` |
| Output item SS/ROP | 0 |
| ROQ/EOQ | `UNAVAILABLE` |

Kesimpulan: jalur Phase 11 sudah tersedia dan aman untuk menahan keputusan yang
belum dapat diaudit. Data live belum memenuhi syarat untuk menghasilkan angka
SS/ROP operasional.

## Evaluator backtest stock policy

`inventory_service.build_inventory_backtest()` sekarang tersedia untuk
mengevaluasi histori ingredient-day yang eksplisit. Setiap baris wajib memuat
`unit`, `opening_stock`, `receipt_quantity`, `adjustment_quantity`, `actual_demand`,
`forecast_demand`, `reorder_point`, dan `target_stock`. Opening stock hari
berikutnya harus sama dengan closing stock terhitung; gap, field hilang,
unit campuran, histori pendek, atau demand nol tidak disulap menjadi angka.

Metrik yang dihasilkan adalah stockout days/rate, unfulfilled demand, weighted
fill rate, excess stock terhadap `target_stock`, dan forecast WAPE. Metrik
undefined diberi status eksplisit, bukan dipaksa menjadi nol.

Output diberi `data_mode=backtest`, `source=explicit_inventory_history`, dan
`operational=false`. Evaluator ini belum menjadi bukti live karena schema live
belum menyimpan histori policy SS/ROP harian yang lengkap; tidak ada write ke
Supabase atau PO yang dibuat.

## Validasi

- Validasi terbaru: `cd backend; python -m pytest -q` menghasilkan **180 passed**.
- Targeted inventory tests: `cd backend; python -m pytest -q backend/tests/test_inventory_service.py`
  menghasilkan **9 passed**.
- Baris validasi historis di bawah ini berasal dari sebelum perubahan lintas
  fase; tidak dipakai sebagai suite terbaru.

- `cd backend; python -m pytest -q` — **79 passed**, 1 warning cache pytest Windows.
- `cd backend; python -m compileall -q app tests` — berhasil.
- `cd frontend; npm.cmd run build` — berhasil; Vite masih memberi warning bundle
  lebih besar dari 500 kB.

File utama:

- `backend/app/services/inventory_service.py`
- `backend/app/api/routers/admin.py`
- `backend/tests/test_inventory_service.py`
- `frontend/src/services/admin.ts`
- `frontend/src/pages/admin/AdminAnalyticsView.tsx`
