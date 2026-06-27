from __future__ import annotations

import os
import sys

from japanese_subtitle.config.model_tiers import MODEL_TIERS
from japanese_subtitle.logging_utils import configure_stdio_utf8
from japanese_subtitle.config.pipeline_config import PipelineConfig
from japanese_subtitle.services.subtitle_service import SubtitleService
from japanese_subtitle.subtitles.burn import SubtitleBurner


def _build_hardsub_path(video_path: str, output_dir: str) -> str:
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(output_dir, f"{video_name}_cn_hardsub.mp4")


def main() -> int:
    configure_stdio_utf8()
    print("欢迎使用日语视频字幕生成器！")
    print("你是否已经有本程序生成的日语字幕文件？")
    choice = input("请输入 y 或 n（y=是，n=否）：").strip().lower()
    writer = SubtitleBurner()
    if choice == "y":
        print("请输入日语字幕文件路径：")
        srt_path = input().strip()
        print("请输入日语视频文件路径：")
        video_path = input().strip()
        output_video_path = _build_hardsub_path(video_path, os.path.dirname(srt_path))
        result = SubtitleService().burn_subtitles(video_path, srt_path, output_video_path)
        if result.success:
            print("烧录成功。")
            return 0
        print("烧录失败，请查看上方错误信息。")
        return 1

    tier = input("模型档位 fast/balanced/accurate（默认 fast）：").strip().lower() or "fast"
    if tier not in MODEL_TIERS:
        tier = "fast"
    default_tier = MODEL_TIERS[tier]
    asr_model = input(f"ASR 模型（默认 {default_tier['asr']}）：").strip() or default_tier["asr"]
    mt_model = input(f"MT 模型（默认 {default_tier['mt']}）：").strip() or default_tier["mt"]
    use_advanced_mt = input("是否先启用高级翻译（优先尝试 Hy-MT2-7B，失败自动回退）？(y/N)：").strip().lower() == "y"
    quality_mode = (
        input(f"质量模式 fast/accurate（默认 {default_tier['quality']}）：").strip().lower()
        or default_tier["quality"]
    )
    if quality_mode not in {"fast", "accurate"}:
        quality_mode = "fast"
    chunk_size_text = input(f"分块时长（秒，30-600，默认 {default_tier['chunk_size']}）：").strip() or str(
        default_tier["chunk_size"]
    )
    overlap_text = input("分块重叠（秒，0-10，默认 2）：").strip() or "2"
    glossary_path = input("术语表文件路径（可选，直接回车跳过）：").strip() or None
    asr_terms_path = input("ASR 术语/修正文件路径（可选，直接回车跳过）：").strip() or None
    audio_preset = input("音频增强预设 standard/denoise/aggressive（默认 standard）：").strip().lower() or "standard"
    if audio_preset not in {"standard", "denoise", "aggressive"}:
        print("音频增强预设无效，已使用默认值 standard。")
        audio_preset = "standard"
    enable_speaker_diarization = input("是否启用说话人识别并仅保留前 3 位响度说话人？(Y/n)：").strip().lower() != "n"

    try:
        chunk_size = int(chunk_size_text)
        if chunk_size < 30 or chunk_size > 600:
            raise ValueError
    except Exception:
        print(f"分块时长无效，已使用默认值 {default_tier['chunk_size']}。")
        chunk_size = int(default_tier["chunk_size"])

    try:
        overlap_seconds = float(overlap_text)
        if overlap_seconds < 0 or overlap_seconds > 10:
            raise ValueError
    except Exception:
        print("重叠时长无效，已使用默认值 2。")
        overlap_seconds = 2

    if glossary_path and not os.path.exists(glossary_path):
        print("未找到术语表文件，已忽略术语表设置。")
        glossary_path = None
    if asr_terms_path and not os.path.exists(asr_terms_path):
        print("未找到 ASR 术语/修正文件，已忽略该设置。")
        asr_terms_path = None

    video_path = input("请输入日语视频文件路径：").strip()
    config = PipelineConfig(
        video_path=video_path,
        output_dir=os.path.dirname(video_path) or os.getcwd(),
        model_tier=tier,
        asr_model_id=asr_model,
        mt_model_id=mt_model,
        use_advanced_mt=use_advanced_mt,
        quality_mode=quality_mode,
        chunk_size_seconds=chunk_size,
        overlap_seconds=overlap_seconds,
        glossary_path=glossary_path,
        asr_terms_path=asr_terms_path,
        audio_preset=audio_preset,
        enable_speaker_diarization=enable_speaker_diarization,
    )
    result = SubtitleService().generate_subtitles(config)
    if not result.success or not result.output_path:
        print("字幕生成失败，请查看错误信息。")
        return 1

    srt_path = str(result.output_path)
    print("请打开生成的 SRT 文件，如有需要先检查/编辑。")
    choice = input("是否现在把中文字幕烧录进视频？(y/N)：").strip().lower()
    if choice == "y":
        output_video_path = _build_hardsub_path(video_path, os.path.dirname(srt_path))
        burn_result = writer.burn_subtitles(video_path, srt_path, output_video_path)
        if burn_result:
            print("烧录成功。")
        else:
            print("烧录失败，请查看上方错误信息。")
            return 1
    else:
        print("已跳过烧录。你可以在编辑 SRT 后重新运行来烧录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
