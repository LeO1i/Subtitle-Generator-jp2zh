from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path

from japanese_subtitle.asr.engine import ASREngine
from japanese_subtitle.asr.quality import maybe_recover_chunk_segments
from japanese_subtitle.config.model_tiers import MODEL_TIERS
from japanese_subtitle.config.pipeline_config import PipelineConfig
from japanese_subtitle.diarization.speaker import assign_speaker, get_top_speaker_windows
from japanese_subtitle.domain.models import QualityMode, Segment, SpeakerWindow
from japanese_subtitle.logging_utils import emit_progress
from japanese_subtitle.media.audio import extract_audio, extract_audio_span, get_audio_filter_chain, next_audio_preset
from japanese_subtitle.media.chunking import split_audio_chunks
from japanese_subtitle.pipeline.checkpoints import CheckpointStore
from japanese_subtitle.pipeline.segment_ops import (
    expand_long_segment,
    merge_boundary_segments,
    merge_short_context_segments,
    segment_needs_second_pass,
)
from japanese_subtitle.subtitles.ass import write_chinese_ass
from japanese_subtitle.subtitles.srt import write_bilingual_srt
from japanese_subtitle.subtitles.wrap import split_segments_for_display
from japanese_subtitle.translation.engine import TranslationEngine
from japanese_subtitle.translation.glossary import load_asr_terms, load_glossary

logger = logging.getLogger(__name__)


class SubtitlePipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.glossary = load_glossary(str(config.glossary_path) if config.glossary_path else None)
        self.asr_terms, self.asr_corrections = load_asr_terms(
            str(config.asr_terms_path) if config.asr_terms_path else None
        )
        self.asr_engine: ASREngine | None = None
        self.translation_engine: TranslationEngine | None = None
        logger.info("ASR 模型：%s", config.asr_model_id)
        logger.info("MT 模型：%s（高级：%s）", config.mt_model_id, config.mt_advanced_model_id)
        logger.info("模型档位：%s", config.model_tier)
        logger.info("设备偏好：%s", config.device)
        logger.info("音频增强预设：%s", config.audio_preset)
        logger.info("说话人识别：%s", "启用" if config.enable_speaker_diarization else "关闭")
        if self.asr_terms:
            logger.info("ASR 术语条目：%s", len(self.asr_terms))
        if self.asr_corrections:
            logger.info("ASR 修正规则：%s", len(self.asr_corrections))
        self._init_asr_engine()

    def _init_asr_engine(self) -> None:
        self.asr_engine = ASREngine(
            model_id=self.config.asr_model_id,
            device=self.config.device,
            asr_terms=self.asr_terms,
            asr_corrections=self.asr_corrections,
        )

    def ensure_asr_engine(self) -> ASREngine:
        if self.asr_engine is None:
            self._init_asr_engine()
        return self.asr_engine

    def release_asr_engine(self) -> None:
        if self.asr_engine is not None:
            self.asr_engine.release()
            self.asr_engine = None

    def ensure_translation_engine(self) -> TranslationEngine:
        if self.translation_engine is None:
            self.translation_engine = TranslationEngine(
                primary_model_id=self.config.mt_model_id,
                advanced_model_id=self.config.mt_advanced_model_id,
                use_advanced=self.config.use_advanced_mt,
                device=self.config.device,
                target_script=self.config.target_script,
            )
            logger.info("最终使用的 MT 模型：%s", self.translation_engine.effective_model_id)
        return self.translation_engine

    def _emit(self, percent: float, message: str) -> None:
        emit_progress(self.config.progress_callback, percent, message)

    def _resolve_runtime_settings(self) -> tuple[str, str, str, int, float]:
        active_quality = self.config.quality_mode
        active_audio_preset = self.config.audio_preset
        active_audio_filter = get_audio_filter_chain(active_audio_preset)
        tier_chunk_size = int(MODEL_TIERS[self.config.model_tier].get("chunk_size", 90))
        active_chunk_size = int(self.config.chunk_size_seconds or tier_chunk_size)
        active_overlap = float(self.config.overlap_seconds)

        if active_quality == QualityMode.FAST.value and active_chunk_size >= 120 and self.config.model_tier == "fast":
            active_chunk_size = 90
            logger.info("快速档位已自动调整分块时长为 90 秒，以降低显存和内存压力。")
        if active_quality == QualityMode.ACCURATE.value and active_chunk_size >= 120:
            active_chunk_size = 60
            logger.info("精确模式已自动调整分块时长为 60 秒，以提升复杂噪声音频识别稳定性。")
        if active_quality == QualityMode.ACCURATE.value and active_overlap < 2.0:
            active_overlap = 2.0
        return active_quality, active_audio_preset, active_audio_filter, active_chunk_size, active_overlap

    def _detect_speakers(self, audio_path: str) -> list[SpeakerWindow]:
        if not self.config.enable_speaker_diarization:
            return []
        try:
            self._emit(3.0, "正在识别说话人...")
            speaker_windows = get_top_speaker_windows(audio_path, top_n=3)
            if speaker_windows:
                speakers = sorted({window.speaker_id for window in speaker_windows})
                logger.info("已识别前 3 位响度说话人用于彩色标注：%s", ", ".join(speakers))
            else:
                logger.info("未检测到可靠说话人窗口，将转写全部语音。")
            return speaker_windows
        except Exception as err:
            logger.warning("说话人识别失败，已回退为转写全部语音：%s", err)
            return []

    def _process_chunk(
        self,
        chunk,
        audio_path: str,
        speaker_windows: list[SpeakerWindow],
        active_quality: str,
        active_audio_filter: str,
        active_audio_preset: str,
        checkpoint_store: CheckpointStore,
    ) -> list[Segment]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_chunk:
            chunk_audio_path = temp_chunk.name
        try:
            extract_audio_span(audio_path, chunk_audio_path, chunk.start, chunk.end)
            asr_engine = self.ensure_asr_engine()
            chunk_duration = max(0.1, chunk.end - chunk.start)
            local_segments = asr_engine.transcribe(
                chunk_audio_path,
                quality_mode=active_quality,
                audio_duration=chunk_duration,
            )
            local_segments = maybe_recover_chunk_segments(
                asr_engine,
                chunk_audio_path,
                local_segments,
                chunk_duration,
                active_quality,
                active_audio_filter,
            )

            chunk_segments: list[Segment] = []
            flagged: list[Segment] = []
            prev_segment: Segment | None = None
            for segment in local_segments:
                global_start = segment.start + chunk.start
                global_end = segment.end + chunk.start
                if global_end <= chunk.content_start or global_start >= chunk.content_end:
                    prev_segment = segment
                    continue
                clipped_start = max(chunk.content_start, global_start)
                clipped_end = min(chunk.content_end, max(global_start + 0.1, global_end))
                normalized = Segment(
                    start=clipped_start,
                    end=clipped_end,
                    text=segment.text.strip(),
                    confidence=segment.confidence,
                )
                if not normalized.text:
                    prev_segment = segment
                    continue
                if speaker_windows:
                    normalized.speaker_id = assign_speaker(normalized, speaker_windows)
                for expanded in expand_long_segment(normalized):
                    if segment_needs_second_pass(expanded, prev_segment):
                        expanded.quality_flagged = True
                        flagged.append(expanded)
                    chunk_segments.append(expanded)
                    prev_segment = expanded

            if flagged:
                for flagged_segment in flagged:
                    local_start = max(0.0, flagged_segment.start - chunk.start)
                    local_end = max(local_start + 0.1, flagged_segment.end - chunk.start)
                    refined = asr_engine.transcribe_region(
                        chunk_audio_path,
                        local_start,
                        local_end,
                        quality_mode=QualityMode.ACCURATE.value,
                        audio_filter=get_audio_filter_chain(next_audio_preset(active_audio_preset)),
                    )
                    if refined:
                        best = refined[0]
                        flagged_segment.text = best.text.strip() or flagged_segment.text
                        flagged_segment.confidence = max(flagged_segment.confidence, best.confidence)

            chunk_segments = merge_short_context_segments(chunk_segments)
            return merge_boundary_segments(chunk_segments)
        finally:
            if os.path.exists(chunk_audio_path):
                os.remove(chunk_audio_path)

    def run(self) -> Path | None:
        self.config.validate()
        video_path = self.config.video_path
        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        active_quality, active_audio_preset, active_audio_filter, active_chunk_size, active_overlap = (
            self._resolve_runtime_settings()
        )
        video_name = video_path.stem
        audio_path = output_dir / f"{video_name}_{uuid.uuid4().hex}_temp.wav"
        subtitle_path = output_dir / f"{video_name}_bilingual.srt"
        ass_subtitle_path = output_dir / f"{video_name}_styled.ass"
        checkpoint_dir = output_dir / f"{video_name}_checkpoints"
        checkpoint_store = CheckpointStore(checkpoint_dir)

        logger.info(
            "分块：%ss，重叠：%ss，质量：%s，音频预设：%s",
            active_chunk_size,
            active_overlap,
            active_quality,
            active_audio_preset,
        )
        logger.info("检查点目录：%s", checkpoint_dir)

        all_segments: list[Segment] = []
        checkpoint_translation_memory: dict[str, str] = {}
        try:
            self._emit(0.0, "正在提取音频...")
            extract_audio(video_path, audio_path, audio_preset=active_audio_preset)
            speaker_windows = self._detect_speakers(str(audio_path))
            if speaker_windows:
                speaker_windows.sort(key=lambda w: w.start)
            chunks = split_audio_chunks(str(audio_path), active_chunk_size, active_overlap)
            total_chunks = max(1, len(chunks))

            checkpoint_translation_memory.update(checkpoint_store.load_translation_memory())

            resumed_chunks = 0
            for chunk in chunks:
                existing = checkpoint_store.load(chunk.index)
                if existing:
                    resumed_chunks += 1
                    logger.info("继续处理：分块 %s 已完成", chunk.index)
                    all_segments.extend(checkpoint_store.segments_from_payload(existing))
                    for source, target in existing.get("translation_memory", {}).items():
                        checkpoint_translation_memory.setdefault(source, target)
                    progress = ((chunk.index + 1) / total_chunks) * 95.0
                    self._emit(progress, f"已续跑分块 {chunk.index + 1}/{total_chunks}")
                    continue

            if resumed_chunks:
                logger.warning(
                    "已从检查点续跑 %s 个分块。若字幕仍有缺失，请删除检查点目录后重新生成：%s",
                    resumed_chunks,
                    checkpoint_dir,
                )

            for chunk in chunks:
                existing = checkpoint_store.load(chunk.index)
                if existing:
                    continue

                logger.info(
                    "正在处理分块 %s/%s (%.2fs - %.2fs)",
                    chunk.index + 1,
                    len(chunks),
                    chunk.start,
                    chunk.end,
                )
                try:
                    self._emit(
                        (chunk.index / total_chunks) * 95.0,
                        f"正在处理分块 {chunk.index + 1}/{total_chunks}",
                    )
                    merged_chunk_segments = self._process_chunk(
                        chunk,
                        str(audio_path),
                        speaker_windows,
                        active_quality,
                        active_audio_filter,
                        active_audio_preset,
                        checkpoint_store,
                    )
                    checkpoint_store.save(
                        chunk.index,
                        {
                            "status": "completed",
                            "chunk_index": chunk.index,
                            "chunk_meta": chunk.to_dict(),
                            "segments": checkpoint_store.segments_to_payload(merged_chunk_segments),
                        },
                    )
                    all_segments.extend(merged_chunk_segments)
                    progress = ((chunk.index + 1) / total_chunks) * 95.0
                    self._emit(progress, f"已处理分块 {chunk.index + 1}/{total_chunks}")
                except Exception as chunk_error:
                    checkpoint_store.save(
                        chunk.index,
                        {"status": "failed", "chunk_index": chunk.index, "error": str(chunk_error)},
                    )
                    logger.error("分块 %s 失败：%s", chunk.index, chunk_error)
                    continue

            merged_segments = merge_boundary_segments(all_segments)
            self._emit(95.5, "正在释放 ASR 并加载翻译模型...")
            self.release_asr_engine()
            translation_engine = self.ensure_translation_engine()
            translation_engine.memory.update(checkpoint_translation_memory)
            self._emit(96.0, "正在翻译为繁體中文...")
            segments_to_translate = [seg for seg in merged_segments if not seg.zh_text]
            total_segments = max(1, len(merged_segments))
            if segments_to_translate:
                batch_size = translation_engine.DEFAULT_BATCH_SIZE

                def _on_progress(done: int, total: int) -> None:
                    percent = 96.0 + (done / max(1, total_segments)) * 1.0
                    self._emit(percent, f"正在翻译字幕 {done}/{total}")

                translations = translation_engine.translate_batch(
                    [seg.text for seg in segments_to_translate],
                    glossary=self.glossary,
                    batch_size=batch_size,
                    progress_callback=_on_progress,
                )
                for seg, zh in zip(segments_to_translate, translations):
                    seg.zh_text = zh

            self._emit(97.0, "正在写入字幕文件...")
            display_segments = split_segments_for_display(merged_segments)
            write_bilingual_srt(display_segments, subtitle_path)
            write_chinese_ass(display_segments, ass_subtitle_path)
            if translation_engine.memory:
                checkpoint_store.save_translation_memory(translation_engine.memory)
            self._emit(100.0, "字幕生成完成")
            logger.info("处理完成。字幕文件：%s", subtitle_path)
            logger.info("已生成彩色 ASS 字幕：%s", ass_subtitle_path)
            return subtitle_path
        except Exception as err:
            logger.exception("处理过程中发生错误：%s", err)
            return None
        finally:
            if audio_path.exists():
                audio_path.unlink()
