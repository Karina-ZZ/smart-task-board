#!/usr/bin/env bash
# Test14: consent-gated writes to an already-running isolated 5174/8001 environment.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python_bin="${PYTHON_BIN:-python3.12}"
if [[ "${STB_TEST14_ALLOW_TEST_WRITES:-}" != "1" ]]; then
  echo 'BLOCKED: verify the disposable test database, then set STB_TEST14_ALLOW_TEST_WRITES=1' >&2
  exit 2
fi
export STB_REAL_E2E=1 PLAYWRIGHT_SKIP_WEBSERVER=true
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://127.0.0.1:5174}"
export STB_REAL_E2E_API_BASE_URL="${STB_REAL_E2E_API_BASE_URL:-http://127.0.0.1:8001}"
export STB_E2E_API_BASE_URL="$STB_REAL_E2E_API_BASE_URL"
export STB_REAL_E2E_EMPLOYEE_NO="${STB_E2E_CREATOR:-E-CREATOR}"
if [[ "$STB_REAL_E2E_EMPLOYEE_NO" == "${STB_E2E_OBSERVER:-E-OBSERVER}" ]]; then
  echo 'BLOCKED: observer-only testing cannot replace the creator regression' >&2
  exit 2
fi
"$python_bin" scripts/verify-ai-send-e2e.py
(cd web && ./node_modules/.bin/playwright test \
  e2e/dev-18-real-login.spec.ts e2e/dev-19-test14-sent-task-workbench.spec.ts \
  --project=mobile-390 --repeat-each=3)
echo 'TEST14 LIVE HTTP + CREATOR BROWSER PASS (not Mini Program or production WeCom acceptance)'
