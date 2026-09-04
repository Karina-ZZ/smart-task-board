"""
Feature: Deterministic performance-metric scoring.

Responsibilities:
- Normalize Chinese/English business text and build 2-4 character n-gram TF-IDF vectors.
- Combine cosine similarity with weighted metric-keyword coverage.
- Apply organization/type rules and the approved 25/25/25/20/5 KPI formula.

Does not own: database reads/writes, authorization, HTTP DTOs, or confirmation state.
Plan task: DEV-14.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

SCORE_QUANT = Decimal("0.01")

# The dictionary is a safe fallback only. Deployments can override/extend it with
# system_parameters.performance_type_dictionary without changing the algorithm.
DEFAULT_TYPE_DICTIONARY: dict[str, tuple[str, ...]] = {
    "渠道": ("渠道", "经销商", "经销", "门店", "终端", "铺市", "分销"),
    "产品": ("产品", "新品", "sku", "产品线", "上市"),
    "销售": ("销售", "营收", "收入", "成交", "销售额", "gmv"),
    "运营": ("运营", "转化", "活跃", "留存", "增长"),
    "质量": ("质量", "缺陷", "合格", "稳定", "故障"),
    "效率": ("效率", "时效", "周期", "及时率", "准时"),
}

COMPANY_WIDE_UNITS = {
    "公司级",
    "全公司",
    "集团",
    "集团级",
    "通用",
    "company",
    "global",
    "all",
}


@dataclass(frozen=True)
class MatchScore:
    type_score: Decimal
    business_unit_score: Decimal
    metric_name_score: Decimal
    definition_formula_score: Decimal
    deliverable_score: Decimal
    total_score: Decimal
    match_level: str
    match_reason: str
    algorithm_version: str = "tfidf-char-ngram-v1"


def _score(value: float | Decimal) -> Decimal:
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    number = min(Decimal("100"), max(Decimal("0"), number))
    return number.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def normalize_text(value: object | None) -> str:
    """Normalize text without Chinese word segmentation or model dependencies."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[^0-9a-z%\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _segments(text: str) -> list[str]:
    return [segment for segment in normalize_text(text).split(" ") if segment]


def char_ngrams(value: object | None, min_n: int = 2, max_n: int = 4) -> Counter[str]:
    grams: Counter[str] = Counter()
    for segment in _segments(str(value or "")):
        # Single-character/numeric terms still need a searchable representation.
        if len(segment) < min_n:
            grams[segment] += 1
            continue
        for size in range(min_n, max_n + 1):
            if len(segment) < size:
                continue
            for index in range(len(segment) - size + 1):
                grams[segment[index : index + size]] += 1
    return grams


def build_idf(documents: Sequence[str]) -> dict[str, float]:
    """Build a smoothed IDF corpus from currently active performance metrics."""
    document_terms = [set(char_ngrams(document)) for document in documents]
    count = max(len(document_terms), 1)
    frequency: Counter[str] = Counter()
    for terms in document_terms:
        frequency.update(terms)
    return {
        term: math.log((1 + count) / (1 + doc_frequency)) + 1.0
        for term, doc_frequency in frequency.items()
    }


def _tfidf_vector(text: str, idf: Mapping[str, float]) -> dict[str, float]:
    counts = char_ngrams(text)
    total = sum(counts.values())
    if total <= 0:
        return {}
    default_idf = math.log(2.0) + 1.0
    return {
        term: (count / total) * idf.get(term, default_idf)
        for term, count in counts.items()
    }


def cosine_similarity(left: str, right: str, idf: Mapping[str, float]) -> float:
    left_vector = _tfidf_vector(left, idf)
    right_vector = _tfidf_vector(right, idf)
    if not left_vector or not right_vector:
        return 0.0
    shared = set(left_vector) & set(right_vector)
    numerator = sum(left_vector[term] * right_vector[term] for term in shared)
    left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / (left_norm * right_norm)))


def keyword_coverage(task_text: str, metric_text: str, idf: Mapping[str, float]) -> float:
    """Measure how much of the metric's discriminative text appears in the task."""
    task_terms = set(char_ngrams(task_text))
    metric_terms = set(char_ngrams(metric_text))
    if not metric_terms:
        return 0.0
    default_idf = math.log(2.0) + 1.0
    weights = {term: idf.get(term, default_idf) for term in metric_terms}
    denominator = sum(weights.values())
    if denominator <= 0:
        return 0.0
    numerator = sum(weight for term, weight in weights.items() if term in task_terms)
    return max(0.0, min(1.0, numerator / denominator))


def text_similarity(task_text: str, metric_text: str, idf: Mapping[str, float]) -> Decimal:
    if not normalize_text(task_text) or not normalize_text(metric_text):
        return Decimal("0.00")
    cosine = cosine_similarity(task_text, metric_text, idf)
    coverage = keyword_coverage(task_text, metric_text, idf)
    return _score(Decimal(str(100 * (0.80 * cosine + 0.20 * coverage))))


def _normalized_aliases(
    dictionary: Mapping[str, Iterable[str]] | None,
) -> dict[str, tuple[str, ...]]:
    source = dictionary or DEFAULT_TYPE_DICTIONARY
    return {
        normalize_text(key): tuple(
            alias for alias in (normalize_text(item) for item in values) if alias
        )
        for key, values in source.items()
        if normalize_text(key)
    }


def type_score(
    task_text: str,
    metric_type: str | None,
    idf: Mapping[str, float],
    type_dictionary: Mapping[str, Iterable[str]] | None = None,
) -> Decimal:
    metric = normalize_text(metric_type)
    task = normalize_text(task_text)
    if not metric or not task:
        return Decimal("0.00")
    aliases = _normalized_aliases(type_dictionary)
    candidate_aliases = {metric}
    for canonical, terms in aliases.items():
        if metric == canonical or metric in terms:
            candidate_aliases.update(terms)
            candidate_aliases.add(canonical)
    if any(alias and alias in task for alias in candidate_aliases):
        return Decimal("100.00")
    # Short type names can overfit; fuzzy fallback is intentionally capped at 80.
    return min(Decimal("80.00"), text_similarity(task, metric, idf))


def _alias_group(value: str, aliases: Mapping[str, Iterable[str]] | None) -> set[str]:
    normalized = normalize_text(value)
    group = {normalized} if normalized else set()
    for canonical, values in (aliases or {}).items():
        items = {normalize_text(canonical), *(normalize_text(item) for item in values)}
        if normalized in items:
            group.update(item for item in items if item)
    return group


def business_unit_score(
    task_business_unit: str | None,
    metric_business_unit: str | None,
    aliases: Mapping[str, Iterable[str]] | None = None,
) -> Decimal:
    task_unit = normalize_text(task_business_unit)
    metric_unit = normalize_text(metric_business_unit)
    if not metric_unit:
        return Decimal("0.00")
    if metric_unit in {normalize_text(item) for item in COMPANY_WIDE_UNITS}:
        return Decimal("70.00")
    if not task_unit:
        return Decimal("0.00")
    if _alias_group(task_unit, aliases) & _alias_group(metric_unit, aliases):
        return Decimal("100.00")
    return Decimal("0.00")


class PerformanceMatchScorer:
    """Reproducible scorer built from one active-metric corpus snapshot."""

    def __init__(
        self,
        metric_documents: Sequence[str],
        *,
        type_dictionary: Mapping[str, Iterable[str]] | None = None,
        business_unit_aliases: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        self.idf = build_idf(metric_documents)
        self.type_dictionary = type_dictionary
        self.business_unit_aliases = business_unit_aliases

    def score(
        self,
        *,
        task_name: str | None,
        task_description: str | None,
        task_goal: str | None,
        task_source: str | None,
        task_deliverable: str | None,
        task_business_unit: str | None,
        metric_type: str | None,
        metric_business_unit: str | None,
        metric_name: str | None,
        definition_formula: str | None,
        target_value: str | None,
        metric_deliverable: str | None,
        data_source: str | None,
    ) -> MatchScore:
        task_business_text = " ".join(
            filter(None, (task_name, task_description, task_goal, task_source))
        )
        name_task_text = " ".join(filter(None, (task_name, task_goal)))
        formula_task_text = " ".join(filter(None, (task_goal, task_description)))
        formula_metric_text = " ".join(
            filter(None, (metric_name, definition_formula, target_value))
        )
        deliverable_metric_text = " ".join(
            filter(None, (metric_name, definition_formula, metric_deliverable, data_source))
        )

        type_value = type_score(
            task_business_text,
            metric_type,
            self.idf,
            self.type_dictionary,
        )
        business_value = business_unit_score(
            task_business_unit,
            metric_business_unit,
            self.business_unit_aliases,
        )
        name_value = text_similarity(name_task_text, metric_name or "", self.idf)
        formula_value = text_similarity(formula_task_text, formula_metric_text, self.idf)
        deliverable_value = (
            text_similarity(task_deliverable or "", deliverable_metric_text, self.idf)
            if normalize_text(task_deliverable)
            else Decimal("0.00")
        )
        total = _score(
            Decimal("0.25") * type_value
            + Decimal("0.25") * business_value
            + Decimal("0.25") * name_value
            + Decimal("0.20") * formula_value
            + Decimal("0.05") * deliverable_value
        )
        level = "strong" if total >= 80 else "weak" if total >= 50 else "no_clear_relation"
        reason = (
            f"类型{type_value}分；事业部{business_value}分；指标名称{name_value}分；"
            f"定义/公式{formula_value}分；交付物{deliverable_value}分。"
        )
        return MatchScore(
            type_score=type_value,
            business_unit_score=business_value,
            metric_name_score=name_value,
            definition_formula_score=formula_value,
            deliverable_score=deliverable_value,
            total_score=total,
            match_level=level,
            match_reason=reason,
        )
