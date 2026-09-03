from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call
from uuid import uuid4

import pytest

from app.models import (
    Task,
    TaskCompletionReview,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
)
from app.services import (
    BusinessValidationError,
    DependencyNotSatisfiedError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    OpenTaskIssueConflictError,
    PermissionDeniedError,
    TaskNodeWorkflowService,
    TaskVersionConflictError,
)

NOW = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)


def _context(
    *,
    task_status: str = "in_progress",
    node_status: str = "pending",
    owner: str | None = "OWNER",
    progress: int = 0,
    actual_hours: Decimal | None = None,
) -> tuple[TaskNodeWorkflowService, MagicMock, Task, TaskNode]:
    task = Task(
        task_id=uuid4(),
        task_name="Task",
        creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE",
        status=task_status,
        task_version=3,
        created_at=NOW,
        updated_at=NOW,
    )
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Node",
        owner_employee_no=owner,
        status=node_status,
        progress_percent=progress,
        actual_hours=actual_hours,
    )
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.tasks.get_by_id_for_update.return_value = task
    uow.task_nodes.get_node.return_value = node
    uow.task_nodes.get_node_for_update.return_value = node
    uow.task_nodes.list_predecessors.return_value = []
    uow.task_issues.has_active_blocker.return_value = False
    uow.task_status_logs.has_action_for_business_ref.return_value = False
    uow.task_status_logs.add.side_effect = lambda value: value
    service = TaskNodeWorkflowService(Mock(return_value=uow), clock=lambda: NOW)
    return service, uow, task, node


def _last_log(uow: MagicMock):
    return uow.task_status_logs.add.call_args.args[0]


def _rejected_review(
    task: Task,
    node: TaskNode,
    *,
    review_round: int = 1,
) -> TaskCompletionReview:
    return TaskCompletionReview(
        completion_review_id=uuid4(),
        task_id=task.task_id,
        review_round=review_round,
        submitted_by_employee_no="ASSIGNEE",
        completion_note="Done",
        deliverable_summary="Artifact",
        reviewer_employee_no="REVIEWER",
        review_status="rejected",
        review_result="rejected",
        reject_reason="Rework this node",
        rework_node_id=node.node_id,
        submitted_task_version=1,
        reviewed_task_version=task.task_version,
        submitted_at=NOW,
        reviewed_at=NOW,
        is_legacy_import=False,
    )


def test_start_node_uses_owner_and_logs_same_task_state() -> None:
    service, uow, task, node = _context()

    service.start_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")

    assert node.status == "in_progress"
    assert task.task_version == 4
    log = _last_log(uow)
    assert (log.action_type, log.from_status, log.to_status, log.task_version) == (
        "node_started",
        "in_progress",
        "in_progress",
        4,
    )
    assert (log.business_ref_type, log.business_ref_id) == (
        "task_node",
        node.node_id,
    )


def test_main_assignee_can_execute_ownerless_node() -> None:
    service, _, task, node = _context(owner=None)

    service.start_node(task.task_id, node.node_id, "ASSIGNEE", 3, "unit-test")

    assert node.status == "in_progress"


def test_node_actor_and_cross_task_are_rejected_without_commit() -> None:
    service, uow, task, node = _context()
    uow.task_nodes.list_participants.return_value = [
        TaskNodeParticipant(
            task_id=task.task_id,
            node_id=node.node_id,
            employee_no="COLLABORATOR",
            participant_role="collaborator",
        )
    ]

    for actor in ("COLLABORATOR", "OUTSIDER"):
        with pytest.raises(PermissionDeniedError):
            service.start_node(task.task_id, node.node_id, actor, 3, "unit-test")
    assert task.task_version == 3
    uow.commit.assert_not_called()

    node.task_id = uuid4()
    with pytest.raises(BusinessValidationError, match="belong"):
        service.start_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")


def test_incomplete_predecessor_blocks_node_start() -> None:
    service, uow, task, node = _context()
    predecessor = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Predecessor",
        status="in_progress",
        progress_percent=50,
    )
    uow.task_nodes.list_predecessors.return_value = [
        TaskNodeDependency(
            task_id=task.task_id,
            predecessor_node_id=predecessor.node_id,
            successor_node_id=node.node_id,
        )
    ]
    uow.task_nodes.get_node.side_effect = lambda value: (
        node if value == node.node_id else predecessor
    )

    with pytest.raises(DependencyNotSatisfiedError):
        service.start_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")

    assert node.status == "pending"
    assert task.task_version == 3
    uow.commit.assert_not_called()


def test_progress_is_monotonic_and_100_percent_does_not_complete_node() -> None:
    service, uow, task, node = _context(
        node_status="in_progress",
        progress=40,
        actual_hours=Decimal("2"),
    )

    service.update_node_progress(
        task.task_id,
        node.node_id,
        "OWNER",
        3,
        "unit-test",
        100,
    )

    assert node.progress_percent == 100
    assert node.actual_hours == Decimal("2")
    assert node.status == "in_progress"
    assert node.completed_at is None
    assert task.task_version == 4
    assert _last_log(uow).action_type == "node_progress_updated"

    uow.reset_mock()
    uow.__enter__.return_value = uow
    uow.tasks.get_by_id_for_update.return_value = task
    uow.task_nodes.get_node.return_value = node
    with pytest.raises(BusinessValidationError, match="decrease"):
        service.update_node_progress(
            task.task_id,
            node.node_id,
            "OWNER",
            4,
            "unit-test",
            99,
        )
    uow.commit.assert_not_called()


def test_manual_node_actual_hours_are_rejected() -> None:
    service, uow, task, node = _context(node_status="in_progress", progress=40)
    with pytest.raises(BusinessValidationError, match="system-derived"):
        service.update_node_progress(
            task.task_id,
            node.node_id,
            "OWNER",
            3,
            "unit-test",
            60,
            Decimal("1.5"),
        )
    uow.commit.assert_not_called()


def test_complete_node_sets_final_node_fields_and_increments_once() -> None:
    service, uow, task, node = _context(node_status="in_progress", progress=80)

    service.complete_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")

    assert (node.status, node.progress_percent, node.completed_at) == (
        "completed",
        100,
        NOW,
    )
    assert task.task_version == 4
    assert _last_log(uow).action_type == "node_completed"

    with pytest.raises(InvalidStateTransitionError):
        service.complete_node(task.task_id, node.node_id, "OWNER", 4, "unit-test")


def test_active_blocker_prevents_node_completion_without_mutation() -> None:
    service, uow, task, node = _context(node_status="in_progress", progress=80)
    uow.task_issues.has_active_blocker.return_value = True

    with pytest.raises(OpenTaskIssueConflictError):
        service.complete_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")

    assert (node.status, node.progress_percent, task.task_version) == (
        "in_progress",
        80,
        3,
    )
    uow.commit.assert_not_called()


@pytest.mark.parametrize("operation", ["start", "progress", "complete"])
def test_pending_review_has_no_node_operation_back_to_in_progress(
    operation: str,
) -> None:
    service, uow, task, node = _context(
        task_status="pending_review",
        node_status="completed",
        progress=100,
    )

    with pytest.raises(InvalidStateTransitionError):
        if operation == "start":
            service.start_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")
        elif operation == "progress":
            service.update_node_progress(
                task.task_id,
                node.node_id,
                "OWNER",
                3,
                "unit-test",
                100,
            )
        else:
            service.complete_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")

    assert task.status == "pending_review"
    assert task.task_version == 3
    uow.commit.assert_not_called()


def test_completed_task_rejects_all_node_operations() -> None:
    service, uow, task, node = _context(
        task_status="completed",
        node_status="completed",
        progress=100,
    )

    with pytest.raises(InvalidStateTransitionError):
        service.start_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")

    uow.commit.assert_not_called()


def test_reopen_node_uses_latest_review_and_preserves_history_and_hours() -> None:
    service, uow, task, node = _context(
        node_status="completed",
        progress=100,
        actual_hours=Decimal("7.5"),
    )
    node.completed_at = NOW
    review = _rejected_review(task, node, review_round=2)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_completion_reviews.get_latest_rejected.return_value = review

    result = service.reopen_node(
        task.task_id,
        node.node_id,
        "REVIEWER",
        3,
        "unit-test",
        review.completion_review_id,
    )

    assert result is node
    assert (node.status, node.progress_percent, node.completed_at) == (
        "in_progress",
        0,
        None,
    )
    assert node.actual_hours == Decimal("7.5")
    assert task.task_version == 4
    assert (
        review.review_status,
        review.review_result,
        review.reviewed_task_version,
    ) == ("rejected", "rejected", 3)
    task_lock = call.tasks.get_by_id_for_update(task.task_id)
    review_lock = call.task_completion_reviews.get_by_task_and_id_for_update(
        task.task_id,
        review.completion_review_id,
    )
    node_lock = call.task_nodes.get_node_for_update(node.node_id)
    assert uow.mock_calls.index(task_lock) < uow.mock_calls.index(review_lock)
    assert uow.mock_calls.index(review_lock) < uow.mock_calls.index(node_lock)
    uow.task_status_logs.has_action_for_business_ref.assert_called_once_with(
        task.task_id,
        "node_reopened",
        "completion_review",
        review.completion_review_id,
    )
    log = _last_log(uow)
    assert (
        log.action_type,
        log.from_status,
        log.to_status,
        log.task_version,
    ) == ("node_reopened", "in_progress", "in_progress", 4)
    assert (log.business_ref_type, log.business_ref_id) == (
        "completion_review",
        review.completion_review_id,
    )
    uow.commit.assert_called_once_with()


def test_reopen_node_requires_snapshot_reviewer_and_exact_version() -> None:
    service, uow, task, node = _context(
        node_status="completed",
        progress=100,
    )
    review = _rejected_review(task, node)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_completion_reviews.get_latest_rejected.return_value = review

    with pytest.raises(TaskVersionConflictError):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            2,
            "unit-test",
            review.completion_review_id,
        )
    with pytest.raises(PermissionDeniedError, match="review reviewer"):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "ASSIGNEE",
            3,
            "unit-test",
            review.completion_review_id,
        )

    assert (node.status, node.progress_percent, task.task_version) == (
        "completed",
        100,
        3,
    )
    uow.commit.assert_not_called()


def test_reopen_node_rejects_cross_task_and_old_reviews() -> None:
    service, uow, task, node = _context(
        node_status="completed",
        progress=100,
    )
    review = _rejected_review(task, node, review_round=1)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = None

    with pytest.raises(EntityNotFoundError, match="completion review"):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            3,
            "unit-test",
            review.completion_review_id,
        )
    uow.task_completion_reviews.get_by_task_and_id_for_update.assert_called_with(
        task.task_id,
        review.completion_review_id,
    )

    latest = _rejected_review(task, node, review_round=2)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_completion_reviews.get_latest_rejected.return_value = latest
    with pytest.raises(InvalidStateTransitionError, match="latest rejected"):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            3,
            "unit-test",
            review.completion_review_id,
        )

    assert (node.status, node.progress_percent, task.task_version) == (
        "completed",
        100,
        3,
    )
    uow.commit.assert_not_called()


@pytest.mark.parametrize("overall_rework", [False, True])
def test_reopen_node_requires_the_review_exact_rework_node(
    overall_rework: bool,
) -> None:
    service, uow, task, node = _context(
        node_status="completed",
        progress=100,
    )
    review = _rejected_review(task, node)
    review.rework_node_id = None if overall_rework else uuid4()
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_completion_reviews.get_latest_rejected.return_value = review

    with pytest.raises(BusinessValidationError, match="does not match"):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            3,
            "unit-test",
            review.completion_review_id,
        )

    uow.task_nodes.get_node_for_update.assert_not_called()
    uow.commit.assert_not_called()


def test_reopen_node_is_once_only_and_requires_completed_same_task_node() -> None:
    service, uow, task, node = _context(
        node_status="completed",
        progress=100,
    )
    review = _rejected_review(task, node)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_completion_reviews.get_latest_rejected.return_value = review
    uow.task_status_logs.has_action_for_business_ref.return_value = True

    with pytest.raises(InvalidStateTransitionError, match="already been reopened"):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            3,
            "unit-test",
            review.completion_review_id,
        )
    uow.task_nodes.get_node_for_update.assert_not_called()

    uow.task_status_logs.has_action_for_business_ref.return_value = False
    node.task_id = uuid4()
    with pytest.raises(BusinessValidationError, match="does not belong"):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            3,
            "unit-test",
            review.completion_review_id,
        )
    node.task_id = task.task_id
    node.status = "in_progress"
    with pytest.raises(InvalidStateTransitionError, match="completed"):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            3,
            "unit-test",
            review.completion_review_id,
        )

    assert task.task_version == 3
    uow.commit.assert_not_called()


def test_reopen_node_requires_in_progress_task_and_propagates_failure() -> None:
    service, uow, task, node = _context(
        task_status="pending_review",
        node_status="completed",
        progress=100,
    )
    review = _rejected_review(task, node)

    with pytest.raises(InvalidStateTransitionError):
        service.reopen_node(
            task.task_id,
            node.node_id,
            "REVIEWER",
            3,
            "unit-test",
            review.completion_review_id,
        )

    uow.task_completion_reviews.get_by_task_and_id_for_update.assert_not_called()
    assert uow.__exit__.called
    assert (node.status, node.progress_percent, task.task_version) == (
        "completed",
        100,
        3,
    )
    uow.commit.assert_not_called()


def test_blocked_task_allows_owner_node_execution_but_assignee_cannot_take_other_owner_node() -> None:
    service, uow, task, node = _context(task_status="blocked", node_status="pending", owner="OWNER")
    service.start_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")
    assert node.status == "in_progress"

    task.task_version = 4
    node.status = "pending"
    with pytest.raises(PermissionDeniedError):
        service.start_node(task.task_id, node.node_id, "ASSIGNEE", 4, "unit-test")


def test_node_completion_derives_actual_hours_from_planned_start() -> None:
    service, _, task, node = _context(node_status="in_progress", progress=80)
    node.planned_start_time = NOW.replace(hour=7)
    service.complete_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")
    assert node.actual_hours == Decimal("2.0")


def test_pending_collaborator_must_accept_before_node_execution() -> None:
    service, uow, task, node = _context()
    node.assignment_status = "pending"

    with pytest.raises(InvalidStateTransitionError, match="accept the node assignment"):
        service.start_node(task.task_id, node.node_id, "OWNER", 3, "unit-test")

    assert node.status == "pending"
    assert task.task_version == 3
    uow.commit.assert_not_called()


def test_collaborator_accepts_assignment_then_execution_reminders_are_created() -> None:
    service, uow, task, node = _context()
    node.assignment_status = "pending"
    node.planned_start_time = NOW
    node.planned_deadline = NOW + timedelta(days=2)
    uow.session.scalar.return_value = None

    accepted = service.accept_node_assignment(
        task.task_id, node.node_id, "OWNER", 3, "unit-test", "assignment-accept-key"
    )

    assert accepted.assignment_status == "accepted"
    assert accepted.assignment_responded_at == NOW
    assert accepted.assignment_reject_reason is None
    assert task.task_version == 4
    added_types = {
        recorded.args[0].reminder_type
        for recorded in uow.session.add.call_args_list
        if recorded.args and recorded.args[0].__class__.__name__ == "ReminderRule"
    }
    assert added_types == {"node_start", "due_soon", "node_due"}
    assert _last_log(uow).action_type == "node_assignment_accepted"
    uow.commit.assert_called_once_with()


def test_collaborator_rejects_assignment_with_reason_and_main_assignee_is_notified() -> None:
    service, uow, task, node = _context()
    node.assignment_status = "pending"

    with pytest.raises(BusinessValidationError, match="reason is required"):
        service.reject_node_assignment(
            task.task_id, node.node_id, "OWNER", 3, "unit-test", "   "
        )

    rejected = service.reject_node_assignment(
        task.task_id, node.node_id, "OWNER", 3, "unit-test", "当前无法承接"
    )

    assert rejected.assignment_status == "rejected"
    assert rejected.assignment_reject_reason == "当前无法承接"
    notifications = [
        call.args[0] for call in uow.session.add.call_args_list
        if call.args and call.args[0].__class__.__name__ == "Notification"
    ]
    assert len(notifications) == 1
    assert notifications[0].recipient_employee_no == "ASSIGNEE"
    assert notifications[0].title == "协办节点无法承接"
    assert _last_log(uow).action_type == "node_assignment_rejected"
