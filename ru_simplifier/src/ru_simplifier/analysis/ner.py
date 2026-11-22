# -*- coding: utf-8 -*-
"""NER через spaCy ru_core_news_lg (Фаза 1).

Здесь живёт ЕДИНЫЙ синглтон nlp-трубы (parser + NER), который переиспользуют
parse.py и pipeline. Модель загружается один раз на процесс; в runtime сеть
не нужна (модель ставится заранее: python -m spacy download ru_core_news_lg).
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

_NLP = None
_NLP_LOCK = threading.Lock()


def get_spacy_nlp():
    """Ленивый потокобезопасный синглтон spaCy Pipeline (загрузка один раз).

    Имя модели берётся из config.yaml (models.spacy); по умолчанию ru_core_news_lg.
    Теггер не используется — в контракт входят только UPOS/morph/dep/ner.
    """
    global _NLP
    if _NLP is None:
        with _NLP_LOCK:
            if _NLP is None:
                import spacy
                from ru_simplifier.config import load_config

                cfg = load_config()
                model_name = (cfg.get("models", {}) or {}).get("spacy", "ru_core_news_lg")
                try:
                    nlp = spacy.load(model_name, exclude=["lemmatizer", "tagger"])
                except OSError as e:  # модель не установлена — понятная ошибка
                    raise RuntimeError(
                        f"spaCy-модель '{model_name}' не найдена. "
                        f"Установите её ОДИН РАЗ вне runtime: "
                        f"`python -m spacy download {model_name}`"
                    ) from e
                _NLP = nlp
    return _NLP


def extract_ner(doc) -> List[Dict[str, Any]]:
    """NER-спансы из готового spaCy Doc.

    Возвращает [{"text", "start", "end", "label"}] со смещениями внутри doc.text.
    Метки: PER/ORG/LOC/MISC (ru_core_news_sm/lg — корпус native).
    """
    return [
        {"text": ent.text, "start": ent.start_char, "end": ent.end_char, "label": ent.label_}
        for ent in doc.ents
    ]


def parse_sentence_with_ner(text: str):
    """Внутренний хелпер: полный разбор предложения одним прогоном трубы.

    Возвращает (doc, tokens_dicts, ner_spans) — используется pipeline для
    однократного прогона модели на предложение (детерминизм + скорость).
    """
    nlp = get_spacy_nlp()
    doc = nlp(text.strip())
    return doc
