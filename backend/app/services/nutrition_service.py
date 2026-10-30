"""Deterministic nutrition calculation from ingredient composition evidence."""

from __future__ import annotations

from typing import Any

MASS_TO_GRAMS = {"g": 1.0, "gram": 1.0, "grams": 1.0, "kg": 1000.0}


def calculate_recipe_nutrition(components: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate macros and energy percentages per recipe yield.

    Missing composition or unsupported units fail closed to ``UNAVAILABLE``;
    they never become zero. Composition values are expected per 100 g and the
    basis is retained in the result.
    """
    warnings: list[str] = []
    totals = {"calories_kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    bases: set[str] = set()
    usable = 0
    for component in components:
        unit = str(component.get("unit") or "").strip().lower()
        factor = MASS_TO_GRAMS.get(unit)
        name = str(component.get("ingredient_name") or component.get("ingredient_id") or "ingredient")
        if factor is None:
            warnings.append(f"{name}: unit {unit or 'kosong'} tidak didukung untuk nutrition.")
            continue
        composition = {
            key: component.get(key)
            for key in ("calories_kcal_100g", "protein_g_100g", "carbs_g_100g", "fat_g_100g")
        }
        if any(value is None for value in composition.values()):
            warnings.append(f"{name}: komposisi per 100 g belum tersedia.")
            continue
        grams = float(component.get("quantity") or 0) * factor
        ratio = grams / 100.0
        totals["calories_kcal"] += float(composition["calories_kcal_100g"]) * ratio
        totals["protein_g"] += float(composition["protein_g_100g"]) * ratio
        totals["carbs_g"] += float(composition["carbs_g_100g"]) * ratio
        totals["fat_g"] += float(composition["fat_g_100g"]) * ratio
        bases.add(str(component.get("composition_basis") or "unknown"))
        usable += 1

    if usable == 0:
        return {
            "status": "UNAVAILABLE",
            "calories_kcal": None,
            "protein_g": None,
            "carbs_g": None,
            "fat_g": None,
            "macro_energy_pct": {},
            "basis": "unknown",
            "warnings": warnings or ["Belum ada komposisi bahan dengan sumber."],
        }

    energy = totals["protein_g"] * 4 + totals["carbs_g"] * 4 + totals["fat_g"] * 9
    macro_pct = {
        "protein": round(totals["protein_g"] * 4 / energy * 100, 2) if energy else None,
        "carbs": round(totals["carbs_g"] * 4 / energy * 100, 2) if energy else None,
        "fat": round(totals["fat_g"] * 9 / energy * 100, 2) if energy else None,
    }
    if len(bases) > 1:
        warnings.append("Basis raw/cooked bercampur; review yield sebelum publikasi.")
    if usable < len(components):
        warnings.append("Sebagian bahan belum memiliki komposisi; hasil hanya parsial dan bukan VERIFIED.")
    return {
        "status": "ESTIMATED" if warnings else "VERIFIED",
        "calories_kcal": round(totals["calories_kcal"], 2),
        "protein_g": round(totals["protein_g"], 2),
        "carbs_g": round(totals["carbs_g"], 2),
        "fat_g": round(totals["fat_g"], 2),
        "macro_energy_pct": macro_pct,
        "basis": ",".join(sorted(bases)) or "unknown",
        "warnings": warnings,
    }
