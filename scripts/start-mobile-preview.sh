#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

WEB_PORT="${GEMMA_MOBILE_PREVIEW_PORT:-54876}"

echo "Gemma 4 mobile PWA preview を起動します。"
echo "Mode: static-only / write APIs blocked"
echo "Port: $WEB_PORT"
echo
echo "同じWi-Fiのスマホで、下に表示される Mobile preview URL をSafari/Chromeで開いてください。"
echo "このモードではチャット生成、ファイル操作、学習保存などのPOST APIは使えません。"
echo

python3 server.py --host 0.0.0.0 --port "$WEB_PORT" --static-only
