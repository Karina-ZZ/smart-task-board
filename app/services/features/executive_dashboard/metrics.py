"""
Feature: Executive dashboard team metrics.
Responsibilities: calculate the four approved metrics and aggregate persisted priority quadrants.
Does not own: department authorization,
priority calculation,
workload calculation,
or HTTP transport.
Plan task: DEV-16.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.models import Task, TaskNode, TaskProgressReport, TaskStatusLog
from app.repositories.executive_dashboard import ExecutiveDashboardRepository
from app.services.features.executive_dashboard.periods import PeriodWindow
from app.services.features.executive_dashboard.permissions import ExecutiveScope

EXECUTION_STATUSES = frozenset({"in_progress", "blocked", "pending_report"})
PROGRESS_STATUSES = frozenset({*EXECUTION_STATUSES, "pending_review"})
QUADRANT_CODES = (
    "important_urgent",
    "important_not_urgent",
    "not_important_urgent",
    "not_important_not_urgent",
)


class ExecutiveMetricsCalculator:
    def __init__(self, repo: ExecutiveDashboardRepository) -> None:
        self.repo = repo

    def active_metric(
        self, active_tasks: list[Task], scope: ExecutiveScope, window: PeriodWindow
    ) -> dict[str, object]:
        previous = self._previous_active_count(scope, window)
        current = len(active_tasks)
        if previous == 0:
            return {
                "count": current,
                "previous_count": previous,
                "change_rate": 0.0 if current == 0 else None,
                "change_direction": "flat" if current == 0 else "new",
            }
        rate = (Decimal(current - previous) / Decimal(previous) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return {
            "count": current,
            "previous_count": previous,
            "change_rate": float(rate),
            "change_direction": "up" if rate > 0 else "down" if rate < 0 else "flat",
        }

    def on_time_metric(
        self, completed: list[Task], scope: ExecutiveScope, window: PeriodWindow
    ) -> dict[str, object]:
        rate = self._on_time_rate(completed)
        previous = self.repo.list_completed_in_period(
            set(scope.department_ids), window.previous_start, window.previous_end
        )
        previous_rate = self._on_time_rate(previous)
        change = None if rate is None or previous_rate is None else round(rate - previous_rate, 2)
        return {
            "completed_count": len(completed),
            "on_time_count": self._on_time_count(completed),
            "rate": rate,
            "previous_rate": previous_rate,
            "change_percentage_points": change,
        }

    def kpi_metric(self, tasks: list[Task]) -> dict[str, int]:
        matches = self.repo.list_confirmed_active_matches([task.task_id for task in tasks])
        return {
            "linked_task_count": len({row.task_id for row in matches}),
            "linked_metric_count": len({row.metric_id for row in matches}),
        }

    def overall_progress(self, tasks: list[Task]) -> dict[str, object]:
        if not tasks:
            return {"rate": None, "task_count": 0, "data_quality_issue_count": 0}
        progress = self.task_progress_map(tasks)
        weighted = Decimal("0")
        weight_total = Decimal("0")
        issues = 0
        for task in tasks:
            value = Decimal(str(progress.get(task.task_id, 0)))
            weight = Decimal(task.task_weight or 0)
            if task.status == "pending_review" and value < 100:
                issues += 1
            if weight > 0:
                weighted += value * weight
                weight_total += weight
        rate = None if weight_total <= 0 else float(
            (weighted / weight_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
        return {"rate": rate, "task_count": len(tasks), "data_quality_issue_count": issues}

    def task_progress_map(self, tasks: list[Task]) -> dict[UUID, int]:
        task_ids = [task.task_id for task in tasks]
        nodes = self.repo.list_nodes_for_tasks(task_ids)
        reports = self.repo.list_root_progress_reports(task_ids)
        nodes_by_task = self._valid_nodes_by_task(tasks, nodes)
        latest_report: dict[UUID, TaskProgressReport] = {}
        for report in reports:
            latest_report.setdefault(report.task_id, report)
        result: dict[UUID, int] = {}
        for task in tasks:
            valid_nodes = nodes_by_task.get(task.task_id, [])
            if valid_nodes:
                result[task.task_id] = round(
                    sum(node.progress_percent for node in valid_nodes) / len(valid_nodes)
                )
            else:
                report = latest_report.get(task.task_id)
                result[task.task_id] = report.progress_percent if report else 0
        return result

    def quadrants(self, tasks: list[Task]) -> dict[str, int]:
        latest = self.latest_priority_map(tasks)
        counts = {code: 0 for code in QUADRANT_CODES}
        unscored = 0
        for task in tasks:
            code = latest.get(task.task_id)
            if code in counts:
                counts[code] += 1
            else:
                unscored += 1
        return {**counts, "unscored_count": unscored}

    def latest_priority_map(self, tasks: list[Task]) -> dict[UUID, str]:
        rows = self.repo.list_priority_scores([task.task_id for task in tasks])
        latest: dict[UUID, str] = {}
        for row in rows:
            latest.setdefault(row.task_id, row.priority_quadrant)
        return latest

    def _previous_active_count(self, scope: ExecutiveScope, window: PeriodWindow) -> int:
        tasks = self.repo.list_tasks_effective_before(
            set(scope.department_ids), window.previous_start, window.previous_end
        )
        logs = self.repo.list_status_logs_for_tasks([task.task_id for task in tasks])
        by_task: dict[UUID, list[TaskStatusLog]] = defaultdict(list)
        for row in logs:
            by_task[row.task_id].append(row)
        return sum(
            1
            for task in tasks
            if self._status_at(task, by_task.get(task.task_id, []), window.previous_end)
            in EXECUTION_STATUSES
        )

    @staticmethod
    def _status_at(task: Task, logs: list[TaskStatusLog], cutoff) -> str | None:
        before = [row for row in logs if row.created_at < cutoff]
        if before:
            return before[-1].to_status
        after = [row for row in logs if row.created_at >= cutoff]
        if after:
            return after[0].from_status
        return task.status if task.created_at < cutoff else None

    @staticmethod
    def _on_time_count(tasks: list[Task]) -> int:
        return sum(
            1
            for task in tasks
            if task.deadline is not None and task.completed_at <= task.deadline
        )

    def _on_time_rate(self, tasks: list[Task]) -> float | None:
        if not tasks:
            return None
        return float(
            (Decimal(self._on_time_count(tasks)) / Decimal(len(tasks)) * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )

    @staticmethod
    def _valid_nodes_by_task(
        tasks: list[Task], nodes: list[TaskNode]
    ) -> dict[UUID, list[TaskNode]]:
        task_by_id = {task.task_id: task for task in tasks}
        result: dict[UUID, list[TaskNode]] = defaultdict(list)
        for node in nodes:
            task = task_by_id[node.task_id]
            if (
                task.latest_decomposition_id is not None
                and node.decomposition_id == task.latest_decomposition_id
            ):
                result[node.task_id].append(node)
        return result
