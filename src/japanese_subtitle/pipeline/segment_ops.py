from __future__ import annotations

import re

from japanese_subtitle.domain.models import Segment


def looks_like_bad_asr(text: str, duration_seconds: float) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return True
    if re.search(r"(.)\1{5,}", cleaned):
        return True
    duration = max(0.1, float(duration_seconds))
    jp_chars = re.findall(r"[ぁ-んァ-ン一-龯々ー]", cleaned)
    jp_ratio = len(jp_chars) / max(1, len(cleaned))
    if duration >= 1.2 and jp_ratio < 0.18:
        return True
    if len(cleaned) > int(duration * 20):
        return True
    punct_ratio = len(re.findall(r"[^\w\sぁ-んァ-ン一-龯々ー。、「」！？!?\-]", cleaned)) / max(1, len(cleaned))
    return punct_ratio > 0.25


def segment_needs_second_pass(segment: Segment, previous_segment: Segment | None) -> bool:
    confidence = segment.confidence
    text = segment.text.strip()
    overlap_like = previous_segment is not None and previous_segment.end > segment.start
    too_short = len(text) <= 2
    low_confidence = confidence < 0.45
    duration = max(0.1, segment.end - segment.start)
    return overlap_like or too_short or low_confidence or looks_like_bad_asr(text, duration)


def looks_like_single_block(segments: list[Segment], chunk_duration: float) -> bool:
    if len(segments) != 1:
        return False
    segment = segments[0]
    text = segment.text.strip()
    if len(text) < 30:
        return False
    span = max(0.0, segment.end - segment.start)
    return span >= max(20.0, chunk_duration * 0.8)


def split_text_units(text: str, max_chars: int = 40) -> list[str]:
    if not text:
        return []
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    if not normalized:
        return []

    sentence_parts = [part.strip() for part in re.split(r"(?<=[。！？!?])\s*", normalized) if part.strip()]
    units: list[str] = []
    for part in sentence_parts:
        if len(part) <= max_chars:
            units.append(part)
            continue
        cursor = 0
        while cursor < len(part):
            units.append(part[cursor : cursor + max_chars].strip())
            cursor += max_chars
    return [unit for unit in units if unit]


def expand_long_segment(segment: Segment) -> list[Segment]:
    text = segment.text.strip()
    start = segment.start
    end = segment.end
    duration = max(0.1, end - start)

    should_split = duration >= 12.0 or len(text) >= 70
    if not should_split:
        return [segment]

    units = split_text_units(text)
    if len(units) <= 1:
        return [segment]

    weights = [max(1, len(unit)) for unit in units]
    total_weight = float(sum(weights))
    cursor = start
    expanded: list[Segment] = []
    for idx, unit in enumerate(units):
        if idx == len(units) - 1:
            unit_end = end
        else:
            unit_end = cursor + (duration * (weights[idx] / total_weight))
        expanded.append(
            Segment(
                start=max(start, cursor),
                end=max(cursor + 0.1, min(end, unit_end)),
                text=unit,
                confidence=segment.confidence,
                quality_flagged=segment.quality_flagged,
                speaker_id=segment.speaker_id,
            )
        )
        cursor = expanded[-1].end
    return expanded


def merge_boundary_segments(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda item: (item.start, item.end))
    merged = [Segment(**ordered[0].to_dict())]
    for current in ordered[1:]:
        prev = merged[-1]
        same_text = prev.text.strip() == current.text.strip()
        same_speaker = prev.speaker_id == current.speaker_id
        near_boundary = current.start - prev.end <= 1.0
        if same_text and same_speaker and near_boundary:
            prev.end = max(prev.end, current.end)
            prev.confidence = max(prev.confidence, current.confidence)
        elif current.start < prev.end and same_text and same_speaker:
            prev.end = max(prev.end, current.end)
        else:
            merged.append(Segment(**current.to_dict()))
    return merged


def merge_short_context_segments(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return []

    ordered = sorted(segments, key=lambda item: (item.start, item.end))
    merged = [Segment(**ordered[0].to_dict())]

    for current in ordered[1:]:
        prev = merged[-1]
        prev_text = prev.text.strip()
        curr_text = current.text.strip()
        if not prev_text:
            merged[-1] = Segment(**current.to_dict())
            continue
        if not curr_text:
            continue

        gap = current.start - prev.end
        prev_duration = prev.end - prev.start
        combined_duration = current.end - prev.start
        combined_text = f"{prev_text}{curr_text}"
        prev_short = len(prev_text) < 16 or prev_duration < 1.6
        prev_incomplete = not re.search(r"[。！？!?]$", prev_text)
        curr_tiny = len(curr_text) < 10
        same_speaker = prev.speaker_id == current.speaker_id
        can_merge = (
            gap <= 0.45
            and len(combined_text) <= 52
            and combined_duration <= 8.0
            and same_speaker
            and (prev_short or prev_incomplete or curr_tiny)
        )
        if can_merge:
            prev.text = combined_text
            prev.end = max(prev.end, current.end)
            prev.confidence = max(prev.confidence, current.confidence)
            prev.quality_flagged = bool(prev.quality_flagged or current.quality_flagged)
        else:
            merged.append(Segment(**current.to_dict()))

    return merged
