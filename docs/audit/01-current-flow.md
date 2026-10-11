# Alur Saat Ini (Current Flow) — Web & Telegram

Dokumen ini memetakan diagram alur sistem aktual yang berjalan sebelum perbaikan arsitektur Fase R.

---

## 1. Alur Web Saat Ini (`frontend`)

```mermaid
flowchart TD
    A[Buka http://localhost:5173] --> B[Halaman Landing Page]
    B --> C{Sudah Login?}
    C -->|Belum| D[Halaman /login]
    D -->|Input Nama + HP| E[POST /api/auth/customer]
    E -->|Sukses Token JWT| F[Redirect ke /order]
    
    C -->|Sudah| F
    
    subgraph Wizard Web
        F --> W1[Langkah 1: Alergi]
        W1 --> W2[Langkah 2: Catatan Diet]
        W2 --> W3[Langkah 3: Pilih Menu 3/hari]
        W3 --> W4[Langkah 4: Jumlah Porsi]
        W4 --> W5[Langkah 5: Ringkasan Biaya]
        W5 --> W6[Langkah 6: Alamat & Kurir]
        W6 --> W7[Langkah 7: Bayar QRIS/VA]
        W7 --> W8[Langkah 8: Status Tiket Dapur]
    end
    
    W7 -->|Konfirmasi Bayar| G[POST /api/orders]
    G -->|201 Created| H[Tiket Dapur Dibuat]
```

### Karakteristik & Limitasi Web Saat Ini:
1. State progres disimpan di memori klien (React State); bila browser ditutup dan dibuka di perangkat lain, progres belum tersambung via server-side `OrderDraft`.
2. Timer countdown 10 menit berjalan di browser, namun belum terintegrasi dengan job pembatalan otomatis di server (background scheduler) jika batas waktu habis.
3. Alamat tersimpan masih berupa mock statis di antarmuka (belum ada CRUD tabel `addresses` di database).

---

## 2. Alur Bot Telegram Saat Ini (`telegram_bot.py`)

```mermaid
flowchart TD
    T1[Pengguna kirim /start] --> T2[Menu Utama Bot]
    T2 --> T3[Pilih Paket Katering - 1 dari 3]
    T3 --> T4[Tandai Pantangan Alergi - 2 dari 3]
    T4 --> T5[Konfirmasi Pesanan - 3 dari 3]
    T5 -->|Menulis Langsung| T6[(Astra DB: kitchen_orders)]
    T6 --> T7[Notifikasi Pesanan Diterima]
```

### Masalah Arsitektur Bot Saat Ini:
1. **Duplikasi Logika Bisnis:** Bot tidak memanggil FastAPI backend, melainkan mengimpor modul `data.py` dan memanggil koneksi Astra DB secara langsung.
2. **Inkonsistensi Alur:** Bot memakai alur 3 langkah ringkas, sementara Web memakai wizard pilihan menu harian.
3. **Pilihan Menu Harian Tidak Tersedia di Bot:** Bot hanya memilih paket (3, 5, atau 6 hari) tanpa membiarkan pelanggan memilih salah satu dari 3 menu harian per hari layanan.
