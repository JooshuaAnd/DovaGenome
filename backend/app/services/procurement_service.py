"""Auditable supplier PO workflow.

The service consumes only a live, operational supplier-sourcing report. It
persists a draft, requires an explicit admin approval, then queues an outbox
notification. Queueing is not delivery: the provider worker is still a
separate open gate.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from typing import Any, Callable, TypeVar

from app.core.config import settings
from app.repositories import supabase as db


CALCULATION_VERSION = "procurement_workflow_v1"
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_T = TypeVar("_T")


class ProcurementUnavailable(RuntimeError):
    """The PO workflow cannot safely proceed from the supplied evidence."""


class ProcurementNotFound(ProcurementUnavailable):
    """A PO is not visible to the authenticated actor."""


def _finite(value: Any, *, field: str, minimum: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ProcurementUnavailable(f"{field} tidak valid.") from exc
    if not math.isfinite(number) or number < minimum:
        raise ProcurementUnavailable(f"{field} tidak valid.")
    return number


def _transaction(callback: Callable[[Any], _T]) -> _T:
    """Run all writes for one workflow transition in one DB transaction."""
    with db.get_conn() as conn:
        with conn.cursor() as cursor:
            return callback(cursor)


def _audit(cursor: Any, *, actor_id: str, action: str, record_id: str, after: dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO audit_log (actor_id, action, table_name, record_id, before_val, after_val, source)
        VALUES (%s, %s, 'purchase_orders', %s, NULL, %s::jsonb, 'procurement_service')
        """,
        (actor_id, action, record_id, json.dumps(after, default=str)),
    )


def build_purchase_order_drafts(sourcing_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a strict sourcing report into deterministic supplier PO drafts."""
    if not isinstance(sourcing_report, dict):
        raise ProcurementUnavailable("Report sourcing harus berupa object.")
    if sourcing_report.get("status") != "OK":
        raise ProcurementUnavailable("Sourcing belum berstatus OK; draft PO ditahan.")
    if sourcing_report.get("data_mode") != "live":
        raise ProcurementUnavailable("Draft PO hanya boleh dibuat dari data live.")
    if sourcing_report.get("source") != "supabase_postgres":
        raise ProcurementUnavailable("Sumber draft PO harus supabase_postgres.")

    grouped: dict[str, dict[str, Any]] = {}
    items = sourcing_report.get("items")
    if not isinstance(items, list) or not items:
        raise ProcurementUnavailable("Sourcing OK tetapi tidak memiliki item shortage.")

    for item in items:
        if not isinstance(item, dict):
            raise ProcurementUnavailable("Item sourcing tidak valid.")
        ingredient_id = str(item.get("ingredient_id") or "").strip()
        ingredient_name = str(item.get("ingredient_name") or "").strip()
        unit = str(item.get("unit") or "").strip()
        shortage = _finite(item.get("shortage_quantity"), field="shortage_quantity")
        supplier = item.get("recommended_supplier")
        if not ingredient_id or not ingredient_name or not unit or not isinstance(supplier, dict):
            raise ProcurementUnavailable("Item sourcing tidak memiliki identitas lengkap.")

        supplier_id = str(supplier.get("supplier_id") or "").strip()
        supplier_name = str(supplier.get("supplier_name") or "").strip()
        supplier_unit = str(supplier.get("unit") or "").strip()
        price = _finite(supplier.get("price_per_unit"), field="price_per_unit")
        lead_time = _finite(supplier.get("lead_time_days"), field="lead_time_days")
        rating = _finite(supplier.get("rating"), field="rating")
        if not supplier_id or not supplier_name or supplier_unit != unit:
            raise ProcurementUnavailable("Supplier atau unit supplier tidak cocok dengan shortage.")
        if rating > 5 or not float(price).is_integer():
            raise ProcurementUnavailable("Harga atau rating supplier tidak memenuhi kontrak PO.")

        raw_moq = supplier.get("moq")
        moq = _finite(raw_moq, field="moq") if raw_moq is not None else 0.0
        if moq and not float(moq).is_integer():
            raise ProcurementUnavailable("MOQ supplier harus bilangan bulat.")
        quantity = max(shortage, moq) if moq > 0 else shortage
        if moq > 0:
            quantity = math.ceil(quantity / moq) * moq
        quantity = round(quantity, 4)
        total = int(round(quantity * price))

        bucket = grouped.setdefault(
            supplier_id,
            {
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "need_by_date": item.get("need_by_date") or sourcing_report.get("need_by_date"),
                "total_amount": 0,
                "items": [],
                "source": "supabase_postgres",
                "calculation_version": CALCULATION_VERSION,
            },
        )
        if bucket["need_by_date"] and bucket["need_by_date"] != (item.get("need_by_date") or sourcing_report.get("need_by_date")):
            raise ProcurementUnavailable("Tanggal kebutuhan PO tidak konsisten.")
        bucket["items"].append(
            {
                "ingredient_id": ingredient_id,
                "item_name": ingredient_name,
                "qty": quantity,
                "unit": unit,
                "unit_price": int(price),
                "subtotal": total,
                "lead_time_days": lead_time,
            }
        )
        bucket["total_amount"] += total

    return sorted(grouped.values(), key=lambda row: row["supplier_id"])


def _validate_key(idempotency_key: str) -> str:
    key = str(idempotency_key or "").strip()
    if not _KEY_RE.fullmatch(key):
        raise ProcurementUnavailable("Idempotency-Key wajib 1–128 karakter alfanumerik atau . _ : -.")
    return key


def create_draft_purchase_orders(
    sourcing_report: dict[str, Any],
    *,
    idempotency_key: str,
    actor_id: str,
) -> dict[str, Any]:
    """Persist one or more draft POs atomically and idempotently."""
    key = _validate_key(idempotency_key)
    drafts = build_purchase_order_drafts(sourcing_report)
    keys = {f"{key}:{draft['supplier_id']}" for draft in drafts}

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            SELECT po_id, supplier_id, status, total_amount, idempotency_key
            FROM purchase_orders
            WHERE idempotency_key = ANY(%s)
            ORDER BY po_id
            """,
            (list(keys),),
        )
        existing = cursor.fetchall()
        if existing:
            if {row["idempotency_key"] for row in existing} != keys:
                raise ProcurementUnavailable("Idempotency-Key sudah dipakai untuk batch PO yang berbeda.")
            return {"status": "EXISTING", "purchase_orders": [dict(row) for row in existing]}

        created: list[dict[str, Any]] = []
        for draft in drafts:
            po_key = f"{key}:{draft['supplier_id']}"
            cursor.execute(
                """
                INSERT INTO purchase_orders
                    (supplier_id, status, total_amount, need_by_date, notes,
                     idempotency_key, created_by, source, calculation_version)
                VALUES (%s, 'DRAFT', %s, %s, %s, %s, %s, %s, %s)
                RETURNING po_id, supplier_id, status, total_amount, need_by_date,
                          idempotency_key, source, calculation_version
                """,
                (
                    draft["supplier_id"],
                    draft["total_amount"],
                    draft["need_by_date"],
                    "Dibuat dari live supplier sourcing; menunggu approval admin.",
                    po_key,
                    actor_id,
                    draft["source"],
                    draft["calculation_version"],
                ),
            )
            po = dict(cursor.fetchone())
            for item in draft["items"]:
                if db.check_procurement_receipt_migrations():
                    cursor.execute(
                        """
                        INSERT INTO po_items
                            (po_id, ingredient_id, item_name, qty, unit, unit_price, subtotal)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            po["po_id"], item["ingredient_id"], item["item_name"], item["qty"], item["unit"],
                            item["unit_price"], item["subtotal"],
                        ),
                    )
                else:
                    # Keep draft/approval usable while the optional receiving
                    # migration is waiting for the backup gate.
                    cursor.execute(
                        """
                        INSERT INTO po_items (po_id, item_name, qty, unit, unit_price, subtotal)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            po["po_id"], item["item_name"], item["qty"], item["unit"],
                            item["unit_price"], item["subtotal"],
                        ),
                    )
            _audit(cursor, actor_id=actor_id, action="PO_DRAFT_CREATED", record_id=po["po_id"], after=po)
            po["items"] = draft["items"]
            created.append(po)
        return {"status": "CREATED", "purchase_orders": created}

    return _transaction(operation)


def _quantity_in_unit(quantity: float, from_unit: str, to_unit: str) -> float:
    """Convert only identical units or explicit g/kg mass units."""
    source = from_unit.strip().lower()
    target = to_unit.strip().lower()
    if source == target:
        return round(quantity, 4)
    factors = {"g": 1.0, "gram": 1.0, "grams": 1.0, "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0}
    if source not in factors or target not in factors:
        raise ProcurementUnavailable(
            f"Unit penerimaan {from_unit} tidak cocok dengan kartu stok {to_unit}."
        )
    return round(quantity * factors[source] / factors[target], 4)


def receive_purchase_order(
    po_id: str,
    supplier_id: str,
    *,
    lines: list[dict[str, Any]],
    idempotency_key: str,
    actor_id: str,
    notes: str = "",
) -> dict[str, Any]:
    """Post a supplier goods receipt and stock movements atomically."""
    if not db.check_procurement_receipt_migrations():
        raise ProcurementUnavailable(
            "Migration goods receipt belum diterapkan di Supabase; penerimaan ditahan."
        )
    key = _validate_key(idempotency_key)
    if not lines:
        raise ProcurementUnavailable("Goods receipt harus memiliki minimal satu item.")
    if len(str(notes or "")) > 500:
        raise ProcurementUnavailable("Catatan penerimaan terlalu panjang.")

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            SELECT receipt_id, po_id, supplier_id, status, notes, received_at
            FROM goods_receipts
            WHERE idempotency_key = %s
            FOR UPDATE
            """,
            (key,),
        )
        existing = cursor.fetchone()
        if existing:
            if str(existing["po_id"]) != po_id or str(existing["supplier_id"]) != supplier_id:
                raise ProcurementUnavailable("Idempotency-Key sudah dipakai untuk PO atau supplier lain.")
            cursor.execute(
                """
                SELECT gri.receipt_item_id, gri.po_item_id, gri.ingredient_id,
                       gri.quantity, gri.unit, pi.item_name
                FROM goods_receipt_items gri
                JOIN po_items pi ON pi.id = gri.po_item_id
                WHERE gri.receipt_id = %s
                ORDER BY gri.receipt_item_id
                """,
                (existing["receipt_id"],),
            )
            return {
                "status": "EXISTING",
                "receipt_id": str(existing["receipt_id"]),
                "po_id": po_id,
                "po_status": "RECEIVED" if str(existing["status"]) == "POSTED" else str(existing["status"]),
                "received_at": existing["received_at"],
                "notes": str(existing.get("notes") or ""),
                "items": [dict(row) for row in cursor.fetchall()],
            }

        cursor.execute(
            """
            SELECT po_id, supplier_id, status
            FROM purchase_orders
            WHERE po_id = %s AND supplier_id = %s
            FOR UPDATE
            """,
            (po_id, supplier_id),
        )
        po = cursor.fetchone()
        if not po:
            raise ProcurementNotFound("PO tidak ditemukan.")
        if po["status"] not in {"ACCEPTED", "PARTIAL"}:
            raise ProcurementUnavailable(
                f"PO berstatus {po['status']} belum siap diterima; supplier harus menerima PO lebih dulu."
            )

        cursor.execute(
            """
            SELECT pi.id, pi.ingredient_id, pi.item_name, pi.qty, pi.unit,
                   pi.unit_price, pi.received_qty,
                   COALESCE(i.ingredient_id, by_name.ingredient_id) AS canonical_ingredient_id
            FROM po_items pi
            LEFT JOIN ingredients i ON i.ingredient_id = pi.ingredient_id
            LEFT JOIN ingredients by_name
              ON by_name.normalized_name = LOWER(REGEXP_REPLACE(TRIM(pi.item_name), '\\s+', ' ', 'g'))
            WHERE pi.po_id = %s
            FOR UPDATE
            """,
            (po_id,),
        )
        po_items = {int(row["id"]): row for row in cursor.fetchall()}
        if not po_items:
            raise ProcurementUnavailable("PO tidak memiliki item.")

        clean_lines: list[dict[str, Any]] = []
        seen: set[int] = set()
        for raw in sorted(lines, key=lambda item: int(item.get("po_item_id") or 0)):
            try:
                item_id = int(raw.get("po_item_id"))
                quantity = float(raw.get("quantity"))
            except (TypeError, ValueError) as exc:
                raise ProcurementUnavailable("Item penerimaan tidak valid.") from exc
            unit = str(raw.get("unit") or "").strip()
            if item_id in seen or item_id not in po_items:
                raise ProcurementUnavailable("PO item penerimaan tidak valid atau duplikat.")
            if not math.isfinite(quantity) or quantity <= 0 or not unit:
                raise ProcurementUnavailable("Quantity dan unit penerimaan wajib valid.")
            seen.add(item_id)
            item = po_items[item_id]
            ordered = float(item["qty"])
            received = float(item.get("received_qty") or 0)
            received_in_po_unit = _quantity_in_unit(quantity, unit, str(item["unit"]))
            remaining = round(ordered - received, 4)
            if received_in_po_unit > remaining + 0.0001:
                raise ProcurementUnavailable(
                    f"Penerimaan {item['item_name']} melebihi sisa PO ({remaining:g} {item['unit']})."
                )
            ingredient_id = str(item.get("ingredient_id") or item.get("canonical_ingredient_id") or "").strip()
            if not ingredient_id:
                raise ProcurementUnavailable(
                    f"Bahan {item['item_name']} belum memiliki ingredient_id canonical; PO ditahan."
                )
            clean_lines.append({
                "po_item_id": item_id,
                "ingredient_id": ingredient_id,
                "item_name": str(item["item_name"]),
                "quantity": received_in_po_unit,
                "unit": str(item["unit"]),
                "unit_price": float(item.get("unit_price") or 0),
            })

        cursor.execute(
            """
            INSERT INTO goods_receipts (po_id, supplier_id, received_by, idempotency_key, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING receipt_id, received_at
            """,
            (po_id, supplier_id, actor_id, key, str(notes or "").strip()),
        )
        receipt = cursor.fetchone()
        posted_items: list[dict[str, Any]] = []
        lot_ready = db.check_production_batch_migrations()
        for line in clean_lines:
            cursor.execute(
                """
                SELECT ingredient_id, ingredient_name, current_stock, min_stock, unit
                FROM inventory_stocks
                WHERE ingredient_id = %s
                FOR UPDATE
                """,
                (line["ingredient_id"],),
            )
            stock = cursor.fetchone()
            if not stock:
                cursor.execute(
                    """
                    SELECT ingredient_id, ingredient_name, current_stock, min_stock, unit
                    FROM inventory_stocks
                    WHERE LOWER(TRIM(ingredient_name)) = LOWER(TRIM(%s))
                    FOR UPDATE
                    """,
                    (line["item_name"],),
                )
                stock = cursor.fetchone()
            if not stock:
                cursor.execute(
                    """
                    INSERT INTO inventory_stocks
                        (ingredient_id, ingredient_name, current_stock, min_stock, unit, status)
                    VALUES (%s, %s, %s, 0, %s, 'AMBIL_AMAN')
                    RETURNING ingredient_id, ingredient_name, current_stock, min_stock, unit
                    """,
                    (line["ingredient_id"], line["item_name"], line["quantity"], line["unit"]),
                )
                stock = cursor.fetchone()
            stock_unit = str(stock["unit"] or "").strip()
            quantity_in_stock_unit = _quantity_in_unit(line["quantity"], line["unit"], stock_unit)
            current = float(stock["current_stock"] or 0)
            minimum = float(stock["min_stock"] or 0)
            new_stock = round(current + quantity_in_stock_unit, 4)
            status = "HABIS" if new_stock <= 0 else "MENIPIS" if new_stock <= minimum else "AMBIL_AMAN"
            cursor.execute(
                """
                UPDATE inventory_stocks
                SET ingredient_id = %s, current_stock = %s, status = %s, updated_at = NOW()
                WHERE ingredient_id = %s OR LOWER(TRIM(ingredient_name)) = LOWER(TRIM(%s))
                """,
                (line["ingredient_id"], new_stock, status, stock.get("ingredient_id"), line["item_name"]),
            )
            lot_id = None
            barcode_value = ""
            if lot_ready:
                cursor.execute(
                    """
                    INSERT INTO stock_lots
                        (ingredient_id, supplier_id, lot_code, barcode_value,
                         received_at, location, quantity_on_hand, unit, cost_per_unit)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE, 'main-kitchen', %s, %s, %s)
                    RETURNING lot_id, barcode_value
                    """,
                    (
                        line["ingredient_id"], supplier_id,
                        f"GR-{str(receipt['receipt_id'])[:8]}-{line['po_item_id']}",
                        f"LOT-{str(receipt['receipt_id']).replace('-', '')[:12]}-{line['po_item_id']}",
                        quantity_in_stock_unit, stock_unit, line["unit_price"],
                    ),
                )
                lot = cursor.fetchone()
                lot_id = lot["lot_id"]
                barcode_value = str(lot["barcode_value"])
            if lot_ready:
                cursor.execute(
                    """
                    INSERT INTO goods_receipt_items
                        (receipt_id, po_item_id, ingredient_id, stock_lot_id, quantity, unit, unit_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (receipt["receipt_id"], line["po_item_id"], line["ingredient_id"], lot_id,
                     line["quantity"], line["unit"], line["unit_price"]),
                )
            else:
                # Migration 014 is optional for the aggregate receipt path;
                # once it is live every receipt gets a lot/barcode above.
                cursor.execute(
                    """
                    INSERT INTO goods_receipt_items
                        (receipt_id, po_item_id, ingredient_id, quantity, unit, unit_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (receipt["receipt_id"], line["po_item_id"], line["ingredient_id"],
                     line["quantity"], line["unit"], line["unit_price"]),
                )
            cursor.execute(
                """
                UPDATE po_items
                SET received_qty = received_qty + %s
                WHERE id = %s
                """,
                (line["quantity"], line["po_item_id"]),
            )
            cursor.execute(
                """
                INSERT INTO inventory_movements
                    (ingredient_id, ingredient_name_snapshot, movement_type, quantity,
                     unit, po_id, idempotency_key, actor_id, note)
                VALUES (%s, %s, 'RECEIPT', %s, %s, %s, %s, %s, %s)
                """,
                (line["ingredient_id"], line["item_name"], quantity_in_stock_unit,
                 stock_unit, po_id, f"receipt:{key}:{line['po_item_id']}", actor_id,
                 f"Goods receipt {receipt['receipt_id']}"),
            )
            posted_items.append({
                **line,
                "stock_quantity_added": quantity_in_stock_unit,
                "stock_unit": stock_unit,
                "current_stock": new_stock,
                "stock_status": status,
                "lot_id": str(lot_id) if lot_id else None,
                "barcode_value": barcode_value,
            })

        cursor.execute(
            """
            SELECT COUNT(*) AS remaining
            FROM po_items
            WHERE po_id = %s AND received_qty < qty
            """,
            (po_id,),
        )
        next_status = "RECEIVED" if int(cursor.fetchone()["remaining"]) == 0 else "PARTIAL"
        cursor.execute(
            """
            UPDATE purchase_orders
            SET status = %s, updated_at = NOW()
            WHERE po_id = %s
            RETURNING po_id, supplier_id, status
            """,
            (next_status, po_id),
        )
        updated_po = cursor.fetchone()
        result = {
            "status": "POSTED",
            "receipt_id": str(receipt["receipt_id"]),
            "po_id": po_id,
            "po_status": str(updated_po["status"]),
            "received_at": receipt["received_at"],
            "notes": str(notes or "").strip(),
            "items": posted_items,
        }
        _audit(cursor, actor_id=actor_id, action="GOODS_RECEIPT_POSTED", record_id=po_id, after=result)
        return result

    return _transaction(operation)


def approve_purchase_order(po_id: str, *, actor_id: str) -> dict[str, Any]:
    """Move exactly one DRAFT PO to APPROVED; repeated approval is idempotent."""
    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            UPDATE purchase_orders
            SET status = 'APPROVED', approved_by = %s, approved_at = NOW(), updated_at = NOW()
            WHERE po_id = %s AND status = 'DRAFT'
            RETURNING po_id, supplier_id, status, total_amount, approved_at
            """,
            (actor_id, po_id),
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            _audit(cursor, actor_id=actor_id, action="PO_APPROVED", record_id=po_id, after=result)
            return result
        cursor.execute("SELECT po_id, supplier_id, status, total_amount, approved_at FROM purchase_orders WHERE po_id = %s", (po_id,))
        existing = cursor.fetchone()
        if not existing:
            raise ProcurementNotFound("PO tidak ditemukan.")
        if existing["status"] == "APPROVED":
            return dict(existing)
        raise ProcurementUnavailable(f"PO berstatus {existing['status']} tidak dapat di-approve.")

    return _transaction(operation)


def reject_purchase_order(po_id: str, *, actor_id: str, notes: str = "") -> dict[str, Any]:
    """Reject a draft PO explicitly; repeated rejection is idempotent."""
    clean_notes = str(notes or "").strip()

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            UPDATE purchase_orders
            SET status = 'REJECTED',
                notes = CASE WHEN %s <> '' THEN notes || ' | Ditolak admin: ' || %s ELSE notes END,
                updated_at = NOW()
            WHERE po_id = %s AND status = 'DRAFT'
            RETURNING po_id, supplier_id, status, total_amount, notes, updated_at
            """,
            (clean_notes, clean_notes, po_id),
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            _audit(cursor, actor_id=actor_id, action="PO_REJECTED", record_id=po_id, after=result)
            return result
        cursor.execute("SELECT po_id, supplier_id, status, total_amount, notes FROM purchase_orders WHERE po_id = %s", (po_id,))
        existing = cursor.fetchone()
        if not existing:
            raise ProcurementNotFound("PO tidak ditemukan.")
        if existing["status"] == "REJECTED":
            return dict(existing)
        raise ProcurementUnavailable(f"PO berstatus {existing['status']} tidak dapat di-reject.")

    return _transaction(operation)


def request_purchase_order_changes(
    po_id: str,
    *,
    actor_id: str,
    notes: str,
) -> dict[str, Any]:
    """Keep a draft open while recording an explicit admin edit request."""
    clean_notes = str(notes or "").strip()
    if not clean_notes:
        raise ProcurementUnavailable("Catatan perubahan PO wajib diisi.")
    if len(clean_notes) > 1000:
        raise ProcurementUnavailable("Catatan perubahan PO terlalu panjang.")

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            UPDATE purchase_orders
            SET notes = CASE WHEN notes = '' THEN %s ELSE notes || ' | Edit admin: ' || %s END,
                updated_at = NOW()
            WHERE po_id = %s AND status = 'DRAFT'
            RETURNING po_id, supplier_id, status, total_amount, notes, updated_at
            """,
            (clean_notes, clean_notes, po_id),
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            _audit(cursor, actor_id=actor_id, action="PO_EDIT_REQUESTED", record_id=po_id, after=result)
            return result
        cursor.execute("SELECT po_id, status FROM purchase_orders WHERE po_id = %s", (po_id,))
        existing = cursor.fetchone()
        if not existing:
            raise ProcurementNotFound("PO tidak ditemukan.")
        raise ProcurementUnavailable(f"PO berstatus {existing['status']} tidak dapat diedit dari draft review.")

    return _transaction(operation)


def queue_purchase_order(po_id: str, *, actor_id: str) -> dict[str, Any]:
    """Queue an approved PO for Telegram delivery without claiming delivery."""
    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            SELECT po.po_id, po.supplier_id, po.status, po.total_amount,
                   s.name AS supplier_name,
                   c.telegram_chat_id AS supplier_telegram_chat_id
            FROM purchase_orders po
            JOIN suppliers s ON s.supplier_id = po.supplier_id
            LEFT JOIN supplier_accounts sa
              ON sa.supplier_id = s.supplier_id AND sa.status = 'active'
            LEFT JOIN customers c
              ON c.customer_id = sa.customer_id
            WHERE po.po_id = %s
            """,
            (po_id,),
        )
        po = cursor.fetchone()
        if not po:
            raise ProcurementNotFound("PO tidak ditemukan.")
        if po["status"] == "SENT":
            return {**dict(po), "delivery_status": "PENDING"}
        if po["status"] != "APPROVED":
            raise ProcurementUnavailable(f"PO berstatus {po['status']} belum dapat di-queue.")
        supplier_chat_id = str(po.get("supplier_telegram_chat_id") or "").strip()
        if not supplier_chat_id:
            raise ProcurementUnavailable(
                "Supplier belum menautkan akun Telegram. Hubungkan supplier_accounts ke customer Telegram sebelum PO dikirim."
            )

        cursor.execute(
            """
            SELECT pi.item_name, pi.qty, pi.unit, pi.subtotal
            FROM po_items pi WHERE pi.po_id = %s ORDER BY pi.id
            """,
            (po_id,),
        )
        items = [dict(row) for row in cursor.fetchall()]
        if not items:
            raise ProcurementUnavailable("PO tidak memiliki item.")
        message = "PO %s dari Dova Kitchen:\n%s\nTotal: %s" % (
            po_id,
            "\n".join(f"- {item['item_name']}: {item['qty']} {item['unit']}" for item in items),
            po["total_amount"],
        )
        cursor.execute(
            """
            UPDATE purchase_orders
            SET status = 'SENT', sent_at = NOW(), updated_at = NOW()
            WHERE po_id = %s AND status = 'APPROVED'
            RETURNING po_id, supplier_id, status, total_amount, sent_at
            """,
            (po_id,),
        )
        sent = dict(cursor.fetchone())
        cursor.execute(
            """
            INSERT INTO notification_outbox
                (recipient_type, recipient_phone, recipient_name, channel, event_type,
                 message, status, idempotency_key)
            VALUES ('supplier', %s, %s, 'telegram', 'PO_READY_FOR_DELIVERY', %s, 'PENDING', %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (supplier_chat_id, po["supplier_name"], message, f"po-send:{po_id}"),
        )
        _audit(cursor, actor_id=actor_id, action="PO_QUEUED_FOR_DELIVERY", record_id=po_id, after=sent)
        return {**sent, "delivery_status": "PENDING"}

    return _transaction(operation)


def record_supplier_response(
    po_id: str,
    supplier_id: str,
    *,
    status: str,
    notes: str = "",
    estimated_delivery: str | None = None,
) -> dict[str, Any]:
    """Record a response only for the authenticated supplier's sent PO."""
    aliases = {
        "ACKNOWLEDGED": "ACCEPTED",
        "PARTIALLY_RECEIVED": "PARTIAL",
        "PARTIAL": "PARTIAL",
        "ACCEPTED": "ACCEPTED",
        "REJECTED": "REJECTED",
    }
    normalized = aliases.get(str(status or "").upper())
    if not normalized:
        raise ProcurementUnavailable("Status supplier tidak valid.")
    delivery_date = None
    if estimated_delivery:
        try:
            delivery_date = date.fromisoformat(estimated_delivery)
        except ValueError as exc:
            raise ProcurementUnavailable("estimated_delivery harus tanggal ISO.") from exc

    admin_chat_ids = [
        value.strip()
        for value in settings.telegram_admin_chat_ids.split(",")
        if value.strip()
    ]
    if not admin_chat_ids:
        raise ProcurementUnavailable(
            "TELEGRAM_ADMIN_CHAT_IDS belum dikonfigurasi; balasan supplier tidak dapat diteruskan ke admin."
        )

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            "SELECT po_id, supplier_id, status, total_amount FROM purchase_orders WHERE po_id = %s AND supplier_id = %s",
            (po_id, supplier_id),
        )
        po = cursor.fetchone()
        if not po:
            raise ProcurementNotFound("PO tidak ditemukan.")
        if po["status"] not in {"SENT", "ACCEPTED", "PARTIAL"}:
            raise ProcurementUnavailable("Supplier hanya dapat merespons PO yang sudah di-queue.")
        cursor.execute(
            """
            UPDATE purchase_orders
            SET status = %s,
                notes = CASE WHEN %s <> '' THEN notes || ' | Respon: ' || %s ELSE notes END,
                supplier_estimated_delivery = %s,
                updated_at = NOW()
            WHERE po_id = %s AND supplier_id = %s
            RETURNING po_id, supplier_id, status, notes, supplier_estimated_delivery
            """,
            (normalized, notes, notes, delivery_date, po_id, supplier_id),
        )
        result = dict(cursor.fetchone())
        cursor.execute(
            """
            INSERT INTO notification_outbox
                (recipient_type, recipient_phone, recipient_name, channel, event_type,
                 message, status, idempotency_key)
            VALUES ('admin', %s, 'Dova Kitchen Admin', 'telegram', 'PO_SUPPLIER_RESPONSE', %s, 'PENDING', %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (admin_chat_ids[0], f"Supplier {supplier_id} memperbarui PO {po_id} menjadi {normalized}: {notes or '-'}", f"po-response:{po_id}:{normalized}"),
        )
        _audit(cursor, actor_id=supplier_id, action="PO_SUPPLIER_RESPONDED", record_id=po_id, after=result)
        return result

    return _transaction(operation)


def record_supplier_change_request(
    po_id: str,
    supplier_id: str,
    *,
    notes: str,
    estimated_delivery: str | None = None,
    idempotency_key: str,
) -> dict[str, Any]:
    """Record a supplier change request without silently changing the PO."""
    clean_notes = str(notes or "").strip()
    if len(clean_notes) < 2:
        raise ProcurementUnavailable("Catatan perubahan supplier wajib diisi.")
    key = _validate_key(idempotency_key)
    delivery_date = None
    if estimated_delivery:
        try:
            delivery_date = date.fromisoformat(estimated_delivery)
        except ValueError as exc:
            raise ProcurementUnavailable("estimated_delivery harus tanggal ISO.") from exc
    admin_chat_ids = [value.strip() for value in settings.telegram_admin_chat_ids.split(",") if value.strip()]
    if not admin_chat_ids:
        raise ProcurementUnavailable(
            "TELEGRAM_ADMIN_CHAT_IDS belum dikonfigurasi; perubahan supplier tidak dapat diteruskan."
        )

    def operation(cursor: Any) -> dict[str, Any]:
        cursor.execute(
            """
            SELECT po_id, supplier_id, status, total_amount, notes, supplier_estimated_delivery
            FROM purchase_orders
            WHERE po_id = %s AND supplier_id = %s
            FOR UPDATE
            """,
            (po_id, supplier_id),
        )
        po = cursor.fetchone()
        if not po:
            raise ProcurementNotFound("PO tidak ditemukan.")
        if po["status"] not in {"SENT", "ACCEPTED", "PARTIAL"}:
            raise ProcurementUnavailable("PO belum berada pada tahap yang dapat diajukan perubahannya.")

        cursor.execute(
            """
            UPDATE purchase_orders
            SET notes = notes || ' | Permintaan perubahan supplier: ' || %s,
                supplier_estimated_delivery = COALESCE(%s, supplier_estimated_delivery),
                updated_at = NOW()
            WHERE po_id = %s AND supplier_id = %s
            RETURNING po_id, supplier_id, status, total_amount, notes, supplier_estimated_delivery
            """,
            (clean_notes, delivery_date, po_id, supplier_id),
        )
        result = dict(cursor.fetchone())
        cursor.execute(
            """
            INSERT INTO notification_outbox
                (recipient_type, recipient_phone, recipient_name, channel,
                 event_type, message, status, idempotency_key)
            VALUES ('admin', %s, 'Dova Kitchen Admin', 'telegram',
                    'PO_SUPPLIER_CHANGE_REQUEST', %s, 'PENDING', %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (
                admin_chat_ids[0],
                f"Supplier {supplier_id} meminta perubahan PO {po_id}: {clean_notes}",
                f"po-change:{po_id}:{key}",
            ),
        )
        _audit(cursor, actor_id=supplier_id, action="PO_SUPPLIER_CHANGE_REQUESTED", record_id=po_id, after={"notes": clean_notes, "idempotency_key": key})
        return {**result, "change_request_idempotency_key": key, "notification_status": "PENDING"}

    return _transaction(operation)
