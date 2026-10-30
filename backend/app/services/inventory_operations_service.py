"""Kitchen-facing inventory writes.

The kitchen records actual consumption here. This keeps the operational stock
ledger separate from the recipe BOM and makes the later Bluetooth-scale input
only another way to provide ``quantity``.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.repositories import supabase as db


def _number(value: Any, field: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} tidak valid.") from exc
    if not math.isfinite(value):
        raise ValidationError(f"{field} tidak valid.")
    return value


def list_kitchen_inventory() -> dict[str, Any]:
    rows = db.execute(
        """
        SELECT ist.ingredient_id, ist.ingredient_name, ist.current_stock,
               ist.min_stock, ist.unit, ist.status, ist.updated_at
        FROM inventory_stocks ist
        ORDER BY CASE ist.status
                   WHEN 'HABIS' THEN 1
                   WHEN 'MENIPIS' THEN 2
                   ELSE 3
                 END,
                 ist.ingredient_name
        """
    )
    items = [
        {
            "ingredient_id": str(row.get("ingredient_id") or ""),
            "ingredient_name": str(row.get("ingredient_name") or ""),
            "current_stock": _number(row.get("current_stock"), "current_stock"),
            "min_stock": _number(row.get("min_stock"), "min_stock"),
            "unit": str(row.get("unit") or ""),
            "status": str(row.get("status") or "AMBIL_AMAN"),
            "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else "",
            "is_scan_ready": bool(row.get("ingredient_id")),
        }
        for row in rows
    ]
    return {
        "items": items,
        "counts": {
            "total": len(items),
            "menipis": sum(1 for item in items if item["status"] == "MENIPIS"),
            "habis": sum(1 for item in items if item["status"] == "HABIS"),
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def record_consumption(
    *,
    ingredient_id: str,
    quantity: float,
    unit: str,
    batch_reference: str,
    note: str,
    idempotency_key: str,
    actor_id: str,
) -> dict[str, Any]:
    """Subtract physical usage from both the ledger and operational balance."""
    clean_id = ingredient_id.strip()
    clean_unit = unit.strip()
    clean_key = idempotency_key.strip()
    used = _number(quantity, "quantity")
    if used <= 0 or not clean_id or not clean_unit or not clean_key:
        raise ValidationError("Bahan, berat, unit, dan idempotency key wajib diisi.")

    # Lot allocation is opt-in until migration 018 is present. The aggregate
    # inventory ledger remains usable during the staged Supabase rollout.
    lot_tracking_ready = (
        db.has_table("stock_lots")
        and db.has_table("inventory_lot_allocations")
        and db.has_column("inventory_movements", "lot_id")
    )

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT movement_id, ingredient_id, ingredient_name_snapshot, quantity, unit
                FROM inventory_movements WHERE idempotency_key = %s
                """,
                (clean_key,),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """
                    SELECT current_stock, min_stock, unit, status
                    FROM inventory_stocks WHERE ingredient_id = %s
                    """,
                    (existing["ingredient_id"],),
                )
                stock = cur.fetchone()
                if not stock:
                    raise ConflictError("Ledger pemakaian ada, tetapi kartu stok bahan tidak ditemukan.")
                allocations: list[dict[str, Any]] = []
                if lot_tracking_ready:
                    cur.execute(
                        """
                        SELECT ila.lot_id, ila.quantity, ila.unit
                        FROM inventory_lot_allocations ila
                        JOIN inventory_movements im ON im.movement_id = ila.movement_id
                        WHERE im.idempotency_key = %s
                        ORDER BY ila.created_at, ila.lot_id
                        """,
                        (clean_key,),
                    )
                    allocations = [
                        {
                            "lot_id": str(row["lot_id"]),
                            "quantity": float(row["quantity"]),
                            "unit": str(row["unit"]),
                        }
                        for row in cur.fetchall()
                    ]
                return {
                    "movement_id": str(existing["movement_id"]),
                    "ingredient_id": str(existing["ingredient_id"]),
                    "ingredient_name": str(existing["ingredient_name_snapshot"]),
                    "consumed_quantity": abs(_number(existing["quantity"], "quantity")),
                    "unit": str(existing["unit"]),
                    "current_stock": _number(stock["current_stock"], "current_stock"),
                    "min_stock": _number(stock["min_stock"], "min_stock"),
                    "status": str(stock["status"]),
                    "idempotent": True,
                    "lot_allocations": allocations,
                }

            cur.execute(
                """
                SELECT ist.ingredient_id, ist.ingredient_name, ist.current_stock,
                       ist.min_stock, ist.unit
                FROM inventory_stocks ist
                WHERE ist.ingredient_id = %s
                FOR UPDATE
                """,
                (clean_id,),
            )
            stock = cur.fetchone()
            if not stock:
                raise NotFoundError("Bahan tidak ditemukan atau belum siap untuk dicatat dari kitchen.")
            stock_unit = str(stock["unit"] or "").strip()
            if stock_unit.lower() != clean_unit.lower():
                raise ValidationError(
                    f"Unit kitchen harus sama dengan kartu stok ({stock_unit}). Konversi unit belum diaktifkan.",
                )
            current = _number(stock["current_stock"], "current_stock")
            minimum = _number(stock["min_stock"], "min_stock")
            if used > current:
                raise ConflictError(
                    f"Pemakaian {used:g} {stock_unit} melebihi stok tersedia {current:g} {stock_unit}.",
                )

            lot_allocations: list[dict[str, Any]] = []
            if lot_tracking_ready:
                cur.execute(
                    """
                    SELECT lot_id, quantity_on_hand, unit, expiry_at, received_at
                    FROM stock_lots
                    WHERE ingredient_id = %s
                      AND status = 'AVAILABLE'
                      AND quantity_on_hand > 0
                      AND LOWER(unit) = LOWER(%s)
                      AND (expiry_at IS NULL OR expiry_at >= CURRENT_DATE)
                    ORDER BY expiry_at NULLS LAST, received_at NULLS LAST, lot_id
                    FOR UPDATE
                    """,
                    (clean_id, stock_unit),
                )
                lots = cur.fetchall()
                lot_total = sum(_number(row["quantity_on_hand"], "quantity_on_hand") for row in lots)
                if lots and lot_total + 1e-9 < used:
                    raise ConflictError(
                        "Stok lot tersedia tidak cukup untuk pemakaian FEFO; periksa penerimaan atau stock count.",
                    )
                remaining_to_allocate = used if lots else 0.0
                for lot in lots:
                    allocation_quantity = min(
                        remaining_to_allocate,
                        _number(lot["quantity_on_hand"], "quantity_on_hand"),
                    )
                    if allocation_quantity <= 0:
                        continue
                    cur.execute(
                        """
                        UPDATE stock_lots
                        SET quantity_on_hand = quantity_on_hand - %s, updated_at = NOW(),
                            status = CASE WHEN quantity_on_hand - %s <= 0 THEN 'CLOSED' ELSE status END
                        WHERE lot_id = %s
                        """,
                        (allocation_quantity, allocation_quantity, lot["lot_id"]),
                    )
                    lot_allocations.append({
                        "lot_id": str(lot["lot_id"]),
                        "quantity": round(allocation_quantity, 4),
                        "unit": stock_unit,
                    })
                    remaining_to_allocate = round(remaining_to_allocate - allocation_quantity, 4)
                    if remaining_to_allocate <= 1e-9:
                        break
            remaining = round(current - used, 4)
            status = "HABIS" if remaining <= 0 else "MENIPIS" if remaining <= minimum else "AMBIL_AMAN"
            movement_note = " | ".join(value for value in [
                f"Batch: {batch_reference.strip()}" if batch_reference.strip() else "",
                note.strip(),
            ] if value)
            cur.execute(
                """
                UPDATE inventory_stocks
                SET current_stock = %s, status = %s, updated_at = NOW()
                WHERE ingredient_id = %s
                """,
                (remaining, status, clean_id),
            )
            movement_lot_id = lot_allocations[0]["lot_id"] if len(lot_allocations) == 1 else None
            if lot_tracking_ready:
                cur.execute(
                    """
                    INSERT INTO inventory_movements
                        (ingredient_id, ingredient_name_snapshot, movement_type, quantity,
                         unit, idempotency_key, actor_id, note, lot_id)
                    VALUES (%s, %s, 'CONSUMPTION', %s, %s, %s, %s, %s, %s)
                    RETURNING movement_id
                    """,
                    (
                        clean_id, stock["ingredient_name"], -used, stock_unit,
                        clean_key, actor_id, movement_note, movement_lot_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO inventory_movements
                        (ingredient_id, ingredient_name_snapshot, movement_type, quantity,
                         unit, idempotency_key, actor_id, note)
                    VALUES (%s, %s, 'CONSUMPTION', %s, %s, %s, %s, %s)
                    RETURNING movement_id
                    """,
                    (
                        clean_id, stock["ingredient_name"], -used, stock_unit,
                        clean_key, actor_id, movement_note,
                    ),
                )
            movement = cur.fetchone()
            if lot_tracking_ready and lot_allocations:
                for allocation in lot_allocations:
                    cur.execute(
                        """
                        INSERT INTO inventory_lot_allocations
                            (movement_id, lot_id, ingredient_id, quantity, unit)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            movement["movement_id"], allocation["lot_id"], clean_id,
                            allocation["quantity"], allocation["unit"],
                        ),
                    )
            return {
                "movement_id": str(movement["movement_id"]),
                "ingredient_id": clean_id,
                "ingredient_name": str(stock["ingredient_name"]),
                "consumed_quantity": used,
                "unit": stock_unit,
                "current_stock": remaining,
                "min_stock": minimum,
                "status": status,
                "idempotent": False,
                "lot_allocations": lot_allocations,
            }
