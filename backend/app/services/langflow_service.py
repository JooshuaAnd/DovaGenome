"""LangflowService — satu-satunya jalan keluar untuk AI (spec §12).

Tanggung jawab: request AI, timeout, retry, error handling, parsing response,
logging.

`LANGFLOW_API_KEY` hanya hidup di backend. Tidak pernah dikembalikan ke client.
React → FastAPI → Langflow → FastAPI → React.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import AIError
from app.core.logging import get_logger
from app.schemas.customer import PassportOut
from app.schemas.internal import AiConsultOut
from app.utils.time import now_iso

log = get_logger("dova.langflow")

#: Tiga bentuk balasan Langflow yang pernah dipakai flow ini (port dari bot).
_FALLBACK_PATHS = (
    lambda r: r["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"],
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
    "disabled": "Layanan AI sedang dinonaktifkan oleh konfigurasi operasional.",
}

READINESS_STATES = ("CONNECTED", "DEGRADED", "OFFLINE", "MISCONFIGURED", "MOCK")


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

    def _degraded_response(
        self,
        *,
        reason: str,
        user_facing_key: str,
        message: str,
        session_id: str,
        passport: PassportOut | None,
        started: float | None = None,
        trace_id: str = "",
    ) -> AiConsultOut:
        """Return explicit fallback only when the operator opted into it."""
        trace_id = trace_id or uuid.uuid4().hex
        if settings.ai_mode == "allow_explicit_fallback":
            try:
                from app.services.rag_ai_service import generate_rag_answer

                reply = generate_rag_answer(
                    message=message,
                    customer_id=getattr(passport, "customer_id", "") or session_id,
                    session_id=session_id,
                )
                return AiConsultOut(
                    reply=reply,
                    session_id=session_id,
                    provider="supabase_rag_fallback",
                    flow_id=settings.langflow_flow_id,
                    trace_id=trace_id,
                    latency_ms=self._elapsed_ms(started) if started is not None else 0,
                    degraded=True,
                    readiness_state="DEGRADED",
                    reason_code=f"explicit_fallback_{reason}",
                    message=f"explicit_fallback:{reason}",
                )
            except Exception as exc:
                log.warning("explicit_fallback_failed reason=%s detail=%s", reason, type(exc).__name__)

        user_message = USER_FACING.get(user_facing_key, USER_FACING["offline"])
        return AiConsultOut(
            reply=user_message,
            session_id=session_id,
            flow_id=settings.langflow_flow_id,
            trace_id=trace_id,
            latency_ms=self._elapsed_ms(started) if started is not None else 0,
            degraded=True,
            readiness_state=self._failure_state(reason),
            reason_code=reason,
            message=f"langflow_unavailable:{reason};ai_mode={settings.ai_mode};fallback=disabled",
        )

    @staticmethod
    def _failure_state(reason: str) -> str:
        if reason == "disabled":
            return "MOCK"
        if reason in {"not_configured", "missing_flow_id"}:
            return "MISCONFIGURED"
        if reason in {"timeout", "network_error"}:
            return "OFFLINE"
        return "DEGRADED"

    # ── Public API ──────────────────────────────────────────────────────────
    def ask(
        self,
        message: str,
        *,
        session_id: str,
        passport: PassportOut | None = None,
        system_context: str = "",
        files: list[str] | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> AiConsultOut:
        """
        Kirim pertanyaan ke Langflow dan kembalikan balasan terstruktur.

        Tidak pernah melempar exception ke pemanggil untuk kegagalan jaringan —
        degradasinya dikembalikan sebagai `AiConsultOut` dengan `degraded=True`
        supaya frontend bisa menampilkan pesan ramah.
        """
        if settings.ai_mode == "disabled":
            return self._degraded_response(
                reason="disabled",
                user_facing_key="disabled",
                message=message,
                session_id=session_id,
                passport=passport,
                trace_id=uuid.uuid4().hex,
            )
        if not self.configured:
            log.info("langflow_not_configured ai_mode=%s", settings.ai_mode)
            return self._degraded_response(
                reason="not_configured",
                user_facing_key="not_configured",
                message=message,
                session_id=session_id,
                passport=passport,
                trace_id=uuid.uuid4().hex,
            )

        payload = self._build_payload(message, session_id, passport, system_context, files)
        started = time.monotonic()
        trace_id = uuid.uuid4().hex

        last_error: str = "unknown"
        retry_limit = settings.langflow_max_retries if max_retries is None else max_retries
        for attempt in range(retry_limit + 1):
            try:
                response = self._get_client().post(
                    settings.langflow_run_url,
                    json=payload,
                    timeout=timeout_seconds,
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
                if attempt < retry_limit:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return self._degraded_response(
                    reason="timeout",
                    user_facing_key="timeout",
                    message=message,
                    session_id=session_id,
                    passport=passport,
                    started=started,
                    trace_id=trace_id,
                )
            except httpx.HTTPError as exc:
                last_error = f"network:{type(exc).__name__}"
                log.warning(
                    "langflow_failure reason=network attempt=%d detail=%s",
                    attempt + 1, type(exc).__name__,
                )
                if attempt < retry_limit:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return self._degraded_response(
                    reason="network_error",
                    user_facing_key="offline",
                    message=message,
                    session_id=session_id,
                    passport=passport,
                    started=started,
                    trace_id=trace_id,
                )

            if response.status_code == 200:
                try:
                    text = self._extract_text(response.json())
                except ValueError:
                    last_error = "invalid_json"
                    log.warning("langflow_failure reason=invalid_json")
                    return self._degraded_response(
                        reason="invalid_json",
                        user_facing_key="unreadable",
                        message=message,
                        session_id=session_id,
                        passport=passport,
                        started=started,
                        trace_id=trace_id,
                    )
                if text:
                    log.info(
                        "langflow_ok session=%s latency_ms=%d chars=%d",
                        session_id, self._elapsed_ms(started), len(text),
                    )
                    return AiConsultOut(
                        reply=text,
                        session_id=session_id,
                        trace_id=trace_id,
                        flow_id=settings.langflow_flow_id,
                        latency_ms=self._elapsed_ms(started),
                        readiness_state="CONNECTED",
                        reason_code="flow_execution_ok",
                    )
                last_error = "empty_text"
                log.warning("langflow_failure reason=empty_text")
                return self._degraded_response(
                    reason="empty_text",
                    user_facing_key="unreadable",
                    message=message,
                    session_id=session_id,
                    passport=passport,
                    started=started,
                    trace_id=trace_id,
                )

            last_error = f"http_{response.status_code}"
            log.warning(
                "langflow_failure reason=%s attempt=%d trace=%s",
                last_error, attempt + 1, trace_id,
            )
            # 4xx = masalah permintaan, tidak berguna diulang.
            if 400 <= response.status_code < 500:
                break
        return self._degraded_response(
            reason=last_error,
            user_facing_key="offline",
            message=message,
            session_id=session_id,
            passport=passport,
            started=started,
            trace_id=trace_id,
        )



    # ── Payload ─────────────────────────────────────────────────────────────
    def _build_payload(
        self,
        message: str,
        session_id: str,
        passport: PassportOut | None,
        system_context: str,
        files: list[str] | None = None,
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
        if files:
            payload["files"] = files
        if session_id:
            payload["session_id"] = str(session_id)
        return payload

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    # ── Health ──────────────────────────────────────────────────────────────
    def health(self, *, probe: bool = False) -> dict[str, Any]:
        """Return redacted platform/flow readiness without ever raising.

        A version response proves only that the Langflow platform is reachable.
        ``probe=True`` performs one cheap flow execution to prove the selected
        flow returned readable output. The probe is opt-in so normal health
        checks do not spend model quota.
        """
        trace_id = uuid.uuid4().hex
        started = time.monotonic()
        base_result: dict[str, Any] = {
            "provider": "langflow",
            "flow_id": settings.langflow_flow_id,
            "trace_id": trace_id,
            "checked_at": now_iso(),
            "probe_requested": probe,
            "flow_execution_proven": False,
        }

        if settings.ai_mode == "disabled":
            return {
                **base_result,
                "state": "MOCK",
                "reachable": False,
                "reason_code": "ai_disabled",
                "latency_ms": 0,
            }
        if not settings.langflow_api_url or not settings.langflow_api_key:
            return {
                **base_result,
                "state": "MISCONFIGURED",
                "reachable": False,
                "reason_code": "missing_langflow_credentials",
                "latency_ms": 0,
            }
        if not settings.langflow_flow_id:
            return {
                **base_result,
                "state": "MISCONFIGURED",
                "reachable": False,
                "reason_code": "missing_flow_id",
                "latency_ms": 0,
            }

        base = settings.langflow_api_url.rstrip("/")
        base = base.split("/api/v1")[0] or base
        try:
            response = httpx.get(
                f"{base}/api/v1/version",
                headers={"x-api-key": settings.langflow_api_key},
                timeout=5.0,
            )
        except Exception as exc:
            log.warning("langflow_health_failed trace=%s reason=%s", trace_id, type(exc).__name__)
            return {
                **base_result,
                "state": "OFFLINE",
                "reachable": False,
                "reason_code": "version_request_failed",
                "error_type": type(exc).__name__,
                "latency_ms": self._elapsed_ms(started),
            }

        result = {
            **base_result,
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "latency_ms": self._elapsed_ms(started),
        }
        if response.status_code != 200:
            result.update({"state": "OFFLINE", "reason_code": "version_http_error"})
            return result
        try:
            result["version"] = response.json().get("version")
        except (TypeError, ValueError):
            result.update({"state": "DEGRADED", "reason_code": "version_payload_invalid"})
            return result

        if not probe:
            result.update({"state": "CONNECTED", "reason_code": "platform_reachable_flow_unprobed"})
            return result

        execution = self._probe_execution(trace_id=trace_id)
        result.update(execution)
        result["latency_ms"] = self._elapsed_ms(started)
        return result

    def _probe_execution(self, *, trace_id: str) -> dict[str, Any]:
        """Execute a non-business probe and return only safe metadata."""
        try:
            response = self._get_client().post(
                settings.langflow_run_url,
                json={
                    "input_value": "healthcheck: jawab READY saja",
                    "input_type": "chat",
                    "output_type": "chat",
                    "session_id": f"health:{trace_id}",
                },
                headers={
                    "x-api-key": settings.langflow_api_key,
                    "Content-Type": "application/json",
                },
            )
        except httpx.TimeoutException:
            log.warning("langflow_probe_failed trace=%s reason=timeout", trace_id)
            return {"state": "OFFLINE", "reason_code": "flow_timeout"}
        except httpx.HTTPError as exc:
            log.warning("langflow_probe_failed trace=%s reason=%s", trace_id, type(exc).__name__)
            return {"state": "OFFLINE", "reason_code": "flow_network_error"}

        if response.status_code != 200:
            log.warning("langflow_probe_failed trace=%s status=%d", trace_id, response.status_code)
            reason = (
                "flow_auth_error"
                if response.status_code in (401, 403)
                else "flow_http_error"
            )
            return {
                "state": "DEGRADED",
                "reason_code": reason,
                "flow_status_code": response.status_code,
            }
        try:
            readable = bool(self._extract_text(response.json()))
        except ValueError:
            readable = False
        if not readable:
            return {"state": "DEGRADED", "reason_code": "flow_output_invalid"}
        return {
            "state": "CONNECTED",
            "reason_code": "flow_execution_ok",
            "flow_execution_proven": True,
        }


#: Instance tunggal.
langflow_service = LangflowService()


def require_langflow() -> None:
    if not langflow_service.configured:
        raise AIError(USER_FACING["not_configured"])
