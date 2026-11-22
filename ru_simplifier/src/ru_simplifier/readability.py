# -*- coding: utf-8 -*-
"""Оценка читаемости — ЗАГЛУШКА (Фаза 4).

Формула Оборневой и целевой FRE из config.yaml (readability.formula/target_fre)
будут реализованы в Фазе 4. Сейчас — только контракт, без реализации.
"""
from __future__ import annotations

from typing import Any, Dict


def score_readability(text: str, formula: str = "oborneva") -> Dict[str, Any]:
    """Возвращает метрики читаемости. Реализация — Фаза 4."""
    raise NotImplementedError("score_readability: реализация в Фазе 4 (формула Оборневой)")
