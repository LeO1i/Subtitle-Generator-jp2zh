from japanese_subtitle.domain.models import Segment
from japanese_subtitle.subtitles.wrap import (
    DEFAULT_MAX_CHARS_PER_LINE,
    DEFAULT_MAX_LINES,
    split_segments_for_display,
    wrap_cjk_text,
)


def test_wrap_cjk_text_two_lines():
    text = "為了獲得幫助這次我們將分成兩組由瀬戸口野道擔任隊長大家將通過熟悉的遊戲來展開比賽"
    wrapped = wrap_cjk_text(text)
    lines = wrapped.split("\n")
    assert 1 <= len(lines) <= DEFAULT_MAX_LINES
    assert all(len(line) <= DEFAULT_MAX_CHARS_PER_LINE for line in lines)


def test_wrap_cjk_text_short_line_unchanged():
    text = "你好世界"
    assert wrap_cjk_text(text) == text


def test_wrap_cjk_text_ass_line_break():
    text = "第一行文字需要换行展示的内容继续延伸"
    wrapped = wrap_cjk_text(text, line_break="\\N")
    assert "\\N" in wrapped or len(wrapped) <= DEFAULT_MAX_CHARS_PER_LINE


def test_split_segments_for_display_splits_long_zh():
    segment = Segment(
        start=0.0,
        end=8.0,
        text="あ" * 50,
        zh_text="為" * 45,
    )
    split = split_segments_for_display([segment])
    assert len(split) >= 2
    assert all(len(item.zh_text) <= DEFAULT_MAX_CHARS_PER_LINE * DEFAULT_MAX_LINES for item in split)
    assert split[0].start == 0.0
    assert split[-1].end == 8.0


def test_split_segments_for_display_keeps_short_segment():
    segment = Segment(start=1.0, end=2.0, text="こんにちは", zh_text="你好")
    split = split_segments_for_display([segment])
    assert len(split) == 1
    assert split[0].zh_text == "你好"
