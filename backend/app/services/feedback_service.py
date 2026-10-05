"""Feedback service — umpan balik pelanggan disimpan lokal, bukan ke Langflow.

Umpan balik sering berisi data pribadi (nama, telepon, alamat). Untuk itu ia
tidak pernah dikirim ke flow AI. Disimpan di collection terpisah agar tidak
mencemari katalog dan tidak ikut di-seed ke project Langflow lain.
"""

from __future__ import annotations

import uuid

from app.core.logging import get_logger
from app.repositories.astra import get_collection
from app.schemas.customer import CustomerOut
from app.schemas.internal import FeedbackIn, FeedbackOut
from app.utils.time import now_iso

log = get_logger("dova.feedback")

COLLECTION_FEEDBACK = "customer_feedback"

ALLOWED_CATEGORIES = {"general", "menu", "service", "delivery", "complaint", "praise"}


def save(payload: FeedbackIn, *, customer: CustomerOut) -> FeedbackOut:
    """Simpan umpan balik. Tidak pernah gagal diam-diam."""
    category = payload.category.strip().lower()
    if category not in ALLOWED_CATEGORIES:
        category = "general"

    feedback_id = f"fb_{uuid.uuid4().hex[:10]}"
    document = {
        "_id": feedback_id,
        "feedback_id": feedback_id,
        "category": category,
        "message": payload.message.strip(),
        "email": payload.email.strip(),
        "order_id": payload.order_id.strip(),
        "rating": payload.rating,
        "customer_id": customer.customer_id,
        "customer_username": customer.username,
        "created_at": now_iso(),
        "handled": False,
    }

    try:
        get_collection(COLLECTION_FEEDBACK).insert_one(document)
    except Exception as exc:
        # Umpan balik penting tapi tidak boleh menjatuhkan halaman.
        log.error("Simpan feedback %s gagal: %s: %s", feedback_id, type(exc).__name__, exc)
        raise

    log.info("feedback_saved id=%s category=%s customer=%s", feedback_id, category, customer.username)
    return FeedbackOut(
        feedback_id=feedback_id,
        received_at=document["created_at"],
        category=category,
    )