#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

APP_VERSION="${1:-}"
OUTPUT_APP="${2:-}"
if [ -z "$APP_VERSION" ] || [ -z "$OUTPUT_APP" ]; then
  echo "使い方: $0 VERSION OUTPUT_APP" >&2
  exit 1
fi

TAG="v${APP_VERSION#v}"
DIST_DIR="$ROOT_DIR/dist"
MAC_ZIP="$DIST_DIR/TOMOS_AI-${TAG}-mac.zip"
SOURCE_DIR_NAME="Gemma4_12B-${TAG}-mac"
ICON_SOURCE="$ROOT_DIR/web/icons/icon-512.png"
SIGNING_IDENTITY="${TOMOS_MAC_APPLICATION_IDENTITY:-}"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tomos-ai-app.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 が見つかりません。Xcode Command Line Tools を入れてください。" >&2
    exit 1
  fi
}

detect_signing_identity() {
  local identities
  local identity_count

  identities="$(
    security find-identity -v -p codesigning 2>/dev/null \
      | sed -n 's/.*"\(Developer ID Application:.*\)"/\1/p' \
      | sort -u
  )"
  identity_count="$(printf '%s\n' "$identities" | sed '/^$/d' | wc -l | tr -d ' ')"

  if [ "$identity_count" -eq 1 ]; then
    printf '%s\n' "$identities"
    return
  fi
  if [ "$identity_count" -eq 0 ]; then
    echo "Developer ID Application証明書が見つかりません。未署名アプリは作成しません。" >&2
    exit 1
  fi

  echo "Developer ID Application証明書が複数あります。TOMOS_MAC_APPLICATION_IDENTITY を指定してください。" >&2
  printf '%s\n' "$identities" >&2
  exit 1
}

require_command sips
require_command iconutil
require_command codesign
require_command unzip

if [ ! -f "$ICON_SOURCE" ]; then
  echo "アプリアイコンが見つかりません: $ICON_SOURCE" >&2
  exit 1
fi

if [ -z "$SIGNING_IDENTITY" ]; then
  SIGNING_IDENTITY="$(detect_signing_identity)"
fi

if [ "$SIGNING_IDENTITY" != "-" ] && [[ "$SIGNING_IDENTITY" != Developer\ ID\ Application:* ]]; then
  echo "TOMOS_MAC_APPLICATION_IDENTITY には Developer ID Application 証明書を指定してください。" >&2
  exit 1
fi

if [ ! -f "$MAC_ZIP" ]; then
  bash "$ROOT_DIR/scripts/make-release-archives.sh" "$APP_VERSION"
fi

if [ -e "$OUTPUT_APP" ]; then
  echo "出力先が既に存在します: $OUTPUT_APP" >&2
  exit 1
fi

mkdir -p "$WORK_DIR/unzip" "$WORK_DIR/TOMOS.iconset" "$(dirname "$OUTPUT_APP")"
unzip -q "$MAC_ZIP" -d "$WORK_DIR/unzip"
SOURCE_ROOT="$WORK_DIR/unzip/$SOURCE_DIR_NAME"
if [ ! -d "$SOURCE_ROOT" ]; then
  echo "Mac用ZIPの中に $SOURCE_DIR_NAME が見つかりません。" >&2
  exit 1
fi

APP_CONTENTS="$OUTPUT_APP/Contents"
APP_MACOS="$OUTPUT_APP/Contents/MacOS"
APP_RESOURCES="$OUTPUT_APP/Contents/Resources"
APP_BUNDLED_ROOT="$OUTPUT_APP/Contents/Resources/Gemma4_12B"
INFO_PLIST="$OUTPUT_APP/Contents/Info.plist"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp -R "$SOURCE_ROOT" "$APP_BUNDLED_ROOT"
cp "$ROOT_DIR/scripts/macos-app-launcher.sh" "$APP_MACOS/TOMOS AI"
chmod +x "$APP_MACOS/TOMOS AI"

create_icon() {
  local file_name="$1"
  local size="$2"
  sips -z "$size" "$size" "$ICON_SOURCE" --out "$WORK_DIR/TOMOS.iconset/$file_name" >/dev/null
}

create_icon "icon_16x16.png" 16
create_icon "icon_16x16@2x.png" 32
create_icon "icon_32x32.png" 32
create_icon "icon_32x32@2x.png" 64
create_icon "icon_128x128.png" 128
create_icon "icon_128x128@2x.png" 256
create_icon "icon_256x256.png" 256
create_icon "icon_256x256@2x.png" 512
create_icon "icon_512x512.png" 512
create_icon "icon_512x512@2x.png" 1024
if ! iconutil -c icns "$WORK_DIR/TOMOS.iconset" -o "$APP_RESOURCES/TOMOS.icns"; then
  echo "iconutil でICNSを生成できないため、sipsで代替生成します。" >&2
  sips -s format icns "$ICON_SOURCE" --out "$APP_RESOURCES/TOMOS.icns" >/dev/null
fi

cat > "$INFO_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key><string>TOMOS AI</string>
  <key>CFBundleExecutable</key><string>TOMOS AI</string>
  <key>CFBundleIconFile</key><string>TOMOS</string>
  <key>CFBundleIdentifier</key><string>com.shibapapastudio.tomos-ai</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${APP_VERSION}</string>
  <key>CFBundleVersion</key><string>${APP_VERSION}</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
</dict>
</plist>
EOF

if [ "$SIGNING_IDENTITY" = "-" ]; then
  codesign --force --sign - "$OUTPUT_APP"
else
  codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" "$OUTPUT_APP"
fi

echo "作成しました: $OUTPUT_APP"
