from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models import (
    AIExtractionRecord,
    EmployeeProfile,
    Notification,
    OperationLog,
    PerformanceMetric,
    ReminderRule,
    Task,
    TaskArchive,
    TaskConflict,
    TaskInput,
    TaskParticipant,
    TaskPerformanceMatch,
    TaskPriorityScore,
    User,
    UserAuthorizedScope,
    WorkloadSnapshot,
)
from app.services import business_capabilities as business_module
from app.services.business_capabilities import (
    ArchiveReuseService,
    FakeASRProvider,
    FakeTaskExtractionProvider,
    PerformanceMetricService,
    PermissionScopeService,
    PlanningAnalyticsService,
    ReminderNotificationService,
    SystemParameterService,
    TaskIntakeService,
)
from app.services.errors import (
    BusinessValidationError,
    PermissionDeniedError,
    TaskVersionConflictError,
)

NOW = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)


class ScalarRows:
    def __init__(self, rows: Iterable[object]) -> None:
        self._rows = list(rows)

    def all(self) -> list[object]:
        return self._rows


class ExecuteRows:
    def __init__(self, rows: Iterable[object]) -> None:
        self._rows = list(rows)

    def all(self) -> list[object]:
        return self._rows

    def scalars(self) -> ScalarRows:
        return ScalarRows(self._rows)

    def scalar_one(self) -> object:
        return self._rows[0]

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None


class RecordingSession:
    def __init__(
        self,
        *,
        objects: dict[tuple[type[object], object], object] | None = None,
        scalar_results: list[object] | None = None,
        scalars_results: list[list[object]] | None = None,
        execute_results: list[list[object]] | None = None,
    ) -> None:
        self.objects = objects or {}
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = list(scalars_results or [])
        self.execute_results = list(execute_results or [])
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    def get(self, model: type[object], key: object) -> object | None:
        return self.objects.get((model, key))

    def add(self, row: object) -> None:
        self.added.append(row)

    def flush(self) -> None:
        self.flushes += 1
        for row in self.added:
            for field in (
                "parameter_id",
                "authorized_scope_id",
                "metric_id",
                "performance_match_id",
                "workload_snapshot_id",
                "priority_score_id",
                "conflict_id",
                "reminder_rule_id",
                "notification_id",
                "archive_id",
                "operation_log_id",
            ):
                if hasattr(row, field) and getattr(row, field) is None:
                    setattr(row, field, uuid4())

    def commit(self) -> None:
        self.commits += 1

    def scalar(self, _statement) -> object | None:
        return self.scalar_results.pop(0) if self.scalar_results else None

    def scalars(self, _statement) -> ScalarRows:
        return ScalarRows(self.scalars_results.pop(0) if self.scalars_results else [])

    def execute(self, _statement) -> ExecuteRows:
        return ExecuteRows(self.execute_results.pop(0) if self.execute_results else [])


def _user(employee_no: str, *, role: str = "employee", department_id: UUID | None = None) -> User:
    return User(
        employee_no=employee_no,
        name=employee_no,
        role_type=role,
        status="active",
        department_id=department_id,
    )


def _task(
    *,
    task_id: UUID | None = None,
    creator: str = "CREATOR",
    assignee: str = "ASSIGNEE",
    status: str = "in_progress",
    deadline: datetime | None = None,
    task_weight: int = 3,
) -> Task:
    return Task(
        task_id=task_id or uuid4(),
        task_name="Revenue launch task",
        task_description="Launch revenue dashboard and KPI deliverable",
        task_goal="Improve revenue reporting",
        creator_employee_no=creator,
        main_assignee_employee_no=assignee,
        reviewer_employee_no="REVIEWER",
        report_to_level="director",
        status=status,
        deadline=deadline,
        estimated_hours=Decimal("16"),
        actual_hours=Decimal("4"),
        task_weight=task_weight,
        deliverable="Revenue dashboard",
        acceptance_criteria="KPI is measurable",
        is_urgent=deadline is not None and deadline <= NOW + timedelta(days=1),
        task_version=3,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(hours=1),
    )


def _operation_logs(session: RecordingSession) -> list[OperationLog]:
    return [row for row in session.added if isinstance(row, OperationLog)]


def test_system_parameter_upsert_validates_admin_type_and_writes_audit() -> None:
    admin = _user("ADMIN", role="admin")
    session = RecordingSession(objects={(User, "ADMIN"): admin}, scalar_results=[None])

    row = SystemParameterService(session, clock=lambda: NOW).upsert_parameter(
        "ADMIN",
        "priority_boost",
        value="25",
        param_type="number",
        module="priority",
        name="Priority boost",
    )

    assert row.param_key == "priority_boost"
    assert row.param_value == "25"
    assert row.updated_by_employee_no == "ADMIN"
    assert _operation_logs(session)[0].action == "parameter_changed"
    assert session.commits == 1


def test_permission_scope_grant_and_recommendation_are_admin_scoped() -> None:
    department_id = uuid4()
    admin = _user("ADMIN", role="admin")
    target = _user("TARGET", department_id=department_id)
    candidate = _user("CANDIDATE", department_id=department_id)
    profile = EmployeeProfile(
        employee_no="CANDIDATE",
        responsibility_text="Revenue dashboard automation",
        skill_tags=["python", "kpi"],
        availability_status="available",
        daily_capacity_hours=Decimal("8"),
        standard_task_count=5,
        standard_task_weight=3,
        emergency_tolerance_count=2,
    )
    session = RecordingSession(
        objects={(User, "ADMIN"): admin, (User, "TARGET"): target, (User, "CANDIDATE"): candidate},
        execute_results=[[(candidate, profile)]],
    )
    service = PermissionScopeService(session, clock=lambda: NOW)

    scope = service.grant_scope(
        "ADMIN",
        employee_no="TARGET",
        scope_type="department",
        scope_id=str(department_id),
        permission_type="view",
        valid_from=NOW,
        valid_to=NOW + timedelta(days=1),
    )
    recommendations = service.recommend_assignees(
        "ADMIN",
        task_description="Need python KPI dashboard",
        required_skill_tags=["kpi"],
        department_id=department_id,
        limit=3,
    )

    assert isinstance(scope, UserAuthorizedScope)
    assert scope.created_by_employee_no == "ADMIN"
    assert recommendations[0]["employee_no"] == "CANDIDATE"
    assert recommendations[0]["score"] > 0
    assert {log.action for log in _operation_logs(session)} == {"permission_scope_granted"}


def test_task_intake_voice_clarify_and_confirm_create_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = _user("CREATOR")
    assignee = _user("ASSIGNEE")
    reviewer = _user("REVIEWER")
    input_id = uuid4()
    session = RecordingSession(
        objects={
            (User, "CREATOR"): actor,
            (User, "ASSIGNEE"): assignee,
            (User, "REVIEWER"): reviewer,
            (TaskInput, input_id): None,
        }
    )
    class FailingDecompositionProvider:
        def decompose(self, _extracted):
            raise AssertionError("task creation must not trigger decomposition")

    service = TaskIntakeService(
        session,
        object,
        asr_provider=FakeASRProvider(),
        extraction_provider=FakeTaskExtractionProvider(),
        decomposition_provider=FailingDecompositionProvider(),
        clock=lambda: NOW,
    )

    result = service.submit_input(
        "CREATOR",
        input_id=input_id,
        input_type="voice",
        raw_text=None,
        voice_file_url="https://example.invalid/audio.wav",
        source_channel="wecom",
    )

    assert result.task_input.asr_text == "Transcribed voice input from https://example.invalid/audio.wav"
    assert "main_assignee_employee_no" in result.extraction.missing_fields
    assert _operation_logs(session)[0].action == "task_input_submitted"

    previous = result.extraction
    session.objects[(TaskInput, input_id)] = result.task_input
    session.scalar_results = [previous]
    clarified = service.clarify(
        "CREATOR",
        input_id,
        {
            "main_assignee_employee_no": "ASSIGNEE",
            "report_to_employee_no": "REVIEWER",
            "deadline": "2026-08-30T09:00:00+00:00",
            "estimated_hours": "8",
            "performance_metric": "Revenue dashboard KPI",
            "acceptance_criteria": "Reviewed output",
        },
    )
    assert clarified.extraction.missing_fields == []
    assert clarified.extraction.confirmed_at == NOW

    department_id = uuid4()
    captured: dict[str, object] = {}

    class CapturingWorkflow:
        def __init__(self, _uow_factory, *, clock) -> None:
            self.clock = clock

        def create_task_draft(self, command):
            captured["command"] = command
            return Task(
                task_id=command.task_id,
                task_name=command.task_name,
                creator_employee_no=command.creator_employee_no,
                main_assignee_employee_no=command.main_assignee_employee_no,
                status="draft",
                task_version=1,
                created_at=NOW,
                updated_at=NOW,
            )

    monkeypatch.setattr(business_module, "TaskWorkflowService", CapturingWorkflow)
    session.objects[(AIExtractionRecord, clarified.extraction.extraction_id)] = clarified.extraction
    session.scalar_results = []
    task = service.create_draft_from_extraction(
        "CREATOR",
        extraction_id=clarified.extraction.extraction_id,
        corrections={"task_name": "Confirmed task", "department_id": str(department_id)},
        task_id=uuid4(),
    )

    command = captured["command"]
    assert task.status == "draft"
    assert command.operation_source == "ai_intake"
    assert command.task_name == "Confirmed task"
    assert command.department_id == department_id
    assert command.nodes == ()
    assert command.dependencies == ()
    assert command.node_participants == ()
    assert command.extraction_record_ids == (clarified.extraction.extraction_id,)


def test_task_intake_accepts_browser_voice_transcript_without_persisting_audio() -> None:
    actor = _user("CREATOR")
    assignee = _user("ASSIGNEE")
    reviewer = _user("REVIEWER")
    session = RecordingSession(
        objects={
            (User, "CREATOR"): actor,
            (User, "ASSIGNEE"): assignee,
            (User, "REVIEWER"): reviewer,
        }
    )
    service = TaskIntakeService(
        session,
        object,
        extraction_provider=FakeTaskExtractionProvider(),
        clock=lambda: NOW,
    )

    result = service.submit_input(
        "CREATOR",
        input_type="voice",
        raw_text=(
            "门店上线\nassignee:ASSIGNEE\nreport_to:REVIEWER\n"
            "deadline:2026-08-30T09:00:00+00:00"
        ),
        voice_file_url=None,
        source_channel="web",
    )

    assert result.task_input.voice_file_url is None
    assert result.task_input.asr_text is not None
    assert result.extraction.extracted_json["main_assignee_employee_no"] == "ASSIGNEE"
    assert result.extraction.missing_fields == []


def test_task_intake_rejects_foreign_retry_and_reuses_owned_latest_extraction() -> None:
    input_id = uuid4()
    owner = _user("OWNER")
    other = _user("OTHER")
    task_input = TaskInput(
        input_id=input_id,
        input_type="text",
        raw_text="Existing task",
        source_channel="web",
        submitted_by_employee_no="OWNER",
        submitted_at=NOW,
    )
    extraction = AIExtractionRecord(
        extraction_id=uuid4(),
        input_id=input_id,
        extracted_json={"task_name": "Existing task"},
        missing_fields=[],
        low_confidence_fields=[],
        confirm_questions=[],
        confidence_score=Decimal("0.95"),
    )
    session = RecordingSession(
        objects={(User, "OWNER"): owner, (User, "OTHER"): other, (TaskInput, input_id): task_input},
        scalar_results=[extraction],
    )
    service = TaskIntakeService(session, object, clock=lambda: NOW)

    with pytest.raises(PermissionDeniedError, match="actor cannot retry this task input"):
        service.retry_extraction("OTHER", input_id)

    result = service.get_latest_extraction("OWNER", input_id)
    assert result.task_input is task_input
    assert result.extraction is extraction


def test_task_intake_validation_prevents_hallucinated_people_and_fuzzy_dates() -> None:
    actor = _user("CREATOR")
    session = RecordingSession(objects={(User, "CREATOR"): actor, (User, "VALID"): _user("VALID")})

    class HallucinatingProvider:
        def extract(self, _text, context=None):
            return {
                "extracted_json": {
                    "task_name": "Task",
                    "task_description": "Task",
                    "main_assignee_employee_no": "MISSING",
                    "report_to_employee_no": "VALID",
                    "reviewer_employee_no": "VALID",
                    "deadline": "下周",
                    "task_weight": 9,
                    "estimated_hours": "8",
                    "unknown_field": "ignored",
                },
                "missing_fields": [],
                "low_confidence_fields": [],
                "confirm_questions": [],
                "confidence_score": Decimal("0.4"),
            }

    service = TaskIntakeService(
        session,
        object,
        extraction_provider=HallucinatingProvider(),
        clock=lambda: NOW,
    )

    result = service.submit_input(
        "CREATOR",
        input_type="text",
        raw_text="请下周完成任务",
        voice_file_url=None,
        source_channel="web",
    )

    extracted = result.extraction.extracted_json
    assert extracted["main_assignee_employee_no"] is None
    assert extracted["deadline"] is None
    assert extracted["task_weight"] is None
    assert "estimated_hours" not in extracted
    assert "unknown_field" not in extracted
    assert {"main_assignee_employee_no", "deadline", "task_weight"} <= set(
        result.extraction.low_confidence_fields
    )


def test_task_intake_provider_failures_are_safe_retryable_errors() -> None:
    session = RecordingSession(objects={(User, "CREATOR"): _user("CREATOR")})

    class RateLimitedProvider:
        def extract(self, _text, context=None):
            raise RuntimeError("AI provider HTTP request failed with status 429")

    service = TaskIntakeService(
        session,
        object,
        extraction_provider=RateLimitedProvider(),
        clock=lambda: NOW,
    )

    with pytest.raises(BusinessValidationError, match="rate limited"):
        service.submit_input(
            "CREATOR",
            input_type="text",
            raw_text="Need a task",
            voice_file_url=None,
            source_channel="web",
        )


def test_main_assignee_suggests_task_plan_after_acceptance_and_sanitizes_owner() -> None:
    task_id = uuid4()
    task = _task(task_id=task_id, status="in_progress", deadline=NOW + timedelta(days=5))
    extraction = AIExtractionRecord(
        extraction_id=uuid4(),
        input_id=uuid4(),
        task_id=task_id,
        extracted_json={"nodes": [{"clientNodeId": "from-extraction", "nodeName": "Old node"}]},
        missing_fields=[],
        low_confidence_fields=[],
        confirm_questions=[],
        confirmed_at=NOW,
    )
    participant = TaskParticipant(
        task_id=task_id,
        employee_no="COLLAB",
        participant_role="collaborator",
        is_primary=False,
    )

    class PlanningProvider:
        def decompose(self, extracted):
            assert extracted["task_id"] == str(task_id)
            assert extracted["planning_instructions"] == "make it execution ready"
            return {
                "nodes": [
                    {
                        "clientNodeId": "draft-node-1",
                        "nodeName": "Prepare scope",
                        "actionDetail": "Confirm input scope.",
                        "ownerEmployeeNo": "OUTSIDER",
                        "plannedDeadline": (NOW + timedelta(days=1)).isoformat(),
                        "deliverable": "Scope note",
                        "acceptanceCriteria": "Scope is approved",
                    },
                    {
                        "clientNodeId": "draft-node-2",
                        "nodeName": "Deliver result",
                        "ownerEmployeeNo": "COLLAB",
                        "plannedDeadline": (NOW + timedelta(days=4)).isoformat(),
                        "dependencies": ["draft-node-1"],
                    },
                ],
                "dependencies": [
                    {
                        "predecessorClientNodeId": "draft-node-1",
                        "successorClientNodeId": "draft-node-2",
                        "dependencyType": "finish_to_start",
                    }
                ],
            }

    session = RecordingSession(
        objects={
            (Task, task_id): task,
            (User, "ASSIGNEE"): _user("ASSIGNEE"),
            (User, "OUTSIDER"): _user("OUTSIDER"),
        },
        scalar_results=[extraction],
        scalars_results=[[participant], [participant]],
    )
    service = TaskIntakeService(
        session,
        object,
        decomposition_provider=PlanningProvider(),
        clock=lambda: NOW,
    )

    with pytest.raises(PermissionDeniedError):
        service.suggest_task_plan("CREATOR", task_id)

    response = service.suggest_task_plan(
        "ASSIGNEE",
        task_id,
        instructions=" make it execution ready ",
    )

    assert response["task_id"] == task_id
    assert len(response["suggested_nodes"]) == 2
    assert response["suggested_nodes"][0]["suggested_owner_employee_no"] is None
    assert response["suggested_nodes"][1]["suggested_owner_employee_no"] == "COLLAB"
    assert response["suggested_dependencies"] == [
        {
            "predecessor_client_node_id": "draft-node-1",
            "successor_client_node_id": "draft-node-2",
            "dependency_type": "finish_to_start",
            "reason": None,
        }
    ]


def test_performance_metric_suggestion_and_confirmation_are_explainable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task()
    metric = PerformanceMetric(
        metric_id=uuid4(),
        metric_type="revenue dashboard",
        metric_name="Revenue dashboard KPI",
        business_unit="sales",
        definition_formula="dashboard completion rate",
        deliverable="Revenue dashboard",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    session = RecordingSession(
        objects={(User, "MANAGER"): _user("MANAGER", role="manager"), (Task, task.task_id): task, (PerformanceMetric, metric.metric_id): metric},
        scalar_results=[None],
        scalars_results=[[metric]],
    )
    monkeypatch.setattr(
        business_module.PermissionScopeService,
        "assert_can_view_task",
        lambda _self, _actor, _task_id: task,
    )

    service = PerformanceMetricService(session, clock=lambda: NOW)
    created = service.create_metric(
        "MANAGER",
        {
            "metric_type": "quality",
            "metric_name": "Release quality",
            "status": "active",
        },
    )
    matches = service.suggest_matches(task.creator_employee_no, task.task_id, limit=1)
    match = matches[0]
    session.objects[(TaskPerformanceMatch, match.performance_match_id)] = match
    confirmed = service.confirm_match(task.creator_employee_no, task.task_id, match.performance_match_id)

    assert created.metric_name == "Release quality"
    assert "指标名称" in match.match_reason
    assert match.algorithm_version == "tfidf-char-ngram-v1"
    assert confirmed.is_confirmed is True
    assert confirmed.confirmed_by_employee_no == task.creator_employee_no
    expected_actions = {
        "performance_metric_created",
        "performance_matches_suggested",
        "kpi_match_confirmed",
    }
    assert expected_actions <= {log.action for log in _operation_logs(session)}


def test_performance_match_management_is_creator_only_and_versioned() -> None:
    task = _task()
    service = PerformanceMetricService(
        RecordingSession(scalar_results=[task]), clock=lambda: NOW
    )
    with pytest.raises(PermissionDeniedError):
        service.suggest_matches("OUTSIDER", task.task_id, expected_task_version=task.task_version)

    service = PerformanceMetricService(
        RecordingSession(scalar_results=[task]), clock=lambda: NOW
    )
    with pytest.raises(TaskVersionConflictError):
        service.suggest_matches(
            task.creator_employee_no, task.task_id,
            expected_task_version=task.task_version + 1,
        )


def test_performance_confirmation_keeps_only_one_confirmed_relation() -> None:
    task = _task()
    first_metric = PerformanceMetric(
        metric_id=uuid4(), metric_type="sales", metric_name="Revenue",
        status="active", created_at=NOW, updated_at=NOW,
    )
    second_metric = PerformanceMetric(
        metric_id=uuid4(), metric_type="sales", metric_name="Margin",
        status="active", created_at=NOW, updated_at=NOW,
    )
    first = TaskPerformanceMatch(
        performance_match_id=uuid4(), task_id=task.task_id, metric_id=first_metric.metric_id,
        type_score=100, business_unit_score=100, metric_name_score=80,
        definition_formula_score=80, deliverable_score=0, total_score=85,
        match_level="strong", is_confirmed=True,
        confirmed_by_employee_no=task.creator_employee_no, confirmed_at=NOW,
        algorithm_version="tfidf-char-ngram-v1", created_at=NOW, updated_at=NOW,
    )
    second = TaskPerformanceMatch(
        performance_match_id=uuid4(), task_id=task.task_id, metric_id=second_metric.metric_id,
        type_score=90, business_unit_score=100, metric_name_score=70,
        definition_formula_score=70, deliverable_score=0, total_score=78,
        match_level="weak", is_confirmed=False,
        algorithm_version="tfidf-char-ngram-v1", created_at=NOW, updated_at=NOW,
    )
    session = RecordingSession(
        objects={
            (Task, task.task_id): task,
            (TaskPerformanceMatch, second.performance_match_id): second,
            (PerformanceMetric, second_metric.metric_id): second_metric,
        },
        scalar_results=[task],
        scalars_results=[[first]],
    )
    result = PerformanceMetricService(session, clock=lambda: NOW).confirm_match(
        task.creator_employee_no, task.task_id, second.performance_match_id,
        expected_task_version=task.task_version,
    )
    assert result.is_confirmed is True
    assert first.is_confirmed is False
    assert first.confirmed_by_employee_no is None
    assert first.confirmed_at is None


def test_clear_performance_confirmation_persists_no_relation_choice() -> None:
    task = _task()
    metric = PerformanceMetric(
        metric_id=uuid4(), metric_type="sales", metric_name="Revenue",
        status="active", created_at=NOW, updated_at=NOW,
    )
    match = TaskPerformanceMatch(
        performance_match_id=uuid4(), task_id=task.task_id, metric_id=metric.metric_id,
        type_score=100, business_unit_score=100, metric_name_score=100,
        definition_formula_score=100, deliverable_score=100, total_score=100,
        match_level="strong", is_confirmed=True,
        confirmed_by_employee_no=task.creator_employee_no, confirmed_at=NOW,
        algorithm_version="tfidf-char-ngram-v1", created_at=NOW, updated_at=NOW,
    )
    session = RecordingSession(
        objects={(Task, task.task_id): task, (PerformanceMetric, metric.metric_id): metric},
        scalar_results=[task], scalars_results=[[match]],
    )
    rows = PerformanceMetricService(session, clock=lambda: NOW).clear_confirmation(
        task.creator_employee_no, task.task_id, expected_task_version=task.task_version
    )
    assert rows == [match]
    assert match.is_confirmed is False
    assert match.confirmed_by_employee_no is None
    assert match.confirmed_at is None


def test_confirming_inactive_performance_metric_is_rejected() -> None:
    task = _task()
    metric = PerformanceMetric(
        metric_id=uuid4(), metric_type="sales", metric_name="Old KPI",
        status="inactive", created_at=NOW, updated_at=NOW,
    )
    match = TaskPerformanceMatch(
        performance_match_id=uuid4(), task_id=task.task_id, metric_id=metric.metric_id,
        type_score=80, business_unit_score=100, metric_name_score=80,
        definition_formula_score=80, deliverable_score=0, total_score=80,
        match_level="strong", is_confirmed=False, algorithm_version="tfidf-char-ngram-v1",
        created_at=NOW, updated_at=NOW,
    )
    session = RecordingSession(
        objects={
            (Task, task.task_id): task,
            (TaskPerformanceMatch, match.performance_match_id): match,
            (PerformanceMetric, metric.metric_id): metric,
        },
        scalar_results=[task],
    )
    with pytest.raises(BusinessValidationError):
        PerformanceMetricService(session, clock=lambda: NOW).confirm_match(
            task.creator_employee_no, task.task_id, match.performance_match_id,
            expected_task_version=task.task_version,
        )


def test_planning_workload_priorities_and_conflict_dedupe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedParameterService:
        def __init__(self, _session) -> None:
            pass

        def snapshot(self, _keys=None) -> dict[str, object]:
            return {
                "daily_capacity_hours": Decimal("4"),
                "standard_task_count": Decimal("1"),
                "standard_task_weight": Decimal("2"),
                "emergency_tolerance_count": Decimal("1"),
                "importance_threshold": Decimal("60"),
                "urgency_threshold": Decimal("60"),
            }

    monkeypatch.setattr(business_module, "SystemParameterService", FixedParameterService)
    target = _user("ASSIGNEE")
    active = _task(assignee="ASSIGNEE", deadline=NOW - timedelta(hours=2), task_weight=5)
    profile = EmployeeProfile(
        employee_no="ASSIGNEE",
        daily_capacity_hours=Decimal("4"),
        standard_task_count=1,
        standard_task_weight=2,
        emergency_tolerance_count=1,
        availability_status="available",
    )
    session = RecordingSession(
        objects={(User, "ASSIGNEE"): target, (EmployeeProfile, "ASSIGNEE"): profile}
    )
    service = PlanningAnalyticsService(session, clock=lambda: NOW)
    monkeypatch.setattr(service, "_active_tasks_for_employee", lambda _employee, **_kwargs: [active])
    monkeypatch.setattr(service, "_blocked_count", lambda _employee, _tasks: 1)
    monkeypatch.setattr(service, "_visible_active_tasks", lambda _actor: [active])
    monkeypatch.setattr(service, "_confirmed_performance_score", lambda _task_id: Decimal("100"))

    workload = service.calculate_workload(
        "ASSIGNEE",
        "ASSIGNEE",
        NOW,
        NOW + timedelta(days=1),
    )
    priorities = service.calculate_priorities("ASSIGNEE")

    existing = TaskConflict(
        conflict_id=uuid4(),
        conflict_type="work_hour",
        employee_no="ASSIGNEE",
        task_id=active.task_id,
        dedupe_key=f"work_hour:ASSIGNEE:{active.task_id}:-:-",
        severity="medium",
        description="old",
        status="resolved",
        detected_at=NOW - timedelta(days=1),
        resolved_by_employee_no="ASSIGNEE",
        resolved_at=NOW - timedelta(hours=1),
        resolution_note="old",
    )
    session.scalar_results = [existing]
    conflict = TaskConflict(
        conflict_type="work_hour",
        employee_no="ASSIGNEE",
        task_id=active.task_id,
        dedupe_key=existing.dedupe_key,
        severity="high",
        description="new",
        suggestion="adjust",
        status="open",
        detected_at=NOW,
    )
    monkeypatch.setattr(service, "_detect_work_hour", lambda _employee, _now: [conflict])
    monkeypatch.setattr(service, "_detect_deadline_concentration", lambda _employee, _now: [])
    monkeypatch.setattr(service, "_detect_dependency_conflicts", lambda _employee, _now: [])
    monkeypatch.setattr(service, "_detect_emergency_displacement", lambda _employee, _now: [])
    conflicts = service.detect_conflicts("ASSIGNEE")

    assert isinstance(workload, WorkloadSnapshot)
    assert workload.workload_level == "normal"
    assert workload.remaining_hours_sum == 0
    assert priorities[0].priority_quadrant == "important_urgent"
    assert conflicts == [existing]
    assert existing.status == "open"
    assert existing.resolved_by_employee_no is None
    assert session.commits == 3


def test_feature12_priority_sort_is_stable_and_uses_weight_after_remaining_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedParameterService:
        def __init__(self, _session) -> None:
            pass

        def snapshot(self, _keys=None) -> dict[str, object]:
            return {
                "daily_capacity_hours": Decimal("8"),
                "standard_task_count": Decimal("5"),
                "standard_task_weight": Decimal("3"),
                "emergency_tolerance_count": Decimal("3"),
                "importance_threshold": Decimal("70"),
                "urgency_threshold": Decimal("70"),
            }

    monkeypatch.setattr(business_module, "SystemParameterService", FixedParameterService)
    user = _user("ASSIGNEE")
    lower_weight = _task(assignee="ASSIGNEE", deadline=NOW + timedelta(days=2), task_weight=3)
    higher_weight = _task(assignee="ASSIGNEE", deadline=NOW + timedelta(days=2), task_weight=5)
    lower_weight.effective_at = NOW - timedelta(days=1)
    higher_weight.effective_at = NOW - timedelta(days=1)
    lower_weight.created_at = NOW - timedelta(days=3)
    higher_weight.created_at = NOW - timedelta(days=1)
    session = RecordingSession(objects={(User, "ASSIGNEE"): user})
    service = PlanningAnalyticsService(session, clock=lambda: NOW)
    monkeypatch.setattr(service, "_visible_active_tasks", lambda _actor: [lower_weight, higher_weight])
    monkeypatch.setattr(service, "_confirmed_performance_score", lambda _task_id: Decimal("100"))

    rows = service.calculate_priorities("ASSIGNEE")

    assert [row.task_id for row in rows] == [higher_weight.task_id, lower_weight.task_id]
    assert [row.sort_rank for row in rows] == [1, 2]
    assert all(isinstance(row, TaskPriorityScore) for row in rows)


def test_feature12_workload_failure_does_not_write_new_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenParameterService:
        def __init__(self, _session) -> None:
            pass

        def snapshot(self, _keys=None) -> dict[str, object]:
            return {
                "daily_capacity_hours": Decimal("0"),
                "standard_task_count": Decimal("5"),
                "standard_task_weight": Decimal("3"),
                "emergency_tolerance_count": Decimal("3"),
                "importance_threshold": Decimal("70"),
                "urgency_threshold": Decimal("70"),
            }

    monkeypatch.setattr(business_module, "SystemParameterService", BrokenParameterService)
    session = RecordingSession(objects={(User, "ASSIGNEE"): _user("ASSIGNEE")})
    with pytest.raises(BusinessValidationError):
        PlanningAnalyticsService(session, clock=lambda: NOW).calculate_workload(
            "ASSIGNEE", "ASSIGNEE", NOW, NOW + timedelta(days=1)
        )
    assert not any(isinstance(row, WorkloadSnapshot) for row in session.added)
    assert session.commits == 0


def test_conflict_acknowledge_records_actor_and_audit() -> None:
    conflict_id = uuid4()
    conflict = TaskConflict(
        conflict_id=conflict_id,
        conflict_type="work_hour",
        employee_no="ASSIGNEE",
        task_id=uuid4(),
        dedupe_key="work_hour:ASSIGNEE:task:-:-",
        severity="medium",
        description="Capacity is tight",
        suggestion="Review workload",
        status="open",
        detected_at=NOW,
    )
    session = RecordingSession(objects={(TaskConflict, conflict_id): conflict})

    result = PlanningAnalyticsService(session, clock=lambda: NOW).resolve_conflict(
        "ASSIGNEE",
        conflict_id,
        resolution_note="Reviewed with owner",
        status="acknowledged",
    )

    assert result.status == "acknowledged"
    assert result.resolved_by_employee_no == "ASSIGNEE"
    assert result.resolved_at == NOW
    assert _operation_logs(session)[0].action == "conflict_acknowledged"
    assert session.commits == 1


def test_reminder_notification_dedupe_retry_and_read_state() -> None:
    rule = ReminderRule(
        reminder_rule_id=uuid4(),
        task_id=uuid4(),
        reminder_type="overdue",
        recipient_employee_no="ASSIGNEE",
        next_trigger_at=NOW,
        repeat_rule="daily",
        dedupe_key="task:1:overdue",
        is_active=True,
        created_at=NOW,
    )
    session = RecordingSession(
        objects={(User, "MANAGER"): _user("MANAGER", role="manager")},
        scalars_results=[[rule]],
    )
    service = ReminderNotificationService(session, clock=lambda: NOW)
    notifications = service.create_due_notifications("MANAGER")

    notification = next(row for row in session.added if isinstance(row, Notification))
    assert notifications == [notification]
    assert notification.dedupe_key == f"task:1:overdue:{NOW.isoformat()}"
    assert rule.last_triggered_at == NOW
    assert rule.next_trigger_at == datetime(2026, 8, 22, 9, 0, tzinfo=UTC)

    class FailingProvider:
        def send(self, _recipient: str, _title: str, _content: str) -> str:
            raise RuntimeError("temporary channel failure")

    session.scalars_results = [[notification]]
    service = ReminderNotificationService(session, provider=FailingProvider(), clock=lambda: NOW)
    sent = service.send_pending("MANAGER")
    assert sent == [notification]
    assert notification.send_status == "failed"
    assert notification.retry_count == 1
    assert notification.retry_next_at == NOW + timedelta(minutes=5)

    session.objects[(Notification, notification.notification_id)] = notification
    marked = service.mark_read("ASSIGNEE", notification.notification_id)
    assert marked.read_at == NOW
    assert session.commits == 3


def test_archive_snapshot_is_immutable_and_reusable(monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task(creator="CREATOR", status="completed")

    class FixedPermissionService:
        def __init__(self, _session, *, clock=None) -> None:
            pass

        def assert_can_view_task(self, _actor: str, _task_id: UUID) -> Task:
            return task

    monkeypatch.setattr(business_module, "PermissionScopeService", FixedPermissionService)
    session = RecordingSession(
        objects={(User, "CREATOR"): _user("CREATOR"), (TaskArchive, uuid4()): None},
        scalar_results=[None],
    )
    service = ArchiveReuseService(session, object, clock=lambda: NOW)
    monkeypatch.setattr(
        service,
        "_snapshot",
        lambda _task: {"task": {"task_name": "Revenue launch"}},
    )
    monkeypatch.setattr(service, "_template", lambda _snapshot: {"nodes": [], "dependencies": []})
    monkeypatch.setattr(service, "_actual_hours_total", lambda _task_id: Decimal("12"))

    archive = service.archive_task(
        "CREATOR",
        task.task_id,
        summary=None,
        search_keywords=["revenue", "dashboard"],
        review_result="approved",
        risk_points=["late input"],
    )

    assert isinstance(archive, TaskArchive)
    assert archive.archive_snapshot == {"task": {"task_name": "Revenue launch"}}
    assert archive.actual_hours_total == Decimal("12")
    assert task.status == "archived"
    assert task.task_version == 4
    assert _operation_logs(session)[0].action == "archive"


def test_admin_can_read_any_task_without_explicit_scope() -> None:
    task = _task(creator="CREATOR", assignee="ASSIGNEE")
    admin = _user("ADMIN", role="admin")
    session = RecordingSession(objects={(User, "ADMIN"): admin})

    service = PermissionScopeService(session, clock=lambda: NOW)

    assert service.can_access_task("ADMIN", task) is True


def test_admin_global_read_does_not_grant_non_view_task_permission() -> None:
    task = _task(creator="CREATOR", assignee="ASSIGNEE")
    admin = _user("ADMIN", role="admin")
    session = RecordingSession(
        objects={(User, "ADMIN"): admin},
        scalars_results=[[]],
    )

    service = PermissionScopeService(session, clock=lambda: NOW)

    assert service.can_access_task("ADMIN", task, permission_type="manage") is False


def test_employee_scope_does_not_expand_business_task_visibility() -> None:
    task = _task(creator="CREATOR", assignee="ASSIGNEE")
    employee = _user("EMPLOYEE", role="employee")
    scope = UserAuthorizedScope(
        employee_no="EMPLOYEE",
        scope_type="user",
        scope_id="ASSIGNEE",
        permission_type="view",
        status="active",
        created_by_employee_no="ADMIN",
        created_at=NOW,
    )
    session = RecordingSession(
        objects={(User, "EMPLOYEE"): employee},
        scalar_results=[False, False, False, False],
        scalars_results=[[scope]],
    )

    service = PermissionScopeService(session, clock=lambda: NOW)

    assert service.can_access_task("EMPLOYEE", task) is False


def test_admin_read_visibility_does_not_depend_on_explicit_scope() -> None:
    task = _task(creator="CREATOR", assignee="ASSIGNEE")
    admin = _user("ADMIN", role="admin")
    session = RecordingSession(objects={(User, "ADMIN"): admin})

    service = PermissionScopeService(session, clock=lambda: NOW)

    assert service.can_access_task("ADMIN", task, permission_type="view") is True


def test_executive_can_view_direct_report_task_without_becoming_task_actor() -> None:
    task = _task(creator="CREATOR", assignee="REPORT")
    executive = _user("EXEC", role="executive")
    session = RecordingSession(
        objects={(User, "EXEC"): executive},
        scalar_results=[False, False, False, False],
        scalars_results=[["REPORT"]],
    )

    service = PermissionScopeService(session, clock=lambda: NOW)

    assert service.can_access_task("EXEC", task) is True


def test_executive_direct_report_scope_includes_collaborator_task_relation() -> None:
    task = _task(creator="CREATOR", assignee="ASSIGNEE")
    executive = _user("EXEC", role="executive")
    session = RecordingSession(
        objects={(User, "EXEC"): executive},
        scalar_results=[False, False, False, False, True],
        scalars_results=[["REPORT"]],
    )

    service = PermissionScopeService(session, clock=lambda: NOW)

    assert service.can_access_task("EXEC", task) is True


def test_feature05_registers_input_without_ai_then_validates_cloud_extraction() -> None:
    actor = _user("CREATOR")
    valid = _user("VALID")
    session = RecordingSession(objects={(User, "CREATOR"): actor, (User, "VALID"): valid})

    class ForbiddenProvider:
        def extract(self, _text, context=None):
            raise AssertionError("register_input must not invoke a backend LLM")

    service = TaskIntakeService(
        session,
        object,
        extraction_provider=ForbiddenProvider(),
        clock=lambda: NOW,
    )
    task_input = service.register_input(
        "CREATOR",
        input_type="text",
        raw_text="周五完成渠道月报，王敏负责",
        voice_file_url=None,
        source_channel="api",
    )
    assert task_input.raw_text == "周五完成渠道月报，王敏负责"
    assert not any(isinstance(row, AIExtractionRecord) for row in session.added)
    session.objects[(TaskInput, task_input.input_id)] = task_input

    result = service.record_external_extraction(
        "CREATOR",
        task_input.input_id,
        {
            "task_draft": {
                "taskName": "完成渠道月报",
                "taskDescription": "周五完成渠道月报",
                "mainAssigneeEmployeeNo": "NOT-A-USER",
                "reportToEmployeeNo": "VALID",
                "reviewerEmployeeNo": "VALID",
                "deadline": "2026-08-28T18:00:00+08:00",
                "taskWeight": 3,
                "estimatedHours": 8,
                "nodes": [{"nodeName": "must never persist"}],
            },
            "missing_fields": [],
            "low_confidence_fields": [],
            "confirm_questions": ["请确认主承办人"],
            "confidence_score": "0.72",
            "agent_result": {"provider": "qwen", "nodes": ["untrusted raw result"]},
        },
    )
    extracted = result.extraction.extracted_json
    assert extracted["task_name"] == "完成渠道月报"
    assert extracted["main_assignee_employee_no"] is None
    assert extracted["report_to_employee_no"] == "VALID"
    assert "estimated_hours" not in extracted
    assert "nodes" not in extracted
    assert extracted["agent_result"] == {"provider": "qwen"}
    assert "main_assignee_employee_no" in result.extraction.missing_fields
    assert "main_assignee_employee_no" in result.extraction.low_confidence_fields
    assert result.extraction.confirmed_at is None
