from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_executive_dashboard_service
from app.main import app

NOW = datetime(2026, 9, 3, 2, 0, tzinfo=UTC)


@pytest.fixture
def executive_context():
    service = MagicMock()
    app.dependency_overrides[get_executive_dashboard_service] = lambda: service
    try:
        yield TestClient(app), service
    finally:
        app.dependency_overrides.clear()


def test_executive_overview_forwards_scope_and_period(executive_context) -> None:
    client, service = executive_context
    department_id = uuid4()
    service.get_overview.return_value = {
        "scope": {"selected_department_id": department_id, "departments": []},
        "period": {
            "type": "week",
            "start": NOW,
            "end": NOW,
            "previous_start": NOW,
            "previous_end": NOW,
        },
        "metrics": {
            "active_tasks": {"count": 0, "previous_count": 0, "change_rate": 0, "change_direction": "flat"},
            "on_time_rate": {"completed_count": 0, "on_time_count": 0, "rate": None, "previous_rate": None, "change_percentage_points": None},
            "kpi_links": {"linked_task_count": 0, "linked_metric_count": 0},
            "overall_progress": {"rate": None, "task_count": 0, "data_quality_issue_count": 0},
        },
        "quadrants": {
            "important_urgent": 0,
            "important_not_urgent": 0,
            "not_important_urgent": 0,
            "not_important_not_urgent": 0,
            "unscored_count": 0,
        },
        "workload_heatmap": {"days": [], "members": []},
    }

    response = client.get(
        f"/api/v1/executive/overview?departmentId={department_id}&period=week",
        headers={"X-Employee-No": "E-EXEC"},
    )

    assert response.status_code == 200
    service.get_overview.assert_called_once_with(
        "E-EXEC", department_id=department_id, period="week"
    )


def test_executive_tasks_validates_quadrant_before_service(executive_context) -> None:
    client, service = executive_context
    response = client.get(
        "/api/v1/executive/tasks?quadrant=invalid",
        headers={"X-Employee-No": "E-EXEC"},
    )
    assert response.status_code == 422
    service.list_quadrant_tasks.assert_not_called()


def test_feature15_executive_tasks_forwards_employee_and_task_filters(executive_context) -> None:
    client, service = executive_context
    department_id = uuid4()
    service.list_tasks.return_value = {
        "items": [],
        "page": 1,
        "page_size": 20,
        "limit": 20,
        "offset": 0,
        "total": 0,
        "status_counts": {},
    }

    response = client.get(
        f"/api/v1/executive/tasks?departmentId={department_id}&employeeNo=E-1&status=blocked"
        "&quadrant=important_urgent&datePreset=week&page=1&pageSize=20",
        headers={"X-Employee-No": "E-EXEC"},
    )

    assert response.status_code == 200
    service.list_tasks.assert_called_once_with(
        "E-EXEC",
        department_id=department_id,
        employee_no="E-1",
        task_status="blocked",
        quadrant="important_urgent",
        near_due=False,
        date_preset="week",
        start_date=None,
        end_date=None,
        search=None,
        sort_by="deadline",
        sort_order="asc",
        page=1,
        page_size=20,
    )


def test_feature15_executive_members_forwards_department_scope(executive_context) -> None:
    client, service = executive_context
    department_id = uuid4()
    service.list_members.return_value = [
        {"employee_no": "E-1", "name": "Alice", "department_id": department_id}
    ]

    response = client.get(
        f"/api/v1/executive/members?departmentId={department_id}",
        headers={"X-Employee-No": "E-EXEC"},
    )

    assert response.status_code == 200
    assert response.json()[0]["employee_no"] == "E-1"
    service.list_members.assert_called_once_with("E-EXEC", department_id=department_id)


def test_feature14_period_remains_compatible_when_date_preset_is_omitted(executive_context) -> None:
    client, service = executive_context
    service.list_tasks.return_value = {
        "items": [], "page": 1, "page_size": 20, "limit": 20, "offset": 0,
        "total": 0, "status_counts": {},
    }

    response = client.get(
        "/api/v1/executive/tasks?quadrant=important_urgent&period=week",
        headers={"X-Employee-No": "E-EXEC"},
    )

    assert response.status_code == 200
    assert service.list_tasks.call_args.kwargs["date_preset"] == "week"


def test_feature15_explicit_all_date_filter_overrides_period_context(executive_context) -> None:
    client, service = executive_context
    service.list_tasks.return_value = {
        "items": [], "page": 1, "page_size": 20, "limit": 20, "offset": 0,
        "total": 0, "status_counts": {},
    }

    response = client.get(
        "/api/v1/executive/tasks?employeeNo=E-1&period=week&datePreset=all",
        headers={"X-Employee-No": "E-EXEC"},
    )

    assert response.status_code == 200
    assert service.list_tasks.call_args.kwargs["date_preset"] == "all"
