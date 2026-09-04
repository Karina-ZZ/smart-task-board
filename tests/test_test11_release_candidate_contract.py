"""Feature 16 Test11 final technical-gate regression contracts.

Responsibilities:
- Freeze the six Ruff import-debt corrections found by the user's Test10 run.
- Require the Test11 gate to use Python 3.12, real Ruff checking, three same-DB
  PostgreSQL passes, and the existing 5 x 20 concurrency stress gate.
- Keep live WeCom E2E separate from the technical release result.

Does not own: product behavior, schema changes, or live provider credentials.
Plan task: DEV-18 / Test11.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_test10_reported_up035_imports_are_removed() -> None:
    wecom = _text("app/integrations/wecom/client.py")
    scoring = _text("app/services/features/performance_matching/scoring.py")
    assert "from collections.abc import Callable" in wecom
    assert "from typing import Callable" not in wecom
    assert "from collections.abc import Iterable, Mapping, Sequence" in scoring
    assert "from typing import Iterable, Mapping, Sequence" not in scoring


def test_test10_reported_i001_import_shapes_are_frozen() -> None:
    business = _text("app/services/business_capabilities.py")
    workflow = _text("app/services/task_workflow.py")
    intake = _text("cloud-functions/ChatService/services/task_intake.py")
    migration_test = _text("tests/migrations/test_alembic_metadata.py")

    assert "EXECUTION_TASK_STATUSES,\n    working_hours_between," in business
    assert "from app.services.shared.idempotency import (" not in workflow
    assert "import config\n\nfrom services import database" in intake
    assert migration_test.index("from alembic.config import Config") < migration_test.index(
        "from sqlalchemy import CheckConstraint"
    )


def test_test11_gate_is_check_only_and_runs_three_postgresql_passes() -> None:
    gate = _text("scripts/run_test11_release_gate.sh")
    assert 'python_bin="${PYTHON_BIN:-python3.12}"' in gate
    assert '"$python_bin" -m ruff check .' in gate
    assert "ruff check --fix" not in gate
    assert "POSTGRES_GATE_PASSES=3" in gate
    assert "tests/test_test11_release_candidate_contract.py" in gate
    assert "TEST11 TECHNICAL GATE PASS" in gate
    assert "run_wecom_real_e2e.py" in gate


def test_postgresql_gate_keeps_five_by_twenty_stress_contract() -> None:
    gate = _text("scripts/run_postgresql_gate.sh")
    assert "POSTGRES_GATE_PASSES=\"${POSTGRES_GATE_PASSES:-2}\"" in gate
    assert "for round in $(seq 1 20)" in gate
    assert gate.count('"tests/integration/') >= 5
    assert "test_concurrent_outbox_workers_must_not_double_send" in gate
    assert "POSTGRESQL_GATE_PASS" in gate
