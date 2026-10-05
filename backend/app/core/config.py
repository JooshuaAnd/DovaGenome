"""Konfigurasi aplikasi — sumber tunggal untuk seluruh environment variable.

Aturan keras:
  * Tidak ada credential default. `ASTRA_DB_*` dan `LANGFLOW_API_KEY` wajib diisi.
  * `.env` dibaca dari repo root (`../.env`) atau `backend/.env`.
  * Nilai rahasia tidak pernah masuk ke response API.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Aplikasi ────────────────────────────────────────────────────────────
    app_name: str = "DovaGenome AI API"
    app_version: str = "1.0.0"
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    api_prefix: str = "/api"

    # Origins allowed untuk CORS. Dipisah koma.
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173"
    )

    # ── Astra DB ────────────────────────────────────────────────────────────
    astra_db_api_endpoint: str
    astra_db_application_token: str

    # ── Langflow ────────────────────────────────────────────────────────────
    langflow_api_url: str
    langflow_api_key: str
    langflow_flow_id: str = ""
    langflow_timeout_seconds: float = Field(default=30.0)
    langflow_max_retries: int = Field(default=1)

    # ── Telegram ────────────────────────────────────────────────────────────
    # `TELEGRAM_TOKEN` adalah nama lama di root `.env`; keduanya diterima agar
    # tidak perlu mengganti file env yang sudah ada.
    telegram_bot_token: str = Field(
        default="", validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN")
    )
    telegram_bot_username: str = Field(
        default="", validation_alias=AliasChoices("TELEGRAM_BOT_USERNAME", "TELEGRAM_BOT")
    )

    # ── Auth ────────────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60 * 24 * 7)
    # Akun tanpa password_hash boleh login hanya dengan username.
    # Aktifkan hanya untuk MVP; admin/kitchen WAJIB memakai password.
    allow_passwordless_login: bool = Field(default=True)
    telegram_link_code_ttl_minutes: int = Field(default=10)

    # ── Data ────────────────────────────────────────────────────────────────
    catalog_cache_ttl_seconds: int = Field(default=120)
    # Saat Astra DB tidak tersambung, JANGAN pernah menyajikan pesanan contoh
    # ke KDS/admin. Default wajib False.
    demo_mode: bool = Field(default=False)
    default_currency: str = "IDR"

    @field_validator("astra_db_api_endpoint")
    @classmethod
    def _strip_endpoint(cls, v: str) -> str:
        return v.strip().rstrip("/")

    @field_validator("telegram_bot_username")
    @classmethod
    def _normalize_username(cls, v: str) -> str:
        return (v or "").strip().lstrip("@")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def langflow_run_url(self) -> str:
        """
        URL run Langflow.

        `LANGFLOW_API_URL` boleh berupa base (`http://host:7860/api/v1`),
        base + `/run`, atau URL run lengkap. Yang sudah memuat `/run`
        dipakai apa adanya supaya flow id tidak terduplikasi.
        """
        url = self.langflow_api_url.strip().rstrip("/")
        if "/run" in url:
            return url
        if not self.langflow_flow_id:
            return f"{url}/run"
        return f"{url}/run/{self.langflow_flow_id}"

    @property
    def telegram_bot_configured(self) -> bool:
        return bool(self.telegram_bot_username or ":" in self.telegram_bot_token)

    def telegram_link(self, payload: str | None = None) -> str:
        user = self.telegram_bot_username
        if not user and ":" in self.telegram_bot_token:
            user = self.telegram_bot_token.split(":", 1)[0]
        if not user:
            return ""
        return f"https://t.me/{user}" + (f"?start={payload}" if payload else "")

    def credential_status(self) -> dict[str, bool]:
        """Status isi credential untuk endpoint diagnosa — nilai tidak pernah dibocorkan."""
        return {
            "ASTRA_DB_API_ENDPOINT": bool(self.astra_db_api_endpoint),
            "ASTRA_DB_APPLICATION_TOKEN": bool(self.astra_db_application_token),
            "LANGFLOW_API_URL": bool(self.langflow_api_url),
            "LANGFLOW_API_KEY": bool(self.langflow_api_key),
            "LANGFLOW_FLOW_ID": bool(self.langflow_flow_id),
            "TELEGRAM_BOT_TOKEN": bool(self.telegram_bot_token),
            "TELEGRAM_BOT_USERNAME": bool(self.telegram_bot_username),
            "JWT_SECRET": self.jwt_secret != "dev-only-change-me",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
