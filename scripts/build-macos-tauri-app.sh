#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$ROOT/build/macos-runtime"
PYTHON="$RUNTIME/python/bin/python3"
RUNTIME_MANIFEST="$RUNTIME/build-manifest.json"
TAURI_APP="$ROOT/src-tauri/target/release/bundle/macos/TOMOS AI.app"
CANDIDATE_DIR="$ROOT/dist/candidate"
CANDIDATE_APP="$CANDIDATE_DIR/TOMOS AI.app"
CANDIDATE_MANIFEST="$CANDIDATE_DIR/build-manifest.json"

fail() {
  echo "portable app buildを停止しました: $*" >&2
  exit 1
}

[ "$(uname -m)" = "arm64" ] || fail "Apple Silicon arm64環境が必要です"
[ -f "$RUNTIME/tomos/server.py" ] || fail "TOMOS runtimeのserver.pyがありません"
[ -f "$RUNTIME/tomos/web/index.html" ] || fail "TOMOS runtimeのweb/index.htmlがありません"
[ -f "$RUNTIME_MANIFEST" ] || fail "runtime build manifestがありません"

git -C "$ROOT" diff --quiet || fail "clean sourceが必要です（未stage変更あり）"
git -C "$ROOT" diff --cached --quiet || fail "clean sourceが必要です（stage変更あり）"
[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ] || fail "clean sourceが必要です（未追跡fileを含む）"

EXPECTED_COMMIT="$(git -C "$ROOT" rev-parse HEAD)"
EXPECTED_VERSION="$(node -e 'const c=require(process.argv[1]); process.stdout.write(c.version)' "$ROOT/src-tauri/tauri.conf.json")"
ACTUAL_COMMIT="$(/usr/bin/plutil -extract sourceCommit raw "$RUNTIME_MANIFEST")"
ACTUAL_VERSION="$(/usr/bin/plutil -extract appVersion raw "$RUNTIME_MANIFEST")"
ARTIFACT_NAME="$(/usr/bin/plutil -extract pythonArtifact.name raw "$RUNTIME_MANIFEST")"
ARTIFACT_SHA256="$(/usr/bin/plutil -extract pythonArtifact.sha256 raw "$RUNTIME_MANIFEST")"
RUNTIME_ARCHIVE="$ROOT/build/cache/$ARTIFACT_NAME"
[ "$ACTUAL_COMMIT" = "$EXPECTED_COMMIT" ] || fail "runtime manifestのsourceCommitが現在HEADと一致しません"
[ "$ACTUAL_VERSION" = "$EXPECTED_VERSION" ] || fail "runtime manifestのappVersionがTauri設定と一致しません"
[ -f "$RUNTIME_ARCHIVE" ] || fail "検証済みPython artifact cacheがありません"
[ "$(shasum -a 256 "$RUNTIME_ARCHIVE" | awk '{print $1}')" = "$ARTIFACT_SHA256" ] || fail "Python artifactのSHA-256がruntime manifestと一致しません"

# Never trust an ignored pre-existing runtime tree. Re-stage it from the
# verified archive descriptor immediately before Tauri reads the fixed source
# path in tauri.conf.json.
python3 "$ROOT/scripts/fetch-macos-python-runtime.py" \
  --archive-cache "$ROOT/build/cache" \
  --output "$RUNTIME/python" \
  --replace-existing

[ -x "$PYTHON" ] || fail "同梱Pythonがありません: $PYTHON"
file "$PYTHON" | grep -q 'arm64' || fail "同梱Pythonがarm64ではありません"
"$PYTHON" --version | grep -Eq '^Python 3\.11\.' || fail "同梱Pythonが3.11系ではありません"

python3 "$ROOT/scripts/test_macos_tauri_bundle.py" --prepare-candidate-dir "$ROOT" >/dev/null

(
  cd "$ROOT"
  cargo tauri build --bundles app
)

[ -d "$TAURI_APP" ] || fail "Tauri app bundleが生成されませんでした"
ditto "$TAURI_APP" "$CANDIDATE_APP"
cp "$RUNTIME_MANIFEST" "$CANDIDATE_MANIFEST"
python3 "$ROOT/scripts/test_macos_tauri_bundle.py" "$CANDIDATE_APP"
codesign --force --deep --sign - "$CANDIDATE_APP"
codesign --verify --deep --strict --verbose=2 "$CANDIDATE_APP"

echo "candidate app: $CANDIDATE_APP"
echo "candidate manifest: $CANDIDATE_MANIFEST"
