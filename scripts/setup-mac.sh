#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${GEMMA_MODEL:-gemma4:12b}"
CODING_MODEL="${GEMMA_CODING_MODEL:-}"

echo "TOMOS AI - macOS setup"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 が見つかりません。"
  echo "https://www.python.org/downloads/ から Python 3 をインストールしてください。"
  exit 1
fi

echo "Python: $(python3 --version)"

python3 - <<'PY' >/dev/null 2>&1 || python3 -m pip install --user segno
import segno
PY

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama が見つかりません。"
  echo "https://ollama.com/download から Ollama をインストールしてから、もう一度このスクリプトを実行してください。"
  exit 1
fi

echo "Ollama: $(ollama --version 2>&1 | tail -1)"

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo "Ollama サーバーを起動します..."
  ollama serve >/tmp/gemma4_ollama.log 2>&1 &
  sleep 3
fi

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo "Ollama を起動できませんでした。Ollama.app を開いてから再実行してください。"
  exit 1
fi

if ! ollama list | awk 'NR > 1 {print $1}' | grep -Fqx "$MODEL"; then
  echo "$MODEL をダウンロードします。初回は数GBの通信が発生します。"
  ollama pull "$MODEL"
else
  echo "Model: installed ($MODEL)"
fi

if [ -n "$CODING_MODEL" ] && [ "$CODING_MODEL" != "$MODEL" ]; then
  if ! ollama list | awk 'NR > 1 {print $1}' | grep -Fqx "$CODING_MODEL"; then
    echo "$CODING_MODEL をコード生成用にダウンロードします。"
    ollama pull "$CODING_MODEL"
  else
    echo "Coding model: installed ($CODING_MODEL)"
  fi
fi

chmod +x "$ROOT"/*.command "$ROOT"/scripts/*.sh 2>/dev/null || true

echo
echo "準備完了です。次は以下を実行してください:"
echo "./Gemma4_12B_Web.command"
