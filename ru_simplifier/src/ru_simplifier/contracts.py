# -*- coding: utf-8 -*-
"""Контракты данных ru_simplifier (JSON-схемы в виде dataclasses).

РЕАЛИЗОВАНО в Фазе 1: AnalyzedSentence и вложенные структуры токенов/spans.
СХЕМЫ ЗАФИКСИРОВАНЫ, РЕАЛИЗАЦИЯ ПОЗЖЕ:
  Proposition      — Фаза 2 (извлечение пропозиций)
  RhetoricalLink   — Фаза 2 (риторические связи)
  SimplificationOp — Фаза 3 (безопасные операторы)
  Result           — Фаза 7 (итоговый результат упрощения)

Все to_dict() детерминированны (INV-4): поля сериализуются в фиксированном
порядке, соответствующем контракту.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ======================= Фаза 1: реализовано =======================

@dataclass
class TokenInfo:
    """Один токен предложения по контракту AnalyzedSentence."""
    id: int
    text: str
    lemma: str
    pos: str                      # UPOS (XPOS не входит в контракт)
    morph: Dict[str, str]         # {"Case": "Dat", "Number": "Sing", ...}
    head: int                     # индекс head-токена в этом же предложении
    dep: str                      #relational dependency label
    ner: Optional[str]            # "PER" | "ORG" | ... | None
    is_stop: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "lemma": self.lemma,
            "pos": self.pos,
            "morph": dict(self.morph),
            "head": self.head,
            "dep": self.dep,
            "ner": self.ner,
            "is_stop": self.is_stop,
        }


@dataclass
class NERSpan:
    """Именованная сущность; start/end — символы внутри текста предложения."""
    text: str
    start: int
    end: int
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end, "label": self.label}


@dataclass
class SentenceAnalysis:
    """Разобранное предложение по контракту AnalyzedSentence."""
    id: int
    text: str
    tokens: List[TokenInfo] = field(default_factory=list)
    ner_spans: List[NERSpan] = field(default_factory=list)
    root: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "tokens": [t.to_dict() for t in self.tokens],
            "ner_spans": [s.to_dict() for s in self.ner_spans],
            "root": self.root,
        }


@dataclass
class AnalyzedSentence:
    """Верхний контракт Фазы 1: результат analyze_text()."""
    text: str
    sentences: List[SentenceAnalysis] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "sentences": [s.to_dict() for s in self.sentences],
        }


# ======================= Схемы (реализация — позже) =======================

@dataclass
class Proposition:
    """Схема (Фаза 2): атомарное смысловое утверждение.

    Пример:
      {"id":"p3","predicate":"лечь_в_основу",
       "args":{"subj":"зарубежный опыт","obj":"дальнейшая застройка"},
       "polarity":"+","modality":"real","tense":"past"}
    INV-1: покрытие пропозиций выходного текста = 1.0.
    INV-2: args обязаны сохранять имена, числа, даты, термины, отрицание, модальность.
    """
    id: str
    predicate: str
    args: Dict[str, str] = field(default_factory=dict)
    polarity: str = "+"                 # "+" | "-"
    modality: str = "real"              # real | irrealis | deontic | dynamic | epistemic
    tense: str = "present"              # past | present | future | infinitive

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "predicate": self.predicate,
            "args": dict(self.args),
            "polarity": self.polarity,
            "modality": self.modality,
            "tense": self.tense,
        }

    @staticmethod
    def extract(analyzed: Optional[AnalyzedSentence]) -> List["Proposition"]:
        """Извлечение пропозиций — Фаза 2. Здесь только контракт."""
        raise NotImplementedError("Proposition.extract: реализация в Фазе 2")


@dataclass
class RhetoricalLink:
    """Схема (Фаза 2): риторическая связь между пропозициями.

    Пример: {"type":"concession","from":"p2","to":"p3","marker":"хотя"}
    Ключ "from" — зарезервированное слово Python, поэтому в dataclass поле
    называется `frm`; конструктор принимает и "from", и "frm" (эквивалентно).
    """
    type: str                           # concession | cause | condition | contrast | ...
    frm: str = ""                       # id исходной пропозиции ("from" в JSON)
    to: str = ""                        # id целевой пропозиции
    marker: Optional[str] = None        # поверхностный маркер ("хотя", "поэтому", ...)

    def __post_init__(self) -> None:
        if not self.frm:
            raise ValueError("RhetoricalLink: поле 'from'/'frm' обязательно")

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "RhetoricalLink":
        """Детерминированный конструктор из JSON-словаря контракта."""
        dd = dict(d)
        frm = dd.pop("from", None)
        if frm is not None:
            dd["frm"] = frm
        return cls(**dd)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "from": self.frm, "to": self.to, "marker": self.marker}

    @staticmethod
    def extract(analyzed: Optional[AnalyzedSentence],
                propositions: Optional[List[Proposition]] = None) -> List["RhetoricalLink"]:
        """Извлечение риторических связей — Фаза 2. Здесь только контракт."""
        raise NotImplementedError("RhetoricalLink.extract: реализация в Фазе 2")


@dataclass
class SimplificationOp:
    """Схема (Фаза 3): одна безопасная операция над формой текста.

    Пример: {"type":"split_clause","target":"p3","safe":true,"reason":"..."}
    INV-6: допускаются только операторы из whitelist resources/operators.yaml.
    """
    type: str                           # split_clause | move_adj | ... (whitelist)
    target: str                         # id цели (пропозиция/предложение)
    safe: bool = True
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "target": self.target, "safe": self.safe, "reason": self.reason}

    def apply(self, *args: Any, **kwargs: Any) -> Any:
        """Применение операторов — Фаза 3. Здесь только контракт."""
        raise NotImplementedError("SimplificationOp.apply: реализация в Фазе 3")


@dataclass
class Result:
    """Схема (Фаза 7): итоговый результат упрощения.

    Пример:
      {"original":"...","simplified":"...","ops":[],"coverage":1.0,
       "nli":0.97,"readability":{"before":32,"after":68}}
    coverage < 1.0 или nli ниже порога => упрощение отклоняется верификатором (Фаза 5).
    """
    original: str
    simplified: str
    ops: List[SimplificationOp] = field(default_factory=list)
    coverage: float = 1.0               # INV-1
    nli: float = 1.0                    # INV-3
    readability: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "simplified": self.simplified,
            "ops": [o.to_dict() for o in self.ops],
            "coverage": self.coverage,
            "nli": self.nli,
            "readability": dict(self.readability),
        }

    @staticmethod
    def simplify(text: str) -> "Result":
        """Упрощение — Фазы 3-7. Здесь только контракт."""
        raise NotImplementedError("Result.simplify: реализация в Фазе 7")
