from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from japanese_subtitle.media.ffmpeg import find_ffmpeg, subprocess_kwargs

logger = logging.getLogger(__name__)


class SubtitleBurner:
    def _escape_path_for_ffmpeg_subtitles(self, path: Path | str) -> str:
        posix_path = Path(path).resolve().as_posix()
        posix_path = posix_path.replace(":", "\\:")
        posix_path = posix_path.replace("'", "\\'")
        return posix_path

    def extract_chinese_from_bilingual_srt(self, bilingual_srt_path: Path | str, chinese_only_srt_path: Path | str):
        logger.info("正在从双语 SRT 中提取中文字幕...")
        try:
            with open(bilingual_srt_path, "r", encoding="utf-8") as handle:
                blocks = handle.read().split("\n\n")

            chinese_blocks = []
            for block in blocks:
                lines = [line for line in block.splitlines() if line.strip()]
                if len(lines) < 2:
                    continue
                timestamp_line = lines[1]
                text_lines = lines[2:]
                if not text_lines:
                    continue
                chinese_text = text_lines[1].strip() if len(text_lines) >= 2 else text_lines[0].strip()
                if not chinese_text:
                    continue
                chinese_blocks.append((timestamp_line, chinese_text))

            with open(chinese_only_srt_path, "w", encoding="utf-8") as handle:
                for idx, (timestamp_line, chinese_text) in enumerate(chinese_blocks, start=1):
                    handle.write(f"{idx}\n")
                    handle.write(f"{timestamp_line}\n")
                    handle.write(f"{chinese_text}\n\n")

            logger.info("已生成仅中文 SRT：%s", chinese_only_srt_path)
            return chinese_only_srt_path
        except Exception as err:
            logger.error("提取中文字幕时出错：%s", err)
            return None

    def _sidecar_ass_path(self, subtitle_path: Path | str) -> Path:
        path = Path(subtitle_path)
        if path.name.endswith("_bilingual.srt"):
            return path.with_name(path.name.replace("_bilingual.srt", "_styled.ass"))
        return path.with_suffix(".ass")

    def _is_generated_bilingual_srt(self, srt_path: Path | str, lines: list[str]) -> bool:
        path = Path(srt_path)
        if path.name.endswith("_bilingual.srt"):
            return True
        for index, line in enumerate(lines):
            if index > 40:
                break
            stripped = line.strip()
            if any(0x3040 <= ord(char) <= 0x309F or 0x30A0 <= ord(char) <= 0x30FF for char in stripped):
                return True
        return False

    def burn_subtitles(
        self,
        video_path: Path | str,
        srt_path: Path | str,
        output_path: Path | str,
        font_name: str = "Microsoft YaHei",
    ) -> bool:
        logger.info("正在将字幕烧录到视频中...")
        temp_chinese_srt = None
        subtitle_to_use = str(srt_path)
        subtitle_ext = os.path.splitext(subtitle_to_use)[1].lower()

        sidecar_ass = self._sidecar_ass_path(srt_path)
        if subtitle_ext != ".ass" and sidecar_ass.exists():
            logger.info("检测到彩色 ASS 字幕，将使用：%s", sidecar_ass)
            subtitle_to_use = str(sidecar_ass)
            subtitle_ext = ".ass"

        try:
            if subtitle_ext != ".ass":
                with open(srt_path, "r", encoding="utf-8") as handle:
                    lines = handle.readlines()
                if self._is_generated_bilingual_srt(srt_path, lines):
                    logger.info("检测到双语 SRT 文件，正在提取中文字幕...")
                    temp_chinese_srt = str(Path(srt_path).with_name(Path(srt_path).stem + "_temp_chinese.srt"))
                    extracted_srt = self.extract_chinese_from_bilingual_srt(srt_path, temp_chinese_srt)
                    if extracted_srt:
                        subtitle_to_use = extracted_srt
                    else:
                        logger.warning("提取中文字幕失败，将使用原始文件")

            ffmpeg_bin = find_ffmpeg()
            subtitle_escaped = self._escape_path_for_ffmpeg_subtitles(subtitle_to_use)
            safe_font = font_name.replace("'", "\\'")
            font_size = 24
            margin_v = 40
            margin_lr = 100
            force_style = (
                f"'FontName={safe_font},FontSize={font_size},Alignment=2,BorderStyle=1,"
                f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                f"Outline=2,Shadow=0,MarginV={margin_v},MarginL={margin_lr},MarginR={margin_lr}'"
            )

            if subtitle_ext == ".ass":
                vf_arg = f"subtitles=filename='{subtitle_escaped}':charenc=UTF-8"
            else:
                vf_arg = f"subtitles=filename='{subtitle_escaped}':charenc=UTF-8:force_style={force_style}"

            cmd = [
                ffmpeg_bin,
                "-hide_banner",
                "-i",
                os.path.abspath(str(video_path)),
                "-vf",
                vf_arg,
                "-c:v",
                "libx264",
                "-crf",
                "20",
                "-preset",
                "medium",
                "-c:a",
                "copy",
                str(output_path),
                "-y",
            ]
            subprocess.run(cmd, check=True, capture_output=True, **subprocess_kwargs())
            logger.info("烧录完成：%s", output_path)
            return True
        except subprocess.CalledProcessError as err:
            try:
                stderr = err.stderr.decode("utf-8", errors="ignore") if err.stderr else ""
            except Exception:
                stderr = str(err)
            logger.error("烧录失败：%s\nFFmpeg 错误输出：\n%s", err, stderr)
            return False
        finally:
            if temp_chinese_srt and os.path.exists(temp_chinese_srt):
                os.remove(temp_chinese_srt)


WriteSubtitle = SubtitleBurner
