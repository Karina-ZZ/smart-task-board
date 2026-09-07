#!/usr/bin/env bash
# Test16: explicit consent; existing local HTTP regression + creator replay browser.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python_bin="${PYTHON_BIN:-python3.12}"
if [[ "${STB_TEST16_ALLOW_TEST_WRITES:-}" != "1" ]]; then
  echo 'BLOCKED: verify a disposable DB, then set STB_TEST16_ALLOW_TEST_WRITES=1' >&2
  exit 2
fi
"$python_bin" - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit("TEST16 BLOCKED: formal live gate requires Python 3.12")
PY
export STB_REAL_E2E=1 PLAYWRIGHT_SKIP_WEBSERVER=true
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://127.0.0.1:5174}"
export STB_REAL_E2E_API_BASE_URL="${STB_REAL_E2E_API_BASE_URL:-http://127.0.0.1:8001}"
export STB_E2E_API_BASE_URL="$STB_REAL_E2E_API_BASE_URL"
export STB_E2E_CREATOR="${STB_E2E_CREATOR:-E-CREATOR}"
if [[ -n "${STB_REAL_E2E_EMPLOYEE_NO:-}" && "$STB_REAL_E2E_EMPLOYEE_NO" != "$STB_E2E_CREATOR" ]]; then
  echo 'BLOCKED: HTTP creator and browser employee must be identical' >&2
  exit 2
fi
export STB_REAL_E2E_EMPLOYEE_NO="$STB_E2E_CREATOR"
if [[ "$STB_E2E_CREATOR" == "${STB_E2E_OBSERVER:-E-OBSERVER}" ]]; then
  echo 'BLOCKED: an observer cannot replace the creator regression' >&2
  exit 2
fi
# Compatibility flag is confined to this child process; no config file is rewritten.
export STB_TEST14_ALLOW_TEST_WRITES=1
"$python_bin" scripts/verify-test16-modal-scope.py
"$python_bin" scripts/verify-ai-send-e2e.py
(cd web && ./node_modules/.bin/playwright test \
  e2e/dev-18-real-login.spec.ts \
  e2e/dev-19-test14-sent-task-workbench.spec.ts \
  e2e/dev-20-test16-replay-workbench.spec.ts \
  --project=mobile-390 --repeat-each=3)
echo 'TEST16 LIVE HTTP + REPLAY CREATOR BROWSER PASS (not Mini Program or production SSO)'
