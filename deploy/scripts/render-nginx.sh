#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="$ROOT_DIR/deploy/nginx/wangxu.conf.template"
OUTPUT="$ROOT_DIR/deploy/runtime/nginx/wangxu.conf"

: "${WANGXU_API_DOMAIN:?set WANGXU_API_DOMAIN, e.g. api.example.com}"
: "${WANGXU_AI_DOMAIN:?set WANGXU_AI_DOMAIN, e.g. ai.example.com}"

mkdir -p "$(dirname "$OUTPUT")"
sed \
  -e "s/__API_DOMAIN__/${WANGXU_API_DOMAIN//\//\\/}/g" \
  -e "s/__AI_DOMAIN__/${WANGXU_AI_DOMAIN//\//\\/}/g" \
  "$TEMPLATE" > "$OUTPUT"

printf 'Rendered %s\n' "$OUTPUT"
