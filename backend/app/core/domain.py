"""Konstanta domain DovaGenome.

Port verbatim dari `data.py` (legacy) agar tidak terjadi rewrite.
Status, alur fulfilment, dan kamus kata kunci alergen adalah kontrak bisnis
yang dipakai bersama oleh backend, Telegram, dan frontend.
"""

from __future__ import annotations

from typing import Any

#: Hari layanan. Minggu tidak dilayani.
DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]

#: Status aktif yang tampil di papan kerja dapur.
ACTIVE_STATUSES = ["PENDING", "PREPARING", "READY"]

#: Alur fulfilment lengkap.
STATUS_FLOW = ["PENDING", "PREPARING", "READY", "COMPLETED"]

#: Status terminal — tidak tampil di KDS.
TERMINAL_STATUSES = ["COMPLETED", "CANCELLED"]

ALL_STATUSES = STATUS_FLOW + ["CANCELLED"]

STATUS_META: dict[str, dict[str, Any]] = {
    "PENDING": {
        "emoji": "🟡",
        "label": "Menunggu Dimasak",
        "short": "Menunggu",
        "color": "#B45309",
        "bg": "#FDF4E3",
        "border": "#EFDCB6",
        "next": "PREPARING",
        "action": "Mulai Masak",
        "action_emoji": "🔥",
        "step": 1,
    },
    "PREPARING": {
        "emoji": "🔵",
        "label": "Sedang Dimasak",
        "short": "Dimasak",
        "color": "#1D4ED8",
        "bg": "#EDF2FE",
        "border": "#CBDCF9",
        "next": "READY",
        "action": "Tandai Siap Kirim",
        "action_emoji": "📦",
        "step": 2,
    },
    "READY": {
        "emoji": "🟢",
        "label": "Siap Dikirim",
        "short": "Siap Kirim",
        "color": "#15803D",
        "bg": "#EBF7F0",
        "border": "#C6E7D3",
        "next": "COMPLETED",
        "action": "Selesai & Kirim",
        "action_emoji": "🚚",
        "step": 3,
    },
    "COMPLETED": {
        "emoji": "⚪",
        "label": "Sudah Diantar",
        "short": "Selesai",
        "color": "#64748B",
        "bg": "#F1F5F9",
        "border": "#DCE3EB",
        "next": None,
        "action": None,
        "action_emoji": "",
        "step": 4,
    },
    "CANCELLED": {
        "emoji": "⛔",
        "label": "Dibatalkan",
        "short": "Dibatalkan",
        "color": "#9F1239",
        "bg": "#FDF1F3",
        "border": "#F2CBD3",
        "next": None,
        "action": None,
        "action_emoji": "",
        "step": 0,
    },
}

#: Kata kunci yang memicu peringatan kontaminasi silang di dapur.
ALLERGEN_KEYWORDS = [
    "gluten", "gandum", "terigu", "mie", "soyun",
    "seafood", "ikan", "udang", "kepiting", "kerang", "cumi", "terasi",
    "kacang", "kedelai", "tahu", "tempe",
    "susu", "laktosa", "keju", "butter", "krim",
    "telur", "mayones",
]

#: Collection milik aplikasi. JANGAN pernah ditulis oleh migrasi buta —
#: database Astra ini juga dipakai project Langflow lain.
REQUIRED_COLLECTIONS = (
    "user_profiles",
    "kitchen_orders",
    "catering_packages",
    "allergen_definitions",
    "catering_menus",
)

COLLECTION_PACKAGES = "catering_packages"
COLLECTION_ALLERGENS = "allergen_definitions"
COLLECTION_MENUS = "catering_menus"
COLLECTION_ORDERS = "kitchen_orders"
COLLECTION_PROFILES = "user_profiles"

#: Collection milik Langflow / project lain — read-only, jangan pernah di-seed.
FOREIGN_COLLECTIONS = ("dova_kitchen_catering", "hr_documents")

#: Collection baru milik aplikasi (dibuat saat startup, additive).
COLLECTION_CUSTOMERS = "customers"
COLLECTION_FEEDBACK = "customer_feedback"

# ── Slot waktu pengiriman yang bisa dihindari pelanggan ────────────────────
AVOIDED_TIME_OPTIONS: dict[str, str] = {
    "avd_pagi": "Pagi (07.00–09.00)",
    "avd_siang": "Siang (11.00–13.00)",
    "avd_sore": "Sore (15.00–17.00)",
    "avd_malam": "Malam (18.00–20.00)",
}

# ── Kategori Dietary Passport (spec §9: jangan campur "pantangan") ─────────
RESTRICTION_CATEGORIES = ("allergy", "intolerance", "medical", "preference")

#: Label manusiawi per kategori.
CATEGORY_LABELS: dict[str, str] = {
    "allergy": "Alergi",
    "intolerance": "Intoleransi",
    "medical": "Restribusi Medis",
    "preference": "Preferensi",
}

#: Kategori yang MEWAKIBKAN protocols steril di dapur. Preferensi tidak.
SAFETY_CRITICAL_CATEGORIES = ("allergy", "intolerance", "medical")

#: Ambang kesegeraan tiket dapur (menit).
SLA_SOON_MINUTES = 20
SLA_LATE_MINUTES = 30


def normalize_allergen_code(value: Any) -> str:
    """
    Bersihkan prefiks ganda dari kode katalog.

    Data live memiliki `alg_alg_telur` akibat bug callback Telegram
    (lihat telegram_bot.py:816-819). Fungsi ini dipakai saat baca maupun tulis
    sehingga data lama dan baru bisa hidup berdampingan.
    """
    code = str(value or "").strip()
    while code.startswith("alg_alg_"):
        code = code[len("alg_") :]
    if code.startswith("alg_alg_"):
        code = code[len("alg_alg_") :]
    return code


def normalize_avoided_code(value: Any) -> str:
    """Bersihkan prefiks ganda `avd_avd_*` dari slot waktu dihindari."""
    code = str(value or "").strip()
    while code.startswith("avd_avd_"):
        code = code[len("avd_") :]
    return code


def split_codes(value: Any) -> list[str]:
    """
    Pecah nilai yang mungkin berupa list, string koma, atau string tunggal
    menjadi daftar kode yang sudah dibersihkan & unik (urutan stabil).
    """
    raw: list[Any]
    if value is None:
        return []
    if isinstance(value, str):
        raw = [p.strip() for p in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]

    out: list[str] = []
    for item in raw:
        code = str(item or "").strip()
        if not code or code in out:
            continue
        out.append(code)
    return out
