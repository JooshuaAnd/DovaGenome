"""Router pelanggan — profil, Dietary Passport, dan tautan Telegram."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_customer, require_admin
from app.core.domain import ACTIVE_STATUSES
from app.core.logging import get_logger
from app.repositories import customer_repo, order_repo
from app.schemas.customer import (
    CustomerAdminOut,
    CustomerOut,
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