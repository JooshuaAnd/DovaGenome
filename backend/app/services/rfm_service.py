"""Live RFM scoring with explicit provenance and no synthetic fallback."""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Iterable

from app.core.errors import DatabaseError
from app.repositories import supabase as db


CALCULATION_VERSION = "rfm_quantile_v1"
FRESHNESS_THRESHOLD_DAYS = 7


class RfmUnavailable(RuntimeError):
    """RFM output cannot safely advance to an operational snapshot."""


def _as_datetime(value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time(), tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _quantile_score(value: float, values: list[float], *, higher_is_better: bool) -> int:
    """Return a conservative 1–5 score from the cohort's empirical rank."""
    if len(values) < 5 or not values or min(values) == max(values):
        return 3
    if higher_is_better:
        rank = sum(item <= value for item in values) / len(values)
    else:
        rank = sum(item >= value for item in values) / len(values)
    return max(1, min(5, int(math.ceil(rank * 5))))


def _segment(r_score: int, f_score: int, m_score: int, frequency: int) -> tuple[str, str]:
    if r_score >= 4 and f_score >= 4 and m_score >= 4:
        return "Champions", "Beri apresiasi VIP dan akses preview menu baru."
    if r_score >= 3 and f_score >= 3:
        return "Loyal Customers", "Tawarkan paket langganan mingguan yang relevan."
    if r_score >= 4 and f_score <= 2:
        if frequency == 1:
            return "New Customers", "Kirim onboarding dan ajakan pembelian kedua."
        return "Potential Loyalists", "Rekomendasikan variasi menu berdasarkan riwayat."
    if r_score <= 2 and f_score >= 3:
        return "At Risk", "Siapkan draft win-back untuk review admin."
    return "Hibernating", "Siapkan draft re-engagement untuk review admin."


def _load_live_rows() -> list[dict[str, Any]]:
    if not db.is_connected():
        raise DatabaseError("Supabase tidak terhubung; segmentasi RFM live ditahan.")
    if not db.check_migrations():
        raise DatabaseError("Migration aplikasi belum lengkap; segmentasi RFM live ditahan.")
    try:
        return db.execute(
            """
            SELECT c.customer_id,
                   c.display_name,
                   c.phone,
                   c.telegram_chat_id,
                   MAX(o.created_at) AS last_order_date,
                   COUNT(o.order_id)::INTEGER AS frequency,
                   COALESCE(SUM(o.total), 0)::NUMERIC AS monetary
            FROM customers c
            JOIN orders o ON o.customer_id = c.customer_id
            WHERE o.status <> 'CANCELLED'
              AND o.payment_status = 'PAID'
            GROUP BY c.customer_id, c.display_name, c.phone, c.telegram_chat_id
            HAVING COUNT(o.order_id) > 0
            ORDER BY monetary DESC, c.customer_id
            """
        )
    except Exception as exc:
        raise DatabaseError("Data order paid untuk RFM live tidak tersedia.") from exc


def build_rfm_report(
    rows: Iterable[dict[str, Any]] | None = None,
    *,
    as_of: dt.date | None = None,
) -> dict[str, Any]:
    """Build a quantile-scored RFM report from live-shaped rows."""
    source = "supabase_postgres" if rows is None else "test_fixture"
    data_mode = "live" if rows is None else "test"
    raw_rows = list(_load_live_rows() if rows is None else rows)
    evidence_date = as_of or dt.datetime.now(dt.timezone.utc).date()
    if not raw_rows:
        return {
            "status": "NO_DATA",
            "data_mode": data_mode,
            "source": source,
            "calculation_version": CALCULATION_VERSION,
            "as_of": evidence_date.isoformat(),
            "total_analyzed": 0,
            "customers": [],
            "segment_counts": {},
            "warnings": ["Tidak ada order PAID non-CANCELLED untuk cohort RFM."],
        }

    normalised: list[dict[str, Any]] = []
    for row in raw_rows:
        last_dt = _as_datetime(row["last_order_date"])
        normalised.append(
            {
                "customer_id": str(row["customer_id"]),
                "name": str(row.get("display_name") or "Pelanggan"),
                "phone": str(row.get("phone") or ""),
                "telegram_chat_id": row.get("telegram_chat_id"),
                "last_order_date": last_dt,
                "recency_days": max(0, (evidence_date - last_dt.date()).days),
                "frequency": int(row.get("frequency") or 0),
                "monetary": float(row.get("monetary") or 0),
            }
        )

    recency_values = [float(row["recency_days"]) for row in normalised]
    frequency_values = [float(row["frequency"]) for row in normalised]
    monetary_values = [float(row["monetary"]) for row in normalised]
    customers: list[dict[str, Any]] = []
    segment_counts: dict[str, int] = {}

    for row in normalised:
        r_score = _quantile_score(row["recency_days"], recency_values, higher_is_better=False)
        f_score = _quantile_score(row["frequency"], frequency_values, higher_is_better=True)
        m_score = _quantile_score(row["monetary"], monetary_values, higher_is_better=True)
        segment, action = _segment(r_score, f_score, m_score, row["frequency"])
        segment_counts[segment] = segment_counts.get(segment, 0) + 1
        customers.append(
            {
                "customer_id": row["customer_id"],
                "name": row["name"],
                "phone": row["phone"],
                "telegram_chat_id": row.get("telegram_chat_id"),
                "last_order_date": row["last_order_date"].date().isoformat(),
                "recency_days": row["recency_days"],
                "frequency": row["frequency"],
                "monetary": round(row["monetary"], 2),
                "r_score": r_score,
                "f_score": f_score,
                "m_score": m_score,
                "rfm_score": f"{r_score}{f_score}{m_score}",
                "segment": segment,
                "recommended_action": action,
            }
        )

    latest_order = max(row["last_order_date"].date() for row in normalised)
    data_age_days = max(0, (evidence_date - latest_order).days)
    freshness_status = "FRESH" if data_age_days <= FRESHNESS_THRESHOLD_DAYS else "STALE_DATA"
    warnings: list[str] = []
    if len(normalised) < 5:
        warnings.append("Cohort RFM kurang dari 5 customer; skor quantile dinetralkan.")
    if freshness_status == "STALE_DATA":
        warnings.append(
            f"Order paid terbaru berumur {data_age_days} hari; gunakan sebagai historical signal saja."
        )
    return {
        "status": "OK",
        "data_mode": data_mode,
        "source": source,
        "calculation_version": CALCULATION_VERSION,
        "as_of": evidence_date.isoformat(),
        "latest_order_date": latest_order.isoformat(),
        "data_age_days": data_age_days,
        "freshness_status": freshness_status,
        "freshness_threshold_days": FRESHNESS_THRESHOLD_DAYS,
        "total_analyzed": len(customers),
        "customers": customers,
        "segment_counts": segment_counts,
        "warnings": warnings,
    }


def persist_rfm_report(report: dict[str, Any]) -> int:
    """Persist a fresh live RFM cohort with idempotent customer/date keys."""
    if report.get("status") != "OK":
        raise RfmUnavailable(f"RFM berstatus {report.get('status')}; snapshot tidak ditulis.")
    if report.get("data_mode") != "live":
        raise RfmUnavailable("Hanya RFM live yang boleh dipersistenkan.")
    if report.get("source") != "supabase_postgres":
        raise RfmUnavailable("Snapshot RFM hanya boleh berasal dari Supabase live.")
    if report.get("freshness_status") != "FRESH":
        raise RfmUnavailable("Snapshot RFM ditahan karena data paid sudah stale.")
    if not isinstance(report.get("as_of"), str) or not report["as_of"].strip():
        raise RfmUnavailable("Snapshot RFM membutuhkan tanggal evidence yang valid.")

    rows = report.get("customers")
    if not isinstance(rows, list) or not rows:
        raise RfmUnavailable("Snapshot RFM membutuhkan customer cohort yang tidak kosong.")

    persisted = 0
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for row in rows:
                customer_id = str(row.get("customer_id") or "").strip()
                segment = str(row.get("segment") or "").strip()
                if not customer_id or not segment:
                    raise RfmUnavailable("Snapshot RFM memiliki customer atau segment yang kosong.")
                try:
                    recency_days = int(row["recency_days"])
                    frequency = int(row["frequency"])
                    monetary = float(row["monetary"])
                    r_score = int(row["r_score"])
                    f_score = int(row["f_score"])
                    m_score = int(row["m_score"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise RfmUnavailable("Snapshot RFM memiliki nilai numerik yang tidak valid.") from exc
                if recency_days < 0 or frequency < 0 or monetary < 0:
                    raise RfmUnavailable("Snapshot RFM memiliki nilai negatif yang tidak valid.")
                if any(score not in {1, 2, 3, 4, 5} for score in (r_score, f_score, m_score)):
                    raise RfmUnavailable("Snapshot RFM memiliki skor di luar rentang 1 sampai 5.")
                cur.execute(
                    """
                    INSERT INTO rfm_snapshots (
                        customer_id, snapshot_date, recency_days, frequency, monetary,
                        recency_score, frequency_score, monetary_score, segment,
                        data_mode, source, calculation_version
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (customer_id, snapshot_date, calculation_version)
                    DO UPDATE SET recency_days = EXCLUDED.recency_days,
                                  frequency = EXCLUDED.frequency,
                                  monetary = EXCLUDED.monetary,
                                  recency_score = EXCLUDED.recency_score,
                                  frequency_score = EXCLUDED.frequency_score,
                                  monetary_score = EXCLUDED.monetary_score,
                                  segment = EXCLUDED.segment,
                                  data_mode = EXCLUDED.data_mode,
                                  source = EXCLUDED.source
                    """,
                    (
                        customer_id,
                        report["as_of"],
                        recency_days,
                        frequency,
                        monetary,
                        r_score,
                        f_score,
                        m_score,
                        segment,
                        report["data_mode"],
                        report["source"],
                        report["calculation_version"],
                    ),
                )
                persisted += 1
    return persisted


def build_segment_movement(report: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare the current cohort with the latest persisted prior snapshot."""
    current = report or build_rfm_report()
    if current.get("status") != "OK":
        return {
            "status": current.get("status"),
            "data_mode": current.get("data_mode"),
            "source": current.get("source"),
            "calculation_version": current.get("calculation_version"),
            "as_of": current.get("as_of"),
            "previous_snapshot_date": None,
            "summary": {},
            "customers": [],
            "warnings": ["Perpindahan segmen belum dapat dihitung dari report RFM ini."],
        }

    try:
        previous_rows = db.execute(
            """
            SELECT DISTINCT ON (customer_id)
                   customer_id, snapshot_date, segment
            FROM rfm_snapshots
            WHERE snapshot_date < %s
              AND calculation_version = %s
            ORDER BY customer_id, snapshot_date DESC, snapshot_id DESC
            """,
            (current.get("as_of"), current.get("calculation_version")),
        )
    except Exception as exc:
        raise DatabaseError("Snapshot RFM sebelumnya tidak dapat dibaca.") from exc

    prior = {str(row["customer_id"]): row for row in previous_rows}
    movement: list[dict[str, Any]] = []
    summary: dict[str, int] = {}
    for customer in current.get("customers", []):
        customer_id = str(customer["customer_id"])
        previous = prior.get(customer_id)
        if previous is None:
            movement_type = "NO_PREVIOUS"
        elif previous.get("segment") == customer.get("segment"):
            movement_type = "UNCHANGED"
        else:
            movement_type = "CHANGED"
        summary[movement_type] = summary.get(movement_type, 0) + 1
        movement.append(
            {
                "customer_id": customer_id,
                "name": customer.get("name"),
                "previous_snapshot_date": previous.get("snapshot_date") if previous else None,
                "previous_segment": previous.get("segment") if previous else None,
                "current_segment": customer.get("segment"),
                "movement": movement_type,
            }
        )

    previous_dates = [str(row["snapshot_date"]) for row in previous_rows if row.get("snapshot_date")]
    return {
        "status": "OK",
        "data_mode": current.get("data_mode"),
        "source": current.get("source"),
        "calculation_version": current.get("calculation_version"),
        "as_of": current.get("as_of"),
        "previous_snapshot_date": max(previous_dates) if previous_dates else None,
        "summary": summary,
        "customers": movement,
        "warnings": (["Belum ada snapshot RFM sebelumnya untuk dibandingkan."] if not previous_rows else []),
    }


def get_customer_rfm(customer_id: str) -> dict[str, Any]:
    """Return one live RFM row without inventing a default segment."""
    report = build_rfm_report()
    for customer in report["customers"]:
        if customer["customer_id"] == customer_id:
            return {
                **customer,
                "status": report["status"],
                "data_mode": report["data_mode"],
                "source": report["source"],
                "calculation_version": report["calculation_version"],
            }
    return {
        "status": "NO_HISTORY",
        "data_mode": report["data_mode"],
        "source": report["source"],
        "calculation_version": report["calculation_version"],
        "customer_id": customer_id,
        "segment": "NO_HISTORY",
        "recency_days": None,
        "frequency": 0,
        "monetary": 0,
        "r_score": None,
        "f_score": None,
        "m_score": None,
        "rfm_score": None,
        "recommended_action": "Belum ada order PAID yang dapat dinilai.",
    }


__all__ = [
    "CALCULATION_VERSION",
    "FRESHNESS_THRESHOLD_DAYS",
    "RfmUnavailable",
    "build_rfm_report",
    "build_segment_movement",
    "get_customer_rfm",
    "persist_rfm_report",
]
