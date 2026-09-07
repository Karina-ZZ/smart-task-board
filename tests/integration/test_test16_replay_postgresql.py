"""Test16: real PostgreSQL replay, side-effect and isolation regressions.

Reuses the unchanged approved PG fixtures, schema, cleanup and URL guards. This
file never provisions/drops a database and does not replace any prior PG test.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.unit_of_work import UnitOfWork
from app.models import (
    Notification,
    OperationLog,
    Task,
    TaskNode,
    TaskParticipant,
    TaskStatusLog,
)
from app.schemas.task import TaskActionResponse
from app.services import InvalidStateTransitionError, TaskVersionConflictError, TaskWorkflowService
from tests.integration.test_core_workflow_api_postgresql import (
    _headers,
    _post_action,
    phase5_client,
    phase5_engine,
    phase5_records,
    phase5_session_factory,
)
from tests.integration.test_test14_regressions_postgresql import _new_task

__all__ = ["phase5_client", "phase5_engine", "phase5_records", "phase5_session_factory"]
pytestmark = pytest.mark.postgresql


def prepared(client, factory, records):
    refs, task_id, task = _new_task(client, factory, records)
    submitted = _post_action(
        client, task_id, "submit-for-confirmation", refs.creator, task["task_version"],
    )
    assert submitted.status_code == 200, submitted.text
    return refs, task_id, submitted.json()


def call(client, task_id, actor, action, body, key):
    path = (f"/api/v1/tasks/{task_id}/assignee" if action == "reassign"
            else f"/api/v1/tasks/{task_id}/actions/{action}")
    return client.request(
        "PUT" if action == "reassign" else "POST", path, json=body,
        headers={**_headers(actor), "Idempotency-Key": key},
    )


def fingerprint(factory, task_id):
    with factory() as session:
        task = session.get(Task, task_id)
        result = {
            "task": (task.status, task.task_version, task.updated_at, task.sent_at,
                     task.main_assignee_employee_no, task.cancel_reason, task.withdraw_reason),
            "participants": sorted(
                (p.employee_no, p.participant_role, p.is_primary, p.confirm_status)
                for p in session.scalars(select(TaskParticipant).where(
                    TaskParticipant.task_id == task_id,
                ))
            ),
            "operations": sorted(str(o.operation_log_id) for o in session.scalars(
                select(OperationLog).where(OperationLog.object_id == str(task_id)),
            )),
        }
        for model in (TaskStatusLog, Notification, TaskNode):
            result[model.__tablename__] = session.scalar(
                select(func.count()).select_from(model).where(model.task_id == task_id),
            )
        return result


@pytest.mark.parametrize("action", ["confirm-and-send", "reassign", "cancel", "withdraw"])
def test_first_action_then_three_replays_have_one_effect_real_pg(
    phase5_client, phase5_session_factory, phase5_records, action,
):
    client, factory = phase5_client, phase5_session_factory
    refs, task_id, task = prepared(client, factory, phase5_records)
    if action != "confirm-and-send":
        sent = call(client, task_id, refs.creator, "confirm-and-send",
                    {"expected_task_version": task["task_version"]}, f"send-{task_id}")
        assert sent.status_code == 200, sent.text
        task = sent.json()
    body = {"expected_task_version": task["task_version"]}
    if action != "confirm-and-send":
        body["reason"] = "Test16 approved regression"
    if action == "reassign":
        body["new_assignee_employee_no"] = refs.reviewer
    key = f"test16-{task_id}-{action}"
    first = call(client, task_id, refs.creator, action, body, key)
    assert first.status_code == 200, first.text
    before = fingerprint(factory, task_id)
    for _ in range(3):
        # Re-send the identical request, including its now-stale request version.
        repeated = call(client, task_id, refs.creator, action, body, key)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json() == first.json()
        assert fingerprint(factory, task_id) == before
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(OperationLog).where(
            OperationLog.object_id == str(task_id), OperationLog.request_id == key,
            OperationLog.result == "success",
        )) == 1
        task = session.get(Task, task_id)
        assert task.task_source is None
        assert session.scalar(select(func.count()).select_from(TaskNode).where(
            TaskNode.task_id == task_id,
        )) == 0
    if action == "confirm-and-send":
        assert before["notifications"] == 1
        with factory() as session:
            notice = session.scalar(select(Notification).where(Notification.task_id == task_id))
            assert notice.recipient_employee_no == refs.assignee
        summary = client.get("/api/v1/dashboard/summary", headers=_headers(refs.creator))
        assert summary.status_code == 200, summary.text
        rows = [t for t in summary.json()["recent_tasks"] if t["task_id"] == str(task_id)]
        assert len(rows) == 1 and "reassign_task" in rows[0]["allowed_actions"]


def test_replay_does_not_bypass_new_key_version_or_actor_guards_real_pg(
    phase5_client, phase5_session_factory, phase5_records,
):
    client, factory = phase5_client, phase5_session_factory
    refs, task_id, task = prepared(client, factory, phase5_records)
    key = f"test16-{task_id}"
    body = {"expected_task_version": task["task_version"]}
    sent = call(client, task_id, refs.creator, "confirm-and-send", body, key)
    assert sent.status_code == 200, sent.text
    before = fingerprint(factory, task_id)["task"]
    for actor, request_key in [(refs.creator, key + "-new"), (refs.outsider, key)]:
        denied = call(client, task_id, actor, "confirm-and-send", body, request_key)
        assert denied.status_code == 409, denied.text  # Existing version guard runs first.
        assert "task_id" not in denied.json()
    denied = call(client, task_id, refs.outsider, "reassign", {
        "expected_task_version": sent.json()["task_version"],
        "new_assignee_employee_no": refs.outsider, "reason": "Unauthorized",
    }, key)
    assert denied.status_code == 403, denied.text
    assert fingerprint(factory, task_id)["task"] == before


def test_same_key_is_scoped_to_task_and_action_real_pg(
    phase5_client, phase5_session_factory, phase5_records,
):
    client, factory = phase5_client, phase5_session_factory
    key = f"test16-scope-{uuid4()}"
    refs, task_id, task = prepared(client, factory, phase5_records)
    sent = call(client, task_id, refs.creator, "confirm-and-send",
                {"expected_task_version": task["task_version"]}, key)
    assert sent.status_code == 200, sent.text
    # Same actor/key but another action must perform that authorized action, not replay send.
    cancelled = call(client, task_id, refs.creator, "cancel", {
        "expected_task_version": sent.json()["task_version"], "reason": "Scope test",
    }, key)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    # Another task with the SAME actor and key must be sent independently.
    from tests.integration.test_core_workflow_api_postgresql import _create_payload

    other_id = uuid4()
    phase5_records.task_ids.add(other_id)
    payload = _create_payload(refs)
    payload.update(task_id=str(other_id), extraction_record_ids=[])
    created = client.post("/api/v1/tasks", json=payload, headers=_headers(refs.creator))
    assert created.status_code == 201, created.text
    submitted = _post_action(client, other_id, "submit-for-confirmation", refs.creator,
                             created.json()["task_version"])
    assert submitted.status_code == 200, submitted.text
    other_sent = call(client, other_id, refs.creator, "confirm-and-send",
                      {"expected_task_version": submitted.json()["task_version"]}, key)
    assert other_sent.status_code == 200, other_sent.text
    assert other_sent.json()["task_id"] == str(other_id)
    assert other_sent.json()["status"] == "pending_acceptance"


def test_old_send_replay_after_withdraw_does_not_resend_real_pg(
    phase5_client, phase5_session_factory, phase5_records,
):
    client, factory = phase5_client, phase5_session_factory
    refs, task_id, task = prepared(client, factory, phase5_records)
    key, body = f"test16-later-{task_id}", {"expected_task_version": task["task_version"]}
    sent = call(client, task_id, refs.creator, "confirm-and-send", body, key)
    assert sent.status_code == 200, sent.text
    withdrawn = call(client, task_id, refs.creator, "withdraw", {
        "expected_task_version": sent.json()["task_version"], "reason": "Later action",
    }, key + "-withdraw")
    assert withdrawn.status_code == 200, withdrawn.text
    before = fingerprint(factory, task_id)
    replayed = call(client, task_id, refs.creator, "confirm-and-send", body, key)
    assert replayed.status_code == 200, replayed.text
    # Existing lookup returns the CURRENT task, not a persisted historical response.
    assert replayed.json() == withdrawn.json()
    assert fingerprint(factory, task_id) == before


def test_concurrent_send_and_subsequent_replay_has_one_effect_real_pg(
    phase5_client, phase5_session_factory, phase5_records,
):
    client, factory = phase5_client, phase5_session_factory
    refs, task_id, task = prepared(client, factory, phase5_records)
    barrier = Barrier(2, timeout=10)
    key = f"test16-concurrent-{task_id}"

    def send_once():
        service = TaskWorkflowService(lambda: UnitOfWork(factory))
        barrier.wait()
        try:
            result = service.confirm_and_send(
                task_id, refs.creator, task["task_version"], "test16", key,
            )
            return 200, TaskActionResponse.model_validate(result).model_dump(mode="json")
        except (TaskVersionConflictError, InvalidStateTransitionError):
            # Preserve the existing concurrent-before-log-commit conflict contract.
            return 409, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send_once) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert any(code == 200 for code, _ in results)
    assert all(code in {200, 409} for code, _ in results)
    before = fingerprint(factory, task_id)
    repeated = call(client, task_id, refs.creator, "confirm-and-send",
                    {"expected_task_version": task["task_version"]}, key)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["task_version"] == task["task_version"] + 1
    assert before["notifications"] == 1
    assert fingerprint(factory, task_id) == before
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(TaskStatusLog).where(
            TaskStatusLog.task_id == task_id, TaskStatusLog.action_type == "confirmed_and_sent",
        )) == 1
        assert session.scalar(select(func.count()).select_from(OperationLog).where(
            OperationLog.object_id == str(task_id), OperationLog.action == "confirm_and_send",
            OperationLog.request_id == key, OperationLog.result == "success",
        )) == 1
