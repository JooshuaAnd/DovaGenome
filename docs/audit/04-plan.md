# Rencana Perbaikan Bertahap & Jawaban Audit Wajib (Fase R0)

Dokumen ini memuat **Daftar Periksa Wajib Audit** dan **Rencana Tindak Lanjut (Fase R1 s/d R3)** dengan pola Strangler (perbaikan bertahap, tanpa merusak fungsionalitas yang ada).

---

## 1. Jawaban Daftar Periksa Wajib Audit

| Pertanyaan Audit Wajib | Jawaban | Bukti Kode (File:Baris) & Catatan |
|---|---|---|
| **Apakah menu muncul sebelum alergi ditanyakan? Apakah alergi dan menu masih satu layar?** | **TIDAK** (di Web) / **YA** (di Bot) | Di Web ([`OrderPage.tsx:145-220`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderPage.tsx#L145-L220)), alergi ditanyakan di Langkah 1 terpisah dari menu di Langkah 3. Namun di Telegram Bot ([`telegram_bot.py:6-8`](file:///d:/DovaGenome/DovaGenome/telegram_bot.py#L6-L8)), paket dipilih dulu di Langkah 1 baru alergi di Langkah 2. |
| **Apakah satu layar berisi lebih dari satu keputusan?** | **TIDAK** (pada wizard baru) | Wizard web baru di [`OrderPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderPage.tsx) telah dipecah menjadi 8 langkah mandiri (satu keputusan per layar). |
| **Apakah pelanggan lama dikenali dan ditanya tambah atau kurangi alergi, atau dipaksa mengisi ulang?** | **YA** | Diimplementasikan di [`OrderPage.tsx:438-475`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderPage.tsx#L438-L475) dengan banner pengenalan profil alergi tersimpan dan 2 opsi aksi (*Tidak ada perubahan* vs *Ubah Alergi*). |
| **Apakah alamat tersimpan dan bisa dipilih ulang? Apakah ada alamat utama dan label?** | **TIDAK** (di server) | Di frontend ([`OrderPage.tsx:65-80`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderPage.tsx#L65-L80)) ada pilihan Rumah/Kantor, tetapi masih statis di klien. Belum ada tabel `addresses` dan endpoint CRUD `/me/addresses` di backend. |
| **Apakah jendela tanggal (besok sampai Minggu, plus Minggu depan bila terbit) dihitung di server dengan zona Asia/Jakarta, atau di klien?** | **SEBAGIAN** | Fungsi waktu di [`backend/app/utils/time.py:35-65`](file:///d:/DovaGenome/DovaGenome/backend/app/utils/time.py#L35-L65) sudah memakai WIB (`Asia/Jakarta`), tetapi fungsi `get_orderable_window(now)` formal dengan cutoff 20:00 belum diimplementasikan di backend. |
| **Apakah pencocokan alergi dilakukan di server, termasuk alasan peringatan?** | **SEBAGIAN** | Modul [`backend/app/services/safety_service.py`](file:///d:/DovaGenome/DovaGenome/backend/app/services/safety_service.py) sudah menghitung bentrok bahan, namun struktur response belum sepenuhnya mengembalikan `warnings[]: {allergen, ingredient, reason}` dalam bahasa Indonesia standar. |
| **Apakah total harga dihitung di server? Apakah klien bisa mengubah harga?** | **YA** | Di [`backend/app/services/order_service.py:120-135`](file:///d:/DovaGenome/DovaGenome/backend/app/services/order_service.py#L120-L135), total order diverifikasi dan dihitung ulang berdasarkan katalog paket di database. |
| **Apakah batas bayar 10 menit ada di server dan gateway, atau hanya timer di browser?** | **HANYA TIMER DI BROWSER** | Countdown timer ada di [`OrderPage.tsx:190-218`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderPage.tsx#L190-L218), tetapi belum ada kolom `expires_at` dan job pembatalan otomatis di server. |
| **Apakah webhook pembayaran diverifikasi signature dan idempotent?** | **BELUM ADA** | Endpoint `/webhooks/payment` belum diimplementasikan di backend FastAPI. |
| **Apakah progres hilang saat refresh atau tombol Kembali? Apakah draft bisa lanjut lintas web dan Telegram?** | **HILANG SAAT REFRESH** | Progres wizard belum disimpan ke tabel `order_drafts` di server, sehingga belum bisa dilanjutkan lintas perangkat/klien. |
| **Apakah logika bisnis terduplikasi di web dan bot?** | **YA** | Terbukti di [`telegram_bot.py:84-95`](file:///d:/DovaGenome/DovaGenome/telegram_bot.py#L84-L95), bot mengakses database Astra DB secara mandiri dan mengelola alur sendiri alih-alih menjadi klien tipis FastAPI. |
| **Apakah ada loading, empty, dan error state? Apakah tombol utama terlihat di mobile?** | **YA** | [`PageState.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/components/common/PageState.tsx) mengelola skeleton loading dan error state. Tombol navigasi wizard di [`OrderPage.tsx`](file:///d:/DovaGenome/DovaGenome/frontend/src/pages/OrderPage.tsx) telah dibuat sticky bottom. |
| **Apakah ada kode mati, endpoint tanpa auth, secret di repo, atau query N+1?** | **YA** | Ada file sisa Streamlit (`landing_page.py`, `kitchen_dashboard.py`, `admin_kitchen_dashboard.py`) di root, serta `backend/package-lock.json` yang tidak terpakai. |
| **Berapa cakupan tes, dan apakah ada e2e?** | **RENDAH & BELUM ADA E2E** | Ada 11 unit test di [`backend/tests/`](file:///d:/DovaGenome/DovaGenome/backend/tests), namun belum ada automated testing Playwright di frontend web. |

---

## 2. Urutan Pelaksanaan Perbaikan Bertahap (Fase R1 s/d R3)

```
[Fase R0: Audit Selesai]
         │
         ▼
[Fase R1: Jaring Pengaman (Characterization Tests & Feature Flag)]
         │
         ▼
[Fase R2: Perbaikan Alur Inti (OrderDraft, get_orderable_window, Midtrans)]
         │
         ▼
[Fase R3: Poles UI/UX (Aksesibilitas AA, Token Desain & Lighthouse)]
```

### Rencana Fase R1 — Jaring Pengaman
1. Tambahkan characterization tests untuk endpoint aktif (`auth`, `catalog`, `orders`) agar regresi segera terdeteksi.
2. Tambahkan feature flag `wizard_v2` di frontend dan backend.
3. Siapkan baseline Playwright test untuk merekam alur yang sudah bekerja.

### Rencana Fase R2 — Perbaikan Alur Inti
1. Pindahkan progres wizard ke entitas `OrderDraft` di PostgreSQL (`POST /drafts`, `GET/PATCH /drafts/{id}`).
2. Implementasikan fungsi `get_orderable_window(now)` di backend dengan penanganan cutoff 20:00 WIB dan zona waktu `Asia/Jakarta`.
3. Perbarui struktur pencocokan alergi di backend (`status: safe | warning`, `warnings[{allergen, ingredient, reason}]`).
4. Implementasikan CRUD tabel `addresses` (`GET/POST/PUT/DELETE /me/addresses`).
5. Pasang batas waktu 10 menit di backend (`expires_at`), simulasi Midtrans sandbox, dan webhook pembayaran idempotent.
6. Refactor bot Telegram (`apps/bot`) agar menjadi klien tipis yang memanggil API FastAPI.

### Rencana Fase R3 — Poles UI/UX
1. Audit aksesibilitas WCAG AA (kontras warna, focus ring, target sentuh 44px, label ARIA).
2. Optimasi animasi dan transisi (respect `prefers-reduced-motion`).
3. Pengujian Lighthouse mobile (target skor performa & aksesibilitas ≥ 90).
