#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/backup.dump" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.production.yml"
BACKUP="$1"

[[ -f "$BACKUP" ]] || { echo "Backup not found: $BACKUP" >&2; exit 2; }
[[ "${WANGXU_ALLOW_RESTORE:-}" == "YES" ]] || {
  echo 'Restore is destructive. Set WANGXU_ALLOW_RESTORE=YES after a change-window approval.' >&2
  exit 2
}

cat "$BACKUP" | docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'pg_restore --clean --if-exists --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'

printf '[PASS] Restore command completed. Run migrations and application smoke tests next.\n'
