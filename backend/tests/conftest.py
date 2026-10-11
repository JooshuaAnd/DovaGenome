"""
conftest.py — setup environment untuk tes unit.

Set minimal env vars supaya Settings() tidak crash saat pytest import
modul app.*. Nilai ini hanya untuk tes; tidak pernah menyentuh DB nyata.
"""

import os
import pytest


# Patch env sebelum modul apapun di-import
os.environ.setdefault("SUPABASE_DB_API_ENDPOINT", "db.test.supabase.co")
os.environ.setdefault("SUPABASE_DB_APPLICATION_TOKEN", "test-token-for-pytest")
os.environ.setdefault("LANGFLOW_API_URL", "http://localhost:7860/api/v1")
os.environ.setdefault("LANGFLOW_API_KEY", "test-langflow-key")
os.environ["DEBUG"] = "false"
os.environ["DEMO_MODE"] = "false"
