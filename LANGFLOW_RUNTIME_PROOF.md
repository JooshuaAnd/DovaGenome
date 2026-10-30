# Langflow Runtime Proof

Tanggal: 2026-10-27 (recheck)

| Readiness | Status | Bukti |
|---|---|---|
| `APP_READY` | PASS | Backend dapat menginisialisasi `LangflowService` dan membentuk run URL tanpa membocorkan secret. |
| `LANGFLOW_REACHABLE` | PASS | `GET /api/v1/version` → HTTP 200, versi `1.12.3`. |
| `FLOW_EXECUTABLE` | PASS_ONCE / SLOW_NOT_STABLE | Graph aktif 15 node/12 edge selesai pada trace terbaru `ddbdeedd-c75a-4963-aa35-319b7690abd8`; total latency 121,8 detik, sehingga melewati timeout client. |
| `MODEL_REACHABLE` | PASS_ONCE / QUOTA_LIMITED | Trace terbaru memuat output `READY` dari `gemma-4-31b-it` dengan 7.480 input token; trace lain tetap menunjukkan Google `429 RESOURCE_EXHAUSTED` pada quota free tier 16.000 token/menit. |
| `VECTOR_RETRIEVAL_READY` | NOT CONFIGURED | LIVE graph sengaja tidak memuat node Supabase VectorStore/Embedding karena credential, tabel, dan RPC belum terverifikasi. RAG/vector belum siap. |
| `LIVE_DATA_READY` | PASS untuk endpoint dan PASS_ONCE untuk flow | Endpoint HTTP 200 bertanda `_data_mode=live`; trace `ddbdeedd-c75a-4963-aa35-319b7690abd8` menunjukkan node context live selesai di graph aktif. Reliabilitas provider belum terbukti. |
| `DETERMINISTIC_SAFETY_READY` | PASS di FastAPI | Allergy Guard dan order gate tetap dihitung backend; LLM tidak menjadi sumber keputusan. |

Catatan credential: `LANGFLOW_API_KEY` hanya mengautentikasi request ke server
Langflow. Node model aktif memilih Google Generative AI `gemma-4-31b-it`, jadi
provider membutuhkan credential dan quota Google tersendiri. Recheck active
flow HTTP 500 dan instance bersih yang gagal pada `GOOGLE_API_KEY` belum
memenuhi bukti `MODEL_REACHABLE` stabil.

## Respons fallback dan recheck provider

Smoke test historis sebelum AI mode diperketat, saat API key ditolak, menghasilkan:

- `degraded=true`
- `message=Supabase RAG Data Stream (http_403)`
- reply berasal dari fallback Supabase RAG

Sekarang `AI_MODE` default adalah `required_langflow`; fallback hanya boleh
berjalan bila operator memilih `allow_explicit_fallback`. Pada mode default,
UI menerima pesan unavailable/degraded dan tidak menganggap fallback sebagai
output flow Langflow live.

## Modul live FastAPI

Pada 2026-10-27 dibuat `langflow/Dova_Kitchen_Chef_BOB_LIVE.json` dan endpoint
read-only `GET /api/ai/internal/context`. Smoke test dengan database aktif:

- HTTP 200;
- `_data_mode=live`;
- `_source=supabase_postgres_via_fastapi`;
- konteks terisi 18 menu, 844 order paid, 1.682 paid order-items, 63 customer,
  6 item stok, dan 8 supplier.
- payload juga membawa `forecast_backtest.7d` dan `forecast_backtest.30d`,
  keduanya `STALE_DATA`, `data_mode=live`, source `supabase_postgres`, dan
  calculation version `forecast_backtest_v2`.
- Context internal mempertahankan `counts.customers=63` tetapi mengirim
  `customers=[]` dengan `customer_profile_context=omitted_internal_aggregate`;
  profil dietary individual tidak dikirim ke graph aggregate agar tidak membuat
  matriks customer×menu dan tidak membocorkan PII yang tidak diperlukan.

Flow LIVE membutuhkan `LANGFLOW_INTERNAL_TOKEN` di FastAPI dan
`DOVAGENOME_INTERNAL_TOKEN` dengan nilai sama di proses Langflow. Detail setup
ada di [LANGFLOW_LIVE_MODULE.md](LANGFLOW_LIVE_MODULE.md). Ini membuktikan
  jalur data live FastAPI-Supabase. Ini bukan bukti flow/model provider berhasil
  dijalankan.

Node Demand Forecast pada file LIVE sekarang hanya memproses report
`forecast_backtest_v2` dengan `data_mode=live` dan source Supabase via FastAPI.
Manual JSON, provenance/version yang salah, quantity/unit invalid, dan unit
campuran ditolak; status `STALE_DATA` tidak dikonversi menjadi demand operasional.

Audit lanjutan menemukan enam node transformasi lain pada export LIVE masih
memiliki input `manual_json`. Seluruh tujuh node tersebut sekarang menolak
manual JSON secara eksplisit; tidak ada lagi `state.update(json.loads(manual_json))`
di graph LIVE. PATCH graph aktif berhasil HTTP 200, dan verifier read-only v2
mengonfirmasi graph server 15/12 serta rejection gate tersebut.

Audit fallback kedua juga menghapus default data tersembunyi pada transformasi
CRM/RFM, inventory, supplier, dan marketing. Field order/stock/supplier yang
hilang kini menahan transformasi atau menghasilkan `DRAFT_BLOCKED`; verifier
v2 memindai pola tersebut dan hasil graph aktif terakhir adalah
`hidden_fallback_patterns=[]` setelah PATCH HTTP 200.

Hardening berikutnya mencakup loader context FastAPI dan state transform
Langflow: menu/allergen mapping, stock, supplier pricing/MOQ/lead-time, RFM
identity, forecast method/warnings, inventory ingredient list, dietary state,
marketing segment, dan Summary counts kini wajib ada atau flow berhenti. URL
backend wajib dikonfigurasi; timeout DovaDataSource harus berasal dari
`DOVAGENOME_LIVE_TIMEOUT_SECONDS` atau `LANGFLOW_TIMEOUT_SECONDS` pada proses
Langflow. Jika keduanya tidak ada/invalid, flow berhenti tanpa timeout default.

## Konfigurasi setelah upload

Setelah file fixed di-upload, gunakan base URL tanpa suffix `/run`:

```env
LANGFLOW_API_URL=http://127.0.0.1:7860/api/v1
LANGFLOW_API_KEY=<API key yang diterima server Langflow>
LANGFLOW_FLOW_ID=<ID flow hasil upload, atau dova-kitchen-ai-fixed bila server menerima endpoint name>
```

Jangan memakai key lama yang menghasilkan HTTP 403. Setelah update environment, ulangi `/api/v1/version` dan smoke test run sebelum menyebut flow live.

## Recheck provider 2026-10-27

- Server `/api/v1/version` reachable, versi `1.12.3`.
- Flow ID terkonfigurasi terdeteksi dari `.env`; API key tersedia tanpa
  dicatat nilainya.
- Flow ID aktif terdeteksi dan graph server sudah diperbarui menjadi 15 node/12
  edge; node forecast memuat `forecast_backtest_v2` dan `STALE_DATA` gate.
- Setelah hardening node forecast dan seluruh manual-state gate, PATCH HTTP 200
  dan GET verifikasi membuktikan server memakai graph 15/12; strict
  quantity/unit, provenance, dan manual-state rejection untuk tujuh node aktif
  terverifikasi.
- Smoke post-sync `Reply only READY.` mencapai graph aktif dan mengembalikan
  HTTP 500 dengan detail provider `gemma-4-31b-it` `429 RESOURCE_EXHAUSTED`;
  error menyebut quota input-token free tier 16.000 token/menit. Ini bukan
  error parsing node forecast. Flow lama dengan vector sebelumnya timeout 60
  detik; pending workflow Langflow kosong.
- Recheck smoke terkontrol pada flow utama memakai `verify_forecast_live.py
  --model-smoke --smoke-timeout 30` mengembalikan HTTP 500 dalam 3,25 detik;
  body sengaja tidak dicatat dan classifier tidak menemukan marker provider.
  Ini belum membuktikan model live stabil.
- Instance Langflow bersih 7861 dengan graph yang sama berhenti setelah node
  forecast dan gagal tepat saat membangun provider Google karena
  `GOOGLE_API_KEY` belum dikonfigurasi. Bukti ini menunjukkan kontrak
  `forecast_status` sudah lolos ke tahap provider, bukan error state Inventory.
- Launcher `backend/scripts/start_langflow_live.ps1` sekarang mewariskan
  backend URL, internal token, dan timeout secara eksplisit ke proses Langflow;
  tidak ada timeout atau backend URL default tersembunyi.
- Trace error terbaru memperlihatkan akar masalah provider: `gemma-4-31b-it`
  mengembalikan Google `429 RESOURCE_EXHAUSTED` karena quota
  `generate_content_free_tier_input_token_count` sebesar `16000` input token
  per menit terlampaui.
- Trace sukses juga membuktikan node `Dova - Live FastAPI Context` selesai dan
  menerima `_data_mode=live`; output model yang sukses tetap belum dianggap
  tersedia sampai quota/provider dipulihkan.
- Endpoint FastAPI live context dapat HTTP 200 secara langsung dalam 6,6 detik.
- Setelah context dipadatkan, trace `ddbdeedd-c75a-4963-aa35-319b7690abd8`
  berstatus `ok`, mengembalikan `READY`, 7.480 input token, 63 customer pada
  KPI context, dan total latency 121.802 ms (121,8 detik). Trace ini membuktikan graph/model
  live dapat selesai; latency dan quota tetap menjadi batas operasional.
- Kesimpulan: dependency backend live sehat; graph/model/context sudah
  terbukti sekali, tetapi runtime belum stabil karena quota provider. Pertanyaan
  operasional harus tetap diberi label degraded bila run gagal.

## Recheck graph contract terbaru

- `GET /api/v1/version` menggunakan server lokal mengembalikan HTTP 200,
  versi `1.12.3`.
- `GET /api/v1/flows/{LANGFLOW_FLOW_ID}` dengan header `x-api-key` yang diterima
  server mengembalikan HTTP 200.
- Graph aktif terverifikasi **15 node / 12 edge** dengan forecast
  `code_hash=dova-live-state-fail-closed-forecast-ff75879defef` dan
  DovaDataSource `dova-live-config-fail-closed-fee473e6bc9f`.
- Node Demand Forecast terverifikasi memuat `forecast_backtest_v2`, menolak
  `manual_json`, dan memiliki gate `STALE_DATA`; enam node transformasi LIVE
  lain juga menolak `manual_json` sehingga graph tidak memiliki fallback manual
  tersembunyi.
- Verifier secret-free juga membaca model node aktif sebagai provider `Google
  Generative AI` dengan model `gemma-4-31b-it`; verifier tidak menyimpulkan
  credential provider tersedia hanya dari metadata graph. Pemeriksaan node
  terbaru mencatat `node_credential_present=false`; global credential tetap
  harus dibuktikan lewat model smoke yang berhasil.
- Header Bearer saja tidak dipakai sebagai bukti flow; endpoint flow menerima
  `x-api-key` sesuai OpenAPI server.

Smoke sebelum context dipadatkan pada 16:22 WIB memakai `x-api-key` dan prompt
`Reply only READY.` timeout di client. Trace terbaru sesudah perubahan context
kemudian selesai dengan status `ok`; timeout client sebelumnya tidak lagi
menjadi bukti terakhir tentang graph, tetapi tetap menunjukkan latency belum
memenuhi batas aplikasi.

