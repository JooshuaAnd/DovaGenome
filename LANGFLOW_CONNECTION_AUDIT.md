# Langflow Connection Audit

Tanggal audit: 2026-10-27 (recheck)

## Hasil singkat

- Langflow lokal reachable pada `http://127.0.0.1:7860`.
- Versi server: `1.12.3`.
- OpenAPI mengonfirmasi endpoint run memakai `x-api-key` melalui header atau query; client FastAPI sudah memakai header yang benar.
- Smoke test historis flow gagal dengan **HTTP 403 — Invalid or missing API key**.
- Recheck 2026-10-27: endpoint FastAPI live context HTTP 200 dalam 6,6 detik;
  trace sukses membuktikan graph/model/context sekali. Run berikutnya tertahan
  pada 120 detik dan trace menunjukkan model `gemma-4-31b-it` ditolak Google
  dengan `429 RESOURCE_EXHAUSTED` karena quota input-token free tier 16.000
  token/menit. Flow executable/model belum stabil.
- Recheck setelah context dipadatkan: trace
  `ddbdeedd-c75a-4963-aa35-319b7690abd8` berstatus `ok`, output `READY`,
  input 7.480 token, total latency 121,8 detik. Ini membuktikan eksekusi live
  dapat selesai, tetapi belum memenuhi timeout client dan belum stabil terhadap
  quota provider.
- `AI_MODE=required_langflow` sekarang menjadi default: kegagalan Langflow
  mengembalikan `degraded=true` tanpa memanggil RAG tersembunyi. Fallback RAG
  hanya tersedia dengan `AI_MODE=allow_explicit_fallback` dan diberi label
  `explicit_fallback`.

## Mismatch konfigurasi

| Item | Nilai/temuan |
|---|---|
| Runtime flow ID dari konfigurasi aplikasi | Ada dan berbentuk UUID, tetapi tidak sama dengan ID export utama |
| ID export utama | `0e604aec-8fea-4055-99bc-05831ac96e7f` |
| Endpoint name export utama | `dova-kitchen-ai` |
| Server/API key | Header `x-api-key` dari environment diterima untuk flow aktif; Bearer saja ditolak; nilainya tidak dicatat di laporan |
| `DovaDataSource.use_sample` export lama | `True` |
| Vector table | `documents` |
| Vector query/RPC | `match_documents` |

## Temuan export

- Export utama historis memiliki 23 node dan 20 edge.
- `docs/langflow/original.json` memiliki 23 node dan 19 edge; export utama memiliki edge tambahan dari `ChatInput` ke `Prompt Template` untuk field `question`.
- Tidak ada duplicate node ID atau dangling edge pada export utama.
- `DovaDataSource` berisi dataset hardcoded dan default sample aktif. Export lama dapat terlihat sukses walaupun tidak memakai data live.
- Vector store mengandalkan tabel/RPC yang tidak didefinisikan oleh migration repo; readiness vector belum terbukti.

## File perbaikan

[Dova_Kitchen_Chef_BOB_FIXED_SAFE.json](D:/DovaGenome/DovaGenome/langflow/Dova_Kitchen_Chef_BOB_FIXED_SAFE.json)

[Dova_Kitchen_Chef_BOB_LIVE.json](D:/DovaGenome/DovaGenome/langflow/Dova_Kitchen_Chef_BOB_LIVE.json)

Modul live FastAPI dan instruksinya ada di
[LANGFLOW_LIVE_MODULE.md](D:/DovaGenome/DovaGenome/LANGFLOW_LIVE_MODULE.md).

Perbaikan di file tersebut:

- endpoint name baru: `dova-kitchen-ai-fixed`;
- sample data opt-in, default `use_sample=false`;
- data kosong pada mode non-sample menghasilkan error eksplisit, bukan diam-diam fallback ke sample;
- prompt menyatakan data simulation/provided bukan bukti live;
- template credential dikosongkan;
- File FIXED SAFE tetap 23 node/20 edge dan lolos validasi compile custom code;
  file LIVE runtime kini fail-closed dengan 15 node/12 edge tanpa vector node.

File ini tidak dapat memperbaiki API key atau membuat data Supabase live otomatis. Keduanya harus dikonfigurasi pada server Langflow/environment.

File LIVE memisahkan masalah tersebut: data operasional diambil read-only dari
FastAPI melalui token internal dan ditolak bila response tidak membuktikan
`_data_mode=live`. API key Langflow tetap harus dikonfigurasi terpisah agar
backend dapat menjalankan flow.

## Recheck provider 2026-10-27

Server tetap reachable dan flow ID/API key terdeteksi dari environment. Graph
LIVE aktif sekarang 15 node/12 edge dan tidak membangun vector store yang
credential-nya tidak tersedia. Namun direct run `Reply only READY.` timeout
120 detik pada percobaan lain; trace sukses sebelumnya membuktikan graph/model
sekali, tetapi status runtime saat ini `NOT_STABLE`, provider terkena quota, dan
vector `NOT_CONFIGURED`.

File LIVE kini meneruskan context `forecast_backtest_v2` dari FastAPI dan
menahan forecast stale sebelum inventory demand dihitung. Endpoint FastAPI
live sudah teruji. Trace Langflow mengisolasi blocker saat ini ke quota
provider Google; tidak ada API key atau billing change yang dilakukan dari
repository.

Recheck setelah audit no-hidden-fallback memperbaiki seluruh tujuh node LIVE
yang memiliki input `manual_json`: input tetap terlihat sebagai field audit,
tetapi setiap nilai non-kosong langsung ditolak dan tidak pernah menimpa state
upstream. Graph aktif disinkronkan dengan PATCH HTTP 200; verifier v2 kemudian
mengonfirmasi 7/7 manual-state rejection tanpa menjalankan model/provider.

Hardening lanjutan menolak default data pada CRM/RFM, inventory, supplier, dan
marketing. Verifier v2 sekarang memeriksa pola fallback operasional tersebut;
graph aktif setelah PATCH HTTP 200 menghasilkan `hidden_fallback_patterns=[]`.

Audit state/context lanjutan juga menolak missing menu/allergen mapping, stock,
supplier price/MOQ/lead-time, forecast method/warnings, dietary state, dan
Summary counts. DovaDataSource tidak lagi memilih localhost atau timeout 15
detik secara diam-diam; timeout harus berasal dari `DOVAGENOME_LIVE_TIMEOUT_SECONDS`
atau `LANGFLOW_TIMEOUT_SECONDS` pada environment proses Langflow, jika tidak
flow berhenti fail-closed.

Recheck graph terbaru mengonfirmasi `GET /api/v1/flows/{flow_id}` HTTP 200
dengan `x-api-key`, graph 15/12, strict forecast code hash
`dova-live-state-fail-closed-forecast-47b87ec92cf8`, dan DovaDataSource hash
`dova-live-config-fail-closed-fee473e6bc9f`. Ini membuktikan konfigurasi graph/credential
API saat ini; belum membuktikan provider model stabil karena smoke run tetap
terkena quota `429`.

Smoke tambahan pada 2026-10-27 16:22 WIB (`Reply only READY.`) tidak selesai
dalam 75 detik dan timeout di sisi client. Runtime tetap `NOT_STABLE`; timeout
ini tidak boleh diperlakukan sebagai respons AI sukses.

Sesudah backend menghilangkan profil dietary individual dari aggregate context,
trace `ddbdeedd-c75a-4963-aa35-319b7690abd8` selesai `ok` dengan model
`gemma-4-31b-it`, 7.480 input token, dan output `READY`. Context tetap membawa
KPI customer count serta forecast v2 live berstatus `STALE_DATA`; hanya matriks
profil customer yang tidak dikirim.

Smoke verifier terkontrol terbaru menghasilkan HTTP 500 dalam 3,12 detik dan
classifier secret-free mengisolasi timeout env Langflow yang belum diwariskan.
Tidak ada retry provider tambahan atau perubahan database yang dilakukan.

