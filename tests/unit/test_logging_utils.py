import logging

from japanese_subtitle.logging_utils import CallbackLogHandler


def test_callback_log_handler_emits_unicode_without_raising():
    messages: list[str] = []
    handler = CallbackLogHandler(messages.append)
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord(
        name="japanese_subtitle.pipeline.orchestrator",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="MT 模型：%s（高级：%s）",
        args=("tencent/Hy-MT2-7B", "tencent/Hy-MT2-7B"),
        exc_info=None,
    )
    handler.emit(record)
    assert "MT 模型" in messages[0]
    assert "高级" in messages[0]
