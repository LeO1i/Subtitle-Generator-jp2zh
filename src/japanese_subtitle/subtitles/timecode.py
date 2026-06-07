from __future__ import annotations

import datetime


def format_srt_time(seconds: float) -> str:
    td = datetime.timedelta(seconds=max(0.0, seconds))
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    sec = td.total_seconds() % 60
    milliseconds = int((sec % 1) * 1000)
    sec = int(sec)
    return f"{hours:02d}:{minutes:02d}:{sec:02d},{milliseconds:03d}"


def format_ass_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole_seconds = int(seconds % 60)
    centiseconds = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"
