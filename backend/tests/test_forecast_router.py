import pytest
from fastapi import HTTPException

from app.api.routers import admin as admin_router
from app.services import forecast_service


def test_forecast_route_translates_live_dependency_failure_to_503(monkeypatch):
    def fail_live_report(**_kwargs):
        raise forecast_service.ForecastUnavailable("Supabase tidak terhubung; forecast live ditahan.")

    monkeypatch.setattr(forecast_service, "build_live_forecast_report", fail_live_report)

    with pytest.raises(HTTPException) as error:
        admin_router.get_forecast_backtest(admin=object())

    assert error.value.status_code == 503
    assert "forecast live ditahan" in str(error.value.detail)


def test_snapshot_route_translates_stale_report_to_409(monkeypatch):
    monkeypatch.setattr(
        forecast_service,
        "build_live_forecast_report",
        lambda **_kwargs: {"status": "STALE_DATA", "data_mode": "live"},
    )

    with pytest.raises(HTTPException) as error:
        admin_router.persist_forecast_snapshot(admin=object())

    assert error.value.status_code == 409
    assert "STALE_DATA" in str(error.value.detail)


def test_snapshot_route_returns_persistence_provenance_for_fresh_report(monkeypatch):
    report = {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": "forecast_backtest_v2",
    }
    monkeypatch.setattr(forecast_service, "build_live_forecast_report", lambda **_kwargs: report)
    monkeypatch.setattr(forecast_service, "persist_forecast_report", lambda _report: 14)

    result = admin_router.persist_forecast_snapshot(admin=object())

    assert result == {
        "status": "OK",
        "persisted_rows": 14,
        "calculation_version": "forecast_backtest_v2",
        "data_mode": "live",
        "source": "supabase_postgres",
    }


@pytest.mark.parametrize(
    "legacy_route",
    [admin_router.get_supply_chain_ml, admin_router.get_demand_insights],
)
def test_legacy_forecast_routes_are_disabled_without_fallback(legacy_route):
    with pytest.raises(HTTPException) as error:
        legacy_route(admin=object())

    assert error.value.status_code == 410
