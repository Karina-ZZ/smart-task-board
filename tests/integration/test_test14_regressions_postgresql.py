"""Test14: real PostgreSQL F1/F2 regressions using the existing isolated gate.

No migrations or test-target guard changes. Reuses the established fixture cleanup,
with unique test IDs; never deletes unrelated tasks or resets an existing database.
"""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models import Notification, Task, TaskNode, TaskParticipant, TaskStatusLog
from tests.integration.test_core_workflow_api_postgresql import (
    _create_payload,
    _create_references,
    _headers,
    _post_action,
    phase5_client,
    phase5_engine,
    phase5_records,
    phase5_session_factory,
)

__all__ = ["phase5_client", "phase5_engine", "phase5_records", "phase5_session_factory"]
pytestmark = pytest.mark.postgresql


def _new_task(client, factory, records, cycle=None):
    refs = _create_references(factory, records)
    payload = _create_payload(refs)
    payload.update(task_id=str(uuid4()), task_name="Test14 creator regression", report_cycle=cycle)
    task_id = UUID(payload["task_id"])
    records.task_ids.add(task_id)
    response = client.post("/api/v1/tasks", json=payload, headers=_headers(refs.creator))
    assert response.status_code == 201, response.text
    return refs, task_id, response.json()


def test_creator_sends_then_reads_dashboard_lists_and_actions_real_postgresql(
    phase5_client, phase5_session_factory, phase5_records,
):
    client = phase5_client
    refs, task_id, task = _new_task(client, phase5_session_factory, phase5_records)
    submitted = _post_action(client, task_id, "submit-for-confirmation", refs.creator,
                             task["task_version"])
    assert submitted.status_code == 200, submitted.text
    headers = {**_headers(refs.creator), "Idempotency-Key": f"test14-{task_id}"}
    payload = {"expected_task_version": submitted.json()["task_version"]}
    url = f"/api/v1/tasks/{task_id}/actions/confirm-and-send"
    sent = client.post(url, json=payload, headers=headers)
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "pending_acceptance"
    repeated = client.post(url, json=payload, headers=headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == sent.json()

    for path, field in [("/api/v1/dashboard/summary", "recent_tasks"),
                        ("/api/v1/tasks?relation=created", "items")]:
        response = client.get(path, headers=_headers(refs.creator))
        assert response.status_code == 200, response.text
        found = [t for t in response.json()[field] if t["task_id"] == str(task_id)]
        assert len(found) == 1, "HTTP 200 is insufficient if the sent task was dropped"
        assert "reassign_task" in found[0]["allowed_actions"]
    for actor, can_reassign in [(refs.creator, True), (refs.assignee, False)]:
        actions = client.get(f"/api/v1/tasks/{task_id}/available-actions", headers=_headers(actor))
        assert actions.status_code == 200, actions.text
        assert ("reassign_task" in actions.json()["allowed_actions"]) is can_reassign
        inbox = client.get("/api/v1/tasks/inbox", headers=_headers(actor))
        assert inbox.status_code == 200, inbox.text
    outsider = client.get("/api/v1/tasks", headers=_headers(refs.outsider))
    assert outsider.status_code == 200
    assert not any(t["task_id"] == str(task_id) for t in outsider.json()["items"])
    denied = client.put(
        f"/api/v1/tasks/{task_id}/assignee", headers=_headers(refs.assignee),
        json={"expected_task_version": sent.json()["task_version"],
              "new_assignee_employee_no": refs.outsider, "reason": "unauthorized probe"},
    )
    assert denied.status_code == 403, denied.text
    with phase5_session_factory() as session:
        persisted = session.get(Task, task_id)
        assert persisted.status == "pending_acceptance"
        assert persisted.task_version == sent.json()["task_version"]
        assert persisted.task_source is None
        assert persisted.report_cycle is None
        assert session.scalar(select(func.count()).select_from(TaskNode).where(
            TaskNode.task_id == task_id)) == 0
        notifications = session.scalars(select(Notification).where(
            Notification.task_id == task_id)).all()
        assert len(notifications) == 1
        assert notifications[0].recipient_employee_no == refs.assignee


@pytest.mark.parametrize("invalid", ["weekly", "\u6bcf\u5468"])
def test_illegal_cycle_create_422_leaves_no_business_rows(
    phase5_client, phase5_session_factory, phase5_records, invalid,
):
    refs = _create_references(phase5_session_factory, phase5_records)
    task_id = uuid4()
    phase5_records.task_ids.add(task_id)
    payload = _create_payload(refs)
    payload.update(task_id=str(task_id), report_cycle=invalid)
    response = phase5_client.post("/api/v1/tasks", json=payload, headers=_headers(refs.creator))
    assert response.status_code == 422, response.text
    assert "report_cycle" in response.text
    with phase5_session_factory() as session:
        for model in (Task, TaskNode, TaskParticipant, TaskStatusLog, Notification):
            assert session.scalar(select(func.count()).select_from(model).where(
                model.task_id == task_id)) == 0


def test_cycle_patch_is_atomic_and_preserves_omitted_vs_null(
    phase5_client, phase5_session_factory, phase5_records,
):
    refs, task_id, task = _new_task(
        phase5_client, phase5_session_factory, phase5_records, "weekly:MON@09:00",
    )
    path = f"/api/v1/tasks/{task_id}/draft"
    headers = _headers(refs.creator)
    for invalid in ("weekly", "weekly:MON@24:00"):
        response = phase5_client.patch(path, headers=headers, json={
            "expected_task_version": task["task_version"],
            "report_cycle": invalid, "task_name": "Must not persist",
        })
        assert response.status_code == 422, response.text
        with phase5_session_factory() as session:
            row = session.get(Task, task_id)
            assert row.task_version == task["task_version"]
            assert row.task_name == "Test14 creator regression"
            assert row.report_cycle == "weekly:MON@09:00"
    for patch, expected in [({"task_goal": "Edited"}, "weekly:MON@09:00"),
                            ({"report_cycle": None}, None),
                            ({"report_cycle": "weekly:FRI@17:30"}, "weekly:FRI@17:30")]:
        response = phase5_client.patch(path, headers=headers, json={
            "expected_task_version": task["task_version"], **patch,
        })
        assert response.status_code == 200, response.text
        task = response.json()
        with phase5_session_factory() as session:
            assert session.get(Task, task_id).report_cycle == expected
