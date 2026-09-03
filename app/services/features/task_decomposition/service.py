"""
Feature: Assignee acceptance and AI decomposition lifecycle.

Responsibilities:
- Accept only by the main assignee and create one effective decomposition attempt.
- Execute/validate AI output, atomically persist nodes/dependencies/reminders, and activate the task.
- Persist failure/retry state and reject stale or invalidated results.

Does not own: HTTP parsing, raw SQL, or provider transport implementation.
Plan task: DEV-09.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, UTC
from typing import Protocol
from uuid import UUID, uuid4

from app.db.unit_of_work import UnitOfWork
from app.models import (
    Notification,
    OperationLog,
    Task,
    TaskDecompositionRecord,
    TaskNode,
    TaskNodeDependency,
    TaskStatusLog,
)
from app.services.clock import utc_now
from app.services.dependency_graph import validate_dependency_graph
from app.services.errors import (
    BusinessValidationError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    PermissionDeniedError,
    TaskVersionConflictError,
)
from app.services.features.notifications import (
    emit_node_assignment_notification,
    schedule_node_execution_reminders,
)


class DecompositionProvider(Protocol):
    def decompose(self, extracted: Mapping[str, object]) -> dict[str, object]: ...


class _UnavailableProvider:
    def decompose(self, extracted: Mapping[str, object]) -> dict[str, object]:
        raise RuntimeError("AI decomposition provider is not configured")


class TaskDecompositionService:
    """Authoritative V1.1 accept/decompose/retry workflow."""

    def __init__(
        self,
        uow_factory,
        *,
        provider: DecompositionProvider | None = None,
        clock=utc_now,
        model_name: str | None = None,
        model_version: str | None = None,
        prompt_version: str = "task-decomposition-v1",
    ) -> None:
        self._uow_factory = uow_factory
        self._provider = provider or _UnavailableProvider()
        self._clock = clock
        self._model_name = model_name
        self._model_version = model_version
        self._prompt_version = prompt_version

    @staticmethod
    def _now(clock) -> datetime:
        value = clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise BusinessValidationError("clock must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _lock_task(uow: UnitOfWork, task_id: UUID, expected_version: int) -> Task:
        task = uow.tasks.get_by_id_for_update(task_id)
        if task is None:
            raise EntityNotFoundError("task was not found")
        if task.task_version != expected_version:
            raise TaskVersionConflictError("task version does not match")
        return task

    @staticmethod
    def _require_assignee(task: Task, actor: str) -> None:
        if task.main_assignee_employee_no != actor:
            raise PermissionDeniedError("actor must be the task main assignee")

    @staticmethod
    def _snapshot(uow: UnitOfWork, task: Task) -> dict[str, object]:
        participant_nos = sorted(
            {
                participant.employee_no
                for participant in uow.tasks.list_participants(task.task_id)
            }
            | ({task.main_assignee_employee_no} if task.main_assignee_employee_no else set())
        )
        return {
            "taskId": str(task.task_id),
            "taskName": task.task_name,
            "taskDescription": task.task_description,
            "taskGoal": task.task_goal,
            "taskSource": task.task_source,
            "mainAssigneeEmployeeNo": task.main_assignee_employee_no,
            "reportToEmployeeNo": task.report_to_employee_no,
            "reviewerEmployeeNo": task.reviewer_employee_no,
            "departmentId": str(task.department_id) if task.department_id else None,
            "startTime": task.start_time.isoformat() if task.start_time else None,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "taskWeight": task.task_weight,
            "deliverable": task.deliverable,
            "acceptanceCriteria": task.acceptance_criteria,
            "isUrgent": task.is_urgent,
            "reportCycle": task.report_cycle,
            "participantEmployeeNos": participant_nos,
            "rules": {
                "nodeCountMin": 5,
                "nodeCountMax": 10,
                "forbidEstimatedHours": True,
                "ownerMustBeParticipant": True,
            },
        }

    @staticmethod
    def _append_status_log(
        uow: UnitOfWork,
        task: Task,
        *,
        from_status: str,
        to_status: str,
        action: str,
        actor: str,
        now: datetime,
        business_ref_id: UUID | None = None,
    ) -> None:
        uow.task_status_logs.add(
            TaskStatusLog(
                task_id=task.task_id,
                from_status=from_status,
                to_status=to_status,
                action_type=action,
                operator_employee_no=actor,
                target_employee_no=task.main_assignee_employee_no,
                task_version=task.task_version,
                business_ref_type="task_decomposition" if business_ref_id else None,
                business_ref_id=business_ref_id,
                operation_source="rest_api",
                created_at=now,
            )
        )
        uow.session.add(
            OperationLog(
                operator_employee_no=actor,
                action=action,
                object_type="task",
                object_id=str(task.task_id),
                before_data={"status": from_status, "taskVersion": task.task_version - 1},
                after_data={"status": to_status, "taskVersion": task.task_version},
                result="success",
                created_at=now,
            )
        )

    @staticmethod
    def _notify(
        uow: UnitOfWork,
        task: Task,
        recipient: str | None,
        *,
        title: str,
        content: str,
        dedupe_key: str,
        now: datetime,
    ) -> None:
        if not recipient:
            return
        uow.session.add(
            Notification(
                task_id=task.task_id,
                recipient_employee_no=recipient,
                channel="in_app",
                title=title,
                content=content,
                send_status="pending",
                retry_count=0,
                dedupe_key=dedupe_key,
                created_at=now,
            )
        )

    def accept_task(
        self,
        task_id: UUID,
        actor: str,
        expected_task_version: int,
        *,
        idempotency_key: str | None = None,
    ) -> Task:
        key = (idempotency_key or f"accept:{task_id}:{expected_task_version}").strip()
        with self._uow_factory() as uow:
            cached = uow.task_decompositions.get_by_idempotency(task_id, key)
            if cached is not None:
                task = uow.tasks.get_by_id(task_id)
                if task is None:
                    raise EntityNotFoundError("task was not found")
                self._require_assignee(task, actor)
                return task
            task = self._lock_task(uow, task_id, expected_task_version)
            self._require_assignee(task, actor)
            if task.status not in {"pending_acceptance", "pending_accept"}:
                raise InvalidStateTransitionError("operation requires pending_accept task")
            if uow.task_decompositions.get_active_for_task(task_id) is not None:
                raise InvalidStateTransitionError("DECOMPOSITION_RUNNING")
            participant = uow.tasks.find_participant(task_id, actor, "assignee")
            if participant is None or not participant.is_primary:
                raise BusinessValidationError("primary assignee projection is missing")
            now = self._now(self._clock)
            previous = task.status
            task.status = "decomposing"
            task.accepted_at = now
            task.decomposition_status = "pending"
            task.effective_at = None
            task.task_version += 1
            task.updated_at = now
            participant.confirm_status = "accepted"
            participant.confirmed_at = now
            record = TaskDecompositionRecord(
                task_id=task.task_id,
                triggered_by_employee_no=actor,
                trigger_type="accept",
                input_snapshot=self._snapshot(uow, task),
                status="pending",
                task_version=task.task_version,
                idempotency_key=key,
                model_name=self._model_name,
                model_version=self._model_version,
                prompt_version=self._prompt_version,
                retry_count=0,
                created_at=now,
            )
            uow.task_decompositions.add(record)
            task.latest_decomposition_id = record.decomposition_id
            self._append_status_log(
                uow, task, from_status=previous, to_status="decomposing",
                action="task_accepted_decomposition_started", actor=actor, now=now,
                business_ref_id=record.decomposition_id,
            )
            uow.commit()
            return task

    def retry(
        self,
        task_id: UUID,
        actor: str,
        expected_task_version: int,
        *,
        idempotency_key: str | None = None,
    ) -> Task:
        key = (idempotency_key or f"retry:{task_id}:{expected_task_version}").strip()
        with self._uow_factory() as uow:
            cached = uow.task_decompositions.get_by_idempotency(task_id, key)
            if cached is not None:
                task = uow.tasks.get_by_id(task_id)
                if task is None:
                    raise EntityNotFoundError("task was not found")
                self._require_assignee(task, actor)
                return task
            task = self._lock_task(uow, task_id, expected_task_version)
            self._require_assignee(task, actor)
            if task.status != "decomposition_failed":
                raise InvalidStateTransitionError("operation requires decomposition_failed task")
            if uow.task_decompositions.get_active_for_task(task_id) is not None:
                raise InvalidStateTransitionError("DECOMPOSITION_RUNNING")
            previous_record = uow.task_decompositions.get_latest_for_task(task_id)
            now = self._now(self._clock)
            task.status = "decomposing"
            task.decomposition_status = "pending"
            task.effective_at = None
            task.task_version += 1
            task.updated_at = now
            record = TaskDecompositionRecord(
                task_id=task.task_id,
                triggered_by_employee_no=actor,
                trigger_type="retry",
                input_snapshot=self._snapshot(uow, task),
                status="pending",
                task_version=task.task_version,
                idempotency_key=key,
                model_name=self._model_name,
                model_version=self._model_version,
                prompt_version=self._prompt_version,
                retry_count=(previous_record.retry_count + 1) if previous_record else 1,
                created_at=now,
            )
            uow.task_decompositions.add(record)
            task.latest_decomposition_id = record.decomposition_id
            self._append_status_log(
                uow, task, from_status="decomposition_failed", to_status="decomposing",
                action="task_decomposition_retried", actor=actor, now=now,
                business_ref_id=record.decomposition_id,
            )
            uow.commit()
            return task

    def get_latest(self, task_id: UUID, actor: str) -> TaskDecompositionRecord:
        with self._uow_factory() as uow:
            task = uow.tasks.get_by_id(task_id)
            if task is None:
                raise EntityNotFoundError("task was not found")
            participants = {p.employee_no for p in uow.tasks.list_participants(task_id)}
            if actor not in participants | {task.creator_employee_no, task.main_assignee_employee_no}:
                raise PermissionDeniedError("actor cannot view task decomposition")
            record = uow.task_decompositions.get_latest_for_task(task_id)
            if record is None:
                raise EntityNotFoundError("task decomposition was not found")
            return record

    def execute(self, task_id: UUID, decomposition_id: UUID, actor: str) -> TaskDecompositionRecord:
        with self._uow_factory() as uow:
            task = uow.tasks.get_by_id_for_update(task_id)
            if task is None:
                raise EntityNotFoundError("task was not found")
            self._require_assignee(task, actor)
            record = uow.task_decompositions.get_for_update(decomposition_id)
            if record is None or record.task_id != task_id:
                raise EntityNotFoundError("task decomposition was not found")
            self._require_current_attempt(task, record)
            if record.status == "succeeded":
                return record
            if record.status != "pending":
                raise InvalidStateTransitionError("decomposition attempt is not pending")
            now = self._now(self._clock)
            record.status = "running"
            record.started_at = now
            task.decomposition_status = "running"
            payload = dict(record.input_snapshot)
            uow.commit()
        try:
            result = self._provider.decompose(payload)
            return self.complete_result(task_id, decomposition_id, actor, result)
        except Exception as exc:
            return self.fail_attempt(task_id, decomposition_id, actor, exc)

    @staticmethod
    def _require_current_attempt(task: Task, record: TaskDecompositionRecord) -> None:
        if record.status == "invalidated":
            raise InvalidStateTransitionError("DECOMPOSITION_INVALIDATED")
        if task.latest_decomposition_id != record.decomposition_id:
            raise InvalidStateTransitionError("decomposition attempt is stale")
        if task.status != "decomposing":
            raise InvalidStateTransitionError("task is not decomposing")
        if task.task_version != record.task_version:
            raise TaskVersionConflictError("decomposition task version is stale")

    @staticmethod
    def _parse_time(value: object, field: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise BusinessValidationError(f"{field} is required")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BusinessValidationError(f"{field} must be ISO 8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise BusinessValidationError(f"{field} must include a timezone")
        return parsed.astimezone(UTC)

    @staticmethod
    def _nonblank(value: object, field: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise BusinessValidationError(f"{field} is required")
        return text

    def _validated_graph(
        self, task: Task, record: TaskDecompositionRecord, result: Mapping[str, object]
    ) -> tuple[list[TaskNode], list[TaskNodeDependency]]:
        raw_nodes = result.get("nodes")
        if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, (str, bytes)):
            raise BusinessValidationError("decomposition nodes must be a list")
        if not 5 <= len(raw_nodes) <= 10:
            raise BusinessValidationError("decomposition must contain 5 to 10 nodes")
        pool = set(record.input_snapshot.get("participantEmployeeNos") or [])
        node_map: dict[str, TaskNode] = {}
        nodes: list[TaskNode] = []
        for index, raw in enumerate(raw_nodes, start=1):
            if not isinstance(raw, Mapping):
                raise BusinessValidationError("decomposition node must be an object")
            if "estimated_hours" in raw or "estimatedHours" in raw:
                raise BusinessValidationError("estimated hours are forbidden in decomposition")
            client_id = str(raw.get("client_node_id") or raw.get("clientNodeId") or f"node-{index}")
            if client_id in node_map:
                raise BusinessValidationError("duplicate decomposition node identifier")
            owner = self._nonblank(raw.get("owner_employee_no") or raw.get("ownerEmployeeNo"), "owner_employee_no")
            if owner not in pool:
                raise BusinessValidationError("node owner must be in confirmed participant pool")
            start = self._parse_time(raw.get("planned_start_time") or raw.get("plannedStartTime"), "planned_start_time")
            deadline = self._parse_time(raw.get("planned_deadline") or raw.get("plannedDeadline"), "planned_deadline")
            if deadline < start:
                raise BusinessValidationError("node deadline must not precede node start")
            if task.start_time and start < task.start_time.astimezone(UTC):
                raise BusinessValidationError("node start is outside task time window")
            if task.deadline and deadline > task.deadline.astimezone(UTC):
                raise BusinessValidationError("node deadline is outside task time window")
            node = TaskNode(
                node_id=uuid4(), task_id=task.task_id, node_order=index,
                sort_weight=int(raw.get("sort_weight") or raw.get("sortWeight") or 0),
                node_name=self._nonblank(raw.get("node_name") or raw.get("nodeName"), "node_name"),
                action_detail=self._nonblank(raw.get("action_detail") or raw.get("actionDetail"), "action_detail"),
                tools_or_materials=raw.get("tools_or_materials") or raw.get("toolsOrMaterials"),
                owner_employee_no=owner,
                assignment_status=(
                    "accepted" if owner == task.main_assignee_employee_no else "pending"
                ),
                assignment_responded_at=None,
                assignment_reject_reason=None,
                planned_start_time=start, planned_deadline=deadline,
                estimated_hours=None, actual_hours=None,
                deliverable=raw.get("deliverable"),
                acceptance_criteria=raw.get("acceptance_criteria") or raw.get("acceptanceCriteria"),
                progress_percent=0, status="pending", decomposition_id=record.decomposition_id,
                source_type="ai", blocked_reason=None,
            )
            nodes.append(node)
            node_map[client_id] = node
        dependencies: list[TaskNodeDependency] = []
        raw_dependencies = result.get("dependencies") or []
        if not isinstance(raw_dependencies, Sequence) or isinstance(raw_dependencies, (str, bytes)):
            raise BusinessValidationError("dependencies must be a list")
        edges: set[tuple[UUID, UUID]] = set()
        for raw in raw_dependencies:
            if not isinstance(raw, Mapping):
                raise BusinessValidationError("dependency must be an object")
            before = str(raw.get("predecessor_client_node_id") or raw.get("predecessorClientNodeId") or "")
            after = str(raw.get("successor_client_node_id") or raw.get("successorClientNodeId") or "")
            if before not in node_map or after not in node_map:
                raise BusinessValidationError("dependency references unknown node")
            edge = (node_map[before].node_id, node_map[after].node_id)
            if edge in edges:
                continue
            edges.add(edge)
            dependencies.append(
                TaskNodeDependency(
                    task_id=task.task_id,
                    predecessor_node_id=edge[0], successor_node_id=edge[1],
                    dependency_type=str(raw.get("dependency_type") or raw.get("dependencyType") or "finish_to_start"),
                )
            )
        validate_dependency_graph((n.node_id for n in nodes), edges)
        return nodes, dependencies

    def complete_result(
        self,
        task_id: UUID,
        decomposition_id: UUID,
        actor: str,
        result: Mapping[str, object],
    ) -> TaskDecompositionRecord:
        with self._uow_factory() as uow:
            task = uow.tasks.get_by_id_for_update(task_id)
            record = uow.task_decompositions.get_for_update(decomposition_id)
            if task is None or record is None or record.task_id != task_id:
                raise EntityNotFoundError("task decomposition was not found")
            self._require_assignee(task, actor)
            self._require_current_attempt(task, record)
            if record.status not in {"pending", "running"}:
                raise InvalidStateTransitionError("decomposition attempt is not active")
            nodes, dependencies = self._validated_graph(task, record, result)
            now = self._now(self._clock)
            for node in nodes:
                uow.task_nodes.add_node(node)
                if node.assignment_status == "accepted":
                    schedule_node_execution_reminders(
                        uow.session, task, node, now=now
                    )
                else:
                    emit_node_assignment_notification(
                        uow.session, task, node, now=now
                    )
            for dependency in dependencies:
                uow.task_nodes.add_dependency(dependency)
            record.status = "succeeded"
            record.node_count = len(nodes)
            record.result_json = dict(result)
            record.error_code = None
            record.error_message = None
            record.completed_at = now
            previous = task.status
            task.status = "in_progress"
            task.decomposition_status = "succeeded"
            task.effective_at = now
            task.task_version += 1
            task.updated_at = now
            self._append_status_log(
                uow, task, from_status=previous, to_status="in_progress",
                action="task_decomposition_succeeded", actor=actor, now=now,
                business_ref_id=record.decomposition_id,
            )
            uow.commit()
            return record

    def fail_attempt(
        self, task_id: UUID, decomposition_id: UUID, actor: str, error: Exception
    ) -> TaskDecompositionRecord:
        with self._uow_factory() as uow:
            task = uow.tasks.get_by_id_for_update(task_id)
            record = uow.task_decompositions.get_for_update(decomposition_id)
            if task is None or record is None or record.task_id != task_id:
                raise EntityNotFoundError("task decomposition was not found")
            self._require_assignee(task, actor)
            self._require_current_attempt(task, record)
            now = self._now(self._clock)
            record.status = "failed"
            record.node_count = 0
            record.error_code = "DECOMPOSITION_FAILED"
            record.error_message = str(error)[:500]
            record.completed_at = now
            previous = task.status
            task.status = "decomposition_failed"
            task.decomposition_status = "failed"
            task.effective_at = None
            task.task_version += 1
            task.updated_at = now
            self._append_status_log(
                uow, task, from_status=previous, to_status="decomposition_failed",
                action="task_decomposition_failed", actor=actor, now=now,
                business_ref_id=record.decomposition_id,
            )
            self._notify(
                uow, task, task.main_assignee_employee_no,
                title="任务智能拆解失败", content="拆解未生效，请检查后重试。",
                dedupe_key=f"decomposition-failed:{record.decomposition_id}", now=now,
            )
            uow.commit()
            return record

    @staticmethod
    def invalidate_active(uow: UnitOfWork, task: Task, *, now: datetime) -> TaskDecompositionRecord | None:
        """Invalidate the active attempt inside the caller's existing lifecycle transaction."""
        record = uow.task_decompositions.get_active_for_task(task.task_id)
        if record is None:
            return None
        record.status = "invalidated"
        record.error_code = "DECOMPOSITION_INVALIDATED"
        record.error_message = "task lifecycle changed while decomposition was running"
        record.completed_at = now
        task.decomposition_status = "invalidated"
        task.effective_at = None
        return record
