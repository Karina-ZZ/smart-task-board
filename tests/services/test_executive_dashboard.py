from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.errors import PermissionDeniedError
from app.services.features.executive_dashboard.metrics import ExecutiveMetricsCalculator
from app.services.features.executive_dashboard.periods import resolve_executive_period
from app.services.features.executive_dashboard.permissions import ExecutiveScopeResolver
from app.services.features.executive_dashboard.service import ExecutiveDashboardService
from app.services.features.executive_dashboard.task_list import ExecutiveTaskListService

NOW = datetime(2026, 9, 3, 2, 0, tzinfo=UTC)


def _service() -> ExecutiveDashboardService:
    service = ExecutiveDashboardService.__new__(ExecutiveDashboardService)
    service.session = MagicMock()
    service.clock = lambda: NOW
    service.repo = MagicMock()
    service.scope_resolver = ExecutiveScopeResolver(service.repo)
    service.metrics = ExecutiveMetricsCalculator(service.repo)
    service.workload = MagicMock()
    service.task_list = ExecutiveTaskListService(
        service.repo, service.scope_resolver, service.metrics, service.clock
    )
    return service


def _department(department_id, parent=None, name="Dept"):
    return SimpleNamespace(
        department_id=department_id,
        parent_department_id=parent,
        department_name=name,
        department_type="department",
        department_path=str(department_id),
        status="active",
    )


def _task(status="in_progress", **overrides):
    values = {
        "task_id": uuid4(),
        "task_no": "T-001",
        "task_name": "Task",
        "status": status,
        "department_id": uuid4(),
        "effective_at": NOW - timedelta(days=10),
        "start_time": NOW - timedelta(days=5),
        "deadline": NOW + timedelta(days=5),
        "completed_at": None,
        "task_weight": 3,
        "task_version": 2,
        "latest_decomposition_id": uuid4(),
        "main_assignee_employee_no": "E-1",
        "created_at": NOW - timedelta(days=20),
        "updated_at": NOW - timedelta(days=1),
        "is_urgent": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_week_and_month_periods_are_half_open_asia_shanghai() -> None:
    week = resolve_executive_period("week", NOW)
    assert week.start.astimezone().tzinfo is not None
    assert week.start < week.end
    assert week.previous_end == week.start
    assert week.end - week.start == timedelta(days=7)

    month = resolve_executive_period("month", NOW)
    assert month.start.day == 31 or month.start.day == 1  # UTC may be previous date
    assert month.previous_end == month.start
    assert month.start < month.end


def test_explicit_department_scope_expands_descendants_and_keeps_all_options() -> None:
    root, child, sibling = uuid4(), uuid4(), uuid4()
    service = _service()
    service.repo.get_user.return_value = SimpleNamespace(status="active", role_type="executive")
    service.repo.list_active_department_scopes.return_value = [SimpleNamespace(scope_id=str(root))]
    service.repo.list_active_departments.return_value = [
        _department(root, None, "Root"),
        _department(child, root, "Child"),
        _department(sibling, root, "Sibling"),
    ]

    scope, departments = service.scope_resolver.authorize("E-X", child, NOW)

    assert scope.root_department_ids == {root}
    assert scope.authorized_department_ids == {root, child, sibling}
    assert scope.department_ids == {child}
    payload = service.scope_resolver.payload(scope, departments)
    assert {row["department_id"] for row in payload["departments"]} == {root, child, sibling}


def test_scope_denies_department_outside_explicit_authorization() -> None:
    root, outside = uuid4(), uuid4()
    service = _service()
    service.repo.get_user.return_value = SimpleNamespace(status="active", role_type="executive")
    service.repo.list_active_department_scopes.return_value = [SimpleNamespace(scope_id=str(root))]
    service.repo.list_active_departments.return_value = [_department(root), _department(outside)]

    with pytest.raises(PermissionDeniedError):
        service.scope_resolver.authorize("E-X", outside, NOW)

    service.repo.add_scope_denied_log.assert_called_once()


def test_kpi_metric_uses_confirmed_relationships_without_match_level_gate() -> None:
    service = _service()
    tasks = [_task() for _ in range(4)]
    metric_a, metric_b = uuid4(), uuid4()
    service.repo.list_confirmed_active_matches.return_value = [
        SimpleNamespace(task_id=tasks[0].task_id, metric_id=metric_a, match_level="strong"),
        SimpleNamespace(task_id=tasks[1].task_id, metric_id=metric_a, match_level="weak"),
        SimpleNamespace(
            task_id=tasks[2].task_id, metric_id=metric_b, match_level="no_clear_relation"
        ),
        SimpleNamespace(task_id=tasks[3].task_id, metric_id=metric_b, match_level="weak"),
    ]

    result = service.metrics.kpi_metric(tasks)

    assert result == {"linked_task_count": 4, "linked_metric_count": 2}


def test_overall_progress_includes_pending_review_and_uses_task_weight() -> None:
    service = _service()
    tasks = [
        _task("in_progress", task_weight=5),
        _task("blocked", task_weight=3),
        _task("pending_review", task_weight=2),
    ]
    service.metrics.task_progress_map = MagicMock(
        return_value={tasks[0].task_id: 60, tasks[1].task_id: 40, tasks[2].task_id: 100}
    )

    result = service.metrics.overall_progress(tasks)

    assert result["rate"] == 62.0
    assert result["task_count"] == 3
    assert result["data_quality_issue_count"] == 0


def test_pending_review_progress_is_not_hard_coded_to_100() -> None:
    service = _service()
    task = _task("pending_review", task_weight=5)
    service.metrics.task_progress_map = MagicMock(return_value={task.task_id: 80})

    result = service.metrics.overall_progress([task])

    assert result["rate"] == 80.0
    assert result["data_quality_issue_count"] == 1


def test_task_progress_uses_latest_decomposition_nodes_then_report_fallback() -> None:
    service = _service()
    task_with_nodes = _task()
    legacy = _task(latest_decomposition_id=None)
    service.repo.list_nodes_for_tasks.return_value = [
        SimpleNamespace(
            task_id=task_with_nodes.task_id,
            decomposition_id=task_with_nodes.latest_decomposition_id,
            progress_percent=100,
        ),
        SimpleNamespace(
            task_id=task_with_nodes.task_id,
            decomposition_id=task_with_nodes.latest_decomposition_id,
            progress_percent=50,
        ),
    ]
    service.repo.list_root_progress_reports.return_value = [
        SimpleNamespace(task_id=legacy.task_id, progress_percent=40)
    ]

    result = service.metrics.task_progress_map([task_with_nodes, legacy])

    assert result[task_with_nodes.task_id] == 75
    assert result[legacy.task_id] == 40


def test_quadrants_use_latest_persisted_priority_and_leave_unscored_visible() -> None:
    service = _service()
    tasks = [_task() for _ in range(3)]
    service.repo.list_priority_scores.return_value = [
        SimpleNamespace(task_id=tasks[0].task_id, priority_quadrant="important_urgent"),
        SimpleNamespace(task_id=tasks[0].task_id, priority_quadrant="routine"),
        SimpleNamespace(task_id=tasks[1].task_id, priority_quadrant="not_important_urgent"),
    ]

    result = service.metrics.quadrants(tasks)

    assert result["important_urgent"] == 1
    assert result["not_important_urgent"] == 1
    assert result["unscored_count"] == 1


def test_on_time_rate_distinguishes_empty_period_from_zero_percent() -> None:
    service = _service()
    scope = SimpleNamespace(department_ids=frozenset({uuid4()}))
    window = resolve_executive_period("week", NOW)
    service.repo.list_completed_in_period.return_value = []
    assert service.metrics.on_time_metric([], scope, window)["rate"] is None

    late = _task(
        completed_at=NOW - timedelta(days=1),
        deadline=NOW - timedelta(days=2),
    )
    service.repo.list_completed_in_period.return_value = []
    result = service.metrics.on_time_metric([late], scope, window)
    assert result["rate"] == 0.0


def test_active_metric_avoids_infinite_growth() -> None:
    service = _service()
    scope = SimpleNamespace(department_ids=frozenset())
    window = SimpleNamespace(previous_start=NOW, previous_end=NOW)
    service.repo.list_tasks_effective_before.return_value = []
    service.repo.list_status_logs_for_tasks.return_value = []
    assert service.metrics.active_metric([], scope, window)["change_rate"] == 0.0
    current = [_task() for _ in range(4)]
    result = service.metrics.active_metric(current, scope, window)
    assert result["change_rate"] is None
    assert result["change_direction"] == "new"


def test_previous_active_status_uses_first_later_transition_from_status() -> None:
    service = _service()
    scope = SimpleNamespace(department_ids=frozenset({uuid4()}))
    window = resolve_executive_period("week", NOW)
    task = _task(
        "archived",
        created_at=window.previous_start - timedelta(days=2),
        updated_at=NOW,
    )
    service.repo.list_tasks_effective_before.return_value = [task]
    service.repo.list_status_logs_for_tasks.return_value = [
        SimpleNamespace(
            task_id=task.task_id,
            from_status="in_progress",
            to_status="archived",
            created_at=window.previous_end + timedelta(hours=2),
        )
    ]

    result = service.metrics.active_metric([], scope, window)

    assert result["previous_count"] == 1
    assert result["change_rate"] == -100.0


def test_feature15_employee_task_filter_uses_main_assignee_inside_explicit_scope() -> None:
    service = _service()
    root = uuid4()
    actor_user = SimpleNamespace(status="active", role_type="executive", department_id=root)
    employee = SimpleNamespace(employee_no="E-1", name="Alice", status="active", department_id=root)
    service.repo.get_user.side_effect = (
        lambda employee_no: actor_user if employee_no == "E-X" else employee
    )
    service.repo.list_active_department_scopes.return_value = [SimpleNamespace(scope_id=str(root))]
    service.repo.list_active_departments.return_value = [_department(root, None, "Root")]
    task = _task(department_id=root, main_assignee_employee_no="E-1", start_time=NOW)
    service.repo.list_tasks_for_scope.return_value = [task]
    service.metrics.task_progress_map = MagicMock(return_value={task.task_id: 55})

    result = service.list_tasks(
        "E-X",
        department_id=root,
        employee_no="E-1",
        task_status="in_progress",
        quadrant=None,
        near_due=False,
        date_preset="all",
        start_date=None,
        end_date=None,
        search=None,
        sort_by="deadline",
        sort_order="asc",
        page=1,
        page_size=20,
    )

    service.repo.list_tasks_for_scope.assert_called_once_with({root}, "E-1")
    assert result["total"] == 1
    assert result["items"][0]["assignee_name"] == "Alice"
    assert result["items"][0]["progress_percent"] == 55


def test_feature15_employee_outside_selected_scope_is_denied_before_task_query() -> None:
    service = _service()
    root, outside = uuid4(), uuid4()
    actor_user = SimpleNamespace(status="active", role_type="executive", department_id=root)
    employee = SimpleNamespace(
        employee_no="E-2", name="Outside", status="active", department_id=outside
    )
    service.repo.get_user.side_effect = (
        lambda employee_no: actor_user if employee_no == "E-X" else employee
    )
    service.repo.list_active_department_scopes.return_value = [SimpleNamespace(scope_id=str(root))]
    service.repo.list_active_departments.return_value = [
        _department(root, None, "Root"),
        _department(outside, None, "Outside"),
    ]

    with pytest.raises(PermissionDeniedError):
        service.list_tasks(
            "E-X",
            department_id=root,
            employee_no="E-2",
            task_status=None,
            quadrant=None,
            near_due=False,
            date_preset="all",
            start_date=None,
            end_date=None,
            search=None,
            sort_by="deadline",
            sort_order="asc",
            page=1,
            page_size=20,
        )

    service.repo.list_tasks_for_scope.assert_not_called()
    service.repo.add_scope_denied_log.assert_called_once()


def test_feature15_members_are_limited_to_effective_department_scope() -> None:
    service = _service()
    root, child = uuid4(), uuid4()
    actor_user = SimpleNamespace(status="active", role_type="executive", department_id=root)
    service.repo.get_user.return_value = actor_user
    service.repo.list_active_department_scopes.return_value = [SimpleNamespace(scope_id=str(root))]
    service.repo.list_active_departments.return_value = [
        _department(root, None, "Root"),
        _department(child, root, "Child"),
    ]
    service.repo.list_active_users.return_value = [
        SimpleNamespace(employee_no="E-1", name="Alice", department_id=child)
    ]

    result = service.list_members("E-X", department_id=child)

    service.repo.list_active_users.assert_called_once_with({child})
    assert result == [{"employee_no": "E-1", "name": "Alice", "department_id": child}]


def test_feature15_quadrant_filter_keeps_feature14_execution_scope_and_period_overlap() -> None:
    service = _service()
    root = uuid4()
    actor_user = SimpleNamespace(status="active", role_type="executive", department_id=root)
    assignee = SimpleNamespace(employee_no="E-1", name="Alice", status="active", department_id=root)
    service.repo.get_user.side_effect = (
        lambda employee_no: actor_user if employee_no == "E-X" else assignee
    )
    service.repo.list_active_department_scopes.return_value = [SimpleNamespace(scope_id=str(root))]
    service.repo.list_active_departments.return_value = [_department(root, None, "Root")]
    window = resolve_executive_period("week", NOW)
    active = _task(
        "in_progress",
        department_id=root,
        effective_at=window.start - timedelta(days=2),
        start_time=window.start - timedelta(days=2),
        deadline=window.end + timedelta(days=1),
    )
    archived = _task(
        "archived",
        department_id=root,
        effective_at=window.start - timedelta(days=2),
        start_time=window.start,
        deadline=window.end,
    )
    service.repo.list_tasks_for_scope.return_value = [active, archived]
    service.metrics.latest_priority_map = MagicMock(
        return_value={
            active.task_id: "important_urgent",
            archived.task_id: "important_urgent",
        }
    )
    service.metrics.task_progress_map = MagicMock(return_value={active.task_id: 50})

    result = service.list_tasks(
        "E-X",
        department_id=root,
        employee_no=None,
        task_status=None,
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

    assert result["total"] == 1
    assert result["items"][0]["task_id"] == active.task_id
