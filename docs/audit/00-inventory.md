# Inventory Komprehensif — Dapur Harian (DovaGenome)

Dokumen ini disusun pada tahap **Fase R0 (Audit)** untuk mencatat inventaris lengkap seluruh aset sistem saat ini.

---

## 1. Halaman & Rute Frontend (`frontend/src`)

| Rute URL | Komponen Halaman | Deskripsi / Fungsi |
|---|---|---|
| `/` | [`LandingPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/LandingPage.tsx) | Halaman publik promosi katering & deep link ke bot |
| `/menu` | [`MenuPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/MenuPage.tsx) | Pratinjau menu mingguan publik |
| `/login` | [`LoginPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/LoginPage.tsx) | Masuk pelanggan (nama + HP) & staf (user + password) |
| `/order` | [`OrderPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderPage.tsx) | Wizard pemesanan makanan |
| `/passport` | [`PassportPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/PassportPage.tsx) | Profil Dietary Passport & manajemen alergi pelanggan |
| `/orders` | [`OrdersPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrdersPage.tsx) | Daftar riwayat pesanan pelanggan aktif |
| `/orders/:id` | [`OrderDetailPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderDetailPage.tsx) | Detail pesanan, status dapur & rincian menu |
| `/orders/:id/invoice` | [`InvoicePage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/InvoicePage.tsx) | Faktur / kwitansi rincian pembayaran |
| `/ai` | [`AiPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/AiPage.tsx) | Konsultasi kecocokan diet AI |
| `/admin` | [`AdminDashboardPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/admin/AdminDashboardPage.tsx) | Portal metrik & ringkasan manajemen |
| `/admin/daily-menu` | [`DailyMenuEditorPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/admin/DailyMenuEditorPage.tsx) | Editor menu mingguan & bahan |
| `/kitchen` | [`KitchenPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/kitchen/KitchenPage.tsx) | Papan kerja eksekusi dapur (KDS) |

---

## 2. API Endpoints Backend (`backend/app/api/routers`)

### Autentikasi (`routers/auth.py`)
- `POST /api/auth/customer` — Masuk/daftar pelanggan otomatis (nama + no HP).
- `POST /api/auth/login` — Masuk akun staf (kata sandi).
- `GET /api/auth/me` — Profil akun aktif dari Bearer JWT.
- `POST /api/auth/telegram/resolve` — Resolusi token deep-link Telegram.

### Katalog (`routers/catalog.py`)
- `GET /api/catalog/packages` — Daftar paket katering mingguan.
- `GET /api/catalog/allergens` — Daftar alergen aktif & risikonya.
- `GET /api/catalog/menus` — Daftar semua menu makanan aktif.
- `GET /api/catalog/menus/week` — Read-model menu mingguan per hari.

### Pelanggan & Paspor Alergi (`routers/customers.py`)
- `GET /api/customers/me/passport` — Membaca Dietary Passport pelanggan.
- `PUT /api/customers/me/passport` — Menyimpan/memperbarui Dietary Passport pelanggan.

### Pesanan (`routers/orders.py`)
- `GET /api/orders` — Daftar pesanan pelanggan yang sedang masuk.
- `POST /api/orders` — Membuat pesanan baru + tiket dapur.
- `GET /api/orders/{order_id}` — Detail pesanan dan verifikasi safety.
- `PATCH /api/orders/{order_id}` — Perubahan pesanan (hanya bila status PENDING).
- `GET /api/orders/{order_id}/timeline` — Riwayat status tiket dapur.
- `GET /api/orders/{order_id}/invoice` — Data faktur resmi pesanan.

### Dapur & Admin (`routers/kitchen.py` & `routers/admin.py`)
- `GET /api/kitchen/orders` — Antrean pesanan aktif tim dapur.
- `POST /api/kitchen/orders/{id}/advance` — Memajukan status tiket dapur.
- `GET /api/admin/metrics` — Metrik operasional harian & mingguan.
- `POST /api/admin/staff` — Manajemen staf internal.

---

## 3. Skema Basis Data PostgreSQL (`supabase/migrations/`)

1. **`customers`** — Identitas pelanggan (id, username, phone, display_name, role, telegram_chat_id).
2. **`dietary_passports`** — Profil kesehatan & alergi per customer (allergies, intolerances, medical, safety_notes).
3. **`packages`** — Definisi paket katering mingguan (kode, nama, hari, harga).
4. **`allergens`** — Definisi alergen dan risiko kesehatan.
5. **`menus`** — Data menu hidangan harian (id, hari, nama, deskripsi, option_index).
6. **`menu_ingredients`** — Bahan baku per hidangan + penanda potensi alergen + alat steril.
7. **`orders`** — Pesanan pelanggan (order_id, customer_id, package_code, status, subtotal, total).
8. **`order_items`** — Pilihan menu harian per pesanan.
9. **`order_status_events`** — Append-only timeline status tiket dapur.
10. **`customer_feedback`** — Ulasan rating dan komentar.
11. **`audit_log`** — Log audit perubahan data administratif.

---

## 4. State Management & Dependensi Frontend

- **State:** React Local State (`useState`, `useMemo`), React Context (`useAuth`), Custom Hooks (`useApi`, `useAsync`).
- **UI & Styling:** Tailwind CSS 4, Radix UI primitives, Lucide React icons, Sonner toast.
- **Routing:** React Router DOM v7.
- **Build Tool:** Vite 6, TypeScript 5.8 (Strict).

---

## 5. Klien Bot Telegram (`telegram_bot.py`)

- **Framework:** `pyTelegramBotAPI` (telebot).
- **Arsitektur Saat Ini:** Monolitik 1.764 baris kode, terhubung **langsung ke Astra DB** secara independen dan menduplikasi aturan bisnis katering.
