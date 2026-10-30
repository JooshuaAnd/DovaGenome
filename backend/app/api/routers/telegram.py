"""Server-to-server Telegram bridge.

The Telegram process is an HTTP client only.  It never opens a database
connection, so the web, Telegram, and kitchen paths all use the same
Supabase-backed order and safety services.
"""

from __future__ import annotations

import hmac
from datetime import date
from typing import Any
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.domain import DAYS
from app.repositories import catalog_repo, customer_repo
from app.repositories import supplier_repo, supabase
from app.schemas.order import DaySelectionIn, OrderCreateIn
from app.services import order_service
from app.services import procurement_service
from app.services import supplier_billing_service

router = APIRouter(prefix="/internal/telegram", tags=["telegram-internal"])


def _authorize(token: str) -> None:
    expected = settings.langflow_internal_token.strip()
    if not expected or not hmac.compare_digest(token.strip(), expected):
        raise HTTPException(status_code=403, detail="Telegram internal bridge tidak diotorisasi.")


class TelegramProfileIn(BaseModel):
    chat_id: int
    nama: str | None = Field(default=None, max_length=120)
    alergen: list[str] | None = None
    avoided_times: list[str] | None = None


class TelegramOrderIn(BaseModel):
    chat_id: int
    customer_name: str = Field(default="", max_length=120)
    package_code: str = ""
    selected_allergen_codes: list[str] = Field(default_factory=list)
    schedule_days: list[str] = Field(default_factory=list)
    selections: dict[str, str] = Field(default_factory=dict)
    customer_note: str = Field(default="", max_length=2000)


class TelegramSupplierResponseIn(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    notes: str = Field(default="", max_length=1000)
    estimated_delivery: str | None = None


class TelegramSupplierChangeIn(BaseModel):
    notes: str = Field(min_length=2, max_length=1000)
    estimated_delivery: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=160)


class TelegramSupplierInvoiceIn(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=100)
    payment_terms: Literal["PAY_ON_DELIVERY", "WEEKLY_INVOICE"]
    amount: float = Field(gt=0, le=1_000_000_000_000)
    due_date: date
    idempotency_key: str = Field(min_length=8, max_length=160)
    po_id: str | None = Field(default=None, max_length=160)
    period_start: date | None = None
    period_end: date | None = None
    notes: str = Field(default="", max_length=1000)


class TelegramSupplierReceiptLineIn(BaseModel):
    po_item_id: int = Field(gt=0)
    quantity: float = Field(gt=0, le=1_000_000)
    unit: str = Field(min_length=1, max_length=32)


class TelegramSupplierReceiptIn(BaseModel):
    lines: list[TelegramSupplierReceiptLineIn] = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=160)


def _ensure_customer(chat_id: int, name: str = "") -> dict[str, Any]:
    row = customer_repo.find_by_telegram_chat_id(chat_id)
    if not row:
        username = f"tg{abs(chat_id)}"[:32]
        row = customer_repo.create_customer(
            username=username,
            display_name=name.strip() or f"Telegram {chat_id}",
            role="customer",
        )
        customer_repo.link_telegram(str(row["customer_id"]), chat_id)
        row = customer_repo.find_by_telegram_chat_id(chat_id) or row
    elif name.strip() and str(row.get("display_name") or "") != name.strip():
        row = customer_repo.update_fields(str(row["customer_id"]), {"display_name": name.strip()})
    return row


def _supplier_for_chat(chat_id: int, token: str) -> tuple[str, dict[str, Any]]:
    _authorize(token)
    customer = customer_repo.find_by_telegram_chat_id(chat_id)
    if not customer or str(customer.get("role") or "") != "supplier":
        raise HTTPException(status_code=403, detail="Telegram chat belum tertaut ke akun supplier.")
    account = supplier_repo.get_account_for_customer(str(customer["customer_id"]))
    if not account:
        raise HTTPException(status_code=403, detail="Akun supplier belum memiliki tenant aktif.")
    return str(account["supplier_id"]), customer


@router.get("/profile/{chat_id}")
def get_profile(chat_id: int, x_dova_internal_token: str = Header(default="")) -> dict[str, Any]:
    _authorize(x_dova_internal_token)
    _ensure_customer(chat_id)
    return customer_repo.get_legacy_profile(chat_id)


@router.post("/profile")
def save_profile(payload: TelegramProfileIn, x_dova_internal_token: str = Header(default="")) -> dict[str, Any]:
    _authorize(x_dova_internal_token)
    _ensure_customer(payload.chat_id, payload.nama or "")
    fields: dict[str, Any] = {}
    if payload.nama is not None:
        fields["nama"] = payload.nama
    if payload.alergen is not None:
        fields["alergen"] = payload.alergen
    if payload.avoided_times is not None:
        fields["avoided_times"] = payload.avoided_times
    if fields:
        customer_repo.update_legacy_profile(payload.chat_id, fields)
    return customer_repo.get_legacy_profile(payload.chat_id)


@router.post("/orders")
def create_order(payload: TelegramOrderIn, x_dova_internal_token: str = Header(default="")) -> dict[str, Any]:
    _authorize(x_dova_internal_token)
    row = _ensure_customer(payload.chat_id, payload.customer_name)
    customer = customer_repo.to_public(row)
    days = [day for day in DAYS if day in set(payload.schedule_days)]
    if not days:
        raise HTTPException(status_code=422, detail="Minimal satu hari layanan wajib dipilih.")

    package_code = payload.package_code.strip()
    if not package_code:
        packages = catalog_repo.list_packages()
        package = next((item for item in packages if set(days).issubset(set(item.days))), None)
        if not package:
            raise HTTPException(status_code=422, detail="Tidak ada paket yang mencakup hari pilihan.")
        package_code = package.code

    selections = [
        DaySelectionIn(hari=day, menu_id=menu_id, quantity=1)
        for day, menu_id in payload.selections.items()
        if day in days and menu_id.strip()
    ]
    result = order_service.create_order(
        customer,
        OrderCreateIn(
            package_code=package_code,
            selected_allergen_codes=payload.selected_allergen_codes,
            customer_note=payload.customer_note,
            schedule_days=days,
            selections=selections or None,
            apply_passport=True,
        ),
    )
    return result.model_dump(mode="json")


@router.get("/orders/{chat_id}")
def list_orders(chat_id: int, x_dova_internal_token: str = Header(default="")) -> list[dict[str, Any]]:
    _authorize(x_dova_internal_token)
    row = customer_repo.find_by_telegram_chat_id(chat_id)
    if not row:
        return []
    return [item.model_dump(mode="json") for item in order_service.list_orders(customer_repo.to_public(row), limit=20)]


@router.get("/supplier/{chat_id}/pos")
def supplier_pos(chat_id: int, x_dova_internal_token: str = Header(default="")) -> list[dict[str, Any]]:
    supplier_id, _ = _supplier_for_chat(chat_id, x_dova_internal_token)
    return supabase.execute(
        """
        SELECT po.po_id, po.supplier_id, po.status, po.total_amount,
               po.need_by_date, po.notes, po.created_at,
               COALESCE(json_agg(json_build_object(
                   'id', pi.id, 'item_name', pi.item_name, 'qty', pi.qty,
                   'unit', pi.unit, 'unit_price', pi.unit_price,
                   'subtotal', pi.subtotal
               ) ORDER BY pi.id) FILTER (WHERE pi.id IS NOT NULL), '[]'::json) AS items
        FROM purchase_orders po
        LEFT JOIN po_items pi ON pi.po_id = po.po_id
        WHERE po.supplier_id = %s
          AND po.status IN ('SENT', 'ACCEPTED', 'PARTIAL', 'RECEIVED')
        GROUP BY po.po_id
        ORDER BY po.created_at DESC
        """,
        (supplier_id,),
    )


@router.post("/supplier/{chat_id}/pos/{po_id}/respond")
def supplier_respond(
    chat_id: int,
    po_id: str,
    payload: TelegramSupplierResponseIn,
    x_dova_internal_token: str = Header(default=""),
) -> dict[str, Any]:
    supplier_id, _ = _supplier_for_chat(chat_id, x_dova_internal_token)
    try:
        result = procurement_service.record_supplier_response(
            po_id,
            supplier_id,
            status=payload.status,
            notes=payload.notes,
            estimated_delivery=payload.estimated_delivery,
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"po_id": po_id, "status": result["status"]}


@router.get("/supplier/{chat_id}/pos/{po_id}")
def supplier_po_detail(chat_id: int, po_id: str, x_dova_internal_token: str = Header(default="")) -> dict[str, Any]:
    supplier_id, _ = _supplier_for_chat(chat_id, x_dova_internal_token)
    rows = supabase.execute(
        """
        SELECT po.po_id, po.supplier_id, po.status, po.total_amount,
               po.need_by_date, po.notes, po.created_at,
               COALESCE(json_agg(json_build_object(
                   'id', pi.id, 'item_name', pi.item_name, 'qty', pi.qty,
                   'unit', pi.unit, 'unit_price', pi.unit_price,
                   'subtotal', pi.subtotal
               ) ORDER BY pi.id) FILTER (WHERE pi.id IS NOT NULL), '[]'::json) AS items
        FROM purchase_orders po
        LEFT JOIN po_items pi ON pi.po_id = po.po_id
        WHERE po.po_id = %s AND po.supplier_id = %s
        GROUP BY po.po_id
        """,
        (po_id, supplier_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="PO tidak ditemukan.")
    return rows[0]


@router.post("/supplier/{chat_id}/pos/{po_id}/change-request")
def supplier_change_request(
    chat_id: int,
    po_id: str,
    payload: TelegramSupplierChangeIn,
    x_dova_internal_token: str = Header(default=""),
) -> dict[str, Any]:
    supplier_id, _ = _supplier_for_chat(chat_id, x_dova_internal_token)
    try:
        return procurement_service.record_supplier_change_request(
            po_id,
            supplier_id,
            notes=payload.notes,
            estimated_delivery=payload.estimated_delivery,
            idempotency_key=payload.idempotency_key,
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/supplier/{chat_id}/invoices")
def supplier_invoices(chat_id: int, x_dova_internal_token: str = Header(default="")) -> list[dict[str, Any]]:
    supplier_id, _ = _supplier_for_chat(chat_id, x_dova_internal_token)
    try:
        return supplier_billing_service.list_invoices(supplier_id=supplier_id)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Migration billing supplier belum diterapkan.") from exc


@router.post("/supplier/{chat_id}/invoices")
def supplier_submit_invoice(
    chat_id: int,
    payload: TelegramSupplierInvoiceIn,
    x_dova_internal_token: str = Header(default=""),
) -> dict[str, Any]:
    supplier_id, customer = _supplier_for_chat(chat_id, x_dova_internal_token)
    try:
        return supplier_billing_service.submit_invoice(
            supplier_id=supplier_id,
            actor_id=str(customer["customer_id"]),
            invoice_number=payload.invoice_number,
            payment_terms=payload.payment_terms,
            amount=payload.amount,
            due_date=payload.due_date,
            idempotency_key=payload.idempotency_key,
            po_id=payload.po_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            notes=payload.notes,
        )
    except (
        supplier_billing_service.ConflictError,
        supplier_billing_service.DatabaseError,
        supplier_billing_service.NotFoundError,
        supplier_billing_service.ValidationError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/supplier/{chat_id}/pos/{po_id}/receive")
def supplier_receive(
    chat_id: int,
    po_id: str,
    payload: TelegramSupplierReceiptIn,
    x_dova_internal_token: str = Header(default=""),
) -> dict[str, Any]:
    supplier_id, customer = _supplier_for_chat(chat_id, x_dova_internal_token)
    try:
        return procurement_service.receive_purchase_order(
            po_id,
            supplier_id,
            lines=[line.model_dump() for line in payload.lines],
            idempotency_key=payload.idempotency_key,
            actor_id=str(customer["customer_id"]),
            notes=payload.notes,
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

