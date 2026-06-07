from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class ModelTierSpec(TypedDict):
    asr: str
    mt: str
    chunk_size: int
    quality: str


DEFAULT_ASR_MODEL = "Qwen/Qwen3-ASR-0.6B"
DEFAULT_MT_MODEL = "Helsinki-NLP/opus-mt-ja-zh"
DEFAULT_ADV_MT_MODEL = "tencent/HY-MT1.5-7B"

MODEL_TIERS: dict[str, ModelTierSpec] = {
    "fast": {
        "asr": "Qwen/Qwen3-ASR-0.6B",
        "mt": "Helsinki-NLP/opus-mt-ja-zh",
        "chunk_size": 90,
        "quality": "fast",
    },
    "balanced": {
        "asr": "Qwen/Qwen3-ASR-0.6B",
        "mt": "tencent/HY-MT1.5-1.8B",
        "chunk_size": 90,
        "quality": "fast",
    },
    "accurate": {
        "asr": "Qwen/Qwen3-ASR-1.7B",
        "mt": "tencent/HY-MT1.5-1.8B",
        "chunk_size": 60,
        "quality": "accurate",
    },
}

GUI_TIER_LABELS: dict[str, str] = {
    "Fast": "fast",
    "Balanced": "balanced",
    "Accurate": "accurate",
}

GUI_TIER_DISPLAY: dict[str, str] = {value: key for key, value in GUI_TIER_LABELS.items()}


@dataclass(frozen=True)
class TierDefaults:
    label: str
    key: str
    asr: str
    mt: str
    chunk: str
    quality: str


def get_gui_tier_options() -> dict[str, TierDefaults]:
    options: dict[str, TierDefaults] = {}
    for label, key in GUI_TIER_LABELS.items():
        spec = MODEL_TIERS[key]
        options[label] = TierDefaults(
            label=label,
            key=key,
            asr=spec["asr"],
            mt=spec["mt"],
            chunk=str(spec["chunk_size"]),
            quality=spec["quality"],
        )
    return options


def resolve_model_tier(model_tier: str | None) -> str:
    normalized = str(model_tier or "fast").strip().lower()
    if normalized in MODEL_TIERS:
        return normalized
    return "fast"


def resolve_asr_model(model_name: str | None) -> str:
    whisper_aliases = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"}
    if model_name in whisper_aliases:
        return DEFAULT_ASR_MODEL
    return model_name or DEFAULT_ASR_MODEL


def normalize_mt_model_id(model_id: str | None) -> str:
    if not model_id:
        return DEFAULT_MT_MODEL
    text = str(model_id).strip()
    alias_map = {
        "HY-MT1.5-1.8B": "tencent/HY-MT1.5-1.8B",
        "HY-MT1.5-7B": "tencent/HY-MT1.5-7B",
    }
    return alias_map.get(text, text)
