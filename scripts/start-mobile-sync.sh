#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

WEB_PORT="${GEMMA_MOBILE_SYNC_PORT:-54877}"

echo "Gemma 4 mobile sync を起動します。"
echo "Mode: mobile-sync-only / mobile APIs only"
echo "Port: $WEB_PORT"
echo
echo "同じWi-Fiのスマホで Mobile preview URL を開き、PC側は /index.html を開いてスマホ接続を確認してください。"
echo "このモードではチャット生成、ファイル操作、学習保存などの通常APIはLANへ公開しません。"
echo

python3 server.py --host 0.0.0.0 --port "$WEB_PORT" --mobile-sync-only
