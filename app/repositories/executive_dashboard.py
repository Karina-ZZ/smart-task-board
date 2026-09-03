"""
Feature: Executive dashboard read repository.

Responsibilities:
- Load authorized organization facts and team dashboard source rows.
- Keep SQL/query concerns out of executive business calculations.

Does not own: authorization decisions, metric formulas, or UI projection.
Plan task: DEV-16.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Department,
    OperationLog,
    PerformanceMetric,
    Task,
    TaskNode,
    TaskPerformanceMatch,
    TaskPriorityScore,
    TaskProgressReport,
    TaskStatusLog,
    User,
    UserAuthorizedScope,
    WorkloadSnapshot,
)


class ExecutiveDashboardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user(self, employee_no: str) -> User | None:
        return self.session.get(User, employee_no)

    def list_active_department_scopes(
        self, employee_no: str, now: datetime
    ) -> list[UserAuthorizedScope]:
        statement = (
            select(UserAuthorizedScope)
            .where(
                UserAuthorizedScope.employee_no == employee_no,
                UserAuthorizedScope.scope_type == "department",
                UserAuthorizedScope.permission_type.in_(("view", "manage", "export")),
                UserAuthorizedScope.status == "active",
                or_(
                    UserAuthorizedScope.valid_from.is_(None),
                    UserAuthorizedScope.valid_from <= now,
                ),
                or_(
                    UserAuthorizedScope.valid_to.is_(None),
                    UserAuthorizedScope.valid_to > now,
                ),
            )
            .order_by(UserAuthorizedScope.created_at, UserAuthorizedScope.authorized_scope_id)
        )
        return list(self.session.scalars(statement).all())

    def list_active_departments(self) -> list[Department]:
        return list(
            self.session.scalars(
                select(Department)
                .where(Department.status == "active")
                .order_by(Department.department_path, Department.department_name)
            ).all()
        )

    def list_active_users(self, department_ids: set[UUID]) -> list[User]:
        if not department_ids:
            return []
        statement = (
            select(User)
            .where(
                User.department_id.in_(department_ids),
                User.status == "active",
                User.role_type != "admin",
            )
            .order_by(User.name, User.employee_no)
        )
        return list(self.session.scalars(statement).all())

    def list_tasks_for_scope(
        self, department_ids: set[UUID], employee_no: str | None = None
    ) -> list[Task]:
        """Return current task rows inside an already-authorized department scope."""
        if not department_ids:
            return []
        statement = select(Task).where(Task.department_id.in_(department_ids))
        if employee_no is not None:
            statement = statement.where(Task.main_assignee_employee_no == employee_no)
        statement = statement.order_by(Task.created_at, Task.task_id)
        return list(self.session.scalars(statement).all())

    def list_tasks_in_period(
        self,
        department_ids: set[UUID],
        statuses: set[str],
        period_start: datetime,
        period_end: datetime,
    ) -> list[Task]:
        if not department_ids:
            return []
        statement = (
            select(Task)
            .where(
                Task.department_id.in_(department_ids),
                Task.status.in_(statuses),
                Task.effective_at.is_not(None),
                or_(Task.start_time.is_(None), Task.start_time < period_end),
                or_(Task.deadline.is_(None), Task.deadline >= period_start),
            )
            .order_by(Task.created_at, Task.task_id)
        )
        return list(self.session.scalars(statement).all())

    def list_tasks_effective_before(
        self,
        department_ids: set[UUID],
        period_start: datetime,
        period_end: datetime,
    ) -> list[Task]:
        if not department_ids:
            return []
        statement = (
            select(Task)
            .where(
                Task.department_id.in_(department_ids),
                Task.effective_at.is_not(None),
                Task.effective_at < period_end,
                Task.created_at < period_end,
                or_(Task.start_time.is_(None), Task.start_time < period_end),
                or_(Task.deadline.is_(None), Task.deadline >= period_start),
            )
            .order_by(Task.created_at, Task.task_id)
        )
        return list(self.session.scalars(statement).all())

    def list_status_logs_for_tasks(self, task_ids: list[UUID]) -> list[TaskStatusLog]:
        if not task_ids:
            return []
        statement = (
            select(TaskStatusLog)
            .where(TaskStatusLog.task_id.in_(task_ids))
            .order_by(
                TaskStatusLog.task_id,
                TaskStatusLog.created_at,
                TaskStatusLog.status_log_id,
            )
        )
        return list(self.session.scalars(statement).all())

    def list_completed_in_period(
        self, department_ids: set[UUID], period_start: datetime, period_end: datetime
    ) -> list[Task]:
        if not department_ids:
            return []
        statement = (
            select(Task)
            .where(
                Task.department_id.in_(department_ids),
                Task.completed_at.is_not(None),
                Task.completed_at >= period_start,
                Task.completed_at < period_end,
            )
            .order_by(Task.completed_at, Task.task_id)
        )
        return list(self.session.scalars(statement).all())

    def list_confirmed_active_matches(
        self, task_ids: list[UUID]
    ) -> list[TaskPerformanceMatch]:
        if not task_ids:
            return []
        statement = (
            select(TaskPerformanceMatch)
            .join(PerformanceMetric, PerformanceMetric.metric_id == TaskPerformanceMatch.metric_id)
            .where(
                TaskPerformanceMatch.task_id.in_(task_ids),
                TaskPerformanceMatch.is_confirmed.is_(True),
                PerformanceMetric.status == "active",
            )
            .order_by(TaskPerformanceMatch.task_id, TaskPerformanceMatch.metric_id)
        )
        return list(self.session.scalars(statement).all())

    def list_nodes_for_tasks(self, task_ids: list[UUID]) -> list[TaskNode]:
        if not task_ids:
            return []
        statement = (
            select(TaskNode)
            .where(TaskNode.task_id.in_(task_ids), TaskNode.status != "cancelled")
            .order_by(TaskNode.task_id, TaskNode.node_order, TaskNode.sort_weight, TaskNode.node_id)
        )
        return list(self.session.scalars(statement).all())

    def list_root_progress_reports(self, task_ids: list[UUID]) -> list[TaskProgressReport]:
        if not task_ids:
            return []
        statement = (
            select(TaskProgressReport)
            .where(TaskProgressReport.task_id.in_(task_ids), TaskProgressReport.node_id.is_(None))
            .order_by(
                TaskProgressReport.task_id,
                TaskProgressReport.created_at.desc(),
                TaskProgressReport.progress_report_id.desc(),
            )
        )
        return list(self.session.scalars(statement).all())

    def list_priority_scores(self, task_ids: list[UUID]) -> list[TaskPriorityScore]:
        if not task_ids:
            return []
        statement = (
            select(TaskPriorityScore)
            .where(TaskPriorityScore.task_id.in_(task_ids))
            .order_by(
                TaskPriorityScore.task_id,
                TaskPriorityScore.calculated_at.desc(),
                TaskPriorityScore.priority_score_id.desc(),
            )
        )
        return list(self.session.scalars(statement).all())

    def list_workload_snapshots(
        self,
        employee_nos: list[str],
        period_start: datetime,
        period_end: datetime,
    ) -> list[WorkloadSnapshot]:
        if not employee_nos:
            return []
        statement = (
            select(WorkloadSnapshot)
            .where(
                WorkloadSnapshot.employee_no.in_(employee_nos),
                WorkloadSnapshot.period_start < period_end,
                WorkloadSnapshot.period_end >= period_start,
            )
            .order_by(
                WorkloadSnapshot.employee_no,
                WorkloadSnapshot.period_start,
                WorkloadSnapshot.calculated_at.desc(),
            )
        )
        return list(self.session.scalars(statement).all())

    def add_scope_denied_log(
        self, actor: str | None, department_id: UUID | None, message: str, now: datetime
    ) -> None:
        self.session.add(
            OperationLog(
                operator_employee_no=actor,
                action="executive_scope_access",
                object_type="department",
                object_id=str(department_id or "executive_dashboard"),
                result="denied",
                error_message=message,
                created_at=now,
            )
        )
        self.session.commit()
