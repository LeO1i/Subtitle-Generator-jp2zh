from pathlib import Path
from unittest.mock import patch

from japanese_subtitle.config.pipeline_config import PipelineConfig
from japanese_subtitle.services.subtitle_service import SubtitleService


def test_subtitle_service_generate_success(tmp_path: Path):
    video_path = tmp_path / "demo.mp4"
    video_path.write_bytes(b"fake")
    config = PipelineConfig(
        video_path=video_path,
        output_dir=tmp_path,
        model_tier="fast",
    )
    service = SubtitleService()
    with patch("japanese_subtitle.services.subtitle_service.SubtitlePipeline") as pipeline_cls:
        pipeline = pipeline_cls.return_value
        pipeline.run.return_value = tmp_path / "demo_bilingual.srt"
        result = service.generate_subtitles(config)
    assert result.success is True
    assert result.output_path == tmp_path / "demo_bilingual.srt"


def test_subtitle_service_burn_failure(tmp_path: Path):
    service = SubtitleService()
    with patch("japanese_subtitle.services.subtitle_service.SubtitleBurner") as burner_cls:
        burner_cls.return_value.burn_subtitles.return_value = False
        result = service.burn_subtitles(tmp_path / "a.mp4", tmp_path / "a.srt", tmp_path / "out.mp4")
    assert result.success is False
