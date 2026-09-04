from datetime import datetime, UTC
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError
import pytest

from app.schemas import (
    CreateTaskRequest,
    ReturnTaskRequest,
    TaskActionRequest,
    TaskActionResponse,
    TaskNodeResponse,
    UpdateNodeProgressRequest,
)


def _valid_request() -> dict[str, object]:
    return {
        "task_name": "Task",
        "task_description": "Description",
        "task_goal": "Goal",
        "task_source": "Source",
        "main_assignee_employee_no": "E002",
        "report_to_employee_no": "E003",
        "reviewer_employee_no": "E004",
        "start_time": "2026-08-18T08:00:00+08:00",
        "deadline": "2026-08-19T08:00:00+08:00",
        "task_weight": 3,
        "participants": [
            {"employee_no": "E005", "participant_role": "collaborator"}
        ],
    }


def test_create_request_accepts_v11_task_level_fields() -> None:
    request = CreateTaskRequest.model_validate(_valid_request())
    assert request.task_name == "Task"
    assert request.start_time is not None and request.start_time.tzinfo is not None
    assert request.participants[0].participant_role == "collaborator"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("creator_employee_no", "E-CREATOR"),
        ("operation_source", "client"),
        ("status", "draft"),
        ("estimated_hours", "3.50"),
        ("actual_hours", "1"),
        (
            "nodes",
            [{"node_id": str(uuid4()), "node_order": 1, "node_name": "Node"}],
        ),
        ("dependencies", []),
        ("node_participants", []),
        ("unexpected", "value"),
    ],
)
def test_create_request_forbids_server_owned_later_flow_and_extra_fields(
    field: str,
    value: object,
) -> None:
    payload = _valid_request()
    payload[field] = value
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CreateTaskRequest.model_validate(payload)


def test_create_request_requires_name_and_aware_ordered_datetimes() -> None:
    with pytest.raises(ValidationError):
        CreateTaskRequest.model_validate({})

    payload = _valid_request()
    payload["start_time"] = "2026-08-18T08:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        CreateTaskRequest.model_validate(payload)

    payload = _valid_request()
    payload["deadline"] = "2026-08-17T08:00:00+08:00"
    with pytest.raises(ValidationError, match="deadline"):
        CreateTaskRequest.model_validate(payload)


def test_action_request_boundaries_and_blank_reason() -> None:
    with pytest.raises(ValidationError):
        TaskActionRequest(expected_task_version=0)
    with pytest.raises(ValidationError):
        ReturnTaskRequest(expected_task_version=1, reason="  ")
    with pytest.raises(ValidationError):
        UpdateNodeProgressRequest(expected_task_version=1, progress_percent=101)
    with pytest.raises(ValidationError):
        UpdateNodeProgressRequest(
            expected_task_version=1,
            progress_percent=50,
            actual_hours=Decimal("-1"),
        )


def test_status_literal_and_decimal_json_serialization() -> None:
    response = TaskActionResponse(
        task_id=uuid4(),
        status="draft",
        task_version=1,
        updated_at=datetime(2026, 8, 18, tzinfo=UTC),
    )
    assert response.model_dump(mode="json")["updated_at"].endswith("Z")

    node = TaskNodeResponse(
        node_id=uuid4(),
        task_id=uuid4(),
        node_order=1,
        sort_weight=0,
        node_name="Node",
        action_detail=None,
        tools_or_materials=None,
        owner_employee_no=None,
        planned_start_time=None,
        planned_deadline=None,
        estimated_hours=Decimal("4.25"),
        actual_hours=Decimal("1.50"),
        deliverable=None,
        acceptance_criteria=None,
        progress_percent=50,
        status="in_progress",
        completed_at=None,
    )
    assert node.model_dump(mode="json")["actual_hours"] == "1.50"

    with pytest.raises(ValidationError):
        TaskActionResponse(
            task_id=uuid4(),
            status="unknown",  # type: ignore[arg-type]
            task_version=1,
            updated_at=datetime(2026, 8, 18, tzinfo=UTC),
        )
