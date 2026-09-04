#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /opt/wangxu/releases/<version>" >&2
  exit 2
fi

release_dir="$(cd "$1" && pwd)"
[[ -f "$release_dir/deploy/docker-compose.production.yml" ]] || {
  echo "Not a Wangxu release directory: $release_dir" >&2
  exit 2
}

sudo mkdir -p /opt/wangxu
sudo ln -sfn "$release_dir" /opt/wangxu/current
printf '[PASS] current release -> %s\n' "$release_dir"
printf 'Run /opt/wangxu/current/deploy/scripts/deploy-compose.sh to apply this release.\n'
