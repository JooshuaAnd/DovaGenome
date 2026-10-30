from app.core.config import settings
from app.services.langflow_service import LangflowService


def test_required_langflow_mode_does_not_silently_call_rag(monkeypatch):
    monkeypatch.setattr(settings, "ai_mode", "required_langflow")
    monkeypatch.setattr(settings, "langflow_api_url", "")
    monkeypatch.setattr(settings, "langflow_api_key", "")
    monkeypatch.setattr(
        "app.services.rag_ai_service.generate_rag_answer",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("hidden fallback")),
    )

    result = LangflowService().ask("test", session_id="s-1")

    assert result.degraded is True
    assert "ai_mode=required_langflow" in result.message
    assert "fallback=disabled" in result.message


def test_explicit_fallback_mode_is_visible_in_response(monkeypatch):
    monkeypatch.setattr(settings, "ai_mode", "allow_explicit_fallback")
    monkeypatch.setattr(settings, "langflow_api_url", "")
    monkeypatch.setattr(settings, "langflow_api_key", "")
    monkeypatch.setattr(
        "app.services.rag_ai_service.generate_rag_answer",
        lambda **_kwargs: "explicit fallback answer",
    )

    result = LangflowService().ask("test", session_id="s-1")

    assert result.reply == "explicit fallback answer"
    assert result.degraded is True
    assert result.message == "explicit_fallback:not_configured"


def test_provider_quota_error_is_not_presented_as_rag_success(monkeypatch):
    class Response:
        status_code = 429
        text = "RESOURCE_EXHAUSTED"

    class Client:
        def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(settings, "ai_mode", "required_langflow")
    monkeypatch.setattr(settings, "langflow_api_url", "http://langflow.test/api/v1")
    monkeypatch.setattr(settings, "langflow_api_key", "key")
    monkeypatch.setattr(settings, "langflow_max_retries", 0)
    service = LangflowService()
    monkeypatch.setattr(service, "_get_client", lambda: Client())
    monkeypatch.setattr(
        "app.services.rag_ai_service.generate_rag_answer",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("quota fallback")),
    )

    result = service.ask("test", session_id="s-1")

    assert result.degraded is True
    assert "http_429" in result.message
    assert "fallback=disabled" in result.message
