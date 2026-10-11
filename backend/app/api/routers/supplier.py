"""Router supplier — PO masuk, respon konfirmasi, katalog harga bahan baku, dan pengiriman."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import get_logger
from app.repositories import supabase

log = get_logger("dova.api.supplier")

router = APIRouter(prefix="/supplier", tags=["supplier"])


class PoResponseIn(BaseModel):
    status: str  # ACKNOWLEDGED | REJECTED | PARTIALLY_RECEIVED | RECEIVED
    notes: str = ""
    estimated_delivery: str | None = None


@router.get("/pos", summary="Daftar Purchase Orders masuk untuk supplier")
def list_pos(supplier_id: str | None = None) -> list[dict[str, Any]]:
    """Mengambil daftar PO aktif yang dikirimkan oleh sistem katering Dova."""
    where_clause = "WHERE po.supplier_id = %s" if supplier_id else ""
    params = (supplier_id,) if supplier_id else ()

    query = f"""
        SELECT po.po_id, po.supplier_id, s.name as supplier_name, s.phone as supplier_phone,
               s.category, s.email, po.status, po.total_amount, po.need_by_date, po.notes, po.created_at,
               COALESCE(json_agg(json_build_object(
                   'id', pi.id,
                   'item_name', pi.item_name,
                   'qty', pi.qty,
                   'unit', pi.unit,
                   'unit_price', pi.unit_price,
                   'subtotal', pi.subtotal
               )) FILTER (WHERE pi.id IS NOT NULL), '[]'::json) as items
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.supplier_id
        LEFT JOIN po_items pi ON po.po_id = pi.po_id
        {where_clause}
        GROUP BY po.po_id, po.supplier_id, s.name, s.phone, s.category, s.email, po.status, po.total_amount, po.need_by_date, po.notes, po.created_at
        ORDER BY po.created_at DESC
    """
    return supabase.execute(query, params)


@router.post("/pos/{po_id}/respond", summary="Tanggapi PO: Terima, Tolak, atau Kirim")
def respond_po(po_id: str, payload: PoResponseIn) -> dict[str, Any]:
    """Supplier mengonfirmasi penerimaan atau penolakan PO."""
    po = supabase.execute_one(
        "SELECT po.*, s.name as supplier_name FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.supplier_id WHERE po.po_id = %s",
        (po_id,)
    )
    if not po:
        raise HTTPException(status_code=404, detail="PO tidak ditemukan")

    # Update status PO
    supabase.execute_write(
        """
        UPDATE purchase_orders
        SET status = %s,
            notes = CASE WHEN %s != '' THEN notes || ' | Respon: ' || %s ELSE notes END
        WHERE po_id = %s
        """,
        (payload.status.upper(), payload.notes, payload.notes, po_id)
    )

    # Kirim notifikasi otomatis balik ke Admin via Notification Outbox
    admin_msg = (
        f"📢 Update Supplier: {po.get('supplier_name')} telah memperbarui status {po_id} "
        f"menjadi '{payload.status.upper()}'. Catatan: {payload.notes or '-'}"
    )
    supabase.execute_write(
        """
        INSERT INTO notification_outbox (recipient_type, recipient_phone, recipient_name, channel, event_type, message, status)
        VALUES ('admin', '+6281326332247', 'Dova Kitchen Admin', 'whatsapp', 'PO_SUPPLIER_RESPONSE', %s, 'SENT')
        """,
        (admin_msg,)
    )

    return {
        "status": "success",
        "po_id": po_id,
        "new_status": payload.status.upper(),
        "notes": payload.notes,
        "message": f"PO {po_id} berhasil diperbarui menjadi {payload.status.upper()}",
    }


@router.get("/catalog", summary="Daftar item katalog yang disuplai")
def list_supplier_catalog(supplier_id: str | None = None) -> list[dict[str, Any]]:
    """Katalog harga bahan baku dari supplier."""
    where_clause = "WHERE si.supplier_id = %s" if supplier_id else ""
    params = (supplier_id,) if supplier_id else ()

    query = f"""
        SELECT si.id, si.supplier_id, si.ingredient_name, si.ingredient_name as item_name,
               si.unit, si.price_per_unit, si.moq, si.lead_time_days,
               s.name as supplier_name, true as is_available
        FROM supplier_items si
        JOIN suppliers s ON si.supplier_id = s.supplier_id
        {where_clause}
        ORDER BY si.ingredient_name ASC
    """
    return supabase.execute(query, params)


@router.get("/summary", summary="Ringkasan statistik supplier")
def supplier_summary() -> dict[str, Any]:
    """Statistik cepat untuk dashboard supplier."""
    total_pos = supabase.execute_one("SELECT COUNT(*) as cnt FROM purchase_orders")
    pending_pos = supabase.execute_one("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status IN ('DRAFT', 'PENDING_APPROVAL', 'SENT')")
    accepted_pos = supabase.execute_one("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status IN ('ACKNOWLEDGED', 'RECEIVED')")
    suppliers = supabase.execute("SELECT supplier_id, name, category, phone, email, rating FROM suppliers")

    return {
        "total_pos": total_pos.get("cnt", 0) if total_pos else 0,
        "pending_pos": pending_pos.get("cnt", 0) if pending_pos else 0,
        "accepted_pos": accepted_pos.get("cnt", 0) if accepted_pos else 0,
        "suppliers": suppliers,
    }


@router.get("/demand-forecast", summary="Prediksi demand dan kebutuhan bahan baku untuk supplier (AI ML)")
def supplier_demand_forecast() -> dict[str, Any]:
    """Proyeksi kebutuhan bahan baku 7 hari ke depan agar supplier dapat menyiapkan pasokan."""
    from app.services.analytics_ml_service import calculate_supply_chain_ml_forecast, calculate_transaction_demand_insights
    sc_ml = calculate_supply_chain_ml_forecast()
    insights = calculate_transaction_demand_insights()
    return {
        "generated_at": sc_ml.get("demand_forecast"),
        "materials": sc_ml.get("materials", []),
        "supplier_7d_forecast": insights.get("supplier_7d_forecast", []),
        "peak_day": insights.get("peak_day"),
        "top_dishes": insights.get("top_dishes", []),
    }

