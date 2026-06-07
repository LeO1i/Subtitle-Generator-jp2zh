from __future__ import annotations

import logging
from pathlib import Path

from japanese_subtitle.domain.models import Segment
from japanese_subtitle.subtitles.timecode import format_ass_time
from japanese_subtitle.subtitles.wrap import wrap_cjk_text

logger = logging.getLogger(__name__)

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Speaker1,Microsoft YaHei,24,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,100,100,45,1
Style: Speaker2,Microsoft YaHei,24,&H0000FFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,100,100,45,1
Style: Speaker3,Microsoft YaHei,24,&H00FFFF00,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,100,100,45,1
Style: Default,Microsoft YaHei,24,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,100,100,45,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _escape_ass_text(text: str) -> str:
    escaped = str(text or "").replace("\\", "\\\\").replace("{", "(").replace("}", ")")
    return escaped.replace("\n", "\\N")


def _speaker_prefix(speaker_id: str | None) -> str:
    mapping = {"Speaker1": "【A】", "Speaker2": "【B】", "Speaker3": "【C】"}
    return mapping.get(str(speaker_id or ""), "")


def write_chinese_ass(segments: list[Segment], output_path: Path | str) -> None:
    logger.info("正在生成彩色 ASS 中文字幕...")
    cleaned = [segment for segment in segments if segment.zh_text.strip()]
    cleaned.sort(key=lambda item: item.start)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(ASS_HEADER)
        for segment in cleaned:
            speaker_id = segment.speaker_id or "Default"
            style = speaker_id if speaker_id in {"Speaker1", "Speaker2", "Speaker3"} else "Default"
            prefix = _speaker_prefix(speaker_id)
            wrapped = wrap_cjk_text(segment.zh_text.strip(), line_break="\n")
            text = _escape_ass_text(f"{prefix}{wrapped}")
            handle.write(
                "Dialogue: 0,"
                f"{format_ass_time(segment.start)},"
                f"{format_ass_time(segment.end)},"
                f"{style},,0,0,0,,{text}\n"
            )
