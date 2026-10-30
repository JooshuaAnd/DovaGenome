"""Auditable BOM explosion and replenishment readiness.

This module is intentionally separate from the legacy analytics facade. It
never invents ingredient consumption, lead time, stock, or supplier data. A
numeric safety-stock/ROP plan is returned only when the latest recipe for each
forecasted menu is verified, units are convertible, the forecast is fresh,
and canonical inventory/supplier records exist.

ROQ/EOQ is deliberately not calculated here: the current schema does not
provide ordering cost, holding cost, or pack-size constraints.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any

from app.repositories import supabase as db
from app.services import forecast_service


CALCULATION_VERSION = "inventory_replenishment_v1"
BACKTEST_CALCULATION_VERSION = "inventory_backtest_v1"
SERVICE_LEVEL = 0.95
Z_SCORE = 1.65


class InventoryPlanUnavailable(RuntimeError):
    """The live inventory plan cannot be built without making assumptions."""


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _unit_to_grams(value: Any, unit: Any) -> float | None:
    amount = _as_float(value)
    if amount is None:
        return None
    factor = {
        "mg": 0.001,
        "milligram": 0.001,
        "milligrams": 0.001,
        "g": 1.0,
        "gram": 1.0,
        "grams": 1.0,
        "kg": 1000.0,
        "kilogram": 1000.0,
        "kilograms": 1000.0,
    }.get(str(unit or "").strip().lower())
    return amount * factor if factor is not None else None


def _grams_to_unit(value: float, unit: Any) -> float | None:
    one_unit = _unit_to_grams(1, unit)
    return value / one_unit if one_unit else None


def _population_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _unique_messages(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _backtest_report(
    *,
    status: str,
    readiness: dict[str, Any],
    warnings: list[str],
    metrics: dict[str, Any] | None = None,
    ingredients: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a non-operational inventory policy evaluation report.

    This report is deliberately separate from ``build_replenishment_plan``.
    It evaluates an explicitly supplied historical policy trace; it does not
    turn the current stock table into historical state and it never fills in
    missing quantities with zero.
    """
    return {
        "status": status,
        "data_mode": "backtest",
        "source": "explicit_inventory_history",
        "calculation_version": BACKTEST_CALCULATION_VERSION,
        "operational": False,
        "readiness": readiness,
        "metrics": metrics or {},
        "ingredients": ingredients or [],
        "warnings": _unique_messages(warnings),
    }


def _strict_backtest_number(
    row: dict[str, Any],
    field: str,
    *,
    minimum: float | None = 0.0,
) -> tuple[float | None, str | None]:
    """Read a required finite number without applying a missing-value default."""
    if field not in row:
        return None, f"missing_{field}"
    value = row.get(field)
    if isinstance(value, bool):
        return None, f"invalid_{field}"
    parsed = _as_float(value)
    if parsed is None or (minimum is not None and parsed < minimum):
        return None, f"invalid_{field}"
    return parsed, None


def _parse_backtest_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def build_inventory_backtest(
    history_rows: list[dict[str, Any]],
    *,
    min_history_days: int = 2,
) -> dict[str, Any]:
    """Evaluate historical stockout, fill-rate, and excess-stock outcomes.

    Each row must describe one ingredient-day and explicitly contain:

    ``ingredient_id``, ``date``, ``opening_stock``, ``receipt_quantity``,
    ``adjustment_quantity``, ``actual_demand``, ``forecast_demand``,
    ``reorder_point``, and ``target_stock``.

    ``opening_stock`` on the next day must equal the prior calculated closing
    stock. A receipt or adjustment must be represented in that day's explicit
    fields. This prevents the evaluator from silently reconciling gaps in the
    inventory ledger. The result is an analysis artifact, never an operational
    SS/ROP recommendation.
    """
    if not isinstance(min_history_days, int) or min_history_days < 2:
        raise ValueError("min_history_days harus integer >= 2.")
    if not isinstance(history_rows, list) or not history_rows:
        return _backtest_report(
            status="NO_DATA",
            readiness={
                "row_count": 0,
                "ingredient_count": 0,
                "valid_row_count": 0,
                "min_history_days": min_history_days,
            },
            warnings=["Riwayat inventory policy belum tersedia; backtest tidak dijalankan."],
        )
    required_fields = (
        "opening_stock",
        "receipt_quantity",
        "adjustment_quantity",
        "actual_demand",
        "forecast_demand",
        "reorder_point",
        "target_stock",
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    invalid_reasons: list[str] = []
    seen_keys: set[tuple[str, date]] = set()

    for index, raw in enumerate(history_rows):
        if not isinstance(raw, dict):
            invalid_reasons.append(f"row_{index}_not_object")
            continue
        ingredient_id = str(raw.get("ingredient_id") or "").strip()
        if not ingredient_id:
            invalid_reasons.append(f"row_{index}_missing_ingredient_id")
            continue
        observation_date = _parse_backtest_date(raw.get("date"))
        if observation_date is None:
            invalid_reasons.append(f"row_{index}_invalid_date")
            continue
        key = (ingredient_id, observation_date)
        if key in seen_keys:
            invalid_reasons.append(f"duplicate_{ingredient_id}_{observation_date.isoformat()}")
            continue
        seen_keys.add(key)

        parsed: dict[str, Any] = {
            "ingredient_id": ingredient_id,
            "date": observation_date,
        }
        unit = str(raw.get("unit") or "").strip().lower()
        if not unit:
            invalid_reasons.append(f"row_{index}_missing_unit")
            continue
        parsed["unit"] = unit
        row_invalid = False
        for field in required_fields:
            minimum = None if field == "adjustment_quantity" else 0.0
            value, reason = _strict_backtest_number(raw, field, minimum=minimum)
            if reason:
                invalid_reasons.append(f"row_{index}_{reason}")
                row_invalid = True
            else:
                parsed[field] = value
        if row_invalid:
            continue
        if parsed["target_stock"] < parsed["reorder_point"]:
            invalid_reasons.append(f"row_{index}_target_below_reorder_point")
            continue
        available = (
            parsed["opening_stock"]
            + parsed["receipt_quantity"]
            + parsed["adjustment_quantity"]
        )
        if available < 0:
            invalid_reasons.append(f"row_{index}_negative_available_stock")
            continue
        parsed["available_stock"] = available
        parsed["fulfilled_demand"] = min(available, parsed["actual_demand"])
        parsed["unfulfilled_demand"] = max(
            0.0, parsed["actual_demand"] - available
        )
        parsed["closing_stock"] = max(
            0.0, available - parsed["actual_demand"]
        )
        parsed["stockout"] = parsed["unfulfilled_demand"] > 1e-9
        parsed["excess_stock"] = max(
            0.0, parsed["closing_stock"] - parsed["target_stock"]
        )
        grouped[ingredient_id].append(parsed)

    readiness = {
        "row_count": len(history_rows),
        "ingredient_count": len(grouped),
        "valid_row_count": sum(len(rows) for rows in grouped.values()),
        "min_history_days": min_history_days,
        "invalid_reasons": invalid_reasons,
    }
    if invalid_reasons:
        return _backtest_report(
            status="INVALID_HISTORY",
            readiness=readiness,
            warnings=[
                "Riwayat inventory tidak lengkap atau tidak konsisten; metrik ditahan.",
            ],
        )

    per_ingredient: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []
    insufficient: list[str] = []
    for ingredient_id, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: row["date"])
        units = {row["unit"] for row in rows}
        if len(units) != 1:
            invalid_reasons.append(f"{ingredient_id}_mixed_units")
            continue
        continuity_breaks: list[str] = []
        for previous, current in zip(rows, rows[1:]):
            if abs(current["opening_stock"] - previous["closing_stock"]) > 1e-9:
                continuity_breaks.append(current["date"].isoformat())
        if continuity_breaks:
            invalid_reasons.extend(
                f"{ingredient_id}_opening_stock_break_{value}"
                for value in continuity_breaks
            )
            continue
        if len(rows) < min_history_days:
            insufficient.append(ingredient_id)
            continue

        demand_total = sum(row["actual_demand"] for row in rows)
        fulfilled_total = sum(row["fulfilled_demand"] for row in rows)
        unfulfilled_total = sum(row["unfulfilled_demand"] for row in rows)
        absolute_forecast_error = sum(
            abs(row["actual_demand"] - row["forecast_demand"])
            for row in rows
        )
        excess_total = sum(row["excess_stock"] for row in rows)
        stockout_days = sum(1 for row in rows if row["stockout"])
        excess_days = sum(1 for row in rows if row["excess_stock"] > 1e-9)
        ingredient_metrics = {
            "ingredient_id": ingredient_id,
            "days": len(rows),
            "start_date": rows[0]["date"].isoformat(),
            "end_date": rows[-1]["date"].isoformat(),
            "actual_demand": round(demand_total, 6),
            "fulfilled_demand": round(fulfilled_total, 6),
            "unfulfilled_demand": round(unfulfilled_total, 6),
            "stockout_days": stockout_days,
            "stockout_rate": round(stockout_days / len(rows), 6),
            "fill_rate": (
                round(fulfilled_total / demand_total, 6)
                if demand_total > 0
                else None
            ),
            "fill_rate_status": "OK" if demand_total > 0 else "UNDEFINED_ZERO_DEMAND",
            "excess_stock_quantity": round(excess_total, 6),
            "excess_stock_average": round(excess_total / len(rows), 6),
            "excess_stock_days": excess_days,
            "forecast_wape": (
                round(absolute_forecast_error / demand_total, 6)
                if demand_total > 0
                else None
            ),
            "forecast_wape_status": (
                "OK" if demand_total > 0 else "UNDEFINED_ZERO_ACTUAL"
            ),
        }
        per_ingredient.append(ingredient_metrics)
        aggregate_rows.extend(rows)

    if invalid_reasons:
        readiness["invalid_reasons"] = invalid_reasons
        return _backtest_report(
            status="INVALID_HISTORY",
            readiness=readiness,
            warnings=[
                "Riwayat inventory memiliki gap opening/closing; metrik ditahan.",
            ],
        )
    if insufficient:
        readiness["insufficient_history_ingredient_ids"] = sorted(insufficient)
        return _backtest_report(
            status="INSUFFICIENT_HISTORY",
            readiness=readiness,
            warnings=[
                "Histori per bahan belum mencapai minimum hari untuk backtest.",
            ],
        )
    if not aggregate_rows:
        return _backtest_report(
            status="NO_DATA",
            readiness=readiness,
            warnings=["Tidak ada bahan dengan histori valid untuk backtest."],
        )

    demand_total = sum(row["actual_demand"] for row in aggregate_rows)
    fulfilled_total = sum(row["fulfilled_demand"] for row in aggregate_rows)
    unfulfilled_total = sum(row["unfulfilled_demand"] for row in aggregate_rows)
    excess_total = sum(row["excess_stock"] for row in aggregate_rows)
    stockout_days = sum(1 for row in aggregate_rows if row["stockout"])
    absolute_forecast_error = sum(
        abs(row["actual_demand"] - row["forecast_demand"])
        for row in aggregate_rows
    )
    metrics = {
        "days": len(aggregate_rows),
        "ingredient_count": len(per_ingredient),
        "actual_demand": round(demand_total, 6),
        "fulfilled_demand": round(fulfilled_total, 6),
        "unfulfilled_demand": round(unfulfilled_total, 6),
        "stockout_days": stockout_days,
        "stockout_rate": round(stockout_days / len(aggregate_rows), 6),
        "fill_rate": (
            round(fulfilled_total / demand_total, 6)
            if demand_total > 0
            else None
        ),
        "fill_rate_status": "OK" if demand_total > 0 else "UNDEFINED_ZERO_DEMAND",
        "excess_stock_quantity": round(excess_total, 6),
        "excess_stock_average": round(excess_total / len(aggregate_rows), 6),
        "forecast_wape": (
            round(absolute_forecast_error / demand_total, 6)
            if demand_total > 0
            else None
        ),
        "forecast_wape_status": "OK" if demand_total > 0 else "UNDEFINED_ZERO_ACTUAL",
    }
    all_dates = [row["date"] for row in aggregate_rows]
    readiness.update(
        {
            "start_date": min(all_dates).isoformat(),
            "end_date": max(all_dates).isoformat(),
        }
    )
    return _backtest_report(
        status="OK",
        readiness=readiness,
        metrics=metrics,
        ingredients=per_ingredient,
        warnings=[
            "Backtest ini mengevaluasi histori eksplisit dan bukan bukti bahwa SS/ROP live siap dipakai.",
        ],
    )


def _base_report(
    *,
    status: str,
    forecast_report: dict[str, Any],
    readiness: dict[str, Any],
    warnings: list[str],
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": CALCULATION_VERSION,
        "service_level": SERVICE_LEVEL,
        "z_score": Z_SCORE,
        "forecast_status": forecast_report.get("status"),
        "forecast_calculation_version": forecast_report.get("calculation_version"),
        "forecast_latest_observation_date": forecast_report.get("latest_observation_date"),
        "forecast_data_age_days": forecast_report.get("data_age_days"),
        "horizon_days": forecast_report.get("horizon_days"),
        "readiness": readiness,
        "items": items or [],
        "roq": {
            "status": "UNAVAILABLE",
            "reason_codes": [
                "ORDERING_COST_MISSING",
                "HOLDING_COST_MISSING",
                "PACK_SIZE_MISSING",
            ],
            "note": "ROQ/EOQ belum dihitung karena ordering cost, holding cost, dan pack size belum tersedia.",
        },
        "warnings": _unique_messages(warnings),
    }


def build_replenishment_plan(
    *,
    published_menu_ids: list[str],
    recipe_rows: list[dict[str, Any]],
    inventory_rows: list[dict[str, Any]],
    supplier_rows: list[dict[str, Any]],
    forecast_report: dict[str, Any],
) -> dict[str, Any]:
    """Build a strict replenishment report from already-loaded live records.

    The function is pure so its readiness gates and calculations can be tested
    without a database connection.
    """
    published = {str(menu_id) for menu_id in published_menu_ids if menu_id}
    forecast_series = [
        series for series in forecast_report.get("series", [])
        if str(series.get("series_key") or "") in published
    ]
    forecast_menu_ids = {str(series.get("series_key")) for series in forecast_series}

    latest_recipe: dict[str, dict[str, Any]] = {}
    components_by_menu: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in recipe_rows:
        menu_id = str(row.get("menu_id") or "")
        if not menu_id or menu_id not in published:
            continue
        latest_recipe.setdefault(menu_id, row)
        if row.get("ingredient_id") or row.get("child_recipe_version_id"):
            components_by_menu[menu_id].append(row)

    unresolved: list[dict[str, Any]] = []
    bom_by_menu: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for menu_id in sorted(forecast_menu_ids):
        recipe = latest_recipe.get(menu_id)
        if not recipe:
            unresolved.append({"menu_id": menu_id, "reason": "latest_recipe_missing"})
            continue
        if str(recipe.get("status") or "") != "VERIFIED":
            unresolved.append({
                "menu_id": menu_id,
                "reason": "latest_recipe_not_verified",
                "status": recipe.get("status"),
            })
            continue
        if str(recipe.get("yield_unit") or "").strip().lower() != "portion":
            unresolved.append({
                "menu_id": menu_id,
                "reason": "recipe_yield_unit_not_portion",
                "unit": recipe.get("yield_unit"),
            })
            continue
        yield_quantity = _as_float(recipe.get("yield_quantity"))
        if not yield_quantity or yield_quantity <= 0:
            unresolved.append({"menu_id": menu_id, "reason": "recipe_yield_invalid"})
            continue
        components = components_by_menu.get(menu_id, [])
        if not components:
            unresolved.append({"menu_id": menu_id, "reason": "recipe_components_missing"})
            continue
        for component in components:
            ingredient_id = str(component.get("ingredient_id") or "")
            if component.get("child_recipe_version_id"):
                unresolved.append({
                    "menu_id": menu_id,
                    "reason": "nested_bom_not_exploded",
                    "child_recipe_version_id": component.get("child_recipe_version_id"),
                })
                continue
            grams = _unit_to_grams(component.get("quantity"), component.get("unit"))
            if (
                not ingredient_id
                or not component.get("ingredient_name")
                or grams is None
                or grams <= 0
                or str(component.get("verification_status") or "") != "VERIFIED"
                or str(component.get("ingredient_status") or "") != "VERIFIED"
            ):
                unresolved.append({
                    "menu_id": menu_id,
                    "ingredient_id": ingredient_id,
                    "reason": "component_or_ingredient_not_verified_or_unit_unknown",
                })
                continue
            bom_by_menu[menu_id].append({
                "ingredient_id": ingredient_id,
                "ingredient_name": str(component.get("ingredient_name")),
                "grams_per_portion": grams / yield_quantity,
            })

    inventory_by_id = {
        str(row.get("ingredient_id")): row
        for row in inventory_rows
        if row.get("ingredient_id")
    }
    suppliers_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in supplier_rows:
        ingredient_id = str(row.get("ingredient_id") or "")
        lead_time = _as_float(row.get("lead_time_days"))
        if ingredient_id and lead_time is not None and lead_time >= 0:
            suppliers_by_id[ingredient_id].append(row)

    missing_inventory: set[str] = set()
    missing_supplier: set[str] = set()
    unsupported_stock_units: set[str] = set()
    ingredient_ids = {
        component["ingredient_id"]
        for components in bom_by_menu.values()
        for component in components
    }
    for ingredient_id in ingredient_ids:
        stock = inventory_by_id.get(ingredient_id)
        if not stock:
            missing_inventory.add(ingredient_id)
        elif _unit_to_grams(stock.get("current_stock"), stock.get("unit")) is None:
            unsupported_stock_units.add(str(stock.get("unit") or ""))
        if not suppliers_by_id.get(ingredient_id):
            missing_supplier.add(ingredient_id)

    readiness = {
        "published_menu_count": len(published),
        "forecast_menu_count": len(forecast_menu_ids),
        "latest_recipe_count": len(latest_recipe),
        "bom_ready_menu_count": len(bom_by_menu),
        "unresolved_bom": unresolved,
        "inventory_item_count": len(inventory_rows),
        "missing_inventory_ingredient_ids": sorted(missing_inventory),
        "unsupported_stock_units": sorted(unsupported_stock_units),
        "supplier_mapped_ingredient_count": len(suppliers_by_id),
        "missing_supplier_ingredient_ids": sorted(missing_supplier),
        "roq_status": "UNAVAILABLE",
    }
    warnings: list[str] = []
    if forecast_report.get("status") != "OK":
        warnings.append(
            f"Forecast berstatus {forecast_report.get('status')}; SS/ROP tidak dihitung sebagai rencana operasional."
        )
    if unresolved:
        warnings.append("BOM recipe terbaru belum verified atau unit/yield belum dapat diaudit.")
    if missing_inventory or unsupported_stock_units:
        warnings.append("Inventory canonical atau unit stok belum lengkap.")
    if missing_supplier:
        warnings.append("Supplier lead time aktif belum tersedia untuk semua bahan BOM.")

    blockers = bool(
        unresolved
        or missing_inventory
        or missing_supplier
        or unsupported_stock_units
        or forecast_report.get("status") != "OK"
    )
    if not forecast_series:
        return _base_report(
            status="NO_DATA",
            forecast_report=forecast_report,
            readiness=readiness,
            warnings=warnings + ["Tidak ada series menu live untuk dieksplode ke BOM."],
        )
    if blockers:
        return _base_report(
            status=("REQUIRES_VERIFICATION" if unresolved or missing_inventory or missing_supplier or unsupported_stock_units else forecast_report.get("status", "REQUIRES_VERIFICATION")),
            forecast_report=forecast_report,
            readiness=readiness,
            warnings=warnings,
        )

    daily_demand: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for series in forecast_series:
        menu_id = str(series["series_key"])
        for forecast_item in series.get("forecast", []):
            target_date = str(forecast_item.get("target_date") or "")
            portions = _as_float(forecast_item.get("quantity"))
            if not target_date or portions is None or portions < 0:
                continue
            for component in bom_by_menu[menu_id]:
                daily_demand[target_date][component["ingredient_id"]] += (
                    portions * component["grams_per_portion"]
                )

    items: list[dict[str, Any]] = []
    horizon_days = int(forecast_report.get("horizon_days") or len(daily_demand) or 1)
    for ingredient_id in sorted(ingredient_ids):
        stock = inventory_by_id[ingredient_id]
        stock_grams = _unit_to_grams(stock.get("current_stock"), stock.get("unit")) or 0.0
        values = [daily_demand[day].get(ingredient_id, 0.0) for day in sorted(daily_demand)]
        daily_average = sum(values) / len(values) if values else 0.0
        demand_std_dev = _population_std(values)
        lead_time_days = min(_as_float(row.get("lead_time_days")) or 0.0 for row in suppliers_by_id[ingredient_id])
        safety_stock_grams = Z_SCORE * demand_std_dev * math.sqrt(lead_time_days)
        reorder_point_grams = daily_average * lead_time_days + safety_stock_grams
        target_grams = daily_average * (lead_time_days + horizon_days) + safety_stock_grams
        shortage_grams = max(0.0, target_grams - stock_grams)
        unit = stock.get("unit") or ""
        items.append({
            "ingredient_id": ingredient_id,
            "ingredient_name": str(stock.get("ingredient_name") or ""),
            "unit": unit,
            "current_stock": round(_grams_to_unit(stock_grams, unit) or 0.0, 4),
            "daily_demand_average": round(_grams_to_unit(daily_average, unit) or 0.0, 4),
            "demand_std_dev": round(_grams_to_unit(demand_std_dev, unit) or 0.0, 4),
            "lead_time_days": lead_time_days,
            "safety_stock": round(_grams_to_unit(safety_stock_grams, unit) or 0.0, 4),
            "reorder_point_rop": round(_grams_to_unit(reorder_point_grams, unit) or 0.0, 4),
            "replenishment_target": round(_grams_to_unit(target_grams, unit) or 0.0, 4),
            "shortage_quantity": round(_grams_to_unit(shortage_grams, unit) or 0.0, 4),
            "status": "REORDER_REQUIRED" if stock_grams < reorder_point_grams else "OK",
            "supplier_candidates": [
                {
                    "supplier_id": str(row.get("supplier_id") or ""),
                    "supplier_name": str(row.get("supplier_name") or ""),
                    "lead_time_days": _as_float(row.get("lead_time_days")) or 0.0,
                    "unit": str(row.get("unit") or ""),
                    "moq": row.get("moq"),
                    "price_per_unit": row.get("price_per_unit"),
                    "rating": row.get("rating"),
                }
                for row in suppliers_by_id[ingredient_id]
            ],
        })
    return _base_report(
        status="OK",
        forecast_report=forecast_report,
        readiness=readiness,
        warnings=warnings,
        items=items,
    )


def build_live_inventory_replenishment_report() -> dict[str, Any]:
    """Build the live Phase 11 report without synthetic fallback data."""
    if not db.is_connected():
        raise InventoryPlanUnavailable("Supabase tidak terhubung; inventory plan ditahan.")
    if not db.check_migrations():
        raise InventoryPlanUnavailable("Migration aplikasi belum lengkap; inventory plan ditahan.")
    try:
        published_rows = db.execute(
            "SELECT menu_id FROM menus WHERE published = TRUE ORDER BY menu_id"
        )
        recipe_rows = db.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (rv.menu_id)
                       rv.menu_id, rv.recipe_version_id, rv.status,
                       rv.yield_quantity, rv.yield_unit
                FROM recipe_versions rv
                ORDER BY rv.menu_id, rv.version_no DESC
            )
            SELECT latest.menu_id, latest.recipe_version_id, latest.status,
                   latest.yield_quantity, latest.yield_unit,
                   rc.ingredient_id, rc.child_recipe_version_id,
                   rc.quantity, rc.unit,
                   rc.verification_status,
                   i.name AS ingredient_name,
                   i.verification_status AS ingredient_status
            FROM latest
            LEFT JOIN recipe_components rc
              ON rc.recipe_version_id = latest.recipe_version_id
            LEFT JOIN ingredients i
              ON i.ingredient_id = rc.ingredient_id
            ORDER BY latest.menu_id, rc.sort_order
            """
        )
        inventory_rows = db.execute(
            """
            SELECT ist.ingredient_id, ist.ingredient_name,
                   i.verification_status, ist.current_stock,
                   ist.unit, ist.updated_at
            FROM inventory_stocks ist
            LEFT JOIN ingredients i ON i.ingredient_id = ist.ingredient_id
            ORDER BY ist.ingredient_name
            """
        )
        supplier_rows = db.execute(
            """
            SELECT si.ingredient_id, si.supplier_id, s.name AS supplier_name,
                   s.rating, si.unit, si.moq, si.lead_time_days, si.price_per_unit
            FROM supplier_items si
            JOIN suppliers s ON s.supplier_id = si.supplier_id
            WHERE s.status = 'active' AND si.ingredient_id IS NOT NULL
            ORDER BY si.ingredient_id, si.lead_time_days, s.name
            """
        )
        forecast_report = forecast_service.build_live_forecast_report(horizon_days=7)
    except forecast_service.ForecastUnavailable as exc:
        raise InventoryPlanUnavailable(str(exc)) from exc
    except Exception as exc:
        raise InventoryPlanUnavailable(
            "Query BOM/inventory/supplier atau forecast gagal; inventory plan ditahan."
        ) from exc

    return build_replenishment_plan(
        published_menu_ids=[str(row.get("menu_id")) for row in published_rows],
        recipe_rows=recipe_rows,
        inventory_rows=inventory_rows,
        supplier_rows=supplier_rows,
        forecast_report=forecast_report,
    )
