from __future__ import annotations

import gc
import logging
from typing import Callable

import torch

from japanese_subtitle.config.model_tiers import DEFAULT_MT_MODEL
from japanese_subtitle.translation.glossary import apply_glossary

logger = logging.getLogger(__name__)

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError:
    AutoModelForCausalLM = None
    AutoTokenizer = None
    pipeline = None

try:
    from opencc import OpenCC
except ImportError:
    OpenCC = None


class TranslationEngine:
    DEFAULT_BATCH_SIZE = 8

    def __init__(
        self,
        primary_model_id: str,
        advanced_model_id: str,
        use_advanced: bool = False,
        device: str | None = None,
        target_script: str = "traditional",
    ):
        if pipeline is None and (AutoModelForCausalLM is None or AutoTokenizer is None):
            raise ImportError("缺少 transformers 包。请运行 pip install -r requirements.txt")
        self.primary_model_id = primary_model_id
        self.advanced_model_id = advanced_model_id
        self.use_advanced = use_advanced
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.target_script = target_script
        self._opencc = self._build_opencc_converter(target_script)
        self.memory: dict[str, str] = {}
        self._backend = "pipeline"
        self._pipeline = None
        self._tokenizer = None
        self._model = None
        self.effective_model_id: str | None = None
        self._task_name = "translation"
        self._load_pipeline()

    @staticmethod
    def _build_opencc_converter(target_script: str):
        if OpenCC is None:
            return None
        normalized = str(target_script or "").strip().lower()
        if normalized in {"traditional", "繁體", "繁体", "zh-tw", "tw", "s2t"}:
            try:
                return OpenCC("s2t")
            except Exception:
                return None
        return None

    def _is_hy_mt_model(self, model_id: str) -> bool:
        lowered = (model_id or "").lower()
        return "hy-mt" in lowered or "hy-mt2" in lowered

    @staticmethod
    def _is_hy_mt2_model(model_id: str) -> bool:
        return "hy-mt2" in (model_id or "").lower()

    def _load_hy_model(self, model_id: str):
        if AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError("transformers 的 AutoModel/AutoTokenizer 不可用。")
        use_cuda = self.device.startswith("cuda") and torch.cuda.is_available()
        model_kwargs = {"device_map": self.device if use_cuda else "cpu", "trust_remote_code": True}
        if use_cuda:
            model_kwargs["torch_dtype"] = torch.bfloat16
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)
        return tokenizer, model

    def _load_translation_pipeline(self, model_id: str):
        use_cuda = self.device.startswith("cuda") and torch.cuda.is_available()
        pipe_device = 0 if use_cuda else -1
        dtype = torch.float16 if use_cuda else torch.float32
        tasks = ["translation", "text2text-generation", "text-generation"]
        last_error = None
        for task_name in tasks:
            try:
                return pipeline(task=task_name, model=model_id, device=pipe_device, torch_dtype=dtype), task_name
            except Exception as err:
                last_error = err
        raise RuntimeError(f"加载翻译模型失败 {model_id}：{last_error}")

    def _load_pipeline(self) -> None:
        model_candidates: list[str] = []
        if self.use_advanced:
            model_candidates.append(self.advanced_model_id)
        model_candidates.append(self.primary_model_id)
        if DEFAULT_MT_MODEL not in model_candidates:
            model_candidates.append(DEFAULT_MT_MODEL)
        errors: list[str] = []
        for model_id in model_candidates:
            try:
                if self._is_hy_mt_model(model_id):
                    self._tokenizer, self._model = self._load_hy_model(model_id)
                    self._backend = "hy_chat"
                    self._task_name = "chat-generation"
                else:
                    self._pipeline, self._task_name = self._load_translation_pipeline(model_id)
                    self._backend = "pipeline"
                self.effective_model_id = model_id
                if model_id == self.advanced_model_id and self.use_advanced:
                    logger.info("使用高级 MT 模型：%s", model_id)
                elif self.use_advanced and model_id == self.primary_model_id:
                    logger.info("高级 MT 模型加载失败，已自动回退到：%s", model_id)
                return
            except Exception as err:
                errors.append(str(err))
        raise RuntimeError("无法加载任何 MT 模型：\n" + "\n".join(errors))

    def _make_prompt(self, text: str) -> str:
        return (
            "Translate the following Japanese subtitle into natural Traditional Chinese. "
            "Keep names and special terms stable.\n"
            f"Japanese: {text}\nChinese:"
        )

    def _hy_chat_prompt(self, text: str) -> tuple[list[dict], bool]:
        model_id = self.effective_model_id or ""
        if self._is_hy_mt2_model(model_id):
            prompt = f"将以下文本翻译为繁體中文，注意只需要输出翻译后的结果，不要额外解释：\n\n{text}"
            add_generation_prompt = True
        else:
            prompt = (
                "Translate the following segment into natural Traditional Chinese, "
                "without additional explanation.\n\n"
                f"{text}"
            )
            add_generation_prompt = False
        return [{"role": "user", "content": prompt}], add_generation_prompt

    def _translate_with_hy_chat(self, text: str) -> str:
        messages, add_generation_prompt = self._hy_chat_prompt(text)
        tokenized_chat = self._tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=add_generation_prompt,
            return_tensors="pt",
        )
        input_ids = tokenized_chat.to(self._model.device)
        outputs = self._model.generate(
            input_ids,
            max_new_tokens=256,
            do_sample=True,
            top_k=20,
            top_p=0.6,
            temperature=0.7,
            repetition_penalty=1.05,
        )
        generated_tokens = outputs[0][input_ids.shape[-1] :]
        translated = self._tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
        return translated or text

    def _translate_batch_hy_chat(self, texts: list[str]) -> list[str]:
        conversations: list[list[dict]] = []
        add_gen_flags: list[bool] = []
        for text in texts:
            messages, add_gen = self._hy_chat_prompt(text)
            conversations.append(messages)
            add_gen_flags.append(add_gen)
        add_generation_prompt = add_gen_flags[0] if add_gen_flags else True

        original_padding = getattr(self._tokenizer, "padding_side", "right")
        self._tokenizer.padding_side = "left"
        try:
            inputs = self._tokenizer.apply_chat_template(
                conversations,
                tokenize=True,
                add_generation_prompt=add_generation_prompt,
                return_tensors="pt",
                return_dict=True,
                padding=True,
            )
        finally:
            self._tokenizer.padding_side = original_padding

        input_ids = inputs["input_ids"].to(self._model.device)
        attention_mask = inputs.get("attention_mask")
        gen_kwargs: dict = dict(
            max_new_tokens=256,
            do_sample=True,
            top_k=20,
            top_p=0.6,
            temperature=0.7,
            repetition_penalty=1.05,
        )
        if attention_mask is not None:
            gen_kwargs["attention_mask"] = attention_mask.to(self._model.device)

        with torch.no_grad():
            outputs = self._model.generate(input_ids, **gen_kwargs)

        input_len = input_ids.shape[-1]
        results: list[str] = []
        for row in outputs:
            new_tokens = row[input_len:]
            decoded = self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            results.append(decoded)
        return results

    def _translate_batch_pipeline(self, texts: list[str]) -> list[str]:
        is_translation_task = self._task_name == "translation"
        prompts = texts if is_translation_task else [self._make_prompt(t) for t in texts]
        results = None
        try:
            results = self._pipeline(prompts, max_new_tokens=128, do_sample=False, batch_size=len(prompts))
        except Exception:
            try:
                results = self._pipeline(prompts, batch_size=len(prompts))
            except Exception:
                results = None

        if not isinstance(results, list) or len(results) != len(prompts):
            # Batch returned malformed/short output; fall back to per-item calls to stay correct.
            return [self._translate_single_pipeline(text) for text in texts]

        outputs: list[str] = []
        for prompt, original, result in zip(prompts, texts, results):
            candidates = result if isinstance(result, list) else [result]
            translated = original
            for candidate in candidates:
                if isinstance(candidate, dict):
                    translated = (
                        candidate.get("translation_text")
                        or candidate.get("generated_text")
                        or candidate.get("summary_text")
                        or original
                    )
                else:
                    translated = str(candidate)
                if translated and translated != original:
                    break
            translated = str(translated).strip()
            if translated.startswith(prompt):
                translated = translated[len(prompt) :].strip()
            outputs.append(translated)
        return outputs

    def _translate_single_pipeline(self, text: str) -> str:
        is_translation_task = self._task_name == "translation"
        prompt = text if is_translation_task else self._make_prompt(text)
        kwargs = {"max_new_tokens": 128, "do_sample": False}
        try:
            result = self._pipeline(prompt, **kwargs)
        except Exception:
            result = self._pipeline(prompt)
        translated = text
        if isinstance(result, list) and result:
            candidate = result[0]
            translated = (
                candidate.get("translation_text")
                or candidate.get("generated_text")
                or candidate.get("summary_text")
                or text
            )
        translated = str(translated).strip()
        if translated.startswith(prompt):
            translated = translated[len(prompt) :].strip()
        return translated

    def translate(self, text: str, glossary: dict[str, str] | None = None) -> str:
        key = str(text or "").strip()
        if not key:
            return ""
        if key in self.memory:
            return self.memory[key]

        if self._backend == "hy_chat":
            translated = self._translate_with_hy_chat(key)
        else:
            is_translation_task = self._task_name == "translation"
            prompt = key if is_translation_task else self._make_prompt(key)
            kwargs = {"max_new_tokens": 128, "do_sample": False}
            try:
                result = self._pipeline(prompt, **kwargs)
            except Exception:
                result = self._pipeline(prompt)
            translated = key
            if isinstance(result, list) and result:
                candidate = result[0]
                translated = (
                    candidate.get("translation_text")
                    or candidate.get("generated_text")
                    or candidate.get("summary_text")
                    or key
                )
            translated = str(translated).strip()
            if translated.startswith(prompt):
                translated = translated[len(prompt) :].strip()
        translated = apply_glossary(key, translated, glossary)
        if self._opencc is not None:
            translated = self._opencc.convert(translated)
        self.memory[key] = translated or key
        return self.memory[key]

    def translate_batch(
        self,
        texts: list[str],
        glossary: dict[str, str] | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        if not texts:
            return []

        keys = [str(t or "").strip() for t in texts]
        cache: dict[str, str] = {}
        unique_to_translate: list[str] = []

        for key in keys:
            if not key:
                continue
            if key in self.memory:
                cache[key] = self.memory[key]
            elif key not in cache:
                cache[key] = ""
                unique_to_translate.append(key)

        total = len(unique_to_translate)
        done = 0
        for start in range(0, total, batch_size):
            batch = unique_to_translate[start : start + batch_size]
            if self._backend == "hy_chat":
                raw_results = self._translate_batch_hy_chat(batch)
            else:
                raw_results = self._translate_batch_pipeline(batch)
            for key, raw in zip(batch, raw_results):
                cleaned = str(raw or "").strip() or key
                cleaned = apply_glossary(key, cleaned, glossary)
                if self._opencc is not None:
                    cleaned = self._opencc.convert(cleaned)
                self.memory[key] = cleaned
                cache[key] = cleaned
            done = min(total, start + len(batch))
            if progress_callback is not None:
                progress_callback(done, total)

        results: list[str] = []
        for key in keys:
            if not key:
                results.append("")
                continue
            value = cache.get(key) or self.memory.get(key) or key
            results.append(value)
        return results

    def release(self) -> None:
        self._pipeline = None
        self._tokenizer = None
        self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
