#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() { echo "[TEST11 BLOCKED] $*" >&2; exit 2; }
python_bin="${PYTHON_BIN:-python3.12}"
command -v "$python_bin" >/dev/null 2>&1 || fail "Python 3.12 is required"
"$python_bin" - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"Python 3.12 required, got {sys.version}")
PY

[[ -n "${VIRTUAL_ENV:-}" ]] || fail "activate the project Python 3.12 virtual environment"
"$python_bin" -m pip install -e ".[dev]"
"$python_bin" -m pip check
"$python_bin" -m ruff check .
"$python_bin" -m compileall -q app cloud-functions tests alembic

# Fast local contracts catch the exact Test4 regressions before starting PostgreSQL.
RUN_POSTGRESQL_INTEGRATION=0 \
DATABASE_URL='sqlite+pysqlite:////tmp/smart_task_board_test6_contract.sqlite3' \
  "$python_bin" -m pytest -q \
  tests/test_test8_release_candidate_contract.py \
  tests/test_test9_release_candidate_contract.py \
  tests/test_test10_release_candidate_contract.py \
  tests/test_test11_release_candidate_contract.py \
  tests/test_postgresql_v11_fixture_contract.py \
  tests/test_dev_dependency_contract.py \
  tests/services/test_business_capabilities.py \
  tests/services/test_task_decomposition.py \
  tests/services/test_task_board_query.py \
  tests/api/test_task_board_routes.py

started_container=""
cleanup() {
  if [[ -n "$started_container" ]] && command -v docker >/dev/null 2>&1; then
    docker rm -f "$started_container" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ -z "${POSTGRES_TEST_DATABASE_URL:-}" ]]; then
  command -v docker >/dev/null 2>&1 || fail "Docker or POSTGRES_TEST_DATABASE_URL is required"
  docker info >/dev/null 2>&1 || fail "Docker daemon is not running"
  started_container="smart-task-board-pg-gate-test11"
  docker rm -f "$started_container" >/dev/null 2>&1 || true
  gate_password="test11-$(date +%s)-$RANDOM"
  docker run -d --name "$started_container" \
    -e POSTGRES_DB=smarttaskboard_core_test \
    -e POSTGRES_USER=smarttaskboard_test \
    -e POSTGRES_PASSWORD="$gate_password" \
    -p 127.0.0.1:46479:5432 postgres:16-alpine >/dev/null
  for _ in $(seq 1 30); do
    if docker exec "$started_container" pg_isready \
      -U smarttaskboard_test -d smarttaskboard_core_test >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  docker exec "$started_container" pg_isready \
    -U smarttaskboard_test -d smarttaskboard_core_test >/dev/null 2>&1 \
    || fail "PostgreSQL 16 gate container did not become ready"
  export POSTGRES_TEST_DATABASE_URL="postgresql+psycopg://smarttaskboard_test:${gate_password}@127.0.0.1:46479/smarttaskboard_core_test"
fi

PYTHON_BIN="$python_bin" POSTGRES_GATE_PASSES=3 \
POSTGRES_TEST_DATABASE_URL="$POSTGRES_TEST_DATABASE_URL" \
  ./scripts/run_postgresql_gate.sh

# Run all credential-free application gates before checking live-provider
# configuration. A missing WeCom/Qwen secret must not hide code regressions.
(
  cd wechat-miniprogram
  npm test
  find . -type f -name '*.js' -not -path './node_modules/*' -print0 | xargs -0 -n1 node --check
)
(
  cd web
  npm ci
  npm run lint
  npm test -- --run
  npm run build
)
(
  cd cloud-functions/ChatService
  PYTHONPATH=. "$python_bin" tests/test_task_intake.py
  PYTHONPATH=. "$python_bin" tests/test_auth.py
  PYTHONPATH=. "$python_bin" tests/test_config_file.py
)

echo "[TEST11 TECHNICAL GATE PASS] Ruff, compile, contracts, PostgreSQL x3, Outbox stress, non-PG, Mini Program, Web, and ChatService passed."
echo "Real WeCom production E2E remains a separate environment gate. Run scripts/run_wecom_real_e2e.py with a fresh wx.qy.login code and the real deployment environment."
