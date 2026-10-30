import datetime as dt

import pytest

from app.core.errors import DatabaseError
from app.repositories import supabase as db
from app.services import churn_service


def test_churn_baseline_is_explainable_and_not_a_probability():
    rows = [
        {"customer_id": "steady", "display_name": "Steady", "order_dates": ["2026-10-11", "2026-10-18", "2026-10-25"]},
        {"customer_id": "medium", "display_name": "Medium", "order_dates": ["2026-09-17", "2026-09-24", "2026-10-01"]},
        {"customer_id": "high", "display_name": "High", "order_dates": ["2026-07-25", "2026-08-01"]},
        {"customer_id": "new", "display_name": "New", "order_dates": ["2026-10-26"]},
    ]

    report = churn_service.build_churn_report(rows, as_of=dt.date(2026, 10, 27))

    assert report["status"] == "BASELINE_ONLY"
    assert report["methodology"] == "rule_based_baseline"
    assert report["model_validated"] is False
    assert report["risk_counts"] == {"LOW": 1, "MEDIUM": 1, "HIGH": 1, "UNKNOWN": 1}
    by_id = {item["customer_id"]: item for item in report["customers"]}
    assert by_id["steady"]["risk_band"] == "LOW"
    assert by_id["medium"]["risk_band"] == "MEDIUM"
    assert by_id["high"]["risk_band"] == "HIGH"
    assert by_id["new"]["risk_band"] == "UNKNOWN"
    assert by_id["new"]["risk_index"] is None
    assert any("bukan model supervised" in warning for warning in report["warnings"])


def test_churn_marks_old_live_observations_stale():
    report = churn_service.build_churn_report(
        [{"customer_id": "c1", "order_dates": ["2026-10-01", "2026-10-08"]}],
        as_of=dt.date(2026, 10, 27),
    )

    assert report["freshness_status"] == "STALE_DATA"
    assert report["data_age_days"] == 19
    assert any("historical signal" in warning for warning in report["warnings"])


def test_churn_has_no_synthetic_fallback_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: False)

    with pytest.raises(DatabaseError, match="baseline churn live ditahan"):
        churn_service.build_churn_report()


def test_live_churn_query_is_paid_and_non_cancelled(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)
    captured = {}

    def fake_execute(sql, params=None):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(db, "execute", fake_execute)
    report = churn_service.build_churn_report()

    assert report["status"] == "NO_DATA"
    assert "payment_status = 'PAID'" in captured["sql"]
    assert "status <> 'CANCELLED'" in captured["sql"]
    assert "o.created_at" in captured["sql"]


def test_churn_backtest_uses_observed_future_window_and_temporal_split():
    rows = [
        {
            "customer_id": "steady",
            "order_dates": [
                "2026-08-01",
                "2026-08-08",
                "2026-08-15",
                "2026-08-22",
                "2026-08-29",
                "2026-09-05",
                "2026-09-12",
                "2026-09-19",
                "2026-09-26",
                "2026-10-03",
                "2026-10-10",
            ],
        },
        {"customer_id": "churned", "order_dates": ["2026-08-01", "2026-08-08"]},
        {"customer_id": "returning", "order_dates": ["2026-08-01", "2026-08-15", "2026-09-20"]},
    ]

    report = churn_service.build_churn_backtest(
        rows,
        as_of=dt.date(2026, 10, 12),
        horizon_days=30,
    )

    assert report["status"] == "BACKTEST_ONLY"
    assert report["model_validated"] is False
    assert report["operational_eligibility"] is False
    assert report["methodology"] == "time_split_observed_label_baseline_backtest"
    assert report["train_cutoff_count"] >= 1
    assert report["test_cutoff_count"] >= 1
    assert report["test_observation_count"] >= 2
    assert "precision" in report["metrics"]
    assert any("bukan model supervised" in warning for warning in report["warnings"])


def test_churn_backtest_does_not_label_missing_future_data_as_churn():
    rows = [
        {"customer_id": "c1", "order_dates": ["2026-10-01", "2026-10-08"]},
        {"customer_id": "c2", "order_dates": ["2026-10-01", "2026-10-09"]},
    ]

    report = churn_service.build_churn_backtest(
        rows,
        as_of=dt.date(2026, 12, 31),
        horizon_days=30,
    )

    assert report["status"] == "INSUFFICIENT_DATA"
    assert "future window lengkap" in report["warnings"][0]
