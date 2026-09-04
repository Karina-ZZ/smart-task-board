"""
Feature: DEV-15 node assignment and reminder policies.

Verifies collaborator acceptance gates and the approved working-span reminder bands.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models import ReminderRule, Task, TaskNode
from app.services.features.notifications import node_due_soon_at, schedule_node_execution_reminders
from app.services.features.planning_analytics import working_hours_between

NOW = datetime(2026, 9, 3, 1, 0, tzinfo=UTC)
CAPACITY = Decimal("8")


class FakeSession:
    def __init__(self):
        self.added = []

    def scalar(self, _statement):
        return None

    def add(self, value):
        self.added.append(value)


def _task() -> Task:
    return Task(
        task_id=uuid4(), task_name="Feature13", creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE", status="in_progress",
        task_version=4, effective_at=NOW, created_at=NOW, updated_at=NOW,
    )


def _node(task: Task, *, owner="COLLAB", assignment_status="accepted", start=NOW, deadline=None):
    return TaskNode(
        node_id=uuid4(), task_id=task.task_id, node_order=1, node_name="协办节点",
        owner_employee_no=owner, assignment_status=assignment_status,
        planned_start_time=start, planned_deadline=deadline or start + timedelta(days=1),
        status="pending", progress_percent=0,
    )


def _assert_lead(start: datetime, deadline: datetime, expected_hours: Decimal) -> None:
    due = node_due_soon_at(start, deadline, daily_capacity=CAPACITY)
    assert due >= start
    actual = working_hours_between(due, deadline, daily_capacity_hours=CAPACITY)
    assert abs(actual - expected_hours) <= Decimal("0.02")


def test_due_soon_uses_two_four_and_one_workday_bands() -> None:
    # Shanghai local dates are Fri, Mon-Wed and Fri-Fri respectively; use weekday windows.
    one_day_start = datetime(2026, 9, 3, 16, 0, tzinfo=UTC)  # Fri 00:00 local
    one_day_end = one_day_start + timedelta(days=1)
    _assert_lead(one_day_start, one_day_end, Decimal("2"))

    two_day_start = datetime(2026, 9, 6, 16, 0, tzinfo=UTC)  # Mon 00:00 local
    two_day_end = two_day_start + timedelta(days=2)
    _assert_lead(two_day_start, two_day_end, Decimal("4"))

    five_day_start = datetime(2026, 9, 6, 16, 0, tzinfo=UTC)
    five_day_end = five_day_start + timedelta(days=5)
    _assert_lead(five_day_start, five_day_end, Decimal("8"))


def test_due_soon_never_precedes_start_and_coincident_start_is_deduped() -> None:
    start = datetime(2026, 9, 3, 16, 0, tzinfo=UTC)
    # This window carries less than two working hours, so due-soon clamps to start.
    deadline = start + timedelta(hours=3)
    task = _task()
    node = _node(task, owner="ASSIGNEE", start=start, deadline=deadline)
    session = FakeSession()

    rules = schedule_node_execution_reminders(session, task, node, now=NOW)

    assert node_due_soon_at(start, deadline, daily_capacity=CAPACITY) == start
    assert [rule.reminder_type for rule in rules] == ["node_start", "node_due"]


def test_pending_collaborator_gets_no_execution_reminders_until_accepted() -> None:
    task = _task()
    node = _node(task, assignment_status="pending")
    node.estimated_hours = Decimal("999")  # historical field must not affect scheduling.
    session = FakeSession()

    assert schedule_node_execution_reminders(session, task, node, now=NOW) == []
    assert not session.added

    node.assignment_status = "accepted"
    rules = schedule_node_execution_reminders(session, task, node, now=NOW)
    assert {rule.reminder_type for rule in rules} == {"node_start", "due_soon", "node_due"}
    assert all(isinstance(rule, ReminderRule) for rule in rules)
