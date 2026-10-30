"""Run the isolated Phase 11 acceptance scenario without writing to Supabase.

This is deliberately a deterministic contract demo, not a production smoke
test. Every row is marked SIMULATED so the report cannot be mistaken for live
orders, stock, invoices, or payments.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    # Make `python backend/scripts/run_phase_acceptance_demo.py` work from the
    # repository root without requiring an editable package install.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.production_batch_service import _grams
from app.services.procurement_service import build_purchase_order_drafts


def run() -> dict:
    portions = 100
    recipe = {
        "recipe_status": "VERIFIED",
        "yield_portions": 1,
        "components": [
            {"ingredient_id": "ing-chicken", "ingredient_name": "Ayam", "quantity_g": 150},
            {"ingredient_id": "ing-rice", "ingredient_name": "Beras", "quantity_g": 100},
        ],
    }
    planned = {
        component["ingredient_id"]: _grams(
            component["quantity_g"] * portions / recipe["yield_portions"], "g"
        )
        for component in recipe["components"]
    }
    actual = {"ing-chicken": 15_200.0, "ing-rice": 10_000.0}
    opening_stock = {"ing-chicken": 30_000.0, "ing-rice": 20_000.0}
    closing_stock = {
        ingredient_id: opening_stock[ingredient_id] - actual[ingredient_id]
        for ingredient_id in actual
    }
    sourcing_report = {
        "status": "OK",
        "data_mode": "live",
        "source": "supabase_postgres",
        "need_by_date": "2026-10-31",
        "items": [
            {
                "ingredient_id": "ing-chicken",
                "ingredient_name": "Ayam",
                "shortage_quantity": 5,
                "unit": "kg",
                "recommended_supplier": {
                    "supplier_id": "sup-a",
                    "supplier_name": "Supplier A",
                    "unit": "kg",
                    "moq": 5,
                    "price_per_unit": 100_000,
                    "lead_time_days": 1,
                    "rating": 4.5,
                },
            }
        ],
    }
    po = build_purchase_order_drafts(sourcing_report)[0]
    receipt_qty = po["items"][0]["qty"]
    expected_invoice = receipt_qty * po["items"][0]["unit_price"]
    invoice_amount = expected_invoice
    delivery = ["PLANNED", "ASSIGNED", "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED"]

    result = {
        "status": "PASS",
        "data_mode": "SIMULATED",
        "source": "isolated_phase_acceptance_demo",
        "service_date": str(date(2026, 10, 31)),
        "recipe": {"status": recipe["recipe_status"], "portions": portions},
        "batch": {
            "planned_grams": planned,
            "actual_grams": actual,
            "variance_grams": {key: actual[key] - planned[key] for key in actual},
            "closing_stock_grams": closing_stock,
            "status": "COMPLETED",
        },
        "purchase_order": {
            "supplier_id": po["supplier_id"],
            "items": po["items"],
            "approval_required": True,
        },
        "goods_receipt": {
            "status": "POSTED",
            "quantity": receipt_qty,
            "internal_lot_barcode": "LOT-SIMULATED-CHICKEN",
        },
        "supplier_invoice": {
            "payment_terms": "WEEKLY_INVOICE",
            "expected_amount": expected_invoice,
            "invoice_amount": invoice_amount,
            "match_status": "MATCHED",
            "payment_status": "APPROVED_PENDING_MANUAL_PAYMENT",
        },
        "delivery": {"status_path": delivery, "gps_provider": "NOT_CONFIGURED"},
        "live_gates": {
            "supabase_extension_migrations": "PENDING_BACKUP_GATE",
            "recipe_operator_verification": "REQUIRED",
            "payment_provider": "NOT_CONFIGURED",
            "langflow_provider": "DEGRADED_LIVE_PROBE",
        },
    }
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
