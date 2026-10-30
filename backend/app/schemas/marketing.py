"""Request contracts for admin-reviewed marketing campaigns."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel


class WinbackCampaignDraftIn(ApiModel):
    """Only campaign delivery choices are client-controlled.

    Audience, risk band, consent, and message provenance are resolved by the
    backend from the live churn baseline; the client cannot submit recipients.
    """

    channel: Literal["whatsapp", "telegram"] = "telegram"
    max_recipients: int = Field(default=100, ge=1, le=1000)
    control_group_percent: int = Field(default=0, ge=0, le=50)
    rate_limit_per_minute: int = Field(default=20, ge=1, le=600)


class MarketingDeliveryWebhookIn(ApiModel):
    """Provider callback; it can only update an existing outbox row."""

    outbox_id: int = Field(ge=1)
    event_id: str = Field(min_length=1, max_length=200)
    status: Literal["SENT", "FAILED"]
    provider_message_id: str = Field(default="", max_length=200)
    failure_reason: str | None = Field(default=None, max_length=500)
