from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin, require_courier
from app.schemas.customer import CustomerOut
from app.schemas.delivery import DeliveryAssignIn, DeliveryStatusIn, DeliveryStopCreateIn
from app.services import delivery_service

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get("/stops", summary="Daftar delivery stop courier")
def stops(
    service_date: date | None = Query(default=None),
    courier: CustomerOut = Depends(require_courier),
) -> list[dict[str, Any]]:
    return delivery_service.list_stops(service_date=service_date, courier_id=courier.customer_id)


@router.patch("/stops/{stop_id}/status", summary="Perbarui status delivery oleh courier")
def status(
    stop_id: str,
    payload: DeliveryStatusIn,
    courier: CustomerOut = Depends(require_courier),
) -> dict[str, Any]:
    return delivery_service.update_status(
        stop_id=stop_id,
        status=payload.status,
        actor_id=courier.customer_id,
        idempotency_key=payload.idempotency_key,
        proof_ref=payload.proof_ref,
        note=payload.note,
    )
