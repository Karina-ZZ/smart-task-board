"""Static release guards for V1.1 PostgreSQL integration fixtures."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _block(path: Path, name: str, next_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(f"def {name}(")
    end = text.index(f"\ndef {next_name}(", start)
    return text[start:end]


def test_pg_api_fixtures_submit_task_level_fields_only() -> None:
    cases = (
        (ROOT / "tests/integration/test_core_workflow_api_postgresql.py", "_create_payload", "_post_action"),
        (ROOT / "tests/integration/test_completion_review_api_postgresql.py", "_create_ready_task", "_cleanup"),
        (ROOT / "tests/integration/test_task_board_api_postgresql.py", "_task_payload", "_post_action"),
    )
    forbidden = ('"nodes":', '"dependencies":', '"node_participants":', '"actual_hours":', '"estimated_hours":')
    required = (
        '"task_description":',
        '"task_goal":',
        '"task_source":',
        '"report_to_employee_no":',
        '"start_time":',
        '"deadline":',
        '"task_weight":',
    )
    for path, name, next_name in cases:
        block = _block(path, name, next_name)
        assert not any(token in block for token in forbidden), path.name
        assert all(token in block for token in required), path.name


def test_pg_service_fixtures_do_not_restore_creator_nodes_or_hours() -> None:
    block = _block(
        ROOT / "tests/integration/test_core_workflow_postgresql.py",
        "_command",
        "_services",
    )
    assert "nodes=" not in block
    assert "dependencies=" not in block
    assert "node_participants=" not in block
    assert "estimated_hours=" not in block
    assert "actual_hours=" not in block


def test_pg_main_flows_use_accept_then_v11_decomposition() -> None:
    for rel in (
        "tests/integration/test_business_capabilities_postgresql.py",
        "tests/integration/test_core_workflow_postgresql.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "confirm_task_plan(" not in text, rel
        assert "complete_v11_decomposition(" in text, rel


def test_self_assigned_pg_flow_still_requires_acceptance() -> None:
    path = ROOT / "tests/integration/test_core_workflow_postgresql.py"
    block = _block(path, "test_self_assigned_confirmation_flow", "test_version_conflict_and_permission_failure_leave_no_partial_changes")
    assert "confirm_self_assigned(" in block
    assert "accept_task(" in block
    assert '("pending_acceptance", 3)' in block
    assert '("decomposing", 4)' in block
