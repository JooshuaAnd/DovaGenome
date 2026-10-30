import pytest

from app.services import procurement_service


def _report():
    return {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "items": [
            {
                "ingredient_id": "ing-a",
                "ingredient_name": "Ayam",
                "shortage_quantity": 6,
                "unit": "kg",
                "recommended_supplier": {
                    "supplier_id": "sup-a",
                    "supplier_name": "Supplier A",
                    "unit": "kg",
                    "moq": 5,
                    "price_per_unit": 100,
                    "lead_time_days": 2,
                    "rating": 4.5,
                },
            },
            {
                "ingredient_id": "ing-b",
                "ingredient_name": "Beras",
                "shortage_quantity": 2,
                "unit": "kg",
                "recommended_supplier": {
                    "supplier_id": "sup-a",
                    "supplier_name": "Supplier A",
                    "unit": "kg",
                    "moq": 5,
                    "price_per_unit": 100,
                    "lead_time_days": 2,
                    "rating": 4.5,
                },
            },
        ],
    }


def test_build_purchase_order_drafts_groups_supplier_and_applies_moq():
    drafts = procurement_service.build_purchase_order_drafts(_report())

    assert len(drafts) == 1
    assert drafts[0]["supplier_id"] == "sup-a"
    assert [item["qty"] for item in drafts[0]["items"]] == [10, 5]
    assert drafts[0]["total_amount"] == 1500


def test_draft_builder_rejects_stale_or_non_live_sourcing():
    for report in (
        {**_report(), "status": "REQUIRES_VERIFICATION"},
        {**_report(), "data_mode": "simulation"},
        {**_report(), "source": "fixture"},
    ):
        with pytest.raises(procurement_service.ProcurementUnavailable):
            procurement_service.build_purchase_order_drafts(report)


def test_draft_builder_rejects_unit_mismatch_instead_of_converting_silently():
    report = _report()
    report["items"][0]["recommended_supplier"]["unit"] = "g"

    with pytest.raises(procurement_service.ProcurementUnavailable, match="unit supplier"):
        procurement_service.build_purchase_order_drafts(report)


def test_draft_creation_requires_bounded_idempotency_key_before_database_write():
    with pytest.raises(procurement_service.ProcurementUnavailable, match="Idempotency-Key"):
        procurement_service.create_draft_purchase_orders(
            _report(), idempotency_key="", actor_id="admin-1"
        )


def test_draft_builder_does_not_invent_need_by_date():
    draft = procurement_service.build_purchase_order_drafts(_report())[0]

    assert draft["need_by_date"] is None


def test_telegram_edit_request_requires_explicit_notes_before_database_write():
    with pytest.raises(procurement_service.ProcurementUnavailable, match="Catatan perubahan"):
        procurement_service.request_purchase_order_changes(
            "po-1", actor_id="admin-1", notes=""
        )

    with pytest.raises(procurement_service.ProcurementUnavailable, match="terlalu panjang"):
        procurement_service.request_purchase_order_changes(
            "po-1", actor_id="admin-1", notes="x" * 1001
        )
