from datetime import date

from app.services import admin_alert_service


def test_daily_stock_alert_is_idempotent_per_admin_and_day(monkeypatch):
    monkeypatch.setattr(admin_alert_service.db, "execute_one", lambda *args: {"ready": 1})
    monkeypatch.setattr(
        admin_alert_service.db,
        "execute",
        lambda *args: [
            {
                "id": 1,
                "ingredient_name": "Ayam",
                "current_stock": 2,
                "min_stock": 5,
                "unit": "kg",
                "status": "MENIPIS",
            }
        ],
    )
    results = iter([1, 0])
    monkeypatch.setattr(admin_alert_service.db, "execute_write", lambda *args: next(results))

    result = admin_alert_service.queue_daily_stock_alert(
        admin_chat_ids="111,111,222",
        day=date(2026, 10, 30),
    )

    assert result["status"] == "QUEUED"
    assert result["critical_items"] == 1
    assert result["admin_recipients"] == 2
    assert result["queued"] == 1
    assert result["duplicates"] == 1
    assert result["idempotent"] is True


def test_daily_stock_alert_does_not_queue_when_inventory_is_clear(monkeypatch):
    monkeypatch.setattr(admin_alert_service.db, "execute_one", lambda *args: {"ready": 1})
    monkeypatch.setattr(admin_alert_service.db, "execute", lambda *args: [])
    monkeypatch.setattr(
        admin_alert_service.db,
        "execute_write",
        lambda *args: (_ for _ in ()).throw(AssertionError("must not write")),
    )

    result = admin_alert_service.queue_daily_stock_alert(
        admin_chat_ids="111",
        day=date(2026, 10, 30),
    )

    assert result["status"] == "NO_ALERT"
    assert result["queued"] == 0
