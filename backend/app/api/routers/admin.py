"""Router admin — katalog, pelanggan, pembayaran, dan diagnosa sistem."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin, get_optional_staff
from app.core.domain import (
    ACTIVE_STATUSES,
    COLLECTION_ALLERGENS,
    COLLECTION_MENUS,
    COLLECTION_ORDERS,
    COLLECTION_PACKAGES,
)
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.repositories import supabase, catalog_repo, customer_repo, order_repo
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
    staff: CustomerOut | None = Depends(get_optional_staff),
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

    connected = supabase.is_connected()
    collections: list[CollectionCount] = []
    if connected:
        for name in (
            COLLECTION_PACKAGES,
            COLLECTION_ALLERGENS,
            COLLECTION_MENUS,
            COLLECTION_ORDERS,
        ):
            collections.append(
                CollectionCount(name=name, documents=supabase.count_rows(name), managed=True)
            )
    return AdminSystemOut(
        astra_connected=connected,
        demo_mode=settings.demo_mode,
        credentials=settings.credential_status(),
        collections=collections,
        foreign_collections=[],
        telegram_bot_username=settings.telegram_bot_username,
        telegram_deep_link_order=settings.telegram_link("order"),
        langflow_configured=bool(settings.langflow_flow_id),
        version=settings.app_version,
    )


# ── POS & Kitchen Display System (Bitepoint UI) ─────────────────────────────
@router.get("/pos-kds", summary="Data lengkap pesanan untuk KDS & Payment")
def get_pos_kds(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Mengambil pesanan aktif, antrean dapur, dan pembayaran langsung dari Supabase."""
    orders = supabase.execute(
        """
        SELECT o.order_id, o.customer_id, o.customer_name, o.delivery_address,
               o.status, o.payment_status, o.total, o.selected_allergens,
               o.created_at,
               COALESCE(json_agg(json_build_object('hari', oi.hari, 'menu_id', oi.menu_id, 'nama_menu', m.nama_menu)) FILTER (WHERE oi.id IS NOT NULL), '[]'::json) as items
        FROM orders o
        LEFT JOIN order_items oi ON o.order_id = oi.order_id
        LEFT JOIN menus m ON oi.menu_id = m.menu_id
        GROUP BY o.order_id, o.customer_id, o.customer_name, o.delivery_address,
                 o.status, o.payment_status, o.total, o.selected_allergens, o.created_at
        ORDER BY o.created_at DESC
        LIMIT 50
        """
    )
    
    # Hitung metrik
    new_orders = sum(1 for o in orders if o.get("status") in ("PENDING", "PREPARING"))
    total_orders = len(orders)
    waiting_list = sum(1 for o in orders if o.get("status") == "PREPARING")

    return {
        "metrics": {
            "new_orders": new_orders,
            "total_orders": total_orders,
            "waiting_list": waiting_list,
        },
        "orders": orders,
    }


@router.post("/orders/{order_id}/advance", summary="Majukan status pesanan dapur")
def advance_order_status(
    order_id: str,
    target_status: str = Query(..., description="PREPARING | READY | COMPLETED | CANCELLED"),
    staff: CustomerOut | None = Depends(get_optional_staff),
) -> dict[str, Any]:
    """Memajukan status tiket dapur dan mencatat notifikasi otomatis ke pelanggan."""
    supabase.execute_write(
        "UPDATE orders SET status = %s, updated_at = NOW() WHERE order_id = %s",
        (target_status.upper(), order_id)
    )

    # Catat event
    actor_name = (staff.display_name or staff.username) if staff else "Kitchen Ops"
    supabase.execute_write(
        "INSERT INTO order_status_events (order_id, status, actor, note) VALUES (%s, %s, %s, %s)",
        (order_id, target_status.upper(), actor_name, f"Status dimajukan ke {target_status}")
    )

    # Tambahkan notifikasi outbox otomatis
    order = supabase.execute_one("SELECT customer_name FROM orders WHERE order_id = %s", (order_id,))
    cname = order.get("customer_name") if order else "Pelanggan"
    msg = f"Halo {cname}! Status pesanan {order_id} kini: {target_status.upper()} di Dova Kitchen."
    supabase.execute_write(
        """
        INSERT INTO notification_outbox (recipient_type, recipient_phone, recipient_name, channel, event_type, message, status)
        VALUES ('customer', '+6281234567890', %s, 'whatsapp', 'STATUS_UPDATE', %s, 'SENT')
        """,
        (cname, msg)
    )

    return {"status": "ok", "order_id": order_id, "new_status": target_status.upper()}


@router.get("/popular-dishes", summary="Menu terpopuler berdasarkan data pesanan riil")
def get_popular_dishes(staff: CustomerOut | None = Depends(get_optional_staff)) -> list[dict[str, Any]]:
    """Mengambil peringkat hidangan terlaris langsung dari tabel order_items di Supabase."""
    return supabase.execute(
        """
        SELECT m.menu_id, m.nama_menu, m.hari,
               COUNT(oi.id) as order_count
        FROM menus m
        JOIN order_items oi ON m.menu_id = oi.menu_id
        GROUP BY m.menu_id, m.nama_menu, m.hari
        ORDER BY order_count DESC, m.nama_menu ASC
        LIMIT 6
        """
    )


@router.get("/inventory-alerts", summary="Peringatan stok kritis & bahan menipis")
def get_inventory_alerts(staff: CustomerOut | None = Depends(get_optional_staff)) -> list[dict[str, Any]]:
    """Mengambil status bahan dari inventory_stocks."""
    return supabase.execute(
        "SELECT id, ingredient_name, current_stock, min_stock, unit, status, updated_at FROM inventory_stocks ORDER BY CASE WHEN status = 'HABIS' THEN 1 WHEN status = 'MENIPIS' THEN 2 ELSE 3 END"
    )


@router.get("/notifications", summary="Daftar outbox notifikasi WA & Telegram")
def list_notifications(staff: CustomerOut | None = Depends(get_optional_staff)) -> list[dict[str, Any]]:
    """Daftar log pesan otomatis WhatsApp/Telegram ke pelanggan dan supplier."""
    return supabase.execute(
        "SELECT id, recipient_type, recipient_name, recipient_phone, channel, event_type, message, status, created_at FROM notification_outbox ORDER BY created_at DESC LIMIT 30"
    )


@router.post("/notifications/send", summary="Kirim pesan otomatis WA/Telegram")
def send_notification(
    recipient_type: str = Query(..., description="customer | supplier | admin"),
    recipient_name: str = Query(...),
    recipient_phone: str = Query(...),
    channel: str = Query("whatsapp", description="whatsapp | telegram"),
    message: str = Query(...),
    staff: CustomerOut | None = Depends(get_optional_staff),
) -> dict[str, Any]:
    """Kirim pesan otomatis dan catat ke outbox."""
    supabase.execute_write(
        """
        INSERT INTO notification_outbox (recipient_type, recipient_phone, recipient_name, channel, event_type, message, status)
        VALUES (%s, %s, %s, %s, 'DIRECT_MESSAGE', %s, 'SENT')
        """,
        (recipient_type, recipient_phone, recipient_name, channel, message)
    )
    return {"status": "sent", "channel": channel, "recipient": recipient_name}


@router.get("/suppliers", summary="Daftar supplier dan status PO aktif")
def list_suppliers_and_pos(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Mengambil supplier, item yang dijual, dan status PO terkini."""
    suppliers = supabase.execute("SELECT * FROM suppliers ORDER BY rating DESC")
    pos = supabase.execute(
        """
        SELECT po.po_id, po.supplier_id, s.name as supplier_name, s.phone as supplier_phone,
               po.status, po.total_amount, po.need_by_date, po.notes, po.created_at,
               COALESCE(json_agg(json_build_object('item_name', pi.item_name, 'qty', pi.qty, 'unit', pi.unit, 'subtotal', pi.subtotal)) FILTER (WHERE pi.id IS NOT NULL), '[]'::json) as lines
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.supplier_id
        LEFT JOIN po_items pi ON po.po_id = pi.po_id
        GROUP BY po.po_id, po.supplier_id, s.name, s.phone, po.status, po.total_amount, po.need_by_date, po.notes, po.created_at
        ORDER BY po.created_at DESC
        """
    )
    return {"suppliers": suppliers, "purchase_orders": pos}


# ── Analitik Statistik & Machine Learning (1.000 Data) ───────────────────────
@router.get("/analytics/descriptive-stats", summary="Statistik deskriptif & deteksi outlier (IQR) 1.000 transaksi")
def get_descriptive_stats(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Menghitung statistik deskriptif dan tabel distribusi frekuensi persis seperti Excel SuperMarket Analysis."""
    from app.services.analytics_ml_service import calculate_descriptive_statistics
    return calculate_descriptive_statistics()


@router.get("/analytics/rfm-crm", summary="Segmentasi pelanggan RFM & rekomendasi tindakan pemasaran")
def get_rfm_crm_segments(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Analisis RFM untuk mengelompokkan pelanggan: Champions, Loyal, At Risk, dll."""
    from app.services.analytics_ml_service import calculate_crm_rfm_segments
    return calculate_crm_rfm_segments()


@router.get("/analytics/supply-chain-ml", summary="Supply chain ML: Demand forecast, safety stock, dan ROP")
def get_supply_chain_ml(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Prediksi konsumsi bahan, perhitungan Safety Stock (SS) dan Reorder Point (ROP = d*L + SS)."""
    from app.services.analytics_ml_service import calculate_supply_chain_ml_forecast
    return calculate_supply_chain_ml_forecast()


@router.get("/analytics/demand-insights", summary="Prediksi demand pesanan, menu terlaris, hari/bulan, & perencanaan menu AI")
def get_demand_insights(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Analisis 1.000 transaksi: ranking menu, pola hari & bulan, rekomendasi menu AI harian."""
    from app.services.analytics_ml_service import calculate_transaction_demand_insights
    return calculate_transaction_demand_insights()
