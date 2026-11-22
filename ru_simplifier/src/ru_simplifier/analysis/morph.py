# -*- coding: utf-8 -*-
"""Морфологический анализ через pymorphy3 (Фаза 1).

Синглтон: словарь pymorphy3 загружается один раз на процесс и кэшируется;
в сеть не ходим (INV-4, offline runtime). Результаты parse_word тоже кэшируются.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from pymorphy3 import MorphAnalyzer

_morph: Optional[MorphAnalyzer] = None
_morph_lock = threading.Lock()
_parse_cache: Dict[str, Optional[Dict[str, Any]]] = {}


def get_morph() -> MorphAnalyzer:
    """Ленивый потокобезопасный синглтон MorphAnalyzer (загрузка один раз)."""
    global _morph
    if _morph is None:
        with _morph_lock:
            if _morph is None:
                _morph = MorphAnalyzer()
    return _morph


# Ключи грамматем pymorphy3, которые прокидываем в контракт morph{}
_MORPH_KEYS = (
    "Case", "Number", "Gender", "Tense", "Aspect", "Mood", "Voice",
    "Person", "Animacy", "Degree", "Transitivity", "Inclination",
)


def parse_word(word: str) -> Optional[Dict[str, Any]]:
    """Разбор одного слова с кэшем.

    Возвращает {"lemma", "pos"}(латинская аббревиатура pymorphy: NOUN/VERB/...)
    и морфологические признаки {Case, Number, Gender, Tense, ...}, либо None
    для чисто пунктуационных токенов.
    """
    cached = _parse_cache.get(word)
    if cached is not None or word in _parse_cache:
        return cached

    m = get_morph()
    parsed = m.parse(word)
    if not parsed:
        _parse_cache[word] = None
        return None
    p = parsed[0]  # детерминированно: первый (наиболее вероятный) вариант
    result: Dict[str, Any] = {
        "lemma": p.normal_form,
        "pos": str(p.tag.POS) if p.tag else "",
        "grammemes": {},
    }
    if p.tag:
        for key in _MORPH_KEYS:
            val = getattr(p.tag, key, None)
            if val is not None:
                result["grammemes"][key] = str(val)
    _parse_cache[word] = result
    return result
