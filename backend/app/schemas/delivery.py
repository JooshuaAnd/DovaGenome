from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel


class DeliveryStopCreateIn(ApiModel):
    order_id: str = Field(min_length=1, max_length=160)
    service_date: date
    meal_slot: Literal["breakfast", "lunch", "dinner"] = "lunch"


class DeliveryAssignIn(ApiModel):
    courier_id: str = Field(min_length=1, max_length=160)


class DeliveryStatusIn(ApiModel):
    status: Literal["PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED", "FAILED"]
    idempotency_key: str = Field(min_length=8, max_length=160)
    proof_ref: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=500)
