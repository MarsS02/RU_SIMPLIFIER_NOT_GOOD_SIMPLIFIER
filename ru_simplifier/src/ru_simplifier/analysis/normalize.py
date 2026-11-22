# -*- coding: utf-8 -*-
"""Нормализация текста (Фаза 1).

Правила:
  * переносы строк/табуляции/\r -> пробелы;
  * схлопывание последовательностей пробелов в один;
  * пробел перед знаком препинания удаляется, после — добавляется (если нужно);
  * знаки препинания НЕ теряются;
  * опция normalize_yo: расстановка "ё" там, где словарь pymorphy3 даёт
    лемму с "ё" (детерминированно, без эвристик угадывания).

Детерминизм (INV-4): чистая функция строки и флага, без случайности.
"""
from __future__ import annotations

import re
from typing import Optional

# Юникод-пробельные символы, включая NBSP и узкие пробелы.
_WS_RE = re.compile(r"[\s\u00a0\u2009\u202f\u205f\u3000\ufeff]+")

# Символы, перед которыми пробел не нужен (закрывающая пунктуация),
# и после которых пробел не нужен (открывающая).
_NO_SPACE_BEFORE = set(",.;:!?»)]}“\"…—–%°")
_NO_SPACE_AFTER = set("(«[{“")

# Ё-нормализация применяется только к кириллице.
_CYR_WORD_RE = re.compile(r"[А-Яа-яЁё]+")


def _fix_spacing(text: str) -> str:
    out = []
    for i, ch in enumerate(text):
        if ch == " ":
            # looking ahead: skip space if next non-space is no-space-before
            j = i + 1
            while j < len(text) and text[j] == " ":
                j += 1
            nxt = text[j] if j < len(text) else ""
            prv = text[i - 1] if i > 0 else ""
            if not out or (nxt in _NO_SPACE_BEFORE) or (prv in _NO_SPACE_AFTER) or nxt == "":
                continue
            out.append(" ")
        elif ch in _NO_SPACE_BEFORE and out and out[-1] != " " \
                and out[-1] not in _NO_SPACE_BEFORE:
            out.append(ch)
        elif ch in ",;:!?" and (not out or out[-1] != " "):
            out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def _add_space_after_punct(text: str) -> str:
    """Между «мир!И» -> «мир! И»: после закрывающей пунктуации нужен пробел,
    если дальше буква/цифра."""
    return re.sub(r"([,;:!?])(?=[0-9A-Za-zА-Яа-яЁё])", r"\1 ", text)


def normalize_text(text: str, normalize_yo: bool = False) -> str:
    """Очистка пробелов/переносов без потери знаков препинания.

    normalize_yo=True: замена е->ё по словарю (см. _yo_word).
    """
    if text is None:
        return ""
    t = _WS_RE.sub(" ", text).strip()
    t = _fix_spacing(t)
    t = _add_space_after_punct(t)
    if normalize_yo:
        t = _normalize_yo(t)
    return t


# ---------------- ё/е ----------------

def _yo_word(word: str) -> str:
    """Детерминированная расстановка 'ё' в одном слове по словарю pymorphy3.

    Если лемма слова содержит 'ё', а в поверхностной форме написано 'е' —
    заменяем 'е' на 'ё' посимвольно (с сохранением регистра). Это словарь,
    а не эвристика: одно слово -> одна лемма -> один результат (INV-4).
    """
    if "е" not in word.lower() and "Е" not in word:
        return word
    from ru_simplifier.analysis import morph as morph_mod

    parse = morph_mod.parse_word(word)  # кэш-синглтон внутри morph.py
    if not parse:
        return word
    lemma = parse["lemma"]
    if "ё" not in lemma and "Ё" not in lemma:
        return word
    # Лемма с 'ё' => приводим поверхностную форму к 'ё'-написанию.
    res = []
    for ch in word:
        if ch == "е":
            res.append("ё")
        elif ch == "Е":
            res.append("Ё")
        else:
            res.append(ch)
    return "".join(res)


def _normalize_yo(text: str) -> str:
    return _CYR_WORD_RE.sub(lambda m: _yo_word(m.group(0)), text)
