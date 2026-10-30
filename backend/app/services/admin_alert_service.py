"""Idempotent operational alerts for the Admin Telegram channel.

The alert job is deliberately a queue producer.  It reads the live inventory
table, creates one Telegram outbox item per configured admin and date, and
never calls Telegram itself.  A provider worker can safely retry the outbox.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.errors import DatabaseError, ValidationError
from app.repositories import supabase as db
from app.utils.time import now_wib


def _admin_chat_ids(raw: str) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in str(raw or "").split(",") if value.strip()))


def _stock_rows() -> list[dict[str, Any]]:
    try:
        return db.execute(
            """
            SELECT id, ingredient_name, current_stock, min_stock, unit, status, updated_at
            FROM inventory_stocks
            WHERE status IN ('HABIS', 'MENIPIS')
            ORDER BY CASE WHEN status = 'HABIS' THEN 0 ELSE 1 END,
                     ingredient_name
            """
        )
    except Exception as exc:
        raise DatabaseError("Stok live tidak tersedia; alert tidak dibuat.") from exc


def _format_message(rows: list[dict[str, Any]], *, day: date) -> str:
    lines = [f"Alert stok DovaGenome — {day.isoformat()}"]
    for row in rows:
        status = str(row.get("status") or "UNKNOWN")
        lines.append(
            f"- {row.get('ingredient_name') or 'Bahan'}: "
            f"{row.get('current_stock')} {row.get('unit') or ''} "
            f"(minimum {row.get('min_stock')}); {status}"
        )
    lines.append("Tinjau /api/admin/analytics/inventory-replenishment sebelum menyetujui PO.")
    return "\n".join(lines)


def queue_daily_stock_alert(
    *,
    admin_chat_ids: str,
    day: date | None = None,
) -> dict[str, Any]:
    """Queue one alert per admin/day and return an auditable result.

    The idempotency column is introduced by the marketing/outbox migration. If
    it is not live yet, this fails closed instead of creating duplicate alerts.
    """
    chats = _admin_chat_ids(admin_chat_ids)
    if not chats:
        raise ValidationError("TELEGRAM_ADMIN_CHAT_IDS belum dikonfigurasi.")
    alert_day = day or now_wib().date()
    try:
        column = db.execute_one(
            """
            SELECT 1 AS ready
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'notification_outbox'
              AND column_name = 'idempotency_key'
            """
        )
    except Exception as exc:
        raise DatabaseError("Outbox Telegram live tidak tersedia; alert ditahan.") from exc
    if not column:
        raise DatabaseError("Migration outbox idempotency belum diterapkan di Supabase.")

    rows = _stock_rows()
    if not rows:
        return {
            "status": "NO_ALERT",
            "day": alert_day.isoformat(),
            "critical_items": 0,
            "queued": 0,
            "idempotent": False,
            "source": "supabase_postgres",
        }

    message = _format_message(rows, day=alert_day)
    queued = 0
    duplicates = 0
    for chat_id in chats:
        key = f"stock-alert:{alert_day.isoformat()}:{chat_id}"
        try:
            result = db.execute_write(
                """
                INSERT INTO notification_outbox
                    (recipient_type, recipient_phone, recipient_name, channel,
                     event_type, message, status, idempotency_key)
                VALUES ('admin', %s, 'DovaGenome Admin', 'telegram',
                        'CRITICAL_STOCK_ALERT', %s, 'PENDING', %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id
                """,
                (chat_id, message, key),
            )
        except Exception as exc:
            raise DatabaseError("Alert stok gagal dimasukkan ke outbox.") from exc
        if result:
            queued += 1
        else:
            duplicates += 1

    return {
        "status": "QUEUED" if queued else "EXISTING",
        "day": alert_day.isoformat(),
        "critical_items": len(rows),
        "admin_recipients": len(chats),
        "queued": queued,
        "duplicates": duplicates,
        "idempotent": True,
        "source": "supabase_postgres",
        "message": message,
    }
