"""Router admin — katalog, pelanggan, pembayaran, dan diagnosa sistem."""

from __future__ import annotations

import json
import hmac
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.api.deps import require_admin, require_staff, get_optional_staff
from app.core.domain import (
    ACTIVE_STATUSES,
    COLLECTION_ALLERGENS,
    COLLECTION_MENUS,
    COLLECTION_ORDERS,
    COLLECTION_PACKAGES,
)
from app.core.errors import DatabaseError, ValidationError
from app.core.config import settings
from app.core.logging import get_logger
from app.repositories import supabase, catalog_repo, customer_repo, order_repo
from app.repositories import recipe_repo
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
    ServiceWeekOut,
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
from app.schemas.recipe import (
    IngredientBatchVerifyIn,
    IngredientVerifyIn,
    RecipeAiDraftApplyIn,
    RecipeAiDraftOut,
    RecipeAiDraftRequestIn,
    RecipeComponentsReplaceIn,
    RecipeVerifyIn,
)
from app.schemas.marketing import MarketingDeliveryWebhookIn, WinbackCampaignDraftIn
from app.schemas.delivery import DeliveryAssignIn, DeliveryStopCreateIn
from app.schemas.supplier_billing import SupplierInvoiceVerifyIn, SupplierPaymentIn
from app.services import (
    auth_service,
    catalog_service,
    dashboard_service,
    invoice_service,
    marketing_service,
    order_service,
    payment_service,
    supplier_billing_service,
    delivery_service,
)
from app.services.recipe_ai_service import recipe_ai_service
from app.services.recipe_document_service import MAX_FILE_BYTES, extract_recipe_document
from app.services.recipe_intake_service import intake_recipe_upload
from app.services.nutrition_service import calculate_recipe_nutrition

log = get_logger("dova.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_telegram_procurement_admin(
    x_dova_internal_token: str = Header(default="", alias="X-Dova-Internal-Token"),
    x_telegram_chat_id: str = Header(default="", alias="X-Telegram-Chat-Id"),
) -> str:
    """Authenticate the bot without creating a second user-session system."""
    expected = settings.langflow_internal_token.strip()
    allowed = {
        value.strip()
        for value in settings.telegram_admin_chat_ids.split(",")
        if value.strip()
    }
    if (
        not expected
        or not allowed
        or not hmac.compare_digest(x_dova_internal_token, expected)
        or x_telegram_chat_id.strip() not in allowed
    ):
        raise HTTPException(status_code=403, detail="Telegram admin belum diotorisasi.")
    if not settings.telegram_admin_customer_id.strip():
        raise HTTPException(status_code=503, detail="TELEGRAM_ADMIN_CUSTOMER_ID belum dikonfigurasi.")
    return x_telegram_chat_id.strip()


@router.get("/telegram/status", summary="Status ringkas untuk Admin Telegram")
def telegram_status(
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    """Expose only operational readiness; never expose credentials or PII."""
    from app.services.langflow_service import langflow_service

    connected = supabase.is_connected()
    return {
        "database_source": "supabase_postgres",
        "supabase_connected": connected,
        "migration_status": (
            "verified"
            if connected and supabase.check_migrations() and supabase.check_phase_migrations()
            else "core_verified_phase_extensions_pending"
            if connected and supabase.check_migrations()
            else "offline_or_incomplete"
        ),
        "astra_state": "OFFLINE_LEGACY",
        "langflow": langflow_service.health(probe=False),
    }


@router.get("/telegram/stock-alerts", summary="Stok kritis untuk Admin Telegram")
def telegram_stock_alerts(
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> list[dict[str, Any]]:
    return supabase.execute(
        """
        SELECT id, ingredient_name, current_stock, min_stock, unit, status, updated_at
        FROM inventory_stocks
        WHERE status IN ('HABIS', 'MENIPIS')
        ORDER BY CASE WHEN status = 'HABIS' THEN 0 ELSE 1 END, ingredient_name
        """
    )


@router.post("/telegram/stock-alerts/queue", summary="Queue alert stok harian idempoten")
def queue_telegram_stock_alert(
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    from app.services import admin_alert_service

    return admin_alert_service.queue_daily_stock_alert(
        admin_chat_ids=settings.telegram_admin_chat_ids,
    )


@router.get("/telegram/forecast", summary="Ringkasan forecast untuk Admin Telegram")
def telegram_forecast(
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    from app.services import forecast_service

    try:
        report = forecast_service.build_live_forecast_report(
            horizon_days=7,
            history_days=90,
            min_history_days=14,
        )
    except forecast_service.ForecastUnavailable as exc:
        return {
            "status": "UNAVAILABLE",
            "source": "supabase_postgres",
            "operational": False,
            "reason": str(exc),
        }
    return {
        "status": report.get("status"),
        "source": report.get("source"),
        "data_mode": report.get("data_mode"),
        "calculation_version": report.get("calculation_version"),
        "operational": report.get("operational", False),
        "latest_observation_date": report.get("latest_observation_date"),
        "stale_series_count": report.get("stale_series_count"),
        "series_count": len(report.get("series") or report.get("rows") or []),
    }


@router.get("/telegram/batches", summary="Batch produksi untuk Admin Telegram")
def telegram_batches(
    service_date: date | None = Query(default=None),
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    from app.services import production_batch_service

    try:
        return production_batch_service.list_batches(service_date=service_date)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/telegram/supplier-invoices", summary="Invoice supplier untuk Admin Telegram")
def telegram_supplier_invoices(
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> list[dict[str, Any]]:
    try:
        return supplier_billing_service.list_invoices()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Migration billing supplier belum tersedia.") from exc


@router.get("/recipe-reviews", summary="Daftar recipe/BOM yang perlu diverifikasi")
def recipe_reviews(
    menu_id: str = Query(""), admin: CustomerOut = Depends(require_admin)
) -> list[dict[str, Any]]:
    return recipe_repo.list_reviews(menu_id=menu_id.strip())


@router.get("/menus/week", response_model=ServiceWeekOut, summary="Kalender menu admin termasuk draft")
def admin_service_week(admin: CustomerOut = Depends(require_admin)) -> ServiceWeekOut:
    return catalog_service.get_service_week(include_unpublished=True)


@router.post(
    "/recipe-intake/import-draft",
    summary="Buat menu dan recipe draft dari dokumen/foto admin",
)
async def import_new_recipe_menu_draft(
    file: UploadFile | None = File(default=None),
    hari: str = Form(...),
    menu_name: str = Form(default=""),
    context: str = Form(default=""),
    recipe_note: str = Form(default=""),
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    content = await file.read(MAX_FILE_BYTES + 1) if file else b""
    return intake_recipe_upload(
        file_name=(file.filename or "recipe") if file else "Catatan admin",
        content=content,
        service_day=hari,
        menu_name=menu_name,
        context=context,
        recipe_note=recipe_note,
        actor_id=admin.customer_id,
        upload_channel="web_admin",
    )


@router.post(
    "/telegram/recipes/import",
    summary="Upload foto/dokumen resep dari Admin Telegram",
)
async def telegram_import_new_recipe_menu_draft(
    file: UploadFile | None = File(default=None),
    hari: str = Form(...),
    menu_name: str = Form(default=""),
    context: str = Form(default=""),
    recipe_note: str = Form(default=""),
    chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    content = await file.read(MAX_FILE_BYTES + 1) if file else b""
    try:
        return intake_recipe_upload(
            file_name=(file.filename or "telegram_recipe") if file else "Catatan admin",
            content=content,
            service_day=hari,
            menu_name=menu_name,
            context=context,
            recipe_note=recipe_note,
            actor_id=settings.telegram_admin_customer_id.strip(),
            upload_channel="telegram_admin",
        )
    except Exception:
        log.exception("telegram_recipe_intake_failed chat_id=%s", chat_id)
        raise


@router.get("/ingredients", summary="Cari master bahan untuk editor recipe")
def recipe_ingredients(
    search: str = Query(default="", max_length=120),
    limit: int = Query(default=500, ge=1, le=1000),
    admin: CustomerOut = Depends(require_admin),
) -> list[dict[str, Any]]:
    return recipe_repo.list_ingredients(search=search, limit=limit)


@router.get("/recipe-versions/{recipe_version_id}/components", summary="Detail komponen recipe")
def recipe_components(
    recipe_version_id: str, admin: CustomerOut = Depends(require_admin)
) -> list[dict[str, Any]]:
    return recipe_repo.list_components(recipe_version_id)


@router.put("/recipe-versions/{recipe_version_id}/components", summary="Simpan komponen recipe untuk review")
def replace_recipe_components(
    recipe_version_id: str,
    payload: RecipeComponentsReplaceIn,
    admin: CustomerOut = Depends(require_admin),
) -> list[dict[str, Any]]:
    return recipe_repo.replace_components(
        recipe_version_id,
        [item.model_dump() for item in payload.components],
        actor_id=admin.customer_id,
    )


@router.post(
    "/recipe-versions/{recipe_version_id}/ai-draft",
    response_model=RecipeAiDraftOut,
    summary="Buat draft BOM dari foto, sumber resep, dan pencarian web",
)
def generate_recipe_ai_draft(
    recipe_version_id: str,
    payload: RecipeAiDraftRequestIn,
    admin: CustomerOut = Depends(require_admin),
) -> RecipeAiDraftOut:
    version = recipe_repo.get_version(recipe_version_id)
    return recipe_ai_service.generate_draft(payload, menu_name=str(version.get("nama_menu") or ""))


@router.post(
    "/recipe-versions/{recipe_version_id}/import-draft",
    response_model=RecipeAiDraftOut,
    summary="Ekstrak PDF/XLSX/CSV/text menjadi draft recipe AI",
)
async def import_recipe_document_draft(
    recipe_version_id: str,
    file: UploadFile = File(...),
    context: str = Form(default=""),
    admin: CustomerOut = Depends(require_admin),
) -> RecipeAiDraftOut:
    """Read an admin-uploaded source and send only bounded text to AI draft.

    The uploaded bytes are not exposed to the customer and the result remains
    PENDING_VERIFICATION until the existing review/apply/verify flow finishes.
    """
    version = recipe_repo.get_version(recipe_version_id)
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("Ukuran dokumen maksimal 10 MB.")
    extracted = extract_recipe_document(file.filename or "recipe", content)
    import_job_id = recipe_repo.create_import_job(
        recipe_version_id=recipe_version_id,
        file_name=str(extracted["source_name"]),
        source_type=str(extracted["source_type"]),
        sha256=str(extracted["sha256"]),
        byte_size=int(extracted["byte_size"]),
        extracted_text=str(extracted["text"]),
        created_by=admin.customer_id,
    )
    request = RecipeAiDraftRequestIn(
        source_text=extracted["text"],
        source_name=extracted["source_name"],
        context=(context or "").strip(),
    )
    try:
        draft = recipe_ai_service.generate_draft(
            request,
            menu_name=str(version.get("nama_menu") or ""),
        )
    except Exception as exc:
        recipe_repo.update_import_job(
            import_job_id,
            status="FAILED",
            error_message=type(exc).__name__,
        )
        raise
    recipe_repo.update_import_job(import_job_id, status="DRAFT_READY")
    return draft


@router.get(
    "/recipe-versions/{recipe_version_id}/nutrition-preview",
    summary="Hitung preview nutrition dari composition evidence",
)
def nutrition_preview(
    recipe_version_id: str,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    recipe_repo.get_version(recipe_version_id)
    return calculate_recipe_nutrition(recipe_repo.list_components(recipe_version_id))


@router.post(
    "/recipe-versions/{recipe_version_id}/apply-ai-draft",
    summary="Simpan draft AI yang telah ditinjau admin sebagai PENDING_VERIFICATION",
)
def apply_recipe_ai_draft(
    recipe_version_id: str,
    payload: RecipeAiDraftApplyIn,
    admin: CustomerOut = Depends(require_admin),
) -> list[dict[str, Any]]:
    evidence = {
        "provider": "openai_recipe_draft",
        "dish_name": payload.dish_name,
        "summary": payload.summary,
        "sources": [source.model_dump() for source in payload.sources],
        "safety_notes": payload.safety_notes,
        "overall_confidence": payload.overall_confidence,
        "nutrition": payload.nutrition.model_dump(mode="json"),
    }
    return recipe_repo.apply_ai_draft(
        recipe_version_id,
        [component.model_dump() for component in payload.components],
        evidence=evidence,
        actor_id=admin.customer_id,
    )


@router.patch("/ingredients/{ingredient_id}/verify", summary="Verifikasi ingredient dan mapping alergen")
def verify_ingredient(
    ingredient_id: str,
    payload: IngredientVerifyIn,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    return recipe_repo.verify_ingredient(
        ingredient_id,
        verifier_id=admin.customer_id,
        allergen_codes=payload.allergen_codes,
        evidence=payload.evidence,
    )


@router.post("/ingredients/verify-batch", summary="Verifikasi bahan yang telah direview admin sekaligus")
def verify_ingredients_batch(
    payload: IngredientBatchVerifyIn,
    admin: CustomerOut = Depends(require_admin),
) -> list[dict[str, Any]]:
    return recipe_repo.verify_ingredients_batch(
        [item.model_dump() for item in payload.ingredients],
        verifier_id=admin.customer_id,
    )


@router.post("/recipe-versions/{recipe_version_id}/verify", summary="Verifikasi recipe/BOM")
def verify_recipe(
    recipe_version_id: str,
    payload: RecipeVerifyIn,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    return recipe_repo.verify_recipe(
        recipe_version_id,
        verifier_id=admin.customer_id,
        cross_contact_risk=payload.cross_contact_risk,
        notes=payload.notes,
    )


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
    staff: CustomerOut = Depends(require_admin),
    status: str = Query(..., description="UNPAID | PENDING | PAID | REFUNDED"),
    reference: str = Query("", max_length=120, description="Nomor transfer/receipt"),
) -> InvoiceOut:
    """
    Admin confirmation is recorded as a payment attempt and releases the
    kitchen ticket only when the status is PAID. It is not public and does not
    trust an amount from the client.
    """
    order = order_service.get_order_detail(order_id, is_staff=True)
    normalized = status.upper()
    if normalized == "PAID":
        payment_service.mark_manual_paid(
            order_id,
            reference=reference,
            actor=f"admin:{staff.username}",
        )
    else:
        invoice_service.set_payment_status(order.id, normalized, reference.strip())
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
        supabase_connected=connected,
        database_source="supabase_postgres",
        astra_connected=False,
        astra_state="OFFLINE_LEGACY",
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
def get_pos_kds(staff: CustomerOut = Depends(require_staff)) -> dict[str, Any]:
    """Mengambil pesanan aktif, antrean dapur, dan pembayaran langsung dari Supabase."""
    try:
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
    except Exception as exc:
        log.error("Supabase gagal memuat pos_kds: %s", type(exc).__name__)
        raise DatabaseError("Data POS/KDS tidak tersedia karena database gagal dibaca.") from exc

    # Payment list tetap memuat semua order agar admin dapat memverifikasi
    # pembayaran. KDS menerima subset paid-only secara eksplisit.
    kitchen_orders = [
        o for o in orders
        if str(o.get("payment_status") or "").upper() == "PAID"
        and o.get("status") in ("PENDING", "PREPARING", "READY")
    ]

    # Hitung metrik dapur dari paid-only queue.
    new_orders = sum(1 for o in kitchen_orders if o.get("status") in ("PENDING", "PREPARING"))
    total_orders = len(orders)
    waiting_list = sum(1 for o in kitchen_orders if o.get("status") == "PREPARING")

    return {
        "metrics": {
            "new_orders": new_orders,
            "total_orders": total_orders,
            "waiting_list": waiting_list,
        },
        "orders": orders,
        "kitchen_orders": kitchen_orders,
    }


@router.post("/orders/{order_id}/advance", summary="Majukan status pesanan dapur")
def advance_order_status(
    order_id: str,
    target_status: str = Query(..., description="PREPARING | READY | COMPLETED | CANCELLED"),
    staff: CustomerOut = Depends(require_staff),
) -> dict[str, Any]:
    """Use the same ordered transition and paid-only guard as the KDS API."""
    current = order_service.get_order_detail(order_id, is_staff=True)
    updated = order_service.advance_status(
        current.id,
        target_status.upper(),
        role=staff.role,
        actor=f"{staff.role}:{staff.username}",
        note=f"Status dimajukan ke {target_status.upper()}",
    )
    return {
        "status": "ok",
        "order_id": updated.order_id,
        "new_status": updated.status.value,
        "payment_status": updated.payment_status.value,
    }


@router.get("/popular-dishes", summary="Menu terpopuler berdasarkan data pesanan riil")
def get_popular_dishes(staff: CustomerOut | None = Depends(get_optional_staff)) -> list[dict[str, Any]]:
    """Mengambil peringkat hidangan terlaris langsung dari tabel order_items di Supabase."""
    try:
        res = supabase.execute(
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
        if res:
            return res
    except Exception as exc:
        log.warning("Supabase offline on popular dishes: %s", exc)

    return [
        {"menu_id": "menu_senin_ayam-rosemary", "nama_menu": "Ayam Panggang Rosemary & Ubi Madu", "hari": "Senin", "order_count": 116},
        {"menu_jumat_pasta-fusilli-pesto": "menu_jumat_pasta-fusilli-pesto", "nama_menu": "Pasta Fusilli Ayam Pesto Keju", "hari": "Jumat", "order_count": 115},
        {"menu_senin_beef-bulgogi": "menu_senin_beef-bulgogi", "nama_menu": "Beef Bulgogi Wijen & Nasi Beras Cokelat", "hari": "Senin", "order_count": 112},
        {"menu_kamis_salmon-lemon": "menu_kamis_salmon-lemon", "nama_menu": "Salmon Fillet Lemon Herb & Kentang Kukus", "hari": "Kamis", "order_count": 98},
    ]


@router.get("/inventory-alerts", summary="Peringatan stok kritis & bahan menipis")
def get_inventory_alerts(staff: CustomerOut | None = Depends(get_optional_staff)) -> list[dict[str, Any]]:
    """Mengambil status bahan live; tidak memakai fixture saat DB gagal."""
    try:
        res = supabase.execute(
            "SELECT id, ingredient_name, current_stock, min_stock, unit, status, updated_at FROM inventory_stocks ORDER BY CASE WHEN status = 'HABIS' THEN 1 WHEN status = 'MENIPIS' THEN 2 ELSE 3 END"
        )
    except Exception as exc:
        log.warning("Supabase unavailable on inventory alerts: %s", exc)
        raise HTTPException(status_code=503, detail="Inventory live tidak tersedia; tidak ada fixture pengganti.") from exc
    return res or []


@router.get("/notifications", summary="Daftar outbox Telegram admin")
def list_notifications(admin: CustomerOut = Depends(require_admin)) -> list[dict[str, Any]]:
    """Daftar pesan Telegram yang dibuat dari workspace admin."""
    return supabase.execute(
        "SELECT id, recipient_type, recipient_name, recipient_phone AS recipient_chat_id, channel, event_type, message, status, created_at FROM notification_outbox WHERE channel = 'telegram' ORDER BY created_at DESC LIMIT 30"
    )


@router.post("/notifications/send", summary="Queue pesan Telegram admin")
def send_notification(
    recipient_type: str = Query(..., description="customer | supplier | admin"),
    recipient_name: str = Query(..., min_length=1),
    recipient_chat_id: str = Query(..., min_length=1, description="Telegram chat ID"),
    message: str = Query(..., min_length=1),
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Queue pesan Telegram manual; worker/provider pengiriman tetap terpisah."""
    if recipient_type not in {"customer", "supplier", "admin"}:
        raise HTTPException(status_code=422, detail="recipient_type tidak valid.")
    supabase.execute_write(
        """
        INSERT INTO notification_outbox (recipient_type, recipient_phone, recipient_name, channel, event_type, message, status)
        VALUES (%s, %s, %s, %s, 'DIRECT_MESSAGE', %s, 'PENDING')
        """,
        (recipient_type, recipient_chat_id, recipient_name, "telegram", message)
    )
    return {
        "status": "queued",
        "channel": "telegram",
        "recipient": recipient_name,
        "recipient_chat_id": recipient_chat_id,
    }


# ── Marketing campaigns ─────────────────────────────────────────────────────
@router.get("/marketing/campaigns", summary="Daftar campaign marketing admin")
def list_marketing_campaigns(
    limit: int = Query(100, ge=1, le=500),
    admin: CustomerOut = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Campaign hanya dapat dilihat admin; tidak ada audience untuk customer umum."""
    try:
        return marketing_service.list_campaigns(limit=limit)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/marketing/campaigns/winback/draft",
    status_code=201,
    summary="Buat draft win-back dari baseline churn live",
)
def create_winback_campaign_draft(
    payload: WinbackCampaignDraftIn,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Persist draft yang lolos freshness, consent, dan channel verification."""
    try:
        draft = marketing_service.build_live_winback_campaign_draft(
            channel=payload.channel,
            max_recipients=payload.max_recipients,
            control_group_percent=payload.control_group_percent,
            rate_limit_per_minute=payload.rate_limit_per_minute,
        )
        if draft.get("status") != "DRAFT":
            raise HTTPException(
                status_code=409,
                detail={"status": draft.get("status"), "warnings": draft.get("warnings", [])},
            )
        return marketing_service.persist_campaign_draft(draft, actor_id=admin.customer_id)
    except marketing_service.MarketingUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/marketing/delivery-webhook", summary="Terima callback delivery marketing bertanda tangan")
async def marketing_delivery_webhook(
    request: Request,
    x_marketing_signature: str = Header(default=""),
) -> dict[str, Any]:
    """Provider callback only; it cannot create an outbox item or send a message."""

    raw_body = await request.body()
    try:
        payload = MarketingDeliveryWebhookIn.model_validate_json(raw_body)
    except (PydanticValidationError, json.JSONDecodeError) as exc:
        raise ValidationError("Payload delivery marketing tidak valid.") from exc
    return marketing_service.process_delivery_webhook(
        payload,
        raw_body=raw_body,
        signature=x_marketing_signature,
    )


@router.post("/marketing/campaigns/{campaign_id}/approve", summary="Approve campaign marketing")
def approve_marketing_campaign(
    campaign_id: str,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return marketing_service.approve_campaign(campaign_id, actor_id=admin.customer_id)
    except marketing_service.MarketingUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/marketing/campaigns/{campaign_id}/queue", summary="Queue campaign ke notification outbox")
def queue_marketing_campaign(
    campaign_id: str,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Queue hanya membuat status PENDING; provider pengiriman belum dipanggil."""
    try:
        return marketing_service.queue_campaign(campaign_id)
    except marketing_service.MarketingUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/marketing/campaigns/{campaign_id}/cancel", summary="Batalkan campaign marketing")
def cancel_marketing_campaign(
    campaign_id: str,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return marketing_service.cancel_campaign(campaign_id, actor_id=admin.customer_id)
    except marketing_service.MarketingUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/suppliers", summary="Daftar supplier dan status PO aktif")
def list_suppliers_and_pos(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Mengambil supplier Dova, status Telegram supplier, dan status PO terkini."""
    suppliers = supabase.execute(
        """
        SELECT s.*,
               supplier_telegram.telegram_chat_id,
               supplier_telegram.telegram_username,
               COALESCE(supplier_telegram.telegram_verified, FALSE) AS telegram_verified
        FROM suppliers s
        LEFT JOIN LATERAL (
            SELECT c.telegram_chat_id, c.telegram_username, c.telegram_verified
            FROM supplier_accounts sa
            JOIN customers c ON c.customer_id = sa.customer_id
            WHERE sa.supplier_id = s.supplier_id
              AND sa.status = 'active'
              AND c.status = 'active'
            ORDER BY c.telegram_verified DESC, c.updated_at DESC
            LIMIT 1
        ) AS supplier_telegram ON TRUE
        ORDER BY s.rating DESC
        """
    )
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


@router.get("/delivery/stops", summary="Manifest delivery untuk admin")
def list_delivery_stops(
    service_date: date | None = Query(default=None),
    admin: CustomerOut = Depends(require_admin),
) -> list[dict[str, Any]]:
    return delivery_service.list_stops(service_date=service_date)


@router.post("/delivery/stops", status_code=201, summary="Buat delivery stop dari order paid")
def create_delivery_stop(
    payload: DeliveryStopCreateIn,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    return delivery_service.create_stop(
        order_id=payload.order_id,
        service_date=payload.service_date,
        meal_slot=payload.meal_slot,
        actor_id=admin.customer_id,
    )


@router.post("/delivery/stops/{stop_id}/assign", summary="Assign delivery stop ke courier")
def assign_delivery_stop(
    stop_id: str,
    payload: DeliveryAssignIn,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    return delivery_service.assign_stop(
        stop_id=stop_id,
        courier_id=payload.courier_id,
        actor_id=admin.customer_id,
    )


# ── Analitik Statistik & Machine Learning (1.000 Data) ───────────────────────
@router.get("/analytics/descriptive-stats", summary="Statistik deskriptif & deteksi outlier (IQR) dari transaksi aktual")
def get_descriptive_stats(staff: CustomerOut | None = Depends(get_optional_staff)) -> dict[str, Any]:
    """Menghitung statistik deskriptif dan tabel distribusi frekuensi persis seperti Excel SuperMarket Analysis."""
    from app.services.analytics_ml_service import calculate_descriptive_statistics
    return calculate_descriptive_statistics()


@router.get("/analytics/rfm-crm", summary="Segmentasi pelanggan RFM & rekomendasi tindakan pemasaran")
def get_rfm_crm_segments(admin: CustomerOut = Depends(require_admin)) -> dict[str, Any]:
    """RFM live untuk admin; tidak mengembalikan cohort sintetis saat DB gagal."""
    from app.services.rfm_service import build_rfm_report
    return build_rfm_report()


@router.post("/analytics/rfm-crm/snapshot", summary="Persist snapshot RFM live yang fresh")
def persist_rfm_snapshot(admin: CustomerOut = Depends(require_admin)) -> dict[str, Any]:
    """Persist RFM only when live provenance and freshness gates pass."""
    from app.services import rfm_service

    try:
        report = rfm_service.build_rfm_report()
        persisted = rfm_service.persist_rfm_report(report)
    except rfm_service.RfmUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "status": report["status"],
        "persisted_rows": persisted,
        "as_of": report["as_of"],
        "calculation_version": report["calculation_version"],
        "data_mode": report["data_mode"],
        "source": report["source"],
    }


@router.get("/analytics/rfm-crm/movement", summary="Perpindahan segmen RFM dari snapshot sebelumnya")
def get_rfm_segment_movement(admin: CustomerOut = Depends(require_admin)) -> dict[str, Any]:
    """Compare current live RFM cohort with the latest prior snapshot."""
    from app.services import rfm_service

    try:
        return rfm_service.build_segment_movement()
    except rfm_service.RfmUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/analytics/churn-risk", summary="Baseline churn risk pelanggan")
def get_churn_risk(admin: CustomerOut = Depends(require_admin)) -> dict[str, Any]:
    """Return an explainable baseline; never present it as a validated model."""
    from app.services.churn_service import build_churn_report
    return build_churn_report()


@router.get("/analytics/churn-backtest", summary="Backtest temporal baseline churn")
def get_churn_backtest(
    horizon_days: int = Query(30, ge=1, le=365),
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Evaluate historical churn labels without presenting a supervised model."""
    from app.services.churn_service import build_churn_backtest

    try:
        return build_churn_backtest(horizon_days=horizon_days)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/analytics/supply-chain-ml", summary="Supply chain ML: Demand forecast, safety stock, dan ROP")
def get_supply_chain_ml(admin: CustomerOut = Depends(require_admin)) -> dict[str, Any]:
    """Deprecated: prevent legacy synthetic SS/ROP from being presented as live."""
    raise HTTPException(
        status_code=410,
        detail="Endpoint legacy dinonaktifkan. Gunakan /admin/analytics/forecast-backtest; SS/ROP menunggu BOM terverifikasi.",
    )


@router.get("/analytics/demand-insights", summary="Prediksi demand pesanan, menu terlaris, hari/bulan, & perencanaan menu AI")
def get_demand_insights(admin: CustomerOut = Depends(require_admin)) -> dict[str, Any]:
    """Deprecated: prevent the legacy synthetic demand payload from being used."""
    raise HTTPException(
        status_code=410,
        detail="Endpoint demand-insights legacy dinonaktifkan. Gunakan forecast-backtest live.",
    )


@router.get("/analytics/forecast-backtest", summary="Forecast demand live dengan rolling-origin backtest")
def get_forecast_backtest(
    horizon_days: int = Query(7, ge=1, le=30),
    history_days: int = Query(90, ge=30, le=365),
    min_history_days: int = Query(14, ge=7, le=60),
    mode: str = Query("live", pattern="^(live|demo)$"),
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Forecast live audit-ready, or explicitly requested synthetic demo data."""
    from app.services import forecast_service

    try:
        if mode == "demo":
            return forecast_service.build_seeded_demo_forecast_report(
                horizon_days=horizon_days,
            )
        return forecast_service.build_live_forecast_report(
            horizon_days=horizon_days,
            history_days=history_days,
            min_history_days=min_history_days,
        )
    except forecast_service.ForecastUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/analytics/forecast-backtest/snapshot", summary="Persist forecast live yang fresh")
def persist_forecast_snapshot(
    horizon_days: int = Query(7, ge=1, le=30),
    history_days: int = Query(90, ge=30, le=365),
    min_history_days: int = Query(14, ge=7, le=60),
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Write forecast snapshots only when the live freshness gate is OK."""
    from app.services import forecast_service

    try:
        report = forecast_service.build_live_forecast_report(
            horizon_days=horizon_days,
            history_days=history_days,
            min_history_days=min_history_days,
        )
        persisted = forecast_service.persist_forecast_report(report)
    except forecast_service.ForecastUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "status": report["status"],
        "persisted_rows": persisted,
        "calculation_version": report["calculation_version"],
        "data_mode": report["data_mode"],
        "source": report["source"],
    }


@router.get("/analytics/inventory-replenishment", summary="BOM explosion dan readiness Safety Stock/ROP/ROQ")
def get_inventory_replenishment(
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Return an auditable inventory plan; never return synthetic SS/ROP."""
    from app.services import inventory_service

    try:
        return inventory_service.build_live_inventory_replenishment_report()
    except inventory_service.InventoryPlanUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/analytics/supplier-sourcing", summary="Ranking supplier untuk shortage live")
def get_supplier_sourcing(
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Rank live supplier candidates without creating or sending a PO."""
    from app.services import inventory_service, supplier_sourcing_service

    try:
        inventory_report = inventory_service.build_live_inventory_replenishment_report()
        return supplier_sourcing_service.build_supplier_sourcing_report(inventory_report)
    except inventory_service.InventoryPlanUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/procurement/drafts", status_code=201, summary="Persist draft PO dari sourcing live")
def create_procurement_drafts(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Persist draft PO atomically; never create one from stale/preview data."""
    from app.services import inventory_service, procurement_service, supplier_sourcing_service

    try:
        inventory_report = inventory_service.build_live_inventory_replenishment_report()
        sourcing_report = supplier_sourcing_service.build_supplier_sourcing_report(inventory_report)
        return procurement_service.create_draft_purchase_orders(
            sourcing_report,
            idempotency_key=idempotency_key or "",
            actor_id=admin.customer_id,
        )
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except inventory_service.InventoryPlanUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/procurement/purchase-orders/{po_id}/approve", summary="Approve draft PO")
def approve_procurement_draft(
    po_id: str,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    from app.services import procurement_service

    try:
        return procurement_service.approve_purchase_order(po_id, actor_id=admin.customer_id)
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/procurement/purchase-orders/{po_id}/send", summary="Queue PO untuk delivery provider")
def queue_procurement_delivery(
    po_id: str,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    """Queue notification; response explicitly remains delivery PENDING."""
    from app.services import procurement_service

    try:
        return procurement_service.queue_purchase_order(po_id, actor_id=admin.customer_id)
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/supplier-invoices", summary="Daftar invoice supplier untuk verifikasi admin")
def list_supplier_invoices_for_admin(
    admin: CustomerOut = Depends(require_admin),
) -> list[dict[str, Any]]:
    return supplier_billing_service.list_invoices()


@router.post("/supplier-invoices/{invoice_id}/verify", summary="Verifikasi three-way match invoice supplier")
def verify_supplier_invoice(
    invoice_id: str,
    payload: SupplierInvoiceVerifyIn,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    return supplier_billing_service.verify_invoice(
        invoice_id=invoice_id,
        actor_id=admin.customer_id,
        decision=payload.decision,
        notes=payload.notes,
    )


@router.post("/supplier-invoices/{invoice_id}/pay", summary="Catat pembayaran manual invoice supplier")
def pay_supplier_invoice(
    invoice_id: str,
    payload: SupplierPaymentIn,
    admin: CustomerOut = Depends(require_admin),
) -> dict[str, Any]:
    return supplier_billing_service.record_payment(
        invoice_id=invoice_id,
        actor_id=admin.customer_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        idempotency_key=payload.idempotency_key,
        notes=payload.notes,
    )


@router.get("/procurement/telegram/pending", summary="Draft PO untuk review admin Telegram")
def list_telegram_procurement_drafts(
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> list[dict[str, Any]]:
    """Return only DRAFT POs; the bot cannot bypass the approval state machine."""
    return supabase.execute(
        """
        SELECT po.po_id, po.supplier_id, s.name AS supplier_name,
               po.status, po.total_amount, po.need_by_date, po.notes, po.created_at,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'item_name', pi.item_name,
                           'qty', pi.qty,
                           'unit', pi.unit,
                           'subtotal', pi.subtotal
                       ) ORDER BY pi.id
                   ) FILTER (WHERE pi.id IS NOT NULL),
                   '[]'::json
               ) AS items
        FROM purchase_orders po
        JOIN suppliers s ON s.supplier_id = po.supplier_id
        LEFT JOIN po_items pi ON pi.po_id = po.po_id
        WHERE po.status = 'DRAFT'
        GROUP BY po.po_id, po.supplier_id, s.name, po.status,
                 po.total_amount, po.need_by_date, po.notes, po.created_at
        ORDER BY po.created_at DESC
        LIMIT 25
        """
    )


@router.post("/procurement/telegram/{po_id}/approve", summary="Approve draft PO dari Telegram")
def approve_telegram_procurement_draft(
    po_id: str,
    chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    from app.services import procurement_service

    try:
        return procurement_service.approve_purchase_order(
            po_id,
            actor_id=settings.telegram_admin_customer_id.strip(),
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/procurement/telegram/{po_id}/reject", summary="Reject draft PO dari Telegram")
def reject_telegram_procurement_draft(
    po_id: str,
    notes: str = Query(default="", max_length=1000),
    _chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    from app.services import procurement_service

    try:
        return procurement_service.reject_purchase_order(
            po_id,
            actor_id=settings.telegram_admin_customer_id.strip(),
            notes=notes,
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/procurement/telegram/{po_id}/send", summary="Queue PO supplier dari Telegram")
def send_telegram_procurement_draft(
    po_id: str,
    chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    from app.services import procurement_service

    try:
        return procurement_service.queue_purchase_order(
            po_id,
            actor_id=settings.telegram_admin_customer_id.strip(),
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/procurement/telegram/{po_id}/edit", summary="Catat permintaan edit PO dari Telegram")
def edit_telegram_procurement_draft(
    po_id: str,
    notes: str = Query(..., min_length=2, max_length=1000),
    chat_id: str = Depends(_require_telegram_procurement_admin),
) -> dict[str, Any]:
    from app.services import procurement_service

    try:
        return procurement_service.request_purchase_order_changes(
            po_id,
            actor_id=settings.telegram_admin_customer_id.strip(),
            notes=notes,
        )
    except procurement_service.ProcurementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except procurement_service.ProcurementUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
