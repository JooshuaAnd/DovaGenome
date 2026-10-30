"""Katalog terstruktur: paket, alergen, menu mingguan — Postgres.

Interface method identik dengan versi Astra sehingga service dan router
tidak berubah sama sekali.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.core.domain import (
    DAYS,
    TABLE_ALLERGENS,
    TABLE_MENU_INGREDIENTS,
    TABLE_MENUS,
    TABLE_PACKAGES,
    normalize_allergen_code,
    split_codes,
)
from app.core.errors import DatabaseError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.repositories import supabase as db
from app.repositories.cache import TTLCache
from app.schemas.catalog import AllergenOut, MenuOut, PackageOut

log = get_logger("dova.repo.catalog")

_cache: TTLCache[Any] = TTLCache(settings.catalog_cache_ttl_seconds)


def _cached(key: str, loader: Any) -> Any:
    value = _cache.get(key)
    if value is None:
        value = loader()
        _cache.set(key, value)
    return value


# ── Allergen ────────────────────────────────────────────────────────────────
def _row_to_allergen(row: dict[str, Any]) -> AllergenOut:
    return AllergenOut(
        code=normalize_allergen_code(row["code"]),
        label=str(row.get("label") or "—"),
        risiko=str(row.get("risiko") or ""),
        active=bool(row.get("active", True)),
        category=str(row.get("category") or "allergy"),
    )


FALLBACK_ALLERGENS_DATA: list[dict[str, Any]] = [
    {"code": "alg_gluten", "label": "Bebas Gluten", "risiko": "Gandum, Kecap Kedelai Biasa, Tepung Terigu", "active": True, "category": "allergy"},
    {"code": "alg_seafood", "label": "Bebas Seafood", "risiko": "Udang, Kepiting, Kerang, Terasi, Minyak Ikan", "active": True, "category": "allergy"},
    {"code": "alg_kacang", "label": "Bebas Kacang Tanah", "risiko": "Kacang Tanah, Selai Kacang, Minyak Kacang", "active": True, "category": "allergy"},
    {"code": "alg_dairy", "label": "Bebas Susu/Laktosa", "risiko": "Butter, Keju, Krim Susu Sapi", "active": True, "category": "intolerance"},
    {"code": "alg_telur", "label": "Bebas Telur", "risiko": "Putih/Kuning Telur, Mayones, Emulsifier", "active": True, "category": "allergy"},
    {"code": "alg_kedelai", "label": "Bebas Kedelai/Terasi", "risiko": "Tahu, Tempe, Kecap Asin, Terasi Udang", "active": True, "category": "allergy"},
]

FALLBACK_PACKAGES_DATA: list[dict[str, Any]] = [
    {"code": "pkg_full", "name": "Full Week (Senin – Sabtu)", "days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"], "description": "Catering lengkap 6 hari: Senin sampai Sabtu.", "price": 495000, "active": True},
    {"code": "pkg_workday", "name": "Hari Kerja (Senin – Jumat)", "days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"], "description": "Lima hari kerja, pas untuk metabolisme kantor yang padat.", "price": 420000, "active": True},
    {"code": "pkg_3hari", "name": "3 Hari Pilihan (Sen, Rab, Jum)", "days": ["Senin", "Rabu", "Jumat"], "description": "Rotasi ringan tiga kali seminggu.", "price": 285000, "active": True},
]


def list_allergens(*, include_inactive: bool = False, use_cache: bool = True) -> list[AllergenOut]:
    if use_cache:
        return list(
            _cached(
                f"allergens:{include_inactive}",
                lambda: list_allergens(include_inactive=include_inactive, use_cache=False),
            )
        )
    try:
        sql = f"SELECT * FROM {TABLE_ALLERGENS} ORDER BY code"  # noqa: S608
        rows = db.execute(sql)
        if not rows:
            rows = FALLBACK_ALLERGENS_DATA
    except Exception as exc:
        log.warning("Baca %s gagal (%s) — menggunakan fallback definisi alergen.", TABLE_ALLERGENS, exc)
        rows = FALLBACK_ALLERGENS_DATA

    out = [_row_to_allergen(r) for r in rows]
    if not include_inactive:
        out = [a for a in out if a.active]
    return sorted(out, key=lambda a: a.code)


# ── Packages ────────────────────────────────────────────────────────────────
def _row_to_package(row: dict[str, Any]) -> PackageOut:
    days_raw = row.get("days") or []
    # Postgres TEXT[] datang sebagai list Python dari psycopg2
    if isinstance(days_raw, str):
        days_raw = split_codes(days_raw)
    days = [d for d in DAYS if d in set(days_raw)]
    price = row.get("price")
    try:
        price_int = int(price) if price is not None else None
    except (TypeError, ValueError):
        log.warning("Harga paket %s bukan angka, diabaikan: %r", row.get("code"), price)
        price_int = None
    return PackageOut(
        code=str(row.get("code") or ""),
        name=str(row.get("name") or "—"),
        days=days,
        description=str(row.get("description") or ""),
        meal_count=len(days),
        price=price_int,
        active=bool(row.get("active", True)),
    )


def list_packages(*, include_inactive: bool = False, use_cache: bool = True) -> list[PackageOut]:
    if use_cache:
        return list(
            _cached(
                f"packages:{include_inactive}",
                lambda: list_packages(include_inactive=include_inactive, use_cache=False),
            )
        )
    try:
        rows = db.execute(f"SELECT * FROM {TABLE_PACKAGES} ORDER BY code")  # noqa: S608
        if not rows:
            rows = FALLBACK_PACKAGES_DATA
    except Exception as exc:
        log.warning("Baca %s gagal (%s) — menggunakan fallback paket.", TABLE_PACKAGES, exc)
        rows = FALLBACK_PACKAGES_DATA

    out = [_row_to_package(r) for r in rows]
    if not include_inactive:
        out = [p for p in out if p.active]
    return sorted(out, key=lambda p: p.code)


def get_package(code: str) -> PackageOut:
    code = normalize_allergen_code(code) if code.startswith("alg_") else code
    for pkg in list_packages(include_inactive=True):
        if pkg.code == code:
            return pkg
    raise NotFoundError(f"Paket '{code}' tidak ditemukan.")


# ── Menu mingguan ───────────────────────────────────────────────────────────
def _critical_ingredient(bahan: dict[str, Any]) -> bool:
    return "⚠" in str(bahan.get("potensi_alergen") or "")


_NEGATION_PATTERNS = (
    r"\btanpa\b[\w\s/-]{0,30}",
    r"\bbebas\b[\w\s/-]{0,20}",
    r"\bnon-?gluten\b",
    r"\b0\s*(susu|gluten|seafood)",
    r"\bwithout\b[\w\s/-]{0,20}",
    r"\bfree\s+(from|of)\b[\w\s/-]{0,20}",
)


def _strip_negations(text: str) -> str:
    out = text.lower()
    for pattern in _NEGATION_PATTERNS:
        out = re.sub(pattern, " ", out)
    return out


def _detect_codes(texts: list[str]) -> list[str]:
    if not texts:
        return []
    blob = _strip_negations(" ".join(texts))
    codes: list[str] = []
    for allergen in list_allergens(include_inactive=True):
        theme = _theme_keywords(allergen.code)
        tokens = set(theme) if theme else set()
        label = allergen.label.lower().replace("bebas ", "").strip()
        if label:
            tokens.add(label)
        plain = allergen.code.replace("alg_", "").replace("_", " ")
        if plain:
            tokens.add(plain)
        if any(t and t in blob for t in tokens) and allergen.code not in codes:
            codes.append(allergen.code)
    return codes


def _theme_keywords(code: str) -> list[str]:
    return {
        "gluten": ["gluten", "gandum", "terigu", "mie", "roti", "biskuit"],
        "seafood": ["seafood", "ikan", "udang", "kepiting", "kerang", "cumi",
                    "terasi", "salmon", "kakap", "tongkol", "ikan bilis"],
        "kacang": ["kacang tanah", "groundnut", "peanut"],
        "dairy": ["susu", "laktosa", "keju", "butter", "krim", "cream", "yoghurt",
                  "yogurt", "feta", "dairy", "ghee"],
        "telur": ["telur", "mayones", "mayonnaise"],
        "kedelai": ["kedelai", "tahu", "tempe", "soyun", "kecap", "terasi"],
        "kacang_pohon": ["almond", "pistachio", "kacang pohon", "walnut", "cashew"],
    }.get(code.replace("alg_", ""), [])


def _rows_to_menu(
    menu_row: dict[str, Any],
    ingredient_rows: list[dict[str, Any]],
    recipe_row: dict[str, Any] | None = None,
) -> MenuOut:
    recipe = recipe_row or {}
    # Recipe components are the canonical source once a recipe is verified.
    # Keep legacy menu_ingredients for compatibility, but append any component
    # that is absent there so a hidden BOM ingredient cannot disappear from the
    # Allergy Guard input.
    ingredient_rows = [dict(row) for row in ingredient_rows]
    known_ingredient_ids = {
        str(row.get("ingredient_id"))
        for row in ingredient_rows
        if row.get("ingredient_id")
    }
    for component in recipe.get("recipe_ingredient_rows") or []:
        if not isinstance(component, dict):
            continue
        ingredient_id = str(component.get("ingredient_id") or "")
        if not ingredient_id or ingredient_id in known_ingredient_ids:
            continue
        allergen_codes = split_codes(component.get("allergen_codes"))
        ingredient_rows.append(
            {
                "nama": str(
                    component.get("ingredient_name")
                    or component.get("name")
                    or ingredient_id
                ),
                "sumber": "recipe_component",
                "potensi_alergen": ", ".join(allergen_codes),
                "is_critical_allergen": bool(component.get("is_critical_allergen", False)),
                "ingredient_id": ingredient_id,
                "canonical_allergen_codes": allergen_codes,
                "ingredient_verification_status": str(
                    component.get("ingredient_status") or "UNVERIFIED"
                ),
                "sort_order": component.get("sort_order", 0),
            }
        )
        known_ingredient_ids.add(ingredient_id)

    structured_codes: set[str] = set()
    structured_mapping_available = bool(ingredient_rows)
    ingredients = [
        {
            "nama": str(r.get("nama") or ""),
            "sumber": str(r.get("sumber") or ""),
            "potensi_alergen": str(r.get("potensi_alergen") or ""),
            "is_critical_allergen": bool(r.get("is_critical_allergen", False)),
            "ingredient_id": str(r.get("ingredient_id") or ""),
            "verification_status": str(
                r.get("ingredient_verification_status")
                or r.get("verification_status")
                or "UNVERIFIED"
            ),
        }
        for r in sorted(ingredient_rows, key=lambda x: x.get("sort_order", 0))
    ]

    for row in ingredient_rows:
        raw_codes = row.get("canonical_allergen_codes")
        if not row.get("ingredient_id") or raw_codes is None:
            structured_mapping_available = False
            continue
        if isinstance(raw_codes, str):
            raw_codes = split_codes(raw_codes)
        for code in raw_codes or []:
            normalized = normalize_allergen_code(str(code))
            if normalized:
                structured_codes.add(normalized)

    flagged = [i["nama"] for i in ingredients if i["is_critical_allergen"]]
    if structured_mapping_available:
        codes = sorted(structured_codes)
    elif flagged:
        codes = _detect_codes(flagged)
    else:
        codes = _detect_codes([str(menu_row.get("nama_menu") or "")] + [i["nama"] for i in ingredients])

    labels = {a.code: a.label for a in list_allergens(include_inactive=True)}
    hari = str(menu_row.get("hari") or "")

    # alat_dapur_steril: Postgres TEXT[] → list
    alat_raw = menu_row.get("alat_dapur_steril") or []
    if isinstance(alat_raw, str):
        alat_raw = split_codes(alat_raw)

    # package_codes: Postgres TEXT[] → list
    pkg_raw = menu_row.get("package_codes") or []
    if isinstance(pkg_raw, str):
        pkg_raw = split_codes(pkg_raw)

    recipe_status = str(recipe.get("status") or "UNVERIFIED")
    component_count = int(recipe.get("component_count") or 0)
    unresolved_count = int(recipe.get("unresolved_component_count") or 0)

    return MenuOut(
        menu_id=str(menu_row.get("menu_id") or menu_doc_id(hari, str(menu_row.get("nama_menu") or ""))),
        hari=hari,
        nama_menu=str(menu_row.get("nama_menu") or "—"),
        deskripsi=str(menu_row.get("deskripsi") or ""),
        bahan_detail=ingredients,
        alat_dapur_steril=[str(a) for a in alat_raw if a],
        allergen_codes=codes,
        allergen_labels=[labels.get(c, c) for c in codes],
        published=bool(menu_row.get("published", True)),
        package_codes=[c for c in pkg_raw if c],
        option_index=int(menu_row.get("option_index") or 0),
        recipe_version_id=str(recipe.get("recipe_version_id") or ""),
        recipe_verification_status=recipe_status,
        recipe_cross_contact_risk=str(recipe.get("cross_contact_risk") or "UNKNOWN"),
        recipe_has_unresolved_components=(
            not recipe_row or component_count == 0 or unresolved_count > 0
        ),
    )


def menu_doc_id(hari: str, nama_menu: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", nama_menu.lower()).strip("-")[:48]
    return f"menu_{hari.lower()}_{slug}" if slug else f"menu_{hari.lower()}"


FALLBACK_WEEKLY_MENUS_DATA: list[tuple[dict[str, Any], list[dict[str, Any]]]] = [
    (
        {
            "menu_id": "menu_senin_ayam-rosemary",
            "hari": "Senin",
            "nama_menu": "Ayam Panggang Rosemary & Ubi Madu",
            "deskripsi": "Ayam fillet panggang rempah herba segar tanpa tepung dengan ubi madu oven.",
            "alat_dapur_steril": ["Oven Station 1 (Khusus Non-Gluten)", "Talenan Polimer Hijau #1", "Pisau Stainless 316"],
            "published": True,
            "package_codes": [],
            "option_index": 0,
        },
        [
            {"nama": "Fillet Dada Ayam", "sumber": "Organik segar", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Rosemary & Oregano", "sumber": "Herba segar", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Minyak Zaitun Extra Virgin", "sumber": "Cold-pressed", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
            {"nama": "Ubi Madu Cilembu", "sumber": "Lokal panggang", "potensi_alergen": "Bebas Gluten", "is_critical_allergen": False, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_senin_beef-bulgogi",
            "hari": "Senin",
            "nama_menu": "Beef Bulgogi Wijen & Nasi Beras Cokelat",
            "deskripsi": "Daging sapi iris bumbu bulgogi wijen panggang disajikan dengan nasi beras cokelat.",
            "alat_dapur_steril": ["Wok Wajan Sapi #1", "Talenan Merah #2", "Spatula Stainless Steril"],
            "published": True,
            "package_codes": [],
            "option_index": 1,
        },
        [
            {"nama": "Daging Sapi Has Dalam", "sumber": "Grass-fed", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Minyak Wijen & Biji Wijen", "sumber": "Wijen panggang murni", "potensi_alergen": "⚠️ Wijen", "is_critical_allergen": True, "sort_order": 1},
            {"nama": "Kecap Asin Kedelai", "sumber": "Kedelai fermentasi", "potensi_alergen": "⚠️ Kedelai", "is_critical_allergen": True, "sort_order": 2},
            {"nama": "Beras Cokelat Organik", "sumber": "Pecah kulit", "potensi_alergen": "Bebas Gluten", "is_critical_allergen": False, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_senin_tumis-tahu-teriyaki",
            "hari": "Senin",
            "nama_menu": "Tumis Tahu Jamur Saus Teriyaki (Vegetarian)",
            "deskripsi": "Tahu sutra organik & aneka jamur segar ditumis dengan saus teriyaki gurih.",
            "alat_dapur_steril": ["Wok Vegetarian Hijau #1", "Talenan Hijau #3", "Spatula Kayu Jati Steril"],
            "published": True,
            "package_codes": [],
            "option_index": 2,
        },
        [
            {"nama": "Tahu Sutra Organik", "sumber": "Non-GMO", "potensi_alergen": "⚠️ Kedelai", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Jamur Tiram & Shitake", "sumber": "Hidroponik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Saus Teriyaki Alami", "sumber": "Bumbu alami non-MSG", "potensi_alergen": "⚠️ Kedelai", "is_critical_allergen": True, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_selasa_sup-daging-rempah",
            "hari": "Selasa",
            "nama_menu": "Sup Daging Sapi Jamur Rempah",
            "deskripsi": "Kaldu sapi rebusan lambat 12 jam dengan jamur kancing dan rempah aromatik.",
            "alat_dapur_steril": ["Stock Pot Stainless Steel #3", "Sendok Sayur Stainless", "Talenan Kuning #2"],
            "published": True,
            "package_codes": [],
            "option_index": 0,
        },
        [
            {"nama": "Daging Sapi Sandung Lamur", "sumber": "Lokal grass-fed", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Kaldu Tulang Sapi", "sumber": "Rebusan murni tanpa MSG", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Jamur Tiram & Kancing", "sumber": "Budidaya higienis", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
            {"nama": "Wortel & Daun Bawang", "sumber": "Sayur hidroponik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_selasa_ayam-salted-egg",
            "hari": "Selasa",
            "nama_menu": "Ayam Fillet Crispy Saus Salted Egg",
            "deskripsi": "Fillet ayam tepung beras renyah disiram saus kuning telur asin harum daun kari.",
            "alat_dapur_steril": ["Deep Fryer Station Bebas Gandum", "Talenan Polimer Hijau #2", "Saringan Stainless Steril"],
            "published": True,
            "package_codes": [],
            "option_index": 1,
        },
        [
            {"nama": "Dada Ayam Fillet", "sumber": "Probiotik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Kuning Telur Asin", "sumber": "Telur bebek pilihan", "potensi_alergen": "⚠️ Telur", "is_critical_allergen": True, "sort_order": 1},
            {"nama": "Tepung Beras & Maizena", "sumber": "Non-gandum murni", "potensi_alergen": "Bebas Gluten", "is_critical_allergen": False, "sort_order": 2},
            {"nama": "Daun Kari Segar", "sumber": "Kebun herbal", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_selasa_dori-lemon",
            "hari": "Selasa",
            "nama_menu": "Fillet Dori Panggang Lemon & Salad Jagung",
            "deskripsi": "Fillet ikan dori lembut dipanggang butter herbal dengan pendamping salad jagung manis.",
            "alat_dapur_steril": ["Pan Khusus Ikan Biru #1", "Talenan Biru #1", "Capitan Silikon"],
            "published": True,
            "package_codes": [],
            "option_index": 2,
        },
        [
            {"nama": "Fillet Dori Laut", "sumber": "Tangkapan segar", "potensi_alergen": "⚠️ Seafood/Ikan", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Lemon Segar & Butter", "sumber": "Dairy butter murni", "potensi_alergen": "⚠️ Susu/Laktosa", "is_critical_allergen": True, "sort_order": 1},
            {"nama": "Jagung Manis Pipil & Selada", "sumber": "Hidroponik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_rabu_ayam-suwir-matah",
            "hari": "Rabu",
            "nama_menu": "Ayam Suwir Sambal Matah & Urap Sayur",
            "deskripsi": "Ayam kukus suwir disiram sambal matah Bali segar dengan pelengkap urap sayur kelapa sangrai.",
            "alat_dapur_steril": ["Steamer Unggas Stainless #1", "Talenan Putih #1", "Pisau Khusus Sayur"],
            "published": True,
            "package_codes": [],
            "option_index": 0,
        },
        [
            {"nama": "Dada Ayam Ungkep", "sumber": "Rempah kuning alami", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Bawang Merah & Cabai Rawit", "sumber": "Segar lokal", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Kelapa Parut Bumbu Urap", "sumber": "Kelapa muda segar", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_rabu_kakap-bakar",
            "hari": "Rabu",
            "nama_menu": "Ikan Kakap Bakar Kunyit & Nasi Merah",
            "deskripsi": "Fillet kakap putih bakar bumbu kunyit lengkuas rempah disajikan bersama nasi beras merah pulen.",
            "alat_dapur_steril": ["Grill Pan Biru #1 (Zona Terisolasi)", "Talenan Biru #3", "Spatula Silikon Seafood"],
            "published": True,
            "package_codes": [],
            "option_index": 1,
        },
        [
            {"nama": "Fillet Kakap Putih", "sumber": "Tangkapan harian", "potensi_alergen": "⚠️ Seafood/Ikan", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Bumbu Kunyit Lengkuas", "sumber": "Ulekan alami", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Nasi Merah Organik", "sumber": "Beras merah pecah kulit", "potensi_alergen": "Bebas Gluten", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_rabu_gado-gado",
            "hari": "Rabu",
            "nama_menu": "Gado-Gado Roll Saus Kacang Gurih",
            "deskripsi": "Gulungan sayuran segar, lontong, dan tempe dengan saus kacang tanah kental resep istimewa.",
            "alat_dapur_steril": ["Prep Table Sayur Higienis", "Talenan Putih #2", "Blender Saus Khusus Kacang"],
            "published": True,
            "package_codes": [],
            "option_index": 2,
        },
        [
            {"nama": "Sayuran Campur & Tauge", "sumber": "Ozon steril", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Tempe Kedelai Kukus", "sumber": "Kedelai lokal", "potensi_alergen": "⚠️ Kedelai", "is_critical_allergen": True, "sort_order": 1},
            {"nama": "Saus Kacang Tanah Mede", "sumber": "Kacang sangrai murni", "potensi_alergen": "⚠️ Kacang Tanah", "is_critical_allergen": True, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_kamis_tumis-ayam-jamur",
            "hari": "Kamis",
            "nama_menu": "Tumis Ayam Jamur Brokoli Saus Bawang",
            "deskripsi": "Tumis ayam probiotik dan brokoli hijau dengan saus bawang putih bening ramah alergen.",
            "alat_dapur_steril": ["Wok Wajan Hijau #2 (Alergen-Free Zone)", "Talenan Putih #1", "Spatula Kayu Jati Steril"],
            "published": True,
            "package_codes": [],
            "option_index": 0,
        },
        [
            {"nama": "Dada Ayam Fillet", "sumber": "Probiotik segar", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Brokoli Organik", "sumber": "Dicuci air garam ozon", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Jamur Kancing", "sumber": "Segar higienis", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
            {"nama": "Saus Bawang Putih Alami", "sumber": "Kaldu ayam & garam murni", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_kamis_udang-madu",
            "hari": "Kamis",
            "nama_menu": "Udang Bakar Madu Jimbaran & Nasi Merah",
            "deskripsi": "Udang windu segar berbalut glaze madu karamel dan rempah khas Jimbaran disajikan dengan nasi merah.",
            "alat_dapur_steril": ["Grill Station Seafood Biru", "Talenan Biru #2", "Kuas Silikon Steril"],
            "published": True,
            "package_codes": [],
            "option_index": 1,
        },
        [
            {"nama": "Udang Windu Segar", "sumber": "Tangkapan muara", "potensi_alergen": "⚠️ Seafood/Udang", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Madu Hutan & Rempah", "sumber": "Madu murni", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Nasi Merah Organik", "sumber": "Pecah kulit", "potensi_alergen": "Bebas Gluten", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_kamis_rendang-suwir",
            "hari": "Kamis",
            "nama_menu": "Rendang Daging Sapi Suwir & Buncis",
            "deskripsi": "Daging sapi suwir karamel santan rempah Minang dipadu buncis muda rebus segar.",
            "alat_dapur_steril": ["Wajan Khusus Daging Merah #1", "Talenan Merah #1", "Sendok Pengaduk Kayu"],
            "published": True,
            "package_codes": [],
            "option_index": 2,
        },
        [
            {"nama": "Daging Sapi Has Dalam", "sumber": "Grass-fed lokal", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Santan Kelapa Murni", "sumber": "Kelapa tua peras pertama", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Bumbu Rempah Rendang", "sumber": "Rempah asli tanpa MSG", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
            {"nama": "Buncis Baby Rebus", "sumber": "Hidroponik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_jumat_ayam-taliwang",
            "hari": "Jumat",
            "nama_menu": "Ayam Bakar Taliwang & Plecing Kangkung",
            "deskripsi": "Ayam bakar bumbu pedas manis Taliwang aromatik disajikan dengan plecing kangkung segar.",
            "alat_dapur_steril": ["Grill Station Unggas #2", "Talenan Hijau #2", "Kuas Panggang Khusus"],
            "published": True,
            "package_codes": [],
            "option_index": 0,
        },
        [
            {"nama": "Ayam Kampung Panggang", "sumber": "Segar non-suntik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Cabai, Terasi, Jeruk Limau", "sumber": "Bumbu Taliwang", "potensi_alergen": "⚠️ Terasi/Seafood", "is_critical_allergen": True, "sort_order": 1},
            {"nama": "Kangkung Segar Rebus", "sumber": "Hidroponik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_jumat_salmon-lemon",
            "hari": "Jumat",
            "nama_menu": "Salmon Fillet Lemon Herb & Kentang Kukus",
            "deskripsi": "Norwegian salmon panggang butter lemon segar disajikan bersama kentang baby kukus dan buncis.",
            "alat_dapur_steril": ["Pan Stainless Khusus Salmon", "Talenan Biru #2", "Kukusan Stainless Bebas Gluten"],
            "published": True,
            "package_codes": [],
            "option_index": 1,
        },
        [
            {"nama": "Norwegian Salmon Fillet", "sumber": "Grade sashimi", "potensi_alergen": "⚠️ Seafood/Ikan", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Lemon Segar & Butter", "sumber": "Dairy butter murni", "potensi_alergen": "⚠️ Susu/Laktosa", "is_critical_allergen": True, "sort_order": 1},
            {"nama": "Kentang Baby Kukus", "sumber": "Kukusan uap murni", "potensi_alergen": "Bebas Gluten", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_jumat_pasta-fusilli-pesto",
            "hari": "Jumat",
            "nama_menu": "Pasta Fusilli Ayam Pesto Keju",
            "deskripsi": "Fusilli al dente dengan saus pesto kemangi harum, potongan ayam panggang, dan taburan keju parmesan.",
            "alat_dapur_steril": ["Pasta Boiler Khusus #1", "Talenan Putih #3", "Spatula Silikon"],
            "published": True,
            "package_codes": [],
            "option_index": 2,
        },
        [
            {"nama": "Fusilli Semolina Gandum", "sumber": "Gandum durum", "potensi_alergen": "⚠️ Gluten", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Dada Ayam Panggang", "sumber": "Fillet ayam", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Pesto Kemangi & Kacang Kenari", "sumber": "Herbal pesto", "potensi_alergen": "⚠️ Kacang", "is_critical_allergen": True, "sort_order": 2},
            {"nama": "Keju Parmesan", "sumber": "Dairy cheese", "potensi_alergen": "⚠️ Susu/Laktosa", "is_critical_allergen": True, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_sabtu_ayam-madu",
            "hari": "Sabtu",
            "nama_menu": "Nasi Merah Ayam Bakar Madu Ketumbar",
            "deskripsi": "Ayam bakar karamel madu hutan asli dan biji ketumbar sangrai murni disajikan dengan nasi merah.",
            "alat_dapur_steril": ["Panggangan Arang Stainless", "Kuas Silikon Khusus", "Talenan Hijau #2"],
            "published": True,
            "package_codes": [],
            "option_index": 0,
        },
        [
            {"nama": "Ayam Kampung Potong", "sumber": "Segar non-suntik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 0},
            {"nama": "Madu Hutan Asli", "sumber": "Madu mentah alami", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Biji Ketumbar Sangrai", "sumber": "Rempah asli murni", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
            {"nama": "Nasi Merah Pulen", "sumber": "Beras lokal organik", "potensi_alergen": "Bebas Gluten", "is_critical_allergen": False, "sort_order": 3},
        ],
    ),
    (
        {
            "menu_id": "menu_sabtu_tom-yum",
            "hari": "Sabtu",
            "nama_menu": "Sup Tom Yum Udang & Ikan Kakap",
            "deskripsi": "Sup asam pedas segar kaldu udang dan ikan kakap dengan serai, lengkuas, dan daun jeruk purut.",
            "alat_dapur_steril": ["Soup Pot Seafood Biru #2", "Talenan Biru #3", "Sendok Sayur Stainless"],
            "published": True,
            "package_codes": [],
            "option_index": 1,
        },
        [
            {"nama": "Udang Segar & Kakap", "sumber": "Tangkapan laut harian", "potensi_alergen": "⚠️ Seafood", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Serai, Daun Jeruk, Cabai", "sumber": "Bumbu rempah tom yum", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Jamur Kancing & Tomat", "sumber": "Sayur hidroponik", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
    (
        {
            "menu_id": "menu_sabtu_steak-tempe",
            "hari": "Sabtu",
            "nama_menu": "Steak Tempe Lada Hitam (Vegetarian)",
            "deskripsi": "Steak tempe kedelai non-GMO panggang lembut berpadu siraman saus lada hitam aromatik.",
            "alat_dapur_steril": ["Grill Pan Vegetarian Hijau #1", "Talenan Hijau #3", "Spatula Kayu"],
            "published": True,
            "package_codes": [],
            "option_index": 2,
        },
        [
            {"nama": "Tempe Organik Non-GMO", "sumber": "Kedelai lokal alami", "potensi_alergen": "⚠️ Kedelai", "is_critical_allergen": True, "sort_order": 0},
            {"nama": "Saus Lada Hitam Alami", "sumber": "Lada hitam & kaldu sayur", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 1},
            {"nama": "Wortel & Buncis Rebus", "sumber": "Sayur segar kukus", "potensi_alergen": "Aman", "is_critical_allergen": False, "sort_order": 2},
        ],
    ),
]


def _fallback_menus(*, include_unpublished: bool = False) -> list[MenuOut]:
    menus = [_rows_to_menu(m_row, ing_rows) for m_row, ing_rows in FALLBACK_WEEKLY_MENUS_DATA]
    if not include_unpublished:
        menus = [m for m in menus if m.published]
    order = {d: i for i, d in enumerate(DAYS)}
    return sorted(menus, key=lambda m: (order.get(m.hari, 99), m.option_index, m.nama_menu))


def list_menus(
    *,
    use_cache: bool = True,
    include_unpublished: bool = False,
) -> list[MenuOut]:
    key = f"menus:{include_unpublished}"
    if use_cache:
        return list(
            _cached(key, lambda: list_menus(use_cache=False, include_unpublished=include_unpublished))
        )

    try:
        menu_rows = db.execute(
            f"SELECT * FROM {TABLE_MENUS} ORDER BY hari, option_index"  # noqa: S608
        )
        if not menu_rows:
            log.info("Tabel %s kosong — menggunakan 18 menu fallback.", TABLE_MENUS)
            return _fallback_menus(include_unpublished=include_unpublished)
        menu_ids = [r["menu_id"] for r in menu_rows]
        ing_rows = db.execute(
            f"""
            SELECT mi.*, i.allergen_codes AS canonical_allergen_codes,
                   i.verification_status AS ingredient_verification_status
            FROM {TABLE_MENU_INGREDIENTS} mi
            LEFT JOIN ingredients i ON i.ingredient_id = mi.ingredient_id
            WHERE mi.menu_id = ANY(%s)
            ORDER BY mi.sort_order
            """,  # noqa: S608
            (menu_ids,),
        )
        recipe_rows = db.execute(
            """
            SELECT
                rv.menu_id,
                rv.recipe_version_id,
                rv.status,
                rv.cross_contact_risk,
                COUNT(rc.recipe_component_id) AS component_count,
                COUNT(rc.recipe_component_id) FILTER (
                    WHERE rc.ingredient_id IS NULL
                       OR rc.quantity IS NULL
                       OR rc.unit = 'UNKNOWN'
                       OR rc.verification_status <> 'VERIFIED'
                       OR i.verification_status <> 'VERIFIED'
                ) AS unresolved_component_count,
                COALESCE(
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'ingredient_id', i.ingredient_id,
                            'ingredient_name', i.name,
                            'ingredient_status', i.verification_status,
                            'allergen_codes', COALESCE(i.allergen_codes, '{}'::TEXT[]),
                            'sort_order', rc.sort_order
                        )
                    ) FILTER (WHERE rc.ingredient_id IS NOT NULL),
                    '[]'::JSONB
                ) AS recipe_ingredient_rows
            FROM recipe_versions rv
            LEFT JOIN recipe_components rc
              ON rc.recipe_version_id = rv.recipe_version_id
            LEFT JOIN ingredients i
              ON i.ingredient_id = rc.ingredient_id
            WHERE rv.menu_id = ANY(%s)
            GROUP BY rv.menu_id, rv.recipe_version_id, rv.version_no,
                     rv.status, rv.cross_contact_risk
            ORDER BY rv.menu_id, rv.version_no DESC
            """,
            (menu_ids,),
        )
    except Exception as exc:
        log.warning("Baca menu dari DB gagal (%s) — menggunakan 18 menu fallback.", exc)
        return _fallback_menus(include_unpublished=include_unpublished)

    # Kelompokkan bahan per menu_id
    ing_map: dict[str, list[dict[str, Any]]] = {}
    for r in ing_rows:
        ing_map.setdefault(r["menu_id"], []).append(r)

    recipe_map: dict[str, dict[str, Any]] = {}
    for row in recipe_rows:
        recipe_map.setdefault(str(row["menu_id"]), row)

    menus = [
        _rows_to_menu(r, ing_map.get(r["menu_id"], []), recipe_map.get(str(r["menu_id"])))
        for r in menu_rows
        if r.get("hari") in DAYS
    ]
    if not include_unpublished:
        menus = [m for m in menus if m.published]

    order = {d: i for i, d in enumerate(DAYS)}
    return sorted(menus, key=lambda m: (order.get(m.hari, 99), m.option_index, m.nama_menu))


def menus_by_day(*, use_cache: bool = True) -> dict[str, list[MenuOut]]:
    if use_cache:
        return dict(_cached("menus_by_day_multi", lambda: menus_by_day(use_cache=False)))
    grouped: dict[str, list[MenuOut]] = {d: [] for d in DAYS}
    for menu in list_menus(use_cache=False):
        grouped.setdefault(menu.hari, []).append(menu)
    return grouped


def primary_menu_by_day(*, use_cache: bool = True) -> dict[str, MenuOut]:
    if use_cache:
        return dict(_cached("menus_primary", lambda: primary_menu_by_day(use_cache=False)))
    return {
        day: options[0]
        for day, options in menus_by_day(use_cache=False).items()
        if options
    }


def get_menu(menu_id: str) -> MenuOut:
    menu_id = str(menu_id or "").strip()
    if not menu_id:
        raise NotFoundError("Menu tidak ditemukan.")
    for menu in list_menus(include_unpublished=True):
        if menu.menu_id == menu_id:
            return menu
    raise NotFoundError(f"Menu '{menu_id}' tidak ditemukan.")


def get_day_options(hari: str, *, package_code: str = "") -> list[MenuOut]:
    options = menus_by_day().get(hari, [])
    if package_code:
        options = [m for m in options if m.available_for(package_code)]
    return options


# ── Agregat + cache ─────────────────────────────────────────────────────────
def load_catalog(*, include_inactive: bool = False, use_cache: bool = True) -> dict[str, Any]:
    key = f"catalog:{include_inactive}"
    if use_cache:
        cached = _cache.get(key)
        if cached is not None:
            return cached
    value = {
        "packages": list_packages(include_inactive=include_inactive),
        "allergens": list_allergens(include_inactive=include_inactive),
        "menus": list_menus(),
        "is_live": True,
    }
    _cache.set(key, value)
    return value


def invalidate_cache() -> None:
    _cache.invalidate()
    log.info("Cache katalog dibersihkan.")


def upsert_document(collection: str, doc: dict[str, Any]) -> None:
    """
    Kompatibilitas dengan service lama yang memanggil upsert_document.

    Di Postgres kita routing berdasarkan nama collection/tabel:
    packages, allergens, menus (dengan menu_ingredients).
    """
    if collection == TABLE_PACKAGES:
        _upsert_package(doc)
    elif collection == TABLE_ALLERGENS:
        _upsert_allergen(doc)
    elif collection == TABLE_MENUS:
        _upsert_menu(doc)
    else:
        raise ValidationError(f"Tabel '{collection}' tidak dikenali untuk upsert_document.")
    invalidate_cache()


def _upsert_package(doc: dict[str, Any]) -> None:
    code = str(doc.get("code") or doc.get("_id") or "")
    if not code:
        raise ValidationError("Paket harus memiliki kode.")
    days_raw = doc.get("days") or []
    if isinstance(days_raw, str):
        days_raw = split_codes(days_raw)
    try:
        db.execute_write(
            """
            INSERT INTO packages (code, name, days, description, price, active)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                days = EXCLUDED.days,
                description = EXCLUDED.description,
                price = EXCLUDED.price,
                active = EXCLUDED.active
            """,
            (
                code,
                str(doc.get("name") or ""),
                days_raw,
                str(doc.get("description") or ""),
                doc.get("price"),
                bool(doc.get("active", True)),
            ),
        )
    except Exception as exc:
        raise DatabaseError(f"Gagal menyimpan paket '{code}'.") from exc


def _upsert_allergen(doc: dict[str, Any]) -> None:
    code = normalize_allergen_code(str(doc.get("code") or doc.get("_id") or ""))
    if not code:
        raise ValidationError("Alergen harus memiliki kode.")
    try:
        db.execute_write(
            """
            INSERT INTO allergens (code, label, risiko, active, category)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                label = EXCLUDED.label,
                risiko = EXCLUDED.risiko,
                active = EXCLUDED.active,
                category = EXCLUDED.category
            """,
            (
                code,
                str(doc.get("label") or ""),
                str(doc.get("risiko") or ""),
                bool(doc.get("active", True)),
                str(doc.get("category") or "allergy"),
            ),
        )
    except Exception as exc:
        raise DatabaseError(f"Gagal menyimpan alergen '{code}'.") from exc


def _upsert_menu(doc: dict[str, Any]) -> None:
    hari = str(doc.get("hari") or "")
    nama = str(doc.get("nama_menu") or "")
    menu_id = str(doc.get("menu_id") or doc.get("_id") or menu_doc_id(hari, nama))
    if not hari or not nama:
        raise ValidationError("Menu harus memiliki hari dan nama_menu.")

    alat_raw = doc.get("alat_dapur_steril") or []
    if isinstance(alat_raw, str):
        alat_raw = split_codes(alat_raw)
    pkg_raw = doc.get("package_codes") or doc.get("packages") or []
    if isinstance(pkg_raw, str):
        pkg_raw = split_codes(pkg_raw)

    try:
        db.execute_write(
            """
            INSERT INTO menus (menu_id, hari, nama_menu, deskripsi, alat_dapur_steril,
                               published, package_codes, option_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (menu_id) DO UPDATE SET
                hari = EXCLUDED.hari,
                nama_menu = EXCLUDED.nama_menu,
                deskripsi = EXCLUDED.deskripsi,
                alat_dapur_steril = EXCLUDED.alat_dapur_steril,
                published = EXCLUDED.published,
                package_codes = EXCLUDED.package_codes,
                option_index = EXCLUDED.option_index
            """,
            (
                menu_id, hari, nama,
                str(doc.get("deskripsi") or ""),
                alat_raw,
                bool(doc.get("published", True)),
                pkg_raw,
                int(doc.get("option_index") or 0),
            ),
        )
        # Ganti semua bahan (delete + insert) — sederhana & aman
        db.execute_write(
            f"DELETE FROM {TABLE_MENU_INGREDIENTS} WHERE menu_id = %s",  # noqa: S608
            (menu_id,),
        )
        bahan_raw = [b for b in (doc.get("bahan_detail") or []) if isinstance(b, dict)]
        for i, bahan in enumerate(bahan_raw):
            db.execute_write(
                """
                INSERT INTO menu_ingredients
                    (menu_id, nama, sumber, potensi_alergen, is_critical_allergen, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    menu_id,
                    str(bahan.get("nama") or ""),
                    str(bahan.get("sumber") or ""),
                    str(bahan.get("potensi_alergen") or ""),
                    "⚠" in str(bahan.get("potensi_alergen") or ""),
                    i,
                ),
            )
    except Exception as exc:
        raise DatabaseError(f"Gagal menyimpan menu '{menu_id}'.") from exc


def update_fields(collection: str, doc_id: str, fields: dict[str, Any]) -> bool:
    """Update field tertentu pada satu baris."""
    if not doc_id:
        raise ValidationError("doc_id wajib diisi.")
    if not fields:
        return True

    if collection == TABLE_PACKAGES:
        pk_col = "code"
    elif collection == TABLE_ALLERGENS:
        pk_col = "code"
    elif collection == TABLE_MENUS:
        pk_col = "menu_id"
    else:
        raise ValidationError(f"Tabel '{collection}' tidak dikenali untuk update_fields.")

    # Hanya izinkan nama kolom alfanumerik+underscore
    safe_fields = {k: v for k, v in fields.items() if re.match(r"^[a-z_]+$", k)}
    if not safe_fields:
        return True

    set_clause = ", ".join(f"{k} = %s" for k in safe_fields)
    values = tuple(safe_fields.values()) + (doc_id,)
    try:
        db.execute_write(
            f"UPDATE {collection} SET {set_clause} WHERE {pk_col} = %s",  # noqa: S608
            values,
        )
    except Exception as exc:
        raise DatabaseError(f"Gagal memperbarui '{doc_id}' di '{collection}'.") from exc
    invalidate_cache()
    return True


def get_raw(collection: str, doc_id: str) -> dict[str, Any] | None:
    if collection == TABLE_PACKAGES:
        return db.execute_one(f"SELECT * FROM {TABLE_PACKAGES} WHERE code = %s", (doc_id,))  # noqa: S608
    if collection == TABLE_ALLERGENS:
        return db.execute_one(f"SELECT * FROM {TABLE_ALLERGENS} WHERE code = %s", (doc_id,))  # noqa: S608
    if collection == TABLE_MENUS:
        return db.execute_one(f"SELECT * FROM {TABLE_MENUS} WHERE menu_id = %s", (doc_id,))  # noqa: S608
    raise DatabaseError(f"Tabel '{collection}' tidak dikenali.")


def fetch_collection(collection: str, *, limit: int = 200, sort: dict | None = None) -> list[dict[str, Any]]:
    # sort dict tidak dipakai di Postgres — gunakan ORDER BY default per tabel
    order_col = "code" if collection in (TABLE_PACKAGES, TABLE_ALLERGENS) else "menu_id"
    try:
        return db.execute(
            f"SELECT * FROM {collection} ORDER BY {order_col} LIMIT %s",  # noqa: S608
            (limit,),
        )
    except Exception as exc:
        raise DatabaseError(f"Gagal membaca tabel '{collection}'.") from exc
