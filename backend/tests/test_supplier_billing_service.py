from datetime import date

import pytest

from app.core.errors import ValidationError
from app.services import supplier_billing_service


def _enable_billing_migration(monkeypatch):
    monkeypatch.setattr(
        supplier_billing_service.db,
        "check_supplier_billing_migrations",
        lambda: True,
    )


def test_pay_on_delivery_requires_po_reference_before_database_write(monkeypatch):
    _enable_billing_migration(monkeypatch)

    with pytest.raises(ValidationError, match="PO reference"):
        supplier_billing_service.submit_invoice(
            supplier_id="sup-1",
            actor_id="customer-1",
            invoice_number="INV-1",
            payment_terms="PAY_ON_DELIVERY",
            amount=100_000,
            due_date=date(2026, 10, 31),
            idempotency_key="invoice-key-1",
        )


def test_weekly_invoice_requires_a_valid_period(monkeypatch):
    _enable_billing_migration(monkeypatch)

    with pytest.raises(ValidationError, match="Periode"):
        supplier_billing_service.submit_invoice(
            supplier_id="sup-1",
            actor_id="customer-1",
            invoice_number="INV-2",
            payment_terms="WEEKLY_INVOICE",
            amount=100_000,
            due_date=date(2026, 11, 7),
            idempotency_key="invoice-key-2",
            period_start=date(2026, 11, 7),
            period_end=date(2026, 11, 1),
        )


def test_unknown_payment_method_is_rejected_before_database_write(monkeypatch):
    _enable_billing_migration(monkeypatch)

    with pytest.raises(ValidationError, match="MANUAL"):
        supplier_billing_service.record_payment(
            invoice_id="invoice-1",
            actor_id="admin-1",
            amount=100_000,
            payment_method="LIVE_GATEWAY",
            payment_reference="",
            idempotency_key="payment-key-1",
        )
