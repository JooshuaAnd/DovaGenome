"""Rate limiter sederhana berbasis proses.

Endpoint publik yang menerima kode sekali pakai (mis. tukar kode Telegram)
menjadi sasaran tebak-kode. Rate limit di sini cukup untuk menutup abuse
sederhana pada satu instance.

Batasnya jelas: ini in-memory per proses, jadi kalau backend dijalankan lebih
dari satu worker atau beberapa container, limit efektifnya terpisah. Untuk
produksi multi-instance, pindahkan ke Redis/WAF di lapisan infrastruktur.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import TooManyRequestsError
from app.core.logging import get_logger

log = get_logger("dova.ratelimit")


class SlidingWindowLimiter:
    """Batas N permintaan dalam rentang `window_seconds` terakhir."""

    def __init__(self, limit: int, window_seconds: int, *, name: str) -> None:
        self.limit = limit
        self.window = window_seconds
        self.name = name
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """
        Catat satu percobaan.

        Mengembalikan `(diizinkan, sisa_kuota)`. Sisa kuota membantu frontend
        menampilkan hitung mundur tanpa perlu menebak.
        """
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= self.limit:
                retry_after = max(1, int(self.window - (now - hits[0])) + 1)
                log.warning(
                    "rate_limit_kena key=%s limit=%s retry_after=%ss",
                    key, self.name, retry_after,
                )
                return False, retry_after

            hits.append(now)
            remaining = self.limit - len(hits)

            #_Junk: kunci yang sudah tidak aktif supaya map tidak tumbuh tanpa batas.
            if len(self._hits) > 2048:
                stale = [k for k, v in self._hits.items() if not v or v[-1] < cutoff]
                for k in stale:
                    self._hits.pop(k, None)

            return True, remaining

    def reset(self) -> None:
        """Bersihkan seluruh counter. Dipakai test dan saat reload konfigurasi."""
        with self._lock:
            self._hits.clear()

    def enforce(self, key: str) -> None:
        allowed, retry_after = self.check(key)
        if not allowed:
            raise TooManyRequestsError(
                "Terlalu banyak percobaan. Coba lagi beberapa saat lagi.",
                retry_after=retry_after,
            )


#: Kode linking hanya 8 karakter dan berumur 10 menit, jadi 20 percobaan per
#: 5 menit sudah jauh melebihi kebutuhan bot yang normal.
telegram_link_limiter = SlidingWindowLimiter(20, 300, name="telegram_link")

#: Login staff dipassword-kan, jadi batasnya lebih ketat untuk memperlambat
#: tebak-kata-sandi.
login_limiter = SlidingWindowLimiter(10, 300, name="login")