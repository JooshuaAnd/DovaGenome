"""LangflowService — satu-satunya jalan keluar untuk AI (spec §12).

Tanggung jawab: request AI, timeout, retry, error handling, parsing response,
logging.

`LANGFLOW_API_KEY` hanya hidup di backend. Tidak pernah dikembalikan ke client.
React → FastAPI → Langflow → FastAPI → React.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import AIError
from app.core.logging import get_logger
from app.schemas.customer import PassportOut
from app.schemas.internal import AiConsultOut

log = get_logger("dova.langflow")

#: Tiga bentuk balasan Langflow yang pernah dipakai flow ini (port dari bot).
_FALLBACK_PATHS = (
    lambda r: r["outputs"][0]["outputs"][0]["results"]["message"]["text"],
    lambda r: r["outputs"][0]["outputs"][0]["artifacts"]["text"],
    lambda r: r["text"],
)

USER_FACING = {
    "busy": (
        "Maaf, asisten AI sedang sibuk. Coba lagi beberapa saat lagi, "
        "atau hubungi tim kami."
    ),
    "unreadable": "Maaf, balasan AI tidak dapat dibaca. Coba ulangi pertanyaannya.",
    "timeout": "Maaf, AI membutuhkan waktu terlalu lama. Silakan coba lagi.",
    "offline": "Maaf, terjadi gangguan koneksi ke asisten AI.",
    "not_configured": (
        "Layanan AI belum dikonfigurasi. Isi LANGFLOW_API_URL dan "
        "LANGFLOW_API_KEY di .env."
    ),
}


class LangflowService:
    """Client Langflow stateless. Satu instance dibagi ke semua request."""

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    # ── HTTP ────────────────────────────────────────────────────────────────
    @property
    def configured(self) -> bool:
        return bool(settings.langflow_api_url and settings.langflow_api_key)

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(settings.langflow_timeout_seconds, connect=5.0)
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ── Parsing ─────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_text(response_json: Any) -> str:
        for path in _FALLBACK_PATHS:
            try:
                value = path(response_json)
            except (KeyError, IndexError, TypeError):
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    # ── Public API ──────────────────────────────────────────────────────────
    def ask(
        self,
        message: str,
        *,
        session_id: str,
        passport: PassportOut | None = None,
        system_context: str = "",
    ) -> AiConsultOut:
        """
        Kirim pertanyaan ke Langflow dan kembalikan balasan terstruktur.

        Tidak pernah melempar exception ke pemanggil untuk kegagalan jaringan —
        degradasinya dikembalikan sebagai `AiConsultOut` dengan `degraded=True`
        supaya frontend bisa menampilkan pesan ramah.
        """
        if not self.configured:
            log.error("langflow_failure reason=not_configured")
            return AiConsultOut(
                reply=USER_FACING["not_configured"],
                session_id=session_id,
                flow_id=settings.langflow_flow_id,
                degraded=True,
                message="LANGFLOW_API_URL / LANGFLOW_API_KEY belum diisi.",
            )

        payload = self._build_payload(message, session_id, passport, system_context)
        started = time.monotonic()

        last_error: str = "unknown"
        for attempt in range(settings.langflow_max_retries + 1):
            try:
                response = self._get_client().post(
                    settings.langflow_run_url,
                    json=payload,
                    headers={
                        "x-api-key": settings.langflow_api_key,
                        "Content-Type": "application/json",
                    },
                )
            except httpx.TimeoutException:
                last_error = "timeout"
                log.warning(
                    "langflow_failure reason=timeout attempt=%d session=%s",
                    attempt + 1, session_id,
                )
                if attempt < settings.langflow_max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return AiConsultOut(
                    reply=USER_FACING["timeout"],
                    session_id=session_id,
                    flow_id=settings.langflow_flow_id,
                    latency_ms=self._elapsed_ms(started),
                    degraded=True,
                    message="Langflow timeout.",
                )
            except httpx.HTTPError as exc:
                last_error = f"network:{type(exc).__name__}"
                log.warning(
                    "langflow_failure reason=network attempt=%d detail=%s",
                    attempt + 1, type(exc).__name__,
                )
                if attempt < settings.langflow_max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return AiConsultOut(
                    reply=USER_FACING["offline"],
                    session_id=session_id,
                    flow_id=settings.langflow_flow_id,
                    latency_ms=self._elapsed_ms(started),
                    degraded=True,
                    message="Langflow tidak dapat dihubungi.",
                )

            if response.status_code == 200:
                try:
                    text = self._extract_text(response.json())
                except ValueError:
                    last_error = "invalid_json"
                    log.warning("langflow_failure reason=invalid_json")
                    return AiConsultOut(
                        reply=USER_FACING["unreadable"],
                        session_id=session_id,
                        flow_id=settings.langflow_flow_id,
                        latency_ms=self._elapsed_ms(started),
                        degraded=True,
                        message="Respons Langflow bukan JSON valid.",
                    )
                if text:
                    log.info(
                        "langflow_ok session=%s latency_ms=%d chars=%d",
                        session_id, self._elapsed_ms(started), len(text),
                    )
                    return AiConsultOut(
                        reply=text,
                        session_id=session_id,
                        flow_id=settings.langflow_flow_id,
                        latency_ms=self._elapsed_ms(started),
                    )
                last_error = "empty_text"
                log.warning("langflow_failure reason=empty_text")
                return AiConsultOut(
                    reply=USER_FACING["unreadable"],
                    session_id=session_id,
                    flow_id=settings.langflow_flow_id,
                    latency_ms=self._elapsed_ms(started),
                    degraded=True,
                    message="Respons Langflow tidak memuat teks.",
                )

            last_error = f"http_{response.status_code}"
            log.warning(
                "langflow_failure reason=%s attempt=%d body=%s",
                last_error, attempt + 1, response.text[:300],
            )
            # 4xx = masalah permintaan, tidak berguna diulang.
            if 400 <= response.status_code < 500:
                break
            if attempt < settings.langflow_max_retries:
                time.sleep(1.5 * (attempt + 1))

        reply = USER_FACING["busy"]
        if last_error == "http_401" or last_error == "http_403":
            reply = (
                "Maaf, layanan AI menolak permintaan (kredensial tidak valid). "
                "Tim teknis sudah diberi tahu."
            )
        return AiConsultOut(
            reply=reply,
            session_id=session_id,
            flow_id=settings.langflow_flow_id,
            latency_ms=self._elapsed_ms(started),
            degraded=True,
            message=f"Langflow gagal: {last_error}",
        )

    # ── Payload ─────────────────────────────────────────────────────────────
    def _build_payload(
        self,
        message: str,
        session_id: str,
        passport: PassportOut | None,
        system_context: str,
    ) -> dict[str, Any]:
        """
        Bangun payload Langflow.

        `input_value` diawali konteks profil agar flow RAG tahu batasan
        pelanggan — ini menggantikan prompt yang sebelumnya dirakit manual di bot.
        """
        prefix_parts: list[str] = []
        if passport and (passport.critical_codes or passport.avoided_ingredients):
            labels = [r.label for r in (*passport.allergies, *passport.intolerances, *passport.medical)]
            prefix_parts.append(
                "Profil dietary pelanggan — Pantangan: "
                + (", ".join(labels) if labels else "tidak ada")
            )
            if passport.avoided_ingredients:
                prefix_parts.append(
                    "Bahan yang dihindari: " + ", ".join(passport.avoided_ingredients)
                )
            if passport.safety_notes:
                prefix_parts.append("Catatan keselamatan: " + passport.safety_notes)
        if system_context:
            prefix_parts.append(system_context)

        value = message
        if prefix_parts:
            value = "[KONTEKS DINAVIS]\n" + "\n".join(prefix_parts) + "\n\n[PERTANYAAN]\n" + message

        payload: dict[str, Any] = {
            "input_value": value,
            "input_type": "chat",
            "output_type": "chat",
        }
        if session_id:
            payload["session_id"] = str(session_id)
        return payload

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    # ── Health ──────────────────────────────────────────────────────────────
    def health(self) -> dict[str, Any]:
        """Cek apakah Langflow hidup. Tidak pernah melempar."""
        if not self.configured:
            return {"reachable": False, "reason": "not_configured"}
        base = settings.langflow_api_url.rstrip("/")
        base = base.split("/api/v1")[0] or base
        try:
            response = httpx.get(
                f"{base}/api/v1/version",
                headers={"x-api-key": settings.langflow_api_key},
                timeout=5.0,
            )
            return {
                "reachable": response.status_code == 200,
                "status_code": response.status_code,
                "version": response.json().get("version") if response.status_code == 200 else None,
            }
        except Exception as exc:
            log.warning("Pengecekalan Langflow gagal: %s", type(exc).__name__)
            return {"reachable": False, "reason": type(exc).__name__}


#: Instance tunggal.
langflow_service = LangflowService()


def require_langflow() -> None:
    if not langflow_service.configured:
        raise AIError(USER_FACING["not_configured"])
