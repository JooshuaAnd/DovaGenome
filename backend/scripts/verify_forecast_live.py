"""Read-only verifier for the Phase 4 live forecast/Langflow contract.

This script never writes Supabase, Langflow, forecast snapshots, or provider
state. It checks the FastAPI live context and, when configured, the active
Langflow graph metadata. A model/provider smoke run is deliberately not
performed because it can consume quota and is not required to validate the
data contract.

Run from the repository root:

    python backend/scripts/verify_forecast_live.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FORECAST_FIELDS = (
    "paid_order_count",
    "paid_order_item_count",
    "invalid_quantity_item_count",
    "missing_unit_item_count",
    "missing_menu_id_item_count",
    "latest_paid_date",
    "latest_non_cancelled_date",
)
FORBIDDEN_LIVE_FALLBACK_PATTERNS = (
    'o.get("quantity", 1)',
    'o.get("total", 0)',
    'stock.get(ing, 0)',
    's.get("moq_kg", 0)',
    's.get("lead_time_days", 0)',
    's.get("capacity_kg", float("inf"))',
    '"menu favoritmu"',
    'os.getenv("DOVAGENOME_BACKEND_URL", "http://127.0.0.1:8000")',
    'os.getenv("DOVAGENOME_LIVE_TIMEOUT_SECONDS", "15")',
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


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _config() -> dict[str, str]:
    file_values = _read_dotenv(REPO_ROOT / ".env")
    return {
        key: os.getenv(key, file_values.get(key, ""))
        for key in (
            "DOVAGENOME_BACKEND_URL",
            "LANGFLOW_INTERNAL_TOKEN",
            "DOVAGENOME_INTERNAL_TOKEN",
            "LANGFLOW_API_URL",
            "LANGFLOW_API_KEY",
            "LANGFLOW_FLOW_ID",
        )
    }


def _get_json(url: str, *, headers: dict[str, str], timeout: float = 20.0) -> Any:
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _provider_markers(text: str) -> list[str]:
    lowered = text.lower()
    return [
        marker
        for marker in ("429", "quota", "resource_exhausted", "rate limit", "internal error")
        if marker in lowered
    ]


def run_model_smoke(config: dict[str, str], *, timeout: float = 30.0) -> dict[str, Any]:
    """Run one bounded, read-only Langflow request without exposing response text."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 5 <= timeout <= 120:
        raise ValueError("timeout smoke harus berada di antara 5 dan 120 detik.")
    api_base = _flow_base_url(config.get("LANGFLOW_API_URL", ""))
    flow_id = config.get("LANGFLOW_FLOW_ID", "").strip()
    api_key = config.get("LANGFLOW_API_KEY", "").strip()
    if not api_base or not flow_id or not api_key:
        return {"status": "NOT_CONFIGURED"}

    payload = {
        "input_value": "Reply only READY.",
        "input_type": "chat",
        "output_type": "chat",
        "session_id": "dova-forecast-contract-smoke",
    }
    request = Request(
        f"{api_base}/run/{flow_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(200_000)
            status_code = response.status
        text = raw.decode("utf-8", "replace")
        markers = _provider_markers(text)
        return {
            "status": "PASS" if not markers else "PROVIDER_ERROR",
            "http_status": status_code,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "response_bytes": len(raw),
            "contains_ready": "ready" in text.lower(),
            "provider_markers": markers,
        }
    except HTTPError as exc:
        raw = exc.read(200_000)
        markers = _provider_markers(raw.decode("utf-8", "replace"))
        return {
            "status": "PROVIDER_QUOTA" if exc.code == 429 or "quota" in markers or "resource_exhausted" in markers else "HTTP_ERROR",
            "http_status": exc.code,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "response_bytes": len(raw),
            "contains_ready": False,
            "provider_markers": markers,
        }
    except (TimeoutError, OSError) as exc:
        return {
            "status": "TIMEOUT" if isinstance(exc, TimeoutError) else "NETWORK_ERROR",
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "error_type": type(exc).__name__,
        }


def _require_int(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} bukan integer non-negatif.")


def validate_context(context: Any) -> dict[str, Any]:
    """Validate only contract fields; return a secret-free evidence summary."""
    if not isinstance(context, dict):
        raise ValueError("Live context bukan object JSON.")
    if context.get("_data_mode") != "live":
        raise ValueError("Context tidak membuktikan _data_mode=live.")
    if context.get("_source") != "supabase_postgres_via_fastapi":
        raise ValueError("Context tidak membuktikan source Supabase via FastAPI.")

    counts = context.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("Context tidak memiliki counts.")
    for field in ("menus", "customers", "orders", "order_items", "stock_items", "suppliers"):
        _require_int(counts.get(field), f"counts.{field}")

    reports = context.get("forecast_backtest")
    if not isinstance(reports, dict):
        raise ValueError("Context tidak memiliki forecast_backtest.")
    horizons: dict[str, dict[str, Any]] = {}
    for horizon in ("7d", "30d"):
        report = reports.get(horizon)
        if not isinstance(report, dict):
            raise ValueError(f"Forecast {horizon} tidak tersedia.")
        if report.get("data_mode") != "live" or report.get("source") != "supabase_postgres":
            raise ValueError(f"Forecast {horizon} bukan report live Supabase.")
        if report.get("calculation_version") != "forecast_backtest_v2":
            raise ValueError(f"Forecast {horizon} bukan calculation_version v2.")
        metadata = report.get("dependency_metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"Forecast {horizon} tidak memiliki dependency metadata.")
        for field in REQUIRED_FORECAST_FIELDS:
            if field not in metadata:
                raise ValueError(f"Forecast {horizon} kehilangan {field}.")
        for field in REQUIRED_FORECAST_FIELDS[:4]:
            _require_int(metadata[field], f"{horizon}.{field}")
        if any(
            metadata[field] != 0
            for field in (
                "invalid_quantity_item_count",
                "missing_unit_item_count",
                "missing_menu_id_item_count",
            )
        ):
            raise ValueError(f"Forecast {horizon} memiliki quality count non-zero.")
        horizons[horizon] = {
            "status": report.get("status"),
            "latest_observation_date": report.get("latest_observation_date"),
            "data_age_days": report.get("data_age_days"),
            "series_count": report.get("series_count"),
            "eligible_series_count": report.get("eligible_series_count"),
            "paid_order_count": metadata["paid_order_count"],
            "paid_order_item_count": metadata["paid_order_item_count"],
            "quality_counts": {
                "invalid_quantity_item_count": metadata["invalid_quantity_item_count"],
                "missing_unit_item_count": metadata["missing_unit_item_count"],
                "missing_menu_id_item_count": metadata["missing_menu_id_item_count"],
            },
        }

    return {
        "status": "PASS",
        "data_mode": context["_data_mode"],
        "source": context["_source"],
        "counts": {
            field: counts[field]
            for field in ("menus", "customers", "orders", "order_items", "stock_items", "suppliers")
        },
        "forecast": horizons,
    }


def _flow_base_url(api_url: str) -> str:
    value = (api_url or "").strip().rstrip("/")
    if "/run" in value:
        value = value.split("/run", 1)[0].rstrip("/")
    return value


def validate_flow(flow: Any) -> dict[str, Any]:
    if not isinstance(flow, dict):
        raise ValueError("Respons flow bukan object JSON.")
    data = flow.get("data") or {}
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    forecast_nodes = []
    model_nodes = []
    manual_json_nodes = []
    hidden_fallback_patterns = []
    for node in nodes:
        node_data = ((node.get("data") or {}).get("node") or {}) if isinstance(node, dict) else {}
        display_name = str(node_data.get("display_name") or "")
        template = node_data.get("template") or {}
        code = str((template.get("code") or {}).get("value") or "")
        if display_name == "Language Model" or "language model" in display_name.lower():
            model_input = template.get("model") or {}
            model_value = model_input.get("value") if isinstance(model_input, dict) else None
            candidates = model_value if isinstance(model_value, list) else [model_value]
            credential_input = template.get("api_key") or {}
            credential_value = (
                credential_input.get("value")
                if isinstance(credential_input, dict)
                else credential_input
            )
            node_credential_present = bool(str(credential_value or "").strip())
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                provider = str(candidate.get("provider") or "").strip()
                model_name = str(candidate.get("name") or "").strip()
                if provider or model_name:
                    model_nodes.append(
                        {
                            "provider": provider,
                            "model": model_name,
                            "node_credential_present": node_credential_present,
                        }
                    )
        for pattern in FORBIDDEN_LIVE_FALLBACK_PATTERNS:
            if pattern in code:
                hidden_fallback_patterns.append({"display_name": display_name, "pattern": pattern})
        if "manual_json" in template:
            manual_json_nodes.append(display_name)
            if "Flow LIVE menolak manual_json" not in code:
                raise ValueError(f"Node LIVE memiliki manual_json tanpa rejection: {display_name}.")
        if "Demand Forecast" in display_name:
            forecast_nodes.append({
                "display_name": display_name,
                "strict_v2": "forecast_backtest_v2" in code,
                "stale_gate": "STALE_DATA" in code,
                "manual_json_rejected": "menolak manual_json" in code,
            })
    if len(nodes) != 15 or len(edges) != 12:
        raise ValueError(f"Graph LIVE tidak sesuai kontrak 15/12: {len(nodes)}/{len(edges)}.")
    if len(forecast_nodes) != 1 or not all(
        item["strict_v2"] and item["stale_gate"] and item["manual_json_rejected"]
        for item in forecast_nodes
    ):
        raise ValueError("Node Demand Forecast tidak memenuhi strict v2/stale/manual gate.")
    if hidden_fallback_patterns:
        raise ValueError(
            "Graph LIVE memiliki default data tersembunyi: "
            + ", ".join(item["display_name"] for item in hidden_fallback_patterns)
        )
    return {
        "status": "PASS",
        "flow_id": flow.get("id"),
        "name": flow.get("name"),
        "nodes": len(nodes),
        "edges": len(edges),
        "forecast_nodes": forecast_nodes,
        "model_nodes": model_nodes,
        "manual_json_nodes": manual_json_nodes,
        "hidden_fallback_patterns": hidden_fallback_patterns,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the DovaGenome live forecast/Langflow contract.")
    parser.add_argument(
        "--model-smoke",
        action="store_true",
        help="Run one bounded Langflow provider request; may consume provider quota.",
    )
    parser.add_argument(
        "--smoke-timeout",
        type=float,
        default=30.0,
        help="Provider smoke timeout in seconds (5-120).",
    )
    args = parser.parse_args(argv)
    config = _config()
    backend_url = (config["DOVAGENOME_BACKEND_URL"] or "http://127.0.0.1:8000").rstrip("/")
    internal_token = config["LANGFLOW_INTERNAL_TOKEN"] or config["DOVAGENOME_INTERNAL_TOKEN"]
    if not internal_token:
        print(json.dumps({"status": "FAIL", "reason": "internal token tidak dikonfigurasi"}, ensure_ascii=False))
        return 2

    evidence: dict[str, Any] = {"verifier": "forecast_live_contract_v2", "model_smoke": "NOT_ATTEMPTED"}
    try:
        context = _get_json(
            f"{backend_url}/api/ai/internal/context",
            headers={"Accept": "application/json", "X-Dova-Internal-Token": internal_token},
        )
        evidence["fastapi_context"] = validate_context(context)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        evidence["status"] = "FAIL"
        evidence["fastapi_context"] = {"status": "FAIL", "reason": type(exc).__name__}
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 1

    api_base = _flow_base_url(config["LANGFLOW_API_URL"])
    flow_id = config["LANGFLOW_FLOW_ID"].strip()
    api_key = config["LANGFLOW_API_KEY"].strip()
    if api_base and flow_id and api_key:
        try:
            flow = _get_json(
                f"{api_base}/flows/{flow_id}",
                headers={"Accept": "application/json", "x-api-key": api_key},
            )
            evidence["langflow_graph"] = validate_flow(flow)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            evidence["status"] = "FAIL"
            evidence["langflow_graph"] = {"status": "FAIL", "reason": type(exc).__name__}
            print(json.dumps(evidence, ensure_ascii=False, indent=2))
            return 1
    else:
        evidence["langflow_graph"] = {"status": "NOT_CONFIGURED"}

    if args.model_smoke:
        try:
            evidence["model_smoke"] = run_model_smoke(config, timeout=args.smoke_timeout)
        except ValueError as exc:
            evidence["model_smoke"] = {"status": "INVALID_CONFIG", "reason": str(exc)}
        if evidence["model_smoke"].get("status") != "PASS":
            evidence["status"] = "PARTIAL"
            print(json.dumps(evidence, ensure_ascii=False, indent=2))
            return 1
    evidence["status"] = "PASS"
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
