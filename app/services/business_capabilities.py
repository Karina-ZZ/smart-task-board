from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

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
    TaskConflict,
    TaskInput,
    TaskIssue,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskPerformanceMatch,
    TaskPriorityScore,
    TaskProgressReport,
    User,
    UserAuthorizedScope,
    WorkloadSnapshot,
)
from app.services.commands import (
    CreateTaskDraftCommand,
    TaskNodeDependencyDraft,
    TaskNodeDraft,
    TaskParticipantDraft,
)
from app.services.errors import (
    BusinessValidationError,
    EntityNotFoundError,
    PermissionDeniedError,
    TaskVersionConflictError,
)
from app.services.features.performance_matching import PerformanceMatchScorer
from app.services.features.planning_analytics import (
    EXECUTION_TASK_STATUSES,
    overdue_days as calculate_overdue_days,
    remaining_hours as calculate_remaining_hours,
    overdue_pressure_score as calculate_overdue_pressure_score,
    time_pressure_score as calculate_time_pressure_score,
    working_hours_between,
    workload_level as calculate_workload_level,
)
from app.services.progress_report import task_report_period
from app.services.task_workflow import TASK_ARCHIVED, TaskWorkflowService

ACTIVE_TASK_STATUSES = frozenset(
    {
        "pending_confirmation",
        "pending_acceptance",
        "returned",
        "in_progress",
        "pending_review",
    }
)
INTAKE_TEXT_MAX_LENGTH = 4000
INTAKE_EMPLOYEE_FIELDS = (
    "main_assignee_employee_no",
    "report_to_employee_no",
    "reviewer_employee_no",
)
INTAKE_DATE_FIELDS = ("start_time", "deadline")
INTAKE_ALLOWED_FIELDS = frozenset(
    {
        "agent_result",
        "task_draft",
        "task_name",
        "task_description",
        "task_goal",
        "task_source",
        "main_assignee_employee_no",
        "report_to_employee_no",
        "report_to_level",
        "reviewer_employee_no",
        "department_id",
        "start_time",
        "deadline",
        "task_weight",
        "deliverable",
        "acceptance_criteria",
        "is_urgent",
        "report_cycle",
        "collaborators",
        "performance_metric",
        "nodes",
        "dependencies",
    }
)
TERMINAL_TASK_STATUSES = frozenset(
    {"completed", "archived", "cancelled", "withdrawn", "merged", "closed"}
)
IMPORTANT_URGENT = "important_urgent"
IMPORTANT_NOT_URGENT = "important_not_urgent"
NOT_IMPORTANT_URGENT = "not_important_urgent"
NOT_IMPORTANT_NOT_URGENT = "not_important_not_urgent"


def _now() -> datetime:
    return datetime.now(UTC)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BusinessValidationError("datetime values must be timezone-aware")
    return value.astimezone(UTC)


def _json_value(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return value


def _required_text(value: str | None, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise BusinessValidationError(f"{field_name} must not be blank")
    return normalized


def _decimal(value: object | None, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise BusinessValidationError("numeric value is invalid") from exc


def _optional_uuid(value: object | None, field_name: str) -> UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise BusinessValidationError(f"{field_name} must be a valid UUID") from exc


def _bounded(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value))


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return _bounded(numerator / denominator * Decimal("100"))


def _tokens(*values: object) -> set[str]:
    text = " ".join(str(value or "") for value in values).casefold()
    return {token for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", text) if token}


def _text_score(left: Iterable[str], right: Iterable[str]) -> Decimal:
    left_tokens = set(left)
    right_tokens = set(right)
    if not left_tokens or not right_tokens:
        return Decimal("0")
    overlap = len(left_tokens & right_tokens)
    return _bounded(Decimal(overlap) / Decimal(len(left_tokens | right_tokens)) * Decimal("100"))


def _workdays(start: datetime, end: datetime) -> int:
    cursor = start.date()
    end_date = end.date()
    days = 0
    while cursor <= end_date:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return max(days, 1)


def _task_text(task: Task) -> str:
    return " ".join(
        str(value or "")
        for value in (
            task.task_name,
            task.task_description,
            task.task_goal,
            task.deliverable,
            task.acceptance_criteria,
            task.task_source,
        )
    )


def _add_operation_log(
    session: Session,
    *,
    actor: str | None,
    action: str,
    object_type: str,
    object_id: object,
    before_data: Mapping[str, object] | None = None,
    after_data: Mapping[str, object] | None = None,
    result: str = "success",
    error_message: str | None = None,
    request_id: str | None = None,
    at: datetime | None = None,
) -> OperationLog:
    row = OperationLog(
        request_id=request_id,
        operator_employee_no=actor,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        before_data=_json_value(before_data) if before_data is not None else None,
        after_data=_json_value(after_data) if after_data is not None else None,
        result=result,
        error_message=error_message,
        created_at=at or _now(),
    )
    session.add(row)
    return row


DEFAULT_PARAMETERS: dict[str, tuple[str, str, str, str, str]] = {
    "daily_capacity_hours": (
        "Daily capacity hours",
        "8",
        "number",
        "workload",
        "Default daily available hours.",
    ),
    "standard_task_count": (
        "Standard task count",
        "5",
        "number",
        "workload",
        "Default active task count capacity.",
    ),
    "standard_task_weight": (
        "Standard task weight",
        "3",
        "number",
        "workload",
        "Default active task weight capacity.",
    ),
    "emergency_tolerance_count": (
        "Emergency tolerance count",
        "3",
        "number",
        "workload",
        "Default urgent-task tolerance.",
    ),
    "importance_threshold": (
        "Importance threshold",
        "70",
        "number",
        "priority",
        "Important quadrant threshold.",
    ),
    "urgency_threshold": (
        "Urgency threshold",
        "70",
        "number",
        "priority",
        "Urgent quadrant threshold.",
    ),
}

INTAKE_FIELD_ALIASES = {
    "taskDraft": "task_draft",
    "taskName": "task_name",
    "taskDescription": "task_description",
    "taskGoal": "task_goal",
    "taskSource": "task_source",
    "mainAssigneeEmployeeNo": "main_assignee_employee_no",
    "reportToEmployeeNo": "report_to_employee_no",
    "reportToLevel": "report_to_level",
    "reviewerEmployeeNo": "reviewer_employee_no",
    "departmentId": "department_id",
    "startTime": "start_time",
    "deadline": "deadline",
    "estimatedHours": "estimated_hours",
    "taskWeight": "task_weight",
    "deliverable": "deliverable",
    "acceptanceCriteria": "acceptance_criteria",
    "isUrgent": "is_urgent",
    "reportCycle": "report_cycle",
    "collaboratorEmployeeNos": "collaborators",
}

INTAKE_NODE_ALIASES = {
    "clientNodeId": "client_node_id",
    "nodeOrder": "node_order",
    "nodeName": "node_name",
    "actionDetail": "action_detail",
    "toolsOrMaterials": "tools_or_materials",
    "ownerEmployeeNo": "owner_employee_no",
    "collaboratorEmployeeNos": "collaborators",
    "plannedStartTime": "planned_start_time",
    "plannedDeadline": "planned_deadline",
    "estimatedHours": "estimated_hours",
    "deliverable": "deliverable",
    "acceptanceCriteria": "acceptance_criteria",
}

INTAKE_DEPENDENCY_ALIASES = {
    "predecessorClientNodeId": "predecessor_client_node_id",
    "successorClientNodeId": "successor_client_node_id",
    "predecessorNodeId": "predecessor_client_node_id",
    "successorNodeId": "successor_client_node_id",
    "dependencyType": "dependency_type",
}


class SystemParameterService:
    def __init__(self, session: Session, clock=_now) -> None:
        self.session = session
        self.clock = clock

    def ensure_defaults(self) -> list[SystemParameter]:
        rows: list[SystemParameter] = []
        now = self.clock()
        for key, (name, value, param_type, module, description) in DEFAULT_PARAMETERS.items():
            row = self.session.scalar(
                select(SystemParameter).where(SystemParameter.param_key == key)
            )
            if row is None:
                row = SystemParameter(
                    param_key=key,
                    param_name=name,
                    param_value=value,
                    param_type=param_type,
                    module=module,
                    description=description,
                    is_active=True,
                    updated_at=now,
                )
                self.session.add(row)
            rows.append(row)
        self.session.commit()
        return rows

    def list_parameters(self) -> list[SystemParameter]:
        self.ensure_defaults()
        statement = select(SystemParameter).order_by(
            SystemParameter.module, SystemParameter.param_key
        )
        return list(self.session.scalars(statement).all())

    def snapshot(self, keys: Sequence[str] | None = None) -> dict[str, object]:
        requested = set(keys or DEFAULT_PARAMETERS)
        defaults = {
            key: self._parse_value(value, param_type)
            for key, (_, value, param_type, _, _) in DEFAULT_PARAMETERS.items()
            if key in requested
        }
        statement = select(SystemParameter).where(
            SystemParameter.is_active.is_(True),
            SystemParameter.param_key.in_(requested),
        )
        for row in self.session.scalars(statement).all():
            defaults[row.param_key] = self._parse_value(row.param_value, row.param_type)
        return defaults

    def upsert_parameter(
        self,
        actor: str,
        key: str,
        *,
        value: str,
        param_type: str,
        module: str,
        name: str | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> SystemParameter:
        self._require_admin(actor)
        self._parse_value(value, param_type)
        now = self.clock()
        row = self.session.scalar(select(SystemParameter).where(SystemParameter.param_key == key))
        before = None
        if row is None:
            row = SystemParameter(
                param_key=key,
                param_name=name or key,
                param_value=value,
                param_type=param_type,
                module=module,
                description=description,
                is_active=is_active,
                updated_by_employee_no=actor,
                updated_at=now,
            )
            self.session.add(row)
        else:
            before = self._parameter_dict(row)
            row.param_name = name or row.param_name
            row.param_value = value
            row.param_type = param_type
            row.module = module
            row.description = description
            row.is_active = is_active
            row.updated_by_employee_no = actor
            row.updated_at = now
        self.session.flush()
        _add_operation_log(
            self.session,
            actor=actor,
            action="parameter_changed",
            object_type="system_parameter",
            object_id=row.parameter_id,
            before_data=before,
            after_data=self._parameter_dict(row),
            at=now,
        )
        self.session.commit()
        return row

    def _require_admin(self, actor: str) -> None:
        user = self.session.get(User, actor)
        if user is None or user.status != "active" or user.role_type != "admin":
            raise PermissionDeniedError("actor must be an active administrator")

    @staticmethod
    def _parse_value(value: str, param_type: str) -> object:
        if param_type == "number":
            return Decimal(value)
        if param_type == "boolean":
            return value.strip().casefold() in {"1", "true", "yes", "on"}
        if param_type == "json":
            return json.loads(value)
        return value

    @staticmethod
    def _parameter_dict(row: SystemParameter) -> dict[str, object]:
        return {
            "param_key": row.param_key,
            "param_value": row.param_value,
            "param_type": row.param_type,
            "module": row.module,
            "is_active": row.is_active,
        }


class PermissionScopeService:
    def __init__(self, session: Session, clock=_now) -> None:
        self.session = session
        self.clock = clock

    def grant_scope(
        self,
        actor: str,
        *,
        employee_no: str,
        scope_type: str,
        scope_id: str | None,
        permission_type: str,
        valid_from: datetime | None,
        valid_to: datetime | None,
        status: str = "active",
    ) -> UserAuthorizedScope:
        self._require_admin(actor)
        target = self.session.get(User, employee_no)
        if target is None:
            raise EntityNotFoundError("authorized employee was not found")
        if scope_type != "all_demo_data" and not scope_id:
            raise BusinessValidationError("scope_id is required")
        if valid_from is not None:
            valid_from = _aware_utc(valid_from)
        if valid_to is not None:
            valid_to = _aware_utc(valid_to)
        row = UserAuthorizedScope(
            employee_no=employee_no,
            scope_type=scope_type,
            scope_id=scope_id,
            permission_type=permission_type,
            valid_from=valid_from,
            valid_to=valid_to,
            status=status,
            created_by_employee_no=actor,
            created_at=self.clock(),
        )
        self.session.add(row)
        self.session.flush()
        _add_operation_log(
            self.session,
            actor=actor,
            action="permission_scope_granted",
            object_type="user_authorized_scope",
            object_id=row.authorized_scope_id,
            after_data=self._scope_dict(row),
        )
        self.session.commit()
        return row

    def list_scopes(self, actor: str, employee_no: str | None = None) -> list[UserAuthorizedScope]:
        self._require_admin_or_self(actor, employee_no or actor)
        target = employee_no or actor
        statement = (
            select(UserAuthorizedScope)
            .where(UserAuthorizedScope.employee_no == target)
            .order_by(
                UserAuthorizedScope.created_at.desc(), UserAuthorizedScope.authorized_scope_id
            )
        )
        return list(self.session.scalars(statement).all())

    def can_view_task(self, actor: str, task_id: UUID) -> bool:
        task = self.session.get(Task, task_id)
        if task is None:
            raise EntityNotFoundError("task was not found")
        return self.can_access_task(actor, task, "view")

    def can_access_task(self, actor: str, task: Task, permission_type: str = "view") -> bool:
        user = self.session.get(User, actor)
        if user is None or user.status != "active":
            return False
        # P0 admin read policy: an active administrator may read every task and
        # its task-scoped read models. This is read-only elevation; business
        # write actions still derive from task relationship/state/version rules.
        if permission_type == "view" and user.role_type == "admin":
            return True
        if permission_type == "view" and self._has_direct_relation(actor, task):
            return True

        # FR-22: employee scope rows do not expand business-task visibility.
        # Executives may read direct-report tasks and may expand read scope only
        # through an active explicit authorized scope.
        people = {
            task.creator_employee_no,
            task.main_assignee_employee_no,
            task.report_to_employee_no,
            task.reviewer_employee_no,
        } - {None}
        if user.role_type == "executive":
            direct_reports = set(
                self.session.scalars(
                    select(User.employee_no).where(User.manager_employee_no == actor)
                ).all()
            )
            if direct_reports & people:
                return True
            if any(self._has_direct_relation(employee_no, task) for employee_no in direct_reports):
                return True
        if user.role_type not in {"executive", "admin"}:
            return False

        for scope in self._active_scopes(actor, permission_type):
            if scope.scope_type == "all_demo_data":
                return True
            if scope.scope_type == "user" and scope.scope_id:
                if scope.scope_id in people or self._has_direct_relation(scope.scope_id, task):
                    return True
            if scope.scope_type == "role" and scope.scope_id:
                if any(self._user_has_role(employee_no, scope.scope_id) for employee_no in people):
                    return True
            if scope.scope_type == "department" and scope.scope_id:
                if self._department_scope_matches(task.department_id, scope.scope_id):
                    return True
        return False

    def can_assign_employee(
        self,
        actor: str,
        target_employee_no: str,
        permission_type: str = "manage",
    ) -> bool:
        actor_user = self.session.get(User, actor)
        if actor_user is None or actor_user.status != "active":
            return False
        target = self.session.get(User, target_employee_no)
        if target is None or target.status != "active":
            return False
        if actor == target_employee_no:
            return True
        if actor_user.role_type == "executive" and target.manager_employee_no == actor:
            return True
        if actor_user.role_type not in {"executive", "admin"}:
            return False
        for scope in self._active_scopes(actor, permission_type):
            if scope.scope_type == "all_demo_data":
                return True
            if scope.scope_type == "user" and scope.scope_id == target_employee_no:
                return True
            if scope.scope_type == "role" and scope.scope_id == target.role_type:
                return True
            if (
                scope.scope_type == "department"
                and scope.scope_id
                and self._department_scope_matches(target.department_id, scope.scope_id)
            ):
                return True
        return False

    def assert_can_view_task(self, actor: str, task_id: UUID) -> Task:
        task = self.session.get(Task, task_id)
        if task is None:
            raise EntityNotFoundError("task was not found")
        if not self.can_access_task(actor, task, "view"):
            raise PermissionDeniedError("actor cannot read this task")
        return task

    def recommend_assignees(
        self,
        actor: str,
        *,
        task_description: str,
        required_skill_tags: Sequence[str],
        department_id: UUID | None,
        limit: int,
    ) -> list[dict[str, object]]:
        requester = self.session.get(User, actor)
        if requester is None or requester.status != "active":
            raise PermissionDeniedError("actor is not active")
        statement = select(User, EmployeeProfile).join(
            EmployeeProfile, User.employee_no == EmployeeProfile.employee_no
        )
        statement = statement.where(
            User.status == "active", EmployeeProfile.availability_status != "disabled"
        )
        if department_id is not None:
            statement = statement.where(User.department_id == department_id)
        desired = _tokens(task_description, *required_skill_tags)
        candidates: list[dict[str, object]] = []
        for user, profile in self.session.execute(statement).all():
            profile_tokens = _tokens(profile.responsibility_text, *profile.skill_tags)
            score = _text_score(desired, profile_tokens)
            if profile.availability_status == "available":
                score += Decimal("15")
            elif profile.availability_status == "busy":
                score += Decimal("5")
            score = _bounded(score)
            candidates.append(
                {
                    "employee_no": user.employee_no,
                    "name": user.name,
                    "score": score,
                    "reasons": self._recommendation_reasons(profile, desired),
                }
            )
        return sorted(candidates, key=lambda item: (-item["score"], item["employee_no"]))[:limit]

    def _active_scopes(self, actor: str, permission_type: str) -> list[UserAuthorizedScope]:
        now = self.clock()
        allowed_permissions = {
            "view": {"view", "manage", "export"},
            "manage": {"manage"},
            "export": {"export", "manage"},
        }[permission_type]
        statement = select(UserAuthorizedScope).where(
            UserAuthorizedScope.employee_no == actor,
            UserAuthorizedScope.status == "active",
            UserAuthorizedScope.permission_type.in_(allowed_permissions),
            or_(
                UserAuthorizedScope.valid_from.is_(None),
                UserAuthorizedScope.valid_from <= now,
            ),
            or_(UserAuthorizedScope.valid_to.is_(None), UserAuthorizedScope.valid_to >= now),
        )
        return list(self.session.scalars(statement).all())

    def _has_direct_relation(self, actor: str, task: Task) -> bool:
        if actor in {
            task.creator_employee_no,
            task.main_assignee_employee_no,
            task.report_to_employee_no,
            task.reviewer_employee_no,
        }:
            return True
        relation_checks = (
            exists().where(
                TaskParticipant.task_id == task.task_id,
                TaskParticipant.employee_no == actor,
            ),
            exists().where(
                TaskNode.task_id == task.task_id,
                TaskNode.owner_employee_no == actor,
            ),
            exists().where(
                TaskNodeParticipant.task_id == task.task_id,
                TaskNodeParticipant.employee_no == actor,
            ),
            exists().where(
                TaskIssue.task_id == task.task_id,
                or_(
                    TaskIssue.reported_by_employee_no == actor,
                    TaskIssue.owner_employee_no == actor,
                    TaskIssue.resolved_by_employee_no == actor,
                    TaskIssue.rejected_by_employee_no == actor,
                    TaskIssue.closed_by_employee_no == actor,
                ),
            ),
        )
        return any(
            bool(self.session.scalar(select(relation_exists)))
            for relation_exists in relation_checks
        )

    def _department_scope_matches(self, department_id: UUID | None, scope_id: str) -> bool:
        if department_id is None:
            return False
        department = self.session.get(Department, department_id)
        if department is None:
            return False
        return str(department.department_id) == scope_id or scope_id in department.department_path

    def _user_has_role(self, employee_no: str, role_type: str) -> bool:
        user = self.session.get(User, employee_no)
        return bool(user is not None and user.role_type == role_type)

    def _require_admin(self, actor: str) -> None:
        user = self.session.get(User, actor)
        if user is None or user.status != "active" or user.role_type != "admin":
            raise PermissionDeniedError("actor must be an active administrator")

    def _require_admin_or_self(self, actor: str, target: str) -> None:
        if actor == target:
            return
        self._require_admin(actor)

    @staticmethod
    def _scope_dict(row: UserAuthorizedScope) -> dict[str, object]:
        return {
            "employee_no": row.employee_no,
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "permission_type": row.permission_type,
            "status": row.status,
        }

    @staticmethod
    def _recommendation_reasons(
        profile: EmployeeProfile,
        desired_tokens: set[str],
    ) -> list[str]:
        reasons: list[str] = []
        matching_skills = [
            skill for skill in profile.skill_tags if skill.casefold() in desired_tokens
        ]
        if matching_skills:
            reasons.append("skill match: " + ", ".join(matching_skills[:3]))
        if profile.responsibility_text:
            reasons.append("responsibility profile available")
        reasons.append(f"availability: {profile.availability_status}")
        return reasons


class ASRProvider(Protocol):
    def transcribe(self, voice_file_url: str) -> str: ...


class TaskExtractionProvider(Protocol):
    def extract(
        self, text: str, context: Mapping[str, object] | None = None
    ) -> dict[str, object]: ...


class TaskDecompositionProvider(Protocol):
    def decompose(self, extracted: Mapping[str, object]) -> dict[str, object]: ...


class FakeASRProvider:
    def transcribe(self, voice_file_url: str) -> str:
        return f"Transcribed voice input from {voice_file_url}"


class FakeTaskExtractionProvider:
    CRITICAL_FIELDS = (
        "task_name",
        "task_description",
        "main_assignee_employee_no",
        "report_to_employee_no",
        "reviewer_employee_no",
        "deadline",
        "task_weight",
    )

    def extract(self, text: str, context: Mapping[str, object] | None = None) -> dict[str, object]:
        merged: dict[str, object] = dict(context or {})
        normalized = text.strip()
        merged.setdefault("task_name", normalized.splitlines()[0][:80] or "Untitled task")
        merged.setdefault("task_description", normalized)
        merged.setdefault("task_source", "manual")
        merged.setdefault("task_weight", 3)
        for key, value in self._parse_key_values(normalized).items():
            merged[key] = value
        if not merged.get("reviewer_employee_no") and merged.get("report_to_employee_no"):
            merged["reviewer_employee_no"] = merged["report_to_employee_no"]
        missing = [field for field in self.CRITICAL_FIELDS if not merged.get(field)]
        low_confidence = [
            field
            for field in ("deadline", "estimated_hours", "performance_metric")
            if field in merged and isinstance(merged[field], str) and "待确认" in str(merged[field])
        ]
        questions = [
            f"Please confirm {field}." for field in dict.fromkeys(missing + low_confidence)
        ]
        confidence = Decimal("0.95") if not missing and not low_confidence else Decimal("0.60")
        return {
            "extracted_json": merged,
            "missing_fields": missing,
            "low_confidence_fields": low_confidence,
            "confirm_questions": questions,
            "confidence_score": confidence,
        }

    @staticmethod
    def _parse_key_values(text: str) -> dict[str, object]:
        aliases = {
            "assignee": "main_assignee_employee_no",
            "main_assignee": "main_assignee_employee_no",
            "report_to": "report_to_employee_no",
            "deadline": "deadline",
            "estimated_hours": "estimated_hours",
            "hours": "estimated_hours",
            "weight": "task_weight",
            "acceptance": "acceptance_criteria",
            "deliverable": "deliverable",
        }
        found: dict[str, object] = {}
        for match in re.finditer(r"([a-zA-Z_]+)\s*[:=]\s*([^;\n]+)", text):
            key = aliases.get(match.group(1).casefold())
            if key is None:
                continue
            value: object = match.group(2).strip()
            if key == "task_weight":
                value = int(value)
            found[key] = value
        return found


class FakeTaskDecompositionProvider:
    def decompose(self, extracted: Mapping[str, object]) -> dict[str, object]:
        goal = str(extracted.get("task_name") or extracted.get("task_description") or "Task")
        owner = extracted.get("main_assignee_employee_no")
        nodes = [
            {
                "node_name": "Clarify scope",
                "action_detail": f"Confirm scope and expected output for {goal}.",
                "tools_or_materials": "task input, stakeholder notes",
                "owner_employee_no": owner,
                "collaborators": [],
                "dependencies": [],
                "estimated_hours": "1",
                "deliverable": "Confirmed scope notes",
                "acceptance_criteria": "Scope, owner, deadline and deliverable are explicit.",
            },
            {
                "node_name": "Collect source material",
                "action_detail": "Collect current documents, data and constraints.",
                "tools_or_materials": "shared documents, systems, interviews",
                "owner_employee_no": owner,
                "collaborators": [],
                "dependencies": [0],
                "estimated_hours": "2",
                "deliverable": "Source material list",
                "acceptance_criteria": "Required source material is available for execution.",
            },
            {
                "node_name": "Produce first draft",
                "action_detail": "Create a complete first draft or working artifact.",
                "tools_or_materials": "approved scope and source material",
                "owner_employee_no": owner,
                "collaborators": [],
                "dependencies": [1],
                "estimated_hours": "3",
                "deliverable": str(extracted.get("deliverable") or "First draft"),
                "acceptance_criteria": str(
                    extracted.get("acceptance_criteria") or "Draft covers the confirmed scope."
                ),
            },
            {
                "node_name": "Review and revise",
                "action_detail": "Collect feedback from reviewer and update the artifact.",
                "tools_or_materials": "review comments",
                "owner_employee_no": owner,
                "collaborators": [],
                "dependencies": [2],
                "estimated_hours": "2",
                "deliverable": "Revised artifact",
                "acceptance_criteria": "Reviewer comments are addressed.",
            },
            {
                "node_name": "Submit for acceptance",
                "action_detail": "Package final output and submit it for completion review.",
                "tools_or_materials": "final artifact",
                "owner_employee_no": owner,
                "collaborators": [],
                "dependencies": [3],
                "estimated_hours": "1",
                "deliverable": "Final submission",
                "acceptance_criteria": "Final output is ready for formal acceptance.",
            },
        ]
        return {"nodes": nodes}


@dataclass(frozen=True)
class IntakeResult:
    task_input: TaskInput
    extraction: AIExtractionRecord


class TaskIntakeService:
    def __init__(
        self,
        session: Session,
        uow_factory,
        *,
        asr_provider: ASRProvider | None = None,
        extraction_provider: TaskExtractionProvider | None = None,
        decomposition_provider: TaskDecompositionProvider | None = None,
        agent_timezone: str = "Asia/Shanghai",
        clock=_now,
    ) -> None:
        self.session = session
        self.uow_factory = uow_factory
        self.asr_provider = asr_provider or FakeASRProvider()
        self.extraction_provider = extraction_provider or FakeTaskExtractionProvider()
        self.decomposition_provider = decomposition_provider or FakeTaskDecompositionProvider()
        self.agent_timezone = agent_timezone
        self.clock = clock

    def register_input(
        self,
        actor: str,
        *,
        input_type: str,
        raw_text: str | None,
        voice_file_url: str | None,
        source_channel: str,
        input_id: UUID | None = None,
    ) -> TaskInput:
        """Persist an original input without invoking an AI provider.

        Feature 05 mini-program flow calls the replaceable ChatService directly, then
        sends the structured result back for server-side validation and persistence.
        """
        self._require_active_user(actor)
        if input_id is not None:
            existing = self.session.get(TaskInput, input_id)
            if existing is not None:
                self._require_task_input_owner(actor, existing)
                return existing
        text = _required_text(raw_text, "raw_text")
        self._validate_input_length(text)
        now = self.clock()
        task_input = TaskInput(
            input_id=input_id or uuid4(),
            input_type=input_type,
            raw_text=raw_text,
            voice_file_url=voice_file_url,
            asr_text=text if input_type == "voice" else None,
            source_channel=source_channel,
            submitted_by_employee_no=actor,
            submitted_at=now,
        )
        self.session.add(task_input)
        _add_operation_log(
            self.session,
            actor=actor,
            action="task_input_registered",
            object_type="task_input",
            object_id=task_input.input_id,
            after_data={"input_type": input_type, "source_channel": source_channel},
            at=now,
        )
        self.session.commit()
        return task_input

    def record_external_extraction(
        self,
        actor: str,
        input_id: UUID,
        payload: Mapping[str, object],
    ) -> IntakeResult:
        """Validate and persist one ChatService/Qwen extraction round."""
        task_input = self._get_owned_task_input(actor, input_id, action="record extraction for")
        task_draft = payload.get("task_draft")
        if not isinstance(task_draft, Mapping):
            raise BusinessValidationError("task_draft must be an object")
        normalized = self._normalize_extraction_payload(task_draft)
        normalized.pop("estimated_hours", None)
        normalized.pop("nodes", None)
        normalized.pop("dependencies", None)
        agent_result = payload.get("agent_result")
        if isinstance(agent_result, Mapping):
            normalized["agent_result"] = _json_value(
                {
                    key: agent_result.get(key)
                    for key in ("provider", "model", "requestId", "request_id", "chatSessionId", "chat_session_id")
                    if agent_result.get(key) is not None
                }
            )
        validated = self._validated_extraction_result(
            {
                "extracted_json": normalized,
                "missing_fields": payload.get("missing_fields") or [],
                "low_confidence_fields": payload.get("low_confidence_fields") or [],
                "confirm_questions": payload.get("confirm_questions") or [],
                "confidence_score": payload.get("confidence_score"),
            }
        )
        now = self.clock()
        extraction = AIExtractionRecord(
            input_id=input_id,
            extracted_json=_json_value(validated["extracted_json"]),
            missing_fields=list(validated["missing_fields"]),
            low_confidence_fields=list(validated["low_confidence_fields"]),
            confirm_questions=list(validated["confirm_questions"]),
            confidence_score=_decimal(validated.get("confidence_score")),
            confirmed_at=(
                now
                if not validated["missing_fields"] and not validated["low_confidence_fields"]
                else None
            ),
        )
        self.session.add(extraction)
        _add_operation_log(
            self.session,
            actor=actor,
            action="task_input_external_extraction_recorded",
            object_type="task_input",
            object_id=input_id,
            after_data={"extraction_id": extraction.extraction_id, "provider": "cloud_chat"},
            at=now,
        )
        self.session.commit()
        return IntakeResult(task_input, extraction)

    def submit_input(
        self,
        actor: str,
        *,
        input_type: str,
        raw_text: str | None,
        voice_file_url: str | None,
        source_channel: str,
        input_id: UUID | None = None,
    ) -> IntakeResult:
        self._require_active_user(actor)
        if input_id is not None:
            existing = self.session.get(TaskInput, input_id)
            if existing is not None:
                self._require_task_input_owner(actor, existing)
                extraction = self._latest_extraction(existing.input_id)
                if extraction is None:
                    raise BusinessValidationError("existing task input has no extraction record")
                return IntakeResult(existing, extraction)
        text = raw_text
        if input_type == "voice":
            text = (
                self.asr_provider.transcribe(_required_text(voice_file_url, "voice_file_url"))
                if voice_file_url
                else raw_text
            )
        text = _required_text(text, "raw_text")
        self._validate_input_length(text)
        now = self.clock()
        task_input = TaskInput(
            input_id=input_id or uuid4(),
            input_type=input_type,
            raw_text=raw_text,
            voice_file_url=voice_file_url,
            asr_text=text if input_type == "voice" else None,
            source_channel=source_channel,
            submitted_by_employee_no=actor,
            submitted_at=now,
        )
        context = (
            self._agent_context(
                actor,
                input_id=task_input.input_id,
                input_type=input_type,
                raw_text=raw_text,
                asr_text=task_input.asr_text,
                source_channel=source_channel,
                now=now,
            )
            if self._uses_structured_agent_context()
            else None
        )
        extracted = self._run_extraction(text, context=context)
        extraction = AIExtractionRecord(
            input_id=task_input.input_id,
            extracted_json=_json_value(extracted["extracted_json"]),
            missing_fields=list(extracted["missing_fields"]),
            low_confidence_fields=list(extracted["low_confidence_fields"]),
            confirm_questions=list(extracted["confirm_questions"]),
            confidence_score=_decimal(extracted.get("confidence_score")),
        )
        self.session.add(task_input)
        self.session.add(extraction)
        _add_operation_log(
            self.session,
            actor=actor,
            action="task_input_submitted",
            object_type="task_input",
            object_id=task_input.input_id,
            after_data={"input_type": input_type, "source_channel": source_channel},
            at=now,
        )
        self.session.commit()
        return IntakeResult(task_input, extraction)

    def clarify(self, actor: str, input_id: UUID, answers: Mapping[str, object]) -> IntakeResult:
        task_input = self._get_owned_task_input(actor, input_id, action="clarify")
        previous = self._latest_extraction(input_id)
        source_text = task_input.asr_text or task_input.raw_text or ""
        clarification_text = answers.get("clarification_text")
        if isinstance(clarification_text, str) and clarification_text.strip():
            source_text = f"{source_text}\n{clarification_text.strip()}"
        context = (
            self._agent_context(
                actor,
                input_id=input_id,
                input_type=task_input.input_type,
                raw_text=task_input.raw_text,
                asr_text=task_input.asr_text,
                source_channel=task_input.source_channel,
                now=self.clock(),
                previous=previous,
                answers=answers,
            )
            if self._uses_structured_agent_context()
            else self._legacy_clarification_context(previous, answers)
        )
        extracted = self._run_extraction(source_text, context=context)
        now = self.clock()
        extraction = AIExtractionRecord(
            input_id=input_id,
            extracted_json=_json_value(extracted["extracted_json"]),
            missing_fields=list(extracted["missing_fields"]),
            low_confidence_fields=list(extracted["low_confidence_fields"]),
            confirm_questions=list(extracted["confirm_questions"]),
            confidence_score=_decimal(extracted.get("confidence_score")),
            confirmed_at=now
            if not extracted["missing_fields"] and not extracted["low_confidence_fields"]
            else None,
        )
        self.session.add(extraction)
        _add_operation_log(
            self.session,
            actor=actor,
            action="task_input_clarified",
            object_type="task_input",
            object_id=input_id,
            after_data={"extraction_id": extraction.extraction_id, "answers": _json_value(answers)},
            at=now,
        )
        self.session.commit()
        return IntakeResult(task_input, extraction)

    def retry_extraction(self, actor: str, input_id: UUID) -> IntakeResult:
        task_input = self._get_owned_task_input(actor, input_id, action="retry")
        source_text = self._source_text(task_input)
        previous = self._latest_extraction(input_id)
        now = self.clock()
        context = (
            self._agent_context(
                actor,
                input_id=input_id,
                input_type=task_input.input_type,
                raw_text=task_input.raw_text,
                asr_text=task_input.asr_text,
                source_channel=task_input.source_channel,
                now=now,
                previous=previous,
            )
            if self._uses_structured_agent_context()
            else (dict(previous.extracted_json) if previous is not None else None)
        )
        extracted = self._run_extraction(source_text, context=context)
        extraction = AIExtractionRecord(
            input_id=input_id,
            extracted_json=_json_value(extracted["extracted_json"]),
            missing_fields=list(extracted["missing_fields"]),
            low_confidence_fields=list(extracted["low_confidence_fields"]),
            confirm_questions=list(extracted["confirm_questions"]),
            confidence_score=_decimal(extracted.get("confidence_score")),
        )
        self.session.add(extraction)
        _add_operation_log(
            self.session,
            actor=actor,
            action="task_input_extraction_retried",
            object_type="task_input",
            object_id=input_id,
            after_data={"extraction_id": extraction.extraction_id},
            at=now,
        )
        self.session.commit()
        return IntakeResult(task_input, extraction)

    def get_latest_extraction(self, actor: str, input_id: UUID) -> IntakeResult:
        task_input = self._get_owned_task_input(actor, input_id, action="read")
        extraction = self._latest_extraction(input_id)
        if extraction is None:
            raise EntityNotFoundError("AI extraction record was not found")
        return IntakeResult(task_input, extraction)

    def create_draft_from_extraction(
        self,
        actor: str,
        *,
        extraction_id: UUID,
        corrections: Mapping[str, object] | None = None,
        task_id: UUID | None = None,
    ) -> Task:
        extraction = self.session.get(AIExtractionRecord, extraction_id)
        if extraction is None:
            raise EntityNotFoundError("AI extraction record was not found")
        task_input = self.session.get(TaskInput, extraction.input_id)
        if task_input is None:
            raise EntityNotFoundError("task input was not found")
        if task_input.submitted_by_employee_no != actor:
            raise PermissionDeniedError("actor cannot confirm this task input")
        if extraction.task_id is not None:
            task = self.session.get(Task, extraction.task_id)
            if task is None:
                raise EntityNotFoundError("linked task was not found")
            return task
        payload = self._normalize_extraction_payload(extraction.extracted_json)
        payload.update(self._normalize_extraction_payload(corrections or {}))
        missing = [
            field
            for field in FakeTaskExtractionProvider.CRITICAL_FIELDS
            if not payload.get(field)
        ]
        if missing:
            raise BusinessValidationError(
                "missing required confirmation fields: " + ", ".join(missing)
            )
        participants = tuple(
            TaskParticipantDraft(str(employee_no), "collaborator")
            for employee_no in self._sequence(payload.get("collaborators"))
        )
        command = CreateTaskDraftCommand(
            task_id=task_id or uuid4(),
            task_name=_required_text(str(payload.get("task_name") or ""), "task_name"),
            creator_employee_no=actor,
            operation_source="ai_intake",
            task_description=str(payload.get("task_description") or ""),
            task_goal=payload.get("task_goal"),
            task_source=str(payload.get("task_source") or "ai_intake"),
            main_assignee_employee_no=str(payload.get("main_assignee_employee_no")),
            report_to_employee_no=str(payload.get("report_to_employee_no")),
            report_to_level=payload.get("report_to_level"),
            reviewer_employee_no=payload.get("reviewer_employee_no")
            or payload.get("report_to_employee_no"),
            department_id=_optional_uuid(payload.get("department_id"), "department_id"),
            start_time=self._optional_datetime(payload.get("start_time"), "start_time"),
            deadline=(
                datetime.fromisoformat(str(payload["deadline"]))
                if payload.get("deadline")
                else None
            ),
            estimated_hours=_decimal(payload.get("estimated_hours")),
            task_weight=int(payload.get("task_weight") or 3),
            deliverable=payload.get("deliverable"),
            acceptance_criteria=str(payload.get("acceptance_criteria") or ""),
            is_urgent=bool(payload.get("is_urgent", False)),
            report_cycle=payload.get("report_cycle"),
            participants=participants,
            extraction_record_ids=(extraction_id,),
        )
        task = TaskWorkflowService(self.uow_factory, clock=self.clock).create_task_draft(command)
        return task

    def suggest_task_plan(
        self,
        actor: str,
        task_id: UUID,
        *,
        instructions: str | None = None,
    ) -> dict[str, object]:
        task = self.session.get(Task, task_id)
        if task is None:
            raise EntityNotFoundError("task was not found")
        if task.main_assignee_employee_no != actor:
            raise PermissionDeniedError("actor must be the task main assignee")
        if task.status != "in_progress":
            raise BusinessValidationError("task planning requires an accepted task")

        extraction = self._latest_confirmed_extraction(task.task_id)
        payload = self._task_payload_for_decomposition(task)
        if extraction is not None:
            payload = {
                **self._normalize_extraction_payload(extraction.extracted_json),
                **payload,
            }
        if instructions and instructions.strip():
            payload["planning_instructions"] = instructions.strip()
        if self._uses_structured_agent_context():
            now = self.clock()
            payload.update(
                {
                    "mode": "task_decomposition",
                    "currentUser": self._agent_user(self.session.get(User, actor)),
                    "candidateUsers": self._agent_candidate_users(),
                    "performanceMetrics": self._agent_performance_metrics(),
                    "rules": {
                        "timezone": self.agent_timezone,
                        "now": self._agent_now(now),
                        "nodeCountMin": 5,
                        "nodeCountMax": 10,
                    },
                }
            )

        decomp = self.decomposition_provider.decompose(payload)
        return self._planning_suggestion_response(actor, task, decomp)

    @staticmethod
    def _normalize_extraction_payload(payload: Mapping[str, object]) -> dict[str, object]:
        normalized: dict[str, object] = {}
        task_draft = payload.get("taskDraft") or payload.get("task_draft")
        if isinstance(task_draft, Mapping):
            normalized.update(TaskIntakeService._normalize_extraction_payload(task_draft))
        for key, value in payload.items():
            normalized[INTAKE_FIELD_ALIASES.get(str(key), str(key))] = _json_value(value)
        collaborators = normalized.get("collaborator_employee_nos")
        if collaborators is not None and "collaborators" not in normalized:
            normalized["collaborators"] = collaborators
        return normalized

    @staticmethod
    def _normalize_node_payload(payload: Mapping[str, object]) -> dict[str, object]:
        return {
            INTAKE_NODE_ALIASES.get(str(key), str(key)): _json_value(value)
            for key, value in payload.items()
        }

    @staticmethod
    def _normalize_dependency_payload(payload: Mapping[str, object]) -> dict[str, object]:
        return {
            INTAKE_DEPENDENCY_ALIASES.get(str(key), str(key)): _json_value(value)
            for key, value in payload.items()
        }

    @staticmethod
    def _sequence(value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, (str, bytes, bytearray)):
            return [value]
        if isinstance(value, Sequence):
            return list(value)
        return []

    @staticmethod
    def _optional_datetime(value: object | None, field_name: str) -> datetime | None:
        if value is None or value == "":
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise BusinessValidationError(f"{field_name} must be a valid datetime") from exc

    @staticmethod
    def _dependency_from_reference(
        predecessor: object,
        successor_id: UUID,
        node_ids: Sequence[UUID],
        node_refs: Mapping[str, UUID],
        dependency_type: str,
    ) -> TaskNodeDependencyDraft | None:
        predecessor_id: UUID | None = None
        if isinstance(predecessor, int):
            if 0 <= predecessor < len(node_ids):
                predecessor_id = node_ids[predecessor]
        else:
            reference = str(predecessor)
            if reference.isdigit():
                index = int(reference)
                if 0 <= index < len(node_ids):
                    predecessor_id = node_ids[index]
            predecessor_id = predecessor_id or node_refs.get(reference)
        if predecessor_id is None:
            return None
        return TaskNodeDependencyDraft(predecessor_id, successor_id, dependency_type)

    def _latest_extraction(self, input_id: UUID) -> AIExtractionRecord | None:
        statement = (
            select(AIExtractionRecord)
            .where(AIExtractionRecord.input_id == input_id)
            .order_by(AIExtractionRecord.extraction_id.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def _latest_confirmed_extraction(self, task_id: UUID) -> AIExtractionRecord | None:
        statement = (
            select(AIExtractionRecord)
            .where(AIExtractionRecord.task_id == task_id)
            .order_by(AIExtractionRecord.confirmed_at.desc().nulls_last())
            .limit(1)
        )
        return self.session.scalar(statement)

    def _task_payload_for_decomposition(self, task: Task) -> dict[str, object]:
        participants = [
            participant.employee_no
            for participant in self.session.scalars(
                select(TaskParticipant)
                .where(
                    TaskParticipant.task_id == task.task_id,
                    TaskParticipant.participant_role == "collaborator",
                )
                .order_by(TaskParticipant.employee_no)
            ).all()
        ]
        return {
            "task_id": str(task.task_id),
            "task_name": task.task_name,
            "task_description": task.task_description,
            "task_goal": task.task_goal,
            "task_source": task.task_source,
            "main_assignee_employee_no": task.main_assignee_employee_no,
            "report_to_employee_no": task.report_to_employee_no,
            "reviewer_employee_no": task.reviewer_employee_no,
            "department_id": str(task.department_id) if task.department_id else None,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "estimated_hours": (
                str(task.estimated_hours) if task.estimated_hours is not None else None
            ),
            "task_weight": task.task_weight,
            "deliverable": task.deliverable,
            "acceptance_criteria": task.acceptance_criteria,
            "is_urgent": task.is_urgent,
            "report_cycle": task.report_cycle,
            "collaborators": participants,
        }

    def _planning_suggestion_response(
        self,
        actor: str,
        task: Task,
        decomp: Mapping[str, object],
    ) -> dict[str, object]:
        raw_nodes = self._sequence(decomp.get("nodes"))
        nodes: list[dict[str, object]] = []
        permission = PermissionScopeService(self.session, clock=self.clock)
        task_people = {
            task.creator_employee_no,
            task.main_assignee_employee_no,
            task.report_to_employee_no,
            task.reviewer_employee_no,
            *(
                participant.employee_no
                for participant in self.session.scalars(
                    select(TaskParticipant).where(TaskParticipant.task_id == task.task_id)
                ).all()
            ),
        } - {None}
        for index, node_payload in enumerate(raw_nodes, start=1):
            if not isinstance(node_payload, Mapping):
                raise BusinessValidationError("decomposition nodes must be objects")
            normalized = self._normalize_node_payload(node_payload)
            client_node_id = str(normalized.get("client_node_id") or f"draft-node-{index}")
            suggested_owner = normalized.get("owner_employee_no")
            suggested_owner_text = (
                str(suggested_owner)
                if isinstance(suggested_owner, str)
                and (
                    suggested_owner in task_people
                    or permission.can_assign_employee(actor, suggested_owner)
                )
                else None
            )
            nodes.append(
                {
                    "client_node_id": client_node_id,
                    "node_order": int(normalized.get("node_order") or index),
                    "node_name": str(normalized.get("node_name") or f"节点 {index}").strip(),
                    "action_detail": normalized.get("action_detail"),
                    "tools_or_materials": normalized.get("tools_or_materials"),
                    "suggested_owner_employee_no": suggested_owner_text,
                    "planned_start_time": self._optional_datetime(
                        normalized.get("planned_start_time"), "planned_start_time"
                    ),
                    "planned_deadline": self._optional_datetime(
                        normalized.get("planned_deadline"), "planned_deadline"
                    ),
                    "estimated_hours": _decimal(normalized.get("estimated_hours")),
                    "deliverable": normalized.get("deliverable"),
                    "acceptance_criteria": normalized.get("acceptance_criteria"),
                    "dependencies": [
                        str(item) for item in self._sequence(normalized.get("dependencies"))
                    ],
                    "enabled": True,
                }
            )
        dependencies: list[dict[str, object]] = []
        seen: set[tuple[str, str, str]] = set()
        for index, node_payload in enumerate(raw_nodes):
            if not isinstance(node_payload, Mapping):
                continue
            normalized = self._normalize_node_payload(node_payload)
            successor = str(normalized.get("client_node_id") or f"draft-node-{index + 1}")
            for predecessor in self._sequence(normalized.get("dependencies")):
                predecessor_ref = self._dependency_reference_to_client_id(
                    predecessor, index, raw_nodes
                )
                if predecessor_ref is None:
                    continue
                key = (predecessor_ref, successor, "finish_to_start")
                if key not in seen:
                    seen.add(key)
                    dependencies.append(
                        {
                            "predecessor_client_node_id": predecessor_ref,
                            "successor_client_node_id": successor,
                            "dependency_type": "finish_to_start",
                            "reason": None,
                        }
                    )
        for dependency_payload in self._sequence(decomp.get("dependencies")):
            if not isinstance(dependency_payload, Mapping):
                continue
            normalized = self._normalize_dependency_payload(dependency_payload)
            predecessor = normalized.get("predecessor_client_node_id")
            successor = normalized.get("successor_client_node_id")
            dependency_type = str(normalized.get("dependency_type") or "finish_to_start")
            if predecessor is None or successor is None:
                continue
            key = (str(predecessor), str(successor), dependency_type)
            if key in seen:
                continue
            seen.add(key)
            dependencies.append(
                {
                    "predecessor_client_node_id": str(predecessor),
                    "successor_client_node_id": str(successor),
                    "dependency_type": dependency_type,
                    "reason": normalized.get("reason"),
                }
            )
        return {
            "task_id": task.task_id,
            "suggested_nodes": nodes,
            "suggested_dependencies": dependencies,
        }

    def _dependency_reference_to_client_id(
        self,
        predecessor: object,
        current_index: int,
        raw_nodes: Sequence[object],
    ) -> str | None:
        if isinstance(predecessor, int):
            return self._client_id_at_index(predecessor, raw_nodes)
        reference = str(predecessor)
        if reference.isdigit():
            by_index = self._client_id_at_index(int(reference), raw_nodes)
            if by_index is not None:
                return by_index
        return reference or None

    def _client_id_at_index(self, index: int, raw_nodes: Sequence[object]) -> str | None:
        if not 0 <= index < len(raw_nodes):
            return None
        item = raw_nodes[index]
        if not isinstance(item, Mapping):
            return None
        normalized = self._normalize_node_payload(item)
        return str(normalized.get("client_node_id") or f"draft-node-{index + 1}")

    def _require_active_user(self, actor: str) -> User:
        user = self.session.get(User, actor)
        if user is None or user.status != "active":
            raise PermissionDeniedError("actor is not active")
        return user

    def _get_owned_task_input(self, actor: str, input_id: UUID, *, action: str) -> TaskInput:
        self._require_active_user(actor)
        task_input = self.session.get(TaskInput, input_id)
        if task_input is None:
            raise EntityNotFoundError("task input was not found")
        self._require_task_input_owner(actor, task_input, action=action)
        return task_input

    @staticmethod
    def _require_task_input_owner(
        actor: str,
        task_input: TaskInput,
        *,
        action: str = "access",
    ) -> None:
        if task_input.submitted_by_employee_no != actor:
            raise PermissionDeniedError(f"actor cannot {action} this task input")

    def _source_text(self, task_input: TaskInput) -> str:
        text = _required_text(task_input.asr_text or task_input.raw_text, "raw_text")
        self._validate_input_length(text)
        return text

    @staticmethod
    def _validate_input_length(text: str) -> None:
        if len(text) > INTAKE_TEXT_MAX_LENGTH:
            raise BusinessValidationError("raw_text must be at most 4000 characters")

    def _run_extraction(
        self,
        text: str,
        *,
        context: Mapping[str, object] | None,
    ) -> dict[str, object]:
        try:
            extracted = self.extraction_provider.extract(text, context=context)
        except RuntimeError as exc:
            message = str(exc)
            if "429" in message:
                raise BusinessValidationError("AI provider is rate limited; retry later") from exc
            raise BusinessValidationError(
                "AI extraction is temporarily unavailable; retry later"
            ) from exc
        except (TimeoutError, ValueError, KeyError, TypeError) as exc:
            raise BusinessValidationError(
                "AI extraction response was invalid; retry later"
            ) from exc
        return self._validated_extraction_result(extracted)

    def _validated_extraction_result(self, extracted: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(extracted, Mapping):
            raise BusinessValidationError("AI extraction response was invalid")
        raw_payload = extracted.get("extracted_json")
        if not isinstance(raw_payload, Mapping):
            raise BusinessValidationError("AI extraction response was invalid")
        payload = {
            str(key): _json_value(value)
            for key, value in raw_payload.items()
            if str(key) in INTAKE_ALLOWED_FIELDS
        }
        # Feature 05 intake is task-level only. Node/dependency planning belongs to Feature 07.
        payload.pop("estimated_hours", None)
        payload.pop("nodes", None)
        payload.pop("dependencies", None)
        missing = self._field_list(extracted.get("missing_fields"))
        low_confidence = self._field_list(extracted.get("low_confidence_fields"))
        for field in ("estimated_hours", "nodes", "dependencies"):
            if field == "estimated_hours":
                while field in missing:
                    missing.remove(field)
                while field in low_confidence:
                    low_confidence.remove(field)
        self._validate_extracted_people(payload, missing, low_confidence)
        self._validate_extracted_dates(payload, missing, low_confidence)
        self._validate_task_weight(payload, missing, low_confidence)
        questions = self._field_list(extracted.get("confirm_questions"), limit=10)
        return {
            "extracted_json": payload,
            "missing_fields": list(dict.fromkeys(missing)),
            "low_confidence_fields": list(dict.fromkeys(low_confidence)),
            "confirm_questions": questions,
            "confidence_score": _decimal(extracted.get("confidence_score"), default=Decimal("0")),
        }

    @staticmethod
    def _field_list(value: object, *, limit: int = 50) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (str, bytes, bytearray)):
            return [str(value)[:200]]
        if not isinstance(value, Sequence):
            return []
        return [str(item)[:200] for item in value[:limit] if str(item).strip()]

    def _validate_extracted_people(
        self,
        payload: dict[str, object],
        missing: list[str],
        low_confidence: list[str],
    ) -> None:
        for field in INTAKE_EMPLOYEE_FIELDS:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            resolved = self._resolve_employee_reference(value.strip())
            if resolved is None:
                payload[field] = None
                missing.append(field)
                low_confidence.append(field)
            else:
                payload[field] = resolved
        collaborators = payload.get("collaborators")
        if isinstance(collaborators, Sequence) and not isinstance(
            collaborators, (str, bytes, bytearray)
        ):
            valid_collaborators: list[str] = []
            for employee_no in collaborators:
                resolved = self._resolve_employee_reference(str(employee_no).strip())
                if resolved is not None:
                    valid_collaborators.append(resolved)
            payload["collaborators"] = valid_collaborators

    def _resolve_employee_reference(self, reference: str) -> str | None:
        user = self.session.get(User, reference)
        if user is not None and user.status == "active":
            return user.employee_no
        statement = (
            select(User)
            .where(User.status == "active", User.name == reference)
            .order_by(User.employee_no)
            .limit(2)
        )
        matches = list(self.session.scalars(statement).all())
        if len(matches) == 1:
            return matches[0].employee_no
        return None

    def _validate_extracted_dates(
        self,
        payload: dict[str, object],
        missing: list[str],
        low_confidence: list[str],
    ) -> None:
        for field in INTAKE_DATE_FIELDS:
            value = payload.get(field)
            if value in (None, ""):
                continue
            try:
                datetime.fromisoformat(str(value))
            except ValueError:
                payload[field] = None
                missing.append(field)
                low_confidence.append(field)

    @staticmethod
    def _validate_task_weight(
        payload: dict[str, object],
        missing: list[str],
        low_confidence: list[str],
    ) -> None:
        value = payload.get("task_weight")
        if value in (None, ""):
            return
        try:
            weight = int(value)
        except (TypeError, ValueError):
            payload["task_weight"] = None
            missing.append("task_weight")
            low_confidence.append("task_weight")
            return
        if not 1 <= weight <= 5:
            payload["task_weight"] = None
            missing.append("task_weight")
            low_confidence.append("task_weight")
            return
        payload["task_weight"] = weight

    def _uses_structured_agent_context(self) -> bool:
        return bool(getattr(self.extraction_provider, "uses_structured_context", False))

    @staticmethod
    def _legacy_clarification_context(
        previous: AIExtractionRecord | None,
        answers: Mapping[str, object],
    ) -> dict[str, object]:
        context = dict(previous.extracted_json) if previous is not None else {}
        context.update(dict(answers))
        return context

    def _agent_context(
        self,
        actor: str,
        *,
        input_id: UUID,
        input_type: str,
        raw_text: str | None,
        asr_text: str | None,
        source_channel: str,
        now: datetime,
        previous: AIExtractionRecord | None = None,
        answers: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        user = self.session.get(User, actor)
        return {
            "input": {
                "inputId": str(input_id),
                "inputType": input_type,
                "rawText": raw_text or "",
                "asrText": asr_text or "",
                "attachmentTexts": [],
                "sourceChannel": source_channel,
            },
            "currentUser": self._agent_user(user),
            "candidateUsers": self._agent_candidate_users(),
            "performanceMetrics": self._agent_performance_metrics(),
            "rules": {
                "timezone": self.agent_timezone,
                "now": self._agent_now(now),
                "nodeCountMin": 5,
                "nodeCountMax": 10,
            },
            "previousExtraction": previous.extracted_json if previous is not None else None,
            "answers": _json_value(answers or {}),
        }

    def _agent_candidate_users(self) -> list[dict[str, object]]:
        statement = (
            select(User)
            .where(User.status == "active")
            .order_by(User.employee_no)
            .limit(100)
        )
        return [self._agent_user(user) for user in self.session.scalars(statement).all()]

    def _agent_performance_metrics(self) -> list[dict[str, object]]:
        statement = (
            select(PerformanceMetric)
            .where(PerformanceMetric.status == "active")
            .order_by(PerformanceMetric.business_unit, PerformanceMetric.metric_name)
            .limit(100)
        )
        metrics: list[dict[str, object]] = []
        for metric in self.session.scalars(statement).all():
            metrics.append(
                {
                    "metricId": str(metric.metric_id),
                    "metricType": metric.metric_type,
                    "businessUnit": metric.business_unit,
                    "metricName": metric.metric_name,
                    "definitionFormula": metric.definition_formula,
                    "targetValue": metric.target_value,
                }
            )
        return metrics

    @staticmethod
    def _agent_user(user: User | None) -> dict[str, object]:
        if user is None:
            return {}
        department = getattr(user, "department", None)
        profile = getattr(user, "employee_profile", None)
        return {
            "employeeNo": user.employee_no,
            "name": user.name,
            "departmentId": str(user.department_id) if user.department_id is not None else None,
            "departmentName": getattr(department, "department_name", None),
            "position": user.position,
            "orgLevel": user.org_level,
            "responsibilityText": getattr(profile, "responsibility_text", None),
            "skillTags": list(getattr(profile, "skill_tags", []) or []),
            "workloadScore": None,
            "workloadLevel": getattr(profile, "availability_status", None),
        }

    def _agent_now(self, now: datetime) -> str:
        try:
            timezone = ZoneInfo(self.agent_timezone)
        except ZoneInfoNotFoundError:
            timezone = UTC
        return now.astimezone(timezone).isoformat()


class PerformanceMetricService:
    """Deterministic task-to-KPI matching and creator confirmation."""

    def __init__(self, session: Session, clock=_now) -> None:
        self.session = session
        self.clock = clock

    def create_metric(self, actor: str, payload: Mapping[str, object]) -> PerformanceMetric:
        self._require_manager(actor)
        now = self.clock()
        metric = PerformanceMetric(
            metric_id=uuid4(),
            metric_type=str(payload["metric_type"]).strip(),
            period=payload.get("period"),
            business_unit=payload.get("business_unit"),
            sequence_no=payload.get("sequence_no"),
            dimension=payload.get("dimension"),
            metric_name=str(payload["metric_name"]).strip(),
            definition_formula=payload.get("definition_formula"),
            weight=payload.get("weight"),
            target_value=payload.get("target_value"),
            deliverable=payload.get("deliverable"),
            data_source=payload.get("data_source"),
            status=str(payload.get("status", "active")),
            created_at=now,
            updated_at=now,
        )
        self.session.add(metric)
        self.session.flush()
        _add_operation_log(
            self.session, actor=actor, action="performance_metric_created",
            object_type="performance_metric", object_id=metric.metric_id,
            after_data=self._metric_dict(metric), at=now,
        )
        self.session.commit()
        return metric

    def list_metrics(self, *, active_only: bool = True) -> list[PerformanceMetric]:
        statement = select(PerformanceMetric)
        if active_only:
            statement = statement.where(PerformanceMetric.status == "active")
        statement = statement.order_by(
            PerformanceMetric.business_unit, PerformanceMetric.metric_name, PerformanceMetric.metric_id
        )
        return list(self.session.scalars(statement).all())

    def suggest_matches(
        self,
        actor: str,
        task_id: UUID,
        limit: int = 10,
        *,
        expected_task_version: int | None = None,
    ) -> list[TaskPerformanceMatch]:
        task = self._locked_creator_task(actor, task_id, expected_task_version)
        metrics = self.list_metrics(active_only=True)
        now = self.clock()
        scorer = self._scorer(metrics)
        task_business_unit = self._task_business_unit(task)
        matches: list[TaskPerformanceMatch] = []
        for metric in metrics:
            match = self._score_match(task, metric, now, scorer, task_business_unit)
            existing = self.session.scalar(
                select(TaskPerformanceMatch).where(
                    TaskPerformanceMatch.task_id == task_id,
                    TaskPerformanceMatch.metric_id == metric.metric_id,
                )
            )
            if existing is None:
                self.session.add(match)
                current = match
            else:
                # A creator-confirmed relation is a business fact; recalculation updates only candidates.
                if not existing.is_confirmed:
                    self._copy_match(existing, match)
                current = existing
            self._attach_metric_projection(current, metric)
            matches.append(current)
        self.session.flush()
        matches.sort(key=lambda item: (-Decimal(item.total_score), str(item.metric_id)))
        _add_operation_log(
            self.session, actor=actor, action="performance_matches_suggested",
            object_type="task", object_id=task_id,
            after_data={"match_count": min(limit, len(matches)), "algorithm_version": "tfidf-char-ngram-v1"},
            at=now,
        )
        self.session.commit()
        return matches[:limit]

    def confirm_match(
        self,
        actor: str,
        task_id: UUID,
        performance_match_id: UUID,
        *,
        expected_task_version: int | None = None,
    ) -> TaskPerformanceMatch:
        task = self._locked_creator_task(actor, task_id, expected_task_version)
        row = self.session.get(TaskPerformanceMatch, performance_match_id)
        if row is None or row.task_id != task_id:
            raise EntityNotFoundError("performance match was not found")
        metric = self.session.get(PerformanceMetric, row.metric_id)
        if metric is None or metric.status != "active":
            raise BusinessValidationError("performance metric is no longer active")
        now = self.clock()
        previous = list(
            self.session.scalars(
                select(TaskPerformanceMatch).where(
                    TaskPerformanceMatch.task_id == task_id,
                    TaskPerformanceMatch.is_confirmed.is_(True),
                )
            ).all()
        )
        for current in previous:
            if current.performance_match_id != row.performance_match_id:
                current.is_confirmed = False
                current.confirmed_by_employee_no = None
                current.confirmed_at = None
                current.updated_at = now
        row.is_confirmed = True
        row.confirmed_by_employee_no = actor
        row.confirmed_at = now
        row.updated_at = now
        self._attach_metric_projection(row, metric)
        _add_operation_log(
            self.session, actor=actor, action="kpi_match_confirmed",
            object_type="task_performance_match", object_id=row.performance_match_id,
            before_data={"confirmed_match_ids": [str(item.performance_match_id) for item in previous]},
            after_data={"is_confirmed": True, "confirmed_by_employee_no": actor},
            at=now,
        )
        self.session.commit()
        return row

    def clear_confirmation(
        self, actor: str, task_id: UUID, *, expected_task_version: int | None = None
    ) -> list[TaskPerformanceMatch]:
        task = self._locked_creator_task(actor, task_id, expected_task_version)
        now = self.clock()
        rows = list(
            self.session.scalars(
                select(TaskPerformanceMatch).where(
                    TaskPerformanceMatch.task_id == task_id,
                    TaskPerformanceMatch.is_confirmed.is_(True),
                )
            ).all()
        )
        for row in rows:
            row.is_confirmed = False
            row.confirmed_by_employee_no = None
            row.confirmed_at = None
            row.updated_at = now
            metric = self.session.get(PerformanceMetric, row.metric_id)
            if metric is not None:
                self._attach_metric_projection(row, metric)
        _add_operation_log(
            self.session, actor=actor, action="kpi_match_cleared",
            object_type="task", object_id=task_id,
            before_data={"confirmed_match_ids": [str(item.performance_match_id) for item in rows]},
            after_data={"confirmed_match_ids": []},
            at=now,
        )
        self.session.commit()
        return rows

    def _locked_creator_task(
        self, actor: str, task_id: UUID, expected_task_version: int | None
    ) -> Task:
        task = self.session.scalar(select(Task).where(Task.task_id == task_id).with_for_update())
        if task is None:
            task = self.session.get(Task, task_id)
        if task is None:
            raise EntityNotFoundError("task was not found")
        if task.creator_employee_no != actor:
            raise PermissionDeniedError("only the task creator may manage performance matches")
        if expected_task_version is not None and task.task_version != expected_task_version:
            raise TaskVersionConflictError("task version does not match")
        return task

    def _task_business_unit(self, task: Task) -> str | None:
        department_id = task.department_id
        visited: set[UUID] = set()
        fallback: str | None = None
        while department_id is not None and department_id not in visited:
            visited.add(department_id)
            department = self.session.get(Department, department_id)
            if department is None or department.status != "active":
                break
            fallback = department.department_name
            if department.department_type in {"business_unit", "division", "事业部"}:
                return department.department_name
            department_id = department.parent_department_id
        return fallback

    def _scorer(self, metrics: Sequence[PerformanceMetric]) -> PerformanceMatchScorer:
        params = SystemParameterService(self.session).snapshot(
            ("performance_type_dictionary", "performance_business_unit_aliases")
        )
        documents = [
            " ".join(
                str(value or "")
                for value in (
                    metric.metric_type, metric.business_unit, metric.dimension, metric.metric_name,
                    metric.definition_formula, metric.target_value, metric.deliverable, metric.data_source,
                )
            )
            for metric in metrics
        ]
        type_dictionary = params.get("performance_type_dictionary")
        unit_aliases = params.get("performance_business_unit_aliases")
        return PerformanceMatchScorer(
            documents,
            type_dictionary=type_dictionary if isinstance(type_dictionary, Mapping) else None,
            business_unit_aliases=unit_aliases if isinstance(unit_aliases, Mapping) else None,
        )

    @staticmethod
    def _score_match(
        task: Task, metric: PerformanceMetric, now: datetime, scorer: PerformanceMatchScorer,
        task_business_unit: str | None,
    ) -> TaskPerformanceMatch:
        score = scorer.score(
            task_name=task.task_name, task_description=task.task_description, task_goal=task.task_goal,
            task_source=task.task_source, task_deliverable=task.deliverable,
            task_business_unit=task_business_unit, metric_type=metric.metric_type,
            metric_business_unit=metric.business_unit, metric_name=metric.metric_name,
            definition_formula=metric.definition_formula, target_value=metric.target_value,
            metric_deliverable=metric.deliverable, data_source=metric.data_source,
        )
        return TaskPerformanceMatch(
            performance_match_id=uuid4(), task_id=task.task_id, metric_id=metric.metric_id,
            type_score=score.type_score, business_unit_score=score.business_unit_score,
            metric_name_score=score.metric_name_score, definition_formula_score=score.definition_formula_score,
            deliverable_score=score.deliverable_score, total_score=score.total_score,
            match_level=score.match_level, match_reason=score.match_reason, is_confirmed=False,
            algorithm_version=score.algorithm_version, created_at=now, updated_at=now,
        )

    @staticmethod
    def _attach_metric_projection(row: TaskPerformanceMatch, metric: PerformanceMetric) -> None:
        row.metric_type = metric.metric_type
        row.period = metric.period
        row.business_unit = metric.business_unit
        row.metric_name = metric.metric_name
        row.definition_formula = metric.definition_formula

    @staticmethod
    def _copy_match(target: TaskPerformanceMatch, source: TaskPerformanceMatch) -> None:
        for key in (
            "type_score", "business_unit_score", "metric_name_score",
            "definition_formula_score", "deliverable_score", "total_score",
            "match_level", "match_reason", "algorithm_version", "updated_at",
        ):
            setattr(target, key, getattr(source, key))

    def _require_manager(self, actor: str) -> None:
        user = self.session.get(User, actor)
        if user is None or user.status != "active" or user.role_type not in {"admin", "manager"}:
            raise PermissionDeniedError("actor must be an active manager")

    @staticmethod
    def _metric_dict(metric: PerformanceMetric) -> dict[str, object]:
        return {
            "metric_type": metric.metric_type, "business_unit": metric.business_unit,
            "metric_name": metric.metric_name, "definition_formula": metric.definition_formula,
            "deliverable": metric.deliverable, "status": metric.status,
        }


class PlanningAnalyticsService:
    def __init__(self, session: Session, clock=_now) -> None:
        self.session = session
        self.clock = clock

    def calculate_workload(
        self,
        actor: str,
        employee_no: str,
        period_start: datetime,
        period_end: datetime,
    ) -> WorkloadSnapshot:
        self._assert_scope(actor, employee_no)
        period_start = _aware_utc(period_start)
        period_end = _aware_utc(period_end)
        if period_end < period_start:
            raise BusinessValidationError("period_end must not precede period_start")

        params = SystemParameterService(self.session).snapshot()
        profile = self.session.get(EmployeeProfile, employee_no)
        calendar_daily_capacity = _decimal(params["daily_capacity_hours"])
        daily_capacity = _decimal(
            profile.daily_capacity_hours if profile is not None else params["daily_capacity_hours"]
        )
        standard_count = int(
            profile.standard_task_count if profile is not None else params["standard_task_count"]
        )
        standard_weight = int(
            profile.standard_task_weight if profile is not None else params["standard_task_weight"]
        )
        emergency_tolerance = int(
            profile.emergency_tolerance_count
            if profile is not None
            else params["emergency_tolerance_count"]
        )
        if daily_capacity <= 0 or standard_count <= 0 or standard_weight <= 0:
            raise BusinessValidationError("workload parameters are incomplete")

        available_hours = working_hours_between(
            period_start, period_end, daily_capacity_hours=daily_capacity
        )
        if available_hours <= 0:
            raise BusinessValidationError("available work hours must be greater than zero")

        tasks = self._active_tasks_for_employee(
            employee_no, period_start=period_start, period_end=period_end
        )
        now = _aware_utc(self.clock())
        remaining_by_task = {
            task.task_id: calculate_remaining_hours(
                start_time=task.start_time, deadline=task.deadline, now=now,
                daily_capacity_hours=calendar_daily_capacity,
            )
            or Decimal("0")
            for task in tasks
        }
        overdue_by_task = {
            task.task_id: calculate_overdue_days(
                task.deadline, now, daily_capacity_hours=calendar_daily_capacity
            )
            for task in tasks
        }
        remaining_hours_sum = sum(remaining_by_task.values(), Decimal("0"))
        active_task_count = len(tasks)
        active_task_weight_sum = sum((Decimal(task.task_weight or 0) for task in tasks), Decimal("0"))
        urgent_task_count = sum(1 for task in tasks if task.is_urgent)
        blocked_tasks = [task for task in tasks if task.status == "blocked"]
        blocked_task_count = len(blocked_tasks)
        overdue_task_count = sum(1 for days in overdue_by_task.values() if days > 0)
        max_overdue_days = max(overdue_by_task.values(), default=0)

        if any(overdue_by_task.get(task.task_id, 0) > 0 for task in blocked_tasks):
            blocked_pressure = Decimal("100")
        elif blocked_tasks:
            blocked_pressure = Decimal("70")
        else:
            blocked_pressure = Decimal("0")
        overdue_pressure = calculate_overdue_pressure_score(max_overdue_days)
        blocked_overdue_pressure = max(blocked_pressure, overdue_pressure)
        standard_weight_capacity = Decimal(standard_count * standard_weight)
        hours_pressure = _ratio(remaining_hours_sum, available_hours)
        weight_pressure = _ratio(active_task_weight_sum, standard_weight_capacity)
        count_pressure = _ratio(Decimal(active_task_count), Decimal(standard_count))
        urgent_pressure = (
            _ratio(Decimal(urgent_task_count), Decimal(emergency_tolerance))
            if emergency_tolerance > 0
            else Decimal("100") if urgent_task_count else Decimal("0")
        )
        score = _bounded(
            Decimal("0.40") * hours_pressure
            + Decimal("0.25") * weight_pressure
            + Decimal("0.15") * count_pressure
            + Decimal("0.10") * urgent_pressure
            + Decimal("0.10") * blocked_overdue_pressure
        )
        level = calculate_workload_level(score)
        parameter_snapshot = {
            **params,
            "resolved_daily_capacity_hours": daily_capacity,
            "resolved_standard_task_count": standard_count,
            "resolved_standard_task_weight": standard_weight,
            "resolved_emergency_tolerance_count": emergency_tolerance,
            "calendar_daily_capacity_hours": calendar_daily_capacity,
        }
        snapshot = WorkloadSnapshot(
            employee_no=employee_no, period_start=period_start, period_end=period_end,
            remaining_hours_sum=remaining_hours_sum, available_hours=available_hours,
            active_task_count=active_task_count, active_task_weight_sum=active_task_weight_sum,
            urgent_task_count=urgent_task_count, blocked_task_count=blocked_task_count,
            overdue_task_count=overdue_task_count, hours_pressure=hours_pressure,
            weight_pressure=weight_pressure, count_pressure=count_pressure,
            urgent_pressure=urgent_pressure, blocked_overdue_pressure=blocked_overdue_pressure,
            workload_score=score, workload_level=level,
            parameter_snapshot=_json_value(parameter_snapshot), calculated_at=now,
        )
        self.session.add(snapshot)
        _add_operation_log(
            self.session, actor=actor, action="workload_calculated",
            object_type="employee_profile", object_id=employee_no,
            after_data={
                "workload_score": snapshot.workload_score,
                "workload_level": level,
                "task_count": active_task_count,
            },
            at=now,
        )
        self.session.commit()
        return snapshot

    def calculate_priorities(self, actor: str) -> list[TaskPriorityScore]:
        user = self.session.get(User, actor)
        if user is None or user.status != "active":
            raise PermissionDeniedError("actor is not active")
        params = SystemParameterService(self.session).snapshot()
        importance_threshold = _decimal(params["importance_threshold"])
        urgency_threshold = _decimal(params["urgency_threshold"])
        calendar_daily_capacity = _decimal(params["daily_capacity_hours"])
        tasks = self._visible_active_tasks(actor)
        now = _aware_utc(self.clock())
        scored_rows = [
            (
                self._priority_for_task(
                    task, now, importance_threshold=importance_threshold,
                    urgency_threshold=urgency_threshold, params=params,
                    calendar_daily_capacity=calendar_daily_capacity,
                ),
                task,
            )
            for task in tasks
        ]
        quadrant_order = {
            IMPORTANT_URGENT: 1, IMPORTANT_NOT_URGENT: 2,
            NOT_IMPORTANT_URGENT: 3, NOT_IMPORTANT_NOT_URGENT: 4,
        }
        scored_rows.sort(
            key=lambda item: (
                quadrant_order[item[0].priority_quadrant],
                item[0].remaining_hours if item[0].remaining_hours is not None else Decimal("999999"),
                -Decimal(item[1].task_weight or 0),
                item[0].task_created_at_snapshot,
                str(item[1].task_id),
            )
        )
        rows = [row for row, _ in scored_rows]
        for rank, row in enumerate(rows, start=1):
            row.sort_rank = rank
            self.session.add(row)
        _add_operation_log(
            self.session, actor=actor, action="priority_calculated",
            object_type="task_priority_score", object_id=actor,
            after_data={"score_count": len(rows)}, at=now,
        )
        self.session.commit()
        return rows

    def detect_conflicts(self, actor: str, employee_no: str | None = None) -> list[TaskConflict]:
        target = employee_no or actor
        self._assert_scope(actor, target)
        now = _aware_utc(self.clock())
        rows: list[TaskConflict] = []
        rows.extend(self._detect_work_hour(target, now))
        rows.extend(self._detect_deadline_concentration(target, now))
        rows.extend(self._detect_dependency_conflicts(target, now))
        rows.extend(self._detect_emergency_displacement(target, now))
        persisted = [self._upsert_conflict(row, actor, now) for row in rows]

        current_keys = {row.dedupe_key for row in persisted}
        existing_open = list(
            self.session.scalars(
                select(TaskConflict).where(
                    TaskConflict.employee_no == target, TaskConflict.status == "open"
                )
            ).all()
        )
        for old in existing_open:
            if old.dedupe_key in current_keys:
                continue
            old.status = "resolved"
            old.resolved_by_employee_no = actor
            old.resolution_note = "Recalculation found that this risk no longer exists."
            old.resolved_at = now

        _add_operation_log(
            self.session, actor=actor, action="conflicts_detected",
            object_type="task_conflict", object_id=target,
            after_data={"open_count": len(persisted), "resolved_count": len([r for r in existing_open if r.dedupe_key not in current_keys])},
            at=now,
        )
        self.session.commit()
        return persisted

    def resolve_conflict(
        self,
        actor: str,
        conflict_id: UUID,
        *,
        resolution_note: str,
        status: str = "resolved",
    ) -> TaskConflict:
        conflict = self.session.get(TaskConflict, conflict_id)
        if conflict is None:
            raise EntityNotFoundError("task conflict was not found")
        self._assert_scope(actor, conflict.employee_no)
        if status not in {"acknowledged", "resolved", "ignored"}:
            raise BusinessValidationError("conflict status is invalid")
        now = self.clock()
        before = {"status": conflict.status}
        conflict.status = status
        conflict.resolved_by_employee_no = actor
        conflict.resolution_note = _required_text(resolution_note, "resolution_note")
        conflict.resolved_at = now
        _add_operation_log(
            self.session,
            actor=actor,
            action=f"conflict_{status}",
            object_type="task_conflict",
            object_id=conflict.conflict_id,
            before_data=before,
            after_data={"status": status},
            at=now,
        )
        self.session.commit()
        return conflict

    def _assert_scope(self, actor: str, target_employee_no: str) -> None:
        if actor == target_employee_no:
            return
        actor_user = self.session.get(User, actor)
        target = self.session.get(User, target_employee_no)
        if actor_user is None or actor_user.status != "active" or target is None:
            raise PermissionDeniedError("actor cannot access this employee")
        if actor_user.role_type == "admin" or target.manager_employee_no == actor:
            return
        if any(
            scope.scope_type == "all_demo_data"
            for scope in PermissionScopeService(self.session, clock=self.clock)._active_scopes(
                actor, "view"
            )
        ):
            return
        raise PermissionDeniedError("actor cannot access this employee")

    def _active_tasks_for_employee(
        self,
        employee_no: str,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> list[Task]:
        statement = select(Task).where(
            Task.main_assignee_employee_no == employee_no,
            Task.status.in_(EXECUTION_TASK_STATUSES),
            Task.effective_at.is_not(None),
        )
        if period_start is not None and period_end is not None:
            statement = statement.where(
                or_(Task.start_time.is_(None), Task.start_time <= period_end),
                or_(Task.deadline.is_(None), Task.deadline >= period_start),
            )
        statement = statement.order_by(Task.deadline.asc().nulls_last(), Task.created_at, Task.task_id)
        return list(self.session.scalars(statement).all())

    def _visible_active_tasks(self, actor: str) -> list[Task]:
        permission = PermissionScopeService(self.session, clock=self.clock)
        return [
            task
            for task in self.session.scalars(
                select(Task)
                .where(Task.status.in_(EXECUTION_TASK_STATUSES), Task.effective_at.is_not(None))
                .order_by(Task.deadline.asc().nulls_last(), Task.created_at, Task.task_id)
                .limit(500)
            ).all()
            if permission.can_access_task(actor, task)
        ]

    def _blocked_count(self, employee_no: str, tasks: Sequence[Task]) -> int:
        task_ids = [task.task_id for task in tasks]
        if not task_ids:
            return 0
        active_issue = exists().where(
            TaskIssue.task_id == Task.task_id,
            TaskIssue.status.in_(("open", "processing")),
        )
        active_conflict = exists().where(
            TaskConflict.task_id == Task.task_id,
            TaskConflict.employee_no == employee_no,
            TaskConflict.status == "open",
        )
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.task_id.in_(task_ids), or_(active_issue, active_conflict))
            )
            or 0
        )

    def _priority_for_task(
        self,
        task: Task,
        now: datetime,
        *,
        importance_threshold: Decimal,
        urgency_threshold: Decimal,
        params: Mapping[str, object],
        calendar_daily_capacity: Decimal,
    ) -> TaskPriorityScore:
        task_weight_score = _bounded(Decimal(task.task_weight or 0) / Decimal("5") * Decimal("100"))
        match_score = self._confirmed_performance_score(task.task_id)
        level_score = self._report_to_level_score(task.report_to_level)
        importance = _bounded(
            Decimal("0.45") * task_weight_score
            + Decimal("0.35") * match_score
            + Decimal("0.20") * level_score
        )
        deadline = _aware_utc(task.deadline) if task.deadline is not None else None
        overdue = deadline is not None and now > deadline
        remaining = calculate_remaining_hours(
            start_time=task.start_time, deadline=task.deadline, now=now,
            daily_capacity_hours=calendar_daily_capacity,
        )
        overdue_day_count = calculate_overdue_days(
            task.deadline, now, daily_capacity_hours=calendar_daily_capacity
        )
        time_pressure = calculate_time_pressure_score(remaining, overdue=overdue)
        overdue_pressure = calculate_overdue_pressure_score(overdue_day_count)
        urgent_pressure = Decimal("100") if task.is_urgent else Decimal("0")
        urgency = _bounded(
            Decimal("0.60") * time_pressure
            + Decimal("0.25") * overdue_pressure
            + Decimal("0.15") * urgent_pressure
        )
        important = importance >= importance_threshold
        urgent = urgency >= urgency_threshold
        quadrant = (
            IMPORTANT_URGENT if important and urgent
            else IMPORTANT_NOT_URGENT if important
            else NOT_IMPORTANT_URGENT if urgent
            else NOT_IMPORTANT_NOT_URGENT
        )
        return TaskPriorityScore(
            task_id=task.task_id, task_weight_score=task_weight_score,
            performance_match_score=match_score, report_to_level_score=level_score,
            importance_score=importance, time_pressure_score=time_pressure,
            overdue_pressure_score=overdue_pressure, urgent_pressure_score=urgent_pressure,
            urgency_score=urgency, priority_quadrant=quadrant, remaining_hours=remaining,
            task_created_at_snapshot=task.created_at,
            explanation=_json_value({
                "parameter_snapshot": params,
                "overdue_days": overdue_day_count,
                "calendar_daily_capacity_hours": calendar_daily_capacity,
            }),
            calculated_at=now,
        )

    def _confirmed_performance_score(self, task_id: UUID) -> Decimal:
        row = self.session.scalar(
            select(TaskPerformanceMatch)
            .where(
                TaskPerformanceMatch.task_id == task_id,
                TaskPerformanceMatch.is_confirmed.is_(True),
            )
            .order_by(TaskPerformanceMatch.total_score.desc())
            .limit(1)
        )
        if row is None:
            return Decimal("0")
        if row.match_level == "strong":
            return Decimal("100")
        if row.match_level == "weak":
            return Decimal("50")
        return Decimal("0")

    @staticmethod
    def _report_to_level_score(level: str | None) -> Decimal:
        mapping = {
            "employee": 20,
            "staff": 20,
            "主管": 40,
            "manager": 50,
            "部门负责人": 65,
            "director": 75,
            "总监": 75,
            "vp": 90,
            "副总裁": 90,
            "president": 100,
            "总裁": 100,
        }
        return Decimal(mapping.get((level or "").casefold(), 50 if level else 0))

    def _detect_work_hour(self, employee_no: str, now: datetime) -> list[TaskConflict]:
        params = SystemParameterService(self.session).snapshot(
            ("daily_capacity_hours", "conflict_capacity_high_ratio")
        )
        daily_capacity = _decimal(params.get("daily_capacity_hours"), Decimal("8"))
        period_end = now + timedelta(days=7)
        capacity = working_hours_between(now, period_end, daily_capacity_hours=daily_capacity)
        if capacity <= 0:
            return []
        tasks = self._active_tasks_for_employee(employee_no, period_start=now, period_end=period_end)
        remaining = sum(
            (
                calculate_remaining_hours(
                    start_time=task.start_time, deadline=task.deadline, now=now,
                    daily_capacity_hours=daily_capacity,
                )
                or Decimal("0")
                for task in tasks
            ),
            Decimal("0"),
        )
        if not tasks or remaining <= capacity:
            return []
        ratio = remaining / capacity
        high_ratio = params.get("conflict_capacity_high_ratio")
        severity = "high" if high_ratio is not None and ratio >= _decimal(high_ratio) else "medium"
        task = min(tasks, key=lambda item: (_aware_utc(item.deadline) if item.deadline else datetime.max.replace(tzinfo=UTC), item.created_at))
        return [
            self._new_conflict(
                "work_hour", employee_no, task.task_id, None, None, severity,
                f"Active task time windows require {remaining}h against {capacity}h available capacity.",
                "Adjust assignments, scope, or deadlines.", now,
            )
        ]

    def _detect_deadline_concentration(self, employee_no: str, now: datetime) -> list[TaskConflict]:
        params = SystemParameterService(self.session).snapshot(
            ("deadline_conflict_window_hours", "deadline_conflict_min_task_count", "deadline_conflict_min_weight")
        )
        if not all(key in params for key in ("deadline_conflict_window_hours", "deadline_conflict_min_task_count", "deadline_conflict_min_weight")):
            return []
        window = timedelta(hours=float(_decimal(params["deadline_conflict_window_hours"])))
        min_count = int(_decimal(params["deadline_conflict_min_task_count"]))
        min_weight = int(_decimal(params["deadline_conflict_min_weight"]))
        tasks = [
            task for task in self._active_tasks_for_employee(employee_no)
            if task.deadline is not None and (task.task_weight or 0) >= min_weight
        ]
        rows: list[TaskConflict] = []
        for task in tasks:
            peers = [
                other for other in tasks
                if other.task_id != task.task_id
                and abs(_aware_utc(other.deadline) - _aware_utc(task.deadline)) <= window
            ]
            if len(peers) + 1 < min_count:
                continue
            related = min(peers, key=lambda item: (abs(_aware_utc(item.deadline) - _aware_utc(task.deadline)), str(item.task_id))) if peers else None
            rows.append(
                self._new_conflict(
                    "deadline_concentration", employee_no, task.task_id,
                    related.task_id if related else None, None, "medium",
                    "High-weight tasks are concentrated inside the configured deadline window.",
                    "Split deliverables or move one deadline.", now,
                )
            )
        return rows

    def _detect_dependency_conflicts(self, employee_no: str, now: datetime) -> list[TaskConflict]:
        lead_params = SystemParameterService(self.session).snapshot(("dependency_conflict_lead_hours",))
        lead = timedelta(hours=float(_decimal(lead_params["dependency_conflict_lead_hours"]))) if "dependency_conflict_lead_hours" in lead_params else timedelta(0)
        statement = (
            select(Task, TaskNode, TaskNodeDependency)
            .join(TaskNode, TaskNode.task_id == Task.task_id)
            .join(
                TaskNodeDependency,
                and_(
                    TaskNodeDependency.task_id == Task.task_id,
                    TaskNodeDependency.successor_node_id == TaskNode.node_id,
                ),
            )
            .where(
                Task.status.in_(EXECUTION_TASK_STATUSES),
                Task.effective_at.is_not(None),
                Task.main_assignee_employee_no == employee_no,
            )
        )
        rows: list[TaskConflict] = []
        for task, successor, dependency in self.session.execute(statement).all():
            predecessor = self.session.get(TaskNode, dependency.predecessor_node_id)
            if predecessor is None or predecessor.status == "completed":
                continue
            start_due = successor.planned_start_time is not None and _aware_utc(successor.planned_start_time) <= now + lead
            deadline_due = successor.planned_deadline is not None and _aware_utc(successor.planned_deadline) <= now + lead
            if not (start_due or deadline_due):
                continue
            rows.append(
                self._new_conflict(
                    "dependency", employee_no, task.task_id, None, successor.node_id, "high",
                    "A successor node is due to start while its predecessor is incomplete.",
                    "Complete or reschedule the predecessor before starting this node.", now,
                )
            )
        return rows

    def _detect_emergency_displacement(self, employee_no: str, now: datetime) -> list[TaskConflict]:
        tasks = self._active_tasks_for_employee(employee_no)
        urgent = [task for task in tasks if task.is_urgent]
        regular = [task for task in tasks if not task.is_urgent and task.deadline is not None]
        if not urgent or not regular:
            return []
        params = SystemParameterService(self.session).snapshot(("daily_capacity_hours",))
        daily_capacity = _decimal(params.get("daily_capacity_hours"), Decimal("8"))
        period_end = now + timedelta(days=1)
        capacity = working_hours_between(now, period_end, daily_capacity_hours=daily_capacity)
        urgent_window = sum(
            (
                calculate_remaining_hours(
                    start_time=task.start_time, deadline=task.deadline, now=now,
                    daily_capacity_hours=daily_capacity,
                )
                or Decimal("0")
                for task in urgent
            ),
            Decimal("0"),
        )
        latest_workload = self.session.scalar(
            select(WorkloadSnapshot)
            .where(WorkloadSnapshot.employee_no == employee_no)
            .order_by(WorkloadSnapshot.calculated_at.desc())
            .limit(1)
        )
        overloaded = latest_workload is not None and latest_workload.workload_level == "overloaded"
        if not overloaded and (capacity <= 0 or urgent_window <= capacity):
            return []
        impacted = min(regular, key=lambda task: _aware_utc(task.deadline))
        urgent_task = min(urgent, key=lambda task: (_aware_utc(task.deadline) if task.deadline else datetime.max.replace(tzinfo=UTC), str(task.task_id)))
        return [
            self._new_conflict(
                "emergency_displacement", employee_no, impacted.task_id, urgent_task.task_id, None,
                "high", "Urgent work pushes current capacity into overload or threatens an existing deadline.",
                "Confirm the priority tradeoff and adjust assignment, scope, or deadline.", now,
            )
        ]

    @staticmethod
    def _new_conflict(
        conflict_type: str,
        employee_no: str,
        task_id: UUID,
        related_task_id: UUID | None,
        node_id: UUID | None,
        severity: str,
        description: str,
        suggestion: str,
        now: datetime,
    ) -> TaskConflict:
        related = str(related_task_id) if related_task_id is not None else "-"
        node = str(node_id) if node_id is not None else "-"
        dedupe_key = f"{conflict_type}:{employee_no}:{task_id}:{related}:{node}"
        return TaskConflict(
            conflict_type=conflict_type,
            employee_no=employee_no,
            task_id=task_id,
            related_task_id=related_task_id,
            node_id=node_id,
            dedupe_key=dedupe_key,
            severity=severity,
            description=description,
            suggestion=suggestion,
            status="open",
            detected_at=now,
        )

    def _upsert_conflict(self, row: TaskConflict, actor: str, now: datetime) -> TaskConflict:
        existing = self.session.scalar(
            select(TaskConflict).where(TaskConflict.dedupe_key == row.dedupe_key).with_for_update()
        )
        if existing is None:
            self.session.add(row)
            return row
        if existing.status in {"ignored", "resolved"}:
            existing.status = "open"
            existing.resolved_by_employee_no = None
            existing.resolution_note = None
            existing.resolved_at = None
        existing.detected_at = now
        existing.severity = row.severity
        existing.description = row.description
        existing.suggestion = row.suggestion
        _add_operation_log(
            self.session,
            actor=actor,
            action="conflict_reopened",
            object_type="task_conflict",
            object_id=existing.conflict_id,
            after_data={"dedupe_key": existing.dedupe_key, "status": existing.status},
            at=now,
        )
        return existing


class WeComProvider(Protocol):
    def send(self, recipient_employee_no: str, title: str, content: str) -> str: ...


class FakeWeComProvider:
    def send(self, recipient_employee_no: str, title: str, content: str) -> str:
        return f"fake-wecom:{recipient_employee_no}:{abs(hash((title, content))) % 1000000}"


class ReminderNotificationService:
    def __init__(self, session: Session, provider: WeComProvider | None = None, clock=_now) -> None:
        self.session = session
        self.provider = provider or FakeWeComProvider()
        self.clock = clock

    def scan_reminders(self, actor: str) -> list[ReminderRule]:
        self._require_manager(actor)
        now = self.clock()
        tasks = list(
            self.session.scalars(
                select(Task)
                .where(Task.status.in_(ACTIVE_TASK_STATUSES))
                .order_by(Task.updated_at, Task.task_id)
            ).all()
        )
        rules: list[ReminderRule] = []
        for task in tasks:
            rules.extend(self._task_rules(task, now))
        for issue in self.session.scalars(
            select(TaskIssue).where(TaskIssue.status.in_(("open", "processing")))
        ).all():
            rules.append(
                self._rule(
                    task_id=issue.task_id,
                    node_id=issue.node_id,
                    issue_id=issue.issue_id,
                    reminder_type="issue_blocker",
                    recipient=issue.owner_employee_no,
                    next_trigger_at=now,
                    dedupe_key=f"issue:{issue.issue_id}:active",
                    repeat_rule="daily",
                    now=now,
                )
            )
        for issue in self.session.scalars(
            select(TaskConflict).where(TaskConflict.status == "open")
        ).all():
            rules.append(
                self._rule(
                    task_id=issue.task_id,
                    node_id=issue.node_id,
                    issue_id=None,
                    reminder_type="issue_blocker",
                    recipient=issue.employee_no,
                    next_trigger_at=now,
                    dedupe_key=f"conflict:{issue.conflict_id}:open",
                    repeat_rule=None,
                    now=now,
                )
            )
        persisted = [self._upsert_rule(rule) for rule in rules]
        _add_operation_log(
            self.session,
            actor=actor,
            action="reminders_scanned",
            object_type="reminder_rule",
            object_id=actor,
            after_data={"rule_count": len(persisted)},
            at=now,
        )
        self.session.commit()
        return persisted

    def create_due_notifications(self, actor: str) -> list[Notification]:
        self._require_manager(actor)
        now = self.clock()
        rules = list(
            self.session.scalars(
                select(ReminderRule).where(
                    ReminderRule.is_active.is_(True),
                    ReminderRule.next_trigger_at.is_not(None),
                    ReminderRule.next_trigger_at <= now,
                )
            ).all()
        )
        notifications: list[Notification] = []
        for rule in rules:
            occurrence_time = rule.next_trigger_at.isoformat() if rule.next_trigger_at else "now"
            occurrence = f"{rule.dedupe_key}:{occurrence_time}"
            existing = self.session.scalar(
                select(Notification).where(
                    Notification.dedupe_key == occurrence,
                    Notification.channel == "in_app",
                    Notification.recipient_employee_no == rule.recipient_employee_no,
                )
            )
            if existing is not None:
                notifications.append(existing)
                continue
            notification = Notification(
                reminder_rule_id=rule.reminder_rule_id,
                task_id=rule.task_id,
                issue_id=rule.issue_id,
                recipient_employee_no=rule.recipient_employee_no,
                channel="in_app",
                title=self._title(rule.reminder_type),
                content=f"{rule.reminder_type} reminder for task {rule.task_id}",
                send_status="pending",
                retry_count=0,
                dedupe_key=occurrence,
                created_at=now,
            )
            self.session.add(notification)
            notifications.append(notification)
            rule.last_triggered_at = now
            rule.next_trigger_at = self._next(rule.repeat_rule, now)
            if rule.repeat_rule is None:
                rule.is_active = False
        _add_operation_log(
            self.session,
            actor=actor,
            action="notifications_created",
            object_type="notification",
            object_id=actor,
            after_data={"notification_count": len(notifications)},
            at=now,
        )
        self.session.commit()
        return notifications

    def send_pending(self, actor: str, limit: int = 50) -> list[Notification]:
        self._require_manager(actor)
        now = self.clock()
        rows = list(
            self.session.scalars(
                select(Notification)
                .where(
                    Notification.send_status.in_(("pending", "failed")),
                    or_(Notification.retry_next_at.is_(None), Notification.retry_next_at <= now),
                    Notification.retry_count < 3,
                )
                .order_by(Notification.created_at, Notification.notification_id)
                .limit(limit)
            ).all()
        )
        for row in rows:
            try:
                row.wecom_message_id = self.provider.send(
                    row.recipient_employee_no, row.title, row.content
                )
                row.send_status = "sent"
                row.sent_at = now
                row.fail_reason = None
            except Exception as exc:  # pragma: no cover - fake provider does not fail
                row.retry_count += 1
                row.send_status = "failed"
                row.fail_reason = str(exc)
                row.retry_next_at = None if row.retry_count >= 3 else now + timedelta(minutes=5)
        _add_operation_log(
            self.session,
            actor=actor,
            action="notifications_sent",
            object_type="notification",
            object_id=actor,
            after_data={"attempt_count": len(rows)},
            at=now,
        )
        self.session.commit()
        return rows

    def list_notifications(self, actor: str, unread_only: bool = False) -> list[Notification]:
        statement = select(Notification).where(Notification.recipient_employee_no == actor)
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        statement = statement.order_by(Notification.created_at.desc(), Notification.notification_id)
        return list(self.session.scalars(statement).all())

    def mark_read(self, actor: str, notification_id: UUID) -> Notification:
        row = self.session.get(Notification, notification_id)
        if row is None:
            raise EntityNotFoundError("notification was not found")
        if row.recipient_employee_no != actor:
            raise PermissionDeniedError("actor cannot read this notification")
        row.read_at = self.clock()
        self.session.commit()
        return row

    def _task_rules(self, task: Task, now: datetime) -> list[ReminderRule]:
        recipient = task.main_assignee_employee_no or task.creator_employee_no
        rules: list[ReminderRule] = []
        if task.status == "pending_acceptance" and task.main_assignee_employee_no:
            rules.append(
                self._rule(
                    task_id=task.task_id,
                    node_id=None,
                    issue_id=None,
                    reminder_type="pending_acceptance",
                    recipient=task.main_assignee_employee_no,
                    next_trigger_at=now,
                    dedupe_key=f"task:{task.task_id}:pending_acceptance",
                    repeat_rule="daily",
                    now=now,
                )
            )
        if task.status == "pending_review":
            rules.append(
                self._rule(
                    task_id=task.task_id,
                    node_id=None,
                    issue_id=None,
                    reminder_type="completion_review",
                    recipient=task.reviewer_employee_no or task.creator_employee_no,
                    next_trigger_at=now,
                    dedupe_key=f"task:{task.task_id}:completion_review",
                    repeat_rule="daily",
                    now=now,
                )
            )
        if task.deadline is not None:
            deadline = _aware_utc(task.deadline)
            if deadline.date() == now.date():
                reminder_type = "due_today"
            elif deadline < now:
                reminder_type = "overdue"
            elif deadline <= now + timedelta(days=3):
                reminder_type = "due_soon"
            else:
                reminder_type = ""
            if reminder_type:
                rules.append(
                    self._rule(
                        task_id=task.task_id,
                        node_id=None,
                        issue_id=None,
                        reminder_type=reminder_type,
                        recipient=recipient,
                        next_trigger_at=now,
                        dedupe_key=f"task:{task.task_id}:{reminder_type}",
                        repeat_rule="daily" if reminder_type == "overdue" else None,
                        now=now,
                    )
                )
        if task.status == "in_progress" and task.report_cycle and task.accepted_at is not None:
            _, period_end = task_report_period(task.report_cycle, task.accepted_at, now)
            if period_end is not None and period_end <= now:
                latest = self.session.scalar(
                    select(TaskProgressReport)
                    .where(
                        TaskProgressReport.task_id == task.task_id,
                        TaskProgressReport.node_id.is_(None),
                    )
                    .order_by(TaskProgressReport.created_at.desc())
                    .limit(1)
                )
                report_type = (
                    "no_response"
                    if period_end + timedelta(days=1) <= now
                    and (latest is None or latest.created_at < period_end)
                    else "pending_report"
                    if latest is None or latest.created_at < period_end
                    else ""
                )
                if report_type:
                    rules.append(
                        self._rule(
                            task_id=task.task_id,
                            node_id=None,
                            issue_id=None,
                            reminder_type=report_type,
                            recipient=recipient,
                            next_trigger_at=now,
                            dedupe_key=f"task:{task.task_id}:{report_type}:{period_end.date()}",
                            repeat_rule="daily",
                            now=now,
                        )
                    )
        return rules

    @staticmethod
    def _rule(
        *,
        task_id: UUID | None,
        node_id: UUID | None,
        issue_id: UUID | None,
        reminder_type: str,
        recipient: str,
        next_trigger_at: datetime,
        dedupe_key: str,
        repeat_rule: str | None,
        now: datetime,
    ) -> ReminderRule:
        return ReminderRule(
            task_id=task_id,
            node_id=node_id,
            issue_id=issue_id,
            reminder_type=reminder_type,
            recipient_employee_no=recipient,
            trigger_time=next_trigger_at,
            next_trigger_at=next_trigger_at,
            repeat_rule=repeat_rule,
            dedupe_key=dedupe_key,
            is_active=True,
            created_at=now,
        )

    def _upsert_rule(self, rule: ReminderRule) -> ReminderRule:
        existing = self.session.scalar(
            select(ReminderRule).where(ReminderRule.dedupe_key == rule.dedupe_key)
        )
        if existing is None:
            self.session.add(rule)
            return rule
        existing.is_active = True
        existing.next_trigger_at = rule.next_trigger_at
        existing.trigger_time = rule.trigger_time
        existing.repeat_rule = rule.repeat_rule
        return existing

    @staticmethod
    def _next(repeat_rule: str | None, now: datetime) -> datetime | None:
        if repeat_rule == "daily":
            return datetime.combine(now.date() + timedelta(days=1), time(hour=9), UTC)
        return None

    @staticmethod
    def _title(reminder_type: str) -> str:
        return reminder_type.replace("_", " ").title()

    def _require_manager(self, actor: str) -> None:
        user = self.session.get(User, actor)
        if user is None or user.status != "active" or user.role_type not in {"admin", "manager"}:
            raise PermissionDeniedError("actor must be an active manager")


class ArchiveReuseService:
    def __init__(self, session: Session, uow_factory, clock=_now) -> None:
        self.session = session
        self.uow_factory = uow_factory
        self.clock = clock

    def archive_task(
        self,
        actor: str,
        task_id: UUID,
        *,
        summary: str | None,
        search_keywords: Sequence[str],
        review_result: str | None,
        risk_points: Sequence[str],
    ) -> TaskArchive:
        permission = PermissionScopeService(self.session, clock=self.clock)
        task = permission.assert_can_view_task(actor, task_id)
        if actor != task.creator_employee_no:
            user = self.session.get(User, actor)
            if user is None or user.role_type != "admin":
                raise PermissionDeniedError("actor cannot archive this task")
        existing = self.session.scalar(select(TaskArchive).where(TaskArchive.task_id == task_id))
        if existing is not None:
            return existing
        snapshot = self._snapshot(task)
        template = self._template(snapshot)
        actual_hours_total = self._actual_hours_total(task_id)
        now = self.clock()
        archive = TaskArchive(
            task_id=task_id,
            archive_snapshot=snapshot,
            source_status_snapshot=task.status,
            summary=summary or task.task_name,
            search_keywords=list(dict.fromkeys(search_keywords)) or self._keywords(snapshot),
            review_result=review_result,
            risk_points=list(risk_points),
            reusable_template=template,
            actual_hours_total=actual_hours_total,
            archived_by_employee_no=actor,
            archived_at=now,
        )
        self.session.add(archive)
        if task.status not in TERMINAL_TASK_STATUSES or task.status == "completed":
            task.status = TASK_ARCHIVED
            task.archived_at = now
            task.task_version += 1
            task.updated_at = now
        _add_operation_log(
            self.session,
            actor=actor,
            action="archive",
            object_type="task_archive",
            object_id=archive.archive_id,
            after_data={"task_id": task_id, "source_status": archive.source_status_snapshot},
            at=now,
        )
        self.session.commit()
        return archive

    def search(
        self,
        actor: str,
        *,
        keyword: str | None = None,
        creator: str | None = None,
        assignee: str | None = None,
        department_id: UUID | None = None,
        archived_from: datetime | None = None,
        archived_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, object]:
        permission = PermissionScopeService(self.session, clock=self.clock)
        statement = select(TaskArchive, Task).join(Task, TaskArchive.task_id == Task.task_id)
        if keyword:
            text = keyword.casefold()
            statement = statement.where(
                or_(
                    TaskArchive.summary.ilike(f"%{text}%"),
                    Task.task_name.ilike(f"%{text}%"),
                )
            )
        if creator:
            statement = statement.where(Task.creator_employee_no == creator)
        if assignee:
            statement = statement.where(Task.main_assignee_employee_no == assignee)
        if department_id is not None:
            statement = statement.where(Task.department_id == department_id)
        if archived_from is not None:
            statement = statement.where(TaskArchive.archived_at >= _aware_utc(archived_from))
        if archived_to is not None:
            statement = statement.where(TaskArchive.archived_at < _aware_utc(archived_to))
        rows = [
            archive
            for archive, task in self.session.execute(
                statement.order_by(TaskArchive.archived_at.desc(), TaskArchive.archive_id)
            ).all()
            if permission.can_access_task(actor, task)
        ]
        return {
            "items": rows[offset : offset + limit],
            "limit": limit,
            "offset": offset,
            "total": len(rows),
        }

    def similar(self, actor: str, task_id: UUID, limit: int = 5) -> list[TaskArchive]:
        task = PermissionScopeService(self.session, clock=self.clock).assert_can_view_task(
            actor, task_id
        )
        query_tokens = _tokens(_task_text(task))
        archives = self.search(actor, limit=500, offset=0)["items"]
        scored = [
            (archive, _text_score(query_tokens, _tokens(archive.summary, *archive.search_keywords)))
            for archive in archives
            if archive.task_id != task_id
        ]
        scored.sort(key=lambda item: (-item[1], str(item[0].archive_id)))
        return [archive for archive, score in scored[:limit] if score > 0]

    def reuse_archive(
        self,
        actor: str,
        archive_id: UUID,
        *,
        task_id: UUID | None = None,
        task_name: str | None = None,
        main_assignee_employee_no: str | None = None,
        deadline: datetime | None = None,
    ) -> Task:
        archive = self.session.get(TaskArchive, archive_id)
        if archive is None:
            raise EntityNotFoundError("task archive was not found")
        source_task = PermissionScopeService(self.session, clock=self.clock).assert_can_view_task(
            actor, archive.task_id
        )
        template = dict(archive.reusable_template or {})
        nodes: list[TaskNodeDraft] = []
        dependencies: list[TaskNodeDependencyDraft] = []
        source_to_new: dict[str, UUID] = {}
        for index, item in enumerate(template.get("nodes", []), start=1):
            node_id = uuid4()
            source_to_new[str(item.get("source_node_id"))] = node_id
            nodes.append(
                TaskNodeDraft(
                    node_id=node_id,
                    node_order=index,
                    node_name=str(item.get("node_name") or f"Node {index}"),
                    action_detail=item.get("action_detail"),
                    tools_or_materials=item.get("tools_or_materials"),
                    owner_employee_no=main_assignee_employee_no,
                    estimated_hours=_decimal(item.get("estimated_hours")),
                    deliverable=item.get("deliverable"),
                    acceptance_criteria=item.get("acceptance_criteria"),
                )
            )
        for item in template.get("dependencies", []):
            predecessor = source_to_new.get(str(item.get("predecessor_node_id")))
            successor = source_to_new.get(str(item.get("successor_node_id")))
            if predecessor is not None and successor is not None:
                dependencies.append(TaskNodeDependencyDraft(predecessor, successor))
        command = CreateTaskDraftCommand(
            task_id=task_id or uuid4(),
            task_name=task_name or f"Reuse: {source_task.task_name}",
            creator_employee_no=actor,
            operation_source="archive_reuse",
            task_description=template.get("task_description"),
            task_goal=template.get("task_goal"),
            task_source="archive_reuse",
            main_assignee_employee_no=main_assignee_employee_no,
            deadline=deadline,
            estimated_hours=_decimal(template.get("estimated_hours")),
            task_weight=int(template.get("task_weight") or 3),
            deliverable=template.get("deliverable"),
            acceptance_criteria=template.get("acceptance_criteria"),
            participants=(),
            nodes=tuple(nodes),
            dependencies=tuple(dependencies),
        )
        task = TaskWorkflowService(self.uow_factory, clock=self.clock).create_task_draft(command)
        _add_operation_log(
            self.session,
            actor=actor,
            action="reuse",
            object_type="task_archive",
            object_id=archive_id,
            after_data={"new_task_id": task.task_id},
        )
        self.session.commit()
        return task

    def _snapshot(self, task: Task) -> dict[str, object]:
        nodes = list(
            self.session.scalars(select(TaskNode).where(TaskNode.task_id == task.task_id)).all()
        )
        dependencies = list(
            self.session.scalars(
                select(TaskNodeDependency).where(TaskNodeDependency.task_id == task.task_id)
            ).all()
        )
        participants = list(
            self.session.scalars(
                select(TaskParticipant).where(TaskParticipant.task_id == task.task_id)
            ).all()
        )
        progress = list(
            self.session.scalars(
                select(TaskProgressReport).where(TaskProgressReport.task_id == task.task_id)
            ).all()
        )
        return _json_value(
            {
                "task": {
                    column.name: getattr(task, column.name) for column in Task.__table__.columns
                },
                "nodes": [
                    {
                        column.name: getattr(node, column.name)
                        for column in TaskNode.__table__.columns
                    }
                    for node in nodes
                ],
                "dependencies": [
                    {
                        column.name: getattr(dependency, column.name)
                        for column in TaskNodeDependency.__table__.columns
                    }
                    for dependency in dependencies
                ],
                "participants": [
                    {
                        column.name: getattr(participant, column.name)
                        for column in TaskParticipant.__table__.columns
                    }
                    for participant in participants
                ],
                "progress_reports": [
                    {
                        column.name: getattr(report, column.name)
                        for column in TaskProgressReport.__table__.columns
                    }
                    for report in progress
                ],
            }
        )

    @staticmethod
    def _template(snapshot: Mapping[str, object]) -> dict[str, object]:
        task = dict(snapshot.get("task", {}))
        return {
            "task_description": task.get("task_description"),
            "task_goal": task.get("task_goal"),
            "estimated_hours": task.get("estimated_hours"),
            "task_weight": task.get("task_weight"),
            "deliverable": task.get("deliverable"),
            "acceptance_criteria": task.get("acceptance_criteria"),
            "nodes": [
                {
                    "source_node_id": node.get("node_id"),
                    "node_name": node.get("node_name"),
                    "action_detail": node.get("action_detail"),
                    "tools_or_materials": node.get("tools_or_materials"),
                    "estimated_hours": node.get("estimated_hours"),
                    "deliverable": node.get("deliverable"),
                    "acceptance_criteria": node.get("acceptance_criteria"),
                }
                for node in snapshot.get("nodes", [])
                if isinstance(node, Mapping)
            ],
            "dependencies": [
                {
                    "predecessor_node_id": dependency.get("predecessor_node_id"),
                    "successor_node_id": dependency.get("successor_node_id"),
                }
                for dependency in snapshot.get("dependencies", [])
                if isinstance(dependency, Mapping)
            ],
        }

    @staticmethod
    def _keywords(snapshot: Mapping[str, object]) -> list[str]:
        task = snapshot.get("task", {})
        if not isinstance(task, Mapping):
            return []
        return sorted(
            _tokens(task.get("task_name"), task.get("task_description"), task.get("task_goal"))
        )

    def _actual_hours_total(self, task_id: UUID) -> Decimal:
        task_hours = self.session.scalar(select(Task.actual_hours).where(Task.task_id == task_id))
        node_hours = self.session.scalars(
            select(TaskNode.actual_hours).where(TaskNode.task_id == task_id)
        ).all()
        return max(
            _decimal(task_hours), sum((_decimal(value) for value in node_hours), Decimal("0"))
        )


class AuditQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_logs(
        self,
        actor: str,
        *,
        object_type: str | None = None,
        object_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        user = self.session.get(User, actor)
        if user is None or user.status != "active" or user.role_type != "admin":
            raise PermissionDeniedError("actor must be an active administrator")
        statement = select(OperationLog)
        if object_type is not None:
            statement = statement.where(OperationLog.object_type == object_type)
        if object_id is not None:
            statement = statement.where(OperationLog.object_id == object_id)
        statement = statement.order_by(
            OperationLog.created_at.desc(), OperationLog.operation_log_id
        )
        rows = list(self.session.scalars(statement).all())
        return {
            "items": rows[offset : offset + limit],
            "limit": limit,
            "offset": offset,
            "total": len(rows),
        }
