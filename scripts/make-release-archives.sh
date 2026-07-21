#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

APP_VERSION="${1:-}"
if [ -z "$APP_VERSION" ]; then
  APP_VERSION="$(python3 - <<'PY'
import pathlib
import re

text = pathlib.Path("server.py").read_text(encoding="utf-8")
match = re.search(r'APP_VERSION = os\.environ\.get\("GEMMA_APP_VERSION", "([^"]+)"\)', text)
if not match:
    raise SystemExit("server.py から APP_VERSION を読めませんでした")
print(match.group(1))
PY
)"
fi

TAG="v${APP_VERSION#v}"
DIST_DIR="$ROOT_DIR/dist"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gemma4-release.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

MAC_ROOT="$WORK_DIR/Gemma4_12B-${TAG}-mac"
WIN_ROOT="$WORK_DIR/Gemma4_12B-${TAG}-windows"

mkdir -p "$DIST_DIR" "$MAC_ROOT" "$WIN_ROOT"

copy_if_exists() {
  local source="$1"
  local target="$2"
  if [ -e "$source" ]; then
    cp -R "$source" "$target"
  fi
}

copy_common() {
  local target="$1"
  mkdir -p "$target/scripts" "$target/docs"

  copy_if_exists "server.py" "$target/"
  copy_if_exists "search_tools.py" "$target/"
  copy_if_exists "README.md" "$target/"
  copy_if_exists "README.ja.md" "$target/"
  copy_if_exists "README.en.md" "$target/"
  copy_if_exists "LICENSE" "$target/"
  copy_if_exists "web" "$target/"

  copy_if_exists "docs/install-students.ja.md" "$target/docs/"
  copy_if_exists "docs/github-release-guide.ja.md" "$target/docs/"
  copy_if_exists "docs/release-checklist.ja.md" "$target/docs/"
  copy_if_exists "docs/native-installers.ja.md" "$target/docs/"
  copy_if_exists "docs/study-pack-import-guide.ja.md" "$target/docs/"

  copy_if_exists "scripts/setup-mac.sh" "$target/scripts/"
  copy_if_exists "scripts/setup-windows.ps1" "$target/scripts/"
  copy_if_exists "scripts/start-dev.sh" "$target/scripts/"
  copy_if_exists "scripts/start-comfyui.sh" "$target/scripts/"
  copy_if_exists "scripts/asr_nemotron_runner.py" "$target/scripts/"
  copy_if_exists "scripts/asr_nemotron_worker.py" "$target/scripts/"
  copy_if_exists "scripts/setup-asr-mac.sh" "$target/scripts/"
  copy_if_exists "scripts/setup-asr-python311.sh" "$target/scripts/"
  copy_if_exists "scripts/setup-ocr-mac.sh" "$target/scripts/"
  copy_if_exists "scripts/smoke-tests.sh" "$target/scripts/"
}

copy_common "$MAC_ROOT"
copy_common "$WIN_ROOT"

copy_if_exists "scripts/macos-app-launcher.sh" "$MAC_ROOT/scripts/"
copy_if_exists "Gemma4_12B_全部起動.command" "$MAC_ROOT/"
copy_if_exists "Gemma4_12B_Web.command" "$MAC_ROOT/"
copy_if_exists "Gemma4_12B_重い処理を停止.command" "$MAC_ROOT/"
copy_if_exists "ComfyUI_Start.command" "$MAC_ROOT/"
copy_if_exists "Start_Mac.command" "$MAC_ROOT/"

copy_if_exists "Gemma4_12B_All_Start.bat" "$WIN_ROOT/"
copy_if_exists "Gemma4_12B_Web.bat" "$WIN_ROOT/"
copy_if_exists "Gemma4_12B_Stop_Heavy.bat" "$WIN_ROOT/"
copy_if_exists "ComfyUI_Start.bat" "$WIN_ROOT/"
copy_if_exists "Start_Windows.bat" "$WIN_ROOT/"

find "$MAC_ROOT" -name "*.command" -o -name "*.sh" | while read -r file; do
  chmod +x "$file"
done

(cd "$WORK_DIR" && zip -qr "$DIST_DIR/TOMOS_AI-${TAG}-mac.zip" "$(basename "$MAC_ROOT")")
(cd "$WORK_DIR" && zip -qr "$DIST_DIR/TOMOS_AI-${TAG}-windows.zip" "$(basename "$WIN_ROOT")")

cat <<EOF
作成しました:
- $DIST_DIR/TOMOS_AI-${TAG}-mac.zip
- $DIST_DIR/TOMOS_AI-${TAG}-windows.zip

GitHub Release には、この2つのZIPを添付してください。
ネイティブインストーラーを使う場合は、別途 .pkg / .msi も添付してください。
EOF
