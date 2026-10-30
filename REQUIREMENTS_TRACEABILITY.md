# Requirements Traceability — DovaGenome

> **V4 Phase 0 re-audit addendum — 2026-10-30:** This file contains historical
> phase notes below. The current V4 source of truth is the addendum at the end
> of this file plus `ERP_GAP_ANALYSIS.md`; historical claims are not treated as
> proof of current runtime state.

Status: **PHASE 0 — selesai pada level inspeksi dan perencanaan; belum ada implementasi kode dari fase berikutnya.**  
Tanggal: 2026-10-26 (historical Phase 0 baseline)

Latest continuation checkpoint 2026-10-30: Phase 10 now has separate Customer,
Admin, and Supplier Telegram thin-client entrypoints with Supabase-backed
FastAPI bridge, tenant/RBAC checks, PO actions, supplier receipt/invoice
commands, and idempotent daily stock-alert queueing. Provider workers and live
bot tokens remain external gates.

Current checkpoint (continuation 2026-10-30): Phases 2, 7, 8, 11, and the
isolated Phase 15 acceptance demo now have local implementations. Supabase/
PostgreSQL is the active source of truth; Astra is `OFFLINE_LEGACY`. Migrations
013–017 remain behind the backup/restore gate, recipe verification is still an
operator action, and live payment/Langflow/provider evidence is not claimed.

## 1. Sumber yang benar-benar tersedia

| Source ID | File | Status pemeriksaan | Catatan |
|---|---|---|---|
| S1 | `AUDIT.md` | Diperiksa | Audit runtime terbaru yang dibuat dari inspeksi repository. |
| S2 | `feedback/DovaGenome - Clara - Josua.pdf` | Diperiksa, 3 halaman | Feedback membahas validasi masalah, fokus pilot, recipe UI, Allergy Guard, forecast, webhook, dan konsistensi omnichannel. |
| S3 | `docs/submission/DovaGenome_Pitch_Deck.pdf` | Diperiksa, 10 halaman/slide | Pitch deck tersedia dalam PDF, bukan file `.pptx` dengan nama yang disebut prompt. |
| S4 | `langflow/Dova Kitchen — CRM Dietary RFM Forecast Supply Chain Marketing (2).json` | Diperiksa | Export flow utama. |
| S5 | `docs/langflow/original.json` | Diperiksa | Export/artefak Langflow lain; hash berbeda dari S4. Keduanya bukan bukti flow sedang aktif di server. |
| S6 | `docs/audit/00-inventory.md` sampai `04-plan.md`, `README.md`, `BOB.md`, `docs/decisions.md` | Diperiksa secara selektif | Dokumentasi arsitektur dan rencana; sebagian berisi target yang belum sama dengan runtime. |
| S7 | `DovaGenome-Technical-Deck.pptx` | **Tidak ditemukan** | Tidak ada file `.pptx` technical deck pada repository. Requirement yang hanya bersumber dari deck ini belum dapat diverifikasi terhadap slide. |
| S8 | `dova-genomepitch-deck.pptx` | **Tidak ditemukan dengan nama tersebut** | Padanan PDF S3 tersedia dan digunakan sebagai sumber yang dapat diperiksa. |

## 2. Konflik sumber dan keputusan traceability

| Konflik | Evidence | Keputusan Phase 0 |
|---|---|---|
| 3 stakeholder bisnis vs 4 role teknis | S2 p1–2 dan master prompt: Customer, Dova Kitchen/operasional, Supplier; role Customer, Admin, Kitchen, Supplier | Dipertahankan. Admin dan Kitchen adalah dua role teknis dalam stakeholder operasional Dova Kitchen. |
| “SAFE” vs larangan menjamin bebas alergen | `SafetyLevel.SAFE` dan UI memakai status safe; S2 p3 serta S3 slide 6/10 menuntut guard deterministik tanpa klaim medis | Target terminology: `ELIGIBLE`, `BLOCKED`, `REQUIRES_VERIFICATION`. `ELIGIBLE` berarti lolos berdasarkan data yang terverifikasi, bukan jaminan bebas alergen. |
| 1.000 transaksi riil vs 250 customer/3.859 order simulasi | S3 slide 1/4 menyebut 1.000 transaksi riil; S2 p3 menyebut 250/3.859 sebagai artefak generator; `analytics_ml_service.py` memiliki fallback 1.000 rows dan nilai hardcoded | Semua angka diberi label **belum tervalidasi** sampai provenance dataset dan perhitungan ulang tersedia. Tidak boleh dipakai sebagai bukti dampak. |
| Custom Langflow node dianggap sudah terkoneksi | S4/S5 memuat node `DovaDietaryCheck`, `DovaRFM`, `DovaForecast`, `DovaInventory`, `DovaSupplierPO`, `DovaMarketing`; runtime FastAPI memakai `LangflowService` dan fallback Python | Export membuktikan isi flow, bukan deployment/live wiring. Integrasi harus dibuktikan dengan contract/live smoke test pada fase 5. |
| Astra vs Supabase | `telegram_bot.py`/`data.py` memakai Astra; `backend/app/repositories/*.py` memakai Supabase/Postgres | Target tunggal adalah FastAPI → Supabase. Astra tidak dihapus sebelum migrasi dan rekonsiliasi data divalidasi. |

### 2.1 Tambahan audit Langflow dari prompt lanjutan

Pemeriksaan statis terhadap export dan runtime menemukan fakta berikut; ini bukan bukti server Langflow sedang hidup:

- Export `langflow/Dova Kitchen — CRM Dietary RFM Forecast Supply Chain Marketing (2).json` berisi 23 node dan 20 edge; `docs/langflow/original.json` berisi 23 node dan 19 edge.
- `DovaDataSource` pada export utama memiliki `use_sample=True`.
- Node Supabase Vector Store pada export mereferensikan tabel `documents` dan RPC `match_documents`; tabel/RPC tersebut tidak ditemukan pada migration repo yang diperiksa.
- `LangflowService.ask` kini default `AI_MODE=required_langflow`; `generate_rag_answer` hanya dipanggil pada `AI_MODE=allow_explicit_fallback` dan response diberi label `explicit_fallback`. Response aplikasi yang degraded tidak dihitung sebagai bukti Langflow live.
- `LangflowService.health` hanya membuktikan endpoint `/api/v1/version` dapat dijangkau; belum membuktikan flow, model, vector retrieval, atau live data siap.
- `Settings.langflow_run_url` membentuk URL dari `LANGFLOW_FLOW_ID`; export juga memiliki `endpoint_name`, tetapi tidak ditemukan validasi runtime bahwa keduanya merujuk endpoint yang sama.

Subfase wajib **Langflow Recovery, Connection Proof & Failover** harus menjadi cross-phase gate setelah Allergy Guard inti dan sebelum klaim Chef BOB/admin AI terintegrasi. Prompt lanjutan menyebut gate ini sebelum klaim Phase 4 selesai, sementara roadmap fitur menempatkan orkestrasi pada Phase 5; keputusan audit yang aman adalah menerapkannya sebagai gate lintas fase yang berlaku sebelum klaim AI apa pun.

## 3. Matriks requirement terhadap implementasi aktual

Status: `implemented` = bukti runtime cukup; `partial` = sebagian ada atau jalur tidak konsisten; `missing` = tidak ditemukan pada runtime; `artifact-only` = hanya ada di export/dokumentasi.

| Requirement ID | Dokumen sumber + slide/halaman | Stakeholder | Fitur | Lokasi kode aktual | Status | Perubahan yang diperlukan | Test ID | Bukti hasil pengujian |
|---|---|---|---|---|---|---|---|---|
| R-01 | S2 p1–2; S3 slide 3, 8 | Semua | Empat role/portal | `frontend/src/App.tsx`; `frontend/src/pages/`; `backend/app/api/routers/` | partial | Lengkapi role Supplier di auth/dependency dan pisahkan Admin vs Kitchen secara konsisten. | T-RBAC-01 | Belum dieksekusi Phase 0. |
| R-02 | Master prompt E; S3 slide 8/10 | Semua | Satu backend dan satu source of truth | Backend Supabase: `backend/app/repositories/supabase.py`; bot Astra: `telegram_bot.py`, `data.py` | partial | Migrasikan bot menjadi thin client FastAPI; rencanakan migrasi Astra → Supabase. | T-OMNI-01 | Belum dieksekusi. |
| R-03 | Master prompt Phase 1–2; S2 p2 | Customer | Dietary Passport server-side | `passport_service.py`; `customers.py`; `supabase/migrations/001_schema.sql` | partial | Tambahkan riwayat perubahan, klasifikasi allergy/intolerance/preference/medical, dan provenance. Bot belum memakai passport server sebagai sumber utama. | T-PASS-01 | Belum dieksekusi. |
| R-04 | Master prompt Phase 1–2; S2 p2–3 | Customer/Kitchen/Admin | Ingredient-allergen foundation | `menus`, `menu_ingredients` di `001_schema.sql`; `catalog_repo.py` | partial | Tambahkan ingredient identity, sub-ingredient/nested BOM, mapping terstruktur, verification status, source, verifier, timestamp, dan cross-contact. | T-RECIPE-01 | Belum dieksekusi. |
| R-05 | S2 p3; S3 slide 6/10 | Customer/Kitchen | Deterministic Allergy Guard | `safety_service.py`: `resolve_exclusions`, `check_menu`, `build_report`; `order_service.py:create_order` | partial | Ubah fail-closed untuk data unknown dan `REQUIRES_VERIFICATION`; gunakan guard yang sama di katalog, cart, checkout, order, kitchen. | T-ALLERGY-01..20 | Existing unit tests terbatas pada `_detect_codes`; adversarial suite belum ada. |
| R-06 | Master prompt D3/D4; S2 p3 | Customer | LLM tidak boleh mengubah keputusan alergen | `ai.py:menu_suggestion`; `langflow_service.py`; `telegram_bot.py:alt_menu` | partial | Wajib structured output + backend post-validation; jangan menerima menu baru/blocked dari LLM; Telegram harus memakai API guard. | T-AI-SAFE-01 | Belum dieksekusi. |
| R-07 | S2 p2; Master prompt Phase 2 | Kitchen/Admin | Recipe editor dan verification workflow | Tidak ditemukan UI recipe versioning atau tabel `ingredients`, `recipe_versions`, verification events | missing | Bangun schema minimal tanpa duplikasi, UI edit/approve terpisah, versioning, audit log, dan re-verification trigger. | T-RECIPE-02 | Belum dieksekusi. |
| R-08 | Master prompt Phase 6; S2 p2–3 | Customer | Web checkout memakai API | `order_service.py:create_order`; `OrderPage.tsx:handleBeginCheckout`; `orders.ts`; `payments.ts` | partial | Cart sekarang mengirim paket/menu live ke `ordersService.create`, lalu membuat payment intent server; total dan safety tetap server-owned. E2E browser dan draft persistence masih terbuka. | T-ORDER-01 | TypeScript/production build berhasil; runtime checkout tertahan fail-closed bila katalog/package live atau recipe verification belum memenuhi gate. |
| R-09 | Master prompt Phase 7; S2 p3 | Customer/Admin | Payment intent, expiry, verified idempotent webhook | `payment_service.py`; `payments.py`; `payments.ts`; `007_payment_kitchen_workflow.sql` | partial | Payment/payment_attempt, provider-neutral intent, HMAC signature verification, 10-minute expiry, idempotency, webhook endpoint, dan audit trail tersedia; provider adapter/sandbox dan migration live masih terbuka. | T-PAY-01..06 | Backend full suite 177 passed; frontend checkout memanggil intent dengan `web-{order_id}`; provider nyata/webhook runtime belum diuji. |
| R-10 | Master prompt Phase 7; S2 p3 | Kitchen | No pay, no cook | `kitchen.py`; `dashboard_service.py`; `order_repo.py:fetch_active_orders`; `payment_service.py` | partial | Board/transition/ticket release hanya untuk order `PAID` dari webhook atau manual admin tercatat; live KDS/provider E2E belum diuji. | T-KDS-01..05 | Backend contract tests lulus; unpaid transition ditolak; migration live dan provider callback masih terbuka. |
| R-11 | Master prompt Phase 8; S2 p3 | Customer/Operasional | Telegram thin client | `telegram_bot.py:create_weekly_order`, `check_menu_allergy_warning`, direct Astra I/O | missing | Hapus business write path bot secara bertahap; gunakan JWT/link identity dan endpoint FastAPI yang sama. | T-OMNI-02..05 | Belum dieksekusi. |
| R-12 | S3 slide 5–6; S4/S5 | Customer/Admin | Chef BOB + RAG | `rag_ai_service.py`; `langflow_service.py`; `ai.py`; `AiPage.tsx` | partial | Sediakan authorized context builder, structured contract, PII scoping, post-validation, dan bukti live integration. Tabel `documents` belum ada di migrations. | T-RAG-01..05 | Belum ada live/contract test. |
| R-13 | Master prompt Phase 9; S2 p3 | Admin | RFM konsisten | `rfm_service.py:build_rfm_report/get_customer_rfm/persist_rfm_report/build_segment_movement`; `admin.py:get_rfm_crm_segments/persist_rfm_snapshot/get_rfm_segment_movement`; `customers.py:get_customer_rfm` | partial | Strict live quantile 1–5, paid/non-cancelled cohort, provenance, ownership, freshness gate, idempotent snapshot, dan movement contract tersedia; write live menunggu data fresh. | T-RFM-01..04 | 123 unit tests passed; live read-only `OK`, 58 customer, source `supabase_postgres`, latest order 2026-10-12, umur 15 hari, `freshness_status=STALE_DATA`, threshold 7 hari. |
| R-14 | Master prompt Phase 10; S2 p3; S4/S5 | Admin | Churn risk/model | `churn_service.py:build_churn_report`, `build_churn_backtest`; `admin.py:get_churn_risk`, `get_churn_backtest`; `AdminAnalyticsView.tsx` | partial | Baseline rule-based live dengan cadence, reason codes, freshness, dan provenance tersedia; backtest label observasi 30 hari dan temporal split tersedia; supervised model tetap ditahan. | T-CHURN-01..06 | Targeted churn/backtest/router tests 11 passed; full backend suite 177 passed; live baseline smoke `BASELINE_ONLY`, 58 customer, HIGH 22/MEDIUM 32/UNKNOWN 4, source `supabase_postgres`, latest order 2026-10-12, freshness `STALE_DATA`; backtest live perlu dijalankan melalui API admin yang punya akses DB. |
| R-15 | Master prompt Phase 4; S2 p3; S3 slide 7 | Admin/Kitchen | Demand forecast + backtest | `forecast_service.py`, `langflow_context_service.py`, `backend/scripts/verify_forecast_live.py`, `GET/POST /admin/analytics/forecast-backtest` | partial | Strict v2 membandingkan naive/MA7/seasonal/linear/RIDGE_LAG_7 dengan rolling-origin, WAPE/MAE/RMSE/sMAPE, interval, provenance, unit consistency, per-series freshness gate, per-series time boundary, global completeness gate, strict quantity/unit validation, observation-shape/temporal validation, undefined-metric labeling, dependency metadata dan quality-count validation untuk setiap live status, source/version gate, strict CRM/RFM context fields, context truncation gate, strict snapshot object/row validation, dan snapshot gate; live backtest berjalan setelah migration `008`; Langflow context dan node forecast LIVE memakai report v2 yang sama; panel admin menampilkan write-gate, paid dependency metadata, quality gate, dan jumlah series stale; route API, persistence provenance, dan verifier read-only diuji. | T-FORECAST-01..07 | Forecast service + verifier tests 56 passed; Langflow live context/flow/service tests 27 passed; full backend suite 190 passed. Live recheck HTTP 200: 18/18 series eligible, 1.054 holdout setelah time boundary per-series, observasi terakhir 2026-10-12, umur data global 15 hari, 18/18 series stale, status `STALE_DATA`, quality counts quantity/unit/menu-id `0/0/0`, sehingga snapshot operasional ditolak. Forecast window 90 hari: 418 paid orders dan 817 paid order-items. Context live: 844 paid orders, 1.682 paid order-items, 63 customer; forecast 7d/30d `STALE_DATA`; graph Langflow aktif 15/12 dan seluruh 7 node manual-state terverifikasi fail-closed setelah PATCH HTTP 200; trace sukses sebelumnya `READY` tetapi latency 121,8 detik dan provider quota belum stabil. |
| R-16 | Master prompt Phase 11; S2 p2–3; S3 slide 7 | Kitchen/Admin | BOM explosion | `recipe_versions`, `recipe_components`, `inventory_service.py` | partial | Quantity recipe, unit conversion, yield `portion`, canonical ingredient, unresolved nested BOM, dan verification gate sudah memiliki runtime contract; waste/substitution/reservation belum selesai. | T-BOM-01..08 | 103 unit tests total; live 18 latest recipe, 0 BOM siap, 18 unresolved; report menahan output. |
| R-17 | Master prompt Phase 11; S2 p3; S3 slide 7 | Kitchen/Admin | Safety stock dan ROP | `inventory_service.py:build_live_inventory_replenishment_report`; `GET /admin/analytics/inventory-replenishment` | partial | SS/ROP hanya memakai forecast fresh, BOM verified, unit massa, stok canonical, dan lead time supplier; tidak ada default/fallback. Backtest stockout/fill-rate/excess stock masih terbuka. | T-INVENTORY-01..05 | Live report `REQUIRES_VERIFICATION`, forecast `STALE_DATA` 15 hari, 0 item SS/ROP dikeluarkan; smoke: 6 inventory items dan 8 supplier mappings. |
| R-18 | Master prompt Phase 11 | Admin | ROQ/EOQ | `inventory_service.py` readiness contract | partial | Target replenishment/shortage dapat dihitung setelah gate; ROQ/EOQ sengaja `UNAVAILABLE` sampai ordering cost, holding cost, pack size, dan constraints tersedia. | T-INVENTORY-06 | Live `roq.status=UNAVAILABLE`; tidak ada PO otomatis. |
| R-19 | Master prompt Phase 12; S4/S5 | Admin/Supplier | Supplier scoring | `supplier_sourcing_service.py`; `GET /admin/analytics/supplier-sourcing` | partial | Ranking backend configurable memakai harga, lead time, dan rating yang tersedia; incomplete candidates ditolak tanpa default. Supplier performance history belum tersedia. | T-SUP-01..03 | Full suite 177 passed; live report tetap menunggu inventory/BOM/forecast `OK`. |
| R-20 | Master prompt Phase 12; S2 p2; S3 slide 7/10 | Admin/Supplier | Draft PO → approval → supplier | `procurement_service.py`; `purchase_orders`/`po_items`; `010_procurement_workflow.sql`; `supplier.py:list_pos`, `respond_po`; admin procurement routes | partial | Draft live-only dipersist atomik dengan idempotency key, approval admin, dan queue outbox `PENDING`; supplier tenant isolation serta response status mapping tersedia. Migration live, provider delivery callback, receiving/stock transaction, dan performance history masih terbuka. | T-PO-01..08 | Saat inventory report bukan `OK`, persist route tidak membuat PO dan sourcing tetap `BLOCKED`; full suite 177 passed. |
| R-21 | Master prompt Phase 13; S2 p1–3 | Admin/Customer | Marketing draft, consent, approval, control group | `marketing_service.py`; `admin.py` marketing/delivery webhook; migrations `009`/`011`; `frontend/src/services/admin.ts` | partial | Campaign state machine, eligibility/consent, deterministic control group, idempotent outbox, HMAC delivery callback, dan audit status tersedia lokal; provider worker, runtime rate-limit enforcement, migration live, dan UI penuh masih terbuka. | T-MKT-01..05 | Marketing targeted 9 passed; full backend 180 passed. Live draft tetap ditahan karena churn `STALE_DATA` dan migration belum diverifikasi. |
| R-22 | Master prompt Phase 14; S3 slide 4/9 | Admin | Statistik/dashboard | `analytics_ml_service.py:calculate_descriptive_statistics`; admin analytics UI | partial | Lengkapi CI, standard error, CV, Q1/Q3/IQR/outlier context, freshness, source labels, dan pisahkan demo dari production. | T-ANALYTICS-01..04 | Belum ada report perhitungan ulang atas dataset terverifikasi. |
| R-23 | Master prompt D2; S2 p3 | Semua | Auth, RBAC, PII, audit log | `auth_service.py`, `api/deps.py`, migration `audit_log`; `supplier.py` tanpa dependency role | partial | Wajibkan dependency role di supplier/admin-sensitive routes; audit semua operasi sensitif; batasi retrieval/log PII. | T-SEC-01..08 | Existing test hanya beberapa endpoint unauthenticated. |
| R-24 | Master prompt D3; S2 p1–3 | Semua | Label simulation/target/backtest/pilot | `analytics_ml_service.py` fallback/hardcoded values; admin sample data | missing | Tambahkan provenance/status label pada data dan dashboard; jangan klaim dampak bisnis/medis tanpa pilot. | T-DATA-01..03 | Belum ada evidence labeling end-to-end. |
| R-25 | Master prompt Phase 15; S2 p3 | Semua | E2E allergy → payment → kitchen → PO → CRM | `backend/tests/` hanya baseline repository/characterization; frontend belum punya test config | missing | Tambahkan pytest API/integration, frontend interaction, mocked Langflow/payment, DB integration, dan E2E demo fixture. | T-E2E-01..06 | Belum dieksekusi. |
| R-26 | Prompt lanjutan E-LF.1–3 | Customer/Admin/Telegram | Inventory AI caller, config, dan readiness terpisah | `AiPage.tsx`, `ai.py`, `langflow_service.py`, `rag_ai_service.py`, `telegram_bot.py`, `LANGFLOW_RUNTIME_PROOF.md` | partial | Readiness dan dependency sudah diaudit tanpa secret; `AI_MODE` sudah eksplisit. Endpoint readiness granular dan seluruh caller omnichannel masih perlu disatukan. | T-LF-01..04 | Server 1.12.3 reachable; graph/model/context terbukti sekali; vector belum configured; quota provider belum stabil. |
| R-27 | Prompt lanjutan E-LF.4–7 | Customer/Admin | Graph execution, live/simulation split, vector contract, provenance | Export memiliki sample mode; `documents`/`match_documents` belum ada di migrations; metadata request/response belum membuktikan source | missing | Uji graph ingestion/query/business path; `DATA_MODE=live|simulation`; validasi schema/vector/RLS/metadata/retrieval; request ID, source, latency, dan proof of call. | T-LF-05..10 | Belum dieksekusi. |
| R-28 | Prompt lanjutan E-LF.8–10 | Semua | Failover, AI mode, Allergy Guard boundary | `langflow_service.py`; `AI_MODE` validator; `LANGFLOW_FAILURE_TEST_REPORT.md` | partial | Mode explicit dan no-hidden-fallback sudah diimplementasikan; controlled failure provider/JSON/timeout/vector/injection belum lengkap, post-filter menu terstruktur, dan checkout revalidasi masih terbuka. | T-LF-11..18; T-AI-SAFE-01 | 103 unit tests; `required_langflow`/`allow_explicit_fallback`/`disabled` dan contract node forecast LIVE diuji. Live graph/model terbukti sekali, tetapi provider quota belum stabil. |
| R-29 | Prompt lanjutan E-LF.11–12 | Admin/Telegram | Admin AI memakai live analytics; web/bot satu FastAPI path | `telegram_bot.py:get_langflow_response`; `POST /api/ai/consult`; `langflow_context_service.py` | partial | Bot sudah menjadi thin client FastAPI dan tidak memiliki RAG fallback lokal; convergence order/profile dan E2E omnichannel masih perlu dibuktikan. | T-LF-19..21; T-OMNI-02..05 | Direct Langflow/RAG fallback di bot dihapus; backend `AI_MODE` menjadi sumber keputusan. |
| R-30 | Prompt lanjutan E-LF.13–14 | Semua | Live smoke test, failure report, repaired export | Tidak ada report runtime proof/failure test atau backup export repaired yang diverifikasi di repo | missing | Jika live test tidak mungkin, tulis `LIVE NOT VERIFIED`; hasilkan `LANGFLOW_CONNECTION_AUDIT.md`, `LANGFLOW_RUNTIME_PROOF.md`, `LANGFLOW_FAILURE_TEST_REPORT.md`, dan backup export tanpa secrets. | T-LF-22..24 | Belum dieksekusi. |

## 4. Bukti test yang tersedia saat Phase 0

- Backend test files ditemukan: `backend/tests/test_characterization.py`, `backend/tests/test_repositories.py`, dan fixture `backend/conftest.py`.
- Test yang ada mencakup health/catalog/auth baseline, repository normalization, ID generation, catalog keyword detection, customer repository, DSN, dan konstanta domain.
- Tidak ditemukan test adversarial Allergy Guard, payment idempotency/webhook, RBAC supplier isolation, Langflow contract, forecast backtest, BOM, PO E2E, frontend, atau omnichannel consistency.
- Tidak ditemukan bukti live Langflow, readiness terpisah, controlled-failure test, request-ID/source provenance, atau pemisahan `DATA_MODE`/`AI_MODE`.
- **Tidak ada hasil test baru yang diklaim oleh dokumen ini.** Test Phase 0 tidak dieksekusi karena scope fase ini adalah inspeksi dan perencanaan.

## 5. Acceptance gate sebelum Phase 1

Phase 1 hanya boleh dimulai setelah approval eksplisit atas:

1. Prioritas keselamatan: Allergy Guard dan data recipe terverifikasi mendahului AI/purchasing.
2. Target arsitektur: Telegram dan web menjadi client, FastAPI menjadi business boundary, Supabase menjadi source of truth.
3. Terminology: tidak menggunakan “aman” sebagai jaminan; gunakan hasil verifikasi dan uncertainty.
4. Status requirement `partial/missing` di atas dianggap baseline yang akan diperbaiki, bukan klaim fitur sudah selesai.
5. Sebelum klaim Chef BOB/admin AI terintegrasi: semua acceptance E-LF harus lulus, atau status harus tetap `LIVE NOT VERIFIED`/`unavailable`; export JSON dan text fallback tidak boleh dihitung sebagai proof live.

## 6. V4 current-state addendum — 2026-10-30

The V4 master prompt was re-audited against the current working tree and local
runtime. The health endpoint reports `db_connected=true`, basic counts of 3
packages, 8 allergens, 18 menus, 66 customers, and 884 orders, and also reports
an Astra connection. Langflow `/api/health/langflow` responds HTTP 200 with
version `1.12.3`. These are connectivity observations only; they do not prove
source-of-truth parity, backup restore, flow execution, model/vector
readiness, or production migration state.

The current V4 mapping and open gaps are maintained in `ERP_GAP_ANALYSIS.md`.
The database gate is maintained in `DB_RECOVERY_PLAN.md`. The planned Phase 1
file/function changes are at the top of `IMPLEMENTATION_ROADMAP.md`.

Current continuation note (2026-10-30): `meal_slot` is now a first-class order
field for `breakfast`, `lunch`, and `dinner`. A customer may submit multiple
menu lines for the same service day when each line uses a distinct meal slot.
The customer cart, order create/update persistence, response enrichment, and
PAID production-batch planner preserve the slot. Legacy rows without the
extension column are interpreted as lunch only. See
`PHASE_3_MEAL_SLOT_REPORT.md`; the full local suite is **222 passed**.

Phase 0 is complete for this turn. No production code edit was performed for
the V4 audit. Continue only after explicit user approval with `lanjut`.

## Phase 1 checkpoint — 2026-10-30

Supabase/PostgreSQL is the active source of truth and Astra is explicitly
`OFFLINE_LEGACY`. Langflow now returns readiness states and trace-safe probe
metadata; the local platform check is connected, but the latest flow probe is
`DEGRADED` with HTTP 500. Backend tests passed 200/200 and the frontend build
passed. Phase 2 remains gated on the next `lanjut` approval.
