"""Harden LIVE Langflow state transforms against missing-key defaults."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FLOW_PATH = ROOT / "langflow" / "Dova_Kitchen_Chef_BOB_LIVE.json"


def _node(payload: dict[str, Any], fragment: str) -> dict[str, Any]:
    matches = [
        node
        for node in payload["data"]["nodes"]
        if fragment in str(node.get("data", {}).get("node", {}).get("display_name", ""))
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one LIVE node for {fragment!r}, found {len(matches)}.")
    return matches[0]["data"]["node"]


def _replace_once(code: str, old: str, new: str, label: str) -> str:
    count = code.count(old)
    if count == 0 and new in code:
        return code
    if count != 1:
        raise RuntimeError(f"Expected one replacement for {label}, found {count}.")
    return code.replace(old, new, 1)


def _set_code(node: dict[str, Any], code: str, label: str) -> None:
    node["template"]["code"]["value"] = code
    node.setdefault("metadata", {})["code_hash"] = (
        f"dova-live-state-fail-closed-{label}-"
        + hashlib.sha256(code.encode()).hexdigest()[:12]
    )


def harden_rfm(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"].replace("\r\n", "\n")
    code = _replace_once(
        code,
        '"customer_id": c, "customer_name": names.get(c, c),',
        '"customer_id": c, "customer_name": names[c],',
        "RFM customer name default",
    )
    _set_code(node, code, "rfm")


def harden_forecast(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"].replace("\r\n", "\n")
    code = _replace_once(
        code,
        '    status = str(report.get("status") or "UNAVAILABLE")\n',
        '    status = report.get("status")\n'
        '    if not isinstance(status, str) or not status.strip():\n'
        '        raise ValueError("Forecast live kehilangan status; output ditahan.")\n'
        '    status = status.strip()\n',
        "forecast status default",
    )
    code = _replace_once(
        code,
        '    if status == "OK":\n        for series in report.get("series", []):\n',
        '    if status == "OK":\n'
        '        series_rows = report.get("series")\n'
        '        if not isinstance(series_rows, list):\n'
        '            raise ValueError("Forecast live kehilangan series; output ditahan.")\n'
        '        for series in series_rows:\n',
        "forecast series default",
    )
    code = _replace_once(
        code,
        '            series_unit = str(series.get("unit") or "").strip()\n'
        '            menu = str(series.get("label") or series.get("series_key") or "").strip()\n'
        '            if not series_unit or not menu:\n',
        '            if "unit" not in series or "label" not in series or "series_key" not in series:\n'
        '                raise ValueError("Forecast live kehilangan identitas series/unit.")\n'
        '            series_unit = str(series["unit"]).strip()\n'
        '            menu = str(series["label"]).strip()\n'
        '            if not series_unit or not menu or not str(series["series_key"]).strip():\n',
        "forecast series identity default",
    )
    old_warning_line = '        "warnings": report.get("warnings") or [],\n'
    generated_warning_line = (
        '        "warnings": report["warnings"] if isinstance(report.get("warnings"), list) else\n'
        '        (_ for _ in ()).throw(ValueError("Forecast live memiliki warnings invalid; output ditahan.")),\n'
    )
    clean_warning_line = '        "warnings": warnings,\n'
    if old_warning_line in code:
        code = code.replace(old_warning_line, generated_warning_line, 1)
    elif generated_warning_line in code:
        code = code.replace(generated_warning_line, clean_warning_line, 1)
    code = _replace_once(
        code,
        '        "warnings": report["warnings"] if isinstance(report.get("warnings"), list) else\n'
        '        (_ for _ in ()).throw(ValueError("Forecast live memiliki warnings invalid; output ditahan.")),\n',
        '        "warnings": warnings,\n',
        "forecast warnings expression",
    )
    code = _replace_once(
        code,
        '    if status == "OK":\n',
        '    warnings = report.get("warnings")\n'
        '    if not isinstance(warnings, list):\n'
        '        raise ValueError("Forecast live memiliki warnings invalid; output ditahan.")\n'
        '    if status == "OK":\n',
        "forecast warnings validation",
    )
    duplicate_warning_validation = (
        '    warnings = report.get("warnings")\n'
        '    if not isinstance(warnings, list):\n'
        '        raise ValueError("Forecast live memiliki warnings invalid; output ditahan.")\n'
        '    warnings = report.get("warnings")\n'
        '    if not isinstance(warnings, list):\n'
        '        raise ValueError("Forecast live memiliki warnings invalid; output ditahan.")\n'
    )
    single_warning_validation = (
        '    warnings = report.get("warnings")\n'
        '    if not isinstance(warnings, list):\n'
        '        raise ValueError("Forecast live memiliki warnings invalid; output ditahan.")\n'
    )
    if duplicate_warning_validation in code:
        code = code.replace(duplicate_warning_validation, single_warning_validation, 1)
    code = _replace_once(
        code,
        '            items.append({\n'
        '                "menu": menu,\n'
        '                "forecast_portions": round(quantity, 2),\n'
        '                "unit": series_unit,\n'
        '                "method": rows[0].get("method"),\n'
        '            })\n',
        '            method = rows[0].get("method")\n'
        '            if not isinstance(method, str) or not method.strip():\n'
        '                raise ValueError("Forecast live kehilangan method; output ditahan.")\n'
        '            items.append({\n'
        '                "menu": menu,\n'
        '                "forecast_portions": round(quantity, 2),\n'
        '                "unit": series_unit,\n'
        '                "method": method,\n'
        '            })\n',
        "forecast method default",
    )
    code = _replace_once(
        code,
        '        "status": status,\n'
        '        "horizon_days": report.get("horizon_days"),\n',
        '        "status": status,\n'
        '        "forecast_status": status,\n'
        '        "horizon_days": report.get("horizon_days"),\n',
        "forecast status alias for inventory contract",
    )
    code = _replace_once(
        code,
        '        reports = state.get("forecast_backtest") or {}\n',
        '        reports = state.get("forecast_backtest")\n'
        '        if not isinstance(reports, dict):\n'
        '            raise ValueError("FastAPI live context kehilangan forecast_backtest; flow dihentikan.")\n',
        "forecast state default",
    )
    _set_code(node, code, "forecast")


def harden_supplier(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"].replace("\r\n", "\n")
    code = _replace_once(
        code,
        '    for row in inventory.get("ingredients", []):\n',
        '    ingredient_rows = inventory.get("ingredients")\n'
        '    if not isinstance(ingredient_rows, list):\n'
        '        raise ValueError("LIVE inventory kehilangan ingredients; supplier ranking ditahan.")\n'
        '    for row in ingredient_rows:\n',
        "supplier inventory ingredients default",
    )
    code = _replace_once(
        code,
        '    for row in ingredient_rows:\n'
        '        if row.get("status") != "SHORTAGE":\n'
        '            continue\n',
        '    for row in ingredient_rows:\n'
        '        if not isinstance(row, dict) or "status" not in row:\n'
        '            raise ValueError("LIVE inventory row kehilangan status; supplier ranking ditahan.")\n'
        '        if row["status"] != "SHORTAGE":\n'
        '            continue\n',
        "supplier status default",
    )
    _set_code(node, code, "inventory")


def harden_dietary(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"].replace("\r\n", "\n")
    broken_block = (
        '        if "customers" not in state or "menu" not in state:\n'
        '        raise ValueError("LIVE context kehilangan customers/menu; dietary ditahan.")\n'
        '    if not isinstance(state["customers"], list) or not isinstance(state["menu"], list):\n'
        '        raise ValueError("LIVE context memiliki customers/menu invalid; dietary ditahan.")\n'
        '    state["dietary"] = check_dietary(state["customers"], state["menu"])\n'
    )
    correct_block = (
        '        if "customers" not in state or "menu" not in state:\n'
        '            raise ValueError("LIVE context kehilangan customers/menu; dietary ditahan.")\n'
        '        if not isinstance(state["customers"], list) or not isinstance(state["menu"], list):\n'
        '            raise ValueError("LIVE context memiliki customers/menu invalid; dietary ditahan.")\n'
        '        state["dietary"] = check_dietary(state["customers"], state["menu"])\n'
    )
    if broken_block in code:
        code = code.replace(broken_block, correct_block, 1)
    code = _replace_once(
        code,
        '    state["dietary"] = check_dietary(state.get("customers", []), state.get("menu", []))\n',
        '    if "customers" not in state or "menu" not in state:\n'
        '            raise ValueError("LIVE context kehilangan customers/menu; dietary ditahan.")\n'
        '        if not isinstance(state["customers"], list) or not isinstance(state["menu"], list):\n'
        '            raise ValueError("LIVE context memiliki customers/menu invalid; dietary ditahan.")\n'
        '        state["dietary"] = check_dietary(state["customers"], state["menu"])\n',
        "dietary state defaults",
    )
    code = _replace_once(
        code,
        '    ingredients = [norm(i) for i in (menu_item.get("ingredients") or [])]\n'
        '    tags = split_terms(menu_item.get("tags"))\n'
        '    name = norm(menu_item.get("name"))\n',
        '    if not isinstance(menu_item, dict) or "ingredients" not in menu_item or not isinstance(menu_item["ingredients"], list):\n'
        '        raise ValueError("LIVE menu kehilangan ingredients; dietary ditahan.")\n'
        '    if "name" not in menu_item or not str(menu_item["name"]).strip():\n'
        '        raise ValueError("LIVE menu kehilangan name; dietary ditahan.")\n'
        '    ingredients = [norm(i) for i in menu_item["ingredients"]]\n'
        '    tags = split_terms(menu_item.get("tags"))\n'
        '    name = norm(menu_item["name"])\n',
        "dietary menu defaults",
    )
    code = _replace_once(
        code,
        '    allergen_alerts(split_terms(customer.get("allergy")), "allergy", "HIGH", "MEDIUM")\n'
        '    allergen_alerts(split_terms(customer.get("intolerance")), "intolerance", "MEDIUM", "LOW")\n'
        '\n'
        '    for r in split_terms(customer.get("restriction")):\n',
        '    required_customer_fields = ("allergy", "intolerance", "restriction", "dislike")\n'
        '    if any(field not in customer for field in required_customer_fields):\n'
        '        raise ValueError("LIVE customer dietary field tidak lengkap; dietary ditahan.")\n'
        '    allergen_alerts(split_terms(customer["allergy"]), "allergy", "HIGH", "MEDIUM")\n'
        '    allergen_alerts(split_terms(customer["intolerance"]), "intolerance", "MEDIUM", "LOW")\n'
        '\n'
        '    for r in split_terms(customer["restriction"]):\n',
        "dietary customer defaults",
    )
    code = _replace_once(
        code,
        '    dislikes = split_terms(customer.get("dislike"))\n',
        '    dislikes = split_terms(customer["dislike"])\n',
        "dietary dislike default",
    )
    code = _replace_once(
        code,
        '    return {"menu": menu_item.get("name"), "shown": True, "has_conflict": bool(alerts),\n',
        '    return {"menu": menu_item["name"], "shown": True, "has_conflict": bool(alerts),\n',
        "dietary menu name default",
    )
    code = _replace_once(
        code,
        '    for c in customers:\n'
        '        out.append({"customer_id": c.get("customer_id"), "name": c.get("name"),\n',
        '    for c in customers:\n'
        '        if not isinstance(c, dict) or "customer_id" not in c or "name" not in c:\n'
        '            raise ValueError("LIVE customer identity tidak lengkap; dietary ditahan.")\n'
        '        out.append({"customer_id": c["customer_id"], "name": c["name"],\n',
        "dietary customer identity default",
    )
    _set_code(node, code, "dietary")


def harden_inventory(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"].replace("\r\n", "\n")
    code = _replace_once(
        code,
        '        for ing, grams in recipe.items():\n'
        '            if isinstance(grams, bool) or not isinstance(grams, (int, float)) or grams < 0:\n',
        '        for ing, grams in recipe.items():\n'
        '            if not str(ing).strip():\n'
        '                raise ValueError("LIVE BOM memiliki ingredient kosong; inventory ditahan.")\n'
        '            if isinstance(grams, bool) or not isinstance(grams, (int, float)) or grams < 0:\n',
        "inventory ingredient identity default",
    )
    code = _replace_once(
        code,
        '    rows.sort(key=lambda r: -r["shortage_g"])\n'
        '    return {"horizon_days": forecast.get("horizon_days"), "forecast_status": forecast.get("status"),\n',
        '    for field in ("horizon_days", "forecast_status"):\n'
        '        if field not in forecast:\n'
        '            raise ValueError(f"LIVE forecast kehilangan {field}; inventory ditahan.")\n'
        '    rows.sort(key=lambda r: -r["shortage_g"])\n'
        '    return {"horizon_days": forecast["horizon_days"], "forecast_status": forecast["forecast_status"],\n',
        "inventory forecast metadata defaults",
    )
    _set_code(node, code, "inventory")


def harden_marketing(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"].replace("\r\n", "\n")
    code = _replace_once(
        code,
        '    for row in rfm_rows:\n'
        '        if not isinstance(row, dict) or row.get("segment") not in ("AT_RISK", "CHURNED"):\n'
        '            continue\n',
        '    for row in rfm_rows:\n'
        '        if not isinstance(row, dict) or "segment" not in row:\n'
        '            raise ValueError("LIVE RFM row kehilangan segment; marketing ditahan.")\n'
        '        if row["segment"] not in ("AT_RISK", "CHURNED"):\n'
        '            continue\n',
        "marketing segment default",
    )
    code = _replace_once(
        code,
        '        customer_id = str(row.get("customer_id") or "").strip()\n',
        '        if "customer_id" not in row or row["customer_id"] is None:\n'
        '            raise ValueError("LIVE RFM row kehilangan customer_id; marketing ditahan.")\n'
        '        customer_id = str(row["customer_id"]).strip()\n',
        "marketing customer identity default",
    )
    code = _replace_once(
        code,
        '            out.append({"customer_id": customer_id, "segment": row.get("segment"),\n',
        '            out.append({"customer_id": customer_id, "segment": row["segment"],\n',
        "marketing segment output default",
    )
    _set_code(node, code, "marketing")


def harden_summary(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"].replace("\r\n", "\n")
    code = _replace_once(
        code,
        '    mode = str(s.get("_data_mode") or "unknown")\n'
        '    source = str(s.get("_source") or "unknown")\n'
        '    counts = s.get("counts") or {}\n',
        '    mode = s.get("_data_mode")\n'
        '    source = s.get("_source")\n'
        '    counts = s.get("counts")\n'
        '    if not isinstance(mode, str) or not mode.strip() or not isinstance(source, str) or not source.strip():\n'
        '        raise ValueError("Summary kehilangan provenance; output ditahan.")\n'
        '    if not isinstance(counts, dict):\n'
        '        raise ValueError("Summary kehilangan counts; output ditahan.")\n'
        '    required_counts = ("menus", "customers", "orders", "stock_items", "suppliers")\n'
        '    if any(field not in counts or isinstance(counts[field], bool) or not isinstance(counts[field], int) or counts[field] < 0 for field in required_counts):\n'
        '        raise ValueError("Summary memiliki counts invalid; output ditahan.")\n',
        "summary provenance/count defaults",
    )
    for field in ("menus", "customers", "orders", "stock_items", "suppliers"):
        code = _replace_once(
            code,
            f"counts.get('{field}', 0)",
            f"counts['{field}']",
            f"summary {field} default",
        )
    code = _replace_once(
        code,
        '    for warning in s.get("warnings") or []:\n',
        '    warnings = s.get("warnings")\n'
        '    if not isinstance(warnings, list):\n'
        '        raise ValueError("Summary memiliki warnings invalid; output ditahan.")\n'
        '    for warning in warnings:\n',
        "summary warnings default",
    )
    code = _replace_once(
        code,
        '    if customer_mode:\n'
        '        L.append("## Menu yang tersedia")\n'
        '        for m in s.get("menu", []):\n',
        '    if customer_mode:\n'
        '        menu_rows = s.get("menu")\n'
        '        customer_rows = s.get("customers")\n'
        '        if not isinstance(menu_rows, list) or not isinstance(customer_rows, list):\n'
        '            raise ValueError("Summary kehilangan menu/customers; output ditahan.")\n'
        '        L.append("## Menu yang tersedia")\n'
        '        for m in menu_rows:\n',
        "summary customer state defaults",
    )
    code = _replace_once(
        code,
        '        if not s.get("customers"):\n',
        '        if not customer_rows:\n',
        "summary customer profile default",
    )
    code = _replace_once(
        code,
        '    for k, f in s.get("forecast", {}).items():\n',
        '    forecast_rows = s.get("forecast")\n'
        '    if not isinstance(forecast_rows, dict):\n'
        '        raise ValueError("Summary kehilangan forecast; output ditahan.")\n'
        '    for k, f in forecast_rows.items():\n',
        "summary forecast state default",
    )
    _set_code(node, code, "summary")


def main() -> None:
    payload = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    harden_rfm(_node(payload, "RFM Segment"))
    harden_forecast(_node(payload, "Demand Forecast"))
    harden_inventory(_node(payload, "Inventory & BOM"))
    harden_supplier(_node(payload, "Supplier Ranking"))
    harden_dietary(_node(payload, "Dietary Check"))
    harden_marketing(_node(payload, "Marketing Draft"))
    harden_summary(_node(payload, "Summary"))
    FLOW_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"hardened={FLOW_PATH} nodes={len(payload['data']['nodes'])} edges={len(payload['data']['edges'])}")


if __name__ == "__main__":
    main()
