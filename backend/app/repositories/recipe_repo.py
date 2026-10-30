"""Repository untuk review dan verifikasi recipe/BOM."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.repositories import supabase as db

log = get_logger("dova.repo.recipe")


def _review_query() -> str:
    return """
        SELECT
            rv.recipe_version_id,
            rv.menu_id,
            m.nama_menu,
            rv.version_no,
            rv.status,
            rv.source,
            rv.source_ref,
            rv.cross_contact_risk,
            rv.verified_by,
            rv.verified_at,
            rv.notes,
            COUNT(rc.recipe_component_id) AS component_count,
            COUNT(rc.recipe_component_id) FILTER (
                WHERE rc.ingredient_id IS NULL
                   OR rc.quantity IS NULL
                   OR rc.unit = 'UNKNOWN'
                   OR rc.verification_status <> 'VERIFIED'
                   OR i.verification_status <> 'VERIFIED'
            ) AS unresolved_component_count
        FROM recipe_versions rv
        JOIN menus m ON m.menu_id = rv.menu_id
        LEFT JOIN recipe_components rc
          ON rc.recipe_version_id = rv.recipe_version_id
        LEFT JOIN ingredients i
          ON i.ingredient_id = rc.ingredient_id
        WHERE (%s = '' OR rv.menu_id = %s)
        GROUP BY rv.recipe_version_id, rv.menu_id, m.nama_menu, m.hari, m.option_index,
                 rv.version_no, rv.status, rv.source, rv.source_ref,
                 rv.cross_contact_risk, rv.verified_by, rv.verified_at, rv.notes
        ORDER BY m.hari, m.option_index, rv.version_no DESC
    """


def list_reviews(*, menu_id: str = "") -> list[dict[str, Any]]:
    return db.execute(_review_query(), (menu_id, menu_id))


def list_ingredients(*, search: str = "", limit: int = 500) -> list[dict[str, Any]]:
    """Search the canonical ingredient master for manual BOM editing."""
    term = search.strip()
    return db.execute(
        """
        SELECT ingredient_id, name, default_unit, verification_status, allergen_codes
        FROM ingredients
        WHERE verification_status <> 'RETIRED'
          AND (%s = '' OR name ILIKE %s)
        ORDER BY name
        LIMIT %s
        """,
        (term, f"%{term}%", max(1, min(limit, 1000))),
    )


def get_version(recipe_version_id: str) -> dict[str, Any]:
    row = db.execute_one(
        """
        SELECT rv.*, m.nama_menu
        FROM recipe_versions rv
        JOIN menus m ON m.menu_id = rv.menu_id
        WHERE rv.recipe_version_id = %s
        """,
        (recipe_version_id,),
    )
    if not row:
        raise NotFoundError("Recipe version tidak ditemukan.")
    return row


def create_draft_version(
    menu_id: str,
    *,
    actor_id: str,
    source_ref: str,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    """Create an unpublished menu's first recipe version and audit event."""
    audit_metadata = json.dumps(metadata or {}, ensure_ascii=False)
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO recipe_versions
                    (menu_id, version_no, status, source, source_ref, notes, metadata)
                VALUES (
                    %s,
                    (SELECT COALESCE(MAX(version_no), 0) + 1 FROM recipe_versions WHERE menu_id = %s),
                    'DRAFT', 'admin_recipe_intake', %s, %s, %s::jsonb
                )
                RETURNING recipe_version_id
                """,
                (menu_id, menu_id, source_ref, notes[:1000], audit_metadata),
            )
            row = cur.fetchone()
            version_id = str(row["recipe_version_id"] if isinstance(row, dict) else row[0])
            cur.execute(
                """
                INSERT INTO recipe_verification_events
                    (recipe_version_id, action, verifier_id, evidence, notes)
                VALUES (%s, 'CREATED', %s, %s::jsonb, %s)
                """,
                (version_id, actor_id, audit_metadata, "Menu dan recipe dibuat dari admin recipe intake."),
            )
    return version_id


def create_import_job(
    *,
    recipe_version_id: str,
    file_name: str,
    source_type: str,
    sha256: str,
    byte_size: int,
    extracted_text: str,
    created_by: str,
) -> str:
    """Persist bounded document provenance when migration 013 is available.

    The optional write is compatibility-safe while the migration is pending;
    the AI draft itself remains usable and is still non-authoritative.
    """
    try:
        row = db.execute_one(
            """
            INSERT INTO recipe_import_jobs
                (recipe_version_id, file_name, source_type, sha256,
                 byte_size, extracted_text, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, 'EXTRACTED', %s)
            RETURNING import_job_id
            """,
            (recipe_version_id, file_name, source_type, sha256, byte_size,
             extracted_text, created_by),
        )
        return str(row["import_job_id"]) if row else ""
    except Exception as exc:
        log.info("recipe_import_jobs pending; provenance write skipped: %s", type(exc).__name__)
        return ""


def update_import_job(import_job_id: str, *, status: str, error_message: str = "") -> None:
    if not import_job_id:
        return
    try:
        db.execute_write(
            """
            UPDATE recipe_import_jobs
            SET status = %s, error_message = %s, updated_at = NOW()
            WHERE import_job_id = %s
            """,
            (status, error_message[:500], import_job_id),
        )
    except Exception as exc:
        log.info("recipe_import_jobs status update skipped: %s", type(exc).__name__)


def list_components(recipe_version_id: str) -> list[dict[str, Any]]:
    get_version(recipe_version_id)
    query_with_nutrition = """
        SELECT rc.recipe_component_id, rc.recipe_version_id, rc.ingredient_id,
               i.name AS ingredient_name, i.verification_status AS ingredient_status,
               i.allergen_codes, i.calories_kcal_100g, i.protein_g_100g,
               i.carbs_g_100g, i.fat_g_100g, i.composition_basis,
               rc.quantity, rc.unit, rc.preparation,
               rc.verification_status, rc.source, rc.sort_order
        FROM recipe_components rc
        LEFT JOIN ingredients i ON i.ingredient_id = rc.ingredient_id
        WHERE rc.recipe_version_id = %s
        ORDER BY rc.sort_order, rc.recipe_component_id
        """
    try:
        return db.execute(query_with_nutrition, (recipe_version_id,))
    except Exception:
        # Migration 013 is intentionally gated behind the backup/restore
        # checkpoint. Keep the existing review screen readable on a database
        # that has migrations 001-012 but not the optional nutrition columns.
        return db.execute(
            """
            SELECT rc.recipe_component_id, rc.recipe_version_id, rc.ingredient_id,
                   i.name AS ingredient_name, i.verification_status AS ingredient_status,
                   i.allergen_codes,
                   rc.quantity, rc.unit, rc.preparation,
                   rc.verification_status, rc.source, rc.sort_order
            FROM recipe_components rc
            LEFT JOIN ingredients i ON i.ingredient_id = rc.ingredient_id
            WHERE rc.recipe_version_id = %s
            ORDER BY rc.sort_order, rc.recipe_component_id
            """,
            (recipe_version_id,),
        )


def list_nutrition_components(recipe_version_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Load nutrition evidence for several recipes in one query."""
    ids = list(dict.fromkeys(str(value) for value in recipe_version_ids if value))
    if not ids:
        return {}
    query = """
        SELECT rv.recipe_version_id, rv.status AS recipe_status,
               rv.yield_quantity, rv.yield_unit,
               rc.ingredient_id, i.name AS ingredient_name,
               i.verification_status AS ingredient_status,
               i.calories_kcal_100g, i.protein_g_100g, i.carbs_g_100g,
               i.fat_g_100g, i.composition_basis,
               rc.quantity, rc.unit,
               rc.verification_status AS component_status
        FROM recipe_versions rv
        LEFT JOIN recipe_components rc ON rc.recipe_version_id = rv.recipe_version_id
        LEFT JOIN ingredients i ON i.ingredient_id = rc.ingredient_id
        WHERE rv.recipe_version_id = ANY(%s)
        ORDER BY rv.recipe_version_id, rc.sort_order, rc.recipe_component_id
    """
    try:
        rows = db.execute(query, (ids,))
    except Exception:
        # Older installations may not yet have the optional nutrition columns.
        rows = db.execute(
            """
            SELECT rv.recipe_version_id, rv.status AS recipe_status,
                   rv.yield_quantity, rv.yield_unit,
                   rc.ingredient_id, i.name AS ingredient_name,
                   i.verification_status AS ingredient_status,
                   rc.quantity, rc.unit,
                   rc.verification_status AS component_status
            FROM recipe_versions rv
            LEFT JOIN recipe_components rc ON rc.recipe_version_id = rv.recipe_version_id
            LEFT JOIN ingredients i ON i.ingredient_id = rc.ingredient_id
            WHERE rv.recipe_version_id = ANY(%s)
            ORDER BY rv.recipe_version_id, rc.sort_order, rc.recipe_component_id
            """,
            (ids,),
        )
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        version_id = str(row.get("recipe_version_id") or "")
        if not version_id:
            continue
        item = grouped.setdefault(version_id, {
            "recipe_status": str(row.get("recipe_status") or ""),
            "yield_quantity": row.get("yield_quantity"),
            "yield_unit": str(row.get("yield_unit") or ""),
            "components": [],
        })
        if row.get("ingredient_id"):
            item["components"].append(row)
    return grouped


def replace_components(
    recipe_version_id: str,
    components: list[dict[str, Any]],
    *,
    actor_id: str,
) -> list[dict[str, Any]]:
    version = get_version(recipe_version_id)
    if str(version.get("status")) == "VERIFIED":
        raise ConflictError("Recipe yang sudah VERIFIED tidak dapat ditimpa; buat version baru.")

    ingredient_ids = [str(c["ingredient_id"]) for c in components]
    existing = db.execute(
        "SELECT ingredient_id FROM ingredients WHERE ingredient_id = ANY(%s)",
        (ingredient_ids,),
    )
    existing_ids = {str(row["ingredient_id"]) for row in existing}
    missing = sorted(set(ingredient_ids) - existing_ids)
    if missing:
        raise ValidationError(
            "Ingredient tidak ditemukan.",
            details={"ingredient_ids": missing},
        )

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM recipe_components WHERE recipe_version_id = %s",
                (recipe_version_id,),
            )
            for component in components:
                cur.execute(
                    """
                    INSERT INTO recipe_components
                        (recipe_version_id, ingredient_id, quantity, unit,
                         preparation, verification_status, source, sort_order)
                    VALUES (%s, %s, %s, %s, %s, 'UNVERIFIED', 'admin_review', %s)
                    """,
                    (
                        recipe_version_id,
                        component["ingredient_id"],
                        component["quantity"],
                        component["unit"].strip(),
                        component.get("preparation", "").strip(),
                        component.get("sort_order", 0),
                    ),
                )
            cur.execute(
                """
                UPDATE recipe_versions
                SET status = 'PENDING_VERIFICATION',
                    verified_by = NULL,
                    verified_at = NULL,
                    updated_at = NOW()
                WHERE recipe_version_id = %s
                """,
                (recipe_version_id,),
            )
            cur.execute(
                """
                INSERT INTO recipe_verification_events
                    (recipe_version_id, action, verifier_id, notes)
                VALUES (%s, 'SUBMITTED', %s, %s)
                """,
                (recipe_version_id, actor_id, "Recipe components replaced for review."),
            )
    return list_components(recipe_version_id)


def verify_ingredient(
    ingredient_id: str,
    *,
    verifier_id: str,
    allergen_codes: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    row = db.execute_one(
        "SELECT ingredient_id FROM ingredients WHERE ingredient_id = %s",
        (ingredient_id,),
    )
    if not row:
        raise NotFoundError("Ingredient tidak ditemukan.")
    db.execute_write(
        """
        UPDATE ingredients
        SET verification_status = 'VERIFIED',
            allergen_codes = %s,
            allergen_evidence = %s,
            verified_by = %s,
            verified_at = NOW(),
            provenance_status = CASE
                WHEN provenance_status = 'UNKNOWN' THEN 'OPERATOR'
                ELSE provenance_status
            END,
            updated_at = NOW()
        WHERE ingredient_id = %s
        """,
        (allergen_codes, evidence, verifier_id, ingredient_id),
    )
    db.execute_write(
        """
        UPDATE recipe_components
        SET verification_status = 'VERIFIED'
        WHERE ingredient_id = %s
          AND quantity IS NOT NULL
          AND unit <> 'UNKNOWN'
        """,
        (ingredient_id,),
    )
    return db.execute_one(
        "SELECT ingredient_id, name, verification_status, allergen_codes, allergen_evidence, verified_by, verified_at FROM ingredients WHERE ingredient_id = %s",
        (ingredient_id,),
    ) or {}


def verify_ingredients_batch(
    ingredients: list[dict[str, Any]],
    *,
    verifier_id: str,
) -> list[dict[str, Any]]:
    """Mark reviewed ingredients in one explicit admin action.

    This is not triggered by AI generation or draft application. The action is
    still auditable and the recipe itself remains pending until verified.
    """
    ingredient_ids = [str(item["ingredient_id"]) for item in ingredients]
    existing = db.execute(
        "SELECT ingredient_id FROM ingredients WHERE ingredient_id = ANY(%s)",
        (ingredient_ids,),
    )
    existing_ids = {str(row["ingredient_id"]) for row in existing}
    missing = sorted(set(ingredient_ids) - existing_ids)
    if missing:
        raise ValidationError("Ingredient tidak ditemukan.", details={"ingredient_ids": missing})

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for item in ingredients:
                ingredient_id = str(item["ingredient_id"])
                allergen_codes = list(item.get("allergen_codes") or [])
                evidence = json.dumps({"source": "admin_batch_recipe_review"})
                cur.execute(
                    """
                    UPDATE ingredients
                    SET verification_status = 'VERIFIED',
                        allergen_codes = %s,
                        allergen_evidence = %s::jsonb,
                        verified_by = %s,
                        verified_at = NOW(),
                        provenance_status = CASE
                            WHEN provenance_status = 'UNKNOWN' THEN 'OPERATOR'
                            ELSE provenance_status
                        END,
                        updated_at = NOW()
                    WHERE ingredient_id = %s
                    """,
                    (allergen_codes, evidence, verifier_id, ingredient_id),
                )
                cur.execute(
                    """
                    UPDATE recipe_components
                    SET verification_status = 'VERIFIED'
                    WHERE ingredient_id = %s
                      AND quantity IS NOT NULL
                      AND unit <> 'UNKNOWN'
                    """,
                    (ingredient_id,),
                )
    return db.execute(
        """
        SELECT ingredient_id, name, verification_status, allergen_codes,
               allergen_evidence, verified_by, verified_at
        FROM ingredients
        WHERE ingredient_id = ANY(%s)
        ORDER BY name
        """,
        (ingredient_ids,),
    )


def _normalized_ingredient_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def apply_ai_draft(
    recipe_version_id: str,
    components: list[dict[str, Any]],
    *,
    evidence: dict[str, Any],
    actor_id: str,
) -> list[dict[str, Any]]:
    """Persist an admin-approved AI draft as unverified recipe components.

    Missing ingredients are added to the master list as UNVERIFIED. They are
    never silently marked safe merely because a model proposed them.
    """
    version = get_version(recipe_version_id)
    if str(version.get("status")) == "VERIFIED":
        raise ConflictError("Recipe yang sudah VERIFIED tidak dapat ditimpa; buat version baru.")

    source_urls = [str(item.get("url") or "") for item in evidence.get("sources", [])]
    source_ref = source_urls[0] if source_urls else "ai_recipe_draft"
    audit_evidence = json.dumps(evidence, ensure_ascii=False)

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            resolved: list[tuple[dict[str, Any], str]] = []
            for component in components:
                name = str(component["ingredient_name"]).strip()
                normalized_name = _normalized_ingredient_name(name)
                cur.execute(
                    "SELECT ingredient_id FROM ingredients WHERE normalized_name = %s",
                    (normalized_name,),
                )
                row = cur.fetchone()
                if row:
                    ingredient_id = str(row[0] if not isinstance(row, dict) else row["ingredient_id"])
                else:
                    metadata = json.dumps(
                        {
                            "created_from": "ai_recipe_draft",
                            "confidence": component.get("confidence", "LOW"),
                            "rationale": component.get("rationale", ""),
                        },
                        ensure_ascii=False,
                    )
                    cur.execute(
                        """
                        INSERT INTO ingredients
                            (name, normalized_name, default_unit, verification_status,
                             provenance_status, source_ref, metadata)
                        VALUES (%s, %s, %s, 'UNVERIFIED', 'UNKNOWN', %s, %s::jsonb)
                        RETURNING ingredient_id
                        """,
                        (name, normalized_name, str(component["unit"]).strip(), source_ref, metadata),
                    )
                    created = cur.fetchone()
                    ingredient_id = str(created[0] if not isinstance(created, dict) else created["ingredient_id"])
                resolved.append((component, ingredient_id))

            cur.execute("DELETE FROM recipe_components WHERE recipe_version_id = %s", (recipe_version_id,))
            for sort_order, (component, ingredient_id) in enumerate(resolved):
                component_metadata = json.dumps(
                    {
                        "quantity_min": component.get("quantity_min"),
                        "quantity_max": component.get("quantity_max"),
                        "confidence": component.get("confidence", "LOW"),
                        "rationale": component.get("rationale", ""),
                        "allergen_codes_proposed": component.get("allergen_codes", []),
                    },
                    ensure_ascii=False,
                )
                cur.execute(
                    """
                    INSERT INTO recipe_components
                        (recipe_version_id, ingredient_id, quantity, unit, preparation,
                         verification_status, source, sort_order, metadata)
                    VALUES (%s, %s, %s, %s, %s, 'UNVERIFIED', 'ai_draft_admin_review', %s, %s::jsonb)
                    """,
                    (
                        recipe_version_id,
                        ingredient_id,
                        component["quantity"],
                        str(component["unit"]).strip(),
                        str(component.get("preparation") or "").strip(),
                        sort_order,
                        component_metadata,
                    ),
                )

            cur.execute(
                """
                UPDATE recipe_versions
                SET status = 'PENDING_VERIFICATION',
                    source = 'ai_photo_web_draft',
                    source_ref = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    verified_by = NULL,
                    verified_at = NULL,
                    updated_at = NOW()
                WHERE recipe_version_id = %s
                """,
                (source_ref, audit_evidence, recipe_version_id),
            )
            cur.execute(
                """
                INSERT INTO recipe_verification_events
                    (recipe_version_id, action, verifier_id, evidence, notes)
                VALUES (%s, 'SUBMITTED', %s, %s::jsonb, %s)
                """,
                (
                    recipe_version_id,
                    actor_id,
                    audit_evidence,
                    "Admin applied an AI-assisted recipe draft; review is still required.",
                ),
            )
    return list_components(recipe_version_id)


def verify_recipe(
    recipe_version_id: str,
    *,
    verifier_id: str,
    cross_contact_risk: str,
    notes: str,
) -> dict[str, Any]:
    version = get_version(recipe_version_id)
    components = list_components(recipe_version_id)
    unresolved = [
        component for component in components
        if not component.get("ingredient_id")
        or component.get("quantity") is None
        or str(component.get("unit") or "").upper() == "UNKNOWN"
        or str(component.get("verification_status")) != "VERIFIED"
        or str(component.get("ingredient_status")) != "VERIFIED"
    ]
    if not components or unresolved:
        raise ValidationError(
            "Recipe belum dapat diverifikasi karena component/ingredient belum lengkap.",
            details={
                "recipe_version_id": recipe_version_id,
                "unresolved_components": unresolved,
            },
        )
    if cross_contact_risk not in {"LOW", "MEDIUM"}:
        raise ValidationError("cross_contact_risk harus LOW atau MEDIUM.")

    verified_at = datetime.now(timezone.utc)
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE recipe_versions
                SET status = 'VERIFIED',
                    cross_contact_risk = %s,
                    verified_by = %s,
                    verified_at = %s,
                    notes = %s,
                    updated_at = NOW()
                WHERE recipe_version_id = %s
                """,
                (cross_contact_risk, verifier_id, verified_at, notes, recipe_version_id),
            )
            cur.execute(
                """
                UPDATE recipe_components
                SET verification_status = 'VERIFIED'
                WHERE recipe_version_id = %s
                """,
                (recipe_version_id,),
            )
            cur.execute(
                """
                INSERT INTO recipe_verification_events
                    (recipe_version_id, action, verifier_id, notes)
                VALUES (%s, 'VERIFIED', %s, %s)
                """,
                (recipe_version_id, verifier_id, notes),
            )
    return get_version(recipe_version_id)
