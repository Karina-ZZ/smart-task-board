"""Test16: real FastAPI response validation after the ORM replay branch.

Persists a successful-log fixture in isolated SQLite, then runs unmocked routes,
service, UnitOfWork and response validation. NOT PG, first-send, real login or UI
acceptance; those have separate gates. No production dependency is modified.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.core.config import get_settings
from app.db.unit_of_work import UnitOfWork
from app.main import app
from tests.services.test_test16_replay_lifetime import CASES, replay_db, seed_success

__all__ = ["replay_db"]


@pytest.mark.parametrize("method,action,status", CASES)
def test_cached_action_has_readable_http_response(replay_db, monkeypatch, method, action, status):
    factory, events = replay_db
    task_id = seed_success(factory, action, status)
    events.clear()
    monkeypatch.setenv("AUTH_MODE", "test_header")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOW_TEST_EMPLOYEE_HEADER", "true")
    monkeypatch.setenv("PROTOTYPE_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[dependencies.get_uow_factory] = lambda: lambda: UnitOfWork(factory)
    path = {
        "confirm_and_send": f"/api/v1/tasks/{task_id}/actions/confirm-and-send",
        "reassign_task": f"/api/v1/tasks/{task_id}/assignee",
        "cancel_task": f"/api/v1/tasks/{task_id}/actions/cancel",
        "withdraw_task": f"/api/v1/tasks/{task_id}/actions/withdraw",
    }[method]
    payload = {"expected_task_version": 2}
    if method != "confirm_and_send":
        payload["reason"] = "Approved regression"
    if method == "reassign_task":
        payload["new_assignee_employee_no"] = "ASSIGNEE"
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            bodies = []
            for _ in range(2):
                response = client.request(
                    "PUT" if method == "reassign_task" else "POST", path, json=payload,
                    headers={"X-Employee-No": "CREATOR", "Idempotency-Key": "test16-replay"},
                )
                assert response.status_code == 200, response.text
                bodies.append(response.json())
            assert bodies[0] == bodies[1]
            assert bodies[0]["task_id"] == str(task_id)
            assert bodies[0]["status"] == status
            assert bodies[0]["task_version"] == 3
            assert set(bodies[0]) == {"task_id", "status", "task_version", "updated_at"}
            assert events == ["rollback", "rollback"]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        get_settings.cache_clear()
