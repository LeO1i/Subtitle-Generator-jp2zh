from __future__ import annotations

import logging
import sys
from typing import Callable

logger = logging.getLogger(__name__)


def configure_stdio_utf8() -> None:
    """Use UTF-8 for console streams on Windows (avoids cp950 logging crashes)."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def emit_progress(callback: Callable[[float, str], None] | None, percent: float, message: str) -> None:
    if callback is None:
        return
    try:
        callback(float(max(0.0, min(100.0, percent))), str(message))
    except Exception:
        logger.debug("Progress callback failed", exc_info=True)


class CallbackLogHandler(logging.Handler):
    """Forward log records to a callback (used by GUI workers)."""

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.callback(self.format(record))
        except Exception:
            # Avoid handleError(): it prints to stderr and can recurse on cp950 Windows consoles.
            pass
