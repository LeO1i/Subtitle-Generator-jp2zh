from __future__ import annotations

import logging
from pathlib import Path

from japanese_subtitle.domain.models import Segment
from japanese_subtitle.subtitles.timecode import format_srt_time
from japanese_subtitle.subtitles.wrap import DEFAULT_JA_MAX_CHARS_PER_LINE, wrap_cjk_text

logger = logging.getLogger(__name__)


def write_bilingual_srt(segments: list[Segment], output_path: Path | str) -> None:
    logger.info("正在生成双语字幕...")
    cleaned = [segment for segment in segments if segment.text.strip()]
    cleaned.sort(key=lambda item: item.start)
    with open(output_path, "w", encoding="utf-8") as handle:
        for index, segment in enumerate(cleaned, start=1):
            ja_line = wrap_cjk_text(segment.text.strip(), max_chars_per_line=DEFAULT_JA_MAX_CHARS_PER_LINE)
            zh_line = wrap_cjk_text(segment.zh_text.strip())
            handle.write(f"{index}\n")
            handle.write(f"{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}\n")
            handle.write(f"{ja_line}\n{zh_line}\n\n")
            if index % 20 == 0:
                logger.info("字幕写入进度：%s/%s", index, len(cleaned))
