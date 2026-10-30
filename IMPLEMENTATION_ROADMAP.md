# V4 Phase 0 Re-audit Addendum — 2026-10-30

Phase 0 audit and the approved Phase 1 implementation are complete. The older
checkpoint history below is retained for provenance and must not be read as
current runtime proof when it conflicts with the Phase 1 completion report.

Current checkpoint: Phase 2 recipe intake, Phase 7 supplier receiving/billing,
Phase 8 status-based delivery, and Phase 11 production batch are implemented
locally. Supabase/PostgreSQL is the active source of truth; Astra is
`OFFLINE_LEGACY`. Langflow version `1.12.3` is reachable, but the latest
opt-in flow probe is `DEGRADED` with HTTP 500, so flow/model execution is not
claimed stable.

Phase 10 continuation is now implemented locally: Customer, Admin, and
Supplier Telegram entrypoints use separate environment tokens, Admin allowlist,
Supplier tenant resolution, FastAPI-only bridge routes, PO approval/rejection/
send, supplier change request/receipt/invoice, and idempotent daily stock-alert
queueing. Telegram provider workers and live bot tokens remain external gates.

Phase 1 files/functions implemented locally:

- `backend/app/core/config.py`: explicit readiness configuration without secret output.
- `backend/app/services/langflow_service.py`: execution proof, redacted trace metadata, explicit fallback state.
- `backend/app/api/routers/health.py` and `backend/app/api/routers/ai.py`: readiness states and trace-safe response contracts.
- `backend/tests/test_langflow_service.py` plus readiness tests: ON/OFF, timeout, malformed output, disabled, fallback, and no-secret logging.
- `DB_RECOVERY_PLAN.md`: read-only migration/schema check and backup/restore gate; no migration application yet.

Phase 1 verification is complete; stop before Phase 2 for another approval
checkpoint.

# Current continuation checkpoint — 2026-10-30

The user requested continuation through the remaining feasible phases. The
following work is now implemented locally on the Supabase/PostgreSQL path:

- Phase 2 recipe intake accepts PDF/XLSX/CSV/TXT/MD, sends bounded source text
  to the AI draft service, and keeps the result pending admin review.
  Nutrition is calculated deterministically from verified composition evidence;
  missing evidence remains unavailable rather than becoming a guessed zero.
- Phase 11 has a production batch/BOM/weigh ledger. Manual weight input is
  idempotent and updates inventory in the same transaction. Bluetooth remains
  explicitly deferred as requested.
- Phase 4 continuation now exposes
  `POST /api/kitchen/production-batches/plan-from-paid-orders`. It groups paid,
  non-cancelled demand by service date/menu/slot, uses the latest VERIFIED
  recipe, and refuses partial writes when one menu is unresolved.
- Phase 8 Telegram customer reads/writes now go through the FastAPI internal
  bridge. The bot no longer imports `astrapy` or requires Astra credentials;
  FastAPI remains the only business-data path and reads Supabase.
- Phase 10 now has separate thin-client entrypoints in `telegram_bot.py`,
  `telegram_admin_bot.py`, and `telegram_supplier_bot.py`. Admin/Supplier
  commands call FastAPI bridge endpoints with RBAC, tenant isolation, audit,
  and idempotency; daily stock alerts are queued, not falsely marked sent.

- Phase 3/4 continuation now carries `meal_slot` end-to-end. Customer cart and
  order API support breakfast/lunch/dinner on the same service day; order
  persistence, response enrichment, update replacement, and paid-demand batch
  planning preserve the slot. Legacy rows remain lunch. See
  `PHASE_3_MEAL_SLOT_REPORT.md`. Migrations 017/018 are still behind the backup gate.

- Phase 5 continuation adds lot-aware kitchen consumption with FEFO ordering,
  transactional `inventory_lot_allocations`, and aggregate-ledger fallback
  while migration 018 is pending. See `PHASE_5_INVENTORY_LOT_REPORT.md`.

New migrations `013_recipe_import_nutrition.sql` through
`018_inventory_fefo_allocations.sql` are still pending the backup/restore gate. Live
Supabase remains connected, but these new tables/columns are not claimed as
live until a migration run is approved and rechecked.

Open external gates remain: recipe records need operator verification,
Langflow flow/model is currently degraded on the live probe, a real payment
provider is not configured, delivery tracking is status-based without a live
GPS/provider adapter, and the new supplier receiving/billing and delivery
migrations need to be applied. Those are not replaced with mock success.

# Implementation Roadmap — DovaGenome

Status: **PHASE 4 IN PROGRESS + PHASE 7/8/11/12 IN PROGRESS + PHASE 9/10 IN PROGRESS + PRODUCT EXPERIENCE PARTIAL — forecast v2, churn baseline, inventory readiness, supplier sourcing, PO→goods receipt→invoice contracts, delivery status flow, UI live-date, dan Telegram approval tersedia lokal tetapi migration/data/provider gates masih terbuka.** Recipe verification, provider payment live, live write snapshot RFM, supervised churn, SS/ROP freshness, ROQ/EOQ, GPS/provider delivery, dan transaksi paid fresh masih memiliki checkpoint terbuka.

Phase 13 is now **PARTIAL**: campaign draft, consent gate, admin approval,
idempotent queue, and notification outbox contract are implemented locally.
Migration 009/011, provider delivery, runtime rate-limit enforcement, and live
freshness remain open.

## 1. Current State

- FastAPI, React, Supabase/Postgres, Telegram bot, dan export Langflow tersedia. Customer web membaca service-week live untuk tanggal menu; procurement Telegram tetap melalui approval admin dan tidak mengirim PO otomatis tanpa klik.
- `backend/app/services/safety_service.py` dan `order_service.py` memiliki guard deterministik untuk sebagian jalur order API.
- `frontend/src/pages/OrderPage.tsx` sekarang membuat order dan payment intent melalui FastAPI; total tetap berasal dari paket/order server dan UI tidak memiliki tombol simulasi sukses.
- `telegram_bot.py` sekarang menjadi thin client FastAPI; order/profile dibaca dan ditulis melalui Supabase-backed bridge.
- Payment backend sudah memiliki intent, idempotency, signed webhook, expiry, dan paid-only KDS; provider nyata, migration live, dan end-to-end webhook tetap terbuka.
- Forecast v2 strict tersedia; Phase 11 sekarang memiliki report BOM/inventory/lead-time yang fail-closed. Angka SS/ROP belum dikeluarkan karena BOM terbaru belum verified dan forecast stale; ROQ/EOQ belum dihitung karena ordering cost, holding cost, dan pack size belum tersedia.
- RFM strict quantile live tersedia di `rfm_service.py`; snapshot idempotent,
  movement contract, dan freshness gate RFM sudah tersedia, tetapi snapshot
  live masih ditahan karena data paid stale.
- Churn baseline strict tersedia di `churn_service.py` dengan cadence order paid, reason codes, freshness, dan status `BASELINE_ONLY`; backtest label-observasi temporal sekarang tersedia, tetapi belum ada supervised model tervalidasi.
- Static Langflow recovery evidence: export utama memiliki 23 node/20 edge, sedangkan `docs/langflow/original.json` memiliki 23 node/19 edge; export utama masih menandai `DovaDataSource.use_sample=True` dan mereferensikan `documents`/`match_documents` yang belum terlacak di migration repo.
- `LangflowService.ask` memakai `AI_MODE=required_langflow` secara default; `generate_rag_answer` hanya dipanggil pada mode `allow_explicit_fallback` dan response diberi label `explicit_fallback`.
- Technical deck `.pptx` tidak tersedia. Pitch deck dan feedback mentor tersedia dan sudah dipetakan di `REQUIREMENTS_TRACEABILITY.md`.
- Phase 1 lokal: `supabase/migrations/005_core_architecture.sql` menambah fondasi identity/provenance recipe, supplier mapping, payment attempts, kitchen tickets, inventory ledger, snapshots, dan audit request metadata.
- Phase 1 lokal: supplier API tidak lagi mempercayai `supplier_id` dari query; tenant di-resolve dari akun JWT melalui `supplier_accounts`. Test RBAC ditambahkan di `backend/tests/test_supplier_rbac.py`.
- Migration 005 sudah diterapkan dan diverifikasi pada target Supabase yang terhubung: `migrations_ok=True`, 11 tabel baru tersedia, RLS aktif, constraint role mencakup `supplier`, dan seluruh legacy ingredient rows berhasil terhubung ke canonical ingredient ID. Environment target (staging/production) tidak disimpulkan dari repository.
- Konfigurasi `DEBUG=release` sekarang diparse sebagai non-debug mode di `backend/app/core/config.py`; sebelumnya backend gagal start karena nilai tersebut bukan boolean.
- Phase 2 lokal: `supabase/migrations/006_recipe_verification_bootstrap.sql` membuat recipe version/component bootstrap untuk 18 menu existing tanpa mengarang takaran, menambahkan canonical allergen evidence pada ingredient, dan mempertahankan status awal `PENDING_VERIFICATION`.
- Phase 2 lokal: `safety_service.py` fail-closed dengan level `REQUIRES_VERIFICATION`; order menolak menu yang blocked atau belum diverifikasi. Konflik allergen kritis tetap diprioritaskan sebagai `BLOCKED`.
- Phase 2 lokal: admin recipe review tersedia melalui `backend/app/repositories/recipe_repo.py`, router admin, dan `frontend/src/pages/admin/RecipeReviewPage.tsx`. Verifikasi recipe hanya berhasil bila komponen, quantity/unit, ingredient status, dan cross-contact risk memenuhi kontrak.
- Phase 2 live verification: migration check `true`; `recipe_versions=18`, seluruhnya `PENDING_VERIFICATION`; `recipe_components=54`, seluruhnya masih memiliki quantity/unit atau status yang belum memenuhi verifikasi; tidak ada komponen dengan ingredient ID kosong.
- Phase 2 live smoke test: `GET /api/health` HTTP 200 dengan `db_connected=true`; `GET /api/catalog/menus/week?days=Senin` HTTP 200, tiga opsi dan tiga status safety `requires_verification`. Ini membuktikan fail-closed gate, bukan bukti bahwa menu sudah aman.
- Phase 3 lokal: `backend/tests/test_allergy_guard_adversarial.py` menguji prompt injection, output LLM yang mencoba mengubah verdict, perubahan Dietary Passport, hidden BOM, dan persistence order.
- Phase 3 lokal: `catalog_repo.py` sekarang menggabungkan ingredient canonical dari `recipe_components` ke input Allergy Guard; ingredient tersembunyi di legacy `menu_ingredients` tidak lagi hilang dari filter.
- Cross-phase Langflow audit: server lokal reachable dan version `1.12.3`; endpoint FastAPI live context HTTP 200 dalam 6,6 detik. Trace aktif 15/12 membuktikan context/model sekali, lalu trace berikutnya menunjukkan Google `429 RESOURCE_EXHAUSTED` karena quota input-token free tier 16.000 token/menit; runtime belum stabil dan vector belum terkonfigurasi. Fallback Supabase RAG tidak dihitung sebagai flow live.
- Cross-phase Langflow export fix: `langflow/Dova_Kitchen_Chef_BOB_FIXED_SAFE.json` dibuat dengan sample opt-in/fail-closed, credential template kosong, dan graph 23 node/20 edge yang tervalidasi.
- Cross-phase Langflow live module: `langflow/Dova_Kitchen_Chef_BOB_LIVE.json` memanggil endpoint read-only FastAPI `/api/ai/internal/context`; endpoint menghasilkan `_data_mode=live`, source `supabase_postgres_via_fastapi`, 844 paid order dan forecast v2 7d/30d `STALE_DATA`. Graph aktif 15/12 sudah diselaraskan ke forecast v2 dan fail-closed tanpa vector node yang belum terkonfigurasi; provider masih quota-limited.
- Recheck graph Langflow: `/api/v1/version` HTTP 200 dan `GET /api/v1/flows/{flow_id}` dengan `x-api-key` HTTP 200; graph aktif 15/12, strict v2/stale gate dan manual-state rejection seluruh 7 node terverifikasi.
- Langflow context hardening: aggregate graph tetap menerima KPI customer count, tetapi tidak mengirim profil dietary individual; hasil live context `customers_sent=0`, `customer_count=63`, `customer_profile_context=omitted_internal_aggregate`, sehingga matriks customer×menu dan PII yang tidak diperlukan tidak masuk prompt.
- Langflow dependency evidence: `forecast_dependency_metadata` per horizon membawa paid order/item counts, quality counts (`invalid_quantity_item_count=0`, `missing_unit_item_count=0`, `missing_menu_id_item_count=0`), serta latest dates tanpa default; field yang hilang atau quality count non-zero menahan forecast live.
- Langflow smoke terbaru sesudah hardening: trace `ddbdeedd-c75a-4963-aa35-319b7690abd8` `ok`, output `READY`, 7.480 input token, latency 121,8 detik. Graph/model terbukti dapat selesai, tetapi provider quota dan latency masih terbuka.
- Recheck provider 2026-10-27: active graph memilih Google Generative AI `gemma-4-31b-it`; verifier secret-free melaporkan `node_credential_present=false`. `.env` hanya memiliki `LANGFLOW_API_KEY` (server credential), tanpa `GOOGLE_API_KEY`/`GEMINI_API_KEY`/`OPENROUTER_API_KEY`. Model smoke active HTTP 500 dan instance bersih gagal saat provider Google dibangun. `MODEL_REACHABLE` belum stabil.
- Phase 4 in progress: `backend/app/services/forecast_service.py` sekarang membandingkan baseline, `LINEAR_TREND`, dan `RIDGE_LAG_7`, menghitung MAE/RMSE/WAPE/sMAPE, interval 80%, provenance, dan snapshot write-gate. Live query paid-only memakai kontrak `order_items.quantity/unit` setelah migration `008`. Detail ada di `PHASE_4_FORECAST_BACKTEST_REPORT.md`.
- Phase 4 UI follow-up: panel admin menampilkan source, calculation version, freshness/write-gate, dan tombol snapshot yang disabled saat report live bukan `OK`; angka stale tidak diberi label operasional.
- Phase 4 Langflow follow-up: node Demand Forecast pada export LIVE menolak manual state dan payload quantity/unit/provenance yang tidak valid; hanya `forecast_backtest_v2` live dari FastAPI yang diproses.
- Phase 4 Langflow fallback audit follow-up: CRM/RFM wajib menerima field order lengkap, inventory tidak mengubah stok hilang menjadi nol, supplier tidak menerima default MOQ/lead/capacity, dan marketing membuat `DRAFT_BLOCKED` bila profile tidak lengkap; active graph verifier v2 melaporkan `hidden_fallback_patterns=[]` setelah PATCH HTTP 200.
- Phase 4 context-source audit follow-up: loader FastAPI kini menolak menu tanpa
  ingredient/allergen mapping, stock dengan current_stock/unit invalid, supplier
  tanpa price/MOQ/lead-time, dan customer-count query tidak lagi dibatasi LIMIT
  tersembunyi; regression tests memverifikasi setiap jalur fail-closed.
- Phase 4 Langflow state audit follow-up: RFM, forecast, inventory, supplier,
  dietary, marketing, dan Summary tidak lagi mengubah state/identity/count yang
  hilang menjadi nama/angka/list pengganti; graph verifier memindai pola tersebut.
- Phase 4 runtime smoke follow-up: `verify_forecast_live.py --model-smoke`
  sekarang mengembalikan status bounded `PASS`, `TIMEOUT`, `PROVIDER_QUOTA`, atau
  `HTTP_ERROR` tanpa mencetak response/secret. Recheck aktif terbaru menghasilkan
  `HTTP_ERROR` HTTP 500; dependency FastAPI tetap PASS, sedangkan provider Google
  belum terbukti reachable karena credential/quota provider belum tersedia di
  runtime Langflow.
- Phase 4 freshness follow-up: freshness gate dihitung per-series; jika satu menu stale, seluruh report ditahan dan dashboard menampilkan jumlah series stale.
- Phase 4 metric follow-up: WAPE pada holdout tanpa actual demand tidak lagi dipaksa menjadi `0%`; diberi status `UNDEFINED_ZERO_ACTUAL` dan ditampilkan sebagai `N/A`.
- Phase 4 metric follow-up: sMAPE dengan seluruh denominator nol sekarang diberi status `UNDEFINED_ZERO_DENOMINATOR` dan ditampilkan sebagai `N/A`, bukan `0%`.
- Phase 4 validation follow-up: series `LOW_VALIDATION` tidak lagi menghasilkan forecast operasional atau dihitung eligible; write-gate tetap tertutup sampai holdout minimum terpenuhi.
- Phase 4 provenance follow-up: report live `OK` dan snapshot kini wajib memiliki `source=supabase_postgres` serta dependency metadata paid-order lengkap; report fixture tidak dapat dipersist sebagai snapshot operasional.
- Phase 4 provenance default follow-up: `build_forecast_report()` sekarang
  default ke `data_mode=fixture`/`source=fixture`; caller harus menyatakan
  provenance Supabase secara eksplisit sebelum report dapat berstatus live.
- Phase 4 dependency follow-up: seluruh report live, termasuk `STALE_DATA`, `LOW_VALIDATION`, `INSUFFICIENT_HISTORY`, dan `NO_DATA`, memvalidasi count/date dependency tanpa default tersembunyi; live query juga memvalidasi quality count quantity/unit/menu-id dan menahan nilai non-zero. Tanggal boleh `null` hanya pada report non-operasional/no-observation.
- Phase 4 UI provenance follow-up: admin forecast hanya menyimpan payload `live` dari `supabase_postgres` dengan `forecast_backtest_v2`, dependency metadata lengkap, dan row forecast valid; refresh gagal/kontrak invalid mengosongkan state forecast agar payload lama tidak tampil sebagai evidence baru.
- Phase 4 snapshot version follow-up: persistence menolak `calculation_version` selain `forecast_backtest_v2`, sehingga snapshot tidak dapat mencampur kontrak model legacy dengan report v2.
- Phase 4 context completeness follow-up: histori order-item untuk CRM/RFM Langflow memakai sentinel `LIMIT 2001` dan fail-closed di atas 2.000 baris; subset live tidak pernah dikirim tanpa penanda.
- Phase 4 observation-shape follow-up: tanggal observasi hilang/invalid dan row non-object sekarang ditolak sebagai `ForecastUnavailable`, bukan berubah menjadi error 500 atau tanggal buatan.
- Phase 4 canonical-field follow-up: forecast observation live wajib memakai
  `series_key` dan `target_date` canonical; alias `menu_id`/`date` tidak lagi
  dipakai untuk menyamarkan field live yang hilang. Parameter backtest invalid
  juga ditolak sebelum model berjalan.
- Phase 4 snapshot-row follow-up: sebelum persistence, report harus object dan series key/unit, target date, method, quantity, interval bound, dan interval level wajib memenuhi kontrak v2; malformed report tidak mencapai database.
- Phase 4 context field follow-up: order context CRM/RFM tidak lagi mengubah customer, menu, tanggal, meal count, atau total yang hilang menjadi placeholder/nol; field live yang tidak lengkap menahan seluruh context.
- Phase 4 temporal follow-up: observasi live bertanggal masa depan ditolak sebagai `ForecastUnavailable`, bukan menjadi HTTP 500 atau forecast yang tampak valid.
- Phase 4 time-boundary follow-up: histori dan horizon forecast sekarang dihitung per-series sampai observasi terakhir series tersebut; tail zero sintetis dari series lain tidak lagi masuk training.
- Phase 4 completeness follow-up: satu series `INSUFFICIENT_HISTORY` kini menahan report global dan snapshot; subset menu yang eligible tidak dipersist sebagai forecast operasional parsial.
- Phase 4 deployment evidence: flow Langflow aktif `daf5e1ab-3bb3-4051-a9d0-270fffff517d` berhasil disinkronkan HTTP 200; GET sesudah patch membuktikan graph 15/12, DovaDataSource `dova-live-config-fail-closed-fee473e6bc9f`, state transforms fail-closed, dan forecast node `dova-live-state-fail-closed-forecast-ff75879defef` aktif di server. Alias `forecast_status` ditambahkan untuk memenuhi kontrak Inventory tanpa mengubah status stale menjadi OK.
- Phase 4 safety follow-up: facade supply-chain legacy yang menghasilkan SS/ROP sintetis sekarang fail-closed; dashboard hanya memakai endpoint forecast-backtest strict dan tidak menampilkan forecast stale sebagai operasional.
- Phase 4 safety follow-up: endpoint `demand-insights` legacy dan fallback demand BOB juga dinonaktifkan; caller aktif memakai forecast live atau mengembalikan unavailable.
- Phase 4 safety follow-up: route supplier `/supplier/demand-forecast` tidak lagi memanggil facade analytics legacy; dikembalikan `410` sampai BOM, inventory, unit conversion, dan lead time terverifikasi.
- Phase 4 UI safety follow-up: tab forecast supplier tidak lagi menampilkan KPI/material demo ketika route legacy `410` atau kontrak live tidak valid; UI menampilkan forecast ditahan tanpa angka pengganti.
- Phase 11 lokal: `backend/app/services/inventory_service.py` menambahkan BOM explosion berbasis recipe terbaru, unit conversion, safety stock/ROP berbasis forecast fresh dan lead time supplier, serta readiness report; tidak ada fallback sintetis dan tidak ada auto-PO.
- Phase 11 lokal: `GET /api/admin/analytics/inventory-replenishment` dan panel admin membaca kontrak inventory live; `/admin/inventory-alerts` tidak lagi mengembalikan fixture saat database gagal.
- Phase 12 lokal: `supplier_sourcing_service.py` menambahkan ranking transparan berbasis harga, lead time, dan rating live; `procurement_service.py` menambahkan draft PO live-only, idempotency key, approval admin, audit event, queue outbox `PENDING`, goods receipt atomik, dan supplier invoice three-way match. Migration `010_procurement_workflow.sql` menyelaraskan status/schema PO; migration `015_goods_receipt.sql` dan `016_supplier_billing.sql` masih menunggu backup gate. `telegram_bot.py` kini memiliki inbox approval allowlist dan route internal `approve → send`; provider notification, payment, dan data fresh masih terbuka.
- Phase 8 lokal: `delivery_service.py` menyediakan manifest, assign courier, transisi pickup→out-for-delivery→delivered, proof reference, idempotency, dan tracking customer. Migration `017_delivery_dispatch.sql` menambah role courier, stop/event ledger, dan meal slot delivery; GPS live sengaja belum diklaim.
- Phase 15 lokal: `backend/scripts/run_phase_acceptance_demo.py` menghasilkan expected-vs-actual report terisolasi dengan provenance `SIMULATED`; demo tidak menulis ke Supabase dan tidak mengklaim provider/payment/delivery live.
- Phase 13 lokal: `backend/app/services/marketing_service.py` menambahkan draft win-back berbasis baseline churn live, consent eksplisit, channel verification, freshness gate, state machine `DRAFT → APPROVED → QUEUED`, dan idempotent notification outbox; queue tidak memanggil provider dan tidak mengklaim pesan terkirim.
- Omnichannel hardening: `telegram_bot.py:get_langflow_response` sekarang thin client ke `POST /api/ai/consult` yang sama dengan web; direct Langflow/RAG fallback bot dihapus dan kegagalan diberi status unavailable eksplisit.
- Phase 7 checkpoint: `backend/app/services/payment_service.py` dan `backend/app/api/routers/payments.py` menambahkan payment intent, HMAC webhook, idempotency, dan ticket release paid-only. KDS/API menolak order unpaid; detail dan batasan ada di `PHASE_7_PAYMENT_KDS_REPORT.md`.

## 2. Target fase implementasi

Target akhir adalah satu alur yang dapat dibuktikan:

```text
Customer/Telegram
        ↓
FastAPI + auth/RBAC + server-side validation
        ↓
Dietary Passport + verified recipe/BOM + Allergy Guard
        ↓
Order draft → payment intent → verified idempotent webhook
        ↓
Paid order → kitchen ticket → BOM/MRP → inventory
        ↓
Forecast + SS/ROP/ROQ (jika datanya cukup)
        ↓
Persistent draft PO → admin approval → supplier response
        ↓
RFM/churn baseline → marketing draft → admin approval
```

LLM/Langflow hanya boleh menyusun bahasa atau draft terstruktur. Keputusan alergi, harga, status lunas, tiket dapur, stok, PO send, dan marketing send harus berasal dari service deterministik/otorisasi backend.

## 3. Fase dan dependency plan

| Fase | Fokus | Kandidat file/area yang akan diubah | Migration utama | Acceptance gate |
|---|---|---|---|---|
| 0 | Requirements mapping & plan | Dokumen Phase 0 saja | Tidak ada | Traceability disetujui; konflik sumber tercatat. |
| 1 | Database & core architecture | `supabase/migrations/`, `backend/app/core/`, repositories, auth/deps | Identity, recipe/ingredient provenance, payment attempts, kitchen tickets, inventory movements, snapshots; hanya tabel yang belum tersedia | Schema/FK/index/RLS/RBAC dan legacy mapping direview. |
| 2 | Dietary Passport & Allergy Guard + recipe verification | `safety_service.py`, `catalog_repo.py`, passport schemas/services, admin recipe UI | Ingredient/allergen mapping, nested BOM, recipe versions, verification events, cross-contact | Fail-closed; `ELIGIBLE/BLOCKED/REQUIRES_VERIFICATION`; order guard memakai data versi terbaru. |
| 3 | Adversarial Allergy Tests | `backend/tests/`, frontend tests, mocked LLM contract | Tidak ada kecuali fixture metadata | Tidak ada bypass untuk prompt injection, blocked output, missing verification, BOM tersembunyi, dan passport change. |
| 4 | Demand Forecast ML & Backtest | `analytics_ml_service.py`, evaluation scripts/reports | `demand_forecasts`, `forecast_evaluations` bila diperlukan | Rolling-origin; bandingkan naive/MA7/seasonal/model; semua metrik berlabel. |
| 5 | Langflow orchestration & Chef BOB | `langflow_service.py`, `rag_ai_service.py`, `api/routers/ai.py`, Langflow contract tests | `documents`/metadata jika memang diperlukan setelah schema review | Authorized context, no unrestricted PII, structured output, post-validation, live/mock distinction. |
| 6 | Customer portal & ordering | `OrderPage.tsx`, `services/orders.ts`, order draft schemas/services | `order_drafts`, addresses jika belum dapat dipetakan ke schema existing | Web cart → server draft/order; harga, menu, safety, ownership seluruhnya server-side. |
| 7 | Payment, KDS, no-pay-no-cook | payment router/provider, webhook, `order_service.py`, `kitchen.py`, worker | payments/payment_attempts/kitchen_tickets/outbox/idempotency | Signature/amount/order validation, expiry 10 menit, one-time webhook, paid-only kitchen visibility. |
| 8 | Telegram omnichannel | `telegram_bot.py`; optional `backend/app/bot/` | Telegram identity/link/audit jika diperlukan | Bot tidak menulis business data langsung; scenario yang sama menghasilkan decision/order status yang sama. |
| 9 | CRM/RFM/customer analytics | `analytics_ml_service.py`, customer/admin routers/UI | RFM snapshots/segment movement jika data memadai | Quantile 1–5, nama fungsi konsisten, data provenance dan customer ownership benar. |
| 10 | Churn prediction | New churn service/evaluation/report; CRM UI | `churn_predictions` jika baseline/model dipersist | Baseline rule dulu; supervised hanya dengan label/time split valid; tidak menyebut At Risk sebagai model tervalidasi. |
| 11 | BOM/inventory/SS/ROP/ROQ | inventory service, recipe/BOM repository, analytics | inventory movements/reservations/forecast snapshots jika belum ada | Quantity dapat diaudit; SS/ROP backtest; shortage quantity tidak disebut EOQ. |
| 12 | Supplier portal & PO | `supplier.py`, admin procurement UI, procurement service | PO workflow/status/idempotency/receiving/performance | Draft persistent → admin approval → send → supplier response; supplier isolation. |
| 13 | Marketing/win-back/notifications | campaign service, outbox worker, admin UI | campaign state, consent, delivery/audit jika belum ada | Draft/review/approve/queue/send; control group; tidak auto-send tanpa approval. |
| 14 | Statistics & analytics dashboard | `analytics_ml_service.py`, `AdminAnalyticsView.tsx`, admin services | evaluation/report tables bila perlu | Mean/median/std/Q1/Q3/IQR/CV/SE/CI/outlier context; simulation labels jelas. |
| 15 | Full E2E & final demo | `backend/tests/`, frontend E2E, `DEMO_SCRIPT.md`, reports | Tidak ada production reset | Allergy, paid order, kitchen→PO, CRM, omnichannel, dan ML evidence reproducible. |

### Cross-phase gate: Langflow Recovery, Connection Proof & Failover

Gate ini wajib dijalankan setelah Allergy Guard inti terpasang dan sebelum klaim Chef BOB/admin AI terintegrasi. Prompt lanjutan menyebut gate sebelum klaim Phase 4 selesai, sedangkan tabel roadmap menempatkan orkestrasi pada Phase 5; untuk menghindari klaim prematur, gate berlaku lintas Phase 4–5 dan tidak boleh dilewati oleh salah satu fase.

Scope gate yang harus direncanakan sebelum implementasi:

1. Inventaris semua caller AI: `AiPage`, `/ai/consult`, `/ai/menu-suggestion`, `langflow_service.py`, `rag_ai_service.py`, `ask_langflow`, `get_langflow_response`, `alt_menu`, dan seluruh fallback; catat input, endpoint, dependency, serta source output.
2. Validasi config Langflow (base URL, flow ID dan `endpoint_name` secara terpisah, auth/key, versi server/export, provider/model IBM/watsonx) tanpa membocorkan secret.
3. Pisahkan readiness `APP_READY`, `LANGFLOW_REACHABLE`, `FLOW_EXECUTABLE`, `MODEL_REACHABLE`, `VECTOR_RETRIEVAL_READY`, dan `LIVE_DATA_READY`.
4. Buktikan graph ingestion/query/business path, `DATA_MODE=live|simulation`, vector schema/RPC/RLS/metadata, retrieval scope/source citation, request ID, latency, serta source `langflow_live|deterministic_fallback|simulated|unavailable`.
5. Jalankan controlled failures (server off, wrong flow ID, invalid credential, model/vector failure, malformed JSON, timeout, prompt injection) dan bedakan `AI_MODE=required_langflow|allow_explicit_fallback|disabled`.
6. Pertahankan rantai safety: verified BOM → allowed menu IDs → restricted retrieval → structured IDs → backend post-filter → checkout revalidation. LLM tidak boleh override; admin AI wajib memakai live analytics dan bot/web harus melalui FastAPI yang sama.
7. Hasil wajib: `LANGFLOW_CONNECTION_AUDIT.md`, `LANGFLOW_RUNTIME_PROOF.md`, `LANGFLOW_FAILURE_TEST_REPORT.md`, serta backup repaired export tanpa secret. Jika smoke test live tidak dapat dilakukan, tulis `LIVE NOT VERIFIED`.

## 4. Urutan dependency yang tidak boleh dilompati

```text
Schema/RBAC/source-of-truth
        ↓
Verified recipe + Allergy Guard
        ↓
Adversarial safety tests
        ↓
Server order draft + payment webhook
        ↓
Paid-only KDS
        ↓
Telegram/API convergence
        ↓
BOM + inventory + forecast/SS/ROP
        ↓
Persistent PO + approval + supplier
        ↓
RFM/churn/marketing + dashboard
        ↓
E2E/demo/pilot evidence
```

RAG/BOB dapat dikerjakan paralel setelah kontrak safety dan authorized context disepakati, tetapi tidak boleh menjadi dependency bagi keputusan Allergy Guard.

## 5. Phase 1 checkpoint

### Files created/updated during Phase 0 and Phase 1

- `AUDIT.md`, `REQUIREMENTS_TRACEABILITY.md`, `IMPLEMENTATION_ROADMAP.md`
- `ARCHITECTURE_GAP_REPORT.md`, `PILOT_VALIDATION_PLAN.md`, `PILOT_AND_PARTNERSHIP_ROADMAP.md`
- `supabase/migrations/005_core_architecture.sql`
- `backend/app/repositories/supplier_repo.py`
- `backend/tests/test_supplier_rbac.py`
- `backend/app/api/deps.py`, `backend/app/api/routers/supplier.py`, `backend/app/models/enums.py`, `backend/app/repositories/supabase.py`
- `frontend/src/App.tsx`, `frontend/src/services/types.ts`

## 6. Phase 2 checkpoint

### Files created/updated during Phase 2

- `supabase/migrations/006_recipe_verification_bootstrap.sql`
- `backend/app/repositories/recipe_repo.py`, `backend/app/schemas/recipe.py`
- `backend/app/repositories/catalog_repo.py`, `backend/app/services/safety_service.py`, `backend/app/services/order_service.py`
- `backend/app/api/routers/admin.py`, `backend/app/repositories/supabase.py`, `backend/app/models/enums.py`, `backend/app/schemas/catalog.py`
- `backend/tests/test_allergy_guard_recipe_gate.py`
- `frontend/src/pages/admin/RecipeReviewPage.tsx`, `frontend/src/services/admin.ts`, `frontend/src/layouts/AdminLayout.tsx`, `frontend/src/App.tsx`

### Phase 2 acceptance evidence

- `cd backend; python -m pytest -q` — **38 passed**, 1 warning cache pytest Windows.
- `cd backend; python -m compileall -q app tests` — berhasil.
- `cd frontend; npm.cmd run build` — berhasil; ada warning bundle >500 kB.
- Supabase live read-only verification — migration check `true`, 18 recipe reviews, 18 pending, review pertama memiliki 3 components dan 3 unresolved components.
- Safety endpoint live verification — tiga opsi Senin memiliki safety level `requires_verification`, recipe status `PENDING_VERIFICATION`, dan unresolved flag `true`.

### Phase 2 belum eligible untuk ditutup

- Operator/admin masih harus memverifikasi ingredient canonical allergen code, takaran/unit, dan cross-contact risk untuk menu demo yang dipilih.
- Sebelum data recipe demo diverifikasi, jangan mendemokan menu sebagai `SAFE`, jangan mengklaim eligibility checkout, dan jangan lanjut ke klaim integrasi payment/KDS.
- Adversarial tests Phase 3 sudah dijalankan; hasil lengkap ada di `PHASE_3_ADVERSARIAL_TEST_REPORT.md`.

## 7. Phase 3 checkpoint

### Files created/updated during Phase 3

- `backend/tests/test_allergy_guard_adversarial.py`
- `backend/app/repositories/catalog_repo.py`
- `PHASE_3_ADVERSARIAL_TEST_REPORT.md`
- `LANGFLOW_CONNECTION_AUDIT.md`, `LANGFLOW_RUNTIME_PROOF.md`, `LANGFLOW_FAILURE_TEST_REPORT.md`
- `langflow/Dova_Kitchen_Chef_BOB_FIXED_SAFE.json`

### Phase 3 acceptance evidence

- `cd backend; python -m pytest -q` — **43 passed**, 1 warning cache pytest Windows.
- `cd backend; python -m compileall -q app tests` — berhasil.
- Supabase read-only query dengan canonical recipe ingredient aggregation — berhasil; 18 menu live terbaca, dan recipe existing tetap fail-closed.
- Boundary order — recipe `REQUIRES_VERIFICATION` menghasilkan `ConflictError` sebelum `insert_order`.
- Langflow `/api/v1/version` — HTTP 200; Langflow run — HTTP 403; status runtime dicatat sebagai `FLOW_EXECUTABLE=NOT VERIFIED`.

### Catatan batas Phase 3

Test Langflow masih menggunakan mocked response. Connection proof, flow execution, model/vector readiness,
fallback mode, dan prompt injection terhadap provider live masuk cross-phase Langflow gate sebelum klaim
Chef BOB/RAG terintegrasi.

## 8. Phase 4 checkpoint — in progress

### Files created/updated during Phase 4

- `backend/app/services/forecast_service.py`
- `backend/app/api/routers/admin.py`
- `backend/tests/test_forecast_service.py`
- `backend/scripts/verify_forecast_live.py`
- `backend/tests/test_forecast_live_verifier.py`
- `frontend/src/services/admin.ts`
- `frontend/src/pages/admin/AdminAnalyticsView.tsx`
- `PHASE_4_FORECAST_BACKTEST_REPORT.md`

### Phase 4 acceptance evidence

- Rolling-origin one-step backtest membandingkan `NAIVE_LAST`, `MA7`, `SEASONAL_NAIVE_7`, `LINEAR_TREND`, dan `RIDGE_LAG_7` dengan MAE/RMSE/WAPE/sMAPE.
- Query live hanya memakai order `PAID`, quantity/unit eksplisit, dan tidak memakai fallback sintetis. Quantity/unit kosong, invalid, atau unit campuran sekarang mengembalikan `ForecastUnavailable`; tidak ada `COALESCE` default quantity/unit pada jalur forecast/context.
- Snapshot endpoint hanya menulis forecast live dengan status `OK`; stale/insufficient/dependency error ditolak.
- Evidence live (2026-10-27): migration `008` berhasil diterapkan; `quantity` dan `unit` tersedia. Backtest v2 berjalan dengan 18/18 series eligible, 1.054 holdout points setelah time boundary per-series, observasi terakhir 2026-10-12, umur data global 15 hari, dan 18/18 series stale. Status `STALE_DATA`; snapshot ditolak oleh freshness write-gate.
- Forecast report kini juga menyimpan dependency evidence `paid_order_count`, `paid_order_item_count`, `invalid_quantity_item_count`, `missing_unit_item_count`, `missing_menu_id_item_count`, `latest_paid_date`, dan `latest_non_cancelled_date`; metadata query wajib lengkap, quality count harus nol, dan tidak memakai default tersembunyi. Panel admin memvalidasi quality gate tersebut.
- Quality gate quantity live mengikuti migration `008`: `NULL` atau `quantity <= 0` dihitung invalid, sehingga constraint database dan report forecast tidak memiliki definisi berbeda.
- Live recheck 16:14 WIB dengan window 90 hari: `paid_order_count=418`, `paid_order_item_count=817`, `latest_paid_date=2026-10-12`, `latest_non_cancelled_date=2026-10-12`, status tetap `STALE_DATA`; angka ini dibedakan dari total context Langflow.
- Read-only recheck terbaru 17:02 WIB: FastAPI health HTTP 200, context live `18` menu / `63` customer / `844` order context / `1.682` paid order-items context / `6` stok / `8` supplier; forecast 7d/30d tetap `STALE_DATA`, dependency `418/817`, quality `invalid_quantity_item_count=0`, `missing_unit_item_count=0`, dan `missing_menu_id_item_count=0`, latest `2026-10-12`.
- Reproducible read-only verifier v2 `backend/scripts/verify_forecast_live.py` menghasilkan `PASS` untuk context FastAPI dan graph Langflow aktif 15/12; seluruh 7 node LIVE yang memiliki `manual_json` diverifikasi menolak fallback, strict forecast v2/stale gate aktif, dan provider graph dilaporkan secret-free sebagai `Google Generative AI / gemma-4-31b-it` dengan `node_credential_present=false`. Verifier tidak menjalankan model/provider smoke (`model_smoke=NOT_ATTEMPTED`).
- Historical forecast-contract verification before the later quality-dependency and procurement tests: `cd backend; python -m pytest -q` **143 passed**, compile backend berhasil, dan `cd frontend; npm.cmd run build` berhasil.
- Latest full verification after forecast quality-dependency, Langflow no-fallback gate, transform hardening, churn backtest, supplier UI fail-closed gate, Phase 13 delivery controls, Telegram procurement gate, provider metadata verifier, missing-menu dependency gate, and explicit fixture provenance: `cd backend; python -m pytest -q` **190 passed**, compile backend berhasil, dan `cd frontend; npm.cmd run build` berhasil; Vite masih memberi warning bundle >500 kB.
- Targeted verifier-contract test addition: `cd backend; python -m pytest -q tests/test_forecast_live_verifier.py` **12 passed**; forecast service + verifier together **56 passed**.
- Historical Phase 4 checkpoint before subsequent metadata/metric tests: `cd backend; python -m pytest -q` — **103 passed**, 1 warning cache pytest Windows.
- `cd frontend; npm.cmd run build` — berhasil; masih ada warning bundle >500 kB.

### Phase 4 belum eligible untuk ditutup penuh

- Migration `008_order_item_quantity_contract.sql` sudah diterapkan dan backtest live v2 sudah dijalankan.
- Forecast operasional belum eligible ditutup karena data paid/non-cancelled terakhir 2026-10-12 (418 paid order dalam window forecast 90 hari; total context Langflow 844); stale 15 hari, sehingga perlu observasi paid yang lebih baru dan rerun freshness/write-gate.
- Recipe/BOM masih `PENDING_VERIFICATION`, sehingga forecast bahan baku belum boleh dianggap MRP final.

## 9. Phase 7 checkpoint — in progress

### Files created/updated during Phase 7

- `backend/app/schemas/payment.py`
- `backend/app/services/payment_service.py`
- `backend/app/api/routers/payments.py`
- `backend/app/api/routers/admin.py`
- `backend/app/api/routers/__init__.py`
- `backend/app/repositories/order_repo.py`
- `backend/app/services/dashboard_service.py`
- `backend/app/services/order_service.py`
- `backend/app/core/config.py`, `.env.example`
- `frontend/src/pages/admin/AdminDashboardPage.tsx`, `frontend/src/services/admin.ts`
- `frontend/src/pages/OrderPage.tsx`, `frontend/src/services/orders.ts`, `frontend/src/services/payments.ts`
- `supabase/migrations/007_payment_kitchen_workflow.sql`
- `backend/tests/test_payment_workflow.py`
- `PHASE_7_PAYMENT_KDS_REPORT.md`

### Phase 7 acceptance evidence

- HMAC signature, tamper rejection, server-owned total, customer ownership, idempotent intent, successful webhook release, and unpaid transition guard diuji.
- Checkout customer sekarang membuat `ordersService.create` dari paket/menu live lalu `paymentsService.createIntent` dengan idempotency key `web-{order_id}`; cart dikunci setelah order terbentuk dan total UI menampilkan total server.
- Langflow LIVE graph terbaru disinkronkan dengan PATCH HTTP 200; context FastAPI dan graph verifier v2 PASS, tetapi forecast tetap stale dan provider model belum stabil.
- Backend full suite terbaru **180 passed**; frontend TypeScript/production build berhasil.

### Phase 7 belum eligible untuk ditutup

- Migration 007 belum diverifikasi pada target live.
- Provider nyata dan webhook sandbox belum diuji.
- Provider response (QRIS/VA), webhook callback, dan status polling customer belum terhubung; UI sengaja hanya menampilkan intent `INITIATED`/status server dan tidak mengklaim `PAID`.

## 10. Phase 9 checkpoint — in progress

### Files created/updated during Phase 9

- `backend/app/services/rfm_service.py`
- `backend/app/services/analytics_ml_service.py`
- `backend/app/api/routers/admin.py`
- `backend/app/api/routers/customers.py`
- `backend/app/services/rag_ai_service.py`
- `frontend/src/pages/AiPage.tsx`
- `frontend/src/services/admin.ts`, `frontend/src/services/customers.ts`
- `backend/tests/test_rfm_service.py`
- `backend/tests/test_rfm_router.py`
- `PHASE_9_RFM_REPORT.md`

### Phase 9 acceptance evidence

- Query live hanya memakai order `PAID` dan bukan `CANCELLED`.
- Quantile scoring 1–5, provenance, data age, dan warnings tersedia.
- Endpoint customer tidak lagi menerima `customer_id` arbitrer atau default
  `Champions`; endpoint admin membutuhkan role admin.
- Live smoke test: `status=OK`, `data_mode=live`, `source=supabase_postgres`,
  58 customer dianalisis, segment counts tercatat di report; freshness
  `STALE_DATA`, umur data 15 hari, threshold operasional 7 hari.
- `persist_rfm_report()` dan `build_segment_movement()` memakai provenance,
  idempotent upsert, serta tidak menulis snapshot saat freshness stale.
- Endpoint admin `/analytics/rfm-crm/snapshot` dan `/analytics/rfm-crm/movement`
  tersedia; tombol UI snapshot otomatis disabled saat report stale.
- Backend test suite setelah Phase 9 follow-up: **123 passed**, compile backend
  berhasil; frontend production build berhasil.

### Phase 9 belum eligible untuk ditutup

- Snapshot/movement/cohort persistence contract sudah ada, tetapi belum eligible
  untuk write live karena data paid terbaru stale 15 hari.
- Belum ada evidence write live yang sukses; setelah transaksi paid baru,
  refresh report lalu jalankan endpoint snapshot untuk mengisi cohort history.

## 11. Phase 10 checkpoint — in progress

### Files created/updated during Phase 10

- `backend/app/services/churn_service.py`
- `backend/app/api/routers/admin.py`
- `backend/tests/test_churn_service.py`
- `frontend/src/services/admin.ts`
- `frontend/src/pages/admin/AdminAnalyticsView.tsx`
- `PHASE_10_CHURN_REPORT.md`

Phase 10 follow-up juga menambahkan temporal backtest endpoint dan panel
historical evidence; hasilnya tetap fail-closed untuk penggunaan operasional.

### Phase 10 acceptance evidence

- Baseline hanya memakai order `PAID` dan bukan `CANCELLED`.
- Cadence dihitung dari median interval antar-order per customer; threshold dan
  reason codes dikembalikan untuk audit.
- Output diberi `BASELINE_ONLY`, `model_validated=false`, dan tidak menyebut
  `risk_index` sebagai probabilitas.
- Customer dengan history kurang dari dua order diberi `UNKNOWN`.
- Backtest memakai label observasi: tidak ada order PAID non-CANCELLED selama
  horizon 30 hari setelah cutoff; cutoff tanpa future window lengkap dikeluarkan.
- Temporal train/test split, precision, recall, F1, dan ROC-AUC baseline
  tersedia dengan metrik undefined diberi `N/A`.
- Live smoke (2026-10-27): 58 customer, HIGH 22, MEDIUM 32, UNKNOWN 4,
  latest order 2026-10-12, data age 15 hari, freshness `STALE_DATA`.
- Targeted backtest/router tests: **11 passed**; full backend suite terbaru:
  **182 passed**, 1 warning cache pytest.
- `cd frontend; npm.cmd run build` — berhasil; masih ada warning bundle >500 kB.

### Phase 10 belum eligible untuk ditutup penuh

- Label observasi, horizon, temporal split, dan metrik baseline sudah ada;
  supervised model tervalidasi tetap belum ada dan tidak boleh diklaim.
- Data paid terbaru stale 15 hari, sehingga output hanya historical signal.
- Marketing masih draft/review dan belum boleh auto-send.

## 12. Phase 11 checkpoint — in progress

### Files created/updated during Phase 11

- `backend/app/services/inventory_service.py`
- `backend/app/api/routers/admin.py`
- `backend/tests/test_inventory_service.py`
- `frontend/src/services/admin.ts`
- `frontend/src/pages/admin/AdminAnalyticsView.tsx`
- `PHASE_11_INVENTORY_REPLENISHMENT_REPORT.md`

### Phase 11 acceptance evidence

- Report baru membaca recipe version terbaru, canonical ingredient, inventory stock,
  supplier lead time, dan forecast live dari source yang sama.
- BOM explosion hanya menerima recipe `VERIFIED`, component/ingredient
  `VERIFIED`, yield `portion`, dan unit massa yang dapat dikonversi.
- SS/ROP memakai variasi demand hasil forecast dan lead time supplier aktif;
  tidak ada default lead time 2 hari, konsumsi 0,18 kg, atau fixture inventory.
- ROQ/EOQ sengaja dikembalikan `UNAVAILABLE` karena ordering cost, holding cost,
  dan pack size belum tersedia. Report hanya memberi target replenishment/shortage
  jika semua gate telah lulus.
- Live smoke (2026-10-27): 18 menu published, 18 forecast menu, 18 latest recipe,
  0 BOM verified, 6 inventory items, 8 supplier mappings, forecast `STALE_DATA`
  umur 15 hari. Status report `REQUIRES_VERIFICATION`, `items=[]`, dan tidak ada
  angka SS/ROP sintetis.
- Evaluator `build_inventory_backtest()` tersedia untuk histori policy eksplisit;
  metrik stockout, fill-rate, excess-stock, dan forecast WAPE fail-closed pada
  field/unit hilang, unit campuran, gap opening/closing, histori pendek, atau
  demand nol. Output
  ditandai `data_mode=backtest`, `source=explicit_inventory_history`, dan
  `operational=false`; schema live belum memiliki histori policy SS/ROP harian.
- Validasi terbaru setelah evaluator: backend full suite **182 passed**;
  targeted inventory tests **9 passed**; frontend production build berhasil.
- Baris validasi `79 passed` di bawah adalah evidence historis sebelum perubahan
  lintas fase, bukan angka suite terbaru.
- `cd backend; python -m pytest -q` — **79 passed**, 1 warning cache pytest Windows.
- `cd frontend; npm.cmd run build` — berhasil; masih ada warning bundle >500 kB.

### Phase 11 belum eligible untuk ditutup penuh

- Semua recipe live yang diperiksa masih belum verified; operator perlu mengisi
  evidence ingredient, quantity/unit, yield, dan cross-contact melalui recipe review.
- Forecast paid/non-cancelled terbaru masih 2026-10-12 dan `STALE_DATA`; setelah
  transaksi paid live baru tersedia, rerun freshness gate sebelum menghitung SS/ROP.
- Evaluator backtest stockout/fill-rate/excess-stock sudah ada secara lokal,
  tetapi belum bisa diberi evidence live karena histori policy SS/ROP harian
  belum tersedia.
- Belum ada data yang memenuhi kontrak ROQ/EOQ: ordering cost, holding cost,
  dan pack-size masih tidak tersedia.

## 13. Phase 13 checkpoint — partial

### Files created/updated during Phase 13

- `supabase/migrations/009_marketing_campaign_workflow.sql`
- `supabase/migrations/011_marketing_delivery_controls.sql`
- `backend/app/services/marketing_service.py`
- `backend/app/schemas/marketing.py`
- `backend/app/services/churn_service.py`
- `backend/app/api/routers/admin.py`
- `backend/tests/test_marketing_service.py`
- `frontend/src/services/admin.ts`
- `PHASE_13_MARKETING_REPORT.md`

### Phase 13 acceptance evidence

- Audience tidak dapat dikirim dari client; server membentuknya dari churn
  baseline dan hanya memilih `HIGH`/`MEDIUM` dengan consent eksplisit.
- Data stale/non-live diblokir; tidak ada default consent, default audience, atau
  klaim model churn tervalidasi.
- Approval admin dan queue outbox mempunyai state serta idempotency key.
- Queue memasukkan status `PENDING`; provider delivery belum terhubung.
- Control group deterministik dipisahkan sebagai `SKIPPED`, policy
  `rate_limit_per_minute` disimpan untuk worker, dan callback delivery HMAC
  memperbarui outbox secara idempotent.
- Targeted tests **9 passed** untuk marketing; full backend terbaru **180
  passed** dan compile backend berhasil.

### Phase 13 belum eligible ditutup

- Migration 009 belum diterapkan dan diverifikasi di Supabase live.
- Churn live masih `STALE_DATA` umur 15 hari, sehingga draft live saat ini harus
  ditahan.
- Migration 011 belum diterapkan dan diverifikasi di Supabase live; provider
  worker, enforcement rate limit runtime, dan UI campaign admin penuh masih
  terbuka.

## 14. Product experience & Telegram procurement checkpoint — partial

### Files created/updated

- `frontend/src/pages/OrderPage.tsx`
- `frontend/src/components/chat/DovaChatbot.tsx`
- `frontend/src/services/types.ts`
- `telegram_bot.py`
- `backend/app/api/routers/admin.py`
- `backend/app/services/procurement_service.py`
- `backend/app/core/config.py`
- `.env.example`
- `WISHLIST.md`

### Acceptance evidence

- Web customer membaca tanggal dari `ServiceWeekOut.service_date/date_label`;
  kartu tidak lagi merender rating/kalori contoh sebagai fakta live.
- Chef BOB memiliki quick actions Menu, Passport, dan Pesanan; mode/model
  response ditampilkan di header chat.
- Draft PO Telegram hanya dapat diakses chat yang ada di
  `TELEGRAM_ADMIN_CHAT_IDS`, memakai `X-Dova-Internal-Token`, dan mencatat
  approval dengan `TELEGRAM_ADMIN_CUSTOMER_ID` agar audit/FK tetap sah.
- Tombol Telegram memisahkan `Approve` dan `Kirim ke supplier`; tombol `Minta
  edit` tidak mengubah status menjadi approved/sent.
- Targeted backend tests **14 passed**, full backend terbaru **188 passed**, Python compile berhasil, dan frontend
  build berhasil (warning bundle >500 kB tetap ada).

### Belum eligible ditutup

- `TELEGRAM_ADMIN_CHAT_IDS` dan `TELEGRAM_ADMIN_CUSTOMER_ID` belum diverifikasi
  dari environment operator, sehingga inbox admin Telegram belum diklaim live.
- Form edit detail PO masih dilakukan di dashboard; tombol Telegram mencatat
  permintaan edit dan tidak mengubah quantity secara langsung.
- Metadata nutrisi/BOM gram/tag belum menjadi kontrak live Supabase; UI hanya
  menampilkan field enriched bila backend benar-benar mengirimkannya.

## 9. Historical Phase 1 evidence

### Database changes

Migration `005_core_architecture.sql` sudah dibuat setelah schema inventory dan mapping, lalu diterapkan pada target Supabase yang terhubung dan diverifikasi dengan introspection read-only.

### Test plan

Test yang sudah dijalankan setelah perubahan Phase 1:

- `cd backend; python -m pytest -q` — **35 passed**, 1 warning cache pytest Windows.
- `cd backend; python -m compileall -q app tests` — berhasil.
- `cd frontend; npm.cmd run build` — berhasil; ada warning bundle >500 kB.
- Migration SQL — diterapkan dan diverifikasi pada target Supabase yang terhubung; seluruh tabel Phase 1 dan RLS terdeteksi.
- Live smoke test `GET /api/health` — **HTTP 200**, `db_connected=true`, baseline table counts terbaca, `demo_mode=false`.
- Test lanjutan tetap mengikuti manifest test ID dari `REQUIREMENTS_TRACEABILITY.md`.
- Tambahkan T-LF-01..24 untuk connection proof, readiness, vector/live-data contract, failover, provenance, dan AI mode sebelum Phase 5 dinyatakan selesai.

### Risiko utama

- Migration terlalu cepat dapat membuat dua schema/order model hidup bersamaan.
- Migrasi Astra tanpa rekonsiliasi dapat memindahkan profile/order dengan schema drift.
- Perubahan safety sebelum recipe provenance tersedia dapat memberi false confidence.
- Payment/KDS yang dikerjakan terpisah dapat tetap memperbolehkan order unpaid masuk board.
- Langflow export dapat disalahartikan sebagai live integration.
- Fallback RAG dapat membuat aplikasi tampak berhasil saat Langflow/model/vector/live data tidak tersedia; setiap demo harus menampilkan source dan readiness.
- Migration 005 dapat gagal pada database yang memiliki role invalid atau data ingredient kosong; jalankan pada staging/backup dan lakukan schema introspection sebelum production.

## 10. Approval yang diperlukan

Checkpoint berikutnya: verifikasi recipe menu demo melalui `/admin/recipes`, lalu lanjut ke **PHASE 4 — DEMAND FORECAST ML & BACKTEST**. Jangan menyebut Chef BOB/RAG live sebelum cross-phase Langflow recovery dan connection proof selesai.
# V4 Phase 0 Re-audit Addendum — 2026-10-30

This addendum supersedes older checkpoint language when it conflicts with the
current repository/runtime. The master prompt explicitly requires Phase 0 only;
no production code edits are authorized before the user replies `lanjut`.

## Current finding

- Local API health: PostgreSQL/Supabase connection and basic counts are live;
  the same response also reports Astra connected. This is not yet a source-of-
  truth or backup/restore proof.
- Langflow health: version endpoint reachable at HTTP 200, version `1.12.3`.
  Flow execution, model reachability, vector retrieval, and provenance remain
  unproven.
- Core working-tree features already present include recipe verification, AI
  recipe draft, payment boundary, KDS routes, inventory consumption, forecast,
  supplier sourcing, procurement approval, analytics, and marketing controls.
- Major gaps remain for three meal slots, recipe document import, nutrition
  source engine, production batch/MRP separation, lot/FEFO barcode ledger,
  supplier billing/3-way match, courier lifecycle, three Telegram bots, and
  Langflow explicit readiness/fallback proof.

## Phase 1 plan — requires approval before edits

### Planned files/functions

- `backend/app/core/config.py`: add/read explicit AI readiness and database
  baseline settings without exposing secrets.
- `backend/app/services/langflow_service.py`: distinguish connectivity from
  executable-flow success, attach redacted trace metadata, and make fallback
  state explicit.
- `backend/app/api/routers/health.py` and/or a small readiness service: expose
  `CONNECTED`, `DEGRADED`, `OFFLINE`, `MISCONFIGURED`, and `MOCK` states.
- `backend/app/api/routers/ai.py`: return trace/readiness metadata while keeping
  Allergy Guard and transaction decisions deterministic.
- `backend/tests/test_langflow_service.py` and new readiness/ON-OFF tests:
  mocked success, timeout, invalid response, disabled mode, explicit fallback,
  and no-secret logging.
- `LANGFLOW_CONNECTION_AUDIT.md` / `LANGFLOW_RUNTIME_PROOF.md`: update only
  with observed evidence, not claims inferred from JSON exports.

### Planned database/read-only work

- Verify migration status and schema objects in staging/read-only mode.
- Verify whether `documents`, `match_documents`, vector metadata filters, and
  RAG permissions actually exist.
- Do not apply migrations, alter data, migrate Astra, or choose a new database
  target during Phase 1 without a backup and explicit approval.

### Phase 1 risks

- The running service may use environment values different from `.env.example`.
- A reachable Langflow version endpoint can coexist with a broken flow/model.
- Existing working-tree changes are broad and dirty; edits must be isolated and
  unrelated changes must be preserved.
- A database migration can create a second schema/order source if applied before
  reconciliation.

### Phase 1 acceptance evidence

- Redacted health/readiness output with state, timestamp, flow ID, trace ID,
  latency, and reason code.
- Langflow ON/OFF smoke tests and explicit fallback output.
- Read-only schema/migration report and backup/restore gate status.
- Full backend tests and frontend build with no secret values in output.

After Phase 1 implementation and verification, stop again for approval before
Phase 2.

## Phase 1 completion checkpoint — 2026-10-30

Phase 1 selesai secara lokal. Supabase/PostgreSQL kini menjadi source of truth
eksplisit; `astra_connected` tidak lagi alias dari koneksi database dan selalu
dikembalikan `false` dengan state `OFFLINE_LEGACY`. Health juga memverifikasi
status migration secara read-only. Langflow memiliki readiness state dan probe
flow opt-in. Runtime lokal membuktikan platform Langflow reachable pada versi
`1.12.3`, tetapi probe flow terakhir mengembalikan HTTP 500 sehingga flow/model
belum stabil dan tidak diklaim live.

Bukti lengkap ada di `PHASE_1_LANGFLOW_DB_BASELINE_REPORT.md`. Backend test:
200 passed; frontend build berhasil. Tidak ada migrasi Astra atau migration
production yang dijalankan.

Checkpoint berikutnya menunggu approval `lanjut` sebelum Phase 2: import
recipe/material document dan nutrition/BOM draft review.

