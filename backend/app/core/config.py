"""Konfigurasi aplikasi — sumber tunggal untuk seluruh environment variable.

Aturan keras:
  * Tidak ada credential default. `SUPABASE_*` dan `LANGFLOW_API_KEY` wajib diisi.
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

    # ── Supabase / Postgres ─────────────────────────────────────────────────
    # Opsi 1: DSN lengkap — paling fleksibel.
    supabase_url: str = Field(default="")

    # Opsi 2: komponen terpisah — pakai nama variable yang sudah diisi user.
    # SUPABASE_DB_API_ENDPOINT  = host Supabase (mis. db.xxxx.supabase.co)
    # SUPABASE_DB_APPLICATION_TOKEN = postgres password / service key
    supabase_db_api_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_DB_API_ENDPOINT", "SUPABASE_HOST"
        ),
    )
    supabase_db_application_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_DB_APPLICATION_TOKEN", "SUPABASE_SERVICE_KEY",
            "SUPABASE_PASSWORD",
        ),
    )
    supabase_db_name: str = Field(default="postgres")
    supabase_db_user: str = Field(default="postgres")
    supabase_db_port: int = Field(default=5432)

    # ── Langflow ────────────────────────────────────────────────────────────
    langflow_api_url: str = Field(default="")
    langflow_api_key: str = Field(default="")
    langflow_flow_id: str = ""
    langflow_internal_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LANGFLOW_INTERNAL_TOKEN", "DOVAGENOME_INTERNAL_TOKEN"
        ),
    )
    langflow_timeout_seconds: float = Field(default=30.0)
    langflow_recipe_timeout_seconds: float = Field(default=180.0, ge=30.0, le=300.0)
    langflow_max_retries: int = Field(default=1)
    ai_mode: str = Field(default="required_langflow")

    # ── OpenAI recipe draft (vision + web search) ───────────────────────
    # Kept separate from the customer-facing Langflow assistant. The key is
    # server-only and is never sent to React.
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("API_KEY_ADMIN", "OPENAI_API_KEY"),
    )
    openai_recipe_model: str = Field(default="gpt-4.1-mini")
    openai_recipe_web_search: bool = Field(default=True)
    openai_recipe_timeout_seconds: float = Field(default=45.0, ge=5.0, le=120.0)

    # ── Pembayaran ─────────────────────────────────────────────────────────
    payment_webhook_secret: str = Field(default="")
    payment_intent_ttl_minutes: int = Field(default=10, ge=1, le=60)
    marketing_delivery_webhook_secret: str = Field(default="")

    # ── IBM Watsonx / Bob AI ────────────────────────────────────────────────
    api_key_ibm_bob: str = Field(
        default="",
        validation_alias=AliasChoices("API_KEY_IBM_BOB", "IBM_BOB_API_KEY", "BOB_API_KEY"),
    )

    # ── Telegram ────────────────────────────────────────────────────────────
    telegram_bot_token: str = Field(
        default="", validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN")
    )
    telegram_bot_username: str = Field(
        default="", validation_alias=AliasChoices("TELEGRAM_BOT_USERNAME", "TELEGRAM_BOT")
    )
    # Telegram chat IDs allowed to review procurement drafts.
    telegram_admin_chat_ids: str = ""
    # Existing admin customer ID used for audit_log and FK-safe approvals.
    telegram_admin_customer_id: str = ""

    # ── Auth ────────────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60 * 24 * 7)
    allow_passwordless_login: bool = Field(default=True)
    telegram_link_code_ttl_minutes: int = Field(default=10)

    # ── Data ────────────────────────────────────────────────────────────────
    catalog_cache_ttl_seconds: int = Field(default=120)
    demo_mode: bool = Field(default=False)
    default_currency: str = "IDR"

    @field_validator("supabase_db_api_endpoint")
    @classmethod
    def _strip_host(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        # Buang scheme bila user menempel URL penuh
        for prefix in ("https://", "http://"):
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v

    @field_validator("debug", mode="before")
    @classmethod
    def _coerce_debug_flag(cls, v: object) -> object:
        """Accept deployment labels such as DEBUG=release as non-debug mode."""
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"release", "production", "prod", "false", "0", "no", "off", ""}:
                return False
            if normalized in {"debug", "development", "true", "1", "yes", "on"}:
                return True
        return v

    @field_validator("telegram_bot_username")
    @classmethod
    def _normalize_username(cls, v: str) -> str:
        return (v or "").strip().lstrip("@")

    @field_validator("ai_mode")
    @classmethod
    def _validate_ai_mode(cls, v: str) -> str:
        value = (v or "").strip().lower()
        allowed = {"required_langflow", "allow_explicit_fallback", "disabled"}
        if value not in allowed:
            raise ValueError(f"AI_MODE harus salah satu dari {sorted(allowed)}.")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def langflow_run_url(self) -> str:
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
        db_configured = bool(self.supabase_url or (
            self.supabase_db_api_endpoint and self.supabase_db_application_token
        ))
        return {
            "SUPABASE_DB": db_configured,
            "LANGFLOW_API_URL": bool(self.langflow_api_url),
            "LANGFLOW_API_KEY": bool(self.langflow_api_key),
            "LANGFLOW_FLOW_ID": bool(self.langflow_flow_id),
            "LANGFLOW_INTERNAL_TOKEN": bool(self.langflow_internal_token),
            "OPENAI_API_KEY": bool(self.openai_api_key),
            "PAYMENT_WEBHOOK_SECRET": bool(self.payment_webhook_secret),
              "MARKETING_DELIVERY_WEBHOOK_SECRET": bool(self.marketing_delivery_webhook_secret),
            "TELEGRAM_BOT_TOKEN": bool(self.telegram_bot_token),
            "TELEGRAM_BOT_USERNAME": bool(self.telegram_bot_username),
            "TELEGRAM_ADMIN_CHAT_IDS": bool(self.telegram_admin_chat_ids.strip()),
            "TELEGRAM_ADMIN_CUSTOMER_ID": bool(self.telegram_admin_customer_id.strip()),
            "API_KEY_IBM_BOB": bool(self.api_key_ibm_bob),
            "JWT_SECRET": self.jwt_secret != "dev-only-change-me",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
