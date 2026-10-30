from __future__ import annotations

from datetime import date

import pytest

from app.core.errors import ValidationError
from app.services import production_batch_service
from app.services.production_batch_service import _allocate_lots, _from_grams, _grams


def test_mass_conversion_is_explicit_and_reversible() -> None:
    assert _grams(1, "kg") == 1000
    assert _grams(250, "g") == 250
    assert _from_grams(1250, "kg") == 1.25
    assert _from_grams(1250, "g") == 1250


def test_non_mass_recipe_units_are_held_before_weighing() -> None:
    with pytest.raises(ValidationError):
        _grams(2, "sendok makan")


def test_fefo_allocator_splits_consumption_across_expiry_order():
    class Cursor:
        def __init__(self):
            self.updates = []

        def execute(self, sql, params):
            self.updates.append((sql, params))

        def fetchall(self):
            return [
                {"lot_id": "lot-expiring", "quantity_on_hand": 1, "unit": "kg"},
                {"lot_id": "lot-later", "quantity_on_hand": 2, "unit": "kg"},
            ]

    cursor = Cursor()
    allocations = _allocate_lots(
        cursor,
        ingredient_id="ing-1",
        unit="kg",
        quantity=2.5,
    )

    assert allocations == [
        {"lot_id": "lot-expiring", "quantity": 1.0, "unit": "kg"},
        {"lot_id": "lot-later", "quantity": 1.5, "unit": "kg"},
    ]
    assert len(cursor.updates) == 3  # select + one update per lot


def test_paid_batch_planner_holds_everything_when_one_recipe_is_unverified(monkeypatch):
    monkeypatch.setattr(production_batch_service.db, "check_production_batch_migrations", lambda: True)
    monkeypatch.setattr(
        production_batch_service.db,
        "execute",
        lambda *args: [{"menu_id": "menu-a", "planned_portions": 4}],
    )
    monkeypatch.setattr(production_batch_service.db, "execute_one", lambda *args: None)
    monkeypatch.setattr(
        production_batch_service,
        "create_batch",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("partial batch must not be written")),
    )

    result = production_batch_service.plan_batches_from_paid_orders(
        service_date=date(2026, 10, 30),
        meal_slot="lunch",
        site_code="main-kitchen",
        actor_id="kitchen-1",
    )

    assert result["status"] == "REQUIRES_VERIFICATION"
    assert result["planned_batches"] == []
    assert result["blocked_menus"][0]["reason"] == "RECIPE_NOT_VERIFIED"


def test_paid_batch_planner_returns_existing_batch_on_retry(monkeypatch):
    monkeypatch.setattr(production_batch_service.db, "check_production_batch_migrations", lambda: True)
    monkeypatch.setattr(
        production_batch_service.db,
        "execute",
        lambda *args: [{"menu_id": "menu-a", "planned_portions": 4}],
    )
    responses = iter([
        {"recipe_version_id": "recipe-a"},
        {"batch_id": "batch-a", "status": "OPEN"},
    ])
    monkeypatch.setattr(production_batch_service.db, "execute_one", lambda *args: next(responses))
    monkeypatch.setattr(
        production_batch_service,
        "create_batch",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("retry must not create a duplicate")),
    )

    result = production_batch_service.plan_batches_from_paid_orders(
        service_date=date(2026, 10, 30),
        meal_slot="lunch",
        site_code="main-kitchen",
        actor_id="kitchen-1",
    )

    assert result["status"] == "EXISTING"
    assert result["planned_batches"][0]["idempotent"] is True


def test_legacy_order_rows_are_not_reinterpreted_as_breakfast(monkeypatch):
    monkeypatch.setattr(production_batch_service.db, "check_production_batch_migrations", lambda: True)

    def missing_slot(*args):
        raise RuntimeError('column "meal_slot" does not exist')

    monkeypatch.setattr(production_batch_service.db, "execute", missing_slot)

    result = production_batch_service.plan_batches_from_paid_orders(
        service_date=date(2026, 10, 30),
        meal_slot="breakfast",
        site_code="main-kitchen",
        actor_id="kitchen-1",
    )

    assert result["status"] == "NO_PAID_DEMAND"
    assert result["planned_batches"] == []

