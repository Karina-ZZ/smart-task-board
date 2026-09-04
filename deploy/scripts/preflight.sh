#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_ENV="${WANGXU_BACKEND_ENV_FILE:-/etc/wangxu/backend.env}"
CHAT_ENV="${WANGXU_CHAT_ENV_FILE:-/etc/wangxu/chatservice.env}"
TLS_DIR="${WANGXU_TLS_CERT_DIR:-/etc/wangxu/tls}"

fail() { printf '[BLOCKED] %s\n' "$*" >&2; exit 2; }
pass() { printf '[PASS] %s\n' "$*"; }

command -v docker >/dev/null 2>&1 || fail 'docker is required for the Compose deployment path'
docker compose version >/dev/null 2>&1 || fail 'docker compose plugin is required'
command -v curl >/dev/null 2>&1 || fail 'curl is required'
[[ -f "$BACKEND_ENV" ]] || fail "backend env not found: $BACKEND_ENV"
[[ -f "$CHAT_ENV" ]] || fail "ChatService env not found: $CHAT_ENV"
[[ -f "$TLS_DIR/fullchain.pem" ]] || fail "TLS certificate not found: $TLS_DIR/fullchain.pem"
[[ -f "$TLS_DIR/privkey.pem" ]] || fail "TLS private key not found: $TLS_DIR/privkey.pem"

set -a
# shellcheck disable=SC1090
source "$BACKEND_ENV"
set +a
[[ "${APP_ENV:-}" == "production" ]] || fail 'backend APP_ENV must be production'
[[ "${AUTH_MODE:-}" == "wecom" ]] || fail 'AUTH_MODE must be wecom'
[[ "${ALLOW_TEST_EMPLOYEE_HEADER:-}" == "false" ]] || fail 'ALLOW_TEST_EMPLOYEE_HEADER must be false'
[[ "${PROTOTYPE_AUTH_ENABLED:-}" == "false" ]] || fail 'PROTOTYPE_AUTH_ENABLED must be false'
[[ -n "${WECOM_CORP_ID:-}" ]] || fail 'WECOM_CORP_ID is required'
[[ -n "${WECOM_AGENT_ID:-}" ]] || fail 'WECOM_AGENT_ID is required'
[[ -n "${WECOM_APP_SECRET:-}" ]] || fail 'WECOM_APP_SECRET is required'
[[ ${#JWT_SECRET_KEY} -ge 32 ]] || fail 'JWT_SECRET_KEY must be at least 32 characters'
[[ ${#CHAT_SERVICE_JWT_SECRET_KEY} -ge 32 ]] || fail 'CHAT_SERVICE_JWT_SECRET_KEY must be at least 32 characters'
[[ "${DATABASE_URL:-}" != *"_test"* ]] || fail 'DATABASE_URL appears to reference a test database'
backend_chat_secret="$CHAT_SERVICE_JWT_SECRET_KEY"

unset APP_ENV CHAT_REQUIRE_AUTH CHAT_SERVICE_JWT_SECRET_KEY
set -a
# shellcheck disable=SC1090
source "$CHAT_ENV"
set +a
[[ "${APP_ENV:-}" == "production" ]] || fail 'ChatService APP_ENV must be production'
[[ "${CHAT_REQUIRE_AUTH:-}" == "true" ]] || fail 'CHAT_REQUIRE_AUTH must be true'
[[ -n "${DASHSCOPE_API_KEY:-}" ]] || fail 'DASHSCOPE_API_KEY is required'
[[ ${#CHAT_SERVICE_JWT_SECRET_KEY} -ge 32 ]] || fail 'ChatService JWT secret must be at least 32 characters'
[[ "$CHAT_SERVICE_JWT_SECRET_KEY" == "$backend_chat_secret" ]] || fail 'backend/chatservice shared JWT secrets do not match'

: "${WANGXU_API_DOMAIN:?set WANGXU_API_DOMAIN}"
: "${WANGXU_AI_DOMAIN:?set WANGXU_AI_DOMAIN}"
[[ "$WANGXU_API_DOMAIN" != "$WANGXU_AI_DOMAIN" ]] || fail 'API and AI domains must be different hostnames'

pass 'production environment and TLS preflight checks passed'
pass 'business source code was not modified by this check'
