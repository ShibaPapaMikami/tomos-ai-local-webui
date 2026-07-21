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
OUT_PKG="$DIST_DIR/TOMOS_AI-${TAG}-mac.pkg"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gemma4-pkg.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
SIGNING_IDENTITY="${TOMOS_MAC_INSTALLER_IDENTITY:-}"

if ! command -v pkgbuild >/dev/null 2>&1; then
  echo "pkgbuild が見つかりません。Xcode Command Line Tools を入れてください。" >&2
  exit 1
fi

if [ -z "$SIGNING_IDENTITY" ]; then
  INSTALLER_IDENTITIES="$(
    security find-identity -v -p basic 2>/dev/null \
      | sed -n 's/.*"\(Developer ID Installer:.*\)"/\1/p' \
      | sort -u
  )"
  IDENTITY_COUNT="$(printf '%s\n' "$INSTALLER_IDENTITIES" | sed '/^$/d' | wc -l | tr -d ' ')"
  if [ "$IDENTITY_COUNT" -eq 1 ]; then
    SIGNING_IDENTITY="$INSTALLER_IDENTITIES"
  elif [ "$IDENTITY_COUNT" -eq 0 ]; then
    echo "Developer ID Installer証明書が見つかりません。未署名PKGは作成しません。" >&2
    exit 1
  else
    echo "Developer ID Installer証明書が複数あります。次のように署名者を指定してください。" >&2
    echo 'TOMOS_MAC_INSTALLER_IDENTITY="Developer ID Installer: ..." bash scripts/make-mac-pkg.sh' >&2
    printf '%s\n' "$INSTALLER_IDENTITIES" >&2
    exit 1
  fi
fi

mkdir -p "$WORK_DIR/pkgroot/Applications"
bash "$ROOT_DIR/scripts/make-mac-app.sh" "$APP_VERSION" "$WORK_DIR/pkgroot/Applications/TOMOS AI.app"

pkgbuild \
  --root "$WORK_DIR/pkgroot" \
  --identifier "jp.local.gemma4-12b" \
  --version "$APP_VERSION" \
  --install-location "/" \
  --sign "$SIGNING_IDENTITY" \
  "$OUT_PKG"

SIGNATURE_OUTPUT="$(pkgutil --check-signature "$OUT_PKG" 2>&1)"
printf '%s\n' "$SIGNATURE_OUTPUT"
if ! printf '%s\n' "$SIGNATURE_OUTPUT" | grep -Fq "$SIGNING_IDENTITY"; then
  echo "PKGの署名者を確認できませんでした。公開しないでください。" >&2
  exit 1
fi

cat <<EOF
作成しました:
- $OUT_PKG

確認:
pkgutil --check-signature "$OUT_PKG"
bash scripts/notarize-mac-pkg.sh "$OUT_PKG"
EOF
