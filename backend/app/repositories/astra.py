"""Koneksi Astra DB.

Menggantikan `data.connect_db` yang mengembalikan `None` diam-diam atas error
apa pun. Di sini kegagalan raising `DatabaseError` dengan pesan jelas.
"""

from __future__ import annotations

import threading
from typing import Any, Iterable

from astrapy import DataAPIClient

from app.core.config import settings
from app.core.domain import (
    COLLECTION_CUSTOMERS,
    COLLECTION_FEEDBACK,
    REQUIRED_COLLECTIONS,
)
from app.core.errors import DatabaseError
from app.core.logging import get_logger

log = get_logger("dova.repo.astra")

_lock = threading.Lock()
_client: DataAPIClient | None = None
_database: Any | None = None


def get_database() -> Any:
    """Koneksi database singleton (thread-safe, lazy)."""
    global _client, _database
    if _database is not None:
        return _database

    with _lock:
        if _database is not None:
            return _database
        try:
            _client = DataAPIClient(settings.astra_db_application_token)
            _database = _client.get_database(settings.astra_db_api_endpoint)
            log.info(
                "Astra DB tersambung: endpoint=%s",
                settings.astra_db_api_endpoint[:12] + "…",
            )
        except Exception as exc:
            log.error("Gagal tersambung ke Astra DB: %s: %s", type(exc).__name__, exc)
            raise DatabaseError(
                "Database tidak tersedia. Periksa ASTRA_DB_API_ENDPOINT dan "
                "ASTRA_DB_APPLICATION_TOKEN di .env."
            ) from exc
        return _database


def is_connected() -> bool:
    try:
        get_database()
        return True
    except DatabaseError:
        return False


#: Semua collection milik aplikasi — legacy + collection baru Phase 2.
#: `FOREIGN_COLLECTIONS` tidak pernah masuk daftar ini.
MANAGED_COLLECTIONS = (
    *REQUIRED_COLLECTIONS,
    COLLECTION_CUSTOMERS,
    COLLECTION_FEEDBACK,
)


def ensure_collections(names: Iterable[str] = MANAGED_COLLECTIONS) -> list[str]:
    """
    Buat collection yang belum ada. Kembalikan daftar yang dibuat.

    Hanya collection milik aplikasi yang boleh dibuat — `FOREIGN_COLLECTIONS`
    tidak pernah disentuh.
    """
    db = get_database()
    try:
        existing = set(db.list_collection_names())
    except Exception as exc:
        log.error("Gagal daftar collection: %s: %s", type(exc).__name__, exc)
        raise DatabaseError("Tidak dapat membaca daftar collection Astra DB.") from exc

    created: list[str] = []
    for name in names:
        if name in existing:
            continue
        try:
            db.create_collection(name)
            created.append(name)
            log.info("Collection dibuat: %s", name)
        except Exception as exc:
            # Race condition antar-instance backend bersifat wajar.
            log.warning("Gagal membuat collection %s: %s: %s", name, type(exc).__name__, exc)
    return created


def get_collection(name: str) -> Any:
    return get_database().get_collection(name)


def list_collection_names() -> list[str]:
    db = get_database()
    try:
        return sorted(db.list_collection_names())
    except Exception as exc:
        log.error("Gagal daftar collection: %s: %s", type(exc).__name__, exc)
        raise DatabaseError("Tidak dapat membaca daftar collection Astra DB.") from exc


def count_documents(name: str) -> int | None:
    """Hitung dokumen. `None` bila collection tidak ada.

    Catatan: build astrapy yang terpasang mewajibkan `upper_bound`.
    """
    try:
        col = get_database().get_collection(name)
    except Exception as exc:
        log.warning("Collection %s tidak dapat diakses: %s", name, type(exc).__name__)
        return None
    try:
        return int(col.count_documents({}, upper_bound=10_000))
    except TypeError:
        try:
            return len(list(col.find({}, limit=10_000)))
        except Exception as exc:
            log.warning("Hitung dokumen %s gagal: %s", name, type(exc).__name__)
            return None
    except Exception as exc:
        log.warning("Hitung dokumen %s gagal: %s: %s", name, type(exc).__name__, exc)
        return None


def reset_connection() -> None:
    """Buang koneksi singleton — dipakai test dan setelah kegagalan jaringan."""
    global _client, _database
    with _lock:
        _client = None
        _database = None
