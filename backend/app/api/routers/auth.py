"""Router autentikasi — register, login, dan tukar kode linking Telegram."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import client_info, get_current_customer
from app.core.logging import get_logger
from app.schemas.customer import (
    CustomerOut,
    LoginIn,
    RegisterIn,
    TelegramLinkIn,
    TelegramLinkOut,
    TokenOut,
)
from app.services import auth_service
from app.utils.ratelimit import login_limiter, telegram_link_limiter

log = get_logger("dova.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201, summary="Daftar akun baru")
def register(payload: RegisterIn) -> TokenOut:
    """
    Buat akun pelanggan.

    Tidak meminta kata sandi (MVP). Token langsung diberikan, tetapi akun belum
    bisa membuat pesanan sampai Telegram tertaut — lihat `/customers/me/telegram`.
    """
    return auth_service.register_customer(payload)


@router.post("/login", response_model=TokenOut, summary="Masuk")
def login(payload: LoginIn, request: Request) -> TokenOut:
    """
    Masuk dengan kata sandi (khusus admin/kitchen).

    Dibatasi rate per IP: endpoint ini satu-satunya yang memeriksa kata sandi,
    jadi harus memperlambat tebak-menebak.
    """
    client = client_info(request)
    login_limiter.enforce(f"login:{client['ip']}")
    return auth_service.login_customer(payload)


@router.get("/me", response_model=CustomerOut, summary="Profil akun saat ini")
def me(customer: CustomerOut = Depends(get_current_customer)) -> CustomerOut:
    return customer


@router.post(
    "/telegram/resolve",
    response_model=TelegramLinkOut,
    summary="Tautkan chat Telegram ke akun",
)
def resolve_telegram(payload: TelegramLinkIn, request: Request) -> TelegramLinkOut:
    """
    Dipanggil Telegram bot setelah user membuka `?start=link_<CODE>`.

    Tidak butuh JWT karena pemanggil adalah bot (server-to-server). Code
    single-use dan hanya berlaku beberapa menit, jadi endpoint ini dibatasi
   -rate supaya kode tidak bisa ditebak brute-force.

    Catatan keamanan: pemanggil yang benar (bot) tidak diverifikasi kredensial
    di sini. Kalau endpoint ini dibuka ke internet, tambahkan shared secret
    header yang hanya bot yang tahu — jangan andalkan kode 8 karakter sebagai
    satu-satunya proteksi.
    """
    client = client_info(request)
    telegram_link_limiter.enforce(f"tg:{client['ip']}")
    return auth_service.link_telegram(payload, actor=client["agent"])