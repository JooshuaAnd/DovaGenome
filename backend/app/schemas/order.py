"""Schema order, safety check, dan invoice."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.core.domain import DAYS, normalize_allergen_code, split_codes
from app.models.enums import OrderStatus, PaymentStatus, SafetyLevel
from app.schemas.common import ApiModel
from app.schemas.customer import PassportOut


# ── Pemeriksaan keamanan (spec §10) ────────────────────────────────────────
class SafetyConflict(ApiModel):
    allergen_code: str
    allergen_label: str
    category: str
    found_in: list[str] = Field(default_factory=list)
    ingredient_names: list[str] = Field(default_factory=list)
    explanation: str = ""


class DaySafetyOut(ApiModel):
    hari: str
    menu_id: str = ""
    nama_menu: str
    deskripsi: str = ""
    allergen_codes: list[str] = Field(default_factory=list)
    allergen_labels: list[str] = Field(default_factory=list)
    alat_dapur_steril: list[str] = Field(default_factory=list)
    level: SafetyLevel = SafetyLevel.SAFE
    conflicts: list[SafetyConflict] = Field(default_factory=list)
    headline: str = ""
    #: Alasan singkat dalam kalimat: menu ini mengandung apa yang mengecualikan
    #: profil pelanggan. Wajib ada di level opsi DAN level hari supaya kartu
    #: keamanan bisa menjelaskan dirinya sendiri tanpa menebak dari `conflicts`.
    explanation: str = ""
    guidance: str = ""
    is_recommended: bool = True


class MenuOptionSafetyOut(ApiModel):
    """
    Status keamanan untuk SATU opsi menu.

    Satu hari layanan punya banyak opsi, dan setiap opsi punya kadar allergen
    berbeda — jadi statusnya harus melekat pada opsi, bukan pada hari.
    """

    menu_id: str
    level: SafetyLevel = SafetyLevel.SAFE
    headline: str = ""
    explanation: str = ""
    guidance: str = ""
    is_recommended: bool = True
    conflicts: list[SafetyConflict] = Field(default_factory=list)


class SafetyReportOut(ApiModel):
    level: SafetyLevel = SafetyLevel.SAFE
    is_recommended: bool = True
    headline: str = ""
    explanation: str = ""
    guidance: str = ""
    menu_contains: list[str] = Field(default_factory=list)
    passport_excludes: list[str] = Field(default_factory=list)
    conflicts: list[SafetyConflict] = Field(default_factory=list)
    per_day: list[DaySafetyOut] = Field(default_factory=list)
    critical_codes: list[str] = Field(default_factory=list)
    keywords_detected: list[str] = Field(default_factory=list)


# ── Order ───────────────────────────────────────────────────────────────────
class DaySelectionIn(ApiModel):
    """
    Satu hari layanan + opsi menu yang dipilih untuk hari itu.

    Inilah yang membedakan "catering mingguan" dari "satu menu untuk semua hari":
    pelanggan memilih satu dari banyak opsi, untuk setiap hari yang dilayani.
    """

    hari: str
    menu_id: str = Field(min_length=1, max_length=120)

    @field_validator("hari")
    @classmethod
    def _valid_day(cls, v: str) -> str:
        if v not in DAYS:
            raise ValueError(f"hari harus salah satu dari: {', '.join(DAYS)}")
        return v


class OrderSelectionOut(ApiModel):
    """Pilihan menu yang tersimpan pada pesanan, sudah di Enriched dengan tanggal."""

    hari: str
    menu_id: str = ""
    service_date: str = ""
    date_label: str = ""
    nama_menu: str = ""
    deskripsi: str = ""
    allergen_labels: list[str] = Field(default_factory=list)
    alat_dapur_steril: list[str] = Field(default_factory=list)
    level: SafetyLevel = SafetyLevel.SAFE
    is_recommended: bool = True


class OrderCreateIn(ApiModel):
    """
    Buat pesanan. Memakai katalog aktif — client tidak boleh menentukan harga.

    `selections` opsional demi kompatibilitas: bila kosong, backend memakai opsi
    utama (pertama) yang tersedia untuk tiap hari paket. Billing lama, Telegram,
    dan `verify_phase2.py` tidak pernah mengirim field ini.
    """

    package_code: str = Field(min_length=2, max_length=64)
    selected_allergen_codes: list[str] = Field(default_factory=list)
    customer_note: str = ""
    schedule_days: list[str] | None = None
    selections: list[DaySelectionIn] | None = None
    delivery_address: str = ""
    apply_passport: bool = True

    @field_validator("selected_allergen_codes")
    @classmethod
    def _normalize(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for raw in v:
            code = normalize_allergen_code(raw)
            if code and code not in out:
                out.append(code)
        return out

    @field_validator("schedule_days")
    @classmethod
    def _valid_days(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        bad = [d for d in v if d not in DAYS]
        if bad:
            raise ValueError(f"hari tidak dikenal: {', '.join(bad)}")
        return [d for d in DAYS if d in set(v)]

    @field_validator("selections")
    @classmethod
    def _unique_days(cls, v: list[DaySelectionIn] | None) -> list[DaySelectionIn] | None:
        """Satu hari hanya boleh punya satu pilihan — duplikat ditolak, bukan diam."""
        if v is None:
            return None
        seen: set[str] = set()
        for item in v:
            if item.hari in seen:
                raise ValueError(f"hari '{item.hari}' dipilih lebih dari sekali")
            seen.add(item.hari)
        # Urut sesuai kalender layanan supaya(order tersimpan rapi.
        return sorted(v, key=lambda s: DAYS.index(s.hari))


class OrderUpdateIn(ApiModel):
    """Perubahan oleh pelanggan sebelum masuk dapur."""

    selected_allergen_codes: list[str] | None = None
    customer_note: str | None = None
    delivery_address: str | None = None
    schedule_days: list[str] | None = None
    selections: list[DaySelectionIn] | None = None


class OrderOut(ApiModel):
    """DTO order — menormalkan kedua shape historis di Astra DB."""

    id: str
    order_id: str
    customer_id: str | None = None
    customer_name: str
    chat_id: int | None = None
    package_code: str = ""
    subscription_type: str
    schedule_days: list[str] = Field(default_factory=list)
    #: Pilihan menu per hari. Kosong untuk order lama (Shape A/B).
    selections: list[OrderSelectionOut] = Field(default_factory=list)
    selected_allergens: list[str] = Field(default_factory=list)
    allergen_labels: list[str] = Field(default_factory=list)
    dietary_profile: str = "Tidak ada"
    kitchen_notes: str = ""
    customer_note: str = ""
    delivery_address: str = ""
    avoided_times: list[str] = Field(default_factory=list)
    meal_count: int = 0
    status: OrderStatus = OrderStatus.PENDING
    status_meta: dict = Field(default_factory=dict)
    next_status: OrderStatus | None = None
    next_action: str = ""
    created_at: str = ""
    updated_at: str = ""
    elapsed_minutes: int = 0
    sla_level: str = "fresh"
    service_day: str | None = None
    service_menu: str | None = None
    has_safety_flags: bool = False
    schema_version: str = "v2"
    invoice_number: str = ""
    subtotal: int = 0
    discount: int = 0
    total: int = 0
    payment_status: PaymentStatus = PaymentStatus.UNPAID


class OrderDetailOut(OrderOut):
    safety: SafetyReportOut | None = None
    passport: PassportOut | None = None
    timeline: list[dict] = Field(default_factory=list)
    demo: bool = False


# ── Invoice (spec §13) ──────────────────────────────────────────────────────
class InvoiceLineOut(ApiModel):
    label: str
    quantity: int = 1
    unit_price: int = 0
    amount: int = 0


class InvoiceOut(ApiModel):
    invoice_number: str
    order_id: str
    issued_at: str
    currency: str = "IDR"
    customer_name: str
    customer_contact: str = ""
    package_name: str
    schedule_days: list[str] = Field(default_factory=list)
    meal_count: int = 0
    dietary_safety_summary: str = ""
    dietary_safety_items: list[str] = Field(default_factory=list)
    lines: list[InvoiceLineOut] = Field(default_factory=list)
    subtotal: int = 0
    discount: int = 0
    total: int = 0
    payment_status: PaymentStatus = PaymentStatus.UNPAID
    payment_reference: str = ""
    demo: bool = False


__all__ = [
    "DaySafetyOut",
    "DaySelectionIn",
    "InvoiceLineOut",
    "InvoiceOut",
    "MenuOptionSafetyOut",
    "OrderCreateIn",
    "OrderDetailOut",
    "OrderOut",
    "OrderSelectionOut",
    "OrderUpdateIn",
    "SafetyConflict",
    "SafetyReportOut",
    "split_codes",
]
