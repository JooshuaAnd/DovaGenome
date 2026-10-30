from app.core.config import settings
from app.api.routers.health import health as health_endpoint
from app.schemas.common import HealthPayload
from app.services.langflow_service import LangflowService


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"version": "test"}
        self.text = "redacted-test-body"

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response):
        self.response = response

    def post(self, *_args, **_kwargs):
        return self.response


def _configure_langflow(monkeypatch):
    monkeypatch.setattr(settings, "ai_mode", "required_langflow")
    monkeypatch.setattr(settings, "langflow_api_url", "http://langflow.test/api/v1")
    monkeypatch.setattr(settings, "langflow_api_key", "server-secret")
    monkeypatch.setattr(settings, "langflow_flow_id", "flow-test")
    monkeypatch.setattr(settings, "langflow_max_retries", 0)


def test_langflow_platform_reachable_is_not_flow_execution_proof(monkeypatch):
    _configure_langflow(monkeypatch)
    monkeypatch.setattr(
        "app.services.langflow_service.httpx.get",
        lambda *_args, **_kwargs: FakeResponse(200, {"version": "1.12.3"}),
    )

    result = LangflowService().health()

    assert result["state"] == "CONNECTED"
    assert result["reason_code"] == "platform_reachable_flow_unprobed"
    assert result["flow_execution_proven"] is False
    assert result["flow_id"] == "flow-test"
    assert len(result["trace_id"]) == 32


def test_langflow_probe_proves_readable_flow_output(monkeypatch):
    _configure_langflow(monkeypatch)
    monkeypatch.setattr(
        "app.services.langflow_service.httpx.get",
        lambda *_args, **_kwargs: FakeResponse(200, {"version": "1.12.3"}),
    )
    service = LangflowService()
    monkeypatch.setattr(
        service,
        "_get_client",
        lambda: FakeClient(FakeResponse(200, {"text": "READY"})),
    )

    result = service.health(probe=True)

    assert result["state"] == "CONNECTED"
    assert result["reason_code"] == "flow_execution_ok"
    assert result["flow_execution_proven"] is True
    assert result["probe_requested"] is True


def test_langflow_readiness_distinguishes_disabled_and_misconfigured(monkeypatch):
    service = LangflowService()

    monkeypatch.setattr(settings, "ai_mode", "disabled")
    disabled = service.health()
    assert disabled["state"] == "MOCK"
    assert disabled["reason_code"] == "ai_disabled"

    monkeypatch.setattr(settings, "ai_mode", "required_langflow")
    monkeypatch.setattr(settings, "langflow_api_url", "")
    monkeypatch.setattr(settings, "langflow_api_key", "")
    missing = service.health()
    assert missing["state"] == "MISCONFIGURED"
    assert missing["reason_code"] == "missing_langflow_credentials"


def test_successful_ai_response_has_redacted_trace_metadata(monkeypatch):
    _configure_langflow(monkeypatch)
    service = LangflowService()
    monkeypatch.setattr(
        service,
        "_get_client",
        lambda: FakeClient(FakeResponse(200, {"text": "Jawaban aman"})),
    )

    result = service.ask("test", session_id="s-1")

    assert result.reply == "Jawaban aman"
    assert result.readiness_state == "CONNECTED"
    assert result.reason_code == "flow_execution_ok"
    assert result.provider == "langflow"
    assert result.trace_id
    assert "server-secret" not in result.model_dump_json()


def test_health_payload_never_aliases_supabase_as_astra():
    payload = HealthPayload(
        status="ok",
        version="1",
        environment="test",
        demo_mode=False,
        db_connected=True,
        supabase_connected=True,
    )

    assert payload.database_source == "supabase_postgres"
    assert payload.supabase_connected is True
    assert payload.astra_connected is False
    assert payload.astra_state == "OFFLINE_LEGACY"


def test_health_endpoint_reports_supabase_source_and_read_only_migration_state(monkeypatch):
    monkeypatch.setattr("app.api.routers.health.supabase.is_connected", lambda: True)
    monkeypatch.setattr("app.api.routers.health.supabase.count_rows", lambda _name: 1)
    monkeypatch.setattr("app.api.routers.health.supabase.check_migrations", lambda: True)
    monkeypatch.setattr("app.api.routers.health.supabase.check_phase_migrations", lambda: True)

    result = health_endpoint()

    assert result.db_connected is True
    assert result.supabase_connected is True
    assert result.database_source == "supabase_postgres"
    assert result.migration_status == "verified"
    assert result.astra_connected is False
