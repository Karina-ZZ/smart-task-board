from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta, UTC
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.unit_of_work import UnitOfWork
from app.models import Notification, OperationLog, Task, TaskIssue, TaskNode, TaskProgressReport
from app.services.clock import Clock, utc_now
from app.services.commands import SubmitProgressReportCommand
from app.services.errors import BusinessValidationError, EntityNotFoundError, PermissionDeniedError
from app.services.task_workflow import (
    _append_log,
    _aware_utc,
    _increment_task,
    _lock_task,
    _required_text,
    TASK_IN_PROGRESS,
)

UowFactory = Callable[[], UnitOfWork]

REPORT_TIMEZONE = ZoneInfo("Asia/Shanghai")
_WEEKDAYS = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}
_WEEKLY_CYCLE = re.compile(
    r"^weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)@(\d{2}):(\d{2})$"
)


def task_report_period(
    report_cycle: str | None,
    accepted_at: datetime | None,
    submitted_at: datetime,
) -> tuple[datetime | None, datetime | None]:
    """Return the single weekly reporting period fulfilled at submission time."""
    if report_cycle is None:
        return None, None
    if accepted_at is None:
        raise BusinessValidationError("accepted_at is required for scheduled reports")
    match = _WEEKLY_CYCLE.fullmatch(report_cycle)
    if match is None:
        raise BusinessValidationError(
            "report_cycle must use weekly:<DAY>@<HH:MM>"
        )
    hour = int(match.group(2))
    minute = int(match.group(3))
    if hour > 23 or minute > 59:
        raise BusinessValidationError("report_cycle contains an invalid time")

    anchor_utc = _aware_utc(accepted_at, "accepted_at")
    submitted_utc = _aware_utc(submitted_at, "submitted_at")
    anchor_local = anchor_utc.astimezone(REPORT_TIMEZONE)
    submitted_local = submitted_utc.astimezone(REPORT_TIMEZONE)
    days_ahead = (_WEEKDAYS[match.group(1)] - anchor_local.weekday()) % 7
    first_boundary = datetime.combine(
        anchor_local.date() + timedelta(days=days_ahead),
        time(hour, minute),
        REPORT_TIMEZONE,
    )
    if first_boundary <= anchor_local:
        first_boundary += timedelta(days=7)

    if submitted_local < first_boundary:
        period_start = anchor_local
        period_end = first_boundary
    else:
        weeks = (submitted_local - first_boundary) // timedelta(days=7)
        period_end = first_boundary + weeks * timedelta(days=7)
        period_start = anchor_local if weeks == 0 else period_end - timedelta(days=7)
    return period_start.astimezone(UTC), period_end.astimezone(UTC)


class ProgressReportService:
    """Append immutable task and node progress snapshots atomically."""

    def __init__(self, uow_factory: UowFactory, clock: Clock = utc_now) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def submit(self, command: SubmitProgressReportCommand) -> TaskProgressReport:
        if not 0 <= command.progress_percent <= 100:
            raise BusinessValidationError("progress_percent must be between 0 and 100")
        report_content = _required_text(command.report_content, "report_content")
        if command.actual_hours is not None:
            raise BusinessValidationError("actual_hours is system-derived and cannot be submitted")
        if command.node_id is not None:
            raise BusinessValidationError("task-level progress reports cannot target a node")
        issue_note = None
        if command.has_issue:
            issue_note = _required_text(command.issue_note or "", "issue_note")
        now = _aware_utc(self._clock(), "clock")

        with self._uow_factory() as uow:
            if command.idempotency_key:
                cached_log = uow.session.scalar(
                    select(OperationLog).where(
                        OperationLog.request_id == command.idempotency_key,
                        OperationLog.operator_employee_no == command.reporter_employee_no,
                        OperationLog.action == "progress_report_submitted",
                        OperationLog.object_type == "progress_report",
                        OperationLog.result == "success",
                    ).limit(1)
                )
                if isinstance(cached_log, OperationLog):
                    cached = uow.progress_reports.get_by_task_and_id(
                        command.task_id, UUID(cached_log.object_id)
                    )
                    if cached is not None:
                        return cached
            task = _lock_task(uow, command.task_id, command.expected_task_version)
            if task.status not in {TASK_IN_PROGRESS, "blocked", "pending_report"}:
                raise BusinessValidationError("task is not in a reportable execution state")
            node = self._node(uow, task, command.node_id)
            self._require_reporter(uow, task, node, command.reporter_employee_no)

            root_report_id = None
            period_start = None
            period_end = None
            action_type = "progress_report_submitted"
            if command.corrects_report_id is not None:
                root_report_id = self._correction_root(
                    uow,
                    task,
                    command.corrects_report_id,
                    command.reporter_employee_no,
                    command.node_id,
                )
                action_type = "progress_report_corrected"
            elif command.node_id is None:
                period_start, period_end = task_report_period(
                    task.report_cycle,
                    task.accepted_at,
                    now,
                )
                if period_end is not None and uow.progress_reports.has_root_task_report_for_period(
                    task.task_id,
                    period_end,
                ):
                    raise BusinessValidationError(
                        "a task report already fulfills this reporting period"
                    )

            previous_status = task.status
            task.status = "blocked" if command.has_issue else TASK_IN_PROGRESS
            _increment_task(task, now)
            report = uow.progress_reports.add(
                TaskProgressReport(
                    progress_report_id=command.progress_report_id,
                    task_id=task.task_id,
                    node_id=command.node_id,
                    reporter_employee_no=command.reporter_employee_no,
                    progress_percent=command.progress_percent,
                    report_content=report_content,
                    stage_result=command.stage_result,
                    difficulty=command.difficulty,
                    resource_request=command.resource_request,
                    actual_hours=None,
                    corrects_report_id=root_report_id,
                    report_period_start=period_start,
                    report_period_end=period_end,
                    task_version=task.task_version,
                    operation_source=_required_text(
                        command.operation_source,
                        "operation_source",
                    ),
                    created_at=now,
                )
            )
            if command.has_issue:
                issue = uow.task_issues.add(
                    TaskIssue(
                        task_id=task.task_id,
                        node_id=None,
                        source_progress_report_id=report.progress_report_id,
                        reported_by_employee_no=command.reporter_employee_no,
                        issue_type="blocker",
                        title="进度汇报卡点",
                        description=issue_note,
                        severity="medium",
                        status="open",
                        owner_employee_no=task.creator_employee_no,
                        created_at=now,
                    )
                )
                uow.session.add(
                    Notification(
                        task_id=task.task_id,
                        recipient_employee_no=task.creator_employee_no,
                        channel="in_app",
                        title="任务出现卡点",
                        content=issue.description,
                        send_status="pending",
                        retry_count=0,
                        dedupe_key=f"progress-issue:{issue.issue_id}",
                        created_at=now,
                    )
                )
            _append_log(
                uow,
                task,
                from_status=previous_status,
                to_status=task.status,
                action_type=action_type,
                operator_employee_no=command.reporter_employee_no,
                operation_source=command.operation_source,
                now=now,
                business_ref_type="progress_report",
                business_ref_id=report.progress_report_id,
            )
            if command.idempotency_key:
                uow.session.add(
                    OperationLog(
                        request_id=command.idempotency_key,
                        operator_employee_no=command.reporter_employee_no,
                        action="progress_report_submitted",
                        object_type="progress_report",
                        object_id=str(report.progress_report_id),
                        before_data=None,
                        after_data={"taskVersion": task.task_version, "status": task.status},
                        result="success",
                        created_at=now,
                    )
                )
            uow.commit()
            return report

    @staticmethod
    def _node(
        uow: UnitOfWork,
        task: Task,
        node_id: UUID | None,
    ) -> TaskNode | None:
        if node_id is None:
            return None
        node = uow.task_nodes.get_node(node_id)
        if node is None:
            raise EntityNotFoundError("task node was not found")
        if node.task_id != task.task_id:
            raise BusinessValidationError("task node does not belong to the task")
        return node

    @staticmethod
    def _require_reporter(
        uow: UnitOfWork,
        task: Task,
        node: TaskNode | None,
        employee_no: str,
    ) -> None:
        if node is None:
            if employee_no != task.main_assignee_employee_no:
                raise PermissionDeniedError(
                    "only the main assignee may submit task-level reports"
                )
            return
        raise PermissionDeniedError("node-level progress reports are not part of the MVP")

    @staticmethod
    def _correction_root(
        uow: UnitOfWork,
        task: Task,
        target_report_id: UUID,
        reporter_employee_no: str,
        node_id: UUID | None,
    ) -> UUID:
        target = uow.progress_reports.get_by_task_and_id(
            task.task_id,
            target_report_id,
        )
        if target is None:
            raise EntityNotFoundError("progress report was not found")
        root_id = target.corrects_report_id or target.progress_report_id
        root = uow.progress_reports.get_by_task_and_id(task.task_id, root_id)
        if root is None:
            raise EntityNotFoundError("root progress report was not found")
        if root.reporter_employee_no != reporter_employee_no:
            raise PermissionDeniedError("only the original reporter may correct a report")
        if root.node_id != node_id:
            raise BusinessValidationError("a correction must keep the original node scope")
        return root.progress_report_id
