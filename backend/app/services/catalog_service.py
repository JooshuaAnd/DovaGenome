"""Catalog service — baca katalog + aturan validasi admin.

Aturan validasi ini sebelumnya berada di callback Streamlit
(`admin_kitchen_dashboard.py`) dan kini dipindah ke backend sebagai aturan tunggal.
"""

from __future__ import annotations

import datetime

from app.core.domain import COLLECTION_ALLERGENS, COLLECTION_MENUS, COLLECTION_PACKAGES, DAYS
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.repositories import catalog_repo
from app.schemas.catalog import (
    AllergenIn,
    AllergenOut,
    AllergenPatch,
    CatalogMetaOut,
    CatalogOut,
    DayOptionsOut,
    MenuIn,
    MenuOut,
    MenuPatch,
    PackageIn,
    PackageOut,
    PackagePatch,
    ServiceWeekOut,
)
from app.schemas.customer import PassportOut
from app.services import safety_service
from app.utils.time import (
    current_service_monday,
    format_service_date,
    now_iso,
    now_wib,
    service_week_dates,
)

log = get_logger("dova.catalog")


# ── Baca (public) ──────────────────────────────────────────────────────────
def list_packages(*, include_inactive: bool = False) -> list[PackageOut]:
    return catalog_repo.list_packages(include_inactive=include_inactive)


def list_allergens(*, include_inactive: bool = False) -> list[AllergenOut]:
    return catalog_repo.list_allergens(include_inactive=include_inactive)


def list_menus() -> list[MenuOut]:
    return catalog_repo.list_menus()


def get_catalog(*, include_inactive: bool = False) -> CatalogOut:
    raw = catalog_repo.load_catalog(include_inactive=include_inactive)
    return CatalogOut(
        packages=raw["packages"],
        allergens=raw["allergens"],
        menus=raw["menus"],
        # previously `[m.hari for m in raw["menus"]]` duplicated every day that had
        # more than one option; a set of unique days is the real intent.
        service_days=service_days(),
        is_live=raw["is_live"],
        source="astra",
    )


def service_days() -> list[str]:
    """Hari layanan yang benar-benar punya minimal satu opsi menu published."""
    grouped = catalog_repo.menus_by_day()
    return [d for d in DAYS if grouped.get(d)]


def get_meta() -> CatalogMetaOut:
    cat = get_catalog(include_inactive=True)
    return CatalogMetaOut(
        service_days=cat.service_days,
        total_packages=len(cat.packages),
        total_allergens=len(cat.allergens),
        total_menus=len(cat.menus),
        is_live=cat.is_live,
        generated_at=now_iso(),
    )


# ── Minggu layanan (read model untuk /menu dan /order) ──────────────────────
def get_service_week(
    *,
    package_code: str = "",
    days: list[str] | None = None,
    passport: PassportOut | None = None,
    selected_codes: list[str] | None = None,
    include_unpublished: bool = False,
) -> ServiceWeekOut:
    """
    "Menu minggu ini": tiap hari layanan + tanggalnya + SEMUA opsi menunya.

    Ini read model yang dipakai `/menu` dan langkah pemilihan harian di `/order`.
    Endpoint `/catalog/menus` tetap hidup dengan bentuk lamanya (daftar datar);
    yang dijamin di sini adalah pengelompokan per hari dan status keamanan per
    opsi, yang memang tidak bisa ditunjukkan dalam bentuk datar.

    Hanya opsi `published` yang muncul. Ketersediaan paket diterapkan di sini
    untuk tampilan, dan ditegakkan ulang di `order_service.validate_selections`
    saat pesanan dibuat.
    """
    wanted = [d for d in (days or list(DAYS)) if d in DAYS] or list(DAYS)
    grouped = catalog_repo.menus_by_day()
    if include_unpublished:
        all_menus = catalog_repo.list_menus(include_unpublished=True)
        grouped = {d: [] for d in DAYS}
        for menu in all_menus:
            grouped.setdefault(menu.hari, []).append(menu)

    dates = service_week_dates(wanted)
    today_wib = now_wib().date()

    excluded, preference, all_codes = safety_service.resolve_exclusions(
        selected_codes=selected_codes, passport=passport
    )
    ctx = safety_service.CatalogContext()

    rows: list[DayOptionsOut] = []
    for day in wanted:
        options = grouped.get(day) or []
        if package_code:
            options = [m for m in options if m.available_for(package_code)]
        if not options:
            continue

        service_date = dates.get(day, "")
        try:
            is_past = bool(service_date) and datetime.date.fromisoformat(service_date) < today_wib
        except ValueError:
            is_past = False

        rows.append(
            DayOptionsOut(
                hari=day,
                service_date=service_date,
                date_label=format_service_date(service_date),
                is_past=is_past,
                options=options,
                # `options` sudah difilter paket, jadi safety harus dihitung dari
                # daftar yang sama — kalau tidak keduanya bergeser.
                safety=safety_service.check_options(
                    options, day, excluded,
                    preference_codes=preference, ctx=ctx,
                ),
            )
        )

    return ServiceWeekOut(
        week_start=current_service_monday().isoformat(),
        days=rows,
        applied_codes=sorted(all_codes),
        has_passport=bool(passport and (passport.critical_codes or passport.preferences)),
        is_live=True,
    )


# ── Tulis (admin) ───────────────────────────────────────────────────────────
def upsert_package(payload: PackageIn) -> PackageOut:
    """Buat/ubah paket. Aturan: code + name wajib, minimal 1 hari layanan."""
    existing = catalog_repo.get_raw(COLLECTION_PACKAGES, payload.code)
    if existing and str(existing.get("code") or existing.get("_id")) != payload.code:
        raise ConflictError(f"Kode paket '{payload.code}' sudah dipakai dokumen lain.")

    doc: dict = {
        "_id": payload.code,
        "code": payload.code,
        "name": payload.name.strip(),
        "days": payload.days,
        "description": payload.description.strip(),
        "active": payload.active,
        "updated_at": now_iso(),
    }
    if payload.price is not None:
        doc["price"] = int(payload.price)
    elif existing and existing.get("price") is not None:
        doc["price"] = int(existing["price"])  # harga lama dipertahankan

    catalog_repo.upsert_document(COLLECTION_PACKAGES, doc)
    log.info("catalog_package_saved code=%s active=%s", payload.code, payload.active)
    return catalog_repo.get_package(payload.code)


def patch_package(code: str, patch: PackagePatch) -> PackageOut:
    existing = catalog_repo.get_raw(COLLECTION_PACKAGES, code)
    if not existing:
        raise ValidationError(f"Paket '{code}' tidak ditemukan.")
    fields = patch.model_dump(exclude_none=True)
    if fields.get("days") is not None and not fields["days"]:
        raise ValidationError("Paket harus punya minimal satu hari layanan.")
    if fields:
        catalog_repo.update_fields(COLLECTION_PACKAGES, code, fields)
        log.info("catalog_package_patched code=%s fields=%s", code, list(fields))
    return catalog_repo.get_package(code)


def upsert_allergen(payload: AllergenIn) -> AllergenOut:
    """Buat/ubah profil alergen. Aturan: code + label wajib."""
    doc = {
        "_id": payload.code,
        "code": payload.code,
        "label": payload.label.strip(),
        "risiko": payload.risiko.strip(),
        "active": payload.active,
        "category": payload.category,
        "updated_at": now_iso(),
    }
    catalog_repo.upsert_document(COLLECTION_ALLERGENS, doc)
    log.info("catalog_allergen_saved code=%s active=%s", payload.code, payload.active)
    return next(
        (a for a in catalog_repo.list_allergens(include_inactive=True) if a.code == payload.code),
        AllergenOut(code=payload.code, label=payload.label),
    )


def patch_allergen(code: str, patch: AllergenPatch) -> AllergenOut:
    existing = catalog_repo.get_raw(COLLECTION_ALLERGENS, code)
    if not existing:
        raise ValidationError(f"Profil '{code}' tidak ditemukan.")
    fields = patch.model_dump(exclude_none=True)
    if fields:
        catalog_repo.update_fields(COLLECTION_ALLERGENS, code, fields)
        log.info("catalog_allergen_patched code=%s fields=%s", code, list(fields))
    return next(
        (a for a in catalog_repo.list_allergens(include_inactive=True) if a.code == code),
        AllergenOut(code=code, label=str(existing.get("label") or code)),
    )


def toggle_active(collection: str, code: str) -> bool:
    """Aktif/nonaktif satu entri katalog."""
    if collection not in (COLLECTION_PACKAGES, COLLECTION_ALLERGENS):
        raise ValidationError("Koleksi tidak dapat di-toggle.")
    existing = catalog_repo.get_raw(collection, code)
    if not existing:
        raise ValidationError(f"Dokumen '{code}' tidak ditemukan.")
    new_value = not bool(existing.get("active", True))
    catalog_repo.update_fields(collection, code, {"active": new_value, "updated_at": now_iso()})
    log.info("catalog_toggled collection=%s code=%s active=%s", collection, code, new_value)
    return new_value


def menu_by_id(menu_id: str) -> MenuOut:
    return catalog_repo.get_menu(menu_id)


def upsert_menu(payload: MenuIn) -> MenuOut:
    """
    Buat atau ubah SATU opsi menu.

    `menu_id` kosong → membuat opsi baru. `_id` diturunkan dari hari + slug nama
    menu, bukan hanya `menu_<hari>`, sehingga satu hari bisa memegang beberapa
    opsi tanpa saling menimpa.

    Aturan dari UI lama dipertahankan: `nama_menu` dan minimal satu
    `alat_dapur_steril` wajib diisi — tanpa itu dapur tidak tahu protokolnya.
    """
    if not payload.hari:
        raise ValidationError("Menu harus punya hari layanan.")

    doc_id = payload.menu_id.strip() or catalog_repo.menu_doc_id(
        payload.hari, payload.nama_menu
    )

    existing = catalog_repo.get_raw(COLLECTION_MENUS, doc_id)
    if existing and str(existing.get("hari") or "") != payload.hari:
        raise ConflictError(
            f"Menu '{doc_id}' sudah terdaftar pada hari {existing.get('hari')}. "
            "Gunakan hari yang sama atau menu_id lain."
        )

    known_packages = {p.code for p in catalog_repo.list_packages(include_inactive=True)}
    unknown = [c for c in payload.package_codes if c not in known_packages]
    if unknown:
        raise ValidationError(
            f"Kode paket tidak dikenal: {', '.join(sorted(unknown))}",
            details={"known": sorted(known_packages)},
        )

    doc: dict = {
        "_id": doc_id,
        "hari": payload.hari,
        "nama_menu": payload.nama_menu.strip(),
        "deskripsi": payload.deskripsi.strip(),
        "bahan_detail": [
            {
                "nama": b.nama.strip(),
                "sumber": b.sumber.strip(),
                "potensi_alergen": b.potensi_alergen.strip() or "Diperiksa dapur",
            }
            for b in payload.bahan_detail
            if b.nama.strip()
        ],
        "alat_dapur_steril": [a.strip() for a in payload.alat_dapur_steril if a.strip()],
        "published": payload.published,
        "packages": list(payload.package_codes),
        "option_index": payload.option_index,
        "updated_at": now_iso(),
    }

    catalog_repo.upsert_document(COLLECTION_MENUS, doc)
    log.info(
        "catalog_menu_saved id=%s hari=%s published=%s bahan=%d",
        doc_id, payload.hari, payload.published, len(doc["bahan_detail"]),
    )
    return catalog_repo.get_menu(doc_id)


def patch_menu(menu_id: str, patch: MenuPatch) -> MenuOut:
    """
    Partial update satu opsi menu.

    Hanya field yang dikirim yang berubah; sisanya diambil dari dokumen yang sudah
    ada. Ini yang membuat form admin bisa menyimpan satu perubahan kecil (mis. hanya
    mencabut satu bahan) tanpa harus mengirim ulang seluruh isi menu.
    """
    existing = catalog_repo.get_raw(COLLECTION_MENUS, menu_id)
    if not existing:
        raise ValidationError(f"Menu '{menu_id}' tidak ditemukan.")

    current = catalog_repo.get_menu(menu_id)
    merged = MenuIn(
        menu_id=menu_id,
        hari=current.hari,
        nama_menu=patch.nama_menu if patch.nama_menu is not None else current.nama_menu,
        deskripsi=patch.deskripsi if patch.deskripsi is not None else current.deskripsi,
        bahan_detail=(
            patch.bahan_detail if patch.bahan_detail is not None else current.bahan_detail
        ),
        alat_dapur_steril=(
            patch.alat_dapur_steril
            if patch.alat_dapur_steril is not None
            else current.alat_dapur_steril
        ),
        published=patch.published if patch.published is not None else current.published,
        package_codes=(
            patch.package_codes if patch.package_codes is not None else current.package_codes
        ),
        option_index=(
            patch.option_index if patch.option_index is not None else current.option_index
        ),
    )
    return upsert_menu(merged)


def set_menu_published(menu_id: str, published: bool) -> MenuOut:
    """
    Publikasikan atau tarik satu opsi menu.

    Menarik sebuah opsi tidak menghapus choice yang sudah dipakai pelanggan:
    order lama tetap menyimpan `menu_id`-nya dan KDS masih bisa menampilkannya
    lewat `order_service.resolve_service_menu`.
    """
    if not catalog_repo.get_raw(COLLECTION_MENUS, menu_id):
        raise ValidationError(f"Menu '{menu_id}' tidak ditemukan.")
    catalog_repo.update_fields(
        COLLECTION_MENUS, menu_id, {"published": published, "updated_at": now_iso()}
    )
    log.info("catalog_menu_published id=%s published=%s", menu_id, published)
    return catalog_repo.get_menu(menu_id)


def list_all_menus(*, include_unpublished: bool = False) -> list[MenuOut]:
    """Semua opsi menu untuk layar admin — termasuk yang belum dipublikasikan."""
    return catalog_repo.list_menus(include_unpublished=include_unpublished)
