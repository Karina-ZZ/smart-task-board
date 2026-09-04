#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

required=(
  deploy/Dockerfile.backend
  deploy/Dockerfile.chatservice
  deploy/docker-compose.production.yml
  deploy/nginx/wangxu.conf.template
  deploy/env/backend.env.production.example
  deploy/env/chatservice.env.production.example
  deploy/scripts/preflight.sh
  deploy/scripts/render-nginx.sh
  deploy/scripts/health-check.sh
  deploy/scripts/backup-postgres.sh
  deploy/scripts/restore-postgres.sh
  deploy/scripts/deploy-compose.sh
  deploy/scripts/rollback-code.sh
  docs/deployment/01-PRODUCTION_DEPLOYMENT_GUIDE.md
  docs/deployment/02-PRODUCTION_ENVIRONMENT_VARIABLES.md
  docs/deployment/03-WECOM_DEPLOYMENT_GUIDE.md
  docs/deployment/04-PRODUCTION_RELEASE_CHECKLIST.md
  docs/deployment/05-OPERATIONS_AND_ROLLBACK.md
)

for path in "${required[@]}"; do
  [[ -s "$path" ]] || { echo "[FAIL] missing or empty: $path" >&2; exit 1; }
done

for script in deploy/scripts/*.sh; do
  bash -n "$script"
done

python3 - <<'PY'
from pathlib import Path
import re

compose = Path('deploy/docker-compose.production.yml').read_text()
assert 'postgres:' in compose
assert 'backend:' in compose
assert 'chatservice:' in compose
assert 'nginx:' in compose
assert '127.0.0.1:5432' not in compose, 'production database must not publish a host port'
assert 'ports:' not in compose.split('postgres:', 1)[1].split('backend:', 1)[0]

backend_env = Path('deploy/env/backend.env.production.example').read_text()
for token in ('APP_ENV=production', 'AUTH_MODE=wecom', 'ALLOW_TEST_EMPLOYEE_HEADER=false'):
    assert token in backend_env
assert 'touristappid' not in backend_env

chat_env = Path('deploy/env/chatservice.env.production.example').read_text()
assert 'APP_ENV=production' in chat_env
assert 'CHAT_REQUIRE_AUTH=true' in chat_env

nginx = Path('deploy/nginx/wangxu.conf.template').read_text()
assert '__API_DOMAIN__' in nginx and '__AI_DOMAIN__' in nginx
assert re.search(r'listen\s+443\s+ssl', nginx)

for secret_name in ('WECOM_APP_SECRET', 'DASHSCOPE_API_KEY', 'JWT_SECRET_KEY'):
    for path in Path('deploy').rglob('*'):
        if not path.is_file() or path.suffix in {'.png', '.jpg'}:
            continue
        text = path.read_text(errors='ignore')
        if secret_name in text:
            # Templates must contain placeholders, never plausible secret values.
            assert 'REPLACE_WITH' in text or path.suffix == '.sh' or 'environment variable' in text.lower()

print('[PASS] RELEASE-01 static deployment contracts')
PY

printf '[PASS] RELEASE-01 deployment files validated\n'
