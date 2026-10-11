# Architecture Decision Records (ADR) & Catatan Keputusan

Dokumen ini mencatat keputusan arsitektur teknis yang disepakati selama siklus pengembangan sistem Dapur Harian.

---

## ADR-01: Memilih Pola Strangler (Bagian C: Mode Perbaikan) daripada Rewrite dari Nol
- **Konteks:** Proyek sudah memiliki basis kode berjalan di FastAPI (`backend`) dan React Vite (`frontend`) dengan koneksi Supabase PostgreSQL aktif.
- **Keputusan:** Menggunakan **Bagian C (Mode Perbaikan)** menggantikan Fase 0 dan Fase 1 dari Bagian B. Kami tidak menghapus atau menulis ulang sistem dari nol, melainkan mengaudit (`Fase R0`), memasang jaring pengaman tes (`Fase R1`), lalu memperbaiki alur pemesanan secara bertahap (`Fase R2` & `Fase R3`).
- **Konsekuensi:** Mengurangi risiko regresi, mempertahankan fitur yang sudah bekerja, dan menghemat waktu implementasi.

---

## ADR-02: Kebijakan Waktu Jendela Pemesanan (`get_orderable_window`)
- **Konteks:** Pemesanan bahan dan persiapan dapur membutuhkan waktu lead time yang pasti.
- **Keputusan:**
  1. Zona waktu wajib menggunakan `Asia/Jakarta` (WIB).
  2. Jam cutoff ditetapkan pukul **20:00 WIB**.
  3. Pemesanan sebelum 20:00 berlaku mulai H+1 (besok).
  4. Pemesanan setelah 20:00 berlaku mulai H+2 (lusa).
  5. Menu pekan depan hanya ditampilkan jika berstatus `published`.

---

## ADR-03: Bot Telegram sebagai Klien Tipis (Thin Client)
- **Konteks:** `telegram_bot.py` lama mengakses database langsung dan menduplikasi logika bisnis pemesanan.
- **Keputusan:** Seluruh logika bisnis (katalog, validasi alergen, pembuatan pesanan, pembayaran) dipusatkan di FastAPI backend. Bot Telegram hanya bertindak sebagai antarmuka input/output tipis yang memanggil endpoint HTTP API yang sama dengan web.
