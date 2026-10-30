"""Live operational context for the Langflow custom data-source component.

Langflow must not receive Supabase credentials. It calls the FastAPI internal
endpoint, while this service reads the same Postgres source of truth as the
web/API application. This module deliberately fails closed: database/query
errors are raised instead of returning synthetic sample data.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.repositories import supabase as db
from app.utils.time import now_wib


MAX_LIVE_ORDER_CONTEXT_ROWS = 2000


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return [value] if value.strip() else []
        return parsed if isinstance(parsed, list) else [parsed]
    return [value]


def _restriction_labels(value: Any) -> list[str]:
    labels: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("code") or "").strip()
        else:
            label = str(item or "").strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def _unit_to_grams(quantity: Any, unit: Any) -> float | None:
    try:
        amount = float(quantity)
    except (TypeError, ValueError):
        return None
    normalized = str(unit or "").strip().lower()
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
    }.get(normalized)
    return amount * factor if factor is not None else None


def _unit_to_kg(quantity: Any, unit: Any) -> float | None:
    try:
        amount = float(quantity)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(amount):
        return None
    normalized = str(unit or "").strip().lower()
    factor = {
        "mg": 0.000001,
        "g": 0.001,
        "gram": 0.001,
        "grams": 0.001,
        "kg": 1.0,
        "kilogram": 1.0,
        "kilograms": 1.0,
    }.get(normalized)
    return amount * factor if factor is not None else None


def _required_text(row: dict[str, Any], field: str, context: str) -> str:
    value = row.get(field)
    if value is None:
        raise RuntimeError(f"{context} tidak memiliki {field}; live context ditahan.")
    text = str(value).strip()
    if not text:
        raise RuntimeError(f"{context} memiliki {field} kosong; live context ditahan.")
    return text


def _required_nonnegative_number(
    row: dict[str, Any],
    field: str,
    context: str,
    *,
    integer: bool = False,
) -> float:
    value = row.get(field)
    if isinstance(value, bool):
        raise RuntimeError(f"{context} memiliki {field} invalid; live context ditahan.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{context} memiliki {field} invalid; live context ditahan.") from exc
    if not math.isfinite(number) or number < 0 or (integer and not number.is_integer()):
        raise RuntimeError(f"{context} memiliki {field} invalid; live context ditahan.")
    return number


def _load_menus() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    menu_rows = db.execute(
        """
        SELECT menu_id, hari, nama_menu, deskripsi, published, option_index
        FROM menus
        WHERE published = TRUE
        ORDER BY hari, option_index, nama_menu
        """
    )
    ingredient_rows = db.execute(
        """
        SELECT mi.menu_id, mi.nama, mi.sort_order,
               i.allergen_codes AS allergen_codes
        FROM menu_ingredients mi
        LEFT JOIN ingredients i ON i.ingredient_id = mi.ingredient_id
        WHERE mi.menu_id = ANY(%s)
        ORDER BY mi.menu_id, mi.sort_order
        """,
        ([str(row["menu_id"]) for row in menu_rows],),
    ) if menu_rows else []
    allergen_rows = db.execute(
        "SELECT code, label FROM allergens WHERE active = TRUE"
    )
    labels = {str(row["code"]): str(row["label"]) for row in allergen_rows}

    ingredients_by_menu: dict[str, list[dict[str, Any]]] = defaultdict(list)
    codes_by_menu: dict[str, set[str]] = defaultdict(set)
    menu_allergen_rows: dict[str, int] = defaultdict(int)
    for row in ingredient_rows:
        menu_id = _required_text(row, "menu_id", "Live menu ingredient")
        name = _required_text(row, "nama", f"Live ingredient menu {menu_id}")
        sort_order = _required_nonnegative_number(
            row, "sort_order", f"Live ingredient menu {menu_id}", integer=True
        )
        ingredients_by_menu[menu_id].append({
            "name": name,
            "sort_order": int(sort_order),
        })
        menu_allergen_rows[menu_id] += 1
        if row.get("allergen_codes") is None:
            raise RuntimeError(
                f"Live ingredient menu {menu_id} tidak memiliki allergen mapping; live context ditahan."
            )
        for code in _as_list(row.get("allergen_codes")):
            normalized = str(code or "").strip()
            if normalized:
                codes_by_menu[menu_id].add(normalized)

    menus: list[dict[str, Any]] = []
    menu_index: dict[str, dict[str, Any]] = {}
    for row in menu_rows:
        menu_id = _required_text(row, "menu_id", "Live menu")
        hari = _required_text(row, "hari", f"Live menu {menu_id}")
        name = _required_text(row, "nama_menu", f"Live menu {menu_id}")
        if not menu_allergen_rows.get(menu_id):
            raise RuntimeError(
                f"Live menu {menu_id} tidak memiliki ingredient mapping; live context ditahan."
            )
        codes = sorted(codes_by_menu.get(menu_id, set()))
        item = {
            "menu_id": menu_id,
            "hari": hari,
            "name": name,
            "deskripsi": row.get("deskripsi"),
            "ingredients": [i["name"] for i in ingredients_by_menu.get(menu_id, [])],
            "allergen_codes": codes,
            "allergens": [labels.get(code, code) for code in codes],
            "allergen_mapping_status": (
                "AVAILABLE" if menu_allergen_rows.get(menu_id, 0) else "NO_INGREDIENT_ROWS"
            ),
            "recipe_verification_status": "UNKNOWN",
        }
        menus.append(item)
        menu_index[menu_id] = item
    return menus, menu_index


def _add_recipe_metadata(
    menus: list[dict[str, Any]],
    menu_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    recipe_rows = db.execute(
        """
        SELECT DISTINCT ON (menu_id)
               menu_id, recipe_version_id, status, cross_contact_risk
        FROM recipe_versions
        ORDER BY menu_id, version_no DESC
        """
    )
    for row in recipe_rows:
        menu = menu_index.get(str(row["menu_id"]))
        if menu:
            menu["recipe_verification_status"] = str(row.get("status") or "UNKNOWN")
            menu["cross_contact_risk"] = str(row.get("cross_contact_risk") or "UNKNOWN")

    verified_recipe_ids = [
        str(row["recipe_version_id"])
        for row in recipe_rows
        if str(row.get("status")) == "VERIFIED"
    ]
    component_rows = db.execute(
        """
        SELECT rc.recipe_version_id, rv.menu_id, i.name AS ingredient_name,
               rc.quantity, rc.unit, rc.verification_status,
               i.verification_status AS ingredient_status
        FROM recipe_components rc
        JOIN recipe_versions rv ON rv.recipe_version_id = rc.recipe_version_id
        LEFT JOIN ingredients i ON i.ingredient_id = rc.ingredient_id
        WHERE rc.recipe_version_id = ANY(%s)
        ORDER BY rv.menu_id, rc.sort_order
        """,
        (verified_recipe_ids,),
    ) if verified_recipe_ids else []

    bom: dict[str, dict[str, float]] = defaultdict(dict)
    unresolved: list[dict[str, Any]] = []
    for row in component_rows:
        menu_id = str(row["menu_id"])
        menu = menu_index.get(menu_id)
        if not menu:
            continue
        menu["ingredients"].append(str(row.get("ingredient_name") or ""))
        grams = _unit_to_grams(row.get("quantity"), row.get("unit"))
        if (
            not row.get("ingredient_name")
            or grams is None
            or str(row.get("verification_status")) != "VERIFIED"
            or str(row.get("ingredient_status")) != "VERIFIED"
        ):
            unresolved.append({
                "menu_id": menu_id,
                "ingredient": row.get("ingredient_name") or "",
                "unit": row.get("unit") or "",
                "reason": "recipe_component_not_fully_verified",
            })
            continue
        ingredient = str(row["ingredient_name"])
        bom[menu_id][ingredient] = bom[menu_id].get(ingredient, 0.0) + grams

    for menu in menus:
        menu["ingredients"] = list(dict.fromkeys(menu["ingredients"]))
    return dict(bom), unresolved


def _load_customers() -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT c.customer_id
        FROM customers c
        WHERE c.role = 'customer' AND c.status = 'active'
        ORDER BY c.created_at
        """
    )
    return [{"customer_id": _required_text(row, "customer_id", "Live customer")} for row in rows]


def _load_orders() -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT o.order_id, o.customer_id, o.customer_name,
               o.created_at::DATE AS order_date,
               m.nama_menu AS menu,
               oi.quantity AS quantity,
               oi.unit AS unit,
               o.meal_count AS order_meal_count,
               o.total AS total
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN menus m ON m.menu_id = oi.menu_id
        WHERE o.status <> 'CANCELLED'
          AND o.payment_status = 'PAID'
        ORDER BY o.created_at DESC
        LIMIT 2001
        """
    )
    if len(rows) > MAX_LIVE_ORDER_CONTEXT_ROWS:
        raise RuntimeError(
            "Live order context melebihi batas aman; context ditahan agar CRM/RFM "
            "tidak memakai subset data tanpa penanda."
        )
    normalized: list[dict[str, Any]] = []
    for row in rows:
        order_id = str(row.get("order_id") or "").strip()
        customer_id = str(row.get("customer_id") or "").strip()
        customer_name = str(row.get("customer_name") or "").strip()
        menu = str(row.get("menu") or "").strip()
        order_date = row.get("order_date")
        if not order_id or not customer_id or not customer_name or not menu or order_date is None:
            raise RuntimeError(
                "Live order context memiliki identity/menu/date yang tidak lengkap; context ditahan."
            )
        try:
            datetime.fromisoformat(str(order_date)[:10])
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Live order context memiliki order_date invalid; context ditahan."
            ) from exc
        raw_quantity = row.get("quantity")
        try:
            quantity = float(raw_quantity)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Live order memiliki quantity invalid; context ditahan.") from exc
        if not math.isfinite(quantity) or not quantity.is_integer() or quantity < 0:
            raise RuntimeError("Live order quantity harus integer dan tidak negatif; context ditahan.")
        unit = str(row.get("unit") or "").strip()
        if not unit:
            raise RuntimeError("Live order tidak memiliki unit; context ditahan.")
        raw_meal_count = row.get("order_meal_count")
        if isinstance(raw_meal_count, bool):
            raise RuntimeError("Live order memiliki meal_count invalid; context ditahan.")
        try:
            meal_count = float(raw_meal_count)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Live order memiliki meal_count invalid; context ditahan.") from exc
        if not math.isfinite(meal_count) or not meal_count.is_integer() or meal_count < 0:
            raise RuntimeError("Live order memiliki meal_count invalid; context ditahan.")
        raw_total = row.get("total")
        try:
            total = float(raw_total)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Live order memiliki total invalid; context ditahan.") from exc
        if not math.isfinite(total) or total < 0:
            raise RuntimeError("Live order memiliki total invalid; context ditahan.")
        normalized.append({
            "order_id": order_id,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "order_date": order_date,
            "menu": menu,
            "quantity": int(quantity),
            "unit": unit,
            "order_meal_count": int(meal_count),
            "total": total,
        })
    return normalized


def _load_stock() -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    rows = db.execute(
        "SELECT ingredient_name, current_stock, unit, status FROM inventory_stocks ORDER BY ingredient_name"
    )
    stock: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = _required_text(row, "ingredient_name", "Live stock")
        if name in stock:
            raise RuntimeError(f"Live stock memiliki ingredient duplikat {name}; live context ditahan.")
        unit = _required_text(row, "unit", f"Live stock {name}")
        raw_status = _required_text(row, "status", f"Live stock {name}")
        kg = _unit_to_kg(row.get("current_stock"), row.get("unit"))
        if kg is None or kg < 0:
            raise RuntimeError(f"Live stock {name} memiliki current_stock/unit invalid; live context ditahan.")
        stock[name] = kg * 1000.0
        metadata[name] = {
            "unit": unit,
            "status": raw_status,
            "current_stock": float(row["current_stock"]),
        }
    return stock, metadata


def _load_suppliers() -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT s.name, si.ingredient_name, si.unit, si.price_per_unit,
               si.moq, si.lead_time_days
        FROM supplier_items si
        JOIN suppliers s ON s.supplier_id = si.supplier_id
        WHERE s.status = 'active'
        ORDER BY si.ingredient_name, s.name
        """
    )
    suppliers: list[dict[str, Any]] = []
    for row in rows:
        name = _required_text(row, "name", "Live supplier")
        ingredient = _required_text(row, "ingredient_name", f"Live supplier {name}")
        unit = _required_text(row, "unit", f"Live supplier {name}/{ingredient}")
        price = _required_nonnegative_number(
            row, "price_per_unit", f"Live supplier {name}/{ingredient}"
        )
        moq = _required_nonnegative_number(
            row, "moq", f"Live supplier {name}/{ingredient}"
        )
        lead_time = _required_nonnegative_number(
            row, "lead_time_days", f"Live supplier {name}/{ingredient}"
        )
        price_kg = _unit_to_kg(price, unit)
        moq_kg = _unit_to_kg(moq, unit)
        if price_kg is None or moq_kg is None:
            raise RuntimeError(
                f"Live supplier {name}/{ingredient} memiliki unit tidak didukung; live context ditahan."
            )
        suppliers.append({
            "name": name,
            "ingredient": ingredient,
            "unit": unit,
            "price_per_kg": price_kg,
            "moq_kg": moq_kg,
            "lead_time_days": int(lead_time) if lead_time.is_integer() else lead_time,
        })
    return suppliers


def build_live_context() -> dict[str, Any]:
    """Build the strict, non-synthetic state consumed by Langflow."""
    if not db.is_connected():
        raise RuntimeError("Supabase tidak terhubung; live context tidak tersedia.")
    if not db.check_migrations():
        raise RuntimeError("Migration aplikasi belum lengkap; live context ditahan.")

    menus, menu_index = _load_menus()
    if not menus:
        raise RuntimeError("Katalog menu live kosong; live context ditahan.")
    bom, bom_unresolved = _add_recipe_metadata(menus, menu_index)
    stock, stock_metadata = _load_stock()
    suppliers = _load_suppliers()
    customer_profiles = _load_customers()
    # The LIVE graph is an internal aggregate-operations context, not a
    # customer-scoped consultation. Do not send every customer's dietary
    # passport to Langflow: the downstream dietary node expands this into a
    # customer x menu matrix, which both leaks unnecessary PII and inflates
    # the LLM prompt. Customer-specific safety decisions stay on FastAPI.
    customers: list[dict[str, Any]] = []
    orders = _load_orders()
    # Keep Langflow's operational forecast on the same source of truth as the
    # admin/API backtest. This is a read-only calculation; stale data remains
    # labelled and is never converted into an operational snapshot.
    from app.services.forecast_service import build_live_forecast_report

    forecast_backtest = {
        "7d": build_live_forecast_report(horizon_days=7),
        "30d": build_live_forecast_report(horizon_days=30),
    }

    warnings: list[str] = []
    if bom_unresolved or any(
        menu.get("recipe_verification_status") != "VERIFIED" for menu in menus
    ):
        warnings.append(
            "Sebagian BOM belum verified; forecast/inventory tidak boleh dianggap lengkap."
        )
    warnings.append(
        "Forecast context hanya memakai order PAID non-CANCELLED dengan quantity/unit dari order_items."
    )
    forecast_dependency_metadata: dict[str, Any] = {}
    for horizon, report in forecast_backtest.items():
        metadata = report.get("dependency_metadata")
        forecast_dependency_metadata[horizon] = metadata
        if not isinstance(metadata, dict):
            warnings.append(
                f"Forecast {horizon}: dependency metadata tidak tersedia; jangan gunakan sebagai angka operasional."
            )
            continue
        warnings.append(
            f"Forecast {horizon} dependency: paid_order_count={metadata.get('paid_order_count')}, "
            f"paid_order_item_count={metadata.get('paid_order_item_count')}, "
            f"invalid_quantity_item_count={metadata.get('invalid_quantity_item_count')}, "
            f"missing_unit_item_count={metadata.get('missing_unit_item_count')}, "
            f"missing_menu_id_item_count={metadata.get('missing_menu_id_item_count')}, "
            f"latest_paid_date={metadata.get('latest_paid_date')}, "
            f"latest_non_cancelled_date={metadata.get('latest_non_cancelled_date')}."
        )
    warnings.append(
        "Profil dietary individual tidak dikirim ke graph internal; keputusan safety customer harus melalui FastAPI yang terotorisasi."
    )

    order_count = len({str(order.get("order_id")) for order in orders if order.get("order_id")})

    return _json_safe({
        "_data_mode": "live",
        "_source": "supabase_postgres_via_fastapi",
        "_generated_at": now_wib(),
        "today": now_wib().date(),
        "customers": customers,
        "orders": orders,
        "menu": menus,
        "bom": bom,
        "bom_unresolved": bom_unresolved,
        "stock": stock,
        "stock_metadata": stock_metadata,
        "suppliers": suppliers,
        "forecast_backtest": forecast_backtest,
        "forecast_dependency_metadata": forecast_dependency_metadata,
        "counts": {
            "customers": len(customer_profiles),
            "orders": order_count,
            "order_items": len(orders),
            "menus": len(menus),
            "bom_menus": len(bom),
            "stock_items": len(stock),
            "suppliers": len(suppliers),
        },
        "customer_profile_context": "omitted_internal_aggregate",
        "warnings": warnings,
    })
