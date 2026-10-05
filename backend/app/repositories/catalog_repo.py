"""Katalog terstruktur: paket, alergen, menu mingguan.

Semua pembacaan sudah dinormalisasi di sini sehingga service dan frontend
tidak pernah melihat dokumen Astra mentah.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.core.domain import (
    COLLECTION_ALLERGENS,
    COLLECTION_MENUS,
    COLLECTION_PACKAGES,
    DAYS,
    normalize_allergen_code,
    split_codes,
)
from app.core.errors import DatabaseError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.repositories.astra import get_collection
from app.repositories.cache import TTLCache
from app.schemas.catalog import AllergenOut, MenuOut, PackageOut

log = get_logger("dova.repo.catalog")

_cache: TTLCache[dict[str, Any]] = TTLCache(settings.catalog_cache_ttl_seconds)


def _cached(key: str, loader: Any) -> Any:
    """
    Baca lewat cache TTL.

    Katalog dibaca sangat sering (safety report memanggilnya per hari, KDS per
    render) sementara isinya berubah sangat jarang. Tanpa cache ini satu
    permintaan bisa menembak Astra puluhan kali.
    """
    value = _cache.get(key)
    if value is None:
        value = loader()
        _cache.set(key, value)
    return value


# ── Allergen ────────────────────────────────────────────────────────────────
def _normalize_allergen(doc: dict[str, Any]) -> AllergenOut:
    return AllergenOut(
        code=normalize_allergen_code(doc.get("code") or doc.get("_id")),
        label=str(doc.get("label") or "—"),
        risiko=str(doc.get("risiko") or ""),
        active=bool(doc.get("active", True)),
        category=str(doc.get("category") or "allergy"),
    )


def list_allergens(*, include_inactive: bool = False, use_cache: bool = True) -> list[AllergenOut]:
    if use_cache:
        # Disalin: list hasil cache dibaca bersama banyak request, dan satu
        # service yang menyortir/menghapus elemennya tidak boleh mengubah
        # salinan milik request lain.
        return list(
            _cached(
                f"allergens:{include_inactive}",
                lambda: list_allergens(include_inactive=include_inactive, use_cache=False),
            )
        )
    try:
        cursor = get_collection(COLLECTION_ALLERGENS).find({}, sort={"code": 1}, limit=200)
        rows = list(cursor)
    except Exception as exc:
        log.error("Baca %s gagal: %s: %s", COLLECTION_ALLERGENS, type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca definisi alergen.") from exc

    out = [_normalize_allergen(d) for d in rows]
    if not include_inactive:
        out = [a for a in out if a.active]
    return sorted(out, key=lambda a: a.code)


# ── Packages ────────────────────────────────────────────────────────────────
def _normalize_package(doc: dict[str, Any]) -> PackageOut:
    days = [d for d in DAYS if d in set(split_codes(doc.get("days")))]
    price = doc.get("price")
    try:
        price_int = int(price) if price is not None else None
    except (TypeError, ValueError):
        log.warning("Harga paket %s bukan angka, diabaikan: %r", doc.get("code"), price)
        price_int = None
    return PackageOut(
        code=str(doc.get("code") or doc.get("_id") or ""),
        name=str(doc.get("name") or "—"),
        days=days,
        description=str(doc.get("description") or ""),
        meal_count=len(days),
        price=price_int,
        active=bool(doc.get("active", True)),
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
        rows = list(get_collection(COLLECTION_PACKAGES).find({}, sort={"code": 1}, limit=100))
    except Exception as exc:
        log.error("Baca %s gagal: %s: %s", COLLECTION_PACKAGES, type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca daftar paket.") from exc

    out = [_normalize_package(d) for d in rows]
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
    """Bahan dianggap alergen kritis bila `potensi_alergen` memuat penanda ⚠."""
    return "⚠" in str(bahan.get("potensi_alergen") or "")


#: Pola negatif yang harus dibuang sebelum pencocokan kata kunci.
#: "Saus Bawang Putih … tanpa kecap kedelai/terasi" TIDAK mengandung kedelai.
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
    """Petakan teks → kode katalog lewat pencocokan kata kunci (sudah antisipasi negasi)."""
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
    """Kata kunciBAHAN per tema alergen — lebih akurat dari label katalog."""
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


def _normalize_menu(doc: dict[str, Any]) -> MenuOut:
    bahan_raw = [b for b in (doc.get("bahan_detail") or []) if isinstance(b, dict)]
    ingredients = [
        {
            "nama": str(b.get("nama") or ""),
            "sumber": str(b.get("sumber") or ""),
            "potensi_alergen": str(b.get("potensi_alergen") or ""),
            "is_critical_allergen": _critical_ingredient(b),
        }
        for b in bahan_raw
    ]

    # Sinyal otoritatif: bahan yang ditandai ⚠ oleh dapur.
    flagged = [i["nama"] for i in ingredients if i["is_critical_allergen"]]
    if flagged:
        codes = _detect_codes(flagged)
    else:
        # Fallback: pindai nama menu + bahan, bukan deskripsi (banyak deskripsi
        # memuat kalimat negatif seperti "tanpa kecap kedelai").
        codes = _detect_codes([str(doc.get("nama_menu") or "")] + [i["nama"] for i in ingredients])

    labels = {a.code: a.label for a in list_allergens(include_inactive=True)}
    hari = str(doc.get("hari") or "")
    return MenuOut(
        menu_id=str(doc.get("_id") or menu_doc_id(hari, str(doc.get("nama_menu") or ""))),
        hari=hari,
        nama_menu=str(doc.get("nama_menu") or "—"),
        deskripsi=str(doc.get("deskripsi") or ""),
        bahan_detail=ingredients,
        alat_dapur_steril=[str(a) for a in (doc.get("alat_dapur_steril") or []) if a],
        allergen_codes=codes,
        allergen_labels=[labels.get(c, c) for c in codes],
        # Absen = published. Enam dokumen live tidak punya field ini dan tetap
        # harus tampil sebagai opsi yang bisa dipesan.
        published=bool(doc.get("published", True)),
        # Absen = tersedia untuk semua paket.
        package_codes=[c for c in split_codes(doc.get("packages") or doc.get("package_codes")) if c],
        option_index=int(doc.get("option_index") or 0),
    )


def menu_doc_id(hari: str, nama_menu: str) -> str:
    """
    `_id` deterministik untuk satu opsi menu: `menu_<hari>_<slug>`.

    Sebelumnya `_id` selalu `menu_<hari>`, sehingga hanya ada satu dokumen per
    hari dan opsi kedua akan menimpa yang pertama. Menyertakan nama menu adalah
    yang membuat satu hari bisa memegang beberapa opsi tanpa koleksi baru.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", nama_menu.lower()).strip("-")[:48]
    return f"menu_{hari.lower()}_{slug}" if slug else f"menu_{hari.lower()}"


def list_menus(
    *,
    use_cache: bool = True,
    include_unpublished: bool = False,
) -> list[MenuOut]:
    """
    Semua opsi menu, diurutkan per hari lalu per urutan opsi.

    Tidak ada `limit` kecil di sini: 6 hari × N opsi melampaui batas lama 20, dan
    pemotongan diam-diam akan menghilangkan opsi yang sebenarnya bisa dipesan.
    """
    key = f"menus:{include_unpublished}"
    if use_cache:
        return list(
            _cached(key, lambda: list_menus(use_cache=False, include_unpublished=include_unpublished))
        )

    try:
        rows = list(
            get_collection(COLLECTION_MENUS).find({}, sort={"hari": 1, "option_index": 1}, limit=500)
        )
    except Exception as exc:
        log.error("Baca %s gagal: %s: %s", COLLECTION_MENUS, type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca menu mingguan.") from exc

    menus = [_normalize_menu(d) for d in rows if d.get("hari") in DAYS]
    if not include_unpublished:
        menus = [m for m in menus if m.published]

    order = {d: i for i, d in enumerate(DAYS)}
    return sorted(menus, key=lambda m: (order.get(m.hari, 99), m.option_index, m.nama_menu))


def menus_by_day(*, use_cache: bool = True) -> dict[str, list[MenuOut]]:
    """Semua opsi per hari. Kunci dict = `DAYS`, nilai = daftar opsi (bisa kosong)."""
    if use_cache:
        return dict(_cached("menus_by_day_multi", lambda: menus_by_day(use_cache=False)))

    grouped: dict[str, list[MenuOut]] = {d: [] for d in DAYS}
    for menu in list_menus(use_cache=False):
        grouped.setdefault(menu.hari, []).append(menu)
    return grouped


def primary_menu_by_day(*, use_cache: bool = True) -> dict[str, MenuOut]:
    """
    Satu opsi utama per hari.

    Dipakai KDS dan rekap admin untuk pesanan yang belum menyimpan pilihan menu
    per pelanggan. Pelanggan yang sudah memilih tetap memakai pilihannya sendiri —
    lihat `order_service.resolve_service_menu`.
    """
    if use_cache:
        return dict(_cached("menus_primary", lambda: primary_menu_by_day(use_cache=False)))
    return {
        day: options[0]
        for day, options in menus_by_day(use_cache=False).items()
        if options
    }


def get_menu(menu_id: str) -> MenuOut:
    """Cari satu opsi menu berdasarkan `menu_id` (nilai dokumen `_id`)."""
    menu_id = str(menu_id or "").strip()
    if not menu_id:
        raise NotFoundError("Menu tidak ditemukan.")
    for menu in list_menus(include_unpublished=True):
        if menu.menu_id == menu_id:
            return menu
    raise NotFoundError(f"Menu '{menu_id}' tidak ditemukan.")


def get_day_options(hari: str, *, package_code: str = "") -> list[MenuOut]:
    """
    Opsi yang boleh dipilih untuk satu hari pada satu paket.

    Ini satu-satunya tempat ketersediaan paket ditegakkan saat PEMBACAAN; saat
    PEMBUATAN pesanan, `order_service.validate_selections` menegakkan aturan yang
    sama dari sisi lain, supaya tidak bisa dilewati dengan mengirim `menu_id` langsung.
    """
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
    """Panggil setelah admin menulis katalog."""
    _cache.invalidate()
    log.info("Cache katalog dibersihkan.")


def upsert_document(collection: str, doc: dict[str, Any]) -> None:
    if "_id" not in doc:
        raise ValidationError("Dokumen harus memiliki `_id`.")
    try:
        get_collection(collection).find_one_and_replace(
            filter={"_id": doc["_id"]}, replacement=doc, upsert=True
        )
    except Exception as exc:
        log.error("Upsert %s/%s gagal: %s: %s", collection, doc["_id"], type(exc).__name__, exc)
        raise DatabaseError(f"Gagal menyimpan ke collection '{collection}'.") from exc
    invalidate_cache()


def update_fields(collection: str, doc_id: str, fields: dict[str, Any]) -> bool:
    if not doc_id:
        raise ValidationError("doc_id wajib diisi.")
    try:
        get_collection(collection).update_one({"_id": doc_id}, {"$set": fields})
    except Exception as exc:
        log.error("Update %s/%s gagal: %s: %s", collection, doc_id, type(exc).__name__, exc)
        raise DatabaseError(f"Gagal memperbarui dokumen '{doc_id}'.") from exc
    invalidate_cache()
    return True


def get_raw(collection: str, doc_id: str) -> dict[str, Any] | None:
    try:
        return get_collection(collection).find_one({"_id": doc_id})
    except Exception as exc:
        log.error("Baca %s/%s gagal: %s: %s", collection, doc_id, type(exc).__name__, exc)
        raise DatabaseError(f"Gagal membaca dokumen '{doc_id}'.") from exc


def fetch_collection(collection: str, *, limit: int = 200, sort: dict | None = None) -> list[dict[str, Any]]:
    try:
        return list(
            get_collection(collection).find({}, sort=sort or {"_id": 1}, limit=limit)
        )
    except Exception as exc:
        log.error("Baca collection %s gagal: %s: %s", collection, type(exc).__name__, exc)
        raise DatabaseError(f"Gagal membaca collection '{collection}'.") from exc
