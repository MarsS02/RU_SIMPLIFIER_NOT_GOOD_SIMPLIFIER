# -*- coding: utf-8 -*-
"""Юнит-тесты Фазы 2: извлечение пропозиций и риторических связей.

TDD: контракты — dict-структуры SemanticsResult (propositions, links).
Детерминизм (INV-4) проверяется повторным прогоном run() на том же входе.
"""
from ru_simplifier.pipeline import analyze_text
from ru_simplifier.semantics import run


def _sem(text):
    return run(analyze_text(text))


# ---------- пропозиции: простые предложения ----------

def test_simple_intransitive():
    r = _sem("Кот спит.")
    preds = [p["predicate"] for p in r["propositions"]]
    assert "спать" in preds
    p = next(p for p in r["propositions"] if p["predicate"] == "спать")
    assert p["args"].get("subj", "").lower() == "кот"
    assert p["polarity"] == "+"
    assert p["tense"] == "present"


def test_transitive_obj():
    r = _sem("Пётр основал город.")
    p = next((p for p in r["propositions"] if p["predicate"] == "основать"), None)
    assert p is not None
    assert p["args"].get("subj", "").lower() == "петр"
    assert "город" in p["args"].get("obj", "").lower()
    assert p["tense"] == "past"


def test_negation_polarity():
    r = _sem("Кот не спит.")
    p = next(p for p in r["propositions"] if p["predicate"] == "спать")
    assert p["polarity"] == "-"
    # отрицание сохранено (INV-2)
    assert "не" in (p.get("modality") or "")


# ---------- связи ----------

def test_concession_link_hотя():
    r = _sem("Хотя шёл дождь, мы гуляли.")
    concessions = [l for l in r["links"] if l["type"] == "concession"]
    assert concessions, "нет связи concession для 'Хотя'"
    link = concessions[0]
    assert link["marker"].lower() == "хотя"
    # from — подчинённая пропозиция (шёл), to — главная (гуляли)
    by_id = {p["id"]: p for p in r["propositions"]}
    assert by_id[link["from"]]["predicate"] == "идти"
    assert by_id[link["to"]]["predicate"] == "гулять"


def test_result_link_chto():
    r = _sem("Опыт лёг в основу, что предопределило облик города.")
    assert any(l["type"] == "result" for l in r["links"])


def test_no_spurious_links_simple_sentence():
    r = _sem("Кот спит.")
    assert r["links"] == []


# ---------- инварианты ----------

def test_ids_unique_and_referenced():
    r = _sem("Хотя шёл дождь, мы гуляли, и ветер стих.")
    ids = [p["id"] for p in r["propositions"]]
    assert len(ids) == len(set(ids)), "дубли id пропозиций"
    for l in r["links"]:
        assert l["from"] in ids and l["to"] in ids


def test_unit_determinism():
    a = _sem("Хотя шёл дождь, мы гуляли.")
    b = _sem("Хотя шёл дождь, мы гуляли.")
    assert a == b
