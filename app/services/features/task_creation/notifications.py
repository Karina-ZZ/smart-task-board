"""
Feature: creator confirm-and-send notification.
Responsibilities: create exactly one pending-accept in-app notification for current main assignee.
Does not own: task visibility, acceptance, or later lifecycle notifications.
Plan task: WECHAT-MP-06 / FR-07.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Notification, Task
from app.services.errors import BusinessValidationError


def add_pending_accept_notification(
    session: Session, task: Task, *, created_at: datetime
) -> Notification:
    recipient = task.main_assignee_employee_no
    if not recipient:
        raise BusinessValidationError("main_assignee_employee_no is required before sending")
    row = Notification(
        task_id=task.task_id,
        recipient_employee_no=recipient,
        channel="in_app",
        title="新任务待接受",
        content=f"“{task.task_name}”等待你接受。",
        send_status="pending",
        retry_count=0,
        dedupe_key=f"task:{task.task_id}:pending_accept:v{task.task_version}",
        created_at=created_at,
    )
    session.add(row)
    return row
