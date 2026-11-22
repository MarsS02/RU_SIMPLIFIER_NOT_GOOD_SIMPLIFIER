# -*- coding: utf-8 -*-
"""Семантика (Фаза 2): извлечение пропозиций и риторических связей.

Точка входа: run(analyzed_sentence_dict) -> SemanticsResult (dict).

Полностью детерминированно (INV-4): только dep-дерево + морфология из
анализатора Фазы 1; генеративных моделей нет. Покрытие содержательных
клауз (advcl/ccomp/parataxis/acl/предиктивы с инфинитивом) — INV-1;
аргументы сохраняют имена, числа, даты, отрицание и модальность — INV-2.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ru_simplifier.config import get_logger
from ru_simplifier.semantics import links as links_mod
from ru_simplifier.semantics import propositions as props_mod

log = get_logger("semantics")


def extract_propositions_internal(analyzed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Пропозиции СО служебными полями (_head/_parent/_marker/_span).

    Внутренний API для links.py; публичный контракт — без служебных полей.
    """
    result: List[Dict[str, Any]] = []
    next_id = 1
    for sent in analyzed.get("sentences", []):
        props = props_mod.extract_from_sentence(sent, next_id)
        next_id += len(props)
        result.extend(props)
    return result


def run(analyzed: Any) -> Dict[str, Any]:
    """SemanticsResult: {"propositions": [...], "links": [...]}.

    :param analyzed: dict контракта AnalyzedSentence (или объект с to_dict()).
    """
    if hasattr(analyzed, "to_dict") and not isinstance(analyzed, dict):
        analyzed = analyzed.to_dict()

    internal = extract_propositions_internal(analyzed)
    propositions = [
        {
            "id": p["id"],
            "predicate": p["predicate"],
            "args": dict(p["args"]),
            "polarity": p["polarity"],
            "modality": p["modality"],
            "tense": p["tense"],
        }
        for p in internal
    ]
    links = links_mod.extract(analyzed, internal)

    log.info("semantics.run: пропозиций=%d, связей=%d",
             len(propositions), len(links))
    return {"propositions": propositions, "links": links}
