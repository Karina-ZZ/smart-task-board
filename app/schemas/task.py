from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.common import DecimalString, ParticipantConfirmStatus, StrictSchema, TaskStatus
from app.schemas.task_change_request import TaskChangeRequestResponse
from app.schemas.task_node import (
    TaskNodeDependencyResponse,
    TaskNodeParticipantResponse,
    TaskNodeResponse,
    _require_aware,
)

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskParticipantDraftRequest(StrictSchema):
    employee_no: NonBlankString
    participant_role: NonBlankString
    is_primary: bool = False


class CreateTaskRequest(StrictSchema):
    """V1.1 creator draft transport; nodes/hours are not client-writable."""

    task_id: UUID | None = None
    task_name: NonBlankString
    task_description: str | None = None
    task_goal: str | None = None
    task_source: str | None = None
    main_assignee_employee_no: str | None = None
    report_to_employee_no: str | None = None
    report_to_level: str | None = None
    reviewer_employee_no: str | None = None
    department_id: UUID | None = None
    start_time: datetime | None = None
    deadline: datetime | None = None
    task_weight: int | None = Field(default=None, ge=1, le=5)
    deliverable: str | None = None
    acceptance_criteria: str | None = None
    is_urgent: bool | None = None
    report_cycle: str | None = None
    participants: tuple[TaskParticipantDraftRequest, ...] = ()
    extraction_record_ids: tuple[UUID, ...] = ()

    _validate_start = field_validator("start_time")(_require_aware)
    _validate_deadline = field_validator("deadline")(_require_aware)

    @model_validator(mode="after")
    def validate_time_order(self) -> "CreateTaskRequest":
        if (
            self.start_time is not None
            and self.deadline is not None
            and self.deadline < self.start_time
        ):
            raise ValueError("deadline must not precede start_time")
        return self


class UpdateTaskDraftRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    task_name: NonBlankString | None = None
    task_description: str | None = None
    task_goal: str | None = None
    task_source: str | None = None
    main_assignee_employee_no: str | None = None
    report_to_employee_no: str | None = None
    report_to_level: str | None = None
    reviewer_employee_no: str | None = None
    department_id: UUID | None = None
    start_time: datetime | None = None
    deadline: datetime | None = None
    task_weight: int | None = Field(default=None, ge=1, le=5)
    deliverable: str | None = None
    acceptance_criteria: str | None = None
    is_urgent: bool | None = None
    report_cycle: str | None = None
    collaborator_employee_nos: tuple[NonBlankString, ...] | None = None

    _validate_start = field_validator("start_time")(_require_aware)
    _validate_deadline = field_validator("deadline")(_require_aware)

    @model_validator(mode="after")
    def validate_time_order(self) -> "UpdateTaskDraftRequest":
        if (
            self.start_time is not None
            and self.deadline is not None
            and self.deadline < self.start_time
        ):
            raise ValueError("deadline must not precede start_time")
        return self


class TaskActionRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)


class ReturnTaskRequest(TaskActionRequest):
    reason: NonBlankString


class ReasonTaskActionRequest(TaskActionRequest):
    reason: NonBlankString


class ReassignTaskRequest(TaskActionRequest):
    new_assignee_employee_no: NonBlankString
    reason: NonBlankString


class TaskActionResponse(StrictSchema):
    task_id: UUID
    status: TaskStatus
    task_version: int
    updated_at: datetime


class TaskParticipantResponse(StrictSchema):
    participant_id: UUID
    task_id: UUID
    employee_no: str
    participant_role: str
    is_primary: bool
    confirm_status: ParticipantConfirmStatus | None
    confirmed_at: datetime | None


class AIExtractionRecordSummaryResponse(StrictSchema):
    extraction_id: UUID
    input_id: UUID
    task_id: UUID | None
    extracted_json: dict[str, object]
    missing_fields: list[str]
    low_confidence_fields: list[str]
    confirm_questions: list[str]
    confidence_score: DecimalString | None
    confirmed_at: datetime | None


class TaskPerformanceMatchSummaryResponse(StrictSchema):
    performance_match_id: UUID
    task_id: UUID
    metric_id: UUID
    metric_type: str
    metric_name: str
    period: str | None
    business_unit: str | None
    definition_formula: str | None
    total_score: DecimalString
    match_level: str
    match_reason: str | None
    is_confirmed: bool
    confirmed_by_employee_no: str | None
    confirmed_at: datetime | None


class TaskOperationLogSummaryResponse(StrictSchema):
    operation_log_id: UUID
    request_id: str | None
    operator_employee_no: str | None
    action: str
    object_type: str
    object_id: str
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    result: str
    error_message: str | None
    created_at: datetime


class TaskPersonSummaryResponse(StrictSchema):
    employee_no: str
    name: str
    department_id: UUID | None


class PaginatedTaskOperationLogResponse(StrictSchema):
    items: list[TaskOperationLogSummaryResponse]
    limit: int
    offset: int
    total: int


class TaskDetailResponse(StrictSchema):
    task_id: UUID
    task_no: str | None
    task_name: str
    task_description: str | None
    task_goal: str | None
    task_source: str | None
    creator_employee_no: str
    main_assignee_employee_no: str | None
    report_to_employee_no: str | None
    report_to_level: str | None
    reviewer_employee_no: str | None
    department_id: UUID | None
    status: TaskStatus
    start_time: datetime | None
    deadline: datetime | None
    estimated_hours: DecimalString | None
    actual_hours: DecimalString | None
    task_weight: int | None
    deliverable: str | None
    acceptance_criteria: str | None
    is_urgent: bool | None
    report_cycle: str | None
    cancel_reason: str | None
    withdraw_reason: str | None
    close_reason: str | None
    merged_into_task_id: UUID | None
    task_version: int
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    sent_at: datetime | None
    accepted_at: datetime | None
    completed_at: datetime | None
    archived_at: datetime | None
    effective_at: datetime | None = None
    decomposition_status: str | None = None
    latest_decomposition_id: UUID | None = None
    priority_quadrant: str | None = None
    importance_score: DecimalString | None = None
    urgency_score: DecimalString | None = None
    remaining_hours: DecimalString | None = None
    open_conflict_count: int = 0
    participants: list[TaskParticipantResponse]
    nodes: list[TaskNodeResponse]
    dependencies: list[TaskNodeDependencyResponse]
    node_participants: list[TaskNodeParticipantResponse]
    ai_extraction_records: list[AIExtractionRecordSummaryResponse]
    performance_matches: list[TaskPerformanceMatchSummaryResponse] = Field(default_factory=list)
    operation_logs: list[TaskOperationLogSummaryResponse] = Field(default_factory=list)
    change_requests: list[TaskChangeRequestResponse] = Field(default_factory=list)
    people: list[TaskPersonSummaryResponse] = Field(default_factory=list)


class TaskStatusLogResponse(StrictSchema):
    status_log_id: UUID
    task_id: UUID
    from_status: TaskStatus | None
    to_status: TaskStatus
    action_type: str
    reason: str | None
    operator_employee_no: str | None
    target_employee_no: str | None
    task_version: int
    business_ref_type: str | None
    business_ref_id: UUID | None
    operation_source: str
    created_at: datetime


class PaginatedTaskStatusLogResponse(StrictSchema):
    items: list[TaskStatusLogResponse]
    limit: int
    offset: int
    total: int
