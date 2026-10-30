"""Phase 2 tests for the deterministic recipe verification safety gate."""

from types import SimpleNamespace

from app.models.enums import SafetyLevel
from app.schemas.catalog import MenuOut
from app.services import safety_service


def _catalog_context():
    return SimpleNamespace(labels={}, categories={})


def _menu(**updates) -> MenuOut:
    values = {
        "menu_id": "menu_test",
        "hari": "Senin",
        "nama_menu": "Menu Test",
        "deskripsi": "",
        "published": True,
        "bahan_detail": [],
        "allergen_codes": [],
        "allergen_labels": [],
        "alat_dapur_steril": [],
        "recipe_version_id": "recipe_test",
        "recipe_verification_status": "PENDING_VERIFICATION",
        "recipe_cross_contact_risk": "UNKNOWN",
        "recipe_has_unresolved_components": True,
    }
    values.update(updates)
    return MenuOut(**values)


def test_pending_recipe_is_requires_verification_not_safe():
    result = safety_service.check_menu(
        "Senin", _menu(), set(), catalog=_catalog_context()
    )

    assert result.level == SafetyLevel.REQUIRES_VERIFICATION
    assert result.is_recommended is False


def test_verified_complete_recipe_can_be_eligible():
    result = safety_service.check_menu(
        "Senin",
        _menu(
            recipe_verification_status="VERIFIED",
            recipe_cross_contact_risk="LOW",
            recipe_has_unresolved_components=False,
        ),
        set(),
        catalog=_catalog_context(),
    )

    assert result.level == SafetyLevel.SAFE
    assert result.is_recommended is True


def test_known_critical_conflict_remains_blocked_even_if_recipe_pending():
    menu = _menu(allergen_codes=["alg_gluten"], allergen_labels=["Gluten"])
    context = SimpleNamespace(
        labels={"alg_gluten": "Gluten"},
        categories={"alg_gluten": "allergy"},
    )

    result = safety_service.check_menu("Senin", menu, {"alg_gluten"}, catalog=context)

    assert result.level == SafetyLevel.BLOCKED
    assert result.is_recommended is False
