from pathlib import Path
from unittest.mock import patch

from japanese_subtitle.domain.models import Segment
from japanese_subtitle.subtitles.ass import write_chinese_ass
from japanese_subtitle.subtitles.wrap import DEFAULT_MAX_CHARS_PER_LINE, DEFAULT_MAX_LINES


def test_ass_output_wraps_long_lines(tmp_path: Path):
    long_text = "為" * 45
    segments = [Segment(start=0.0, end=5.0, text="test", zh_text=long_text, speaker_id="Speaker1")]
    ass_path = tmp_path / "demo_styled.ass"
    write_chinese_ass(segments, ass_path)
    content = ass_path.read_text(encoding="utf-8")
    assert "WrapStyle: 2" in content
    assert ",100,100,45,1" in content
    assert "\\N" in content or len(long_text) <= DEFAULT_MAX_CHARS_PER_LINE * DEFAULT_MAX_LINES


def test_orchestrator_keeps_unmatched_speaker_segments():
    from japanese_subtitle.pipeline.orchestrator import SubtitlePipeline

    pipeline = SubtitlePipeline.__new__(SubtitlePipeline)
    chunk = type("Chunk", (), {"start": 0.0, "end": 10.0, "content_start": 0.0, "content_end": 10.0})()

    local_segments = [Segment(start=0.0, end=2.0, text="テスト", confidence=1.0)]

    with patch.object(SubtitlePipeline, "ensure_asr_engine") as mock_asr, patch(
        "japanese_subtitle.pipeline.orchestrator.extract_audio_span"
    ), patch(
        "japanese_subtitle.pipeline.orchestrator.maybe_recover_chunk_segments",
        side_effect=lambda *_args, **_kwargs: local_segments,
    ), patch(
        "japanese_subtitle.pipeline.orchestrator.assign_speaker",
        return_value=None,
    ), patch(
        "japanese_subtitle.pipeline.orchestrator.expand_long_segment", side_effect=lambda seg: [seg]
    ), patch(
        "japanese_subtitle.pipeline.orchestrator.segment_needs_second_pass", return_value=False
    ), patch(
        "japanese_subtitle.pipeline.orchestrator.merge_short_context_segments", side_effect=lambda segs: segs
    ), patch(
        "japanese_subtitle.pipeline.orchestrator.merge_boundary_segments", side_effect=lambda segs: segs
    ):
        mock_asr.return_value.transcribe.return_value = local_segments
        result = SubtitlePipeline._process_chunk(
            pipeline,
            chunk,
            "audio.wav",
            speaker_windows=[object()],
            active_quality="fast",
            active_audio_filter=None,
            active_audio_preset="standard",
            checkpoint_store=object(),
        )

    assert len(result) == 1
    assert result[0].text == "テスト"
    assert result[0].speaker_id is None
