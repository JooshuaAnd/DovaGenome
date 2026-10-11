"""
Characterization / Baseline Regression Tests (Fase 0).

Memastikan endpoint inti backend berfungsi stabil dan output sesuai kontrak
sebelum perubahan dilakukan di fase-fase berikutnya.
"""

from __future__ import annotations

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.catalog import PackageOut, AllergenOut, MenuOut

client = TestClient(app)


def test_health_check_endpoints():
    """Memastikan /health dan /api/health mengembalikan 200 dengan status ok/degraded."""
    res_root = client.get("/health")
    assert res_root.status_code == 200
    assert res_root.json()["status"] in ("ok", "degraded")

    res_api = client.get("/api/health")
    assert res_api.status_code == 200
    assert res_api.json()["status"] in ("ok", "degraded")


@patch("app.services.catalog_service.list_packages")
@patch("app.services.catalog_service.list_allergens")
@patch("app.services.catalog_service.list_menus")
def test_catalog_endpoints(mock_menus, mock_allergens, mock_packages):
    """Memastikan katalog publik dapat diakses dan mengembalikan data sesuai schema."""
    mock_packages.return_value = [
        PackageOut(code="pkg_full", name="Full Week", days=["Senin", "Selasa"], price=150000, description="")
    ]
    mock_allergens.return_value = [
        AllergenOut(code="alg_gluten", label="Gluten", risiko="Tinggi", active=True, category="allergy")
    ]
    mock_menus.return_value = [
        MenuOut(menu_id="menu_senin_ayam", hari="Senin", nama_menu="Ayam Panggang", deskripsi="", published=True)
    ]

    res_pkgs = client.get("/api/catalog/packages")
    assert res_pkgs.status_code == 200
    pkgs = res_pkgs.json()
    assert isinstance(pkgs, list)
    assert len(pkgs) == 1
    assert pkgs[0]["code"] == "pkg_full"

    res_allergens = client.get("/api/catalog/allergens")
    assert res_allergens.status_code == 200
    allergens = res_allergens.json()
    assert isinstance(allergens, list)
    assert len(allergens) == 1
    assert allergens[0]["code"] == "alg_gluten"

    res_menus = client.get("/api/catalog/menus")
    assert res_menus.status_code == 200
    menus = res_menus.json()
    assert isinstance(menus, list)
    assert len(menus) == 1
    assert menus[0]["menu_id"] == "menu_senin_ayam"


def test_unauthenticated_protected_endpoints():
    """Memastikan endpoint privat menolak akses tanpa token (401)."""
    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 401

    res_passport = client.get("/api/customers/me/passport")
    assert res_passport.status_code == 401

    res_order = client.post("/api/orders", json={})
    assert res_order.status_code == 401
