from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, delete, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.unit_of_work import UnitOfWork
from app.models import (
    AIExtractionRecord,
    Department,
    EmployeeProfile,
    Notification,
    OperationLog,
    PerformanceMetric,
    ReminderRule,
    SystemParameter,
    Task,
    TaskArchive,
    TaskChangeRequest,
    TaskCompletionReview,
    TaskConflict,
    TaskDecompositionRecord,
    TaskInput,
    TaskIssue,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskPerformanceMatch,
    TaskPriorityScore,
    TaskProgressReport,
    TaskStatusLog,
    User,
    UserAuthorizedScope,
    WorkloadSnapshot,
)
from app.services.business_capabilities import (
    ArchiveReuseService,
    PerformanceMetricService,
    PermissionScopeService,
    PlanningAnalyticsService,
    ReminderNotificationService,
    SystemParameterService,
    TaskIntakeService,
)
from app.services.task_workflow import TaskWorkflowService
from tests.integration.v11_postgresql_helpers import send_accept_and_decompose_v11

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
    "task_change_requests",
    "task_completion_reviews",
    "task_conflicts",
    "task_decomposition_records",
    "task_inputs",
    "task_issues",
    "task_node_dependencies",
    "task_node_participants",
    "task_nodes",
    "task_participants",
    "task_performance_matches",
    "task_priority_scores",
    "task_progress_reports",
    "task_status_logs",
    "tasks",
    "user_authorized_scopes",
    "users",
    "workload_snapshots",
}


@dataclass
class CreatedRecords:
    department_ids: set[UUID] = field(default_factory=set)
    employee_nos: set[str] = field(default_factory=set)
    input_ids: set[UUID] = field(default_factory=set)
    extraction_ids: set[UUID] = field(default_factory=set)
    task_ids: set[UUID] = field(default_factory=set)
    metric_ids: set[UUID] = field(default_factory=set)
    match_ids: set[UUID] = field(default_factory=set)
    workload_ids: set[UUID] = field(default_factory=set)
    priority_ids: set[UUID] = field(default_factory=set)
    conflict_ids: set[UUID] = field(default_factory=set)
    reminder_ids: set[UUID] = field(default_factory=set)
    notification_ids: set[UUID] = field(default_factory=set)
    archive_ids: set[UUID] = field(default_factory=set)
    authorized_scope_ids: set[UUID] = field(default_factory=set)
    parameter_keys: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class References:
    department_id: UUID
    admin: str
    creator: str
    assignee: str
    reviewer: str
    scoped_user: str


class StepClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        result = self.current
        self.current += timedelta(seconds=1)
        return result


@pytest.fixture(scope="session")
def business_engine() -> Iterator[Engine]:
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
        pytest.fail("PostgreSQL integration target is not the approved isolated database")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 2,
            "options": "-c statement_timeout=5000 -c lock_timeout=1000",
        },
    )
    try:
        database_tables = set(inspect(engine).get_table_names(schema="public"))
        assert database_tables - {"alembic_version"} == EXPECTED_TABLES
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all()
        assert revisions == [EXPECTED_REVISION]
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def business_session_factory(business_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=business_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def records(business_engine: Engine) -> Iterator[CreatedRecords]:
    created = CreatedRecords()
    yield created
    with business_engine.begin() as connection:
        task_ids = created.task_ids
        if task_ids:
            # Test cleanup follows the task graph, not only explicitly captured IDs.
            # Business services can create reminders/issues/decomposition records
            # implicitly, so ID-only cleanup is not sufficient for isolation.
            connection.execute(delete(Notification).where(Notification.task_id.in_(task_ids)))
            connection.execute(delete(ReminderRule).where(ReminderRule.task_id.in_(task_ids)))
            connection.execute(delete(TaskIssue).where(TaskIssue.task_id.in_(task_ids)))
            connection.execute(delete(TaskConflict).where(TaskConflict.task_id.in_(task_ids)))
            connection.execute(
                delete(TaskCompletionReview).where(TaskCompletionReview.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskChangeRequest).where(TaskChangeRequest.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskPerformanceMatch).where(TaskPerformanceMatch.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskPriorityScore).where(TaskPriorityScore.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskProgressReport).where(TaskProgressReport.task_id.in_(task_ids))
            )
            connection.execute(delete(TaskArchive).where(TaskArchive.task_id.in_(task_ids)))
            connection.execute(delete(TaskStatusLog).where(TaskStatusLog.task_id.in_(task_ids)))
            connection.execute(
                delete(TaskNodeDependency).where(TaskNodeDependency.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskNodeParticipant).where(TaskNodeParticipant.task_id.in_(task_ids))
            )
            connection.execute(delete(TaskParticipant).where(TaskParticipant.task_id.in_(task_ids)))
            connection.execute(
                delete(AIExtractionRecord).where(AIExtractionRecord.task_id.in_(task_ids))
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
            connection.execute(delete(Task).where(Task.task_id.in_(task_ids)))

        for model, column, values in (
            (WorkloadSnapshot, WorkloadSnapshot.workload_snapshot_id, created.workload_ids),
            (AIExtractionRecord, AIExtractionRecord.extraction_id, created.extraction_ids),
            (TaskInput, TaskInput.input_id, created.input_ids),
            (PerformanceMetric, PerformanceMetric.metric_id, created.metric_ids),
            (
                UserAuthorizedScope,
                UserAuthorizedScope.authorized_scope_id,
                created.authorized_scope_ids,
            ),
            (EmployeeProfile, EmployeeProfile.employee_no, created.employee_nos),
            (SystemParameter, SystemParameter.param_key, created.parameter_keys),
            (OperationLog, OperationLog.operator_employee_no, created.employee_nos),
            (User, User.employee_no, created.employee_nos),
            (Department, Department.department_id, created.department_ids),
        ):
            if values:
                connection.execute(delete(model).where(column.in_(values)))


def _employee_no(label: str) -> str:
    return f"BIZ-{label}-{uuid4().hex[:8]}"


def _create_references(
    session_factory: sessionmaker[Session],
    records: CreatedRecords,
) -> References:
    department_id = uuid4()
    refs = References(
        department_id=department_id,
        admin=_employee_no("admin"),
        creator=_employee_no("creator"),
        assignee=_employee_no("assignee"),
        reviewer=_employee_no("reviewer"),
        scoped_user=_employee_no("scope"),
    )
    records.department_ids.add(department_id)
    records.employee_nos.update(
        {refs.admin, refs.creator, refs.assignee, refs.reviewer, refs.scoped_user}
    )
    with session_factory() as session:
        session.add(
            Department(
                department_id=department_id,
                department_name="Business Integration",
                department_type="team",
                department_path=f"/{department_id}",
                status="active",
            )
        )
        session.add_all(
            [
                User(
                    employee_no=refs.admin,
                    name="Admin",
                    department_id=department_id,
                    role_type="admin",
                    status="active",
                ),
                User(
                    employee_no=refs.creator,
                    name="Creator",
                    department_id=department_id,
                    role_type="manager",
                    status="active",
                    manager_employee_no=refs.admin,
                ),
                User(
                    employee_no=refs.assignee,
                    name="Assignee",
                    department_id=department_id,
                    role_type="employee",
                    status="active",
                    manager_employee_no=refs.creator,
                ),
                User(
                    employee_no=refs.reviewer,
                    name="Reviewer",
                    department_id=department_id,
                    role_type="manager",
                    status="active",
                    manager_employee_no=refs.admin,
                ),
                User(
                    employee_no=refs.scoped_user,
                    name="Scoped Executive",
                    department_id=department_id,
                    role_type="executive",
                    status="active",
                ),
            ]
        )
        session.add(
            EmployeeProfile(
                employee_no=refs.assignee,
                responsibility_text="Revenue dashboard and KPI automation",
                skill_tags=["python", "kpi", "dashboard"],
                daily_capacity_hours=Decimal("1"),
                standard_task_count=1,
                standard_task_weight=1,
                emergency_tolerance_count=1,
                availability_status="available",
            )
        )
        session.commit()
    return refs


def _uow_factory(session_factory: sessionmaker[Session]):
    return lambda: UnitOfWork(session_factory)


def _current_task_version(session_factory: sessionmaker[Session], task_id: UUID) -> int:
    with session_factory() as session:
        task = session.get(Task, task_id)
        assert task is not None
        return task.task_version


def test_full_business_capability_flow_with_real_postgresql(
    business_session_factory: sessionmaker[Session],
    records: CreatedRecords,
) -> None:
    refs = _create_references(business_session_factory, records)
    clock = StepClock()
    uow_factory = _uow_factory(business_session_factory)

    with business_session_factory() as session:
        parameter = SystemParameterService(session, clock=clock).upsert_parameter(
            refs.admin,
            f"business_test_{uuid4().hex}",
            value="true",
            param_type="boolean",
            module="acceptance",
            name="Business test flag",
        )
        records.parameter_keys.add(parameter.param_key)
        scope = PermissionScopeService(session, clock=clock).grant_scope(
            refs.admin,
            employee_no=refs.scoped_user,
            scope_type="department",
            scope_id=str(refs.department_id),
            permission_type="view",
            valid_from=clock.current,
            valid_to=clock.current + timedelta(days=1),
        )
        records.authorized_scope_ids.add(scope.authorized_scope_id)
        recommendations = PermissionScopeService(session, clock=clock).recommend_assignees(
            refs.creator,
            task_description="Need python KPI dashboard owner",
            required_skill_tags=["python", "kpi"],
            department_id=refs.department_id,
            limit=3,
        )
        assert recommendations[0]["employee_no"] == refs.assignee

    with business_session_factory() as session:
        intake = TaskIntakeService(session, uow_factory, clock=clock)
        submitted = intake.submit_input(
            refs.creator,
            input_type="text",
            raw_text=(
                "Revenue dashboard\n"
                f"assignee: {refs.assignee}; report_to: {refs.reviewer}; "
                f"reviewer: {refs.reviewer}; "
                "deadline: 2026-08-22T09:00:00+00:00; weight: 5; "
                "deliverable: Revenue dashboard; acceptance: KPI is measurable"
            ),
            voice_file_url=None,
            source_channel="api",
        )
        records.input_ids.add(submitted.task_input.input_id)
        records.extraction_ids.add(submitted.extraction.extraction_id)
        clarified = intake.clarify(
            refs.creator,
            submitted.task_input.input_id,
            {"performance_metric": "Revenue dashboard KPI"},
        )
        records.extraction_ids.add(clarified.extraction.extraction_id)
        task = intake.create_draft_from_extraction(
            refs.creator,
            extraction_id=clarified.extraction.extraction_id,
            corrections={
                "department_id": str(refs.department_id),
                "task_goal": "Deliver a measurable revenue dashboard",
                "start_time": "2026-08-20T09:00:00+00:00",
            },
        )
        records.task_ids.add(task.task_id)

    workflow = TaskWorkflowService(uow_factory, clock=clock)
    _, decomposed_version = send_accept_and_decompose_v11(
        workflow,
        business_session_factory,
        task,
        refs.creator,
        refs.assignee,
        "postgresql-test",
        keep_active_nodes=2,
        clock=clock,
    )
    with business_session_factory() as session:
        task = session.get(Task, task.task_id)
        assert task is not None
        assert (task.status, task.task_version) == ("in_progress", decomposed_version)
    _, change_request = workflow.submit_change_request(
        task.task_id,
        refs.assignee,
        task.task_version,
        "postgresql-test",
        {"task_weight": 4},
        "Business priority changed",
    )
    task, change_request = workflow.approve_change_request(
        task.task_id,
        refs.creator,
        task.task_version,
        "postgresql-test",
        change_request.change_request_id,
        "Approved",
    )
    assert task.task_weight == 4
    assert change_request.status == "approved"

    with business_session_factory() as session:
        metric_service = PerformanceMetricService(session, clock=clock)
        metric = metric_service.create_metric(
            refs.admin,
            {
                "metric_type": "dashboard",
                "metric_name": "Revenue dashboard KPI",
                "definition_formula": "dashboard completion rate",
                "deliverable": "Revenue dashboard",
                "status": "active",
            },
        )
        records.metric_ids.add(metric.metric_id)
        matches = metric_service.suggest_matches(refs.creator, task.task_id)
        records.match_ids.update(match.performance_match_id for match in matches)
        confirmed_match = metric_service.confirm_match(
            refs.creator,
            task.task_id,
            matches[0].performance_match_id,
        )
        assert confirmed_match.is_confirmed is True

    with business_session_factory() as session:
        planning = PlanningAnalyticsService(session, clock=clock)
        workload = planning.calculate_workload(
            refs.admin,
            refs.assignee,
            datetime(2026, 8, 21, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 23, 0, 0, tzinfo=UTC),
        )
        records.workload_ids.add(workload.workload_snapshot_id)
        priorities = planning.calculate_priorities(refs.admin)
        records.priority_ids.update(row.priority_score_id for row in priorities)
        conflicts = planning.detect_conflicts(refs.admin, refs.assignee)
        records.conflict_ids.update(row.conflict_id for row in conflicts)
        assert workload.workload_score > 0
        assert any(row.task_id == task.task_id for row in priorities)
        assert conflicts
        acknowledged = planning.resolve_conflict(
            refs.admin,
            conflicts[0].conflict_id,
            resolution_note="Reviewed by manager",
            status="acknowledged",
        )
        assert acknowledged.status == "acknowledged"
        resolved = planning.resolve_conflict(
            refs.admin,
            conflicts[0].conflict_id,
            resolution_note="Capacity adjusted",
        )
        assert resolved.status == "resolved"
        redetected = planning.detect_conflicts(refs.admin, refs.assignee)
        records.conflict_ids.update(row.conflict_id for row in redetected)
        assert any(row.status == "open" for row in redetected)

    with business_session_factory() as session:
        notifications = ReminderNotificationService(session, clock=clock)
        rules = notifications.scan_reminders(refs.admin)
        records.reminder_ids.update(rule.reminder_rule_id for rule in rules)
        pending = notifications.create_due_notifications(refs.admin)
        records.notification_ids.update(row.notification_id for row in pending)
        assert len({row.dedupe_key for row in pending}) == len(pending)
        sent = notifications.send_pending(refs.admin)
        assert sent
        assert all(row.send_status == "sent" for row in sent)
        owned_notifications = notifications.list_notifications(refs.assignee)
        assert owned_notifications
        read = notifications.mark_read(refs.assignee, owned_notifications[0].notification_id)
        assert read.read_at is not None

    with business_session_factory() as session:
        nodes = list(session.scalars(select(TaskNode).where(TaskNode.task_id == task.task_id)))
        for node in nodes:
            node.status = "completed"
            node.progress_percent = 100
            node.completed_at = clock()
        session.commit()

    current_version = _current_task_version(business_session_factory, task.task_id)
    task, review = workflow.submit_completion(
        task.task_id,
        refs.assignee,
        current_version,
        "postgresql-test",
        "Complete",
        "Dashboard delivered",
    )
    task, review = workflow.approve_completion(
        task.task_id,
        refs.reviewer,
        task.task_version,
        "postgresql-test",
        review.completion_review_id,
    )
    assert task.status == "archived"

    with business_session_factory() as session:
        # Feature 11 automatically archives approved tasks without a reusable
        # snapshot. Exercise the legacy/manual archive-reuse capability with a
        # separate completed task so the two contracts do not overwrite each other.
        reusable_source = Task(
            task_id=uuid4(),
            task_name="Reusable revenue dashboard source",
            task_description="Reusable revenue dashboard source",
            task_goal="Preserve archive reuse capability",
            task_source="postgresql-test",
            creator_employee_no=refs.creator,
            main_assignee_employee_no=refs.assignee,
            report_to_employee_no=refs.reviewer,
            reviewer_employee_no=refs.reviewer,
            department_id=refs.department_id,
            start_time=clock.current - timedelta(days=2),
            deadline=clock.current - timedelta(days=1),
            task_weight=3,
            status="completed",
            task_version=1,
            created_at=clock.current - timedelta(days=3),
            updated_at=clock.current,
            effective_at=clock.current,
        )
        session.add(reusable_source)
        session.commit()
        records.task_ids.add(reusable_source.task_id)

        archive_service = ArchiveReuseService(session, uow_factory, clock=clock)
        archive = archive_service.archive_task(
            refs.creator,
            reusable_source.task_id,
            summary="Reusable revenue dashboard",
            search_keywords=["revenue", "dashboard"],
            review_result=review.review_result,
            risk_points=[],
        )
        records.archive_ids.add(archive.archive_id)
        search_result = archive_service.search(refs.scoped_user, keyword="revenue")
        reused = archive_service.reuse_archive(
            refs.creator,
            archive.archive_id,
            task_name="Reusable dashboard copy",
            main_assignee_employee_no=refs.assignee,
        )
        records.task_ids.add(reused.task_id)
        assert search_result["total"] >= 1
        assert reused.status == "draft"

    with business_session_factory() as session:
        operations = session.scalars(
            select(OperationLog).where(OperationLog.operator_employee_no.in_(records.employee_nos))
        ).all()
        actions = {row.action for row in operations}
        assert {
            "parameter_changed",
            "permission_scope_granted",
            "task_input_submitted",
            "performance_metric_created",
            "performance_matches_suggested",
            "kpi_match_confirmed",
            "workload_calculated",
            "priority_calculated",
            "conflicts_detected",
            "notifications_created",
            "notifications_sent",
            "archive",
            "reuse",
        } <= actions
