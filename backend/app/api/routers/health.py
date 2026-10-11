"""Router health & diagnosa — Supabase."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories import supabase
from app.schemas.common import HealthPayload
from app.services.langflow_service import langflow_service

log = get_logger("dova.api.health")

router = APIRouter(tags=["health"])

# Tabel yang ditampilkan di health check (subset dari MANAGED_TABLES)
_HEALTH_TABLES = (
    "packages",
    "allergens",
    "menus",
    "customers",
    "orders",
)


@router.get("/health", response_model=HealthPayload, summary="Status aplikasi")
def health() -> HealthPayload:
    connected = supabase.is_connected()
    counts: dict[str, Any] = {}
    if connected:
        for name in _HEALTH_TABLES:
            counts[name] = supabase.count_rows(name)
    return HealthPayload(
        status="ok" if connected else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        demo_mode=settings.demo_mode,
        db_connected=connected,
        tables=counts,
        credentials=settings.credential_status() if settings.debug else {},
        telegram_bot_username=settings.telegram_bot_username,
    )


@router.get("/health/langflow", summary="Status Langflow")
def langflow_health() -> dict[str, Any]:
    """Diagnostik AI terpisah. Tidak mengembalikan API key."""
    return langflow_service.health()


@router.get("/health/config", summary="Ringkasan konfigurasi")
def config_summary() -> dict[str, Any]:
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "api_prefix": settings.api_prefix,
        "demo_mode": settings.demo_mode,
        "allow_passwordless_login": settings.allow_passwordless_login,
        "jwt_expire_minutes": settings.jwt_expire_minutes,
        "telegram_link_code_ttl_minutes": settings.telegram_link_code_ttl_minutes,
        "catalog_cache_ttl_seconds": settings.catalog_cache_ttl_seconds,
        "langflow_run_url_configured": bool(settings.langflow_run_url),
        "credentials": settings.credential_status(),
        "telegram_deep_link_base": settings.telegram_link(),
    }
