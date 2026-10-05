"""Pydantic schema DovaGenome."""

from app.schemas.catalog import (
    AllergenIn,
    AllergenOut,
    AllergenPatch,
    CatalogMetaOut,
    CatalogOut,
    MenuIn,
    MenuIngredient,
    MenuOut,
    PackageIn,
    PackageOut,
    PackagePatch,
)
from app.schemas.common import ApiModel, ErrorBody, ErrorResponse, HealthPayload, Page
from app.schemas.customer import (
    CustomerAdminOut,
    CustomerOut,
    EmergencyContact,
    LoginIn,
    PassportIn,
    PassportOut,
    RegisterIn,
    RestrictionIn,
    RestrictionOut,
    StaffIn,
    TelegramLinkIn,
    TelegramLinkOut,
    TokenOut,
)
from app.schemas.internal import (
    AdminDashboardOut,
    AdminDayScheduleOut,
    AdminKpi,
    AdminOrderRow,
    AdminScheduleOut,
    AdminSystemOut,
    AiConsultIn,
    AiConsultOut,
    AiMenuSuggestionIn,
    CollectionCount,
    FeedbackIn,
    FeedbackOut,
    KitchenBoardOut,
    KitchenStatusIn,
    KitchenTicketOut,
)
from app.schemas.order import (
    DaySafetyOut,
    InvoiceLineOut,
    InvoiceOut,
    OrderCreateIn,
    OrderDetailOut,
    OrderOut,
    OrderUpdateIn,
    SafetyConflict,
    SafetyReportOut,
)

__all__ = [name for name in dir() if not name.startswith("_")]
