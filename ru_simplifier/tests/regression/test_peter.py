# -*- coding: utf-8 -*-
"""Приёмочный регрессионный тест «Пётр» (Фаза 0/1).

Смысл ассертов фиксирован: одна фраза, NER PER=Петра, ключевые леммы,
наличие подчинительной клаузы, детерминизм, UTF-8 round-trip.
Допустимо уточнять конкретные dep-метки по фактической модели ru_core_news_lg,
но смысл проверок менять нельзя.
"""
import pytest

from ru_simplifier.pipeline import analyze_text

PETER = ("Хотя мечте Петра не суждено было сбыться, именно зарубежный опыт лёг в основу "
         "дальнейшей застройки, что в конечном итоге предопределило архитектурный облик "
         "города на многие десятилетия вперёд.")


def test_peter_single_sentence():
    r = analyze_text(PETER)
    assert len(r["sentences"]) == 1


def test_peter_ner_person():
    r = analyze_text(PETER)
    spans = [(s["text"], s["label"]) for sent in r["sentences"] for s in sent["ner_spans"]]
    assert any("Петра" in t and lab == "PER" for t, lab in spans)


def test_peter_key_lemmas():
    r = analyze_text(PETER)
    lemmas = {t["lemma"].lower() for sent in r["sentences"] for t in sent["tokens"]}
    for w in ["мечта", "зарубежный", "опыт", "застройка", "облик", "город"]:
        assert w in lemmas, f"нет леммы {w}"


def test_peter_has_subordinate_clause():
    r = analyze_text(PETER)
    deps = {t["dep"] for sent in r["sentences"] for t in sent["tokens"]}
    assert deps & {"advcl", "ccomp", "parataxis", "acl"}, "нет подчинительной клаузы"


def test_determinism():
    assert analyze_text(PETER) == analyze_text(PETER)


def test_utf8_roundtrip():
    r = analyze_text("Привет, мир!")
    assert r["sentences"][0]["text"].startswith("Привет")


# ================= ФАЗА 2: пропозиции и риторические связи =================

from ru_simplifier.semantics import run as semantics_run


def test_peter_propositions():
    analyzed = analyze_text(PETER)
    result = semantics_run(analyzed)
    # P2: "мечта не сбылась"
    assert any(p["predicate"] == "сбыться" and p["polarity"] == "-"
               for p in result["propositions"])
    # P3: "опыт лёг в основу"
    assert any(p["predicate"] == "лечь" and "опыт" in p["args"].get("subj", "")
               for p in result["propositions"])
    # P4: "предопределило облик"
    assert any(p["predicate"] == "предопределить" for p in result["propositions"])


def test_peter_links():
    analyzed = analyze_text(PETER)
    result = semantics_run(analyzed)
    # Уступка: "Хотя P2 → P3"
    assert any(link["type"] == "concession" for link in result["links"])
    # Следствие: P3 → P4 ("что в конечном итоге")
    assert any(link["type"] == "result" for link in result["links"])


def test_semantics_determinism():
    analyzed1 = analyze_text(PETER)
    analyzed2 = analyze_text(PETER)
    result1 = semantics_run(analyzed1)
    result2 = semantics_run(analyzed2)
    assert result1 == result2


def test_peter_proposition_ids_consistent():
    """Каждая связь ссылается только на существующие id пропозиций."""
    result = semantics_run(analyze_text(PETER))
    ids = {p["id"] for p in result["propositions"]}
    for link in result["links"]:
        assert link["from"] in ids and link["to"] in ids
