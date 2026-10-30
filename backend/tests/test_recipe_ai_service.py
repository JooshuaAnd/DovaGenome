from __future__ import annotations

import json

import pytest

from app.core.errors import AIError
from app.schemas.recipe import RecipeAiDraftRequestIn
from app.services.recipe_ai_service import RecipeAiService


def _draft_json() -> str:
    return json.dumps(
        {
            "dish_name": "Ayam Panggang",
            "summary": "Estimasi per porsi.",
            "components": [
                {
                    "ingredient_name": "Ayam fillet",
                    "quantity": 120,
                    "unit": "g",
                    "quantity_min": 100,
                    "quantity_max": 140,
                    "preparation": "panggang",
                    "allergen_codes": [],
                    "confidence": "MEDIUM",
                    "rationale": "Estimasi visual dan referensi resep.",
                }
            ],
            "sources": [],
            "safety_notes": ["Tinjau label bumbu."],
            "overall_confidence": "MEDIUM",
            "generated_by": "openai_recipe_draft",
        }
    )


def test_recipe_ai_draft_requires_photo_or_source() -> None:
    with pytest.raises(ValueError):
        RecipeAiDraftRequestIn()


def test_recipe_ai_draft_rejects_non_image_data_url() -> None:
    with pytest.raises(ValueError):
        RecipeAiDraftRequestIn(image_data_url="data:text/plain;base64,SGk=")


def test_recipe_ai_draft_extracts_response_text() -> None:
    assert RecipeAiService._output_text({"output_text": _draft_json()}) == _draft_json()
    assert RecipeAiService._output_text(
        {"output": [{"content": [{"type": "output_text", "text": _draft_json()}]}]}
    ) == _draft_json()


def test_recipe_ai_draft_is_unavailable_without_server_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(AIError):
        RecipeAiService().generate_draft(
            RecipeAiDraftRequestIn(source_url="https://example.com/resep"),
            menu_name="Menu uji",
        )
