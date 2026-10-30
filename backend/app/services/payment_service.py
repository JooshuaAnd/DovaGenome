"""Payment boundary: intent, signed webhook, idempotency, and KDS release.

Provider-specific SDK calls stay outside this module. The backend only accepts
an intent for the server-owned order total and a signed provider event. A
successful payment changes the order to PAID and creates the kitchen ticket in
the same database transaction. No LLM or client field can release the order.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.errors import ConflictError, ExternalServiceError, PermissionError_, ValidationError
from app.core.logging import get_logger
from app.repositories import order_repo
from app.repositories import supabase as db
from app.schemas.customer import CustomerOut
from app.schemas.payment import (
    PaymentIntentOut,
    PaymentWebhookIn,
    PaymentWebhookOut,
)

log = get_logger("dova.payment")

ACTIVE_ATTEMPT_STATUSES = ("INITIATED", "REQUIRES_ACTION")
SUCCESS_STATUSES = {"SUCCEEDED", "PAID", "SUCCESS"}
FAILURE_STATUSES = {"FAILED", "EXPIRED", "REFUNDED"}


def sign_payload(raw_body: bytes, secret: str) -> str:
    """Return the provider-neutral HMAC-SHA256 header value."""
    if not secret:
        raise ExternalServiceError("PAYMENT_WEBHOOK_SECRET belum dikonfigurasi.")
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(raw_body: bytes, signature: str, secret: str | None = None) -> bool:
    configured = (secret if secret is not None else settings.payment_webhook_secret).strip()
    if not configured or not signature:
        return False
    expected = sign_payload(raw_body, configured)
    candidate = signature.strip()
    if candidate.lower().startswith("sha256="):
        candidate = "sha256=" + candidate.split("=", 1)[1].lower()
    return hmac.compare_digest(expected, candidate)


def _assert_customer_order(order: dict[str, Any], customer: CustomerOut) -> None:
    if order.get("customer_id") == customer.customer_id:
        return
    if (
        customer.telegram_chat_id
        and order.get("chat_id")
        and int(order["chat_id"]) == int(customer.telegram_chat_id)
    ):
        return
    raise PermissionError_("Pesanan tidak ditemukan.")


def _attempt_out(row: dict[str, Any]) -> PaymentIntentOut:
    expires = row.get("expires_at")
    if expires is not None and not isinstance(expires, datetime):
        try:
            expires = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        except ValueError:
            expires = None
    return PaymentIntentOut(
        payment_attempt_id=str(row["payment_attempt_id"]),
        order_id=str(row["order_id"]),
        provider=str(row["provider"]),
        provider_payment_id=str(row.get("provider_payment_id") or ""),
        idempotency_key=str(row["idempotency_key"]),
        status=str(row["status"]),
        amount=int(row["amount"]),
        currency=str(row.get("currency") or settings.default_currency),
        expires_at=expires,
    )


def create_intent(
    order_id: str,
    customer: CustomerOut,
    *,
    provider: str,
    idempotency_key: str,
) -> PaymentIntentOut:
    """Create or replay a payment intent using the stored order total."""
    order = order_repo.get_order_by_id(order_id)
    _assert_customer_order(order, customer)

    if order.get("status") in {"CANCELLED", "COMPLETED"}:
        raise ConflictError("Pesanan sudah tidak dapat dibayar.")
    if order.get("payment_status") == "PAID":
        raise ConflictError("Pesanan ini sudah lunas.")

    existing = db.execute_one(
        """
        SELECT payment_attempt_id, order_id, provider, provider_payment_id,
               idempotency_key, status, amount, currency, expires_at
        FROM payment_attempts
        WHERE idempotency_key = %s
        """,
        (idempotency_key,),
    )
    if existing:
        if str(existing["order_id"]) != order_id:
            raise ConflictError("Idempotency key sudah dipakai untuk pesanan lain.")
        return _attempt_out(existing)

    amount = int(order.get("total") or 0)
    if amount <= 0:
        raise ValidationError("Total pesanan belum valid untuk dibuatkan pembayaran.")

    ttl = max(1, min(int(settings.payment_intent_ttl_minutes), 60))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    row = db.execute_one(
        """
        INSERT INTO payment_attempts (
            order_id, provider, idempotency_key, status, amount, currency, expires_at
        ) VALUES (%s, %s, %s, 'INITIATED', %s, %s, %s)
        RETURNING payment_attempt_id, order_id, provider, provider_payment_id,
                  idempotency_key, status, amount, currency, expires_at
        """,
        (order_id, provider.strip().lower(), idempotency_key, amount, settings.default_currency, expires_at),
    )
    if not row:
        raise ExternalServiceError("Payment intent tidak dapat dibuat.")

    order_repo.update_fields(order["id"], {"payment_status": "PENDING"})
    log.info("payment_intent_created order=%s provider=%s", order_id, provider)
    return _attempt_out(row)


def _redacted_payload(payload: PaymentWebhookIn) -> str:
    return json.dumps(
        {
            "provider": payload.provider,
            "event_id": payload.event_id,
            "provider_payment_id": payload.provider_payment_id,
            "order_id": payload.order_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "status": payload.status,
        },
        separators=(",", ":"),
    )


def process_webhook(
    payload: PaymentWebhookIn,
    *,
    raw_body: bytes,
    signature: str,
) -> PaymentWebhookOut:
    """Verify and apply one provider event atomically and idempotently."""
    if not verify_signature(raw_body, signature):
        raise PermissionError_("Signature webhook pembayaran tidak valid.")

    provider = payload.provider.lower()
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payment_attempt_id, order_id, provider, provider_payment_id,
                       status, amount, currency, expires_at
                FROM payment_attempts
                WHERE provider = %s AND provider_event_id = %s
                FOR UPDATE
                """,
                (provider, payload.event_id),
            )
            duplicate = cur.fetchone()
            if duplicate:
                return PaymentWebhookOut(
                    duplicate=True,
                    order_id=str(duplicate["order_id"]),
                    payment_attempt_id=str(duplicate["payment_attempt_id"]),
                    payment_status="PAID" if duplicate["status"] == "SUCCEEDED" else "UNPAID",
                    kitchen_ticket_created=False,
                )

            cur.execute(
                """
                SELECT payment_attempt_id, order_id, provider_payment_id, status,
                       amount, currency, expires_at
                FROM payment_attempts
                WHERE order_id = %s AND provider = %s
                  AND (provider_payment_id = %s OR provider_payment_id = '')
                ORDER BY created_at DESC
                LIMIT 1
                FOR UPDATE
                """,
                (payload.order_id, provider, payload.provider_payment_id),
            )
            attempt = cur.fetchone()
            if not attempt:
                raise ValidationError("Payment attempt tidak ditemukan untuk pesanan ini.")
            if int(attempt["amount"]) != payload.amount:
                raise ConflictError("Nominal webhook tidak sama dengan total pesanan.")
            if str(attempt["currency"]).upper() != payload.currency.upper():
                raise ConflictError("Mata uang webhook tidak sama dengan payment intent.")
            if attempt.get("expires_at") and attempt["expires_at"] < datetime.now(timezone.utc):
                raise ConflictError("Payment intent sudah kedaluwarsa.")
            if attempt["status"] == "SUCCEEDED":
                return PaymentWebhookOut(
                    duplicate=True,
                    order_id=payload.order_id,
                    payment_attempt_id=str(attempt["payment_attempt_id"]),
                    payment_status="PAID",
                    kitchen_ticket_created=False,
                )

            event_status = payload.status.upper()
            if event_status not in SUCCESS_STATUSES | FAILURE_STATUSES:
                raise ValidationError("Status webhook pembayaran tidak dikenal.")

            attempt_status = "SUCCEEDED" if event_status in SUCCESS_STATUSES else event_status
            cur.execute(
                """
                UPDATE payment_attempts
                   SET provider_payment_id = %s,
                       provider_event_id = %s,
                       status = %s,
                       signature_verified = TRUE,
                       verified_at = NOW(),
                       provider_payload_redacted = %s::jsonb,
                       updated_at = NOW()
                 WHERE payment_attempt_id = %s
                """,
                (
                    payload.provider_payment_id,
                    payload.event_id,
                    attempt_status,
                    _redacted_payload(payload),
                    attempt["payment_attempt_id"],
                ),
            )

            if event_status in SUCCESS_STATUSES:
                cur.execute(
                    """
                    UPDATE orders
                       SET payment_status = 'PAID', payment_reference = %s, updated_at = NOW()
                     WHERE order_id = %s AND status <> 'CANCELLED'
                    """,
                    (payload.provider_payment_id, payload.order_id),
                )
                cur.execute(
                    """
                    INSERT INTO kitchen_tickets (
                        order_id, payment_attempt_id, status, allergy_snapshot, recipe_snapshot,
                        released_at
                    )
                    SELECT o.order_id, %s, 'QUEUED',
                           jsonb_build_object(
                               'selected_allergens', o.selected_allergens,
                               'kitchen_notes', o.kitchen_notes
                           ),
                           jsonb_build_object('menu_selections', COALESCE(
                               (SELECT jsonb_agg(jsonb_build_object('hari', oi.hari, 'menu_id', oi.menu_id, 'quantity', oi.quantity, 'unit', oi.unit)
                                  ORDER BY oi.sort_order)
                                  FROM order_items oi WHERE oi.order_id = o.order_id), '[]'::jsonb
                           )),
                           NOW()
                      FROM orders o
                     WHERE o.order_id = %s AND o.status <> 'CANCELLED'
                    ON CONFLICT (order_id) DO NOTHING
                    """,
                    (attempt["payment_attempt_id"], payload.order_id),
                )
                cur.execute(
                    """
                    INSERT INTO order_status_events (order_id, status, actor, note)
                    VALUES (%s, 'PENDING', %s, 'Pembayaran terverifikasi; tiket dapur dibuka')
                    """,
                    (payload.order_id, f"payment_webhook:{provider}"),
                )
                return PaymentWebhookOut(
                    order_id=payload.order_id,
                    payment_attempt_id=str(attempt["payment_attempt_id"]),
                    payment_status="PAID",
                    kitchen_ticket_created=True,
                )

            cur.execute(
                """
                UPDATE orders
                   SET payment_status = 'UNPAID', updated_at = NOW()
                 WHERE order_id = %s AND payment_status <> 'PAID'
                """,
                (payload.order_id,),
            )
            return PaymentWebhookOut(
                order_id=payload.order_id,
                payment_attempt_id=str(attempt["payment_attempt_id"]),
                payment_status="UNPAID",
                kitchen_ticket_created=False,
            )


def mark_manual_paid(order_id: str, *, reference: str, actor: str) -> None:
    """Admin-confirmed payment uses the same ticket release boundary."""
    reference = reference.strip()
    if len(reference) < 4:
        raise ValidationError("Referensi pembayaran wajib diisi.")
    order = order_repo.get_order_by_id(order_id)
    if order.get("status") == "CANCELLED":
        raise ConflictError("Pesanan dibatalkan dan tidak dapat dilunasi.")
    if order.get("payment_status") == "PAID":
        return

    attempt_id = str(uuid.uuid4())
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payment_attempts (
                    payment_attempt_id, order_id, provider, provider_payment_id,
                    idempotency_key, status, amount, currency, signature_verified,
                    verified_at, provider_payload_redacted
                ) VALUES (%s, %s, 'manual', %s, %s, 'SUCCEEDED', %s, %s, FALSE,
                          NOW(), %s::jsonb)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    attempt_id,
                    order_id,
                    reference,
                    f"manual:{order_id}:{reference}",
                    int(order.get("total") or 0),
                    settings.default_currency,
                    json.dumps({"actor": actor, "reference": reference}, separators=(",", ":")),
                ),
            )
            cur.execute(
                """
                UPDATE orders
                   SET payment_status = 'PAID', payment_reference = %s, updated_at = NOW()
                 WHERE order_id = %s AND status <> 'CANCELLED'
                """,
                (reference, order_id),
            )
            cur.execute(
                """
                INSERT INTO kitchen_tickets (
                    order_id, payment_attempt_id, status, allergy_snapshot, recipe_snapshot, released_at
                )
                SELECT o.order_id, pa.payment_attempt_id, 'QUEUED',
                       jsonb_build_object('selected_allergens', o.selected_allergens,
                                          'kitchen_notes', o.kitchen_notes),
                       jsonb_build_object('menu_selections', COALESCE(
                           (SELECT jsonb_agg(jsonb_build_object('hari', oi.hari, 'menu_id', oi.menu_id, 'quantity', oi.quantity, 'unit', oi.unit)
                              ORDER BY oi.sort_order)
                              FROM order_items oi WHERE oi.order_id = o.order_id), '[]'::jsonb
                       )), NOW()
                  FROM orders o
                  JOIN payment_attempts pa ON pa.order_id = o.order_id
                                           AND pa.idempotency_key = %s
                 WHERE o.order_id = %s AND o.status <> 'CANCELLED'
                ON CONFLICT (order_id) DO NOTHING
                """,
                (f"manual:{order_id}:{reference}", order_id),
            )
            cur.execute(
                """
                INSERT INTO order_status_events (order_id, status, actor, note)
                VALUES (%s, 'PENDING', %s, 'Pembayaran manual diverifikasi; tiket dapur dibuka')
                """,
                (order_id, actor),
            )


__all__ = ["create_intent", "mark_manual_paid", "process_webhook", "sign_payload", "verify_signature"]
