"""Koneksi Supabase (Postgres) — menggantikan repositories/astra.py.

Memakai psycopg2 dengan connection pool sederhana (ThreadedConnectionPool).
Kegagalan credential raising DatabaseError dengan pesan jelas — sama seperti
pola yang sudah ada di modul lama.

Credential dibaca dari Settings:
  SUPABASE_URL        — postgres DSN lengkap  ATAU
  SUPABASE_DB_HOST + SUPABASE_DB_PASSWORD  (host dari API endpoint)
  SUPABASE_SERVICE_KEY  — alias alternatif untuk password

Backend selalu memakai service_role sehingga RLS dilewati secara otomatis.
Frontend dan bot Telegram tidak pernah menyentuh database langsung.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
import psycopg2.pool
import psycopg2.extras

from app.core.config import settings
from app.core.errors import DatabaseError
from app.core.logging import get_logger

log = get_logger("dova.repo.supabase")

_lock = threading.Lock()
_pool: psycopg2.pool.ThreadedConnectionPool | None = None

# Tabel yang dikelola aplikasi — dipakai health check.
MANAGED_TABLES = (
    "packages",
    "allergens",
    "menus",
    "menu_ingredients",
    "customers",
    "dietary_passports",
    "orders",
    "order_items",
    "order_status_events",
    "customer_feedback",
)


def _build_dsn() -> str:
    """
    Susun DSN dari variable yang tersedia.

    Urutan prioritas:
    1. SUPABASE_URL — DSN postgres:// lengkap (paling fleksibel)
    2. SUPABASE_DB_API_ENDPOINT + SUPABASE_DB_APPLICATION_TOKEN — nama variable
       yang sudah diisi user.
    """
    if settings.supabase_url:
        return settings.supabase_url.strip()

    host = settings.supabase_db_api_endpoint.strip()
    password = settings.supabase_db_application_token.strip()

    if not host:
        raise DatabaseError(
            "SUPABASE_DB_API_ENDPOINT belum diisi. "
            "Isi host Supabase di .env (mis. db.xxxx.supabase.co)."
        )
    if not password:
        raise DatabaseError(
            "SUPABASE_DB_APPLICATION_TOKEN belum diisi. "
            "Isi service key atau password Supabase di .env."
        )

    # Bersihkan prefix URL bila user mengisi URL lengkap di endpoint
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.rstrip("/")

    db_name = settings.supabase_db_name or "postgres"
    port = settings.supabase_db_port or 5432
    user = settings.supabase_db_user or "postgres"

    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _lock:
        if _pool is not None:
            return _pool
        try:
            dsn = _build_dsn()
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=dsn,
                cursor_factory=psycopg2.extras.RealDictCursor,
                options="-c search_path=public",
                connect_timeout=10,
                sslmode="require",
            )
            log.info("Supabase pool dibuat (minconn=1 maxconn=10)")
        except Exception as exc:
            log.error("Gagal membuat pool Supabase: %s: %s", type(exc).__name__, exc)
            raise DatabaseError(
                "Database tidak tersedia. Periksa SUPABASE_DB_API_ENDPOINT dan "
                "SUPABASE_DB_APPLICATION_TOKEN di .env."
            ) from exc
    return _pool


@contextmanager
def get_conn() -> Generator[Any, None, None]:
    """
    Context manager: ambil koneksi dari pool, kembalikan saat selesai.
    Mendukung auto-recovery jika koneksi stale atau terputus oleh pooler.
    """
    pool = _get_pool()
    conn = None
    try:
        conn = pool.getconn()
        if conn.closed:
            pool.putconn(conn, close=True)
            reset_connection()
            pool = _get_pool()
            conn = pool.getconn()
    except Exception:
        reset_connection()
        pool = _get_pool()
        conn = pool.getconn()

    try:
        yield conn
        conn.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        reset_connection()
        raise DatabaseError("Koneksi database terputus. Silakan coba lagi.") from exc
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        if conn is not None:
            try:
                pool.putconn(conn)
            except Exception:
                pass
        raise
    else:
        if conn is not None:
            try:
                pool.putconn(conn)
            except Exception:
                pass


def execute(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Jalankan query dan kembalikan semua baris sebagai list[dict]. Auto-retry 1x bila broken pipe."""
    for attempt in range(2):
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    if cur.description:
                        return [dict(r) for r in cur.fetchall()]
                    return []
        except DatabaseError:
            if attempt == 0:
                log.warning("Query execute retry setelah koneksi terputus: %s", sql[:60])
                continue
            raise


def execute_one(sql: str, params: tuple | None = None) -> dict[str, Any] | None:
    """Jalankan query dan kembalikan satu baris atau None."""
    rows = execute(sql, params)
    return rows[0] if rows else None


def execute_write(sql: str, params: tuple | None = None) -> int:
    """Jalankan INSERT/UPDATE/DELETE, kembalikan rowcount. Auto-retry 1x bila broken pipe."""
    for attempt in range(2):
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.rowcount
        except DatabaseError:
            if attempt == 0:
                log.warning("Query write retry setelah koneksi terputus: %s", sql[:60])
                continue
            raise


def is_connected() -> bool:
    """Ping database. False bila kredensial/jaringan bermasalah."""
    try:
        execute("SELECT 1")
        return True
    except Exception as exc:
        log.warning("Supabase tidak tersambung: %s: %s", type(exc).__name__, exc)
        reset_connection()
        return False


def check_migrations() -> bool:
    """
    Verifikasi bahwa migrasi 001_schema.sql sudah dijalankan.

    Cara: periksa apakah semua tabel yang dikelola sudah ada di information_schema.
    """
    try:
        rows = execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (list(MANAGED_TABLES),),
        )
        existing = {r["table_name"] for r in rows}
        missing = [t for t in MANAGED_TABLES if t not in existing]
        if missing:
            log.warning("Tabel belum ada (migrasi belum dijalankan?): %s", missing)
            return False
        return True
    except Exception as exc:
        log.warning("check_migrations gagal: %s: %s", type(exc).__name__, exc)
        return False


def count_rows(table: str) -> int | None:
    """Hitung baris tabel. None bila tabel tidak ada atau error."""
    if not table.replace("_", "").isalnum():
        log.warning("Nama tabel tidak aman: %r", table)
        return None
    try:
        row = execute_one(f"SELECT COUNT(*) AS n FROM {table}")  # noqa: S608
        return int(row["n"]) if row else None
    except Exception as exc:
        log.warning("count_rows %s gagal: %s", table, type(exc).__name__)
        return None


def reset_connection() -> None:
    """Buang pool — dipakai setelah kegagalan jaringan atau di tes."""
    global _pool
    with _lock:
        if _pool is not None:
            try:
                _pool.closeall()
            except Exception:
                pass
            _pool = None
