"""Logging terstruktur untuk backend DovaGenome.

Event yang wajib tercatat (spec §23):
  order_creation · database_failure · langflow_failure ·
  telegram_failure · kitchen_status_update
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s :: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Pasang satu stream handler ke root logger. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Astrapy/pyTelegramBotAPI/https noisy di INFO.
    for noisy in ("httpx", "httpcore", "urllib3", "telebot", "apscheduler", "astrapy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
