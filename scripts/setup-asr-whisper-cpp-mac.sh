#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "whisper.cpp 音声入力を準備します。"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew が見つかりません。先に Homebrew を導入してください。"
  exit 1
fi

if ! command -v whisper-cli >/dev/null 2>&1; then
  brew install whisper-cpp
fi

mkdir -p models/whisper

if [ ! -f "models/whisper/ggml-tiny.bin" ]; then
  EXISTING_MODEL="$HOME/Library/Application Support/com.prakashjoshipax.VoiceInk/WhisperModels/ggml-tiny.bin"
  if [ -f "$EXISTING_MODEL" ]; then
    cp "$EXISTING_MODEL" models/whisper/ggml-tiny.bin
  else
    curl -L --fail \
      -o models/whisper/ggml-tiny.bin \
      https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin
  fi
fi

echo "完了しました。"
echo "whisper-cli: $(command -v whisper-cli)"
echo "model: $(pwd)/models/whisper/ggml-tiny.bin"
echo
echo "起動例:"
echo "GEMMA_ASR_MODEL=whisper.cpp:tiny GEMMA_WHISPER_CPP_FAST_MODEL=\"$(pwd)/models/whisper/ggml-tiny.bin\" ./Gemma4_12B_Web.command"
