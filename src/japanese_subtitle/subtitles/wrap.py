from __future__ import annotations

import re

from japanese_subtitle.domain.models import Segment

DEFAULT_MAX_CHARS_PER_LINE = 20
DEFAULT_MAX_LINES = 2
DEFAULT_JA_MAX_CHARS_PER_LINE = 35

_CJK_PUNCT = re.compile(r"(?<=[。！？，、；：])")


def _split_long_unit(unit: str, max_chars: int) -> list[str]:
    if len(unit) <= max_chars:
        return [unit]
    parts: list[str] = []
    cursor = 0
    while cursor < len(unit):
        parts.append(unit[cursor : cursor + max_chars])
        cursor += max_chars
    return [part for part in parts if part]


def _split_into_display_chunks(text: str, max_chars: int) -> list[str]:
    cleaned = re.sub(r"\s+", "", str(text or "").strip())
    if not cleaned:
        return [""]
    if len(cleaned) <= max_chars:
        return [cleaned]

    sentence_parts = [part.strip() for part in _CJK_PUNCT.split(cleaned) if part.strip()]
    if not sentence_parts:
        return _split_long_unit(cleaned, max_chars)

    chunks: list[str] = []
    current = ""
    for part in sentence_parts:
        units = _split_long_unit(part, max_chars)
        for unit in units:
            candidate = f"{current}{unit}" if current else unit
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            if len(unit) <= max_chars:
                current = unit
            else:
                chunks.extend(_split_long_unit(unit, max_chars))
                current = ""
    if current:
        chunks.append(current)
    return chunks or [cleaned]


def wrap_cjk_text(
    text: str,
    max_chars_per_line: int = DEFAULT_MAX_CHARS_PER_LINE,
    max_lines: int = DEFAULT_MAX_LINES,
    line_break: str = "\n",
) -> str:
    cleaned = re.sub(r"\s+", "", str(text or "").strip())
    if not cleaned:
        return ""

    if len(cleaned) <= max_chars_per_line:
        return cleaned

    units: list[str] = []
    for part in _CJK_PUNCT.split(cleaned):
        part = part.strip()
        if not part:
            continue
        units.extend(_split_long_unit(part, max_chars_per_line))

    lines: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
            continue
        if len(current) + len(unit) <= max_chars_per_line:
            current += unit
        else:
            lines.append(current)
            current = unit
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)

    return line_break.join(lines[:max_lines])


def split_segments_for_display(
    segments: list[Segment],
    max_chars_per_line: int = DEFAULT_MAX_CHARS_PER_LINE,
    max_lines: int = DEFAULT_MAX_LINES,
) -> list[Segment]:
    max_display_chars = max_chars_per_line * max_lines
    display_segments: list[Segment] = []

    for segment in segments:
        zh_text = segment.zh_text.strip()
        ja_text = segment.text.strip()
        if not zh_text and not ja_text:
            continue

        if len(zh_text) <= max_display_chars:
            display_segments.append(Segment(**segment.to_dict()))
            continue

        zh_units = _split_into_display_chunks(zh_text, max_display_chars)
        ja_units = _split_into_display_chunks(ja_text, DEFAULT_JA_MAX_CHARS_PER_LINE * max_lines) if ja_text else [""]
        if len(ja_units) < len(zh_units):
            ja_units.extend([""] * (len(zh_units) - len(ja_units)))
        elif len(ja_units) > len(zh_units):
            ja_units = ja_units[: len(zh_units)]

        start = segment.start
        end = segment.end
        duration = max(0.1, end - start)
        weights = [max(1, len(unit)) for unit in zh_units]
        total_weight = float(sum(weights))
        cursor = start

        for index, zh_unit in enumerate(zh_units):
            ja_unit = ja_units[index] if index < len(ja_units) else ""
            if index == len(zh_units) - 1:
                unit_end = end
            else:
                unit_end = cursor + (duration * (weights[index] / total_weight))
            display_segments.append(
                Segment(
                    start=max(start, cursor),
                    end=max(cursor + 0.1, min(end, unit_end)),
                    text=ja_unit or ja_text,
                    zh_text=zh_unit,
                    confidence=segment.confidence,
                    speaker_id=segment.speaker_id,
                    quality_flagged=segment.quality_flagged,
                )
            )
            cursor = display_segments[-1].end

    return display_segments
