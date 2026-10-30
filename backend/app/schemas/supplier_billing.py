"""Supplier invoice and payable API contracts."""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel


class SupplierInvoiceIn(ApiModel):
    invoice_number: str = Field(min_length=1, max_length=100)
    payment_terms: Literal["PAY_ON_DELIVERY", "WEEKLY_INVOICE"]
    amount: float = Field(gt=0, le=1_000_000_000_000)
    due_date: date
    po_id: str | None = Field(default=None, max_length=160)
    period_start: date | None = None
    period_end: date | None = None
    notes: str = Field(default="", max_length=1000)


class SupplierInvoiceVerifyIn(ApiModel):
    decision: Literal["APPROVE", "REJECT"]
    notes: str = Field(min_length=1, max_length=1000)


class SupplierPaymentIn(ApiModel):
    amount: float = Field(gt=0, le=1_000_000_000_000)
    payment_method: Literal["MANUAL", "QR_ILLUSTRATIVE"]
    payment_reference: str = Field(default="", max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=160)
    notes: str = Field(default="", max_length=1000)
