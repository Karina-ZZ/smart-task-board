"""
Feature: Executive workload heatmap projection.
Responsibilities: map persisted employee workload snapshots onto authorized working-day cells.
Does not own: workload formulas, persistence writes, or employee-task drilldown.
Plan task: DEV-16.
"""

from __future__ import annotations

from datetime import timedelta

from app.repositories.executive_dashboard import ExecutiveDashboardRepository
from app.services.features.executive_dashboard.periods import BUSINESS_TIMEZONE, PeriodWindow
from app.services.features.executive_dashboard.permissions import ExecutiveScope


class ExecutiveWorkloadHeatmapBuilder:
    def __init__(self, repo: ExecutiveDashboardRepository) -> None:
        self.repo = repo

    def build(self, scope: ExecutiveScope, window: PeriodWindow) -> dict[str, object]:
        users = self.repo.list_active_users(set(scope.department_ids))
        employee_nos = [user.employee_no for user in users]
        snapshots = self.repo.list_workload_snapshots(employee_nos, window.start, window.end)
        by_employee_day: dict[tuple[str, str], object] = {}
        for row in snapshots:
            day = row.period_start.astimezone(BUSINESS_TIMEZONE).date().isoformat()
            by_employee_day.setdefault((row.employee_no, day), row)
        days = self._workdays(window)
        members = []
        for user in users:
            cells = [
                self._snapshot_payload(
                    by_employee_day.get((user.employee_no, day["date"])), day["date"]
                )
                for day in days
            ]
            members.append(
                {
                    "employee_no": user.employee_no,
                    "name": user.name,
                    "department_id": user.department_id,
                    "cells": cells,
                }
            )
        return {"days": days, "members": members}

    @staticmethod
    def _workdays(window: PeriodWindow) -> list[dict[str, str]]:
        cursor = window.start.astimezone(BUSINESS_TIMEZONE).date()
        end_date = window.end.astimezone(BUSINESS_TIMEZONE).date()
        labels = "一二三四五六日"
        result = []
        while cursor < end_date:
            if cursor.weekday() < 5:
                result.append({"date": cursor.isoformat(), "label": f"周{labels[cursor.weekday()]}"})
            cursor += timedelta(days=1)
        return result

    @staticmethod
    def _snapshot_payload(row, date_value: str) -> dict[str, object]:
        if row is None:
            return {
                "date": date_value,
                "snapshot_id": None,
                "workload_score": None,
                "workload_level": None,
            }
        return {
            "date": date_value,
            "snapshot_id": row.workload_snapshot_id,
            "workload_score": float(row.workload_score),
            "workload_level": row.workload_level,
            "remaining_hours_sum": float(row.remaining_hours_sum),
            "available_hours": float(row.available_hours),
            "active_task_count": row.active_task_count,
            "urgent_task_count": row.urgent_task_count,
            "blocked_task_count": row.blocked_task_count,
            "overdue_task_count": row.overdue_task_count,
            "hours_pressure": float(row.hours_pressure),
            "weight_pressure": float(row.weight_pressure),
            "count_pressure": float(row.count_pressure),
            "urgent_pressure": float(row.urgent_pressure),
            "blocked_overdue_pressure": float(row.blocked_overdue_pressure),
            "calculated_at": row.calculated_at,
        }
