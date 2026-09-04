from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
import os
import secrets
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, delete, Engine, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api import dependencies
from app.core.config import get_settings, Settings
from app.db.unit_of_work import UnitOfWork
from app.main import app
from app.models import (
    AIExtractionRecord,
    Department,
    Notification,
    OperationLog,
    ReminderRule,
    Task,
    TaskArchive,
    TaskCompletionReview,
    TaskDecompositionRecord,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskStatusLog,
    User,
)
from tests.integration.v11_postgresql_helpers import complete_v11_decomposition

pytestmark = pytest.mark.postgresql

EXPECTED_DATABASE = "smarttaskboard_core_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 46479
EXPECTED_REVISION = "c2d3e4f5a6b7"
EXPECTED_TABLES = {
    "ai_extraction_records",
    "auth_refresh_tokens",
    "departments",
    "employee_profiles",
    "notifications",
    "operation_logs",
    "performance_metrics",
    "reminder_rules",
    "system_parameters",
    "task_archives",
    "task_conflicts",
    "task_decomposition_records",
    "task_inputs",
    "task_node_dependencies",
    "task_node_participants",
    "task_nodes",
    "task_participants",
    "task_completion_reviews",
    "task_change_requests",
    "task_progress_reports",
    "task_issues",
    "task_status_logs",
    "tasks",
    "task_performance_matches",
    "task_priority_scores",
    "user_authorized_scopes",
    "users",
    "workload_snapshots",
}
FORBIDDEN_RESPONSE_KEYS = {
    "database_url",
    "password",
    "password_hash",
    "secret",
    "session",
    "sqlalchemy_instance_state",
}
UNIMPLEMENTED_ACTIONS = {
    "retry_node",
}


@dataclass(frozen=True)
class Batch1References:
    department_id: UUID
    creator: str
    assignee: str
    reviewer: str
    node_participant: str
    outsider: str

    @property
    def employee_nos(self) -> tuple[str, ...]:
        return (
            self.creator,
            self.assignee,
            self.reviewer,
            self.node_participant,
            self.outsider,
        )


def _employee_no(label: str) -> str:
    return f"B1-{label}-{uuid4().hex[:12]}"


def _references() -> Batch1References:
    return Batch1References(
        department_id=uuid4(),
        creator=_employee_no("creator"),
        assignee=_employee_no("assignee"),
        reviewer=_employee_no("reviewer"),
        node_participant=_employee_no("node-participant"),
        outsider=_employee_no("outsider"),
    )


def _assert_safe_response(payload: object) -> None:
    if isinstance(payload, dict):
        assert not (set(payload) & FORBIDDEN_RESPONSE_KEYS)
        for value in payload.values():
            _assert_safe_response(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_safe_response(value)


def _assert_safe_error(response) -> None:
    assert set(response.json()) == {"error"}
    assert set(response.json()["error"]) == {"code", "message", "details"}
    lowered = response.text.casefold()
    for forbidden in (
        "database_url",
        "postgresql+psycopg",
        "sqlalchemy",
        "traceback",
        "password",
    ):
        assert forbidden not in lowered


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, employee_no: str) -> str:
    response = client.post(
        "/api/v1/auth/prototype-login",
        json={"employee_no": employee_no},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] > 0
    assert payload["user"]["employee_no"] == employee_no
    assert isinstance(payload["access_token"], str) and payload["access_token"]
    return payload["access_token"]


def _task_payload(
    refs: Batch1References,
    *,
    task_name: str,
    is_urgent: bool,
    deadline: datetime,
    with_dependency: bool,
) -> dict[str, object]:
    """Build a V1.1 task-level creator payload; AI owns nodes after acceptance."""
    return {
        "task_name": task_name,
        "task_description": f"{task_name} PostgreSQL task-board workflow",
        "task_goal": "Verify task board filtering and lifecycle behavior",
        "task_source": "postgresql-integration",
        "main_assignee_employee_no": refs.assignee,
        "report_to_employee_no": refs.reviewer,
        "report_to_level": "manager",
        "reviewer_employee_no": refs.reviewer,
        "department_id": str(refs.department_id),
        "start_time": (deadline - timedelta(days=1)).isoformat(),
        "deadline": deadline.isoformat(),
        "task_weight": 3,
        "deliverable": f"{task_name} deliverable",
        "acceptance_criteria": "All active AI-generated nodes accepted",
        "is_urgent": is_urgent,
        "participants": [
            {
                "employee_no": refs.node_participant,
                "participant_role": "collaborator",
            }
        ],
    }

def _post_action(
    client: TestClient,
    token: str,
    task_id: UUID,
    action: str,
    expected_task_version: int,
    **payload: object,
):
    body = {"expected_task_version": expected_task_version, **payload}
    return client.post(
        f"/api/v1/tasks/{task_id}/actions/{action}",
        headers=_bearer(token),
        json=body,
    )


def _create_task(
    client: TestClient,
    token: str,
    payload: dict[str, object],
) -> tuple[UUID, dict[str, object]]:
    response = client.post(
        "/api/v1/tasks",
        headers=_bearer(token),
        json=payload,
    )
    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["task_version"]) == ("draft", 1)
    return UUID(body["task_id"]), body


def _seed_references(
    factory: sessionmaker[Session],
    refs: Batch1References,
) -> None:
    names = {
        refs.creator: "Batch 1 Creator",
        refs.assignee: "Batch 1 Assignee",
        refs.reviewer: "Batch 1 Reviewer",
        refs.node_participant: "Batch 1 Node Collaborator",
        refs.outsider: "Batch 1 Outsider",
    }
    with factory.begin() as session:
        session.add(
            Department(
                department_id=refs.department_id,
                department_name="Batch 1 PostgreSQL API Integration",
                department_type="team",
                department_path=f"/{refs.department_id}",
                status="active",
            )
        )
        session.add_all(
            [
                User(
                    employee_no=employee_no,
                    name=name,
                    department_id=refs.department_id,
                    role_type="employee",
                    status="active",
                )
                for employee_no, name in names.items()
            ]
        )


def _cleanup_and_count(
    engine: Engine,
    refs: Batch1References,
    task_ids: set[UUID],
) -> int:
    with engine.begin() as connection:
        if task_ids:
            connection.execute(
                delete(OperationLog).where(
                    OperationLog.operator_employee_no.in_(refs.employee_nos)
                )
            )
            connection.execute(
                delete(Notification).where(Notification.task_id.in_(task_ids))
            )
            connection.execute(
                delete(ReminderRule).where(ReminderRule.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskStatusLog).where(TaskStatusLog.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskCompletionReview).where(
                    TaskCompletionReview.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskNodeDependency).where(
                    TaskNodeDependency.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskNodeParticipant).where(
                    TaskNodeParticipant.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskParticipant).where(TaskParticipant.task_id.in_(task_ids))
            )
            connection.execute(
                delete(AIExtractionRecord).where(
                    AIExtractionRecord.task_id.in_(task_ids)
                )
            )
            connection.execute(delete(TaskNode).where(TaskNode.task_id.in_(task_ids)))
            connection.execute(
                update(Task)
                .where(Task.task_id.in_(task_ids))
                .values(latest_decomposition_id=None)
            )
            connection.execute(
                delete(TaskDecompositionRecord).where(
                    TaskDecompositionRecord.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskArchive).where(TaskArchive.task_id.in_(task_ids))
            )
            connection.execute(delete(Task).where(Task.task_id.in_(task_ids)))
        connection.execute(
            delete(User).where(User.employee_no.in_(refs.employee_nos))
        )
        connection.execute(
            delete(Department).where(Department.department_id == refs.department_id)
        )

    selectors = (
        select(func.count()).select_from(TaskStatusLog).where(
            TaskStatusLog.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(TaskCompletionReview).where(
            TaskCompletionReview.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(TaskNodeDependency).where(
            TaskNodeDependency.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(TaskNodeParticipant).where(
            TaskNodeParticipant.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(TaskParticipant).where(
            TaskParticipant.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(AIExtractionRecord).where(
            AIExtractionRecord.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(TaskNode).where(TaskNode.task_id.in_(task_ids)),
        select(func.count()).select_from(TaskDecompositionRecord).where(
            TaskDecompositionRecord.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(ReminderRule).where(
            ReminderRule.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(Notification).where(
            Notification.task_id.in_(task_ids)
        ),
        select(func.count()).select_from(Task).where(Task.task_id.in_(task_ids)),
        select(func.count()).select_from(User).where(
            User.employee_no.in_(refs.employee_nos)
        ),
        select(func.count()).select_from(Department).where(
            Department.department_id == refs.department_id
        ),
    )
    with engine.connect() as connection:
        return sum(connection.execute(statement).scalar_one() for statement in selectors)


def test_batch1_real_bearer_task_board_workflow_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
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
        pytest.fail("Batch 1 target is not the approved isolated database")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=1000"},
    )
    task_ids: set[UUID] = set()
    refs = _references()
    try:
        assert set(inspect(engine).get_table_names(schema="public")) - {
            "alembic_version"
        } == EXPECTED_TABLES
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all()
        assert revisions == [EXPECTED_REVISION]

        factory = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )
        _seed_references(factory, refs)
        settings = Settings(
            app_env="test",
            database_url=database_url,
            auth_mode="prototype",
            prototype_auth_enabled=True,
            prototype_user_employee_nos=",".join(refs.employee_nos),
            jwt_secret_key=secrets.token_urlsafe(48),
            jwt_issuer="smart-task-board-batch1-test",
            jwt_audience="smart-task-board-batch1-client",
            allow_test_employee_header=False,
        )

        def override_uow_factory():
            return lambda: UnitOfWork(factory)

        def override_get_db() -> Iterator[Session]:
            session = factory()
            try:
                yield session
            finally:
                session.close()

        monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
        app.dependency_overrides[dependencies.get_uow_factory] = override_uow_factory
        app.dependency_overrides[dependencies.get_db] = override_get_db
        app.dependency_overrides[get_settings] = lambda: settings

        with TestClient(app, raise_server_exceptions=False) as client:
            prototype_users = client.get("/api/v1/auth/prototype-users")
            assert prototype_users.status_code == 200
            assert [item["employee_no"] for item in prototype_users.json()] == list(
                refs.employee_nos
            )
            assert all(
                set(item)
                == {
                    "employee_no",
                    "name",
                    "department_id",
                    "department_name",
                    "role_type",
                }
                for item in prototype_users.json()
            )

            creator_token = _login(client, refs.creator)
            assignee_token = _login(client, refs.assignee)
            reviewer_token = _login(client, refs.reviewer)
            node_participant_token = _login(client, refs.node_participant)
            outsider_token = _login(client, refs.outsider)
            tokens = (
                creator_token,
                assignee_token,
                reviewer_token,
                node_participant_token,
                outsider_token,
            )

            me = client.get("/api/v1/me", headers=_bearer(creator_token))
            assert me.status_code == 200
            me_payload = me.json()
            assert me_payload["employee_no"] == refs.creator
            assert me_payload["name"] == "Batch 1 Creator"
            assert me_payload["department"] == {
                "department_id": str(refs.department_id),
                "department_name": "Batch 1 PostgreSQL API Integration",
            }
            assert me_payload["role_type"] == "employee"
            assert me_payload["roles"] == ["employee"]
            assert me_payload["auth_mode"] == "prototype"
            assert set(me_payload["permissions"]) == {
                "can_access_executive",
                "can_manage_permissions",
                "can_view_all_tasks",
                "can_view_all_demo_data",
                "allowed_routes",
                "capabilities",
            }
            assert isinstance(me_payload["scopes"], list)
            _assert_safe_response(me_payload)

            missing_bearer = client.get("/api/v1/me")
            header_fallback = client.get(
                "/api/v1/me", headers={"X-Employee-No": refs.creator}
            )
            tampered_bearer = client.get(
                "/api/v1/me",
                headers=_bearer(f"{creator_token}tampered"),
            )
            for response in (missing_bearer, header_fallback, tampered_bearer):
                assert response.status_code == 401
                assert response.json()["error"]["code"] == "authentication_required"
                _assert_safe_error(response)

            now = datetime.now(UTC)
            alpha_payload = _task_payload(
                refs,
                task_name="Batch 1 API Workflow Alpha",
                is_urgent=False,
                deadline=now + timedelta(days=5),
                with_dependency=True,
            )
            beta_payload = _task_payload(
                refs,
                task_name="Batch 1 Urgent Draft Beta",
                is_urgent=True,
                deadline=now + timedelta(days=2),
                with_dependency=False,
            )
            alpha_id, _ = _create_task(client, creator_token, alpha_payload)
            task_ids.add(alpha_id)
            beta_id, _ = _create_task(client, creator_token, beta_payload)
            task_ids.add(beta_id)

            creator_page = client.get(
                "/api/v1/tasks",
                headers=_bearer(creator_token),
                params={"relation": "created", "limit": 1, "offset": 0},
            )
            assert creator_page.status_code == 200
            assert creator_page.json()["total"] == 2
            assert creator_page.json()["limit"] == 1
            assert [item["task_id"] for item in creator_page.json()["items"]] == [
                str(beta_id)
            ]
            assert creator_page.json()["items"][0]["allowed_actions"] == [
                "submit_for_confirmation",
                "cancel_task",
                "merge_task",
            ]
            _assert_safe_response(creator_page.json())

            filtered = client.get(
                "/api/v1/tasks",
                headers=_bearer(creator_token),
                params={"relation": "created", "search": "Workflow Alpha"},
            )
            assigned = client.get(
                "/api/v1/tasks",
                headers=_bearer(assignee_token),
                params={"relation": "assigned"},
            )
            outsider_tasks = client.get(
                "/api/v1/tasks", headers=_bearer(outsider_token)
            )
            assert filtered.status_code == assigned.status_code == 200
            assert filtered.json()["total"] == 1
            assert filtered.json()["items"][0]["task_id"] == str(alpha_id)
            assert assigned.json()["total"] == 2
            assert outsider_tasks.status_code == 200
            assert outsider_tasks.json()["total"] == 0
            assert outsider_tasks.json()["items"] == []

            outsider_detail = client.get(
                f"/api/v1/tasks/{alpha_id}", headers=_bearer(outsider_token)
            )
            outsider_actions = client.get(
                f"/api/v1/tasks/{alpha_id}/available-actions",
                headers=_bearer(outsider_token),
            )
            assert outsider_detail.status_code == outsider_actions.status_code == 403
            _assert_safe_error(outsider_detail)
            _assert_safe_error(outsider_actions)

            creator_dashboard = client.get(
                "/api/v1/dashboard/summary", headers=_bearer(creator_token)
            )
            empty_dashboard = client.get(
                "/api/v1/dashboard/summary", headers=_bearer(outsider_token)
            )
            assert creator_dashboard.status_code == empty_dashboard.status_code == 200
            assert creator_dashboard.json()["created_task_count"] == 2
            assert creator_dashboard.json()["assigned_task_count"] == 0
            assert creator_dashboard.json()["due_within_7_days_count"] == 2
            assert creator_dashboard.json()["overdue_count"] == 0
            assert empty_dashboard.json() == {
                "created_task_count": 0,
                "assigned_task_count": 0,
                "inbox_count": 0,
                "in_progress_count": 0,
                "pending_acceptance_count": 0,
                "today_task_count": 0,
                "due_within_3_days_count": 0,
                "due_within_7_days_count": 0,
                "overdue_count": 0,
                "report_due_count": 0,
                "open_issue_count": 0,
                "blocked_task_count": 0,
                "completion_review_count": 0,
                "unread_notification_count": 0,
                "open_conflict_count": 0,
                "due_window_days": 7,
                "on_time_completion_rate": 0,
                "on_time_completion_count": 0,
                "completion_sample_count": 0,
                "completion_rate_period_days": 90,
                "recent_tasks": [],
                "latest_workload": None,
                "priority_items": [],
            }
            _assert_safe_response(creator_dashboard.json())

            draft_actions = client.get(
                f"/api/v1/tasks/{alpha_id}/available-actions",
                headers=_bearer(creator_token),
            )
            assert draft_actions.status_code == 200
            assert draft_actions.json()["allowed_actions"] == [
                "submit_for_confirmation",
                "cancel_task",
                "merge_task",
            ]
            assert all(
                not node["allowed_actions"] for node in draft_actions.json()["nodes"]
            )

            submitted = _post_action(
                client,
                creator_token,
                alpha_id,
                "submit-for-confirmation",
                1,
            )
            assert (submitted.status_code, submitted.json()["status"]) == (
                200,
                "pending_confirmation",
            )
            creator_inbox = client.get(
                "/api/v1/tasks/inbox",
                headers=_bearer(creator_token),
                params={"action_code": "confirm_task", "limit": 1},
            )
            outsider_inbox = client.get(
                "/api/v1/tasks/inbox", headers=_bearer(outsider_token)
            )
            assert creator_inbox.status_code == outsider_inbox.status_code == 200
            assert creator_inbox.json()["total"] == 1
            confirm_item = creator_inbox.json()["items"][0]
            assert confirm_item["task"]["task_id"] == str(alpha_id)
            assert confirm_item["task"]["task_name"] == "Batch 1 API Workflow Alpha"
            assert confirm_item["task"]["status"] == "pending_confirmation"
            assert confirm_item["expected_task_version"] == 2
            assert confirm_item["allowed_actions"] == ["confirm_and_send"]
            assert outsider_inbox.json()["total"] == 0

            sent = _post_action(
                client,
                creator_token,
                alpha_id,
                "confirm-and-send",
                2,
            )
            assert (sent.status_code, sent.json()["status"]) == (
                200,
                "pending_acceptance",
            )
            assignee_inbox = client.get(
                "/api/v1/tasks/inbox?action_code=accept_task",
                headers=_bearer(assignee_token),
            )
            assert assignee_inbox.status_code == 200
            assert assignee_inbox.json()["total"] == 1
            accept_item = assignee_inbox.json()["items"][0]
            assert accept_item["expected_task_version"] == 3
            assert accept_item["allowed_actions"] == ["accept", "return"]
            assert accept_item["endpoint"].endswith("/actions/accept")

            failed_accept = _post_action(
                client,
                assignee_token,
                alpha_id,
                "accept",
                99,
            )
            assert failed_accept.status_code == 409
            assert failed_accept.json()["error"]["code"] == "task_version_conflict"
            _assert_safe_error(failed_accept)
            with factory() as session:
                stored = session.get(Task, alpha_id)
                assert stored is not None
                assert (stored.status, stored.task_version) == (
                    "pending_acceptance",
                    3,
                )
                assert session.scalar(
                    select(func.count()).select_from(TaskStatusLog).where(
                        TaskStatusLog.task_id == alpha_id
                    )
                ) == 3

            accepted = _post_action(
                client,
                assignee_token,
                alpha_id,
                "accept",
                3,
            )
            assert (
                accepted.status_code,
                accepted.json()["status"],
                accepted.json()["task_version"],
            ) == (200, "decomposing", 4)
            alpha_nodes, active_version = complete_v11_decomposition(
                factory, alpha_id, refs.assignee, keep_active_nodes=2
            )
            assert active_version == 5
            in_progress_actions = client.get(
                f"/api/v1/tasks/{alpha_id}/available-actions",
                headers=_bearer(assignee_token),
            )
            collaborator_actions = client.get(
                f"/api/v1/tasks/{alpha_id}/available-actions",
                headers=_bearer(node_participant_token),
            )
            assert in_progress_actions.status_code == collaborator_actions.status_code == 200
            action_nodes = {
                UUID(item["node_id"]): item["allowed_actions"]
                for item in in_progress_actions.json()["nodes"]
            }
            assert action_nodes[alpha_nodes[0]] == ["start_node"]
            assert action_nodes[alpha_nodes[1]] == []
            assert all(not action_nodes[node_id] for node_id in alpha_nodes[2:])
            assert collaborator_actions.json()["allowed_actions"] == []
            collaborator_node_actions = {
                UUID(item["node_id"]): item["allowed_actions"]
                for item in collaborator_actions.json()["nodes"]
            }
            assert all(not actions for actions in collaborator_node_actions.values())

            node1_started = client.post(
                f"/api/v1/tasks/{alpha_id}/nodes/{alpha_nodes[0]}/actions/start",
                headers=_bearer(assignee_token),
                json={"expected_task_version": active_version},
            )
            node1_progress = client.patch(
                f"/api/v1/tasks/{alpha_id}/nodes/{alpha_nodes[0]}/progress",
                headers=_bearer(assignee_token),
                json={"expected_task_version": 6, "progress_percent": 60},
            )
            node1_completed = client.post(
                f"/api/v1/tasks/{alpha_id}/nodes/{alpha_nodes[0]}/actions/complete",
                headers=_bearer(assignee_token),
                json={"expected_task_version": 7},
            )
            node2_started = client.post(
                f"/api/v1/tasks/{alpha_id}/nodes/{alpha_nodes[1]}/actions/start",
                headers=_bearer(assignee_token),
                json={"expected_task_version": 8},
            )
            node2_completed = client.post(
                f"/api/v1/tasks/{alpha_id}/nodes/{alpha_nodes[1]}/actions/complete",
                headers=_bearer(assignee_token),
                json={"expected_task_version": 9},
            )
            node_responses = (
                node1_started,
                node1_progress,
                node1_completed,
                node2_started,
                node2_completed,
            )
            assert [response.status_code for response in node_responses] == [200] * 5
            assert [response.json()["task_version"] for response in node_responses] == [
                6,
                7,
                8,
                9,
                10,
            ]

            completion_inbox = client.get(
                "/api/v1/tasks/inbox?action_code=submit_completion",
                headers=_bearer(assignee_token),
            )
            assert completion_inbox.status_code == 200
            assert completion_inbox.json()["total"] == 1
            assert completion_inbox.json()["items"][0]["allowed_actions"] == [
                "submit_completion"
            ]
            completion = _post_action(
                client,
                assignee_token,
                alpha_id,
                "submit-completion",
                10,
                completion_note="All workflow steps completed",
                deliverable_summary="The final API deliverable is ready",
            )
            assert (completion.status_code, completion.json()["status"]) == (
                200,
                "pending_review",
            )
            completion_review_id = completion.json()["review"][
                "completion_review_id"
            ]
            assert completion.json()["review"] | {
                "submitted_at": None,
            } == {
                "completion_review_id": completion_review_id,
                "task_id": str(alpha_id),
                "review_round": 1,
                "submitted_by_employee_no": refs.assignee,
                "completion_note": "All workflow steps completed",
                "deliverable_summary": "The final API deliverable is ready",
                "reviewer_employee_no": refs.reviewer,
                "review_status": "submitted",
                "review_result": None,
                "reject_reason": None,
                "rework_node_id": None,
                "submitted_task_version": 11,
                "reviewed_task_version": None,
                "submitted_at": None,
                "reviewed_at": None,
                "is_legacy_import": False,
            }

            review_inbox = client.get(
                "/api/v1/tasks/inbox?action_code=approve_completion",
                headers=_bearer(reviewer_token),
            )
            review_actions = client.get(
                f"/api/v1/tasks/{alpha_id}/available-actions",
                headers=_bearer(reviewer_token),
            )
            assert review_inbox.status_code == review_actions.status_code == 200
            assert review_inbox.json()["total"] == 1
            assert len(review_inbox.json()["items"]) == 1
            assert review_inbox.json()["items"][0]["inbox_item_type"] == (
                "approve_completion"
            )
            assert review_inbox.json()["items"][0]["allowed_actions"] == [
                "approve_completion",
                "reject_completion",
            ]
            assert review_actions.json()["allowed_actions"] == [
                "approve_completion",
                "reject_completion",
            ]
            approved = _post_action(
                client,
                reviewer_token,
                alpha_id,
                "approve-completion",
                11,
                completion_review_id=completion_review_id,
            )
            assert (
                approved.status_code,
                approved.json()["status"],
                approved.json()["task_version"],
            ) == (200, "archived", 13)

            expected_archived_actions = {
                creator_token: ["restore_task"],
                assignee_token: [],
                reviewer_token: [],
            }
            for token, expected_actions in expected_archived_actions.items():
                completed_actions = client.get(
                    f"/api/v1/tasks/{alpha_id}/available-actions",
                    headers=_bearer(token),
                )
                assert completed_actions.status_code == 200
                assert completed_actions.json()["allowed_actions"] == expected_actions
                assert all(
                    not item["allowed_actions"]
                    for item in completed_actions.json()["nodes"]
                )
                serialized_actions = completed_actions.text.casefold()
                assert not (UNIMPLEMENTED_ACTIONS & set(serialized_actions.split('"')))

            final_creator_dashboard = client.get(
                "/api/v1/dashboard/summary", headers=_bearer(creator_token)
            )
            final_assignee_dashboard = client.get(
                "/api/v1/dashboard/summary", headers=_bearer(assignee_token)
            )
            assert final_creator_dashboard.status_code == 200
            assert final_assignee_dashboard.status_code == 200
            assert final_creator_dashboard.json()["created_task_count"] == 2
            assert final_creator_dashboard.json()["due_within_7_days_count"] == 1
            assert final_assignee_dashboard.json()["assigned_task_count"] == 2
            assert final_assignee_dashboard.json()["in_progress_count"] == 0
            assert final_assignee_dashboard.json()["due_within_7_days_count"] == 1
            assert all(
                value >= 0
                for key, value in final_creator_dashboard.json().items()
                if key.endswith("_count")
            )

            final_detail = client.get(
                f"/api/v1/tasks/{alpha_id}", headers=_bearer(creator_token)
            )
            assert final_detail.status_code == 200
            assert (final_detail.json()["status"], final_detail.json()["task_version"]) == (
                "archived",
                13,
            )
            _assert_safe_response(final_detail.json())
            with factory() as session:
                assert session.scalar(
                    select(func.count()).select_from(TaskStatusLog).where(
                        TaskStatusLog.task_id == alpha_id
                    )
                ) == 13
                beta = session.get(Task, beta_id)
                assert beta is not None
                assert (beta.status, beta.task_version) == ("draft", 1)
                assert session.scalar(
                    select(func.count()).select_from(TaskStatusLog).where(
                        TaskStatusLog.task_id == beta_id
                    )
                ) == 1

            for token in tokens:
                assert token not in caplog.text
    finally:
        app.dependency_overrides.clear()
        residual_count = _cleanup_and_count(engine, refs, task_ids)
        engine.dispose()
        assert residual_count == 0, f"Batch1TestResidualCount={residual_count}"
