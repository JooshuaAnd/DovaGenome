import pytest

from app.repositories import supabase as db
from app.services import inventory_service


def _forecast(status="OK"):
    return {
        "status": status,
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": "forecast_backtest_v2",
        "latest_observation_date": "2026-10-27",
        "data_age_days": 0,
        "horizon_days": 2,
        "series": [
            {
                "series_key": "menu-a",
                "forecast": [
                    {"target_date": "2026-10-28", "quantity": 10, "unit": "portion"},
                    {"target_date": "2026-10-29", "quantity": 20, "unit": "portion"},
                ],
            }
        ],
    }


def _complete_records():
    recipe_rows = [
        {
            "menu_id": "menu-a",
            "recipe_version_id": "recipe-a",
            "status": "VERIFIED",
            "yield_quantity": 1,
            "yield_unit": "portion",
            "ingredient_id": "ing-a",
            "ingredient_name": "Ayam",
            "quantity": 100,
            "unit": "g",
            "verification_status": "VERIFIED",
            "ingredient_status": "VERIFIED",
        },
        {
            "menu_id": "menu-a",
            "recipe_version_id": "recipe-a",
            "status": "VERIFIED",
            "yield_quantity": 1,
            "yield_unit": "portion",
            "ingredient_id": "ing-b",
            "ingredient_name": "Beras",
            "quantity": 80,
            "unit": "g",
            "verification_status": "VERIFIED",
            "ingredient_status": "VERIFIED",
        },
    ]
    inventory_rows = [
        {"ingredient_id": "ing-a", "ingredient_name": "Ayam", "current_stock": 0.5, "unit": "kg"},
        {"ingredient_id": "ing-b", "ingredient_name": "Beras", "current_stock": 2, "unit": "kg"},
    ]
    supplier_rows = [
        {"ingredient_id": "ing-a", "supplier_id": "sup-a", "supplier_name": "Supplier A", "unit": "kg", "lead_time_days": 2},
        {"ingredient_id": "ing-b", "supplier_id": "sup-b", "supplier_name": "Supplier B", "unit": "kg", "lead_time_days": 1},
    ]
    return recipe_rows, inventory_rows, supplier_rows


def test_replenishment_plan_calculates_ss_and_rop_only_for_verified_contract():
    recipe_rows, inventory_rows, supplier_rows = _complete_records()

    report = inventory_service.build_replenishment_plan(
        published_menu_ids=["menu-a"],
        recipe_rows=recipe_rows,
        inventory_rows=inventory_rows,
        supplier_rows=supplier_rows,
        forecast_report=_forecast(),
    )

    assert report["status"] == "OK"
    assert report["data_mode"] == "live"
    assert report["calculation_version"] == "inventory_replenishment_v1"
    assert len(report["items"]) == 2
    assert report["items"][0]["reorder_point_rop"] >= 0
    assert report["roq"]["status"] == "UNAVAILABLE"


def test_stale_forecast_and_unverified_bom_never_emit_inventory_numbers():
    recipe_rows, inventory_rows, supplier_rows = _complete_records()
    recipe_rows[0]["status"] = "PENDING_VERIFICATION"

    report = inventory_service.build_replenishment_plan(
        published_menu_ids=["menu-a"],
        recipe_rows=recipe_rows,
        inventory_rows=inventory_rows,
        supplier_rows=supplier_rows,
        forecast_report=_forecast(status="STALE_DATA"),
    )

    assert report["status"] == "REQUIRES_VERIFICATION"
    assert report["items"] == []
    assert report["forecast_status"] == "STALE_DATA"
    assert report["readiness"]["unresolved_bom"]


def test_missing_supplier_blocks_plan_without_fallback():
    recipe_rows, inventory_rows, _supplier_rows = _complete_records()

    report = inventory_service.build_replenishment_plan(
        published_menu_ids=["menu-a"],
        recipe_rows=recipe_rows,
        inventory_rows=inventory_rows,
        supplier_rows=[],
        forecast_report=_forecast(),
    )

    assert report["status"] == "REQUIRES_VERIFICATION"
    assert report["items"] == []
    assert report["readiness"]["missing_supplier_ingredient_ids"] == ["ing-a", "ing-b"]


def test_live_inventory_plan_fails_closed_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: False)

    with pytest.raises(inventory_service.InventoryPlanUnavailable, match="tidak terhubung"):
        inventory_service.build_live_inventory_replenishment_report()


def _inventory_history():
    return [
        {
            "ingredient_id": "ing-a",
            "date": "2026-10-25",
            "unit": "kg",
            "opening_stock": 100,
            "receipt_quantity": 0,
            "adjustment_quantity": 0,
            "actual_demand": 60,
            "forecast_demand": 50,
            "reorder_point": 5,
            "target_stock": 10,
        },
        {
            "ingredient_id": "ing-a",
            "date": "2026-10-26",
            "unit": "kg",
            "opening_stock": 40,
            "receipt_quantity": 0,
            "adjustment_quantity": 0,
            "actual_demand": 70,
            "forecast_demand": 80,
            "reorder_point": 5,
            "target_stock": 20,
        },
    ]


def test_inventory_backtest_reports_stockout_fill_rate_and_excess_stock():
    report = inventory_service.build_inventory_backtest(_inventory_history())

    assert report["status"] == "OK"
    assert report["data_mode"] == "backtest"
    assert report["operational"] is False
    assert report["calculation_version"] == "inventory_backtest_v1"
    assert report["metrics"]["actual_demand"] == 130
    assert report["metrics"]["fulfilled_demand"] == 100
    assert report["metrics"]["unfulfilled_demand"] == 30
    assert report["metrics"]["stockout_days"] == 1
    assert report["metrics"]["fill_rate"] == 0.769231
    assert report["metrics"]["excess_stock_quantity"] == 30
    assert report["metrics"]["forecast_wape"] == 0.153846
    assert report["ingredients"][0]["stockout_rate"] == 0.5


def test_inventory_backtest_rejects_missing_fields_without_zero_default():
    row = _inventory_history()[0]
    row.pop("receipt_quantity")

    report = inventory_service.build_inventory_backtest([row, _inventory_history()[1]])

    assert report["status"] == "INVALID_HISTORY"
    assert report["metrics"] == {}
    assert "row_0_missing_receipt_quantity" in report["readiness"]["invalid_reasons"]


def test_inventory_backtest_rejects_opening_stock_continuity_break():
    rows = _inventory_history()
    rows[1]["opening_stock"] = 41

    report = inventory_service.build_inventory_backtest(rows)

    assert report["status"] == "INVALID_HISTORY"
    assert any(
        reason.startswith("ing-a_opening_stock_break_")
        for reason in report["readiness"]["invalid_reasons"]
    )


def test_inventory_backtest_marks_short_history_without_metrics():
    report = inventory_service.build_inventory_backtest([_inventory_history()[0]])

    assert report["status"] == "INSUFFICIENT_HISTORY"
    assert report["metrics"] == {}
    assert report["readiness"]["insufficient_history_ingredient_ids"] == ["ing-a"]


def test_inventory_backtest_does_not_turn_zero_demand_into_zero_fill_rate():
    rows = _inventory_history()
    rows[0]["actual_demand"] = 0
    rows[0]["forecast_demand"] = 0
    rows[1]["opening_stock"] = 100
    rows[1]["actual_demand"] = 0
    rows[1]["forecast_demand"] = 0

    report = inventory_service.build_inventory_backtest(rows)

    assert report["status"] == "OK"
    assert report["metrics"]["fill_rate"] is None
    assert report["metrics"]["fill_rate_status"] == "UNDEFINED_ZERO_DEMAND"
    assert report["metrics"]["forecast_wape"] is None
    assert report["metrics"]["forecast_wape_status"] == "UNDEFINED_ZERO_ACTUAL"
