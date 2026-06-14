#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
./scripts/start-comfyui.sh

echo
echo "ComfyUI: http://127.0.0.1:8188"
echo "This window can stay open. Close it only when you want to stop ComfyUI."
read -r -p "Press Enter to close this launcher..."
