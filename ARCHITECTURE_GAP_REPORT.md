# Architecture Gap Report — DovaGenome

Status: **PHASE 0 — inspection only.** Tidak ada kode produksi yang diubah.

## 1. Current architecture yang terbukti dari repository

```text
React frontend ──┐
                 ├── sebagian endpoint FastAPI ── Supabase/Postgres
Telegram bot ────┘             │
                               ├── deterministic services
                               └── Langflow/fallback RAG

Telegram legacy path ── Astra DB langsung
Legacy helpers ──────── data.py / Astra collections
Langflow export ─────── JSON artifact, live deployment belum terbukti
```

Evidence utama:

- FastAPI entry: `backend/app/main.py`.
- Supabase repository: `backend/app/repositories/supabase.py`, `catalog_repo.py`, `order_repo.py`.
- Telegram direct Astra: `telegram_bot.py`, `data.py`.
- AI boundary backend: `backend/app/services/langflow_service.py`, `rag_ai_service.py`.
- Langflow flow artifact: `langflow/*.json` dan `docs/langflow/original.json`.

## 2. Target architecture yang diperlukan

```text
Customer Web / Telegram / Admin / Kitchen / Supplier
                         │
                 FastAPI + JWT/RBAC
                         │
      authorized context + deterministic business services
                         │
              Supabase/PostgreSQL transaction boundary
                         │
       payment webhook / worker / notification outbox

AI path:
FastAPI context → Allergy/PII validation → Langflow/RAG/LLM
             → structured output → backend post-validation → response
```

## 3. Gap register

Severity:

- **P0**: keselamatan, transaksi, atau akses data dapat dilanggar.
- **P1**: jalur utama MVP belum dapat dibuktikan.
- **P2**: analytics/operational completeness.

| Gap ID | Severity | Area | Bukti aktual | Risiko | Target resolution |
|---|---|---|---|---|---|
| G-01 | P0 | Source of truth | Bot menulis Astra; API menulis Supabase | Web, bot, dan kitchen dapat melihat data berbeda | Migrasi bot menjadi API client; lakukan dual-read/migration verification sebelum cutover. |
| G-02 | P0 | Allergy enforcement | Backend `create_order` memblokir `BLOCKED`, tetapi bot/UI punya checker sendiri | Jalur non-API dapat melewati policy yang sama | Satu `AllergyGuard` service/API; semua channel memakai response yang sama; fail-closed pada unknown. |
| G-03 | P0 | Recipe evidence | Tidak ada nested BOM, recipe version, verification history, cross-contact schema | “Eligible” dapat dihitung dari data bahan yang tidak lengkap | Bangun ingredient/recipe verification foundation sebelum mengklaim safety. |
| G-04 | P0 | Payment/KDS | Order dibuat `UNPAID`; kitchen board/advance tidak terbukti membatasi `payment_status=PAID`; payment hanya manual admin | Pesanan unpaid dapat masuk operational flow | Payment webhook idempotent + paid-only ticket/board/API/DB constraint. |
| G-05 | P0 | RBAC supplier | `backend/app/api/routers/supplier.py` tidak memakai dependency auth/role pada list/respond/catalog/summary | Supplier dapat mengakses/mengubah data di luar tenant | Enforce supplier identity and ownership server-side; isolation tests. |
| G-06 | P1 | Web checkout | `OrderPage.tsx` memakai local cart dan `handleSimulatePaymentSuccess`; tidak memanggil create order API | Demo web tidak membuktikan transaksi end-to-end | Hubungkan cart → server draft/order → payment intent. |
| G-07 | P1 | AI safety contract | `/ai/consult` dan Telegram `alt_menu` memakai text prompt/raw reply; post-validation terstruktur belum ada | LLM dapat mengarang menu atau menyatakan menu aman | Structured schema, allowed menu IDs, guard recheck, prompt injection tests. |
| G-08 | P1 | RAG data | `rag_ai_service.search_rag_documents` membaca `documents`, tabel tidak ada di repo migrations | RAG runtime bergantung pada schema eksternal yang tidak terlacak | Putuskan source RAG: Supabase table/vector metadata atau external Langflow; dokumentasikan migration/contract. |
| G-09 | P1 | Langflow wiring | Export memuat Dova components, tetapi tidak ada bukti live deployment/contract test | Pitch claim dapat melampaui runtime | Mock contract + optional live smoke test dengan credentials; pisahkan artifact vs runtime. |
| G-10 | P1 | Order model | `orders` sudah ada tetapi belum ada `order_drafts`, `payments`, `kitchen_tickets`, address model | Status transaksi dan operational ticket tidak memiliki boundary kuat | Tambah hanya schema yang diperlukan setelah inventory Phase 1. |
| G-11 | P1 | Telegram identity | Bot memakai `chat_id` dan legacy `user_profiles`; API customer memakai customer/JWT | Ownership dan passport dapat tidak sinkron | Link Telegram server-side, token/identity mapping, parameter ID tidak dipercaya dari user. |
| G-12 | P1 | Recipe UI | Tidak ditemukan recipe editor/approval UI | Data recipe tidak dapat dipelihara operator secara auditable | Admin/kitchen edit vs approve, versioning, evidence upload, audit log. |
| G-13 | P2 | Forecast evidence | Forecast service ada, tetapi baseline/backtest/WAPE report tidak ada; beberapa values hardcoded | Klaim ML tidak reproducible | Rolling-origin evaluator dengan naive/MA7/seasonal/model current. |
| G-14 | P2 | Inventory math | SS/ROP aktif memakai lead time tetap dan faktor material generik; BOM belum lengkap | Rekomendasi stock/PO tidak dapat diaudit per recipe | BOM quantity + unit normalization + lead time/variability + backtest. |
| G-15 | P2 | ROQ | Tidak ditemukan ROQ/EOQ | Suggested shortage qty dapat disalahlabel sebagai EOQ | Tetap label shortage/target replenishment atau implementasikan EOQ dengan cost inputs nyata. |
| G-16 | P1 | PO workflow | Schema/list/respond tersedia; insert draft dari forecast dan approval transition tidak ditemukan | “Closed-loop supply chain” belum terbukti | Persistent idempotent draft, admin approval, send, supplier response, receiving. |
| G-17 | P2 | Churn | Tidak ada active churn model; `At Risk` hanya RFM | Retention claim bisa misleading | Rule baseline dulu; supervised model hanya dengan label/time split. |
| G-18 | P2 | Marketing control | Langflow `draft_marketing` artifact; campaign state/consent/control group runtime tidak ditemukan | Draft dapat dianggap campaign terkirim/causal impact | Campaign state machine + approval/outbox + experiment plan. |
| G-19 | P1 | Analytics provenance | Fallback 1.000 rows/hardcoded supplier forecast/sample admin data ditemukan | Simulation dapat tampil sebagai production | Provenance enum/label pada API, database, dan UI. |
| G-20 | P1 | Test coverage | Test hanya baseline backend; frontend/E2E/adversarial/payment/PO tidak ada | Regression dan safety claims tidak terbukti | Test matrix per requirement; jangan ubah assertion untuk membuat hijau. |
| G-21 | P2 | Technical source | Technical deck `.pptx` tidak tersedia | Traceability terhadap requirement deck tidak lengkap | Minta file jika requirement teknis tertentu wajib dijadikan acceptance criteria. |
| G-22 | P1 | PO state contract | Migration membatasi status PO ke `DRAFT,SENT,ACCEPTED,REJECTED,PARTIAL,RECEIVED,CLOSED`, sedangkan `supplier.py` membaca/menerima `PENDING_APPROVAL`, `ACKNOWLEDGED`, dan `PARTIALLY_RECEIVED` tanpa validation model | Update/query PO dapat gagal atau menghasilkan state yang tidak konsisten | Satu state machine + enum/schema validation + migration yang disepakati; supplier route wajib ownership check. |
| G-23 | P1 | Langflow connection proof | Export utama 23 node/20 edge, `docs/langflow/original.json` 23 node/19 edge; live server/flow execution/model belum terbukti | Artifact dapat disalahartikan sebagai runtime terintegrasi | Inventory caller/config; contract test dan live smoke test; label `LIVE NOT VERIFIED` bila tidak bisa dibuktikan. |
| G-24 | P1 | Langflow failover/readiness | `LangflowService.ask` fallback ke `generate_rag_answer`; `health()` hanya memeriksa `/api/v1/version` | Text response sukses dapat menutupi Langflow/model/vector/live-data failure | Readiness terpisah: app, reachability, executable flow, model, vector, live data; source/latency/request ID wajib. |
| G-25 | P0 | AI allergy boundary | Passport dapat masuk prompt; Telegram `alt_menu` dan raw AI paths belum post-filter structured menu IDs | LLM/prompt injection dapat mengusulkan menu yang tidak eligible | Verified BOM → allowed IDs → restricted retrieval → structured IDs → backend post-filter → checkout revalidation. |
| G-26 | P1 | Sample/live data mode | Export `DovaDataSource.use_sample=True`; `documents`/`match_documents` belum ada di migration repo | Demo/sample atau fallback dapat tampak sebagai live data | `DATA_MODE=live|simulation`; live mode gagal jelas tanpa data; validasi vector schema/RPC/RLS/metadata dan citation. |
| G-27 | P1 | AI mode and controlled failure | Tidak ditemukan `AI_MODE` atau report untuk wrong flow ID, credential, model/vector, JSON, timeout, dan prompt injection | Failure behavior tidak dapat dibedakan dari success atau fallback | `required_langflow|allow_explicit_fallback|disabled`; deterministic business/safety tetap berjalan dan source output dilabeli. |

## 4. Data model gap

| Domain | Ada saat ini | Belum ada/kurang | Consequence |
|---|---|---|---|
| Customer/passport | `customers`, `dietary_passports` | history/verification/provenance yang kaya; role supplier belum pada constraint customer | Passport dan role belum sepenuhnya sesuai target. |
| Catalog | `packages`, `allergens`, `menus`, `menu_ingredients` | ingredient master, subcomponents, recipe versions, verification, cross-contact | Safety belum dapat ditelusuri sampai sumber bahan. |
| Order | `orders`, `order_items`, `order_status_events` | draft/address/payment attempt/kitchen ticket | No-pay-no-cook tidak punya boundary persistence. |
| Supply chain | suppliers/items/PO/inventory/outbox | movements/reservations/receiving/performance/MRP snapshots | PO dan stock calculation belum transactional end-to-end. |
| Analytics | feedback, likes, cart history, order columns | forecast evaluation, RFM snapshots, churn predictions, campaign state | Evaluation dan historical movement belum tersimpan. |
| RAG | runtime query `documents`; no migration | provenance/access scope/vector metadata decision | RAG contract tidak reproducible dari repo saja. |

## 5. Security and operational gaps

1. Supplier endpoints perlu auth/tenant ownership sebelum demo.
2. Endpoint admin tertentu memakai `get_optional_staff`; route sensitif harus memakai dependency wajib dan role tepat.
3. Hardcoded phone/recipient dan sample data terlihat pada notification/analytics code; harus dipindah ke configuration/data source dan diberi audit/provenance.
4. Payment status manual tidak cukup untuk settlement; perlu signature, amount, order, expiry, replay/idempotency checks.
5. PII/dietary data tidak boleh masuk log, prompt, vector retrieval, atau supplier response tanpa scope.
6. Semua perubahan recipe, passport, payment, order status, inventory, PO, dan campaign memerlukan audit actor/time/before-after.

## 6. Minimum safe pilot slice

Sebelum mengejar seluruh roadmap, pilot yang paling aman dan dapat didemokan adalah:

1. Satu segmen Dova Kitchen dengan menu dan recipe fixture yang provenance-nya jelas.
2. Customer passport → API catalog safety → API order; web dan Telegram hanya client.
3. Simulated payment provider yang tetap memverifikasi signature/idempotency dalam test.
4. Paid order → kitchen ticket → BOM fixture → inventory recommendation → persistent draft PO → admin approval.
5. RFM baseline dan marketing draft manual approval; churn diberi label heuristic.
6. Semua output demo diberi label `Data simulasi`, `Target`, atau `Backtest`, bukan production impact.

## 7. Langflow recovery acceptance gate

Sebelum Chef BOB atau admin AI disebut terintegrasi, harus ada tiga laporan: `LANGFLOW_CONNECTION_AUDIT.md`, `LANGFLOW_RUNTIME_PROOF.md`, dan `LANGFLOW_FAILURE_TEST_REPORT.md`, plus backup export repaired tanpa secrets. Bukti minimum adalah satu request Chef BOB dan satu request admin AI yang menunjukkan request ID, endpoint/flow yang benar, readiness, source `langflow_live`, latency, dan retrieval scope. Jika Langflow dimatikan pada mode `required_langflow`, hasil harus `unavailable`; pada mode fallback, hasil harus diberi source fallback. Tidak boleh ada status “integrated” bila salah satu bukti tersebut gagal.
