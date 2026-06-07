from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


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
            self.handleError(record)
