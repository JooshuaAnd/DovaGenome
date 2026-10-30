"""Transparent supplier ranking for the verified replenishment contract.

This module ranks only candidates already produced by the live inventory
service. It never invents a supplier, price, lead time, rating, quantity, or
purchase order. A draft PO remains blocked unless the upstream forecast/BOM
report is operationally ready.
"""

from __future__ import annotations

import math
from typing import Any


CALCULATION_VERSION = "supplier_sourcing_v1"
SCORING_WEIGHTS = {
    "price": 0.50,
    "lead_time": 0.30,
    "rating": 0.20,
}


class SupplierSourcingUnavailable(RuntimeError):
    """The supplier sourcing report cannot be built from live dependencies."""


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _inverse_score(value: float, values: list[float]) -> float:
    """Return 0..100 where the smallest value is best."""
    low = min(values)
    high = max(values)
    if high == low:
        return 100.0
    return ((high - value) / (high - low)) * 100.0


def rank_supplier_candidates(
    candidates: list[dict[str, Any]],
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Rank complete supplier candidates with a visible, deterministic score.

    Price, lead time, and rating are all required. Incomplete candidates are
    reported as blocked instead of receiving a default score.
    """
    active_weights = {
        key: float(value)
        for key, value in dict(weights or SCORING_WEIGHTS).items()
    }
    if set(active_weights) != set(SCORING_WEIGHTS) or any(
        not math.isfinite(float(value)) or float(value) < 0
        for value in active_weights.values()
    ) or not math.isclose(sum(float(value) for value in active_weights.values()), 1.0):
        raise ValueError("Supplier scoring weights must be non-negative and sum to 1.")

    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in candidates:
        supplier_id = str(candidate.get("supplier_id") or "")
        price = _as_float(candidate.get("price_per_unit"))
        lead_time = _as_float(candidate.get("lead_time_days"))
        rating = _as_float(candidate.get("rating"))
        reasons: list[str] = []
        if not supplier_id:
            reasons.append("supplier_id_missing")
        if price is None or price < 0:
            reasons.append("price_missing_or_invalid")
        if lead_time is None or lead_time < 0:
            reasons.append("lead_time_missing_or_invalid")
        if rating is None or rating < 0 or rating > 5:
            reasons.append("rating_missing_or_invalid")
        if reasons:
            rejected.append({"supplier_id": supplier_id, "reason_codes": reasons})
            continue
        valid.append(
            {
                **candidate,
                "price_per_unit": price,
                "lead_time_days": lead_time,
                "rating": rating,
            }
        )

    if not valid:
        return {
            "status": "REQUIRES_VERIFICATION",
            "weights": active_weights,
            "candidates": [],
            "rejected_candidates": rejected,
            "warnings": ["Tidak ada kandidat supplier dengan harga, lead time, dan rating yang lengkap."],
        }

    prices = [candidate["price_per_unit"] for candidate in valid]
    lead_times = [candidate["lead_time_days"] for candidate in valid]
    ranked: list[dict[str, Any]] = []
    for candidate in valid:
        price_score = _inverse_score(candidate["price_per_unit"], prices)
        lead_time_score = _inverse_score(candidate["lead_time_days"], lead_times)
        rating_score = (candidate["rating"] / 5.0) * 100.0
        total_score = (
            active_weights["price"] * price_score
            + active_weights["lead_time"] * lead_time_score
            + active_weights["rating"] * rating_score
        )
        ranked.append(
            {
                "supplier_id": candidate["supplier_id"],
                "supplier_name": str(candidate.get("supplier_name") or ""),
                "unit": str(candidate.get("unit") or ""),
                "moq": candidate.get("moq"),
                "price_per_unit": candidate["price_per_unit"],
                "lead_time_days": candidate["lead_time_days"],
                "rating": candidate["rating"],
                "score": round(total_score, 4),
                "score_components": {
                    "price": round(price_score, 4),
                    "lead_time": round(lead_time_score, 4),
                    "rating": round(rating_score, 4),
                },
            }
        )

    ranked.sort(key=lambda row: (-row["score"], row["supplier_id"]))
    return {
        "status": "OK",
        "weights": active_weights,
        "candidates": ranked,
        "rejected_candidates": rejected,
        "warnings": [],
    }


def build_supplier_sourcing_report(inventory_report: dict[str, Any]) -> dict[str, Any]:
    """Create a sourcing recommendation from a strict inventory report.

    No numeric sourcing recommendation is emitted while inventory is stale,
    BOM is unverified, or the upstream report is otherwise not operational.
    """
    base = {
        "status": "REQUIRES_VERIFICATION",
        "data_mode": "live",
        "source": inventory_report.get("source", "supabase_postgres"),
        "calculation_version": CALCULATION_VERSION,
        "inventory_status": inventory_report.get("status"),
        "forecast_status": inventory_report.get("forecast_status"),
        "weights": dict(SCORING_WEIGHTS),
        "items": [],
        "draft_po": {
            "status": "BLOCKED",
            "reason_codes": ["INVENTORY_PLAN_NOT_OPERATIONAL"],
            "message": "Draft PO belum dibuat; inventory/BOM/forecast belum memenuhi gate.",
        },
        "warnings": [],
    }

    if inventory_report.get("status") != "OK":
        base["warnings"] = [
            "Supplier sourcing menunggu inventory replenishment berstatus OK.",
        ]
        return base

    sourcing_items: list[dict[str, Any]] = []
    blocked_items: list[dict[str, Any]] = []
    for item in inventory_report.get("items", []):
        shortage = _as_float(item.get("shortage_quantity"))
        if shortage is None or shortage <= 0:
            continue
        ranking = rank_supplier_candidates(item.get("supplier_candidates", []))
        if ranking["status"] != "OK":
            blocked_items.append(
                {
                    "ingredient_id": item.get("ingredient_id"),
                    "reason_codes": ["SUPPLIER_CANDIDATE_INCOMPLETE"],
                    "details": ranking["rejected_candidates"],
                }
            )
            continue
        sourcing_items.append(
            {
                "ingredient_id": item.get("ingredient_id"),
                "ingredient_name": item.get("ingredient_name"),
                "shortage_quantity": shortage,
                "unit": item.get("unit"),
                "recommended_supplier": ranking["candidates"][0],
                "supplier_candidates": ranking["candidates"],
            }
        )

    if blocked_items:
        base["warnings"] = ["Sebagian kandidat supplier belum memiliki field scoring yang lengkap."]
        base["blocked_items"] = blocked_items
        return base

    base["status"] = "OK"
    base["items"] = sourcing_items
    base["draft_po"] = {
        "status": "PREVIEW_ONLY",
        "reason_codes": ["ADMIN_APPROVAL_REQUIRED"],
        "message": "Rekomendasi supplier tersedia; persist draft PO memerlukan endpoint approval terpisah.",
    }
    return base
