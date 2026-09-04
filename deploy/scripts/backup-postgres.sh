#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.production.yml"
BACKUP_DIR="${WANGXU_BACKUP_DIR:-/var/backups/wangxu/postgres}"
RETENTION_DAYS="${WANGXU_BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%dT%H%M%S)"
OUTPUT="$BACKUP_DIR/smart_task_board_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"
umask 077

docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'pg_dump --format=custom --no-owner --no-privileges --username="$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$OUTPUT"

test -s "$OUTPUT"
sha256sum "$OUTPUT" > "$OUTPUT.sha256"
find "$BACKUP_DIR" -type f \( -name '*.dump' -o -name '*.dump.sha256' \) -mtime "+$RETENTION_DAYS" -delete
printf '[PASS] PostgreSQL backup created: %s\n' "$OUTPUT"
