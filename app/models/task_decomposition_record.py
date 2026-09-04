"""
Feature: Assignee-triggered AI task decomposition lifecycle.

Responsibilities:
- Persist one immutable decomposition attempt and its validation/result state.
- Keep model/provider/prompt traceability and a frozen input snapshot.
- Enforce one active attempt and idempotency constraints at the database boundary.

Does not own: task authorization, provider calls, or node creation orchestration.
Plan task: DEV-09.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskDecompositionRecord(Base):
    """One accepted task's AI decomposition attempt and audit payload."""

    __tablename__ = "task_decomposition_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'invalidated')",
            name="ck_task_decomposition_records_status",
        ),
        CheckConstraint("task_version >= 1", name="ck_task_decomposition_records_task_version"),
        CheckConstraint("node_count >= 0", name="ck_task_decomposition_records_node_count"),
        CheckConstraint("retry_count >= 0", name="ck_task_decomposition_records_retry_count"),
        Index("ix_task_decomposition_records_task_created", "task_id", "created_at"),
        Index("ix_task_decomposition_records_status", "status", "created_at"),
        Index(
            "uq_task_decomposition_records_idempotency",
            "task_id",
            "idempotency_key",
            unique=True,
        ),
        Index(
            "uq_task_decomposition_records_one_active",
            "task_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    decomposition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT"), nullable=False
    )
    triggered_by_employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    trigger_type: Mapped[str] = mapped_column(String, nullable=False, default="accept")
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    task_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String)
    model_version: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(
        String, nullable=False, default="task-decomposition-v1"
    )
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    task: Mapped[Task] = relationship(
        back_populates="decomposition_records",
        foreign_keys=[task_id],
    )
