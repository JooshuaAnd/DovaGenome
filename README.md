# DovaGenome — Precision Catering

Catering makan siang mingguan dengan **profil pantangan per pelanggan**, bot
Telegram untuk memesan, dan papan kerja dapur untuk eksekusi harian.

```
Pelanggan  ──►  Telegram Bot  ──►  FastAPI  ──►  Supabase/Postgres  ──►  Papan Kerja Dapur  ──►  Diantar
                                        ▲
Landing Page  ──►  deep-link  ──────────┘
Admin Portal  ──►  katalog (menu / alergen / paket)
```

## Berkas

| Berkas | Untuk siapa | Isi |
| --- | --- | --- |
| `backend/app/main.py` | — | Aplikasi FastAPI: middleware, lifecycle, router (`/api/*`) |
| `backend/app/core/config.py` | — | Satu-satunya sumber semua environment variable |
| `backend/app/repositories/supabase.py` | — | Koneksi Supabase/Postgres (sumber data aktif) |
| `backend/app/services/langflow_service.py` | — | Satu-satunya jalan keluar untuk AI; retry + parse 3 bentuk balasan |
| `backend/scripts/seed_staff.py` | Admin | Membuat akun admin/kitchen pertama |
| `frontend/src/services/http.ts` | — | Base URL + prefiks API untuk semua panggilan |
| `frontend/` | Klien / Admin / Dapur | Antarmuka web React + Vite + Tailwind + Lucide Icons |
| `telegram_bot.py` | Pelanggan | Alur pemesanan 3 langkah, consultations AI, Dietary Passport, status pesanan |
| `telegram_admin_bot.py` | Admin | Status, stok kritis, forecast, batch, approval PO, invoice supplier |
| `telegram_supplier_bot.py` | Supplier | PO tenant sendiri, konfirmasi, perubahan, goods receipt, invoice, tagihan |
| `data.py` | — | Lapisan data bersama: status, helper waktu WIB, katalog + fallback, deep-link |
| `seed_catering_data.py` | Admin | Mengisi paket, alergen, dan menu ke DB |

## Menjalankan

Aplikasi ini menggunakan **FastAPI + Supabase / Postgres (Backend) dan React + Vite (Frontend)**.

```
Pelanggan ──► React (Vite)  ──►  FastAPI  ──►  Supabase / Postgres
                     ▲             │
                     └── Telegram Bot ──► Langflow / Gemini RAG (AI)
```

### 1. Menjalankan Backend & Frontend

```powershell
# 1. Kredensial
Copy-Item .env.example .env
code .env

# 2. Dependency Python
python -m pip install -r backend\requirements.txt

# 3. Backend (Terminal 1)
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 4. Frontend (Terminal 2)
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Cek backend:

| Endpoint | Isi |
| --- | --- |
| `GET /api/health` | `status` `ok` / `degraded`, status koneksi database |
| `GET /api/health/langflow` | `reachable` + versi Langflow |
| `GET /api/health/config` | Ringkasan konfigurasi non-rahasia |

Akun staff pertama (endpoint `/api/admin/staff` hanya bisa dipakai admin yang
sudah ada, jadi akun pertama harus dibuat lewat skrip):

```powershell
python backend\scripts\seed_staff.py --username admin --password "rahasia-kuat"
python backend\scripts\seed_staff.py --username dapur --role kitchen --password "rahasia-kuat"
```

### 2. Menjalankan Bot Telegram (Opsional)

```powershell
python -m pip install -r requirements.txt
# Isi tiga token berbeda; jangan gunakan token yang sama untuk tiga bot.
python telegram_bot.py
# Terminal terpisah:
python telegram_admin_bot.py
# Terminal terpisah:
python telegram_supplier_bot.py
```

Konfigurasi bot:

- `TELEGRAM_CUSTOMER_BOT_TOKEN` untuk Customer Bot (nama `TELEGRAM_TOKEN`
  masih diterima sebagai fallback legacy).
- `TELEGRAM_ADMIN_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_IDS`, dan
  `TELEGRAM_ADMIN_CUSTOMER_ID` untuk Admin Bot.
- `TELEGRAM_SUPPLIER_BOT_TOKEN` untuk Supplier Bot. Chat supplier harus
  tertaut ke akun supplier aktif; bot tidak membaca Supabase secara langsung.
- `DOVAGENOME_INTERNAL_TOKEN` mengamankan bridge server-to-server.
- `ADMIN_STOCK_ALERT_HOUR_WIB` mengatur jam queue alert harian (default `8`);
  proses Admin Bot harus tetap online agar daemon lokal menjalankannya.

Semua bot adalah thin client FastAPI. Status `PENDING` pada notification
outbox berarti menunggu worker/provider Telegram, bukan bukti pesan sudah
terkirim. Astra tidak lagi menjadi jalur data; health akan menampilkan
`database_source=supabase_postgres` dan `astra_state=OFFLINE_LEGACY`.

## Alur pemesanan

Pelanggan selalu tahu sedang di langkah berapa — tiap layar menampilkan
`📍 Langkah X dari 3` plus tombol **🏠 Menu utama**.

```
1️⃣  Pesan Paket Mingguan   → pilih paket (6 hari / hari kerja / 3 hari)
2️⃣  Tandai pantangan       → toggle alergen yang harus dihindari
3️⃣  Konfirmasi             → pratinjau menu, lalu kirim tiket ke dapur
```

Pada halaman order, pelanggan memilih slot **Sarapan / Makan siang / Makan
malam** secara terpisah. Beberapa menu pada hari yang sama diperbolehkan selama
slotnya berbeda; order lama tanpa slot dibaca sebagai makan siang.

Dokumen implementasi lanjutan: `PHASE_3_MEAL_SLOT_REPORT.md`,
`PHASE_5_INVENTORY_LOT_REPORT.md`, dan `PHASE_11_PRODUCTION_BATCH_REPORT.md`.

Perintah bot: `/start` `/order` `/menu` `/orders` `/passport` `/ai` `/cancel` `/help`

Admin procurement Telegram bersifat opt-in dan fail-closed. Isi
`TELEGRAM_ADMIN_CHAT_IDS` dengan chat ID admin yang diizinkan dan
`TELEGRAM_ADMIN_CUSTOMER_ID` dengan `customers.customer_id` role `admin` yang
dipakai untuk audit. Bot akan mengirim draft PO ke inbox admin; tombol
`Approve` dan `Kirim ke supplier` adalah dua tahap terpisah. `/procurement`
memuat ulang draft secara manual.

### Deep-link dari landing page

| Payload | Tujuan |
| --- | --- |
| `?start=order` | Langsung ke langkah 1 (pilih paket) |
| `?start=ai` | Langsung ke konsultasi AI |
| `?start=menu` | Pratinjau menu minggu ini |
| `?start=orders` | Status pesanan sendiri |
| `?start=passport` | Dietary Passport |

## Alur operasional di dapur

```
PENDING   Menunggu Dimasak  🔥 Mulai Masak
PREPARING Sedang Dimasak    📦 Tandai Siap Kirim
READY     Siap Dikirim      🚚 Selesai & Kirim
COMPLETED Selesai Diorder   —  (arsip)
CANCELLED Dibatalkan        —  (khusus admin)
```

Semua perubahan katalog di Admin Portal dibaca ulang bot maksimal 2 menit
 kemudian, dan langsung dipakai pratinjau menu di bot.

## Mode demo

Jika database belum tersambung atau ingin mencoba simulasi tanpa koneksi backend, sistem mendukung mode demo (`DEMO_MODE=true`).