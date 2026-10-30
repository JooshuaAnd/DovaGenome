# Langflow Failure Test Report

Tanggal: 2026-10-27 (recheck)

| Test | Hasil | Catatan |
|---|---|---|
| Version/health endpoint | PASS | Server menjawab HTTP 200, versi `1.12.3`. |
| Run dengan konfigurasi aplikasi saat ini | PASS_ONCE / PARTIAL | Trace terbaru `ddbdeedd-c75a-4963-aa35-319b7690abd8` berstatus `ok` dan mengembalikan `READY` setelah context dipadatkan; latency 121,8 detik melewati timeout client. Trace lain tetap mengembalikan Google `429 RESOURCE_EXHAUSTED`; HTTP 403 dicatat sebagai kegagalan konfigurasi historis. |
| Fallback setelah run gagal | PASS | Mode default `required_langflow` mengembalikan `degraded=true` tanpa fallback tersembunyi; mode `allow_explicit_fallback` diuji dan memberi label `explicit_fallback`. |
| Export JSON parse | PASS | File fixed dapat diparse sebagai JSON. |
| Export graph integrity | PASS | 23 node, 20 edge, ID unik, tidak ada edge menggantung. |
| Custom component syntax | PASS | 21 blok `code` dapat dikompilasi Python. |
| LIVE forecast malformed payload/manual state | PASS | Node Demand Forecast menolak manual JSON, provenance/version salah, quantity/unit hilang atau invalid, dan unit campuran; tidak memakai default `0`/`portion`. |
| Live model/vector/database flow | PARTIAL | Graph aktif/model/context terbukti selesai pada trace terbaru; vector belum dikonfigurasi, latency tinggi, dan provider quota belum stabil. |

Recheck runtime aktif: graph `daf5e1ab-3bb3-4051-a9d0-270fffff517d` memiliki 15
node/12 edge, `Dova Demand Forecast` memuat `forecast_backtest_v2` dan
`STALE_DATA` gate, serta tidak memiliki node Supabase/Embedding/Vector. Trace
`55a5de6b-807d-4496-b0b8-04710bf98634` berstatus `ok` dengan model
`gemma-4-31b-it` dan context live; percobaan berikutnya gagal karena Google
`429 RESOURCE_EXHAUSTED`. Karena itu statusnya `PASS_ONCE/NOT_STABLE`, bukan
production-ready.

Smoke post-sync historis `Reply only READY.` mengembalikan HTTP 500 dengan
detail provider `gemma-4-31b-it`, yaitu quota input-token free tier 16.000
token/menit. Setelah backend tidak mengirim profil dietary individual ke
aggregate context, trace `ddbdeedd-c75a-4963-aa35-319b7690abd8` selesai `ok`
dengan 7.480 input token dan output `READY`. Tidak ada indikasi error parsing
pada node forecast LIVE setelah hash strict diterapkan; batas yang tersisa
adalah latency dan quota provider.

## Root cause yang dapat dibuktikan

1. API key yang dibaca aplikasi tidak diterima oleh server Langflow lokal.
2. Runtime flow ID pada environment tidak sama dengan ID export utama.
3. Export lama mengaktifkan sample data dan tidak memiliki bukti live-data ingestion.

## Perbaikan yang diperlukan di luar JSON

- Ambil/ganti API key dari server Langflow lokal.
- Upload file fixed, lalu ambil flow ID hasil upload.
- Set `LANGFLOW_API_URL` sebagai base `/api/v1` dan `LANGFLOW_FLOW_ID` ke flow baru.
- Bila mode non-sample digunakan, isi data operational JSON secara eksplisit atau implementasikan connector live di environment Langflow.

