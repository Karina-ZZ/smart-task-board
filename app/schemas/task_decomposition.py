"""
Feature: AI decomposition API DTOs.
Responsibilities: validate decomposition action transport and serialize attempt state.
Does not own: workflow, persistence, or provider calls.
Plan task: DEV-09.
"""
from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictSchema


class ExecuteDecompositionRequest(StrictSchema):
    decomposition_id: UUID


class RetryDecompositionRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)


class TaskDecompositionResponse(StrictSchema):
    decomposition_id: UUID
    task_id: UUID
    triggered_by_employee_no: str
    trigger_type: str
    status: str
    task_version: int
    model_name: str | None
    model_version: str | None
    prompt_version: str
    node_count: int
    error_code: str | None
    error_message: str | None
    retry_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
