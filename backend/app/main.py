"""Aplikasi FastAPI DovaGenome AI.

Titik masuk tunggal backend. Tanggung jawab file ini hanya:
  * konfigurasi middleware (CORS, security headers),
  * lifecycle (koneksi Astra, cache, cleanup),
  * pemasangan router,
  * pemetaan error domain → JSON yang konsisten.

Semua aturan bisnis berada di `app.services`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import api_router
from app.core.config import settings
from app.core.errors import AppError, TooManyRequestsError
from app.core.logging import configure_logging, get_logger
from app.repositories import astra, catalog_repo
from app.services.langflow_service import langflow_service as ai_client

configure_logging()
log = get_logger("dova.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Startup & shutdown.

    Koneksi Astra dibuat lebih awal supaya kegagalan credential terlihat di
    log server, bukan muncul sporadik sebagai 500 saat user sedang memesan.
    """
    log.info(
        "startup app=%s env=%s demo_mode=%s",
        settings.app_name, settings.environment, settings.demo_mode,
    )

    connected = astra.is_connected()
    if connected:
        created = astra.ensure_collections()
        log.info(
            "astra_connected collections_ready=%d created=%s",
            len(astra.MANAGED_COLLECTIONS), created or "-",
        )
    else:
        log.error(
            "astra_unreachable — KDS & admin TIDAK akan menampilkan data contoh. "
            "Periksa ASTRA_DB_API_ENDPOINT & ASTRA_DB_APPLICATION_TOKEN."
        )

    if settings.demo_mode:
        log.warning("DEMO_MODE aktif — pastikan ini tidak dipakai di produksi.")

    try:
        yield
    finally:
        catalog_repo.invalidate_cache()
        ai_client.close()
        astra.reset_connection()
        log.info("shutdown selesai")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend DovaGenome AI: katalog, pesanan, dapur, Dietary Passport, "
        "invoice, dan integrasi Langflow."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    """Header dasar. CSP ketat ditambahkan di Phase 3 saat ada frontend statis."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


# ── Error handling ──────────────────────────────────────────────────────────
@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """
    Error domain → JSON konsisten.

    Pesan aman untuk ditampilkan ke user; detail internal tetap di log server.
    """
    if exc.status_code >= 500:
        log.error(
            "app_error path=%s code=%s detail=%s",
            request.url.path, exc.code, exc.details,
        )
    else:
        log.info("app_error path=%s code=%s", request.url.path, exc.code)

    headers: dict[str, str] = {}
    if isinstance(exc, TooManyRequestsError):
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.to_payload()},
        headers=headers or None,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic 422 → bentuk yang sama dengan error domain."""
    fields = [
        {
            "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    log.info("validation_error path=%s fields=%d", request.url.path, len(fields))
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Data yang dikirim belum lengkap atau tidak valid.",
                "details": {"fields": fields},
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    """
    Jaring pengaman terakhir.

    Detail exception TIDAK pernah dikirim ke client — bisa memuat path server,
    nama collection, atau potongan credential.
    """
    logging.getLogger("dova.unhandled").exception(
        "unhandled_error path=%s", request.url.path, exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Terjadi kesalahan di sisi kami. Tim sudah diberi tahu.",
                "details": {},
            }
        },
    )


# ── Router ──────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Root ringkas supaya developer tidak salah mengira server mati."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_prefix,
    }