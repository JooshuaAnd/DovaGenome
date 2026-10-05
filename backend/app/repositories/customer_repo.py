"""Repository customer + Dietary Passport.

Relationship dengan data legacy:
  * `user_profiles` (lama)  → `_id` = str(chat_id). Dipakai Telegram.
  * `customers`     (baru)  → `_id` = customer_id, punya `telegram_chat_id`.

Bot Telegram dan webotrustomer berinteraksi dengan customer yang sama lewat
`TelegramLinkService` (`auth_service.link_telegram`).
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.core.domain import (
    AVOIDED_TIME_OPTIONS,
    COLLECTION_CUSTOMERS,
    COLLECTION_PROFILES,
    normalize_allergen_code,
    normalize_avoided_code,
    split_codes,
)
from app.core.errors import ConflictError, DatabaseError, NotFoundError
from app.core.logging import get_logger
from app.models.enums import RestrictionCategory, Role
from app.repositories.astra import get_collection
from app.schemas.customer import (
    CustomerOut,
    EmergencyContact,
    PassportIn,
    PassportOut,
    RestrictionOut,
)
from app.utils.time import now_iso

log = get_logger("dova.repo.customer")

PHONE_RE = re.compile(r"^\+?[0-9][0-9\s-]{6,19}$")


# ── ID ──────────────────────────────────────────────────────────────────────
def new_customer_id() -> str:
    return f"cus_{uuid.uuid4().hex[:12]}"


def _doc_to_customer(doc: dict[str, Any]) -> CustomerOut:
    return CustomerOut(
        customer_id=str(doc.get("customer_id") or doc.get("_id") or ""),
        username=str(doc.get("username") or ""),
        display_name=str(doc.get("display_name") or doc.get("nama") or ""),
        phone=str(doc.get("phone") or ""),
        role=str(doc.get("role") or Role.CUSTOMER.value),
        status=str(doc.get("status") or "active"),
        telegram_chat_id=doc.get("telegram_chat_id"),
        telegram_verified=bool(doc.get("telegram_verified")),
        telegram_link_code=str(doc.get("telegram_link_code") or ""),
        created_at=str(doc.get("created_at") or ""),
        updated_at=str(doc.get("updated_at") or ""),
    )


# ── CRUD customer ───────────────────────────────────────────────────────────
def find_by_username(username: str) -> dict[str, Any] | None:
    try:
        return get_collection(COLLECTION_CUSTOMERS).find_one(
            {"username": username.strip().lower()}
        )
    except Exception as exc:
        log.error("Cari username %s gagal: %s", username, type(exc).__name__)
        raise DatabaseError("Gagal mencari pelanggan.") from exc


def get_by_id(customer_id: str) -> dict[str, Any]:
    """
    Cari customer berdasarkan id.

    Astra Data API tidak mendukung `$or` pada field `_id`, jadi tidak boleh
    pakai `{"$or": [{"_id": …}, {"customer_id": …}]}`. Karena `_id` selalu
    diisi dengan `customer_id`, pencarian `_id` langsung sudah cukup; fallback
    ke `customer_id` hanya untuk dokumen lama yang belum konsisten.
    """
    try:
        collection = get_collection(COLLECTION_CUSTOMERS)
        doc = collection.find_one({"_id": customer_id})
        if not doc:
            doc = collection.find_one({"customer_id": customer_id})
    except Exception as exc:
        log.error("Cari customer %s gagal: %s", customer_id, type(exc).__name__)
        raise DatabaseError("Gagal mencari pelanggan.") from exc
    if not doc:
        raise NotFoundError("Pelanggan tidak ditemukan.")
    return doc


def get_public(customer_id: str) -> CustomerOut:
    return to_public(get_by_id(customer_id))


def to_public(doc: dict[str, Any]) -> CustomerOut:
    """Konversi dokumen Astra → DTO publik (dipakai service & router)."""
    return _doc_to_customer(doc)


def find_by_link_code(code: str) -> dict[str, Any] | None:
    """Cari customer berdasarkan code linking Telegram (single-use, ada TTL)."""
    code = code.strip().upper()
    if not code:
        return None
    try:
        return get_collection(COLLECTION_CUSTOMERS).find_one({"telegram_link_code": code})
    except Exception as exc:
        log.error("Cari link code gagal: %s", type(exc).__name__)
        raise DatabaseError("Gagal memverifikasi kode linking.") from exc


def find_by_telegram_chat_id(chat_id: int) -> dict[str, Any] | None:
    try:
        return get_collection(COLLECTION_CUSTOMERS).find_one(
            {"telegram_chat_id": int(chat_id)}
        )
    except Exception as exc:
        log.error("Cari customer via chat_id %s gagal: %s", chat_id, type(exc).__name__)
        raise DatabaseError("Gagal mencari pelanggan via Telegram.") from exc


def create_customer(
    *,
    username: str,
    display_name: str = "",
    phone: str = "",
    role: str = Role.CUSTOMER.value,
    password_hash: str = "",
    status: str = "active",
) -> dict[str, Any]:
    username = username.strip().lower()
    if find_by_username(username):
        raise ConflictError(f"Username '{username}' sudah dipakai.")

    if phone and not PHONE_RE.match(phone):
        raise ConflictError("Nomor telepon tidak valid.")
    if phone:
        existing = get_collection(COLLECTION_CUSTOMERS).find_one({"phone": phone})
        if existing:
            raise ConflictError("Nomor telepon sudah terdaftar.")

    customer_id = new_customer_id()
    now = now_iso()
    doc = {
        "_id": customer_id,
        "customer_id": customer_id,
        "username": username,
        "display_name": display_name.strip() or username,
        "phone": phone.strip(),
        "role": role,
        "status": status,
        "password_hash": password_hash,
        "telegram_chat_id": None,
        "telegram_verified": False,
        "telegram_username": "",
        "passport": _empty_passport(),
        "created_at": now,
        "updated_at": now,
    }
    try:
        get_collection(COLLECTION_CUSTOMERS).insert_one(doc)
    except Exception as exc:
        log.error("Buat customer %s gagal: %s: %s", username, type(exc).__name__, exc)
        raise DatabaseError("Gagal membuat akun pelanggan.") from exc

    log.info("customer_created id=%s username=%s role=%s", customer_id, username, role)
    return doc


def update_fields(customer_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    payload = {**fields, "updated_at": now_iso()}
    try:
        result = get_collection(COLLECTION_CUSTOMERS).update_one(
            {"_id": customer_id}, {"$set": payload}
        )
    except Exception as exc:
        log.error("Update customer %s gagal: %s", customer_id, type(exc).__name__)
        raise DatabaseError("Gagal menyimpan perubahan pelanggan.") from exc
    if not _was_modified(result):
        # `_id` tidak cocok — coba lewat `customer_id` (dokumen lama).
        try:
            result = get_collection(COLLECTION_CUSTOMERS).update_one(
                {"customer_id": customer_id}, {"$set": payload}
            )
        except Exception as exc:
            log.error("Update customer %s (fallback) gagal: %s", customer_id, type(exc).__name__)
            raise DatabaseError("Gagal menyimpan perubahan pelanggan.") from exc
    return get_by_id(customer_id)


def _was_modified(result: Any) -> bool:
    """Astra sering melaporkan n=0 walau dokumen ada; andalkan `nModified`."""
    info = getattr(result, "update_info", None) or {}
    try:
        return int(info.get("n", 0)) > 0
    except (TypeError, ValueError):
        return bool(result)


def set_telegram_link_code(customer_id: str, code: str, expires_at: str) -> None:
    update_fields(
        customer_id, {"telegram_link_code": code, "telegram_link_code_expires_at": expires_at}
    )


def clear_telegram_link_code(customer_id: str) -> None:
    update_fields(customer_id, {"telegram_link_code": "", "telegram_link_code_expires_at": ""})


def link_telegram(
    customer_id: str, chat_id: int, telegram_username: str = ""
) -> dict[str, Any]:
    """Ikat chat_id Telegram ke customer. Sekaligus menulis `customer_id` ke `user_profiles`."""
    doc = update_fields(
        customer_id,
        {
            "telegram_chat_id": int(chat_id),
            "telegram_verified": True,
            "telegram_linked_at": now_iso(),
            "telegram_username": telegram_username.strip().lstrip("@"),
            "telegram_link_code": "",
            "telegram_link_code_expires_at": "",
        },
    )
    sync_legacy_profile(
        chat_id=chat_id,
        customer_id=customer_id,
        nama=doc.get("display_name") or doc.get("username", ""),
    )
    log.info("telegram_linked customer=%s chat_id=%s", customer_id, chat_id)
    return doc


def list_customers(*, limit: int = 500) -> list[dict[str, Any]]:
    try:
        return list(
            get_collection(COLLECTION_CUSTOMERS).find(
                {}, sort={"created_at": -1}, limit=limit
            )
        )
    except Exception as exc:
        log.error("Daftar customer gagal: %s", type(exc).__name__)
        raise DatabaseError("Gagal membaca daftar pelanggan.") from exc


def count_customers(*, verified_only: bool = False) -> int:
    query = {"telegram_verified": True} if verified_only else {}
    try:
        return int(
            get_collection(COLLECTION_CUSTOMERS).count_documents(query, upper_bound=10_000)
        )
    except Exception:
        try:
            return len(list(get_collection(COLLECTION_CUSTOMERS).find(query, limit=10_000)))
        except Exception as exc:
            log.warning("Hitung customer gagal: %s", type(exc).__name__)
            return 0


# ── Sinkronisasi ke `user_profiles` (legacy Telegram) ───────────────────────
def sync_legacy_profile(*, chat_id: int, customer_id: str, nama: str) -> None:
    """
    Tulis `customer_id` ke `user_profiles` agar order lama & bot tetap terhubung.

    Kegagalan tidak fatal — web tetap berfungsi, hanya history Telegram yang
    belum tersambung.
    """
    try:
        get_collection(COLLECTION_PROFILES).update_one(
            {"_id": str(chat_id)},
            {"$set": {"customer_id": customer_id, "nama": nama, "updated_at": now_iso()}},
            upsert=True,
        )
    except Exception as exc:
        log.warning(
            "Sinkron user_profiles/%s gagal: %s: %s", chat_id, type(exc).__name__, exc
        )


def get_legacy_profile(chat_id: int) -> dict[str, Any]:
    try:
        doc = get_collection(COLLECTION_PROFILES).find_one({"_id": str(chat_id)}) or {}
    except Exception as exc:
        log.error("Baca user_profiles/%s gagal: %s", chat_id, type(exc).__name__)
        raise DatabaseError("Gagal membaca profil Telegram.") from exc
    doc.pop("_id", None)
    return doc


def update_legacy_profile(chat_id: int, fields: dict[str, Any]) -> None:
    """Simpan preferensi non-struktur ke profil Telegram (avoided_times, dll)."""
    try:
        get_collection(COLLECTION_PROFILES).update_one(
            {"_id": str(chat_id)},
            {"$set": {**fields, "updated_at": now_iso()}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("Update user_profiles/%s gagal: %s", chat_id, type(exc).__name__)
        raise DatabaseError("Gagal menyimpan profil Telegram.") from exc


def resolve_customer_id_by_chat_id(chat_id: int) -> str | None:
    """Petakan chat_id → customer_id (dari `customers`, lalu `user_profiles`)."""
    doc = find_by_telegram_chat_id(chat_id)
    if doc:
        return str(doc.get("customer_id") or doc.get("_id"))
    legacy = get_legacy_profile(chat_id)
    return str(legacy.get("customer_id")) if legacy.get("customer_id") else None


def normalize_legacy_avoided_times(raw: Any) -> list[str]:
    out: list[str] = []
    for item in split_codes(raw):
        code = normalize_avoided_code(item)
        if code in AVOIDED_TIME_OPTIONS and code not in out:
            out.append(code)
    return out


# ── Dietary Passport ────────────────────────────────────────────────────────
def _empty_passport() -> dict[str, Any]:
    return {
        "allergies": [],
        "intolerances": [],
        "medical": [],
        "preferences": [],
        "avoided_ingredients": [],
        "avoided_times": [],
        "medical_notes": "",
        "safety_notes": "",
        "emergency_notes": "",
        "emergency_contact": {"name": "", "phone": "", "relationship": ""},
        "updated_at": "",
    }


def _restriction(raw: Any, category: RestrictionCategory) -> RestrictionOut:
    if isinstance(raw, dict):
        return RestrictionOut(
            code=normalize_allergen_code(raw.get("code") or ""),
            label=str(raw.get("label") or raw.get("code") or "—"),
            category=category,
            severity=str(raw.get("severity") or ""),
            notes=str(raw.get("notes") or ""),
        )
    return RestrictionOut(
        code=normalize_allergen_code(raw),
        label=str(raw),
        category=category,
    )


def get_passport(customer_id: str) -> PassportOut:
    """
    Baca Dietary Passport terstruktur.

    Bila passport belum pernah diisi, bangun tampilan dari `user_profiles` —
    3 profil lama hanya punya `dietary_profile` berupa string koma.
    """
    doc = get_by_id(customer_id)
    raw = doc.get("passport") or {}
    legacy = _passport_from_legacy_profile(doc)

    def group(key: str, category: RestrictionCategory) -> list[RestrictionOut]:
        items = raw.get(key)
        if isinstance(items, list) and items:
            return [_restriction(i, category) for i in items]
        return legacy.get(key, [])

    allergies = group("allergies", RestrictionCategory.ALLERGY)
    intolerances = group("intolerances", RestrictionCategory.INTOLERANCE)
    medical = group("medical", RestrictionCategory.MEDICAL)
    preferences = group("preferences", RestrictionCategory.PREFERENCE)

    avoided_times = normalize_legacy_avoided_times(
        raw.get("avoided_times") or doc.get("avoided_times") or legacy.get("avoided_times")
    )

    return PassportOut(
        allergies=allergies,
        intolerances=intolerances,
        medical=medical,
        preferences=preferences,
        avoided_ingredients=[str(a) for a in (raw.get("avoided_ingredients") or []) if a],
        avoided_times=avoided_times,
        medical_notes=str(raw.get("medical_notes") or ""),
        safety_notes=str(raw.get("safety_notes") or ""),
        emergency_notes=str(raw.get("emergency_notes") or ""),
        emergency_contact=EmergencyContact(
            **(raw.get("emergency_contact") or {})  # type: ignore[arg-type]
        ),
        critical_codes=sorted(
            {r.code for r in (*allergies, *intolerances, *medical) if r.code}
        ),
        legacy_dietary_profile=str(
            (raw.get("legacy_dietary_profile") or doc.get("legacy_dietary_profile") or "")
        ),
        structured=bool(
            allergies or intolerances or medical or preferences
            or raw.get("avoided_ingredients")
        ),
        updated_at=str(raw.get("updated_at") or doc.get("updated_at") or ""),
    )


def _passport_from_legacy_profile(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Bentuk passport sementara dari `dietary_profile` legacy.

    Data lama (`user_profiles`) hanya menyimpan satu string bebas
    `dietary_profile` — tidak membedakan alergi, intoleransi, atau preferensi.
    Semuanya diklasifikasikan sebagai `allergy` (kategori kritis, lihat
    `SAFETY_CRITICAL_CATEGORIES`) agar tidak ada alergi nyata yang lolos ke
    dapur hanya karena salah klasifikasi. Konsekuensinya sistem lebih sering
    memberi peringatan — itu memang pilihan yang benar untuk produksi makanan.
    Dapur tetap bisa mengoreksi klasifikasi lewat kolom notes.
    """
    fallback = _empty_passport()
    chat_id = doc.get("telegram_chat_id")
    legacy_dietary = str(doc.get("legacy_dietary_profile") or "")
    legacy_avoided: list[str] = []

    if chat_id:
        try:
            profile = get_legacy_profile(int(chat_id))
            legacy_dietary = legacy_dietary or str(profile.get("dietary_profile") or "")
            legacy_avoided = normalize_legacy_avoided_times(profile.get("avoided_times"))
        except DatabaseError:
            pass

    labels = _legacy_labels()
    items: list[RestrictionOut] = []
    for part in split_codes(legacy_dietary):
        if part.lower() in ("tidak ada", "-", ""):
            continue
        code = normalize_allergen_code(part)
        items.append(
            RestrictionOut(
                code=code,
                label=labels.get(code, part),
                category=RestrictionCategory.ALLERGY,
                notes="Diimpor dari dietary_profile lama (klasifikasi perlu dikonfirmasi)",
            )
        )

    fallback["intolerances"] = items
    fallback["avoided_times"] = legacy_avoided
    return fallback


def _legacy_labels() -> dict[str, str]:
    from app.repositories.catalog_repo import list_allergens

    try:
        return {a.code: a.label for a in list_allergens(include_inactive=True)}
    except DatabaseError:
        return {}


def save_passport(customer_id: str, payload: PassportIn) -> PassportOut:
    """
    Simpan passport. Partial update: hanya bagian yang diisi yang ditulis.

    `payload` adalah model `PassportIn`; field yang `None` berarti "tidak
    diubah", bukan "dikosongkan".
    """
    doc = get_by_id(customer_id)
    current = {**_empty_passport(), **(doc.get("passport") or {})}

    for key in ("allergies", "intolerances", "medical", "preferences"):
        group = getattr(payload, key, None)
        if group is not None:
            current[key] = [r.model_dump(mode="json") for r in group]

    for key in (
        "avoided_ingredients",
        "medical_notes",
        "safety_notes",
        "emergency_notes",
        "avoided_times",
    ):
        value = getattr(payload, key, None)
        if value is not None:
            current[key] = value

    if payload.emergency_contact is not None:
        current["emergency_contact"] = payload.emergency_contact.model_dump()

    # Simpan juga representasi legacy agar bot Telegram & order lama konsisten.
    # WAJIB dihitung dari `current` (hasil merge), bukan dari `payload`: kalau
    # pelanggan hanya mengirim `avoided_times`, allergen sebelumnya tetap berlaku
    # dan string legacy tidak boleh ikut hilang.
    critical_labels = [
        str(item.get("label") or item.get("code") or "").strip()
        for group in ("allergies", "intolerances", "medical")
        for item in (current.get(group) or [])
    ]
    current["legacy_dietary_profile"] = (
        ", ".join(label for label in critical_labels if label) or "Tidak ada"
    )
    current["updated_at"] = now_iso()

    update_fields(customer_id, {"passport": current})

    # Cermin ke user_profiles bila customer sudah tertaut Telegram.
    chat_id = doc.get("telegram_chat_id")
    if chat_id:
        mirror = {
            "dietary_profile": current["legacy_dietary_profile"],
            "avoided_times": current.get("avoided_times") or [],
        }
        if doc.get("display_name"):
            mirror["nama"] = doc["display_name"]
        update_legacy_profile(int(chat_id), mirror)

    log.info("passport_updated customer=%s", customer_id)
    return get_passport(customer_id)


def critical_codes_for_customer(customer_id: str) -> list[str]:
    return get_passport(customer_id).critical_codes
