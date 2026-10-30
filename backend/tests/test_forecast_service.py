import datetime as dt

import pytest

from app.core.errors import DatabaseError
from app.repositories import supabase as db
from app.services import analytics_ml_service
from app.services import forecast_service


LIVE_DEPENDENCY_METADATA = {
    "paid_order_count": 10,
    "paid_order_item_count": 20,
    "invalid_quantity_item_count": 0,
    "missing_unit_item_count": 0,
    "missing_menu_id_item_count": 0,
    "latest_paid_date": "2026-10-27",
    "latest_non_cancelled_date": "2026-10-27",
}


def test_backtest_compares_baselines_and_selects_a_method():
    values = [10, 10, 11, 10, 12, 11, 10] * 5

    result = forecast_service.backtest_series(
        values,
        min_history_days=14,
        min_backtest_points=7,
    )

    assert result["status"] == "OK"
    assert result["selected_method"] in forecast_service.METHODS
    assert set(result["methods"]) == set(forecast_service.METHODS)
    assert all(result["methods"][name]["holdout_points"] == 21 for name in forecast_service.METHODS)


def test_wape_is_explicitly_undefined_when_holdout_actual_is_zero():
    result = forecast_service._metrics([0.0, 0.0], [0.0, 1.0])

    assert result["wape_percent"] is None
    assert result["wape_status"] == "UNDEFINED_ZERO_ACTUAL"


def test_smape_is_explicitly_undefined_when_all_denominators_are_zero():
    result = forecast_service._metrics([0.0, 0.0], [0.0, 0.0])

    assert result["smape_percent"] is None
    assert result["smape_status"] == "UNDEFINED_ZERO_DENOMINATOR"


def test_smape_remains_defined_when_at_least_one_denominator_is_nonzero():
    result = forecast_service._metrics([0.0, 2.0], [0.0, 1.0])

    assert result["smape_percent"] == 66.6667
    assert result["smape_status"] == "DEFINED"


def test_build_report_preserves_live_provenance_and_forecast_dates():
    start = dt.date.today() - dt.timedelta(days=20)
    rows = [
        {
            "series_key": "menu-a",
            "label": "Menu A",
            "target_date": start + dt.timedelta(days=offset),
            "quantity": 10 + (offset % 3),
            "unit": "portion",
        }
        for offset in range(21)
    ]

    result = forecast_service.build_forecast_report(
        rows,
        horizon_days=7,
        min_history_days=14,
        min_backtest_points=7,
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata={
            "paid_order_count": 3,
            "paid_order_item_count": 5,
            "invalid_quantity_item_count": 0,
            "missing_unit_item_count": 0,
            "missing_menu_id_item_count": 0,
            "latest_paid_date": "2026-10-27",
            "latest_non_cancelled_date": "2026-10-27",
        },
    )

    assert result["status"] == "OK"
    assert result["data_mode"] == "live"
    assert result["source"] == "supabase_postgres"
    assert result["eligible_series_count"] == 1
    forecast = result["series"][0]["forecast"]
    assert len(forecast) == 7
    assert forecast[0]["target_date"] == (dt.date.today() + dt.timedelta(days=1)).isoformat()
    assert all(item["quantity"] >= 0 for item in forecast)
    assert all(item["lower_bound"] <= item["quantity"] <= item["upper_bound"] for item in forecast)
    assert result["quantity_contract"] == "order_items.quantity + explicit unit; no mixed units per series"
    assert result["paid_order_count"] == 3
    assert result["dependency_metadata"]["paid_order_count"] == 3
    assert "wape_percent" in result["model_comparison"]["RIDGE_LAG_7"]


def test_report_defaults_to_non_operational_fixture_provenance():
    result = forecast_service.build_forecast_report([
        {
            "series_key": "menu-fixture",
            "target_date": "2026-10-01",
            "quantity": 1,
            "unit": "portion",
        }
    ])

    assert result["data_mode"] == "fixture"
    assert result["source"] == "fixture"


def test_live_report_requires_explicit_supabase_provenance():
    with pytest.raises(forecast_service.ForecastUnavailable, match="supabase_postgres"):
        forecast_service.build_forecast_report(
            [{
                "series_key": "menu-a",
                "target_date": "2026-10-01",
                "quantity": 1,
                "unit": "portion",
            }],
            data_mode="live",
            dependency_metadata=LIVE_DEPENDENCY_METADATA,
        )


def test_ok_live_report_requires_dependency_metadata():
    rows = [
        {
            "series_key": "menu-a",
            "target_date": dt.date(2026, 10, 1) + dt.timedelta(days=offset),
            "quantity": 4,
            "unit": "portion",
        }
        for offset in range(21)
    ]

    with pytest.raises(forecast_service.ForecastUnavailable, match="Metadata dependency"):
        forecast_service.build_forecast_report(
            rows,
            horizon_days=7,
            min_history_days=14,
            min_backtest_points=7,
            as_of=dt.date(2026, 10, 21),
            data_mode="live",
            source="supabase_postgres",
        )


def test_live_report_rejects_non_supabase_source():
    with pytest.raises(forecast_service.ForecastUnavailable, match="supabase_postgres"):
        forecast_service.build_forecast_report(
            [],
            data_mode="live",
            source="test_fixture",
            dependency_metadata=LIVE_DEPENDENCY_METADATA,
        )


def test_backtest_includes_dependency_free_ml_model():
    values = [4, 5, 6, 5, 7, 8, 6] * 6

    result = forecast_service.backtest_series(values, min_history_days=14, min_backtest_points=7)

    assert "RIDGE_LAG_7" in result["methods"]
    assert result["methods"]["RIDGE_LAG_7"]["holdout_points"] == 28


def test_build_report_marks_short_history_without_inventing_forecast():
    rows = [
        {"series_key": "menu-a", "label": "Menu A", "target_date": "2026-10-01", "quantity": 4, "unit": "portion"}
    ]

    result = forecast_service.build_forecast_report(
        rows,
        horizon_days=7,
        min_history_days=14,
        as_of=dt.date(2026, 10, 1),
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata=LIVE_DEPENDENCY_METADATA,
    )

    assert result["status"] == "INSUFFICIENT_HISTORY"
    assert result["series"][0]["forecast"] == []
    assert result["series"][0]["backtest"]["selected_method"] is None
    assert result["warnings"]


def test_low_validation_history_does_not_emit_operational_forecast():
    result = forecast_service.build_forecast_report(
        [
            {
                "series_key": "menu-a",
                "label": "Menu A",
                "target_date": dt.date(2026, 10, 1) + dt.timedelta(days=offset),
                "quantity": 4,
                "unit": "portion",
            }
            for offset in range(15)
        ],
        horizon_days=7,
        min_history_days=14,
        min_backtest_points=7,
        as_of=dt.date(2026, 10, 15),
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata=LIVE_DEPENDENCY_METADATA,
    )

    assert result["status"] == "LOW_VALIDATION"
    assert result["eligible_series_count"] == 0
    assert result["series"][0]["backtest"]["status"] == "LOW_VALIDATION"
    assert result["series"][0]["forecast"] == []
    assert any("forecast operasional ditahan" in warning for warning in result["warnings"])


def test_one_insufficient_series_blocks_global_operational_report():
    rows = [
        {
            "series_key": "menu-ready",
            "label": "Menu Ready",
            "target_date": dt.date(2026, 10, 1) + dt.timedelta(days=offset),
            "quantity": 4,
            "unit": "portion",
        }
        for offset in range(21)
    ] + [
        {
            "series_key": "menu-new",
            "label": "Menu New",
            "target_date": "2026-10-21",
            "quantity": 2,
            "unit": "portion",
        }
    ]

    result = forecast_service.build_forecast_report(
        rows,
        horizon_days=7,
        min_history_days=14,
        min_backtest_points=7,
        as_of=dt.date(2026, 10, 21),
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata={
            "paid_order_count": 10,
            "paid_order_item_count": 20,
            "invalid_quantity_item_count": 0,
            "missing_unit_item_count": 0,
            "missing_menu_id_item_count": 0,
            "latest_paid_date": "2026-10-21",
            "latest_non_cancelled_date": "2026-10-21",
        },
    )

    assert result["status"] == "INSUFFICIENT_HISTORY"
    assert result["eligible_series_count"] == 1
    short = next(item for item in result["series"] if item["series_key"] == "menu-new")
    assert short["forecast"] == []


def test_build_report_labels_stale_observations():
    result = forecast_service.build_forecast_report(
        [
            {
                "series_key": "menu-a",
                "label": "Menu A",
                "target_date": dt.date(2020, 1, 1) + dt.timedelta(days=offset),
                "quantity": 4,
                "unit": "portion",
            }
            for offset in range(15)
        ],
        horizon_days=7,
        min_history_days=7,
        min_backtest_points=1,
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata=LIVE_DEPENDENCY_METADATA,
    )

    assert result["status"] == "STALE_DATA"
    assert result["data_age_days"] > result["freshness_threshold_days"]
    assert any("stale" in warning for warning in result["warnings"])


def test_any_stale_series_blocks_report_even_when_another_series_is_fresh():
    as_of = dt.date(2026, 10, 27)
    rows = [
        {
            "series_key": "menu-fresh",
            "label": "Menu Fresh",
            "target_date": dt.date(2026, 10, 13) + dt.timedelta(days=offset),
            "quantity": 4,
            "unit": "portion",
        }
        for offset in range(15)
    ] + [
        {
            "series_key": "menu-stale",
            "label": "Menu Stale",
            "target_date": dt.date(2026, 10, 1) + dt.timedelta(days=offset),
            "quantity": 4,
            "unit": "portion",
        }
        for offset in range(15)
    ]

    result = forecast_service.build_forecast_report(
        rows,
        horizon_days=7,
        min_history_days=7,
        min_backtest_points=1,
        stale_after_days=3,
        as_of=as_of,
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata=LIVE_DEPENDENCY_METADATA,
    )

    assert result["status"] == "STALE_DATA"
    assert result["stale_series_count"] == 1
    stale_series = next(item for item in result["series"] if item["series_key"] == "menu-stale")
    assert stale_series["data_age_days"] == 12
    assert any("Menu Stale" in warning for warning in result["warnings"])


def test_forecast_horizon_starts_after_each_series_observation_not_global_tail():
    as_of = dt.date(2026, 10, 21)
    rows = [
        {
            "series_key": "menu-newer",
            "label": "Menu Newer",
            "target_date": dt.date(2026, 10, 1) + dt.timedelta(days=offset),
            "quantity": 4,
            "unit": "portion",
        }
        for offset in range(21)
    ] + [
        {
            "series_key": "menu-older",
            "label": "Menu Older",
            "target_date": dt.date(2026, 10, 1) + dt.timedelta(days=offset),
            "quantity": 3,
            "unit": "portion",
        }
        for offset in range(20)
    ]

    result = forecast_service.build_forecast_report(
        rows,
        horizon_days=7,
        min_history_days=14,
        min_backtest_points=5,
        stale_after_days=3,
        as_of=as_of,
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata={
            "paid_order_count": 10,
            "paid_order_item_count": 20,
            "invalid_quantity_item_count": 0,
            "missing_unit_item_count": 0,
            "missing_menu_id_item_count": 0,
            "latest_paid_date": "2026-10-21",
            "latest_non_cancelled_date": "2026-10-21",
        },
    )

    by_key = {item["series_key"]: item for item in result["series"]}
    assert by_key["menu-newer"]["forecast"][0]["target_date"] == "2026-10-22"
    assert by_key["menu-older"]["forecast"][0]["target_date"] == "2026-10-21"
    assert by_key["menu-older"]["history_days"] == 20


def test_live_report_fails_closed_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: False)

    with pytest.raises(forecast_service.ForecastUnavailable):
        forecast_service.build_live_forecast_report()


def test_live_report_fails_closed_when_quantity_contract_query_fails(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)
    monkeypatch.setattr(db, "execute", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("missing quantity")))

    with pytest.raises(forecast_service.ForecastUnavailable, match="quantity"):
        forecast_service.build_live_forecast_report()


def test_mixed_units_fail_closed_instead_of_being_merged():
    with pytest.raises(forecast_service.ForecastUnavailable, match="unit campuran"):
        forecast_service.build_forecast_report(
            [
                {"series_key": "menu-a", "target_date": "2026-10-01", "quantity": 2, "unit": "portion"},
                {"series_key": "menu-a", "target_date": "2026-10-02", "quantity": 1, "unit": "kg"},
            ],
            data_mode="live",
            source="supabase_postgres",
        )


def test_missing_quantity_or_unit_is_rejected_instead_of_defaulted():
    with pytest.raises(forecast_service.ForecastUnavailable, match="quantity"):
        forecast_service.build_forecast_report(
            [{"series_key": "menu-a", "target_date": "2026-10-01", "unit": "portion"}],
            data_mode="live",
            source="supabase_postgres",
        )
    with pytest.raises(forecast_service.ForecastUnavailable, match="unit"):
        forecast_service.build_forecast_report(
            [{"series_key": "menu-a", "target_date": "2026-10-01", "quantity": 2, "unit": ""}],
            data_mode="live",
            source="supabase_postgres",
        )


@pytest.mark.parametrize(
    "row, message",
    [
        ({"label": "Menu A", "target_date": "2026-10-01", "quantity": 2, "unit": "portion"}, "series_key"),
        ({"series_key": "menu-a", "quantity": 2, "unit": "portion"}, "tanggal"),
        ({"series_key": "menu-a", "target_date": "not-a-date", "quantity": 2, "unit": "portion"}, "tanggal invalid"),
        (None, "object"),
    ],
)
def test_invalid_observation_shape_or_date_fails_closed(row, message):
    with pytest.raises(forecast_service.ForecastUnavailable, match=message):
        forecast_service.build_forecast_report(
            [row],
            data_mode="live",
            source="supabase_postgres",
            dependency_metadata=LIVE_DEPENDENCY_METADATA,
        )


def test_live_forecast_rejects_future_observation_as_unavailable():
    with pytest.raises(forecast_service.ForecastUnavailable, match="masa depan"):
        forecast_service.build_forecast_report(
            [{
                "series_key": "menu-a",
                "target_date": dt.date(2030, 1, 1),
                "quantity": 2,
                "unit": "portion",
            }],
            as_of=dt.date(2029, 12, 31),
            data_mode="live",
            source="supabase_postgres",
            dependency_metadata=LIVE_DEPENDENCY_METADATA,
        )


def test_live_query_does_not_default_quantity_or_unit(monkeypatch):
    captured = []
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)

    def fake_execute(sql, params=None):
        captured.append(sql)
        if "COUNT(DISTINCT o.order_id)" in sql:
            return [{
                "paid_order_count": 0,
                "paid_order_item_count": 0,
                "invalid_quantity_item_count": 0,
                "missing_unit_item_count": 0,
                "missing_menu_id_item_count": 0,
                "latest_paid_date": None,
                "latest_non_cancelled_date": None,
            }]
        return []

    monkeypatch.setattr(db, "execute", fake_execute)
    result = forecast_service.build_live_forecast_report()

    assert result["status"] == "NO_DATA"
    observation_sql = next(sql for sql in captured if "SUM(oi.quantity)" in sql)
    assert "COALESCE(oi.quantity" not in observation_sql
    assert "COALESCE(NULLIF(oi.unit" not in observation_sql
    metadata_sql = next(sql for sql in captured if "COUNT(DISTINCT o.order_id)" in sql)
    assert "oi.quantity <= 0" in metadata_sql
    assert result["dependency_metadata"] == {
        "paid_order_count": 0,
        "paid_order_item_count": 0,
        "invalid_quantity_item_count": 0,
        "missing_unit_item_count": 0,
        "missing_menu_id_item_count": 0,
        "latest_paid_date": None,
        "latest_non_cancelled_date": None,
    }
    assert result["paid_order_count"] == 0


def test_live_dependency_metadata_failure_is_not_defaulted(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)

    def fake_execute(sql, params=None):
        if "COUNT(DISTINCT o.order_id)" in sql:
            return [{"paid_order_count": None, "paid_order_item_count": 2}]
        return []

    monkeypatch.setattr(db, "execute", fake_execute)
    with pytest.raises(forecast_service.ForecastUnavailable, match="paid_order_count"):
        forecast_service.build_live_forecast_report()


def test_live_quality_metadata_rejects_invalid_paid_item_rows(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)

    def fake_execute(sql, params=None):
        if "COUNT(DISTINCT o.order_id)" in sql:
            return [{
                "paid_order_count": 1,
                "paid_order_item_count": 2,
                "invalid_quantity_item_count": 1,
                "missing_unit_item_count": 0,
                "missing_menu_id_item_count": 0,
                "latest_paid_date": "2026-10-27",
                "latest_non_cancelled_date": "2026-10-27",
            }]
        return []

    monkeypatch.setattr(db, "execute", fake_execute)
    with pytest.raises(forecast_service.ForecastUnavailable, match="invalid_quantity_item_count"):
        forecast_service.build_live_forecast_report()


def test_live_quality_metadata_rejects_paid_items_without_menu_id(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)

    def fake_execute(sql, params=None):
        if "COUNT(DISTINCT o.order_id)" in sql:
            return [{
                "paid_order_count": 1,
                "paid_order_item_count": 2,
                "invalid_quantity_item_count": 0,
                "missing_unit_item_count": 0,
                "missing_menu_id_item_count": 1,
                "latest_paid_date": "2026-10-27",
                "latest_non_cancelled_date": "2026-10-27",
            }]
        return []

    monkeypatch.setattr(db, "execute", fake_execute)
    with pytest.raises(forecast_service.ForecastUnavailable, match="missing_menu_id_item_count"):
        forecast_service.build_live_forecast_report()


def test_live_quality_metadata_cannot_be_omitted(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "check_migrations", lambda: True)

    def fake_execute(sql, params=None):
        if "COUNT(DISTINCT o.order_id)" in sql:
            return [{
                "paid_order_count": 1,
                "paid_order_item_count": 1,
                "latest_paid_date": "2026-10-27",
                "latest_non_cancelled_date": "2026-10-27",
            }]
        return []

    monkeypatch.setattr(db, "execute", fake_execute)
    with pytest.raises(forecast_service.ForecastUnavailable, match="invalid_quantity_item_count"):
        forecast_service.build_live_forecast_report()


def test_no_data_live_report_requires_dependency_metadata():
    with pytest.raises(forecast_service.ForecastUnavailable, match="Metadata dependency"):
        forecast_service.build_forecast_report(
            [],
            data_mode="live",
            source="supabase_postgres",
        )


def test_stale_live_report_rejects_invalid_dependency_metadata():
    rows = [
        {
            "series_key": "menu-a",
            "target_date": dt.date(2020, 1, 1) + dt.timedelta(days=offset),
            "quantity": 4,
            "unit": "portion",
        }
        for offset in range(15)
    ]

    with pytest.raises(forecast_service.ForecastUnavailable, match="latest_paid_date"):
        forecast_service.build_forecast_report(
            rows,
            horizon_days=7,
            min_history_days=7,
            min_backtest_points=1,
            data_mode="live",
            source="supabase_postgres",
            dependency_metadata={
                "paid_order_count": 10,
                "paid_order_item_count": 20,
                "invalid_quantity_item_count": 0,
                "missing_unit_item_count": 0,
                "missing_menu_id_item_count": 0,
                "latest_paid_date": "not-a-date",
                "latest_non_cancelled_date": None,
            },
        )


def test_stale_report_cannot_be_persisted():
    with pytest.raises(forecast_service.ForecastUnavailable, match="STALE_DATA"):
        forecast_service.persist_forecast_report(
            {"data_mode": "live", "status": "STALE_DATA"}
        )


def test_snapshot_rejects_non_object_report():
    with pytest.raises(forecast_service.ForecastUnavailable, match="object"):
        forecast_service.persist_forecast_report([])


def test_simulated_report_cannot_be_persisted():
    with pytest.raises(forecast_service.ForecastUnavailable, match="live"):
        forecast_service.persist_forecast_report(
            {"data_mode": "simulation", "status": "OK"}
        )


def test_fresh_report_persists_snapshot_rows_with_provenance(monkeypatch):
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
    report = {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": "forecast_backtest_v2",
        "dependency_metadata": {
            "paid_order_count": 10,
            "paid_order_item_count": 20,
            "invalid_quantity_item_count": 0,
            "missing_unit_item_count": 0,
            "missing_menu_id_item_count": 0,
            "latest_paid_date": "2026-10-27",
            "latest_non_cancelled_date": "2026-10-27",
        },
        "series": [{
            "series_key": "menu-a",
                "unit": "portion",
            "forecast": [
                {
                    "target_date": "2026-10-28",
                    "quantity": 4.5,
                    "unit": "portion",
                    "method": "MA7",
                    "lower_bound": 2.0,
                    "upper_bound": 7.0,
                        "interval_level": 0.8,
                },
                {
                    "target_date": "2026-10-29",
                    "quantity": 5.0,
                    "unit": "portion",
                    "method": "MA7",
                    "lower_bound": 2.5,
                    "upper_bound": 7.5,
                        "interval_level": 0.8,
                },
            ],
        }],
    }

    assert forecast_service.persist_forecast_report(report) == 2
    assert executed[0][0:2] == ("menu-a", "MENU")
    assert executed[0][3:8] == (4.5, "portion", "MA7", 2.0, 7.0)
    assert executed[0][8:] == ("live", "supabase_postgres", "forecast_backtest_v2")


def test_snapshot_rejects_live_report_without_supabase_provenance():
    with pytest.raises(forecast_service.ForecastUnavailable, match="Supabase live"):
        forecast_service.persist_forecast_report({
            "status": "OK",
            "data_mode": "live",
            "source": "test_fixture",
            "dependency_metadata": {
                "paid_order_count": 1,
                "paid_order_item_count": 1,
                "latest_paid_date": "2026-10-27",
                "latest_non_cancelled_date": "2026-10-27",
            },
            "series": [],
        })


def test_snapshot_rejects_wrong_calculation_version():
    with pytest.raises(forecast_service.ForecastUnavailable, match="calculation_version"):
        forecast_service.persist_forecast_report({
            "status": "OK",
            "data_mode": "live",
            "source": "supabase_postgres",
            "calculation_version": "legacy_forecast_v1",
            "dependency_metadata": LIVE_DEPENDENCY_METADATA,
            "series": [],
        })


@pytest.mark.parametrize(
    "series, message",
    [
        ([{"series_key": "menu-a", "unit": "portion", "forecast": []}], "identitas/unit/forecast"),
        ([{"series_key": "menu-a", "unit": "portion", "forecast": [{"target_date": "2026-10-28", "quantity": 2, "unit": "kg", "method": "MA7", "lower_bound": 1, "upper_bound": 3, "interval_level": 0.8}]}], "unit"),
        ([{"series_key": "menu-a", "unit": "portion", "forecast": [{"target_date": "2026-10-28", "quantity": 2, "unit": "portion", "method": "LEGACY", "lower_bound": 1, "upper_bound": 3, "interval_level": 0.8}]}], "method"),
        ([{"series_key": "menu-a", "unit": "portion", "forecast": [{"target_date": "2026-10-28", "quantity": 2, "unit": "portion", "method": "MA7", "lower_bound": 3, "upper_bound": 4, "interval_level": 0.8}]}], "Interval"),
    ],
)
def test_snapshot_rejects_malformed_forecast_rows(series, message):
    with pytest.raises(forecast_service.ForecastUnavailable, match=message):
        forecast_service.persist_forecast_report({
            "status": "OK",
            "data_mode": "live",
            "source": "supabase_postgres",
            "calculation_version": "forecast_backtest_v2",
            "dependency_metadata": LIVE_DEPENDENCY_METADATA,
            "series": series,
        })


def test_legacy_supply_chain_facade_fails_closed():
    with pytest.raises(DatabaseError, match="legacy dinonaktifkan"):
        analytics_ml_service.calculate_supply_chain_ml_forecast()


def test_legacy_demand_insights_facade_fails_closed():
    with pytest.raises(DatabaseError, match="Demand insights legacy"):
        analytics_ml_service.calculate_transaction_demand_insights()
