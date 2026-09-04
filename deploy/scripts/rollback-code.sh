#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /opt/wangxu/releases/<previous-version>" >&2
  exit 2
fi

previous="$(cd "$1" && pwd)"
[[ -f "$previous/deploy/docker-compose.production.yml" ]] || {
  echo "Invalid previous release: $previous" >&2
  exit 2
}

sudo ln -sfn "$previous" /opt/wangxu/current
cd /opt/wangxu/current

docker compose -f deploy/docker-compose.production.yml build backend chatservice
docker compose -f deploy/docker-compose.production.yml up -d backend chatservice nginx
./deploy/scripts/health-check.sh

cat <<'MSG'
[PASS] Code rollback completed.
Database was NOT downgraded. Review the migration compatibility before any database rollback.
MSG
