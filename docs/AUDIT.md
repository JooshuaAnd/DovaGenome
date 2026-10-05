# DovaGenome AI — PHASE 1 Audit Report

**Status:** read-only audit. No source file was modified, moved, or deleted.
**Date:** 2026-10-04
**Verified against:** live Astra DB (read-only queries), live Langflow (health check), `.git` history, `.venv`.

---

## 0. Executive Summary

| Question | Answer |
| --- | --- |
| Is Streamlit a hidden dependency of anything that must survive? | **No.** Only the 3 Streamlit apps + `theme.py` import it. `data.py`, `telegram_bot.py`, `seed_catering_data.py`, `repair_catalog.py` are all Streamlit-free. |
| Can Streamlit be removed cleanly? | **Yes**, after the React equivalents ship. One hidden coupling: `admin_kitchen_dashboard.py` imports `landing_page.render_landing`. |
| Is there a live credential in git? | **YES — URGENT.** `.bob/mcp.json` is git-tracked and contains a plaintext Langflow API key. |
| Is existing data usable as-is? | **Partially.** Catalog is clean. `kitchen_orders` has **two incompatible schemas** and 4 orders total. `user_profiles` has 3 docs with double-prefix data bugs. |
| Does Langflow work? | **Yes.** v1.12.3 reachable, API key valid, RAG knowledge base populated (14 docs). |
| Biggest architectural risk | Business logic lives in `telegram_bot.py` and inside Streamlit callbacks, not in a service layer. |

---

## 1. Existing Architecture

```
                      ┌──────────────────────────────┐
   Browser ─────────► │ Streamlit :8501               │
                      │  landing_page.py             │
                      │  kitchen_dashboard.py        │
                      │  admin_kitchen_dashboard.py  │
                      └───────┬──────────────┬───────┘
                              │              │
                      ┌───────▼──────┐  ┌────▼─────────────┐
                      │  theme.py    │  │  data.py (598 L) │
                      │  (641 L)     │  │  domain + DB +   │
                      │  design sys  │  │  helpers + fallb.│
                      └──────────────┘  └────┬─────────────┘
                                             │
   Telegram ───► ┌──────────────────┐         │
   (long poll)  │ telegram_bot.py  │─────────┤
                 │ (1008 L)         │         │
                 │ ⚠ business logic │         │
                 │ ⚠ direct DB I/O  │         │
                 │ ⚠ direct Langflow│         ▼
                 └──────────────────┘    ┌──────────────┐
                                          │  Astra DB    │
                                          └──────────────┘
                 ┌──────────────────┐    ┌──────────────┐
                 │ Langflow :7860   │◄───│ RAG vector   │
                 └──────────────────┘    │ store        │
                                          └──────────────┘
```

### Characteristics

- **Flat, root-level layout.** 15 tracked files, no package structure.
- **No backend layer.** Each frontend file opens its own `DataAPIClient` and reads/writes collections directly.
- **No auth.** All three Streamlit apps are fully public on `:8501`.
- **No API.** React will have nothing to call; a FastAPI layer must be created from existing logic.
- **Two unrelated vector collections** in the same Astra DB (`dova_kitchen_catering`, `hr_documents`) — the DB is shared with other Langflow projects.

---

## 2. Existing Streamlit Pages

| File | Lines | Role | Reads | Writes | Exports used elsewhere |
| --- | ---: | --- | --- | --- | --- |
| `landing_page.py` | 374 | Public marketing site | `load_catalog`, `bot_username`, `DAYS`, `today_name`, `telegram_link` | — | **`render_landing(preview=True)` imported by admin tab 4** |
| `kitchen_dashboard.py` | 259 | KDS kanban (3 columns) | `load_catalog`, `fetch_orders`, `parse_dt`, `order_*`, `elapsed_minutes`, `sla_level` | `update_order_status` | — |
| `admin_kitchen_dashboard.py` | 674 | Admin: 5 tabs | `load_catalog`, `fetch_orders`, `fetch_collection`, env vars, `list_collection_names` | `upsert_doc`, `update_fields`, `update_order_status` | — |
| `theme.py` | 641 | Design system | `STATUS_META`, `order_*`, `elapsed_minutes`, `sla_level`, `current_menu`, `today_name` | — | imported by all 3 apps |

### `admin_kitchen_dashboard.py` tabs

1. **Ringkasan & Papan** — 8 KPIs, full kanban with cancel dialog, JSON detail popover
2. **Jadwal Mingguan** — 6 day cards, per-day order list, allergen alert count
3. **Katalog** — 3 sub-tabs: Menu Mingguan / Profil Pantangan / Paket Katering (CRUD + active toggle)
4. **Halaman Tamu** — deep-link buttons + **embedded live landing page preview**
5. **Sistem** — masked env credential table + per-collection document counts

### `theme.py` inventory (14 colour tokens + 16 builders)

Tokens: `IVORY #FBF8F3`, `CREAM #F4EDE1`, `SURFACE #FFFFFF`, `INK #1B2A24`, `INK_SOFT #41544C`, `MUTED #6E8078`, `LINE #E7DFD1`, `FOREST_900/700/600/100/50`, `GOLD_600/500/50`, `ROSE_600/50`.
Typography: `Georgia/Cambria` display serif + `Segoe UI` sans.
Builders: `esc`, `sla_minutes`, `_render_css`, `page_config`, `inject_css`, `brand_bar`, `sidebar_brand`, `hero`, `section_head`, `kpi`, `kpi_row`, `status_chip`, `allergen_pills`, `day_pills`, `stepper`, `order_card`, `empty_state`, `note`, `footer`, `st_markdown`, `telegram_cta`.

**Reusable after migration (→ React/Tailwind):** colour tokens, type scale, radius, `STATUS_META` colours, `order_card` *layout intent*, `stepper`, `allergen_pills`/`day_pills`/`status_chip` as Badge variants, SLA threshold logic.
**Discard:** all 320 lines of CSS, all `st.*` wrappers, `_HIDE_CHROME_CSS`.

---

## 3. Existing Business Logic

### 3.1 `data.py` — Streamlit-free, portable as-is → **service/repository/core layer**

| Group | Symbols | Destination |
| --- | --- | --- |
| Domain constants | `DAYS`, `ACTIVE_STATUSES`, `STATUS_FLOW`, `STATUS_META`, `ALLERGEN_KEYWORDS`, `REQUIRED_COLLECTIONS`, `WIB` | `app/core/domain.py` |
| Fallback catalog | `FALLBACK_PACKAGES`, `FALLBACK_ALLERGENS`, `FALLBACK_MENUS` | `app/core/fallbacks.py` |
| DB connection | `connect_db`, `ensure_collections` | `app/repositories/astra.py` |
| Catalog read | `load_catalog` | `app/repositories/catalog_repo.py` |
| Order read/write | `fetch_orders`, `update_order_status`, `upsert_doc`, `update_fields`, `fetch_collection` | `app/repositories/order_repo.py` |
| Time helpers (WIB) | `now_wib`, `parse_dt`, `fmt_wib`, `elapsed_minutes`, `sla_level` | `app/utils/time.py` |
| Order doc readers | `order_id`, `order_customer`, `order_package`, `order_allergens`, `order_notes`, `scheduled_days`, `today_name`, `current_service_day`, `current_menu`, `count_by_status` | `app/services/order_service.py` (normalizers) |
| Safety keyword scan | `detect_allergy_risks` | `app/services/safety_service.py` |
| Telegram links | `bot_username`, `telegram_link`, `telegram_link_html` | `app/core/config.py` (url only) |
| Demo data | `demo_orders` | keep, but **opt-in only** (see Risk 7) |

### 3.2 Business logic trapped inside `telegram_bot.py` → **must move to FastAPI services**

| Logic | Location | Notes |
| --- | --- | --- |
| `create_weekly_order()` | `:168-208` | Order doc builder, SOP text generation, order-id format `ORD-%Y%m%d%H%M%S-<6 hex>`, initial `PENDING`, **auto-syncs Dietary Passport** |
| Catalog cache | `:89-127` | 120 s TTL, lock-protected, `paket_options`/`paket_days`/`allergen_opts` maps |
| `save_user_profile` / `get_user_profile` | `:150-165` | `_id = str(chat_id)` |
| `my_orders()` | `:211-221` | per-`chat_id` history, limit 8 |
| `get_langflow_response()` | `:689-723` | 3-path response parser, 300 s timeout, Indonesian user-facing error strings |
| `route_deep_link()` | `:613-626` | `order`, `ai`/`konsultasi`, `menu`, `orders`/`status`, `passport` |
| `AVOIDED_TIME_OPTIONS` | `:314-319` | 4 delivery windows |
| `awaiting_name` flow | `:962-982` | Free-text name capture → save profile → create order |
| `avoided_times` toggling | `:842-876` | ⚠ contains prefix bug (§ Risk 3) |
| `kb_*` keyboards, `text_*` | `:227-464` | Presentation only → React / Telegram markup |

### 3.3 Business logic trapped inside Streamlit callbacks → **must move to FastAPI services**

| Logic | Location | Rule it encodes |
| --- | --- | --- |
| `closed_today()` | `admin:57-70` | Completed/cancelled count for **WIB** day |
| `_advance()` / `advance()` | `admin:175`, `kitchen:203` | Status transition via `STATUS_META[s]["next"]` |
| `apply_filters()` | `kitchen:60-68` | Search by customer/order-id; alert-only filter |
| `_katalog_menu()` | `admin:330-387` | Menu upsert; **`nama_menu` and `alat_dapur_steril` both required** |
| `_katalog_alergen()` | `admin:398-456` | Allergen upsert; `code` + `label` required |
| `_katalog_paket()` | `admin:459-524` | Package upsert; `code` + `name` + ≥1 day required; `price` optional |
| `_toggle()` | `admin:390-395` | Flip `active` flag |
| `_mask()` | `admin:577-580` | Credential masking for diagnostics |
| Allergen extraction | `landing:185-191` | `potensi_alergen` containing `"⚠"` ⇒ ingredient is "mengandung" |
| SLA thresholds | `theme:57`, `data:501` | `fresh` <20 min, `soon` 20–29, `late` ≥30 |
| KPI definitions | `kitchen:154-159`, `admin:163-172` | Operational metric set |

---

## 4. Existing Astra DB Collections (live, verified)

Database is shared with other Langflow projects. **5 app collections + 2 foreign collections.**

| Collection | Docs | App usage | Schema |
| --- | ---: | --- | --- |
| `allergen_definitions` | 6 | `load_catalog`, admin catalog | `_id`, `code`, `label`, `risiko`, `active` — clean |
| `catering_packages` | 3 | `load_catalog`, admin catalog | `_id`, `code`, `name`, `days[]`, `description`, `active` — ⚠ **no `price`** |
| `catering_menus` | 6 | `load_catalog`, admin catalog, landing | `hari`, `nama_menu`, `deskripsi`, `bahan_detail[]{nama,sumber,potensi_alergen}`, `alat_dapur_steril[]` — clean |
| `kitchen_orders` | 4 | bot create, KDS, admin | ⚠ **TWO INCOMPATIBLE SHAPES** |
| `user_profiles` | 3 | bot passport | `_id = str(chat_id)` — ⚠ **no `customer_id`** |
| `dova_kitchen_catering` | 14 | **Langflow vector store (RAG)** | `page_content`, `metadata{flow_id, category, content_blocks, …}` — `flow_id = 09778e1b-f424-48e9-bf6d-36d8fb2cdb90`. **Langflow-owned. Do not touch.** |
| `hr_documents` | 1 | — | Langflow demo sample (`Employee_Handbook.pdf`). Unrelated orphan. |

### 4.1 `kitchen_orders` — verified schema drift

**Shape A — legacy (2 docs: `…CF311DB0`, `…466E9CFB`)**
```
_id, order_id, chat_id, nama, menu_name, dietary_profile ("udang/seafood"),
kitchen_notes, status, created_at, updated_at
```
No `customer_name`, no `subscription_type`, no `schedule_days`, no `selected_allergens`.

**Shape B — current (2 docs)**
```
_id, order_id, chat_id, customer_name, subscription_type, schedule_days[],
selected_allergens[] (catalog codes), dietary_profile (comma string),
kitchen_notes, status, created_at
```

**Spec §16 requires, and does NOT exist anywhere:** `customer_id`, `package_id`,
`invoice_number`, `meal_count`, `subtotal`, `discount`, `total`, `payment_status`.

**Live data bug:** Shape B doc has `dietary_profile = "alg_alg_telur, alg_alg_kacang, …"`
and matching `kitchen_notes`. `repair_catalog.py` was written to fix exactly this but only
cleans `selected_allergens`, which is already clean. The dirty fields were never migrated.

### 4.2 `user_profiles` — verified

```
_id="6178944533"  nama="Anjels"     dietary_profile="udang/seafood"  tanggal_lahir="09-09-2007"  avoided_times=["avd_avd_siang","avd_avd_sore","avd_avd_malam"]
_id="1"           nama="Budi Santoso" dietary_profile="Bebas Susu/Laktosa, Bebas Gluten"
_id="8335882459"  nama="manik"     dietary_profile="udang/seafood"  tanggal_lahir="02-03-2003"
```
- ⚠ `avd_avd_*` double prefix from `telegram_bot.py:852` (`full = data` instead of stripping).
- ⚠ `dietary_profile` is a **flat comma string of free text** — cannot express spec §9's
  four-way distinction (allergy / intolerance / preference / medical restriction).
- ⚠ `tanggal_lahir` is stored `DD-MM-YYYY` as a **string**.
- ⚠ `_id="1"` is a test/fixture profile.

---

## 5. Existing Telegram Functionality

| Area | Detail |
| --- | --- |
| Transport | `telebot` long polling, `infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)`, wrapped in retry loop (`:1001-1008`) |
| Commands | `/start` `/order` `/menu` `/orders` `/passport` `/ai` `/cancel` `/help` |
| Deep links | `order`, `ai` \| `konsultasi`, `menu`, `orders` \| `status`, `passport` — all mapped in `route_deep_link` (`:613-626`) |
| Order flow | 3 steps (`TOTAL_STEPS=3`) with `📍 Langkah X dari 3` + `▰▱▱` progress bar on every screen |
| Keyboards | 6 (`kb_main`, `kb_paket`, `kb_alergen`, `kb_konfirmasi`, `kb_avoided_times`, `kb_back_only`) |
| Callback router | `_dispatch` — ~35 branches, single-answer guarantee (`:730-744`) |
| Name capture | `awaiting_name` free-text step when profile has no `nama` |
| Passport | Read-only view of `dietary_profile` (no edit UI) |
| Avoided times | 4-window toggle, persisted to `user_profiles` |
| AI | Threaded (`ask_langflow`); `alt_menu` = "recommend alternative menu" |
| Text templates | `step_header`, `md_code`, `text_menu_weekly`, `text_avoided_times`, `text_menu_preview`, `text_ticket`, `text_orders`, `text_help` |
| Config source | `TELEGRAM_TOKEN`, `TELEGRAM_BOT_USERNAME` (⚠ **EMPTY** in `.env`) |

**No business logic may remain here** (spec §17). Bot becomes a thin client of FastAPI.

---

## 6. Existing Langflow Integration

| Item | Finding |
| --- | --- |
| Call sites | **Only** `telegram_bot.py` (`:59-63`, `:674-723`). React does not exist; Streamlit never called it. |
| `LANGFLOW_API_KEY` | **set** in `.env` (46 chars) |
| `LANGFLOW_API_URL` | ⚠ **EMPTY** in `.env` → falls back to hardcoded `http://127.0.0.1:7860/api/v1/run/09778e1b-…` |
| `LANGFLOW_FLOW_ID` | ⚠ **EMPTY** in `.env` → falls back to hardcoded `09778e1b-f424-48e9-bf6d-36d8fb2cdb90` |
| Live status | ✅ Langflow **1.12.3** reachable; `GET /api/v1/version` → `200` |
| Request | `POST` JSON `{input_value, input_type:"chat", output_type:"chat", session_id?}`, header `x-api-key` |
| Response parsing | 3 fallback paths: `outputs[0].outputs[0].results.message.text` → `…artifacts.text` → `text`. **Must be preserved.** |
| Timeout | `300` s — far too long for a web request |
| Session | `session_id = chat_id` (integer) — unusable for web customers |
| RAG KB | `dova_kitchen_catering`, 14 docs, `flow_id` matches, rich allergen/menu knowledge incl. per-dish modification options |
| Error handling | 3 Indonesian user-facing strings inline; `print()` logging only; no retry, no rate limit, no timeout tuning |

---

## 7. Dependencies

`requirements.txt` (5 lines): `astrapy`, `pyTelegramBotAPI`, `requests`, `python-dotenv`, `streamlit`.

- All 5 installed and importable in `.venv` (CPython 3.12).
- `requests` is used **only** by the Langflow call → becomes `httpx` in FastAPI (or keep `requests`).
- `streamlit` → **remove** in Phase 7.
- Verified: this `astrapy` build requires `upper_bound=` on `count_documents()` — any new count helper must comply.
- No `node`/`npm` project exists yet. Toolchain available: `node v24.18.0`, `npm 11.16.0`.

---

## 8. Files Safe to Delete

| File / Dir | Verdict |
| --- | --- |
| `run_landing.ps1` | ✅ Safe now — pure `streamlit run landing_page.py` launcher |
| `run_dashboard.ps1` | ✅ Safe now — pure `streamlit run kitchen_dashboard.py` launcher |
| `run_admin.ps1` | ✅ Safe now — pure `streamlit run admin_kitchen_dashboard.py` launcher |
| `__pycache__/` | ✅ Safe — 10 `.pyc`, already gitignored, pure artifact |
| `backup_junk_catalog_20261001_005258.json` | ✅ Safe — fixtures already deleted from Astra; `repair_catalog.py` verification reports catalog clean |
| `backup_junk_catalog_20261001_005320.json` | ✅ Safe — identical duplicate of the above (same 2398 bytes) |
| `dova_kitchen.db` | ✅ Safe — SQLite `users` table, **0 references in any `.py`**, already gitignored and untracked |
| `theme.py` | ⏳ Phase 7 — after tokens ported to Tailwind |
| `landing_page.py` | ⏳ Phase 7 — after React landing + menu live |
| `kitchen_dashboard.py` | ⏳ Phase 7 — after React KDS live |
| `admin_kitchen_dashboard.py` | ⏳ Phase 7 — after React admin live |
| `.bob/mcp.json` | 🔴 **Untrack + rotate key** — see Risk 1 |

**Never delete:** `.git/`, `.env`, `.venv/` (until new venv/requirements verified), the 5 Astra app collections, `dova_kitchen_catering`.

---

## 9. Files That Must Be Preserved

| Asset | Action |
| --- | --- |
| `data.py` domain logic | Port to `backend/app/core/domain.py`, `utils/time.py`, `repositories/*`, `services/order_service.py` — **no rewrite** |
| `data.py` fallback catalog | Keep as degraded-mode seed for new installs |
| `demo_orders()` | Keep but gate behind explicit `DEMO_MODE=true` |
| `telegram_bot.py` | Move to `telegram/telegram_bot.py`; keep keyboards, text templates, deep links, AI chat; **strip all DB/Langflow/business logic** |
| `seed_catering_data.py` | Move to `scripts/seed_catering_data.py`; keep `PACKAGES`, `ALLERGENS`, `WEEKLY_MENUS` as canonical source; **add `price` to packages** |
| `repair_catalog.py` | Move to `scripts/repair_catalog.py`; fix `sys.path` to reach `backend/`; **extend to clean `dietary_profile`, `kitchen_notes`, `avoided_times`** |
| Astra collections (5 app) | Untouched. Reuse. Only additive changes. |
| `dova_kitchen_catering` | Untouched — Langflow-owned |
| `theme.py` colour tokens + type scale | → Tailwind theme / CSS variables |
| `STATUS_META` colours + labels | → shared status registry served by API |
| SLA thresholds (20/30 min) | → backend `safety_service` |
| Menu validation rules | → backend `catalog_service` |

---

## 10. Migration Risks

| # | Severity | Risk | Mitigation |
| ---: | --- | --- | --- |
| 1 | 🔴 **CRITICAL** | **Live Langflow API key committed to git.** `.bob/mcp.json` is tracked (commits `4f4e6c4`, `8650297`) with plaintext key `sk-A6toV7P7…`. | Rotate key in Langflow **now**; `git rm --cached .bob/mcp.json`; add `.bob/` to `.gitignore`; **never copy the key into new code.** |
| 2 | 🔴 High | **`kitchen_orders` schema drift** — 2 incompatible shapes, 4 live docs. A naive Pydantic model will drop `nama`/`menu_name` from legacy orders. | Read-normalizer mapping both shapes → one API DTO. **No destructive migration.** Write only the new shape. |
| 3 | 🔴 High | **Unfixed data bugs.** `alg_alg_*` in `dietary_profile` + `kitchen_notes`; `avd_avd_*` in `user_profiles.avoided_times`. | Fix at the source (the two code bugs), extend `repair_catalog.py` to migrate existing docs, run once with `--yes`. |
| 4 | 🔴 High | **No `price` in `catering_packages`.** Spec §13 invoice needs Subtotal/Total. | Add `price` via `seed_catering_data.py` (fallback values already exist in `data.FALLBACK_PACKAGES`: 495000 / 420000 / 285000). Backfill, don't re-create. |
| 5 | 🔴 High | **No `customer_id`.** Orders keyed by Telegram `chat_id` (int). Web customers have no `chat_id`. | Introduce `customers` collection keyed by a generated UUID; map `chat_id → customer_id` in a `customer_channels` field. Legacy orders keep `chat_id`. |
| 6 | 🟠 Medium | **`dietary_profile` is a flat free-text string.** Spec §9 needs allergy / intolerance / preference / medical as distinct fields. | Add structured fields (`allergies[]`, `intolerances[]`, `medical_diet`, `preferences[]`, `avoided_ingredients[]`, `safety_notes`, `emergency_notes`) — additive. Keep legacy `dietary_profile` as read-only fallback for the 3 existing profiles. |
| 7 | 🟠 Medium | **Silent demo fallback.** `fetch_orders(..., fallback_to_demo=True)` returns fake orders whenever DB is down. In FastAPI this publishes fabricated orders to KDS/admin. | Default `DEMO_MODE=false`. Fallback only when explicitly enabled; health endpoint reports degraded state loudly. |
| 8 | 🟠 Medium | **~20 silent `except` blocks.** `connect_db` returns `None` on any error; `fetch_orders`/`update_order_status`/`load_catalog` swallow everything. Spec §23 forbids this. | Structured `logging`, typed exceptions, `AppError` → HTTP mapping, no bare `except: pass`. |
| 9 | 🟠 Medium | **Langflow URL/FLOW_ID are empty in `.env`** and rely on hardcoded Python fallbacks. | Make them **required** in backend `Settings`; fail fast at startup with a clear message. |
| 10 | 🟠 Medium | **Langflow timeout = 300 s** and `session_id = chat_id`. Web requests would hang. | `LangflowService` with ~20–30 s timeout, one retry, typed errors, string `session_id`, structured logging. |
| 11 | 🟡 Low | **Streamlit caching semantics lost.** `@st.cache_data(ttl=60/300)`, `@st.cache_resource`, `@st.fragment(run_every=…)`. | Backend TTL cache (`CatalogCache`, 120 s) + React polling for KDS/admin. |
| 12 | 🟡 Low | **Hidden cross-import:** `admin_kitchen_dashboard.py:568` → `from landing_page import render_landing`. Deleting `landing_page.py` first breaks admin. | Delete admin (or its tab) before/with `landing_page.py`. |
| 13 | 🟡 Low | **`repair_catalog.py` path fragility:** `sys.path.insert(0, dirname(abspath(__file__)))` + `os.chdir(...)`. Moving to `scripts/` breaks `import data` and `import seed_catering_data`. | Rewrite to insert `<repo>/backend` on `sys.path`; make imports explicit; add `--dry-run` default. |
| 14 | 🟡 Low | **No authentication anywhere.** Streamlit apps were public on `:8501`. Spec §21 needs customer/admin/kitchen. | Simple JWT (HTTPBearer) + role dependency; `ADMIN`/`KITCHEN` roles required for `/api/admin/*` and `/api/kitchen/*`. |
| 15 | 🟡 Low | **Foreign collections** (`dova_kitchen_catering`, `hr_documents`) live in the same DB. | Migration/seed scripts must whitelist collections; never iterate-and-write blindly. |
| 16 | ⚪ Info | **No tests, no lint config, no CI.** | Add `pytest` for backend services + `vitest` for frontend safety logic. |
| 17 | ⚪ Info | **Git working tree is clean**, HEAD `8650297`. No uncommitted work at risk. | Safe to branch. |

---

## 11. Proposed Target Structure

```
dova-kitchen/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory, CORS, router mount
│   │   ├── core/
│   │   │   ├── config.py            # Settings (pydantic-settings) — required env, no silent defaults
│   │   │   ├── domain.py            # DAYS, STATUS_FLOW, STATUS_META, ALLERGEN_KEYWORDS, WIB
│   │   │   ├── logging.py           # structured logging
│   │   │   └── errors.py            # AppError hierarchy → HTTP mapping
│   │   ├── api/
│   │   │   ├── deps.py              # auth + role dependencies, DI wiring
│   │   │   └── v1/
│   │   │       ├── health.py        # GET /api/health
│   │   │       ├── catalog.py       # /api/packages /allergens /menus
│   │   │       ├── customers.py     # /api/customers, /api/customers/{id}/passport
│   │   │       ├── orders.py        # POST/GET /api/orders, /api/orders/{id}, /api/orders/{id}/invoice
│   │   │       ├── kitchen.py       # /api/kitchen/orders, /api/kitchen/orders/{id}/status
│   │   │       ├── admin.py         # /api/admin/dashboard, /api/admin/catalog/*
│   │   │       └── ai.py            # /api/ai/consultation, /api/feedback
│   │   ├── services/
│   │   │   ├── catalog_service.py   # catalog read + admin validation rules (§3.3)
│   │   │   ├── order_service.py     # create_order, validate_package, status flow
│   │   │   ├── invoice_service.py   # generate_invoice (§13)
│   │   │   ├── safety_service.py    # validate_allergens, detect risks, SLA
│   │   │   ├── passport_service.py  # Dietary Passport CRUD
│   │   │   ├── dashboard_service.py # KPIs, closed_today, analytics
│   │   │   └── langflow_service.py  # §12 — timeout, retry, parse, logging
│   │   ├── repositories/
│   │   │   ├── astra.py             # connect_db, ensure_collections
│   │   │   ├── catalog_repo.py      # load_catalog
│   │   │   ├── order_repo.py        # fetch/update/upsert orders  (+ legacy shape normalizer)
│   │   │   ├── customer_repo.py     # user_profiles ↔ customers
│   │   │   └── cache.py             # TTL cache replacing st.cache_data
│   │   ├── schemas/                 # Pydantic: catalog, order, passport, invoice, kitchen, ai
│   │   ├── models/                  # domain enums + DTOs
│   │   └── utils/                   # time (WIB), formatting, ids
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/ui/           # shadcn/ui primitives
│   │   ├── components/brand/        # Logo, NavBar, Footer
│   │   ├── components/safety/       # SafetyCheck, AllergenBadge, RestrictionGroup
│   │   ├── components/order/        # OrderStepper, PackageCard, OrderSummary
│   │   ├── components/kitchen/      # KitchenTicket, StatusColumn, CriticalAllergen
│   │   ├── pages/
│   │   │   ├── LandingPage.tsx  MenuPage.tsx  OrderPage.tsx  PassportPage.tsx
│   │   │   ├── OrdersPage.tsx  OrderDetailPage.tsx  InvoicePage.tsx  AiPage.tsx
│   │   │   ├── admin/  DashboardPage.tsx  CatalogPage.tsx  OrdersPage.tsx  AnalyticsPage.tsx
│   │   │   └── kitchen/ KitchenBoardPage.tsx
│   │   ├── layouts/  PublicLayout · AdminLayout · KitchenLayout
│   │   ├── hooks/     useOrders, useCatalog, usePolling, useAuth
│   │   ├── services/  api.ts (fetch wrapper), catalog.ts, orders.ts, kitchen.ts, ai.ts
│   │   ├── lib/       status.ts (mirrors STATUS_META), safety.ts, format.ts, cn.ts
│   │   ├── types/     index.ts
│   │   └── index.css  # Tailwind theme ← theme.py tokens
│   ├── package.json · vite.config.ts · tsconfig.json · tailwind.config.ts
│
├── telegram/
│   └── telegram_bot.py              # thin client → FastAPI only
│
├── scripts/
│   ├── seed_catering_data.py        # + price backfill
│   └── repair_catalog.py            # + fix dietary_profile/kitchen_notes/avoided_times
│
├── docs/
│   ├── AUDIT.md                     # this file
│   ├── API.md
│   └── MIGRATION.md
│
├── .env · .env.example · .gitignore · README.md
```

### Data strategy — additive only

| Collection | Action |
| --- | --- |
| `allergen_definitions` | Reuse as-is. Optionally add `category` (allergy/intolerance/preference/medical) for spec §9. |
| `catering_packages` | Reuse. **Add `price`** to the 3 existing docs (backfill, don't recreate). |
| `catering_menus` | Reuse as-is. `potensi_alergen` + `alat_dapur_steril` already feed the safety engine. |
| `kitchen_orders` | Reuse. Write only the new superset shape. Read-normalizer handles Shape A + B. Add optional `customer_id`, `package_id`, invoice fields, `meal_count`. |
| `user_profiles` | Keep as Telegram-channel record. Add `customer_id` link. |
| `customers` | **NEW** — web customers: identity, contact, structured Dietary Passport (`allergies[]`, `intolerances[]`, `preferences[]`, `medical_diet`, `avoided_ingredients[]`, `safety_notes`, `emergency_notes`). |
| `dova_kitchen_catering` | **UNTOUCHED** — Langflow vector store. |
| `hr_documents` | **UNTOUCHED** — unrelated. |

---

## 12. Order of Implementation

| Phase | Scope | Exit criteria |
| --- | --- | --- |
| **0 — Security** *(do now, independent)* | Rotate Langflow key; `git rm --cached .bob/mcp.json`; add `.bob/` to `.gitignore` | Key in `.env` only; nothing tracked |
| **1 — Audit** | This document | ✅ Done |
| **2 — Backend** | `backend/` skeleton, `core/`, `repositories/` (port `data.py`), `services/`, `schemas/`, all `/api/*` routers, `LangflowService`, JWT roles, logging, `errors.py` | `/api/health` green; catalog + orders + kitchen + ai + admin all respond against **real Astra data** — ✅ Done, 60/60 checks pass against live Astra |
| **2b — Data care** | `scripts/seed_catering_data.py` price backfill; `scripts/repair_catalog.py` prefix cleanup (`--dry-run` first) | Catalog has prices; no `alg_alg_*` / `avd_avd_*` remain |
| **3 — React customer** | Vite + TS + Tailwind + shadcn/ui scaffold; design tokens from `theme.py`; `/`, `/menu`, `/order` (6-step stepper), `/passport`, `/orders`, `/orders/:id`, `/orders/:id/invoice`, `/ai` | Manual pass of §29 Customer + Safety test paths |
| **4 — React admin** | `/admin` dashboard, catalog CRUD, orders, customer dietary info, analytics | §29 Admin path passes |
| **5 — React KDS** | Kitchen queue, ticket with critical-allergen block, status workflow | §29 Kitchen path `PENDING→PREPARING→READY→COMPLETED` |
| **6 — Telegram refactor** | Move to `telegram/`; replace all DB/Langflow calls with FastAPI HTTP calls; preserve deep links + keyboards | §29 Telegram path passes; zero business logic left in bot |
| **7 — Streamlit removal** | Delete `landing_page.py`, `kitchen_dashboard.py`, `admin_kitchen_dashboard.py`, `theme.py`, `run_*.ps1`; drop `streamlit` from requirements; rewrite README; update `.gitignore`; clean `__pycache__`, backups, `dova_kitchen.db` | §30 Definition of Done — all 16 criteria |

---

## 13. Open Questions for the Team

1. **Package prices** — confirm 495000 / 420000 / 285000 (from `data.FALLBACK_PACKAGES`) as the real backfill values?
2. **Currency & tax** — invoices in IDR, no tax line, or add PPN?
3. **Legacy orders** — keep Shape A docs readable in admin/KDS, or migrate them forward?
4. **Dietary Passport migration** — 3 existing profiles only have a flat string. Backfill structured fields, or leave them on the legacy fallback?
5. **Auth method** — simple email+password JWT, or magic-link? Any customer self-signup, or admin-created accounts only?
6. **Telegram identity** — link web customers to Telegram via deep-link token, or keep the two channels' histories separate?
7. **Discount** — spec §13 lists a Discount line. Is there a discount mechanism, or always 0?
8. **Deployment** — where do backend + frontend run (local only, or a host)? Affects CORS and cookie strategy.

---

## 14. Phase 2 Handoff Notes (backend selesai)

### Cara menjalankan & memverifikasi

```bash
python -m uvicorn app.main:app --reload --app-dir backend   # jalankan API
python backend/scripts/seed_staff.py --username admin        # akun admin pertama
python backend/scripts/verify_phase2.py                      # 35 cek,/~60 dtk
python backend/scripts/verify_phase2.py --write              # 60 cek,/~2 mnt
```

`verify_phase2.py` berjalan terhadap Astra live dan **selalu** menghapus data
ujinya sendiri di akhir (termasuk akun staff sementara). Ia tidak pernah
menyentuh `dova_kitchen_catering` atau `hr_documents`.

### Koleksi yang dibuat aplikasi

`customers` dan `customer_feedback` dibuat otomatis saat startup, additive.
Hanya `customers` yang menjadi sumber kebenaran; `user_profiles` tetap dipakai
sebagai cermin untuk bot Telegram.

### Batasan Astra Data API yang sudah diverifikasi

* `$or` **tidak** dipakai pada `_id` — filter langsung, atau `$in`.
* `count_documents()` butuh `upper_bound`.
* Dipakai: `$in`, range, upsert (`find_one_and_replace`), `$push`, nested `$set`,
  sort, limit.

### Perilaku yang berubah dari legacy

* Order kini satu baris per pesanan dengan `schedule_days[]`. Order lama (Shape A,
  satu baris per hari) tetap terbaca oleh normalizer, tapi tidak ditulis ulang.
* Harga selalu dari katalog; tidak ada harga yang dipercaya dari client.
* Pembatalan pesanan hanya admin, dan wajib menyertakan alasan.
* `GET /api/catalog?include_inactive=true` hanya untuk admin.

### Utang teknis yang sengaja tinggalkan untuk produksi

1. **Rate limit in-memory per proses.** `app/utils/ratelimit.py` cukup untuk
   development satu worker. Multi-instance/containers → pindahkan ke Redis/WAF.
2. **`POST /api/auth/telegram/resolve` belum punya shared secret.** Endpoint ini
   dirancang untuk dipanggil bot; kalau dibuka ke internet, tambahkan header
   secret yang hanya bot yang tahu.
3. **`ALLOW_PASSWORDLESS_LOGIN=true`** hanya untuk MVP. Matikan di produksi.
4. **`.bob/mcp.json` masih tracked** dan berisi Langflow key plaintext
   (Phase 0 belum dikerjakan).
5. **Retry Astra belum ada.** Koneksi ke Astra kadang timeout saat handshake TLS;
   satu request KDS bisa gagal karena itu. Tambahkan retry/backoff di
   `astra.get_database()` sebelum produksi.
6. **Harga paket masih `None`** — lihat Open Questions #1. Order/invoice uji
   otomatis karena itu menghasilkan `total=0`.
