#!/usr/bin/env bash
set -euo pipefail

umask 077

ROOT="$(cd "$(/usr/bin/dirname "$0")/.." && /bin/pwd -P)"
CANDIDATE_APP="$ROOT/dist/candidate/TOMOS AI.app"
CANDIDATE_MANIFEST="$ROOT/dist/candidate/build-manifest.json"
SIGNED_DIR="$ROOT/dist/signed"
SIGNED_APP="$SIGNED_DIR/TOMOS AI.app"
SIGNED_MANIFEST="$SIGNED_DIR/build-manifest.json"
ENTITLEMENTS="$ROOT/src-tauri/Entitlements.plist"
PUBLISHER="$ROOT/scripts/macos-atomic-publish.py"
SIGNING_IDENTITY="${TOMOS_MAC_APPLICATION_IDENTITY:-}"
SIGNING_FINGERPRINT=""
EXPECTED_TEAM_ID="AJK3HH9G22"
TEST_TOOLS_DIR="${TOMOS_SIGN_TEST_TOOLS_DIR:-}"
CANONICAL_TEST_TOOLS_DIR=""
TEST_HOOK_ENABLED=0

CODESIGN="/usr/bin/codesign"
DITTO="/usr/bin/ditto"
FILE="/usr/bin/file"
FIND="/usr/bin/find"
MKDIR="/bin/mkdir"
MKTEMP="/usr/bin/mktemp"
RM="/bin/rm"
PLUTIL="/usr/bin/plutil"
PYTHON="/usr/bin/python3"
SECURITY="/usr/bin/security"
UNAME="/usr/bin/uname"
AWK="/usr/bin/awk"
STAGING_DIR=""
STAGING_PAYLOAD=""
STAGING_APP=""
STAGING_MANIFEST=""
PUBLISHED=0

fail() {
  echo "macOS app署名を停止しました: $*" >&2
  exit 1
}

cleanup_signal() {
  local code="$1"
  trap - EXIT HUP INT TERM
  cleanup_with_status "$code"
}

cleanup_with_status() {
  local code="$1"
  if [ -n "$STAGING_DIR" ] && [ -d "$STAGING_DIR" ]; then
    case "$STAGING_DIR" in
      "$ROOT"/.tomos-signing.*) "$RM" -rf "$STAGING_DIR" ;;
      *) code=1 ;;
    esac
  fi
  exit "$code"
}

cleanup_exit() {
  local code=$?
  trap - EXIT HUP INT TERM
  if [ "$PUBLISHED" -ne 1 ] && [ "$code" -eq 0 ]; then
    code=1
  fi
  cleanup_with_status "$code"
}

require_real_directory() {
  local target="$1"
  local label="$2"
  [ -d "$target" ] && [ ! -L "$target" ] || fail "$label が実directoryではありません"
}

require_regular_file() {
  local target="$1"
  local label="$2"
  [ -f "$target" ] && [ ! -L "$target" ] || fail "$label が通常fileではありません"
}

configure_test_tools() {
  [ -n "$TEST_TOOLS_DIR" ] || return 0
  CANONICAL_TEST_TOOLS_DIR="$("$PYTHON" - "$ROOT" "$TEST_TOOLS_DIR" <<'PY'
import os
import stat
import sys
from pathlib import Path

root_input = Path(sys.argv[1])
tools_input = Path(sys.argv[2])
allowed_parent = Path("/private/tmp")
try:
    if not tools_input.is_absolute() or ".." in tools_input.parts:
        raise ValueError("tool path must be canonical")
    root = root_input.resolve(strict=True)
    tools = tools_input.resolve(strict=True)
    if root_input != root:
        raise ValueError("root must be canonical")
    root_stat = root.lstat()
    marker = root / ".tomos-sign-test-root"
    marker_stat = marker.lstat()
    expected_tools = root / ".test-tools"
    tools_stat = expected_tools.lstat()
    root.relative_to(allowed_parent)
except (OSError, ValueError):
    raise SystemExit(1)
if tools != expected_tools or root.parent != allowed_parent or not root.name.startswith("tomos-sign-test-"):
    raise SystemExit(1)
if (
    stat.S_ISLNK(root_stat.st_mode)
    or not stat.S_ISDIR(root_stat.st_mode)
    or root_stat.st_uid != os.geteuid()
    or stat.S_IMODE(root_stat.st_mode) != 0o700
    or stat.S_ISLNK(marker_stat.st_mode)
    or not stat.S_ISREG(marker_stat.st_mode)
    or marker_stat.st_uid != os.geteuid()
    or stat.S_IMODE(marker_stat.st_mode) != 0o600
    or stat.S_ISLNK(tools_stat.st_mode)
    or not stat.S_ISDIR(tools_stat.st_mode)
    or tools_stat.st_uid != os.geteuid()
    or stat.S_IMODE(tools_stat.st_mode) != 0o700
):
    raise SystemExit(1)
for name in ("codesign", "ditto", "file", "security", "uname"):
    item = expected_tools / name
    item_stat = item.lstat()
    if (
        stat.S_ISLNK(item_stat.st_mode)
        or not stat.S_ISREG(item_stat.st_mode)
        or item_stat.st_uid != os.geteuid()
        or item_stat.st_mode & 0o022
        or not item_stat.st_mode & stat.S_IXUSR
    ):
        raise SystemExit(1)
print(expected_tools)
PY
)" || fail "test tool hookは専用temporary rootでのみ使用できます"
  CODESIGN="$CANONICAL_TEST_TOOLS_DIR/codesign"
  DITTO="$CANONICAL_TEST_TOOLS_DIR/ditto"
  FILE="$CANONICAL_TEST_TOOLS_DIR/file"
  SECURITY="$CANONICAL_TEST_TOOLS_DIR/security"
  UNAME="$CANONICAL_TEST_TOOLS_DIR/uname"
  require_regular_file "$CODESIGN" "test codesign"
  require_regular_file "$DITTO" "test ditto"
  require_regular_file "$FILE" "test file"
  require_regular_file "$SECURITY" "test security"
  require_regular_file "$UNAME" "test uname"
  [ -x "$CODESIGN" ] && [ -x "$DITTO" ] && [ -x "$FILE" ] && [ -x "$SECURITY" ] && [ -x "$UNAME" ] || fail "test toolが実行可能ではありません"
  TEST_HOOK_ENABLED=1
}

validate_symlinks() {
  local app_path="$1"
  "$PYTHON" - "$app_path" <<'PY'
import os
import sys
from pathlib import Path

app = Path(sys.argv[1])
root = app.resolve(strict=True)
for directory, directories, files in os.walk(app, followlinks=False):
    for name in [*directories, *files]:
        path = Path(directory) / name
        if not path.is_symlink():
            continue
        try:
            target = path.resolve(strict=True)
            target.relative_to(root)
        except (FileNotFoundError, ValueError, OSError) as exc:
            raise SystemExit(f"symlink target outside app or unavailable: {path}") from exc
PY
}

validate_regular_inside_app() {
  local app_path="$1"
  local target="$2"
  local executable="$3"
  "$PYTHON" - "$app_path" "$target" "$executable" <<'PY'
import os
import stat
import sys
from pathlib import Path

app = Path(sys.argv[1]).resolve(strict=True)
target = Path(sys.argv[2])
require_executable = sys.argv[3] == "true"
try:
    metadata = target.lstat()
    resolved = target.resolve(strict=True)
    resolved.relative_to(app)
except (FileNotFoundError, ValueError, OSError) as exc:
    raise SystemExit(f"sign target is not a regular app-contained file: {target}") from exc
if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
    raise SystemExit(f"sign target is not a regular app-contained file: {target}")
if require_executable and not (metadata.st_mode & stat.S_IXUSR):
    raise SystemExit(f"main executable is not executable: {target}")
PY
}

is_arm64_macho() {
  local target="$1"
  local executable="$2"
  local description
  validate_regular_inside_app "$STAGING_APP" "$target" "$executable" || fail "sign targetが不正です"
  description="$("$FILE" -b "$target")" || fail "Mach-O確認に失敗しました"
  case "$description" in
    *Mach-O*arm64*|*arm64*Mach-O*) return 0 ;;
    *) return 1 ;;
  esac
}

read_main_executable_name() {
  local info_plist="$STAGING_APP/Contents/Info.plist"
  validate_regular_inside_app "$STAGING_APP" "$info_plist" false
  MAIN_EXECUTABLE_NAME="$("$PLUTIL" -extract CFBundleExecutable raw "$info_plist" 2>/dev/null)" || fail "CFBundleExecutableを読めません"
  case "$MAIN_EXECUTABLE_NAME" in
    ""|.|..|*/*|*\\*|*$'\n'*|*$'\r'*) fail "CFBundleExecutableが不正です" ;;
  esac
  MAIN_EXECUTABLE="$STAGING_APP/Contents/MacOS/$MAIN_EXECUTABLE_NAME"
}

validate_signing_identity() {
  local selector_kind
  [ -n "$SIGNING_IDENTITY" ] || fail "Developer ID Application証明書の指定が必要です"
  if [ "${#SIGNING_IDENTITY}" -eq 40 ] && [[ "$SIGNING_IDENTITY" != *[!0-9A-Fa-f]* ]]; then
    selector_kind="fingerprint"
  else
    selector_kind="label"
    case "$SIGNING_IDENTITY" in
      "Developer ID Application:"*"($EXPECTED_TEAM_ID)") ;;
      *) fail "Developer ID Application証明書のTeam IDが一致しません" ;;
    esac
  fi
  SIGNING_FINGERPRINT="$(
    "$SECURITY" find-identity -v -p codesigning 2>/dev/null |
      "$AWK" -v selector="$SIGNING_IDENTITY" -v selector_kind="$selector_kind" -v expected_team="$EXPECTED_TEAM_ID" '
        {
          line = $0
          sub(/^[ \t]*/, "", line)
          if (line !~ /^[0-9]+\)[ \t]+/) {
            next
          }
          sub(/^[0-9]+\)[ \t]+/, "", line)
          fingerprint = substr(line, 1, 40)
          if (length(fingerprint) != 40 || fingerprint ~ /[^0-9A-Fa-f]/) {
            next
          }
          rest = substr(line, 41)
          if (rest !~ /^[ \t]+"/) {
            next
          }
          sub(/^[ \t]+"/, "", rest)
          if (length(rest) < 2 || substr(rest, length(rest), 1) != "\"") {
            next
          }
          label = substr(rest, 1, length(rest) - 1)
          if (index(label, "\"") != 0) {
            next
          }
          fingerprint = toupper(fingerprint)
          if (!(fingerprint in first_label)) {
            first_label[fingerprint] = label
          } else if (first_label[fingerprint] != label) {
            conflicting_label[fingerprint] = 1
          }
          if (selector_kind == "label" && label == selector) {
            selected_fingerprints[fingerprint] = 1
          } else if (selector_kind == "fingerprint" && fingerprint == toupper(selector)) {
            selected_fingerprints[fingerprint] = 1
          }
        }
        END {
          count = 0
          selected = ""
          for (fingerprint in selected_fingerprints) {
            count += 1
            selected = fingerprint
          }
          if (count != 1 || conflicting_label[selected]) {
            exit 1
          }
          prefix = "Developer ID Application:"
          suffix = " (" expected_team ")"
          label = first_label[selected]
          if (index(label, prefix) != 1 ||
              length(label) <= length(prefix) + length(suffix) ||
              substr(label, length(label) - length(suffix) + 1) != suffix) {
            exit 1
          }
          print selected
        }
      '
  )" || fail "Developer ID Application証明書を確認できません"
  [ -n "$SIGNING_FINGERPRINT" ] || fail "Developer ID Application証明書を一意に特定できません"
}

collect_regular_paths_inner_first() {
  local path_list="$STAGING_DIR/nested-paths.nul"
  "$FIND" "$STAGING_APP" -type f -print0 > "$path_list" || return 1
  "$PYTHON" - "$STAGING_APP" "$path_list" <<'PY'
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
path_list = Path(sys.argv[2])
paths: list[Path] = []
for raw_path in path_list.read_bytes().split(b"\0"):
    if not raw_path:
        continue
    path = Path(os.fsdecode(raw_path))
    metadata = path.lstat()
    if not stat.S_ISLNK(metadata.st_mode) and stat.S_ISREG(metadata.st_mode):
        path.resolve(strict=True).relative_to(root)
        paths.append(path)
for path in sorted(paths, key=lambda item: (-len(item.relative_to(root).parts), item.as_posix())):
    sys.stdout.buffer.write(os.fsencode(path) + b"\0")
PY
}

sign_nested_code() {
  local nested_path
  local sorted_path_list="$STAGING_DIR/nested-paths-sorted.nul"
  collect_regular_paths_inner_first > "$sorted_path_list" || fail "nested codeの収集に失敗しました"
  while IFS= read -r -d '' nested_path; do
    [ "$nested_path" = "$MAIN_EXECUTABLE" ] && continue
    if is_arm64_macho "$nested_path" false; then
      "$CODESIGN" --force --sign "$SIGNING_FINGERPRINT" --options runtime --timestamp "$nested_path"
    fi
  done < "$sorted_path_list"
}

sign_main_executable() {
  is_arm64_macho "$MAIN_EXECUTABLE" true || fail "main executableがarm64 Mach-Oではありません"
  "$CODESIGN" --force --sign "$SIGNING_FINGERPRINT" --options runtime --timestamp \
    --entitlements "$ENTITLEMENTS" "$MAIN_EXECUTABLE"
}

sign_app_bundle() {
  require_real_directory "$STAGING_APP" "staging app"
  validate_symlinks "$STAGING_APP"
  "$CODESIGN" --force --sign "$SIGNING_FINGERPRINT" --options runtime --timestamp \
    --entitlements "$ENTITLEMENTS" "$STAGING_APP"
}

copy_build_manifest() {
  "$PYTHON" - "$CANDIDATE_MANIFEST" "$STAGING_MANIFEST" <<'PY'
import json
import os
import stat
import sys
from pathlib import Path

candidate = Path(sys.argv[1])
staging = Path(sys.argv[2])
source_fd = destination_fd = -1
try:
    source_fd = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW)
    source_stat = os.fstat(source_fd)
    if not stat.S_ISREG(source_stat.st_mode):
        raise SystemExit("candidate build manifest must be a regular file")
    contents = bytearray()
    while chunk := os.read(source_fd, 1024 * 1024):
        contents.extend(chunk)
    manifest = json.loads(bytes(contents).decode("utf-8"))
    if not isinstance(manifest, dict):
        raise SystemExit("build manifest must be a JSON object")
    if os.environ.get("TEST_HOOK_ENABLED") == "1":
        replacement = os.environ.get("TOMOS_SIGN_TEST_SWAP_MANIFEST_AFTER_READ")
        if replacement == "invalid":
            candidate.write_text("not-json\n", encoding="utf-8")
        elif replacement == "symlink":
            target = candidate.with_name(f"{candidate.name}.replacement")
            target.write_text("not-json\n", encoding="utf-8")
            candidate.unlink()
            candidate.symlink_to(target.name)
        elif replacement:
            raise SystemExit("unknown manifest test replacement")
    destination_fd = os.open(
        staging,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    remaining = memoryview(contents)
    while remaining:
        written = os.write(destination_fd, remaining)
        remaining = remaining[written:]
finally:
    if destination_fd >= 0:
        os.close(destination_fd)
    if source_fd >= 0:
        os.close(source_fd)
PY
  require_regular_file "$STAGING_MANIFEST" "staging build manifest"
}

publish_signed_app() {
  "$PYTHON" "$PUBLISHER" --root "$ROOT" --stage-name "${STAGING_DIR##*/}" --payload-name "${STAGING_PAYLOAD##*/}" --app-name "TOMOS AI.app" || fail "signed appのatomic publishに失敗しました"
  require_real_directory "$SIGNED_APP" "published signed app"
  require_regular_file "$SIGNED_MANIFEST" "published signed build manifest"
  PUBLISHED=1
}

configure_test_tools
[ "$("$UNAME" -m)" = "arm64" ] || fail "Apple Silicon arm64環境が必要です"
require_real_directory "$ROOT" "repository root"
require_real_directory "$ROOT/dist" "dist directory"
require_real_directory "$ROOT/dist/candidate" "candidate directory"
require_real_directory "$CANDIDATE_APP" "candidate app"
if [ -e "$SIGNED_DIR" ] || [ -L "$SIGNED_DIR" ]; then
  fail "signed distribution は上書きしません"
fi
require_regular_file "$CANDIDATE_MANIFEST" "candidate build manifest"
require_regular_file "$ENTITLEMENTS" "Entitlements.plist"
require_regular_file "$PUBLISHER" "macOS atomic publisher"
"$PLUTIL" -lint "$ENTITLEMENTS" >/dev/null || fail "Entitlements.plistが不正です"
validate_signing_identity
validate_symlinks "$CANDIDATE_APP"

STAGING_DIR="$("$MKTEMP" -d "$ROOT/.tomos-signing.XXXXXX")" || fail "private staging directoryを作成できません"
STAGING_DIR="$(cd "$STAGING_DIR" && /bin/pwd -P)"
trap cleanup_exit EXIT
trap 'cleanup_signal 129' HUP
trap 'cleanup_signal 130' INT
trap 'cleanup_signal 143' TERM
STAGING_PAYLOAD="$STAGING_DIR/payload"
"$MKDIR" "$STAGING_PAYLOAD" || fail "signed payloadを作成できません"
STAGING_APP="$STAGING_PAYLOAD/TOMOS AI.app"
STAGING_MANIFEST="$STAGING_PAYLOAD/build-manifest.json"
"$DITTO" "$CANDIDATE_APP" "$STAGING_APP"
require_real_directory "$STAGING_APP" "staging app"
copy_build_manifest
validate_symlinks "$STAGING_APP"
read_main_executable_name
sign_nested_code
sign_main_executable
sign_app_bundle
"$CODESIGN" --verify --deep --strict --verbose=2 "$STAGING_APP"
if [ "$TEST_HOOK_ENABLED" -eq 1 ] && [ "${TOMOS_SIGN_TEST_EXIT_BEFORE_PUBLISH:-}" = "1" ]; then
  exit 0
fi
publish_signed_app

echo "signed app: $SIGNED_APP"
