"""Daftar router yang dipasang di `app.main`.

Urutan penting: `health` dulu (supaya load balancer bisa memeriksa tanpa auth),
lalu auth/catalog (publik), baru customers/orders, lalu kitchen/admin (staff),
terakhir ai.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routers import admin, ai, auth, catalog, customers, health, kitchen, orders

#: Router publik + privat digabung di satu prefix agar URL konsisten.
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(customers.router)
api_router.include_router(orders.router)
api_router.include_router(kitchen.router)
api_router.include_router(admin.router)
api_router.include_router(ai.router)

__all__ = ["api_router"]