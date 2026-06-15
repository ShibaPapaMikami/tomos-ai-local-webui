#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

WEB_HOST="${GEMMA_WEB_HOST:-127.0.0.1}"
WEB_PORT="${GEMMA_WEB_PORT:-54876}"
WEB_URL="http://$WEB_HOST:$WEB_PORT"
APP_VERSION="${GEMMA_APP_VERSION:-0.4.0}"
CHAT_MODEL="${GEMMA_MODEL:-gemma4:12b}"
CODING_MODEL="${GEMMA_CODING_MODEL:-$CHAT_MODEL}"
TRANSLATION_MODEL="${GEMMA_TRANSLATION_MODEL:-auto}"

echo "Gemma 4 12B + ComfyUI を起動します。"
echo "App version: $APP_VERSION"
echo "Chat model: $CHAT_MODEL"
echo "Coding model: $CODING_MODEL"
echo "Translation model: $TRANSLATION_MODEL"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 が見つかりません。"
  read -r -p "Enterで閉じます..."
  exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama が見つかりません。Ollama.appをインストールしてください。"
  read -r -p "Enterで閉じます..."
  exit 1
fi

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null; then
  echo "Ollamaを起動中..."
  ollama serve >/tmp/gemma4_ollama.log 2>&1 &
  sleep 3
fi

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null; then
  echo "Ollamaを起動できませんでした。Ollama.appを開いてから再実行してください。"
  read -r -p "Enterで閉じます..."
  exit 1
fi

if [ -x "./scripts/start-comfyui.sh" ]; then
  ./scripts/start-comfyui.sh
else
  echo "scripts/start-comfyui.sh が見つかりません。"
  read -r -p "Enterで閉じます..."
  exit 1
fi

echo
echo "Web UI: $WEB_URL"
echo "ComfyUI: http://127.0.0.1:8188"
echo

(sleep 1; open -a Safari "$WEB_URL" >/dev/null 2>&1 || true) &
python3 server.py --host "$WEB_HOST" --port "$WEB_PORT"
