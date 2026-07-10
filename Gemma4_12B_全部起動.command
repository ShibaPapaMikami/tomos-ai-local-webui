#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

WEB_HOST="${GEMMA_WEB_HOST:-127.0.0.1}"
WEB_PORT="${GEMMA_WEB_PORT:-54876}"
WEB_URL="http://$WEB_HOST:$WEB_PORT"
APP_VERSION="0.8.211"
APP_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || true)"
CHAT_MODEL="${GEMMA_MODEL:-gemma4:12b-mlx}"
CODING_MODEL="${GEMMA_CODING_MODEL:-$CHAT_MODEL}"
TRANSLATION_MODEL="${GEMMA_TRANSLATION_MODEL:-auto}"
ASR_MODEL="${GEMMA_ASR_MODEL:-whisper.cpp:tiny}"
if [ -x ".venv-asr/bin/python" ]; then
  DEFAULT_ASR_RUNNER=".venv-asr/bin/python scripts/asr_nemotron_runner.py"
  DEFAULT_ASR_WORKER=".venv-asr/bin/python scripts/asr_nemotron_worker.py"
else
  DEFAULT_ASR_RUNNER="python3 scripts/asr_nemotron_runner.py"
  DEFAULT_ASR_WORKER="python3 scripts/asr_nemotron_worker.py"
fi
ASR_RUNNER="${GEMMA_ASR_RUNNER:-$DEFAULT_ASR_RUNNER}"
ASR_WORKER="${GEMMA_ASR_WORKER:-$DEFAULT_ASR_WORKER}"
ASR_LANGUAGE="${GEMMA_ASR_LANGUAGE:-ja-JP}"
export GEMMA_ASR_MODEL="$ASR_MODEL"
export GEMMA_ASR_RUNNER="$ASR_RUNNER"
export GEMMA_ASR_WORKER="$ASR_WORKER"
export GEMMA_ASR_LANGUAGE="$ASR_LANGUAGE"
export GEMMA_APP_VERSION="$APP_VERSION"

stop_old_web_server() {
  local running_version
  local running_commit
  local running_info
  running_info="$(curl -s "$WEB_URL/api/health" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("appVersion","")); print(data.get("appCommit",""))' 2>/dev/null || true)"
  running_version="$(printf "%s\n" "$running_info" | sed -n '1p')"
  running_commit="$(printf "%s\n" "$running_info" | sed -n '2p')"
  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi
  if ! lsof -tiTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    return
  fi
  if [ "$running_version" = "$APP_VERSION" ] && { [ -z "$APP_COMMIT" ] || [ "$running_commit" = "$APP_COMMIT" ]; }; then
    return
  fi
  if [ -n "$running_version" ]; then
    echo "古いWeb UI ($running_version ${running_commit:-no-commit}) が起動中のため停止します。"
  else
    echo "ポート $WEB_PORT を使用中の別サーバーを停止します。"
  fi
  lsof -tiTCP:"$WEB_PORT" -sTCP:LISTEN | while read -r pid; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  sleep 1
}

echo "TOMOS AI + ComfyUI を起動します。"
echo "App version: $APP_VERSION"
echo "App commit: ${APP_COMMIT:-no-git}"
echo "Chat model: $CHAT_MODEL"
echo "Coding model: $CODING_MODEL"
echo "Translation model: $TRANSLATION_MODEL"
echo "ASR model: $ASR_MODEL"
echo "ASR runner: $ASR_RUNNER"
echo "ASR worker: $ASR_WORKER"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 が見つかりません。"
  read -r -p "Enterで閉じます..."
  exit 1
fi

stop_old_web_server

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
