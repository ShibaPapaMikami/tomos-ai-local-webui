#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-gemma4:12b}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama: not found"
  exit 1
fi

echo "ollama: $(ollama --version 2>&1 | tail -1)"

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null; then
  echo "server: not running at http://127.0.0.1:11434"
  exit 1
fi

echo "server: running"

if ollama list | awk 'NR > 1 {print $1}' | grep -qx "$MODEL"; then
  echo "model: installed ($MODEL)"
else
  echo "model: missing ($MODEL)"
  echo "run: ollama pull $MODEL"
  exit 1
fi
