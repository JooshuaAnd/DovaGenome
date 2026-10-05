"""Dependency FastAPI — auth, role, dan akses koleksi.

Pola yang dipakai:
  * `get_current_customer`  → customer terautentikasi (JWT valid).
  * `get_verified_customer` → customer yang Telegram-nya sudah tertaut.
  * `require_roles(...)`    → gerbang role untuk admin/kitchen.

Router TIDAK boleh membaca body request atau database secara langsung untuk
menentukan hak akses; semuanya lewat sini supaya tidak ada celah yang terlewat.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AuthError, PermissionError_
from app.core.logging import get_logger
from app.models.enums import Role
from app.schemas.customer import CustomerOut
from app.services import auth_service

log = get_logger("dova.api.deps")

#: auto_error=False supaya token yang tidak ada tidak jadi 403 sendirian —
#: kita ingin 401 dengan pesan yang bisa langsung ditampilkan ke user.
_bearer = HTTPBearer(auto_error=False)


def get_current_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CustomerOut:
    if not credentials or not credentials.credentials:
        raise AuthError("Silakan masuk terlebih dahulu.")
    payload = auth_service.decode_token(credentials.credentials)
    return auth_service.customer_from_token_payload(payload)


def get_verified_customer(customer: CustomerOut = Depends(get_current_customer)) -> CustomerOut:
    """Untuk operasi yang butuh kepastian channel (mis. membuat pesanan)."""
    auth_service.require_telegram_verified(customer)
    return customer


def require_roles(*roles: Role) -> Callable[[CustomerOut], CustomerOut]:
    """Dependency factory: `Depends(require_roles(Role.ADMIN, Role.KITCHEN))`."""
    allowed = {r.value for r in roles}
    wanted = {r.value for r in roles}

    def _dependency(customer: CustomerOut = Depends(get_current_customer)) -> CustomerOut:
        if customer.role not in allowed:
            log.warning(
                "Akses ditolak user=%s role=%s butuh=%s",
                customer.username, customer.role, sorted(wanted),
            )
            raise PermissionError_("Kamu tidak punya akses ke bagian ini.")
        return customer

    return _dependency


#: Shortcut yang sering dipakai router.
require_admin = require_roles(Role.ADMIN)
require_staff = require_roles(Role.ADMIN, Role.KITCHEN)


def get_optional_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CustomerOut | None:
    """
    Auth opsional untuk pelanggan mana pun (bukan hanya staff).

    Dipakai endpoint publik yang menjadi lebih berguna bila pelanggan sudah masuk
    — `/menu` tetap terbuka untuk pengunjung, tetapi menampilkan status keamanan
    yang sudah memperhitungkan preferensi yang tersimpan.

    Token yang ada tapi rusak tetap ditolak, sama seperti `get_current_customer`:
    diam-diam memperlakukannya sebagai anonim akan menyembunyikan bug sesi.
    """
    if not credentials or not credentials.credentials:
        return None
    payload = auth_service.decode_token(credentials.credentials)
    return auth_service.customer_from_token_payload(payload)


def get_optional_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CustomerOut | None:
    """
    Auth opsional: mengembalikan staff, atau `None` kalau tidak login.

    Dipakai endpoint yang terbuka untuk umum tapi punya perilaku berbeda bila
    pemanggil adalah admin (mis. katalog dengan `include_inactive`). Token
    yang ada tapi rusak tetap ditolak — diam-diam mengabaikannya akan
    menyembunyikan bug konfigurasi dari pemanggil.
    """
    if not credentials or not credentials.credentials:
        return None
    payload = auth_service.decode_token(credentials.credentials)
    customer = auth_service.customer_from_token_payload(payload)
    return customer if customer.role in {Role.ADMIN.value, Role.KITCHEN.value} else None


def client_info(request: Request) -> dict[str, str]:
    """Metadata client untuk log. Tidak pernah menyimpan alamat lengkap."""
    return {
        "ip": request.client.host if request.client else "",
        "agent": (request.headers.get("user-agent") or "")[:120],
    }