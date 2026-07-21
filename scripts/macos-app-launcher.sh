#!/usr/bin/env bash
set -euo pipefail

RESOURCE_ROOT="${TOMOS_RESOURCE_ROOT:-$(cd "$(dirname "$0")/../Resources/Gemma4_12B" && pwd)}"
WEB_URL="${TOMOS_WEB_URL:-http://127.0.0.1:54876}"
START_COMMAND="${TOMOS_START_COMMAND:-$RESOURCE_ROOT/Start_Mac.command}"
OPEN_COMMAND="${TOMOS_OPEN_COMMAND:-open}"
LOG_DIR="${TOMOS_LOG_DIR:-$HOME/Library/Logs/TOMOS AI}"
LOCK_DIR="${TOMOS_LAUNCH_LOCK_DIR:-$LOG_DIR/launcher.lock}"
LOCK_OWNER_FILE="$LOCK_DIR/owner"
LOCK_STALE_SECONDS="${TOMOS_LOCK_STALE_SECONDS:-300}"

health_ok() {
  curl -fsS "$WEB_URL/api/health" >/dev/null 2>&1
}

show_start_error() {
  osascript -e 'display dialog "TOMOS AIを起動できませんでした。Ollamaが起動しているか確認してください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

wait_for_launcher() {
  for _ in $(seq 1 30); do
    sleep 1
    if health_ok; then
      exit 0
    fi
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

if health_ok; then
  "$OPEN_COMMAND" "$WEB_URL"
  exit 0
fi

mkdir -p "$LOG_DIR"
if ! acquire_lock; then
  wait_for_launcher
fi

cleanup_lock() {
  rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup_lock EXIT HUP INT TERM

if health_ok; then
  "$OPEN_COMMAND" "$WEB_URL"
  exit 0
fi

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
