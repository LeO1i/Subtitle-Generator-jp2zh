from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class QualityMode(str, Enum):
    FAST = "fast"
    ACCURATE = "accurate"


class AudioPreset(str, Enum):
    STANDARD = "standard"
    DENOISE = "denoise"
    AGGRESSIVE = "aggressive"


@dataclass
class Segment:
    start: float
    end: float
    text: str
    zh_text: str = ""
    confidence: float = 1.0
    speaker_id: str | None = None
    quality_flagged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Segment:
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")).strip(),
            zh_text=str(data.get("zh_text", "")).strip(),
            confidence=float(data.get("confidence", 1.0)),
            speaker_id=data.get("speaker_id"),
            quality_flagged=bool(data.get("quality_flagged", False)),
        )


@dataclass
class AudioChunk:
    index: int
    start: float
    end: float
    content_start: float
    content_end: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudioChunk:
        return cls(
            index=int(data["index"]),
            start=float(data["start"]),
            end=float(data["end"]),
            content_start=float(data["content_start"]),
            content_end=float(data["content_end"]),
        )


@dataclass
class SpeakerWindow:
    start: float
    end: float
    speaker_id: str
    loudness: float = 0.0


@dataclass
class JobResult:
    success: bool
    message: str
    output_path: Path | None = None


def segments_to_dicts(segments: list[Segment]) -> list[dict[str, Any]]:
    return [segment.to_dict() for segment in segments]


def segments_from_dicts(items: list[dict[str, Any]]) -> list[Segment]:
    return [Segment.from_dict(item) for item in items]
