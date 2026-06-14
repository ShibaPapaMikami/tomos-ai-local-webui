#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x "./scripts/stop-heavy.sh" ]; then
  echo "scripts/stop-heavy.sh が見つからないか、実行できません。"
  read -r -p "Enterで閉じます..."
  exit 1
fi

./scripts/stop-heavy.sh
echo
read -r -p "Enterで閉じます..."
