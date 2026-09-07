#!/usr/bin/env bash
# =============================================================================
# SmartTaskBoard isolated Web prototype-login launcher.
#
# Purpose:
# - Start the exact source tree that contains this script.
# - Keep the proven Test11 local topology separate from legacy 5173/8000 services.
# - Refuse to reuse unknown processes already occupying the selected ports.
# - Never migrate, seed, create, drop, or clean a database.
#
# Required preparation:
#   cp config-examples/web-demo.env.example /tmp/stb-web-demo.env
#   # Fill DATABASE_URL and JWT_SECRET_KEY in /tmp/stb-web-demo.env.
#   WANGXU_WEB_DEMO_ENV_FILE=/tmp/stb-web-demo.env ./scripts/start-web-demo.sh
#
# Open in browser after READY:
#   http://127.0.0.1:5174/login
# Stop both processes with Ctrl+C.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BACKEND_PORT="${STB_WEB_DEMO_BACKEND_PORT:-8001}"
FRONTEND_PORT="${STB_WEB_DEMO_FRONTEND_PORT:-5174}"
BACKEND_HOST="127.0.0.1"
FRONTEND_HOST="127.0.0.1"
BACKEND_ENV_FILE="${WANGXU_WEB_DEMO_ENV_FILE:-${WANGXU_BACKEND_ENV_FILE:-}}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [ -z "$BACKEND_ENV_FILE" ]; then
  fail "set WANGXU_WEB_DEMO_ENV_FILE to an isolated prototype env file; do not use production backend.env"
fi
if [ ! -f "$BACKEND_ENV_FILE" ]; then
  fail "Web demo env file not found: $BACKEND_ENV_FILE"
fi
if [ ! -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  fail "missing .venv. Prepare the approved Python 3.12 environment before starting the demo"
fi
if [ ! -d "$PROJECT_ROOT/web/node_modules" ]; then
  fail "web/node_modules is missing. Run npm ci in web/ before starting the demo"
fi

require_env_line() {
  local key="$1"
  local expected="$2"
  if ! grep -Eq "^${key}=${expected}$" "$BACKEND_ENV_FILE"; then
    fail "$key must be ${expected} in the isolated Web demo env file"
  fi
}
require_nonempty_env_line() {
  local key="$1"
  if ! grep -Eq "^${key}=.+$" "$BACKEND_ENV_FILE"; then
    fail "$key is missing or empty in $BACKEND_ENV_FILE"
  fi
}

require_env_line "APP_ENV" "development"
require_env_line "AUTH_MODE" "prototype"
require_env_line "PROTOTYPE_AUTH_ENABLED" "true"
require_env_line "ALLOW_TEST_EMPLOYEE_HEADER" "false"
require_nonempty_env_line "PROTOTYPE_USER_EMPLOYEE_NOS"
require_nonempty_env_line "DATABASE_URL"
require_nonempty_env_line "JWT_SECRET_KEY"

EXPECTED_ORIGIN="http://${FRONTEND_HOST}:${FRONTEND_PORT}"
if ! grep -E '^CORS_ALLOWED_ORIGINS=' "$BACKEND_ENV_FILE" | grep -Fq "$EXPECTED_ORIGIN"; then
  fail "CORS_ALLOWED_ORIGINS must include ${EXPECTED_ORIGIN}"
fi

port_in_use() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PY'
import socket
import sys
host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket()
s.settimeout(0.25)
try:
    result = s.connect_ex((host, port)) == 0
finally:
    s.close()
raise SystemExit(0 if result else 1)
PY
}

if port_in_use "$BACKEND_HOST" "$BACKEND_PORT"; then
  fail "backend port ${BACKEND_PORT} is already in use. Do not reuse an unknown/old instance"
fi
if port_in_use "$FRONTEND_HOST" "$FRONTEND_PORT"; then
  fail "frontend port ${FRONTEND_PORT} is already in use. Do not reuse an unknown/old Vite instance"
fi

export WANGXU_BACKEND_ENV_FILE="$BACKEND_ENV_FILE"
export VITE_API_BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"

"$PROJECT_ROOT/.venv/bin/python" - <<'PY'
from app.core.config import get_settings
settings = get_settings()
print(
    "Config OK: "
    f"APP_ENV={settings.app_env}; AUTH_MODE={settings.auth_mode}; "
    f"prototype_users={len(settings.prototype_employee_nos)}; secrets hidden"
)
PY

BACKEND_LOG="${TMPDIR:-/tmp}/stb-web-demo-backend-${BACKEND_PORT}.log"
FRONTEND_LOG="${TMPDIR:-/tmp}/stb-web-demo-frontend-${FRONTEND_PORT}.log"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  local code=$?
  trap - EXIT INT TERM
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  exit "$code"
}
trap cleanup EXIT INT TERM

echo "Project root : $PROJECT_ROOT"
echo "Backend env  : $BACKEND_ENV_FILE"
echo "Backend URL  : http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Frontend URL : http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "Login URL    : http://${FRONTEND_HOST}:${FRONTEND_PORT}/login"
echo "Note         : 5173/8000 are not reused automatically; production WeCom login is separate."

echo "==> Starting FastAPI"
"$PROJECT_ROOT/.venv/bin/python" -m uvicorn app.main:app \
  --host "$BACKEND_HOST" --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

backend_ready=false
for _ in $(seq 1 60); do
  if curl --noproxy '*' -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/health/ready" >/dev/null 2>&1; then
    backend_ready=true
    break
  fi
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    tail -n 40 "$BACKEND_LOG" >&2 || true
    fail "FastAPI exited before becoming ready"
  fi
  sleep 1
done
if [ "$backend_ready" != true ]; then
  tail -n 40 "$BACKEND_LOG" >&2 || true
  fail "FastAPI readiness check timed out"
fi

PROTOTYPE_USERS_JSON="$(curl --noproxy '*' -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/api/v1/auth/prototype-users")" || {
  tail -n 40 "$BACKEND_LOG" >&2 || true
  fail "prototype-users endpoint failed"
}
"$PROJECT_ROOT/.venv/bin/python" - "$PROTOTYPE_USERS_JSON" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
if not isinstance(payload, list) or not payload:
    raise SystemExit("ERROR: prototype-users returned no usable demo users")
print(f"Prototype users OK: {len(payload)} available")
PY

echo "==> Starting Vite"
(
  cd "$PROJECT_ROOT/web"
  exec npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

frontend_ready=false
for _ in $(seq 1 60); do
  if curl --noproxy '*' -fsS "http://${FRONTEND_HOST}:${FRONTEND_PORT}/login" >/dev/null 2>&1; then
    frontend_ready=true
    break
  fi
  if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    tail -n 40 "$FRONTEND_LOG" >&2 || true
    fail "Vite exited before becoming ready"
  fi
  sleep 1
done
if [ "$frontend_ready" != true ]; then
  tail -n 40 "$FRONTEND_LOG" >&2 || true
  fail "Vite readiness check timed out"
fi

echo
echo "============================================================"
echo " WEB DEMO READY"
echo " Open: http://${FRONTEND_HOST}:${FRONTEND_PORT}/login"
echo " API : http://${BACKEND_HOST}:${BACKEND_PORT}"
echo " Docs: http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
echo " Backend log : $BACKEND_LOG"
echo " Frontend log: $FRONTEND_LOG"
echo " Stop: Ctrl+C"
echo "============================================================"

wait "$BACKEND_PID" "$FRONTEND_PID"
