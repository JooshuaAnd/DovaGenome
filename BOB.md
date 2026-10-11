# AGENTS.md — Dova Kitchen (Precision Catering)

Sumber kebenaran tunggal (*single source of truth*) untuk seluruh agen AI dan pengembang.

---

## I.1 Peran dan Aturan Kerja Agent
Kamu adalah tim engineering senior (backend, frontend, DevOps, keamanan). Bangun dan sempurnakan Dova Kitchen: katering harian (3 menu per hari) dengan website untuk empat peran (pelanggan, kitchen, admin, supplier) dan bot Telegram, semuanya memakai satu backend.

### Aturan Wajib:
1. **Proyek sudah ada.** Audit dulu, jangan menulis ulang dari nol. Hapus kode mati hanya setelah terbukti tidak dipakai.
2. **Tulis tes yang gagal dulu (regression test), lalu perbaiki.** Satu branch per fase, commit kecil.
3. **Tidak ada logika bisnis di klien (web, Mini App, bot).** Semua aturan, harga, alergi, jendela tanggal, dan status ada di backend.
4. **Keselamatan alergi di atas segalanya.** Sistem tidak pernah menyatakan sebuah menu aman; hanya melaporkan konflik yang terdeteksi.
5. **Rahasia hanya di .env (gitignore).** Nomor telepon admin dan supplier hanya di .env atau seed, tidak di source code, dan disamarkan di log.
6. **Langflow tidak diubah oleh agent.** Hanya dipanggil sesuai kontrak I.6.
7. **Jika ada keputusan ambigu, buat asumsi eksplisit di docs/decisions.md dan lanjut.**
8. **Akhiri tiap fase dengan:** file yang berubah, cara menjalankan, hasil tes, dan sisa pekerjaan.

---

## I.2 Stack dan Struktur (Pertahankan yang Ada)
- **Backend (`backend/app/`):** FastAPI, Pydantic v2, PostgreSQL di Supabase lewat `ThreadedConnectionPool` (psycopg2) dengan SQL mentah di `repositories/`. Pertahankan pola berlapis: `api/routers` memanggil `services`, yang memanggil `repositories`, dengan validasi di `schemas`. Tidak ada SQL di service dan tidak ada logika bisnis di router.
- **Frontend (`frontend/src/`):** React 18, Vite, TypeScript strict, Tailwind, shadcn/ui, React Router, `services/http.ts` sebagai klien HTTP tunggal.
- **Tambahan Baru:**
  - `backend/app/worker/`: proses terpisah dengan APScheduler untuk job terjadwal (expire pembayaran, MRP harian, ringkasan harian). Pakai `pg_try_advisory_lock` agar tidak berjalan ganda.
  - `backend/app/bot/`: bot Telegram dengan aiogram 3, sebagai klien tipis yang memanggil service backend yang sama.
  - `backend/app/services/ai_gateway.py`: satu-satunya jalur ke Langflow.
  - `backend/migrations/` / `supabase/migrations/`: migration SQL bernomor berurutan.
  - Tes: pytest + httpx (backend), Vitest dan Playwright (frontend). Docker Compose: api, worker, bot, web. GitHub Actions: lint dan tes.

### Peta Berkas & Perubahan yang Dibutuhkan:
- `core/domain.py`: Hari layanan jadi konfigurasi (bawaan Senin sampai Minggu, bukan hanya Senin sampai Sabtu); normalisasi nomor telepon; daftar alergen resmi.
- `core/config.py`: Tambah `LANGFLOW_*`, `ADMIN_PHONES`, `SUPPLIER_PHONES`, `OTP_*`, `PAYMENT_*`, `BOT_TOKEN`, `WEBAPP_URL`, `AI_ENABLED`.
- `services/auth_service.py`: Login pelanggan nomor HP + OTP; login staf (admin, kitchen, supplier); audience JWT per peran.
- `services/safety_service.py`: Ganti ke pemetaan bahan ke alergen (I.4.4).
- `services/order_service.py`: Draft server, total di server, pembayaran, aturan masak setelah bayar.
- `services/catalog_service.py`: Jendela menu (I.4.3), publish menu pekan depan.
- `services/dashboard_service.py`: KPI admin dan produksi kitchen.
- `services/langflow_service.py`: Diganti oleh `ai_gateway.py` sesuai I.6.
- `api/routers/*`: Tambah payments, webhooks, supplier, procurement, inventory, ai, notifications.
- `pages/OrderPage.tsx`: Wizard satu keputusan per layar (I.4.2).
- `pages/LoginPage.tsx`: Nomor HP + OTP untuk pelanggan; username + password untuk staf.
- `pages/kitchen`, `pages/admin`: Diperluas; tambah `pages/supplier`.

---

## I.3 Empat Portal Web dan Hak Akses

| Portal | Rute | Login | Fungsi Utama |
|---|---|---|---|
| Pelanggan | `/` | Nomor HP + OTP | Landing, wizard pesan, bayar, lacak, riwayat, faktur, paspor diet |
| Kitchen | `/kitchen` | Username + password | Lembar produksi, papan tiket (hanya pesanan lunas), penerimaan barang, stok, waste, label |
| Admin | `/admin` | Username + password | Dashboard, menu, bahan dan resep, pelanggan dan CRM, pesanan, supplier, PO, stok, asisten AI, pengaturan, pengguna, audit |
| Supplier | `/supplier` | Username + password, subdomain terpisah | PO masuk, terima/tolak/sebagian, ASN, katalog harga, invoice, performa |

*Setiap peran memakai audience JWT sendiri; token pelanggan tidak bisa membuka endpoint staf dan sebaliknya.*

### Matriks Hak Akses:
| Area | Pelanggan | Kitchen | Admin | Supplier |
|---|---|---|---|---|
| Menu, resep | baca menu | baca | tulis | tidak |
| Pesanan | miliknya | pesanan lunas saja | semua | tidak |
| Data pelanggan | miliknya | alergi dan catatan di tiket | semua | tidak pernah |
| Stok dan penerimaan | tidak | tulis | baca dan koreksi | tidak |
| PO | tidak | baca | setujui | PO miliknya saja |
| Harga katalog supplier | tidak | tidak | setujui | ajukan |
| Asisten AI | tidak | tidak | ya | tidak |

*Supplier hanya melihat PO, katalog, dan invoice miliknya. Wajib ada tes isolasi antar supplier.*

---

## I.4 Aturan Bisnis Inti

### I.4.1 Login Pelanggan: Hanya Nomor Telepon
- Tidak ada kolom nama saat login. `customers.name` boleh kosong; nama penerima diisi di langkah alamat. Tampilan cadangan: `Pelanggan •••1234`.
- Satu fungsi normalisasi nomor di `core/domain.py` (`08xx` -> `+628xx`; `628xx` -> `+628xx`), dengan unique index.
- Web: `POST /api/auth/otp/request` dan `/verify`. OTP 6 digit dari secrets, hash + salt, kedaluwarsa 5 menit, sekali pakai, maksimal 5 percobaan lalu kunci 15 menit, rate limit 3 permintaan per 10 menit per nomor dan per IP. Respons permintaan sama untuk nomor baru dan lama. Pengiriman lewat interface `OtpSender` (adapter WhatsApp atau SMS; mode dev mencetak ke log hanya jika `ENV=dev`).
- Mini App Telegram: nomor diambil dari tombol bagikan kontak yang diverifikasi Telegram (`contact.user_id` sama dengan `from_user.id`), jadi tidak butuh OTP.
- Pelanggan lama otomatis dikenali; login lama (nama + HP tanpa verifikasi) dinonaktifkan karena profil alergi adalah data kesehatan.

### I.4.2 Wizard Pemesanan: Satu Keputusan Per Layar
Sama persis di web dan Mini App. Progres disimpan server sebagai `OrderDraft` (`current_step`), sehingga bisa mulai di web dan lanjut di Telegram.
1. Alergi (chip, plus catatan) -> 2. Catatan diet -> 3. Menu per hari (satu hari per layar, tab tanggal) -> 4. Porsi -> 5. Keranjang -> 6. Alamat (alamat tersimpan, label, nama penerima, catatan kurir) -> 7. Bayar (batas 10 menit) -> 8. Pelacakan.
- **Pelanggan lama:** layar pertama menampilkan kartu: *"Kamu tercatat alergi: X dan Y. Mau ada yang ditambah atau dikurangi?"* dengan pilihan: `Tidak ada perubahan`, `Tambah`, `Kurangi`. Perubahan disimpan dengan riwayat (`allergy_history`: siapa, kapan, sebelum, sesudah), dan profil dikonfirmasi ulang tiap 30 hari atau setelah lama tidak memesan. Alamat lama jadi pilihan cepat (utama, label Rumah/Kantor).

### I.4.3 Jendela Menu
- Zona waktu: `Asia/Jakarta`. Dihitung hanya di backend (`get_orderable_window(now)`) dengan tes tiap hari dalam sepekan.
- Mulai besok (atau lusa jika lewat cutoff, bawaan 20:00 malam sebelumnya, konfigurabel); berakhir di Minggu pekan berjalan.
- Memesan hari Minggu menampilkan Senin sampai Minggu; memesan hari Kamis menampilkan Jumat sampai Minggu.
- Jika admin sudah mempublikasikan menu pekan depan, tampilkan juga hari-hari pekan depan dengan label *Minggu depan* dan tanggalnya. Jika belum, jangan tampilkan apa pun. Menu draft tidak pernah terlihat pelanggan.
- Tiap hari tepat 3 menu (divalidasi saat publish).

### I.4.4 Pencocokan Alergi (Pengganti Pencocokan Kata Persis)
- Tabel: `allergens`, `ingredients`, `ingredient_allergens` (confidence DIRECT atau POSSIBLE). Alergen menu diturunkan dari bahan resep, bukan diketik manual. Seed awal 9 alergen: kacang, susu, telur, gluten, kedelai, ikan, krustasea, moluska, wijen, beserta bahan turunannya (kecap = kedelai; tepung panko = gluten; keju dan mentega = susu; udang = krustasea; dst). Cocokkan dengan batas kata, bukan substring (agar mirin tidak terdeteksi sebagai mi).
- Hasil per menu:
  - `status`: `WARNING` | `NO_CONFLICT_DETECTED` | `DATA_INCOMPLETE`
  - `matched_allergens`: daftar alergen yang bentrok
  - `reasons[]`: alasan dalam Bahasa Indonesia (mis. *"Sebaiknya dihindari karena mengandung udang (krustasea), yang dapat memicu reaksi alergi berat."*)
  - `may_contain[]`: peringatan kontaminasi silang
- Menu WARNING tetap tampil dengan penanda merah, ikon, dan alasan; saat ditambah ke keranjang wajib konfirmasi eksplisit (*"Saya paham risikonya"*). Menu tanpa konflik diberi label *Tidak ada konflik terdeteksi* (bukan aman), plus keterangan bahwa informasi berasal dari resep dan untuk alergi berat sebaiknya konfirmasi ke tim.
- Pesanan dengan konfirmasi menu berisiko ditandai di tiket dapur dan dikirim sebagai notifikasi ke admin dan kitchen.
- Tes wajib: tiap alergen terhadap bahan turunannya, bahan tanpa data, banyak alergen sekaligus, dan tidak ada false negative pada minimal 30 kasus.

### I.4.5 Pembayaran dan Aturan Masak Setelah Bayar (ATURAN KERAS)
**Kitchen tidak boleh melihat, menghitung, atau memasak pesanan yang belum lunas.** Terapkan di empat lapis:
1. **Pembuatan tiket:** `kitchen_tickets` hanya dibuat di dalam transaksi webhook pembayaran setelah memverifikasi signature, jumlah, dan order id, serta perubahan `payments.status` dari pending ke paid (satu transaksi database dengan perubahan status order menjadi paid).
2. **Database:** trigger atau constraint yang menolak insert atau update `kitchen_tickets` jika `payments.status` bukan paid atau `paid_at` kosong.
3. **API:** `POST /api/kitchen/tickets/{id}/transition` mengembalikan `409 PAYMENT_REQUIRED` untuk pesanan tak lunas; endpoint antrean kitchen, lembar produksi, dan perhitungan kebutuhan bahan (MRP) hanya membaca pesanan paid.
4. **UI:** portal kitchen tidak pernah menampilkan pesanan belum lunas.
- **Detail pembayaran:** Total dihitung di server. Midtrans sandbox (QRIS dan VA) dibungkus `PaymentProvider`. Batas bayar 10 menit (`expires_at`). Worker tiap 30 detik menandai expired. Webhook diverifikasi signature & idempotent.

### I.4.6 Tiket Dapur
- State machine: `paid -> accepted -> cooking -> packed -> out_for_delivery -> delivered` (cabang: `cancelled`, `failed_delivery`).
- Satu pesanan multi-hari menghasilkan satu tiket per tanggal kirim. Setiap perubahan menyimpan `ticket_events` (append-only) dan memicu notifikasi. Tiket menampilkan alergi dan catatan pelanggan dengan latar merah.

---

## I.5 Bot Telegram: Notifikasi Otomatis ke Admin dan Supplier

### I.5.1 Fakta Teknis & Allowlist
Bot Telegram tidak bisa mengirim pesan ke nomor telepon; bot hanya bisa mengirim ke `chat_id` dari user yang pernah membuka bot dan menekan Start. Karena itu nomor admin dan supplier dipakai sebagai allowlist:
- `ADMIN_PHONES=+6281326332247`
- `SUPPLIER_PHONES=+6285866408193`
(Disimpan di `.env` lokal, disamarkan di log).

### I.5.2 Alur Penautan
1. Admin atau supplier buka bot, tekan Start, lalu kirim kontak (`request_contact`).
2. Validasi: `contact.user_id == message.from_user.id`.
3. Normalisasi nomor, cocokkan dengan allowlist staf / `staff_users.phone`. Simpan `telegram_chat_id` dan peran.
4. Notifikasi pending disimpan di `notification_outbox` status `pending_link` dan dikirim begitu tertaut.

### I.5.3 Matriks Notifikasi:
- Pesanan lunas -> Admin & Kitchen (ada alergi/menu berisiko ditandai khusus).
- Menu berisiko dipilih -> Admin & Kitchen (sorotan merah).
- Status tiket berubah -> Pelanggan (edit pesan di tempat).
- Pembayaran hampir habis / expired -> Pelanggan.
- Draf PO butuh persetujuan -> Admin (inline button Setujui / Tolak).
- PO disetujui & dikirim -> Supplier (inline button Terima / Tolak / Sebagian).
- Supplier menjawab PO -> Admin.
- Ringkasan harian 05:00 -> Admin (dari AI Langflow).

### I.5.4 Pengiriman Andal
- Outbox table: `notification_outbox` dengan dedupe_key, retry, backoff, rate limit.

### I.5.5 Identitas & Tampilan Bot
- Menu bot membuka Telegram Mini App (React yang sama dengan web).
- `/start`: Hero card dengan tombol Pesan sekarang (Mini App), Pesanan saya, Bantuan.
- HTML parse mode dengan escape terpusat, edit message in-place untuk update status.

---

## I.6 Integrasi Langflow yang Sudah Jadi (Jangan Diubah)
- Flow: `Dova Kitchen — CRM Dietary RFM Forecast Supply Chain Marketing`, endpoint `dova-kitchen-ai`.
- File ekspor: `docs/langflow/original.json`.
- Akses: Hanya admin, dilarang diekspos ke publik/pelanggan.
- Backend mengirim state JSON lewat tweaks ke node `CustomComponent-WpAGa` (`use_sample: false`, `json_text: <STATE JSON>`).
- Jika Langflow mati, seluruh fungsi backend tetap berjalan deterministik. Modul Python backend menyalin fungsi murni untuk RFM, forecast, inventory, dan ranking supplier.

---

## I.7 Supply Chain Otomatis
- Kebutuhan bahan dihitung deterministik di Python: pesanan lunas + sisa kapasitas forecast -> BOM explosion -> kurangi stok FEFO & PO berjalan -> safety stock & lead time -> pembulatan MOQ & pack size -> skor supplier -> draf PO.
- Ambang PO default: Rp1.000.000 (di bawah ini bisa auto-kirim untuk supplier tepercaya, di atasnya wajib persetujuan admin).
- Siklus PO: `draft -> pending_approval -> sent -> acknowledged -> partially_received -> received -> closed`.
- Pengecualian: substitusi bahan wajib lolos cek alergi dan diblokir otomatis jika menambah alergen pada pesanan lunas.

---

## I.8 Desain UI Total
- Kesan visual: bersih, premium, klinis-hangat, terpercaya.
- Design tokens:
  - Background: `--bg: #F7F6F2`, `--surface: #FFFFFF`, `--surface-2: #EFEDE7` (Gelap: `#12151A`, `#1B2027`, `#242A33`)
  - Text: `--text: #14213D`, `--text-muted: #5B6475` (Gelap: `#F1F3F7`, `#A3ABBA`)
  - Brand: `--brand: #14213D`, `--accent: #B8893A` (Gelap: `#E9EDF7`, `#D9AE63`)
  - Border: `--border: #E3E0D8` (Gelap: `#2F3640`)
  - Safe: `--safe: #1E7B53`, `--safe-bg: #E3F3EA` (Gelap: `#58C28E`, `#16302A`)
  - Caution: `--caution: #B45309`, `--caution-bg: #FDF0DC` (Gelap: `#F0A94B`, `#3A2A12`)
  - Danger: `--danger: #B42318`, `--danger-bg: #FDE8E6` (Gelap: `#FF8A7E`, `#3D1A17`)
- Font: Plus Jakarta Sans (self-host UI), Fraunces (display judul landing).
- Status keselamatan: Selalu Warna + Ikon + Teks (tidak boleh warna saja).
- Komponen: Button, Input, OTP 6 kotak, Chip alergen, MenuCard, AllergyBanner, WizardShell sticky bottom, BottomSheet, Toast, CountdownPill, DataTable, TicketTimeline.
