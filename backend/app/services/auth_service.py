"""Auth service â€” MVP passwordless berbasis nomor telepon.

Alur pelanggan:
  1. Customer mengisi nama lengkap + nomor telepon (satu form, masuk/daftar).
  2. Nomor telepon = pengenal unik: sudah ada â†’ login, belum ada â†’ akun dibuat.
  3. Backend menerbitkan JWT. Pelanggan langsung bisa memesan di web.

Menautkan Telegram bersifat opsional: bila tertaut, bot mengirim konfirmasi &
pembaruan status; bila tidak, pesanan tetap berjalan.

Admin/kitchen WAJIB memakai password (`password_hash` terisi).

CATATAN KEAMANAN: mode passwordless cocok untuk MVP, bukan produksi. Ia
dibatasi rate-limit di router. Kolom `password_hash` sudah tersedia sehingga
migrasi ke password/OTP tidak memerlukan perubahan schema.
"""

from __future__ import annotations

import datetime
import secrets
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.errors import AuthError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.enums import Role
from app.repositories import customer_repo
from app.repositories.customer_repo import normalize_phone, username_from_phone
from app.schemas.customer import (
    CustomerOut,
    CustomerSignIn,
    LoginIn,
    RegisterIn,
    TelegramLinkIn,
    TelegramLinkOut,
    TokenOut,
)
from app.utils.time import now_iso, now_wib

log = get_logger("dova.auth")

#: Alfabet tanpa karakter ambigu (0/O, 1/I/l) supaya code mudah dibaca & di Diction.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        log.warning("password_hash tidak valid untuk dibandingkan.")
        return False


def generate_link_code() -> str:
    """Code 8 karakter, single-use, berlaku singkat."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


# â”€â”€ Token â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def issue_token(customer_id: str, role: str) -> tuple[str, int]:
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": customer_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Sesi Anda sudah berakhir. Silakan masuk kembali.") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Token tidak valid.") from exc


# â”€â”€ Customer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def register_customer(payload: RegisterIn) -> TokenOut:
    """Daftar tanpa password â€” langsung dapat token, tapi belum bisa memesan."""
    doc = customer_repo.create_customer(
        username=payload.username,
        display_name=payload.display_name or payload.username,
        phone=payload.phone,
        role=Role.CUSTOMER.value,
    )
    customer = customer_repo.to_public(doc)
    code, expires_at = _mint_link_code(customer.customer_id)
    customer = customer.model_copy(
        update={
            "telegram_link_code": code,
            "telegram_deep_link": settings.telegram_link(f"link_{code}"),
        }
    )
    token, expires_in = issue_token(customer.customer_id, customer.role)
    log.info("customer_registered username=%s", customer.username)
    return TokenOut(
        access_token=token, expires_in=expires_in, customer=customer
    )


def sign_in_customer(payload: CustomerSignIn) -> TokenOut:
    """Masuk / daftar pelanggan hanya dengan nama lengkap + nomor telepon.

    Nomor telepon adalah pengenal unik: bila sudah terdaftar → login, bila belum
    → akun pelanggan baru dibuat. Tidak ada kata sandi (MVP), dan pelanggan bisa
    langsung memesan di web tanpa menautkan Telegram.
    """
    phone = normalize_phone(payload.phone)
    if not phone:
        raise ValidationError("Nomor telepon wajib diisi.")

    doc = customer_repo.find_by_phone(phone)
    if doc:
        if str(doc.get("status")) != "active":
            raise AuthError("Akun ini dinonaktifkan. Hubungi admin.")
        if str(doc.get("role") or Role.CUSTOMER.value) != Role.CUSTOMER.value:
            raise AuthError("Nomor ini milik akun staf. Silakan masuk lewat tab staf.")
        customer_id = str(doc.get("customer_id") or doc.get("_id"))
        if payload.display_name and payload.display_name != str(doc.get("display_name") or ""):
            doc = customer_repo.update_fields(customer_id, {"display_name": payload.display_name})
        log.info("customer_signin username=%s", doc.get("username"))
    else:
        doc = customer_repo.create_customer(
            username=username_from_phone(phone),
            display_name=payload.display_name,
            phone=phone,
            role=Role.CUSTOMER.value,
        )
        log.info("customer_registered username=%s", doc.get("username"))

    customer_id = str(doc.get("customer_id") or doc.get("_id"))
    role = str(doc.get("role") or Role.CUSTOMER.value)
    token, expires_in = issue_token(customer_id, role)
    return TokenOut(access_token=token, expires_in=expires_in, customer=customer_repo.to_public(doc))


def login_customer(payload: LoginIn) -> TokenOut:
    """
    Login.

    Akun dengan `password_hash` (admin/kitchen) wajib menyertakan password benar.
    Akun tanpa `password_hash` hanya boleh masuk bila `ALLOW_PASSWORDLESS_LOGIN`
    aktif dan `telegram_verified` sudah true.
    """
    doc = customer_repo.find_by_username(payload.username)
    if not doc:
        # Jangan bocorkan apakah username ada.
        raise AuthError("Username atau kredensial salah.")

    if str(doc.get("status")) != "active":
        raise AuthError("Akun ini dinonaktifkan. Hubungi admin.")

    password_hash = str(doc.get("password_hash") or "")
    if password_hash:
        if not payload.password or not verify_password(payload.password, password_hash):
            log.warning("login_failed username=%s reason=bad_password", payload.username)
            raise AuthError("Username atau kredensial salah.")
    else:
        if not settings.allow_passwordless_login:
            raise AuthError(
                "Login tanpa kata sandi sedang dinonaktifkan. Hubungi admin."
            )
        if not doc.get("telegram_verified"):
            raise ConflictError(
                "Hubungkan Telegram terlebih dahulu untuk mengaktifkan akun Anda.",
                details={"telegram_link_code": str(doc.get("telegram_link_code") or "")},
            )

    customer_id = str(doc.get("customer_id") or doc.get("_id"))
    role = str(doc.get("role") or Role.CUSTOMER.value)
    token, expires_in = issue_token(customer_id, role)
    log.info("login_ok username=%s role=%s", payload.username, role)
    return TokenOut(access_token=token, expires_in=expires_in, customer=customer_repo.to_public(doc))


def _mint_link_code(customer_id: str) -> tuple[str, str]:
    code = generate_link_code()
    expires_at = (
        now_wib() + datetime.timedelta(minutes=settings.telegram_link_code_ttl_minutes)
    ).isoformat()
    customer_repo.set_telegram_link_code(customer_id, code, expires_at)
    return code, expires_at


def issue_link_code(customer_id: str) -> CustomerOut:
    """Buat/segarkan code Linking (dipakai customer & admin)."""
    customer_repo.get_by_id(customer_id)  # pastikan ada
    code, _ = _mint_link_code(customer_id)
    doc = customer_repo.get_by_id(customer_id)
    return customer_repo.to_public(doc).model_copy(
        update={
            "telegram_link_code": code,
            "telegram_deep_link": settings.telegram_link(f"link_{code}"),
        }
    )


def link_telegram(payload: TelegramLinkIn, *, actor: str = "") -> TelegramLinkOut:
    """
    Ditukar bot Telegram setelah user membuka `?start=link_<CODE>`.

    Tidak butuh JWT — pemanggil adalah bot (server-to-server). Code single-use
    dengan TTL pendek. `actor` hanya untuk log audit.
    """
    code = payload.code.strip().upper()
    doc = customer_repo.find_by_link_code(code)
    if not doc:
        log.warning("telegram_link_failed reason=code_not_found")
        raise NotFoundError("Kode Linking tidak dikenal. Minta kode baru di halaman akun.")

    expires_at = str(doc.get("telegram_link_code_expires_at") or "")
    if expires_at:
        from app.utils.time import parse_dt

        exp = parse_dt(expires_at)
        if exp is None or exp < datetime.datetime.now(datetime.timezone.utc):
            customer_repo.clear_telegram_link_code(str(doc.get("customer_id") or doc.get("_id")))
            log.warning("telegram_link_failed reason=expired")
            raise ValidationError("Kode linking sudah kedaluwarsa. Minta kode baru.")

    existing = customer_repo.find_by_telegram_chat_id(payload.chat_id)
    if existing and str(existing.get("customer_id") or existing.get("_id")) != str(
        doc.get("customer_id") or doc.get("_id")
    ):
        raise ConflictError(
            "Akun Telegram ini sudah tertaut ke akun pelanggan lain."
        )

    customer_id = str(doc.get("customer_id") or doc.get("_id"))
    customer_repo.link_telegram(customer_id, payload.chat_id, payload.telegram_username)
    log.info(
        "telegram_linked customer=%s chat_id=%s actor=%s",
        customer_id, payload.chat_id, actor or "unknown",
    )
    return TelegramLinkOut(
        customer_id=customer_id,
        telegram_chat_id=payload.chat_id,
        linked_at=now_iso(),
    )


def customer_from_token_payload(payload: dict[str, Any]) -> CustomerOut:
    """Validasi klaim JWT lalu ambil customer terbaru dari database."""
    subject = str(payload.get("sub") or "")
    if not subject:
        raise AuthError("Token tidak memiliki subjek.")
    doc = customer_repo.get_by_id(subject)
    if str(doc.get("status")) != "active":
        raise AuthError("Akun ini dinonaktifkan.")
    return customer_repo.to_public(doc)


# â”€â”€ Staff (admin / kitchen) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def create_staff(
    *, username: str, password: str, display_name: str, role: str
) -> CustomerOut:
    """Staff WAJIB berpassword. Dipakai script seed atau endpoint admin."""
    if role not in (Role.ADMIN.value, Role.KITCHEN.value):
        raise ValidationError("Role staff harus 'admin' atau 'kitchen'.")
    if len(password) < 8:
        raise ValidationError("Kata sandi minimal 8 karakter.")
    doc = customer_repo.create_customer(
        username=username,
        display_name=display_name or username,
        role=role,
        password_hash=hash_password(password),
    )
    log.info("staff_created username=%s role=%s", username, role)
    return customer_repo.to_public(doc)


def unlink_telegram(customer_id: str) -> CustomerOut:
    doc = customer_repo.update_fields(
        customer_id,
        {
            "telegram_chat_id": None,
            "telegram_verified": False,
            "telegram_linked_at": "",
        },
    )
    log.info("telegram_unlinked customer=%s", customer_id)
    return customer_repo.to_public(doc)
