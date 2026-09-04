"""Feature 11 completion, review, idempotency, and automatic archive rules."""
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import MagicMock, Mock
from uuid import uuid4

from app.models import OperationLog, Task, TaskCompletionReview, TaskNode
from app.services import TaskWorkflowService

NOW = datetime(2026, 9, 3, 2, 0, tzinfo=UTC)


def _task(*, status: str = "pending_review", version: int = 9) -> Task:
    return Task(
        task_id=uuid4(),
        task_name="Feature 11 task",
        task_description="Completion lifecycle",
        task_goal="Archive after approval",
        creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE",
        reviewer_employee_no="REVIEWER",
        status=status,
        start_time=NOW - timedelta(hours=26.5),
        task_version=version,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(hours=1),
    )


def _review(task: Task) -> TaskCompletionReview:
    return TaskCompletionReview(
        completion_review_id=uuid4(),
        task_id=task.task_id,
        review_round=2,
        submitted_by_employee_no="ASSIGNEE",
        completion_note="Finished all requested work",
        deliverable_summary="Final delivery summary",
        reviewer_employee_no="REVIEWER",
        review_status="submitted",
        submitted_task_version=task.task_version,
        submitted_at=NOW - timedelta(minutes=10),
        is_legacy_import=False,
    )


def _service(task: Task, review: TaskCompletionReview):
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Done",
        status="completed",
        progress_percent=100,
    )
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.tasks.get_by_id_for_update.return_value = task
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_nodes.list_nodes.return_value = [node]
    uow.task_nodes.list_dependencies.return_value = []
    uow.task_nodes.list_participants_by_task_id.return_value = []
    uow.task_issues.has_non_closed.return_value = False
    uow.task_archives.get_by_task_id.return_value = None
    uow.task_archives.add.side_effect = lambda value: value
    uow.task_status_logs.add.side_effect = lambda value: value
    return TaskWorkflowService(Mock(return_value=uow), clock=lambda: NOW), uow


def test_creator_can_approve_and_approval_immediately_archives_without_snapshot() -> None:
    task = _task()
    review = _review(task)
    service, uow = _service(task, review)

    saved_task, saved_review = service.approve_completion(
        task.task_id,
        "CREATOR",
        9,
        "unit-test",
        review.completion_review_id,
    )

    assert saved_task is task and saved_review is review
    assert task.status == "archived"
    assert task.completed_at == NOW
    assert task.archived_at == NOW
    assert task.actual_hours == Decimal("26.5")
    assert review.review_status == "approved"
    assert review.review_result == "approved"
    assert review.reject_reason is None
    assert review.reviewed_task_version == 11
    archive = uow.task_archives.add.call_args.args[0]
    assert archive.archive_snapshot is None
    assert archive.source_status_snapshot == "completed"
    assert archive.actual_hours_total == Decimal("26.5")
    assert archive.review_result == "approved"
    assert [call.args[0].action_type for call in uow.task_status_logs.add.call_args_list] == [
        "completion_approved",
        "task_archived",
    ]
    uow.commit.assert_called_once_with()


def test_completion_approval_idempotency_returns_existing_archive_result() -> None:
    task = _task(status="archived", version=11)
    review = _review(task)
    review.review_status = "approved"
    review.review_result = "approved"
    review.reviewed_at = NOW
    review.reviewed_task_version = 11
    log = OperationLog(
        request_id="review-key",
        operator_employee_no="REVIEWER",
        action="completion_approved",
        object_type="completion_review",
        object_id=str(review.completion_review_id),
        result="success",
        created_at=NOW,
    )
    service, uow = _service(task, review)
    uow.session.scalar.return_value = log
    uow.task_completion_reviews.get_by_id.return_value = review
    uow.tasks.get_by_id.return_value = task

    result = service.approve_completion(
        task.task_id,
        "REVIEWER",
        9,
        "unit-test",
        review.completion_review_id,
        "review-key",
    )

    assert result == (task, review)
    uow.tasks.get_by_id_for_update.assert_not_called()
    uow.task_archives.add.assert_not_called()
    uow.commit.assert_not_called()
