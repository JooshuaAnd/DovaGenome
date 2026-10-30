"""Router dapur (KDS) — hanya untuk admin & kitchen.

Aturan tampilan yang ditegakkan di service, bukan di sini:
  * tidak ada data demo,
  * label allergen siap tampil (bukan kode internal),
  * tiket dengan pantangan didahulukan.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_staff
from app.core.logging import get_logger
from app.schemas.customer import CustomerOut
from app.schemas.internal import (
    KitchenBoardOut,
    KitchenConsumptionIn,
    KitchenConsumptionOut,
    KitchenInventoryOut,
    KitchenStatusIn,
    ProductionBatchCreateIn,
    ProductionBatchPlanIn,
    ProductionBatchListOut,
    ProductionBatchOut,
    ProductionWeighIn,
    ProductionWeighOut,
)
from app.schemas.order import OrderDetailOut
from app.services import (
    dashboard_service,
    inventory_operations_service,
    order_service,
    production_batch_service,
)

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


@router.get("/inventory", response_model=KitchenInventoryOut, summary="Kartu stok untuk pemakaian kitchen")
def inventory(staff: CustomerOut = Depends(require_staff)) -> KitchenInventoryOut:
    return KitchenInventoryOut.model_validate(inventory_operations_service.list_kitchen_inventory())


@router.post("/inventory/consume", response_model=KitchenConsumptionOut, summary="Catat pemakaian bahan aktual")
def consume_inventory(
    payload: KitchenConsumptionIn,
    staff: CustomerOut = Depends(require_staff),
) -> KitchenConsumptionOut:
    return KitchenConsumptionOut.model_validate(
        inventory_operations_service.record_consumption(
            ingredient_id=payload.ingredient_id,
            quantity=payload.quantity,
            unit=payload.unit,
            batch_reference=payload.batch_reference,
            note=payload.note,
            idempotency_key=payload.idempotency_key,
            actor_id=staff.customer_id,
        )
    )


@router.get(
    "/production-batches",
    response_model=ProductionBatchListOut,
    summary="Daftar batch produksi dan BOM terencana",
)
def production_batches(
    service_date: date | None = Query(default=None),
    staff: CustomerOut = Depends(require_staff),
) -> ProductionBatchListOut:
    return ProductionBatchListOut.model_validate(
        production_batch_service.list_batches(service_date=service_date)
    )


@router.post(
    "/production-batches",
    response_model=ProductionBatchOut,
    status_code=201,
    summary="Buat batch produksi dari recipe VERIFIED",
)
def create_production_batch(
    payload: ProductionBatchCreateIn,
    staff: CustomerOut = Depends(require_staff),
) -> ProductionBatchOut:
    return ProductionBatchOut.model_validate(
        production_batch_service.create_batch(
            service_date=payload.service_date,
            meal_slot=payload.meal_slot,
            recipe_version_id=payload.recipe_version_id,
            planned_portions=payload.planned_portions,
            site_code=payload.site_code,
            notes=payload.notes,
            actor_id=staff.customer_id,
        )
    )


@router.post(
    "/production-batches/plan-from-paid-orders",
    summary="Agregasikan order PAID menjadi batch produksi",
)
def plan_production_batches(
    payload: ProductionBatchPlanIn,
    staff: CustomerOut = Depends(require_staff),
) -> dict:
    return production_batch_service.plan_batches_from_paid_orders(
        service_date=payload.service_date,
        meal_slot=payload.meal_slot,
        site_code=payload.site_code,
        actor_id=staff.customer_id,
    )


@router.post(
    "/production-batches/{batch_id}/weigh",
    response_model=ProductionWeighOut,
    summary="Catat berat bahan ke batch dan ledger stok",
)
def weigh_production_requirement(
    batch_id: str,
    payload: ProductionWeighIn,
    staff: CustomerOut = Depends(require_staff),
) -> ProductionWeighOut:
    return ProductionWeighOut.model_validate(
        production_batch_service.record_weigh(
            batch_id=batch_id,
            requirement_id=payload.requirement_id,
            actual_net_grams=payload.actual_net_grams,
            tare_grams=payload.tare_grams,
            idempotency_key=payload.idempotency_key,
            lot_id=payload.lot_id,
            scale_source=payload.scale_source,
            device_id=payload.device_id,
            actor_id=staff.customer_id,
            note=payload.note,
        )
    )


@router.post(
    "/production-batches/{batch_id}/complete",
    response_model=ProductionBatchOut,
    summary="Selesaikan batch setelah seluruh bahan ditimbang",
)
def complete_production_batch(
    batch_id: str,
    staff: CustomerOut = Depends(require_staff),
) -> ProductionBatchOut:
    return ProductionBatchOut.model_validate(
        production_batch_service.complete_batch(
            batch_id=batch_id,
            actor_id=staff.customer_id,
        )
    )


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
