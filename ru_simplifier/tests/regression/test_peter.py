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
