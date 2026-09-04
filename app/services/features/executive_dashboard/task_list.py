"""
Feature: Executive employee task filtering.
Responsibilities: authorize employee filters,
apply task-list filters,
and build read-only task summaries.
Does not own: HTTP parsing,
dashboard metrics,
workload calculation,
persistence writes,
or task mutations.
Plan task: DEV-17 / FEATURE-15.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, UTC
from uuid import UUID

from app.models import Task
from app.repositories.executive_dashboard import ExecutiveDashboardRepository
from app.services.features.executive_dashboard.metrics import (
    EXECUTION_STATUSES,
    ExecutiveMetricsCalculator,
)
from app.services.features.executive_dashboard.periods import (
    BUSINESS_TIMEZONE,
    resolve_executive_period,
)
from app.services.features.executive_dashboard.permissions import ExecutiveScopeResolver

QUADRANT_ALIASES = {
    "urgent_not_important": "not_important_urgent",
    "routine": "not_important_not_urgent",
}
TERMINAL_TASK_STATUSES = {"completed", "archived", "cancelled", "withdrawn", "merged", "closed"}
NEAR_DUE_DAYS = 3


class ExecutiveTaskListService:
    def __init__(
        self,
        repo: ExecutiveDashboardRepository,
        scope_resolver: ExecutiveScopeResolver,
        metrics: ExecutiveMetricsCalculator,
        clock,
    ) -> None:
        self.repo = repo
        self.scope_resolver = scope_resolver
        self.metrics = metrics
        self.clock = clock

    def list_members(
        self, actor: str, *, department_id: UUID | None = None
    ) -> list[dict[str, object]]:
        scope, _ = self.scope_resolver.authorize(actor, department_id, self.clock())
        return [
            {
                "employee_no": row.employee_no,
                "name": row.name,
                "department_id": row.department_id,
            }
            for row in self.repo.list_active_users(set(scope.department_ids))
        ]

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
        now = self.clock()
        scope, _ = self.scope_resolver.authorize(actor, department_id, now)
        if employee_no:
            self.scope_resolver.authorize_employee(actor, scope, employee_no, now)
        tasks = self.repo.list_tasks_for_scope(set(scope.department_ids), employee_no)
        tasks = self._filter_tasks(
            tasks,
            now=now,
            task_status=task_status,
            quadrant=quadrant,
            near_due=near_due,
            date_preset=date_preset,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
        tasks = self._sort_tasks(tasks, sort_by, sort_order)
        start = (page - 1) * page_size
        return {
            "items": [self._task_summary(task) for task in tasks[start : start + page_size]],
            "page": page,
            "page_size": page_size,
            "limit": page_size,
            "offset": start,
            "total": len(tasks),
            "status_counts": self._status_counts(tasks),
        }

    def _filter_tasks(
        self,
        tasks: list[Task],
        *,
        now: datetime,
        task_status: str | None,
        quadrant: str | None,
        near_due: bool,
        date_preset: str,
        start_date: date | None,
        end_date: date | None,
        search: str | None,
    ) -> list[Task]:
        normalized_quadrant = QUADRANT_ALIASES.get(quadrant, quadrant)
        latest = self.metrics.latest_priority_map(tasks) if normalized_quadrant else {}
        date_bounds = self._date_bounds(date_preset, start_date, end_date, now)
        normalized_search = search.strip().casefold() if search and search.strip() else None
        result: list[Task] = []
        for task in tasks:
            if task_status and task.status != task_status:
                continue
            if normalized_quadrant and not self._matches_quadrant(
                task, normalized_quadrant, latest
            ):
                continue
            if normalized_search and normalized_search not in task.task_name.casefold():
                continue
            if near_due and not self._is_near_due(task, now):
                continue
            if date_bounds and not self._matches_date(task, date_bounds, bool(normalized_quadrant)):
                continue
            result.append(task)
        return result

    @staticmethod
    def _matches_quadrant(task: Task, quadrant: str, latest: dict[UUID, str]) -> bool:
        return (
            task.status in EXECUTION_STATUSES
            and task.effective_at is not None
            and latest.get(task.task_id) == quadrant
        )

    @classmethod
    def _matches_date(
        cls, task: Task, bounds: tuple[datetime, datetime], use_overlap: bool
    ) -> bool:
        if use_overlap:
            return cls._overlaps_range(task, *bounds)
        return cls._starts_in_range(task, *bounds)

    @staticmethod
    def _date_bounds(
        date_preset: str,
        start_date: date | None,
        end_date: date | None,
        now: datetime,
    ) -> tuple[datetime, datetime] | None:
        if date_preset in {"week", "month"}:
            window = resolve_executive_period(date_preset, now)
            return window.start, window.end
        if date_preset == "custom" and start_date and end_date:
            start = datetime.combine(start_date, time.min, tzinfo=BUSINESS_TIMEZONE).astimezone(UTC)
            end = datetime.combine(
                end_date + timedelta(days=1),
                time.min,
                tzinfo=BUSINESS_TIMEZONE,
            ).astimezone(UTC)
            return start, end
        return None

    @staticmethod
    def _starts_in_range(task: Task, start: datetime, end: datetime) -> bool:
        if task.start_time is None:
            return False
        value = task.start_time if task.start_time.tzinfo else task.start_time.replace(tzinfo=UTC)
        return start <= value < end

    @staticmethod
    def _overlaps_range(task: Task, start: datetime, end: datetime) -> bool:
        if task.start_time is not None:
            value = (
                task.start_time
                if task.start_time.tzinfo
                else task.start_time.replace(tzinfo=UTC)
            )
            if value >= end:
                return False
        if task.deadline is not None:
            value = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=UTC)
            if value < start:
                return False
        return True

    @staticmethod
    def _is_near_due(task: Task, now: datetime) -> bool:
        if task.deadline is None or task.status in TERMINAL_TASK_STATUSES:
            return False
        deadline = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=UTC)
        return now <= deadline <= now + timedelta(days=NEAR_DUE_DAYS)

    @staticmethod
    def _sort_tasks(tasks: list[Task], sort_by: str, sort_order: str) -> list[Task]:
        def aware_timestamp(value: datetime | None, *, missing: float) -> float:
            if value is None:
                return missing
            aware = value if value.tzinfo else value.replace(tzinfo=UTC)
            return aware.timestamp()

        def value(task: Task):
            if sort_by == "created_at":
                return aware_timestamp(task.created_at, missing=float("inf"))
            if sort_by == "updated_at":
                return aware_timestamp(task.updated_at, missing=float("inf"))
            if sort_by == "status":
                return task.status
            if sort_by == "task_weight":
                return task.task_weight if task.task_weight is not None else -1
            return aware_timestamp(task.deadline, missing=float("inf"))

        return sorted(
            tasks,
            key=lambda task: (value(task), str(task.task_id)),
            reverse=sort_order == "desc",
        )

    def _task_summary(self, task: Task) -> dict[str, object]:
        progress = self.metrics.task_progress_map([task]).get(task.task_id, 0)
        assignee = (
            self.repo.get_user(task.main_assignee_employee_no)
            if task.main_assignee_employee_no
            else None
        )
        deadline = task.deadline
        aware_deadline = (
            None
            if deadline is None
            else deadline if deadline.tzinfo else deadline.replace(tzinfo=UTC)
        )
        return {
            "task_id": task.task_id,
            "task_no": task.task_no,
            "task_name": task.task_name,
            "status": task.status,
            "deadline": task.deadline,
            "is_urgent": bool(task.is_urgent),
            "task_weight": task.task_weight,
            "task_version": task.task_version,
            "progress_percent": progress,
            "assignee_name": assignee.name if assignee else task.main_assignee_employee_no,
            "is_overdue": bool(aware_deadline and aware_deadline < self.clock()),
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    @staticmethod
    def _status_counts(tasks: list[Task]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in tasks:
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts
