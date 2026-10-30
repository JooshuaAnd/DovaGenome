"""AI-assisted draft creation for admin recipe review.

Drafts are intentionally non-authoritative: they may estimate a per-portion
BOM, but cannot set ingredient or recipe verification statuses.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.config import settings
from app.core.errors import AIError
from app.core.logging import get_logger
from app.schemas.recipe import RecipeAiDraftOut, RecipeAiDraftRequestIn

log = get_logger("dova.recipe_ai")


_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "dish_name", "summary", "components", "sources", "safety_notes",
        "overall_confidence", "generated_by",
    ],
    "properties": {
        "dish_name": {"type": "string"},
        "summary": {"type": "string"},
        "overall_confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
        "generated_by": {"type": "string"},
        "nutrition": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "calories_kcal": {"type": ["number", "null"]},
                "protein_g": {"type": ["number", "null"]},
                "carbs_g": {"type": ["number", "null"]},
                "fat_g": {"type": ["number", "null"]},
                "protein_energy_pct": {"type": ["number", "null"]},
                "carbs_energy_pct": {"type": ["number", "null"]},
                "fat_energy_pct": {"type": ["number", "null"]},
                "basis": {"type": "string"},
                "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
        "safety_notes": {"type": "array", "items": {"type": "string"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "url", "excerpt"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "excerpt": {"type": "string"},
                },
            },
        },
        "components": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "ingredient_name", "quantity", "unit", "quantity_min", "quantity_max",
                    "preparation", "allergen_codes", "confidence", "rationale",
                ],
                "properties": {
                    "ingredient_name": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "quantity_min": {"type": ["number", "null"]},
                    "quantity_max": {"type": ["number", "null"]},
                    "preparation": {"type": "string"},
                    "allergen_codes": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "rationale": {"type": "string"},
                },
            },
        },
    },
}


class RecipeAiService:
    @property
    def configured(self) -> bool:
        return bool(
            settings.ai_mode != "disabled"
            and settings.langflow_api_url.strip()
            and settings.langflow_api_key.strip()
            and settings.langflow_flow_id.strip()
        )

    def generate_draft(self, request: RecipeAiDraftRequestIn, *, menu_name: str) -> RecipeAiDraftOut:
        return self._generate_via_langflow(request, menu_name=menu_name)

    def _generate_via_langflow(
        self,
        request: RecipeAiDraftRequestIn,
        *,
        menu_name: str,
    ) -> RecipeAiDraftOut:
        """Use the configured Chef BOB Langflow flow for recipe intake."""
        if not self.configured:
            raise AIError(
                "AI resep belum tersambung ke Langflow. Periksa LANGFLOW_API_URL, LANGFLOW_API_KEY, LANGFLOW_FLOW_ID, dan AI_MODE di backend."
            )

        from app.services.langflow_service import langflow_service

        prompt = self._prompt(request, menu_name)
        response = langflow_service.ask(
            prompt,
            session_id=f"admin-recipe-{uuid.uuid4().hex}",
            system_context=(
                "Anda sedang membuat draft resep untuk admin. Balas hanya dengan satu objek JSON valid "
                "yang memiliki dish_name, summary, components, sources, safety_notes, overall_confidence, "
                "nutrition, generated_by. Jangan gunakan markdown atau teks di luar JSON. "
                "Komponen harus memuat ingredient_name, quantity, unit, quantity_min, quantity_max, "
                "preparation, allergen_codes, confidence, rationale. Nutrition memuat calories_kcal, "
                "protein_g, carbs_g, fat_g, protein_energy_pct, carbs_energy_pct, fat_energy_pct, basis, "
                "confidence, warnings. Nilai gizi adalah estimasi AI, tidak terverifikasi. "
                "Semua field list wajib berupa array; sources berisi object {title,url,excerpt}; "
                "safety_notes dan nutrition.warnings berupa array string; nutrition.basis maksimal 40 karakter."
            ),
            files=[request.image_data_url] if request.image_data_url else None,
            timeout_seconds=settings.langflow_recipe_timeout_seconds,
            max_retries=0,
        )
        if response.degraded or not response.reply.strip():
            reason = response.reason_code or response.readiness_state
            if reason == "timeout":
                hint = (
                    f" Flow resep tidak selesai dalam batas {settings.langflow_recipe_timeout_seconds:g} detik. "
                    "Periksa eksekusi model di Langflow; "
                    "coba kirim catatan lebih ringkas atau tanpa lampiran besar."
                )
            elif reason in {"http_401", "http_403"}:
                hint = (
                    " LANGFLOW_API_KEY harus berisi API key Langflow yang valid dan punya akses ke flow ini; "
                    "setelah mengubah .env, muat ulang backend."
                )
            elif reason == "http_500":
                hint = (
                    " Langflow mengembalikan HTTP 500. Periksa detail error terbaru pada log eksekusi "
                    "POST /api/v1/run di Langflow; penyebabnya bisa berasal dari komponen flow atau provider model."
                )
            else:
                hint = " Periksa LANGFLOW_API_URL, LANGFLOW_API_KEY, dan LANGFLOW_FLOW_ID."
            raise AIError(
                f"Langflow Chef BOB gagal menjalankan draft ({response.readiness_state}: {reason}).{hint}"
            )
        try:
            start = response.reply.find("{")
            if start < 0:
                raise ValueError("JSON object missing")
            parsed, _ = json.JSONDecoder().raw_decode(response.reply[start:])
            if not isinstance(parsed, dict):
                raise ValueError("JSON object expected")

            # Langflow's chat model sometimes serializes list fields as prose
            # and may invent source titles. Keep only provenance supplied by
            # the admin and normalize the common string/list shape mismatch.
            source_title = request.source_name.strip() or request.source_url.strip()
            parsed["sources"] = (
                [{
                    "title": source_title,
                    "url": request.source_url.strip(),
                    "excerpt": request.source_text.strip()[:1000],
                }]
                if source_title or request.source_url.strip()
                else []
            )
            safety_notes = parsed.get("safety_notes", [])
            if isinstance(safety_notes, str):
                parsed["safety_notes"] = [safety_notes.strip()] if safety_notes.strip() else []
            nutrition = parsed.get("nutrition")
            if isinstance(nutrition, dict):
                if isinstance(nutrition.get("warnings"), str):
                    warning = nutrition["warnings"].strip()
                    nutrition["warnings"] = [warning] if warning else []
                if isinstance(nutrition.get("basis"), str):
                    nutrition["basis"] = nutrition["basis"].strip()[:40]
            draft = RecipeAiDraftOut.model_validate(parsed)
        except (ValueError, TypeError) as exc:
            log.warning("langflow_recipe_draft_invalid detail=%s", type(exc).__name__)
            raise AIError(
                "Chef BOB belum menghasilkan format draft resep yang dapat dibaca. Coba kirim catatan resep lebih lengkap."
            ) from exc

        return draft.model_copy(update={"generated_by": "langflow_chef_bob_recipe_draft"})

    @staticmethod
    def _output_text(body: dict[str, Any]) -> str:
        direct = body.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        for item in body.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text
        raise ValueError("no structured output")

    @staticmethod
    def _prompt(request: RecipeAiDraftRequestIn, menu_name: str) -> str:
        source = request.source_url or "Tidak ada link eksternal; gunakan catatan, dokumen, dan lampiran yang dikirim admin."
        document = request.source_text.strip()
        document_block = (
            "\n\nDOKUMEN RESEP YANG DIUPLOAD (bukan bukti terverifikasi):\n"
            + document[:100_000]
            if document
            else ""
        )
        return f"""
Anda membantu operator katering membuat DRAFT recipe/BOM per SATU porsi.
Menu internal yang harus dianalisis: {menu_name}.
Referensi URL dari operator: {source}
Nama dokumen upload: {request.source_name or '-'}.
Konteks tambahan operator: {request.context or '-'}
{document_block}

Analisis lampiran foto/dokumen dan catatan admin bila tersedia. Jangan mencari atau mengarang sumber eksternal;
isi sources hanya jika sumber memang diberikan. Jangan mengklaim nilai pasti dari foto atau dokumen.
Semua quantity adalah estimasi per porsi, berikan range bila tidak pasti. Kembalikan hanya JSON sesuai schema.
Gunakan kode alergen ringkas seperti alg_gluten, alg_dairy, alg_egg, alg_soy, alg_peanut, alg_tree_nut,
alg_fish, alg_shellfish, alg_sesame bila memang beralasan. Tandai confidence LOW jika bahan/gramasi tidak jelas.
Jangan menyatakan menu aman untuk alergi dan jangan menghapus bahan yang tidak terlihat jelas. URL sumber wajib
ditulis pada sources jika tersedia dari pencarian. Ini adalah draft yang akan ditinjau manusia.
""".strip()


recipe_ai_service = RecipeAiService()
