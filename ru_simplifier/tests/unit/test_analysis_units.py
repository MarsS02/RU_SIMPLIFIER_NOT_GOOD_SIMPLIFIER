# -*- coding: utf-8 -*-
"""Юнит-тесты Фаз 0/1: нормализация, сегментация, морфология, контракты."""
import json

from ru_simplifier.analysis.normalize import normalize_text
from ru_simplifier.analysis.segment import segment_sentences, tokenize
from ru_simplifier.contracts import Proposition, RhetoricalLink, SimplificationOp, Result


# ---------- normalize ----------

def test_normalize_collapses_whitespace_and_newlines():
    src = "Первая   строка.\nВторая\tстрока.\r\nТретья."
    out = normalize_text(src)
    assert out == "Первая строка. Вторая строка. Третья."


def test_normalize_keeps_punctuation():
    src = "А! Б? В... Г, Д; Е:"
    out = normalize_text(src)
    for ch in "!?... ,; :":
        assert ch in out


def test_normalize_yo_option_off_by_default():
    src = "Петр встал рано и съел яйцо."
    assert normalize_text(src) == src  # без опции ё не трогаем


def test_normalize_yo_option_on():
    src = "Петр встал рано и съел яйцо."
    out = normalize_text(src, normalize_yo=True)
    assert "Пётр" in out and "яйцо" in out


def test_normalize_deterministic():
    src = "a  \n b\t\tc\r\nd"
    assert normalize_text(src) == normalize_text(src)


# ---------- segment ----------

def test_segment_two_sentences():
    sents = segment_sentences("Это первое. Это второе!")
    assert len(sents) == 2
    assert sents[0]["text"] == "Это первое."
    assert sents[1]["text"] == "Это второе!"
    assert sents[0]["start"] == 0


def test_segment_offsets_are_correct():
    text = "Привет, мир. Как дела?"
    for s in segment_sentences(text):
        assert text[s["start"]:s["end"]] == s["text"]


def test_tokenize_basic():
    toks = tokenize("Привет, мир!")
    texts = [t["text"] for t in toks]
    assert texts == ["Привет", ",", "мир", "!"]


def test_tokenize_offsets():
    text = "Привет, мир!"
    for t in tokenize(text):
        assert text[t["start"]:t["end"]] == t["text"]


# ---------- contracts (схемы зафиксированы, реализация — позже) ----------

def test_contracts_are_json_serializable_schemas():
    p = Proposition(id="p3", predicate="лечь_в_основу",
                    args={"subj": "зарубежный опыт", "obj": "дальнейшая застройка"},
                    polarity="+", modality="real", tense="past")
    assert p.to_dict()["predicate"] == "лечь_в_основу"

    rl = RhetoricalLink.from_json({"type": "concession", "from": "p2", "to": "p3", "marker": "хотя"})
    d = rl.to_dict()
    assert d["type"] == "concession" and d["from"] == "p2" and d["to"] == "p3"

    op = SimplificationOp(type="split_clause", target="p3", safe=True, reason="длинная клауза")
    assert op.to_dict()["safe"] is True

    res = Result(original="x", simplified="y", ops=[], coverage=1.0, nli=0.97,
                 readability={"before": 32, "after": 68})
    assert json.loads(json.dumps(res.to_dict(), ensure_ascii=False))["coverage"] == 1.0


def test_proposition_extract_not_implemented():
    """Фаза 2 не реализована: извлечение пропозиций должно быть NotImplemented."""
    with pytest.raises(NotImplementedError):
        Proposition.extract(None)


def test_semantics_operators_verify_are_placeholders():
    import ru_simplifier.semantics as semantics
    import ru_simplifier.operators as operators
    import ru_simplifier.verify as verify
    for mod in (semantics, operators, verify):
        with pytest.raises(NotImplementedError):
            mod.run(None)
