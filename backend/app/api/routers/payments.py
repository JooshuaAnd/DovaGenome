"""Payment intent dan webhook provider."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError as PydanticValidationError

from app.api.deps import get_current_customer
from app.core.errors import ValidationError
from app.schemas.customer import CustomerOut
from app.schemas.payment import PaymentIntentIn, PaymentIntentOut, PaymentWebhookIn, PaymentWebhookOut
from app.services import payment_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/orders/{order_id}/intent", response_model=PaymentIntentOut)
def create_intent(
    order_id: str,
    payload: PaymentIntentIn,
    customer: CustomerOut = Depends(get_current_customer),
) -> PaymentIntentOut:
    return payment_service.create_intent(
        order_id,
        customer,
        provider=payload.provider,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/webhooks/{provider}", response_model=PaymentWebhookOut)
async def webhook(
    provider: str,
    request: Request,
    x_payment_signature: str = Header(default=""),
) -> PaymentWebhookOut:
    raw_body = await request.body()
    try:
        payload = PaymentWebhookIn.model_validate_json(raw_body)
    except (PydanticValidationError, json.JSONDecodeError) as exc:
        raise ValidationError("Payload webhook pembayaran tidak valid.") from exc
    if payload.provider.lower() != provider.strip().lower():
        raise ValidationError("Provider pada URL dan payload tidak sama.")
    return payment_service.process_webhook(
        payload,
        raw_body=raw_body,
        signature=x_payment_signature,
    )


__all__ = ["router"]
