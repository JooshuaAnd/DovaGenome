from io import BytesIO

import pytest

from app.core.errors import ValidationError
from app.services.nutrition_service import calculate_recipe_nutrition
from app.services.recipe_document_service import extract_recipe_document


def test_csv_recipe_document_is_normalized_and_hashed():
    result = extract_recipe_document("menu.csv", b"bahan,gram\nayam,120\n")

    assert result["source_type"] == "csv"
    assert result["sha256"]
    assert "bahan | gram" in result["text"]
    assert "ayam | 120" in result["text"]


def test_xlsx_recipe_document_reads_sheet_rows():
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Resep"
    sheet.append(["Bahan", "Gram"])
    sheet.append(["Ayam", 120])
    stream = BytesIO()
    workbook.save(stream)

    result = extract_recipe_document("menu.xlsx", stream.getvalue())

    assert "[SHEET: Resep]" in result["text"]
    assert "Ayam | 120" in result["text"]


def test_recipe_document_rejects_unsupported_extensions():
    with pytest.raises(ValidationError):
        extract_recipe_document("menu.exe", b"not a recipe")


def test_nutrition_calculation_uses_4_4_9_macro_energy_formula():
    result = calculate_recipe_nutrition(
        [
            {
                "ingredient_name": "Ayam",
                "quantity": 100,
                "unit": "g",
                "calories_kcal_100g": 165,
                "protein_g_100g": 31,
                "carbs_g_100g": 0,
                "fat_g_100g": 3.6,
                "composition_basis": "raw",
            }
        ]
    )

    assert result["status"] == "VERIFIED"
    assert result["protein_g"] == 31
    assert result["macro_energy_pct"]["protein"] == 79.28


def test_nutrition_missing_composition_fails_closed():
    result = calculate_recipe_nutrition(
        [{"ingredient_name": "Bumbu", "quantity": 10, "unit": "g"}]
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["protein_g"] is None
    assert result["warnings"]
