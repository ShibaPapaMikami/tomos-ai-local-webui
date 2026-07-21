#!/usr/bin/env bash
set -euo pipefail

RESOURCE_ROOT="${TOMOS_RESOURCE_ROOT:-$(cd "$(dirname "$0")/../Resources/Gemma4_12B" && pwd)}"
WEB_URL="${TOMOS_WEB_URL:-http://127.0.0.1:54876}"
START_COMMAND="${TOMOS_START_COMMAND:-$RESOURCE_ROOT/Start_Mac.command}"
OPEN_COMMAND="${TOMOS_OPEN_COMMAND:-open}"
LOG_DIR="${TOMOS_LOG_DIR:-$HOME/Library/Logs/TOMOS AI}"

health_ok() {
  curl -fsS "$WEB_URL/api/health" >/dev/null 2>&1
}

show_start_error() {
  osascript -e 'display dialog "TOMOS AIを起動できませんでした。Ollamaが起動しているか確認してください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

if health_ok; then
  "$OPEN_COMMAND" "$WEB_URL"
  exit 0
fi

mkdir -p "$LOG_DIR"
GEMMA_SKIP_BROWSER_OPEN=1 nohup /bin/bash "$START_COMMAND" >"$LOG_DIR/launcher.log" 2>&1 &

for _ in $(seq 1 30); do
  sleep 1
  if health_ok; then
    "$OPEN_COMMAND" "$WEB_URL"
    exit 0
  fi
done

show_start_error
exit 1
