"""
Tes unit untuk lapisan repository Fase 0.

Semua tes menggunakan mock psycopg2 — tidak memerlukan koneksi database nyata.
Jalankan:
    cd backend
    python -m pytest tests/test_repositories.py -v
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────
def _make_row(**kwargs) -> dict[str, Any]:
    return dict(kwargs)


# ── test_order_repo.normalize_order ─────────────────────────────────────────
class TestNormalizeOrder:
    def test_basic_fields(self):
        from app.repositories.order_repo import normalize_order

        doc = {
            "id": "uuid-1",
            "order_id": "ORD-20260101-ABC123",
            "customer_name": "Budi",
            "package_code": "pkg_full",
            "subscription_type": "Full Week",
            "status": "PENDING",
            "schedule_days": ["Senin", "Selasa"],
            "menu_selections": [{"hari": "Senin", "menu_id": "menu_senin_abc"}],
            "selected_allergens": ["alg_gluten"],
            "dietary_profile": "Tidak ada",
            "meal_count": 2,
            "schema_version": "v3",
        }
        result = normalize_order(doc)
        assert result["order_id"] == "ORD-20260101-ABC123"
        assert result["customer_name"] == "Budi"
        assert result["status"] == "PENDING"
        assert result["schedule_days"] == ["Senin", "Selasa"]
        assert result["selected_allergens"] == ["alg_gluten"]
        assert result["has_safety_flags"] is True

    def test_unknown_status_defaults_to_pending(self):
        from app.repositories.order_repo import normalize_order

        doc = {
            "order_id": "ORD-X",
            "status": "UNKNOWN_STATUS",
            "customer_name": "A",
            "subscription_type": "x",
            "schedule_days": [],
            "selected_allergens": [],
            "meal_count": 0,
        }
        result = normalize_order(doc)
        assert result["status"] == "PENDING"

    def test_allergen_prefix_cleanup(self):
        from app.repositories.order_repo import normalize_order

        doc = {
            "order_id": "ORD-Y",
            "status": "PENDING",
            "customer_name": "X",
            "subscription_type": "y",
            "schedule_days": [],
            "selected_allergens": ["alg_alg_telur", "alg_gluten"],
            "dietary_profile": "",
            "meal_count": 0,
        }
        result = normalize_order(doc)
        # alg_alg_telur harus dinormalisasi menjadi alg_telur
        assert "alg_telur" in result["selected_allergens"]
        assert "alg_alg_telur" not in result["selected_allergens"]
        assert "alg_gluten" in result["selected_allergens"]


# ── test_order_repo.generate_order_id ────────────────────────────────────────
class TestGenerateOrderId:
    def test_format(self):
        from app.repositories.order_repo import generate_order_id

        oid = generate_order_id()
        assert oid.startswith("ORD-")
        parts = oid.split("-")
        assert len(parts) == 3
        assert len(parts[2]) == 6

    def test_unique(self):
        from app.repositories.order_repo import generate_order_id

        ids = {generate_order_id() for _ in range(50)}
        assert len(ids) == 50


# ── test_order_repo.build_kitchen_notes ──────────────────────────────────────
class TestBuildKitchenNotes:
    def test_with_allergens(self):
        from app.repositories.order_repo import build_kitchen_notes

        note = build_kitchen_notes(["Gluten", "Susu"])
        assert "PROTOKOL WAJIB" in note
        assert "Gluten" in note
        assert "Susu" in note

    def test_no_allergens(self):
        from app.repositories.order_repo import build_kitchen_notes

        note = build_kitchen_notes([])
        assert "prosedur steril standar" in note.lower()


# ── test_catalog_repo.menu_doc_id ────────────────────────────────────────────
class TestMenuDocId:
    def test_basic(self):
        from app.repositories.catalog_repo import menu_doc_id

        mid = menu_doc_id("Senin", "Ayam Panggang Rosemary")
        assert mid.startswith("menu_senin_")
        assert "ayam" in mid
        assert "rosemary" in mid

    def test_empty_nama(self):
        from app.repositories.catalog_repo import menu_doc_id

        mid = menu_doc_id("Rabu", "")
        assert mid == "menu_rabu"

    def test_slug_max_length(self):
        from app.repositories.catalog_repo import menu_doc_id

        long_name = "A" * 200
        mid = menu_doc_id("Kamis", long_name)
        slug_part = mid[len("menu_kamis_"):]
        assert len(slug_part) <= 48


# ── test_catalog_repo._detect_codes ──────────────────────────────────────────
class TestDetectCodes:
    @patch("app.repositories.catalog_repo.list_allergens")
    def test_detect_seafood(self, mock_allergens):
        from app.repositories.catalog_repo import _detect_codes
        from app.schemas.catalog import AllergenOut

        mock_allergens.return_value = [
            AllergenOut(code="alg_seafood", label="Bebas Seafood", active=True),
        ]
        codes = _detect_codes(["Fillet Kakap Putih", "ikan segar"])
        assert "alg_seafood" in codes

    @patch("app.repositories.catalog_repo.list_allergens")
    def test_negation_stripped(self, mock_allergens):
        from app.repositories.catalog_repo import _detect_codes
        from app.schemas.catalog import AllergenOut

        mock_allergens.return_value = [
            AllergenOut(code="alg_kedelai", label="Bebas Kedelai", active=True),
        ]
        # "tanpa kecap kedelai" seharusnya TIDAK mendeteksi kedelai
        codes = _detect_codes(["Saus bawang putih tanpa kecap kedelai"])
        assert "alg_kedelai" not in codes


# ── test_customer_repo ────────────────────────────────────────────────────────
class TestCustomerRepo:
    def test_new_customer_id_format(self):
        from app.repositories.customer_repo import new_customer_id

        cid = new_customer_id()
        assert cid.startswith("cust_")
        assert len(cid) > 10

    def test_new_customer_id_unique(self):
        from app.repositories.customer_repo import new_customer_id

        ids = {new_customer_id() for _ in range(50)}
        assert len(ids) == 50

    @patch("app.repositories.customer_repo.db")
    def test_find_by_username_returns_none(self, mock_db):
        from app.repositories.customer_repo import find_by_username

        mock_db.execute_one.return_value = None
        result = find_by_username("nonexistent")
        assert result is None

    @patch("app.repositories.customer_repo.db")
    def test_get_by_id_not_found(self, mock_db):
        from app.repositories.customer_repo import get_by_id
        from app.core.errors import NotFoundError

        mock_db.execute_one.return_value = None
        with pytest.raises(NotFoundError):
            get_by_id("cust_nonexistent")

    @patch("app.repositories.customer_repo.db")
    def test_to_public_maps_fields(self, mock_db):
        from app.repositories.customer_repo import to_public

        row = {
            "customer_id": "cust_abc",
            "username": "budi",
            "display_name": "Budi S",
            "phone": "08123",
            "role": "customer",
            "status": "active",
            "telegram_chat_id": 12345,
            "telegram_verified": True,
            "telegram_link_code": "ABCD1234",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        out = to_public(row)
        assert out.customer_id == "cust_abc"
        assert out.username == "budi"
        assert out.telegram_verified is True


# ── test_supabase._build_dsn ──────────────────────────────────────────────────
class TestBuildDsn:
    def test_supabase_url_takes_priority(self):
        """Bila SUPABASE_URL diisi, pakai langsung."""
        with patch("app.repositories.supabase.settings") as mock_settings:
            mock_settings.supabase_url = "postgresql://user:pass@host:5432/db"
            mock_settings.supabase_db_api_endpoint = ""
            mock_settings.supabase_db_application_token = ""
            mock_settings.supabase_db_name = "postgres"
            mock_settings.supabase_db_user = "postgres"
            mock_settings.supabase_db_port = 5432

            from app.repositories.supabase import _build_dsn
            dsn = _build_dsn()
            assert dsn == "postgresql://user:pass@host:5432/db"

    def test_builds_from_components(self):
        with patch("app.repositories.supabase.settings") as mock_settings:
            mock_settings.supabase_url = ""
            mock_settings.supabase_db_api_endpoint = "db.xxxx.supabase.co"
            mock_settings.supabase_db_application_token = "mypassword"
            mock_settings.supabase_db_name = "postgres"
            mock_settings.supabase_db_user = "postgres"
            mock_settings.supabase_db_port = 5432

            from app.repositories.supabase import _build_dsn
            dsn = _build_dsn()
            assert "db.xxxx.supabase.co" in dsn
            assert "postgres" in dsn

    def test_raises_when_no_host(self):
        from app.core.errors import DatabaseError

        with patch("app.repositories.supabase.settings") as mock_settings:
            mock_settings.supabase_url = ""
            mock_settings.supabase_db_api_endpoint = ""
            mock_settings.supabase_db_application_token = "token"
            mock_settings.supabase_db_name = "postgres"
            mock_settings.supabase_db_user = "postgres"
            mock_settings.supabase_db_port = 5432

            from app.repositories.supabase import _build_dsn
            with pytest.raises(DatabaseError, match="SUPABASE_DB_API_ENDPOINT"):
                _build_dsn()


# ── test_domain ────────────────────────────────────────────────────────────────
class TestDomain:
    def test_table_constants_exist(self):
        from app.core.domain import (
            TABLE_PACKAGES, TABLE_ALLERGENS, TABLE_MENUS,
            TABLE_ORDERS, TABLE_CUSTOMERS, TABLE_DIETARY_PASSPORTS,
        )
        assert TABLE_PACKAGES == "packages"
        assert TABLE_ALLERGENS == "allergens"
        assert TABLE_MENUS == "menus"
        assert TABLE_ORDERS == "orders"
        assert TABLE_CUSTOMERS == "customers"
        assert TABLE_DIETARY_PASSPORTS == "dietary_passports"

    def test_backward_compat_aliases(self):
        from app.core.domain import (
            COLLECTION_PACKAGES, COLLECTION_ALLERGENS,
            COLLECTION_MENUS, COLLECTION_ORDERS, COLLECTION_CUSTOMERS,
        )
        assert COLLECTION_PACKAGES == "packages"
        assert COLLECTION_ALLERGENS == "allergens"
        assert COLLECTION_MENUS == "menus"
        assert COLLECTION_ORDERS == "orders"
        assert COLLECTION_CUSTOMERS == "customers"

    def test_no_astra_collection_names(self):
        import app.core.domain as d
        # Pastikan nama koleksi Astra lama tidak ada sebagai konstanta aktif
        for attr in dir(d):
            val = getattr(d, attr)
            if isinstance(val, str):
                assert "kitchen_orders" not in val, f"{attr} masih memakai nama Astra"
                assert "catering_packages" not in val, f"{attr} masih memakai nama Astra"
                assert "allergen_definitions" not in val, f"{attr} masih memakai nama Astra"
