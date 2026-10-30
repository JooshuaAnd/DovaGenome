"""Supplier invoice and payable workflow on the Supabase ledger.

An invoice is submitted first, matched against posted goods receipts, and only
then can an admin approve it. Payment records are manual/auditable; the QR
method is explicitly illustrative until a real gateway is configured.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Callable, TypeVar

from app.core.errors import ConflictError, DatabaseError, NotFoundError, ValidationError
from app.repositories import supabase as db


_T = TypeVar("_T")
_TERMS = {"PAY_ON_DELIVERY", "WEEKLY_INVOICE"}
_PAYMENT_METHODS = {"MANUAL", "QR_ILLUSTRATIVE"}


class SupplierBillingUnavailable(RuntimeError):
    """The supplier billing workflow cannot safely proceed."""


def _transaction(callback: Callable[[Any], _T]) -> _T:
    with db.get_conn() as conn:
        with conn.cursor() as cursor:
            return callback(cursor)


def _number(value: Any, field: str, *, minimum: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} tidak valid.") from exc
    if not math.isfinite(number) or number < minimum:
        raise ValidationError(f"{field} tidak valid.")
    return round(number, 2)


def _date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} harus tanggal ISO.") from exc


def _check_migration() -> None:
    if not db.check_supplier_billing_migrations():
        raise DatabaseError("Migration supplier billing belum diterapkan di Supabase.")


def _invoice_out(row: dict[str, Any], *, po_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "supplier_invoice_id": str(row["supplier_invoice_id"]),
        "supplier_id": str(row["supplier_id"]),
        "supplier_name": str(row.get("supplier_name") or ""),
        "invoice_number": str(row["invoice_number"]),
        "payment_terms": str(row["payment_terms"]),
        "period_start": row.get("period_start").isoformat() if row.get("period_start") else None,
        "period_end": row.get("period_end").isoformat() if row.get("period_end") else None,
        "due_date": row["due_date"].isoformat() if hasattr(row.get("due_date"), "isoformat") else str(row.get("due_date") or ""),
        "amount": float(row["amount"]),
        "expected_amount": float(row["expected_amount"]),
        "currency": str(row.get("currency") or "IDR"),
        "match_status": str(row["match_status"]),
        "status": str(row["status"]),
        "invoice_idempotent": bool(row.get("invoice_idempotent", False)),
        "notes": str(row.get("notes") or ""),
        "created_at": row["created_at"].isoformat() if hasattr(row.get("created_at"), "isoformat") else str(row.get("created_at") or ""),
        "po_ids": po_ids or [],
    }


def submit_invoice(
    *,
    supplier_id: str,
    actor_id: str,
    invoice_number: str,
    payment_terms: str,
    amount: float,
    due_date: date,
    idempotency_key: str,
    po_id: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    notes: str = "",
) -> dict[str, Any]:
    _check_migration()
    clean_number = str(invoice_number or "").strip()
    clean_terms = str(payment_terms or "").strip().upper()
    clean_key = str(idempotency_key or "").strip()
    if not clean_number or len(clean_number) > 100:
        raise ValidationError("Nomor invoice supplier wajib diisi.")
    if clean_terms not in _TERMS:
        raise ValidationError("Termin supplier harus PAY_ON_DELIVERY atau WEEKLY_INVOICE.")
    if not clean_key or len(clean_key) > 160:
        raise ValidationError("Idempotency-Key invoice wajib diisi.")
    amount_number = _number(amount, "amount", minimum=0.01)
    clean_due_date = _date(due_date, "due_date")
    if len(str(notes or "")) > 1000:
        raise ValidationError("Catatan invoice terlalu panjang.")
    if clean_terms == "PAY_ON_DELIVERY" and not str(po_id or "").strip():
        raise ValidationError("PAY_ON_DELIVERY wajib memiliki PO reference.")
    if clean_terms == "WEEKLY_INVOICE":
        if not period_start or not period_end:
            raise ValidationError("WEEKLY_INVOICE wajib memiliki periode awal dan akhir.")
        if period_end < period_start:
            raise ValidationError("Periode invoice tidak valid.")

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            SELECT si.*, s.name AS supplier_name
            FROM supplier_invoices si
            JOIN suppliers s ON s.supplier_id = si.supplier_id
            WHERE si.idempotency_key = %s
            FOR UPDATE
            """,
            (clean_key,),
        )
        existing = cursor.fetchone()
        if existing:
            if str(existing["supplier_id"]) != supplier_id:
                raise ConflictError("Idempotency-Key invoice sudah dipakai supplier lain.")
            cursor.execute(
                "SELECT po_id FROM supplier_invoice_pos WHERE supplier_invoice_id = %s ORDER BY po_id",
                (existing["supplier_invoice_id"],),
            )
            result = _invoice_out(existing, po_ids=[str(row["po_id"]) for row in cursor.fetchall()])
            result["invoice_idempotent"] = True
            return result

        cursor.execute(
            """
            SELECT supplier_invoice_id
            FROM supplier_invoices
            WHERE supplier_id = %s AND invoice_number = %s
            """,
            (supplier_id, clean_number),
        )
        if cursor.fetchone():
            raise ConflictError("Nomor invoice supplier sudah pernah diajukan.")

        po_rows: list[dict[str, Any]]
        if clean_terms == "PAY_ON_DELIVERY":
            cursor.execute(
                """
                SELECT po_id, status
                FROM purchase_orders
                WHERE po_id = %s AND supplier_id = %s
                FOR UPDATE
                """,
                (str(po_id).strip(), supplier_id),
            )
            po = cursor.fetchone()
            if not po:
                raise NotFoundError("PO invoice tidak ditemukan.")
            if po["status"] != "RECEIVED":
                raise ConflictError("PAY_ON_DELIVERY hanya boleh untuk PO yang sudah RECEIVED.")
            cursor.execute(
                """
                SELECT COALESCE(SUM(gri.quantity * gri.unit_price), 0) AS expected_amount
                FROM goods_receipt_items gri
                JOIN goods_receipts gr ON gr.receipt_id = gri.receipt_id AND gr.status = 'POSTED'
                WHERE gr.po_id = %s
                """,
                (str(po_id).strip(),),
            )
            po_rows = [{"po_id": str(po_id).strip(), "expected_amount": float(cursor.fetchone()["expected_amount"] or 0)}]
        else:
            cursor.execute(
                """
                SELECT po.po_id, COALESCE(SUM(gri.quantity * gri.unit_price), 0) AS expected_amount
                FROM purchase_orders po
                JOIN goods_receipts gr ON gr.po_id = po.po_id AND gr.status = 'POSTED'
                JOIN goods_receipt_items gri ON gri.receipt_id = gr.receipt_id
                WHERE po.supplier_id = %s
                  AND po.status = 'RECEIVED'
                  AND gr.received_at >= %s
                  AND gr.received_at < (%s::date + INTERVAL '1 day')
                  AND NOT EXISTS (
                      SELECT 1 FROM supplier_invoice_pos sip WHERE sip.po_id = po.po_id
                  )
                GROUP BY po.po_id
                ORDER BY po.po_id
                """,
                (supplier_id, period_start, period_end),
            )
            po_rows = [dict(row) for row in cursor.fetchall()]
            if not po_rows:
                raise ConflictError("Tidak ada PO RECEIVED yang belum ditagihkan pada periode ini.")

        expected = round(sum(float(row["expected_amount"]) for row in po_rows), 2)
        match_status = "MATCHED" if abs(amount_number - expected) <= 0.01 else "REQUIRES_REVIEW"
        cursor.execute(
            """
            INSERT INTO supplier_invoices
                (supplier_id, invoice_number, payment_terms, period_start, period_end,
                 due_date, amount, expected_amount, match_status, idempotency_key,
                 notes, submitted_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (supplier_id, clean_number, clean_terms, period_start, period_end,
             clean_due_date, amount_number, expected, match_status, clean_key,
             str(notes or "").strip(), actor_id),
        )
        invoice = cursor.fetchone()
        cursor.executemany(
            """
            INSERT INTO supplier_invoice_pos (supplier_invoice_id, po_id, expected_amount)
            VALUES (%s, %s, %s)
            """,
            [(invoice["supplier_invoice_id"], row["po_id"], row["expected_amount"]) for row in po_rows],
        )
        result = _invoice_out(invoice, po_ids=[str(row["po_id"]) for row in po_rows])
        result["invoice_idempotent"] = False
        return result

    return _transaction(operation)


def list_invoices(*, supplier_id: str | None = None) -> list[dict[str, Any]]:
    _check_migration()
    where = "WHERE si.supplier_id = %s" if supplier_id else ""
    params = (supplier_id,) if supplier_id else None
    rows = db.execute(
        f"""
        SELECT si.*, s.name AS supplier_name,
               COALESCE(array_agg(sip.po_id) FILTER (WHERE sip.po_id IS NOT NULL), ARRAY[]::TEXT[]) AS po_ids
        FROM supplier_invoices si
        JOIN suppliers s ON s.supplier_id = si.supplier_id
        LEFT JOIN supplier_invoice_pos sip ON sip.supplier_invoice_id = si.supplier_invoice_id
        {where}
        GROUP BY si.supplier_invoice_id, s.name
        ORDER BY si.created_at DESC
        """,
        params,
    )
    return [_invoice_out(row, po_ids=[str(po_id) for po_id in (row.get("po_ids") or [])]) for row in rows]


def verify_invoice(*, invoice_id: str, actor_id: str, decision: str, notes: str = "") -> dict[str, Any]:
    _check_migration()
    normalized = str(decision or "").strip().upper()
    if normalized not in {"APPROVE", "REJECT"}:
        raise ValidationError("Keputusan invoice harus APPROVE atau REJECT.")
    if normalized == "APPROVE" and not notes.strip():
        # A note is required for both matched and mismatched review so the
        # operator's decision is auditable rather than an invisible click.
        raise ValidationError("Catatan verifikasi invoice wajib diisi.")

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            SELECT spr.*, si.status AS invoice_status, si.amount AS invoice_amount
            FROM supplier_payment_records spr
            JOIN supplier_invoices si ON si.supplier_invoice_id = spr.supplier_invoice_id
            WHERE spr.idempotency_key = %s
            FOR UPDATE
            """,
            (clean_key,),
        )
        existing_payment = cursor.fetchone()
        if existing_payment:
            if str(existing_payment["supplier_invoice_id"]) != invoice_id:
                raise ConflictError("Idempotency-Key pembayaran sudah dipakai invoice lain.")
            cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) AS paid FROM supplier_payment_records WHERE supplier_invoice_id = %s",
                (invoice_id,),
            )
            total_paid = float(cursor.fetchone()["paid"] or 0)
            return {
                "supplier_payment_id": str(existing_payment["supplier_payment_id"]),
                "supplier_invoice_id": invoice_id,
                "amount": float(existing_payment["amount"]),
                "total_paid": total_paid,
                "outstanding": round(max(0, float(existing_payment["invoice_amount"]) - total_paid), 2),
                "invoice_status": str(existing_payment["invoice_status"]),
                "payment_method": str(existing_payment["payment_method"]),
                "live_gateway": False,
                "paid_at": existing_payment["paid_at"].isoformat() if hasattr(existing_payment["paid_at"], "isoformat") else str(existing_payment["paid_at"]),
                "idempotent": True,
            }
        cursor.execute(
            "SELECT * FROM supplier_invoices WHERE supplier_invoice_id = %s FOR UPDATE",
            (invoice_id,),
        )
        invoice = cursor.fetchone()
        if not invoice:
            raise NotFoundError("Invoice supplier tidak ditemukan.")
        if invoice["status"] != "SUBMITTED":
            raise ConflictError(f"Invoice sudah berstatus {invoice['status']}.")
        status = "APPROVED" if normalized == "APPROVE" else "REJECTED"
        cursor.execute(
            """
            UPDATE supplier_invoices
            SET status = %s, verified_by = %s, verified_at = NOW(),
                notes = CASE WHEN %s <> '' THEN notes || ' | Verifikasi: ' || %s ELSE notes END,
                updated_at = NOW()
            WHERE supplier_invoice_id = %s
            RETURNING *
            """,
            (status, actor_id, notes.strip(), notes.strip(), invoice_id),
        )
        updated = cursor.fetchone()
        return _invoice_out(updated)

    return _transaction(operation)


def record_payment(
    *,
    invoice_id: str,
    actor_id: str,
    amount: float,
    payment_method: str,
    payment_reference: str,
    idempotency_key: str,
    notes: str = "",
) -> dict[str, Any]:
    _check_migration()
    method = str(payment_method or "").strip().upper()
    if method not in _PAYMENT_METHODS:
        raise ValidationError("Metode pembayaran hanya MANUAL atau QR_ILLUSTRATIVE.")
    clean_key = str(idempotency_key or "").strip()
    if not clean_key:
        raise ValidationError("Idempotency-Key pembayaran wajib diisi.")
    paid_amount = _number(amount, "amount", minimum=0.01)

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            "SELECT * FROM supplier_invoices WHERE supplier_invoice_id = %s FOR UPDATE",
            (invoice_id,),
        )
        invoice = cursor.fetchone()
        if not invoice:
            raise NotFoundError("Invoice supplier tidak ditemukan.")
        if invoice["status"] not in {"APPROVED", "PARTIALLY_PAID"}:
            raise ConflictError("Invoice harus diverifikasi admin sebelum dibayar.")
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) AS paid FROM supplier_payment_records WHERE supplier_invoice_id = %s",
            (invoice_id,),
        )
        paid_before = float(cursor.fetchone()["paid"] or 0)
        outstanding = round(float(invoice["amount"]) - paid_before, 2)
        if paid_amount > outstanding + 0.01:
            raise ConflictError(f"Pembayaran melebihi sisa tagihan {outstanding:g}.")
        cursor.execute(
            """
            INSERT INTO supplier_payment_records
                (supplier_invoice_id, amount, payment_method, payment_reference,
                 idempotency_key, recorded_by, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING supplier_payment_id, paid_at
            """,
            (invoice_id, paid_amount, method, str(payment_reference or "").strip(), clean_key, actor_id, str(notes or "").strip()),
        )
        payment = cursor.fetchone()
        total_paid = round(paid_before + paid_amount, 2)
        next_status = "PAID" if total_paid >= float(invoice["amount"]) - 0.01 else "PARTIALLY_PAID"
        cursor.execute(
            "UPDATE supplier_invoices SET status = %s, updated_at = NOW() WHERE supplier_invoice_id = %s",
            (next_status, invoice_id),
        )
        return {
            "supplier_payment_id": str(payment["supplier_payment_id"]),
            "supplier_invoice_id": invoice_id,
            "amount": paid_amount,
            "total_paid": total_paid,
            "outstanding": round(max(0, float(invoice["amount"]) - total_paid), 2),
            "invoice_status": next_status,
            "payment_method": method,
            "live_gateway": False,
            "paid_at": payment["paid_at"].isoformat() if hasattr(payment["paid_at"], "isoformat") else str(payment["paid_at"]),
            "idempotent": False,
        }

    return _transaction(operation)

