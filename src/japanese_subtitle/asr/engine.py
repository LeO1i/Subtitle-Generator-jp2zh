from __future__ import annotations

import gc
import logging
import os
import tempfile
from pathlib import Path

import torch

from japanese_subtitle.domain.models import QualityMode, Segment
from japanese_subtitle.media.audio import extract_audio_span, get_audio_duration

logger = logging.getLogger(__name__)

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

try:
    from qwen_asr import Qwen3ASRModel
except ImportError:
    Qwen3ASRModel = None


class ASREngine:
    DEFAULT_QWEN_MAX_NEW_TOKENS = 1024

    def __init__(
        self,
        model_id: str,
        device: str | None = None,
        asr_terms: list[str] | None = None,
        asr_corrections: dict[str, str] | None = None,
    ):
        self.model_id = model_id
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.qwen_max_new_tokens = self._resolve_qwen_max_new_tokens()
        self.asr_terms = list(asr_terms or [])
        self.asr_corrections = dict(asr_corrections or {})
        self.qwen_prompt = self._build_qwen_prompt(self.asr_terms)
        self._backend = "transformers"
        self._pipeline = None
        self._qwen_model = None
        self._build_asr_backend()

    def _resolve_qwen_max_new_tokens(self) -> int:
        raw_value = os.getenv("QWEN_ASR_MAX_NEW_TOKENS", str(self.DEFAULT_QWEN_MAX_NEW_TOKENS)).strip()
        try:
            parsed = int(raw_value)
        except Exception:
            parsed = self.DEFAULT_QWEN_MAX_NEW_TOKENS
        return max(256, parsed)

    def _is_qwen3_asr(self) -> bool:
        model = (self.model_id or "").lower()
        return "qwen3-asr" in model

    @staticmethod
    def _build_qwen_prompt(terms: list[str]) -> str | None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for term in terms:
            value = str(term).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        if not cleaned:
            return None
        joined = "、".join(cleaned[:32])
        return f"这是日语语音转写任务。请保持专有名词和术语拼写稳定，优先使用以下词汇：{joined}"

    def _build_asr_backend(self) -> None:
        if self._is_qwen3_asr():
            if Qwen3ASRModel is None:
                raise ImportError("使用 Qwen3-ASR 模型需要安装 qwen-asr 包。请运行 pip install qwen-asr 后重试。")
            self._backend = "qwen_asr"
            self._qwen_model = self._build_qwen_model()
            return
        if pipeline is None:
            raise ImportError("缺少 transformers 包。请运行 pip install -r requirements.txt")
        self._backend = "transformers"
        self._pipeline = self._build_pipeline()

    def release(self) -> None:
        self._pipeline = None
        self._qwen_model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    def _build_qwen_model(self):
        use_cuda = self.device.startswith("cuda") and torch.cuda.is_available()
        dtype = torch.bfloat16 if use_cuda else torch.float32
        device_map = self.device if use_cuda else "cpu"
        try:
            return Qwen3ASRModel.from_pretrained(
                self.model_id,
                dtype=dtype,
                device_map=device_map,
                max_inference_batch_size=32,
                max_new_tokens=self.qwen_max_new_tokens,
            )
        except Exception as load_error:
            if use_cuda:
                logger.warning("Qwen ASR 模型在 CUDA 加载失败，已回退到 CPU：%s", load_error)
                return Qwen3ASRModel.from_pretrained(
                    self.model_id,
                    dtype=torch.float32,
                    device_map="cpu",
                    max_inference_batch_size=16,
                    max_new_tokens=self.qwen_max_new_tokens,
                )
            raise RuntimeError(f"加载 Qwen ASR 模型失败 {self.model_id}：{load_error}") from load_error

    def _build_pipeline(self):
        use_cuda = self.device.startswith("cuda") and torch.cuda.is_available()
        pipe_device = 0 if use_cuda else -1
        dtype = torch.float16 if use_cuda else torch.float32
        try:
            return pipeline(
                task="automatic-speech-recognition",
                model=self.model_id,
                device=pipe_device,
                torch_dtype=dtype,
            )
        except Exception as load_error:
            if use_cuda:
                logger.warning("ASR 模型在 CUDA 加载失败，已回退到 CPU：%s", load_error)
                return pipeline(
                    task="automatic-speech-recognition",
                    model=self.model_id,
                    device=-1,
                    torch_dtype=torch.float32,
                )
            raise RuntimeError(f"加载 ASR 模型失败 {self.model_id}：{load_error}") from load_error

    def _normalize_segments(self, asr_output, audio_duration: float) -> list[Segment]:
        chunks = asr_output.get("chunks") if isinstance(asr_output, dict) else None
        if not chunks:
            text = (asr_output.get("text", "") if isinstance(asr_output, dict) else str(asr_output)).strip()
            if not text:
                return []
            return [
                Segment(start=0.0, end=max(0.5, audio_duration), text=text, confidence=1.0),
            ]

        normalized: list[Segment] = []
        for chunk in chunks:
            timestamp = chunk.get("timestamp") or (0.0, 0.0)
            start = float(timestamp[0] or 0.0)
            end = float(timestamp[1] or start + 0.5)
            text = str(chunk.get("text", "")).strip()
            if not text:
                continue
            score = chunk.get("score")
            normalized.append(
                Segment(
                    start=max(0.0, start),
                    end=max(start + 0.1, end),
                    text=text,
                    confidence=float(score) if isinstance(score, (int, float)) else 1.0,
                )
            )
        return normalized

    def _normalize_qwen_segments(self, results, audio_duration: float) -> list[Segment]:
        if not results:
            return []

        entries = list(results) if isinstance(results, (list, tuple)) else [results]
        normalized: list[Segment] = []
        untimed_texts: list[str] = []

        for entry in entries:
            raw_segments = None
            for attr_name in ("segments", "chunks", "time_stamps", "timestamps", "timestamp"):
                if hasattr(entry, attr_name):
                    raw_segments = getattr(entry, attr_name)
                    break
                if isinstance(entry, dict) and attr_name in entry:
                    raw_segments = entry.get(attr_name)
                    break

            if raw_segments:
                for segment in raw_segments:
                    if isinstance(segment, dict):
                        start = segment.get("start", segment.get("begin", segment.get("from", 0.0)))
                        end = segment.get("end", segment.get("stop", segment.get("to", start)))
                        text = segment.get("text", segment.get("token", ""))
                        score = segment.get("score", segment.get("confidence"))
                    elif isinstance(segment, (list, tuple)) and len(segment) >= 3:
                        start, end, text = segment[0], segment[1], segment[2]
                        score = segment[3] if len(segment) > 3 else 1.0
                    else:
                        continue
                    text = str(text).strip()
                    if not text:
                        continue
                    try:
                        start_f = float(start or 0.0)
                        end_f = float(end or start_f + 0.5)
                    except Exception:
                        continue
                    normalized.append(
                        Segment(
                            start=max(0.0, start_f),
                            end=max(start_f + 0.1, end_f),
                            text=text,
                            confidence=float(score) if isinstance(score, (int, float)) else 1.0,
                        )
                    )
                continue

            text = ""
            if hasattr(entry, "text"):
                text = str(getattr(entry, "text", "")).strip()
            elif isinstance(entry, dict):
                text = str(entry.get("text", "")).strip()
            if text:
                untimed_texts.append(text)

        if normalized:
            normalized.sort(key=lambda item: (item.start, item.end))
            return normalized

        if not untimed_texts:
            return []

        total_duration = max(0.5, float(audio_duration))
        span = total_duration / max(1, len(untimed_texts))
        fallback_segments: list[Segment] = []
        for index, text in enumerate(untimed_texts):
            start = index * span
            end = total_duration if index == len(untimed_texts) - 1 else (index + 1) * span
            fallback_segments.append(
                Segment(start=start, end=max(start + 0.1, end), text=text, confidence=1.0)
            )
        return fallback_segments

    def _apply_asr_corrections(self, text: str) -> str:
        output = str(text or "")
        if not output or not self.asr_corrections:
            return output
        for source, target in self.asr_corrections.items():
            if source and target:
                output = output.replace(source, target)
        return output

    def transcribe(self, audio_path: Path | str, quality_mode: QualityMode | str = QualityMode.FAST) -> list[Segment]:
        quality = quality_mode.value if isinstance(quality_mode, QualityMode) else str(quality_mode)
        if self._backend == "qwen_asr":
            audio_duration = max(0.5, get_audio_duration(audio_path))
            attempts = [
                {"language": "Japanese", "return_time_stamps": True},
                {"language": None, "return_time_stamps": True},
                {"language": "Japanese"},
                {"language": None},
            ]
            results = None
            last_error = None
            prompt_variants: list[str | None] = [None]
            if self.qwen_prompt:
                prompt_variants = ["prompt", "system_prompt", "text_prompt", None]
            for kwargs in attempts:
                for prompt_key in prompt_variants:
                    merged = dict(kwargs)
                    if prompt_key and self.qwen_prompt:
                        merged[prompt_key] = self.qwen_prompt
                    try:
                        results = self._qwen_model.transcribe(audio=str(audio_path), **merged)
                        break
                    except Exception as err:
                        last_error = err
                        continue
                if results is not None:
                    break
            if results is None:
                raise RuntimeError(f"Qwen ASR 转写失败：{last_error}") from last_error
            normalized = self._normalize_qwen_segments(results, audio_duration)
            for segment in normalized:
                segment.text = self._apply_asr_corrections(segment.text)
            return normalized

        generate_kwargs = {"language": "ja"}
        if quality == QualityMode.ACCURATE.value:
            generate_kwargs.update({"num_beams": 4, "temperature": 0.0})
        try:
            output = self._pipeline(str(audio_path), return_timestamps=True, generate_kwargs=generate_kwargs)
        except Exception:
            output = self._pipeline(str(audio_path), return_timestamps=True)
        normalized = self._normalize_segments(output, max(0.5, get_audio_duration(audio_path)))
        for segment in normalized:
            segment.text = self._apply_asr_corrections(segment.text)
        return normalized

    def transcribe_region(
        self,
        audio_path: Path | str,
        start_seconds: float,
        end_seconds: float,
        quality_mode: QualityMode | str = QualityMode.ACCURATE,
        audio_filter: str | None = None,
    ) -> list[Segment]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_clip = temp_file.name
        try:
            extract_audio_span(audio_path, temp_clip, start_seconds, end_seconds, audio_filter=audio_filter)
            region_segments = self.transcribe(temp_clip, quality_mode=quality_mode)
            duration = max(0.1, end_seconds - start_seconds)
            fixed_segments: list[Segment] = []
            for segment in region_segments:
                fixed_segments.append(
                    Segment(
                        start=min(duration, max(0.0, segment.start)) + start_seconds,
                        end=min(duration, max(0.0, segment.end)) + start_seconds,
                        text=segment.text,
                        confidence=segment.confidence,
                    )
                )
            return fixed_segments
        finally:
            if os.path.exists(temp_clip):
                os.remove(temp_clip)
