"""
Feature: Executive team dashboard.
Responsibilities: orchestrate authorized DEV-16 metrics/workload and expose the
DEV-17 task-list facade.
Does not own: persistence queries,
priority/workload formulas,
task-filter internals,
or task mutations.
Plan task: DEV-16 / FEATURE-14 and DEV-17 / FEATURE-15.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from app.repositories.executive_dashboard import ExecutiveDashboardRepository
from app.services.features.executive_dashboard.metrics import (
    EXECUTION_STATUSES,
    ExecutiveMetricsCalculator,
    PROGRESS_STATUSES,
)
from app.services.features.executive_dashboard.periods import (
    ExecutivePeriod,
    resolve_executive_period,
)
from app.services.features.executive_dashboard.permissions import ExecutiveScopeResolver
from app.services.features.executive_dashboard.task_list import ExecutiveTaskListService
from app.services.features.executive_dashboard.workload import ExecutiveWorkloadHeatmapBuilder


class ExecutiveDashboardService:
    def __init__(self, session, clock=lambda: datetime.now(UTC)) -> None:
        self.session = session
        self.clock = clock
        self.repo = ExecutiveDashboardRepository(session)
        self.scope_resolver = ExecutiveScopeResolver(self.repo)
        self.metrics = ExecutiveMetricsCalculator(self.repo)
        self.workload = ExecutiveWorkloadHeatmapBuilder(self.repo)
        self.task_list = ExecutiveTaskListService(
            self.repo, self.scope_resolver, self.metrics, self.clock
        )

    def get_overview(
        self,
        actor: str,
        *,
        department_id: UUID | None = None,
        period: ExecutivePeriod = "week",
    ) -> dict[str, object]:
        now = self.clock()
        scope, departments = self.scope_resolver.authorize(actor, department_id, now)
        window = resolve_executive_period(period, now)
        active_tasks = self.repo.list_tasks_in_period(
            set(scope.department_ids), set(EXECUTION_STATUSES), window.start, window.end
        )
        progress_tasks = self.repo.list_tasks_in_period(
            set(scope.department_ids), set(PROGRESS_STATUSES), window.start, window.end
        )
        completed = self.repo.list_completed_in_period(
            set(scope.department_ids), window.start, window.end
        )
        return {
            "scope": self.scope_resolver.payload(scope, departments),
            "period": {
                "type": period,
                "start": window.start,
                "end": window.end,
                "previous_start": window.previous_start,
                "previous_end": window.previous_end,
            },
            "metrics": {
                "active_tasks": self.metrics.active_metric(active_tasks, scope, window),
                "on_time_rate": self.metrics.on_time_metric(completed, scope, window),
                "kpi_links": self.metrics.kpi_metric(progress_tasks),
                "overall_progress": self.metrics.overall_progress(progress_tasks),
            },
            "quadrants": self.metrics.quadrants(active_tasks),
            "workload_heatmap": self.workload.build(scope, window),
        }

    def list_members(
        self, actor: str, *, department_id: UUID | None = None
    ) -> list[dict[str, object]]:
        return self.task_list.list_members(actor, department_id=department_id)

    def list_tasks(
        self,
        actor: str,
        *,
        department_id: UUID | None,
        employee_no: str | None,
        task_status: str | None,
        quadrant: str | None,
        near_due: bool,
        date_preset: str,
        start_date: date | None,
        end_date: date | None,
        search: str | None,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        return self.task_list.list_tasks(
            actor,
            department_id=department_id,
            employee_no=employee_no,
            task_status=task_status,
            quadrant=quadrant,
            near_due=near_due,
            date_preset=date_preset,
            start_date=start_date,
            end_date=end_date,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    def list_quadrant_tasks(
        self,
        actor: str,
        *,
        department_id: UUID | None,
        period: ExecutivePeriod,
        quadrant: str,
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        return self.list_tasks(
            actor,
            department_id=department_id,
            employee_no=None,
            task_status=None,
            quadrant=quadrant,
            near_due=False,
            date_preset=period,
            start_date=None,
            end_date=None,
            search=None,
            sort_by="deadline",
            sort_order="asc",
            page=page,
            page_size=page_size,
        )
