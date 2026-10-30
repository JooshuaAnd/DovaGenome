# Audit DovaGenome

Tanggal audit: 2026-10-26  
Metode: inspeksi statis repository. Tidak ada file kode/config yang diubah. Dokumen ini adalah file audit baru yang diminta.

## 1. Peta struktur repository

| Area | Lokasi | Temuan |
|---|---|---|
| Backend | `backend/app/` | Aplikasi FastAPI aktif. Entry point: `backend/app/main.py`, objek `app`; router dipasang melalui `app.include_router(...)`. |
| Backend API | `backend/app/api/routers/` | Router `auth`, `catalog`, `customers`, `orders`, `kitchen`, `admin`, `supplier`, `ai`, dan `health`. Registry ada di `backend/app/api/routers/__init__.py`. |
| Backend service | `backend/app/services/` | Business logic untuk safety, order, RAG/AI, analytics/ML, passport, invoice, dan Langflow. |
| Backend repository | `backend/app/repositories/` | Akses Supabase/Postgres aktif melalui `supabase.py`, catalog melalui `catalog_repo.py`. |
| Frontend | `frontend/src/` | React + Vite. Entry point `frontend/src/main.tsx`, root app `frontend/src/App.tsx`. |
| Frontend pages | `frontend/src/pages/` | Customer ordering, AI, passport, orders, admin, kitchen, dan supplier. Catatan: route `/`, `/order`, dan `/menu` saat ini me-mount `OrderPage`; `MenuPage.tsx` ada tetapi tidak menjadi page yang aktif dari route tersebut. |
| Bot Telegram | `telegram_bot.py` | Entry point bot Telebot; menjalankan `bot.infinity_polling()` pada blok `__main__`. Bot masih mengakses Astra DB secara langsung. |
| Legacy data layer | `data.py` | Layer Astra lama untuk Streamlit/Telegram, berisi collection `user_profiles`, `kitchen_orders`, `catering_packages`, `allergen_definitions`, dan `catering_menus`. |
| Supabase schema | `supabase/migrations/001_schema.sql` sampai `004_analytics_ml_and_interactions.sql` | Skema relasional aplikasi, supplier, inventory, PO, analytics, feedback, dan interaksi customer. |
| Langflow artifact | `docs/langflow/original.json` | Export flow Langflow dengan custom component Dova. Ini artefak konfigurasi; tidak ditemukan import langsung dari runtime FastAPI. |

### Skema Supabase yang ditemukan

- `001_schema.sql`: `packages`, `allergens`, `menus`, `menu_ingredients`, `customers`, `dietary_passports`, `orders`, `order_items`, `order_status_events`, `customer_feedback`, `audit_log`.
- `002_phone_unique.sql`: unique partial index untuk nomor telepon customer.
- `003_supplier_inventory.sql`: `suppliers`, `supplier_items`, `purchase_orders`, `po_items`, `notification_outbox`, `inventory_stocks`.
- `004_analytics_ml_and_interactions.sql`: kolom analytics pada order/order item serta `customer_likes` dan `cart_history`.

Catatan: `backend/app/services/rag_ai_service.py` membaca tabel `documents`, tetapi tabel tersebut tidak dibuat oleh migration Supabase yang ada di repository. Itu adalah dependency runtime yang belum terdefinisi di schema repo ini.

## 2. Pemetaan fitur dan fungsi

### Allergy Guard

**Ditemukan sebagai logika deterministik di backend**, walaupun tidak ada fungsi bernama persis `Allergy Guard`.

- `backend/app/services/safety_service.py`
  - `resolve_exclusions`: menggabungkan alergi yang dipilih dengan passport customer.
  - `check_menu`: membandingkan allergen menu dengan exclusion dan menghasilkan `SAFE`, `CAUTION`, atau `BLOCKED`.
  - `check_day`, `check_options`, `check_day_options`, `check_selected`: variasi pemeriksaan menu/day/selection.
  - `build_report`: membangun safety report.
- `backend/app/repositories/catalog_repo.py`
  - `_critical_ingredient`, `_detect_codes`, `_rows_to_menu`: menurunkan kode allergen dari data menu/ingredient.
- `backend/app/services/order_service.py`
  - `validate_allergens`, `validate_selections`, `build_safety_report`, `create_order`.
  - `create_order` menolak order apabila report berstatus `BLOCKED`.
- API terkait: `backend/app/api/routers/catalog.py` (`service_week`, `preview_safety`), `orders.py` (`create_order`), dan `customers.py` (passport).

**Duplikasi/varian lain:**

- `telegram_bot.py`: `check_menu_allergy_warning` memakai keyword/map alergen dan hanya memberi warning; tidak memanggil `safety_service` dan tidak menjadi hard block.
- `frontend/src/pages/OrderPage.tsx`: `checkMenuConflict` melakukan substring check lokal; pengguna dapat melanjutkan melalui `riskAccepted`.
- `data.py`: `detect_allergy_risks` adalah implementasi legacy berbasis keyword.

### Rekomendasi menu AI Chef BOB / RAG

- `backend/app/services/rag_ai_service.py`
  - `get_customer_profile_and_history`: mengambil profile, passport, dan histori order.
  - `get_live_catalog_from_db`: mengambil katalog aktif.
  - `search_rag_documents`: pencarian dokumen dengan `ILIKE`; bukan vector search pada kode aktif ini.
  - `generate_rag_answer`: routing jawaban untuk rekomendasi menu, allergen, histori, RFM, supply chain, dan pertanyaan umum.
- `backend/app/services/langflow_service.py`
  - `LangflowService.ask`: memanggil Langflow jika terkonfigurasi, atau fallback ke `generate_rag_answer`.
  - `_build_payload`: mengirim konteks sebagai teks prompt.
- `backend/app/api/routers/ai.py`
  - `consult`: konsultasi AI umum.
  - `menu_suggestion`: menghitung `safety_service.build_report` lebih dahulu, lalu meminta AI menyusun jawaban natural-language.
- `telegram_bot.py`
  - `ask_langflow`, `get_langflow_response`, dan `alt_menu`: bot mengirim prompt langsung ke Langflow; fallback dapat mengimpor `generate_rag_answer`.
- Frontend: `frontend/src/pages/AiPage.tsx` (`handleSendMessage`) dan `frontend/src/services/ai.ts`.

`docs/langflow/original.json` juga memuat custom component seperti `DovaDataSource`, `DovaDietaryCheck`, `DovaCRMProfile`, `DovaRFM`, `DovaForecast`, `DovaInventory`, dan `DovaSupplierPO`. Di dalam export itu terdapat fungsi seperti `check_dietary`, `compute_rfm`, `forecast_demand`, dan `rank_suppliers_and_draft_po`; statusnya hanya artefak flow, bukan fungsi Python runtime yang ditemukan di backend.

### RFM

**Ditemukan di runtime backend.**

- `backend/app/services/analytics_ml_service.py`: `calculate_crm_rfm_segments` menghitung recency, frequency, monetary, score, dan segment seperti `Champions`, `Loyal Customers`, `At Risk`, dan `Hibernating`.
- `backend/app/api/routers/admin.py`: `get_rfm_crm_segments` memakai fungsi tersebut.
- `backend/app/services/rag_ai_service.py`: memakai hasil RFM untuk konteks jawaban AI.

**Bug yang ditemukan:** `backend/app/api/routers/customers.py` (`get_customer_rfm`) memanggil `calculate_rfm_crm_segments`, sedangkan fungsi yang tersedia bernama `calculate_crm_rfm_segments`. Endpoint customer RFM tersebut berpotensi gagal dengan `AttributeError`.

### Churn

**Tidak ditemukan sebagai implementasi aktif** berupa fungsi/model/endpoint churn khusus.

- Segment RFM `At Risk` dan `Hibernating` bukan churn model.
- `docs/langflow/original.json` memuat referensi `CHURN`, `CHURNED`, dan marketing win-back, tetapi itu hanya export Langflow.
- Dokumentasi/proposal menyebut churn, namun implementasi runtime khusus tidak ditemukan.

### Forecast

**Ditemukan di runtime backend.**

- `backend/app/services/analytics_ml_service.py`
  - `calculate_supply_chain_ml_forecast`: forecast demand harian dan proyeksi material.
  - `calculate_transaction_demand_insights`: insight transaksi, tren, top dishes, dan forecast operasional.
- `backend/app/api/routers/admin.py`: `get_supply_chain_ml`, `get_demand_insights`.
- `backend/app/api/routers/supplier.py`: `supplier_demand_forecast`.
- `backend/app/services/rag_ai_service.py`: memakai fungsi forecast untuk pertanyaan supply-chain.

Forecast aktif menggunakan histori order, moving average/regresi sederhana, fallback histori, serta beberapa nilai rencana hardcoded.

### Safety stock dan ROP

**Ditemukan dalam satu fungsi supply-chain, bukan fungsi terpisah.**

- File: `backend/app/services/analytics_ml_service.py`.
- Fungsi: `calculate_supply_chain_ml_forecast`.
- Rumus yang terlihat:
  - safety stock memakai `Z = 1.65`, sigma demand material, dan lead time tetap `L = 2.0`.
  - ROP = kebutuhan harian material × lead time + safety stock.
  - `needs_reorder` aktif ketika stock <= ROP.
  - `suggested_order_qty` adalah kekurangan terhadap target, bukan ROQ/EOQ.

Tidak ditemukan BOM explosion yang lengkap atau lead time per supplier di implementasi aktif; kode memakai faktor material generik.

### ROQ / EOQ

**Tidak ditemukan.** Pencarian terhadap `ROQ`, `EOQ`, dan `economic order quantity` tidak menemukan implementasi aktif, migration, frontend logic, maupun fungsi yang ekuivalen secara eksplisit.

### Draft PO

**Persistence schema dan workflow supplier ditemukan, tetapi pembuatan draft PO otomatis tidak ditemukan di runtime aktif.**

- Schema: `supabase/migrations/003_supplier_inventory.sql` membuat `purchase_orders` dan `po_items`.
- API: `backend/app/api/routers/supplier.py` (`list_pos`, `respond_po`, `supplier_summary`, `supplier_demand_forecast`).
- Admin: `backend/app/api/routers/admin.py` (`list_suppliers_and_pos`).
- Forecast mengembalikan `auto_po_recommendations` secara in-memory, tetapi tidak ditemukan insert runtime ke `purchase_orders`/`po_items` dari hasil forecast.
- `docs/langflow/original.json` memiliki fungsi export `rank_suppliers_and_draft_po`, tetapi tidak terbukti terhubung ke FastAPI runtime.

### Pembayaran dan webhook

**Webhook gateway tidak ditemukan.**

- `backend/app/services/invoice_service.py`: `generate_invoice_number`, `build_invoice`, `ensure_invoice_persisted`, `set_payment_status`.
- `backend/app/api/routers/admin.py`: endpoint `set_payment` hanya untuk perubahan status pembayaran secara manual oleh admin.
- `backend/app/services/order_service.py`: order baru berstatus `UNPAID` dan invoice dapat dipersist.
- `frontend/src/pages/OrderPage.tsx`: `handleSimulatePaymentSuccess` hanya mengubah state UI/toast dan navigasi; tidak memanggil payment gateway atau webhook.
- Tidak ditemukan endpoint/function untuk `/webhooks/payment`, Midtrans, signature verification, idempotency, atau callback gateway.
- Frontend menampilkan simulasi QRIS/VA dengan data hardcoded.

## 3. Duplikasi antara bot Telegram dan web/API

**Ya, duplikasi cukup signifikan dan ada perbedaan enforcement.**

| Area | Web/API | Telegram/legacy | Dampak |
|---|---|---|---|
| Database | Supabase/Postgres melalui `backend/app/repositories/supabase.py` | Astra langsung di `telegram_bot.py` dan `data.py` | Profile, menu, dan order tidak memakai satu source of truth. |
| Katalog | `catalog_repo.py` dan tabel `menus`/`menu_ingredients` | `get_daily_menu_options`, Astra, dan `CURATED_DAILY_OPTIONS` | Katalog dapat berbeda. |
| Alergen | `safety_service.py` + `catalog_repo.py` | `check_menu_allergy_warning` + keyword map bot | Algoritma dan level blocking berbeda. |
| Order | `order_service.create_order` menulis `orders`/`order_items` Supabase | `create_weekly_order` menulis `kitchen_orders` Astra | Dua format dan dua jalur order. |
| AI | `LangflowService.ask` dan router `/ai/*` | `requests.post` langsung melalui `get_langflow_response` | Prompt, fallback, dan konteks dapat berbeda. |
| Passport/profile | `customers` + `dietary_passports` | `user_profiles` flat/legacy | Data pantangan tidak otomatis tersinkron. |

Tambahan: `OrderPage` yang aktif saat ini bahkan tidak memanggil `ordersService.create`; alur checkout-nya masih simulasi UI. Jadi hard gate backend belum menjadi satu-satunya jalur yang digunakan frontend.

## 4. Apakah LLM dapat memengaruhi filter alergen?

**Jawaban: ya untuk beberapa jalur rekomendasi, tetapi tidak untuk hard gate `create_order` backend. Enforcement belum end-to-end.**

- `POST /orders` memakai `safety_service` secara deterministik dan menolak report `BLOCKED`; keputusan tersebut tidak diserahkan ke LLM.
- `/ai/menu-suggestion` menghitung safety report sebelum memanggil AI. Days/menu yang aman berasal dari kode, sedangkan LLM menyusun jawaban.
- `/ai/consult` meneruskan pertanyaan ke Langflow/fallback dan menampilkan output model; endpoint ini bukan validator alergen. Pada route ini passport server tidak diteruskan sebagai objek terstruktur ke `ai_client.ask`.
- `LangflowService._build_payload` memasukkan konteks passport sebagai teks prompt. Jika flow memakai instruksi prompt untuk filtering, itu bukan enforcement kode.
- Telegram `alt_menu` memasukkan pantangan ke prompt dan memakai jawaban Langflow tanpa post-validation terstruktur terhadap `safety_service`.
- Fallback `generate_rag_answer` memiliki heuristic sendiri; beberapa cabang memakai kata alergen dari pertanyaan, bukan selalu passport customer.
- `OrderPage` melakukan warning lokal dan mengizinkan `riskAccepted`, sehingga UI aktif tidak setara dengan hard block backend.

Kesimpulan: jangan menganggap rekomendasi LLM sebagai bukti menu bebas alergen. Jalur order backend memiliki guard kode, tetapi jalur bot, konsultasi AI, dan checkout frontend aktif belum seluruhnya melewati guard yang sama.

## 5. Ringkasan temuan kritis

1. Allergy Guard backend ditemukan dan deterministik, tetapi bot dan frontend memiliki implementasi terpisah yang lebih lemah.
2. Web/API memakai Supabase, sedangkan bot masih memakai Astra; order, katalog, dan passport terduplikasi.
3. RFM aktif, tetapi endpoint customer RFM memiliki mismatch nama fungsi.
4. Forecast, safety stock, dan ROP aktif; ROQ/EOQ tidak ditemukan.
5. Schema PO dan endpoint respons/list ditemukan, tetapi generator draft PO otomatis runtime tidak ditemukan.
6. Churn khusus dan payment webhook tidak ditemukan di runtime aktif.
7. Banyak capability seperti churn dan `rank_suppliers_and_draft_po` hanya terlihat di `docs/langflow/original.json` atau dokumentasi, bukan bukti wiring runtime.
8. Tabel `documents` yang dibutuhkan RAG tidak didefinisikan pada migration Supabase repository.

## 6. Tambahan audit Langflow dari prompt lanjutan

- Export `langflow/Dova Kitchen — CRM Dietary RFM Forecast Supply Chain Marketing (2).json` terverifikasi secara statis memiliki 23 node dan 20 edge; `docs/langflow/original.json` memiliki 23 node dan 19 edge. Ini hanya artefak, bukan bukti deployment/live execution.
- `DovaDataSource` pada export utama memiliki `use_sample=True`.
- Supabase Vector Store pada export mereferensikan tabel `documents` dan RPC `match_documents`; keduanya tidak ditemukan pada migration Supabase yang diperiksa.
- `backend/app/services/langflow_service.py:LangflowService.ask` dapat fallback ke `generate_rag_answer` saat Langflow tidak terkonfigurasi, timeout, error jaringan, atau request gagal. Karena itu response AI yang tampak sukses belum membuktikan Langflow aktif.
- `LangflowService.health` hanya memeriksa endpoint `/api/v1/version`; belum membuktikan flow executable, model reachable, vector retrieval ready, atau live data ready.
- `Settings.langflow_run_url` memakai `LANGFLOW_FLOW_ID`; export juga memiliki `endpoint_name`, tetapi validasi bahwa keduanya cocok tidak ditemukan.
- Belum ditemukan `AI_MODE`, `DATA_MODE`, request-ID/source/latency proof, readiness breakdown, controlled-failure report, atau live smoke-test evidence. Status live harus dianggap `LIVE NOT VERIFIED` sampai bukti tersedia.
- Gate wajib sebelum Chef BOB/admin AI disebut integrated: inventaris semua caller; validasi config tanpa secret; bukti healthy live untuk Chef BOB dan admin AI; failover mode yang eksplisit; vector/RAG scope; dan rantai Allergy Guard tetap deterministik dengan backend post-filter serta checkout revalidation.
