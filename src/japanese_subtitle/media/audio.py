from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from japanese_subtitle.domain.models import AudioPreset
from japanese_subtitle.media.ffmpeg import find_ffmpeg, find_ffprobe, subprocess_kwargs

logger = logging.getLogger(__name__)

AUDIO_FILTER_PRESETS = {
    AudioPreset.STANDARD.value: "highpass=f=80,lowpass=f=8000,volume=1.5,dynaudnorm",
    AudioPreset.DENOISE.value: (
        "highpass=f=90,lowpass=f=7800,"
        "afftdn=nr=14:nf=-28:tn=1,"
        "acompressor=threshold=-21dB:ratio=2.2:attack=15:release=220:makeup=2,"
        "dynaudnorm=f=200:g=11:p=0.85"
    ),
    AudioPreset.AGGRESSIVE.value: (
        "highpass=f=100,lowpass=f=7600,"
        "afftdn=nr=20:nf=-30:tn=1,"
        "acompressor=threshold=-24dB:ratio=3.0:attack=10:release=260:makeup=3,"
        "dynaudnorm=f=150:g=13:p=0.9"
    ),
}


def resolve_audio_preset(preset: str | None) -> str:
    normalized = str(preset or "").strip().lower()
    if normalized in AUDIO_FILTER_PRESETS:
        return normalized
    return AudioPreset.STANDARD.value


def get_audio_filter_chain(preset: str | None) -> str:
    normalized = resolve_audio_preset(preset)
    return AUDIO_FILTER_PRESETS.get(normalized, AUDIO_FILTER_PRESETS[AudioPreset.STANDARD.value])


def next_audio_preset(preset: str) -> str:
    current = resolve_audio_preset(preset)
    if current == AudioPreset.STANDARD.value:
        return AudioPreset.DENOISE.value
    if current == AudioPreset.DENOISE.value:
        return AudioPreset.AGGRESSIVE.value
    return AudioPreset.AGGRESSIVE.value


def get_audio_duration(audio_path: Path | str) -> float:
    ffprobe_bin = find_ffprobe()
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, **subprocess_kwargs())
    return float(result.stdout.strip())


def extract_audio_span(
    source_audio_path: Path | str,
    output_audio_path: Path | str,
    start_seconds: float,
    end_seconds: float,
    audio_filter: str | None = None,
) -> None:
    ffmpeg_bin = find_ffmpeg()
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(source_audio_path),
        "-ss",
        str(max(0.0, start_seconds)),
        "-to",
        str(max(start_seconds + 0.1, end_seconds)),
    ]
    if audio_filter:
        cmd.extend(["-af", str(audio_filter)])
    cmd.extend(
        [
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_audio_path),
            "-y",
        ]
    )
    subprocess.run(cmd, check=True, capture_output=True, **subprocess_kwargs())


def extract_audio(video_path: Path | str, audio_path: Path | str, audio_preset: str | None = None) -> None:
    logger.info("正在从视频中提取音频...")
    ffmpeg_bin = find_ffmpeg()
    selected_preset = resolve_audio_preset(audio_preset)
    audio_filter = get_audio_filter_chain(selected_preset)
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(video_path),
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-af",
        audio_filter,
        str(audio_path),
        "-y",
    ]
    subprocess.run(cmd, check=True, capture_output=True, **subprocess_kwargs())
    logger.info("音频提取完成：%s", audio_path)
