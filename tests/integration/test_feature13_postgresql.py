"""
Feature: PostgreSQL production gate for Feature 13 notifications and node assignment.

Responsibilities:
- Verify collaborator assignment state against real PostgreSQL constraints and row locks.
- Verify transaction rollback and notification/reminder uniqueness under concurrent sessions.
- Detect duplicate delivery races in the notification outbox.

Does not own: provisioning PostgreSQL or external WeCom delivery.
Plan task: DEV-15 PostgreSQL gate.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, delete, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.unit_of_work import UnitOfWork
from app.models import Notification, OperationLog, ReminderRule, Task, TaskNode, TaskStatusLog, User
from app.services import InvalidStateTransitionError, TaskVersionConflictError
from app.services.business_capabilities import ReminderNotificationService
from app.services.task_node_workflow import TaskNodeWorkflowService

pytestmark = pytest.mark.postgresql

EXPECTED_DATABASE = "smarttaskboard_core_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 46479
EXPECTED_REVISION = "c2d3e4f5a6b7"
NOW = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Seed:
    task_id: UUID
    node_id: UUID
    creator: str
    main: str
    collaborator: str
    admin: str


@pytest.fixture(scope="session")
def feature13_pg_engine() -> Iterator[Engine]:
    if os.getenv("RUN_POSTGRESQL_INTEGRATION") != "1":
        pytest.skip("set RUN_POSTGRESQL_INTEGRATION=1 for explicit PostgreSQL tests")
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    parsed = make_url(database_url)
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host != EXPECTED_HOST
        or parsed.port != EXPECTED_PORT
        or parsed.database != EXPECTED_DATABASE
    ):
        pytest.fail("Feature 13 target is not the approved isolated PostgreSQL database")
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=1500"},
    )
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalar_one()
            assert revision == EXPECTED_REVISION
        columns = {item["name"] for item in inspect(engine).get_columns("task_nodes")}
        assert {
            "assignment_status",
            "assignment_responded_at",
            "assignment_reject_reason",
        } <= columns
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session_factory(feature13_pg_engine: Engine):
    return sessionmaker(bind=feature13_pg_engine, expire_on_commit=False)


@pytest.fixture
def seed(session_factory) -> Iterator[Seed]:
    suffix = uuid4().hex[:10]
    refs = Seed(
        task_id=uuid4(),
        node_id=uuid4(),
        creator=f"PG13-C-{suffix}",
        main=f"PG13-M-{suffix}",
        collaborator=f"PG13-X-{suffix}",
        admin=f"PG13-A-{suffix}",
    )
    with session_factory() as session:
        session.add_all(
            [
                User(employee_no=refs.creator, name="PG creator", role_type="employee", status="active"),
                User(employee_no=refs.main, name="PG main", role_type="employee", status="active"),
                User(employee_no=refs.collaborator, name="PG collaborator", role_type="employee", status="active"),
                User(employee_no=refs.admin, name="PG scheduler", role_type="admin", status="active"),
            ]
        )
        session.add(
            Task(
                task_id=refs.task_id,
                task_no=f"PG13-{suffix}",
                task_name="Feature 13 PostgreSQL gate task",
                creator_employee_no=refs.creator,
                main_assignee_employee_no=refs.main,
                status="in_progress",
                task_version=1,
                start_time=NOW,
                deadline=NOW + timedelta(days=2),
                effective_at=NOW,
            )
        )
        session.add(
            TaskNode(
                node_id=refs.node_id,
                task_id=refs.task_id,
                node_order=1,
                node_name="Collaborator assignment gate",
                owner_employee_no=refs.collaborator,
                planned_start_time=NOW + timedelta(hours=1),
                planned_deadline=NOW + timedelta(days=2),
                status="pending",
                assignment_status="pending",
            )
        )
        session.commit()
    try:
        yield refs
    finally:
        with session_factory() as session:
            # Child rows are explicitly removed because production FKs use RESTRICT.
            session.execute(delete(Notification).where(Notification.task_id == refs.task_id))
            session.execute(delete(ReminderRule).where(ReminderRule.task_id == refs.task_id))
            session.execute(delete(OperationLog).where(OperationLog.object_id.in_(
                [str(refs.task_id), str(refs.node_id), refs.admin, refs.collaborator]
            )))
            session.execute(delete(TaskStatusLog).where(TaskStatusLog.task_id == refs.task_id))
            session.execute(delete(TaskNode).where(TaskNode.task_id == refs.task_id))
            session.execute(delete(Task).where(Task.task_id == refs.task_id))
            session.execute(delete(User).where(User.employee_no.in_(
                [refs.creator, refs.main, refs.collaborator, refs.admin]
            )))
            session.commit()


def _service(session_factory, *, clock=lambda: NOW) -> TaskNodeWorkflowService:
    return TaskNodeWorkflowService(lambda: UnitOfWork(session_factory), clock=clock)


def test_assignment_status_check_constraint_is_real(feature13_pg_engine: Engine, seed: Seed) -> None:
    with Session(feature13_pg_engine) as session:
        node = session.get(TaskNode, seed.node_id)
        assert node is not None
        node.assignment_status = "invalid-status"
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.get(TaskNode, seed.node_id).assignment_status == "pending"


def test_pending_collaborator_cannot_start_real_postgresql(session_factory, seed: Seed) -> None:
    service = _service(session_factory)
    with pytest.raises(InvalidStateTransitionError, match="accept the node assignment"):
        service.start_node(
            seed.task_id,
            seed.node_id,
            seed.collaborator,
            1,
            "postgresql-gate",
        )
    with session_factory() as session:
        node = session.get(TaskNode, seed.node_id)
        task = session.get(Task, seed.task_id)
        assert node.assignment_status == "pending"
        assert node.status == "pending"
        assert task.task_version == 1


def test_accept_transaction_rolls_back_if_reminder_scheduling_fails(
    session_factory, seed: Seed, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_schedule(*args, **kwargs):
        raise RuntimeError("forced reminder failure")

    monkeypatch.setattr(
        "app.services.task_node_workflow.schedule_node_execution_reminders",
        fail_schedule,
    )
    service = _service(session_factory)
    with pytest.raises(RuntimeError, match="forced reminder failure"):
        service.accept_node_assignment(
            seed.task_id,
            seed.node_id,
            seed.collaborator,
            1,
            "postgresql-gate",
        )
    with session_factory() as session:
        node = session.get(TaskNode, seed.node_id)
        task = session.get(Task, seed.task_id)
        assert node.assignment_status == "pending"
        assert node.assignment_responded_at is None
        assert task.task_version == 1
        assert session.scalar(
            select(ReminderRule).where(ReminderRule.task_id == seed.task_id)
        ) is None


def test_concurrent_accept_has_one_effect_real_postgresql(session_factory, seed: Seed) -> None:
    barrier = threading.Barrier(2)

    def accept_once():
        barrier.wait(timeout=3)
        service = _service(session_factory)
        try:
            service.accept_node_assignment(
                seed.task_id,
                seed.node_id,
                seed.collaborator,
                1,
                "postgresql-gate",
            )
            return "accepted"
        except (TaskVersionConflictError, InvalidStateTransitionError) as exc:
            return type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept_once(), range(2)))
    assert results.count("accepted") == 1
    with session_factory() as session:
        task = session.get(Task, seed.task_id)
        node = session.get(TaskNode, seed.node_id)
        rules = list(session.scalars(
            select(ReminderRule).where(ReminderRule.task_id == seed.task_id)
        ).all())
        assert task.task_version == 2
        assert node.assignment_status == "accepted"
        assert len({row.dedupe_key for row in rules}) == len(rules)
        assert {row.reminder_type for row in rules} <= {"node_start", "due_soon", "node_due"}


def test_concurrent_accept_reject_finishes_in_one_coherent_state(session_factory, seed: Seed) -> None:
    barrier = threading.Barrier(2)

    def accept_once():
        barrier.wait(timeout=3)
        try:
            _service(session_factory).accept_node_assignment(
                seed.task_id, seed.node_id, seed.collaborator, 1, "postgresql-gate"
            )
            return "accepted"
        except (TaskVersionConflictError, InvalidStateTransitionError):
            return "lost"

    def reject_once():
        barrier.wait(timeout=3)
        try:
            _service(session_factory).reject_node_assignment(
                seed.task_id,
                seed.node_id,
                seed.collaborator,
                1,
                "postgresql-gate",
                "cannot take this node",
            )
            return "rejected"
        except (TaskVersionConflictError, InvalidStateTransitionError):
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(accept_once), pool.submit(reject_once)]
        outcomes = [item.result(timeout=8) for item in results]
    assert outcomes.count("lost") == 1
    assert sum(item in {"accepted", "rejected"} for item in outcomes) == 1
    with session_factory() as session:
        node = session.get(TaskNode, seed.node_id)
        task = session.get(Task, seed.task_id)
        assert task.task_version == 2
        if node.assignment_status == "accepted":
            assert node.assignment_reject_reason is None
        else:
            assert node.assignment_status == "rejected"
            assert node.assignment_reject_reason == "cannot take this node"


def test_notification_unique_constraint_wins_concurrent_insert(session_factory, seed: Seed) -> None:
    barrier = threading.Barrier(2)
    dedupe = f"pg13:{seed.node_id}:same-occurrence"

    def insert_once() -> str:
        with session_factory() as session:
            session.add(
                Notification(
                    task_id=seed.task_id,
                    recipient_employee_no=seed.collaborator,
                    channel="in_app",
                    title="PG gate",
                    content="dedupe race",
                    send_status="pending",
                    retry_count=0,
                    dedupe_key=dedupe,
                    created_at=NOW,
                )
            )
            barrier.wait(timeout=3)
            try:
                session.commit()
                return "committed"
            except IntegrityError:
                session.rollback()
                return "integrity"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: insert_once(), range(2)))
    assert sorted(results) == ["committed", "integrity"]
    with session_factory() as session:
        rows = list(session.scalars(
            select(Notification).where(Notification.dedupe_key == dedupe)
        ).all())
        assert len(rows) == 1


class _BarrierProvider:
    def __init__(self) -> None:
        self.barrier = threading.Barrier(2)
        self._lock = threading.Lock()
        self.send_count = 0

    def send(self, recipient_employee_no: str, title: str, content: str) -> str:
        with self._lock:
            self.send_count += 1
            count = self.send_count
        self.barrier.wait(timeout=3)
        return f"pg13-message-{count}"


def test_concurrent_outbox_workers_must_not_double_send(session_factory, seed: Seed) -> None:
    with session_factory() as session:
        session.add(
            Notification(
                task_id=seed.task_id,
                recipient_employee_no=seed.collaborator,
                channel="in_app",
                title="Concurrent delivery",
                content="must be sent once",
                send_status="pending",
                retry_count=0,
                dedupe_key=f"pg13:{seed.node_id}:outbox",
                created_at=NOW,
            )
        )
        session.commit()

    provider = _BarrierProvider()
    start = threading.Barrier(2)

    def send_once():
        with session_factory() as session:
            start.wait(timeout=3)
            service = ReminderNotificationService(session, provider=provider, clock=lambda: NOW)
            return service.send_pending(seed.admin, limit=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send_once), pool.submit(send_once)]
        [future.result(timeout=8) for future in futures]

    # This assertion deliberately catches an outbox race: selecting without row locking
    # allows two PostgreSQL workers to call the external provider for the same row.
    assert provider.send_count == 1
    with session_factory() as session:
        row = session.scalar(select(Notification).where(
            Notification.dedupe_key == f"pg13:{seed.node_id}:outbox"
        ))
        assert row.send_status == "sent"
