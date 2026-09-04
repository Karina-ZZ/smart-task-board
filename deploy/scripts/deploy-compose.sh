#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.production.yml"

"$ROOT_DIR/deploy/scripts/preflight.sh"
"$ROOT_DIR/deploy/scripts/render-nginx.sh"

docker compose -f "$COMPOSE_FILE" config >/dev/null
printf '[PASS] docker compose configuration is valid\n'

docker compose -f "$COMPOSE_FILE" pull postgres nginx

docker compose -f "$COMPOSE_FILE" build backend chatservice

docker compose -f "$COMPOSE_FILE" up -d postgres

docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head
printf '[PASS] Alembic upgrade head completed\n'

docker compose -f "$COMPOSE_FILE" up -d backend chatservice nginx
"$ROOT_DIR/deploy/scripts/health-check.sh"

printf '[PASS] RELEASE-01 Compose deployment completed. Business E2E is still required before GO.\n'
