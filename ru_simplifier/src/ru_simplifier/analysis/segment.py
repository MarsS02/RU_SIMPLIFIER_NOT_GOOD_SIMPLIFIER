# -*- coding: utf-8 -*-
"""Сегментация текста на предложения и токены через razdel (Фаза 1).

razdel не требует сети и детерминирован (INV-4).
"""
from __future__ import annotations

from typing import Any, Dict, List

from razdel import sentenize, tokenize


def segment_sentences(text: str) -> List[Dict[str, Any]]:
    """Разбивает текст на предложения.

    Возвращает список словарей {"text", "start", "end"}; start/end —
    символьные отступы в исходном тексте (для построения NER-смещений).
    """
    return [
        {"text": s.text, "start": s.start, "end": s.stop}
        for s in sentenize(text)
    ]


def tokenize(text: str) -> List[Dict[str, Any]]:
    """Токенизация одного фрагмента текста.

    Возвращает список {"text", "start", "end"} с отступами относительно
    переданного текста.
    """
    return [
        {"text": t.text, "start": t.start, "end": t.stop}
        for t in tokenize_raw(text)
    ]


def tokenize_raw(text: str):
    return list(tokenize(text))
