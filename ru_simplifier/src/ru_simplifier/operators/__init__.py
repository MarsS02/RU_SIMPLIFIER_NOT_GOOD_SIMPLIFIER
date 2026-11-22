# -*- coding: utf-8 -*-
"""Операторы упрощения формы (Фаза 3).

ПУСТО в Фазах 0-1. Контракт зафиксирован в ru_simplifier.contracts
(SimplificationOp). Whitelist операторов — resources/operators.yaml (Фаза 3).
INV-6: только whitelisted safe-операторы.
"""
from __future__ import annotations

from typing import Any


def run(text: Any) -> Any:
    """Применение безопасных операторов. Реализация — Фаза 3."""
    raise NotImplementedError("operators.run: реализация в Фазе 3")
