"""Invoice service — lifecycle order: Created → Invoice → Payment → Kitchen (spec §13).

Untuk tahap awal invoice berupa halaman web yang bisa dicetak; tidak ada
payment gateway. `discount` selalu 0 kecuali diisi manual oleh admin.
"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.core.domain import AVOIDED_TIME_OPTIONS
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.schemas.order import InvoiceLineOut, InvoiceOut
from app.services import safety_service
from app.utils.time import now_iso, now_wib

log = get_logger("dova.invoice")


def generate_invoice_number(order_id: str, created_at: str = "") -> str:
    """
    Nomor invoice stabil & diturunkan dari order id.

    Format: `INV-<tahun><bulan>-<suffix order>`. Suffix diambil dari karakter
    alfanumerik terakhir order id agar nomor tidak berubah-ubah.
    """
    stamp = now_wib().strftime("%Y%m")
    suffix = "".join(ch for ch in order_id if ch.isalnum())[-6:].upper() or uuid.uuid4().hex[:6].upper()
    return f"INV-{stamp}-{suffix}"


def build_invoice(order: dict, safety_summary: str = "") -> InvoiceOut:
    """
    Susun invoice dari order yang sudah dinormalisasi repository.

    Harga diambil dari katalog paket — bukan dari input klien.
    """
    package_name = order.get("subscription_type") or "Paket Katering"
    price = _package_price(order)

    if price is None:
        lines = [
            InvoiceLineOut(
                label=f"{package_name} · {order.get('meal_count', 0)} meal",
                quantity=order.get("meal_count", 0),
                unit_price=0,
                amount=0,
            )
        ]
        subtotal = 0
    else:
        lines = [
            InvoiceLineOut(
                label=f"{package_name} · {order.get('meal_count', 0)} meal",
                quantity=1,
                unit_price=price,
                amount=price,
            )
        ]
        subtotal = price

    discount = int(order.get("discount") or 0)
    total = int(order.get("total") or 0) or max(0, subtotal - discount)

    days = order.get("schedule_days") or []
    avoided = order.get("avoided_times") or []
    safety_items = [
        f"Hari layanan: {', '.join(days)}" if days else "",
        f"Batasan aktif: {', '.join(safety_service.critical_labels(order.get('selected_allergens') or [])) or 'Tidak ada'}",
        f"Waktu dihindari: {', '.join(AVOIDED_TIME_OPTIONS.get(a, a) for a in avoided) or 'Tidak ada'}",
        safety_summary or order.get("kitchen_notes", ""),
    ]
    safety_items = [s for s in safety_items if s]

    return InvoiceOut(
        invoice_number=order.get("invoice_number") or generate_invoice_number(order["order_id"]),
        order_id=order["order_id"],
        issued_at=order.get("created_at") or now_iso(),
        currency=settings.default_currency,
        customer_name=order.get("customer_name") or "—",
        customer_contact=str(order.get("customer_contact") or order.get("delivery_address") or ""),
        package_name=package_name,
        schedule_days=days,
        meal_count=int(order.get("meal_count") or len(days)),
        dietary_safety_summary=safety_summary or "Tidak ada batasan yang tercatat.",
        dietary_safety_items=safety_items,
        lines=lines,
        subtotal=subtotal,
        discount=discount,
        total=total,
        payment_status=str(order.get("payment_status") or "UNPAID").upper(),  # type: ignore[arg-type]
        payment_reference=str(order.get("payment_reference") or ""),
    )


def _package_price(order: dict) -> int | None:
    """
    Harga paket dari katalog.

    Falls back ke pencocokan nama paket bila `package_code` belum tercatat pada
    order lama (semua order live dibuat sebelum Phase 2).
    """
    from app.repositories.catalog_repo import list_packages

    code = order.get("package_code") or ""
    label = (order.get("subscription_type") or "").strip()

    try:
        packages = list_packages(include_inactive=True)
    except Exception as exc:
        log.warning("Harga paket tidak dapat dimuat: %s", type(exc).__name__)
        return None

    if code:
        for pkg in packages:
            if pkg.code == code:
                return pkg.price
    if label:
        for pkg in packages:
            if pkg.name.strip() == label:
                return pkg.price
        for pkg in packages:
            if pkg.name.strip().lower() == label.lower():
                return pkg.price
    return None


def ensure_invoice_persisted(order_doc_id: str, order: dict) -> dict:
    """
    Tulis blok invoice ke dokumen order bila belum ada.

    Dipanggil saat order dibuat supaya `/orders/:id/invoice` langsung bisa dibuka
    tanpa menghitung ulang.
    """
    from app.repositories.order_repo import update_fields

    existing = order.get("invoice_number")
    if existing:
        return order

    invoice = build_invoice(order)
    update_fields(
        order_doc_id,
        {
            "invoice_number": invoice.invoice_number,
            "subtotal": invoice.subtotal,
            "discount": invoice.discount,
            "total": invoice.total,
            "payment_status": invoice.payment_status,
        },
    )
    log.info("invoice_generated order=%s invoice=%s total=%d",
             order["order_id"], invoice.invoice_number, invoice.total)
    return {**order, **invoice.model_dump()}


def set_payment_status(order_doc_id: str, status: str, reference: str = "") -> dict:
    """Diubah admin. Tidak ada payment gateway pada MVP."""
    from app.models.enums import PaymentStatus

    if status not in {s.value for s in PaymentStatus}:
        raise ValidationError(f"Status pembayaran tidak dikenal: {status}")
    from app.repositories.order_repo import update_fields

    log.info("payment_status_updated order_doc=%s status=%s", order_doc_id, status)
    return update_fields(
        order_doc_id, {"payment_status": status, "payment_reference": reference}
    )
