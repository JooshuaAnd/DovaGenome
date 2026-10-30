import datetime as dt

import pytest

from app.core.errors import DatabaseError
from app.repositories import supabase as db
from app.services import rfm_service


def _rows():
    dates = [
        dt.date(2026, 10, 26),
        dt.date(2026, 10, 20),
        dt.date(2026, 10, 10),
        dt.date(2026, 9, 20),
        dt.date(2026, 8, 1),
    ]
    return [
        {
            "customer_id": f"c{index}",
            "display_name": f"Customer {index}",
            "phone": "",
            "last_order_date": date,
            "frequency": frequency,
            "monetary": frequency * 100,
        }
        for index, (date, frequency) in enumerate(zip(dates, [10, 8, 5, 2, 1]), start=1)
    ]


def test_quantile_rfm_scores_are_cohort_based_and_provenanced():
    report = rfm_service.build_rfm_report(_rows(), as_of=dt.date(2026, 10, 27))

    assert report["status"] == "OK"
    assert report["data_mode"] == "test"
    assert report["source"] == "test_fixture"
    assert report["calculation_version"] == "rfm_quantile_v1"
    assert report["freshness_status"] == "FRESH"
    assert report["freshness_threshold_days"] == 7
    assert report["total_analyzed"] == 5
    assert report["customers"][0]["rfm_score"] == "555"
    assert report["customers"][-1]["rfm_score"] == "111"
    assert sum(report["segment_counts"].values()) == 5


def test_rfm_has_no_synthetic_fallback_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: False)

    with pytest.raises(DatabaseError, match="RFM live ditahan"):
        rfm_service.build_rfm_report()


def test_live_rfm_query_uses_paid_non_cancelled_orders(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)
    captured = {}

    def fake_execute(sql, params=None):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(db, "execute", fake_execute)
    report = rfm_service.build_rfm_report()

    assert report["status"] == "NO_DATA"
    assert "payment_status = 'PAID'" in captured["sql"]
    assert "status <> 'CANCELLED'" in captured["sql"]
    assert "COUNT(o.order_id)" in captured["sql"]


def test_unknown_customer_does_not_receive_default_champions(monkeypatch):
    monkeypatch.setattr(rfm_service, "build_rfm_report", lambda: {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": "rfm_quantile_v1",
        "customers": [],
    })

    result = rfm_service.get_customer_rfm("unknown")

    assert result["status"] == "NO_HISTORY"
    assert result["segment"] == "NO_HISTORY"
    assert result["frequency"] == 0
    assert result["rfm_score"] is None


def _live_report(*, freshness_status="FRESH"):
    return {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": rfm_service.CALCULATION_VERSION,
        "as_of": "2026-10-27",
        "freshness_status": freshness_status,
        "customers": [{
            "customer_id": "c1",
            "name": "Customer 1",
            "recency_days": 1,
            "frequency": 3,
            "monetary": 300.0,
            "r_score": 5,
            "f_score": 4,
            "m_score": 4,
            "segment": "Champions",
        }],
    }


def test_rfm_snapshot_rejects_stale_live_report():
    with pytest.raises(rfm_service.RfmUnavailable, match="stale"):
        rfm_service.persist_rfm_report(_live_report(freshness_status="STALE_DATA"))


def test_rfm_snapshot_persists_idempotent_rows_with_provenance(monkeypatch):
    executed = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _sql, params):
            executed.append(params)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(db, "get_conn", lambda: FakeConnection())

    assert rfm_service.persist_rfm_report(_live_report()) == 1
    assert executed[0] == (
        "c1", "2026-10-27", 1, 3, 300.0, 5, 4, 4, "Champions",
        "live", "supabase_postgres", "rfm_quantile_v1",
    )


def test_rfm_movement_marks_changed_and_new_customers(monkeypatch):
    monkeypatch.setattr(db, "execute", lambda _sql, _params: [
        {"customer_id": "c1", "snapshot_date": "2026-10-20", "segment": "At Risk"},
    ])
    report = _live_report()
    report["customers"].append({
        "customer_id": "c2",
        "name": "Customer 2",
        "segment": "New Customers",
    })

    result = rfm_service.build_segment_movement(report)

    assert result["summary"] == {"CHANGED": 1, "NO_PREVIOUS": 1}
    assert result["previous_snapshot_date"] == "2026-10-20"
