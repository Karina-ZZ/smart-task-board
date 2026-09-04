#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() { echo "[TEST8 BLOCKED] $*" >&2; exit 2; }
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
  started_container="smart-task-board-pg-gate-test8"
  docker rm -f "$started_container" >/dev/null 2>&1 || true
  gate_password="test8-$(date +%s)-$RANDOM"
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

PYTHON_BIN="$python_bin" POSTGRES_TEST_DATABASE_URL="$POSTGRES_TEST_DATABASE_URL" \
  ./scripts/run_postgresql_gate.sh

: "${WANGXU_BACKEND_ENV_FILE:?WANGXU_BACKEND_ENV_FILE is required for real WeCom gate}"
[[ -f "$WANGXU_BACKEND_ENV_FILE" ]] || fail "backend env file does not exist"
set -a
# shellcheck disable=SC1090
source "$WANGXU_BACKEND_ENV_FILE"
set +a
[[ "${AUTH_MODE:-}" == "wecom" ]] || fail "AUTH_MODE=wecom is required"
: "${WECOM_CORP_ID:?WECOM_CORP_ID is required}"
: "${WECOM_AGENT_ID:?WECOM_AGENT_ID is required}"
: "${WECOM_APP_SECRET:?WECOM_APP_SECRET is required}"
if grep -q '"appid"[[:space:]]*:[[:space:]]*"touristappid"' wechat-miniprogram/project.config.json; then
  fail "real WeCom gate requires a real mini-program AppID"
fi
grep -q 'mode:[[:space:]]*"api"' wechat-miniprogram/config.js \
  || fail 'real WeCom gate requires mode="api"'
if grep -q 'apiBaseUrl:[[:space:]]*""' wechat-miniprogram/config.js; then
  fail "real WeCom gate requires a non-empty apiBaseUrl"
fi

: "${WANGXU_CHAT_ENV_FILE:?WANGXU_CHAT_ENV_FILE is required for real Qwen gate}"
[[ -f "$WANGXU_CHAT_ENV_FILE" ]] || fail "ChatService env file does not exist"
set -a
# shellcheck disable=SC1090
source "$WANGXU_CHAT_ENV_FILE"
set +a
[[ "${CHAT_REQUIRE_AUTH:-}" == "true" ]] || fail "CHAT_REQUIRE_AUTH=true is required"
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is required}"
: "${CHAT_SERVICE_JWT_SECRET_KEY:?CHAT_SERVICE_JWT_SECRET_KEY is required}"

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

echo "[TEST8 AUTOMATED GATE PASS] automated gates passed."
echo "Run scripts/run_wecom_real_e2e.py with a fresh wx.qy.login code, then complete device E2E."
