"""Feedback service — umpan balik pelanggan disimpan lokal, bukan ke Langflow.

Umpan balik sering berisi data pribadi (nama, telepon, alamat). Untuk itu ia
tidak pernah dikirim ke flow AI. Disimpan di collection terpisah agar tidak
mencemari katalog dan tidak ikut di-seed ke project Langflow lain.
"""

from __future__ import annotations

import uuid

from app.core.logging import get_logger
from app.repositories import supabase as db
from app.schemas.customer import CustomerOut
from app.schemas.internal import FeedbackIn, FeedbackOut
from app.utils.time import now_iso

log = get_logger("dova.feedback")

ALLOWED_CATEGORIES = {"general", "menu", "service", "delivery", "complaint", "praise"}


def save(payload: FeedbackIn, *, customer: CustomerOut) -> FeedbackOut:
    """Simpan umpan balik. Tidak pernah gagal diam-diam."""
    category = payload.category.strip().lower()
    if category not in ALLOWED_CATEGORIES:
        category = "general"

    order_id_val = payload.order_id.strip() or None
    created_at = now_iso()
    try:
        db.execute_write(
            """
            INSERT INTO customer_feedback
                (customer_id, order_id, rating, comment, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                customer.customer_id,
                order_id_val,
                payload.rating,
                payload.message.strip(),
                created_at,
            ),
        )
    except Exception as exc:
        log.error("Simpan feedback gagal: %s: %s", type(exc).__name__, exc)
        raise

    feedback_id = f"fb_{uuid.uuid4().hex[:10]}"
    log.info("feedback_saved category=%s customer=%s", category, customer.username)
    return FeedbackOut(
        feedback_id=feedback_id,
        received_at=created_at,
        category=category,
    )