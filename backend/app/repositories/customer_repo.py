"""Repository customer + Dietary Passport — Postgres.

Interface identik dengan versi Astra sehingga auth_service dan router tidak berubah.

Perubahan internal:
- customers + user_profiles → tabel customers
- passport nested → tabel dietary_passports (satu baris per customer)
- customer_id pakai kolom TEXT (bukan _id UUID dari Astra)
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.core.domain import (
    CATEGORY_LABELS,
    RESTRICTION_CATEGORIES,
    TABLE_CUSTOMERS,
    TABLE_DIETARY_PASSPORTS,
    normalize_allergen_code,
    normalize_avoided_code,
    split_codes,
)
from app.core.errors import DatabaseError, NotFoundError
from app.core.logging import get_logger
from app.models.enums import RestrictionCategory
from app.repositories import supabase as db
from app.schemas.customer import (
    CustomerOut,
    EmergencyContact,
    PassportIn,
    PassportOut,
    RestrictionOut,
)
from app.utils.time import now_iso, now_wib

log = get_logger("dova.repo.customer")

PHONE_RE = re.compile(r"^\+?[0-9][0-9\s-]{6,19}$")


# ── Helper ──────────────────────────────────────────────────────────────────
def new_customer_id() -> str:
    return "cust_" + uuid.uuid4().hex[:24]


def normalize_phone(raw: str) -> str:
    """Normalisasi nomor telepon agar lookup & keunikan konsisten.

    `0812...` → `+62812...`, `62812...` → `+62812...`, nomor lain dipakai apa
    adanya (digit saja, opsional awalan `+`).
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if digits.startswith("62"):
        return "+" + digits
    if digits.startswith("0"):
        return "+62" + digits[1:]
    return ("+" + digits) if plus else digits


def username_from_phone(phone: str) -> str:
    """Username internal deterministik dari nomor telepon (pengenal unik)."""
    digits = re.sub(r"\D", "", phone or "") or uuid.uuid4().hex[:8]
    return ("cust" + digits)[:32]


def find_by_phone(phone: str) -> dict[str, Any] | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    try:
        return db.execute_one(
            f"SELECT * FROM {TABLE_CUSTOMERS} WHERE phone = %s",  # noqa: S608
            (normalized,),
        )
    except Exception as exc:
        log.error("find_by_phone gagal: %s", exc)
        raise DatabaseError("Gagal membaca data pelanggan.") from exc


def _row_to_customer(row: dict[str, Any]) -> CustomerOut:
    return CustomerOut(
        customer_id=str(row.get("customer_id") or ""),
        username=str(row.get("username") or ""),
        display_name=str(row.get("display_name") or ""),
        phone=str(row.get("phone") or ""),
        role=str(row.get("role") or "customer"),
        status=str(row.get("status") or "active"),
        telegram_chat_id=row.get("telegram_chat_id"),
        telegram_verified=bool(row.get("telegram_verified", False)),
        telegram_link_code=str(row.get("telegram_link_code") or ""),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


# ── Pembacaan ───────────────────────────────────────────────────────────────
def find_by_username(username: str) -> dict[str, Any] | None:
    try:
        return db.execute_one(
            f"SELECT * FROM {TABLE_CUSTOMERS} WHERE username = %s",  # noqa: S608
            (username.strip().lower(),),
        )
    except Exception as exc:
        log.error("find_by_username gagal: %s", exc)
        raise DatabaseError("Gagal membaca data pelanggan.") from exc


def get_by_id(customer_id: str) -> dict[str, Any]:
    try:
        row = db.execute_one(
            f"SELECT * FROM {TABLE_CUSTOMERS} WHERE customer_id = %s",  # noqa: S608
            (customer_id,),
        )
    except Exception as exc:
        raise DatabaseError("Gagal membaca data pelanggan.") from exc
    if not row:
        raise NotFoundError(f"Pelanggan '{customer_id}' tidak ditemukan.")
    return row


def get_public(customer_id: str) -> CustomerOut:
    return to_public(get_by_id(customer_id))


def to_public(doc: dict[str, Any]) -> CustomerOut:
    return _row_to_customer(doc)


def find_by_link_code(code: str) -> dict[str, Any] | None:
    if not code:
        return None
    try:
        return db.execute_one(
            f"SELECT * FROM {TABLE_CUSTOMERS} WHERE telegram_link_code = %s",  # noqa: S608
            (code.strip().upper(),),
        )
    except Exception as exc:
        raise DatabaseError("Gagal mencari kode linking.") from exc


def find_by_telegram_chat_id(chat_id: int) -> dict[str, Any] | None:
    try:
        return db.execute_one(
            f"SELECT * FROM {TABLE_CUSTOMERS} WHERE telegram_chat_id = %s",  # noqa: S608
            (int(chat_id),),
        )
    except Exception as exc:
        raise DatabaseError("Gagal mencari pelanggan by chat_id.") from exc


# ── Penulisan ───────────────────────────────────────────────────────────────
def create_customer(
    *,
    username: str,
    display_name: str = "",
    phone: str = "",
    role: str = "customer",
    password_hash: str | None = None,
) -> dict[str, Any]:
    username = username.strip().lower()
    existing = find_by_username(username)
    if existing:
        from app.core.errors import ConflictError
        raise ConflictError(f"Username '{username}' sudah dipakai.")

    phone = normalize_phone(phone)
    if phone and role == "customer":
        from app.core.errors import ConflictError
        if find_by_phone(phone):
            raise ConflictError(
                "Nomor telepon ini sudah terdaftar. Silakan masuk dengan nomor tersebut."
            )

    customer_id = new_customer_id()
    try:
        db.execute_write(
            f"""
            INSERT INTO {TABLE_CUSTOMERS}
                (customer_id, username, display_name, phone, role, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,  # noqa: S608
            (customer_id, username, display_name or username, phone or "", role, password_hash),
        )
    except Exception as exc:
        raise DatabaseError("Gagal membuat akun pelanggan.") from exc
    return get_by_id(customer_id)


def update_fields(customer_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    if not fields:
        return get_by_id(customer_id)

    safe = {k: v for k, v in fields.items() if re.match(r"^[a-z_]+$", k)}
    if not safe:
        return get_by_id(customer_id)

    safe["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = %s" for k in safe)
    values = tuple(safe.values()) + (customer_id,)
    try:
        db.execute_write(
            f"UPDATE {TABLE_CUSTOMERS} SET {set_clause} WHERE customer_id = %s",  # noqa: S608
            values,
        )
    except Exception as exc:
        raise DatabaseError("Gagal memperbarui data pelanggan.") from exc
    return get_by_id(customer_id)


def set_telegram_link_code(customer_id: str, code: str, expires_at: str) -> None:
    update_fields(
        customer_id,
        {
            "telegram_link_code": code.upper(),
            "telegram_link_code_expires_at": expires_at,
        },
    )


def clear_telegram_link_code(customer_id: str) -> None:
    update_fields(
        customer_id,
        {"telegram_link_code": None, "telegram_link_code_expires_at": None},
    )


def link_telegram(customer_id: str, chat_id: int, telegram_username: str = "") -> None:
    update_fields(
        customer_id,
        {
            "telegram_chat_id": int(chat_id),
            "telegram_verified": True,
            "telegram_username": telegram_username or "",
            "telegram_linked_at": now_iso(),
            "telegram_link_code": None,
            "telegram_link_code_expires_at": None,
        },
    )
    # Sync ke dietary_passports bila sudah ada
    _ensure_passport_row(customer_id)


def _ensure_passport_row(customer_id: str) -> None:
    """Buat baris dietary_passports bila belum ada."""
    try:
        db.execute_write(
            f"""
            INSERT INTO {TABLE_DIETARY_PASSPORTS} (customer_id)
            VALUES (%s)
            ON CONFLICT (customer_id) DO NOTHING
            """,  # noqa: S608
            (customer_id,),
        )
    except Exception:
        pass


def list_customers(*, limit: int = 500) -> list[dict[str, Any]]:
    try:
        return db.execute(
            f"SELECT * FROM {TABLE_CUSTOMERS} ORDER BY created_at ASC LIMIT %s",  # noqa: S608
            (limit,),
        )
    except Exception as exc:
        raise DatabaseError("Gagal membaca daftar pelanggan.") from exc


def count_customers(*, verified_only: bool = False) -> int:
    try:
        if verified_only:
            row = db.execute_one(
                f"SELECT COUNT(*) AS n FROM {TABLE_CUSTOMERS} WHERE telegram_verified = TRUE",  # noqa: S608
            )
        else:
            row = db.execute_one(f"SELECT COUNT(*) AS n FROM {TABLE_CUSTOMERS}")  # noqa: S608
        return int(row["n"]) if row else 0
    except Exception as exc:
        log.warning("count_customers gagal: %s", exc)
        return 0


# ── Legacy profile sync (kompatibilitas bot Telegram lama) ──────────────────
def sync_legacy_profile(*, chat_id: int, customer_id: str, nama: str) -> None:
    """Perbarui display_name dan chat_id di tabel customers."""
    update_fields(
        customer_id,
        {"telegram_chat_id": int(chat_id), "display_name": nama or ""},
    )


def get_legacy_profile(chat_id: int) -> dict[str, Any]:
    """Baca profil lama berformat {nama, alergen, avoided_times}."""
    row = find_by_telegram_chat_id(chat_id)
    if not row:
        return {}
    passport_row = db.execute_one(
        f"SELECT * FROM {TABLE_DIETARY_PASSPORTS} WHERE customer_id = %s",  # noqa: S608
        (row["customer_id"],),
    )
    return _legacy_format(row, passport_row)


def _legacy_format(row: dict[str, Any], passport_row: dict[str, Any] | None) -> dict[str, Any]:
    """Kembalikan format lama yang dipakai bot Telegram."""
    allergies: list[str] = []
    if passport_row:
        import json as _json
        raw = passport_row.get("allergies") or []
        if isinstance(raw, str):
            try:
                raw = _json.loads(raw)
            except Exception:
                raw = []
        for r in raw:
            if isinstance(r, dict) and r.get("code"):
                allergies.append(normalize_allergen_code(r["code"]))

    avoided_raw = (passport_row or {}).get("avoided_times") or []
    if isinstance(avoided_raw, str):
        avoided_raw = split_codes(avoided_raw)

    return {
        "customer_id": str(row.get("customer_id") or ""),
        "chat_id": row.get("telegram_chat_id"),
        "nama": str(row.get("display_name") or ""),
        "alergen": allergies,
        "avoided_times": avoided_raw,
        "dietary_profile": ", ".join(allergies) if allergies else "Tidak ada",
    }


def update_legacy_profile(chat_id: int, fields: dict[str, Any]) -> None:
    """Perbarui profil lama (kompatibilitas bot)."""
    row = find_by_telegram_chat_id(chat_id)
    if not row:
        return
    customer_id = str(row["customer_id"])
    customer_fields: dict[str, Any] = {}
    if "nama" in fields:
        customer_fields["display_name"] = fields["nama"]
    if customer_fields:
        update_fields(customer_id, customer_fields)

    # Alergen dan avoided_times disimpan ke passport
    passport_fields: dict[str, Any] = {}
    if "alergen" in fields:
        import json as _json
        codes = fields["alergen"] if isinstance(fields["alergen"], list) else split_codes(fields["alergen"])
        passport_fields["allergies"] = _json.dumps(
            [{"code": normalize_allergen_code(c), "label": c, "category": "allergy", "severity": "", "notes": ""} for c in codes if c]
        )
    if "avoided_times" in fields:
        raw = fields["avoided_times"]
        if isinstance(raw, list):
            avoided = raw
        else:
            avoided = split_codes(raw)
        passport_fields["avoided_times"] = avoided

    if passport_fields:
        _ensure_passport_row(customer_id)
        safe = {k: v for k, v in passport_fields.items() if re.match(r"^[a-z_]+$", k)}
        if safe:
            set_clause = ", ".join(f"{k} = %s" for k in safe)
            vals = tuple(safe.values()) + (customer_id,)
            db.execute_write(
                f"UPDATE {TABLE_DIETARY_PASSPORTS} SET {set_clause} WHERE customer_id = %s",  # noqa: S608
                vals,
            )


def resolve_customer_id_by_chat_id(chat_id: int) -> str | None:
    row = find_by_telegram_chat_id(chat_id)
    return str(row["customer_id"]) if row else None


def normalize_legacy_avoided_times(raw: Any) -> list[str]:
    from app.core.domain import AVOIDED_TIME_OPTIONS
    items = raw if isinstance(raw, list) else split_codes(raw)
    out: list[str] = []
    for item in items:
        code = normalize_avoided_code(str(item or ""))
        if code in AVOIDED_TIME_OPTIONS and code not in out:
            out.append(code)
    return out


# ── Dietary Passport ─────────────────────────────────────────────────────────
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
        "emergency_contact": {},
        "legacy_dietary_profile": "",
        "structured": False,
        "updated_at": "",
    }


def _restriction(raw: Any, category: RestrictionCategory) -> RestrictionOut:
    if isinstance(raw, dict):
        return RestrictionOut(
            code=normalize_allergen_code(str(raw.get("code") or "")),
            label=str(raw.get("label") or ""),
            category=category,
            severity=str(raw.get("severity") or ""),
            notes=str(raw.get("notes") or ""),
        )
    return RestrictionOut(
        code=normalize_allergen_code(str(raw or "")),
        label=str(raw or ""),
        category=category,
    )


def get_passport(customer_id: str) -> PassportOut:
    import json as _json

    # Pastikan customer ada
    get_by_id(customer_id)

    row = db.execute_one(
        f"SELECT * FROM {TABLE_DIETARY_PASSPORTS} WHERE customer_id = %s",  # noqa: S608
        (customer_id,),
    )
    if not row:
        return PassportOut()

    def _parse_jsonb(val: Any) -> list:
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            return _json.loads(val)
        except Exception:
            return []

    def group(key: str, category: RestrictionCategory) -> list[RestrictionOut]:
        items = _parse_jsonb(row.get(key))
        return [_restriction(r, category) for r in items if r]

    allergies    = group("allergies",    RestrictionCategory.ALLERGY)
    intolerances = group("intolerances", RestrictionCategory.INTOLERANCE)
    medical      = group("medical",      RestrictionCategory.MEDICAL)
    preferences  = group("preferences",  RestrictionCategory.PREFERENCE)

    avoided_ingredients = row.get("avoided_ingredients") or []
    if isinstance(avoided_ingredients, str):
        avoided_ingredients = split_codes(avoided_ingredients)

    avoided_times = row.get("avoided_times") or []
    if isinstance(avoided_times, str):
        avoided_times = split_codes(avoided_times)

    from app.core.domain import SAFETY_CRITICAL_CATEGORIES
    critical_codes = list({
        r.code
        for r in (allergies + intolerances + medical)
        if r.category.value in SAFETY_CRITICAL_CATEGORIES and r.code
    })

    ec_raw = row.get("emergency_contact") or {}
    if isinstance(ec_raw, str):
        try:
            ec_raw = _json.loads(ec_raw)
        except Exception:
            ec_raw = {}

    return PassportOut(
        allergies=allergies,
        intolerances=intolerances,
        medical=medical,
        preferences=preferences,
        avoided_ingredients=list(avoided_ingredients),
        avoided_times=list(avoided_times),
        medical_notes=str(row.get("medical_notes") or ""),
        safety_notes=str(row.get("safety_notes") or ""),
        emergency_notes=str(row.get("emergency_notes") or ""),
        emergency_contact=EmergencyContact(**ec_raw) if isinstance(ec_raw, dict) else EmergencyContact(),
        critical_codes=critical_codes,
        legacy_dietary_profile=str(row.get("legacy_dietary_profile") or ""),
        structured=bool(row.get("structured", False)),
        updated_at=str(row.get("updated_at") or ""),
    )


def save_passport(customer_id: str, payload: PassportIn) -> PassportOut:
    import json as _json

    get_by_id(customer_id)  # pastikan ada
    _ensure_passport_row(customer_id)

    row = db.execute_one(
        f"SELECT * FROM {TABLE_DIETARY_PASSPORTS} WHERE customer_id = %s",  # noqa: S608
        (customer_id,),
    )
    existing = row or _empty_passport()

    def _ser(items: Any) -> str:
        if items is None:
            return _json.dumps([])
        return _json.dumps(
            [
                {
                    "code": normalize_allergen_code(r.code),
                    "label": r.label,
                    "category": r.category.value if hasattr(r.category, "value") else str(r.category),
                    "severity": r.severity,
                    "notes": r.notes,
                }
                for r in items
            ]
        )

    def _get_existing_list(key: str) -> str:
        val = existing.get(key) or []
        if isinstance(val, str):
            return val
        return _json.dumps(val)

    fields: dict[str, Any] = {
        "allergies":    _ser(payload.allergies)    if payload.allergies    is not None else _get_existing_list("allergies"),
        "intolerances": _ser(payload.intolerances) if payload.intolerances is not None else _get_existing_list("intolerances"),
        "medical":      _ser(payload.medical)      if payload.medical      is not None else _get_existing_list("medical"),
        "preferences":  _ser(payload.preferences)  if payload.preferences  is not None else _get_existing_list("preferences"),
        "avoided_ingredients": payload.avoided_ingredients if payload.avoided_ingredients is not None
                               else (existing.get("avoided_ingredients") or []),
        "avoided_times": payload.avoided_times if payload.avoided_times is not None
                         else (existing.get("avoided_times") or []),
        "medical_notes":    payload.medical_notes    if payload.medical_notes    is not None else str(existing.get("medical_notes") or ""),
        "safety_notes":     payload.safety_notes     if payload.safety_notes     is not None else str(existing.get("safety_notes") or ""),
        "emergency_notes":  payload.emergency_notes  if payload.emergency_notes  is not None else str(existing.get("emergency_notes") or ""),
        "emergency_contact": _json.dumps(payload.emergency_contact.model_dump()) if payload.emergency_contact is not None
                             else (_json.dumps(existing.get("emergency_contact") or {}) if isinstance(existing.get("emergency_contact"), dict) else (existing.get("emergency_contact") or "{}")),
        "structured": True,
        "updated_at": now_iso(),
    }

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = tuple(fields.values()) + (customer_id,)
    try:
        db.execute_write(
            f"UPDATE {TABLE_DIETARY_PASSPORTS} SET {set_clause} WHERE customer_id = %s",  # noqa: S608
            values,
        )
    except Exception as exc:
        raise DatabaseError("Gagal menyimpan Dietary Passport.") from exc

    return get_passport(customer_id)


def critical_codes_for_customer(customer_id: str) -> list[str]:
    """Kode alergen kritis dari passport customer."""
    try:
        passport = get_passport(customer_id)
        return passport.critical_codes
    except (NotFoundError, DatabaseError):
        return []
