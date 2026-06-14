#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not available."
  read -r -p "Press Enter to close..."
  exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed or not available in PATH."
  read -r -p "Press Enter to close..."
  exit 1
fi

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null; then
  echo "Starting Ollama server..."
  ollama serve >/tmp/gemma4_ollama.log 2>&1 &
  sleep 3
fi

if ! curl -s http://127.0.0.1:11434/api/version >/dev/null; then
  echo "Ollama server did not start."
  echo "Open Ollama.app, then run this file again."
  read -r -p "Press Enter to close..."
  exit 1
fi

(sleep 1; open -a Safari http://127.0.0.1:54876 >/dev/null 2>&1 || true) &
python3 server.py --host 127.0.0.1 --port 54876
