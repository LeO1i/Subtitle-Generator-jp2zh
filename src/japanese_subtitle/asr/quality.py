from __future__ import annotations

import logging

from japanese_subtitle.asr.engine import ASREngine
from japanese_subtitle.domain.models import QualityMode, Segment
from japanese_subtitle.pipeline.segment_ops import looks_like_single_block

logger = logging.getLogger(__name__)


def recover_segments_by_windows(
    asr_engine: ASREngine,
    chunk_audio_path: str,
    chunk_duration: float,
    quality_mode: QualityMode | str,
    audio_filter: str | None = None,
) -> list[Segment]:
    quality = quality_mode.value if isinstance(quality_mode, QualityMode) else str(quality_mode)
    window_seconds = 30.0 if quality != QualityMode.ACCURATE.value else 20.0
    overlap_seconds = 2.0
    recovered: list[Segment] = []
    start = 0.0
    while start < chunk_duration:
        end = min(chunk_duration, start + window_seconds)
        region_segments = asr_engine.transcribe_region(
            chunk_audio_path,
            start,
            end,
            quality_mode=quality_mode,
            audio_filter=audio_filter,
        )
        for segment in region_segments:
            text = segment.text.strip()
            if not text:
                continue
            if recovered:
                prev = recovered[-1]
                same_text = prev.text == text
                near = abs(segment.start - prev.end) <= 0.6
                if same_text and near:
                    prev.end = max(prev.end, segment.end)
                    prev.confidence = max(prev.confidence, segment.confidence)
                    continue
            recovered.append(
                Segment(
                    start=max(0.0, segment.start),
                    end=min(chunk_duration, max(segment.start + 0.1, segment.end)),
                    text=text,
                    confidence=segment.confidence,
                )
            )
        start += max(1.0, window_seconds - overlap_seconds)
    return recovered


def maybe_recover_chunk_segments(
    asr_engine: ASREngine,
    chunk_audio_path: str,
    local_segments: list[Segment],
    chunk_duration: float,
    quality_mode: QualityMode | str,
    audio_filter: str | None,
) -> list[Segment]:
    if looks_like_single_block(local_segments, chunk_duration):
        logger.info("检测到 ASR 时间戳较粗糙，使用短窗口重试该分块...")
        recovered = recover_segments_by_windows(
            asr_engine,
            chunk_audio_path,
            chunk_duration=chunk_duration,
            quality_mode=quality_mode,
            audio_filter=audio_filter,
        )
        if recovered:
            return recovered
    return local_segments
