from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from app.models import Task, TaskParticipant
from app.services.errors import (
    InvalidStateTransitionError,
    PermissionDeniedError,
    TaskVersionConflictError,
)
from app.services.features.task_decomposition import TaskDecompositionService

NOW = datetime(2026, 9, 3, 1, 0, tzinfo=UTC)


class Provider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def decompose(self, payload):
        self.calls.append(payload)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _task(status="pending_acceptance", version=3, assignee="E1001"):
    return Task(
        task_id=uuid4(), task_name="DEV-09 task", task_description="desc", task_goal="goal",
        task_source="unit", creator_employee_no="E1003", main_assignee_employee_no=assignee,
        report_to_employee_no="E1003", reviewer_employee_no="E1003", status=status,
        start_time=NOW, deadline=NOW + timedelta(days=7), task_weight=4,
        task_version=version, created_at=NOW, updated_at=NOW,
    )


def _participant(task):
    return TaskParticipant(
        task_id=task.task_id, employee_no=task.main_assignee_employee_no,
        participant_role="assignee", is_primary=True, confirm_status="pending",
    )


def _uow_context(task):
    participant = _participant(task)
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.tasks.get_by_id_for_update.return_value = task
    uow.tasks.get_by_id.return_value = task
    uow.tasks.find_participant.return_value = participant
    uow.tasks.list_participants.return_value = [participant]
    uow.task_decompositions.get_by_idempotency.return_value = None
    uow.task_decompositions.get_active_for_task.return_value = None
    uow.task_decompositions.get_latest_for_task.return_value = None
    uow.task_status_logs.add.side_effect = lambda item: item

    def add_record(record):
        if record.decomposition_id is None:
            record.decomposition_id = uuid4()
        uow.task_decompositions.get_for_update.return_value = record
        uow.task_decompositions.get_latest_for_task.return_value = record
        return record

    uow.task_decompositions.add.side_effect = add_record
    return uow, participant


def _valid_result(owner="E1001"):
    nodes = []
    for index in range(5):
        nodes.append(
            {
                "clientNodeId": f"n{index + 1}",
                "nodeName": f"节点{index + 1}",
                "actionDetail": f"执行动作{index + 1}",
                "ownerEmployeeNo": owner,
                "plannedStartTime": (NOW + timedelta(hours=index)).isoformat(),
                "plannedDeadline": (NOW + timedelta(hours=index + 1)).isoformat(),
            }
        )
    dependencies = [
        {
            "predecessorClientNodeId": f"n{index}",
            "successorClientNodeId": f"n{index + 1}",
            "dependencyType": "finish_to_start",
        }
        for index in range(1, 5)
    ]
    return {"nodes": nodes, "dependencies": dependencies}


def test_accept_only_main_assignee_enters_decomposing_and_creates_one_attempt():
    task = _task()
    uow, participant = _uow_context(task)
    service = TaskDecompositionService(Mock(return_value=uow), clock=lambda: NOW)

    accepted = service.accept_task(task.task_id, "E1001", 3, idempotency_key="accept-key")

    assert accepted.status == "decomposing"
    assert accepted.accepted_at == NOW
    assert accepted.effective_at is None
    assert accepted.decomposition_status == "pending"
    assert accepted.task_version == 4
    assert participant.confirm_status == "accepted"
    record = uow.task_decompositions.add.call_args.args[0]
    assert record.status == "pending"
    assert record.task_version == 4
    assert record.idempotency_key == "accept-key"
    assert record.input_snapshot["rules"]["forbidEstimatedHours"] is True
    assert record.input_snapshot["participantEmployeeNos"] == ["E1001"]
    assert task.latest_decomposition_id == record.decomposition_id
    uow.commit.assert_called_once_with()


def test_accept_rejects_non_main_assignee():
    task = _task()
    uow, _ = _uow_context(task)
    service = TaskDecompositionService(Mock(return_value=uow), clock=lambda: NOW)
    with pytest.raises(PermissionDeniedError):
        service.accept_task(task.task_id, "E9999", 3)
    uow.commit.assert_not_called()



def test_get_latest_detaches_record_before_read_only_uow_closes():
    task = _task(status="decomposing", version=4)
    uow, _ = _uow_context(task)
    record = MagicMock()
    uow.task_decompositions.get_latest_for_task.return_value = record
    service = TaskDecompositionService(Mock(return_value=uow), clock=lambda: NOW)

    result = service.get_latest(task.task_id, "E1001")

    assert result is record
    uow.session.expunge.assert_called_once_with(record)


def test_execute_valid_result_persists_nodes_dependencies_and_effective_at():
    task = _task()
    uow, _ = _uow_context(task)
    provider = Provider(_valid_result())
    service = TaskDecompositionService(Mock(return_value=uow), provider=provider, clock=lambda: NOW)
    service.accept_task(task.task_id, "E1001", 3)
    record = uow.task_decompositions.add.call_args.args[0]
    uow.commit.reset_mock()

    result = service.execute(task.task_id, record.decomposition_id, "E1001")

    assert result.status == "succeeded"
    assert result.node_count == 5
    assert task.status == "in_progress"
    assert task.effective_at == NOW
    assert task.decomposition_status == "succeeded"
    assert uow.task_nodes.add_node.call_count == 5
    assert uow.task_nodes.add_dependency.call_count == 4
    for call in uow.task_nodes.add_node.call_args_list:
        node = call.args[0]
        assert node.decomposition_id == record.decomposition_id
        assert node.source_type == "ai"
        assert node.estimated_hours is None
        assert node.actual_hours is None
    assert provider.calls[0]["rules"]["nodeCountMin"] == 5
    assert uow.commit.call_count == 2  # running marker + success transaction


def test_invalid_result_fails_without_formal_nodes():
    task = _task()
    uow, _ = _uow_context(task)
    invalid = _valid_result()
    invalid["nodes"][0]["estimatedHours"] = 3
    service = TaskDecompositionService(
        Mock(return_value=uow), provider=Provider(invalid), clock=lambda: NOW
    )
    service.accept_task(task.task_id, "E1001", 3)
    record = uow.task_decompositions.add.call_args.args[0]
    uow.task_nodes.add_node.reset_mock()

    result = service.execute(task.task_id, record.decomposition_id, "E1001")

    assert result.status == "failed"
    assert result.error_code == "DECOMPOSITION_FAILED"
    assert task.status == "decomposition_failed"
    assert task.effective_at is None
    uow.task_nodes.add_node.assert_not_called()
    uow.task_nodes.add_dependency.assert_not_called()


def test_retry_creates_new_attempt_and_preserves_old_attempt():
    task = _task(status="decomposition_failed", version=7)
    uow, _ = _uow_context(task)
    old = MagicMock(retry_count=2)
    uow.task_decompositions.get_latest_for_task.return_value = old
    service = TaskDecompositionService(Mock(return_value=uow), clock=lambda: NOW)

    retried = service.retry(task.task_id, "E1001", 7, idempotency_key="retry-key")

    record = uow.task_decompositions.add.call_args.args[0]
    assert retried.status == "decomposing"
    assert retried.task_version == 8
    assert record.trigger_type == "retry"
    assert record.retry_count == 3
    assert record.idempotency_key == "retry-key"
    assert old.status != "invalidated"


def test_invalidated_or_stale_callback_cannot_write_nodes():
    task = _task()
    uow, _ = _uow_context(task)
    service = TaskDecompositionService(
        Mock(return_value=uow), provider=Provider(_valid_result()), clock=lambda: NOW
    )
    service.accept_task(task.task_id, "E1001", 3)
    record = uow.task_decompositions.add.call_args.args[0]
    record.status = "running"
    uow.task_decompositions.get_active_for_task.return_value = record

    TaskDecompositionService.invalidate_active(uow, task, now=NOW)
    assert record.status == "invalidated"
    with pytest.raises(InvalidStateTransitionError, match="DECOMPOSITION_INVALIDATED"):
        service.complete_result(task.task_id, record.decomposition_id, "E1001", _valid_result())
    uow.task_nodes.add_node.assert_not_called()


def test_callback_rechecks_task_version_before_commit():
    task = _task()
    uow, _ = _uow_context(task)
    service = TaskDecompositionService(Mock(return_value=uow), clock=lambda: NOW)
    service.accept_task(task.task_id, "E1001", 3)
    record = uow.task_decompositions.add.call_args.args[0]
    record.status = "running"
    task.task_version += 1
    with pytest.raises(TaskVersionConflictError):
        service.complete_result(task.task_id, record.decomposition_id, "E1001", _valid_result())
    uow.task_nodes.add_node.assert_not_called()


def test_success_main_assignee_nodes_are_accepted_without_success_fyi_notifications() -> None:
    task = _task()
    uow, _ = _uow_context(task)
    uow.session.scalar.return_value = None
    service = TaskDecompositionService(
        Mock(return_value=uow), provider=Provider(_valid_result("E1001")), clock=lambda: NOW
    )
    service.accept_task(task.task_id, "E1001", 3)
    record = uow.task_decompositions.add.call_args.args[0]
    uow.session.add.reset_mock()

    service.execute(task.task_id, record.decomposition_id, "E1001")

    nodes = [call.args[0] for call in uow.task_nodes.add_node.call_args_list]
    assert all(node.assignment_status == "accepted" for node in nodes)
    notifications = [
        call.args[0] for call in uow.session.add.call_args_list
        if call.args and call.args[0].__class__.__name__ == "Notification"
    ]
    assert notifications == []


def test_success_collaborator_nodes_are_pending_and_only_collaborator_gets_assignment_notice(
) -> None:
    task = _task()
    uow, assignee = _uow_context(task)
    collaborator = TaskParticipant(
        task_id=task.task_id, employee_no="E2002", participant_role="collaborator",
        is_primary=False, confirm_status="accepted",
    )
    uow.tasks.list_participants.return_value = [assignee, collaborator]
    uow.session.scalar.return_value = None
    service = TaskDecompositionService(
        Mock(return_value=uow), provider=Provider(_valid_result("E2002")), clock=lambda: NOW
    )
    service.accept_task(task.task_id, "E1001", 3)
    record = uow.task_decompositions.add.call_args.args[0]
    uow.session.add.reset_mock()

    service.execute(task.task_id, record.decomposition_id, "E1001")

    nodes = [call.args[0] for call in uow.task_nodes.add_node.call_args_list]
    assert all(node.assignment_status == "pending" for node in nodes)
    notifications = [
        call.args[0] for call in uow.session.add.call_args_list
        if call.args and call.args[0].__class__.__name__ == "Notification"
    ]
    assert len(notifications) == 5
    assert {row.recipient_employee_no for row in notifications} == {"E2002"}
    assert {row.title for row in notifications} == {"节点待承接"}
