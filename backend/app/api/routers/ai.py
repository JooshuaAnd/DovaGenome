"""Router AI — satu-satunya pintu keluar ke Langflow.

Credential Langflow hanya hidup di server (`app.core.config`). Frontend tidak
pernah melihat `LANGFLOW_API_KEY` maupun `LANGFLOW_API_URL`.
"""

from __future__ import annotations

import hmac
import re

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import get_current_customer, get_optional_customer
from app.core.config import settings
from app.core.domain import DAYS
from app.core.logging import get_logger
from app.models.enums import SafetyLevel
from app.repositories import catalog_repo, recipe_repo
from app.schemas.customer import CustomerOut, PassportIn
from app.schemas.internal import (
    AiConsultIn,
    AiConsultOut,
    AiMenuSuggestionIn,
    AiMenuSuggestionOut,
    FeedbackIn,
    FeedbackOut,
)
from app.services import feedback_service, langflow_context_service, passport_service, safety_service
from app.services.langflow_service import langflow_service as ai_client
from app.services.nutrition_service import calculate_recipe_nutrition
from app.utils.time import now_iso

log = get_logger("dova.api.ai")

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/internal/context", summary="Live operational context untuk Langflow")
def live_context(
    x_dova_internal_token: str = Header(default="", alias="X-Dova-Internal-Token"),
) -> dict:
    """Read-only live context; only the configured Langflow connector may call it."""
    expected = settings.langflow_internal_token.strip()
    if not expected or not hmac.compare_digest(x_dova_internal_token, expected):
        raise HTTPException(status_code=401, detail="Internal Langflow token tidak valid.")
    try:
        return langflow_context_service.build_live_context()
    except Exception as exc:
        log.warning("langflow_live_context_unavailable reason=%s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Live operational context belum tersedia.",
        ) from exc


@router.post("/consult", response_model=AiConsultOut, summary="Tanya asisten AI")
def consult(
    payload: AiConsultIn, customer: CustomerOut | None = Depends(get_optional_customer)
) -> AiConsultOut:
    """
    Tanya asisten katering.

    Bila Langflow tidak bisa dihubungi, mode default mengembalikan status
    degraded yang eksplisit. RAG hanya dipakai bila `AI_MODE=allow_explicit_fallback`.
    """
    session_id = payload.session_id or (customer.customer_id if customer else "guest")
    passport = passport_service.passport_for(customer)
    # Allergy and explicit dislike requests use deterministic catalog logic first.
    # Do not let a successful but ungrounded model answer override these checks.
    if _has_allergy_intent(payload.message):
        structured = _structured_allergy_reply(payload.message, session_id, passport, customer)
        if structured is not None:
            return structured
    if _has_preference_intent(payload.message):
        history = payload.context.get("conversation_history", [])
        if not isinstance(history, list):
            history = []
        history = [str(item)[:2000] for item in history[-10:] if isinstance(item, str)]
        structured = _structured_preference_reply(
            payload.message, session_id, passport, customer, history
        )
        if structured is not None:
            return structured

    safe_context = {key: value for key, value in payload.context.items() if key != "conversation_history"}
    answer = ai_client.ask(
        message=payload.message,
        session_id=session_id,
        system_context=_customer_context(customer, safe_context, passport),
    )
    return answer


def _customer_context(customer: CustomerOut | None, extra: dict, passport=None) -> str:
    """Konteks ringkas untuk prompt — bukan data sensitif."""
    lines = []
    if customer:
        lines.extend([
            f"Pelanggan: {customer.display_name or customer.username}",
            f"Peran: {customer.role}",
            f"Telegram tertaut: {'ya' if customer.telegram_verified else 'belum'}",
        ])
    if passport:
        restrictions = [
            r.label or r.code
            for group in (passport.allergies, passport.intolerances, passport.medical)
            for r in group
        ]
        lines.append("Pantangan tersimpan: " + (", ".join(restrictions) or "tidak ada"))
    for key, value in extra.items():
        lines.append(f"{key}: {value}")
    return " | ".join(lines)


def _has_allergy_intent(message: str) -> bool:
    return any(word in message.casefold() for word in ("alergi", "alergen", "pantangan", "intoleran"))


def _has_preference_intent(message: str) -> bool:
    text = message.casefold()
    return any(term in text for term in (
        "tidak suka", "nggak suka", "enggak suka", "gak suka", "gasuka", "ga suka",
        "kurang suka", "tidak doyan", "nggak doyan", "enggak doyan", "gak doyan",
        "hindari", "jangan", "diet", "turun berat", "defisit kalori", "lebih ringan",
        "jaga kalori", "mau kurus", "mengurangi lemak", "kurangi lemak", "turun lemak",
        "lemak tubuh", "body fat", "fat loss", "rendah lemak", "ga berlemak", "gak berlemak",
        "nggak berlemak", "tidak berlemak", "minim lemak", "sedikit lemak", "low fat",
        "protein tinggi", "tinggi protein", "banyak protein", "high protein",
        "berlemak tinggi", "tinggi lemak", "lemak tinggi", "high fat",
    ))


def _structured_preference_reply(
    message: str,
    session_id: str,
    passport=None,
    customer: CustomerOut | None = None,
    history: list[str] | None = None,
) -> AiConsultOut | None:
    """Give a deterministic dislike-filtered suggestion from the current menu catalog."""
    text = "; ".join([*(history or []), message]).casefold()
    current_text = message.casefold()
    aliases = {
        "ayam": ("ayam",), "pedas": ("pedas", "sambal", "cabai", "cabe", "rawit"),
        "ikan": ("ikan", "fish"),
        "sapi": ("sapi", "beef", "daging sapi"), "udang": ("udang", "shrimp"),
        "seafood": ("seafood", "hasil laut", "ikan", "fish", "udang", "shrimp", "kerang", "cumi", "sotong", "kepiting", "crab", "lobster", "kakap", "salmon", "tuna", "dori", "patin", "tongkol", "lele", "bandeng", "sarden", "makarel"),
        "kakap": ("kakap",), "salmon": ("salmon",), "tuna": ("tuna",),
        "dori": ("dori",), "patin": ("patin",), "tongkol": ("tongkol",),
        "lele": ("lele",), "bandeng": ("bandeng",), "sarden": ("sarden",),
        "makarel": ("makarel", "mackerel"), "kerang": ("kerang",),
        "cumi": ("cumi",), "sotong": ("sotong",), "kepiting": ("kepiting", "crab"),
        "lobster": ("lobster",),
        "sayur": (
            "sayur", "vegetarian", "tahu", "tempe", "gado-gado", "urap", "salad",
            "brokoli", "wortel", "buncis", "selada", "kangkung", "bayam", "sawi",
            "tauge", "toge", "jagung", "kol", "kubis", "kembang kol", "terong",
            "terung", "paprika", "labu", "timun", "mentimun", "asparagus",
            "kacang panjang", "rebung", "vegetable",
        ),
    }
    negative_markers = (
            "tidak suka", "nggak suka", "enggak suka", "gak suka", "gasuka", "ga suka",
            "kurang suka", "tidak doyan", "nggak doyan", "enggak doyan", "gak doyan",
            "hindari", "jangan",
    )
    explicit_dislikes: set[str] = set()
    for contrast_side in re.split(r"\btapi\b|\bsedangkan\b|\bnamun\b|\btetapi\b", text):
        clauses = re.split(r"[,;]", contrast_side)
        previous_was_dislike = False
        for clause in clauses:
            clause = clause.strip()
            has_negative = any(marker in clause for marker in negative_markers)
            has_positive = any(marker in clause for marker in ("suka", "doyan", "gemar")) and not has_negative
            continuation = previous_was_dislike and bool(re.match(r"^(yang|terlalu|agak|dan\s+(?!suka|doyan))", clause))
            if (has_negative or continuation) and not has_positive:
                explicit_dislikes.update(
                    key for key, terms in aliases.items()
                    if (key != "seafood" or "seafood" in clause or "hasil laut" in clause)
                    if any(term in clause for term in terms)
                )
            previous_was_dislike = has_negative or (continuation and not has_positive)
    seafood_item_keys = (
        "udang", "kakap", "salmon", "tuna", "dori", "patin", "tongkol", "lele",
        "bandeng", "sarden", "makarel", "kerang", "cumi", "sotong", "kepiting", "lobster",
    )
    specific_seafood_item = next((
        key for key in seafood_item_keys
        if any(re.search(rf"\b{re.escape(term)}\b", current_text) for term in aliases[key])
    ), "")
    specific_seafood_only = (
        "seafood" in current_text
        and bool(specific_seafood_item)
        and any(term in current_text for term in ("spesifik", "khusus", "aja", "saja"))
        and any(term in current_text for term in ("hindari", "menghindari", "tidak suka", "gak suka", "ga suka", "gasuka"))
    )
    seafood_preference_keys = {"seafood", "ikan", *seafood_item_keys}
    seafood_preference_terms = {
        term for key in seafood_preference_keys for term in aliases.get(key, (key,))
    }
    if specific_seafood_only:
        explicit_dislikes.difference_update(seafood_preference_keys)
        explicit_dislikes.add(specific_seafood_item)
    disliked = set(explicit_dislikes)
    if passport:
        stored = " ".join(passport.avoided_ingredients).casefold()
        disliked.update(
            key for key, terms in aliases.items()
            if (key != "seafood" or "seafood" in stored or "hasil laut" in stored)
            if any(term in stored for term in terms)
        )
    if specific_seafood_only:
        disliked.difference_update(seafood_preference_keys)
        disliked.add(specific_seafood_item)
    low_fat_terms = (
        "rendah lemak", "ga berlemak", "gak berlemak", "nggak berlemak", "tidak berlemak",
        "minim lemak", "sedikit lemak", "low fat", "kurang lemak",
    )
    fat_loss_terms = (
        "mengurangi lemak", "kurangi lemak", "turun lemak", "lemak tubuh", "body fat", "fat loss",
    )
    high_protein_terms = ("protein tinggi", "tinggi protein", "banyak protein", "high protein")
    high_fat_terms = ("berlemak tinggi", "tinggi lemak", "lemak tinggi", "high fat")
    lighter_terms = ("diet", "turun berat", "defisit kalori", "lebih ringan", "jaga kalori", "mau kurus")
    requested_goal = (
        "high_fat_high_protein" if any(term in current_text for term in high_fat_terms) and any(term in current_text for term in high_protein_terms)
        else "high_protein" if any(term in current_text for term in high_protein_terms)
        else "high_fat" if any(term in current_text for term in high_fat_terms)
        else "low_fat" if any(term in current_text for term in low_fat_terms)
        else "fat_loss" if any(term in current_text for term in fat_loss_terms)
        else "lighter" if any(term in current_text for term in lighter_terms)
        else ""
    )
    saved_goal = passport.nutrition_goal if passport else ""
    macro_goals = {"high_fat_high_protein", "high_protein", "high_fat"}
    macro_goal = requested_goal in macro_goals
    active_macro_goal = requested_goal
    diet_focus = requested_goal in {"lighter", "fat_loss", "low_fat"}
    if not disliked and not requested_goal:
        return None
    preferences_saved = bool(customer and passport and (disliked or saved_goal))
    if customer and (explicit_dislikes or requested_goal):
        previous = passport.avoided_ingredients if passport else []
        if specific_seafood_only:
            previous = [
                item for item in previous
                if not any(term in item.casefold().strip() for term in seafood_preference_terms)
            ]
        merged = list(dict.fromkeys([*previous, *sorted(explicit_dislikes)]))
        try:
            fields = {}
            if explicit_dislikes:
                fields["avoided_ingredients"] = merged
            if requested_goal:
                fields["nutrition_goal"] = requested_goal
            passport = passport_service.save_passport(
                customer.customer_id, PassportIn(**fields)
            )
            preferences_saved = True
        except Exception as exc:
            log.warning("chat_preference_save_failed reason=%s", type(exc).__name__)
    try:
        catalog = safety_service.CatalogContext()
        available = []
        for day in DAYS:
            for menu in catalog.menus.get(day, []):
                if (
                    menu.recipe_verification_status != "VERIFIED"
                    or menu.recipe_has_unresolved_components
                    or not menu.recipe_version_id
                ):
                    continue
                recipe_ingredients = [
                    item.nama for item in menu.bahan_detail
                    if item.sumber == "recipe_component"
                    and item.ingredient_id
                    and item.verification_status == "VERIFIED"
                ]
                if not recipe_ingredients:
                    continue
                safety = safety_service.check_menu(
                    day, menu, set(passport.critical_codes if passport else []), catalog=catalog
                )
                if safety.level != SafetyLevel.SAFE:
                    continue
                searchable = " ".join(recipe_ingredients).casefold()
                if any(term in searchable for key in disliked for term in aliases[key]):
                    continue
                available.append(f"{menu.nama_menu} ({day})")
        macro_recommendations = (
            _verified_macro_suggestions(catalog, disliked, passport, aliases, active_macro_goal)
            if macro_goal else []
        )
        if macro_goal:
            intro = "Siap, aku paham kamu mencari makanan tinggi "
            intro += (
                "lemak dan protein. " if active_macro_goal == "high_fat_high_protein"
                else "protein. " if active_macro_goal == "high_protein"
                else "lemak. "
            )
            if macro_recommendations:
                menu_text = "Dari menu dengan makro per porsi yang terverifikasi: " + "; ".join(macro_recommendations) + "."
            else:
                menu_text = "Belum ada menu yang lolos verifikasi makro dan porsi untuk target ini; aku tidak akan menebak kandungan gizinya."
        elif disliked:
            intro = (
                f"Siap, aku catat kamu menghindari {specific_seafood_item} saja; seafood lainnya tetap boleh. "
                if specific_seafood_only else
                "Siap, aku paham kamu menghindari " + " dan ".join(sorted(disliked)) + ". "
            )
            menu_text = (
                "Dari resep terverifikasi minggu ini, yang cocok dengan selera dan pantanganmu: " + ", ".join(available[:6]) + "."
                if available else "Belum ada resep terverifikasi yang bisa dipastikan cocok dengan selera dan pantanganmu minggu ini."
            )
        elif requested_goal == "fat_loss":
            intro = "Siap, aku paham targetmu mengurangi lemak tubuh. "
            menu_text = "Aku belum bisa memilih menu khusus untuk target itu dari data nutrisi yang tersedia."
        elif requested_goal == "low_fat":
            intro = "Siap, aku paham kamu mencari makanan rendah lemak. "
            menu_text = "Aku belum bisa memilih menu rendah lemak karena katalog belum memiliki data kandungan lemak terverifikasi."
        else:
            intro = "Siap, aku paham kamu ingin fokus makan lebih ringan. "
            menu_text = "Aku belum bisa memilih menu khusus diet dari katalog saat ini."
        if macro_goal:
            diet_note = ""
        elif requested_goal == "low_fat":
            diet_note = (
                " Katalog belum menyediakan data lemak menu yang terverifikasi, jadi "
                + ("daftar ini hanya difilter dari selera tersimpan, bukan dinilai rendah lemak." if disliked
                   else "aku belum bisa menilai menu mana yang rendah lemak.")
            )
        elif requested_goal == "fat_loss":
            diet_note = (
                " Targetmu untuk mengurangi lemak tubuh sudah kusimpan. Data energi dan lemak menu belum terverifikasi, "
                "jadi daftar ini hanya disaring menurut selera, belum dinilai untuk target tersebut."
            )
        elif diet_focus:
            diet_note = (
                " Fokus makan lebih ringan sudah kusimpan. Data kalori menu belum terverifikasi, "
                "jadi daftar ini belum bisa dinilai untuk defisit kalori."
            )
        else:
            diet_note = ""
        if preferences_saved:
            saved_note = (
                " Preferensi selera dan target nutrisimu sudah kusimpan di Passport akunmu."
                if requested_goal else " Preferensi seleramu sudah kusimpan di Passport akunmu."
            )
        else:
            saved_note = " Preferensi ini belum tersimpan; simpan di Profil agar tetap dipakai pada kunjungan berikutnya."
        reply = intro + menu_text + diet_note + saved_note
        return AiConsultOut(reply=reply, session_id=session_id, model="catalog_preferences", provider="catalog_preferences",
                            degraded=True, readiness_state="DEGRADED",
                            reason_code="structured_preference_saved" if preferences_saved else "structured_preference_filter",
                            message="Preferensi dijawab langsung dari filter katalog menu aktif.")
    except Exception as exc:
        log.warning("structured_preference_filter_unavailable reason=%s", type(exc).__name__)
        return AiConsultOut(
            reply=("Aku menangkap preferensi makanmu, tetapi katalog menu live sedang tidak bisa diakses. "
                   "Aku belum bisa memilih hidangan yang cocok. Preferensi ini belum tersimpan; kamu bisa menyimpannya di Profil."),
            session_id=session_id, model="catalog_preferences", provider="catalog_preferences",
            degraded=True, readiness_state="DEGRADED", reason_code="live_catalog_unavailable",
            message="Katalog live tidak tersedia; tidak ada rekomendasi yang dibuat.",
        )


def _verified_macro_suggestions(
    catalog: safety_service.CatalogContext,
    disliked: set[str],
    passport,
    aliases: dict[str, tuple[str, ...]],
    goal: str,
) -> list[str]:
    """Return only safe recipes with verified ingredients and per-portion macros."""
    candidates: list[tuple[str, object]] = []
    for day in DAYS:
        for menu in catalog.menus.get(day, []):
            searchable = " ".join(
                [menu.nama_menu, menu.deskripsi]
                + [item.nama for item in menu.bahan_detail]
            ).casefold()
            if any(term in searchable for key in disliked for term in aliases[key]):
                continue
            if not menu.recipe_version_id or menu.recipe_verification_status != "VERIFIED":
                continue
            if menu.recipe_has_unresolved_components or menu.recipe_cross_contact_risk == "UNKNOWN":
                continue
            safety = safety_service.check_menu(
                day, menu, set(passport.critical_codes if passport else []), catalog=catalog
            )
            if safety.level != SafetyLevel.SAFE:
                continue
            candidates.append((day, menu))

    evidence = recipe_repo.list_nutrition_components(
        [menu.recipe_version_id for _, menu in candidates]
    )
    ranked: list[tuple[float, str, str, float, float]] = []
    for day, menu in candidates:
        recipe = evidence.get(menu.recipe_version_id)
        if not recipe or recipe["recipe_status"] != "VERIFIED":
            continue
        yield_quantity = recipe.get("yield_quantity")
        try:
            portions = float(yield_quantity)
        except (TypeError, ValueError):
            continue
        if portions <= 0 or str(recipe.get("yield_unit") or "").strip().casefold() not in {
            "portion", "portions", "porsi"
        }:
            continue
        components = recipe.get("components", [])
        if not components or any(
            not row.get("ingredient_id")
            or row.get("ingredient_status") != "VERIFIED"
            or row.get("component_status") != "VERIFIED"
            for row in components
        ):
            continue
        nutrition = calculate_recipe_nutrition(components)
        if nutrition.get("status") != "VERIFIED":
            continue
        fat = float(nutrition["fat_g"]) / portions
        protein = float(nutrition["protein_g"]) / portions
        ranked.append((0.0, day, menu.nama_menu, fat, protein))

    max_fat = max((item[3] for item in ranked), default=0.0)
    max_protein = max((item[4] for item in ranked), default=0.0)
    if goal == "high_fat":
        ranked.sort(key=lambda item: item[3], reverse=True)
    elif goal == "high_protein":
        ranked.sort(key=lambda item: item[4], reverse=True)
    else:
        ranked.sort(
            key=lambda item: min(
                item[3] / max_fat if max_fat else 0.0,
                item[4] / max_protein if max_protein else 0.0,
            ),
            reverse=True,
        )
    suggestions = []
    for _, day, name, fat, protein in ranked[:3]:
        if goal == "high_fat":
            macros = f"{fat:.1f} g lemak/porsi"
        elif goal == "high_protein":
            macros = f"{protein:.1f} g protein/porsi"
        else:
            macros = f"{fat:.1f} g lemak dan {protein:.1f} g protein/porsi"
        suggestions.append(f"{name} ({day}, {macros})")
    return suggestions


def _structured_allergy_reply(
    message: str,
    session_id: str,
    passport=None,
    customer: CustomerOut | None = None,
) -> AiConsultOut | None:
    """Answer an allergy question from the live catalog without model inference."""
    text = message.casefold()
    try:
        allergens = catalog_repo.list_allergens(include_inactive=True)
        passport_codes = {
            restriction.code
            for group in (passport.allergies, passport.intolerances, passport.medical)
            for restriction in group
        } if passport else set()
        text_matches = [
            allergen for allergen in allergens
            if any(term in text for term in (allergen.code.casefold(), allergen.label.casefold(), allergen.risiko.casefold()))
        ]
        matches = [a for a in allergens if a.code in passport_codes]
        matches.extend(a for a in text_matches if a.code not in {m.code for m in matches})
        if not text_matches:
            # Common customer wording is not always identical to the catalog label.
            aliases = {
                "ikan": ("ikan", "fish"),
                "fish": ("ikan", "fish"),
                "salmon": ("ikan", "fish"),
                "tuna": ("ikan", "fish"),
                "dori": ("ikan", "fish"),
                "kakap": ("ikan", "fish"),
                "patin": ("ikan", "fish"),
                "tongkol": ("ikan", "fish"),
                "udang": ("udang", "shrimp"),
                "kerang": ("kerang", "shellfish", "seafood"),
                "susu": ("susu", "dairy", "laktosa"),
                "telur": ("telur", "egg"),
                "kacang": ("kacang", "peanut", "nut"),
                "gandum": ("gandum", "gluten", "terigu"),
                "kedelai": ("kedelai", "soy", "tofu", "tempe"),
            }
            for phrase, terms in aliases.items():
                if phrase in text:
                    alias_matches = [a for a in allergens if any(
                        term in f"{a.code} {a.label} {a.risiko}".casefold() for term in terms
                    )]
                    matches.extend(a for a in alias_matches if a.code not in {m.code for m in matches})
                    text_matches.extend(a for a in alias_matches if a.code not in {m.code for m in text_matches})
                    if alias_matches:
                        break
        if not matches:
            return AiConsultOut(
                reply="Aku belum menemukan kategori alergen yang cocok di katalog. Simpan pantanganmu di Passport agar ikut diperiksa pada menu; untuk alergi berat, konfirmasi juga langsung ke tim dapur.",
                session_id=session_id, model="catalog_safety", provider="catalog_safety",
                degraded=True, readiness_state="DEGRADED", reason_code="allergen_not_in_catalog",
                message="AI sedang tidak tersedia; jawaban memakai pemeriksaan katalog terstruktur.",
            )

        codes = {a.code for a in matches}
        labels = ", ".join(dict.fromkeys(a.label for a in matches))
        saved_to_passport = False
        if customer and text_matches:
            try:
                existing = list(passport.allergies if passport else [])
                by_code = {item.code: item for item in existing}
                for allergen in text_matches:
                    by_code.setdefault(allergen.code, allergen)
                passport = passport_service.save_passport(
                    customer.customer_id,
                    PassportIn(allergies=[
                        {
                            "code": item.code,
                            "label": item.label,
                            "severity": getattr(item, "severity", ""),
                            "notes": getattr(item, "notes", ""),
                        }
                        for item in by_code.values()
                    ]),
                )
                saved_to_passport = True
            except Exception as exc:
                log.warning("chat_allergy_save_failed reason=%s", type(exc).__name__)
        catalog = safety_service.CatalogContext()
        blocked: list[str] = []
        unverified: list[str] = []
        menu_count = 0
        fish_terms = (
            "ikan", "fish", "dori", "salmon", "tuna", "kakap", "patin",
            "tongkol", "lele", "sarden", "bandeng", "makarel", "mackerel",
        )
        for day in DAYS:
            options = catalog.menus.get(day, [])
            menu_count += len(options)
            results = safety_service.check_options(options, day, codes, ctx=catalog)
            for menu, result in zip(options, results):
                ingredient_text = " ".join(
                    [menu.nama_menu, menu.deskripsi]
                    + [ingredient.nama for ingredient in menu.bahan_detail]
                ).casefold()
                reported_words = set(re.findall(r"[a-z]+", text))
                explicit_fish = bool(reported_words.intersection(fish_terms))
                ingredient_words = set(re.findall(r"[a-z]+", ingredient_text))
                contains_reported_item = explicit_fish and bool(ingredient_words.intersection(fish_terms))
                if result.level == SafetyLevel.BLOCKED or contains_reported_item:
                    blocked.append(f"{menu.nama_menu} ({day})")
                elif result.level == SafetyLevel.REQUIRES_VERIFICATION:
                    unverified.append(f"{menu.nama_menu} ({day})")

        details = []
        if blocked:
            details.append("Terindikasi mengandung alergen terkait: " + ", ".join(blocked[:8]) + ("…" if len(blocked) > 8 else "."))
        if unverified:
            details.append("Belum bisa dinyatakan aman karena resep belum lolos verifikasi: " + ", ".join(unverified[:6]) + ("…" if len(unverified) > 6 else "."))
        if menu_count == 0:
            details.append("Katalog menu sedang tidak memuat hidangan untuk diperiksa.")
        elif not blocked and not unverified:
            details.append("Tidak ada konflik yang tercatat pada menu terverifikasi di katalog saat ini.")
        reply = (
            f"Aku mencocokkan pantangan {labels} dengan data katalog. "
            + " ".join(details)
            + " Ini pemeriksaan bahan yang tercatat, bukan jaminan bebas kontaminasi silang. "
            + (
                "Alergimu sudah kusimpan di Passport dan beranda akan mengikuti pantangan ini. "
                if saved_to_passport else
                "Untuk menyimpan alergi ini di Passport, masuk ke akun terlebih dahulu. "
                if customer is None else
                "Alergi ini belum berhasil tersimpan di Passport; coba simpan lewat Profil. "
            )
            + "Untuk alergi berat, konfirmasi juga langsung ke tim dapur."
        )
        return AiConsultOut(
            reply=reply, session_id=session_id, model="catalog_safety", provider="catalog_safety",
            degraded=True, readiness_state="DEGRADED",
            reason_code="structured_allergen_saved" if saved_to_passport else "structured_allergen_check",
            message="Pemeriksaan alergi dihitung dari data katalog dan status verifikasi resep.",
        )
    except Exception as exc:  # fail closed when the safety catalog cannot be checked
        log.warning("structured_allergy_check_unavailable reason=%s", type(exc).__name__)
        return AiConsultOut(
            reply=("Aku belum bisa memeriksa alergi itu karena katalog bahan sedang tidak tersedia. "
                   "Jadi aku tidak bisa menyatakan menu aman; hubungi tim dapur sebelum memesan."),
            session_id=session_id, model="catalog_safety", provider="catalog_safety",
            degraded=True, readiness_state="DEGRADED", reason_code="safety_catalog_unavailable",
            message="Pemeriksaan bahan gagal; tidak ada kesimpulan keamanan yang dibuat.",
        )


@router.post(
    "/menu-suggestion",
    response_model=AiMenuSuggestionOut,
    summary="Saran menu aman untuk hari tertentu",
)
def menu_suggestion(
    payload: AiMenuSuggestionIn,
    customer: CustomerOut = Depends(get_current_customer),
) -> AiMenuSuggestionOut:
    """
    Gabung laporan safety deterministik dengan saran bahasa alami dari Langflow.

    Laporan safety tetap dihitung lokal — keputusan "aman / tidak aman" tidak
    pernah diserahkan ke model bahasa.
    """
    days = [d for d in payload.service_days if d in DAYS] or list(DAYS)
    report = safety_service.build_report(
        selected_codes=payload.selected_allergen_codes,
        passport=None,
        schedule_days=days,
    )

    answer = ai_client.ask(
        message=(
            "Pelanggan meminta saran menu untuk hari: "
            + ", ".join(days)
            + ". Batasan yang dipilih: "
            + (", ".join(report.passport_excludes) or "tidak ada")
            + ". Jawab singkat dan ramah dalam Bahasa Indonesia."
        ),
        session_id=f"menu:{customer.customer_id}",
        system_context=f"Tingkat kecocokan menu: {report.level}",
    )

    return AiMenuSuggestionOut(
        reply=answer.reply,
        safety=report,
        suggested_days=[d.hari for d in report.per_day if d.is_recommended],
        avoided_days=[d.hari for d in report.per_day if not d.is_recommended],
        session_id=answer.session_id,
        degraded=answer.degraded,
    )


@router.post("/feedback", response_model=FeedbackOut, status_code=201, summary="Kirim umpan balik")
def feedback(
    payload: FeedbackIn, customer: CustomerOut = Depends(get_current_customer)
) -> FeedbackOut:
    return feedback_service.save(payload, customer=customer)


@router.get("/config", summary="Status konfigurasi AI")
def ai_config(customer: CustomerOut = Depends(get_current_customer)) -> dict:
    """Apa yang tersimpan tentang integrasi AI (tanpa secret)."""
    return {
        "provider": "langflow",
        "configured": ai_client.configured,
        "ai_mode": settings.ai_mode,
        "flow_id_set": bool(settings.langflow_flow_id),
        "telegram_bot_username": settings.telegram_bot_username,
        "checked_at": now_iso(),
    }
