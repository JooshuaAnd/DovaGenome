"""Repository order — lapisan ini yang menyembunyikan bentuk lamanya.

AUDIT (PHASE 1) menemukan `kitchen_orders` menyimpan DUA shape tidak
kompatibel:

  Shape A (legacy, 2 doc)  : nama, menu_name, dietary_profile(teks bebas)
  Shape B (current, 2 doc)  : customer_name, subscription_type,
                             schedule_days[], selected_allergens[]

Modul ini menormalkan KEDUA shape menjadi satu DTO, dan hanya menulis
Shape C (superset) untuk dokumen baru. Tidak ada migrasi destruktif.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.domain import (
    ACTIVE_STATUSES,
    AVOIDED_TIME_OPTIONS,
    COLLECTION_ORDERS,
    DAYS,
    STATUS_META,
    normalize_allergen_code,
    normalize_avoided_code,
    split_codes,
)
from app.core.errors import DatabaseError, NotFoundError
from app.core.logging import get_logger
from app.repositories.astra import get_collection
from app.utils.time import elapsed_minutes, now_iso, now_wib, sla_level

log = get_logger("dova.repo.order")

#: Versi shape yang ditulis untuk dokumen baru.
#: v3 menambah `menu_selections` (satu opsi menu per hari layanan). Dokumen v2
#: yang belum punya field itu tetap dibaca normal — `order_selections` mengembalikan
#: daftar kosong dan pemanggil lama tetap memakai opsi utama per hari.
SCHEMA_VERSION = "v3"


# ── Pembacaan field toleran terhadap dua shape ──────────────────────────────
def _clean_allergen_list(raw: Any) -> list[str]:
    """`selected_allergens` cleaned dari prefiks ganda, unik, urutan stabil."""
    return [
        normalize_allergen_code(v)
        for v in split_codes(raw)
        if normalize_allergen_code(v)
    ]


def _clean_avoided_list(raw: Any) -> list[str]:
    out: list[str] = []
    for item in split_codes(raw):
        code = normalize_avoided_code(item)
        if code in AVOIDED_TIME_OPTIONS and code not in out:
            out.append(code)
    return out


def order_customer_name(doc: dict[str, Any]) -> str:
    """Pelanggan bisa tersimpan sebagai `customer_name` (B) atau `nama` (A)."""
    return str(doc.get("customer_name") or doc.get("nama") or "—")


def order_package_label(doc: dict[str, Any]) -> str:
    return str(doc.get("subscription_type") or doc.get("package") or "—")


def package_code_of(doc: dict[str, Any]) -> str:
    return str(doc.get("package_code") or doc.get("package_id") or "")


def scheduled_days(doc: dict[str, Any]) -> list[str]:
    raw = doc.get("schedule_days") or []
    if isinstance(raw, str):
        raw = [raw]
    picked = {str(d).strip() for d in raw}
    return [d for d in DAYS if d in picked]


def order_selections(doc: dict[str, Any]) -> list[dict[str, str]]:
    """
    Pilihan menu per hari, dibaca dari dokumen order.

    `menu_selections` menyimpan `[{hari, menu_id}]` — inilah yang membedakan
    "catering mingguan" dari satu menu untuk semua hari. Order lama tidak punya
    field ini dan menghasilkan daftar kosong; `schedule_days`-nya tetap dibaca
    seperti biasa sehingga tidak ada data yang hilang.
    """
    raw = doc.get("menu_selections") or []
    if not isinstance(raw, list):
        return []

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        day = str(item.get("hari") or "").strip()
        menu_id = str(item.get("menu_id") or "").strip()
        if day not in DAYS or not menu_id or day in seen:
            continue
        seen.add(day)
        out.append({"hari": day, "menu_id": menu_id})

    order = {d: i for i, d in enumerate(DAYS)}
    return sorted(out, key=lambda s: order.get(s["hari"], 99))


def selection_map(doc: dict[str, Any]) -> dict[str, str]:
    """`hari -> menu_id` untuk pencarian cepat di service layer."""
    return {s["hari"]: s["menu_id"] for s in order_selections(doc)}


def today_name() -> str | None:
    """
    Nama hari layanan hari ini dalam zona WIB, atau None bila Minggu.

    Server bisa berjalan di zona waktu lain (atau UTC di container), sedangkan
    operasional dapur selalu memakai WIB — hari yang salah di sini berarti tiket
    akan muncul di kolom yang salah.
    """
    idx = now_wib().weekday()
    return DAYS[idx] if idx < 6 else None


def current_service_day(doc: dict[str, Any]) -> str | None:
    """Hari layanan relevan: hari ini bila dijadwalkan, else hari berikutnya."""
    sched = scheduled_days(doc)
    if not sched:
        return None
    today = today_name()
    if today and today in sched:
        return today
    start = DAYS.index(today) if today else -1
    for day in DAYS[start + 1 :]:
        if day in sched:
            return day
    return sched[-1]


def detect_schema_version(doc: dict[str, Any]) -> str:
    if "customer_name" in doc or "subscription_type" in doc or "schedule_days" in doc:
        return "v2"
    if "nama" in doc or "menu_name" in doc:
        return "legacy"
    return "unknown"


def normalize_order(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Ubah dokumen Astra (shape A atau B) menjadi dict netral.

    Dipakai repository (baca) dan tidak pernah menulis balik ke DB.
    """
    status = str(doc.get("status") or "PENDING").upper()
    if status not in STATUS_META:
        log.warning("Status tak dikenal pada order %s: %r → PENDING", doc.get("order_id"), status)
        status = "PENDING"
    meta = STATUS_META[status]

    allergen_codes = _clean_allergen_list(doc.get("selected_allergens"))
    dietary_profile = str(doc.get("dietary_profile") or "").strip()
    # Data lama bisa berisi `alg_alg_*` — bersihkan agar tampilan benar.
    if dietary_profile and dietary_profile.lower() != "tidak ada":
        parts = [normalize_allergen_code(p) for p in dietary_profile.split(",")]
        dietary_profile = ", ".join(p for p in parts if p) or "Tidak ada"

    notes = str(doc.get("kitchen_notes") or "")
    if "alg_alg_" in notes:
        cleaned = notes
        while "alg_alg_" in cleaned:
            cleaned = cleaned.replace("alg_alg_", "alg_")
        notes = cleaned

    days = scheduled_days(doc)
    meal_count = int(doc.get("meal_count") or len(days))

    return {
        "id": str(doc.get("_id") or ""),
        "order_id": str(doc.get("order_id") or doc.get("_id") or "—"),
        "customer_id": doc.get("customer_id"),
        "customer_name": order_customer_name(doc),
        "chat_id": doc.get("chat_id"),
        "package_code": package_code_of(doc),
        "subscription_type": order_package_label(doc),
        "schedule_days": days,
        "menu_selections": order_selections(doc),
        "selected_allergens": allergen_codes,
        "dietary_profile": dietary_profile or "Tidak ada",
        "kitchen_notes": notes,
        "customer_note": str(doc.get("customer_note") or ""),
        "delivery_address": str(doc.get("delivery_address") or ""),
        "avoided_times": _clean_avoided_list(doc.get("avoided_times")),
        "meal_count": meal_count,
        "status": status,
        "status_meta": meta,
        "next_status": meta["next"],
        "next_action": meta["action"] or "",
        "created_at": str(doc.get("created_at") or ""),
        "updated_at": str(doc.get("updated_at") or ""),
        "elapsed_minutes": elapsed_minutes(doc.get("created_at")),
        "sla_level": sla_level(elapsed_minutes(doc.get("created_at"))),
        "service_day": current_service_day(doc),
        "has_safety_flags": bool(allergen_codes),
        "schema_version": detect_schema_version(doc),
        "invoice_number": str(doc.get("invoice_number") or ""),
        "subtotal": int(doc.get("subtotal") or 0),
        "discount": int(doc.get("discount") or 0),
        "total": int(doc.get("total") or 0),
        "payment_status": str(doc.get("payment_status") or "UNPAID").upper(),
        "legacy_menu_name": str(doc.get("menu_name") or ""),
    }


# ── Query ───────────────────────────────────────────────────────────────────
def fetch_orders(
    *,
    statuses: list[str] | None = None,
    customer_id: str | None = None,
    chat_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Ambil pesanan dari Astra DB. Selalu mengembalikan list (kosong bila DB kosong).

    Tidak ada fallback data demo di sini — data palsu tidak boleh muncul di
    KDS/admin. Mode demo ditangani eksplisit di service layer.
    """
    query: dict[str, Any] = {}
    if statuses:
        query["status"] = {"$in": list(statuses)}
    if customer_id:
        query["customer_id"] = customer_id
    if chat_id is not None:
        query["chat_id"] = int(chat_id)

    try:
        rows = list(
            get_collection(COLLECTION_ORDERS).find(
                query, sort={"created_at": 1}, limit=limit
            )
        )
    except Exception as exc:
        log.error("Baca %s gagal: %s: %s", COLLECTION_ORDERS, type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca daftar pesanan.") from exc

    orders = [normalize_order(d) for d in rows]
    # Sortir ulang berdasarkan waktu dibuat (paling lama dulu) agar tidak
    # bergantung pada urutan string ISO.
    orders.sort(key=lambda o: o["created_at"] or "9999")
    return orders


def fetch_active_orders(*, limit: int = 200) -> list[dict[str, Any]]:
    return fetch_orders(statuses=ACTIVE_STATUSES, limit=limit)


def get_order_by_id(order_id: str) -> dict[str, Any]:
    """Cari berdasarkan `order_id` publik (mis. ORD-2026-…-ABC123)."""
    try:
        doc = get_collection(COLLECTION_ORDERS).find_one({"order_id": order_id})
    except Exception as exc:
        log.error("Cari order %s gagal: %s: %s", order_id, type(exc).__name__, exc)
        raise DatabaseError("Gagal mencari pesanan.") from exc
    if not doc:
        raise NotFoundError(f"Pesanan '{order_id}' tidak ditemukan.")
    return normalize_order(doc)


def get_order_by_doc_id(doc_id: str) -> dict[str, Any]:
    try:
        doc = get_collection(COLLECTION_ORDERS).find_one({"_id": doc_id})
    except Exception as exc:
        log.error("Cari order doc %s gagal: %s: %s", doc_id, type(exc).__name__, exc)
        raise DatabaseError("Gagal mencari pesanan.") from exc
    if not doc:
        raise NotFoundError("Pesanan tidak ditemukan.")
    return normalize_order(doc)


# ── Penulisan ───────────────────────────────────────────────────────────────
def generate_order_id() -> str:
    """Format sama dengan yang dipakai bot Telegram: ORD-<YYYYmmddHHMMSS>-<6 hex>."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"ORD-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def build_kitchen_notes(allergen_labels: list[str]) -> str:
    """Teks protokol wajib untuk dapur — sama seperti yang dulu dibuat bot."""
    if allergen_labels:
        return (
            "PROTOKOL WAJIB: peralatan, talenan, dan zona masak terpisah. "
            f"Pantangan aktif: {', '.join(allergen_labels)}."
        )
    return "Tidak ada pantangan khusus — prosedur steril standar berlaku."


def insert_order(document: dict[str, Any]) -> str:
    try:
        result = get_collection(COLLECTION_ORDERS).insert_one(document)
        return str(result.inserted_id)
    except Exception as exc:
        log.error(
            "Insert order %s gagal: %s: %s",
            document.get("order_id"), type(exc).__name__, exc,
        )
        raise DatabaseError("Gagal menyimpan pesanan ke database.") from exc


def update_fields(doc_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """$set field + `updated_at`, lalu kembalikan dokumen ternormalisasi."""
    if not doc_id:
        raise NotFoundError("ID pesanan tidak valid.")
    payload = {**fields, "updated_at": now_iso()}
    try:
        get_collection(COLLECTION_ORDERS).update_one({"_id": doc_id}, {"$set": payload})
    except Exception as exc:
        log.error(
            "Update order %s gagal: %s: %s", doc_id, type(exc).__name__, exc
        )
        raise DatabaseError("Gagal menyimpan perubahan pesanan.") from exc
    return get_order_by_doc_id(doc_id)


def update_status(doc_id: str, new_status: str) -> dict[str, Any]:
    """Perubahan status. Timeline ditulis terpisah oleh `push_status_event`."""
    before = get_order_by_doc_id(doc_id)
    result = update_fields(doc_id, {"status": new_status})
    log.info(
        "kitchen_status_update order=%s %s → %s",
        before["order_id"], before["status"], new_status,
    )
    return result


def push_status_event(doc_id: str, status: str, actor: str, note: str = "") -> None:
    """Tambahkan entri timeline tanpa menimpa field lain."""
    event = {
        "status": status,
        "actor": actor,
        "note": note,
        "at": now_iso(),
        "at_wib": now_wib().strftime("%d %b %Y · %H:%M"),
    }
    try:
        get_collection(COLLECTION_ORDERS).update_one(
            {"_id": doc_id}, {"$push": {"status_events": event}, "$set": {"updated_at": now_iso()}}
        )
    except Exception as exc:
        # Timeline bersifat audit — kegagalannya tidak boleh membatalkan transisi status.
        log.warning(
            "Gagal menulis timeline order %s: %s: %s", doc_id, type(exc).__name__, exc
        )


def fetch_status_events(doc_id: str) -> list[dict[str, Any]]:
    try:
        doc = get_collection(COLLECTION_ORDERS).find_one({"_id": doc_id})
    except Exception as exc:
        log.warning("Baca timeline %s gagal: %s", doc_id, type(exc).__name__)
        return []
    if not doc:
        return []
    events = doc.get("status_events") or []
    return [e for e in events if isinstance(e, dict)]


def count_orders(*, statuses: list[str] | None = None) -> int:
    query: dict[str, Any] = {}
    if statuses:
        query["status"] = {"$in": list(statuses)}
    try:
        return int(get_collection(COLLECTION_ORDERS).count_documents(query, upper_bound=10_000))
    except Exception:
        try:
            return len(list(get_collection(COLLECTION_ORDERS).find(query, limit=10_000)))
        except Exception as exc:
            log.warning("Hitung order gagal: %s", type(exc).__name__)
            return 0


def fetch_orders_between(start_iso: str, end_iso: str, *, limit: int = 1000) -> list[dict[str, Any]]:
    """Order dalam rentang waktu (untuk tren mingguan)."""
    try:
        rows = list(
            get_collection(COLLECTION_ORDERS).find(
                {"created_at": {"$gte": start_iso, "$lt": end_iso}},
                sort={"created_at": 1},
                limit=limit,
            )
        )
    except Exception as exc:
        log.warning("Fetch rentang order gagal: %s", type(exc).__name__)
        return []
    return [normalize_order(d) for d in rows]
