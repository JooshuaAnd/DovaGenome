# Langflow Live Data Module

Tanggal: 2026-10-27

Modul live memakai jalur berikut:

```text
Langflow custom component
  -> GET FastAPI /api/ai/internal/context
  -> FastAPI membaca Supabase/Postgres dengan service connection
  -> JSON context bertanda _data_mode=live
  -> node RFM / forecast_backtest_v2 / inventory / supplier PO / summary
```

Langflow tidak menerima credential Supabase. Konektor juga fail-closed: jika
token tidak ada, FastAPI tidak dapat dihubungi, response bukan JSON, atau
response tidak bertanda `live`, flow berhenti dan tidak memakai sample.

## File

- `backend/app/services/langflow_context_service.py` — builder konteks live.
- `backend/app/api/routers/ai.py` — endpoint internal read-only.
- `langflow/Dova_Kitchen_Chef_BOB_LIVE.json` — export flow siap di-upload.
- `.env.example` — nama environment variable yang dibutuhkan.

## Environment

LIVE graph saat ini berisi 15 node/12 edge. Node Supabase VectorStore,
Embedding, dan file-ingestion sengaja tidak dimuat karena credential, tabel,
RPC, dan sumber file belum memiliki evidence runtime yang cukup. Dengan begitu
graph tidak gagal membangun node vector secara diam-diam; `VECTOR_RETRIEVAL_READY`
tetap `NOT_CONFIGURED`.

Isi secret yang sama di dua proses, tetapi jangan commit secret ke repo.

FastAPI `.env`:

```env
LANGFLOW_INTERNAL_TOKEN=<secret-random-yang-sama>
```

Proses Langflow:

```env
DOVAGENOME_BACKEND_URL=http://127.0.0.1:8000
DOVAGENOME_INTERNAL_TOKEN=<secret-random-yang-sama>
DOVAGENOME_LIVE_TIMEOUT_SECONDS=15
```

`DOVAGENOME_LIVE_TIMEOUT_SECONDS` harus benar-benar berada di environment
proses Langflow, bukan hanya di `.env` FastAPI. Node LIVE juga menerima
`LANGFLOW_TIMEOUT_SECONDS` sebagai nama alternatif eksplisit; jika keduanya
tidak ada atau invalid, flow berhenti fail-closed tanpa memakai timeout diam-diam.

Untuk menghindari proses Langflow mewarisi environment yang tidak lengkap,
gunakan launcher repository berikut dari root repo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\start_langflow_live.ps1
```

Launcher membaca shared token dan timeout dari `.env`, memetakan token ke
`DOVAGENOME_INTERNAL_TOKEN` (serta alias `LANGFLOW_INTERNAL_TOKEN`) tanpa
mencetak secret. Untuk development lokal, backend URL default-nya
`http://127.0.0.1:8000`; gunakan `-BackendUrl` untuk Docker atau host lain.
Proses Langflow yang sudah berjalan tidak menerima perubahan environment,
jadi tutup proses lama lalu jalankan launcher tersebut untuk menerapkan token.

Jika Langflow berjalan di Docker sedangkan FastAPI di host Windows, gunakan
`DOVAGENOME_BACKEND_URL=http://host.docker.internal:8000`.

`LANGFLOW_API_KEY` tetap merupakan credential terpisah untuk memanggil server
Langflow dari backend; token internal di atas hanya untuk konektor live ke
FastAPI.

### Provider model adalah credential ketiga

Node `Language Model` pada flow aktif saat ini memilih provider Google
Generative AI dengan model `gemma-4-31b-it`. Karena itu proses Langflow juga
harus memiliki credential provider yang sesuai, misalnya `GOOGLE_API_KEY` atau
`GEMINI_API_KEY`, melalui konfigurasi provider Langflow/UI. Nilai
`LANGFLOW_API_KEY` tidak dapat dipakai sebagai pengganti API key Google.

Jika memakai provider lain, pilih model yang benar-benar memiliki credential
dan quota di instance tersebut, lalu sinkronkan export flow dan ulangi smoke
test. Jangan mengganti provider dengan fallback lokal atau prompt-only data:
flow tetap harus menerima context live FastAPI dan status error harus terlihat
sebagai unavailable/degraded.

Konfigurasi `.bob/mcp.json` adalah jalur MCP terpisah. File flow LIVE ini tidak
membacanya; ia memanggil endpoint FastAPI dengan `X-Dova-Internal-Token`.
Jangan commit API key yang ditulis langsung di file MCP; rotasi key tersebut
jika sudah pernah tersimpan di repository atau terbagi ke pihak lain.

## Upload dan konfigurasi

1. Restart FastAPI setelah mengisi `LANGFLOW_INTERNAL_TOKEN`.
2. Set environment proses Langflow, lalu restart Langflow.
3. Upload `langflow/Dova_Kitchen_Chef_BOB_LIVE.json` melalui UI Langflow.
4. Catat flow ID yang diberikan Langflow setelah upload.
5. Set backend:

   ```env
   LANGFLOW_API_URL=http://127.0.0.1:7860/api/v1
   LANGFLOW_FLOW_ID=<flow-id-hasil-upload>
   ```

6. Restart backend dan jalankan Playground atau `/api/ai/consult`.

Jangan mengaktifkan toggle sample pada flow LIVE. Untuk demo simulasi gunakan
`langflow/Dova_Kitchen_Chef_BOB_FIXED_SAFE_ASCII.json`.

## Verifikasi

Endpoint read-only dapat diuji dengan header berikut:

```text
GET /api/ai/internal/context
X-Dova-Internal-Token: <secret-random-yang-sama>
```

Response yang dianggap valid harus memuat:

```json
{
  "_data_mode": "live",
  "_source": "supabase_postgres_via_fastapi",
  "counts": {}
}
```

Smoke test database aktif pada 2026-10-27 menghasilkan HTTP 200 dan mode live.
Konteks terbaca 18 menu, 844 order paid, 1.682 paid order-items, 63 customer,
6 item stok, dan 8 supplier. Forecast context 7d/30d berasal dari
`forecast_backtest_v2` dan keduanya berstatus `STALE_DATA`.
Context juga membawa `forecast_dependency_metadata` per horizon tanpa default
tersembunyi: jumlah order/item paid dan dua tanggal latest ditampilkan sebagai
evidence warning agar model tidak menerima angka forecast tanpa provenance.
Read-only recheck 16:38 WIB mengonfirmasi kedua horizon memiliki
`paid_order_count=418`, `paid_order_item_count=817`, dan latest dates
`2026-10-12`; status forecast tetap `STALE_DATA`.
Untuk graph aggregate internal, KPI `counts.customers` tetap 63 tetapi
`customers` dikosongkan dan diberi `customer_profile_context=
omitted_internal_aggregate`; profil dietary individual tidak dikirim ke
Langflow. Keputusan safety customer tetap harus melalui FastAPI terotorisasi.

Smoke graph terbaru setelah hardening context menghasilkan trace `ok`, output
`READY`, 7.480 input token, dan latency 121,8 detik. Artinya graph/model live
terbukti dapat selesai, tetapi client timeout dan quota provider masih harus
dianggap sebagai batas operasional.

Recheck 2026-10-27 pada active flow mengembalikan HTTP 500. Graph dan context
tetap lolos verifier, tetapi model smoke belum dapat disebut stabil; instance
Langflow bersih yang memakai graph sama berhenti saat provider Google dibangun
karena `GOOGLE_API_KEY` belum dikonfigurasi.

## Batasan data yang sengaja terlihat

- BOM hanya dipakai penuh jika recipe dan component sudah `VERIFIED`.
- Forecast context hanya memakai order `PAID` non-`CANCELLED` dan quantity/unit
  eksplisit dari `order_items`. Karena data terbaru stale dan BOM belum
  verified, hasil tidak boleh dianggap sebagai jumlah produksi final.
- Endpoint hanya read-only. Modul tidak membuat order, mengirim PO, mengubah
  status pembayaran, atau mengirim pesan marketing.
- Allergy Guard untuk web/order tetap berada di FastAPI dan tidak digantikan
  oleh keputusan LLM di Langflow.
