"""Helper waktu WIB — port dari `data.py` dengan logging dan tanpa bare except."""

from __future__ import annotations

import datetime

from app.core.domain import SLA_LATE_MINUTES, SLA_SOON_MINUTES
from app.core.logging import get_logger

log = get_logger("dova.time")

WIB = datetime.timezone(datetime.timedelta(hours=7))
UTC = datetime.timezone.utc


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def now_wib() -> datetime.datetime:
    return datetime.datetime.now(WIB)


def now_iso() -> str:
    return now_utc().isoformat()


def parse_dt(value: str | datetime.datetime | None) -> datetime.datetime | None:
    """
    Parse ISO-8601 menjadi datetime timezone-aware (UTC bila tanpa offset).

    Nilai yang gagal di-parse dicatat sebagai warning dan menghasilkan None —
    bukan exception, karena data live memang pernah tidak rapi.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        log.warning("Timestamp tidak dapat di-parse, dianggap kosong: %r", value)
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def to_wib(dt: datetime.datetime | None) -> datetime.datetime | None:
    return dt.astimezone(WIB) if dt else None


def fmt_wib(value: str | datetime.datetime | None, *, with_date: bool = False) -> str:
    """Format timestamp menjadi string WIB."""
    dt = to_wib(parse_dt(value))
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y · %H:%M" if with_date else "%H:%M WIB")


def elapsed_minutes(value: str | datetime.datetime | None) -> int:
    """Menit sejak timestamp (minimal 0)."""
    dt = parse_dt(value)
    if dt is None:
        return 0
    return max(0, int((now_utc() - dt).total_seconds() // 60))


def sla_level(minutes: int) -> str:
    """fresh < 20 menit · soon 20–29 · late >= 30 (port dari data.py)."""
    if minutes >= SLA_LATE_MINUTES:
        return "late"
    if minutes >= SLA_SOON_MINUTES:
        return "soon"
    return "fresh"


def is_same_wib_day(value: str | datetime.datetime | None, *, ref: datetime.datetime | None = None) -> bool:
    """True bila timestamp jatuh pada hari yang sama di zona WIB."""
    dt = to_wib(parse_dt(value))
    if dt is None:
        return False
    return dt.date() == (ref or now_wib()).date()


def wib_day_bounds(day: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    """Batas [mulai, selesai) satu hari WIB dalam UTC — untuk query rentang."""
    start_wib = datetime.datetime.combine(day, datetime.time.min, tzinfo=WIB)
    return start_wib.astimezone(UTC), (start_wib + datetime.timedelta(days=1)).astimezone(UTC)


# ── Minggu layanan ──────────────────────────────────────────────────────────
def current_service_monday(*, ref: datetime.datetime | None = None) -> datetime.date:
    """
    Tanggal Senin dari minggu layanan yang sedang berjalan (WIB).

    Katalog menyimpan NAMA hari (`Senin`..`Sabtu`), bukan tanggal. Tanggal kalender
    dihitung dari sini, sekali, di satu tempat — supaya `/menu` dan `/order`
    tidak pernah menampilkan tanggal yang berbeda untuk hari yang sama.

    Minggu dianchor pada Senin.-Minggu sengaja digeser ke Senin berikutnya: Minggu
    bukan hari layanan, jadi bila pelanggan membuka halaman pada hari Minggu dan
    tetap dikasih Senin minggu ini, seluruh hari layanan akan terlewat dan tampil
    sebagai tanggal yang sudah lewat. Dapur baru mulai bergerak lagi pada Senin.
    """
    today = (ref or now_wib()).date()
    # weekday(): Senin=0 … Minggu=6.
    if today.weekday() == 6:
        return today + datetime.timedelta(days=1)
    return today - datetime.timedelta(days=today.weekday())


def service_week_dates(
    days: list[str] | None = None, *, ref: datetime.datetime | None = None
) -> dict[str, str]:
    """
    Peta `nama hari` → tanggal ISO (`YYYY-MM-DD`) untuk minggu layanan berjalan.

    `days` default ke `domain.DAYS`. Hari yang tidak dikenal dilewati, bukan
    dipetakan ke tanggal yang salah.
    """
    from app.core.domain import DAYS

    monday = current_service_monday(ref=ref)
    wanted = [d for d in (days or list(DAYS)) if d in DAYS]
    return {
        day: (monday + datetime.timedelta(days=DAYS.index(day))).isoformat()
        for day in wanted
    }


def service_date_for_day(day: str, *, ref: datetime.datetime | None = None) -> str | None:
    """Tanggal ISO untuk satu hari layanan, atau None bila namanya tak dikenal."""
    return service_week_dates([day], ref=ref).get(day)


_MONTH_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def format_service_date(iso_date: str) -> str:
    """`2026-10-12` → `12 Oktober 2026`. String kosong bila tanggal tidak valid."""
    try:
        parsed = datetime.date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return ""
    return f"{parsed.day} {_MONTH_ID[parsed.month - 1]} {parsed.year}"
