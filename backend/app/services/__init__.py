"""Service layer — satu-satunya tempat aturan bisnis DovaGenome berada.

Frontend (React) dan Telegram bot keduanya memanggil router FastAPI yang
selalu menyentuh modul di sini. Tidak ada aturan bisnis yang boleh ditulis di
router atau di komponen frontend.
"""