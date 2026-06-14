#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_ROOT="$ROOT/ComfyUI"
PYTHON="$COMFY_ROOT/.venv/bin/python"
LOG_FILE="${COMFYUI_LOG:-/tmp/gemma4_comfyui.log}"
HOST="${COMFYUI_HOST:-127.0.0.1}"
PORT="${COMFYUI_PORT:-8188}"

if [ ! -d "$COMFY_ROOT" ]; then
  echo "ComfyUI is not installed at $COMFY_ROOT"
  exit 1
fi

if [ ! -x "$PYTHON" ]; then
  echo "ComfyUI Python environment is not ready at $PYTHON"
  exit 1
fi

if curl -s "http://$HOST:$PORT/object_info" >/dev/null 2>&1; then
  echo "ComfyUI is already running at http://$HOST:$PORT"
  exit 0
fi

echo "Starting ComfyUI at http://$HOST:$PORT"
cd "$COMFY_ROOT"
nohup env PYTORCH_ENABLE_MPS_FALLBACK=1 "$PYTHON" main.py --listen "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
echo $! > /tmp/gemma4_comfyui.pid

for _ in $(seq 1 60); do
  if curl -s "http://$HOST:$PORT/object_info" >/dev/null 2>&1; then
    echo "ComfyUI is ready."
    exit 0
  fi
  sleep 1
done

echo "ComfyUI did not become ready within 60 seconds. Log: $LOG_FILE"
exit 1
