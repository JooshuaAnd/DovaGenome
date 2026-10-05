"""Router AI — satu-satunya pintu keluar ke Langflow.

Credential Langflow hanya hidup di server (`app.core.config`). Frontend tidak
pernah melihat `LANGFLOW_API_KEY` maupun `LANGFLOW_API_URL`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_customer
from app.core.config import settings
from app.core.domain import DAYS
from app.core.logging import get_logger
from app.schemas.customer import CustomerOut
from app.schemas.internal import (
    AiConsultIn,
    AiConsultOut,
    AiMenuSuggestionIn,
    AiMenuSuggestionOut,
    FeedbackIn,
    FeedbackOut,
)
from app.services import feedback_service, safety_service
from app.services.langflow_service import langflow_service as ai_client
from app.utils.time import now_iso

log = get_logger("dova.api.ai")

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/consult", response_model=AiConsultOut, summary="Tanya asisten AI")
def consult(
    payload: AiConsultIn, customer: CustomerOut = Depends(get_current_customer)
) -> AiConsultOut:
    """
    Tanya asisten katering.

    Bila Langflow tidak bisa dihubungi, backend tetap membalas dengan pesan
    fallback yang jelas dan `degraded=true` — bukan traceback.
    """
    return ai_client.ask(
        message=payload.message,
        session_id=payload.session_id or customer.customer_id,
        system_context=_customer_context(customer, payload.context),
    )


def _customer_context(customer: CustomerOut, extra: dict) -> str:
    """Konteks ringkas untuk prompt — bukan data sensitif."""
    lines = [
        f"Pelanggan: {customer.display_name or customer.username}",
        f"Peran: {customer.role}",
        f"Telegram tertaut: {'ya' if customer.telegram_verified else 'belum'}",
    ]
    for key, value in extra.items():
        lines.append(f"{key}: {value}")
    return " | ".join(lines)


@router.post(
    "/menu-suggestion",
    response_model=AiMenuSuggestionOut,
    summary="Saran menu aman untuk hari tertentu",
)
def menu_suggestion(
    payload: AiMenuSuggestionIn,
    customer: CustomerOut = Depends(get_current_customer),
) -> AiMenuSuggestionOut:
    """
    Gabung laporan safety deterministik dengan saran bahasa alami dari Langflow.

    Laporan safety tetap dihitung lokal — keputusan "aman / tidak aman" tidak
    pernah diserahkan ke model bahasa.
    """
    days = [d for d in payload.service_days if d in DAYS] or list(DAYS)
    report = safety_service.build_report(
        selected_codes=payload.selected_allergen_codes,
        passport=None,
        schedule_days=days,
    )

    answer = ai_client.ask(
        message=(
            "Pelanggan meminta saran menu untuk hari: "
            + ", ".join(days)
            + ". Batasan yang dipilih: "
            + (", ".join(report.passport_excludes) or "tidak ada")
            + ". Jawab singkat dan ramah dalam Bahasa Indonesia."
        ),
        session_id=f"menu:{customer.customer_id}",
        system_context=f"Tingkat kecocokan menu: {report.level}",
    )

    return AiMenuSuggestionOut(
        reply=answer.reply,
        safety=report,
        suggested_days=[d.hari for d in report.per_day if d.is_recommended],
        avoided_days=[d.hari for d in report.per_day if not d.is_recommended],
        session_id=answer.session_id,
        degraded=answer.degraded,
    )


@router.post("/feedback", response_model=FeedbackOut, status_code=201, summary="Kirim umpan balik")
def feedback(
    payload: FeedbackIn, customer: CustomerOut = Depends(get_current_customer)
) -> FeedbackOut:
    return feedback_service.save(payload, customer=customer)


@router.get("/config", summary="Status konfigurasi AI")
def ai_config(customer: CustomerOut = Depends(get_current_customer)) -> dict:
    """Apa yang tersimpan tentang integrasi AI (tanpa secret)."""
    return {
        "provider": "langflow",
        "configured": ai_client.configured,
        "flow_id_set": bool(settings.langflow_flow_id),
        "telegram_bot_username": settings.telegram_bot_username,
        "checked_at": now_iso(),
    }