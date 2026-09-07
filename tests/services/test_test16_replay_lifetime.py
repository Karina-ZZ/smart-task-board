"""Test16: exercise real ORM rollback/close, not a mocked UnitOfWork.

SQLite column-only fixtures deliberately test object lifetime, NOT PostgreSQL
constraints, locks, or business transactions. The independent PG suite keeps all
production schema and safety guards. Successful records below are fixture facts.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import JSON, Column, MetaData, Table, create_engine, event, inspect, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.unit_of_work import UnitOfWork
from app.models import OperationLog, Task
from app.schemas.task import TaskActionResponse
from app.services.shared.idempotency import find_task
from app.services.task_workflow import TaskWorkflowService

NOW = datetime(2026, 9, 7, 6, 0, tzinfo=UTC)
CASES = [
    ("confirm_and_send", "confirm_and_send", "pending_acceptance"),
    ("reassign_task", "assignee_reassigned", "pending_acceptance"),
    ("cancel_task", "task_cancelled", "cancelled"),
    ("withdraw_task", "task_withdrawn", "withdrawn"),
]


@pytest.fixture(params=[False, True], ids=["commit_keeps_fields", "commit_expires_fields"])
def replay_db(request):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    metadata = MetaData()
    for model in (Task, OperationLog):
        # A local column-only table, never a change to model metadata or migrations.
        Table(model.__tablename__, metadata, *[
            Column(c.name, JSON() if isinstance(c.type, JSONB) else c.type,
                   primary_key=c.primary_key, nullable=c.nullable)
            for c in model.__table__.columns
        ])
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=request.param)
    events = []
    event.listen(factory, "after_commit", lambda session: events.append("commit"))
    event.listen(factory, "after_rollback", lambda session: events.append("rollback"))
    try:
        yield factory, events
    finally:
        engine.dispose()


def seed_success(factory, action, status, *, actor="CREATOR", key="test16-replay"):
    task_id = uuid4()
    with factory.begin() as session:
        session.add(Task(
            task_id=task_id, task_name="Test16 lifetime probe", task_source=None,
            creator_employee_no="CREATOR", main_assignee_employee_no="ASSIGNEE",
            status=status, task_version=3, created_at=NOW, updated_at=NOW,
            cancel_reason="Stopped" if status == "cancelled" else None,
        ))
        session.add(OperationLog(
            operation_log_id=uuid4(), request_id=key, operator_employee_no=actor,
            action=action, object_type="task", object_id=str(task_id), result="success",
            after_data={"status": status, "task_version": 3}, created_at=NOW,
        ))
    return task_id


def replay(service, method, task_id):
    args = (task_id, "CREATOR", 2, "test16-lifetime")
    if method == "reassign_task":
        return service.reassign_task(*args, "ASSIGNEE", "Capacity", "test16-replay")
    if method in {"cancel_task", "withdraw_task"}:
        return getattr(service, method)(*args, "Stopped", "test16-replay")
    return service.confirm_and_send(*args, "test16-replay")


@pytest.mark.parametrize("method,action,status", CASES)
def test_replay_readable_after_real_uow_rollback_and_close(replay_db, method, action, status):
    factory, events = replay_db
    task_id = seed_success(factory, action, status)
    events.clear()
    service = TaskWorkflowService(lambda: UnitOfWork(factory))
    for _ in range(3):
        result = replay(service, method, task_id)
        response = TaskActionResponse.model_validate(result)
        assert response.task_id == task_id
        assert response.status == status
        assert response.task_version == 3
        # Preserve existing internal callers that consume Task fields beyond the DTO.
        assert isinstance(result, Task)
        assert result.task_source is None
        assert result.main_assignee_employee_no == "ASSIGNEE"
        assert inspect(result).detached
        assert not inspect(result).expired_attributes
        assert not (set(inspect(Task).column_attrs.keys()) & inspect(result).unloaded)
    assert events == ["rollback"] * 3, "Read-only replay must not commit"
    with factory() as session:
        assert session.get(Task, task_id).task_version == 3
        assert len(session.scalars(select(OperationLog)).all()) == 1


def test_unmodified_uow_still_expires_uncommitted_bound_instances(replay_db):
    factory, events = replay_db
    task_id = seed_success(factory, "confirm_and_send", "pending_acceptance")
    events.clear()
    with UnitOfWork(factory) as uow:
        raw = uow.session.get(Task, task_id)
        raw.task_name = "Uncommitted, must roll back"
    with pytest.raises(ValidationError) as exc:
        TaskActionResponse.model_validate(raw)
    errors = exc.value.errors(include_url=False)
    assert {e["loc"][0] for e in errors} == {
        "task_id", "status", "task_version", "updated_at",
    }
    assert all("DetachedInstanceError" in str(e.get("ctx")) for e in errors)
    assert events == ["rollback"]
    with factory() as session:
        assert session.get(Task, task_id).task_name == "Test16 lifetime probe"


@pytest.mark.parametrize("dimension", ["key", "actor", "action", "task_id"])
def test_idempotency_lookup_scope_is_unchanged(replay_db, dimension):
    factory, _ = replay_db
    task_id = seed_success(factory, "confirm_and_send", "pending_acceptance")
    query = dict(key="test16-replay", actor="CREATOR", action="confirm_and_send", task_id=task_id)
    query[dimension] = uuid4() if dimension == "task_id" else "different"
    with UnitOfWork(factory) as uow:
        assert find_task(uow.session, **query) is None


@pytest.mark.parametrize("method,action,status", CASES)
def test_replay_does_not_restore_an_old_state(replay_db, method, action, status):
    factory, events = replay_db
    task_id = seed_success(factory, action, status)
    with factory.begin() as session:
        task = session.get(Task, task_id)
        task.status = "archived"
        task.task_version = 9
    events.clear()
    result = replay(TaskWorkflowService(lambda: UnitOfWork(factory)), method, task_id)
    response = TaskActionResponse.model_validate(result)
    assert response.status == "archived"
    assert response.task_version == 9
    assert events == ["rollback"]
    with factory() as session:
        assert session.get(Task, task_id).status == "archived"
        assert session.get(Task, task_id).task_version == 9
