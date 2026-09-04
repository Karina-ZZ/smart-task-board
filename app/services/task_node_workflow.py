from collections.abc import Callable
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.db.unit_of_work import UnitOfWork
from app.models import OperationLog, Task, TaskNode
from app.services.clock import Clock, utc_now
from app.services.errors import (
    BusinessValidationError,
    DependencyNotSatisfiedError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    OpenTaskIssueConflictError,
    PermissionDeniedError,
)
from app.services.features.notifications import (
    emit_node_assignment_rejected_notification,
    schedule_node_execution_reminders,
)
from app.services.task_workflow import (
    _append_log,
    _aware_utc,
    _increment_task,
    _lock_task,
    _require_state,
    TASK_IN_PROGRESS,
)

UowFactory = Callable[[], UnitOfWork]


class TaskNodeWorkflowService:
    """Execute task nodes while preserving task version and audit invariants."""

    def __init__(self, uow_factory: UowFactory, clock: Clock = utc_now) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def start_node(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        idempotency_key: str | None = None,
    ) -> TaskNode:
        with self._uow_factory() as uow:
            cached = self._find_idempotent_node(
                uow, idempotency_key, actor_employee_no, "node_started", node_id
            )
            if cached is not None:
                return cached
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_execution_state(task)
            node = self._task_node(uow, task, node_id)
            if node.status != "pending":
                raise InvalidStateTransitionError(
                    "start_node requires a pending task node"
                )
            self._require_node_actor(uow, task, node, actor_employee_no)
            self._require_dependencies_completed(uow, task_id, node_id)
            now = _aware_utc(self._clock(), "clock")
            node.status = "in_progress"
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="node_started",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="task_node",
                business_ref_id=node.node_id,
            )
            self._record_idempotency(
                uow, idempotency_key, actor_employee_no, "node_started", node, task, now
            )
            uow.commit()
            return node

    def update_node_progress(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        progress_percent: int,
        actual_hours: Decimal | None = None,
    ) -> TaskNode:
        if not 0 <= progress_percent <= 100:
            raise BusinessValidationError("progress_percent must be between 0 and 100")
        if actual_hours is not None:
            raise BusinessValidationError("actual_hours is system-derived and cannot be submitted")
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_execution_state(task)
            node = self._task_node(uow, task, node_id)
            if node.status != "in_progress":
                raise InvalidStateTransitionError(
                    "progress updates require an in-progress task node"
                )
            self._require_node_actor(uow, task, node, actor_employee_no)
            if progress_percent < node.progress_percent:
                raise BusinessValidationError("node progress cannot decrease")
            now = _aware_utc(self._clock(), "clock")
            node.progress_percent = progress_percent
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="node_progress_updated",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="task_node",
                business_ref_id=node.node_id,
            )
            uow.commit()
            return node

    def complete_node(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        idempotency_key: str | None = None,
    ) -> TaskNode:
        with self._uow_factory() as uow:
            cached = self._find_idempotent_node(
                uow, idempotency_key, actor_employee_no, "node_completed", node_id
            )
            if cached is not None:
                return cached
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_execution_state(task)
            node = self._task_node(uow, task, node_id)
            if node.status != "in_progress":
                raise InvalidStateTransitionError(
                    "complete_node requires an in-progress task node"
                )
            self._require_node_actor(uow, task, node, actor_employee_no)
            self._require_dependencies_completed(uow, task_id, node_id)
            if uow.task_issues.has_active_blocker(task.task_id, node.node_id):
                raise OpenTaskIssueConflictError(
                    "active blocker issues must be closed before completing the node"
                )
            now = _aware_utc(self._clock(), "clock")
            node.progress_percent = 100
            node.status = "completed"
            node.completed_at = now
            if node.planned_start_time is not None:
                seconds = max(0, (now - node.planned_start_time).total_seconds())
                node.actual_hours = Decimal(str(round(seconds / 3600, 2)))
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="node_completed",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="task_node",
                business_ref_id=node.node_id,
            )
            self._record_idempotency(
                uow, idempotency_key, actor_employee_no, "node_completed", node, task, now
            )
            uow.commit()
            return node

    def accept_node_assignment(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        idempotency_key: str | None = None,
    ) -> TaskNode:
        with self._uow_factory() as uow:
            cached = self._find_idempotent_node(
                uow, idempotency_key, actor_employee_no,
                "node_assignment_accepted", node_id
            )
            if cached is not None:
                return cached
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_execution_state(task)
            node = self._task_node(uow, task, node_id)
            self._require_assignment_actor(task, node, actor_employee_no)
            if node.assignment_status != "pending":
                raise InvalidStateTransitionError(
                    "node assignment acceptance requires pending status"
                )
            now = _aware_utc(self._clock(), "clock")
            node.assignment_status = "accepted"
            node.assignment_responded_at = now
            node.assignment_reject_reason = None
            _increment_task(task, now)
            schedule_node_execution_reminders(uow.session, task, node, now=now)
            _append_log(
                uow, task, from_status=task.status, to_status=task.status,
                action_type="node_assignment_accepted",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source, now=now,
                business_ref_type="task_node", business_ref_id=node.node_id,
            )
            self._record_idempotency(
                uow, idempotency_key, actor_employee_no,
                "node_assignment_accepted", node, task, now
            )
            uow.commit()
            return node

    def reject_node_assignment(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        reason: str,
        idempotency_key: str | None = None,
    ) -> TaskNode:
        reason = (reason or "").strip()
        if not reason:
            raise BusinessValidationError("node assignment rejection reason is required")
        with self._uow_factory() as uow:
            cached = self._find_idempotent_node(
                uow, idempotency_key, actor_employee_no,
                "node_assignment_rejected", node_id
            )
            if cached is not None:
                return cached
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_execution_state(task)
            node = self._task_node(uow, task, node_id)
            self._require_assignment_actor(task, node, actor_employee_no)
            if node.assignment_status != "pending":
                raise InvalidStateTransitionError(
                    "node assignment rejection requires pending status"
                )
            now = _aware_utc(self._clock(), "clock")
            node.assignment_status = "rejected"
            node.assignment_responded_at = now
            node.assignment_reject_reason = reason
            _increment_task(task, now)
            emit_node_assignment_rejected_notification(
                uow.session, task, node, reason=reason, now=now
            )
            _append_log(
                uow, task, from_status=task.status, to_status=task.status,
                action_type="node_assignment_rejected",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source, now=now,
                business_ref_type="task_node", business_ref_id=node.node_id,
                reason=reason,
            )
            self._record_idempotency(
                uow, idempotency_key, actor_employee_no,
                "node_assignment_rejected", node, task, now
            )
            uow.commit()
            return node

    def reopen_node(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        completion_review_id: UUID,
    ) -> TaskNode:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_IN_PROGRESS)
            review = (
                uow.task_completion_reviews.get_by_task_and_id_for_update(
                    task.task_id,
                    completion_review_id,
                )
            )
            if review is None:
                raise EntityNotFoundError("completion review was not found")
            latest_rejected = (
                uow.task_completion_reviews.get_latest_rejected(task.task_id)
            )
            if (
                review.review_status != "rejected"
                or latest_rejected is None
                or latest_rejected.completion_review_id
                != review.completion_review_id
            ):
                raise InvalidStateTransitionError(
                    "reopen_node requires the latest rejected completion review"
                )
            if review.rework_node_id != node_id:
                raise BusinessValidationError(
                    "task node does not match the rejected rework node"
                )
            if review.reviewed_task_version is None:
                raise BusinessValidationError(
                    "rejected completion review is missing its reviewed version"
                )
            if actor_employee_no != review.reviewer_employee_no:
                raise PermissionDeniedError(
                    "actor must be the completion review reviewer"
                )
            if uow.task_status_logs.has_action_for_business_ref(
                task.task_id,
                "node_reopened",
                "completion_review",
                review.completion_review_id,
            ):
                raise InvalidStateTransitionError(
                    "the rejected task node has already been reopened"
                )
            node = uow.task_nodes.get_node_for_update(node_id)
            if node is None:
                raise EntityNotFoundError("task node was not found")
            if node.task_id != task.task_id:
                raise BusinessValidationError(
                    "task node does not belong to the task"
                )
            if node.status != "completed":
                raise InvalidStateTransitionError(
                    "reopen_node requires a completed task node"
                )
            now = _aware_utc(self._clock(), "clock")
            node.status = "in_progress"
            node.progress_percent = 0
            node.completed_at = None
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="node_reopened",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="completion_review",
                business_ref_id=review.completion_review_id,
            )
            uow.commit()
            return node

    @staticmethod
    def _find_idempotent_node(
        uow: UnitOfWork,
        key: str | None,
        actor: str,
        action: str,
        node_id: UUID,
    ) -> TaskNode | None:
        if not key:
            return None
        row = uow.session.scalar(
            select(OperationLog).where(
                OperationLog.request_id == key,
                OperationLog.operator_employee_no == actor,
                OperationLog.action == action,
                OperationLog.object_type == "task_node",
                OperationLog.object_id == str(node_id),
                OperationLog.result == "success",
            ).limit(1)
        )
        if not isinstance(row, OperationLog):
            return None
        return uow.task_nodes.get_node(node_id)

    @staticmethod
    def _record_idempotency(
        uow: UnitOfWork,
        key: str | None,
        actor: str,
        action: str,
        node: TaskNode,
        task: Task,
        now,
    ) -> None:
        if not key:
            return
        uow.session.add(
            OperationLog(
                request_id=key,
                operator_employee_no=actor,
                action=action,
                object_type="task_node",
                object_id=str(node.node_id),
                before_data=None,
                after_data={"status": node.status, "taskVersion": task.task_version},
                result="success",
                created_at=now,
            )
        )

    @staticmethod
    def _require_execution_state(task: Task) -> None:
        if task.status not in {TASK_IN_PROGRESS, "blocked", "pending_report"}:
            raise InvalidStateTransitionError(
                f"node execution is not allowed from task status {task.status}"
            )

    @staticmethod
    def _require_dependencies_completed(
        uow: UnitOfWork, task_id: UUID, node_id: UUID
    ) -> None:
        for dependency in uow.task_nodes.list_predecessors(task_id, node_id):
            predecessor = uow.task_nodes.get_node(dependency.predecessor_node_id)
            if predecessor is None or predecessor.status != "completed":
                raise DependencyNotSatisfiedError(
                    "all predecessor nodes must be completed"
                )

    @staticmethod
    def _task_node(uow: UnitOfWork, task: Task, node_id: UUID) -> TaskNode:
        node = uow.task_nodes.get_node(node_id)
        if node is None:
            raise EntityNotFoundError("task node was not found")
        if node.task_id != task.task_id:
            raise BusinessValidationError("task node does not belong to the task")
        return node

    @staticmethod
    def _require_assignment_actor(
        task: Task, node: TaskNode, actor_employee_no: str
    ) -> None:
        if node.owner_employee_no != actor_employee_no:
            raise PermissionDeniedError("only the assigned node owner can respond")
        if actor_employee_no == task.main_assignee_employee_no:
            raise InvalidStateTransitionError(
                "main-assignee nodes do not require assignment acceptance"
            )

    @staticmethod
    def _require_node_actor(
        uow: UnitOfWork,
        task: Task,
        node: TaskNode,
        actor_employee_no: str,
    ) -> None:
        authorized = actor_employee_no == node.owner_employee_no
        if node.owner_employee_no is None and actor_employee_no == task.main_assignee_employee_no:
            authorized = True
        if not authorized:
            authorized = any(
                participant.employee_no == actor_employee_no
                and participant.participant_role == "owner"
                for participant in uow.task_nodes.list_participants(
                    task.task_id, node.node_id
                )
            )
        if not authorized:
            raise PermissionDeniedError("actor cannot execute this task node")
        if (
            actor_employee_no != task.main_assignee_employee_no
            and (node.assignment_status or "accepted") != "accepted"
        ):
            raise InvalidStateTransitionError(
                "collaborator must accept the node assignment before execution"
            )
