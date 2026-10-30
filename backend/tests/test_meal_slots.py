from types import SimpleNamespace

import pytest

from app.schemas.order import DaySelectionIn
from app.repositories.order_repo import order_selections
from app.services import order_service


def _menu(menu_id: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        menu_id=menu_id,
        nama_menu=name,
        published=True,
        hari="Senin",
        package_codes=["pkg_full"],
        available_for=lambda _package_code: True,
    )


def test_day_selection_accepts_three_meal_slots_and_keeps_slot_order(monkeypatch):
    menus = {
        "menu_pagi": _menu("menu_pagi", "Sarapan"),
        "menu_siang": _menu("menu_siang", "Makan siang"),
        "menu_malam": _menu("menu_malam", "Makan malam"),
    }
    monkeypatch.setattr(order_service.catalog_repo, "get_menu", menus.__getitem__)
    package = SimpleNamespace(code="pkg_full", name="Full Week", days=["Senin"])
    selections = [
        DaySelectionIn(hari="Senin", menu_id="menu_malam", meal_slot="dinner"),
        DaySelectionIn(hari="Senin", menu_id="menu_pagi", meal_slot="breakfast"),
        DaySelectionIn(hari="Senin", menu_id="menu_siang", meal_slot="lunch"),
    ]

    resolved = order_service.validate_selections(selections, package, schedule_days=["Senin"])

    assert [item["meal_slot"] for item in resolved] == ["breakfast", "lunch", "dinner"]
    assert [item["menu_id"] for item in resolved] == ["menu_pagi", "menu_siang", "menu_malam"]


def test_day_selection_rejects_unknown_meal_slot():
    with pytest.raises(ValueError):
        DaySelectionIn(hari="Senin", menu_id="menu_pagi", meal_slot="snack")


def test_normalized_order_keeps_meal_slot_for_legacy_and_new_rows():
    selections = order_selections({
        "menu_selections": [
            {"hari": "Senin", "menu_id": "menu_malam", "meal_slot": "dinner"},
            {"hari": "Senin", "menu_id": "menu_lama"},
        ],
    })

    assert [item["meal_slot"] for item in selections] == ["lunch", "dinner"]
