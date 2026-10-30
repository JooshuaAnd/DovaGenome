"""Production batch and manual weigh ledger.

The first adapter is deliberately manual.  A future Bluetooth scale adapter
only needs to submit the same ``ProductionWeighIn`` contract; stock and BOM
rules stay in this service and never move into the device integration.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any

from app.core.domain import DAYS
from app.core.errors import ConflictError, DatabaseError, NotFoundError, ValidationError
from app.repositories import supabase as db


_MASS_TO_GRAMS = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
}


def _number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} tidak valid.") from exc
    if not math.isfinite(number):
        raise ValidationError(f"{field} tidak valid.")
    return number


def _grams(quantity: Any, unit: Any, field: str = "quantity") -> float:
    clean_unit = str(unit or "").strip().lower()
    if clean_unit not in _MASS_TO_GRAMS:
        raise ValidationError(
            f"Unit '{unit}' belum bisa ditimbang. Gunakan gram atau kilogram.",
            details={"supported_units": ["g", "kg"], "field": field},
        )
    value = _number(quantity, field)
    if value <= 0:
        raise ValidationError(f"{field} harus lebih besar dari nol.")
    return value * _MASS_TO_GRAMS[clean_unit]


def _from_grams(grams: float, unit: Any) -> float:
    clean_unit = str(unit or "").strip().lower()
    if clean_unit not in _MASS_TO_GRAMS:
        raise ValidationError(f"Unit stok '{unit}' belum memiliki konversi massa.")
    return round(grams / _MASS_TO_GRAMS[clean_unit], 4)


def _lot_tracking_ready() -> bool:
    return (
        db.has_table("stock_lots")
        and db.has_table("inventory_lot_allocations")
        and db.has_column("inventory_movements", "lot_id")
    )


def _allocate_lots(
    cur: Any,
    *,
    ingredient_id: str,
    unit: str,
    quantity: float,
    requested_lot_id: str | None = None,
) -> list[dict[str, Any]]:
    """Deduct quantity from available lots in FEFO order inside one transaction."""
    lot_filter = "AND lot_id = %s" if requested_lot_id else ""
    params: tuple[Any, ...] = (ingredient_id, unit, requested_lot_id) if requested_lot_id else (ingredient_id, unit)
    cur.execute(
        f"""
        SELECT lot_id, quantity_on_hand, unit, expiry_at, received_at
        FROM stock_lots
        WHERE ingredient_id = %s
          AND status = 'AVAILABLE'
          AND quantity_on_hand > 0
          AND LOWER(unit) = LOWER(%s)
          AND (expiry_at IS NULL OR expiry_at >= CURRENT_DATE)
          {lot_filter}
        ORDER BY expiry_at NULLS LAST, received_at NULLS LAST, lot_id
        FOR UPDATE
        """,
        params,
    )
    lots = cur.fetchall()
    if requested_lot_id and not lots:
        raise ConflictError("Lot yang dipilih tidak tersedia, expired, atau unitnya tidak sesuai.")
    if not lots:
        return []
    total = sum(_number(row["quantity_on_hand"], "quantity_on_hand") for row in lots)
    if total + 1e-9 < quantity:
        raise ConflictError("Stok lot tersedia tidak cukup untuk penimbangan FEFO.")

    allocations: list[dict[str, Any]] = []
    remaining = quantity
    for lot in lots:
        amount = min(remaining, _number(lot["quantity_on_hand"], "quantity_on_hand"))
        if amount <= 0:
            continue
        cur.execute(
            """
            UPDATE stock_lots
            SET quantity_on_hand = quantity_on_hand - %s, updated_at = NOW(),
                status = CASE WHEN quantity_on_hand - %s <= 0 THEN 'CLOSED' ELSE status END
            WHERE lot_id = %s
            """,
            (amount, amount, lot["lot_id"]),
        )
        allocations.append({"lot_id": str(lot["lot_id"]), "quantity": round(amount, 4), "unit": unit})
        remaining = round(remaining - amount, 4)
        if remaining <= 1e-9:
            break
    return allocations


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _requirement(row: dict[str, Any]) -> dict[str, Any]:
    planned = _grams(row["planned_quantity"], row["unit"], "planned_quantity")
    issued = _grams(row.get("issued_quantity") or 0.0001, row["unit"], "issued_quantity")
    # The tiny positive input above avoids treating a zero issued quantity as
    # an invalid measurement; the result is explicitly reset to zero below.
    if float(row.get("issued_quantity") or 0) == 0:
        issued = 0.0
    remaining = max(0.0, planned - issued)
    return {
        "requirement_id": str(row["requirement_id"]),
        "ingredient_id": str(row["ingredient_id"]),
        "ingredient_name": str(row.get("ingredient_name") or ""),
        "planned_quantity": float(row["planned_quantity"]),
        "unit": str(row["unit"]),
        "issued_quantity": float(row.get("issued_quantity") or 0),
        "variance_quantity": float(row.get("variance_quantity") or 0),
        "planned_grams": round(planned, 4),
        "issued_grams": round(issued, 4),
        "remaining_grams": round(remaining, 4),
    }


def _batch_out(row: dict[str, Any], requirements: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "batch_id": str(row["batch_id"]),
        "service_date": _iso(row.get("service_date")),
        "meal_slot": str(row.get("meal_slot") or "lunch"),
        "site_code": str(row.get("site_code") or "main-kitchen"),
        "recipe_version_id": str(row["recipe_version_id"]),
        "menu_name": str(row.get("menu_name") or ""),
        "planned_portions": int(row["planned_portions"]),
        "status": str(row.get("status") or "DRAFT"),
        "notes": str(row.get("notes") or ""),
        "requirements": [_requirement(item) for item in requirements],
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def _batch_row(batch_id: str) -> dict[str, Any]:
    row = db.execute_one(
        """
        SELECT pb.*, m.nama_menu AS menu_name
        FROM production_batches pb
        JOIN recipe_versions rv ON rv.recipe_version_id = pb.recipe_version_id
        JOIN menus m ON m.menu_id = rv.menu_id
        WHERE pb.batch_id = %s
        """,
        (batch_id,),
    )
    if not row:
        raise NotFoundError("Production batch tidak ditemukan.")
    return row


def _assert_phase_migration() -> None:
    if not db.check_production_batch_migrations():
        raise DatabaseError(
            "Migration recipe import/production batch belum diterapkan di Supabase."
        )


def get_batch(batch_id: str) -> dict[str, Any]:
    _assert_phase_migration()
    row = _batch_row(batch_id)
    requirements = db.execute(
        """
        SELECT requirement_id, batch_id, ingredient_id, ingredient_name,
               planned_quantity, unit, issued_quantity, variance_quantity
        FROM production_batch_requirements
        WHERE batch_id = %s
        ORDER BY ingredient_name, requirement_id
        """,
        (batch_id,),
    )
    return _batch_out(row, requirements)


def list_batches(*, service_date: date | None = None) -> dict[str, Any]:
    _assert_phase_migration()
    if service_date:
        rows = db.execute(
            """
            SELECT pb.*, m.nama_menu AS menu_name
            FROM production_batches pb
            JOIN recipe_versions rv ON rv.recipe_version_id = pb.recipe_version_id
            JOIN menus m ON m.menu_id = rv.menu_id
            WHERE pb.service_date = %s
            ORDER BY pb.meal_slot, m.nama_menu, pb.created_at DESC
            """,
            (service_date,),
        )
    else:
        rows = db.execute(
            """
            SELECT pb.*, m.nama_menu AS menu_name
            FROM production_batches pb
            JOIN recipe_versions rv ON rv.recipe_version_id = pb.recipe_version_id
            JOIN menus m ON m.menu_id = rv.menu_id
            WHERE pb.service_date >= CURRENT_DATE
            ORDER BY pb.service_date, pb.meal_slot, m.nama_menu, pb.created_at DESC
            """
        )
    items = []
    for row in rows:
        requirements = db.execute(
            """
            SELECT requirement_id, batch_id, ingredient_id, ingredient_name,
                   planned_quantity, unit, issued_quantity, variance_quantity
            FROM production_batch_requirements
            WHERE batch_id = %s
            ORDER BY ingredient_name, requirement_id
            """,
            (row["batch_id"],),
        )
        items.append(_batch_out(row, requirements))
    return {
        "items": items,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def create_batch(
    *,
    service_date: date,
    meal_slot: str,
    recipe_version_id: str,
    planned_portions: int,
    site_code: str,
    notes: str,
    actor_id: str,
) -> dict[str, Any]:
    _assert_phase_migration()
    recipe = db.execute_one(
        """
        SELECT rv.recipe_version_id, rv.status, rv.yield_quantity,
               rv.yield_unit, m.nama_menu AS menu_name
        FROM recipe_versions rv
        JOIN menus m ON m.menu_id = rv.menu_id
        WHERE rv.recipe_version_id = %s
        """,
        (recipe_version_id,),
    )
    if not recipe:
        raise NotFoundError("Recipe version tidak ditemukan.")
    if str(recipe.get("status")) != "VERIFIED":
        raise ConflictError(
            "Batch hanya boleh dibuat dari recipe yang sudah VERIFIED.",
            details={"recipe_version_id": recipe_version_id, "status": recipe.get("status")},
        )
    components = db.execute(
        """
        SELECT rc.ingredient_id, i.name AS ingredient_name, rc.quantity, rc.unit
        FROM recipe_components rc
        JOIN ingredients i ON i.ingredient_id = rc.ingredient_id
        WHERE rc.recipe_version_id = %s
          AND rc.verification_status = 'VERIFIED'
        ORDER BY rc.sort_order, rc.recipe_component_id
        """,
        (recipe_version_id,),
    )
    if not components:
        raise ValidationError("Recipe VERIFIED tetapi BOM-nya kosong.")
    yield_quantity = _number(recipe.get("yield_quantity") or 0, "yield_quantity")
    if yield_quantity <= 0:
        raise ValidationError("Yield recipe tidak valid.")

    try:
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO production_batches
                        (service_date, meal_slot, site_code, recipe_version_id,
                         planned_portions, status, notes, created_by)
                    VALUES (%s, %s, %s, %s, %s, 'OPEN', %s, %s)
                    RETURNING batch_id
                    """,
                    (service_date, meal_slot, site_code, recipe_version_id,
                     planned_portions, notes, actor_id),
                )
                batch = cur.fetchone()
                batch_id = str(batch["batch_id"])
                for component in components:
                    quantity = _number(component.get("quantity"), "recipe quantity")
                    unit = str(component.get("unit") or "").strip()
                    # Validate now, at batch creation, instead of discovering
                    # an unsupported unit when kitchen is already weighing.
                    _grams(quantity, unit, "recipe quantity")
                    planned_quantity = quantity * planned_portions / yield_quantity
                    cur.execute(
                        """
                        INSERT INTO production_batch_requirements
                            (batch_id, ingredient_id, ingredient_name,
                             planned_quantity, unit)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (batch_id, component["ingredient_id"], component["ingredient_name"],
                         planned_quantity, unit),
                    )
    except ConflictError:
        raise
    except Exception as exc:
        if "production_batches" in str(exc) and "does not exist" in str(exc):
            raise DatabaseError(
                "Migration production batch belum diterapkan di Supabase."
            ) from exc
        raise DatabaseError("Gagal membuat production batch.") from exc
    return get_batch(batch_id)


def plan_batches_from_paid_orders(
    *,
    service_date: date,
    meal_slot: str,
    site_code: str,
    actor_id: str,
) -> dict[str, Any]:
    """Aggregate paid demand into production batches for one service date.

    Legacy order rows have no meal-slot column, so they are treated as the
    explicitly requested slot. Once the delivery/order-slot migration is live,
    the query uses the stored slot and does not mix breakfast/lunch/dinner.
    """
    _assert_phase_migration()
    if meal_slot not in {"breakfast", "lunch", "dinner", "snack"}:
        raise ValidationError("Meal slot batch tidak valid.")
    if service_date.weekday() >= len(DAYS):
        raise ValidationError("Tanggal layanan harus Senin sampai Sabtu.")
    day_name = DAYS[service_date.weekday()]
    clean_site = str(site_code or "main-kitchen").strip() or "main-kitchen"

    try:
        demand = db.execute(
            """
            SELECT oi.menu_id, COALESCE(SUM(oi.quantity), COUNT(*)) AS planned_portions,
                   COALESCE(oi.meal_slot, %s) AS demand_meal_slot
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.payment_status = 'PAID'
              AND o.status <> 'CANCELLED'
              AND oi.hari = %s
              AND oi.menu_id IS NOT NULL
              AND COALESCE(oi.meal_slot, %s) = %s
            GROUP BY oi.menu_id, COALESCE(oi.meal_slot, %s)
            ORDER BY oi.menu_id
            """,
            (meal_slot, day_name, meal_slot, meal_slot, meal_slot),
        )
    except Exception as exc:
        # Migration 017 adds order_items.meal_slot. Keep the planner readable
        # against the core schema, where all historical demand is lunch. Do
        # not reinterpret legacy lunch orders as breakfast/dinner demand.
        if meal_slot != "lunch" and not (
            "meal_slot" in str(exc).lower() and "column" in str(exc).lower()
        ):
            raise DatabaseError("Gagal membaca demand PAID dari Supabase.") from exc
        if meal_slot != "lunch":
            demand = []
        else:
            demand = db.execute(
                """
                SELECT oi.menu_id, COALESCE(SUM(oi.quantity), COUNT(*)) AS planned_portions
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.order_id
                WHERE o.payment_status = 'PAID'
                  AND o.status <> 'CANCELLED'
                  AND oi.hari = %s
                  AND oi.menu_id IS NOT NULL
                GROUP BY oi.menu_id
                ORDER BY oi.menu_id
                """,
                (day_name,),
            )

    if not demand:
        return {
            "status": "NO_PAID_DEMAND",
            "service_date": service_date.isoformat(),
            "meal_slot": meal_slot,
            "site_code": clean_site,
            "planned_batches": [],
            "blocked_menus": [],
            "source": "supabase_postgres",
        }

    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in demand:
        menu_id = str(row.get("menu_id") or "").strip()
        portions = int(float(row.get("planned_portions") or 0))
        if not menu_id or portions <= 0:
            continue
        recipe = db.execute_one(
            """
            SELECT recipe_version_id, yield_quantity, yield_unit, version_no
            FROM recipe_versions
            WHERE menu_id = %s AND status = 'VERIFIED'
            ORDER BY version_no DESC, verified_at DESC NULLS LAST
            LIMIT 1
            """,
            (menu_id,),
        )
        if not recipe:
            blocked.append({
                "menu_id": menu_id,
                "planned_portions": portions,
                "reason": "RECIPE_NOT_VERIFIED",
            })
            continue
        candidates.append({
            "menu_id": menu_id,
            "recipe_version_id": str(recipe["recipe_version_id"]),
            "planned_portions": portions,
        })

    # A partially planned date is dangerous: the kitchen could interpret it
    # as the complete demand. Hold every write until all paid menus are ready.
    if blocked:
        return {
            "status": "REQUIRES_VERIFICATION",
            "service_date": service_date.isoformat(),
            "meal_slot": meal_slot,
            "site_code": clean_site,
            "planned_batches": [],
            "blocked_menus": blocked,
            "source": "supabase_postgres",
        }

    planned: list[dict[str, Any]] = []
    existing_count = 0
    for candidate in candidates:
        existing = db.execute_one(
            """
            SELECT batch_id, status
            FROM production_batches
            WHERE service_date = %s
              AND meal_slot = %s
              AND site_code = %s
              AND recipe_version_id = %s
              AND status <> 'CANCELLED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (service_date, meal_slot, clean_site, candidate["recipe_version_id"]),
        )
        if existing:
            existing_count += 1
            planned.append({
                "batch_id": str(existing["batch_id"]),
                "recipe_version_id": candidate["recipe_version_id"],
                "menu_id": candidate["menu_id"],
                "planned_portions": candidate["planned_portions"],
                "status": str(existing["status"]),
                "idempotent": True,
            })
            continue
        batch = create_batch(
            service_date=service_date,
            meal_slot=meal_slot,
            recipe_version_id=candidate["recipe_version_id"],
            planned_portions=candidate["planned_portions"],
            site_code=clean_site,
            notes="Dibuat dari agregasi order PAID; bukan forecast.",
            actor_id=actor_id,
        )
        planned.append({
            "batch_id": batch["batch_id"],
            "recipe_version_id": candidate["recipe_version_id"],
            "menu_id": candidate["menu_id"],
            "planned_portions": candidate["planned_portions"],
            "status": batch["status"],
            "idempotent": False,
        })

    return {
        "status": "EXISTING" if existing_count == len(planned) else "CREATED",
        "service_date": service_date.isoformat(),
        "meal_slot": meal_slot,
        "site_code": clean_site,
        "planned_batches": planned,
        "blocked_menus": [],
        "source": "supabase_postgres",
    }


def record_weigh(
    *,
    batch_id: str,
    requirement_id: str,
    actual_net_grams: float,
    tare_grams: float,
    idempotency_key: str,
    lot_id: str | None,
    scale_source: str,
    device_id: str,
    actor_id: str,
    note: str,
) -> dict[str, Any]:
    _assert_phase_migration()
    if scale_source != "manual":
        raise ValidationError(
            "Adapter Bluetooth timbangan belum diaktifkan. Gunakan input manual dulu."
        )
    actual = _number(actual_net_grams, "actual_net_grams")
    tare = _number(tare_grams, "tare_grams")
    if actual <= 0 or tare < 0:
        raise ValidationError("Berat net harus lebih besar dari nol dan tare tidak negatif.")
    lot_tracking_ready = _lot_tracking_ready()
    if lot_id and not lot_tracking_ready:
        raise ValidationError("Lot tracking belum aktif di Supabase; jangan kirim lot_id sebelum migration 018.")

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT we.weigh_event_id, we.batch_id, we.requirement_id,
                       we.ingredient_id, we.actual_net_grams,
                       im.movement_id, im.quantity AS movement_quantity,
                       ist.current_stock, ist.unit AS stock_unit, ist.status AS stock_status,
                       pbr.issued_quantity, pbr.planned_quantity, pbr.unit,
                       i.name AS ingredient_name
                FROM weigh_events we
                LEFT JOIN inventory_movements im ON im.weigh_event_id = we.weigh_event_id
                JOIN production_batch_requirements pbr ON pbr.requirement_id = we.requirement_id
                JOIN ingredients i ON i.ingredient_id = we.ingredient_id
                LEFT JOIN inventory_stocks ist ON ist.ingredient_id = we.ingredient_id
                WHERE we.idempotency_key = %s
                """,
                (idempotency_key.strip(),),
            )
            existing = cur.fetchone()
            if existing:
                if not existing.get("movement_id"):
                    raise ConflictError("Event timbang sudah ada tetapi ledger belum lengkap.")
                return {
                    "weigh_event_id": str(existing["weigh_event_id"]),
                    "movement_id": str(existing["movement_id"]),
                    "batch_id": str(existing["batch_id"]),
                    "requirement_id": str(existing["requirement_id"]),
                    "ingredient_id": str(existing["ingredient_id"]),
                    "ingredient_name": str(existing["ingredient_name"]),
                    "actual_net_grams": float(existing["actual_net_grams"]),
                    "stock_quantity_deducted": abs(float(existing["movement_quantity"])) if existing.get("movement_quantity") else 0,
                    "stock_unit": str(existing.get("stock_unit") or ""),
                    "current_stock": float(existing.get("current_stock") or 0),
                    "stock_status": str(existing.get("stock_status") or ""),
                    "issued_grams": round(_grams(existing["issued_quantity"], existing["unit"], "issued_quantity"), 4),
                    "remaining_planned_grams": round(
                        max(0, _grams(existing["planned_quantity"], existing["unit"], "planned_quantity")
                            - _grams(existing["issued_quantity"], existing["unit"], "issued_quantity")),
                        4,
                    ),
                    "idempotent": True,
                    "lot_allocations": [],
                }

            cur.execute(
                """
                SELECT pb.batch_id, pb.status, pbr.*, i.name AS ingredient_name
                FROM production_batch_requirements pbr
                JOIN production_batches pb ON pb.batch_id = pbr.batch_id
                JOIN ingredients i ON i.ingredient_id = pbr.ingredient_id
                WHERE pbr.requirement_id = %s AND pbr.batch_id = %s
                FOR UPDATE OF pb, pbr
                """,
                (requirement_id, batch_id),
            )
            req = cur.fetchone()
            if not req:
                raise NotFoundError("Komponen batch tidak ditemukan.")
            if req["status"] in ("CANCELLED", "COMPLETED"):
                raise ConflictError(f"Batch berstatus {req['status']} tidak dapat ditimbang.")
            planned_grams = _grams(req["planned_quantity"], req["unit"], "planned_quantity")
            issued_grams = 0 if not req.get("issued_quantity") else _grams(req["issued_quantity"], req["unit"], "issued_quantity")
            remaining_before = max(0, planned_grams - issued_grams)
            ingredient_id = str(req["ingredient_id"])
            cur.execute(
                """
                SELECT ingredient_id, ingredient_name, current_stock, min_stock, unit
                FROM inventory_stocks
                WHERE ingredient_id = %s
                FOR UPDATE
                """,
                (ingredient_id,),
            )
            stock = cur.fetchone()
            if not stock:
                raise NotFoundError("Kartu stok bahan belum memiliki ingredient_id canonical.")
            deducted = _from_grams(actual, stock["unit"])
            current = _number(stock["current_stock"], "current_stock")
            minimum = _number(stock["min_stock"], "min_stock")
            if deducted > current:
                raise ConflictError(
                    f"Pemakaian {deducted:g} {stock['unit']} melebihi stok tersedia {current:g} {stock['unit']}."
                )
            lot_allocations = (
                _allocate_lots(
                    cur,
                    ingredient_id=ingredient_id,
                    unit=str(stock["unit"]),
                    quantity=deducted,
                    requested_lot_id=lot_id,
                )
                if lot_tracking_ready
                else []
            )
            event_lot_id = lot_allocations[0]["lot_id"] if len(lot_allocations) == 1 else None
            remaining_stock = round(current - deducted, 4)
            stock_status = "HABIS" if remaining_stock <= 0 else "MENIPIS" if remaining_stock <= minimum else "AMBIL_AMAN"
            cur.execute(
                """
                INSERT INTO weigh_events
                    (batch_id, requirement_id, ingredient_id, lot_id,
                     planned_grams, tare_grams, actual_net_grams,
                     scale_source, device_id, operator_id, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING weigh_event_id
                """,
                (batch_id, requirement_id, ingredient_id, event_lot_id,
                 max(0.0001, remaining_before), tare, actual,
                 scale_source, device_id, actor_id, idempotency_key.strip()),
            )
            event = cur.fetchone()
            event_id = str(event["weigh_event_id"])
            cur.execute(
                """
                UPDATE inventory_stocks
                SET current_stock = %s, status = %s, updated_at = NOW()
                WHERE ingredient_id = %s
                """,
                (remaining_stock, stock_status, ingredient_id),
            )
            movement_note = " | ".join(value for value in [
                f"Production batch: {batch_id}",
                f"Tare: {tare:g} g",
                note.strip(),
            ] if value)
            if lot_tracking_ready:
                cur.execute(
                    """
                    INSERT INTO inventory_movements
                        (ingredient_id, ingredient_name_snapshot, movement_type, quantity,
                         unit, idempotency_key, actor_id, note,
                         production_batch_id, weigh_event_id, lot_id)
                    VALUES (%s, %s, 'CONSUMPTION', %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING movement_id
                    """,
                    (ingredient_id, stock["ingredient_name"], -deducted, stock["unit"],
                     f"weigh:{idempotency_key.strip()}", actor_id, movement_note,
                     batch_id, event_id, event_lot_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO inventory_movements
                        (ingredient_id, ingredient_name_snapshot, movement_type, quantity,
                         unit, idempotency_key, actor_id, note,
                         production_batch_id, weigh_event_id)
                    VALUES (%s, %s, 'CONSUMPTION', %s, %s, %s, %s, %s, %s, %s)
                    RETURNING movement_id
                    """,
                    (ingredient_id, stock["ingredient_name"], -deducted, stock["unit"],
                     f"weigh:{idempotency_key.strip()}", actor_id, movement_note,
                     batch_id, event_id),
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
                        (movement["movement_id"], allocation["lot_id"], ingredient_id,
                         allocation["quantity"], allocation["unit"]),
                    )
            # actual is grams; requirement units are guaranteed to be mass by
            # batch creation, so convert it before persisting issued_quantity.
            issued_after = issued_grams + _from_grams(actual, req["unit"])
            variance = issued_after - _number(req["planned_quantity"], "planned_quantity")
            cur.execute(
                """
                UPDATE production_batch_requirements
                SET issued_quantity = %s, variance_quantity = %s, updated_at = NOW()
                WHERE requirement_id = %s
                """,
                (issued_after, variance, requirement_id),
            )
            cur.execute(
                "UPDATE production_batches SET status = 'IN_PROGRESS', updated_at = NOW() WHERE batch_id = %s",
                (batch_id,),
            )
            return {
                "weigh_event_id": event_id,
                "movement_id": str(movement["movement_id"]),
                "batch_id": batch_id,
                "requirement_id": requirement_id,
                "ingredient_id": ingredient_id,
                "ingredient_name": str(req["ingredient_name"]),
                "actual_net_grams": actual,
                "stock_quantity_deducted": deducted,
                "stock_unit": str(stock["unit"]),
                "current_stock": remaining_stock,
                "stock_status": stock_status,
                "issued_grams": round(_grams(issued_after, req["unit"], "issued_quantity"), 4),
                "remaining_planned_grams": round(max(0, planned_grams - _grams(issued_after, req["unit"], "issued_quantity")), 4),
                "idempotent": False,
                "lot_allocations": lot_allocations,
            }


def complete_batch(*, batch_id: str, actor_id: str) -> dict[str, Any]:
    """Close a batch only after every planned material has been issued at least once."""
    _assert_phase_migration()
    try:
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT batch_id, status
                    FROM production_batches
                    WHERE batch_id = %s
                    FOR UPDATE
                    """,
                    (batch_id,),
                )
                batch = cur.fetchone()
                if not batch:
                    raise NotFoundError("Production batch tidak ditemukan.")
                if batch["status"] == "COMPLETED":
                    return get_batch(batch_id)
                if batch["status"] == "CANCELLED":
                    raise ConflictError("Batch yang dibatalkan tidak dapat diselesaikan.")

                cur.execute(
                    """
                    SELECT requirement_id, ingredient_name, planned_quantity, unit,
                           issued_quantity
                    FROM production_batch_requirements
                    WHERE batch_id = %s
                    FOR UPDATE
                    """,
                    (batch_id,),
                )
                requirements = cur.fetchall()
                if not requirements:
                    raise ValidationError("Batch tidak memiliki material requirement.")
                missing = [
                    str(row["ingredient_name"])
                    for row in requirements
                    if float(row.get("issued_quantity") or 0) <= 0
                ]
                if missing:
                    raise ConflictError(
                        "Batch belum dapat diselesaikan karena masih ada bahan yang belum ditimbang.",
                        details={"missing_ingredients": missing},
                    )
                cur.execute(
                    """
                    UPDATE production_batches
                    SET status = 'COMPLETED', updated_at = NOW()
                    WHERE batch_id = %s
                    RETURNING batch_id, status, updated_at
                    """,
                    (batch_id,),
                )
                updated = cur.fetchone()
                if not updated:
                    raise DatabaseError("Batch gagal diperbarui.")
                # Keep the operator identity in the audit trail without making
                # audit logging a reason to lose the inventory transaction.
                cur.execute(
                    """
                    INSERT INTO audit_log
                        (actor_id, action, table_name, record_id, before_val, after_val, source)
                    VALUES (%s, 'PRODUCTION_BATCH_COMPLETED', 'production_batches', %s,
                            NULL, %s::jsonb, 'production_batch_service')
                    """,
                    (actor_id, batch_id, '{"status":"COMPLETED"}'),
                )
        return get_batch(batch_id)
    except (ConflictError, NotFoundError, ValidationError, DatabaseError):
        raise
    except Exception as exc:
        raise DatabaseError("Gagal menyelesaikan production batch.") from exc

