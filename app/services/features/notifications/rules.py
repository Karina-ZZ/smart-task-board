"""
Feature: notification timing and node-assignment reminder policies.

Responsibilities:
- Calculate node due-soon time from approved DEV-15 working-span bands.
- Persist executable-node reminder rules without estimated-hours dependencies.
- Emit immediate node-assignment notifications only to the assigned collaborator.

Does not own: HTTP routes, task state transitions, or channel delivery.
Plan task: DEV-15 / feature 13.
"""
from __future__ import annotations

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, ReminderRule, SystemParameter, Task, TaskNode
from app.services.features.planning_analytics import working_hours_between

DEFAULT_DAILY_CAPACITY = Decimal("8")
ACTIVE_NODE_STATUSES = frozenset({"pending", "in_progress", "blocked"})


def daily_capacity_hours(session: Session) -> Decimal:
    row = session.scalar(
        select(SystemParameter).where(
            SystemParameter.param_key == "daily_capacity_hours",
            SystemParameter.is_active.is_(True),
        )
    )
    if row is None:
        return DEFAULT_DAILY_CAPACITY
    try:
        value = Decimal(str(row.param_value))
    except Exception:
        return DEFAULT_DAILY_CAPACITY
    return value if value > 0 else DEFAULT_DAILY_CAPACITY


def subtract_working_hours(
    end: datetime,
    hours: Decimal,
    *,
    daily_capacity: Decimal,
) -> datetime:
    """Find the latest instant whose weekday-capacity distance to end equals hours."""
    if hours <= 0:
        return end
    # Search farther than the theoretical weekday span so weekends are always covered.
    workdays = max(1, int((hours / daily_capacity).to_integral_value(rounding="ROUND_CEILING")))
    low = end - timedelta(days=workdays * 3 + 7)
    high = end
    for _ in range(64):
        mid = low + (high - low) / 2
        value = working_hours_between(mid, end, daily_capacity_hours=daily_capacity)
        if value > hours:
            low = mid
        else:
            high = mid
    return high.astimezone(UTC)


def node_due_soon_at(
    start: datetime,
    deadline: datetime,
    *,
    daily_capacity: Decimal,
) -> datetime:
    span = working_hours_between(start, deadline, daily_capacity_hours=daily_capacity)
    if span <= daily_capacity:
        lead = Decimal("2")
    elif span <= daily_capacity * 3:
        lead = Decimal("4")
    else:
        lead = daily_capacity
    due_soon = subtract_working_hours(deadline, lead, daily_capacity=daily_capacity)
    return max(start.astimezone(UTC), due_soon)


def assignment_allows_execution(task: Task, node: TaskNode) -> bool:
    if node.owner_employee_no == task.main_assignee_employee_no:
        return (node.assignment_status or "accepted") == "accepted"
    return (node.assignment_status or "accepted") == "accepted"


def _existing_rule(session: Session, dedupe_key: str) -> ReminderRule | None:
    return session.scalar(select(ReminderRule).where(ReminderRule.dedupe_key == dedupe_key))


def _persist_rule(
    session: Session,
    *,
    task_id: UUID,
    node_id: UUID,
    reminder_type: str,
    recipient: str,
    at: datetime,
    dedupe_key: str,
    now: datetime,
) -> ReminderRule:
    existing = _existing_rule(session, dedupe_key)
    if existing is not None:
        existing.recipient_employee_no = recipient
        existing.trigger_time = at
        existing.next_trigger_at = at
        existing.is_active = True
        return existing
    rule = ReminderRule(
        task_id=task_id,
        node_id=node_id,
        reminder_type=reminder_type,
        recipient_employee_no=recipient,
        trigger_time=at,
        next_trigger_at=at,
        repeat_rule=None,
        dedupe_key=dedupe_key,
        is_active=True,
        created_at=now,
    )
    session.add(rule)
    return rule


def schedule_node_execution_reminders(
    session: Session,
    task: Task,
    node: TaskNode,
    *,
    now: datetime,
) -> list[ReminderRule]:
    """Schedule only reminders that imply an accepted execution responsibility."""
    if not assignment_allows_execution(task, node):
        return []
    if node.status not in ACTIVE_NODE_STATUSES or not node.owner_employee_no:
        return []
    capacity = daily_capacity_hours(session)
    rules: list[ReminderRule] = []
    if node.planned_start_time is not None:
        rules.append(
            _persist_rule(
                session,
                task_id=task.task_id,
                node_id=node.node_id,
                reminder_type="node_start",
                recipient=node.owner_employee_no,
                at=node.planned_start_time.astimezone(UTC),
                dedupe_key=f"node:{node.node_id}:start",
                now=now,
            )
        )
    if node.planned_start_time is not None and node.planned_deadline is not None:
        due_soon = node_due_soon_at(
            node.planned_start_time,
            node.planned_deadline,
            daily_capacity=capacity,
        )
        start_at = node.planned_start_time.astimezone(UTC)
        # A coincident start/due-soon instant is represented by the start reminder only.
        if due_soon != start_at:
            rules.append(
                _persist_rule(
                    session,
                    task_id=task.task_id,
                    node_id=node.node_id,
                    reminder_type="due_soon",
                    recipient=node.owner_employee_no,
                    at=due_soon,
                    dedupe_key=f"node:{node.node_id}:due-soon",
                    now=now,
                )
            )
    if node.planned_deadline is not None:
        rules.append(
            _persist_rule(
                session,
                task_id=task.task_id,
                node_id=node.node_id,
                reminder_type="node_due",
                recipient=node.owner_employee_no,
                at=node.planned_deadline.astimezone(UTC),
                dedupe_key=f"node:{node.node_id}:due",
                now=now,
            )
        )
    return rules


def emit_node_assignment_notification(
    session: Session,
    task: Task,
    node: TaskNode,
    *,
    now: datetime,
) -> Notification | None:
    recipient = node.owner_employee_no
    if not recipient or recipient == task.main_assignee_employee_no:
        return None
    rule_key = f"node:{node.node_id}:assignment"
    rule = _existing_rule(session, rule_key)
    if rule is None:
        rule = ReminderRule(
            task_id=task.task_id,
            node_id=node.node_id,
            reminder_type="collaboration",
            recipient_employee_no=recipient,
            trigger_time=now,
            next_trigger_at=None,
            repeat_rule=None,
            dedupe_key=rule_key,
            is_active=False,
            last_triggered_at=now,
            created_at=now,
        )
        session.add(rule)
    dedupe = f"{rule_key}:pending"
    existing = session.scalar(
        select(Notification).where(
            Notification.dedupe_key == dedupe,
            Notification.recipient_employee_no == recipient,
            Notification.channel == "in_app",
        )
    )
    if existing is not None:
        return existing
    row = Notification(
        reminder_rule_id=rule.reminder_rule_id,
        task_id=task.task_id,
        recipient_employee_no=recipient,
        channel="in_app",
        title="节点待承接",
        content=f"“{node.node_name}”需要你确认是否承接。",
        send_status="pending",
        retry_count=0,
        dedupe_key=dedupe,
        created_at=now,
    )
    session.add(row)
    return row


def emit_node_assignment_rejected_notification(
    session: Session,
    task: Task,
    node: TaskNode,
    *,
    reason: str,
    now: datetime,
) -> Notification | None:
    recipient = task.main_assignee_employee_no
    if not recipient:
        return None
    rule_key = f"node:{node.node_id}:assignment-rejected:{task.task_version}"
    rule = ReminderRule(
        task_id=task.task_id,
        node_id=node.node_id,
        reminder_type="collaboration",
        recipient_employee_no=recipient,
        trigger_time=now,
        next_trigger_at=None,
        repeat_rule=None,
        dedupe_key=rule_key,
        is_active=False,
        last_triggered_at=now,
        created_at=now,
    )
    session.add(rule)
    row = Notification(
        reminder_rule_id=rule.reminder_rule_id,
        task_id=task.task_id,
        recipient_employee_no=recipient,
        channel="in_app",
        title="协办节点无法承接",
        content=f"“{node.node_name}”的负责人无法承接：{reason}",
        send_status="pending",
        retry_count=0,
        dedupe_key=rule_key,
        created_at=now,
    )
    session.add(row)
    return row
