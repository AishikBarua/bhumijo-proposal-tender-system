"""One logging setup for the whole system — console plus a rotating file."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .settings import settings

_CONFIGURED = False
_FORMAT = "[%(asctime)s] %(levelname)-7s %(name)-22s %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings.ensure_dirs()
    root = logging.getLogger("bhumijo")
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.log_dir / "bhumijo.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"bhumijo.{name}")
