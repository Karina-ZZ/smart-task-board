"""
Feature: Executive dashboard HTTP API.
Responsibilities: parse authorized dashboard and DEV-17 employee-task filter requests.
Does not own: scope decisions, metric formulas, or database queries.
Plan task: DEV-16 / FEATURE-14 and DEV-17 / FEATURE-15.
"""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_employee_no, get_executive_dashboard_service
from app.schemas.common import TaskStatus
from app.schemas.executive_dashboard import (
    ExecutiveMemberResponse,
    ExecutiveOverviewResponse,
    ExecutiveTaskPageResponse,
)
from app.schemas.task_board import SortOrder, TaskOverviewSort
from app.services.errors import BusinessValidationError
from app.services.features.executive_dashboard import ExecutiveDashboardService

router = APIRouter(prefix="/executive", tags=["executive-dashboard"])
Actor = Annotated[str, Depends(get_current_employee_no)]
ExecutiveService = Annotated[ExecutiveDashboardService, Depends(get_executive_dashboard_service)]
Quadrant = Literal[
    "important_urgent",
    "important_not_urgent",
    "not_important_urgent",
    "not_important_not_urgent",
    "urgent_not_important",
    "routine",
]


@router.get(
    "/overview",
    response_model=ExecutiveOverviewResponse,
    summary="Get executive team overview",
)
def get_executive_overview(
    actor: Actor,
    service: ExecutiveService,
    department_id: Annotated[UUID | None, Query(alias="departmentId")] = None,
    period: Literal["week", "month"] = "week",
) -> dict[str, object]:
    return service.get_overview(actor, department_id=department_id, period=period)


@router.get(
    "/members",
    response_model=list[ExecutiveMemberResponse],
    summary="List employees in the authorized executive department scope",
)
def list_executive_members(
    actor: Actor,
    service: ExecutiveService,
    department_id: Annotated[UUID | None, Query(alias="departmentId")] = None,
) -> list[dict[str, object]]:
    return service.list_members(actor, department_id=department_id)


@router.get(
    "/tasks",
    response_model=ExecutiveTaskPageResponse,
    summary="List authorized team tasks",
)
def list_executive_tasks(
    actor: Actor,
    service: ExecutiveService,
    department_id: Annotated[UUID | None, Query(alias="departmentId")] = None,
    employee_no: Annotated[str | None, Query(alias="employeeNo", max_length=64)] = None,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    quadrant: Quadrant | None = None,
    near_due: Annotated[bool, Query(alias="nearDue")] = False,
    date_preset: Annotated[
        Literal["all", "week", "month", "custom"] | None, Query(alias="datePreset")
    ] = None,
    start_date: Annotated[date | None, Query(alias="startDate")] = None,
    end_date: Annotated[date | None, Query(alias="endDate")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort_by: Annotated[TaskOverviewSort, Query(alias="sortBy")] = "deadline",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
    period: Literal["week", "month"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> dict[str, object]:
    if date_preset == "custom" and (start_date is None or end_date is None):
        raise BusinessValidationError("custom date filter requires startDate and endDate")
    if start_date and end_date and start_date > end_date:
        raise BusinessValidationError("startDate must not be after endDate")
    # Old feature-14 links may send only period. Feature-15 sends datePreset explicitly,
    # including `all` when the high-level date filter is cleared.
    effective_date_preset = date_preset if date_preset is not None else (period or "all")
    return service.list_tasks(
        actor,
        department_id=department_id,
        employee_no=employee_no,
        task_status=task_status,
        quadrant=quadrant,
        near_due=near_due,
        date_preset=effective_date_preset,
        start_date=start_date,
        end_date=end_date,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
