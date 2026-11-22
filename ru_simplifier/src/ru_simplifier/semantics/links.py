# -*- coding: utf-8 -*-
"""Фаза 2: детерминированное извлечение риторических связей (INV-4).

Связь — это отношение между двумя пропозициями, маркированное:
  * dep-структурой (advcl / ccomp / parataxis + mark-союз), и/или
  * лексическими маркерами (хотя, поэтому, что, и, затем, ...).

Типология (фиксированный словарь):
  concession — уступка:   'хотя', 'несмотря на', 'невзирая на', 'пускай'
  result     — следствие: 'что' (коррелят 'именно... , что'), 'поэтому',
               'так что', 'следовательно', 'значит'
  cause      — причина:   'потому что', 'ибо', 'благодаря', 'из-за'
  condition  — условие:   'если', 'при условии', 'коль скоро'
  contrast   — противопоставление: 'но', 'однако', 'зато', 'а'
  sequence   — последовательность: 'и', 'затем', 'потом', 'после'

Правило направления: from — подчинённая/маркированная пропозиция,
to — главная (или предшествующая в случае parataxis-следствия).

Реализация опирается только на AnalyzedSentence (Фаза 1) и служебные поля
пропозиций (_head/_parent/_marker/_span), которые propositions.py сохраняет
для внутреннего использования links.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

CONCESSION = {"хотя", "пускай", "пусть", "несмотря", "невзирая"}
RESULT_ADV = {"поэтому", "следовательно", "значит", "итого", "такие"}
RESULT_REL_PRONOUN = "что"          # 'что в конечном итоге...' -> следствие
CAUSE = {"потому", "ибо", "благодаря", "из-за", "так.как"}
CONDITION = {"если", "коли", "коль", "предположим"}
CONTRAST = {"но", "однако", "зато", "а", "же"}
SEQUENCE = {"затем", "потом", "после", "далее", "и"}


def _classify_marker(marker: Optional[str],
                     by_idx: Dict[int, Dict[str, Any]],
                     head: int) -> Optional[str]:
    """Определить тип связи по союзу-маркеру клаузы."""
    if not marker:
        return None
    lem = marker.lower().strip(",.;:")
    # многокомпонентные союзы: 'так как', 'несмотря на', 'в результате чего'
    if lem in CONCESSION:
        return "concession"
    if lem in RESULT_ADV:
        return "result"
    if lem in CAUSE or lem == "потому":
        # 'потому что' — mark может быть 'потому' с дочерним 'что'
        return "cause"
    if lem in CONDITION or lem == "если":
        return "condition"
    if lem in CONTRAST:
        return "contrast"
    if lem in SEQUENCE and lem != "и":
        return "sequence"
    if lem == "и":
        return "sequence"
    if lem == RESULT_REL_PRONOUN:
        # союзное 'что' при глагольном ядре придаточного — связь результата/
        # изложения; тип уточняется ниже по контексту (см. extract)
        return "result"
    return None


def extract(analyzed: Dict[str, Any],
            props_internal: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Связи между пропозициями.

    :param props_internal: пропозиции WITH служебными полями
        (_head, _parent, _marker, _span) из propositions.extract_from_sentence.
    """
    links: List[Dict[str, Any]] = []
    seen = set()

    def add(link_type: str, frm: str, to: str, marker: Optional[str]) -> None:
        key = (link_type, frm, to, marker)
        if frm == to or key in seen:
            return
        seen.add(key)
        links.append({
            "type": link_type,
            "from": frm,
            "to": to,
            "marker": marker,
        })

    # группируем пропозиции по предложениям, строим карту token->prop id
    for sent in analyzed.get("sentences", []):
        tokens = {t["id"]: t for t in sent["tokens"]}
        props = [p for p in props_internal
                 if p["_head"] in tokens and _same_sent(p, sent)]
        by_head = {p["_head"]: p for p in props}

        for p in props:
            parent = p.get("_parent")
            if parent is None or parent not in by_head:
                continue
            q = by_head[parent]
            marker = p.get("_marker")
            ltype = _classify_marker(marker, tokens, p["_head"])

            # спецслучай: придаточное следствия 'что в конечном итоге ...'
            # — маркер отсутствует в dep-дереве (что=nsubj), классифицируем
            # по местоимению-подлежащему + advmod-адвербиалу итога
            if ltype is None and marker is None:
                ltype = _infer_result_by_structure(tokens, p)

            if ltype is None:
                # неизвестный союз => консервативно не создаём связь
                continue

            # направление: from — подчинённая (p), to — главная (q)
            add(ltype, p["id"], q["id"], marker or _surface_marker(tokens, p))

    # порядок связей детерминирован: сортировка по (from, to, type, marker)
    links.sort(key=lambda l: (l["from"], l["to"], l["type"], l["marker"] or ""))
    return links


def _same_sent(prop: Dict[str, Any], sent: Dict[str, Any]) -> bool:
    ids = {t["id"] for t in sent["tokens"]}
    return prop["_head"] in ids


def _surface_marker(tokens: Dict[int, Dict[str, Any]],
                    prop: Dict[str, Any]) -> Optional[str]:
    """Первый содержательный токен клаузы как поверхностный маркер."""
    span = [i for i in prop.get("_span", []) if i in tokens]
    if not span:
        return None
    first = tokens[min(span)]
    if first["pos"] in ("SCONJ", "CCONJ", "PART", "ADV"):
        return first["text"]
    return None


def _infer_result_by_structure(tokens: Dict[int, Dict[str, Any]],
                               prop: Dict[str, Any]) -> Optional[str]:
    """Придаточное изложения/следствия без mark-союза в дереве.

    Признак: подлежащее — союзное 'что' + модальный/adverbial контекст
    ('в конечном итоге', 'в результате') или перфективный глагол.
    """
    span = set(prop.get("_span", []))
    has_chto_nsubj = False
    has_outcome_adv = False
    for i, t in tokens.items():
        if i not in span:
            continue
        if t["dep"] in ("nsubj", "nsubjpass") and t["lemma"] == "что":
            has_chto_nsubj = True
        if t["dep"] == "obl" and t["lemma"] in ("итог", "результат", "конце"):
            has_outcome_adv = True
    if has_chto_nsubj:
        return "result" if (has_outcome_adv or prop.get("tense") == "past") else None
    return None
