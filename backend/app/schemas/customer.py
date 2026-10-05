"""Schema customer + Dietary Passport.

Dietary Passport memisahkan empat jenis batasan (spec §9) — allergy,
intolerance, medical restriction, dan preference tidak boleh dicampur.
"""

from __future__ import annotations

import re

from pydantic import Field, field_validator

from app.core.domain import AVOIDED_TIME_OPTIONS, normalize_avoided_code
from app.models.enums import RestrictionCategory
from app.schemas.common import ApiModel

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s-]{6,19}$")


class RestrictionOut(ApiModel):
    """Satu batasan yang sudah diklasifikasi."""

    code: str
    label: str
    category: RestrictionCategory = RestrictionCategory.ALLERGY
    severity: str = ""
    notes: str = ""


class RestrictionIn(ApiModel):
    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    category: RestrictionCategory = RestrictionCategory.ALLERGY
    severity: str = ""
    notes: str = ""


class EmergencyContact(ApiModel):
    name: str = ""
    phone: str = ""
    relationship: str = ""


class PassportIn(ApiModel):
    """Body untuk menyimpan Dietary Passport. Semua field opsional → partial update."""

    allergies: list[RestrictionIn] | None = None
    intolerances: list[RestrictionIn] | None = None
    medical: list[RestrictionIn] | None = None
    preferences: list[RestrictionIn] | None = None
    avoided_ingredients: list[str] | None = None
    medical_notes: str | None = None
    safety_notes: str | None = None
    emergency_notes: str | None = None
    emergency_contact: EmergencyContact | None = None
    avoided_times: list[str] | None = None

    @field_validator("avoided_times")
    @classmethod
    def _valid_slots(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for raw in v:
            code = normalize_avoided_code(raw)
            if code in AVOIDED_TIME_OPTIONS and code not in out:
                out.append(code)
        return out


class PassportOut(ApiModel):
    """Dietary Passport yang sudah dikelompokkan per kategori."""

    allergies: list[RestrictionOut] = Field(default_factory=list)
    intolerances: list[RestrictionOut] = Field(default_factory=list)
    medical: list[RestrictionOut] = Field(default_factory=list)
    preferences: list[RestrictionOut] = Field(default_factory=list)
    avoided_ingredients: list[str] = Field(default_factory=list)
    avoided_times: list[str] = Field(default_factory=list)
    medical_notes: str = ""
    safety_notes: str = ""
    emergency_notes: str = ""
    emergency_contact: EmergencyContact = Field(default_factory=EmergencyContact)
    critical_codes: list[str] = Field(default_factory=list)
    # Kolom legacy `dietary_profile` (string koma) — dipertahankan sebagai
    # fallback baca untuk 3 profil lama yang belum punya passport terstruktur.
    legacy_dietary_profile: str = ""
    structured: bool = False
    updated_at: str = ""


class CustomerOut(ApiModel):
    customer_id: str
    username: str
    display_name: str = ""
    phone: str = ""
    role: str = "customer"
    status: str = "active"
    telegram_chat_id: int | None = None
    telegram_verified: bool = False
    telegram_link_code: str = ""
    telegram_deep_link: str = ""
    created_at: str = ""
    updated_at: str = ""


class CustomerAdminOut(CustomerOut):
    order_count: int = 0
    active_order_count: int = 0
    last_order_at: str | None = None
    passport: PassportOut | None = None


# ── Auth ────────────────────────────────────────────────────────────────────
class RegisterIn(ApiModel):
    """MVP passwordless: username (+ telepon opsional) sudah cukup untuk masuk."""

    username: str
    display_name: str = Field(default="", max_length=120)
    phone: str = ""

    @field_validator("username")
    @classmethod
    def _valid_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError(
                "username harus 3–32 karakter: huruf kecil, angka, titik, "
                "underscore, atau strip"
            )
        return v

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, v: str) -> str:
        v = (v or "").strip()
        if v and not PHONE_RE.match(v):
            raise ValueError("nomor telepon tidak valid")
        return v


class LoginIn(ApiModel):
    username: str
    password: str | None = None


class TokenOut(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    customer: CustomerOut


class StaffIn(ApiModel):
    username: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = ""
    role: str = "admin"


class TelegramLinkIn(ApiModel):
    """Dipanggil oleh Telegram bot untuk mengikat chat_id ke customer."""

    code: str = Field(min_length=4, max_length=64)
    chat_id: int
    telegram_username: str = ""


class TelegramLinkOut(ApiModel):
    customer_id: str
    telegram_chat_id: int
    linked_at: str
