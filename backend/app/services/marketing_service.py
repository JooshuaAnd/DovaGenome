"""Admin-reviewed marketing workflow with consent and idempotent outbox queue.

This phase deliberately stops at a queued outbox item. There is no provider
call here and no automatic send. The source audience is the live, explainable
churn baseline; stale or non-live data cannot become a campaign draft.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any

from psycopg2.extras import Json

from app.core.config import settings
from app.core.errors import ConflictError, PermissionError_, ValidationError
from app.repositories import supabase as db
from app.schemas.marketing import MarketingDeliveryWebhookIn


CALCULATION_VERSION = "marketing_winback_v1"
CAMPAIGN_TYPE = "WINBACK"
FRESHNESS_MAX_DAYS = 7
ALLOWED_CHANNELS = {"whatsapp", "telegram"}
TARGET_RISK_BANDS = {"HIGH", "MEDIUM"}
DELIVERY_STATUSES = {"SENT", "FAILED"}


class MarketingUnavailable(RuntimeError):
    """The marketing workflow cannot safely advance."""


def _message(name: str, risk_band: str) -> str:
    greeting = name.strip() or "Kak"
    if risk_band == "HIGH":
        return (
            f"Halo {greeting}, Chef BOB rindu menyiapkan menu Dova Kitchen untukmu. "
            "Kalau ingin kembali memesan, kami siap membantu memilih menu yang sesuai."
        )
    return (
        f"Halo {greeting}, sudah beberapa waktu sejak pesanan terakhirmu di Dova Kitchen. "
        "Mau melihat pilihan menu terbaru yang sesuai profilmu?"
    )


def _is_control_group(customer_id: str, *, seed: str, percent: int) -> bool:
    """Assign a stable bucket without random state or PII in the seed."""

    if percent <= 0:
        return False
    digest = hashlib.sha256(f"{seed}:{customer_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100 < percent


def build_winback_campaign_draft(
    churn_report: dict[str, Any],
    *,
    channel: str = "telegram",
    max_recipients: int = 100,
    control_group_percent: int = 0,
    rate_limit_per_minute: int = 20,
) -> dict[str, Any]:
    """Build a deterministic draft without persisting or sending anything."""

    channel = str(channel or "").strip().lower()
    if channel not in ALLOWED_CHANNELS:
        raise ValueError("Channel harus whatsapp atau telegram.")
    if not isinstance(max_recipients, int) or not 1 <= max_recipients <= 1000:
        raise ValueError("max_recipients harus berada pada rentang 1 sampai 1000.")
    if not isinstance(control_group_percent, int) or not 0 <= control_group_percent <= 50:
        raise ValueError("control_group_percent harus berada pada rentang 0 sampai 50.")
    if not isinstance(rate_limit_per_minute, int) or not 1 <= rate_limit_per_minute <= 600:
        raise ValueError("rate_limit_per_minute harus berada pada rentang 1 sampai 600.")

    base: dict[str, Any] = {
        "status": "BLOCKED",
        "campaign_type": CAMPAIGN_TYPE,
        "channel": channel,
        "calculation_version": CALCULATION_VERSION,
        "data_mode": churn_report.get("data_mode", ""),
        "source": churn_report.get("source", ""),
        "source_calculation_version": churn_report.get("calculation_version", ""),
        "as_of": churn_report.get("as_of", ""),
        "latest_order_date": churn_report.get("latest_order_date"),
        "data_age_days": churn_report.get("data_age_days"),
        "freshness_status": churn_report.get("freshness_status", "UNKNOWN"),
        "control_group_percent": control_group_percent,
        "rate_limit_per_minute": rate_limit_per_minute,
        "audience": [],
        "excluded": {},
        "audience_count": 0,
        "sendable_count": 0,
        "control_group_count": 0,
        "warnings": [],
    }

    if churn_report.get("status") != "BASELINE_ONLY" or churn_report.get("data_mode") != "live":
        base["warnings"] = [
            "Campaign hanya boleh dibuat dari baseline churn live yang terprovenance."
        ]
        return base

    freshness = churn_report.get("freshness_status")
    data_age = churn_report.get("data_age_days")
    if freshness != "FRESH" or not isinstance(data_age, int) or data_age > FRESHNESS_MAX_DAYS:
        base["status"] = "BLOCKED_STALE_DATA"
        base["warnings"] = [
            "Data churn stale; refresh transaksi paid sebelum membuat campaign win-back."
        ]
        return base

    excluded: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    for row in churn_report.get("customers", []):
        risk_band = str(row.get("risk_band") or "UNKNOWN")
        if risk_band not in TARGET_RISK_BANDS:
            excluded["risk_band_not_targeted"] = excluded.get("risk_band_not_targeted", 0) + 1
            continue
        if not bool(row.get("marketing_opt_in", False)):
            excluded["consent_missing"] = excluded.get("consent_missing", 0) + 1
            continue
        if not str(row.get("phone") or "").strip():
            excluded["phone_missing"] = excluded.get("phone_missing", 0) + 1
            continue
        if channel == "telegram" and (
            not bool(row.get("telegram_verified", False))
            or row.get("telegram_chat_id") in (None, "")
        ):
            excluded["telegram_not_verified"] = excluded.get("telegram_not_verified", 0) + 1
            continue
        candidates.append(row)

    risk_order = {"HIGH": 0, "MEDIUM": 1}
    candidates.sort(
        key=lambda row: (
            risk_order.get(str(row.get("risk_band")), 99),
            -int(row.get("recency_days") or 0),
            str(row.get("customer_id") or ""),
        )
    )
    audience: list[dict[str, Any]] = []
    for row in candidates[:max_recipients]:
        customer_id = str(row["customer_id"])
        is_control_group = _is_control_group(
            customer_id,
            seed=f"{CAMPAIGN_TYPE}:{base['as_of']}",
            percent=control_group_percent,
        )
        audience.append(
            {
                "customer_id": customer_id,
                "recipient_name": str(row.get("name") or "Pelanggan"),
                "recipient_phone": str(row["phone"]).strip(),
                "recipient_chat_id": row.get("telegram_chat_id"),
                "risk_band": str(row["risk_band"]),
                "recency_days": int(row.get("recency_days") or 0),
                "reason_codes": list(row.get("reason_codes") or []),
                "message": _message(str(row.get("name") or "Pelanggan"), str(row["risk_band"])),
                "is_control_group": is_control_group,
            }
        )

    if len(candidates) > max_recipients:
        excluded["max_recipients"] = len(candidates) - max_recipients
    base["excluded"] = excluded
    base["audience"] = audience
    base["audience_count"] = len(audience)
    base["control_group_count"] = sum(1 for row in audience if row["is_control_group"])
    base["sendable_count"] = len(audience) - base["control_group_count"]
    if not audience or base["sendable_count"] == 0:
        base["status"] = "NO_ELIGIBLE_RECIPIENTS"
        base["warnings"] = [
            "Tidak ada customer target yang dapat dikirimi setelah consent, kanal, dan control group gate."
        ]
        return base

    base["status"] = "DRAFT"
    base["warnings"] = [
        "Draft menunggu review dan approval admin; belum ada pesan yang dikirim."
    ]
    return base


def build_live_winback_campaign_draft(
    *,
    channel: str = "telegram",
    max_recipients: int = 100,
    control_group_percent: int = 0,
    rate_limit_per_minute: int = 20,
) -> dict[str, Any]:
    """Build a draft from the live churn baseline only."""

    from app.services.churn_service import build_churn_report

    return build_winback_campaign_draft(
        build_churn_report(),
        channel=channel,
        max_recipients=max_recipients,
        control_group_percent=control_group_percent,
        rate_limit_per_minute=rate_limit_per_minute,
    )


def persist_campaign_draft(draft: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
    """Persist a DRAFT and recipients atomically; never persist blocked output."""

    if draft.get("status") != "DRAFT":
        raise MarketingUnavailable("Campaign belum memenuhi gate untuk dipersist.")
    if draft.get("data_mode") != "live" or draft.get("source") != "supabase_postgres":
        raise MarketingUnavailable("Campaign harus bersumber dari data live Supabase.")
    audience = list(draft.get("audience") or [])
    if not audience:
        raise MarketingUnavailable("Audience campaign kosong.")

    campaign_id = f"cmp_{uuid.uuid4().hex[:24]}"
    as_of = draft.get("as_of") or None
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO marketing_campaigns
                    (campaign_id, campaign_type, status, channel,
                     data_mode, source, calculation_version,
                     source_calculation_version, source_as_of, data_age_days,
                     audience_count, excluded_count, control_group_percent,
                     rate_limit_per_minute, created_by)
                VALUES (%s, %s, 'DRAFT', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING campaign_id, status, created_at
                """,
                (
                    campaign_id,
                    CAMPAIGN_TYPE,
                    draft["channel"],
                    draft["data_mode"],
                    draft["source"],
                    draft["calculation_version"],
                    draft["source_calculation_version"],
                    as_of,
                    draft.get("data_age_days"),
                    len(audience),
                    sum(draft.get("excluded", {}).values()),
                    int(draft["control_group_percent"]),
                    int(draft["rate_limit_per_minute"]),
                    actor_id,
                ),
            )
            row = cur.fetchone() or {}
            for recipient in audience:
                cur.execute(
                    """
                    INSERT INTO marketing_campaign_recipients
                        (campaign_id, customer_id, recipient_name, recipient_phone,
                         recipient_chat_id, risk_band, reason_codes, message,
                         is_control_group, status, idempotency_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                            CASE WHEN %s THEN 'SKIPPED' ELSE 'PENDING_REVIEW' END, %s)
                    """,
                    (
                        campaign_id,
                        recipient["customer_id"],
                        recipient["recipient_name"],
                        recipient["recipient_phone"],
                        recipient.get("recipient_chat_id"),
                        recipient["risk_band"],
                        Json(recipient["reason_codes"]),
                        recipient["message"],
                        bool(recipient["is_control_group"]),
                        bool(recipient["is_control_group"]),
                        f"{campaign_id}:{recipient['customer_id']}",
                    ),
                )
    return {
        **draft,
        "campaign_id": campaign_id,
        "status": "DRAFT",
        "created_by": actor_id,
        "created_at": row.get("created_at"),
    }


def list_campaigns(*, limit: int = 100) -> list[dict[str, Any]]:
    if not 1 <= limit <= 500:
        raise ValueError("limit harus berada pada rentang 1 sampai 500.")
    return db.execute(
        """
        SELECT campaign_id, campaign_type, status, channel, data_mode, source,
               calculation_version, source_calculation_version, source_as_of,
               data_age_days, audience_count, excluded_count,
               control_group_percent, rate_limit_per_minute, created_by,
               approved_by, created_at, approved_at, queued_at
        FROM marketing_campaigns
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def approve_campaign(campaign_id: str, *, actor_id: str) -> dict[str, Any]:
    row = db.execute_one(
        """
        UPDATE marketing_campaigns
        SET status = 'APPROVED', approved_by = %s, approved_at = NOW()
        WHERE campaign_id = %s AND status = 'DRAFT'
        RETURNING campaign_id, status, approved_by, approved_at
        """,
        (actor_id, campaign_id),
    )
    if not row:
        raise MarketingUnavailable("Campaign tidak ditemukan atau bukan berstatus DRAFT.")
    return row


def queue_campaign(campaign_id: str) -> dict[str, Any]:
    """Move APPROVED recipients to PENDING outbox entries idempotently."""

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT campaign_id, status, channel, rate_limit_per_minute FROM marketing_campaigns WHERE campaign_id = %s FOR UPDATE",
                (campaign_id,),
            )
            campaign = cur.fetchone()
            if not campaign:
                raise MarketingUnavailable("Campaign tidak ditemukan.")
            if campaign["status"] == "QUEUED":
                cur.execute(
                    "SELECT COUNT(*) AS n FROM marketing_campaign_recipients WHERE campaign_id = %s AND status = 'QUEUED'",
                    (campaign_id,),
                )
                return {
                    "campaign_id": campaign_id,
                    "status": "QUEUED",
                    "queued_count": int(cur.fetchone()["n"]),
                    "rate_limit_per_minute": int(campaign["rate_limit_per_minute"]),
                    "delivery_status": "PENDING",
                }
            if campaign["status"] != "APPROVED":
                raise MarketingUnavailable("Campaign harus di-approve sebelum di-queue.")
            cur.execute(
                "SELECT * FROM marketing_campaign_recipients WHERE campaign_id = %s AND status = 'PENDING_REVIEW' FOR UPDATE",
                (campaign_id,),
            )
            recipients = cur.fetchall()
            queued_count = 0
            for recipient in recipients:
                cur.execute(
                    """
                    INSERT INTO notification_outbox
                        (recipient_type, recipient_phone, recipient_name, channel,
                         event_type, message, status, campaign_id, idempotency_key)
                    VALUES ('customer', %s, %s, %s, 'MARKETING_CAMPAIGN', %s,
                            'PENDING', %s, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (
                        recipient["recipient_phone"],
                        recipient["recipient_name"],
                        campaign["channel"],
                        recipient["message"],
                        campaign_id,
                        recipient["idempotency_key"],
                    ),
                )
                cur.execute(
                    "UPDATE marketing_campaign_recipients SET status = 'QUEUED', queued_at = NOW() WHERE id = %s",
                    (recipient["id"],),
                )
                queued_count += 1
            cur.execute(
                "UPDATE marketing_campaigns SET status = 'QUEUED', queued_at = NOW() WHERE campaign_id = %s",
                (campaign_id,),
            )
    return {
        "campaign_id": campaign_id,
        "status": "QUEUED",
        "queued_count": queued_count,
        "rate_limit_per_minute": int(campaign["rate_limit_per_minute"]),
        "delivery_status": "PENDING",
    }


def sign_delivery_payload(raw_body: bytes, secret: str) -> str:
    configured = (secret or "").strip()
    if not configured:
        raise PermissionError_("MARKETING_DELIVERY_WEBHOOK_SECRET belum dikonfigurasi.")
    digest = hmac.new(configured.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_delivery_signature(raw_body: bytes, signature: str, secret: str | None = None) -> bool:
    configured = (secret if secret is not None else settings.marketing_delivery_webhook_secret).strip()
    if not configured or not signature:
        return False
    candidate = signature.strip().lower()
    expected = sign_delivery_payload(raw_body, configured).lower()
    return hmac.compare_digest(expected, candidate)


def process_delivery_webhook(
    payload: MarketingDeliveryWebhookIn,
    *,
    raw_body: bytes,
    signature: str,
) -> dict[str, Any]:
    """Apply a signed provider callback; duplicate event delivery is harmless."""

    if not verify_delivery_signature(raw_body, signature):
        raise PermissionError_("Signature delivery webhook tidak valid.")
    if payload.status not in DELIVERY_STATUSES:
        raise ValidationError("Status delivery tidak dikenal.")

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, campaign_id, status, provider_event_id
                FROM notification_outbox
                WHERE id = %s
                FOR UPDATE
                """,
                (payload.outbox_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValidationError("Outbox delivery tidak ditemukan.")
            if row.get("provider_event_id") == payload.event_id:
                return {"outbox_id": payload.outbox_id, "status": row["status"], "duplicate": True}
            if row["status"] != "PENDING":
                raise ConflictError("Outbox delivery sudah memiliki status final berbeda.")

            now_column = "sent_at" if payload.status == "SENT" else "failed_at"
            cur.execute(
                f"""
                UPDATE notification_outbox
                   SET status = %s,
                       provider_message_id = %s,
                       provider_event_id = %s,
                       failure_reason = %s,
                       {now_column} = NOW(),
                       last_callback_at = NOW()
                 WHERE id = %s
                """,
                (
                    payload.status,
                    payload.provider_message_id or None,
                    payload.event_id,
                    payload.failure_reason,
                    payload.outbox_id,
                ),
            )
            if row.get("campaign_id"):
                recipient_status = payload.status
                cur.execute(
                    f"""
                    UPDATE marketing_campaign_recipients
                       SET status = %s,
                           sent_at = {"NOW()" if payload.status == "SENT" else "sent_at"},
                           failure_reason = %s
                     WHERE campaign_id = %s
                       AND idempotency_key = (
                           SELECT idempotency_key FROM notification_outbox WHERE id = %s
                       )
                    """,
                    (recipient_status, payload.failure_reason, row["campaign_id"], payload.outbox_id),
                )
    return {"outbox_id": payload.outbox_id, "status": payload.status, "duplicate": False}


def cancel_campaign(campaign_id: str, *, actor_id: str) -> dict[str, Any]:
    row = db.execute_one(
        """
        UPDATE marketing_campaigns
        SET status = 'CANCELLED', approved_by = COALESCE(approved_by, %s)
        WHERE campaign_id = %s AND status IN ('DRAFT', 'APPROVED')
        RETURNING campaign_id, status
        """,
        (actor_id, campaign_id),
    )
    if not row:
        raise MarketingUnavailable("Campaign tidak ditemukan atau sudah diproses.")
    return row


__all__ = [
    "CALCULATION_VERSION",
    "MarketingUnavailable",
    "build_winback_campaign_draft",
    "build_live_winback_campaign_draft",
    "persist_campaign_draft",
    "list_campaigns",
    "approve_campaign",
    "queue_campaign",
    "cancel_campaign",
    "sign_delivery_payload",
    "verify_delivery_signature",
    "process_delivery_webhook",
]
