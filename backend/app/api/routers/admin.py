"""Router admin — katalog, pelanggan, pembayaran, dan diagnosa sistem."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.core.domain import (
    ACTIVE_STATUSES,
    COLLECTION_ALLERGENS,
    COLLECTION_MENUS,
    COLLECTION_ORDERS,
    COLLECTION_PACKAGES,
    COLLECTION_PROFILES,
    FOREIGN_COLLECTIONS,
)
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.repositories import astra, catalog_repo, customer_repo, order_repo
from app.schemas.catalog import (
    AllergenIn,
    AllergenOut,
    AllergenPatch,
    MenuIn,
    MenuOut,
    MenuPatch,
    PackageIn,
    PackageOut,
    PackagePatch,
)
from app.schemas.customer import CustomerAdminOut, CustomerOut, StaffIn
from app.schemas.internal import (
    AdminDashboardOut,
    AdminKpi,
    AdminScheduleOut,
    AdminSystemOut,
    CollectionCount,
)
from app.schemas.order import InvoiceOut, OrderDetailOut
from app.services import auth_service, catalog_service, dashboard_service, invoice_service, order_service

log = get_logger("dova.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Dashboard ───────────────────────────────────────────────────────────────
@router.get("/dashboard", response_model=AdminDashboardOut, summary="Ringkasan admin")
def dashboard(admin: CustomerOut = Depends(require_admin)) -> AdminDashboardOut:
    return dashboard_service.admin_dashboard()


@router.get("/kpis", response_model=list[AdminKpi], summary="Kartu KPI")
def kpis(admin: CustomerOut = Depends(require_admin)) -> list[AdminKpi]:
    return dashboard_service.kpi_cards()


@router.get("/schedule", response_model=AdminScheduleOut, summary="Jadwal per hari layanan")
def schedule(admin: CustomerOut = Depends(require_admin)) -> AdminScheduleOut:
    return dashboard_service.admin_schedule()


# ── Katalog ─────────────────────────────────────────────────────────────────
@router.put("/packages/{code}", response_model=PackageOut, summary="Buat/ubah paket")
def save_package(
    code: str, payload: PackageIn, admin: CustomerOut = Depends(require_admin)
) -> PackageOut:
    """`code` pada path harus sama dengan `code` pada body."""
    if code != payload.code:
        payload = payload.model_copy(update={"code": code})
    return catalog_service.upsert_package(payload)


@router.patch("/packages/{code}", response_model=PackageOut, summary="Ubah sebagian paket")
def patch_package(
    code: str, patch: PackagePatch, admin: CustomerOut = Depends(require_admin)
) -> PackageOut:
    return catalog_service.patch_package(code, patch)


@router.put("/allergens/{code}", response_model=AllergenOut, summary="Buat/ubah profil alergen")
def save_allergen(
    code: str, payload: AllergenIn, admin: CustomerOut = Depends(require_admin)
) -> AllergenOut:
    if code != payload.code:
        payload = payload.model_copy(update={"code": code})
    return catalog_service.upsert_allergen(payload)


@router.patch("/allergens/{code}", response_model=AllergenOut, summary="Ubah sebagian profil alergen")
def patch_allergen(
    code: str, patch: AllergenPatch, admin: CustomerOut = Depends(require_admin)
) -> AllergenOut:
    return catalog_service.patch_allergen(code, patch)


@router.put("/menus/{hari}", response_model=MenuOut, summary="Buat/ubah opsi menu harian")
def save_menu(
    hari: str, payload: MenuIn, admin: CustomerOut = Depends(require_admin)
) -> MenuOut:
    """
    Upsert satu opsi menu pada hari `hari`.

    `menu_id` menentukan dokumen yang disentuh. Kalau dikosongkan, opsi baru dibuat
    dengan `menu_id` deterministik, sehingga admin dapat memuat ulang form tanpa
    menghasilkan dokumen duplikat setiap kali menyimpan.
    """
    return catalog_service.upsert_menu(payload.model_copy(update={"hari": hari}))


@router.post(
    "/menus/{hari}",
    response_model=MenuOut,
    status_code=201,
    summary="Tambah opsi menu kedua (atau seterusnya) untuk satu hari",
)
def add_menu_option(
    hari: str, payload: MenuIn, admin: CustomerOut = Depends(require_admin)
) -> MenuOut:
    """
    Tambah opsi BARU untuk hari yang sama tanpa menyentuh opsi yang sudah ada.

    Berbeda dari `PUT /menus/{hari}` yang bersifat upsert, pemanggil di sini
    sedang membuat opsi baru: `menu_id` yang dikirim dipakai apa adanya, dan yang
    kosong berarti "biarkan backend yang menentukan" (turunan hari + slug judul).
    Ini juga yang membuat form admin bisa mengirim ulang tanpa membuat duplikat.
    """
    return catalog_service.upsert_menu(payload.model_copy(update={"hari": hari}))


@router.patch("/menus/{menu_id}", response_model=MenuOut, summary="Ubah sebagian opsi menu")
def patch_menu_option(
    menu_id: str, patch: MenuPatch, admin: CustomerOut = Depends(require_admin)
) -> MenuOut:
    """Ubah satu opsi menu berdasarkan `menu_id`-nya, bukan posisinya di daftar."""
    return catalog_service.patch_menu(menu_id, patch)


@router.post(
    "/menus/{menu_id}/publish",
    response_model=MenuOut,
    summary="Terbitkan sebuah opsi menu",
)
def publish_menu_option(
    menu_id: str, admin: CustomerOut = Depends(require_admin)
) -> MenuOut:
    """
    Meng-published opsi menu membuatnya muncul di `/menu` dan bisa dipilih pelanggan.

    Menu yang ditarik tidak dihapus: pesanan yang sudah memakai `menu_id` itu tetap
    punya judulnya, dan data historis tidak berubah.
    """
    return catalog_service.set_menu_published(menu_id, published=True)


@router.delete(
    "/menus/{menu_id}/publish",
    response_model=MenuOut,
    summary="Tarik opsi menu dari pelanggan (tidak menghapus data)",
)
def unpublish_menu_option(
    menu_id: str, admin: CustomerOut = Depends(require_admin)
) -> MenuOut:
    return catalog_service.set_menu_published(menu_id, published=False)


@router.post("/catalog/{kind}/{code}/toggle", summary="Aktif/nonaktif entri katalog")
def toggle(
    kind: str, code: str, admin: CustomerOut = Depends(require_admin)
) -> dict[str, Any]:
    """`kind` harus `packages` atau `allergens`."""
    mapping = {"packages": COLLECTION_PACKAGES, "allergens": COLLECTION_ALLERGENS}
    if kind not in mapping:
        raise ValidationError("Jenis katalog tidak dikenal. Gunakan 'packages' atau 'allergens'.")
    active = catalog_service.toggle_active(mapping[kind], code)
    catalog_repo.invalidate_cache()
    return {"code": code, "active": active}


# ── Pelanggan ───────────────────────────────────────────────────────────────
@router.get("/customers", response_model=list[CustomerAdminOut], summary="Daftar pelanggan")
def list_customers(
    admin: CustomerOut = Depends(require_admin),
    limit: int = Query(200, ge=1, le=1000),
) -> list[CustomerAdminOut]:
    """
    Daftar pelanggan beserta ringkasan order-nya.

    `passport` sengaja tidak ikut dikembalikan di daftar (bisa besar) — ambil
    lewat `/api/customers/{customer_id}` bila perlu.
    """
    out: list[CustomerAdminOut] = []
    for doc in customer_repo.list_customers(limit=limit):
        base = customer_repo.to_public(doc)
        orders = order_repo.fetch_orders(customer_id=base.customer_id, limit=1000)
        out.append(
            CustomerAdminOut(
                **base.model_dump(),
                order_count=len(orders),
                active_order_count=sum(1 for o in orders if o["status"] in ACTIVE_STATUSES),
                last_order_at=next((o["created_at"] for o in orders if o["created_at"]), None),
            )
        )
    return out


@router.post("/staff", response_model=CustomerOut, status_code=201, summary="Buat akun admin/kitchen")
def create_staff(
    payload: StaffIn, admin: CustomerOut = Depends(require_admin)
) -> CustomerOut:
    """
    Buat akun staff. Password wajib (minimal 8 karakter).

    Endpoint ini hanya bisa dipakai admin yang sudah ada. Akun admin pertama
    dibuat lewat skrip seed (`backend/scripts/seed_staff.py`) supaya tidak
    ada akun yang bisa membuat akun lain tanpa seed.
    """
    return auth_service.create_staff(
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        role=payload.role,
    )


# ── Pembayaran ──────────────────────────────────────────────────────────────
@router.post(
    "/orders/{order_id}/payment",
    response_model=InvoiceOut,
    summary="Perbarui status pembayaran",
)
def set_payment(
    order_id: str,
    admin: CustomerOut = Depends(require_admin),
    status: str = Query(..., description="UNPAID | PENDING | PAID | REFUNDED"),
    reference: str = Query("", max_length=120, description="Nomor transfer/receipt"),
) -> InvoiceOut:
    """
    Tandai pembayaran secara manual.

    Belum ada payment gateway pada MVP, jadi ini satu-satunya cara invoice
    berubah status.
    """
    order = order_service.get_order_detail(order_id, is_staff=True)
    invoice_service.set_payment_status(order.id, status.upper(), reference.strip())
    return order_service.get_invoice_for_staff(order_id)


# ── Sistem ──────────────────────────────────────────────────────────────────
@router.get("/system", response_model=AdminSystemOut, summary="Status sistem & database")
def system(admin: CustomerOut = Depends(require_admin)) -> AdminSystemOut:
    from app.core.config import settings

    connected = astra.is_connected()
    collections: list[CollectionCount] = []
    if connected:
        for name in (
            COLLECTION_PACKAGES,
            COLLECTION_ALLERGENS,
            COLLECTION_MENUS,
            COLLECTION_ORDERS,
            COLLECTION_PROFILES,
        ):
            collections.append(
                CollectionCount(name=name, documents=astra.count_documents(name), managed=True)
            )
    return AdminSystemOut(
        astra_connected=connected,
        demo_mode=settings.demo_mode,
        credentials=settings.credential_status(),
        collections=collections,
        foreign_collections=list(FOREIGN_COLLECTIONS),
        telegram_bot_username=settings.telegram_bot_username,
        telegram_deep_link_order=settings.telegram_link("order"),
        langflow_configured=bool(settings.langflow_flow_id),
        version=settings.app_version,
    )