"""
Root conftest — dijalankan SEBELUM semua test.
Override env vars yang mungkin invalid dari .env live SEBELUM Settings di-cache.
"""
import os

# Set SEBELUM pydantic_settings membaca .env
os.environ["DEBUG"] = "false"
os.environ["DEMO_MODE"] = "false"
os.environ["SUPABASE_DB_API_ENDPOINT"] = "db.test.supabase.co"
os.environ["SUPABASE_DB_APPLICATION_TOKEN"] = "test-token-for-pytest"
os.environ["LANGFLOW_API_URL"] = "http://localhost:7860/api/v1"
os.environ["LANGFLOW_API_KEY"] = "test-key"

# Bersihkan lru_cache Settings bila sudah pernah di-load
try:
    from app.core.config import get_settings
    get_settings.cache_clear()
except Exception:
    pass
