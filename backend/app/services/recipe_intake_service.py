"""Shared admin intake for recipe documents and Telegram photo uploads."""

from __future__ import annotations

import base64
import hashlib
import uuid
from pathlib import Path
from typing import Any

from app.core.domain import DAYS
from app.core.errors import ValidationError
from app.repositories import recipe_repo
from app.schemas.catalog import MenuIn
from app.schemas.recipe import RecipeAiDraftRequestIn
from app.services import catalog_service
from app.services.nutrition_service import calculate_recipe_nutrition
from app.services.recipe_ai_service import recipe_ai_service
from app.services.recipe_document_service import (
    MAX_FILE_BYTES,
    extract_recipe_document,
)

IMAGE_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
DOCUMENT_SUFFIXES = {".pdf", ".xlsx", ".csv", ".txt", ".md"}


def intake_recipe_upload(
    *,
    file_name: str,
    content: bytes,
    service_day: str,
    actor_id: str,
    menu_name: str = "",
    context: str = "",
    recipe_note: str = "",
    upload_channel: str = "web_admin",
) -> dict[str, Any]:
    """Generate and persist an unpublished menu with an unverified recipe draft."""
    safe_name = Path(file_name or ("Catatan admin" if recipe_note.strip() else "recipe")).name[:255]
    suffix = Path(safe_name).suffix.lower()
    if service_day not in DAYS:
        raise ValidationError(f"Hari layanan harus salah satu dari: {', '.join(DAYS)}.")
    recipe_note = recipe_note.strip()[:120_000]
    if not content and not recipe_note:
        raise ValidationError("Lampirkan file resep atau tulis catatan resep di chat.")
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("Ukuran file maksimal 10 MB.")
    if content and suffix not in IMAGE_MIME_BY_SUFFIX and suffix not in DOCUMENT_SUFFIXES:
        raise ValidationError("Format didukung: foto JPG/PNG/WebP, PDF, XLSX, CSV, TXT, atau MD.")
    if content and len(content) > MAX_FILE_BYTES:
        raise ValidationError("Ukuran file maksimal 10 MB.")
    if content and suffix in IMAGE_MIME_BY_SUFFIX and len(content) > 4_500_000:
        raise ValidationError("Foto maksimal 4,5 MB agar dapat diproses AI vision.")

    source_hash = hashlib.sha256(content if content else recipe_note.encode("utf-8")).hexdigest()
    source_text = recipe_note
    image_data_url = ""
    source_type = suffix.lstrip(".") if content else "admin_note"
    if content and suffix in IMAGE_MIME_BY_SUFFIX:
        mime = IMAGE_MIME_BY_SUFFIX[suffix]
        image_data_url = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
        source_type = "image"
    elif content:
        extracted = extract_recipe_document(safe_name, content)
        source_text = str(extracted["text"])
        source_type = str(extracted["source_type"])

    request = RecipeAiDraftRequestIn(
        image_data_url=image_data_url,
        source_text=source_text,
        source_name=safe_name,
        context=context.strip()[:1000],
    )
    proposed_name = menu_name.strip()[:200]
    ai_menu_hint = proposed_name or "Ambil nama menu dari sumber yang diunggah"
    draft = recipe_ai_service.generate_draft(request, menu_name=ai_menu_hint)
    final_name = proposed_name or draft.dish_name.strip()[:200]
    if len(final_name) < 2:
        raise ValidationError("Nama menu belum dapat dikenali. Isi nama menu lalu unggah ulang.")

    menu_id = f"recipe_draft_{uuid.uuid4().hex[:20]}"
    menu = catalog_service.upsert_menu(
        MenuIn(
            menu_id=menu_id,
            hari=service_day,
            nama_menu=final_name,
            deskripsi=draft.summary[:1000],
            alat_dapur_steril=["Perlu ditinjau operator sebelum dipublikasikan"],
            published=False,
        )
    )

    evidence = {
        "provider": draft.generated_by,
        "dish_name": draft.dish_name,
        "summary": draft.summary,
        "sources": [source.model_dump() for source in draft.sources],
        "safety_notes": draft.safety_notes,
        "overall_confidence": draft.overall_confidence,
        "nutrition": draft.nutrition.model_dump(mode="json"),
        "upload_channel": upload_channel,
        "source_name": safe_name,
        "source_type": source_type,
        "source_sha256": source_hash,
    }
    recipe_version_id = recipe_repo.create_draft_version(
        menu.menu_id,
        actor_id=actor_id,
        source_ref=source_hash,
        notes="Menu intake AI; unpublished dan menunggu review bahan, takaran, alergen, serta gizi.",
        metadata=evidence,
    )
    import_job_id = ""
    if content and source_type in {value.lstrip(".") for value in DOCUMENT_SUFFIXES} and source_text:
        import_job_id = recipe_repo.create_import_job(
            recipe_version_id=recipe_version_id,
            file_name=safe_name,
            source_type=source_type,
            sha256=source_hash,
            byte_size=len(content),
            extracted_text=source_text,
            created_by=actor_id,
        )
    try:
        recipe_repo.apply_ai_draft(
            recipe_version_id,
            [component.model_dump() for component in draft.components],
            evidence=evidence,
            actor_id=actor_id,
        )
    except Exception as exc:
        recipe_repo.update_import_job(import_job_id, status="FAILED", error_message=type(exc).__name__)
        raise
    recipe_repo.update_import_job(import_job_id, status="DRAFT_READY")

    evidence_components = recipe_repo.list_components(recipe_version_id)
    nutrition_from_composition = calculate_recipe_nutrition(evidence_components)
    return {
        "menu_id": menu.menu_id,
        "menu_name": menu.nama_menu,
        "service_day": menu.hari,
        "published": menu.published,
        "menu_status": "UNPUBLISHED_DRAFT",
        "recipe_version_id": recipe_version_id,
        "recipe_status": "PENDING_VERIFICATION",
        "import_job_id": import_job_id,
        "source_name": safe_name,
        "source_type": source_type,
        "source_sha256": source_hash,
        "ai_draft": draft.model_dump(mode="json"),
        "nutrition_from_composition": nutrition_from_composition,
        "review_required": True,
    }
