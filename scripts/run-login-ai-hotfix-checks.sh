#!/usr/bin/env bash
# Static/local verification wrapper for the Web-login + AI clarification-gate hotfix.
# Real PostgreSQL/browser/WeChat gates remain explicit and are never reported as PASS unless executed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

bash -n scripts/start-web-demo.sh
python3 -m py_compile scripts/verify-ai-send-e2e.py
node wechat-miniprogram/tests/task-creation-clarification-hotfix.test.js

if grep -q 'if *(this\.data\.needsClarification)' wechat-miniprogram/pages/create-details/index.js; then
  echo "FAIL: create-details still contains a needsClarification hard gate" >&2
  exit 1
fi
if ! grep -Fq '必填信息完整后即可进入发送确认' wechat-miniprogram/pages/create-details/index.wxml; then
  echo "FAIL: advisory clarification UI contract missing" >&2
  exit 1
fi
if ! grep -Fq 'await screen.findByLabelText("演示用户")' web/src/app/router.test.tsx; then
  echo "FAIL: router async prototype-user assertion not fixed" >&2
  exit 1
fi

echo "STATIC_HOTFIX_CHECKS_PASS"

echo "Real environment gates (run separately when prerequisites exist):"
echo "  Web: STB_REAL_E2E=1 ... npx playwright test e2e/dev-18-real-login.spec.ts"
echo "  AI send: STB_E2E_API_BASE_URL=... ./scripts/verify-ai-send-e2e.py"
echo "  PostgreSQL/Test11 full gate: existing project release-gate script"
echo "  WeChat DevTools API-mode: manual/automator flow in docs/LOCAL_PORTS_AND_LOGIN_GUIDE.md"
