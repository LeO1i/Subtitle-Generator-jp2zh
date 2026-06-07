from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import torch

from japanese_subtitle.config.model_tiers import (
    DEFAULT_ADV_MT_MODEL,
    MODEL_TIERS,
    normalize_mt_model_id,
    resolve_asr_model,
    resolve_model_tier,
)
from japanese_subtitle.domain.exceptions import ConfigError
from japanese_subtitle.domain.models import AudioPreset, QualityMode

logger = logging.getLogger(__name__)

SUPPORTED_VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv")


@dataclass
class PipelineConfig:
    video_path: Path
    output_dir: Path
    model_tier: str = "fast"
    asr_model_id: str | None = None
    mt_model_id: str | None = None
    mt_advanced_model_id: str = DEFAULT_ADV_MT_MODEL
    use_advanced_mt: bool = False
    quality_mode: str = "fast"
    chunk_size_seconds: int = 90
    overlap_seconds: float = 2.0
    glossary_path: Path | None = None
    asr_terms_path: Path | None = None
    audio_preset: str = AudioPreset.STANDARD.value
    enable_speaker_diarization: bool = True
    device: str | None = None
    target_script: str = "traditional"
    progress_callback: object | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.video_path = Path(self.video_path).resolve()
        self.output_dir = Path(self.output_dir).resolve()
        self.model_tier = resolve_model_tier(self.model_tier)
        tier = MODEL_TIERS[self.model_tier]  # noqa: F821
        self.asr_model_id = resolve_asr_model(self.asr_model_id or tier["asr"])
        self.mt_model_id = normalize_mt_model_id(self.mt_model_id or tier["mt"])
        self.mt_advanced_model_id = normalize_mt_model_id(self.mt_advanced_model_id)
        if self.quality_mode not in {QualityMode.FAST.value, QualityMode.ACCURATE.value}:
            self.quality_mode = tier["quality"]
        self.device = self.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        if self.glossary_path is not None:
            self.glossary_path = Path(self.glossary_path)
        if self.asr_terms_path is not None:
            self.asr_terms_path = Path(self.asr_terms_path)

    def validate(self) -> None:
        if self.video_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            raise ConfigError(f"不支持的视频格式：{self.video_path}")
        if not self.video_path.exists():
            raise ConfigError(f"视频文件不存在：{self.video_path}")
        if self.chunk_size_seconds < 30 or self.chunk_size_seconds > 600:
            raise ConfigError("分块时长必须为 30-600 秒")
        if self.overlap_seconds < 0 or self.overlap_seconds > 10:
            raise ConfigError("重叠时长必须为 0-10 秒")
        if self.glossary_path and not self.glossary_path.exists():
            raise ConfigError(f"术语表文件不存在：{self.glossary_path}")
        if self.asr_terms_path and not self.asr_terms_path.exists():
            raise ConfigError(f"ASR 术语文件不存在：{self.asr_terms_path}")
