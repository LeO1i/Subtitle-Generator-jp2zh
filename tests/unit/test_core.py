from pathlib import Path

from japanese_subtitle.config.model_tiers import MODEL_TIERS, get_gui_tier_options, resolve_model_tier
from japanese_subtitle.domain.models import Segment, segments_from_dicts, segments_to_dicts
from japanese_subtitle.pipeline.checkpoints import CHECKPOINT_VERSION, CheckpointStore
from japanese_subtitle.pipeline.segment_ops import expand_long_segment, merge_boundary_segments
from japanese_subtitle.subtitles.ass import write_chinese_ass
from japanese_subtitle.subtitles.srt import write_bilingual_srt
from japanese_subtitle.subtitles.timecode import format_ass_time, format_srt_time
from japanese_subtitle.translation.glossary import apply_glossary, load_asr_terms, load_glossary


def test_resolve_model_tier_defaults_to_fast():
    assert resolve_model_tier(None) == "fast"
    assert resolve_model_tier("unknown") == "fast"
    assert resolve_model_tier("accurate") == "accurate"


def test_gui_tier_options_match_model_tiers():
    options = get_gui_tier_options()
    assert set(options.keys()) == {"Fast", "Balanced", "Accurate"}
    assert options["Fast"].key == "fast"
    assert options["Fast"].asr == MODEL_TIERS["fast"]["asr"]


def test_load_glossary_parses_equals_and_tabs(tmp_path: Path):
    glossary_file = tmp_path / "glossary.txt"
    glossary_file.write_text("日本=日本語\n東京\t台北\n# comment\n", encoding="utf-8")
    glossary = load_glossary(str(glossary_file))
    assert glossary["日本"] == "日本語"
    assert glossary["東京"] == "台北"


def test_load_asr_terms_parses_corrections(tmp_path: Path):
    terms_file = tmp_path / "terms.txt"
    terms_file.write_text("東京\n誤字=>正字\n", encoding="utf-8")
    terms, corrections = load_asr_terms(str(terms_file))
    assert "東京" in terms
    assert corrections["誤字"] == "正字"


def test_apply_glossary_replaces_matching_terms():
    result = apply_glossary("東京", "東京塔", {"東京": "東京都"})
    assert result == "東京都塔"


def test_merge_boundary_segments_merges_same_text():
    segments = [
        Segment(start=0.0, end=1.0, text="こんにちは"),
        Segment(start=1.2, end=2.0, text="こんにちは"),
    ]
    merged = merge_boundary_segments(segments)
    assert len(merged) == 1
    assert merged[0].end == 2.0


def test_expand_long_segment_splits_long_text():
    segment = Segment(start=0.0, end=15.0, text="あ" * 80)
    expanded = expand_long_segment(segment)
    assert len(expanded) > 1


def test_checkpoint_round_trip(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    segments = [Segment(start=0.0, end=1.0, text="test", zh_text="測試")]
    payload = {
        "status": "completed",
        "chunk_index": 0,
        "segments": store.segments_to_payload(segments),
        "translation_memory": {"test": "測試"},
    }
    store.save(0, payload)
    loaded = store.load(0)
    assert loaded is not None
    assert loaded["checkpoint_version"] == CHECKPOINT_VERSION
    restored = store.segments_from_payload(loaded)
    assert restored[0].text == "test"


def test_timecode_formatters():
    assert format_srt_time(3661.5) == "01:01:01,500"
    assert format_ass_time(3661.5) == "1:01:01.50"


def test_write_subtitle_files(tmp_path: Path):
    segments = [
        Segment(start=0.0, end=1.0, text="こんにちは", zh_text="你好", speaker_id="Speaker1"),
    ]
    srt_path = tmp_path / "demo_bilingual.srt"
    ass_path = tmp_path / "demo_styled.ass"
    write_bilingual_srt(segments, srt_path)
    write_chinese_ass(segments, ass_path)
    srt_text = srt_path.read_text(encoding="utf-8")
    ass_text = ass_path.read_text(encoding="utf-8")
    assert "こんにちは" in srt_text
    assert "你好" in srt_text
    assert "Speaker1" in ass_text
    assert "【A】" in ass_text


def test_segment_dict_conversion():
    segment = Segment(start=1.0, end=2.0, text="abc", zh_text="中文")
    restored = segments_from_dicts(segments_to_dicts([segment]))
    assert restored[0].text == "abc"
    assert restored[0].zh_text == "中文"
