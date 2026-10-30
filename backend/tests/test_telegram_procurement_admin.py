import pytest
from fastapi import HTTPException

from app.api.routers.admin import _require_telegram_procurement_admin
from app.core.config import settings


def test_telegram_procurement_route_rejects_unallowlisted_chat(monkeypatch):
    monkeypatch.setattr(settings, "langflow_internal_token", "secret")
    monkeypatch.setattr(settings, "telegram_admin_chat_ids", "123")
    monkeypatch.setattr(settings, "telegram_admin_customer_id", "admin-1")

    with pytest.raises(HTTPException) as error:
        _require_telegram_procurement_admin("secret", "999")

    assert error.value.status_code == 403


def test_telegram_procurement_route_requires_auditable_admin_customer(monkeypatch):
    monkeypatch.setattr(settings, "langflow_internal_token", "secret")
    monkeypatch.setattr(settings, "telegram_admin_chat_ids", "123")
    monkeypatch.setattr(settings, "telegram_admin_customer_id", "")

    with pytest.raises(HTTPException) as error:
        _require_telegram_procurement_admin("secret", "123")

    assert error.value.status_code == 503


def test_telegram_procurement_route_accepts_exact_token_and_chat(monkeypatch):
    monkeypatch.setattr(settings, "langflow_internal_token", "secret")
    monkeypatch.setattr(settings, "telegram_admin_chat_ids", "123,456")
    monkeypatch.setattr(settings, "telegram_admin_customer_id", "admin-1")

    assert _require_telegram_procurement_admin("secret", "456") == "456"
