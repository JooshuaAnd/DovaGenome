import pytest
from io import BytesIO
from urllib.error import HTTPError

from scripts import verify_forecast_live
from scripts.verify_forecast_live import validate_context, validate_flow


def _forecast_report():
    return {
        "status": "STALE_DATA",
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": "forecast_backtest_v2",
        "latest_observation_date": "2026-10-12",
        "data_age_days": 15,
        "series_count": 18,
        "eligible_series_count": 18,
        "dependency_metadata": {
            "paid_order_count": 418,
            "paid_order_item_count": 817,
            "invalid_quantity_item_count": 0,
            "missing_unit_item_count": 0,
            "missing_menu_id_item_count": 0,
            "latest_paid_date": "2026-10-12",
            "latest_non_cancelled_date": "2026-10-12",
        },
    }


def _live_context():
    return {
        "_data_mode": "live",
        "_source": "supabase_postgres_via_fastapi",
        "counts": {
            "menus": 18,
            "customers": 63,
            "orders": 844,
            "order_items": 1682,
            "stock_items": 6,
            "suppliers": 8,
        },
        "forecast_backtest": {
            "7d": _forecast_report(),
            "30d": _forecast_report(),
        },
    }


def _live_flow():
    code = """
    calculation_version = 'forecast_backtest_v2'
    if status == 'STALE_DATA':
        raise ValueError('STALE_DATA')
    raise ValueError('menolak manual_json')
    """
    return {
        "id": "flow-1",
        "name": "LIVE",
        "data": {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "display_name": "Dova · Demand Forecast",
                            "template": {"code": {"value": code}},
                        }
                    }
                }
            ]
            + [{"data": {"node": {"display_name": f"Node {i}"}}} for i in range(14)],
            "edges": [{"id": str(i)} for i in range(12)],
        },
    }


def test_forecast_live_verifier_accepts_verified_context():
    result = validate_context(_live_context())

    assert result["status"] == "PASS"
    assert result["data_mode"] == "live"
    assert result["counts"]["orders"] == 844
    assert result["forecast"]["7d"]["quality_counts"] == {
        "invalid_quantity_item_count": 0,
        "missing_unit_item_count": 0,
        "missing_menu_id_item_count": 0,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda context: context.update({"_data_mode": "manual"}),
        lambda context: context["forecast_backtest"]["7d"]["dependency_metadata"].update(
            {"missing_unit_item_count": 1}
        ),
        lambda context: context["forecast_backtest"]["7d"]["dependency_metadata"].update(
            {"missing_menu_id_item_count": 1}
        ),
    ],
)
def test_forecast_live_verifier_rejects_unverified_context(mutation):
    context = _live_context()
    mutation(context)

    with pytest.raises(ValueError):
        validate_context(context)


def test_forecast_live_verifier_accepts_strict_langflow_graph():
    result = validate_flow(_live_flow())

    assert result["status"] == "PASS"
    assert result["nodes"] == 15
    assert result["edges"] == 12
    assert result["model_nodes"] == []
    assert result["forecast_nodes"][0] == {
        "display_name": "Dova · Demand Forecast",
        "strict_v2": True,
        "stale_gate": True,
        "manual_json_rejected": True,
    }


def test_forecast_live_verifier_reports_provider_without_exposing_credentials():
    flow = _live_flow()
    flow["data"]["nodes"][1] = {
        "data": {
            "node": {
                "display_name": "Language Model",
                "template": {
                    "model": {
                        "value": [{"provider": "Google Generative AI", "name": "gemma-4-31b-it"}]
                    }
                },
            }
        }
    }

    result = validate_flow(flow)

    assert result["model_nodes"] == [
        {
            "provider": "Google Generative AI",
            "model": "gemma-4-31b-it",
            "node_credential_present": False,
        }
    ]
    assert "api_key" not in str(result).lower()


def test_forecast_live_verifier_rejects_incomplete_langflow_graph():
    flow = _live_flow()
    flow["data"]["edges"] = flow["data"]["edges"][:-1]

    with pytest.raises(ValueError):
        validate_flow(flow)


def test_forecast_live_verifier_rejects_hidden_transform_fallback():
    flow = _live_flow()
    flow["data"]["nodes"][1] = {
        "data": {
            "node": {
                "display_name": "Dova Inventory",
                "template": {
                    "code": {"value": 'have = stock.get(ing, 0)'}
                },
            }
        }
    }

    with pytest.raises(ValueError, match="default data tersembunyi"):
        validate_flow(flow)


@pytest.mark.parametrize(
    "hidden_config",
    [
        'backend_url = os.getenv("DOVAGENOME_BACKEND_URL", "http://127.0.0.1:8000")',
        'timeout = float(os.getenv("DOVAGENOME_LIVE_TIMEOUT_SECONDS", "15"))',
    ],
)
def test_forecast_live_verifier_rejects_hidden_runtime_config_defaults(hidden_config):
    flow = _live_flow()
    flow["data"]["nodes"][1] = {
        "data": {
            "node": {
                "display_name": "Dova Live FastAPI Context",
                "template": {"code": {"value": hidden_config}},
            }
        }
    }

    with pytest.raises(ValueError, match="default data tersembunyi"):
        validate_flow(flow)


class _FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.body


def test_model_smoke_returns_secret_free_pass_summary(monkeypatch):
    monkeypatch.setattr(
        verify_forecast_live,
        "urlopen",
        lambda _request, timeout: _FakeResponse(b'{"message":"READY"}'),
    )

    result = verify_forecast_live.run_model_smoke(
        {
            "LANGFLOW_API_URL": "http://127.0.0.1:7860/api/v1",
            "LANGFLOW_FLOW_ID": "flow-1",
            "LANGFLOW_API_KEY": "secret-that-must-not-appear",
        },
        timeout=5,
    )

    assert result["status"] == "PASS"
    assert result["contains_ready"] is True
    assert "secret-that-must-not-appear" not in str(result)


def test_model_smoke_classifies_provider_quota_without_response_body(monkeypatch):
    error = HTTPError(
        "http://127.0.0.1:7860/api/v1/run/flow-1",
        429,
        "quota",
        {},
        BytesIO(b"RESOURCE_EXHAUSTED quota details"),
    )
    monkeypatch.setattr(
        verify_forecast_live,
        "urlopen",
        lambda _request, timeout: (_ for _ in ()).throw(error),
    )

    result = verify_forecast_live.run_model_smoke(
        {
            "LANGFLOW_API_URL": "http://127.0.0.1:7860/api/v1",
            "LANGFLOW_FLOW_ID": "flow-1",
            "LANGFLOW_API_KEY": "secret-that-must-not-appear",
        },
        timeout=5,
    )

    assert result["status"] == "PROVIDER_QUOTA"
    assert result["provider_markers"] == ["quota", "resource_exhausted"]
    assert "secret-that-must-not-appear" not in str(result)
