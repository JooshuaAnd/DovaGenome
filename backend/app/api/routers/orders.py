"""Router pesanan — siklus hidup order dari sudut pandang pelanggan."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_customer, get_verified_customer
from app.core.logging import get_logger
from app.schemas.customer import CustomerOut
from app.schemas.order import (
    InvoiceOut,
    OrderCreateIn,
    OrderDetailOut,
    OrderOut,
    OrderUpdateIn,
)
from app.services import order_service

log = get_logger("dova.api.orders")

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut], summary="Pesanan saya")
def my_orders(
    customer: CustomerOut = Depends(get_current_customer),
    limit: int = Query(50, ge=1, le=200),
) -> list[OrderOut]:
    """
    Hanya pesanan milik pemanggil.

    Order lama yang belum punya `customer_id` dicocokkan lewat `chat_id`
    Telegram, jadi pelanggan lama tetap melihat riwayatnya.
    """
    return order_service.list_orders(customer, limit=limit)


@router.post(
    "",
    response_model=OrderDetailOut,
    status_code=201,
    summary="Buat pesanan",
)
def create_order(
    payload: OrderCreateIn, customer: CustomerOut = Depends(get_verified_customer)
) -> OrderDetailOut:
    """
    Buat pesanan + tiket dapur.

    Ditolak bila allergen kritis bertabrakan dengan menu, atau jadwal di luar
    hari paket. Pesan penolakan selalu berupa bahasa manusia, bukan kode error.
    """
    return order_service.create_order(customer, payload)


@router.get("/{order_id}", response_model=OrderDetailOut, summary="Detail pesanan")
def get_order(
    order_id: str, customer: CustomerOut = Depends(get_current_customer)
) -> OrderDetailOut:
    return order_service.get_order_detail(order_id, customer=customer)


@router.patch("/{order_id}", response_model=OrderDetailOut, summary="Ubah pesanan")
def update_order(
    order_id: str,
    payload: OrderUpdateIn,
    customer: CustomerOut = Depends(get_current_customer),
) -> OrderDetailOut:
    """Hanya bisa diubah selama masih `PENDING`."""
    return order_service.update_order(order_id, customer, payload)


@router.get("/{order_id}/timeline", summary="Riwayat status pesanan")
def timeline(
    order_id: str, customer: CustomerOut = Depends(get_current_customer)
) -> list[dict]:
    order_service.get_order_detail(order_id, customer=customer)
    return order_service.timeline(order_id)


@router.get("/{order_id}/invoice", response_model=InvoiceOut, summary="Invoice pesanan")
def invoice(
    order_id: str, customer: CustomerOut = Depends(get_current_customer)
) -> InvoiceOut:
    """
    Invoice dihitung dari nilai yang tersimpan pada pesanan.

    Harga tidak pernah berasal dari input pelanggan.
    """
    return order_service.get_invoice(order_id, customer)