#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$PYTHON_BIN"
elif [[ -x /opt/homebrew/bin/python3.12 ]]; then
  PYTHON_BIN="/opt/homebrew/bin/python3.12"
else
  PYTHON_BIN="python3"
fi
ASR_VENV="${ASR_VENV:-.venv-asr}"

echo "Gemma 4 ASR / Nemotron setup"
echo "Python: $PYTHON_BIN"
echo "Virtual env: $ASR_VENV"
echo

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 が見つかりません。Python 3.11以上をインストールしてください。"
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import hashlib, sys; raise SystemExit(0 if sys.version_info >= (3, 11) and hasattr(hashlib, "blake2b") else 1)' >/dev/null 2>&1; then
  echo "Nemotron ASRには、Python 3.11以上かつ hashlib.blake2b が使えるPythonが必要です。"
  echo "Macでは Homebrew の Python 3.12 以上を推奨します。"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg が見つかりません。Homebrewなどで ffmpeg をインストールしてください。"
  echo "例: brew install ffmpeg"
  exit 1
fi

"$PYTHON_BIN" -m venv --clear "$ASR_VENV"
# shellcheck source=/dev/null
source "$ASR_VENV/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install Cython packaging
python -m pip install torch torchaudio
python -m pip install "nemo_toolkit[asr] @ git+https://github.com/NVIDIA/NeMo.git@main"

echo
echo "ASR setup finished."
echo "起動時は次のように指定できます:"
echo "GEMMA_ASR_RUNNER=\"$ASR_VENV/bin/python scripts/asr_nemotron_runner.py\" ./Gemma4_12B_Web.command"
