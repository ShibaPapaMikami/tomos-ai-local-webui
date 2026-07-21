#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

RESOURCE_ROOT="${TOMOS_RESOURCE_ROOT:-$(cd "$(dirname "$0")/../Resources/Gemma4_12B" && pwd)}"
WEB_URL="${TOMOS_WEB_URL:-http://127.0.0.1:54876}"
START_COMMAND="${TOMOS_START_COMMAND:-$RESOURCE_ROOT/Start_Mac.command}"
OPEN_COMMAND="${TOMOS_OPEN_COMMAND:-open}"
LOG_DIR="${TOMOS_LOG_DIR:-$HOME/Library/Logs/TOMOS AI}"
LOCK_DIR="${TOMOS_LAUNCH_LOCK_DIR:-$LOG_DIR/launcher.lock}"
LOCK_OWNER_FILE="$LOCK_DIR/owner"
LOCK_STALE_SECONDS="${TOMOS_LOCK_STALE_SECONDS:-300}"
EXPECTED_APP_VERSION="${TOMOS_APP_VERSION:-0.8.220}"
APP_SUPPORT_DIR="${TOMOS_APP_SUPPORT_DIR:-$HOME/Library/Application Support/TOMOS AI}"
LEGACY_ROOT="${TOMOS_LEGACY_ROOT:-/Applications/Gemma4_12B}"
STARTED_PROCESS_PID=""
STARTUP_SUCCEEDED=0

health_state() {
  local response
  local status_code
  local payload
  if ! response="$(curl -sS -i "$WEB_URL/api/health" 2>/dev/null)"; then
    printf '%s\n' "unreachable"
    return
  fi
  payload="$response"
  if [[ "$response" == HTTP/* ]]; then
    status_code="$(printf '%s\n' "$response" | sed -n '1s/HTTP\/[0-9.]* \([0-9][0-9][0-9]\).*/\1/p')"
    if [[ "$response" == *$'\r\n\r\n'* ]]; then
      payload="${response#*$'\r\n\r\n'}"
    else
      payload="${response#*$'\n\n'}"
    fi
    if [ "$status_code" != "200" ]; then
      printf '%s\n' "different-app"
      return
    fi
  fi
  python3 -B -c '
import json
import sys
try:
    payload = json.load(sys.stdin)
except json.JSONDecodeError:
    print("different-app")
    raise SystemExit(0)
if payload.get("appVersion") == sys.argv[1]:
    print("ready")
else:
    print("different-app")
' "$EXPECTED_APP_VERSION" <<< "$payload" 2>/dev/null || printf '%s\n' "different-app"
}

health_ok() {
  [ "$(health_state)" = "ready" ]
}

show_start_error() {
  osascript -e 'display dialog "TOMOS AIを起動できませんでした。Ollamaが起動しているか確認してください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

show_different_app_error() {
  osascript -e 'display dialog "別のTOMOSまたは古いバージョンのサーバーがこのポートで動作しています。終了してからTOMOS AIを開き直してください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

show_missing_start_command_error() {
  osascript -e 'display dialog "TOMOS AIの起動ファイルが見つかりません。アプリを入れ直してください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

wait_for_launcher() {
  for _ in $(seq 1 30); do
    sleep 1
    case "$(health_state)" in
      ready)
        exit 0
        ;;
      different-app)
        show_different_app_error
        exit 1
        ;;
    esac
    if [ ! -d "$LOCK_DIR" ]; then
      show_start_error
      exit 1
    fi
  done

  show_start_error
  exit 1
}

process_fingerprint() {
  ps -p "$1" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

read_lock_owner() {
  LOCK_OWNER_PID=""
  LOCK_OWNER_FINGERPRINT=""
  [ -r "$LOCK_OWNER_FILE" ] || return 1
  IFS='|' read -r LOCK_OWNER_PID LOCK_OWNER_FINGERPRINT < "$LOCK_OWNER_FILE" || true
  case "$LOCK_OWNER_PID" in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ -n "$LOCK_OWNER_FINGERPRINT" ]
}

lock_has_expired() {
  local lock_modified_at
  local now
  lock_modified_at="$(stat -f %m "$LOCK_DIR" 2>/dev/null || true)"
  now="$(date +%s)"
  case "$lock_modified_at" in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ $((now - lock_modified_at)) -ge "$LOCK_STALE_SECONDS" ]
}

recover_stale_lock() {
  local current_fingerprint
  if ! read_lock_owner; then
    if ! lock_has_expired; then
      return 1
    fi
  elif ! kill -0 "$LOCK_OWNER_PID" 2>/dev/null; then
    :
  else
    current_fingerprint="$(process_fingerprint "$LOCK_OWNER_PID")"
    if [ -z "$current_fingerprint" ] || [ "$current_fingerprint" = "$LOCK_OWNER_FINGERPRINT" ]; then
      return 1
    fi
  fi

  rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null
}

acquire_lock() {
  local owner_fingerprint
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    if ! recover_stale_lock; then
      return 1
    fi
  done
  owner_fingerprint="$(process_fingerprint "$$")"
  if [ -z "$owner_fingerprint" ]; then
    rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
    rmdir "$LOCK_DIR" 2>/dev/null
    return 1
  fi
  printf '%s|%s\n' "$$" "$owner_fingerprint" > "$LOCK_OWNER_FILE"
}

INITIAL_HEALTH_STATE="$(health_state)"
if [ "$INITIAL_HEALTH_STATE" = "ready" ]; then
  "$OPEN_COMMAND" "$WEB_URL"
  exit 0
fi
if [ "$INITIAL_HEALTH_STATE" = "different-app" ]; then
  show_different_app_error
  exit 1
fi

mkdir -p "$LOG_DIR"
if ! acquire_lock; then
  wait_for_launcher
fi

terminate_started_process() {
  if [ -n "$STARTED_PROCESS_PID" ] && kill -0 "$STARTED_PROCESS_PID" 2>/dev/null; then
    kill -TERM -- "-$STARTED_PROCESS_PID" 2>/dev/null || true
    wait "$STARTED_PROCESS_PID" 2>/dev/null || true
  fi
}

cleanup_launcher() {
  if [ "$STARTUP_SUCCEEDED" -ne 1 ]; then
    terminate_started_process
  fi
  rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup_launcher EXIT HUP INT TERM

LOCK_HEALTH_STATE="$(health_state)"
if [ "$LOCK_HEALTH_STATE" = "ready" ]; then
  "$OPEN_COMMAND" "$WEB_URL"
  exit 0
fi
if [ "$LOCK_HEALTH_STATE" = "different-app" ]; then
  show_different_app_error
  exit 1
fi

if [ ! -x "$START_COMMAND" ]; then
  show_missing_start_command_error
  exit 1
fi

migrate_legacy_data() {
  local relative_path
  local source_path
  local destination_path
  mkdir -p "$APP_SUPPORT_DIR"
  for relative_path in ".gemma4-data" "data/person-photos"; do
    source_path="$LEGACY_ROOT/$relative_path"
    destination_path="$APP_SUPPORT_DIR/$relative_path"
    if [ -d "$source_path" ] && [ ! -e "$destination_path" ]; then
      cp -R "$source_path" "$destination_path"
    fi
  done
}

migrate_legacy_data
export TOMOS_APP_SUPPORT_DIR="$APP_SUPPORT_DIR"

GEMMA_SKIP_BROWSER_OPEN=1 nohup python3 -B -c '
import os
import sys
os.setsid()
os.execv("/bin/bash", ["/bin/bash", sys.argv[1]])
' "$START_COMMAND" >"$LOG_DIR/launcher.log" 2>&1 &
STARTED_PROCESS_PID=$!

for _ in $(seq 1 30); do
  sleep 1
  POLL_HEALTH_STATE="$(health_state)"
  if [ "$POLL_HEALTH_STATE" = "ready" ]; then
    STARTUP_SUCCEEDED=1
    "$OPEN_COMMAND" "$WEB_URL"
    exit 0
  fi
  if [ "$POLL_HEALTH_STATE" = "different-app" ]; then
    show_different_app_error
    exit 1
  fi
done

show_start_error
exit 1
