"""Contract API untuk verifikasi ingredient dan recipe/BOM."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiModel


class RecipeComponentIn(ApiModel):
    ingredient_id: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    preparation: str = Field(default="", max_length=500)
    sort_order: int = Field(default=0, ge=0)


class RecipeComponentsReplaceIn(ApiModel):
    components: list[RecipeComponentIn] = Field(min_length=1, max_length=200)


class IngredientVerifyIn(ApiModel):
    allergen_codes: list[str] = Field(default_factory=list, max_length=50)
    evidence: dict = Field(default_factory=dict)


class RecipeVerifyIn(ApiModel):
    cross_contact_risk: Literal["LOW", "MEDIUM"]
    notes: str = Field(default="", max_length=1000)


class RecipeAiDraftRequestIn(ApiModel):
    """Input for a non-authoritative recipe draft generated from AI."""

    image_data_url: str = Field(default="", max_length=6_500_000)
    source_url: str = Field(default="", max_length=2048)
    source_text: str = Field(default="", max_length=120_000)
    source_name: str = Field(default="", max_length=255)
    context: str = Field(default="", max_length=1000)

    @field_validator("image_data_url")
    @classmethod
    def validate_image_data_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        allowed_prefixes = (
            "data:image/jpeg;base64,",
            "data:image/png;base64,",
            "data:image/webp;base64,",
        )
        if not value.startswith(allowed_prefixes):
            raise ValueError("Foto harus JPEG, PNG, atau WebP.")
        return value

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Link referensi harus diawali http:// atau https://.")
        return value

    @model_validator(mode="after")
    def require_input(self) -> "RecipeAiDraftRequestIn":
        if not self.image_data_url and not self.source_url and not self.source_text:
            raise ValueError("Unggah foto, isi link referensi, atau upload dokumen resep.")
        return self


class RecipeAiDraftSource(ApiModel):
    title: str = Field(default="", max_length=300)
    url: str = Field(default="", max_length=2048)
    excerpt: str = Field(default="", max_length=1000)


class RecipeNutritionDraft(ApiModel):
    calories_kcal: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    protein_energy_pct: float | None = Field(default=None, ge=0, le=100)
    carbs_energy_pct: float | None = Field(default=None, ge=0, le=100)
    fat_energy_pct: float | None = Field(default=None, ge=0, le=100)
    basis: str = Field(default="unknown", max_length=40)
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    warnings: list[str] = Field(default_factory=list, max_length=20)


class RecipeAiDraftComponent(ApiModel):
    ingredient_name: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, le=100_000)
    unit: str = Field(min_length=1, max_length=32)
    quantity_min: float | None = Field(default=None, gt=0, le=100_000)
    quantity_max: float | None = Field(default=None, gt=0, le=100_000)
    preparation: str = Field(default="", max_length=500)
    allergen_codes: list[str] = Field(default_factory=list, max_length=50)
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    rationale: str = Field(default="", max_length=600)

    @model_validator(mode="after")
    def validate_range(self) -> "RecipeAiDraftComponent":
        if self.quantity_min and self.quantity_max and self.quantity_min > self.quantity_max:
            raise ValueError("quantity_min tidak boleh melebihi quantity_max.")
        return self


class RecipeAiDraftOut(ApiModel):
    dish_name: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=1500)
    components: list[RecipeAiDraftComponent] = Field(min_length=1, max_length=100)
    sources: list[RecipeAiDraftSource] = Field(default_factory=list, max_length=10)
    safety_notes: list[str] = Field(default_factory=list, max_length=20)
    overall_confidence: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    nutrition: RecipeNutritionDraft = Field(default_factory=RecipeNutritionDraft)
    generated_by: str = Field(default="openai_recipe_draft", max_length=100)


class RecipeAiDraftApplyIn(ApiModel):
    """Admin-approved AI proposal. This deliberately stays PENDING_VERIFICATION."""

    dish_name: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=1500)
    components: list[RecipeAiDraftComponent] = Field(min_length=1, max_length=100)
    sources: list[RecipeAiDraftSource] = Field(default_factory=list, max_length=10)
    safety_notes: list[str] = Field(default_factory=list, max_length=20)
    overall_confidence: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    nutrition: RecipeNutritionDraft = Field(default_factory=RecipeNutritionDraft)


class IngredientBatchVerifyItem(ApiModel):
    ingredient_id: str = Field(min_length=1, max_length=120)
    allergen_codes: list[str] = Field(default_factory=list, max_length=50)


class IngredientBatchVerifyIn(ApiModel):
    ingredients: list[IngredientBatchVerifyItem] = Field(min_length=1, max_length=200)
