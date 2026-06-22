#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "OCRプラグインを準備します。"
echo "PROGRESS 1/5 Homebrewを確認中"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew が見つかりません。先に Homebrew を導入してください。"
  exit 1
fi

echo "PROGRESS 2/5 Tesseractを確認中"
if ! command -v tesseract >/dev/null 2>&1; then
  echo "Tesseract をインストールします。"
  brew install tesseract
else
  echo "Tesseract は導入済みです。"
fi

echo "PROGRESS 3/5 日本語OCRデータを確認中"
if ! tesseract --list-langs 2>/dev/null | grep -q '^jpn$'; then
  echo "日本語OCR用の言語データをインストールします。"
  brew install tesseract-lang
else
  echo "日本語OCR用の言語データは導入済みです。"
fi

echo "PROGRESS 4/5 PDF読み取り用ツールを確認中"
if ! command -v pdftoppm >/dev/null 2>&1; then
  echo "PDF画像化用のPopplerをインストールします。"
  brew install poppler
else
  echo "Poppler は導入済みです。"
fi

echo "PROGRESS 5/5 OCR環境を確認中"
echo "OCRセットアップが完了しました。"
echo "tesseract: $(command -v tesseract || true)"
echo "pdftoppm: $(command -v pdftoppm || true)"
tesseract --list-langs 2>/dev/null | sed 's/^/lang: /' | head -20 || true
