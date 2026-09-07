#!/usr/bin/env bash
# Test14: approved gates only, no dependency upgrades or automatic DB/container deletion.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python_bin="${PYTHON_BIN:-python3.12}"
"$python_bin" - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit("TEST14 BLOCKED: formal acceptance requires Python 3.12")
PY
: "${POSTGRES_TEST_DATABASE_URL:?Provide the explicitly isolated EMPTY PostgreSQL gate database}"
# These exports affect this test process only, never the running prototype/WeCom services.
export WANGXU_BACKEND_ENV_FILE=/dev/null
export AUTH_MODE=test_header APP_ENV=test ALLOW_TEST_EMPLOYEE_HEADER=true
export PROTOTYPE_AUTH_ENABLED=false AI_PROVIDER=fake
export DATABASE_URL="$POSTGRES_TEST_DATABASE_URL"
"$python_bin" -m pip check
"$python_bin" -m ruff check .
"$python_bin" -m compileall -q app tests alembic cloud-functions scripts
"$python_bin" scripts/verify-test14-scope.py
# Original safety guards, empty-db migration, all 32 PG tests x3 and original 5x20 stress.
PYTHON_BIN="$python_bin" POSTGRES_GATE_PASSES=3 bash scripts/run_postgresql_gate.sh
(cd wechat-miniprogram && npm test)
while IFS= read -r -d '' file; do node --check "$file"; done < <(
  find wechat-miniprogram -name '*.js' -not -path '*/node_modules/*' -print0
)
(cd web && npm ci && npm run lint && npm test -- --run && npm run build)
(cd cloud-functions/ChatService &&
  PYTHONPATH=. "$python_bin" tests/test_task_intake.py &&
  PYTHONPATH=. "$python_bin" tests/test_auth.py &&
  PYTHONPATH=. "$python_bin" tests/test_config_file.py)
echo 'TEST14 TECHNICAL GATE PASS (live browser / Mini Program API / real AI are separate)'
