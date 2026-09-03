#!/usr/bin/env bash
set -euo pipefail

CONTAINER="smart-task-board-pg-gate"
PORT="46479"
DB="smarttaskboard_core_test"
USER="smarttaskboard_test"
PASSWORD="${POSTGRES_GATE_PASSWORD:-smarttaskboard_test_only}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed" >&2
  exit 2
fi
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: container $CONTAINER already exists; remove it explicitly before provisioning" >&2
  exit 3
fi

docker run -d --name "$CONTAINER" \
  -e POSTGRES_DB="$DB" \
  -e POSTGRES_USER="$USER" \
  -e POSTGRES_PASSWORD="$PASSWORD" \
  -p "127.0.0.1:${PORT}:5432" \
  postgres:16-alpine >/dev/null

for _ in $(seq 1 60); do
  if docker exec "$CONTAINER" pg_isready -U "$USER" -d "$DB" >/dev/null 2>&1; then
    echo "PostgreSQL gate database ready"
    echo "export POSTGRES_TEST_DATABASE_URL='postgresql+psycopg://${USER}:${PASSWORD}@127.0.0.1:${PORT}/${DB}'"
    echo "Cleanup when finished: docker rm -f $CONTAINER"
    exit 0
  fi
  sleep 1
done

echo "ERROR: PostgreSQL did not become ready" >&2
exit 4
