"""Schema bersama (Pydantic v2)."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    error: ErrorBody


class Page(ApiModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class HealthPayload(ApiModel):
    status: str
    version: str
    environment: str
    demo_mode: bool
    db_connected: bool
    tables: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, bool] = Field(default_factory=dict)
    telegram_bot_username: str = ""
    # Backward-compat alias — beberapa klien masih membaca field ini
    astra_connected: bool = False

    def model_post_init(self, __context: Any) -> None:
        # Sinkronkan alias agar klien lama tetap benar
        object.__setattr__(self, "astra_connected", self.db_connected)
