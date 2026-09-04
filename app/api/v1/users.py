"""Feature 06 creator-flow people search endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_employee_no
from app.db.session import get_db
from app.schemas.task_creation import TaskCreationPersonResponse
from app.services.features.task_creation.people import TaskCreationPeopleService

router=APIRouter(tags=["users"])
@router.get(
    "/users",
    response_model=list[TaskCreationPersonResponse],
    summary="List task-creation employee candidates",
)
def list_people(
    actor: Annotated[str, Depends(get_current_employee_no)],
    session: Annotated[Session, Depends(get_db)],
    keyword: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[TaskCreationPersonResponse]:
    rows = TaskCreationPeopleService(session).list_candidates(actor, keyword, limit)
    return [TaskCreationPersonResponse.model_validate(row) for row in rows]
