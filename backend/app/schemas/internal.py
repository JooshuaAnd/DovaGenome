"""Schema API internal: KDS, admin, AI, feedback."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field, field_validator

from app.core.domain import ALL_STATUSES
from app.models.enums import OrderStatus, PaymentStatus
from app.schemas.common import ApiModel
from app.schemas.order import OrderOut, SafetyReportOut


# ── Kitchen Display System ──────────────────────────────────────────────────
class KitchenStatusIn(ApiModel):
    status: OrderStatus
    note: str = Field(default="", max_length=500)

    @field_validator("status")
    @classmethod
    def _known(cls, v: OrderStatus) -> OrderStatus:
        if str(v) not in ALL_STATUSES:
            raise ValueError(f"status tidak dikenal: {v}")
        return v


class KitchenTicketOut(OrderOut):
    """Tiket dapur — safety info dibuat menonjol, bukan hanya mengandalkan warna."""

    critical_allergens: list[str] = Field(default_factory=list)
    is_critical: bool = False
    safety_banner: str = ""
    equipment_notes: list[str] = Field(default_factory=list)
    menu_ingredients: list[str] = Field(default_factory=list)


class KitchenBoardOut(ApiModel):
    columns: dict[str, list[KitchenTicketOut]] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    total_active: int = 0
    fetched_at: str = ""
    demo: bool = False


class KitchenInventoryItemOut(ApiModel):
    ingredient_id: str = ""
    ingredient_name: str
    current_stock: float
    min_stock: float
    unit: str
    status: str
    updated_at: str = ""
    is_scan_ready: bool = False


class KitchenInventoryOut(ApiModel):
    items: list[KitchenInventoryItemOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    fetched_at: str = ""


class KitchenConsumptionIn(ApiModel):
    ingredient_id: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0, le=100_000)
    unit: str = Field(min_length=1, max_length=32)
    batch_reference: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=128)


class KitchenConsumptionOut(ApiModel):
    movement_id: str
    ingredient_id: str
    ingredient_name: str
    consumed_quantity: float
    unit: str
    current_stock: float
    min_stock: float
    status: str
    idempotent: bool = False
    lot_allocations: list[dict[str, Any]] = Field(default_factory=list)


# ── Production batch & weigh ledger ────────────────────────────────────────
MealSlot = Literal["breakfast", "lunch", "dinner", "snack"]


class ProductionBatchCreateIn(ApiModel):
    service_date: date
    meal_slot: MealSlot = "lunch"
    recipe_version_id: str = Field(min_length=1, max_length=160)
    planned_portions: int = Field(gt=0, le=100_000)
    site_code: str = Field(default="main-kitchen", min_length=1, max_length=80)
    notes: str = Field(default="", max_length=500)


class ProductionBatchPlanIn(ApiModel):
    service_date: date
    meal_slot: MealSlot = "lunch"
    site_code: str = Field(default="main-kitchen", min_length=1, max_length=80)


class ProductionBatchRequirementOut(ApiModel):
    requirement_id: str
    ingredient_id: str
    ingredient_name: str
    planned_quantity: float
    unit: str
    issued_quantity: float = 0
    variance_quantity: float = 0
    planned_grams: float = 0
    issued_grams: float = 0
    remaining_grams: float = 0


class ProductionBatchOut(ApiModel):
    batch_id: str
    service_date: str
    meal_slot: MealSlot
    site_code: str
    recipe_version_id: str
    menu_name: str = ""
    planned_portions: int
    status: str
    notes: str = ""
    requirements: list[ProductionBatchRequirementOut] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ProductionWeighIn(ApiModel):
    requirement_id: str = Field(min_length=1, max_length=160)
    actual_net_grams: float = Field(gt=0, le=1_000_000)
    tare_grams: float = Field(default=0, ge=0, le=1_000_000)
    idempotency_key: str = Field(min_length=8, max_length=160)
    lot_id: str | None = Field(default=None, max_length=160)
    scale_source: Literal["manual"] = "manual"
    device_id: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=500)


class ProductionWeighOut(ApiModel):
    weigh_event_id: str
    movement_id: str
    batch_id: str
    requirement_id: str
    ingredient_id: str
    ingredient_name: str
    actual_net_grams: float
    stock_quantity_deducted: float
    stock_unit: str
    current_stock: float
    stock_status: str
    issued_grams: float
    remaining_planned_grams: float
    idempotent: bool = False
    lot_allocations: list[dict[str, Any]] = Field(default_factory=list)


class ProductionBatchListOut(ApiModel):
    items: list[ProductionBatchOut] = Field(default_factory=list)
    fetched_at: str = ""


# ── Admin ───────────────────────────────────────────────────────────────────
class AdminKpi(ApiModel):
    key: str
    label: str
    value: int
    note: str = ""
    tone: str = "neutral"


class AdminDashboardOut(ApiModel):
    generated_at: str
    active_orders: int
    pending_orders: int
    preparing_orders: int
    packed_orders: int
    delivering_orders: int
    completed_today: int
    cancelled_today: int
    safety_alerts: int
    average_wait_minutes: int
    oldest_ticket_minutes: int
    total_customers: int
    verified_customers: int
    orders_by_package: list[dict] = Field(default_factory=list)
    orders_by_restriction: list[dict] = Field(default_factory=list)
    orders_by_status: list[dict] = Field(default_factory=list)
    weekly_trend: list[dict] = Field(default_factory=list)
    demo: bool = False


class AdminOrderRow(ApiModel):
    id: str
    order_id: str
    customer_name: str
    customer_id: str | None = None
    subscription_type: str
    status: OrderStatus
    allergen_labels: list[str] = Field(default_factory=list)
    created_at: str = ""
    elapsed_minutes: int = 0
    total: int = 0
    payment_status: PaymentStatus = PaymentStatus.UNPAID


class AdminDayScheduleOut(ApiModel):
    hari: str
    nama_menu: str
    deskripsi: str = ""
    order_count: int = 0
    orders: list[AdminOrderRow] = Field(default_factory=list)
    flagged_count: int = 0
    alat_dapur_steril: list[str] = Field(default_factory=list)
    is_today: bool = False
    #: Satu hari bisa punya banyak opsi menu. `nama_menu` tetap opsi utama supaya
    #: tampilan lama tidak berubah; `option_count`/`option_names` memberi tahu sisa.
    option_count: int = 0
    option_names: list[str] = Field(default_factory=list)
    #: Menu yang benar-benar dipilih tiap pelanggan pada hari ini.
    chosen_menus: dict[str, str] = Field(default_factory=dict)


class AdminScheduleOut(ApiModel):
    days: list[AdminDayScheduleOut] = Field(default_factory=list)
    is_service_day: bool = True
    generated_at: str = ""


class CollectionCount(ApiModel):
    name: str
    documents: int | None = None
    managed: bool = True


class AdminSystemOut(ApiModel):
    supabase_connected: bool = False
    database_source: str = "supabase_postgres"
    astra_connected: bool = False
    astra_state: str = "OFFLINE_LEGACY"
    demo_mode: bool
    credentials: dict[str, bool] = Field(default_factory=dict)
    collections: list[CollectionCount] = Field(default_factory=list)
    foreign_collections: list[str] = Field(default_factory=list)
    telegram_bot_username: str = ""
    telegram_deep_link_order: str = ""
    langflow_configured: bool = False
    version: str = ""


# ── AI ──────────────────────────────────────────────────────────────────────
class AiConsultIn(ApiModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = ""
    context: dict = Field(default_factory=dict)


class AiConsultOut(ApiModel):
    reply: str
    session_id: str
    model: str = "langflow"
    provider: str = "langflow"
    flow_id: str = ""
    trace_id: str = ""
    latency_ms: int = 0
    degraded: bool = False
    readiness_state: str = "CONNECTED"
    reason_code: str = "flow_execution_ok"
    message: str = ""


class AiMenuSuggestionIn(ApiModel):
    selected_allergen_codes: list[str] = Field(default_factory=list)
    service_days: list[str] = Field(default_factory=list)


class AiMenuSuggestionOut(ApiModel):
    """Saran menu + laporan safety deterministik yang mendasarinya."""

    reply: str
    safety: SafetyReportOut
    suggested_days: list[str] = Field(default_factory=list)
    avoided_days: list[str] = Field(default_factory=list)
    session_id: str = ""
    degraded: bool = False


class FeedbackIn(ApiModel):
    category: str = Field(default="general", max_length=40)
    message: str = Field(min_length=1, max_length=2000)
    email: str = ""
    order_id: str = ""
    rating: int | None = Field(default=None, ge=1, le=5)


class FeedbackOut(ApiModel):
    feedback_id: str
    received_at: str
    category: str
