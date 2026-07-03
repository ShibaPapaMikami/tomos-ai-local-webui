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
MAC_ZIP="$DIST_DIR/TOMOS_AI-${TAG}-mac.zip"
OUT_PKG="$DIST_DIR/TOMOS_AI-${TAG}-mac.pkg"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gemma4-pkg.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

if ! command -v pkgbuild >/dev/null 2>&1; then
  echo "pkgbuild が見つかりません。Xcode Command Line Tools を入れてください。" >&2
  exit 1
fi

if [ ! -f "$MAC_ZIP" ]; then
  bash "$ROOT_DIR/scripts/make-release-archives.sh" "$APP_VERSION"
fi

mkdir -p "$WORK_DIR/unzip" "$WORK_DIR/pkgroot/Applications"
unzip -q "$MAC_ZIP" -d "$WORK_DIR/unzip"

PAYLOAD_DIR="$(find "$WORK_DIR/unzip" -maxdepth 1 -type d -name "Gemma4_12B-${TAG}-mac" -print -quit)"
if [ -z "$PAYLOAD_DIR" ]; then
  echo "Mac用ZIPの中に Gemma4_12B-${TAG}-mac が見つかりません。" >&2
  exit 1
fi

cp -R "$PAYLOAD_DIR" "$WORK_DIR/pkgroot/Applications/Gemma4_12B"

pkgbuild \
  --root "$WORK_DIR/pkgroot" \
  --identifier "jp.local.gemma4-12b" \
  --version "$APP_VERSION" \
  --install-location "/" \
  "$OUT_PKG"

cat <<EOF
作成しました:
- $OUT_PKG

確認:
pkgutil --payload-files "$OUT_PKG" | sed -n '1,40p'
EOF
