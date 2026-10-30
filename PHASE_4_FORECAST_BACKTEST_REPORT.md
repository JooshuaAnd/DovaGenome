# Phase 4 — Demand Forecast & Backtest Report

Tanggal evidence: 2026-10-27

## Status

**IN PROGRESS — strict ML/backtest contract implemented and live backtest executed; operational snapshot remains held because the live data is stale.**

Phase 4 sekarang memiliki kontrak baru di:

- `backend/app/services/forecast_service.py`
- `backend/app/services/langflow_context_service.py`
- `GET /api/admin/analytics/forecast-backtest`
- `frontend/src/services/admin.ts`
- `frontend/src/pages/admin/AdminAnalyticsView.tsx`
- `langflow/Dova_Kitchen_Chef_BOB_LIVE.json`

Service baru tidak memakai fallback sintetis. Jika Supabase tidak tersedia,
endpoint menahan forecast dengan error `503`; jika histori pendek, series diberi
status `INSUFFICIENT_HISTORY` tanpa mengarang prediksi.

Semua report live, termasuk `STALE_DATA`, `LOW_VALIDATION`, `INSUFFICIENT_HISTORY`,
dan `NO_DATA`, sekarang wajib membawa dependency metadata paid-order yang
strukturnya valid. Jalur live juga membawa bukti kualitas item
`invalid_quantity_item_count`, `missing_unit_item_count`, dan
`missing_menu_id_item_count`; ketiganya wajib ada dan bernilai nol sebelum
report live diterima. Report `OK` juga wajib memiliki tanggal observasi terbaru dan
`source=supabase_postgres` dan `calculation_version=forecast_backtest_v2`.
Snapshot menolak report yang dibuat dari fixture, versi kalkulasi lain, atau
provenance yang tidak lengkap.
Sebelum write transaction, report harus berupa object dan setiap row snapshot
divalidasi untuk series key, unit, target date, method v2, quantity, interval
bound, dan interval level.

Regression hardening juga menolak observasi tanpa `series_key`, quantity/unit
yang kosong atau invalid, tanggal observasi yang hilang/invalid, row non-object,
tanggal masa depan, unit campuran, dan model lag yang belum memiliki histori minimum.
Alias `menu_id` dan `date` tidak digunakan lagi untuk observation live; query
harus mengirim `series_key` dan `target_date` canonical. Label boleh jatuh ke
`series_key` hanya sebagai metadata tampilan dan tidak pernah menjadi input
angka/model.
Query live tidak
lagi memberi default tersembunyi untuk `order_items.quantity` atau
`order_items.unit`; input shape invalid dipetakan ke jalur fail-closed.
Nilai quantity `NULL` atau `<= 0` juga dihitung invalid sesuai constraint
migration `008`.
Builder report generik juga tidak lagi default ke provenance live: tanpa
provenance eksplisit hasilnya berlabel `fixture`, dan `data_mode=live` tanpa
`source=supabase_postgres` ditolak.

## Metode yang dibandingkan

- `NAIVE_LAST`
- `MA7`
- `SEASONAL_NAIVE_7`
- `LINEAR_TREND`
- `RIDGE_LAG_7` — dependency-free supervised ridge model using lag-1, lag-7, and trailing-7-day features.

Backtest memakai rolling-origin one-step holdout. Metrik yang dihitung adalah
MAE, RMSE, WAPE, dan sMAPE. Forecast menyertakan interval tengah 80% berbasis
RMSE holdout. Metode terpilih ditentukan per series berdasarkan MAE, lalu RMSE
sebagai tie-breaker. Jika actual holdout seluruhnya nol, WAPE diberi status
`UNDEFINED_ZERO_ACTUAL` dan UI menampilkan `N/A`, bukan `0%`. sMAPE juga diberi
status `UNDEFINED_ZERO_DENOMINATOR` bila seluruh denominator nol; UI tidak
menyulapnya menjadi `0%`. Versi kalkulasi saat ini `forecast_backtest_v2`.

Series dengan status backtest `LOW_VALIDATION` tidak menghasilkan forecast
operasional, tidak dihitung sebagai eligible, dan membuat report global
`LOW_VALIDATION` (kecuali freshness lebih dulu berstatus `STALE_DATA`).
Histori juga dibatasi sampai observasi terakhir masing-masing series; series
yang lebih tua tidak dipadding dengan nol sampai tanggal series lain yang lebih
baru, dan horizon forecast dimulai dari tanggal observasi series itu sendiri.
Jika ada series `INSUFFICIENT_HISTORY`, report global juga ditahan dan snapshot
tidak boleh menyimpan hanya subset series yang kebetulan cukup histori.

## Live dependency evidence

Read-only introspection dan backtest live pada 2026-10-27 membuktikan:

| Field | Nilai |
|---|---:|
| koneksi Supabase | `True` |
| migration tabel utama | `True` |
| `order_items.quantity` | ada, `integer DEFAULT 1` |
| `order_items.unit` | ada, `text DEFAULT 'portion'` setelah migration 008 |
| strict forecast v2 | `STALE_DATA` |
| jumlah series / eligible | `18 / 18` |
| series stale | `18 / 18` |
| observasi terakhir | `2026-10-12` |
| umur data | `15 hari` |
| rolling-origin holdout | `1.054 points` |
| invalid quantity items | `0` |
| missing/blank unit items | `0` |
| live snapshot | **ditolak oleh freshness write-gate** |

Migration `008_order_item_quantity_contract.sql` diterapkan pada 14:06 WIB.
Backtest v2 dijalankan pada 14:07 WIB dengan `data_mode=live` dan
`source=supabase_postgres`. Service tetap fail-closed: hasil backtest boleh
diaudit, tetapi forecast stale tidak boleh dipersistenkan sebagai forecast
operasional.

Audit freshness read-only pada 14:08 WIB menunjukkan `latest_paid_date` dan
`latest_non_cancelled_date` sama-sama `2026-10-12`; terdapat 844 order paid.
Artinya status stale berasal dari tidak adanya order paid/non-cancelled yang
lebih baru, bukan dari kegagalan query atau migration.

Report v2 sekarang membawa dependency evidence terstruktur: `paid_order_count`,
`paid_order_item_count`, `invalid_quantity_item_count`,
`missing_unit_item_count`, `missing_menu_id_item_count`, `latest_paid_date`,
dan `latest_non_cancelled_date`.
Query metadata ini wajib berhasil; count/date tidak diisi dengan default ketika
dependency gagal. Count harus integer non-negatif, quality count harus nol,
tanggal harus ISO atau null hanya ketika report bukan `OK`/tidak memiliki
observasi. Panel admin memvalidasi quality gate tersebut bersama paid orders,
paid items, dan latest paid date.

### Live recheck setelah metadata contract

Read-only recheck pada 2026-10-27 16:14 WIB memakai window forecast 90 hari:

| Field | Nilai |
|---|---:|
| status | `STALE_DATA` |
| series / eligible / stale | `18 / 18 / 18` |
| latest observation | `2026-10-12` |
| latest paid / non-cancelled | `2026-10-12 / 2026-10-12` |
| paid orders dalam window | `418` |
| paid order-items dalam window | `817` |
| invalid quantity / missing unit | `0 / 0` |
| umur data | `15 hari` |

Angka 418/817 adalah dependency evidence untuk window forecast 90 hari; angka
context Langflow 844/1.682 pada report lain adalah total context dan tidak
digunakan sebagai metrik forecast window.

Recheck read-only terbaru 2026-10-27 17:02 WIB mengonfirmasi FastAPI health
HTTP 200, context `_data_mode=live`, source
`supabase_postgres_via_fastapi`, 18 menu, 63 customer, 844 order context,
1.682 paid order-items context, 6 stok, dan 8 supplier. Forecast 7d/30d tetap
`STALE_DATA` dengan dependency `418/817`, quality quantity/unit/menu-id `0/0/0`, dan latest date
`2026-10-12`.

Verifier reproducible `backend/scripts/verify_forecast_live.py` dijalankan
read-only pada runtime yang sama dan menghasilkan `status=PASS` untuk context
FastAPI serta graph Langflow aktif. Verifier v2 memeriksa mode/source, enam
count operasional, dependency forecast 7d/30d termasuk quality count nol, dan
graph 15/12 dengan node Demand Forecast strict v2/stale gate. Setelah audit
menemukan node transformasi lain masih membuka fallback, export LIVE dan graph
aktif disinkronkan ulang HTTP 200; seluruh 7 node yang memiliki input
`manual_json` sekarang menolaknya dan tidak lagi melakukan `state.update` dari
JSON manual. Verifier sengaja tidak melakukan model/provider smoke run
(`model_smoke=NOT_ATTEMPTED`) agar tidak mengonsumsi quota atau membuat
perubahan eksternal.

Audit kedua menemukan default data pada transformasi CRM/RFM, inventory, dan
supplier. Export LIVE kemudian di-hardening fail-closed: field order wajib,
stock yang hilang tidak dianggap nol, kapasitas/MOQ/lead supplier wajib ada,
dan draft marketing tanpa profile lengkap berstatus `DRAFT_BLOCKED`. Verifier
v2 sekarang memindai pola fallback tersebut pada graph server; hasil terakhir
`hidden_fallback_patterns=[]` setelah PATCH HTTP 200.

Audit context/state lanjutan juga menutup fallback di luar node forecast:
loader FastAPI menolak menu tanpa ingredient/allergen mapping, stock invalid,
supplier tanpa field harga/MOQ/lead-time, dan customer query tidak lagi memakai
LIMIT tersembunyi. Transform RFM/forecast/inventory/supplier/dietary/marketing/
Summary di graph aktif menolak state, identity, count, unit, dan warning list
yang hilang; tidak ada nilai pengganti untuk membuat output tampak lengkap.

### Metrik live rolling-origin

| Metode | MAE | RMSE | WAPE | sMAPE | Holdout |
|---|---:|---:|---:|---:|---:|
| `NAIVE_LAST` | 0.7600 | 1.0790 | 126.1417% | 150.7623% | 1,054 |
| `MA7` | 0.6597 | 0.8172 | 109.4938% | 142.4935% | 1,054 |
| `SEASONAL_NAIVE_7` | 0.7495 | 1.0794 | 124.4094% | 148.4408% | 1,054 |
| `LINEAR_TREND` | **0.6514** | 0.8115 | **108.1260%** | 144.6455% | 1,054 |
| `RIDGE_LAG_7` | 0.6583 | **0.8113** | 109.2667% | **139.8483%** | 1,054 |

Model agregat dengan MAE terbaik adalah `LINEAR_TREND`, sedangkan RMSE terbaik
adalah `RIDGE_LAG_7`. Pemilihan per series tetap dilakukan oleh service; distribusinya
adalah `LINEAR_TREND=6`, `RIDGE_LAG_7=7`, `MA7=4`, dan
`SEASONAL_NAIVE_7=1`.

Query v2 memakai `quantity` dan `unit` eksplisit, hanya order `PAID`, dan tidak
memakai fallback sintetis. Evidence 18 series/1.054 holdout di atas adalah
hasil v2; angka pre-v2 yang menghitung baris order item tidak dipakai sebagai
metrik final.

Service juga menolak series yang mencampur unit berbeda; unit tidak pernah
digabung diam-diam ke satu angka demand.

Freshness sekarang dievaluasi per-series. Satu series stale sudah cukup untuk
menahan seluruh report pada `STALE_DATA`, walaupun series lain memiliki observasi
yang lebih baru.

Panel admin sekarang menampilkan source, calculation version, freshness/write-gate,
dan menyediakan tombol snapshot yang hanya aktif bila report live berstatus `OK`.
Saat `STALE_DATA`, tombol disabled dan backend tetap menolak persistence.
UI juga menolak payload forecast yang bukan `live` dari `supabase_postgres` dengan
versi `forecast_backtest_v2`, dependency metadata yang tidak lengkap, atau baris
forecast pertama yang invalid; UI menghapus payload lama saat refresh gagal sehingga
refresh error tidak dapat meninggalkan forecast stale di state halaman.
Context Langflow juga fail-closed bila histori order-item melewati batas payload
2.000 baris; query memakai satu baris sentinel sehingga truncation tidak diam-diam
mengubah CRM/RFM menjadi subset data. Identity order/customer, menu, date,
quantity/unit, meal count, dan total juga wajib ada; field kosong tidak diubah
menjadi placeholder atau nol.

Node Demand Forecast pada export Langflow LIVE juga sudah fail-closed: hanya menerima
`forecast_backtest_v2` dari FastAPI live, menolak `manual_json`, dan menolak quantity,
unit, series, atau provenance yang hilang/tidak valid.

Sinkronisasi read-only/patch ke server Langflow aktif `daf5e1ab-3bb3-4051-a9d0-270fffff517d`
berhasil HTTP 200. GET verifikasi sesudah patch menunjukkan graph tetap 15/12,
DovaDataSource dan seluruh state transform memiliki hash fail-closed, serta
`code_hash=dova-live-state-fail-closed-forecast-ff75879defef` pada strict forecast node.

## Konvergensi Langflow

Context read-only FastAPI yang dipakai Langflow sekarang memakai kontrak yang
sama dengan backend forecast: hanya order `PAID` non-`CANCELLED`, quantity/unit
eksplisit, dan report `forecast_backtest_v2` untuk horizon 7 hari serta 30 hari.
Smoke context 2026-10-27 menghasilkan 63 customer, 844 order paid, 1.682
paid order-items, 18 menu, `bom_menus=0`, 6 item stok, dan 8 supplier.
Kedua report Langflow berstatus `STALE_DATA`; tidak ada forecast stale yang
diteruskan menjadi inventory demand operasional.

File LIVE sudah diperbarui agar node `Dova Forecast` memakai report backend ini,
bukan algoritme forecast kedua. Graph aktif sudah diperbarui menjadi 15 node/12
edge tanpa vector node yang belum terkonfigurasi. Direct run Langflow tertahan
oleh provider quota: trace terakhir menunjukkan Google `429
RESOURCE_EXHAUSTED` pada `gemma-4-31b-it` karena batas input-token free tier
16.000 token/menit. Vector retrieval belum dikonfigurasi.
Smoke tambahan 16:22 WIB dengan `x-api-key` dan prompt minimal tidak selesai
dalam 75 detik; runtime Langflow tetap belum stabil dan tidak menjadi bukti
forecast live berhasil dieksekusi.
Sesudah context internal dipadatkan, trace `ddbdeedd-c75a-4963-aa35-319b7690abd8`
berstatus `ok` dan mengembalikan `READY` dengan 7.480 input token; latency
121,8 detik tetap melewati timeout client. Context mempertahankan KPI customer
count 63 dan forecast v2 live, tetapi tidak mengirim matriks profil dietary
individual ke graph aggregate. Metadata dependency `paid_order_count`,
`paid_order_item_count`, `invalid_quantity_item_count`,
`missing_unit_item_count`, `missing_menu_id_item_count`, `latest_paid_date`, dan
`latest_non_cancelled_date`
sekarang juga dibawa terstruktur dan ditampilkan sebagai warning evidence.
Read-only recheck context 16:38 WIB mengonfirmasi mode `live`, source
`supabase_postgres_via_fastapi`, customer count 63, `customers_sent=0`, dan
dependency 7d/30d masing-masing `418` paid orders, `817` paid order-items,
latest dates `2026-10-12`; forecast tetap `STALE_DATA`.

## Batasan yang masih terbuka

- Data live terakhir masih berumur 15 hari, sehingga status `STALE_DATA` dan
  snapshot ditolak. Data order paid yang lebih baru diperlukan sebelum forecast
  dipakai secara operasional; freshness threshold tidak boleh diturunkan hanya
  untuk melewati write-gate.
- Forecast bahan baku belum boleh disebut BOM/MRP final karena recipe existing
  masih `PENDING_VERIFICATION`.
- Endpoint strict v2 menjadi satu-satunya jalur forecast demand aktif. Endpoint
  `supply-chain-ml` dan `demand-insights` legacy dinonaktifkan dengan fail-closed
  response; route supplier `/supplier/demand-forecast` juga ditahan agar tidak
  memanggil facade sintetis; tab demand legacy tidak menampilkan payload demo.
- Tab forecast supplier juga fail-closed: response `410`, error, atau payload
  yang bukan `live`/`supabase_postgres`/`forecast_backtest_v2` tidak lagi
  menampilkan KPI atau material demo.
- `POST /api/admin/analytics/forecast-backtest/snapshot` hanya menulis bila
  report live berstatus `OK`; `STALE_DATA` atau dependency kurang ditolak.
- Test forecast terarah setelah quality-dependency, missing-menu, dan explicit-provenance gate: **44 passed**; full backend suite terbaru **190 passed**. Compile backend dan production build frontend berhasil.
- Test forecast service + verifier: **56 passed**; test Langflow live context/flow/service: **27 passed**. Verifier dapat diulang dengan `python backend/scripts/verify_forecast_live.py` tanpa write ke Supabase, snapshot, atau provider state. Smoke `--model-smoke` sekarang memberi status eksplisit; recheck aktif terbaru menghasilkan HTTP 500, sementara graph memilih Google Generative AI tanpa credential provider yang terbukti tersedia, sehingga provider smoke belum dapat dianggap sukses. Forecast tetap `STALE_DATA`; PASS verifier hanya berarti kontrak dan provenance terverifikasi.
  pytest Windows.

Recheck lanjutan setelah launcher live ditambahkan: active graph tetap 15/12,
forecast code hash menjadi `dova-live-state-fail-closed-forecast-ff75879defef`,
dan model smoke utama masih HTTP 500 tanpa marker provider. Instance Langflow
bersih berhenti pada konfigurasi `GOOGLE_API_KEY` yang belum tersedia. Kontrak
forecast tidak mengubah `STALE_DATA` menjadi `OK`.
