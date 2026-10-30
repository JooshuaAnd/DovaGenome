import pytest
import json

from app.core.errors import PermissionError_
from app.services import marketing_service


def _report(*, freshness="FRESH", data_age_days=2, customers=None):
    return {
        "status": "BASELINE_ONLY",
        "data_mode": "live",
        "source": "supabase_postgres",
        "calculation_version": "churn_rule_baseline_v1",
        "as_of": "2026-10-27",
        "latest_order_date": "2026-10-25",
        "data_age_days": data_age_days,
        "freshness_status": freshness,
        "customers": customers or [],
    }


def _customer(customer_id, *, risk_band="HIGH", opt_in=True, telegram=True, phone="+628120000000"):
    return {
        "customer_id": customer_id,
        "name": customer_id.title(),
        "phone": phone,
        "marketing_opt_in": opt_in,
        "telegram_chat_id": 1000 if telegram else None,
        "telegram_verified": telegram,
        "risk_band": risk_band,
        "recency_days": 40,
        "reason_codes": ["RECENCY_EXCEEDS_3X_EXPECTED_INTERVAL"],
    }


def test_winback_draft_is_consent_and_channel_gated():
    report = _report(
        customers=[
            _customer("high-ok"),
            _customer("high-no-consent", opt_in=False),
            _customer("medium-unverified", risk_band="MEDIUM", telegram=False),
            _customer("low", risk_band="LOW"),
        ]
    )

    result = marketing_service.build_winback_campaign_draft(report, channel="telegram")

    assert result["status"] == "DRAFT"
    assert result["audience_count"] == 1
    assert result["audience"][0]["customer_id"] == "high-ok"
    assert result["excluded"] == {
        "consent_missing": 1,
        "telegram_not_verified": 1,
        "risk_band_not_targeted": 1,
    }
    assert "belum ada pesan" in result["warnings"][0]


def test_whatsapp_draft_requires_consent_but_not_telegram_link():
    result = marketing_service.build_winback_campaign_draft(
        _report(customers=[_customer("wa", telegram=False)]), channel="whatsapp"
    )

    assert result["status"] == "DRAFT"
    assert result["audience"][0]["customer_id"] == "wa"


def test_stale_churn_cannot_become_campaign_draft():
    result = marketing_service.build_winback_campaign_draft(
        _report(freshness="STALE_DATA", data_age_days=15, customers=[_customer("stale")])
    )

    assert result["status"] == "BLOCKED_STALE_DATA"
    assert result["audience"] == []
    assert "refresh transaksi paid" in result["warnings"][0]


def test_non_live_or_unknown_consent_is_blocked_without_default_audience():
    report = _report(customers=[_customer("fixture")])
    report["data_mode"] = "test"

    result = marketing_service.build_winback_campaign_draft(report)

    assert result["status"] == "BLOCKED"
    assert result["audience_count"] == 0


def test_empty_or_missing_consent_never_gets_promoted():
    result = marketing_service.build_winback_campaign_draft(
        _report(customers=[_customer("unknown", opt_in=False)])
    )

    assert result["status"] == "NO_ELIGIBLE_RECIPIENTS"
    assert result["audience"] == []
    assert result["excluded"] == {"consent_missing": 1}


def test_invalid_channel_and_recipient_limit_are_rejected():
    with pytest.raises(ValueError, match="whatsapp atau telegram"):
        marketing_service.build_winback_campaign_draft(_report(), channel="email")
    with pytest.raises(ValueError, match="rentang"):
        marketing_service.build_winback_campaign_draft(_report(), max_recipients=0)


def test_control_group_assignment_is_stable_and_not_sent():
    customers = [_customer(f"customer-{index}") for index in range(20)]
    report = _report(customers=customers)

    first = marketing_service.build_winback_campaign_draft(
        report,
        control_group_percent=50,
        rate_limit_per_minute=30,
    )
    second = marketing_service.build_winback_campaign_draft(
        report,
        control_group_percent=50,
        rate_limit_per_minute=30,
    )

    first_buckets = [(row["customer_id"], row["is_control_group"]) for row in first["audience"]]
    second_buckets = [(row["customer_id"], row["is_control_group"]) for row in second["audience"]]
    assert first_buckets == second_buckets
    assert first["control_group_count"] > 0
    assert first["sendable_count"] > 0
    assert first["rate_limit_per_minute"] == 30
    assert all("message" in row for row in first["audience"])


def test_delivery_signature_is_hmac_and_rejects_tampering():
    raw_body = json.dumps(
        {
            "outbox_id": 7,
            "event_id": "evt-1",
            "status": "SENT",
        },
        separators=(",", ":"),
    ).encode()
    signature = marketing_service.sign_delivery_payload(raw_body, "test-secret")

    assert marketing_service.verify_delivery_signature(raw_body, signature, "test-secret")
    assert not marketing_service.verify_delivery_signature(raw_body + b" ", signature, "test-secret")
    assert not marketing_service.verify_delivery_signature(raw_body, signature, "wrong-secret")


def test_invalid_delivery_secret_cannot_create_signature():
    with pytest.raises(PermissionError_, match="MARKETING_DELIVERY_WEBHOOK_SECRET"):
        marketing_service.sign_delivery_payload(b"{}", "")
