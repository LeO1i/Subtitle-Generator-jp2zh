from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "_MEIPASS", None):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parents[3]
    return base_path / relative_path


def app_icon():
    from PySide6.QtGui import QIcon

    for relative_path in ("assets/app.ico", "assets/app.svg"):
        path = resource_path(relative_path)
        if path.exists():
            return QIcon(str(path))
    return QIcon()
