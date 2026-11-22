# -*- coding: utf-8 -*-
"""Фаза 2: детерминированное извлечение пропозиций из dep-дерева (INV-4).

Алгоритм (на предложение):
  1. Находим клаузальные ядра — токены с dep в {ROOT, root, advcl, ccomp,
     parataxis, acl, acl:relcl}, чей лемма — глагол (UPOS VERB/AUX) либо
     pymorphy3 даёт INFN/VERB (страховка от ошибок POS-тэга модели, напр.
     'лёг' -> NOUN в ru_core_news_lg), либо предикативное слово
     (ADJshort / предикатив типа 'суждено', 'можно', 'нужно').
  2. Ядро клаузы = ближайший предок-клаузальное ядро; корневая клауза — то,
     у которого предка среди ядер нет.
  3. Для каждой клаузы извлекаем:
       predicate — лемма ядра (инфинитив через pymorphy3);
       args.subj — nsubj / csubj (+ nominal subject для предикативных
                  клауз) / obl и iobj в дативе (безличные конструкции:
                  'мечте ... не суждено' -> subj='мечта');
       args.obj  — dobj / obj / obl с case-предлогом (вин./род./др.),
                  склеивается с зависимыми amod/nmod чисел и дат (INV-2);
       polarity  '-' если в поддереве клаузы есть PART 'не';
       modality  поверхностная строка отрицания/модальности
                 ('не суждено', 'можно', 'должен', ...) или 'real';
       tense     Past/Present/Future из morph, INFN -> 'infinitive'.
  4. Имена собственные (ner=PER/ORG/LOC), числа (NUM) и даты сохраняются в
     args как есть — защита содержимого (INV-2, INV-3).

Никакого рандома, никакого network: только входной AnalyzedSentence +
pymorphy3 (кэш Фазы 1). Порядок пропозиций детерминирован: по предложениям,
внутри предложения — по индексу токена ядра.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ru_simplifier.analysis import morph as morph_mod

# Dep-метки, помечающие начало содержательной клаузы (INV-1: ни одна такая
# клауза не должна теряться при извлечении).
CLAUSE_DEPS = {"root", "advcl", "ccomp", "parataxis", "acl", "acl:relcl"}

# Аргументные деппозиции подлежащего.
SUBJ_DEPS = ("nsubj", "csubj", "nsubjpass", "csubjpass", "expl:subj")

# Предикативные слова (состояние/невозможность/обязанность), образующие
# безличную предикативную клаузу даже без глагола.
PREDICATIVE_LEMMAS = {
    "суждено", "нельзя", "можно", "нужно", "надо", "должен", "следует",
    "стоит", "известно", "ясно", "понятно", "жаль", "пора", "стоит",
}

MODAL_LEMMAS = {
    "мочь", "смочь", "мочь", "должен", "должно", "должны", "надо", "нужно",
    "следует", "стоит", "хотеть", "желать", "планировать", "собираться",
    "намерен", "может", "возможно", "казаться", "приходиться", "удаваться",
}

# Маркеры причинно-следственных/уступительных связей (используются links.py,
# здесь нужны чтобы корректно относить mark-зависимости к клаузе).
CONCESSION_MARKERS = {"хотя", "пускай", "несмотря", " невзирая"}
RESULT_MARKERS = {"поэтому", "следовательно", "значит", "итого"}


def _is_verb_like(tok: Dict[str, Any]) -> bool:
    """Глагольность токена: UPOS spaCy + страховка через pymorphy3 (lemma-tag)."""
    if tok["pos"] in ("VERB", "AUX"):
        return True
    mp = morph_mod.parse_word(tok["text"])
    if mp and mp.get("pos") in ("VERB", "INFN"):
        return True
    return False


def _is_predicative(tok: Dict[str, Any]) -> bool:
    """Предикативное состояние: короткое прилагательное (ADJS) или лексический
    предикатив ('суждено', 'можно', 'нужно', ...)."""
    if tok["lemma"] in PREDICATIVE_LEMMAS:
        return True
    # в контракте AnalyzedCase морфология из spaCy Feat; короткая форма в
    # ru_core_news обычно не помечается отдельно — опираемся на лексикон +
    # POS=ADJ без Case у зависимого инфинитива-клаузы (см. heads-эвристику)
    return False


def _has_infinitive_child(by_idx, children, h: int) -> bool:
    """Есть ли у токена глагольный зависимый с инфинитивной леммой (-ть/-сь)."""
    for c in children.get(h, []):
        t = by_idx[c]
        if t["pos"] in ("VERB", "AUX") and (t["lemma"].endswith("ть")
                                            or t["lemma"].endswith("ти")):
            return True
    return False


def _core_predicate_lemma(tok: Dict[str, Any]) -> str:
    """Лемма-предикат клаузы: инфинитив для глаголов (через pymorphy3)."""
    lemma = tok["lemma"].lower()
    mp = morph_mod.parse_word(tok["text"])
    if mp and mp.get("pos") in ("VERB", "INFN"):
        # pymorphy3 normal_form уже инфинитив
        return mp["lemma"].lower()
    return lemma


def _phrase(tokens: List[Dict[str, Any]], idx: int) -> str:
    """Поверхностная фраза аргумента: ядро + preposition/amod/nmod(число/дата).

    Сохраняем числительные и даты целиком (INV-2): 'на многие десятилетия'
    -> 'многие десятилетия', '1991 год' -> '1991 год'.
    """
    head = tokens[idx]
    parts: List[Dict[str, Any]] = [head]
    for j, t in enumerate(tokens):
        if j == idx:
            continue
        if t["head"] == idx and t["dep"] in ("amod", "nummod", "compound",
                                             "appos", "nmod:poss"):
            parts.append(t)
        elif t["head"] == idx and t["dep"] == "case":
            # предлог включаем только если он перед ядром (детерминированно)
            pass
    # добавляем ведущий предлог, если он стоит непосредственно перед ядром
    if idx > 0 and tokens[idx - 1]["dep"] == "case" and tokens[idx - 1]["head"] == idx:
        parts.insert(0, tokens[idx - 1])
    parts.sort(key=lambda t: t["id"])
    phrase = " ".join(p["text"] for p in parts)
    # нормализация регистра сохраняем как есть — имена собственные важны (INV-2)
    return phrase.strip()


def _tense_of(tok: Dict[str, Any], is_clause_head: bool) -> str:
    morph = tok.get("morph") or {}
    t = morph.get("Tense")
    if t == "Past":
        return "past"
    if t == "Pres":
        return "present"
    if t == "Fut":
        return "future"
    mp = morph_mod.parse_word(tok["text"]) or {}
    tags = set(mp.get("tags") or [])
    if "INFN" in tags:
        return "infinitive"
    if "PRTF" in tags or "GRND" in tags:
        # причастие/деепричастие: время из вспомогательного контекста
        return "past" if "PAST" in tags else "present"
    if mp.get("pos") == "VERB":
        return "present"
    return "present"


def extract_from_sentence(sent: Dict[str, Any], start_id: int) -> List[Dict[str, Any]]:
    """Пропозиции одного предложения. start_id — первый свободный id (p{n})."""
    tokens: List[Dict[str, Any]] = sent["tokens"]
    if not tokens:
        return []

    children: Dict[int, List[int]] = {t["id"]: [] for t in tokens}
    for t in tokens:
        children.setdefault(t["head"], []).append(t["id"])
    by_idx = {t["id"]: t for t in tokens}

    def subtree_indices(root: int) -> List[int]:
        out, stack = [], [root]
        while stack:
            i = stack.pop()
            out.append(i)
            stack.extend(children.get(i, []))
        return sorted(out)

    # ---- 1. ядра клауз --------------------------------------------------
    heads: List[int] = []
    for t in tokens:
        dep = t["dep"]
        if dep in CLAUSE_DEPS and (_is_verb_like(t) or _is_predicative(t)):
            heads.append(t["id"])
        elif dep in ("advcl", "csubj", "ccomp", "parataxis") and t["pos"] == "ADJ" \
                and _has_infinitive_child(by_idx, children, t["id"]):
            # предиктив с зависимым инфинитивом — клаузальное ядро
            # ('не суждено было сбыться')
            heads.append(t["id"])
    # корень предложения: dep ROOT/root может быть не у глагола (ошибка модели,
    # напр. 'лёг' помечен NOUN). Берём token с self-head и проверяем verb-like.
    root_tok = by_idx.get(sent.get("root", 0))
    if root_tok is not None and root_tok["id"] not in heads:
        if _is_verb_like(root_tok) or _is_predicative(root_tok):
            heads.append(root_tok["id"])
    heads = sorted(set(heads))
    if not heads:
        return []

    head_set = set(heads)

    def clause_parent(h: int) -> Optional[int]:
        cur = by_idx[h]["head"]
        seen = set()
        while cur != h and cur not in seen:
            seen.add(cur)
            if cur in head_set:
                return cur
            cur = by_idx[cur]["head"]
        return None

    # ---- 2. сбор пропозиций --------------------------------------------
    propositions: List[Dict[str, Any]] = []
    for h in heads:
        core = by_idx[h]
        sub = set(subtree_indices(h))
        # исключаем поддерево дочерних клауз (их аргументы принадлежат им)
        for other in heads:
            if other != h and clause_parent(other) == h:
                sub -= set(subtree_indices(other))

        # predicate
        predicate = _core_predicate_lemma(core)

        # subj / obj
        args: Dict[str, str] = {}
        subj_candidates: List[str] = []
        obl_dat: List[str] = []
        obj_candidates: List[str] = []
        for i in sorted(sub):
            t = by_idx[i]
            if t["id"] == h:
                continue
            # прямой аргумент клаузы — зависимость непосредственно от ядра
            if t["head"] != h:
                continue
            if t["dep"] in SUBJ_DEPS:
                subj_candidates.append(_phrase(tokens, i))
            elif t["dep"] in ("iobj", "obl") and (t.get("morph") or {}).get("Case") == "Dat":
                obl_dat.append(_phrase(tokens, i))
            elif t["dep"] in ("obj", "dobj", "obl_agent"):
                obj_candidates.append(_phrase(tokens, i))
            elif t["dep"] == "obl" and (t.get("morph") or {}).get("Case") in ("Acc", "Gen"):
                obj_candidates.append(_phrase(tokens, i))
        # номинальный субъект для предикативных клауз (если ядро не глагол)
        if not subj_candidates and not _is_verb_like(core):
            for i in sorted(sub):
                t = by_idx[i]
                if t["head"] == h and t["dep"] in ("nsubj", "npadvmod"):
                    subj_candidates.append(_phrase(tokens, i))

        if subj_candidates:
            args["subj"] = "; ".join(dict.fromkeys(subj_candidates))
        elif obl_dat:
            # безличная конструкция: дативный экспириент/пациент -> subj
            args["subj"] = "; ".join(dict.fromkeys(obl_dat))
        if obj_candidates:
            args["obj"] = "; ".join(dict.fromkeys(obj_candidates))

        # polarity / modality
        neg_tok = None
        modal_words: List[str] = []
        for i in sorted(sub):
            t = by_idx[i]
            if t["dep"] == "advmod" and t["head"] == h and t["lemma"] == "не":
                neg_tok = t
            if t["lemma"] in MODAL_LEMMAS and _is_verb_like(t) and t["id"] != h:
                modal_words.append(t["text"].lower())
            if _is_predicative(t) and t["id"] != h:
                modal_words.append(t["lemma"])
        polarity = "-" if neg_tok is not None else "+"

        # modality: поверхностная строка. Если ядро само предикатив/модал —
        # модалити = ядро (+отрицание). Иначе 'real' или перечисление слов.
        if neg_tok is not None and _is_predicative(core):
            modality = f"не {core['lemma']}"
        elif neg_tok is not None:
            modality = "не " + " ".join(modal_words) if modal_words else "не " + predicate
        elif _is_predicative(core):
            modality = core["lemma"]
        elif modal_words:
            modality = " ".join(sorted(set(modal_words)))
        else:
            modality = "real"

        tense = _tense_of(core, True)
        # если ядро — предиктив, а в поддереве есть cop/инфинитив, берём
        # tense из него (было/будет)
        for i in sorted(sub):
            t = by_idx[i]
            if t["dep"] == "cop" and t["head"] == h:
                tt = _tense_of(t, False)
                if tt in ("past", "future"):
                    tense = tt
        # инфинитивное ядро (сбыться) при предиктиве -> tense infinitive?
        # Контракт примера: P2 tense past ('не суждено было') — оставляем past
        # из cop 'было'.

        propositions.append({
            "id": f"p{start_id + len(propositions)}",
            "predicate": predicate,
            "args": args,
            "polarity": polarity,
            "modality": modality,
            "tense": tense,
            "_head": h,          # служебное (удаляется перед возвратом)
            "_parent": clause_parent(h),
            "_span": sorted(sub),
            "_marker": _clause_marker(by_idx, children, h),
        })

    return propositions


def _clause_marker(by_idx: Dict[int, Dict[str, Any]],
                   children: Dict[int, List[int]], h: int) -> Optional[str]:
    """Поверхностный союз-маркер клаузы (mark-зависимость от ядра)."""
    for c in sorted(children.get(h, [])):
        t = by_idx[c]
        if t["dep"] == "mark":
            return t["text"]
    return None


def extract(analyzed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Все пропозиции текста. Возвращает dict'ы строго по контракту Proposition."""
    result: List[Dict[str, Any]] = []
    next_id = 1
    for sent in analyzed.get("sentences", []):
        props = extract_from_sentence(sent, next_id)
        next_id += len(props)
        result.extend(props)
    # чистим служебные поля, фиксируем порядок ключей (INV-4)
    cleaned: List[Dict[str, Any]] = []
    for p in result:
        cleaned.append({
            "id": p["id"],
            "predicate": p["predicate"],
            "args": dict(p["args"]),
            "polarity": p["polarity"],
            "modality": p["modality"],
            "tense": p["tense"],
        })
    return cleaned
