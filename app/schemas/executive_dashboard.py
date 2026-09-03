"""
Feature: Executive dashboard transport schemas.
Responsibilities: validate the read-only DEV-16 dashboard and team-task projections.
Does not own: aggregation, authorization, or persistence.
Plan task: DEV-16.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import StrictSchema


class ExecutiveDepartmentResponse(StrictSchema):
    department_id: UUID
    department_name: str
    department_type: str
    parent_department_id: UUID | None


class ExecutiveScopeResponse(StrictSchema):
    selected_department_id: UUID | None
    departments: list[ExecutiveDepartmentResponse]


class ExecutivePeriodResponse(StrictSchema):
    type: Literal["week", "month"]
    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime


class ActiveTaskMetricResponse(StrictSchema):
    count: int
    previous_count: int
    change_rate: float | None
    change_direction: Literal["up", "down", "flat", "new"]


class OnTimeMetricResponse(StrictSchema):
    completed_count: int
    on_time_count: int
    rate: float | None
    previous_rate: float | None
    change_percentage_points: float | None


class KpiLinkMetricResponse(StrictSchema):
    linked_task_count: int
    linked_metric_count: int


class OverallProgressMetricResponse(StrictSchema):
    rate: float | None
    task_count: int
    data_quality_issue_count: int


class ExecutiveMetricsResponse(StrictSchema):
    active_tasks: ActiveTaskMetricResponse
    on_time_rate: OnTimeMetricResponse
    kpi_links: KpiLinkMetricResponse
    overall_progress: OverallProgressMetricResponse


class ExecutiveQuadrantsResponse(StrictSchema):
    important_urgent: int
    important_not_urgent: int
    not_important_urgent: int
    not_important_not_urgent: int
    unscored_count: int


class WorkloadHeatmapDayResponse(StrictSchema):
    date: str
    label: str


class WorkloadHeatmapCellResponse(StrictSchema):
    date: str
    snapshot_id: UUID | None
    workload_score: float | None
    workload_level: str | None
    remaining_hours_sum: float | None = None
    available_hours: float | None = None
    active_task_count: int | None = None
    urgent_task_count: int | None = None
    blocked_task_count: int | None = None
    overdue_task_count: int | None = None
    hours_pressure: float | None = None
    weight_pressure: float | None = None
    count_pressure: float | None = None
    urgent_pressure: float | None = None
    blocked_overdue_pressure: float | None = None
    calculated_at: datetime | None = None


class WorkloadHeatmapMemberResponse(StrictSchema):
    employee_no: str
    name: str
    department_id: UUID | None
    cells: list[WorkloadHeatmapCellResponse]


class WorkloadHeatmapResponse(StrictSchema):
    days: list[WorkloadHeatmapDayResponse]
    members: list[WorkloadHeatmapMemberResponse]


class ExecutiveOverviewResponse(StrictSchema):
    scope: ExecutiveScopeResponse
    period: ExecutivePeriodResponse
    metrics: ExecutiveMetricsResponse
    quadrants: ExecutiveQuadrantsResponse
    workload_heatmap: WorkloadHeatmapResponse


class ExecutiveMemberResponse(StrictSchema):
    employee_no: str
    name: str
    department_id: UUID | None


class ExecutiveTaskSummaryResponse(StrictSchema):
    task_id: UUID
    task_no: str | None
    task_name: str
    status: str
    deadline: datetime | None
    is_urgent: bool
    task_weight: int | None
    task_version: int
    progress_percent: int
    assignee_name: str | None
    is_overdue: bool
    created_at: datetime
    updated_at: datetime


class ExecutiveTaskPageResponse(StrictSchema):
    items: list[ExecutiveTaskSummaryResponse]
    page: int
    page_size: int
    limit: int
    offset: int
    total: int
    status_counts: dict[str, int]
