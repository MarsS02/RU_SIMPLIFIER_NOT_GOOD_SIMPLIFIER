# -*- coding: utf-8 -*-
"""Точка входа Фазы 1: analyze_text(text) -> AnalyzedSentence (dict).

Конвейер (полностью детерминированный, INV-4):
    normalize -> segment (razdel) -> spaCy ru_core_news_lg (parse+NER за один прогон)
              -> pymorphy3 (лемма + грамматики) -> сборка контракта.

Важно:
  * spaCy-токенизация первична для токенов предложения (она даёт head/dep/morph);
    текст предложения вырезается из нормализованного входа по span'у doc'а,
    поэтому "text" == конкатенация "text" токенов — потерь нет (INV-1 на уровне формы);
  * модели (spaCy, pymorphy3) грузятся один раз — синглтоны в ner.py / morph.py;
  * сеть в runtime не используется.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ru_simplifier.analysis import ner as ner_mod
from ru_simplifier.analysis import morph as morph_mod
from ru_simplifier.analysis.normalize import normalize_text
from ru_simplifier.analysis.segment import segment_sentences
from ru_simplifier.config import get_logger, load_config
from ru_simplifier.contracts import (
    AnalyzedSentence,
    NERSpan,
    SentenceAnalysis,
    TokenInfo,
)

log = get_logger("pipeline")


def _sentence_ner_spans(doc, sent_start_in_core: int) -> List[NERSpan]:
    """NER-спансы; start/end — символьные отступы внутри текста предложения.

    (Контракт AnalyzedSentence: смещения относятся к тексту предложения.)
    sent_start_in_core — сдвиг core-текста относительно начала предложения
    (обычно 0; ненулевой, если у предложения есть ведущие пробелы).
    """
    spans: List[NERSpan] = []
    for ent in doc.ents:
        spans.append(NERSpan(
            text=ent.text,
            start=sent_start_in_core + ent.start_char,
            end=sent_start_in_core + ent.end_char,
            label=ent.label_,
        ))
    return spans


def _per_token_ner(doc) -> List[Optional[str]]:
    """Метка NER для каждого токена doc'а (или None)."""
    token_labels: List[Optional[str]] = [None] * len(doc)
    for ent in doc.ents:
        for tok in ent:
            token_labels[tok.i] = ent.label_
    return token_labels


def analyze_text(text: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Детерминированный анализ текста. Возвращает dict по контракту AnalyzedSentence.

    :param text: исходный русский текст (одно или несколько предложений).
    :param config: необязательная конфигурация поверх config.yaml (для тестов).
    """
    cfg = load_config()
    if config:
        cfg = {**cfg, **config}
    norm_yo = bool(((cfg.get("normalize", {}) or {}).get("normalize_yo", False)))

    normalized = normalize_text(text, normalize_yo=norm_yo)
    log.info("analyze_text: вход %d симв., после нормализации %d симв.",
             len(text or ""), len(normalized))

    analyzed = AnalyzedSentence(text=normalized)
    sents = segment_sentences(normalized)
    nlp = ner_mod.get_spacy_nlp()  # загрузка один раз (синглтон)

    for sid, sent in enumerate(sents):
        stripped = sent["text"]
        lead_ws = len(stripped) - len(stripped.lstrip())
        core = stripped.strip()

        doc = nlp(core)  # parse + NER за один прогон, детерминированно
        token_labels = _per_token_ner(doc)

        tokens: List[TokenInfo] = []
        root_idx: Optional[int] = None
        for tok in doc:
            mp = morph_mod.parse_word(tok.text)
            lemma = mp["lemma"] if mp else tok.text.lower()
            # морфология: приоритет у Feat'а spaCy (контекстная), дополняем pymorphy3
            morph_dict: Dict[str, str] = {}
            for feat_key in ("Case", "Number", "Gender", "Tense", "Aspect",
                             "Mood", "Voice", "Person", "Animacy", "Degree"):
                val = tok.morph.get(feat_key)
                if val:
                    morph_dict[feat_key] = "|".join(val)
            if mp and not morph_dict:
                morph_dict = dict(mp["grammemes"])

            is_root = tok.dep_ == "root"
            if is_root:
                root_idx = tok.i
            head_idx = tok.head.i  # 0-based; у корня head.i == i (самоуказание)

            tokens.append(TokenInfo(
                id=tok.i,
                text=tok.text,
                lemma=lemma,
                pos=tok.pos_,
                morph=morph_dict,
                head=head_idx,
                dep=tok.dep_,
                ner=token_labels[tok.i],
                is_stop=bool(tok.is_stop),
            ))

        ner_spans = _sentence_ner_spans(doc, lead_ws)

        sent_obj = SentenceAnalysis(
            id=sid,
            text="".join(t.text for t in tokens),  # == core при согласованном спейсинге
            tokens=tokens,
            ner_spans=ner_spans,
            root=root_idx if root_idx is not None else 0,
        )
        analyzed.sentences.append(sent_obj)
        log.debug("предложение %d: %d токенов, root=%s, ents=%d",
                  sid, len(tokens), root_idx, len(ner_spans))

    log.info("analyze_text: готово, предложений=%d", len(analyzed.sentences))
    return analyzed.to_dict()
