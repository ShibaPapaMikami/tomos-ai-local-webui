#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PKG_PATH="${1:-}"
NOTARY_PROFILE="${TOMOS_NOTARY_PROFILE:-tomos-notary}"

if [ -z "$PKG_PATH" ] || [ ! -f "$PKG_PATH" ]; then
  echo "使い方: bash scripts/notarize-mac-pkg.sh dist/TOMOS_AI-vX.X.X-mac.pkg" >&2
  exit 1
fi

for command_name in pkgutil xcrun spctl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "$command_name が見つかりません。" >&2
    exit 1
  fi
done

echo "1/5 署名を確認します"
pkgutil --check-signature "$PKG_PATH"

echo "2/5 Appleへ公証を申請します"
xcrun notarytool submit "$PKG_PATH" \
  --keychain-profile "$NOTARY_PROFILE" \
  --wait

echo "3/5 公証チケットをPKGへ添付します"
xcrun stapler staple "$PKG_PATH"

echo "4/5 公証チケットを確認します"
xcrun stapler validate "$PKG_PATH"

echo "5/5 Gatekeeperの判定を確認します"
spctl -a -vv -t install "$PKG_PATH"

echo "署名・公証・Gatekeeper確認が完了しました: $PKG_PATH"
