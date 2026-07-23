#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
TOMOS_OLLAMA_BIN_PATHS="${TOMOS_OLLAMA_BIN_PATHS:-/opt/homebrew/bin:/usr/local/bin:/Applications/Ollama.app/Contents/Resources}"
export PATH="$TOMOS_OLLAMA_BIN_PATHS:$PATH"
TOMOS_REQUIRE_OLLAMA="${TOMOS_REQUIRE_OLLAMA:-1}"
OLLAMA_DOWNLOAD_URL="${TOMOS_OLLAMA_DOWNLOAD_URL:-https://ollama.com/download}"

RESOURCE_ROOT="${TOMOS_RESOURCE_ROOT:-$(cd "$(dirname "$0")/../Resources/Gemma4_12B" && pwd)}"
WEB_URL="${TOMOS_WEB_URL:-http://127.0.0.1:54876}"
START_COMMAND="${TOMOS_START_COMMAND:-$RESOURCE_ROOT/Start_Mac.command}"
OPEN_COMMAND="${TOMOS_OPEN_COMMAND:-open}"
LOG_DIR="${TOMOS_LOG_DIR:-$HOME/Library/Logs/TOMOS AI}"
LOCK_DIR="${TOMOS_LAUNCH_LOCK_DIR:-$LOG_DIR/launcher.lock}"
LOCK_OWNER_FILE="$LOCK_DIR/owner"
LOCK_STALE_SECONDS="${TOMOS_LOCK_STALE_SECONDS:-300}"
EXPECTED_APP_VERSION="${TOMOS_APP_VERSION:-0.8.227}"
APP_SUPPORT_DIR="${TOMOS_APP_SUPPORT_DIR:-$HOME/Library/Application Support/TOMOS AI}"
LEGACY_ROOT="${TOMOS_LEGACY_ROOT:-/Applications/Gemma4_12B}"
MANAGED_SERVER_ROOT="${TOMOS_MANAGED_SERVER_ROOT:-$RESOURCE_ROOT}"
TERMINATE_COMMAND="${TOMOS_TERMINATE_COMMAND:-/bin/kill}"
STARTED_PROCESS_PID=""
STARTED_PROCESS_PGID=""
STARTED_PROCESS_TOKEN=""
STARTED_PROCESS_FINGERPRINT=""
PARENT_LAUNCHER_PID="$$"
PARENT_LAUNCHER_FINGERPRINT=""
HANDSHAKE_ID=""
PROCESS_OWNER_FILE=""
PROCESS_RELEASE_FILE=""
PROCESS_READY_FILE=""
MONITOR_READY_TIMEOUT_SECONDS="${TOMOS_MONITOR_READY_TIMEOUT_SECONDS:-15}"
STARTUP_SUCCEEDED=0

health_state() {
  local response
  local status_code
  local payload
  if ! response="$(curl -sS -i --connect-timeout "${TOMOS_CURL_CONNECT_TIMEOUT:-1}" --max-time "${TOMOS_CURL_MAX_TIME:-2}" "$WEB_URL/api/health" 2>/dev/null)"; then
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
actual = str(payload.get("appVersion") or "")
expected = sys.argv[1]
if actual == expected:
    print("ready")
elif payload.get("ok") is True:
    try:
        actual_parts = tuple(int(part) for part in actual.split("."))
        expected_parts = tuple(int(part) for part in expected.split("."))
    except ValueError:
        print("different-app")
    else:
        print("outdated-tomos" if actual_parts < expected_parts else "different-app")
else:
    print("different-app")
' "$EXPECTED_APP_VERSION" <<< "$payload" 2>/dev/null || printf '%s\n' "different-app"
}

health_ok() {
  [ "$(health_state)" = "ready" ]
}

tcp_port_is_occupied() {
  python3 -B - "$WEB_URL" "${TOMOS_TCP_CONNECT_TIMEOUT:-0.25}" <<'PY'
import socket
import sys
from urllib.parse import urlparse

parsed = urlparse(sys.argv[1])
host = parsed.hostname
port = parsed.port
if not host or not port:
    raise SystemExit(1)
try:
    with socket.create_connection((host, port), timeout=float(sys.argv[2])):
        raise SystemExit(0)
except OSError:
    raise SystemExit(1)
PY
}

managed_outdated_tomos_pid() {
  local port
  local listener_pid
  local listener_cwd
  command -v lsof >/dev/null 2>&1 || return 1
  port="$(python3 -B - "$WEB_URL" <<'PY'
import sys
from urllib.parse import urlparse
print(urlparse(sys.argv[1]).port or "")
PY
)"
  case "$port" in
    ''|*[!0-9]*) return 1 ;;
  esac
  listener_pid="$(lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1)"
  case "$listener_pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  listener_cwd="$(lsof -a -p "$listener_pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)"
  [ "$listener_cwd" = "$MANAGED_SERVER_ROOT" ] || return 1
  printf '%s\n' "$listener_pid"
}

stop_managed_outdated_tomos() {
  local listener_pid
  listener_pid="$(managed_outdated_tomos_pid)" || return 1
  "$TERMINATE_COMMAND" -TERM "$listener_pid" 2>/dev/null || return 1
  for _ in $(seq 1 30); do
    if ! tcp_port_is_occupied; then
      return 0
    fi
    /bin/sleep 0.1
  done
  return 1
}

show_start_error() {
  osascript -e 'display dialog "TOMOS AIを起動できませんでした。いったん終了して、もう一度開いてください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

show_different_app_error() {
  osascript -e 'display dialog "別のTOMOSまたは古いバージョンのサーバーがこのポートで動作しています。終了してからTOMOS AIを開き直してください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

show_missing_start_command_error() {
  osascript -e 'display dialog "TOMOS AIの起動ファイルが見つかりません。アプリを入れ直してください。" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
}

show_missing_ollama_guide() {
  local choice
  choice="$(osascript -e 'display dialog "TOMOS AIにはOllamaが必要です。\n\n「Ollamaを入れる」を押してインストールした後、TOMOS AIをもう一度開いてください。ターミナル操作は不要です。" buttons {"閉じる", "Ollamaを入れる"} default button "Ollamaを入れる" with icon caution' 2>/dev/null || true)"
  if [[ "$choice" == *"Ollamaを入れる"* ]]; then
    "$OPEN_COMMAND" "$OLLAMA_DOWNLOAD_URL" >/dev/null 2>&1 || true
  fi
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
    if lock_is_owned_by_live_launcher; then
      continue
    fi
    if tcp_port_is_occupied; then
      show_different_app_error
      exit 1
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

lock_is_owned_by_live_launcher() {
  local current_fingerprint
  read_lock_owner || return 1
  kill -0 "$LOCK_OWNER_PID" 2>/dev/null || return 1
  current_fingerprint="$(process_fingerprint "$LOCK_OWNER_PID")"
  [ -n "$current_fingerprint" ] && [ "$current_fingerprint" = "$LOCK_OWNER_FINGERPRINT" ]
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
if [ "$INITIAL_HEALTH_STATE" = "outdated-tomos" ]; then
  if stop_managed_outdated_tomos; then
    INITIAL_HEALTH_STATE="unreachable"
  else
    show_different_app_error
    exit 1
  fi
fi
if [ "$INITIAL_HEALTH_STATE" = "different-app" ]; then
  show_different_app_error
  exit 1
fi
if [ "$TOMOS_REQUIRE_OLLAMA" = "1" ] && ! command -v ollama >/dev/null 2>&1; then
  show_missing_ollama_guide
  exit 1
fi

mkdir -p "$LOG_DIR"
if ! acquire_lock; then
  wait_for_launcher
fi
if tcp_port_is_occupied; then
  show_different_app_error
  exit 1
fi

read_started_process_owner() {
  local owner_pid
  local owner_pgid
  local owner_token
  [ -r "$PROCESS_OWNER_FILE" ] || return 1
  IFS='|' read -r owner_pid owner_pgid owner_token < "$PROCESS_OWNER_FILE" || true
  case "$owner_pid:$owner_pgid" in
    *[!0-9:]*|:*) return 1 ;;
  esac
  [ "$owner_pid" = "$STARTED_PROCESS_PID" ] || return 1
  [ "$owner_token" = "$STARTED_PROCESS_TOKEN" ] || return 1
  STARTED_PROCESS_PGID="$owner_pgid"
}

started_process_owner_matches() {
  local current_fingerprint
  local current_pgid
  read_started_process_owner || return 1
  [ "$STARTED_PROCESS_PGID" = "$STARTED_PROCESS_PID" ] || return 1
  current_fingerprint="$(process_fingerprint "$STARTED_PROCESS_PID")"
  current_pgid="$(ps -p "$STARTED_PROCESS_PID" -o pgid= 2>/dev/null | tr -d ' ')"
  [ "$current_pgid" = "$STARTED_PROCESS_PID" ] || return 1
  [ -n "$STARTED_PROCESS_FINGERPRINT" ] && [ "$current_fingerprint" = "$STARTED_PROCESS_FINGERPRINT" ]
}

wait_for_started_process_owner() {
  local deadline
  local now
  local owner_fingerprint
  deadline=$(( $(date +%s) + MONITOR_READY_TIMEOUT_SECONDS ))
  while :; do
    if read_started_process_owner; then
      owner_fingerprint="$(process_fingerprint "$STARTED_PROCESS_PID")"
      if [ -n "$owner_fingerprint" ] && [ "$STARTED_PROCESS_PGID" = "$STARTED_PROCESS_PID" ]; then
        STARTED_PROCESS_FINGERPRINT="$owner_fingerprint"
        if started_process_owner_matches; then
          return 0
        fi
      fi
    fi
    if ! kill -0 "$STARTED_PROCESS_PID" 2>/dev/null; then
      return 1
    fi
    now="$(date +%s)"
    if [ "$now" -ge "$deadline" ]; then
      return 1
    fi
    /bin/sleep 0.05
  done
}

terminate_started_process() {
  if started_process_owner_matches; then
    kill -TERM -- "-$STARTED_PROCESS_PGID" 2>/dev/null || true
    wait "$STARTED_PROCESS_PID" 2>/dev/null || true
  elif [ -n "$STARTED_PROCESS_PID" ]; then
    : > "$PROCESS_RELEASE_FILE"
    wait "$STARTED_PROCESS_PID" 2>/dev/null || true
  fi
}

release_started_process() {
  if [ -n "$STARTED_PROCESS_PID" ]; then
    : > "$PROCESS_RELEASE_FILE"
    wait "$STARTED_PROCESS_PID" 2>/dev/null || true
  fi
}

cleanup_launcher() {
  if [ "$STARTUP_SUCCEEDED" -ne 1 ]; then
    terminate_started_process
  else
    release_started_process
  fi
  rm -f "$PROCESS_OWNER_FILE" "$PROCESS_RELEASE_FILE" "$PROCESS_READY_FILE" 2>/dev/null || true
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
if tcp_port_is_occupied; then
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
PARENT_LAUNCHER_FINGERPRINT="$(process_fingerprint "$PARENT_LAUNCHER_PID")"
if [ -z "$PARENT_LAUNCHER_FINGERPRINT" ]; then
  show_start_error
  exit 1
fi
STARTED_PROCESS_TOKEN="$(python3 -B -c 'import secrets; print(secrets.token_hex(24))')"
HANDSHAKE_ID="$PARENT_LAUNCHER_PID-$STARTED_PROCESS_TOKEN"
PROCESS_OWNER_FILE="$LOG_DIR/started-process.$HANDSHAKE_ID.owner"
PROCESS_RELEASE_FILE="$LOG_DIR/started-process.$HANDSHAKE_ID.release"
PROCESS_READY_FILE="$LOG_DIR/started-process.$HANDSHAKE_ID.ready"
rm -f "$PROCESS_OWNER_FILE" "$PROCESS_RELEASE_FILE" "$PROCESS_READY_FILE"

GEMMA_SKIP_BROWSER_OPEN=1 nohup python3 -B -c '
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

os.setsid()
start_command = sys.argv[1]
owner_file = Path(sys.argv[2])
release_file = Path(sys.argv[3])
ready_file = Path(sys.argv[4])
token = sys.argv[5]
parent_pid = int(sys.argv[6])
parent_fingerprint = sys.argv[7]

def release_requested():
    return release_file.exists()

def cleanup_handshake():
    for path in (owner_file, release_file, ready_file):
        path.unlink(missing_ok=True)

def parent_is_current():
    try:
        os.kill(parent_pid, 0)
        fingerprint = subprocess.check_output(
            ["ps", "-p", str(parent_pid), "-o", "lstart="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return fingerprint == parent_fingerprint

try:
    owner_delay_seconds = float(os.environ.get("TOMOS_OWNER_REGISTER_DELAY_SECONDS", "0"))
except ValueError:
    owner_delay_seconds = 0
deadline = time.monotonic() + max(owner_delay_seconds, 0)
while time.monotonic() < deadline:
    if release_requested() or not parent_is_current():
        cleanup_handshake()
        raise SystemExit(0)
    time.sleep(0.05)
try:
    owner_file.write_text(f"{os.getpid()}|{os.getpgrp()}|{token}\n", encoding="utf-8")
except OSError:
    cleanup_handshake()
    raise SystemExit(1)
while not ready_file.exists():
    if release_requested() or not parent_is_current():
        cleanup_handshake()
        raise SystemExit(0)
    time.sleep(0.05)
if release_requested():
    cleanup_handshake()
    raise SystemExit(0)
subprocess.Popen(["/bin/bash", start_command])
while not release_requested():
    if not parent_is_current():
        cleanup_handshake()
        os.killpg(os.getpgrp(), signal.SIGTERM)
        raise SystemExit(0)
    time.sleep(0.05)
cleanup_handshake()
' "$START_COMMAND" "$PROCESS_OWNER_FILE" "$PROCESS_RELEASE_FILE" "$PROCESS_READY_FILE" "$STARTED_PROCESS_TOKEN" "$PARENT_LAUNCHER_PID" "$PARENT_LAUNCHER_FINGERPRINT" >"$LOG_DIR/launcher.log" 2>&1 &
STARTED_PROCESS_PID=$!
if ! wait_for_started_process_owner; then
  show_start_error
  exit 1
fi
: > "$PROCESS_READY_FILE"

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
