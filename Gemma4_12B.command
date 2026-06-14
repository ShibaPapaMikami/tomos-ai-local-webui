#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed or not available in PATH."
  echo "Install Ollama from https://ollama.com/download and try again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null; then
  echo "Ollama server is not running."
  echo "Open Ollama.app, then run this file again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if ! ollama list | awk 'NR > 1 {print $1}' | grep -qx "gemma4:12b"; then
  echo "gemma4:12b is not installed."
  echo "Run: ollama pull gemma4:12b"
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Starting Gemma 4 12B..."
echo "Type /bye to exit."
echo

./scripts/chat.sh
