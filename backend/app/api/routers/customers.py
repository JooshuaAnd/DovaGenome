"""Router pelanggan — profil, Dietary Passport, dan tautan Telegram."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_customer, require_admin
from app.core.domain import ACTIVE_STATUSES
from app.core.errors import PermissionError_
from app.core.logging import get_logger
from app.repositories import customer_repo, order_repo
from app.schemas.customer import (
    CustomerAdminOut,
    CustomerOut,
    CustomerProfilePatch,
    PassportIn,
    PassportOut,
)
from app.schemas.order import SafetyReportOut
from app.services import auth_service, passport_service

log = get_logger("dova.api.customers")

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/me", response_model=CustomerOut, summary="Profil saya")
def me(customer: CustomerOut = Depends(get_current_customer)) -> CustomerOut:
    return customer


@router.patch("/me", response_model=CustomerOut, summary="Perbarui profil saya")
def update_me(
    payload: CustomerProfilePatch,
    customer: CustomerOut = Depends(get_current_customer),
) -> CustomerOut:
    return customer_repo.to_public(
        customer_repo.update_fields(customer.customer_id, {"display_name": payload.display_name})
    )


@router.get("/me/passport", response_model=PassportOut, summary="Dietary Passport saya")
def my_passport(customer: CustomerOut = Depends(get_current_customer)) -> PassportOut:
    return passport_service.get_passport(customer.customer_id)


@router.put("/me/passport", response_model=PassportOut, summary="Simpan Dietary Passport")
def save_my_passport(
    payload: PassportIn, customer: CustomerOut = Depends(get_current_customer)
) -> PassportOut:
    """Partial update — cukup kirim bagian yang ingin diubah."""
    return passport_service.save_passport(customer.customer_id, payload)


@router.get(
    "/me/passport/preview", response_model=SafetyReportOut, summary="Simulasi dampak passport"
)
def preview_passport(customer: CustomerOut = Depends(get_current_customer)) -> SafetyReportOut:
    """
    Laporan kecocokan menu berdasarkan passport saat ini — belum disimpan.

    Dipakai frontend agar pelanggan melihat konsekuensi sebelum menekan
    tombol simpan.
    """
    return passport_service.preview_report(customer)


@router.get("/me/passport/summary", summary="Ringkasan passport")
def passport_summary(customer: CustomerOut = Depends(get_current_customer)) -> dict[str, Any]:
    return passport_service.legacy_snapshot(customer)


@router.post(
    "/me/telegram/code", response_model=CustomerOut, summary="Buat kode tautan Telegram"
)
def new_link_code(customer: CustomerOut = Depends(get_current_customer)) -> CustomerOut:
    """
    Terbitkan kode baru untuk ditautkan ke Telegram.

    Kode lama otomatis tidak berlaku karena hanya satu kode aktif per akun.
    """
    return auth_service.issue_link_code(customer.customer_id)


@router.delete("/me/telegram", response_model=CustomerOut, summary="Lepas tautan Telegram")
def unlink(customer: CustomerOut = Depends(get_current_customer)) -> CustomerOut:
    return auth_service.unlink_telegram(customer.customer_id)


# ── Interaksi Pelanggan (Likes, Cart History, & Rekomendasi ML) ─────────────
from pydantic import BaseModel

class LikeIn(BaseModel):
    menu_id: str
    customer_id: str | None = None

class CartEventIn(BaseModel):
    menu_id: str
    quantity: int = 1
    action: str = "add"  # 'add', 'remove', 'abandon'
    customer_id: str | None = None


@router.post("/likes/toggle", summary="Toggle like/favorite pada menu")
def toggle_like(payload: LikeIn) -> dict[str, Any]:
    """Menyimpan atau membatalkan like pada hidangan."""
    from app.repositories import supabase
    cid = payload.customer_id or "guest_default"
    existing = supabase.execute_one(
        "SELECT id FROM customer_likes WHERE customer_id = %s AND menu_id = %s",
        (cid, payload.menu_id)
    )
    if existing:
        supabase.execute_write(
            "DELETE FROM customer_likes WHERE id = %s",
            (existing["id"],)
        )
        return {"liked": False, "menu_id": payload.menu_id}
    else:
        supabase.execute_write(
            "INSERT INTO customer_likes (customer_id, menu_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (cid, payload.menu_id)
        )
        return {"liked": True, "menu_id": payload.menu_id}


@router.get("/likes", summary="Daftar menu yang disukai")
def list_likes(customer_id: str = "guest_default") -> list[str]:
    """Mengambil ID menu yang disukai pelanggan."""
    from app.repositories import supabase
    rows = supabase.execute(
        "SELECT menu_id FROM customer_likes WHERE customer_id = %s",
        (customer_id,)
    )
    return [r["menu_id"] for r in rows]


@router.post("/cart-event", summary="Catat riwayat interaksi keranjang")
def track_cart_event(payload: CartEventIn) -> dict[str, Any]:
    """Mencatat aktivitas keranjang (add, remove, abandon) untuk Machine Learning."""
    from app.repositories import supabase
    cid = payload.customer_id or "guest_default"
    supabase.execute_write(
        "INSERT INTO cart_history (customer_id, menu_id, quantity, action) VALUES (%s, %s, %s, %s)",
        (cid, payload.menu_id, payload.quantity, payload.action)
    )
    return {"status": "recorded", "action": payload.action, "menu_id": payload.menu_id}


@router.get("/recommendations", summary="Rekomendasi Presisi Multi-Faktor (ML)")
def get_recommendations(customer_id: str = "cust_ml_001") -> list[dict[str, Any]]:
    """
    Rekomendasi presisi multi-faktor menggabungkan:
    1. Filter Keamanan Diet & Alergi
    2. Riwayat Transaksi Sebelumnya
    3. Riwayat Keranjang (Cart History)
    4. Likes / Favorit Makanan
    """
    from app.services.analytics_ml_service import get_personalized_recommendations
    return get_personalized_recommendations(customer_id)


@router.get("/rfm", summary="Status Segmentasi RFM Pelanggan (ML)")
def get_customer_rfm(
    customer_id: str | None = Query(default=None),
    customer: CustomerOut = Depends(get_current_customer),
) -> dict[str, Any]:
    """RFM hanya untuk customer yang sedang login; tidak ada default Champions."""
    if customer_id and customer_id != customer.customer_id:
        raise PermissionError_("RFM hanya boleh dilihat oleh customer yang sedang login.")
    from app.services.rfm_service import get_customer_rfm as get_live_customer_rfm
    return get_live_customer_rfm(customer.customer_id)


@router.get(
    "/{customer_id}", response_model=CustomerAdminOut, summary="Detail pelanggan (admin)"
)
def detail(
    customer_id: str, admin: CustomerOut = Depends(require_admin)
) -> CustomerAdminOut:
    """Ringkasan pelanggan + jumlah order. Hanya admin."""
    doc = customer_repo.get_by_id(customer_id)
    base = customer_repo.to_public(doc)
    orders = order_repo.fetch_orders(customer_id=customer_id, limit=1000)
    return CustomerAdminOut(
        **base.model_dump(),
        order_count=len(orders),
        active_order_count=sum(1 for o in orders if o["status"] in ACTIVE_STATUSES),
        last_order_at=next((o["created_at"] for o in orders if o["created_at"]), None),
        passport=customer_repo.get_passport(customer_id),
    )

