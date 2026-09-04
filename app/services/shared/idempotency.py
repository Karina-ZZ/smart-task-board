"""
Feature: persisted write idempotency via operation_logs.request_id.
Responsibilities: detect/record successful business action keys without adding a new table.
Does not own: HTTP header parsing or task state transitions.
Plan task: DEV-08 and later write actions.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OperationLog, Task


def find_task(
    session: Session,
    *,
    key: str | None,
    actor: str,
    action: str,
    task_id,
) -> Task | None:
    if not key:
        return None
    row = session.scalar(
        select(OperationLog).where(
            OperationLog.request_id == key,
            OperationLog.operator_employee_no == actor,
            OperationLog.action == action,
            OperationLog.object_type == "task",
            OperationLog.object_id == str(task_id),
            OperationLog.result == "success",
        ).order_by(OperationLog.created_at.desc()).limit(1)
    )
    if not isinstance(row, OperationLog):
        return None
    return session.get(Task, task_id)


def record_task(
    session: Session,
    *,
    key: str | None,
    actor: str,
    action: str,
    task: Task,
    at: datetime,
) -> None:
    if not key:
        return
    session.add(
        OperationLog(
            request_id=key,
        operator_employee_no=actor,
        action=action,
        object_type="task",
        object_id=str(task.task_id),
        before_data=None,
        after_data={"status": task.status, "task_version": task.task_version},
        result="success",
            created_at=at,
        )
    )
