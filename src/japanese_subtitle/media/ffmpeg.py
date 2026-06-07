"""Shared FFmpeg / FFprobe helpers used by multiple modules."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def subprocess_kwargs():
    """Return extra kwargs for subprocess calls (hides console window on Windows)."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _bundled_binary(name):
    candidates = []
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                executable_dir / "ffmpeg" / name,
                executable_dir / "_internal" / "ffmpeg" / name,
            ]
        )
        bundle_root = Path(getattr(sys, "_MEIPASS", executable_dir))
        candidates.append(bundle_root / "ffmpeg" / name)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def find_ffmpeg():
    """Locate ffmpeg, preferring bundled binaries in packaged builds."""
    ffmpeg_bin = _bundled_binary("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    fallback = "C:/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe"
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError("未在 PATH 或默认路径中找到 ffmpeg")


def find_ffprobe():
    """Locate ffprobe, preferring bundled binaries in packaged builds."""
    ffprobe_bin = _bundled_binary("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if ffprobe_bin:
        return ffprobe_bin
    ffprobe_bin = shutil.which("ffprobe")
    if ffprobe_bin:
        return ffprobe_bin
    fallback = "C:/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffprobe.exe"
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError("未在 PATH 或默认路径中找到 ffprobe")
