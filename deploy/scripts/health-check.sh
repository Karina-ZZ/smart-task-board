#!/usr/bin/env bash
set -euo pipefail

: "${WANGXU_API_DOMAIN:?set WANGXU_API_DOMAIN}"
: "${WANGXU_AI_DOMAIN:?set WANGXU_AI_DOMAIN}"

api_url="${WANGXU_API_URL:-https://${WANGXU_API_DOMAIN}}"
ai_url="${WANGXU_AI_URL:-https://${WANGXU_AI_DOMAIN}}"

curl --fail --silent --show-error --max-time 15 "$api_url/health/live" >/dev/null
printf '[PASS] FastAPI live: %s\n' "$api_url/health/live"

curl --fail --silent --show-error --max-time 15 "$api_url/health/ready" >/dev/null
printf '[PASS] FastAPI ready: %s\n' "$api_url/health/ready"

curl --fail --silent --show-error --max-time 15 "$ai_url/health" >/dev/null
printf '[PASS] ChatService health: %s\n' "$ai_url/health"
