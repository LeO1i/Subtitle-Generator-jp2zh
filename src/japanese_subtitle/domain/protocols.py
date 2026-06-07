from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from japanese_subtitle.domain.models import QualityMode, Segment

ProgressReporter = Callable[[float, str], None]


class ASRBackend(Protocol):
    def transcribe(
        self,
        audio_path: Path | str,
        quality_mode: QualityMode | str = QualityMode.FAST,
    ) -> list[Segment]: ...

    def transcribe_region(
        self,
        audio_path: Path | str,
        start_seconds: float,
        end_seconds: float,
        quality_mode: QualityMode | str = QualityMode.ACCURATE,
        audio_filter: str | None = None,
    ) -> list[Segment]: ...

    def release(self) -> None: ...


class TranslationBackend(Protocol):
    memory: dict[str, str]

    def translate(self, text: str, glossary: dict[str, str] | None = None) -> str: ...

    def release(self) -> None: ...
