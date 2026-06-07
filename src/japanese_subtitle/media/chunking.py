from __future__ import annotations

from japanese_subtitle.domain.models import AudioChunk
from japanese_subtitle.media.audio import get_audio_duration


def split_audio_chunks(audio_path: str, chunk_size_seconds: int, overlap_seconds: float) -> list[AudioChunk]:
    duration = get_audio_duration(audio_path)
    chunks: list[AudioChunk] = []
    chunk_size_seconds = max(30, min(600, int(chunk_size_seconds)))
    overlap_seconds = max(0.0, min(10.0, float(overlap_seconds)))
    start = 0.0
    index = 0
    while start < duration:
        end = min(duration, start + chunk_size_seconds)
        chunks.append(
            AudioChunk(
                index=index,
                start=max(0.0, start - overlap_seconds if index > 0 else start),
                end=end,
                content_start=start,
                content_end=end,
            )
        )
        index += 1
        start += chunk_size_seconds
    return chunks
