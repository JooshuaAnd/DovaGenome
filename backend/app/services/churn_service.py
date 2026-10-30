"""Rule-based churn-risk baseline with explicit provenance.

This is deliberately not a supervised model and does not emit probabilities.
The baseline estimates a customer's normal reorder interval from paid,
non-cancelled orders, then reports an explainable risk band.  A model may only
replace this service after a labelled, time-split evaluation is available.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from statistics import median
from typing import Any, Iterable

from app.core.errors import DatabaseError
from app.repositories import supabase as db


CALCULATION_VERSION = "churn_rule_baseline_v1"
BACKTEST_CALCULATION_VERSION = "churn_rule_baseline_backtest_v1"
FRESHNESS_THRESHOLD_DAYS = 7
MIN_HISTORY_ORDERS = 2
MIN_EXPECTED_INTERVAL_DAYS = 7
AT_RISK_MULTIPLIER = 1.5
CHURN_MULTIPLIER = 3.0
DEFAULT_BACKTEST_HORIZON_DAYS = 30
MIN_BACKTEST_EVALUATION_POINTS = 2


def _as_datetime(value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time(), tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _load_live_rows() -> list[dict[str, Any]]:
    if not db.is_connected():
        raise DatabaseError("Supabase tidak terhubung; baseline churn live ditahan.")
    if not db.check_migrations():
        raise DatabaseError("Migration aplikasi belum lengkap; baseline churn live ditahan.")
    try:
        # Consent marketing belongs to migration 009. Keep the churn baseline
        # readable before that migration, but expose NULL (unknown) rather
        # than inventing opt-in. Marketing eligibility then remains blocked.
        consent_columns = db.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'customers'
              AND column_name IN ('marketing_opt_in')
            """
        )
        has_marketing_opt_in = any(
            row.get("column_name") == "marketing_opt_in" for row in consent_columns
        )
        marketing_opt_in_sql = "c.marketing_opt_in" if has_marketing_opt_in else "NULL::BOOLEAN"
        return db.execute(
            f"""
            SELECT c.customer_id,
                   c.display_name,
                   c.phone,
                   {marketing_opt_in_sql} AS marketing_opt_in,
                   c.telegram_chat_id,
                   c.telegram_verified,
                   o.created_at AS order_date
            FROM customers c
            JOIN orders o ON o.customer_id = c.customer_id
            WHERE o.status <> 'CANCELLED'
              AND o.payment_status = 'PAID'
            ORDER BY c.customer_id, o.created_at
            """
        )
    except Exception as exc:
        raise DatabaseError("Data order paid untuk baseline churn tidak tersedia.") from exc


def _group_history(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "customer_id": "",
            "name": "Pelanggan",
            "phone": "",
            "marketing_opt_in": None,
            "telegram_chat_id": None,
            "telegram_verified": False,
            "order_dates": [],
        }
    )
    for row in rows:
        customer_id = str(row.get("customer_id") or "").strip()
        if not customer_id:
            continue
        item = grouped[customer_id]
        item["customer_id"] = customer_id
        item["name"] = str(row.get("display_name") or row.get("name") or "Pelanggan")
        item["phone"] = str(row.get("phone") or "")
        item["marketing_opt_in"] = row.get("marketing_opt_in")
        item["telegram_chat_id"] = row.get("telegram_chat_id")
        item["telegram_verified"] = bool(row.get("telegram_verified", False))
        dates = row.get("order_dates")
        if dates is None:
            dates = [row.get("order_date") or row.get("created_at")]
        elif isinstance(dates, (str, dt.date, dt.datetime)):
            dates = [dates]
        item["order_dates"].extend(_as_datetime(value) for value in dates if value is not None)
    return sorted(grouped.values(), key=lambda item: item["customer_id"])


def _thresholds(order_dates: list[dt.datetime]) -> tuple[int, int, int | None]:
    if len(order_dates) < MIN_HISTORY_ORDERS:
        return MIN_EXPECTED_INTERVAL_DAYS, 0, None
    gaps = [max(0, (right.date() - left.date()).days) for left, right in zip(order_dates, order_dates[1:])]
    expected_interval = max(MIN_EXPECTED_INTERVAL_DAYS, int(round(median(gaps))))
    at_risk_after = max(14, int(math.ceil(expected_interval * AT_RISK_MULTIPLIER)))
    churn_after = max(30, int(math.ceil(expected_interval * CHURN_MULTIPLIER)))
    return expected_interval, at_risk_after, churn_after


def _classify(
    *,
    recency_days: int,
    expected_interval_days: int,
    at_risk_after_days: int,
    churn_after_days: int | None,
    frequency: int,
) -> tuple[str, int | None, list[str], str]:
    if frequency < MIN_HISTORY_ORDERS or churn_after_days is None:
        return (
            "UNKNOWN",
            None,
            ["INSUFFICIENT_HISTORY"],
            "Belum cukup order paid untuk mengestimasi cadence; jangan kirim win-back otomatis.",
        )
    if recency_days >= churn_after_days:
        return (
            "HIGH",
            min(100, round(recency_days / churn_after_days * 100)),
            ["RECENCY_EXCEEDS_3X_EXPECTED_INTERVAL"],
            "Siapkan draft win-back untuk review admin; tidak ada pengiriman otomatis.",
        )
    if recency_days >= at_risk_after_days:
        return (
            "MEDIUM",
            min(99, round(recency_days / churn_after_days * 100)),
            ["RECENCY_EXCEEDS_1_5X_EXPECTED_INTERVAL"],
            "Siapkan draft re-engagement untuk review admin; tidak ada pengiriman otomatis.",
        )
    return (
        "LOW",
        min(99, round(recency_days / churn_after_days * 100)),
        ["RECENCY_WITHIN_EXPECTED_INTERVAL"],
        f"Monitor cadence; interval historis pelanggan sekitar {expected_interval_days} hari.",
    )


def build_churn_report(
    rows: Iterable[dict[str, Any]] | None = None,
    *,
    as_of: dt.date | None = None,
) -> dict[str, Any]:
    """Build a live or fixture-backed, explainable churn baseline report."""
    source = "supabase_postgres" if rows is None else "test_fixture"
    data_mode = "live" if rows is None else "test"
    histories = _group_history(_load_live_rows() if rows is None else rows)
    evidence_date = as_of or dt.datetime.now(dt.timezone.utc).date()

    if not histories:
        return {
            "status": "NO_DATA",
            "data_mode": data_mode,
            "source": source,
            "calculation_version": CALCULATION_VERSION,
            "methodology": "rule_based_baseline",
            "model_validated": False,
            "as_of": evidence_date.isoformat(),
            "total_analyzed": 0,
            "risk_counts": {},
            "customers": [],
            "warnings": ["Tidak ada order PAID non-CANCELLED untuk baseline churn."],
        }

    customers: list[dict[str, Any]] = []
    risk_counts: dict[str, int] = {}
    all_dates: list[dt.datetime] = []
    for history in histories:
        order_dates = sorted(history["order_dates"])
        if not order_dates:
            continue
        all_dates.extend(order_dates)
        last_order_date = order_dates[-1].date()
        recency_days = max(0, (evidence_date - last_order_date).days)
        expected_interval, at_risk_after, churn_after = _thresholds(order_dates)
        risk_band, risk_index, reason_codes, action = _classify(
            recency_days=recency_days,
            expected_interval_days=expected_interval,
            at_risk_after_days=at_risk_after,
            churn_after_days=churn_after,
            frequency=len(order_dates),
        )
        risk_counts[risk_band] = risk_counts.get(risk_band, 0) + 1
        customers.append(
            {
                "customer_id": history["customer_id"],
                "name": history["name"],
                "phone": history["phone"],
                "marketing_opt_in": history["marketing_opt_in"],
                "telegram_chat_id": history["telegram_chat_id"],
                "telegram_verified": history["telegram_verified"],
                "last_order_date": last_order_date.isoformat(),
                "recency_days": recency_days,
                "frequency": len(order_dates),
                "expected_interval_days": expected_interval,
                "at_risk_after_days": at_risk_after or None,
                "churn_after_days": churn_after,
                "risk_band": risk_band,
                "risk_index": risk_index,
                "reason_codes": reason_codes,
                "recommended_action": action,
            }
        )

    latest_order = max(value.date() for value in all_dates)
    data_age_days = max(0, (evidence_date - latest_order).days)
    freshness_status = "STALE_DATA" if data_age_days > FRESHNESS_THRESHOLD_DAYS else "FRESH"
    warnings = [
        "Ini baseline rule-based, bukan model supervised dan risk_index bukan probabilitas.",
        "Belum ada label churn dan time-split evaluation; jangan menyebut hasil ini model tervalidasi.",
    ]
    if freshness_status == "STALE_DATA":
        warnings.append(
            f"Order paid terbaru berumur {data_age_days} hari; gunakan sebagai historical signal saja."
        )
    return {
        "status": "BASELINE_ONLY",
        "data_mode": data_mode,
        "source": source,
        "calculation_version": CALCULATION_VERSION,
        "methodology": "rule_based_baseline",
        "model_validated": False,
        "as_of": evidence_date.isoformat(),
        "latest_order_date": latest_order.isoformat(),
        "data_age_days": data_age_days,
        "freshness_status": freshness_status,
        "total_analyzed": len(customers),
        "risk_counts": risk_counts,
        "customers": customers,
        "warnings": warnings,
    }


def _binary_metrics(labels: list[int], predictions: list[int], scores: list[float]) -> dict[str, Any]:
    """Return auditable binary metrics, keeping undefined values explicit."""
    true_positive = sum(label == 1 and prediction == 1 for label, prediction in zip(labels, predictions))
    true_negative = sum(label == 0 and prediction == 0 for label, prediction in zip(labels, predictions))
    false_positive = sum(label == 0 and prediction == 1 for label, prediction in zip(labels, predictions))
    false_negative = sum(label == 1 and prediction == 0 for label, prediction in zip(labels, predictions))

    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    precision = ratio(true_positive, true_positive + false_positive)
    recall = ratio(true_positive, true_positive + false_negative)
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    roc_auc: float | None = None
    positives = [(score, label) for score, label in zip(scores, labels) if label == 1]
    negatives = [(score, label) for score, label in zip(scores, labels) if label == 0]
    if positives and negatives:
        wins = sum(1 for positive, _ in positives for negative, _ in negatives if positive > negative)
        ties = sum(1 for positive, _ in positives for negative, _ in negatives if positive == negative)
        roc_auc = round((wins + 0.5 * ties) / (len(positives) * len(negatives)), 4)

    return {
        "sample_count": len(labels),
        "positive_count": sum(labels),
        "negative_count": len(labels) - sum(labels),
        "predicted_positive_count": sum(predictions),
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": roc_auc,
        "undefined_metrics": [
            name
            for name, value in {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "roc_auc": roc_auc,
            }.items()
            if value is None
        ],
    }


def build_churn_backtest(
    rows: Iterable[dict[str, Any]] | None = None,
    *,
    as_of: dt.date | None = None,
    horizon_days: int = DEFAULT_BACKTEST_HORIZON_DAYS,
) -> dict[str, Any]:
    """Evaluate the explainable baseline with observed, time-ordered labels.

    A positive label means that a customer had no paid, non-cancelled order in
    the ``horizon_days`` after a historical cutoff.  The cutoff is excluded
    from the future window, and cutoffs after the last observed order are not
    used; this prevents missing future data from being mislabeled as churn.
    This is a baseline backtest, not a trained or validated churn model.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days harus >= 1.")

    source = "supabase_postgres" if rows is None else "test_fixture"
    data_mode = "live" if rows is None else "test"
    histories = _group_history(_load_live_rows() if rows is None else rows)
    evidence_date = as_of or dt.datetime.now(dt.timezone.utc).date()
    all_dates = sorted({order_date.date() for history in histories for order_date in history["order_dates"]})
    if not all_dates:
        return {
            "status": "NO_DATA",
            "data_mode": data_mode,
            "source": source,
            "calculation_version": BACKTEST_CALCULATION_VERSION,
            "methodology": "time_split_observed_label_baseline_backtest",
            "model_validated": False,
            "horizon_days": horizon_days,
            "warnings": ["Tidak ada order PAID non-CANCELLED untuk backtest churn."],
        }

    latest_observed = min(evidence_date, all_dates[-1])
    cutoff_limit = latest_observed - dt.timedelta(days=horizon_days)
    cutoff_dates = [value for value in all_dates if value <= cutoff_limit]
    if len(cutoff_dates) < MIN_BACKTEST_EVALUATION_POINTS:
        return {
            "status": "INSUFFICIENT_DATA",
            "data_mode": data_mode,
            "source": source,
            "calculation_version": BACKTEST_CALCULATION_VERSION,
            "methodology": "time_split_observed_label_baseline_backtest",
            "model_validated": False,
            "horizon_days": horizon_days,
            "latest_observed_date": latest_observed.isoformat(),
            "cutoff_count": len(cutoff_dates),
            "warnings": [
                "Belum ada minimal dua cutoff historis dengan future window lengkap; backtest ditahan.",
            ],
        }

    split_index = max(1, min(len(cutoff_dates) - 1, int(len(cutoff_dates) * 0.7)))
    train_cutoffs = cutoff_dates[:split_index]
    test_cutoffs = cutoff_dates[split_index:]
    observations: list[dict[str, Any]] = []
    for cutoff in cutoff_dates:
        future_end = cutoff + dt.timedelta(days=horizon_days)
        for history in histories:
            order_dates = sorted(order_date.date() for order_date in history["order_dates"])
            before = [value for value in order_dates if value <= cutoff]
            if len(before) < MIN_HISTORY_ORDERS:
                continue
            expected_interval, at_risk_after, churn_after = _thresholds(
                [dt.datetime.combine(value, dt.time(), tzinfo=dt.timezone.utc) for value in before]
            )
            recency_days = max(0, (cutoff - before[-1]).days)
            risk_band, risk_index, reason_codes, _ = _classify(
                recency_days=recency_days,
                expected_interval_days=expected_interval,
                at_risk_after_days=at_risk_after,
                churn_after_days=churn_after,
                frequency=len(before),
            )
            future_orders = [value for value in order_dates if cutoff < value <= future_end]
            observations.append(
                {
                    "customer_id": history["customer_id"],
                    "cutoff_date": cutoff.isoformat(),
                    "label_churn": not future_orders,
                    "predicted_churn": risk_band == "HIGH",
                    "risk_score": float(risk_index or 0),
                    "risk_band": risk_band,
                    "reason_codes": reason_codes,
                }
            )

    train_observations = [item for item in observations if item["cutoff_date"] <= train_cutoffs[-1].isoformat()]
    test_observations = [item for item in observations if item["cutoff_date"] >= test_cutoffs[0].isoformat()]
    if len(test_observations) < MIN_BACKTEST_EVALUATION_POINTS:
        return {
            "status": "INSUFFICIENT_DATA",
            "data_mode": data_mode,
            "source": source,
            "calculation_version": BACKTEST_CALCULATION_VERSION,
            "methodology": "time_split_observed_label_baseline_backtest",
            "model_validated": False,
            "horizon_days": horizon_days,
            "cutoff_count": len(cutoff_dates),
            "train_cutoff_end": train_cutoffs[-1].isoformat(),
            "test_cutoff_start": test_cutoffs[0].isoformat(),
            "train_observation_count": len(train_observations),
            "test_observation_count": len(test_observations),
            "warnings": ["Holdout time-split belum memiliki minimal dua customer-cutoff observation."],
        }

    labels = [int(item["label_churn"]) for item in test_observations]
    predictions = [int(item["predicted_churn"]) for item in test_observations]
    scores = [item["risk_score"] for item in test_observations]
    latest_order = all_dates[-1]
    data_age_days = max(0, (evidence_date - latest_order).days)
    freshness_status = "STALE_DATA" if data_age_days > FRESHNESS_THRESHOLD_DAYS else "FRESH"
    return {
        "status": "BACKTEST_ONLY",
        "data_mode": data_mode,
        "source": source,
        "calculation_version": BACKTEST_CALCULATION_VERSION,
        "methodology": "time_split_observed_label_baseline_backtest",
        "model_validated": False,
        "operational_eligibility": False,
        "horizon_days": horizon_days,
        "label_definition": "no PAID non-CANCELLED order in the horizon after cutoff",
        "latest_observed_date": latest_order.isoformat(),
        "data_age_days": data_age_days,
        "freshness_status": freshness_status,
        "cutoff_count": len(cutoff_dates),
        "train_cutoff_count": len(train_cutoffs),
        "test_cutoff_count": len(test_cutoffs),
        "train_cutoff_end": train_cutoffs[-1].isoformat(),
        "test_cutoff_start": test_cutoffs[0].isoformat(),
        "train_observation_count": len(train_observations),
        "test_observation_count": len(test_observations),
        "metrics": _binary_metrics(labels, predictions, scores),
        "warnings": [
            "Ini backtest baseline dengan label observasi, bukan model supervised yang dilatih.",
            "Risk score hanya ranking baseline dan bukan probabilitas churn.",
            "Hasil tidak boleh dipakai untuk auto-send marketing atau mengubah status customer.",
            *([f"Order paid terbaru berumur {data_age_days} hari; scoring operasional tetap stale."] if freshness_status == "STALE_DATA" else []),
        ],
    }


__all__ = [
    "BACKTEST_CALCULATION_VERSION",
    "CALCULATION_VERSION",
    "build_churn_backtest",
    "build_churn_report",
]
