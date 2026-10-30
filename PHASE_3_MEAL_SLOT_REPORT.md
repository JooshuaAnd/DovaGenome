# Phase 3 continuation — meal-slot ordering

Status: **implemented locally; Supabase extension migration pending**.

Pelanggan sekarang dapat memilih sarapan, makan siang, dan makan malam secara
terpisah untuk tanggal layanan yang sama. Tidak ada lagi guard “satu menu untuk
satu hari”; beberapa baris order pada hari yang sama dibedakan dengan
`meal_slot`.

Yang selesai:

- `DaySelectionIn` dan `OrderSelectionOut` memakai slot `breakfast`, `lunch`,
  atau `dinner`; order lama tanpa kolom slot dibaca sebagai `lunch`.
- `order_items.meal_slot` ditulis dan dibaca dengan fallback aman saat migration
  017 belum diterapkan. Update order mengganti item secara atomik, termasuk
  quantity dan slot.
- Customer Order UI memiliki pilihan slot dan cart key yang memisahkan menu
  yang sama pada slot berbeda. Payload checkout mengirim `meal_slot` ke API.
- Planner production batch memisahkan demand PAID per slot. Data legacy tanpa
  kolom slot hanya dihitung sebagai lunch, sehingga tidak salah menjadi
  sarapan/makan malam.
- Verifikasi mencakup schema validation, ordering tiga slot, normalisasi order
  lama, dan guard planner legacy.

Acceptance evidence lokal:

- `python -m pytest -q` — **222 passed**.
- `python -m compileall -q backend/app backend/tests telegram_bot.py telegram_admin_bot.py telegram_supplier_bot.py` — passed.
- `frontend: npm.cmd run build` — passed; Vite hanya memberi warning ukuran
  bundle yang sudah ada.

Batas live: kolom `order_items.meal_slot` berasal dari
`supabase/migrations/017_delivery_dispatch.sql` serta migration 018 belum
diklaim aktif sampai backup/restore gate serta migration Supabase dijalankan
dan diverifikasi.
