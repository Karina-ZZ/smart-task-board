"""Test14 F1/F2: exercise response serialization and request validation.

Uses real action projection and HTTP/Pydantic contracts; repository mocks here
are not a substitute for the separate PostgreSQL and browser integration gates.
"""
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import get_args
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.api.dependencies import get_task_board_query_service, get_task_workflow_service
from app.main import app
from app.schemas.task import CreateTaskRequest, UpdateTaskDraftRequest
from app.schemas.task_board import AllowedAction
from app.services.task_board_query import _task_actions

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 7, tzinfo=UTC)


@pytest.mark.parametrize("status", [
    "pending_acceptance", "returned", "decomposing", "decomposition_failed",
    "in_progress", "blocked", "pending_report",
])
def test_creator_actions_are_representable_without_changing_permissions(status):
    task = SimpleNamespace(
        status=status, creator_employee_no="CREATOR", main_assignee_employee_no="ASSIGNEE",
        reviewer_employee_no="REVIEWER",
    )
    actions = _task_actions(task, "CREATOR", [], include_change_actions=True)
    assert "reassign_task" in actions
    assert TypeAdapter(list[AllowedAction]).validate_python(actions) == actions
    assert "reassign_task" not in _task_actions(task, "OBSERVER", [], include_change_actions=True)
    assert "reassign_task" not in _task_actions(task, "ASSIGNEE", [], include_change_actions=True)


def test_web_and_backend_action_contracts_are_identical_and_closed():
    block = (ROOT / "web/src/api/types.ts").read_text().split(
        "export type AllowedAction =", 1
    )[1].split(";", 1)[0]
    web_actions = set(re.findall(r'"([a-z_]+)"', block))
    assert web_actions == set(get_args(AllowedAction.__value__))
    assert "reassign_task" in web_actions
    with pytest.raises(ValidationError):
        TypeAdapter(AllowedAction).validate_python("not_a_real_action")


def summary(task_id):
    return {
        "task_id": task_id, "task_no": None, "task_name": "Test14 sent task",
        "status": "pending_acceptance", "deadline": NOW, "task_weight": 3,
        "is_urgent": False, "task_version": 3,
        "creator": {"employee_no": "CREATOR", "name": "Creator"},
        "main_assignee": {"employee_no": "ASSIGNEE", "name": "Assignee"},
        "current_user_relations": ["created"],
        "allowed_actions": ["reassign_task", "withdraw_task"],
        "is_overdue": False, "days_until_deadline": 1,
        "created_at": NOW, "updated_at": NOW,
    }


@pytest.mark.parametrize("endpoint", ["summary", "tasks", "inbox", "actions"])
def test_f1_actual_response_models_accept_creator_reassign(endpoint):
    task_id = uuid4()
    service = MagicMock()
    item = summary(task_id)
    service.dashboard_summary.return_value = {
        "created_task_count": 1, "assigned_task_count": 0, "inbox_count": 0,
        "in_progress_count": 0, "due_within_7_days_count": 0, "overdue_count": 0,
        "report_due_count": 0, "open_issue_count": 0, "due_window_days": 7,
        "recent_tasks": [item],
    }
    service.list_tasks.return_value = {"items": [item], "limit": 20, "offset": 0, "total": 1}
    service.available_actions.return_value = {
        "task_id": task_id, "task_version": 3, "current_user_relations": ["created"],
        "allowed_actions": item["allowed_actions"], "nodes": [],
    }
    service.list_inbox.return_value = {
        "items": [{
            "inbox_item_type": "accept_task", "action_code": "accept_task", "task": item,
            "node": None, "reason": "Waiting", "expected_task_version": 3,
            "endpoint": f"/api/v1/tasks/{task_id}/actions/accept",
            "allowed_actions": ["accept"], "is_overdue": False, "relevant_at": NOW,
        }], "limit": 20, "offset": 0, "total": 1,
    }
    paths = {
        "summary": "/api/v1/dashboard/summary", "tasks": "/api/v1/tasks",
        "inbox": "/api/v1/tasks/inbox", "actions": f"/api/v1/tasks/{task_id}/available-actions",
    }
    app.dependency_overrides[get_task_board_query_service] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(paths[endpoint], headers={"X-Employee-No": "CREATOR"})
        assert response.status_code == 200, response.text
        assert "reassign_task" in response.text
        assert str(task_id) in response.text
    finally:
        app.dependency_overrides.clear()


INVALID_CYCLES = [
    "weekly", "\u6bcf\u5468", "", "weekly:MON@24:00", "weekly:MON@09:60",
    "weekly:XXX@09:00", "weekly:mon@09:00", "weekly:MON@9:00",
    "weekly:MON@09:00\n", " weekly:MON@09:00", True, 5,
]


@pytest.mark.parametrize("cycle", INVALID_CYCLES)
@pytest.mark.parametrize("update", [False, True])
def test_invalid_cycle_is_422_before_workflow_or_database(cycle, update):
    service = MagicMock()
    app.dependency_overrides[get_task_workflow_service] = lambda: service
    service.create_task_draft.return_value = SimpleNamespace(
        task_id=uuid4(), status="draft", task_version=1, updated_at=NOW,
    )
    service.update_task_draft.return_value = service.create_task_draft.return_value
    body = {"expected_task_version": 1} if update else {"task_name": "Test14"}
    body["report_cycle"] = cycle
    path = f"/api/v1/tasks/{uuid4()}/draft" if update else "/api/v1/tasks"
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.request(
                "PATCH" if update else "POST", path, json=body,
                headers={"X-Employee-No": "CREATOR"},
            )
        assert response.status_code == 422, response.text
        assert "report_cycle" in response.text
        service.create_task_draft.assert_not_called()
        service.update_task_draft.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("cycle", [None, "weekly:MON@00:00", "weekly:SUN@23:59"])
def test_valid_cycles_and_partial_update_semantics(cycle):
    assert CreateTaskRequest(task_name="Test14", report_cycle=cycle).report_cycle == cycle
    update = UpdateTaskDraftRequest(expected_task_version=1, report_cycle=cycle)
    assert update.model_dump(exclude_unset=True)["report_cycle"] == cycle
    omitted = UpdateTaskDraftRequest(expected_task_version=1)
    assert "report_cycle" not in omitted.model_dump(exclude_unset=True)
