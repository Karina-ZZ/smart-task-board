"""
Feature: Task decomposition persistence.

Responsibilities: query, lock, add, and list decomposition attempts.
Does not own: state transitions, authorization, provider calls, or validation.
Plan task: DEV-09.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaskDecompositionRecord


class TaskDecompositionRepository:
    """Persistence-only access for decomposition attempts."""

    ACTIVE_STATUSES = ("pending", "running")

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, record: TaskDecompositionRecord) -> TaskDecompositionRecord:
        self.session.add(record)
        self.session.flush()
        return record

    def get(self, decomposition_id: UUID) -> TaskDecompositionRecord | None:
        return self.session.get(TaskDecompositionRecord, decomposition_id)

    def get_for_update(self, decomposition_id: UUID) -> TaskDecompositionRecord | None:
        statement = (
            select(TaskDecompositionRecord)
            .where(TaskDecompositionRecord.decomposition_id == decomposition_id)
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_idempotency(
        self, task_id: UUID, idempotency_key: str
    ) -> TaskDecompositionRecord | None:
        statement = select(TaskDecompositionRecord).where(
            TaskDecompositionRecord.task_id == task_id,
            TaskDecompositionRecord.idempotency_key == idempotency_key,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_active_for_task(self, task_id: UUID) -> TaskDecompositionRecord | None:
        statement = (
            select(TaskDecompositionRecord)
            .where(
                TaskDecompositionRecord.task_id == task_id,
                TaskDecompositionRecord.status.in_(self.ACTIVE_STATUSES),
            )
            .order_by(TaskDecompositionRecord.created_at.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_latest_for_task(self, task_id: UUID) -> TaskDecompositionRecord | None:
        statement = (
            select(TaskDecompositionRecord)
            .where(TaskDecompositionRecord.task_id == task_id)
            .order_by(
                TaskDecompositionRecord.created_at.desc(),
                TaskDecompositionRecord.decomposition_id.desc(),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_for_task(self, task_id: UUID) -> list[TaskDecompositionRecord]:
        statement = (
            select(TaskDecompositionRecord)
            .where(TaskDecompositionRecord.task_id == task_id)
            .order_by(
                TaskDecompositionRecord.created_at,
                TaskDecompositionRecord.decomposition_id,
            )
        )
        return list(self.session.execute(statement).scalars().all())
