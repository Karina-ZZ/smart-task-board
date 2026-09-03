"""
Feature: Completion approval automatic archival.
Responsibilities: persist one task archive row and load the existing row by task.
Does not own: review authorization, task state transitions, or archive snapshot generation.
Plan task: DEV-13 / Feature 11.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaskArchive


class TaskArchiveRepository:
    """Persistence helper for the one-archive-per-task invariant."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, archive: TaskArchive) -> TaskArchive:
        self.session.add(archive)
        self.session.flush()
        return archive

    def get_by_task_id(self, task_id: UUID) -> TaskArchive | None:
        statement = select(TaskArchive).where(TaskArchive.task_id == task_id)
        return self.session.execute(statement).scalar_one_or_none()
