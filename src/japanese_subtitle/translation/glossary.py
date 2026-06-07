from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def load_glossary(glossary_path: str | None) -> dict[str, str]:
    if not glossary_path:
        return {}
    glossary: dict[str, str] = {}
    try:
        with open(glossary_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    source, target = line.split("=", 1)
                elif "\t" in line:
                    source, target = line.split("\t", 1)
                else:
                    continue
                glossary[source.strip()] = target.strip()
    except Exception as err:
        logger.warning("加载术语表失败 %s：%s", glossary_path, err)
    return glossary


def apply_glossary(japanese_text: str, chinese_text: str, glossary: dict[str, str] | None) -> str:
    if not glossary:
        return chinese_text
    output = chinese_text
    for ja_term, zh_term in glossary.items():
        if ja_term and zh_term and ja_term in japanese_text:
            output = output.replace(ja_term, zh_term)
    return output


def load_asr_terms(asr_terms_path: str | None) -> tuple[list[str], dict[str, str]]:
    if not asr_terms_path:
        return [], {}
    terms: list[str] = []
    corrections: dict[str, str] = {}
    seen: set[str] = set()
    try:
        with open(asr_terms_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=>" in line:
                    source, target = line.split("=>", 1)
                    source = source.strip()
                    target = target.strip()
                    if source and target:
                        corrections[source] = target
                    continue
                term = line.strip()
                key = term.lower()
                if term and key not in seen:
                    seen.add(key)
                    terms.append(term)
    except Exception as err:
        logger.warning("加载 ASR 术语失败 %s：%s", asr_terms_path, err)
    return terms, corrections
