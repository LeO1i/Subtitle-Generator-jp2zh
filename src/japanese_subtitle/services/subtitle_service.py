from __future__ import annotations

import logging
from pathlib import Path

from japanese_subtitle.config.pipeline_config import PipelineConfig
from japanese_subtitle.domain.models import JobResult
from japanese_subtitle.logging_utils import CallbackLogHandler
from japanese_subtitle.pipeline.orchestrator import SubtitlePipeline
from japanese_subtitle.subtitles.burn import SubtitleBurner

logger = logging.getLogger(__name__)


class SubtitleService:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self._handler: CallbackLogHandler | None = None

    def _attach_logging(self) -> None:
        if self.log_callback is None:
            return
        root = logging.getLogger("japanese_subtitle")
        if self._handler is not None:
            root.removeHandler(self._handler)
        self._handler = CallbackLogHandler(self.log_callback)
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(self._handler)
        root.setLevel(logging.INFO)
        # Keep GUI logs on the callback handler only; root StreamHandler uses cp950 on Windows.
        root.propagate = False

    def generate_subtitles(self, config: PipelineConfig) -> JobResult:
        self._attach_logging()
        try:
            pipeline = SubtitlePipeline(config)
            result_path = pipeline.run()
            if result_path:
                return JobResult(success=True, message="字幕生成完成", output_path=Path(result_path))
            return JobResult(success=False, message="字幕生成失败，请查看日志。")
        except Exception as err:
            logger.exception("字幕生成失败")
            return JobResult(success=False, message=str(err))

    def burn_subtitles(self, video_path: Path | str, subtitle_path: Path | str, output_path: Path | str) -> JobResult:
        self._attach_logging()
        burner = SubtitleBurner()
        success = burner.burn_subtitles(video_path, subtitle_path, output_path)
        if success:
            return JobResult(success=True, message="烧录完成", output_path=Path(output_path))
        return JobResult(success=False, message="字幕烧录失败，请查看日志。")
