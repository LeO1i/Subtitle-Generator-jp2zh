from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from japanese_subtitle.domain.models import Segment, segments_from_dicts, segments_to_dicts

logger = logging.getLogger(__name__)

CHECKPOINT_VERSION = 6


class CheckpointStore:
    def __init__(self, checkpoint_dir: Path | str, version: int = CHECKPOINT_VERSION):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.version = version

    def _checkpoint_path(self, chunk_index: int) -> Path:
        return self.checkpoint_dir / f"chunk_{chunk_index:04d}.json"

    def load(self, chunk_index: int) -> dict[str, Any] | None:
        file_path = self._checkpoint_path(chunk_index)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("checkpoint_version") != self.version:
                return None
            if payload.get("status") == "completed":
                return payload
        except Exception as err:
            logger.warning("读取检查点失败 %s：%s", file_path, err)
        return None

    def save(self, chunk_index: int, payload: dict[str, Any]) -> None:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._checkpoint_path(chunk_index)
        payload["checkpoint_version"] = self.version
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def save_translation_memory(self, memory: dict[str, str]) -> None:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.checkpoint_dir / "translation_memory.json"
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(memory, handle, ensure_ascii=False, indent=2)

    def load_translation_memory(self) -> dict[str, str]:
        file_path = self.checkpoint_dir / "translation_memory.json"
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except Exception as err:
            logger.warning("读取翻译记忆失败 %s：%s", file_path, err)
            return {}

    @staticmethod
    def segments_from_payload(payload: dict[str, Any]) -> list[Segment]:
        return segments_from_dicts(payload.get("segments", []))

    @staticmethod
    def segments_to_payload(segments: list[Segment]) -> list[dict[str, Any]]:
        return segments_to_dicts(segments)
