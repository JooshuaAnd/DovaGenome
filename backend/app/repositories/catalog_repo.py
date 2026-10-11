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
    except Exception as exc:
        log.error("Baca %s gagal: %s: %s", TABLE_ALLERGENS, type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca definisi alergen.") from exc

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
    except Exception as exc:
        log.error("Baca %s gagal: %s: %s", TABLE_PACKAGES, type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca daftar paket.") from exc

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


def _rows_to_menu(menu_row: dict[str, Any], ingredient_rows: list[dict[str, Any]]) -> MenuOut:
    ingredients = [
        {
            "nama": str(r.get("nama") or ""),
            "sumber": str(r.get("sumber") or ""),
            "potensi_alergen": str(r.get("potensi_alergen") or ""),
            "is_critical_allergen": bool(r.get("is_critical_allergen", False)),
        }
        for r in sorted(ingredient_rows, key=lambda x: x.get("sort_order", 0))
    ]

    flagged = [i["nama"] for i in ingredients if i["is_critical_allergen"]]
    if flagged:
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
    )


def menu_doc_id(hari: str, nama_menu: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", nama_menu.lower()).strip("-")[:48]
    return f"menu_{hari.lower()}_{slug}" if slug else f"menu_{hari.lower()}"


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
            return []
        menu_ids = [r["menu_id"] for r in menu_rows]
        ing_rows = db.execute(
            f"SELECT * FROM {TABLE_MENU_INGREDIENTS} WHERE menu_id = ANY(%s) ORDER BY sort_order",  # noqa: S608
            (menu_ids,),
        )
    except Exception as exc:
        log.error("Baca menu gagal: %s: %s", type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca menu mingguan.") from exc

    # Kelompokkan bahan per menu_id
    ing_map: dict[str, list[dict[str, Any]]] = {}
    for r in ing_rows:
        ing_map.setdefault(r["menu_id"], []).append(r)

    menus = [
        _rows_to_menu(r, ing_map.get(r["menu_id"], []))
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
