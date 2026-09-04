"""
Feature: DEV-14 deterministic performance, priority, workload, and conflict rules.

Responsibilities:
- Prove the approved KPI similarity algorithm is reproducible and LLM-free.
- Prove priority/workload calculations ignore estimated_hours and use time windows.
- Protect documented threshold boundaries.

Does not own: PostgreSQL locking semantics or browser rendering.
Plan task: DEV-14.
"""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from uuid import uuid4

from app.models import Task
from app.services.features.performance_matching.scoring import (
    business_unit_score,
    PerformanceMatchScorer,
    text_similarity,
)
from app.services.features.planning_analytics.calculations import (
    overdue_pressure_score,
    remaining_hours,
    time_pressure_score,
    working_hours_between,
    workload_level,
)

NOW = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)  # Monday


def test_text_similarity_is_reproducible_and_semantically_weighted() -> None:
    documents = [
        "渠道 新品铺市率 有效门店数 目标门店数 渠道门店系统",
        "销售 新品销售额达成率 销售额 目标销售额 ERP",
    ]
    scorer = PerformanceMatchScorer(documents)
    first = scorer.score(
        task_name="宠物新品全国渠道铺市",
        task_description="推动重点门店完成新品上架和铺货",
        task_goal="提高新品渠道覆盖",
        task_source="事业部重点任务",
        task_deliverable="全国门店铺市完成清单",
        task_business_unit="宠物事业部",
        metric_type="渠道",
        metric_business_unit="宠物事业部",
        metric_name="新品铺市率",
        definition_formula="已铺货有效门店数 / 目标门店数",
        target_value="95%",
        metric_deliverable=None,
        data_source="渠道门店系统",
    )
    second = scorer.score(
        task_name="宠物新品全国渠道铺市",
        task_description="推动重点门店完成新品上架和铺货",
        task_goal="提高新品渠道覆盖",
        task_source="事业部重点任务",
        task_deliverable="全国门店铺市完成清单",
        task_business_unit="宠物事业部",
        metric_type="渠道",
        metric_business_unit="宠物事业部",
        metric_name="新品铺市率",
        definition_formula="已铺货有效门店数 / 目标门店数",
        target_value="95%",
        metric_deliverable=None,
        data_source="渠道门店系统",
    )
    assert first == second
    expected = (
        Decimal("0.25") * first.type_score
        + Decimal("0.25") * first.business_unit_score
        + Decimal("0.25") * first.metric_name_score
        + Decimal("0.20") * first.definition_formula_score
        + Decimal("0.05") * first.deliverable_score
    ).quantize(Decimal("0.01"))
    assert first.total_score == expected
    assert first.business_unit_score == Decimal("100.00")
    assert first.algorithm_version == "tfidf-char-ngram-v1"


def test_business_unit_mismatch_caps_strong_relation_by_formula() -> None:
    assert business_unit_score("宠物事业部", "食品事业部") == Decimal("0.00")
    assert business_unit_score("宠物事业部", "集团级") == Decimal("70.00")


def test_text_similarity_prefers_related_metric_text() -> None:
    from app.services.features.performance_matching.scoring import build_idf

    corpus = ["新品铺市率 有效门店 目标门店", "员工培训完成率 培训课程"]
    idf = build_idf(corpus)
    related = text_similarity("重点门店新品铺货覆盖", corpus[0], idf)
    unrelated = text_similarity("重点门店新品铺货覆盖", corpus[1], idf)
    assert related > unrelated


def test_working_calendar_and_remaining_hours_ignore_estimates() -> None:
    full_weekday = working_hours_between(
        datetime(2026, 9, 7, 0, tzinfo=UTC),
        datetime(2026, 9, 8, 0, tzinfo=UTC),
        daily_capacity_hours=Decimal("8"),
    )
    weekend = working_hours_between(
        datetime(2026, 9, 12, 0, tzinfo=UTC),
        datetime(2026, 9, 13, 0, tzinfo=UTC),
        daily_capacity_hours=Decimal("8"),
    )
    assert full_weekday == Decimal("8.00")
    assert weekend == Decimal("0.00")
    assert remaining_hours(
        start_time=NOW - timedelta(days=1),
        deadline=NOW + timedelta(days=1),
        now=NOW,
        daily_capacity_hours=Decimal("8"),
    ) == Decimal("8.00")


def test_priority_pressure_boundaries_match_handoff_contract() -> None:
    assert time_pressure_score(Decimal("8"), overdue=False) == 90
    assert time_pressure_score(Decimal("9"), overdue=False) == 75
    assert time_pressure_score(Decimal("24"), overdue=False) == 75
    assert time_pressure_score(Decimal("25"), overdue=False) == 50
    assert time_pressure_score(Decimal("56"), overdue=False) == 50
    assert time_pressure_score(Decimal("57"), overdue=False) == 25
    assert time_pressure_score(Decimal("0"), overdue=True) == 100
    assert overdue_pressure_score(0) == 0
    assert overdue_pressure_score(1) == 60
    assert overdue_pressure_score(2) == 80
    assert overdue_pressure_score(3) == 80
    assert overdue_pressure_score(4) == 100


def test_estimated_hours_do_not_change_remaining_window() -> None:
    task_a = Task(
        task_id=uuid4(), task_name="A", creator_employee_no="C", status="in_progress",
        start_time=NOW, deadline=NOW + timedelta(days=2), estimated_hours=Decimal("1"),
        task_version=1, created_at=NOW, updated_at=NOW,
    )
    task_b = Task(
        task_id=uuid4(), task_name="B", creator_employee_no="C", status="in_progress",
        start_time=NOW, deadline=NOW + timedelta(days=2), estimated_hours=Decimal("999"),
        task_version=1, created_at=NOW, updated_at=NOW,
    )
    left = remaining_hours(start_time=task_a.start_time, deadline=task_a.deadline, now=NOW)
    right = remaining_hours(start_time=task_b.start_time, deadline=task_b.deadline, now=NOW)
    assert left == right


def test_workload_level_boundaries_match_contract() -> None:
    assert workload_level(Decimal("40")) == "idle"
    assert workload_level(Decimal("40.01")) == "normal"
    assert workload_level(Decimal("70")) == "normal"
    assert workload_level(Decimal("70.01")) == "busy"
    assert workload_level(Decimal("90")) == "busy"
    assert workload_level(Decimal("90.01")) == "overloaded"


def test_calendar_uses_asia_shanghai_weekday_boundary() -> None:
    # Friday 16:00 UTC is Saturday 00:00 in Shanghai, so the next local day is weekend.
    assert working_hours_between(
        datetime(2026, 9, 11, 16, tzinfo=UTC),
        datetime(2026, 9, 12, 16, tzinfo=UTC),
        daily_capacity_hours=Decimal("8"),
    ) == Decimal("0.00")
