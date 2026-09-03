from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.models import Task, TaskCompletionReview, TaskNode, TaskNodeDependency
from app.services.errors import BusinessValidationError
from app.services.task_board_query import (
    TaskBoardQueryService,
    _node_actions,
    _task_actions,
)

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)


def _task(status: str, **overrides: object) -> Task:
    values: dict[str, object] = {
        "task_id": uuid4(),
        "task_name": "Board task",
        "creator_employee_no": "E-CREATOR",
        "main_assignee_employee_no": "E-ASSIGNEE",
        "reviewer_employee_no": "E-REVIEWER",
        "status": status,
        "task_version": 3,
        "created_at": NOW - timedelta(days=1),
        "updated_at": NOW,
    }
    values.update(overrides)
    return Task(**values)


def _node(task: Task, status: str = "pending", **overrides: object) -> TaskNode:
    values: dict[str, object] = {
        "node_id": uuid4(),
        "task_id": task.task_id,
        "node_order": 1,
        "node_name": "Do work",
        "owner_employee_no": "E-OWNER",
        "status": status,
        "progress_percent": 0,
    }
    values.update(overrides)
    return TaskNode(**values)


def _review(task: Task, status: str = "submitted", **overrides: object) -> TaskCompletionReview:
    values: dict[str, object] = {
        "completion_review_id": uuid4(),
        "task_id": task.task_id,
        "review_round": 1,
        "submitted_by_employee_no": "E-ASSIGNEE",
        "completion_note": "Done",
        "deliverable_summary": "Delivered",
        "reviewer_employee_no": "E-REVIEWER",
        "review_status": status,
        "submitted_task_version": 3,
        "submitted_at": NOW,
        "is_legacy_import": False,
    }
    values.update(overrides)
    return TaskCompletionReview(**values)


def test_task_actions_match_phase4_state_and_actor_rules() -> None:
    node = _node(_task("draft"))
    draft = _task("draft")
    assert _task_actions(draft, "E-CREATOR", [node]) == ["submit_for_confirmation"]
    assert _task_actions(draft, "E-OUTSIDE", [node]) == []
    pending = _task("pending_confirmation")
    assert _task_actions(pending, "E-CREATOR", [node]) == ["confirm_and_send"]
    self_assigned = _task("pending_confirmation", main_assignee_employee_no="E-CREATOR")
    assert _task_actions(self_assigned, "E-CREATOR", [node]) == ["confirm_and_send"]
    acceptance = _task("pending_acceptance")
    assert _task_actions(acceptance, "E-ASSIGNEE", [node]) == ["accept", "return"]
    assert _task_actions(_task("returned"), "E-CREATOR", [node]) == ["resend"]
    completed_node = _node(_task("in_progress"), status="completed", progress_percent=100)
    assert _task_actions(_task("in_progress"), "E-ASSIGNEE", [completed_node]) == [
        "submit_progress_report",
        "report_task_issue",
        "submit_completion",
    ]
    assert "submit_completion" not in _task_actions(
        _task("in_progress"),
        "E-ASSIGNEE",
        [completed_node],
        has_non_closed_issue=True,
    )
    pending_review = _task("pending_review")
    assert _task_actions(
        pending_review,
        "E-REVIEWER",
        [node],
        current_review=_review(pending_review),
    ) == [
        "approve_completion",
        "reject_completion",
    ]
    assert _task_actions(pending_review, "E-REVIEWER", [node]) == []
    in_progress = _task("in_progress")
    assert _task_actions(in_progress, "E-CREATOR", [node]) == []
    assert _task_actions(
        in_progress,
        "E-PARTICIPANT",
        [node],
        is_task_participant=True,
    ) == []


def test_feature10_change_and_lifecycle_actions_follow_task_relationships() -> None:
    task = _task("blocked")
    node = _node(task)
    assignee_actions = _task_actions(
        task,
        "E-ASSIGNEE",
        [node],
        include_change_actions=True,
    )
    assert "submit_change_request" in assignee_actions
    assert "withdraw_task" not in assignee_actions
    creator_actions = _task_actions(
        task,
        "E-CREATOR",
        [node],
        include_change_actions=True,
    )
    assert {"reassign_task", "withdraw_task", "cancel_task"} <= set(creator_actions)


def test_targeted_rework_requires_explicit_reopen_before_resubmission() -> None:
    task = _task("in_progress")
    node = _node(task, status="completed", progress_percent=100)
    rejected = _review(
        task,
        status="rejected",
        review_result="rejected",
        reject_reason="Revise the selected node",
        rework_node_id=node.node_id,
        reviewed_task_version=4,
        reviewed_at=NOW,
    )

    blocked = _task_actions(
        task,
        "E-ASSIGNEE",
        [node],
        latest_review=rejected,
        rework_node_reopened=False,
    )
    assert "submit_completion" not in blocked

    reopened = _task_actions(
        task,
        "E-ASSIGNEE",
        [node],
        latest_review=rejected,
        rework_node_reopened=True,
    )
    assert "submit_completion" in reopened


def test_node_actions_keep_owner_fallback_and_dependency_rules() -> None:
    task = _task("in_progress")
    predecessor = _node(task, status="pending", node_order=1)
    successor = _node(task, status="pending", node_order=2)
    dependency = TaskNodeDependency(
        dependency_id=uuid4(),
        task_id=task.task_id,
        predecessor_node_id=predecessor.node_id,
        successor_node_id=successor.node_id,
    )
    nodes = {predecessor.node_id: predecessor, successor.node_id: successor}
    arguments = {
        "can_execute": True,
        "can_report": True,
        "has_active_blocker": False,
    }
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes, **arguments) == []
    predecessor.status = "completed"
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes, **arguments) == [
        "start_node",
    ]
    successor.status = "in_progress"
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes, **arguments) == [
        "update_node_progress",
        "complete_node",
    ]
    assert (
        _node_actions(
            task,
            successor,
            "E-NODE-PARTICIPANT",
            [],
            nodes,
            can_execute=False,
            can_report=False,
            has_active_blocker=False,
        )
        == []
    )
    assert _node_actions(
        task,
        successor,
        "E-NODE-PARTICIPANT",
        [],
        nodes,
        can_execute=False,
        can_report=True,
        has_active_blocker=False,
    ) == []
    successor.owner_employee_no = None
    assert _node_actions(task, successor, "E-ASSIGNEE", [], nodes, **arguments) == [
        "update_node_progress",
        "complete_node",
    ]
    assert "complete_node" not in _node_actions(
        task,
        successor,
        "E-ASSIGNEE",
        [],
        nodes,
        can_execute=True,
        can_report=True,
        has_active_blocker=True,
    )
    successor.status = "completed"
    assert _node_actions(
        task,
        successor,
        "E-REVIEWER",
        [],
        nodes,
        can_execute=False,
        can_report=False,
        has_active_blocker=False,
        can_reopen=True,
    ) == ["reopen_node"]


def test_inbox_projects_task_and_node_actions_with_expected_version() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)
    task = _task("in_progress", deadline=NOW - timedelta(hours=1))
    node = _node(task, status="in_progress")
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._issues = MagicMock()
    service._reports = MagicMock()
    service._completion_reviews = MagicMock()
    service._logs = MagicMock()
    service._completion_reviews.list_submitted_for_reviewer.return_value = []
    service._completion_reviews.list_rejected_rework_candidates_for_reviewer.return_value = []
    service._completion_reviews.get_current_submitted.return_value = None
    service._completion_reviews.get_latest.return_value = None
    service._issues.has_non_closed.return_value = False
    service._issues.has_active_blocker.return_value = False
    service._tasks.list_inbox_candidates.return_value = [task]
    service._tasks.list_participants.return_value = []
    service._nodes.list_nodes.return_value = [node]
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = [
        SimpleNamespace(employee_no="E-NODE-PARTICIPANT")
    ]
    service._users.list_by_employee_nos.return_value = [
        SimpleNamespace(employee_no="E-CREATOR", name="Creator"),
        SimpleNamespace(employee_no="E-ASSIGNEE", name="Assignee"),
    ]
    result = service.list_inbox("E-OWNER", action_code=None, limit=20, offset=0)
    assert result["total"] == 2
    assert {item["action_code"] for item in result["items"]} == {
        "update_node",
        "complete_node",
    }
    assert all(item["expected_task_version"] == 3 for item in result["items"])
    assert all(item["is_overdue"] is True for item in result["items"])


def test_inbox_projects_issue_owner_actions_and_issue_relation() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)
    task = _task("in_progress")
    node = _node(task, status="in_progress")
    issue = SimpleNamespace(
        issue_id=uuid4(),
        task_id=task.task_id,
        node_id=node.node_id,
        status="open",
        owner_employee_no="E-ISSUE-OWNER",
        reported_by_employee_no="E-ASSIGNEE",
        severity="high",
        issue_type="blocker",
        title="Waiting for access",
        created_at=NOW,
    )
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._issues = MagicMock()
    service._reports = MagicMock()
    service._completion_reviews = MagicMock()
    service._logs = MagicMock()
    service._completion_reviews.list_submitted_for_reviewer.return_value = []
    service._completion_reviews.list_rejected_rework_candidates_for_reviewer.return_value = []
    service._completion_reviews.get_current_submitted.return_value = None
    service._completion_reviews.get_latest.return_value = None
    service._tasks.list_inbox_candidates.return_value = []
    service._tasks.get_by_id.return_value = task
    service._tasks.list_participants.return_value = []
    service._nodes.list_nodes.return_value = [node]
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = []
    service._users.list_by_employee_nos.return_value = []
    service._issues.list_actionable_for.return_value = [issue]
    service._issues.has_non_closed.return_value = True
    service._issues.has_employee_relation.return_value = True

    result = service.list_inbox(
        "E-ISSUE-OWNER",
        action_code="handle_issue",
        limit=20,
        offset=0,
    )

    assert result["total"] == 1
    item = result["items"][0]
    assert item["allowed_actions"] == [
        "start_processing_issue",
        "resolve_issue",
        "reject_issue",
    ]
    assert item["node"]["node_id"] == node.node_id
    assert item["endpoint"].endswith(f"/{issue.issue_id}/actions")
    assert "issue_participant" in item["task"]["current_user_relations"]


def test_dashboard_uses_bounded_counts_three_day_window_and_completion_rate() -> None:
    session = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.side_effect = [2, 1]
    session.execute.return_value = count_result
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.scalars.return_value.all.return_value = []
    service = TaskBoardQueryService(session, clock=lambda: NOW)
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._issues = MagicMock()
    service._reports = MagicMock()
    service._completion_reviews = MagicMock()
    service._logs = MagicMock()
    service._completion_reviews.list_submitted_for_reviewer.return_value = []
    service._completion_reviews.list_rejected_rework_candidates_for_reviewer.return_value = []
    service._issues.count_open_owned_by.return_value = 6
    service._tasks.completion_stats_related.return_value = (10, 9)
    service._tasks.list_recent_related.return_value = []
    service._tasks.list_inbox_candidates.return_value = []
    service._tasks.list_related.return_value = ([], 0)
    service._tasks.count_related.side_effect = [2, 3, 4, 5, 7, 6, 8, 1]
    result = service.dashboard_summary("E-CREATOR")
    assert result == {
        "created_task_count": 2,
        "assigned_task_count": 3,
        "inbox_count": 0,
        "in_progress_count": 4,
        "pending_acceptance_count": 5,
        "today_task_count": 7,
        "due_within_3_days_count": 6,
        "due_within_7_days_count": 8,
        "overdue_count": 1,
        "report_due_count": 0,
        "open_issue_count": 6,
        "blocked_task_count": 6,
        "completion_review_count": 0,
        "unread_notification_count": 2,
        "open_conflict_count": 1,
        "due_window_days": 7,
        "on_time_completion_rate": 90,
        "on_time_completion_count": 9,
        "completion_sample_count": 10,
        "completion_rate_period_days": 90,
        "recent_tasks": [],
        "latest_workload": None,
        "priority_items": [],
    }
    service._tasks.completion_stats_related.assert_called_once_with(
        "E-CREATOR",
        completed_from=NOW - timedelta(days=90),
    )


def test_task_overview_rejects_invalid_custom_date_range() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)

    try:
        service.list_tasks(
            "E-CREATOR",
            date_preset="custom",
            start_date=date(2026, 8, 20),
            end_date=date(2026, 8, 18),
        )
    except BusinessValidationError as exc:
        assert "startDate" in str(exc)
    else:
        raise AssertionError("invalid custom date range should be rejected")


def test_task_overview_filters_near_due_terminal_states_and_paginates(monkeypatch) -> None:
    class AllowAll:
        def __init__(self, _session) -> None:
            pass

        def can_access_task(self, _actor, _task) -> bool:
            return True

    monkeypatch.setattr("app.services.task_board_query.PermissionScopeService", AllowAll)
    session = MagicMock()
    near = _task("in_progress", task_name="near", deadline=NOW + timedelta(days=3))
    later = _task("in_progress", task_name="later", deadline=NOW + timedelta(days=4))
    terminal_tasks = [
        _task(status, task_name=f"terminal-{status}", deadline=NOW + timedelta(days=1))
        for status in ("archived", "cancelled", "withdrawn", "merged", "closed")
    ]
    session.scalars.return_value.all.return_value = [later, near, *terminal_tasks]
    service = TaskBoardQueryService(session, clock=lambda: NOW)
    service._users = MagicMock()
    service._users.list_by_employee_nos.return_value = []
    service._nodes = MagicMock()
    service._nodes.list_nodes.return_value = []
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = []
    service._tasks = MagicMock()
    service._tasks.list_participants.return_value = []
    service._issues = MagicMock()
    service._issues.has_employee_relation.return_value = False
    service._issues.has_non_closed.return_value = False
    service._change_requests = MagicMock()
    service._change_requests.get_pending.return_value = None
    service._completion_reviews = MagicMock()
    service._completion_reviews.get_current_submitted.return_value = None
    service._completion_reviews.get_latest.return_value = None

    result = service.list_tasks(
        "E-CREATOR",
        near_due=True,
        page=1,
        page_size=1,
        limit=1,
        offset=0,
    )

    assert result["total"] == 1
    assert result["items"][0]["task_name"] == "near"
    assert result["status_counts"]["in_progress"] == 1


def test_node_overview_filters_permission_scoped_results_and_paginates(monkeypatch) -> None:
    class Scope:
        def __init__(self, _session) -> None:
            pass

        def can_access_task(self, _actor, task) -> bool:
            return task.task_name != "hidden"

    monkeypatch.setattr("app.services.task_board_query.PermissionScopeService", Scope)
    session = MagicMock()
    visible_task = _task("in_progress", task_name="visible")
    hidden_task = _task("in_progress", task_name="hidden")
    first_node = _node(
        visible_task,
        owner_employee_no="E-CREATOR",
        planned_start_time=NOW,
        planned_deadline=NOW + timedelta(days=1),
    )
    second_node = _node(
        visible_task,
        owner_employee_no="E-CREATOR",
        node_name="later node",
        node_order=2,
        planned_start_time=NOW,
        planned_deadline=NOW + timedelta(days=2),
    )
    hidden_node = _node(
        hidden_task,
        owner_employee_no="E-CREATOR",
        planned_start_time=NOW,
        planned_deadline=NOW + timedelta(days=1),
    )
    session.execute.return_value.all.return_value = [
        (second_node, visible_task),
        (hidden_node, hidden_task),
        (first_node, visible_task),
    ]
    service = TaskBoardQueryService(session, clock=lambda: NOW)
    service._users = MagicMock()
    service._users.list_by_employee_nos.return_value = [
        SimpleNamespace(employee_no="E-CREATOR", name="Creator")
    ]

    result = service.list_tasks(
        "E-CREATOR",
        mode="nodes",
        near_due=True,
        page=2,
        page_size=1,
        limit=1,
        offset=1,
    )

    assert result["total"] == 2
    assert result["page"] == 2
    assert result["items"][0]["node_name"] == "later node"
    assert result["items"][0]["owner"]["name"] == "Creator"
    assert result["status_counts"]["in_progress"] == 2


def test_executive_default_task_overview_can_consume_authorized_scope_candidates(
    monkeypatch,
) -> None:
    class ScopedAccess:
        def __init__(self, _session) -> None:
            pass

        def can_access_task(self, _actor, _task) -> bool:
            return True

    monkeypatch.setattr("app.services.task_board_query.PermissionScopeService", ScopedAccess)
    session = MagicMock()
    session.get.return_value = SimpleNamespace(status="active", role_type="executive")
    scoped_task = _task(
        "in_progress",
        task_name="authorized team task",
        creator_employee_no="E-OTHER",
        main_assignee_employee_no="E-REPORT",
        reviewer_employee_no="E-OTHER",
    )
    session.scalars.return_value.all.return_value = [scoped_task]
    service = TaskBoardQueryService(session, clock=lambda: NOW)
    service._users = MagicMock()
    service._users.list_by_employee_nos.return_value = []
    service._nodes = MagicMock()
    service._nodes.list_nodes.return_value = []
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = []
    service._tasks = MagicMock()
    service._tasks.list_participants.return_value = []
    service._issues = MagicMock()
    service._issues.has_employee_relation.return_value = False
    service._issues.has_non_closed.return_value = False
    service._change_requests = MagicMock()
    service._change_requests.get_pending.return_value = None
    service._completion_reviews = MagicMock()
    service._completion_reviews.get_current_submitted.return_value = None
    service._completion_reviews.get_latest.return_value = None

    result = service.list_tasks("E-EXEC", page=1, page_size=20, limit=20, offset=0)

    assert result["total"] == 1
    assert result["items"][0]["task_name"] == "authorized team task"
    statement = str(session.scalars.call_args_list[0].args[0])
    assert "WHERE" not in statement, (
        "default executive overview must not pre-filter to direct task relations"
    )


def _available_actions_service(task: Task, node: TaskNode) -> TaskBoardQueryService:
    service = TaskBoardQueryService.__new__(TaskBoardQueryService)
    service._session = MagicMock()
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._issues = MagicMock()
    service._reports = MagicMock()
    service._completion_reviews = MagicMock()
    service._change_requests = MagicMock()
    service._priorities = MagicMock()
    service._tasks.get_by_id.return_value = task
    service._tasks.list_participants.return_value = []
    service._nodes.list_nodes.return_value = [node]
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = []
    service._completion_reviews.get_current_submitted.return_value = None
    service._completion_reviews.get_latest.return_value = None
    service._change_requests.get_pending.return_value = None
    service._issues.has_non_closed.return_value = False
    service._issues.has_employee_relation.return_value = False
    return service


def test_available_actions_handles_task_without_priority_record(monkeypatch) -> None:
    task = _task("in_progress")
    node = _node(task)
    service = _available_actions_service(task, node)
    monkeypatch.setattr(
        "app.services.task_board_query.PermissionScopeService.can_access_task",
        lambda *_args, **_kwargs: True,
    )
    service._latest_priority = MagicMock(return_value=None)

    result = service.available_actions(task.task_id, "E-ASSIGNEE")

    assert result["priority_quadrant"] is None
    assert result["importance_score"] is None
    assert result["urgency_score"] is None
    assert result["remaining_hours"] is None
    assert result["sort_rank"] is None
    service._latest_priority.assert_called_once_with(task.task_id)


def test_available_actions_projects_latest_priority(monkeypatch) -> None:
    task = _task("in_progress")
    node = _node(task)
    service = _available_actions_service(task, node)
    monkeypatch.setattr(
        "app.services.task_board_query.PermissionScopeService.can_access_task",
        lambda *_args, **_kwargs: True,
    )
    service._latest_priority = MagicMock(
        return_value=SimpleNamespace(
            priority_quadrant="important_urgent",
            importance_score=72,
            urgency_score=88,
            remaining_hours=4,
            sort_rank=2,
        )
    )

    result = service.available_actions(task.task_id, "E-ASSIGNEE")

    assert result["priority_quadrant"] == "important_urgent"
    assert result["importance_score"] == "72"
    assert result["urgency_score"] == "88"
    assert result["remaining_hours"] == "4"
    assert result["sort_rank"] == 2
