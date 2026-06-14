#!/usr/bin/env bash
set -u

COMFYUI_URL="${COMFYUI_URL:-http://127.0.0.1:8188}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
GEMMA_MODEL="${GEMMA_MODEL:-gemma4:12b}"
PID_FILE="/tmp/gemma4_comfyui.pid"

echo "ComfyUIのモデルメモリを解放します..."
curl -s -X POST "$COMFYUI_URL/free" \
  -H "Content-Type: application/json" \
  -d '{"unload_models":true,"free_memory":true}' >/dev/null 2>&1 || true

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
    echo "ComfyUIを停止します..."
    kill "$PID" >/dev/null 2>&1 || true
  fi
fi

PIDS="$(pgrep -f "ComfyUI.*main.py --listen 127.0.0.1 --port 8188" 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
  echo "残っているComfyUIプロセスを停止します..."
  for PID in $PIDS; do
    kill "$PID" >/dev/null 2>&1 || true
  done
fi

PORT_PIDS="$(lsof -ti tcp:8188 -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$PORT_PIDS" ]; then
  echo "8188番ポートで待機中のComfyUIプロセスを停止します..."
  for PID in $PORT_PIDS; do
    kill "$PID" >/dev/null 2>&1 || true
  done
fi

echo "OllamaのGemmaモデルをメモリから解放します..."
curl -s "$OLLAMA_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$GEMMA_MODEL\",\"prompt\":\"\",\"keep_alive\":0}" >/dev/null 2>&1 || true

echo "完了しました。Web UIは起動したまま使えます。"
