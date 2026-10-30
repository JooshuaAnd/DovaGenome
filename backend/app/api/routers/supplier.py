"""Router supplier — PO masuk, respon konfirmasi, katalog harga bahan baku, dan pengiriman."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import SupplierPrincipal, require_supplier
from app.core.logging import get_logger
from app.repositories import supabase
from app.schemas.supplier_billing import SupplierInvoiceIn
from app.services import procurement_service
from app.services import supplier_billing_service

log = get_logger("dova.api.supplier")

router = APIRouter(prefix="/supplier", tags=["supplier"])


class PoResponseIn(BaseModel):
    status: str  # ACKNOWLEDGED/ACCEPTED | REJECTED | PARTIALLY_RECEIVED/PARTIAL | RECEIVED
    notes: str = ""
    estimated_delivery: str | None = None


class GoodsReceiptLineIn(BaseModel):
    po_item_id: int = Field(gt=0)
    quantity: float = Field(gt=0, le=1_000_000)
    unit: str = Field(min_length=1, max_length=32)


class GoodsReceiptIn(BaseModel):
    lines: list[GoodsReceiptLineIn] = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=500)


@router.get("/pos", summary="Daftar Purchase Orders masuk untuk supplier")
def list_pos(
    principal: SupplierPrincipal = Depends(require_supplier),
) -> list[dict[str, Any]]:
    """Mengambil daftar PO aktif yang dikirimkan oleh sistem katering Dova."""
    receipt_fields = supabase.check_procurement_receipt_migrations()
    item_fields = """
                   'ingredient_id', pi.ingredient_id,
                   'received_qty', pi.received_qty
    """ if receipt_fields else """
                   'ingredient_id', NULL,
                   'received_qty', 0
    """
    query = f"""
        SELECT po.po_id, po.supplier_id, s.name as supplier_name, s.phone as supplier_phone,
               s.category, s.email, po.status, po.total_amount, po.need_by_date, po.notes, po.created_at,
               COALESCE(json_agg(json_build_object(
                   'id', pi.id,
                   'item_name', pi.item_name,
                   'qty', pi.qty,
                   'unit', pi.unit,
                   'unit_price', pi.unit_price,
                   'subtotal', pi.subtotal,
                   {item_fields}
               )) FILTER (WHERE pi.id IS NOT NULL), '[]'::json) as items
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.supplier_id
        LEFT JOIN po_items pi ON po.po_id = pi.po_id
        WHERE po.supplier_id = %s
          AND po.status IN ('SENT', 'ACCEPTED', 'REJECTED', 'PARTIAL', 'RECEIVED', 'CLOSED')
        GROUP BY po.po_id, po.supplier_id, s.name, s.phone, s.category, s.email, po.status, po.total_amount, po.need_by_date, po.notes, po.created_at
        ORDER BY po.created_at DESC
    """
    return supabase.execute(query, (principal.supplier_id,))


@router.post("/pos/{po_id}/respond", summary="Tanggapi PO: Terima, Tolak, atau Kirim")
def respond_po(
    po_id: str,
    payload: PoResponseIn,
    principal: SupplierPrincipal = Depends(require_supplier),
) -> dict[str, Any]:
    """Supplier mengonfirmasi penerimaan atau penolakan PO."""
    try:
        result = procurement_service.record_supplier_response(
            po_id,
            principal.supplier_id,
            status=payload.status,
            notes=payload.notes,
            estimated_delivery=payload.estimated_delivery,
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "status": "success",
        "po_id": po_id,
        "new_status": result["status"],
        "notes": result.get("notes", payload.notes),
        "message": f"PO {po_id} berhasil ditanggapi dengan status {result['status']}",
    }


@router.post("/pos/{po_id}/receive", summary="Posting goods receipt dan tambah stok")
def receive_po(
    po_id: str,
    payload: GoodsReceiptIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: SupplierPrincipal = Depends(require_supplier),
) -> dict[str, Any]:
    """Supplier posts actual delivered quantities; stock is updated atomically."""
    try:
        result = procurement_service.receive_purchase_order(
            po_id,
            principal.supplier_id,
            lines=[line.model_dump() for line in payload.lines],
            idempotency_key=idempotency_key or "",
            actor_id=principal.customer.customer_id,
            notes=payload.notes,
        )
        return result
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/invoices", summary="Daftar invoice supplier milik tenant ini")
def list_supplier_invoices(
    principal: SupplierPrincipal = Depends(require_supplier),
) -> list[dict[str, Any]]:
    return supplier_billing_service.list_invoices(supplier_id=principal.supplier_id)


@router.post("/invoices", status_code=201, summary="Ajukan invoice supplier")
def submit_supplier_invoice(
    payload: SupplierInvoiceIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: SupplierPrincipal = Depends(require_supplier),
) -> dict[str, Any]:
    return supplier_billing_service.submit_invoice(
        supplier_id=principal.supplier_id,
        actor_id=principal.customer.customer_id,
        invoice_number=payload.invoice_number,
        payment_terms=payload.payment_terms,
        amount=payload.amount,
        due_date=payload.due_date,
        idempotency_key=idempotency_key or "",
        po_id=payload.po_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        notes=payload.notes,
    )


@router.get("/catalog", summary="Daftar item katalog yang disuplai")
def list_supplier_catalog(
    principal: SupplierPrincipal = Depends(require_supplier),
) -> list[dict[str, Any]]:
    """Katalog harga bahan baku dari supplier."""
    query = f"""
        SELECT si.id, si.supplier_id, si.ingredient_name, si.ingredient_name as item_name,
               si.unit, si.price_per_unit, si.moq, si.lead_time_days,
               s.name as supplier_name, true as is_available
        FROM supplier_items si
        JOIN suppliers s ON si.supplier_id = s.supplier_id
        WHERE si.supplier_id = %s
        ORDER BY si.ingredient_name ASC
    """
    return supabase.execute(query, (principal.supplier_id,))


@router.get("/summary", summary="Ringkasan statistik supplier")
def supplier_summary(
    principal: SupplierPrincipal = Depends(require_supplier),
) -> dict[str, Any]:
    """Statistik cepat untuk dashboard supplier."""
    total_pos = supabase.execute_one(
        "SELECT COUNT(*) as cnt FROM purchase_orders WHERE supplier_id = %s",
        (principal.supplier_id,),
    )
    pending_pos = supabase.execute_one(
        "SELECT COUNT(*) as cnt FROM purchase_orders WHERE supplier_id = %s AND status = 'SENT'",
        (principal.supplier_id,),
    )
    accepted_pos = supabase.execute_one(
        "SELECT COUNT(*) as cnt FROM purchase_orders WHERE supplier_id = %s AND status IN ('ACCEPTED', 'RECEIVED')",
        (principal.supplier_id,),
    )
    suppliers = supabase.execute(
        "SELECT supplier_id, name, category, phone, email, rating FROM suppliers WHERE supplier_id = %s",
        (principal.supplier_id,),
    )

    return {
        "total_pos": total_pos.get("cnt", 0) if total_pos else 0,
        "pending_pos": pending_pos.get("cnt", 0) if pending_pos else 0,
        "accepted_pos": accepted_pos.get("cnt", 0) if accepted_pos else 0,
        "suppliers": suppliers,
    }


@router.get("/demand-forecast", summary="Prediksi demand dan kebutuhan bahan baku untuk supplier (AI ML)")
def supplier_demand_forecast(
    principal: SupplierPrincipal = Depends(require_supplier),
) -> dict[str, Any]:
    """Hold the legacy material forecast until BOM/inventory contracts exist.

    The old implementation called analytics facades that contained synthetic
    demand, inventory, and supplier fallbacks. Returning 410 is safer than
    exposing a plausible-looking supplier forecast with no auditable BOM.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "Supplier material forecast legacy dinonaktifkan. Gunakan forecast "
            "backtest live admin; material demand menunggu BOM, inventory, "
            "unit conversion, dan lead time terverifikasi."
        ),
    )

