# DovaGenome

## Menjalankan Telegram bot

Isi file `.env` di folder proyek dengan kredensial Telegram, Langflow, dan Astra DB. Jika file tersebut belum ada (misalnya setelah checkout baru), salin template terlebih dahulu:

```powershell
Copy-Item .env.example .env
code .env
```

Isi nilainya memakai kredensial Anda sendiri. Jalankan bot dari folder proyek:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r ".\requirements.txt"
& ".\.venv\Scripts\python.exe" ".\telegram_bot.py"
```

Bot menggunakan collection dokumen biasa bernama `user_profiles`. Setiap profil disimpan dengan `chat_id` sebagai `_id`; `save_user_profile(chat_id, user_data)` melakukan upsert dan `get_user_profile(chat_id)` mengembalikan dictionary profil atau `None`.