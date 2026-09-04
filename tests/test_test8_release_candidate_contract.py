"""Static Test8 guards for the repaired DEV-18 release-candidate contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_ai_intake_draft_does_not_restore_client_hours() -> None:
    text = _text("app/services/business_capabilities.py")
    start = text.index("    def create_draft_from_extraction(")
    end = text.index("\n    def suggest_task_plan(", start)
    block = text[start:end]
    assert "estimated_hours=None" in block
    assert '_decimal(payload.get("estimated_hours"))' not in block


def test_ai_people_contract_is_parse_only_not_recommendation() -> None:
    prompt = _text("app/ai/prompts/task_intake.md")
    assert "明确提到" in prompt
    assert "主动推荐人员" in prompt
    assert "岗位" in prompt
    assert "负荷" in prompt


def test_postgresql_cleanup_removes_archives_before_tasks() -> None:
    files = (
        "tests/integration/test_core_workflow_postgresql.py",
        "tests/integration/test_core_workflow_api_postgresql.py",
        "tests/integration/test_completion_review_api_postgresql.py",
        "tests/integration/test_task_board_api_postgresql.py",
    )
    for relative in files:
        text = _text(relative)
        archive_delete = text.index("delete(TaskArchive)")
        task_delete = text.index("delete(Task).where")
        assert archive_delete < task_delete, relative


def test_postgresql_completion_contract_uses_automatic_archive() -> None:
    core = _text("tests/integration/test_core_workflow_postgresql.py")
    review = _text("tests/integration/test_completion_review_api_postgresql.py")
    assert 'assert stored_task.status == "archived"' in core
    assert '"completion_approved",' in core
    assert '"task_archived",' in core
    assert ') == (200, "archived", 13, "approved")' in review


def test_task_board_pending_node_actions_follow_v11_contract() -> None:
    text = _text("tests/integration/test_task_board_api_postgresql.py")
    assert 'assert action_nodes[alpha_nodes[0]] == ["start_node"]' in text
    assert "assert action_nodes[alpha_nodes[1]] == []" in text


def test_python_sources_fit_the_configured_ruff_line_length() -> None:
    long_lines: list[str] = []
    for base in ("app", "tests", "alembic", "cloud-functions", "scripts"):
        for path in (ROOT / base).rglob("*.py"):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if len(line) > 100:
                    long_lines.append(
                        f"{path.relative_to(ROOT)}:{line_number}:{len(line)}"
                    )
    assert long_lines == []
