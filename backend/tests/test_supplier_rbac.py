"""Phase 1 tests for supplier tenant resolution and RBAC."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_supplier
from app.api.deps import SupplierPrincipal
from app.api.routers.supplier import supplier_demand_forecast
from app.core.errors import PermissionError_
from app.main import app
from app.schemas.customer import CustomerOut

client = TestClient(app)


def _customer(*, role: str = "supplier") -> CustomerOut:
    return CustomerOut(
        customer_id="cust_supplier_1",
        username="supplier.user",
        role=role,
    )


def test_require_supplier_rejects_non_supplier_role():
    with pytest.raises(PermissionError_):
        require_supplier(_customer(role="customer"))


@patch("app.api.deps.supplier_repo.get_account_for_customer", return_value=None)
def test_require_supplier_rejects_unmapped_supplier(mock_account):
    with pytest.raises(PermissionError_):
        require_supplier(_customer())
    mock_account.assert_called_once_with("cust_supplier_1")


@patch(
    "app.api.deps.supplier_repo.get_account_for_customer",
    return_value={
        "customer_id": "cust_supplier_1",
        "supplier_id": "sup_1",
        "supplier_name": "Supplier One",
        "status": "active",
    },
)
def test_require_supplier_resolves_server_side_tenant(mock_account):
    principal = require_supplier(_customer())

    assert principal.customer.customer_id == "cust_supplier_1"
    assert principal.supplier_id == "sup_1"
    assert principal.supplier_name == "Supplier One"
    mock_account.assert_called_once_with("cust_supplier_1")


def test_supplier_demand_forecast_fails_closed_without_verified_material_contract():
    principal = SupplierPrincipal(
        customer=_customer(),
        supplier_id="sup_1",
        supplier_name="Supplier One",
    )

    with pytest.raises(Exception) as exc_info:
        supplier_demand_forecast(principal)

    assert getattr(exc_info.value, "status_code", None) == 410


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/supplier/pos"),
        ("get", "/api/supplier/catalog"),
        ("get", "/api/supplier/summary"),
        ("get", "/api/supplier/demand-forecast"),
    ],
)
def test_supplier_routes_require_authentication(method: str, path: str):
    response = getattr(client, method)(path)
    assert response.status_code == 401
