#!/usr/bin/env bash
# =============================================================================
# SmartTaskBoard local development launcher.
#
# Secrets are read from secrets/backend.env by default. Override with:
#   WANGXU_BACKEND_ENV_FILE=/absolute/path/backend.env ./scripts/start-dev.sh
#
# The script never creates or mutates secret files and never prints secret values.
# =============================================================================
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.homebrew/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BACKEND_ENV_FILE="${WANGXU_BACKEND_ENV_FILE:-$PROJECT_ROOT/secrets/backend.env}"
export WANGXU_BACKEND_ENV_FILE="$BACKEND_ENV_FILE"

if [ ! -f "$BACKEND_ENV_FILE" ]; then
  echo "ERROR: backend secret file not found: $BACKEND_ENV_FILE"
  echo "Create it from config-examples/backend.env.example and fill the required values."
  exit 1
fi

for key in DATABASE_URL POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD JWT_SECRET_KEY; do
  if ! grep -Eq "^${key}=.+" "$BACKEND_ENV_FILE"; then
    echo "ERROR: required setting $key is missing or empty in $BACKEND_ENV_FILE"
    exit 1
  fi
done

echo "==> [1/6] Check Docker"
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running. Start Docker Desktop first."
  exit 1
fi

echo "==> [2/6] Start PostgreSQL"
docker compose --env-file "$BACKEND_ENV_FILE" up -d postgres
for _ in $(seq 1 30); do
  if docker compose --env-file "$BACKEND_ENV_FILE" exec -T postgres \
    sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    echo "    PostgreSQL ready"
    break
  fi
  sleep 2
done
if ! docker compose --env-file "$BACKEND_ENV_FILE" exec -T postgres \
  sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
  echo "ERROR: PostgreSQL did not become ready."
  exit 1
fi

echo "==> [3/6] Activate Python 3.12 virtual environment"
if ! command -v python3.12 >/dev/null 2>&1; then
  echo "ERROR: python3.12 is required."
  exit 1
fi
if [ ! -d .venv ]; then
  python3.12 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -e ".[dev]"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"ERROR: Python 3.12 is required, got {sys.version}")
PY

echo "==> [4/6] Validate backend configuration"
python - <<'PY'
from app.core.config import get_settings
settings = get_settings()
print(f"    configuration valid (AUTH_MODE={settings.auth_mode}; secrets hidden)")
PY

echo "==> [5/6] Apply Alembic migrations"
python -m alembic upgrade head

echo "==> [6/6] Start FastAPI and Vite"
nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  > /tmp/stb-backend.log 2>&1 < /dev/null &

cd web
nohup npm run dev -- --host 127.0.0.1 --port 5173 \
  > /tmp/stb-frontend.log 2>&1 < /dev/null &
cd ..

sleep 6

echo
echo "============================================================"
echo " SmartTaskBoard development environment started"
echo "============================================================"
echo " Backend API : http://127.0.0.1:8000"
echo " Swagger     : http://127.0.0.1:8000/docs"
echo " Frontend    : http://127.0.0.1:5173"
echo " Backend log : /tmp/stb-backend.log"
echo " Frontend log: /tmp/stb-frontend.log"
echo " Secret file : $BACKEND_ENV_FILE"
echo "============================================================"
