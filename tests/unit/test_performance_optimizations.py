"""Unit tests for the performance-optimization changes.

These cover the pure-Python logic (dedup/cache, sidecar checkpoint, speaker
assignment, ASR correction regex) without loading real models or running ffmpeg.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from japanese_subtitle.diarization.speaker import assign_speaker
from japanese_subtitle.domain.models import Segment, SpeakerWindow
from japanese_subtitle.pipeline.checkpoints import CheckpointStore
from japanese_subtitle.translation.engine import TranslationEngine


def _make_translation_engine(backend: str = "pipeline") -> TranslationEngine:
    """Build a TranslationEngine without triggering model loading in __init__."""
    engine = TranslationEngine.__new__(TranslationEngine)
    engine._backend = backend
    engine.memory = {}
    engine._opencc = None
    engine._pipeline = None
    engine._tokenizer = None
    engine._model = None
    engine._task_name = "translation"
    engine.effective_model_id = "tencent/Hy-MT2-7B"
    return engine


def test_translate_batch_deduplicates_repeated_texts():
    engine = _make_translation_engine(backend="hy_chat")
    seen_batches: list[list[str]] = []

    def fake_batch(texts: list[str]) -> list[str]:
        seen_batches.append(list(texts))
        return [f"譯:{t}" for t in texts]

    engine._translate_batch_hy_chat = fake_batch  # type: ignore[assignment]

    texts = ["こんにちは", "こんにちは", "さようなら", "こんにちは", "ありがとう"]
    result = engine.translate_batch(texts)

    assert len(result) == len(texts)
    assert result[0] == "譯:こんにちは"
    assert result[1] == "譯:こんにちは"
    assert result[2] == "譯:さようなら"
    assert result[3] == "譯:こんにちは"
    assert result[4] == "譯:ありがとう"

    # Only 3 unique non-cached texts should have been sent to the model.
    assert len(seen_batches) == 1
    assert sorted(seen_batches[0]) == sorted(["こんにちは", "さようなら", "ありがとう"])


def test_translate_batch_uses_memory_cache_and_skips_model():
    engine = _make_translation_engine(backend="hy_chat")
    engine.memory["こんにちは"] = "你好"

    call_count = {"n": 0}

    def fake_batch(texts: list[str]) -> list[str]:
        call_count["n"] += 1
        return [f"譯:{t}" for t in texts]

    engine._translate_batch_hy_chat = fake_batch  # type: ignore[assignment]

    texts = ["こんにちは", "さようなら"]
    result = engine.translate_batch(texts)

    assert result[0] == "你好"
    assert result[1] == "譯:さようなら"
    assert call_count["n"] == 1
    # Cached entry should not be retranslated.
    assert "さようなら" in engine.memory


def test_translate_batch_handles_empty_and_blank_inputs():
    engine = _make_translation_engine(backend="hy_chat")
    engine._translate_batch_hy_chat = lambda texts: [f"譯:{t}" for t in texts]  # type: ignore[assignment]
    result = engine.translate_batch(["", "  ", "こんにちは"])
    assert result[0] == ""
    assert result[1] == ""
    assert result[2] == "譯:こんにちは"


def test_translate_batch_progress_callback_reports_unique_counts():
    engine = _make_translation_engine(backend="hy_chat")

    def fake_batch(texts: list[str]) -> list[str]:
        return [f"譯:{t}" for t in texts]

    engine._translate_batch_hy_chat = fake_batch  # type: ignore[assignment]

    reports: list[tuple[int, int]] = []
    # 5 unique texts, batch_size=2 -> 3 batches (2, 2, 1).
    texts = ["a", "b", "c", "d", "e"]
    engine.translate_batch(texts, batch_size=2, progress_callback=lambda done, total: reports.append((done, total)))

    assert reports[-1][0] == 5
    assert reports[-1][1] == 5
    assert all(total == 5 for _, total in reports)
    assert [done for done, _ in reports] == [2, 4, 5]


def test_translate_batch_pipeline_falls_back_when_length_mismatches():
    engine = _make_translation_engine(backend="pipeline")

    # Pipeline returns a malformed (short) list -> should fall back to per-item.
    engine._pipeline = lambda prompts, **kwargs: [{"translation_text": "短"}]  # type: ignore[assignment]
    single_calls: list[str] = []

    def fake_single(text: str) -> str:
        single_calls.append(text)
        return f"譯:{text}"

    engine._translate_single_pipeline = fake_single  # type: ignore[assignment]
    result = engine.translate_batch(["a", "b", "c"])
    assert result == ["譯:a", "譯:b", "譯:c"]
    assert sorted(single_calls) == ["a", "b", "c"]


def test_checkpoint_translation_memory_sidecar_round_trip(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    memory = {"こんにちは": "你好", "さようなら": "再見"}
    store.save_translation_memory(memory)
    loaded = store.load_translation_memory()
    assert loaded == memory


def test_checkpoint_load_translation_memory_missing_returns_empty(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    assert store.load_translation_memory() == {}


def test_assign_speaker_returns_best_overlap_with_sorted_windows():
    windows = [
        SpeakerWindow(start=0.0, end=2.0, speaker_id="Speaker1"),
        SpeakerWindow(start=2.0, end=4.0, speaker_id="Speaker2"),
        SpeakerWindow(start=4.0, end=6.0, speaker_id="Speaker3"),
    ]
    seg = Segment(start=2.5, end=3.5, text="x")
    assert assign_speaker(seg, windows) == "Speaker2"


def test_assign_speaker_returns_none_when_no_overlap():
    windows = [
        SpeakerWindow(start=0.0, end=1.0, speaker_id="Speaker1"),
        SpeakerWindow(start=10.0, end=12.0, speaker_id="Speaker2"),
    ]
    seg = Segment(start=5.0, end=6.0, text="x")
    assert assign_speaker(seg, windows) is None


def test_asr_corrections_regex_applies_longest_match_first():
    from japanese_subtitle.asr.engine import ASREngine

    regex_bundle = ASREngine._build_corrections_regex({"宇治波": "宇智波", "宇治波佐助": "宇智波佐助"})
    assert regex_bundle is not None
    regex, mapping = regex_bundle
    text = "宇治波佐助来了"
    out = regex.sub(lambda m: mapping[m.group(0)], text)
    assert out == "宇智波佐助来了"


def test_asr_corrections_regex_none_when_empty():
    from japanese_subtitle.asr.engine import ASREngine

    assert ASREngine._build_corrections_regex({}) is None
    assert ASREngine._build_corrections_regex({"": "x"}) is None


def test_asr_transcribe_accepts_audio_duration_and_skips_ffprobe(tmp_path: Path):
    from japanese_subtitle.asr.engine import ASREngine

    engine = ASREngine.__new__(ASREngine)
    engine._backend = "transformers"
    engine._pipeline = lambda path, **kwargs: {"text": "テスト", "chunks": None}  # type: ignore[assignment]
    engine.qwen_prompt = None
    engine._corrections_regex = None
    engine.asr_corrections = {}

    with patch("japanese_subtitle.asr.engine.get_audio_duration") as probe:
        segments = engine.transcribe("fake.wav", audio_duration=5.0)
        # Should not have invoked ffprobe since duration was supplied.
        probe.assert_not_called()
    assert len(segments) == 1
    assert segments[0].text == "テスト"
