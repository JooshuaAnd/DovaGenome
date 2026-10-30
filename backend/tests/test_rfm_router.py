import pytest
from fastapi import HTTPException

from app.api.routers import admin as admin_router
from app.core.errors import DatabaseError
from app.services import rfm_service


def test_rfm_snapshot_route_translates_stale_report_to_409(monkeypatch):
    report = {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "freshness_status": "STALE_DATA",
    }
    monkeypatch.setattr(rfm_service, "build_rfm_report", lambda: report)

    with pytest.raises(HTTPException) as error:
        admin_router.persist_rfm_snapshot(admin=object())

    assert error.value.status_code == 409
    assert "fresh" in str(error.value.detail).lower() or "stale" in str(error.value.detail).lower()


def test_rfm_snapshot_route_returns_persistence_provenance(monkeypatch):
    report = {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "as_of": "2026-10-27",
        "calculation_version": rfm_service.CALCULATION_VERSION,
        "freshness_status": "FRESH",
    }
    monkeypatch.setattr(rfm_service, "build_rfm_report", lambda: report)
    monkeypatch.setattr(rfm_service, "persist_rfm_report", lambda _report: 58)

    result = admin_router.persist_rfm_snapshot(admin=object())

    assert result == {
        "status": "OK",
        "persisted_rows": 58,
        "as_of": "2026-10-27",
        "calculation_version": "rfm_quantile_v1",
        "data_mode": "live",
        "source": "supabase_postgres",
    }


def test_rfm_movement_route_translates_database_failure_to_503(monkeypatch):
    monkeypatch.setattr(
        rfm_service,
        "build_segment_movement",
        lambda: (_ for _ in ()).throw(DatabaseError("snapshot table unavailable")),
    )

    with pytest.raises(HTTPException) as error:
        admin_router.get_rfm_segment_movement(admin=object())

    assert error.value.status_code == 503
    assert "snapshot table unavailable" in str(error.value.detail)


def test_churn_backtest_route_passes_horizon_and_propagates_report(monkeypatch):
    captured = {}

    def fake_backtest(*, horizon_days):
        captured["horizon_days"] = horizon_days
        return {"status": "BACKTEST_ONLY", "horizon_days": horizon_days}

    monkeypatch.setattr("app.services.churn_service.build_churn_backtest", fake_backtest)

    result = admin_router.get_churn_backtest(horizon_days=45, admin=object())

    assert captured == {"horizon_days": 45}
    assert result == {"status": "BACKTEST_ONLY", "horizon_days": 45}


def test_churn_backtest_route_translates_database_failure_to_503(monkeypatch):
    monkeypatch.setattr(
        "app.services.churn_service.build_churn_backtest",
        lambda *, horizon_days: (_ for _ in ()).throw(DatabaseError("orders unavailable")),
    )

    with pytest.raises(HTTPException) as error:
        admin_router.get_churn_backtest(horizon_days=30, admin=object())

    assert error.value.status_code == 503
    assert "orders unavailable" in str(error.value.detail)
