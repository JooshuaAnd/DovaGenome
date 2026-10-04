"""
DovaGenome — Lapisan Data Bersama
=================================
Berisi definisi domain (status, alur kerja, hari), helper waktu WIB,
pembacaan katalog dari Astra DB beserta fallback, dan pembuatan deep-link
Telegram.

Modul ini SENGAJA tidak mengimpor Streamlit agar bisa dipakai langsung oleh
` telegram_bot.py`, `kitchen_dashboard.py`, `admin_kitchen_dashboard.py`,
dan `landing_page.py`.
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Iterable

try:  # opsional — hanya dipakai bila .env dimuat
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Konstanta domain
# ---------------------------------------------------------------------------

DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]

#: Status aktif yang tampil di papan kerja dapur
ACTIVE_STATUSES = ["PENDING", "PREPARING", "READY"]

#: Alur fulfilment lengkap — dipakai untuk stepper di UI
STATUS_FLOW = ["PENDING", "PREPARING", "READY", "COMPLETED"]

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

#: Kata kunci yang memicu peringatan kontaminasi silang di dapur
ALLERGEN_KEYWORDS = [
    "gluten", "gandum", "terigu", "mie", "soyun",
    "seafood", "ikan", "udang", "kepiting", "kerang", "cumi", "terasi",
    "kacang", "kedelai", "tahu", "tempe",
    "susu", "laktosa", "keju", "butter", "krim",
    "telur", "mayones",
]

REQUIRED_COLLECTIONS = (
    "user_profiles",
    "kitchen_orders",
    "catering_packages",
    "allergen_definitions",
    "catering_menus",
)


# ---------------------------------------------------------------------------
# Fallback katalog (dipakai saat DB kosong / belum di-seed)
# ---------------------------------------------------------------------------

FALLBACK_PACKAGES: list[dict] = [
    {
        "code": "pkg_full",
        "name": "Full Week (Senin – Sabtu)",
        "days": DAYS[:],
        "description": "Catering lengkap 6 hari: Senin sampai Sabtu.",
        "price": 495000,
    },
    {
        "code": "pkg_workday",
        "name": "Hari Kerja (Senin – Jumat)",
        "days": DAYS[:5],
        "description": "Lima hari kerja, pas untuk metabolisme kantor yang padat.",
        "price": 420000,
    },
    {
        "code": "pkg_3hari",
        "name": "3 Hari Pilihan (Sen, Rab, Jum)",
        "days": ["Senin", "Rabu", "Jumat"],
        "description": "Rotasi ringan tiga kali seminggu.",
        "price": 285000,
    },
]

FALLBACK_ALLERGENS: list[dict] = [
    {"code": "alg_gluten", "label": "Bebas Gluten",
     "risiko": "Gandum, terigu, kecap kedelai biasa, mie"},
    {"code": "alg_seafood", "label": "Bebas Seafood",
     "risiko": "Ikan, udang, kepiting, kerang, terasi"},
    {"code": "alg_kacang", "label": "Bebas Kacang Tanah",
     "risiko": "Kacang tanah, selai kacang, minyak kacang"},
    {"code": "alg_dairy", "label": "Bebas Susu/Laktosa",
     "risiko": "Butter, keju, krim susu, yoghurt"},
    {"code": "alg_telur", "label": "Bebas Telur",
     "risiko": "Putih/kuning telur, mayones, emulsifier"},
    {"code": "alg_kedelai", "label": "Bebas Kedelai/Terasi",
     "risiko": "Tahu, tempe, kecap asin, terasi udang"},
]

FALLBACK_MENUS: dict[str, dict] = {
    "Senin": {
        "nama_menu": "Ayam Panggang Rosemary & Ubi Panggang",
        "deskripsi": "Fillet ayam panggang rempah herba, tanpa tepung.",
        "bahan_detail": [],
        "alat_dapur_steril": [],
    },
    "Selasa": {
        "nama_menu": "Sup Daging Sapi Jamur Rempah",
        "deskripsi": "Kaldu sapi rebusan lambat dengan jamur tiram.",
        "bahan_detail": [],
        "alat_dapur_steril": [],
    },
    "Rabu": {
        "nama_menu": "Ikan Kakap Bakar Kunyit & Nasi Merah",
        "deskripsi": "Ikan kakap segar bumbu kunyit lengkuas.",
        "bahan_detail": [],
        "alat_dapur_steril": [],
    },
    "Kamis": {
        "nama_menu": "Tumis Ayam Jamur Brokoli",
        "deskripsi": "Saus bawang putih buatan sendiri, bebas kecap.",
        "bahan_detail": [],
        "alat_dapur_steril": [],
    },
    "Jumat": {
        "nama_menu": "Salmon Fillet Lemon Herb",
        "deskripsi": "Salmon panggang dengan lemon segar dan dill.",
        "bahan_detail": [],
        "alat_dapur_steril": [],
    },
    "Sabtu": {
        "nama_menu": "Nasi Merah Ayam Bakar Madu Ketumbar",
        "deskripsi": "Ayam bakar karamel madu hutan asli.",
        "bahan_detail": [],
        "alat_dapur_steril": [],
    },
}


def demo_orders() -> list[dict]:
    """Pesanan contoh untuk mode demo pada dashboard."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return [
        {
            "_id": "demo-001",
            "order_id": "ORD-2026-081",
            "customer_name": "Clara Anjelita",
            "chat_id": 1000001,
            "subscription_type": "Full Week (Senin – Sabtu)",
            "schedule_days": DAYS[:],
            "selected_allergens": ["Bebas Gluten", "Bebas Kacang Tanah"],
            "dietary_profile": "Bebas Gluten, Bebas Kacang Tanah",
            "kitchen_notes": "Wajan berlabel hijau khusus bebas gluten. Kecap wajib non-gandum.",
            "status": "PENDING",
            "created_at": (now - datetime.timedelta(minutes=24)).isoformat(),
        },
        {
            "_id": "demo-002",
            "order_id": "ORD-2026-082",
            "customer_name": "Budi Santoso",
            "chat_id": 1000002,
            "subscription_type": "Full Week (Senin – Sabtu)",
            "schedule_days": DAYS[:],
            "selected_allergens": ["Bebas Susu/Laktosa", "Bebas Seafood"],
            "dietary_profile": "Bebas Susu/Laktosa, Bebas Seafood",
            "kitchen_notes": "Talenan #3 steril. Penggorengan memakai minyak kelapa baru, tanpa butter.",
            "status": "PREPARING",
            "created_at": (now - datetime.timedelta(minutes=16)).isoformat(),
        },
        {
            "_id": "demo-003",
            "order_id": "ORD-2026-080",
            "customer_name": "Rian Kusuma",
            "chat_id": 1000003,
            "subscription_type": "Hari Kerja (Senin – Jumat)",
            "schedule_days": DAYS[:5],
            "selected_allergens": ["Bebas Telur"],
            "dietary_profile": "Bebas Telur",
            "kitchen_notes": "Area penggorengan terpisah dari penanganan telur.",
            "status": "READY",
            "created_at": (now - datetime.timedelta(minutes=7)).isoformat(),
        },
        {
            "_id": "demo-004",
            "order_id": "ORD-2026-079",
            "customer_name": "Sekar Ayu",
            "chat_id": 1000004,
            "subscription_type": "3 Hari Pilihan (Sen, Rab, Jum)",
            "schedule_days": ["Senin", "Rabu", "Jumat"],
            "selected_allergens": [],
            "dietary_profile": "Tidak ada",
            "kitchen_notes": "Tanpa pantangan — prosedur standar.",
            "status": "COMPLETED",
            "created_at": (now - datetime.timedelta(hours=5)).isoformat(),
        },
    ]


# ---------------------------------------------------------------------------
# Koneksi Astra DB
# ---------------------------------------------------------------------------

def connect_db(endpoint: str | None = None, token: str | None = None):
    """Buka koneksi Astra DB. Kembalikan objek database atau None."""
    endpoint = endpoint or os.getenv("ASTRA_DB_API_ENDPOINT", "")
    token    = token or os.getenv("ASTRA_DB_APPLICATION_TOKEN", "")
    if not endpoint or not token:
        return None
    try:
        from astrapy import DataAPIClient

        return DataAPIClient(token).get_database(endpoint)
    except Exception:
        return None


def ensure_collections(db, names: Iterable[str] = REQUIRED_COLLECTIONS) -> None:
    """Buat collection yang belum ada (diabaikan bila sudah ada)."""
    if db is None:
        return
    existing = set()
    try:
        existing = set(db.list_collection_names())
    except Exception:
        return
    for name in names:
        if name not in existing:
            try:
                db.create_collection(name)
            except Exception:
                pass


def load_catalog(db) -> dict[str, Any]:
    """
    Baca paket, alergen, dan menu mingguan dari Astra DB.

    Selalu mengembalikan dict berisi:
        packages : list[dict]
        allergens: list[dict]
        menus    : dict[str, dict]  (kunci = nama hari)
    Bila DB kosong / gagal, dipakai data fallback.
    """
    packages: list[dict] = []
    allergens: list[dict] = []
    menus: dict[str, dict] = {}

    if db is not None:
        try:
            packages = list(
                db.get_collection("catering_packages").find(
                    {"active": True}, sort={"_id": 1}, limit=30
                )
            )
        except Exception:
            packages = []
        try:
            allergens = list(
                db.get_collection("allergen_definitions").find(
                    {"active": True}, sort={"_id": 1}, limit=40
                )
            )
        except Exception:
            allergens = []
        try:
            menus = {
                m["hari"]: m
                for m in db.get_collection("catering_menus").find(
                    {}, sort={"hari": 1}, limit=10
                )
            }
        except Exception:
            menus = {}

    return {
        "packages":  packages or [dict(p) for p in FALLBACK_PACKAGES],
        "allergens": allergens or [dict(a) for a in FALLBACK_ALLERGENS],
        "menus":     menus or {k: dict(v) for k, v in FALLBACK_MENUS.items()},
        "is_live":   bool(packages or allergens or menus),
    }


# ---------------------------------------------------------------------------
# Pembacaan & pembaruan pesanan
# ---------------------------------------------------------------------------

def fetch_orders(
    db,
    statuses: Iterable[str] | None = None,
    limit: int = 200,
    fallback_to_demo: bool = True,
) -> list[dict]:
    """Ambil pesanan dari Astra DB; urut dari yang terlama masuk."""
    wanted = list(statuses) if statuses else list(ACTIVE_STATUSES)
    if db is None:
        return demo_orders() if fallback_to_demo else []
    try:
        cursor = db.get_collection("kitchen_orders").find(
            {"status": {"$in": wanted}},
            sort={"created_at": 1},
            limit=limit,
        )
        rows = list(cursor)
        return rows if rows else ([] if not fallback_to_demo else demo_orders())
    except Exception:
        return demo_orders() if fallback_to_demo else []


def update_order_status(db, doc_id: str, new_status: str) -> bool:
    """Ubah status satu pesanan. True bila berhasil ditulis ke DB."""
    if db is None or not doc_id:
        return False
    try:
        db.get_collection("kitchen_orders").update_one(
            {"_id": doc_id},
            {"$set": {
                "status": new_status,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }},
        )
        return True
    except Exception:
        return False


def upsert_doc(db, collection: str, doc: dict) -> None:
    """Simpan dokumen berdasarkan _id (insert atau ganti)."""
    if db is None:
        raise RuntimeError("Astra DB tidak terhubung.")
    db.get_collection(collection).find_one_and_replace(
        filter={"_id": doc["_id"]}, replacement=doc, upsert=True,
    )


def update_fields(db, collection: str, doc_id: str, fields: dict) -> bool:
    """Ubah sebagian field satu dokumen."""
    if db is None or not doc_id:
        return False
    try:
        db.get_collection(collection).update_one({"_id": doc_id}, {"$set": fields})
        return True
    except Exception:
        return False


def fetch_collection(db, collection: str, limit: int = 50, sort: dict | None = None) -> list[dict]:
    """Baca satu collection penuh (dengan fallback list kosong)."""
    if db is None:
        return []
    try:
        return list(db.get_collection(collection).find({}, sort=sort or {"_id": 1}, limit=limit))
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Helper Telegram
# ---------------------------------------------------------------------------

def bot_username() -> str:
    """
    Username bot Telegram tanpa '@'.

    Diambil dari TELEGRAM_BOT_USERNAME; bila kosong, diturunkan dari
    token (bagian sebelum tanda ':' sudah berupa ID bot yang sah untuk t.me).
    """
    name = (os.getenv("TELEGRAM_BOT_USERNAME", "") or "").strip().lstrip("@")
    if name:
        return name
    token = (os.getenv("TELEGRAM_TOKEN", "") or "").strip()
    if ":" in token:
        return token.split(":", 1)[0]
    return ""


def telegram_link(payload: str | None = None) -> str:
    """Buat deep-link Telegram, mis. `t.me/dova_bot?start=order`."""
    user = bot_username()
    if not user:
        return ""
    return f"https://t.me/{user}" + (f"?start={payload}" if payload else "")


def telegram_link_html(payload: str | None = None, label: str = "Buka Telegram") -> str:
    """Versi HTML untuk ditampilkan di dalam komponen Streamlit."""
    url = telegram_link(payload)
    if not url:
        return (
            "<span style='color:#9F1239;font-weight:700'>"
            "⚠️ TELEGRAM_BOT_USERNAME belum diisi di file .env</span>"
        )
    return (
        f"<a href='{url}' target='_blank' rel='noopener' "
        f"style='color:#1F5648;font-weight:800;text-decoration:underline'>{label}</a>"
    )


# ---------------------------------------------------------------------------
# Helper waktu (WIB)
# ---------------------------------------------------------------------------

WIB = datetime.timezone(datetime.timedelta(hours=7))


def now_wib() -> datetime.datetime:
    return datetime.datetime.now(WIB)


def parse_dt(iso_str: str | None) -> datetime.datetime | None:
    if not iso_str:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(iso_str))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def fmt_wib(iso_str: str | None, with_date: bool = False) -> str:
    """Format waktu ISO menjadi string WIB."""
    dt = parse_dt(iso_str)
    if dt is None:
        return "—"
    return dt.astimezone(WIB).strftime("%d %b %Y · %H:%M" if with_date else "%H:%M WIB")


def elapsed_minutes(iso_str: str | None) -> int:
    """Menit sejak pesanan dibuat (minimal 0)."""
    dt = parse_dt(iso_str)
    if dt is None:
        return 0
    delta = datetime.datetime.now(datetime.timezone.utc) - dt
    return max(0, int(delta.total_seconds() // 60))


def sla_level(minutes: int) -> str:
    """Level kesegeraan: fresh / soon / late."""
    if minutes >= 30:
        return "late"
    if minutes >= 20:
        return "soon"
    return "fresh"


# ---------------------------------------------------------------------------
# Helper pembacaan dokumen pesanan
# ---------------------------------------------------------------------------

def order_id(order: dict) -> str:
    return str(order.get("order_id") or order.get("_id") or "—")


def order_customer(order: dict) -> str:
    return str(order.get("customer_name") or order.get("nama") or "—")


def order_package(order: dict) -> str:
    return str(order.get("subscription_type") or order.get("package") or "—")


def order_allergens(order: dict) -> list[str]:
    raw = order.get("selected_allergens") or []
    if isinstance(raw, str):
        raw = [p.strip() for p in raw.split(",") if p.strip()]
    return [str(a) for a in raw]


def order_notes(order: dict) -> str:
    return str(order.get("kitchen_notes") or "")


def scheduled_days(order: dict) -> list[str]:
    raw = order.get("schedule_days") or []
    if isinstance(raw, str):
        raw = [raw]
    return [d for d in DAYS if d in raw]


def today_name() -> str | None:
    """Nama hari ini, atau None bila Minggu (tidak ada layanan)."""
    idx = datetime.datetime.now().weekday()
    return DAYS[idx] if idx < 6 else None


def current_service_day(order: dict) -> str | None:
    """
    Hari layanan yang relevan: hari ini bila dijadwalkan, jika tidak hari
    layanan berikutnya. None bila pesanan tidak punya jadwal.
    """
    sched = scheduled_days(order)
    if not sched:
        return None
    today = today_name()
    if today and today in sched:
        return today
    start = DAYS.index(today) if today else -1
    for day in DAYS[start + 1:]:
        if day in sched:
            return day
    return sched[-1]


def current_menu(order: dict, menus: dict[str, dict]) -> tuple[str | None, str]:
    """Kembalikan (hari, nama menu) yang relevan untuk pesanan ini."""
    day = current_service_day(order)
    if day is None:
        return None, "Tidak ada jadwal"
    doc = menus.get(day) or {}
    name = str(doc.get("nama_menu") or "—")
    return day, name


def detect_allergy_risks(*texts: str | None) -> list[str]:
    """Kembalikan daftar kata kunci alergen yang muncul pada teks."""
    blob = " ".join(t for t in texts if t).lower()
    found = [kw for kw in ALLERGEN_KEYWORDS if kw in blob]
    # urutkan dari terpanjang agar tidak duplikat ("susu" vs "krim susu")
    found.sort(key=len, reverse=True)
    seen: list[str] = []
    for kw in found:
        if not any(kw in s and s in kw for s in seen):
            seen.append(kw)
    return seen


def count_by_status(orders: list[dict], statuses: Iterable[str] = ACTIVE_STATUSES) -> dict[str, int]:
    wanted = set(statuses)
    counts = {s: 0 for s in wanted}
    for order in orders:
        status = str(order.get("status") or "")
        if status in counts:
            counts[status] += 1
    return counts