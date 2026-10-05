"""Hierarchy error aplikasi → pemetaan HTTP.

Menggantikan pola `except Exception: pass` di `data.py` (legacy).
Tidak ada error domain yang sampai ke client sebagai traceback atau credential.
"""

from __future__ import annotations

import logging

log = logging.getLogger("dova.errors")


class AppError(Exception):
    """Dasar untuk semua error yang aman untuk ditampilkan ke user."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PermissionError_(AppError):
    status_code = 403
    code = "forbidden"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class TooManyRequestsError(AppError):
    """429 dengan `Retry-After` supaya client tahu kapan boleh mencoba lagi."""

    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str, *, retry_after: int = 60, details: dict | None = None) -> None:
        super().__init__(message, details=details)
        self.retry_after = retry_after


class DatabaseError(AppError):
    status_code = 503
    code = "database_unavailable"


class AIError(AppError):
    status_code = 502
    code = "ai_unavailable"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"
