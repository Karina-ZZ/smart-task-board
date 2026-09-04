#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
EXPECTED_DB="smarttaskboard_core_test"
EXPECTED_HOST="127.0.0.1"
EXPECTED_PORT="46479"
EXPECTED_HEAD="c2d3e4f5a6b7"
POSTGRES_GATE_PASSES="${POSTGRES_GATE_PASSES:-2}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON_BIN is required. Project supports Python >=3.12,<3.13." >&2
  exit 2
fi
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"ERROR: Python 3.12 is required for the formal gate, got {sys.version}")
import psycopg
print("psycopg", psycopg.__version__)
PY

: "${POSTGRES_TEST_DATABASE_URL:?Set POSTGRES_TEST_DATABASE_URL to the isolated test database}"
export RUN_POSTGRESQL_INTEGRATION=1
export DATABASE_URL="$POSTGRES_TEST_DATABASE_URL"

"$PYTHON_BIN" - <<'PY'
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
url = make_url(os.environ["POSTGRES_TEST_DATABASE_URL"])
expected = ("postgresql+psycopg", "127.0.0.1", 46479, "smarttaskboard_core_test")
actual = (url.drivername, url.host, url.port, url.database)
if actual != expected:
    raise SystemExit(f"ERROR: unsafe PostgreSQL target {actual}; expected {expected}")
engine = create_engine(os.environ["POSTGRES_TEST_DATABASE_URL"], pool_pre_ping=True)
try:
    tables = set(inspect(engine).get_table_names(schema="public"))
finally:
    engine.dispose()
if tables:
    raise SystemExit(f"ERROR: gate requires an empty isolated database; found tables: {sorted(tables)}")
print("isolated empty database safety check: PASS")
PY

"$PYTHON_BIN" -m alembic upgrade head
CURRENT_HEAD="$("$PYTHON_BIN" -m alembic current 2>/dev/null | awk '{print $1}' | tail -1)"
if [[ "$CURRENT_HEAD" != "$EXPECTED_HEAD" ]]; then
  echo "ERROR: Alembic head mismatch: $CURRENT_HEAD != $EXPECTED_HEAD" >&2
  exit 3
fi

echo "Alembic empty-db upgrade: PASS ($CURRENT_HEAD)"

if ! [[ "$POSTGRES_GATE_PASSES" =~ ^[2-9][0-9]*$ ]]; then
  echo "ERROR: POSTGRES_GATE_PASSES must be an integer >= 2" >&2
  exit 4
fi
for pass_number in $(seq 1 "$POSTGRES_GATE_PASSES"); do
  # The first pass proves behavior on a freshly migrated database. Every
  # later pass reuses the same database and therefore proves test isolation.
  echo "PostgreSQL suite pass ${pass_number}/${POSTGRES_GATE_PASSES}"
  "$PYTHON_BIN" -m pytest -m postgresql -q
done

STRESS_TESTS=(
  "tests/integration/test_repositories_postgresql.py::test_task_for_update_blocks_a_second_session_with_bounded_timeout"
  "tests/integration/test_feature13_postgresql.py::test_concurrent_accept_has_one_effect_real_postgresql"
  "tests/integration/test_feature13_postgresql.py::test_concurrent_accept_reject_finishes_in_one_coherent_state"
  "tests/integration/test_feature13_postgresql.py::test_notification_unique_constraint_wins_concurrent_insert"
  "tests/integration/test_feature13_postgresql.py::test_concurrent_outbox_workers_must_not_double_send"
)
for test_id in "${STRESS_TESTS[@]}"; do
  for round in $(seq 1 20); do
    echo "stress [$round/20] $test_id"
    "$PYTHON_BIN" -m pytest -q "$test_id"
  done
done

# Re-run the ordinary suite to prove the PostgreSQL gate changes did not regress non-PG behavior.
RUN_POSTGRESQL_INTEGRATION=0 DATABASE_URL='sqlite+pysqlite:////tmp/smart_task_board_pg_gate_nonpg.sqlite3' \
  "$PYTHON_BIN" -m pytest -m 'not postgresql' -q

echo "POSTGRESQL_GATE_PASS"
