import json
import sys
import types
from pathlib import Path

import pytest


FLOW_PATH = Path(__file__).resolve().parents[2] / "langflow" / "Dova_Kitchen_Chef_BOB_LIVE.json"


def _nodes():
    payload = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    nodes = payload["data"]["nodes"]
    return payload, {node["id"]: node for node in nodes}


def _custom_code(nodes: dict[str, dict], display_name_fragment: str) -> str:
    node = next(
        node for node in nodes.values()
        if display_name_fragment in node.get("data", {}).get("node", {}).get("display_name", "")
    )
    return node["data"]["node"]["template"]["code"]["value"]


def test_live_flow_json_graph_and_custom_code_contract():
    payload, nodes = _nodes()
    edges = payload["data"]["edges"]

    assert len(nodes) == 15
    assert len(edges) == 12
    assert len(nodes) == len(set(nodes))
    assert all(edge["source"] in nodes and edge["target"] in nodes for edge in edges)
    assert not any(
        "Supabase" in node.get("data", {}).get("node", {}).get("display_name", "")
        or "Embedding" in node.get("data", {}).get("node", {}).get("display_name", "")
        for node in nodes.values()
    )

    context_code = _custom_code(nodes, "Live FastAPI")
    assert "DovaDataSource" in context_code
    assert "use_sample" in context_code
    assert "_data_mode" in context_code
    assert "_source" in context_code

    forecast_code = _custom_code(nodes, "Demand Forecast")
    assert "forecast_backtest_v2" in forecast_code
    assert "STALE_DATA" in forecast_code
    assert "forecast_demand" not in forecast_code
    assert "state[\"forecast_backtest\"]" in forecast_code or "state.get(\"forecast_backtest\")" in forecast_code
    forecast_node = next(
        node for node in nodes.values()
        if "Demand Forecast" in node["data"]["node"].get("display_name", "")
    )
    assert forecast_node["data"]["node"]["metadata"]["code_hash"].startswith(
        "dova-live-state-fail-closed-forecast-"
    )


def test_live_flow_forecast_node_has_no_default_sample_path():
    _payload, nodes = _nodes()
    forecast_code = _custom_code(nodes, "Demand Forecast")

    assert "state.get(\"orders\")" not in forecast_code
    assert "[25, 28, 30" not in forecast_code
    assert "forecast backtest live untuk horizon" in forecast_code.lower()


def test_live_flow_all_manual_inputs_are_rejected_instead_of_fallback():
    _payload, nodes = _nodes()
    guarded_nodes = []

    for node in nodes.values():
        node_data = node["data"]["node"]
        template = node_data.get("template") or {}
        if "manual_json" not in template:
            continue
        display_name = node_data.get("display_name", "")
        code = template["code"]["value"]
        guarded_nodes.append(display_name)
        assert "Flow LIVE menolak manual_json" in code, display_name
        assert "state.update(json.loads(manual_json))" not in code, display_name

    assert len(guarded_nodes) == 7


def test_live_flow_transforms_reject_missing_operational_fields_instead_of_defaulting():
    _payload, nodes = _nodes()
    custom_code = "\n".join(
        str(((node.get("data") or {}).get("node") or {}).get("template", {}).get("code", {}).get("value") or "")
        for node in nodes.values()
    )

    forbidden_defaults = (
        'o.get("quantity", 1)',
        'o.get("total", 0)',
        'stock.get(ing, 0)',
        's.get("moq_kg", 0)',
        's.get("lead_time_days", 0)',
        's.get("capacity_kg", float("inf"))',
        '"menu favoritmu"',
        'names.get(c, c)',
        'counts.get(\'menus\', 0)',
        'counts.get(\'customers\', 0)',
        'counts.get(\'orders\', 0)',
        'counts.get(\'stock_items\', 0)',
        'counts.get(\'suppliers\', 0)',
        'state.get("forecast_backtest") or {}',
        'report.get("series", [])',
        'inventory.get("ingredients", [])',
        'report.get("warnings") or []',
        'state.get("customers", [])',
        'state.get("menu", [])',
        'str(report.get("status") or "UNAVAILABLE")',
    )
    for pattern in forbidden_defaults:
        assert pattern not in custom_code, pattern
    assert "ingredient_without_stock" in custom_code
    assert "DRAFT_BLOCKED" in custom_code


def test_live_flow_forecast_node_rejects_hidden_quantity_unit_defaults_and_manual_state():
    _payload, nodes = _nodes()
    forecast_code = _custom_code(nodes, "Demand Forecast")

    assert "row.get(\"quantity\") or 0" not in forecast_code
    assert "series.get(\"unit\") or \"portion\"" not in forecast_code
    assert "manual_json" in forecast_code
    assert "menolak manual_json" in forecast_code
    assert "data_age_days" in forecast_code
    assert "_data_mode" in forecast_code


def test_supplier_forecast_ui_does_not_render_legacy_demo_payload():
    supplier_page = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "pages"
        / "supplier"
        / "SupplierPage.tsx"
    ).read_text(encoding="utf-8")

    assert "const trustedForecast" in supplier_page
    assert "calculation_version === 'forecast_backtest_v2'" in supplier_page
    assert "Forecast supplier belum tersedia" in supplier_page
    assert "forecastData?.peak_day || 'Jumat'" not in supplier_page
    assert "supplier_7d_forecast || []" not in supplier_page
    assert "top_dishes || []" not in supplier_page
    assert "Data 1.000 pesanan" not in supplier_page


def _load_forecast_namespace(monkeypatch):
    langflow = types.ModuleType("langflow")
    custom = types.ModuleType("langflow.custom")
    io = types.ModuleType("langflow.io")
    schema = types.ModuleType("langflow.schema")
    custom.Component = object
    for name in ("DataInput", "IntInput", "MultilineInput", "Output"):
        setattr(io, name, lambda **_kwargs: None)
    schema.Data = object
    langflow.custom = custom
    langflow.io = io
    langflow.schema = schema
    monkeypatch.setitem(sys.modules, "langflow", langflow)
    monkeypatch.setitem(sys.modules, "langflow.custom", custom)
    monkeypatch.setitem(sys.modules, "langflow.io", io)
    monkeypatch.setitem(sys.modules, "langflow.schema", schema)

    _payload, nodes = _nodes()
    code = _custom_code(nodes, "Demand Forecast")
    namespace: dict[str, object] = {}
    exec(compile(code, "<langflow-live-forecast>", "exec"), namespace)
    return namespace


def test_live_flow_forecast_node_runtime_contract_fails_closed(monkeypatch):
    namespace = _load_forecast_namespace(monkeypatch)
    report = {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": "forecast_backtest_v2",
        "horizon_days": 7,
        "data_age_days": 0,
        "warnings": [],
        "series": [{
            "series_key": "menu-a",
            "label": "Menu A",
            "unit": "portion",
            "forecast": [
                {"quantity": 2, "unit": "portion", "method": "MA7"},
                {"quantity": 3, "unit": "portion", "method": "MA7"},
            ],
        }],
    }

    result = namespace["report_to_items"](report)
    assert result["items"][0]["forecast_portions"] == 5
    assert result["data_age_days"] == 0

    for invalid_row in (
        {"unit": "portion"},
        {"quantity": 2},
        {"quantity": -1, "unit": "portion"},
    ):
        invalid_report = {**report, "series": [{
            **report["series"][0],
            "forecast": [invalid_row],
        }]}
        with pytest.raises(ValueError):
            namespace["report_to_items"](invalid_report)

    mixed_report = {**report, "series": [{
        **report["series"][0],
        "forecast": [{"quantity": 2, "unit": "portion"}, {"quantity": 1, "unit": "kg"}],
    }]}
    with pytest.raises(ValueError, match="unit campuran"):
        namespace["report_to_items"](mixed_report)

    with pytest.raises(ValueError, match="menolak manual_json"):
        namespace["load_state"]({"_data_mode": "live"}, "{\"forecast_backtest\": {}}")
