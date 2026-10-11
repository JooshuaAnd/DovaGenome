# DovaGenome — Precision Catering

Catering makan siang mingguan dengan **profil pantangan per pelanggan**, bot
Telegram untuk memesan, dan papan kerja dapur untuk eksekusi harian.

```
Pelanggan  ──►  Telegram Bot  ──►  Astra DB  ──►  Papan Kerja Dapur  ──►  Diantar
                                        ▲
Landing Page  ──►  deep-link  ──────────┘
Admin Portal  ──►  katalog (menu / alergen / paket)
```

## Berkas

| Berkas | Untuk siapa | Isi |
| --- | --- | --- |
| `backend/app/main.py` | — | Aplikasi FastAPI: middleware, lifecycle, router (`/api/*`) |
| `backend/app/core/config.py` | — | Satu-satunya sumber semua environment variable |
| `backend/app/repositories/astra.py` | — | Koneksi Astra DB (gagal = exception jelas, bukan `None`) |
| `backend/app/services/langflow_service.py` | — | Satu-satunya jalan keluar untuk AI; retry + parse 3 bentuk balasan |
| `backend/scripts/seed_staff.py` | Admin | Membuat akun admin/kitchen pertama |
| `frontend/src/services/http.ts` | — | Base URL + prefiks API untuk semua panggilan |
| `landing_page.py` | Pelanggan (publik) | Situs marketing: menu minggu ini, paket, keamanan pangan, CTA ke bot |
| `telegram_bot.py` | Pelanggan | Alur pemesanan 3 langkah, consultations AI, Dietary Passport, status pesanan |
| `kitchen_dashboard.py` | Tim dapur | Papan eksekusi: Diterima → Dimasak → Dikemas → Diantar |
| `admin_kitchen_dashboard.py` | Admin | Analytics, papan kendali penuh, katalog menu/alergen/paket, pratinjau landing page, diagnosa sistem |
| `theme.py` | — | Design system (warna, tipografi, komponen HTML) |
| `data.py` | — | Lapisan data bersama: status, helper waktu WIB, katalog + fallback, deep-link |
| `seed_catering_data.py` | Admin | Mengisi paket, alergen, dan menu ke Astra DB (jalankan sekali) |

## Menjalankan

Repo ini berisi dua stack. **Stack utama (Phase 2+) adalah FastAPI + React.**
Stack Streamlit lama masih ada di root dan masih bisa dijalankan.

```
Pelanggan ──► React (Vite)  ──►  FastAPI  ──►  Astra DB
                     ▲             │
                     └── Telegram Bot ──► Langflow (AI)
```

### Stack utama — FastAPI + React

```powershell
# 1. kredensial
Copy-Item .env.example .env
code .env

# 2. dependency
python -m pip install -r backend\requirements.txt

# 3. backend — terminal 1. WAJIB dari folder backend/ karena import `app.`
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 4. frontend — terminal 2
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Cek backend:

| Endpoint | Isi |
| --- | --- |
| `GET /api/health` | `status` `ok` / `degraded`, `astra_connected`, status isi credential (butuh `DEBUG=true`) |
| `GET /api/health/langflow` | `reachable` + versi Langflow |
| `GET /api/health/config` | ringkasan konfigurasi non-rahasia |

`status: "degraded"` berarti Astra DB tidak tersambung. KDS dan admin tetap
jalan tetapi **kosong** — data contoh hanya muncul bila `DEMO_MODE=true`.

Akun staff pertama (endpoint `/api/admin/staff` hanya bisa dipakai admin yang
sudah ada, jadi akun pertama harus lewat skrip):

```powershell
python backend\scripts\seed_staff.py --username admin --password "rahasia-kuat"
python backend\scripts\seed_staff.py --username dapur --role kitchen --password "rahasia-kuat"
```

### Stack lama — Streamlit + bot

### 1. Siapkan kredensial

```powershell
Copy-Item .env.example .env
code .env
```

Isi minimal: `TELEGRAM_TOKEN`, `ASTRA_DB_API_ENDPOINT`, `ASTRA_DB_APPLICATION_TOKEN`,
dan `TELEGRAM_BOT_USERNAME` (tanpa `@`) agar tombol di landing page tahu bot mana
yang harus dibuka.

### 2. Pasang dependensi & isi data awal

Dependency root dipakai stack Streamlit. Skrip `run_*.ps1` memakai `.venv` kalau
ada, kalau tidak jatuh ke `python` sistem.

```powershell
python -m pip install -r requirements.txt
python seed_catering_data.py
```

### 3. Jalankan

Tiap halaman Streamlit berjalan di terminal sendiri:

```powershell
python -m streamlit run landing_page.py             # situs tamu
python -m streamlit run kitchen_dashboard.py        # dapur
python -m streamlit run admin_kitchen_dashboard.py  # admin
python telegram_bot.py                              # bot Telegram
```

Atau pakai skrip pintasan: `.\run_landing.ps1`, `.\run_dashboard.ps1`,
`.\run_admin.ps1`.

## Alur pemesanan

Pelanggan selalu tahu sedang di langkah berapa — tiap layar menampilkan
`📍 Langkah X dari 3` plus tombol **🏠 Menu utama**.

```
1️⃣  Pesan Paket Mingguan   → pilih paket (6 hari / hari kerja / 3 hari)
2️⃣  Tandai pantangan       → toggle alergen yang harus dihindari
3️⃣  Konfirmasi             → pratinjau menu, lalu kirim tiket ke dapur
```

Perintah bot: `/start` `/order` `/menu` `/orders` `/passport` `/ai` `/cancel` `/help`

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

Jika Astra DB tidak tersambung, ketiga halaman dashboard dan landing page tetap
jalan memakai data contoh — berguna untuk 미리 tinjau tampilan tanpa koneksi.