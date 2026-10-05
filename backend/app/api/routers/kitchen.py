"""Router dapur (KDS) — hanya untuk admin & kitchen.

Aturan tampilan yang ditegakkan di service, bukan di sini:
  * tidak ada data demo,
  * label allergen siap tampil (bukan kode internal),
  * tiket dengan pantangan didahulukan.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_staff
from app.core.logging import get_logger
from app.schemas.customer import CustomerOut
from app.schemas.internal import KitchenBoardOut, KitchenStatusIn
from app.schemas.order import OrderDetailOut
from app.services import dashboard_service, order_service

log = get_logger("dova.api.kitchen")

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


@router.get("/board", response_model=KitchenBoardOut, summary="Papan dapur")
def board(
    staff: CustomerOut = Depends(require_staff),
    statuses: list[str] = Query(default_factory=list),
) -> KitchenBoardOut:
    """
    Kolom PENDING / PREPARING / READY dengan tiket di dalamnya.

    `statuses` opsional untuk memfilter, mis. `?statuses=PENDING&statuses=PREPARING`.
    """
    return dashboard_service.kitchen_board(statuses=statuses or None)


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderDetailOut,
    summary="Majukan status pesanan",
)
def advance(
    order_id: str,
    payload: KitchenStatusIn,
    staff: CustomerOut = Depends(require_staff),
) -> OrderDetailOut:
    """
    Pindahkan status satu tahap (PENDING → PREPARING → READY → COMPLETED).

    Melompat tahap ditolak. Pembatalan hanya untuk admin.
    """
    order = order_service.get_order_detail(order_id, is_staff=True)
    return order_service.advance_status(
        order.id,
        str(payload.status),
        role=staff.role,
        actor=f"{staff.role}:{staff.username}",
        note=payload.note,
    )