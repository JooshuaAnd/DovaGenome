# DovaGenome ERP Katering — Phase 0 Gap Analysis V4

Tanggal audit: 2026-10-30  
Scope: Phase 0 audit ditambah Phase 1 connectivity baseline. Perubahan Phase 1
dibatasi pada health/readiness contract dan tidak menjalankan migrasi produksi.

## Cara membaca dokumen

`Modul SAP01 Update.pdf` diperlakukan sebagai inspirasi konseptual untuk integrasi master data, sales/order, procurement, production, goods receipt/issue, dan approval. Dokumen tersebut bukan spesifikasi produk DovaGenome dan tidak menjadi sumber data menu, harga, UI, atau klaim operasional.

`DovaGenome_Codex_Master_Prompt_ERP_Katering_v4.md` adalah requirement utama.
Instruksi fase dan checkpoint di dalamnya tetap diikuti; Phase 1 sudah
diselesaikan setelah approval dan Phase 2 masih menunggu `lanjut`.

## Bukti runtime yang tersedia

- `GET http://localhost:8000/api/health` berhasil pada audit ini: `db_connected=true`, `supabase_connected=true`, `database_source=supabase_postgres`, `migration_status=verified`, dan `astra_connected=false` dengan state `OFFLINE_LEGACY`.
- `GET http://localhost:8000/api/health/langflow` berhasil: Langflow reachable, HTTP 200, versi `1.12.3`.
- Bukti di atas hanya membuktikan konektivitas dan query health. Belum membuktikan Langflow flow/model/vector retrieval live, backup restore, atau kesesuaian semua migration.
- `.env` memiliki konfigurasi Supabase, Astra, Langflow, Telegram, auth, dan IBM BOB. Nilai secret tidak dibaca atau dicatat di dokumen ini.
- Repository memakai FastAPI + PostgreSQL/Supabase melalui `backend/app/repositories/supabase.py`, React/Vite melalui `frontend/src`, dan artefak Langflow JSON di `docs/langflow/original.json` serta `langflow/`.

## Current vs target

| Domain requirement V4 | Kondisi repository saat ini | Gap / risiko | Target phase |
|---|---|---|---|
| Role dan least privilege | `customer`, `admin`, `kitchen`, `supplier` sudah ada; `require_admin`, `require_staff`, dan supplier guard sudah digunakan di router tertentu | Role courier, bot identity terpisah, supplier row-scope, re-auth approval, dan delivery permission belum menjadi kontrak end-to-end | 1, 7, 8, 10 |
| Recipe/material master | `ingredients`, `recipe_versions`, `recipe_components`, ingredient verification, recipe review, dan draft AI foto/URL sudah ada di working tree | Import PDF/XLSX/CSV/text sebagai job private, nested BOM, brand/SKU/subingredients, unit/yield, nutrition source, lot/expiry, dan approval event lengkap belum terintegrasi penuh | 2 |
| Allergy Guard | `safety_service.py` melakukan keputusan deterministik dan order service memiliki recipe gate | Jalur legacy Telegram/Astra dan beberapa frontend/AI paths perlu parity serta post-filter; recursive BOM/cross-contact production contract belum lengkap | 1, 2, 3 |
| Nutrition | Draft AI mengembalikan proposal komposisi; beberapa menu type memiliki field enriched bila tersedia | Belum ada nutrition composition source table, raw/cooked basis, yield calculation, deterministic macro/kcal engine, status ESTIMATED/VERIFIED/UNAVAILABLE, dan review evidence | 2 |
| Customer dietary | Passport dan endpoint `/customers/me/passport` tersedia; preference/free text sebagian ada | Klasifikasi allergy/intolerance/preference/medical, parse-confirm draft, per-order snapshot, substitution workflow, dan support ticket belum lengkap | 3 |
| Breakfast/lunch/dinner | Domain menu/order saat ini terutama berbasis hari dan menu; UI customer sudah diperluas untuk beberapa pilihan hari | `meal_slot` dan kalender tiga slot sebagai invariant database/order/batch belum menjadi kontrak menyeluruh | 3, 4, 8 |
| Customer order/payment | Orders, payment intent/webhook boundary, idempotency, paid-only kitchen ticket service sudah berada di working tree | Frontend/customer flow dan live provider proof masih perlu E2E; QR/payment simulator tidak boleh diklaim live | 4 |
| Production batch | Kitchen board/KDS route dan inventory consumption manual tersedia | Belum ada pemisahan subscription/menu cycle vs `production_batch`, firm demand vs forecast, batch requirements, reservations, variance, dan close reconciliation | 4 |
| Barcode/weigh | Kitchen page menerima scan/ID dan input berat manual; `inventory_movements` punya consumption ledger | Material barcode vs lot label, `weigh_events`, lot/expiry/FEFO, camera scan, label rendering, reservation release, dan scale adapter belum ada. Bluetooth sengaja ditunda dan tidak boleh diasumsikan mempunyai API universal | 5 |
| Inventory truth | `inventory_stocks`, `inventory_movements`, `inventory_reservations`, receipt/consumption foundations, replenishment service tersedia | Goods receipt per lot, waste/stock count, location, negative-stock/invariant tests, planned-vs-actual linked to batch, dan no-double-deduction E2E belum terbukti | 5 |
| Forecast/MRP | Forecast service, backtest, SS/ROP replenishment report, supplier sourcing, and stale-data gates tersedia | Firm paid demand + forecast netting per slot, 7/30-day evaluation evidence, ROQ pack/MOQ/capacity, daily alert scheduler, dan source freshness E2E belum complete | 6 |
| Supplier/PO | Supplier tables, supplier items, supplier accounts, draft/approve/queue PO service, outbox, and supplier routes exist | Goods receipt, supplier confirmation tolerances, invoice 3-way match, weekly statement, pay-on-delivery, billing status, and unassigned sourcing UI still incomplete | 7 |
| Delivery/courier | No confirmed complete courier route/role found in active route map | Delivery task/manifest/dispatch slot/POD/status tracking and privacy boundaries are missing or partial | 8 |
| Telegram | `telegram_bot.py` is legacy/one-bot oriented; admin procurement paths and outbox-related code exist | Three independent Customer/Admin/Supplier bot identities, webhook/update dedup, audience isolation, secure approvals, retries/dead-letter, and parity are not proven | 10 |
| Langflow | Health endpoint checks `/api/v1/version`; `LangflowService.ask` exists and can fallback; JSON exports include custom Dova components | A version response is not execution proof. Need trace IDs, explicit CONNECTED/DEGRADED/OFFLINE/MISCONFIGURED/MOCK, ON/OFF smoke, flow/model/vector readiness, and no silent fallback | 1 |
| RAG/vector | `rag_ai_service.py` performs `ILIKE` document search; Langflow export refers to `documents`/`match_documents`/Supabase vector store | Repository migrations do not prove the required `documents`/RPC/vector schema. Must not call ILIKE vector RAG | 1 |
| Billing/audit/security | Audit tables, payment signatures, idempotency, and RBAC foundations exist | Database backup proof, restore drill, private file storage, upload antivirus/limits, approval re-auth/nonce, supplier invoice matching, and cross-role adversarial tests remain | 1, 2, 7, 10 |

## Reference availability

Available in repository: `AUDIT.md`, `docs/audit/`, Langflow exports, pitch-deck PDF/screenshots, migration files, tests, and the source application. The user-provided SAP PDF exists outside the repository at `C:\Users\LENOVO\Downloads\Modul SAP01 Update.pdf`. The V4 prompt references additional decks, mentor PDFs, recipe samples, SKU catalogs, scale labels, invoice examples, and delivery data; those artifacts are not all present in the repository and must remain explicitly unverified until supplied.

## Phase 0 decision

The safest next step is Phase 1: prove Langflow execution/fallback states and establish a database backup/restore baseline before adding migrations or production workflows. Existing working-tree changes are preserved; no reset or cleanup was performed.

## Phase 1 correction — 2026-10-30

The Phase 1 implementation has now been completed locally. Supabase/PostgreSQL
is the active source of truth; Astra is not an active API database path and is
reported as `OFFLINE_LEGACY`. Langflow platform reachability is proven, while
the opt-in flow probe is currently `DEGRADED` because the provider returned
HTTP 500. See `PHASE_1_LANGFLOW_DB_BASELINE_REPORT.md` for the exact evidence
and stop gate.
