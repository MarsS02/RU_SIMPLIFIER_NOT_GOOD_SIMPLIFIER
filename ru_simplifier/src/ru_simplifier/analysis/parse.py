# -*- coding: utf-8 -*-
"""Dependency-парсинг через spaCy ru_core_news_lg (Фаза 1).

Модель загружается ОДИН раз (ленивый потокобезопасный синглтон, см. ner.py —
модуль parse переиспользует тот же экземпляр через get_spacy_nlp()).
В runtime сеть не нужна: модель установлена один раз командой
    python -m spacy download ru_core_news_lg
Детерминизм (INV-4): парсер spaCy детерминирован при фиксированных весах;
рандом в runtime отсутствует.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Импорт из ner.py: единый синглтон nlp на весь пакет (NER + parser в одной трубe).
from ru_simplifier.analysis.ner import get_spacy_nlp


def parse_sentence(text: str) -> List[Dict[str, Any]]:
    """Разбирает одно предложение.

    Возвращает список токенов вида:
      {"text", "start", "end", "upos", "xpos",
       "morph": {"Case": "Dat", ...},   # фичи Feat'а spaCy
       "head": <индекс head-токена>, "dep": <метка>, "is_stop": bool}
    Индексы head — 0-based внутри предложения; у корня head == свой индекс.
    """
    doc = get_spacy_nlp()(text.strip())
    tokens: List[Dict[str, Any]] = []
    for tok in doc:
        morph: Dict[str, str] = {}
        for feat_key in ("Case", "Number", "Gender", "Tense", "Aspect",
                         "Mood", "Voice", "Person", "Animacy", "Degree"):
            val = tok.morph.get(feat_key)
            if val:
                morph[feat_key] = "|".join(val)  # детерминированный порядок spaCy
        head_idx = tok.head.i if tok.head.i != tok.i else tok.i
        tokens.append({
            "text": tok.text,
            "start": tok.idx,
            "end": tok.idx + len(tok.text),
            "upos": tok.pos_,
            "xpos": tok.tag_,
            "morph": morph,
            "head": head_idx,
            "dep": tok.dep_,
            "is_stop": tok.is_stop,
        })
    return tokens


def find_root(tokens: List[Dict[str, Any]]) -> Optional[int]:
    """Индекс корневого токена (dep == 'root'); None, если не найден."""
    for i, t in enumerate(tokens):
        if t["dep"] == "root":
            return i
    return None
