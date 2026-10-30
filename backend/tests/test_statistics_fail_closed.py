from __future__ import annotations

from app.services import analytics_ml_service


def test_descriptive_stats_never_invents_rows_when_database_is_empty(monkeypatch):
    monkeypatch.setattr(analytics_ml_service.supabase, "execute", lambda *_args, **_kwargs: [])

    result = analytics_ml_service.calculate_descriptive_statistics()

    assert result["status"] == "UNAVAILABLE"
    assert result["source"] == "supabase_postgres"
    assert result["n"] == 0
    assert result["variables"] == []

