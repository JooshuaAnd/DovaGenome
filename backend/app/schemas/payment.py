"""Contract pembayaran: intent pelanggan dan webhook provider."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ApiModel


class PaymentIntentIn(ApiModel):
    provider: str = Field(default="manual", min_length=2, max_length=40)
    idempotency_key: str = Field(min_length=8, max_length=120)

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("provider pembayaran tidak valid")
        return value


class PaymentIntentOut(ApiModel):
    payment_attempt_id: str
    order_id: str
    provider: str
    provider_payment_id: str = ""
    idempotency_key: str
    status: str
    amount: int
    currency: str = "IDR"
    expires_at: datetime | None = None


class PaymentWebhookIn(ApiModel):
    provider: str = Field(min_length=2, max_length=40)
    event_id: str = Field(min_length=2, max_length=160)
    provider_payment_id: str = Field(min_length=1, max_length=160)
    order_id: str = Field(min_length=5, max_length=120)
    amount: int = Field(ge=0)
    currency: str = Field(default="IDR", min_length=3, max_length=8)
    status: Literal["SUCCEEDED", "FAILED", "EXPIRED", "REFUNDED"]

    @field_validator("provider", "currency")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip().upper()


class PaymentWebhookOut(ApiModel):
    accepted: bool = True
    duplicate: bool = False
    order_id: str
    payment_attempt_id: str
    payment_status: str
    kitchen_ticket_created: bool = False


__all__ = [
    "PaymentIntentIn",
    "PaymentIntentOut",
    "PaymentWebhookIn",
    "PaymentWebhookOut",
]
