"""API layer FastAPI.

Router hanya menangani routing + validasi; seluruh aturan bisnis ada di
`app.services`. Tidak ada akses langsung ke Astra DB dari modul ini kecuali
untuk pemeriksaan kesehatan/diagnostik.
"""