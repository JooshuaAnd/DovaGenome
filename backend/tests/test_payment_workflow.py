"""Contract tests for payment idempotency and the paid-only kitchen boundary."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.core.errors import ConflictError, PermissionError_
from app.repositories import order_repo
from app.schemas.customer import CustomerOut
from app.schemas.payment import PaymentWebhookIn
from app.services import order_service, payment_service


def _customer() -> CustomerOut:
    return CustomerOut(customer_id="cust-1", username="cust1", display_name="Cust 1")


def test_webhook_signature_is_hmac_and_tamper_proof():
    raw = b'{"event_id":"evt-1"}'
    signature = payment_service.sign_payload(raw, "secret")

    assert payment_service.verify_signature(raw, signature, "secret") is True
    assert payment_service.verify_signature(raw + b" ", signature, "secret") is False
    assert payment_service.verify_signature(raw, "sha256=bad", "secret") is False


def test_create_intent_uses_server_total_and_replays_idempotency(monkeypatch):
    order = {
        "id": "order-db-1",
        "order_id": "ORD-1",
        "customer_id": "cust-1",
        "status": "PENDING",
        "payment_status": "UNPAID",
        "total": 125000,
    }
    attempt = {
        "payment_attempt_id": "attempt-1",
        "order_id": "ORD-1",
        "provider": "manual",
        "provider_payment_id": "",
        "idempotency_key": "idem-123456",
        "status": "INITIATED",
        "amount": 125000,
        "currency": "IDR",
        "expires_at": datetime.now(timezone.utc),
    }
    monkeypatch.setattr(order_repo, "get_order_by_id", lambda _: order)
    monkeypatch.setattr(order_repo, "update_fields", lambda *_args, **_kwargs: order)
    with patch.object(payment_service.db, "execute_one", side_effect=[None, attempt]) as query:
        result = payment_service.create_intent(
            "ORD-1", _customer(), provider="manual", idempotency_key="idem-123456"
        )

    assert result.amount == 125000
    assert query.call_count == 2
    insert_params = query.call_args_list[1].args[1]
    assert insert_params[3] == 125000


def test_create_intent_rejects_order_owned_by_another_customer(monkeypatch):
    order = {
        "id": "order-db-1",
        "order_id": "ORD-1",
        "customer_id": "someone-else",
        "status": "PENDING",
        "payment_status": "UNPAID",
        "total": 125000,
    }
    monkeypatch.setattr(order_repo, "get_order_by_id", lambda _: order)

    with pytest.raises(PermissionError_):
        payment_service.create_intent(
            "ORD-1", _customer(), provider="manual", idempotency_key="idem-123456"
        )


class _Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return next(self.rows, None)


class _Connection:
    def __init__(self, rows):
        self.cursor_obj = _Cursor(rows)

    def cursor(self):
        return self.cursor_obj


def test_success_webhook_releases_paid_order_and_kitchen_ticket(monkeypatch):
    payload = PaymentWebhookIn(
        provider="mock",
        event_id="evt-1",
        provider_payment_id="pay-1",
        order_id="ORD-1",
        amount=125000,
        currency="IDR",
        status="SUCCEEDED",
    )
    raw = json.dumps(payload.model_dump(), separators=(",", ":")).encode()
    attempt = {
        "payment_attempt_id": "attempt-1",
        "order_id": "ORD-1",
        "provider_payment_id": "",
        "status": "INITIATED",
        "amount": 125000,
        "currency": "IDR",
        "expires_at": None,
    }
    conn = _Connection([None, attempt])

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(payment_service.settings, "payment_webhook_secret", "secret")
    monkeypatch.setattr(payment_service.db, "get_conn", fake_connection)
    result = payment_service.process_webhook(
        payload,
        raw_body=raw,
        signature=payment_service.sign_payload(raw, "secret"),
    )

    assert result.payment_status == "PAID"
    assert result.kitchen_ticket_created is True
    assert any("INSERT INTO kitchen_tickets" in sql for sql, _ in conn.cursor_obj.executed)
    assert any("UPDATE orders" in sql for sql, _ in conn.cursor_obj.executed)


def test_order_cannot_enter_preparing_before_paid(monkeypatch):
    current = {
        "id": "order-db-1",
        "order_id": "ORD-1",
        "status": "PENDING",
        "payment_status": "UNPAID",
    }
    monkeypatch.setattr(order_repo, "get_order_by_doc_id", lambda _: current)

    with pytest.raises(ConflictError, match="belum lunas"):
        order_service.advance_status("order-db-1", "PREPARING", role="kitchen", actor="kitchen:k1")
