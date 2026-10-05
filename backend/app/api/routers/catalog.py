"""Router katalog — endpoint publik yang dipakai landing page.

Pelanggan tidak perlu login untuk melihat paket, menu, dan ketersediaan hari.
Harga dan label allergen selalu berasal dari katalog di Astra DB.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_optional_customer, get_optional_staff
from app.core.domain import DAYS
from app.core.errors import PermissionError_
from app.core.logging import get_logger
from app.schemas.catalog import (
    AllergenOut,
    CatalogMetaOut,
    CatalogOut,
    MenuOut,
    PackageOut,
    ServiceWeekOut,
)
from app.schemas.customer import CustomerOut
from app.schemas.order import SafetyReportOut
from app.services import catalog_service, order_service, passport_service, safety_service

log = get_logger("dova.api.catalog")

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=CatalogOut, summary="Katalog lengkap (paket, alergen, menu)")
def get_catalog(
    include_inactive: bool = Query(False, description="Khusus admin; default hanya yang aktif"),
    staff: CustomerOut | None = Depends(get_optional_staff),
) -> CatalogOut:
    """
    Katalog publik.

    `include_inactive` sengaja butuh akun admin: entri nonaktif bisa berisi
    harga/isi lama yang sudah tidak berlaku, jadi tidak boleh bocor lewat
    endpoint publik.
    """
    if include_inactive and not staff:
        raise PermissionError_("Hanya admin yang dapat melihat entri katalog nonaktif.")
    return catalog_service.get_catalog(include_inactive=include_inactive)


@router.get("/meta", response_model=CatalogMetaOut, summary="Ringkasan katalog")
def get_meta() -> CatalogMetaOut:
    return catalog_service.get_meta()


@router.get("/packages", response_model=list[PackageOut], summary="Daftar paket")
def list_packages() -> list[PackageOut]:
    return catalog_service.list_packages()


@router.get("/allergens", response_model=list[AllergenOut], summary="Daftar profil alergen")
def list_allergens() -> list[AllergenOut]:
    return catalog_service.list_allergens()


@router.get("/menus", response_model=list[MenuOut], summary="Menu per hari layanan")
def list_menus() -> list[MenuOut]:
    """
    Semua opsi menu yang dipublikasikan.

    Satu hari layanan bisa punya banyak entri — ini yang membuat "pilih satu menu
    per hari" mungkin. Gunakan `/catalog/menus/week` untuk versi yang sudah
    dikelompokkan per hari beserta tanggal dan status keamanannya.
    """
    return catalog_service.list_menus()


@router.get(
    "/menus/week",
    response_model=ServiceWeekOut,
    summary="Menu minggu ini per hari (dengan pilihan per hari)",
)
def service_week(
    package_code: str = Query("", description="Saring opsi sesuai ketersediaan paket"),
    days: list[str] = Query(default_factory=list, description="Default: semua hari layanan"),
    selected_allergen_codes: list[str] = Query(default_factory=list),
    customer: CustomerOut | None = Depends(get_optional_customer),
) -> ServiceWeekOut:
    """
    Read model untuk `/menu` dan langkah pemilihan harian di `/order`.

    Mengembalikan tiap hari layanan + tanggalnya + daftar opsi menunya, masing-masing
    dengan status keamanan. Tidak butuh login — bila pelanggan sudah masuk, Dietary
    Passport-nya ikut dipakai sehingga kartu bisa langsung menunjukkan "aman" atau
    "mengandung X" sesuai preferensi yang tersimpan.
    """
    passport = passport_service.passport_for(customer) if customer else None

    return catalog_service.get_service_week(
        package_code=package_code.strip(),
        days=[d for d in days if d in DAYS] or None,
        passport=passport,
        selected_codes=selected_allergen_codes,
    )


@router.get(
    "/safety",
    response_model=SafetyReportOut,
    summary="Cek kecocokan menu (tanpa login)",
)
def preview_safety(
    selected_allergen_codes: list[str] = Query(default_factory=list),
    days: list[str] = Query(default_factory=list),
) -> SafetyReportOut:
    """
    Cek menu tanpa menyimpan apa pun.

    Tidak menerapkan Dietary Passport karena belum ada akun — pemanggil sendiri
    yang mengoper kode batasan yang dipilih.
    """
    return safety_service.build_report(
        selected_codes=selected_allergen_codes,
        passport=None,
        schedule_days=[d for d in days if d in DAYS] or list(DAYS),
    )