"""Structured logging with a filter that scrubs secrets from every record."""
from __future__ import annotations

import logging
import sys

from app.core.security import mask_secrets


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = mask_secrets(record.getMessage())
            record.args = ()
        except Exception:  # never let logging break the app
            pass
        return True


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not any(getattr(h, "_saksham", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler._saksham = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        handler.addFilter(SecretFilter())
        root.addHandler(handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx logs full URLs at INFO


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"saksham.{name}")
