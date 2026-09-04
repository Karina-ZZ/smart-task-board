"""Feature 16 Test9 release-candidate regression contracts.

Responsibilities:
- Freeze the PostgreSQL task-graph cleanup that prevents suite pollution.
- Freeze archive scope semantics and sparse available-actions projection.
- Require two consecutive PostgreSQL suite passes in the formal gate.

Does not own: PostgreSQL execution, product state transitions, or WeCom credentials.
Plan task: DEV-18 / Test9.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_business_postgresql_cleanup_follows_the_task_graph() -> None:
    text = _text("tests/integration/test_business_capabilities_postgresql.py")
    assert "delete(Notification).where(Notification.task_id.in_(task_ids))" in text
    assert "delete(ReminderRule).where(ReminderRule.task_id.in_(task_ids))" in text
    assert "delete(TaskIssue).where(TaskIssue.task_id.in_(task_ids))" in text
    assert ".values(latest_decomposition_id=None)" in text
    assert "delete(TaskDecompositionRecord).where(" in text


def test_archive_department_scope_is_executive_read_scope_not_employee_elevation() -> None:
    text = _text("tests/integration/test_business_capabilities_postgresql.py")
    assert 'name="Scoped Executive"' in text
    assert 'role_type="executive"' in text
    permission_tests = _text("tests/services/test_business_capabilities.py")
    assert "def test_employee_scope_does_not_expand_business_task_visibility" in permission_tests


def test_available_actions_projection_is_sparse() -> None:
    service = _text("app/services/task_board_query.py")
    integration = _text("tests/integration/test_task_board_api_postgresql.py")
    assert '"nodes": self._available_node_actions(' in service
    assert "if actions:" in service
    assert 'assert action_nodes == {alpha_nodes[0]: ["start_node"]}' in integration
    assert 'assert collaborator_actions.json()["nodes"] == []' in integration


def test_formal_postgresql_gate_requires_two_consecutive_suite_passes() -> None:
    gate = _text("scripts/run_postgresql_gate.sh")
    command = '"$PYTHON_BIN" -m pytest -m postgresql -q'
    assert gate.count(command) >= 2
    assert "PostgreSQL suite pass 1/2" in gate
    assert "PostgreSQL suite pass 2/2" in gate
