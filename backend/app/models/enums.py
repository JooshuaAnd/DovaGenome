"""Enum & value object domain."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "customer"
    KITCHEN = "kitchen"
    ADMIN = "admin"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    READY = "READY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentStatus(StrEnum):
    UNPAID = "UNPAID"
    PENDING = "PENDING"
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class RestrictionCategory(StrEnum):
    ALLERGY = "allergy"
    INTOLERANCE = "intolerance"
    MEDICAL = "medical"
    PREFERENCE = "preference"


class SafetyLevel(StrEnum):
    """Tingkat keparahan hasil pemeriksaan kecocokan menu."""

    SAFE = "safe"            # tidak ada tabrakan
    CAUTION = "caution"      # ada batasan ringan atau preferensi, bukan allergen kritis
    BLOCKED = "blocked"      # ada allergen kritis yang dikecualikan passport


class MenuStatus(StrEnum):
    """
    Siklus hidup Daily Menu.

    DRAFT   → hanya terlihat admin, tidak bisa dipesan.
    PUBLISHED → terlihat pelanggan yang eligible dan bisa dipesan.
    CLOSED  → tidak ada pesanan baru; tetap tampil pada order lama.
    """

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class MealType(StrEnum):
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
