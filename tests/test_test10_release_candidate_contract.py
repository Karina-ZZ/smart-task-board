"""Feature 16 Test10 final release-gate regression contracts.

Responsibilities:
- Freeze task-version-first status-log timeline ordering.
- Freeze the explicit Web testing-library dependency needed by clean npm installs.
- Require Test10 to exercise three PostgreSQL passes during candidate validation.

Does not own: PostgreSQL execution, product state transitions, or live WeCom credentials.
Plan task: DEV-18 / Test10.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_status_log_timeline_is_ordered_by_task_version_first() -> None:
    repository = _text("app/repositories/task_status_log.py")
    assert "TaskStatusLog.task_version," in repository
    assert "TaskStatusLog.task_version.desc()," in repository
    assert repository.index("TaskStatusLog.task_version,") < repository.index(
        "TaskStatusLog.created_at,"
    )


def test_completion_approval_can_emit_two_versions_at_the_same_timestamp() -> None:
    workflow = _text("app/services/task_workflow.py")
    start = workflow.index("def approve_completion(")
    end = workflow.index("def reject_completion(")
    section = workflow[start:end]
    assert 'now = _aware_utc(self._clock(), "clock")' in section
    assert 'action_type="completion_approved"' in section
    assert 'action_type="task_archived"' in section
    assert section.count("now=now") >= 2


def test_web_declares_testing_library_dom_directly() -> None:
    package = json.loads(_text("web/package.json"))
    lock = json.loads(_text("web/package-lock.json"))
    assert package["devDependencies"]["@testing-library/dom"] == "^10.4.1"
    assert lock["packages"][""]["devDependencies"]["@testing-library/dom"] == "^10.4.1"


def test_test10_release_gate_requests_three_postgresql_passes() -> None:
    gate = _text("scripts/run_test10_release_gate.sh")
    assert "POSTGRES_GATE_PASSES=3" in gate
    assert "tests/test_test10_release_candidate_contract.py" in gate
