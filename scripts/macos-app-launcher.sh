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

lock_owner_is_alive() {
  local lock_owner_pid
  lock_owner_pid="$(sed -n '1{s/ .*//;p;}' "$LOCK_OWNER_FILE" 2>/dev/null || true)"
  case "$lock_owner_pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  kill -0 "$lock_owner_pid" 2>/dev/null
}

lock_owner_is_dead() {
  local lock_owner_pid
  lock_owner_pid="$(sed -n '1{s/ .*//;p;}' "$LOCK_OWNER_FILE" 2>/dev/null || true)"
  case "$lock_owner_pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  ! kill -0 "$lock_owner_pid" 2>/dev/null
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
  if lock_has_expired || lock_owner_is_dead; then
    rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
    rmdir "$LOCK_DIR" 2>/dev/null
    return $?
  fi
  if lock_owner_is_alive; then
    return 1
  fi
  return 1
}

acquire_lock() {
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    if ! recover_stale_lock; then
      return 1
    fi
  done
  printf '%s\n' "$$" > "$LOCK_OWNER_FILE"
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
