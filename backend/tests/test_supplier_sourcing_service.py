import pytest

from app.services import supplier_sourcing_service


def _candidate(supplier_id, *, price, lead_time, rating=4.0):
    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_id.title(),
        "unit": "kg",
        "moq": 1,
        "price_per_unit": price,
        "lead_time_days": lead_time,
        "rating": rating,
    }


def test_rank_supplier_candidates_is_explicit_and_deterministic():
    result = supplier_sourcing_service.rank_supplier_candidates(
        [
            _candidate("slow-expensive", price=120, lead_time=4, rating=4.0),
            _candidate("fast-cheap", price=100, lead_time=2, rating=4.0),
        ]
    )

    assert result["status"] == "OK"
    assert result["candidates"][0]["supplier_id"] == "fast-cheap"
    assert result["candidates"][0]["score"] == 96.0
    assert result["weights"] == {"price": 0.5, "lead_time": 0.3, "rating": 0.2}


def test_incomplete_supplier_candidate_is_rejected_without_default_score():
    result = supplier_sourcing_service.rank_supplier_candidates(
        [_candidate("missing-price", price=None, lead_time=1)]
    )

    assert result["status"] == "REQUIRES_VERIFICATION"
    assert result["candidates"] == []
    assert result["rejected_candidates"][0]["reason_codes"] == ["price_missing_or_invalid"]


def test_supplier_report_blocks_draft_po_when_inventory_is_not_operational():
    result = supplier_sourcing_service.build_supplier_sourcing_report(
        {
            "status": "REQUIRES_VERIFICATION",
            "source": "supabase_postgres",
            "forecast_status": "STALE_DATA",
            "items": [],
        }
    )

    assert result["status"] == "REQUIRES_VERIFICATION"
    assert result["items"] == []
    assert result["draft_po"]["status"] == "BLOCKED"


def test_supplier_report_is_preview_only_and_never_persists_po():
    result = supplier_sourcing_service.build_supplier_sourcing_report(
        {
            "status": "OK",
            "source": "supabase_postgres",
            "forecast_status": "OK",
            "items": [
                {
                    "ingredient_id": "ing-a",
                    "ingredient_name": "Ayam",
                    "shortage_quantity": 2,
                    "unit": "kg",
                    "supplier_candidates": [_candidate("sup-a", price=100, lead_time=1)],
                }
            ],
        }
    )

    assert result["status"] == "OK"
    assert result["items"][0]["recommended_supplier"]["supplier_id"] == "sup-a"
    assert result["draft_po"]["status"] == "PREVIEW_ONLY"


def test_invalid_weights_are_rejected():
    with pytest.raises(ValueError, match="sum to 1"):
        supplier_sourcing_service.rank_supplier_candidates([], weights={"price": 1, "lead_time": 0, "rating": 1})
