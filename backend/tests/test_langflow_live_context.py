from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.services import langflow_context_service


client = TestClient(app)


def test_live_context_rejects_missing_or_wrong_token():
    with patch("app.api.routers.ai.settings.langflow_internal_token", "test-internal-token"):
        missing = client.get("/api/ai/internal/context")
        wrong = client.get(
            "/api/ai/internal/context",
            headers={"X-Dova-Internal-Token": "wrong-token"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401


def test_live_context_returns_verified_live_payload():
    payload = {
        "_data_mode": "live",
        "_source": "supabase_postgres_via_fastapi",
        "counts": {"menus": 1, "orders": 0, "customers": 0},
    }
    with (
        patch("app.api.routers.ai.settings.langflow_internal_token", "test-internal-token"),
        patch.object(langflow_context_service, "build_live_context", return_value=payload),
    ):
        response = client.get(
            "/api/ai/internal/context",
            headers={"X-Dova-Internal-Token": "test-internal-token"},
        )

    assert response.status_code == 200
    assert response.json() == payload


def test_live_context_helpers_use_explicit_weight_units():
    assert langflow_context_service._unit_to_grams(2, "kg") == 2000
    assert langflow_context_service._unit_to_grams(500, "g") == 500
    assert langflow_context_service._unit_to_grams(1, "liter") is None
    assert langflow_context_service._unit_to_kg(2500, "g") == 2.5


def test_live_menu_context_rejects_missing_allergen_mapping(monkeypatch):
    def fake_execute(sql, params=None):
        if "FROM menus" in sql:
            return [{
                "menu_id": "m1",
                "hari": "Senin",
                "nama_menu": "Menu A",
                "deskripsi": "",
                "published": True,
                "option_index": 1,
            }]
        if "FROM menu_ingredients" in sql:
            return [{
                "menu_id": "m1",
                "nama": "Bahan A",
                "sort_order": 1,
                "allergen_codes": None,
            }]
        return []

    monkeypatch.setattr(langflow_context_service.db, "execute", fake_execute)

    with pytest.raises(RuntimeError, match="allergen mapping"):
        langflow_context_service._load_menus()


def test_live_menu_context_rejects_missing_ingredient_mapping(monkeypatch):
    def fake_execute(sql, params=None):
        if "FROM menus" in sql:
            return [{
                "menu_id": "m1",
                "hari": "Senin",
                "nama_menu": "Menu A",
                "deskripsi": "",
                "published": True,
                "option_index": 1,
            }]
        if "FROM menu_ingredients" in sql:
            return []
        return []

    monkeypatch.setattr(langflow_context_service.db, "execute", fake_execute)

    with pytest.raises(RuntimeError, match="ingredient mapping"):
        langflow_context_service._load_menus()


def test_live_stock_context_rejects_missing_stock_without_zero_default(monkeypatch):
    monkeypatch.setattr(
        langflow_context_service.db,
        "execute",
        lambda *_args, **_kwargs: [{
            "ingredient_name": "Ayam",
            "current_stock": None,
            "unit": "kg",
            "status": "AMAN",
        }],
    )

    with pytest.raises(RuntimeError, match="current_stock/unit invalid"):
        langflow_context_service._load_stock()


def test_live_supplier_context_rejects_missing_moq_without_zero_default(monkeypatch):
    monkeypatch.setattr(
        langflow_context_service.db,
        "execute",
        lambda *_args, **_kwargs: [{
            "name": "Supplier A",
            "ingredient_name": "Ayam",
            "unit": "kg",
            "price_per_unit": 10,
            "moq": None,
            "lead_time_days": 2,
        }],
    )

    with pytest.raises(RuntimeError, match="moq"):
        langflow_context_service._load_suppliers()


def test_live_order_context_uses_paid_quantity_and_unit(monkeypatch):
    captured = {}

    def fake_execute(sql, params=None):
        captured["sql"] = sql
        return [{
            "order_id": "ORD-1",
            "customer_id": "cust-1",
            "customer_name": "Customer",
            "order_date": "2026-10-12",
            "menu": "Menu A",
            "quantity": 3,
            "unit": "portion",
            "order_meal_count": 3,
            "total": 90000,
        }]

    monkeypatch.setattr(langflow_context_service.db, "execute", fake_execute)

    rows = langflow_context_service._load_orders()

    assert rows[0]["quantity"] == 3
    assert rows[0]["unit"] == "portion"
    assert "o.payment_status = 'PAID'" in captured["sql"]
    assert "o.status <> 'CANCELLED'" in captured["sql"]
    assert "oi.quantity" in captured["sql"]
    assert "COALESCE(oi.quantity" not in captured["sql"]
    assert "COALESCE(NULLIF(oi.unit" not in captured["sql"]


def test_live_order_context_rejects_missing_quantity_or_unit(monkeypatch):
    monkeypatch.setattr(
        langflow_context_service.db,
        "execute",
        lambda *_args, **_kwargs: [{
            "order_id": "ORD-1",
            "customer_id": "cust-1",
            "customer_name": "Customer",
            "order_date": "2026-10-12",
            "menu": "Menu A",
            "quantity": None,
            "unit": "portion",
            "order_meal_count": 3,
            "total": 90000,
        }],
    )

    with pytest.raises(RuntimeError, match="quantity"):
        langflow_context_service._load_orders()


@pytest.mark.parametrize(
    "field, message",
    [
        ("customer_id", "identity/menu/date"),
        ("menu", "identity/menu/date"),
        ("order_date", "identity/menu/date"),
        ("total", "total"),
        ("order_meal_count", "meal_count"),
    ],
)
def test_live_order_context_rejects_missing_aggregate_fields(monkeypatch, field, message):
    row = {
        "order_id": "ORD-1",
        "customer_id": "cust-1",
        "customer_name": "Customer",
        "order_date": "2026-10-12",
        "menu": "Menu A",
        "quantity": 3,
        "unit": "portion",
        "order_meal_count": 3,
        "total": 90000,
    }
    row[field] = None
    monkeypatch.setattr(langflow_context_service.db, "execute", lambda *_args, **_kwargs: [row])

    with pytest.raises(RuntimeError, match=message):
        langflow_context_service._load_orders()


def test_live_order_context_rejects_silent_truncation(monkeypatch):
    monkeypatch.setattr(
        langflow_context_service.db,
        "execute",
        lambda *_args, **_kwargs: [{}] * (langflow_context_service.MAX_LIVE_ORDER_CONTEXT_ROWS + 1),
    )

    with pytest.raises(RuntimeError, match="melebihi batas aman"):
        langflow_context_service._load_orders()


def test_live_context_attaches_strict_forecast_reports(monkeypatch):
    menu = {
        "menu_id": "m1",
        "hari": "Senin",
        "name": "Menu A",
        "deskripsi": "",
        "ingredients": [],
        "allergen_codes": [],
        "allergens": [],
        "recipe_verification_status": "PENDING_VERIFICATION",
    }
    monkeypatch.setattr(langflow_context_service.db, "is_connected", lambda: True)
    monkeypatch.setattr(langflow_context_service.db, "check_migrations", lambda: True)
    monkeypatch.setattr(langflow_context_service, "_load_menus", lambda: ([menu], {"m1": menu}))
    monkeypatch.setattr(langflow_context_service, "_add_recipe_metadata", lambda *_args: ({}, []))
    monkeypatch.setattr(langflow_context_service, "_load_stock", lambda: ({}, {}))
    monkeypatch.setattr(langflow_context_service, "_load_suppliers", lambda: [])
    monkeypatch.setattr(langflow_context_service, "_load_customers", lambda: [])
    monkeypatch.setattr(langflow_context_service, "_load_orders", lambda: [])

    def fake_forecast_report(*, horizon_days, **_kwargs):
        return {
            "status": "STALE_DATA",
            "data_mode": "live",
            "source": "supabase_postgres",
            "calculation_version": "forecast_backtest_v2",
            "horizon_days": horizon_days,
            "paid_order_count": 4,
            "paid_order_item_count": 7,
            "invalid_quantity_item_count": 0,
            "missing_unit_item_count": 0,
            "missing_menu_id_item_count": 0,
            "latest_paid_date": "2026-10-12",
            "latest_non_cancelled_date": "2026-10-12",
            "dependency_metadata": {
                "paid_order_count": 4,
                "paid_order_item_count": 7,
                "invalid_quantity_item_count": 0,
                "missing_unit_item_count": 0,
                "missing_menu_id_item_count": 0,
                "latest_paid_date": "2026-10-12",
                "latest_non_cancelled_date": "2026-10-12",
            },
            "series": [],
            "warnings": ["stale"],
        }

    monkeypatch.setattr(
        "app.services.forecast_service.build_live_forecast_report",
        fake_forecast_report,
    )

    context = langflow_context_service.build_live_context()

    assert context["_data_mode"] == "live"
    assert context["forecast_backtest"]["7d"]["calculation_version"] == "forecast_backtest_v2"
    assert context["forecast_backtest"]["7d"]["paid_order_count"] == 4
    assert context["forecast_backtest"]["7d"]["latest_paid_date"] == "2026-10-12"
    assert context["forecast_backtest"]["30d"]["horizon_days"] == 30
    assert context["forecast_dependency_metadata"]["7d"]["paid_order_count"] == 4
    assert context["forecast_dependency_metadata"]["7d"]["invalid_quantity_item_count"] == 0
    assert context["forecast_dependency_metadata"]["7d"]["missing_menu_id_item_count"] == 0
    assert any("Forecast 7d dependency" in warning for warning in context["warnings"])


def test_internal_context_omits_customer_dietary_profiles_but_preserves_count(monkeypatch):
    menu = {
        "menu_id": "m1",
        "hari": "Senin",
        "name": "Menu A",
        "deskripsi": "",
        "ingredients": [],
        "allergen_codes": [],
        "allergens": [],
        "recipe_verification_status": "PENDING_VERIFICATION",
    }
    monkeypatch.setattr(langflow_context_service.db, "is_connected", lambda: True)
    monkeypatch.setattr(langflow_context_service.db, "check_migrations", lambda: True)
    monkeypatch.setattr(langflow_context_service, "_load_menus", lambda: ([menu], {"m1": menu}))
    monkeypatch.setattr(langflow_context_service, "_add_recipe_metadata", lambda *_args: ({}, []))
    monkeypatch.setattr(langflow_context_service, "_load_stock", lambda: ({}, {}))
    monkeypatch.setattr(langflow_context_service, "_load_suppliers", lambda: [])
    monkeypatch.setattr(langflow_context_service, "_load_customers", lambda: [
        {"customer_id": "c1", "name": "Customer", "allergy": ["susu"]},
    ])
    monkeypatch.setattr(langflow_context_service, "_load_orders", lambda: [])
    monkeypatch.setattr(
        "app.services.forecast_service.build_live_forecast_report",
        lambda *, horizon_days, **_kwargs: {
            "status": "NO_DATA",
            "data_mode": "live",
            "source": "supabase_postgres",
            "calculation_version": "forecast_backtest_v2",
            "horizon_days": horizon_days,
            "series": [],
            "warnings": [],
        },
    )

    context = langflow_context_service.build_live_context()

    assert context["customers"] == []
    assert context["counts"]["customers"] == 1
    assert context["customer_profile_context"] == "omitted_internal_aggregate"
    assert any("Profil dietary individual" in warning for warning in context["warnings"])
