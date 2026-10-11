"""
DovaGenome — Telegram Bot (Pelanggan)
======================================
Alur pelanggan, dirancang agar tidak ada tombol yang menebak-nebak:

    📍 Langkah 1 dari 3  →  pilih paket
    📍 Langkah 2 dari 3  →  tandai pantangan
    📍 Langkah 3 dari 3  →  konfirmasi ke dapur

Setiap layar selalu punya tombol "🏠 Menu utama" dan "/cancel" untuk keluar.
Menu utama juga bisa dipanggil dari deep-link landing page:

    t.me/<bot>?start=order     → langsung ke langkah 1
    t.me/<bot>?start=ai        → langsung ke konsultasi AI
    t.me/<bot>?start=menu      → pratinjau menu mingguan
    t.me/<bot>?start=orders    → status pesanan sendiri
    t.me/<bot>?start=passport  → Dietary Passport
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
import threading

# Pastikan modul backend/app dapat diimpor langsung saat bot dijalankan dari root
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import time
import uuid

import requests
import telebot
from astrapy import DataAPIClient
from dotenv import load_dotenv
from telebot import types
from telebot.formatting import escape_markdown as esc_md

import data as D

load_dotenv()

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} belum diisi. Lengkapi nilainya di file .env.")
    return value


# Sembunyikan log error jaringan telebot di terminal
telebot.logger.setLevel(logging.CRITICAL)
log = logging.getLogger("dova.bot")

telebot.apihelper.RETRY_ON_ERROR = True
telebot.apihelper.RETRY_ENGINE = 1
telebot.apihelper.MAX_RETRIES = 6
telebot.apihelper.RETRY_TIMEOUT = 2

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN = _required_env("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

FLOW_ID = os.getenv("LANGFLOW_FLOW_ID", "09778e1b-f424-48e9-bf6d-36d8fb2cdb90")
LANGFLOW_API_URL = os.getenv(
    "LANGFLOW_API_URL", f"http://127.0.0.1:7860/api/v1/run/{FLOW_ID}"
)
LANGFLOW_API_KEY = _required_env("LANGFLOW_API_KEY")

#: Nama brand yang tampil di pesan
BRAND = "DovaGenome"
TOTAL_STEPS = 3


# ---------------------------------------------------------------------------
# Astra DB
# ---------------------------------------------------------------------------

ASTRA_DB_API_ENDPOINT      = _required_env("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = _required_env("ASTRA_DB_APPLICATION_TOKEN")
astra_database = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN).get_database(
    ASTRA_DB_API_ENDPOINT
)
D.ensure_collections(astra_database)

user_profiles_collection  = astra_database.get_collection("user_profiles")
kitchen_orders_collection = astra_database.get_collection("kitchen_orders")


# ---------------------------------------------------------------------------
# Katalog dinamis (paket, alergen, menu) — di-cache 2 menit
# ---------------------------------------------------------------------------

_CACHE_LOCK = threading.Lock()
_CACHE_TTL  = 120
_cache_data: dict = {}
_cache_loaded_at: float = 0.0


def _load_config_from_db() -> dict:
    """Tarik katalog dari Astra DB; otomatis jatuh ke data bawaan."""
    raw = D.load_catalog(astra_database)
    packages  = raw["packages"]
    allergens = raw["allergens"]

    def code_of(doc: dict) -> str:
        return str(doc.get("code") or doc.get("_id") or "")

    return {
        "packages":      packages,
        "allergens":     allergens,
        "menus":         raw["menus"],
        "paket_options": {code_of(p): p.get("name", "") for p in packages if code_of(p)},
        "paket_days":    {code_of(p): p.get("days", []) for p in packages if code_of(p)},
        "allergen_opts": {code_of(a): a.get("label", "") for a in allergens if code_of(a)},
        "is_live":       raw["is_live"],
    }


def get_config() -> dict:
    """Katalog ter-cache, dimuat ulang otomatis setelah TTL."""
    global _cache_data, _cache_loaded_at
    with _CACHE_LOCK:
        if time.time() - _cache_loaded_at > _CACHE_TTL or not _cache_data:
            _cache_data      = _load_config_from_db()
            _cache_loaded_at = time.time()
        return _cache_data


def cfg_paket() -> dict[str, str]:   return get_config()["paket_options"]
def cfg_days()  -> dict[str, list]:  return get_config()["paket_days"]
def cfg_algen() -> dict[str, str]:   return get_config()["allergen_opts"]
def cfg_menus() -> dict[str, dict]:  return get_config()["menus"]


# ---------------------------------------------------------------------------
# Katalog Pilihan Menu Harian (Dropdown per Hari)
# ---------------------------------------------------------------------------

CURATED_DAILY_OPTIONS: dict[str, list[dict]] = {
    "Senin": [
        {
            "nama_menu": "Ayam Panggang Rosemary & Ubi Panggang",
            "deskripsi": "Fillet ayam panggang herba segar tanpa tepung",
            "potensi_alergen": "Bebas Gluten",
        },
        {
            "nama_menu": "Beef Teriyaki Shirataki Bowl",
            "deskripsi": "Daging sapi iris saus teriyaki bebas gluten & mie shirataki",
            "potensi_alergen": "Bebas Gluten",
        },
        {
            "nama_menu": "Tofu Steak Saus Wijen & Sayur Panggang",
            "deskripsi": "Tahu organik bakar dengan saus wijen sangrai gurih",
            "potensi_alergen": "Kedelai",
        },
    ],
    "Selasa": [
        {
            "nama_menu": "Sup Daging Sapi Jamur Rempah",
            "deskripsi": "Kaldu sapi rebusan lambat 12 jam dengan jamur tiram",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Ayam Kukus Jahe & Nasi Kembang Kol",
            "deskripsi": "Fillet ayam kukus jahe herba segar, rendah kalori",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Pepes Kakap Kemangi & Jagung Manis",
            "deskripsi": "Ikan kakap bumbu kuning daun kemangi bungkus daun pisang",
            "potensi_alergen": "Seafood/Ikan",
        },
    ],
    "Rabu": [
        {
            "nama_menu": "Ikan Kakap Bakar Kunyit & Nasi Merah",
            "deskripsi": "Fillet kakap bakar rempah kunyit lengkuas alami",
            "potensi_alergen": "Seafood/Ikan",
        },
        {
            "nama_menu": "Ayam Bakar Taliwang & Plecing Kangkung",
            "deskripsi": "Ayam panggang rempah khas tanpa terasi komersial",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Daging Gulung Buncis Saus Lada Hitam",
            "deskripsi": "Rolled beef tenderloin isi buncis dengan lada hitam",
            "potensi_alergen": "Aman",
        },
    ],
    "Kamis": [
        {
            "nama_menu": "Tumis Ayam Jamur Brokoli Saus Bawang",
            "deskripsi": "Ayam fillet dan brokoli saus bawang putih steril",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Salmon Panggang Miso & Edamame",
            "deskripsi": "Salmon norway panggang miso manis gurih dengan edamame",
            "potensi_alergen": "Seafood/Ikan, Kedelai",
        },
        {
            "nama_menu": "Dori Fillet Garlic Herb & Ubi Ungu",
            "deskripsi": "Ikan dori panggang renyah dengan herba lemon",
            "potensi_alergen": "Seafood/Ikan",
        },
    ],
    "Jumat": [
        {
            "nama_menu": "Salmon Fillet Lemon Herb & Kentang Kukus",
            "deskripsi": "Salmon panggang dengan lemon segar dan herba dill",
            "potensi_alergen": "Seafood/Ikan",
        },
        {
            "nama_menu": "Ayam Rica Kemangi Rendah Minyak",
            "deskripsi": "Ayam rica rempah wangi bebas minyak jenuh",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Beef Bulgogi Bowl & Tumis Zucchini",
            "deskripsi": "Irisan daging sapi saus pir korea tanpa gluten",
            "potensi_alergen": "Aman",
        },
    ],
    "Sabtu": [
        {
            "nama_menu": "Nasi Merah Ayam Bakar Madu Ketumbar",
            "deskripsi": "Ayam kampung bakar karamel madu hutan murni",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Steak Tempe Bakar Lada Hitam & Ubi Madu",
            "deskripsi": "Tempe kedelai non-GMO panggang saus lada hitam",
            "potensi_alergen": "Kedelai",
        },
        {
            "nama_menu": "Sup Ikan Dori Kuah Asam Segar",
            "deskripsi": "Sup ikan fillet kuah bening tomat hijau dan kemangi",
            "potensi_alergen": "Seafood/Ikan",
        },
    ],
    "Minggu": [
        {
            "nama_menu": "Ayam Panggang Lemon Herba & Salad Alpukat",
            "deskripsi": "Ayam fillet panggang juicy dengan salad alpukat segar",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Daging Sapi Panggang Saus Rosemary & Kentang",
            "deskripsi": "Tenderloin sapi panggang dengan herba aromatik",
            "potensi_alergen": "Aman",
        },
        {
            "nama_menu": "Salmon Quinoa Bowl & Edamame Rebus",
            "deskripsi": "Salmon norway panggang dengan quinoa superfood",
            "potensi_alergen": "Seafood/Ikan, Kedelai",
        },
    ],
}


def get_daily_menu_options(hari: str) -> list[dict]:
    """Kembalikan daftar opsi menu untuk hari tertentu (menggabungkan DB & curated)."""
    options: list[dict] = []
    seen_names: set[str] = set()

    # 1. Ambil menu utama dari DB / Astra
    db_menus = cfg_menus()
    primary = db_menus.get(hari)
    if primary and primary.get("nama_menu"):
        name = str(primary["nama_menu"]).strip()
        options.append({
            "nama_menu": name,
            "deskripsi": str(primary.get("deskripsi", "Menu andalan dapur")),
            "potensi_alergen": str(primary.get("potensi_alergen", "Sesuai SOP")),
        })
        seen_names.add(name.lower())

    # 2. Tambahkan alternatif dari curated options
    for cur in CURATED_DAILY_OPTIONS.get(hari, []):
        c_name = cur["nama_menu"].strip()
        if c_name.lower() not in seen_names:
            options.append(cur)
            seen_names.add(c_name.lower())

    return options or [{"nama_menu": f"Menu Spesial {hari}", "deskripsi": "Menu sehat harian", "potensi_alergen": "Aman"}]


# ---------------------------------------------------------------------------
# Kategori & Detail Bahan Alergi (Dropdown Bertingkat)
# ---------------------------------------------------------------------------

ALLERGEN_CATEGORIES: dict[str, dict] = {
    "seafood": {
        "key": "seafood",
        "name": "Seafood & Makanan Laut",
        "emoji": "🦐",
        "items": [
            {"code": "sf_all",      "name": "Semua Seafood / Ikan", "keywords": ["seafood", "ikan", "udang", "kepiting", "kerang", "cumi", "terasi", "dori", "salmon", "kakap"]},
            {"code": "sf_udang",    "name": "Udang", "keywords": ["udang"]},
            {"code": "sf_kepiting", "name": "Kepiting & Rajungan", "keywords": ["kepiting", "rajungan", "crab"]},
            {"code": "sf_cumi",     "name": "Cumi & Gurita", "keywords": ["cumi", "gurita", "squid"]},
            {"code": "sf_ikan",     "name": "Ikan (Salmon, Kakap, Dori, dll)", "keywords": ["ikan", "salmon", "kakap", "dori", "tuna"]},
            {"code": "sf_kerang",   "name": "Kerang & Tiram", "keywords": ["kerang", "tiram", "clam", "oyster"]},
            {"code": "sf_terasi",   "name": "Terasi / Fermentasi Laut", "keywords": ["terasi", "petis"]},
        ],
    },
    "gluten": {
        "key": "gluten",
        "name": "Gluten & Gandum",
        "emoji": "🌾",
        "items": [
            {"code": "glt_all",    "name": "Semua Gluten / Gandum", "keywords": ["gluten", "gandum", "terigu", "tepung", "mie", "pasta", "roti"]},
            {"code": "glt_terigu", "name": "Tepung Terigu", "keywords": ["terigu", "gandum", "tepung"]},
            {"code": "glt_mie",    "name": "Mie & Pasta", "keywords": ["mie", "pasta", "spageti", "makaroni"]},
            {"code": "glt_roti",   "name": "Roti & Pastry", "keywords": ["roti", "pastry", "cake"]},
            {"code": "glt_kecap",  "name": "Kecap Manis Bergluten / Saus Tepung", "keywords": ["kecap", "saus tiram"]},
            {"code": "glt_oat",    "name": "Oat / Barley / Jelai", "keywords": ["oat", "barley", "jelai"]},
        ],
    },
    "dairy": {
        "key": "dairy",
        "name": "Susu & Produk Susu (Dairy)",
        "emoji": "🥛",
        "items": [
            {"code": "dry_all",     "name": "Semua Produk Susu & Laktosa", "keywords": ["susu", "dairy", "laktosa", "keju", "butter", "mentega", "krim", "yoghurt"]},
            {"code": "dry_susu",    "name": "Susu Sapi Murni", "keywords": ["susu"]},
            {"code": "dry_keju",    "name": "Keju (Semua Jenis)", "keywords": ["keju", "cheese"]},
            {"code": "dry_butter",  "name": "Butter & Mentega", "keywords": ["butter", "mentega"]},
            {"code": "dry_krim",    "name": "Krim & Yoghurt", "keywords": ["krim", "cream", "yoghurt"]},
            {"code": "dry_laktosa", "name": "Intoleransi Laktosa Murni", "keywords": ["laktosa"]},
        ],
    },
    "kacang": {
        "key": "kacang",
        "name": "Kacang-kacangan (Nuts)",
        "emoji": "🥜",
        "items": [
            {"code": "kcg_all",    "name": "Semua Jenis Kacang", "keywords": ["kacang", "peanut", "cashew", "almond", "walnut", "mede"]},
            {"code": "kcg_tanah",  "name": "Kacang Tanah", "keywords": ["kacang tanah", "peanut"]},
            {"code": "kcg_mede",   "name": "Kacang Mede (Cashew)", "keywords": ["mede", "mente", "cashew"]},
            {"code": "kcg_almond", "name": "Kacang Almond", "keywords": ["almond"]},
            {"code": "kcg_walnut", "name": "Walnut & Hazelnut", "keywords": ["walnut", "hazelnut"]},
            {"code": "kcg_selai",  "name": "Selai & Minyak Kacang", "keywords": ["selai kacang", "minyak kacang"]},
        ],
    },
    "kedelai": {
        "key": "kedelai",
        "name": "Kedelai & Olahan Kedelai",
        "emoji": "🫘",
        "items": [
            {"code": "kdl_all",       "name": "Semua Olahan Kedelai", "keywords": ["kedelai", "tahu", "tempe", "kecap", "soyun", "edamame"]},
            {"code": "kdl_tahutempe", "name": "Tahu & Tempe", "keywords": ["tahu", "tempe"]},
            {"code": "kdl_kecap",     "name": "Kecap Kedelai (Soy Sauce)", "keywords": ["kecap", "soy sauce"]},
            {"code": "kdl_susu",      "name": "Susu Kedelai (Soymilk)", "keywords": ["susu kedelai", "soymilk"]},
            {"code": "kdl_edamame",   "name": "Edamame", "keywords": ["edamame"]},
        ],
    },
    "telur": {
        "key": "telur",
        "name": "Telur & Olahan Telur",
        "emoji": "🥚",
        "items": [
            {"code": "tlr_all",    "name": "Semua Olahan Telur", "keywords": ["telur", "mayones", "egg"]},
            {"code": "tlr_putih",  "name": "Putih Telur", "keywords": ["putih telur"]},
            {"code": "tlr_kuning", "name": "Kuning Telur", "keywords": ["kuning telur"]},
            {"code": "tlr_mayo",   "name": "Mayones & Dressing Bertelur", "keywords": ["mayones", "mayo"]},
        ],
    },
}

ALLERGEN_CODE_MAP: dict[str, dict] = {}
for _ck, _cdata in ALLERGEN_CATEGORIES.items():
    for _it in _cdata["items"]:
        ALLERGEN_CODE_MAP[_it["code"]] = {
            "cat_key": _ck,
            "cat_name": _cdata["name"],
            "cat_emoji": _cdata["emoji"],
            "code": _it["code"],
            "name": _it["name"],
            "keywords": _it["keywords"],
        }

LEGACY_ALLERGEN_MAP: dict[str, str] = {
    "alg_seafood": "sf_all",
    "alg_gluten":  "glt_all",
    "alg_dairy":   "dry_all",
    "alg_kacang":  "kcg_all",
    "alg_kedelai": "kdl_all",
    "alg_telur":   "tlr_all",
}


def normalize_allergen_code(code: str) -> str:
    """Konversi kode legacy ke kode sistem baru jika ada."""
    return LEGACY_ALLERGEN_MAP.get(code, code)


def format_active_allergens_summary(allergens: set[str]) -> list[str]:
    """
    Format daftar kode alergen menjadi ringkasan per-kategori yang ramah & presisi.
    Contoh: ['🦐 Seafood: Udang, Kepiting', '🌾 Gluten: Tepung Terigu']
    """
    if not allergens:
        return []

    grouped: dict[str, list[str]] = {}
    for raw_code in sorted(allergens):
        code = normalize_allergen_code(raw_code)
        meta = ALLERGEN_CODE_MAP.get(code)
        if meta:
            cat_label = f"{meta['cat_emoji']} {meta['cat_name']}"
            grouped.setdefault(cat_label, []).append(meta["name"])
        else:
            lbl = cfg_algen().get(raw_code, raw_code)
            grouped.setdefault("🛡️ Pantangan Lain", []).append(lbl)

    results: list[str] = []
    for cat_label, items in grouped.items():
        all_item = next((it for it in items if "Semua" in it), None)
        if all_item:
            results.append(f"{cat_label} (Semua)")
        else:
            results.append(f"{cat_label}: {', '.join(items)}")
    return results


def get_active_allergens_grouped_text(allergens: set[str]) -> list[str]:
    """Format daftar pantangan aktif untuk layar pemilihan bot."""
    if not allergens:
        return []
    return format_active_allergens_summary(allergens)


def check_menu_allergy_warning(option: dict, allergens: set[str]) -> str | None:
    """Deteksi jika opsi menu mengandung alergen yang sedang dihindari pelanggan secara presisi."""
    if not allergens:
        return None
    blob = f"{option.get('nama_menu', '')} {option.get('deskripsi', '')} {option.get('potensi_alergen', '')}".lower()

    for raw_code in allergens:
        code = normalize_allergen_code(raw_code)
        meta = ALLERGEN_CODE_MAP.get(code)
        if meta:
            keywords = meta.get("keywords", [])
            if any(kw in blob for kw in keywords):
                return meta["name"]
        else:
            # Fallback legacy
            mapping = {
                "alg_seafood": ("Seafood", ["ikan", "salmon", "kakap", "udang", "kepiting", "cumi", "seafood", "dori"]),
                "alg_gluten":  ("Gluten",  ["gluten", "tepung", "gandum", "mie"]),
                "alg_dairy":   ("Dairy",   ["susu", "keju", "butter", "dairy", "laktosa"]),
                "alg_kacang":  ("Kacang",  ["kacang", "peanut"]),
                "alg_kedelai": ("Kedelai", ["kedelai", "tahu", "tempe", "soyun"]),
                "alg_telur":   ("Telur",   ["telur", "mayones"]),
            }
            key, kws = mapping.get(raw_code, ("", []))
            if any(kw in blob for kw in kws):
                return key
    return None


INDONESIAN_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
INDONESIAN_DAYS   = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def get_dynamic_service_schedule(chat_id: int | None = None) -> list[dict]:
    """
    Hitung daftar hari dan tanggal layanan dinamis berdasarkan hari saat customer memesan:
    - Minggu (weekday 6) / Sabtu (weekday 5) / atau force_next_week:
      Bot menyediakan 7 hari ke depan (Senin s/d Minggu depan).
    - Senin (weekday 0):
      Bot menyediakan sisa hari minggu ini: Selasa, Rabu, Kamis, Jumat, Sabtu, Minggu.
    - Selasa (weekday 1):
      Bot menyediakan: Rabu, Kamis, Jumat, Sabtu, Minggu.
    - Rabu (weekday 2):
      Bot menyediakan: Kamis, Jumat, Sabtu, Minggu.
    - Kamis (weekday 3):
      Bot menyediakan: Jumat, Sabtu, Minggu.
    - Jumat (weekday 4):
      Bot menyediakan: Sabtu, Minggu (atau minggu depan bila beralih siklus).
    """
    now = D.now_wib()
    weekday = now.weekday()  # 0=Senin, ..., 6=Minggu

    sess = session(chat_id) if chat_id else {}
    force_next = sess.get("force_next_week", False)

    schedule: list[dict] = []

    if weekday in (5, 6) or force_next:
        # Akhir pekan (Sabtu/Minggu) atau customer meminta siklus minggu depan:
        # Sediakan 7 hari ke depan mulai hari Senin berikutnya
        days_until_monday = (7 - weekday) % 7 or 7
        start_date = now + datetime.timedelta(days=days_until_monday)
        for i in range(7):
            dt = start_date + datetime.timedelta(days=i)
            hari_name = INDONESIAN_DAYS[dt.weekday()]
            tgl_str = f"{dt.day:02d} {INDONESIAN_MONTHS[dt.month]}"
            schedule.append({
                "hari": hari_name,
                "tanggal": tgl_str,
                "label": f"{hari_name} ({tgl_str})",
                "date_iso": dt.strftime("%Y-%m-%d"),
            })
    else:
        # Hari kerja tengah minggu (Senin s/d Jumat):
        # Mulai BESOK (H+1) sampai akhir minggu (s/d Minggu)
        for offset in range(1, (6 - weekday) + 1):
            dt = now + datetime.timedelta(days=offset)
            hari_name = INDONESIAN_DAYS[dt.weekday()]
            tgl_str = f"{dt.day:02d} {INDONESIAN_MONTHS[dt.month]}"
            schedule.append({
                "hari": hari_name,
                "tanggal": tgl_str,
                "label": f"{hari_name} ({tgl_str})",
                "date_iso": dt.strftime("%Y-%m-%d"),
            })

        if not schedule:
            days_until_monday = (7 - weekday) % 7 or 7
            start_date = now + datetime.timedelta(days=days_until_monday)
            for i in range(7):
                dt = start_date + datetime.timedelta(days=i)
                hari_name = INDONESIAN_DAYS[dt.weekday()]
                tgl_str = f"{dt.day:02d} {INDONESIAN_MONTHS[dt.month]}"
                schedule.append({
                    "hari": hari_name,
                    "tanggal": tgl_str,
                    "label": f"{hari_name} ({tgl_str})",
                    "date_iso": dt.strftime("%Y-%m-%d"),
                })

    return schedule


# ---------------------------------------------------------------------------
# Session per pengguna
# ---------------------------------------------------------------------------

user_sessions: dict[int, dict] = {}


def session(user_id: int) -> dict:
    return user_sessions.setdefault(user_id, {})


def reset_flow(user_id: int) -> None:
    user_sessions.pop(user_id, None)


# ---------------------------------------------------------------------------
# Penyimpanan profil & pesanan
# ---------------------------------------------------------------------------

def save_user_profile(chat_id, user_data: dict) -> None:
    user_profiles_collection.update_one(
        {"_id": str(chat_id)},
        {"$set": {k: v for k, v in user_data.items() if k != "_id"}},
        upsert=True,
    )


def get_user_profile(chat_id) -> dict:
    try:
        profile = user_profiles_collection.find_one({"_id": str(chat_id)}) or {}
    except Exception as exc:
        print(f"[DB] Gagal membaca profil: {exc}")
        profile = {}
    profile.pop("_id", None)
    return profile


def create_weekly_order(
    chat_id: int,
    allergens: set[str],
    schedule_days: list[str] | None = None,
    selections: dict[str, str] | None = None,
) -> dict:
    """Buat tiket dapur untuk pesanan katering harian beserta menu terpilih."""
    profile       = get_user_profile(chat_id)
    customer_name = profile.get("nama") or f"Pelanggan-{chat_id}"
    days          = schedule_days or (
        [d for d in D.DAYS if selections and selections.get(d) != "SKIP"] or D.DAYS[:]
    )
    paket_label   = f"Katering Harian ({len(days)} Hari)"
    labels        = format_active_allergens_summary(allergens)
    avoided_times = profile.get("avoided_times", [])

    if labels:
        sop = (
            "PROTOKOL WAJIB: peralatan, talenan, dan zona masak terpisah. "
            f"Pantangan aktif: {', '.join(labels)}."
        )
    else:
        sop = "Tidak ada pantangan khusus — prosedur steril standar berlaku."

    # Susun pilihan menu tiap hari aktif
    selections = selections or {}
    db_menus = cfg_menus()
    menu_selections: list[dict[str, str]] = []
    for day in days:
        chosen = selections.get(day)
        if not chosen or chosen == "SKIP":
            opts = get_daily_menu_options(day)
            chosen = opts[0]["nama_menu"] if opts else (db_menus.get(day, {}).get("nama_menu") or "Menu Standar Harian")
        menu_selections.append({
            "hari": day,
            "menu_id": f"menu_{day.lower()}",
            "nama_menu": chosen,
        })

    now = datetime.datetime.now(datetime.timezone.utc)
    order = {
        "order_id":           f"ORD-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        "chat_id":            chat_id,
        "customer_name":      customer_name,
        "subscription_type":  paket_label,
        "schedule_days":      days,
        "selected_allergens": labels,
        "dietary_profile":    ", ".join(labels) if labels else "Tidak ada",
        "avoided_times":      avoided_times,
        "menu_selections":    menu_selections,
        "selected_menus":     {s["hari"]: s["nama_menu"] for s in menu_selections},
        "kitchen_notes":      sop,
        "status":             "PENDING",
        "created_at":         now.isoformat(),
    }
    kitchen_orders_collection.insert_one(order)
    order["_id"] = None

    # Passport selalu diperbarui — termasuk profil lama yang masih "udang/seafood"
    save_user_profile(chat_id, {
        "nama":            customer_name,
        "dietary_profile": order["dietary_profile"],
        "avoided_times":   avoided_times,
    })
    return order


def my_orders(chat_id: int, limit: int = 8) -> list[dict]:
    try:
        return list(
            kitchen_orders_collection.find(
                {"chat_id": int(chat_id)}, sort={"created_at": -1}, limit=limit
            )
        )
    except Exception as exc:
        print(f"[DB] Gagal membaca pesanan: {exc}")
        return []


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

def kb_main() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("1️⃣  Pesan Katering Harian", callback_data="menu_order"),
        types.InlineKeyboardButton("2️⃣  Pesanan Saya",          callback_data="menu_orders"),
        types.InlineKeyboardButton("3️⃣  Konsultasi AI Alergi",   callback_data="menu_ai"),
        types.InlineKeyboardButton("4️⃣  Dietary Passport",       callback_data="menu_passport"),
    )
    return kb


def kb_home_row() -> list[types.InlineKeyboardButton]:
    return [types.InlineKeyboardButton("🏠 Menu utama", callback_data="back_main")]


def text_returning_customer(chat_id: int, profile: dict) -> str:
    name = esc_md(str(profile.get("nama") or "Pelanggan"))
    diet = esc_md(str(profile.get("dietary_profile") or "Tidak ada"))
    return (
        f"👋 *Halo kembali, {name}!*\n\n"
        f"Kami mendeteksi profil pantangan tersimpan Anda:\n"
        f"🛡️ *Pantangan Tercatat:* {diet}\n\n"
        "Apakah ada perubahan untuk pesanan Anda kali ini?"
    )


def kb_returning_customer() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✅  Tidak Ada Perubahan (Lanjut)", callback_data="ret_no_change"),
        types.InlineKeyboardButton("➕  Ubah / Tambah Pantangan",      callback_data="ret_change"),
        types.InlineKeyboardButton(" Hapus Semua Pantangan",       callback_data="ret_clear"),
    )
    kb.add(*kb_home_row()) 
    return kb


def text_alergen(chat_id: int) -> str:
    sess = session(chat_id)
    active = sess.get("allergens", set())
    expanded = sess.get("expanded_allergen_cat")

    lines = [
        step_header(1, "Tandai Pantangan & Alergi"),
        "",
        "🛡️ *Pilih Bahan yang Ingin Dihindari:*",
        "Ketuk kategori di bawah untuk membuka daftar bahan spesifik.",
        "",
        "📋 *Pantangan Aktif Saat Ini:*",
    ]

    summaries = get_active_allergens_grouped_text(active)
    if summaries:
        for s in summaries:
            lines.append(f"  • {s}")
    else:
        lines.append("  • _Tidak ada pantangan (Semua menu aman)_")

    if expanded and expanded in ALLERGEN_CATEGORIES:
        cat_info = ALLERGEN_CATEGORIES[expanded]
        lines += [
            "",
            f"🔽 *Bahan untuk {cat_info['emoji']} {cat_info['name']}:*",
            "_Centang bahan yang ingin Anda hindari di bawah ini:_",
        ]

    lines += [
        "",
        "_Jika tidak memiliki pantangan atau sudah selesai, klik tombol **Lanjut** di bawah._",
    ]
    return "\n".join(lines)


def kb_alergen(chat_id: int) -> types.InlineKeyboardMarkup:
    """Keyboard bertingkat kategori & detail alergi yang bersih dan rapi."""
    sess     = session(chat_id)
    active   = sess.setdefault("allergens", set())
    expanded = sess.get("expanded_allergen_cat")

    kb = types.InlineKeyboardMarkup(row_width=1)

    for cat_key, cat in ALLERGEN_CATEGORIES.items():
        is_open = (expanded == cat_key)
        cat_item_codes = {it["code"] for it in cat["items"]}
        active_in_cat = [c for c in cat_item_codes if c in active or normalize_allergen_code(c) in active]

        if is_open:
            btn_text = f"▲ {cat['emoji']} {cat['name']} (Tutup)"
            cb_data  = "acat_close"
        else:
            if any(c.endswith("_all") for c in active_in_cat):
                btn_text = f"▼ {cat['emoji']} {cat['name']} [Semua Dihindari] ✅"
            elif active_in_cat:
                btn_text = f"▼ {cat['emoji']} {cat['name']} ({len(active_in_cat)} dipilih) ✅"
            else:
                btn_text = f"▶️ {cat['emoji']} {cat['name']}"
            cb_data = f"acat_{cat_key}"

        kb.add(types.InlineKeyboardButton(btn_text, callback_data=cb_data))

        # Jika kategori sedang dibuka (dropdown aktif):
        if is_open:
            for it in cat["items"]:
                it_code = it["code"]
                is_checked = (it_code in active or normalize_allergen_code(it_code) in active)
                mark = "🔘" if is_checked else "⚪"
                label = f"  {mark} {it['name']}"
                if len(label) > 55:
                    label = label[:52] + "…"
                kb.add(types.InlineKeyboardButton(label, callback_data=f"alg_{it_code}"))

            # Tombol aksi dalam kategori (Pilih Semua / Kosongkan Kategori)
            all_code = next((it["code"] for it in cat["items"] if it["code"].endswith("_all")), None)
            row_actions = []
            if all_code:
                row_actions.append(types.InlineKeyboardButton(f"⚡ Semua {cat['emoji']}", callback_data=f"algall_{cat_key}"))
            if active_in_cat:
                row_actions.append(types.InlineKeyboardButton(f"🧹 Hapus Kategori", callback_data=f"algclr_{cat_key}"))
            if row_actions:
                kb.row(*row_actions)

    # Navigasi utama yang jelas
    if active:
        kb.add(types.InlineKeyboardButton("➡️  Simpan & Lanjut — Pilih Menu", callback_data="alg_done"))
        kb.add(types.InlineKeyboardButton("🧹  Kosongkan Semua Pantangan", callback_data="alg_clear_all"))
    else:
        kb.add(types.InlineKeyboardButton("✅  Bebas Pantangan — Lanjut Pilih Menu ➡️", callback_data="alg_done"))

    kb.add(*kb_home_row())
    return kb


def text_menu_day(chat_id: int, day_idx: int) -> str:
    """Tampilan detail satu hari per layar yang rapi, informatif, dan tidak memusingkan."""
    sched = get_dynamic_service_schedule(chat_id)
    if not sched:
        return "Jadwal belum tersedia."
    day_idx = max(0, min(day_idx, len(sched) - 1))

    item = sched[day_idx]
    d = item["hari"]
    total = len(sched)
    sess = session(chat_id)
    selections = sess.get("menu_selections", {})
    allergens = sess.get("allergens", set())
    chosen = selections.get(d)

    # Mini indicator: Sen 👉 · Sel ⚪ · Rab ✅
    day_tags = []
    for idx, sc in enumerate(sched):
        dh = sc["hari"][:3]
        sel = selections.get(sc["hari"])
        if idx == day_idx:
            status_icon = "👉"
        elif sel == "SKIP":
            status_icon = "❌"
        elif sel:
            status_icon = "✅"
        else:
            status_icon = "⚪"
        day_tags.append(f"{dh} {status_icon}")
    progress_str = " · ".join(day_tags)

    options = get_daily_menu_options(d)

    lines = [
        step_header(2, f"Pilih Menu ({day_idx + 1}/{total})"),
        "",
        f"📅 *{item['label']}*",
        f"Progres: `{progress_str}`",
        "",
        "Silakan tentukan menu makan siang untuk hari ini:",
        "",
    ]

    for idx, opt in enumerate(options, 1):
        num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][idx - 1] if idx <= 4 else f"{idx}."
        opt_name = opt["nama_menu"]
        deskripsi = opt.get("deskripsi", "")
        alergen_tag = opt.get("potensi_alergen", "Aman")
        warning = check_menu_allergy_warning(opt, allergens)

        is_picked = (chosen == opt_name)
        picked_marker = " 👈 *(Pilihan Anda)*" if is_picked else ""

        lines.append(f"{num_emoji} *{esc_md(opt_name)}*{picked_marker}")
        if deskripsi:
            lines.append(f"    _{esc_md(deskripsi)}_")

        if warning:
            lines.append(f"    ⚠️ *Peringatan Pantangan:* Mengandung {esc_md(warning)}")
        else:
            lines.append(f"    🛡️ Info Alergen: _{esc_md(alergen_tag)}_")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    if chosen == "SKIP":
        lines.append("📌 *Status Hari Ini:* ❌ *Dilewati (Tidak Ada Pengiriman)*")
    elif chosen:
        lines.append(f"📌 *Status Hari Ini:* ✅ *Terpilih:* {esc_md(chosen)}")
    else:
        lines.append("📌 *Status Hari Ini:* ⚪ _Belum dipilih — ketuk tombol di bawah_")

    return "\n".join(lines)


def kb_menu_day(chat_id: int, day_idx: int) -> types.InlineKeyboardMarkup:
    """Keyboard bersih per hari — tidak ada default answer, tombol rapi dan mudah ditekan."""
    sched = get_dynamic_service_schedule(chat_id)
    if not sched:
        return kb_back_only()
    day_idx = max(0, min(day_idx, len(sched) - 1))

    item = sched[day_idx]
    d = item["hari"]
    total = len(sched)
    sess = session(chat_id)
    selections = sess.get("menu_selections", {})
    allergens = sess.get("allergens", set())
    chosen = selections.get(d)

    options = get_daily_menu_options(d)
    kb = types.InlineKeyboardMarkup(row_width=1)

    # 1. Tombol Opsi Menu (Maksimal 3-4 opsi, bersih tanpa teks terpotong panjang)
    for idx, opt in enumerate(options):
        num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][idx] if idx < 4 else f"{idx+1}."
        opt_name = opt["nama_menu"]
        warning = check_menu_allergy_warning(opt, allergens)
        warn_icon = " ⚠️" if warning else ""

        is_selected = (chosen == opt_name)
        marker = "🔘" if is_selected else "⚪"

        short_name = opt_name if len(opt_name) <= 30 else opt_name[:28] + "…"
        btn_text = f"{marker} {num_emoji} {short_name}{warn_icon}"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"pick_menu_{day_idx}_{idx}"))

    # 2. Opsi Lewati hari ini (tidak kirim)
    skip_marker = "🔘" if chosen == "SKIP" else "⚪"
    kb.add(types.InlineKeyboardButton(
        f"{skip_marker} ❌ Lewati Hari Ini (Tidak Kirim)",
        callback_data=f"pick_skip_{day_idx}"
    ))

    # 3. Baris Navigasi Hari (Sebelumnya / Info / Selanjutnya)
    nav_row = []
    if day_idx > 0:
        prev_name = sched[day_idx - 1]["hari"][:3]
        nav_row.append(types.InlineKeyboardButton(f"◀️ {prev_name}", callback_data=f"goto_day_{day_idx - 1}"))
    else:
        nav_row.append(types.InlineKeyboardButton("📋 Ringkasan", callback_data="menu_overview"))

    nav_row.append(types.InlineKeyboardButton(f"📅 {day_idx + 1} dari {total}", callback_data="menu_overview"))

    if day_idx < total - 1:
        next_name = sched[day_idx + 1]["hari"][:3]
        nav_row.append(types.InlineKeyboardButton(f"{next_name} ▶️", callback_data=f"goto_day_{day_idx + 1}"))
    else:
        nav_row.append(types.InlineKeyboardButton("📋 Selesai", callback_data="menu_overview"))

    kb.row(*nav_row)

    # 4. Baris Quick-Jump Tab Hari
    tab_row = []
    for idx, sc in enumerate(sched):
        dh = sc["hari"][:3]
        sel = selections.get(sc["hari"])
        if idx == day_idx:
            t_icon = "👉"
        elif sel == "SKIP":
            t_icon = "❌"
        elif sel:
            t_icon = "✅"
        else:
            t_icon = "⚪"
        tab_row.append(types.InlineKeyboardButton(f"{dh}{t_icon}", callback_data=f"goto_day_{idx}"))
    kb.row(*tab_row)

    # 5. Tombol Lanjut Konfirmasi jika SEMUA hari sudah ada keputusan
    all_decided = all(selections.get(sc["hari"]) is not None for sc in sched)
    has_active = any(selections.get(sc["hari"]) and selections.get(sc["hari"]) != "SKIP" for sc in sched)

    if all_decided and has_active:
        kb.add(types.InlineKeyboardButton("➡️  Lanjut — Konfirmasi Pesanan", callback_data="menu_done"))
    else:
        kb.add(types.InlineKeyboardButton("📋  Lihat Ringkasan Pilihan", callback_data="menu_overview"))

    # 6. Navigasi bawah
    kb.row(
        types.InlineKeyboardButton("⬅️ Ubah Pantangan", callback_data="back_allergen"),
        types.InlineKeyboardButton("🏠 Menu Utama", callback_data="back_main"),
    )
    return kb


def text_menu_overview(chat_id: int) -> str:
    """Layar ringkasan seluruh hari dengan tata letak yang bersih dan terstruktur."""
    sched = get_dynamic_service_schedule(chat_id)
    sess = session(chat_id)
    selections = sess.get("menu_selections", {})
    allergens = sess.get("allergens", set())

    lines = [
        step_header(2, "Ringkasan Pilihan Menu"),
        "",
        "Berikut status pemilihan menu katering harian Anda:",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    undecided_count = 0
    active_count = 0

    for idx, item in enumerate(sched, 1):
        d = item["hari"]
        label = item["label"]
        chosen = selections.get(d)
        if chosen == "SKIP":
            lines.append(f"• *{label}:* ❌ _[Dilewati / Tidak Kirim]_")
        elif chosen:
            active_count += 1
            warning = ""
            opts = get_daily_menu_options(d)
            matched_opt = next((o for o in opts if o["nama_menu"] == chosen), None)
            if matched_opt:
                w = check_menu_allergy_warning(matched_opt, allergens)
                if w:
                    warning = f" ⚠️ *({w})*"
            lines.append(f"• *{label}:* ✅ {esc_md(chosen)}{warning}")
        else:
            undecided_count += 1
            lines.append(f"• *{label}:* ⚪ _[Belum Dipilih]_")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📦 *Total Hari Aktif Pengiriman:* {active_count} hari")

    if undecided_count > 0:
        lines.append(f"\n⚠️ Masih ada *{undecided_count} hari* yang belum ditentukan.")
        lines.append("_Ketuk nama hari di bawah untuk memilih menu._")
    else:
        lines.append("\n✅ Seluruh jadwal telah lengkap! Tekan tombol di bawah untuk melanjutkan.")

    return "\n".join(lines)


def kb_menu_overview(chat_id: int) -> types.InlineKeyboardMarkup:
    """Keyboard navigasi ringkasan menu."""
    sched = get_dynamic_service_schedule(chat_id)
    sess = session(chat_id)
    selections = sess.get("menu_selections", {})
    kb = types.InlineKeyboardMarkup(row_width=2)

    day_btns = []
    for idx, item in enumerate(sched):
        d = item["hari"]
        chosen = selections.get(d)
        if chosen == "SKIP":
            mark = "❌"
        elif chosen:
            mark = "✅"
        else:
            mark = "⚪"
        day_btns.append(types.InlineKeyboardButton(f"{mark} {item['label']}", callback_data=f"goto_day_{idx}"))
    kb.add(*day_btns)

    all_decided = all(selections.get(sc["hari"]) is not None for sc in sched)
    has_active = any(selections.get(sc["hari"]) and selections.get(sc["hari"]) != "SKIP" for sc in sched)

    if all_decided and has_active:
        kb.add(types.InlineKeyboardButton("➡️  Lanjut — Konfirmasi Pesanan", callback_data="menu_done"))
    else:
        first_undecided = next((i for i, sc in enumerate(sched) if selections.get(sc["hari"]) is None), 0)
        undecided_day_name = sched[first_undecided]["hari"]
        kb.add(types.InlineKeyboardButton(f"👉  Pilih Menu Hari {undecided_day_name}", callback_data=f"goto_day_{first_undecided}"))

    now = D.now_wib()
    if now.weekday() in (3, 4):
        if sess.get("force_next_week"):
            kb.add(types.InlineKeyboardButton("🔄 Sisa Minggu Ini", callback_data="toggle_week_cycle"))
        else:
            kb.add(types.InlineKeyboardButton("🔄 7 Hari Minggu Depan", callback_data="toggle_week_cycle"))

    kb.row(
        types.InlineKeyboardButton("⬅️ Ubah Pantangan", callback_data="back_allergen"),
        types.InlineKeyboardButton("🏠 Menu Utama", callback_data="back_main"),
    )
    return kb


def kb_menu_selection(chat_id: int) -> types.InlineKeyboardMarkup:
    """Fallback kompatibilitas mengarahkan ke kb_menu_day."""
    sess = session(chat_id)
    day_idx = sess.get("active_day_idx", 0)
    return kb_menu_day(chat_id, day_idx)


def kb_konfirmasi() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✅  Kirim Pesanan ke Dapur",    callback_data="confirm_order"),
        types.InlineKeyboardButton("🍽️  Ubah Pilihan Menu",         callback_data="back_menu"),
        types.InlineKeyboardButton("🕐  Atur Waktu yang Dihindari", callback_data="set_avoided"),
        types.InlineKeyboardButton("🤖  Minta Alternatif Menu (AI)", callback_data="alt_menu"),
        types.InlineKeyboardButton("⬅️  Ubah Pantangan",            callback_data="back_allergen"),
    )
    kb.add(*kb_home_row())
    return kb


def kb_back_only() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(row_width=1).add(*kb_home_row())


# ---------------------------------------------------------------------------
# Teks
# ---------------------------------------------------------------------------

def step_header(step: int, title: str) -> str:
    """Penanda posisi agar pengguna selalu tahu di langkah berapa."""
    bar = "".join("▰" if i <= step else "▱" for i in range(1, TOTAL_STEPS + 1))
    return f"📍 *Langkah {step} dari {TOTAL_STEPS}* · {title}\n{bar}"


def md_code(value) -> str:
    """
    Bungkus nilai di dalam code span Telegram.

    Hanya `\\` dan backtick yang perlu di-escape di dalam code span — unlike
    markdown biasa, meng-escape `-` di sana akan menampilkan garis miring
    secara harfiah ke pengguna.
    """
    safe = str(value).replace("\\", "\\\\").replace("`", "\\`")
    return f"`{safe}`"


# Slot waktu yang bisa dihindari pelanggan
AVOIDED_TIME_OPTIONS: dict[str, str] = {
    "avd_pagi":   "Pagi (07.00–09.00)",
    "avd_siang":  "Siang (11.00–13.00)",
    "avd_sore":   "Sore (15.00–17.00)",
    "avd_malam":  "Malam (18.00–20.00)",
}


def kb_avoided_times(active: set[str]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(
            f"{'✅' if code in active else '⬜'} {label}",
            callback_data=f"avd_{code}",
        )
        for code, label in AVOIDED_TIME_OPTIONS.items()
    ]
    kb.add(*buttons)
    kb.add(
        types.InlineKeyboardButton("💾  Simpan & Kembali", callback_data="avd_done"),
    )
    kb.add(*kb_home_row())
    return kb


def text_menu_weekly() -> str:
    menus = cfg_menus()
    lines = ["🍽️ *Menu Mingguan DovaGenome*\n"]
    for day in D.DAYS:
        doc  = menus.get(day, {})
        name = doc.get("nama_menu", "—")
        mark = "👉 " if day == D.today_name() else ""
        lines.append(f"{mark}*{day}* — {name}")
    lines.append(
        "\n_Pesan lewat 1️⃣ *Pesan Paket Mingguan* untuk memakai menu ini._"
    )
    return "\n".join(lines)


def text_avoided_times(active: set[str]) -> str:
    labels = [AVOIDED_TIME_OPTIONS[k] for k in active if k in AVOIDED_TIME_OPTIONS]
    return (
        "🕐 *Atur Waktu Pengiriman yang Dihindari*\n\n"
        "Centak waktu yang *tidak* bisa Anda terima pengiriman.\n"
        "_Ketuk tombol untuk menyalakan/mematikan._\n\n"
        + (f"Saat ini dihindari: _{', '.join(labels)}_" if labels else "Belum ada waktu yang dipilih.")
    )


def text_menu_selection(chat_id: int) -> str:
    sess = session(chat_id)
    day_idx = sess.get("active_day_idx", 0)
    return text_menu_day(chat_id, day_idx)


def text_menu_preview(allergens: set[str], chat_id: int = 0) -> str:
    sched   = get_dynamic_service_schedule(chat_id)
    sess    = session(chat_id) if chat_id else {}
    selections = sess.get("menu_selections", {})
    days    = [it["hari"] for it in sched if selections.get(it["hari"]) and selections.get(it["hari"]) != "SKIP"]

    lines   = [
        step_header(3, "Konfirmasi Pesanan"),
        "",
        f"📦 *Layanan:* Katering Harian ({len(days)} Hari Aktif Pengiriman)",
        "",
        "🍽️ *Rincian Menu yang Dipilih:*",
    ]
    for d in days:
        item = next((it for it in sched if it["hari"] == d), None)
        lbl = item["label"] if item else d
        chosen = selections.get(d, "—")
        lines.append(f"  • *{lbl}:* {esc_md(chosen)}")

    skipped = [it["label"] for it in sched if selections.get(it["hari"]) == "SKIP"]
    if skipped:
        lines.append(f"  • *Dilewati (Libur):* {', '.join(skipped)}")

    if allergens:
        labels = format_active_allergens_summary(allergens)
        lines += ["", "🛡️ *Filter Pantangan Aktif:*"]
        for lb in labels:
            lines.append(f"  • {lb}")
    else:
        lines += ["", "🛡️ *Filter Pantangan:* Bebas Alergen / Semua Aman"]

    sess_avoided: set[str] = set()
    if chat_id:
        sess_avoided = sess.get("avoided_times", set())
        if not sess_avoided:
            sess_avoided = set(get_user_profile(chat_id).get("avoided_times", []))
    if sess_avoided:
        av_labels = [AVOIDED_TIME_OPTIONS.get(k, k) for k in sorted(sess_avoided)]
        lines += ["", f"🕐 *Waktu Pengiriman Dihindari:* {', '.join(av_labels)}"]
    else:
        lines += ["", "🕐 *Waktu Pengiriman Dihindari:* Tidak ada (Bebas jam antar)"]

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "Tekan *Kirim Pesanan ke Dapur* jika rincian di atas sudah sesuai.",
    ]
    return "\n".join(lines)


def text_ticket(order: dict) -> str:
    days    = ", ".join(order.get("schedule_days", []))
    algs    = ", ".join(order.get("selected_allergens", [])) or "Tidak ada"
    label   = D.STATUS_META.get(order.get("status", "PENDING"), D.STATUS_META["PENDING"])
    avoided = order.get("avoided_times", [])
    av_str  = (
        ", ".join(AVOIDED_TIME_OPTIONS.get(k, k) for k in avoided)
        if avoided else "Tidak ada"
    )

    menu_lines = []
    for s in (order.get("menu_selections") or []):
        menu_lines.append(f"  • {s.get('hari')}: {esc_md(s.get('nama_menu', '—'))}")
    menu_str = "\n".join(menu_lines) if menu_lines else "  • Sesuai menu mingguan"

    return (
        "🎫 *Pesanan diterima dapur!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Tiket: {md_code(order['order_id'])}\n"
        f"👤 Nama: {esc_md(str(order['customer_name']))}\n"
        f"📦 Paket: {esc_md(str(order['subscription_type']))}\n"
        f"📅 Hari layanan: {esc_md(days)}\n"
        "🍽️ *Menu per hari:*\n"
        f"{menu_str}\n"
        f"🛡️ Pantangan: {esc_md(algs)}\n"
        f"🕐 Waktu dihindari: {esc_md(av_str)}\n"
        f"🔪 Protokol: _{esc_md(str(order['kitchen_notes']))}_\n"
        f"🔄 Status: {label['emoji']} *{label['label']}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Cek perkembangannya kapan saja lewat *2️⃣ Pesanan Saya*.\n"
        "Terima kasih sudah memesan! 🙏"
    )


def text_orders(rows: list[dict]) -> str:
    if not rows:
        return (
            "🚚 *Belum ada pesanan*\n\n"
            "Yuk mulai lewat 1️⃣ *Pesan Katering Harian*. "
            "Pilih menu harian → tandai pantangan → konfirmasi."
        )
    lines = ["🚚 *Pesanan Anda*\n"]
    for order in rows:
        status = str(order.get("status", "PENDING"))
        label  = D.STATUS_META.get(status, D.STATUS_META["PENDING"])
        lines += [
            f"{label['emoji']} {md_code(order.get('order_id', '—'))} — {label['label']}",
            f"   📦 {esc_md(str(order.get('subscription_type', '—')))}",
        ]
        day, _ = D.current_menu(order, cfg_menus())
        if day:
            lines.append(f"   📅 Berikutnya: {esc_md(day)}")
        lines.append("")
    lines.append("_Status diperbarui oleh dapur secara otomatis._")
    return "\n".join(lines)


def text_help() -> str:
    return (
        "ℹ️ *Cara pakai bot DovaGenome*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "/start — buka menu utama\n"
        "/order — langsung pesan katering harian\n"
        "/menu — pratinjau menu minggu ini\n"
        "/orders — status pesanan saya\n"
        "/ai — konsultasi keamanan allergen\n"
        "/passport — Dietary Passport saya\n"
        "/cancel — batalkan alur pemesanan\n\n"
        "Alur pemesanan praktis:\n"
        "1️⃣ Tandai pantangan → 2️⃣ Pilih menu per hari → 3️⃣ Konfirmasi pesanan.\n\n"
        "_Setiap layar punya tombol 🏠 Menu utama, jadi tidak pernah tersesat._"
    )


# ---------------------------------------------------------------------------
# Tampilan layar
# ---------------------------------------------------------------------------

def show_main(chat_id: int, edit_id: int | None = None, intro: str = "") -> None:
    name = esc_md(str(get_user_profile(chat_id).get("nama") or "Pelanggan"))
    intro = intro or "Mau melakukan apa hari ini?"
    text = (
        f"👋 Halo, *{name}*!\n\n"
        f"*{BRAND} Precision Catering* 🍽️\n"
        "Makan siang yang aman dan higienis untuk profil Anda.\n\n"
        f"{intro}"
    )
    _send_or_edit(chat_id, edit_id, text, kb_main())


def show_alergen(chat_id: int, edit_id: int | None = None) -> None:
    text = text_alergen(chat_id)
    _send_or_edit(chat_id, edit_id, text, kb_alergen(chat_id))


def show_menu_day(chat_id: int, day_idx: int, edit_id: int | None = None) -> None:
    sess = session(chat_id)
    sess["active_day_idx"] = day_idx
    text = text_menu_day(chat_id, day_idx)
    _send_or_edit(chat_id, edit_id, text, kb_menu_day(chat_id, day_idx))


def show_menu_overview(chat_id: int, edit_id: int | None = None) -> None:
    text = text_menu_overview(chat_id)
    _send_or_edit(chat_id, edit_id, text, kb_menu_overview(chat_id))


def show_menu_selection(chat_id: int, edit_id: int | None = None) -> None:
    sess = session(chat_id)
    day_idx = sess.get("active_day_idx", 0)
    show_menu_day(chat_id, day_idx, edit_id=edit_id)


def show_confirm(chat_id: int, edit_id: int | None = None) -> None:
    sess = session(chat_id)
    text = text_menu_preview(
        sess.get("allergens", set()),
        chat_id=chat_id,
    )
    _send_or_edit(chat_id, edit_id, text, kb_konfirmasi())


def _send_or_edit(chat_id: int, edit_id: int | None, text: str, markup) -> None:
    """Edit pesan yang sama bila memungkinkan; jika tidak, kirim baru."""
    if edit_id:
        try:
            bot.edit_message_text(text, chat_id, edit_id,
                                  parse_mode="Markdown", reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)


def _send_safe(chat_id: int, edit_id: int | None, text: str, markup) -> bool:
    """Kirim teks yang mungkin berisi Markdown valid dari AI (dengan fallback)."""
    attempts = [("edit_message_text", True), ("send_message", False)]
    if not edit_id:
        attempts = [("send_message", False)]

    for index, (method, can_edit) in enumerate(attempts):
        try:
            if method == "send_message":
                bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.edit_message_text(text, chat_id, edit_id,
                                      parse_mode="Markdown", reply_markup=markup)
            return True
        except Exception:
            continue

    # Terakhir: kirim tanpa parse_mode agar isi tetap sampai ke pengguna.
    try:
        if edit_id:
            bot.edit_message_text(text, chat_id, edit_id, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
        return True
    except Exception as exc:
        print(f"[Kirim] Gagal mengirim pesan: {exc}")
        return False


# ---------------------------------------------------------------------------
# Perintah
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start"])
def cmd_start(message):
    chat_id = message.chat.id
    reset_flow(chat_id)
    payload = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            payload = parts[1].strip().split()[0].lower() if parts[1].strip() else ""
    route_deep_link(chat_id, payload, edit_id=None)


@bot.message_handler(commands=["order"])
def cmd_order(message):
    chat_id = message.chat.id
    reset_flow(chat_id)
    profile = get_user_profile(chat_id)
    diet = profile.get("dietary_profile")
    if diet and diet not in ("Tidak ada", "Belum ada", ""):
        session(chat_id)["step"] = "returning_customer"
        _send_or_edit(chat_id, None, text_returning_customer(chat_id, profile), kb_returning_customer())
    else:
        session(chat_id)["step"] = "pick_allergen"
        show_alergen(chat_id)


@bot.message_handler(commands=["menu"])
def cmd_menu(message):
    bot.send_message(message.chat.id, text_menu_weekly(), parse_mode="Markdown",
                     reply_markup=kb_back_only())


@bot.message_handler(commands=["orders"])
def cmd_orders(message):
    bot.send_message(message.chat.id, text_orders(my_orders(message.chat.id)),
                     parse_mode="Markdown", reply_markup=kb_back_only())


@bot.message_handler(commands=["passport"])
def cmd_passport(message):
    show_passport(message.chat.id, None)


@bot.message_handler(commands=["ai"])
def cmd_ai(message):
    start_ai_chat(message.chat.id, None)


@bot.message_handler(commands=["cancel"])
def cmd_cancel(message):
    reset_flow(message.chat.id)
    bot.send_message(
        message.chat.id,
        "↩️ Alur pemesanan dibatalkan. Tidak ada perubahan yang disimpan.\n"
        "Kapan saja mulai lagi dari menu utama 👇",
        parse_mode="Markdown", reply_markup=kb_main(),
    )


@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.send_message(message.chat.id, text_help(), parse_mode="Markdown",
                     reply_markup=kb_back_only())


def route_deep_link(chat_id: int, payload: str, edit_id: int | None) -> None:
    """Terjemahkan ?start=<payload> dari landing page ke layar yang tepat."""
    if payload == "order":
        session(chat_id)["step"] = "pick_allergen"
        show_alergen(chat_id, edit_id)
    elif payload in ("ai", "konsultasi"):
        start_ai_chat(chat_id, edit_id)
    elif payload == "menu":
        _send_or_edit(chat_id, edit_id, text_menu_weekly(), kb_back_only())
    elif payload in ("orders", "status"):
        _send_or_edit(chat_id, edit_id, text_orders(my_orders(chat_id)), kb_back_only())
    elif payload == "passport":
        show_passport(chat_id, edit_id)
    else:
        show_main(chat_id, edit_id)


# ---------------------------------------------------------------------------
# Dietary Passport
# ---------------------------------------------------------------------------

def show_passport(chat_id: int, edit_id: int | None = None) -> None:
    profile = get_user_profile(chat_id)
    if not profile:
        text = (
            "📋 *Dietary Passport*\n\n"
            "⚠️ Belum ada profil tercatat.\n"
            "Buat passport otomatis dengan memesan sekali — pilih paket, "
            "lalu tandai pantangan Anda."
        )
    else:
        algs = profile.get("dietary_profile", "Tidak ada")
        text = (
            "📋 *Dietary Passport Anda*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Nama: *{esc_md(str(profile.get('nama', '—')))}*\n"
            f"🛡️ Pantangan aktif: {esc_md(str(algs))}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "_Passport diperbarui setiap kali Anda memesan._"
        )
    _send_or_edit(chat_id, edit_id, text, kb_back_only())


# ---------------------------------------------------------------------------
# Konsultasi AI
# ---------------------------------------------------------------------------

def start_ai_chat(chat_id: int, edit_id: int | None = None) -> None:
    session(chat_id)["step"] = "ai_chat"
    alg = get_user_profile(chat_id).get("dietary_profile") or "belum didaftarkan"
    _send_or_edit(
        chat_id, edit_id,
        "🧬 *Konsultasi Keamanan Allergen*\n\n"
        f"Profil pantangan Anda: _{esc_md(str(alg))}_\n\n"
        "Tulis pertanyaan Anda, misalnya:\n"
        "• _\"Aman gak makan tempe buat bebas gluten?\"_\n"
        "• _\"MENU Rabu mengandung seafood, saya harus ganti apa?\"_\n\n"
        "Tekan 🏠 Menu utama kapan saja untuk berhenti.",
        kb_back_only(),
    )


def ask_langflow(chat_id: int, loading_id: int, prompt: str) -> None:
    """Jawab di thread terpisah agar polling bot tidak terblokir."""
    reply = get_langflow_response(prompt, session_id=chat_id)
    for attempt in range(3):
        if _send_safe(chat_id, loading_id, reply, kb_back_only()):
            return
        if attempt < 2:
            time.sleep(2 ** attempt)
    print("[Langflow] Balasan tidak dapat dikirim ke pengguna.")


# ---------------------------------------------------------------------------
# Langflow
# ---------------------------------------------------------------------------

def get_langflow_response(message_text: str, session_id=None) -> str:
    payload = {
        "input_value": message_text,
        "input_type": "chat",
        "output_type": "chat",
    }
    if session_id:
        payload["session_id"] = str(session_id)
    headers = {"x-api-key": LANGFLOW_API_KEY, "Content-Type": "application/json"}

    try:
        response = requests.post(LANGFLOW_API_URL, json=payload, headers=headers,
                                 timeout=15)
        if response.status_code == 200:
            res = response.json()
            for path in (
                lambda r: r["outputs"][0]["outputs"][0]["results"]["message"]["text"],
                lambda r: r["outputs"][0]["outputs"][0]["artifacts"]["text"],
                lambda r: r["text"],
            ):
                try:
                    value = path(res)
                    if isinstance(value, str) and value.strip():
                        return value
                except (KeyError, IndexError, TypeError):
                    continue
    except Exception as exc:
        print(f"[Langflow] Beralih ke Supabase Live RAG: {exc}")

    # Aliran Data RAG Supabase Dinamis (Profil, Alergi, Riwayat Pesanan, & Menu)
    try:
        from app.services.rag_ai_service import generate_rag_answer
        return generate_rag_answer(message_text, customer_id=str(session_id or ""), session_id=str(session_id or ""))
    except Exception as err:
        print(f"[Supabase RAG Error]: {err}")
        return "Halo! Kami menyediakan hidangan lezat dan aman dari alergi yang dipersiapkan dengan workstation steril di Dova Kitchen."



# ---------------------------------------------------------------------------
# Callback query — router
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda c: True)
def on_click(call: types.CallbackQuery):
    """
    Router callback query.

    Penting: satu callback hanya boleh dijawab SATU kali. Telegram menolak
    panggilan `answer_callback_query` kedua dengan "query is too old and invalid",
    sehingga notifikasi kecil (toast) tidak pernah tampil ke pengguna.
    """
    ctx: dict[str, str] = {}
    try:
        _dispatch(call, ctx)
    finally:
        _answer(call, ctx.get("toast"))


def _answer(call: types.CallbackQuery, toast: str | None = None) -> None:
    try:
        if toast:
            bot.answer_callback_query(call.id, toast)
        else:
            bot.answer_callback_query(call.id)
    except Exception:
        log.warning("gagal menjawab callback query", exc_info=True)


def _dispatch(call: types.CallbackQuery, ctx: dict[str, str]) -> None:
    chat_id = call.message.chat.id
    msg_id  = call.message.message_id
    data    = call.data or ""
    sess    = session(chat_id)

    # ── navigasi ──────────────────────────────────────────────────────────
    if data == "back_main":
        reset_flow(chat_id)
        show_main(chat_id, edit_id=msg_id)
        return

    if data == "back_allergen":
        sess["step"] = "pick_allergen"
        sess["expanded_allergen_cat"] = None
        show_alergen(chat_id, edit_id=msg_id)
        return

    if data == "back_menu":
        sess["step"] = "pick_menu"
        show_menu_overview(chat_id, edit_id=msg_id)
        return

    if data == "back_ai":
        reset_flow(chat_id)
        show_main(chat_id, edit_id=msg_id)
        return

    # ── menu utama ────────────────────────────────────────────────────────
    if data == "menu_order":
        reset_flow(chat_id)
        sess = session(chat_id)
        profile = get_user_profile(chat_id)
        diet = profile.get("dietary_profile")
        if diet and diet not in ("Tidak ada", "Belum ada", ""):
            sess["step"] = "returning_customer"
            _send_or_edit(chat_id, msg_id, text_returning_customer(chat_id, profile), kb_returning_customer())
            return

        sess["step"] = "pick_allergen"
        sess["allergens"] = set()
        sess["schedule_days"] = [item["hari"] for item in get_dynamic_service_schedule(chat_id)]
        sess["menu_selections"] = {}
        sess["active_day_idx"] = 0
        sess["expanded_allergen_cat"] = None
        show_alergen(chat_id, edit_id=msg_id)
        return

    if data == "menu_orders":
        reset_flow(chat_id)
        _send_or_edit(chat_id, msg_id, text_orders(my_orders(chat_id)), kb_back_only())
        return

    if data == "menu_ai":
        start_ai_chat(chat_id, edit_id=msg_id)
        return

    if data == "menu_passport":
        show_passport(chat_id, edit_id=msg_id)
        return

    # ── alur pelanggan lama (returning customer) ──────────────────────────
    if data == "ret_no_change":
        sess = session(chat_id)
        sess["step"] = "pick_menu"
        sess["active_day_idx"] = 0
        sess["menu_selections"] = {}
        ctx["toast"] = "✅ Profil pantangan digunakan"
        show_menu_day(chat_id, 0, edit_id=msg_id)
        return

    if data == "ret_change":
        sess = session(chat_id)
        sess["step"] = "pick_allergen"
        sess["expanded_allergen_cat"] = None
        show_alergen(chat_id, edit_id=msg_id)
        return

    if data == "ret_clear":
        sess = session(chat_id)
        sess["allergens"] = set()
        save_user_profile(chat_id, {"dietary_profile": "Tidak ada"})
        sess["step"] = "pick_menu"
        sess["active_day_idx"] = 0
        sess["menu_selections"] = {}
        ctx["toast"] = "🧹 Pantangan dibersihkan"
        show_menu_day(chat_id, 0, edit_id=msg_id)
        return

    # ── langkah 1: toggle kategori & bahan pantangan ───────────────────────
    if data == "acat_close":
        sess["expanded_allergen_cat"] = None
        _send_or_edit(chat_id, msg_id, text_alergen(chat_id), kb_alergen(chat_id))
        return

    if data.startswith("acat_"):
        cat_key = data[len("acat_"):]
        curr = sess.get("expanded_allergen_cat")
        sess["expanded_allergen_cat"] = None if curr == cat_key else cat_key
        _send_or_edit(chat_id, msg_id, text_alergen(chat_id), kb_alergen(chat_id))
        return

    if data.startswith("algall_"):
        cat_key = data[len("algall_"):]
        cat = ALLERGEN_CATEGORIES.get(cat_key)
        if cat:
            allergens = sess.setdefault("allergens", set())
            all_code = next((it["code"] for it in cat["items"] if it["code"].endswith("_all")), None)
            for it in cat["items"]:
                allergens.discard(it["code"])
                allergens.discard(normalize_allergen_code(it["code"]))
            if all_code:
                allergens.add(all_code)
            else:
                for it in cat["items"]:
                    allergens.add(it["code"])
            ctx["toast"] = f"✅ Semua {cat['name']} ditandai"
        _send_or_edit(chat_id, msg_id, text_alergen(chat_id), kb_alergen(chat_id))
        return

    if data.startswith("algclr_"):
        cat_key = data[len("algclr_"):]
        cat = ALLERGEN_CATEGORIES.get(cat_key)
        if cat:
            allergens = sess.setdefault("allergens", set())
            for it in cat["items"]:
                allergens.discard(it["code"])
                allergens.discard(normalize_allergen_code(it["code"]))
            ctx["toast"] = f"🧹 {cat['name']} dibersihkan"
        _send_or_edit(chat_id, msg_id, text_alergen(chat_id), kb_alergen(chat_id))
        return

    if data == "alg_clear_all":
        sess["allergens"] = set()
        ctx["toast"] = "🧹 Semua pantangan dikosongkan"
        _send_or_edit(chat_id, msg_id, text_alergen(chat_id), kb_alergen(chat_id))
        return

    if data.startswith("alg_") and data != "alg_done":
        code = data[len("alg_"):]
        allergens = sess.setdefault("allergens", set())
        meta = ALLERGEN_CODE_MAP.get(code)
        item_name = meta["name"] if meta else code
        is_active = (code in allergens or normalize_allergen_code(code) in allergens)

        if is_active:
            allergens.discard(code)
            allergens.discard(normalize_allergen_code(code))
            ctx["toast"] = f"➖ {item_name} dihapus"
        else:
            cat_key = meta.get("cat_key") if meta else None
            if cat_key and ALLERGEN_CATEGORIES.get(cat_key):
                cat = ALLERGEN_CATEGORIES[cat_key]
                if code.endswith("_all"):
                    for it in cat["items"]:
                        allergens.discard(it["code"])
                        allergens.discard(normalize_allergen_code(it["code"]))
                else:
                    all_code = next((it["code"] for it in cat["items"] if it["code"].endswith("_all")), None)
                    if all_code:
                        allergens.discard(all_code)
            allergens.add(code)
            ctx["toast"] = f"✅ {item_name} ditambahkan"

        _send_or_edit(chat_id, msg_id, text_alergen(chat_id), kb_alergen(chat_id))
        return

    if data == "alg_done":
        sess["expanded_allergen_cat"] = None
        sess["step"] = "pick_menu"
        sess["active_day_idx"] = 0
        if not sess.get("schedule_days"):
            sess["schedule_days"] = [item["hari"] for item in get_dynamic_service_schedule(chat_id)]
        # CATATAN: TIDAK ADA DEFAULT ANSWER! Menu dimulai dalam keadaan belum dipilih
        sess["menu_selections"] = sess.get("menu_selections", {})
        show_menu_day(chat_id, 0, edit_id=msg_id)
        return

    # ── langkah 2: alur pemilihan menu harian per layar (bersih & tanpa default) ─
    if data.startswith("pick_menu_"):
        parts = data.split("_")
        if len(parts) == 4:
            try:
                day_idx = int(parts[2])
                opt_idx = int(parts[3])
                sched = get_dynamic_service_schedule(chat_id)
                if 0 <= day_idx < len(sched):
                    day_item = sched[day_idx]
                    day_name = day_item["hari"]
                    opts = get_daily_menu_options(day_name)
                    if 0 <= opt_idx < len(opts):
                        chosen_menu = opts[opt_idx]["nama_menu"]
                        selections = sess.setdefault("menu_selections", {})
                        selections[day_name] = chosen_menu
                        ctx["toast"] = f"✅ {day_name}: {chosen_menu[:24]}"

                        # Otomatis melangkah ke hari berikutnya untuk alur yang cepat & mulus
                        if day_idx + 1 < len(sched):
                            next_idx = day_idx + 1
                            sess["active_day_idx"] = next_idx
                            show_menu_day(chat_id, next_idx, edit_id=msg_id)
                            return
                        else:
                            # Hari terakhir selesai dipilih → tampilkan ringkasan
                            show_menu_overview(chat_id, edit_id=msg_id)
                            return
            except (ValueError, IndexError):
                pass
        show_menu_day(chat_id, sess.get("active_day_idx", 0), edit_id=msg_id)
        return

    if data.startswith("pick_skip_"):
        parts = data.split("_")
        if len(parts) == 3:
            try:
                day_idx = int(parts[2])
                sched = get_dynamic_service_schedule(chat_id)
                if 0 <= day_idx < len(sched):
                    day_item = sched[day_idx]
                    day_name = day_item["hari"]
                    selections = sess.setdefault("menu_selections", {})
                    selections[day_name] = "SKIP"
                    ctx["toast"] = f"❌ {day_name} dilewati"

                    if day_idx + 1 < len(sched):
                        next_idx = day_idx + 1
                        sess["active_day_idx"] = next_idx
                        show_menu_day(chat_id, next_idx, edit_id=msg_id)
                        return
                    else:
                        show_menu_overview(chat_id, edit_id=msg_id)
                        return
            except (ValueError, IndexError):
                pass
        show_menu_day(chat_id, sess.get("active_day_idx", 0), edit_id=msg_id)
        return

    if data.startswith("goto_day_"):
        try:
            day_idx = int(data[len("goto_day_"):])
            sess["active_day_idx"] = day_idx
            show_menu_day(chat_id, day_idx, edit_id=msg_id)
            return
        except ValueError:
            pass

    if data == "menu_overview":
        show_menu_overview(chat_id, edit_id=msg_id)
        return

    # Dukungan kompatibilitas bila ada tombol lama
    if data.startswith("day_") and data != "day_close":
        selected_day = data[len("day_"):]
        sched = get_dynamic_service_schedule(chat_id)
        target_idx = next((i for i, s in enumerate(sched) if s["hari"] == selected_day), 0)
        show_menu_day(chat_id, target_idx, edit_id=msg_id)
        return

    if data == "day_close":
        show_menu_overview(chat_id, edit_id=msg_id)
        return

    if data.startswith("selm_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            day_name = parts[1]
            sched = get_dynamic_service_schedule(chat_id)
            target_idx = next((i for i, s in enumerate(sched) if s["hari"] == day_name), 0)
            if parts[2] == "skip":
                sess.setdefault("menu_selections", {})[day_name] = "SKIP"
            else:
                try:
                    opt_idx = int(parts[2])
                    opts = get_daily_menu_options(day_name)
                    if 0 <= opt_idx < len(opts):
                        sess.setdefault("menu_selections", {})[day_name] = opts[opt_idx]["nama_menu"]
                except (ValueError, IndexError):
                    pass
            show_menu_day(chat_id, target_idx, edit_id=msg_id)
            return

    if data == "toggle_week_cycle":
        sess["force_next_week"] = not sess.get("force_next_week", False)
        sess["menu_selections"] = {}
        sess["active_day_idx"] = 0
        new_sched = get_dynamic_service_schedule(chat_id)
        sess["schedule_days"] = [item["hari"] for item in new_sched]
        ctx["toast"] = "🔄 Siklus jadwal diperbarui"
        show_menu_day(chat_id, 0, edit_id=msg_id)
        return

    if data == "menu_done":
        sched = get_dynamic_service_schedule(chat_id)
        selections = sess.setdefault("menu_selections", {})

        # Pastikan seluruh hari sudah ditentukan (tidak ada default answer tersembunyi)
        undecided_idx = next((i for i, sc in enumerate(sched) if selections.get(sc["hari"]) is None), None)
        if undecided_idx is not None:
            undecided_day = sched[undecided_idx]["hari"]
            ctx["toast"] = f"⚠️ Tentukan menu/lewati untuk {undecided_day}"
            show_menu_day(chat_id, undecided_idx, edit_id=msg_id)
            return

        active_days = [sc["hari"] for sc in sched if selections.get(sc["hari"]) and selections.get(sc["hari"]) != "SKIP"]
        if not active_days:
            ctx["toast"] = "⚠️ Pilih minimal 1 hari aktif pengiriman"
            show_menu_overview(chat_id, edit_id=msg_id)
            return

        sess["schedule_days"] = active_days
        sess["step"] = "confirm"
        show_confirm(chat_id, edit_id=msg_id)
        return

    # ── waktu yang dihindari ──────────────────────────────────────────────
    if data == "set_avoided":
        avoided = sess.setdefault("avoided_times", set())
        if not avoided:
            stored = get_user_profile(chat_id).get("avoided_times", [])
            avoided.update(stored)
        _send_or_edit(chat_id, msg_id, text_avoided_times(avoided), kb_avoided_times(avoided))
        return

    if data.startswith("avd_") and data != "avd_done":
        code    = data[len("avd_"):]
        full    = data
        avoided = sess.setdefault("avoided_times", set())
        if full in avoided:
            avoided.discard(full)
            ctx["toast"] = f"➖ {AVOIDED_TIME_OPTIONS.get(full, full)} dihapus"
        else:
            avoided.add(full)
            ctx["toast"] = f"✅ {AVOIDED_TIME_OPTIONS.get(full, full)} ditambahkan"
        try:
            bot.edit_message_text(
                text_avoided_times(avoided), chat_id, msg_id,
                parse_mode="Markdown", reply_markup=kb_avoided_times(avoided),
            )
        except Exception:
            pass
        return

    if data == "avd_done":
        avoided = sess.get("avoided_times", set())
        save_user_profile(chat_id, {"avoided_times": list(avoided)})
        ctx["toast"] = "✅ Waktu yang dihindari tersimpan"
        show_confirm(chat_id, edit_id=msg_id)
        return

    # ── langkah 4: konfirmasi ─────────────────────────────────────────────
    if data == "alt_menu":
        allergens = sess.get("allergens", set())
        labels = [cfg_algen().get(k, k) for k in sorted(allergens)] or ["tanpa pantangan"]
        loading = bot.send_message(
            chat_id, "🤖 AI sedang menyusun alternatif menu…", parse_mode="Markdown"
        )
        threading.Thread(
            target=ask_langflow, args=(chat_id, loading.message_id,
                   "Rekomendasikan menu katering mingguan Senin–Sabtu yang aman untuk "
                   f"pantangan: {', '.join(labels)}. Sebutkan nama menu dan bahan utamanya."),
            daemon=True,
        ).start()
        return

    if data == "confirm_order":
        do_confirm(chat_id, msg_id)
        return

    # ── tombol tidak dikenal ──────────────────────────────────────────────
    try:
        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=kb_main())
    except Exception:
        pass


def do_confirm(chat_id: int, msg_id: int) -> None:
    sess      = session(chat_id)
    allergens = sess.get("allergens", set())
    days      = sess.get("schedule_days") or [item["hari"] for item in get_dynamic_service_schedule(chat_id)]
    selections = sess.get("menu_selections", {})
    active_days = [d for d in days if selections.get(d) != "SKIP"] or days

    profile = get_user_profile(chat_id)
    if not profile.get("nama"):
        # Simpan pilihan sementara, lalu minta nama pelanggan.
        sess["step"]               = "awaiting_name"
        sess["pending_alg"]        = allergens
        sess["pending_days"]       = active_days
        sess["pending_selections"] = selections
        try:
            bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=None)
        except Exception:
            pass
        bot.send_message(
            chat_id,
            "✍️ *Langkah terakhir!* Bot perlu nama Anda untuk mencetak tiket dapur.\n\n"
            "Balas pesan ini dengan *nama lengkap* Anda.",
            parse_mode="Markdown",
        )
        return

    try:
        order = create_weekly_order(
            chat_id,
            allergens,
            schedule_days=active_days,
            selections=selections,
        )
    except Exception as exc:
        print(f"[Order] Gagal membuat tiket: {exc}")
        bot.send_message(
            chat_id,
            "😵 Gagal membuat tiket pesanan. Tim teknis sudah diberi tahu. "
            "Silakan coba lagi sebentar lagi.",
            parse_mode="Markdown", reply_markup=kb_main(),
        )
        return

    reset_flow(chat_id)
    _send_or_edit(chat_id, msg_id, text_ticket(order), kb_main())


# ---------------------------------------------------------------------------
# Pesan teks
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text is not None)
def on_text(message):
    chat_id = message.chat.id
    text    = message.text.strip()
    sess    = session(chat_id)

    # Perintah sudah ditangani handler commands — jangan balas dua kali.
    if text.startswith("/"):
        return

    # Nama pelanggan, sebelum tiket dicetak.
    if sess.get("step") == "awaiting_name":
        if len(text) < 2:
            bot.reply_to(message, "Nama terlalu pendek. Tulis nama lengkap Anda ya.")
            return
        pending_alg     = sess.get("pending_alg", set())
        pending_days    = sess.get("pending_days") or [item["hari"] for item in get_dynamic_service_schedule(chat_id)]
        pending_avoided = sess.get("avoided_times", set())
        pending_selections = sess.get("pending_selections", {})
        alg_labels      = [cfg_algen().get(k, k) for k in sorted(pending_alg)]
        # Simpan profil lengkap sebelum buat order agar create_weekly_order baca benar
        save_user_profile(chat_id, {
            "nama":            text[:80],
            "dietary_profile": ", ".join(alg_labels) if alg_labels else "Tidak ada",
            "avoided_times":   list(pending_avoided),
        })
        order = create_weekly_order(
            chat_id,
            pending_alg,
            schedule_days=pending_days,
            selections=pending_selections,
        )
        reset_flow(chat_id)
        bot.reply_to(message, text_ticket(order), parse_mode="Markdown")
        return

    # Mode konsultasi AI
    if sess.get("step") == "ai_chat":
        loading = bot.send_message(chat_id, "🤖 sedang menganalisis…")
        bot.send_chat_action(chat_id, "typing")
        threading.Thread(target=ask_langflow,
                         args=(chat_id, loading.message_id, text),
                         daemon=True).start()
        return

    # Default: kembalikan ke menu utama
    show_main(chat_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("🤖 Bot Telegram DovaGenome berjalan…  (Ctrl+C untuk berhenti)")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
        except Exception as exc:
            print(f"[Polling] Jaringan bermasalah: {exc}")
            time.sleep(3)