"""Configuration compatibility tests for deployment environment labels."""

from app.core.config import Settings


def test_release_debug_label_is_non_debug():
    assert Settings(debug="release").debug is False


def test_debug_labels_remain_supported():
    assert Settings(debug="true").debug is True


def test_ai_mode_is_explicit_and_validated():
    assert Settings(ai_mode="required_langflow").ai_mode == "required_langflow"
    assert Settings(ai_mode="allow_explicit_fallback").ai_mode == "allow_explicit_fallback"
    assert Settings(ai_mode="disabled").ai_mode == "disabled"


def test_ai_mode_rejects_unknown_values():
    import pytest

    with pytest.raises(ValueError, match="AI_MODE"):
        Settings(ai_mode="silent_fallback")


def test_telegram_procurement_admin_settings_are_explicit():
    settings = Settings(
        telegram_admin_chat_ids="123,456",
        telegram_admin_customer_id="admin-1",
    )
    assert settings.telegram_admin_chat_ids == "123,456"
    assert settings.telegram_admin_customer_id == "admin-1"
