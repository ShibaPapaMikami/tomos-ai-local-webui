#!/usr/bin/env bash
set -euo pipefail

umask 077

ROOT="$(cd "$(/usr/bin/dirname "$0")/.." && /bin/pwd -P)"
SIGNED_DIR="$ROOT/dist/signed"
SIGNED_APP="$SIGNED_DIR/TOMOS AI.app"
SIGNED_MANIFEST="$SIGNED_DIR/build-manifest.json"
CANDIDATE_DIR="$ROOT/dist/candidate"
OUT_NAME="TOMOS_AI-v0.8.233-mac-arm64.pkg"
OUT_PKG="$CANDIDATE_DIR/$OUT_NAME"
APP_VERSION="0.8.233"
PACKAGE_IDENTIFIER="jp.local.gemma4-12b"
EXPECTED_BUNDLE_ID="com.shibapapastudio.tomos-ai"
EXPECTED_TEAM_ID="AJK3HH9G22"
SIGNING_IDENTITY="${TOMOS_MAC_INSTALLER_IDENTITY:-}"
SIGNING_FINGERPRINT=""
TEST_TOOLS_DIR="${TOMOS_PKG_TEST_TOOLS_DIR:-}"
CANONICAL_TEST_TOOLS_DIR=""
TEST_HOOK_ENABLED=0
SOURCE_COMMIT=""

AWK="/usr/bin/awk"
CODESIGN="/usr/bin/codesign"
DITTO="/usr/bin/ditto"
FIND="/usr/bin/find"
GREP="/usr/bin/grep"
GIT="/usr/bin/git"
MKDIR="/bin/mkdir"
MKTEMP="/usr/bin/mktemp"
PKGBUILD="/usr/bin/pkgbuild"
PKGUTIL="/usr/sbin/pkgutil"
PLUTIL="/usr/bin/plutil"
PYTHON="/usr/bin/python3"
RM="/bin/rm"
SECURITY="/usr/bin/security"
STAGING_DIR=""
STAGING_ROOT=""
STAGING_APP=""
STAGING_MANIFEST=""
STAGING_AUDIT_MANIFEST=""
STAGING_PKG=""
PKGBUILD_OUTPUT=""
CODESIGN_VERIFY_OUTPUT=""
CODESIGN_DETAILS=""
PUBLISHED=0

fail() {
  echo "macOS PKG作成を停止しました: $*" >&2
  exit 1
}

cleanup_with_status() {
  local code="$1"
  if [ -n "$STAGING_DIR" ] && [ -d "$STAGING_DIR" ]; then
    case "$STAGING_DIR" in
      "$ROOT"/.tomos-pkg.*) "$RM" -rf "$STAGING_DIR" ;;
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

cleanup_signal() {
  local code="$1"
  trap - EXIT HUP INT TERM
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
    marker = root / ".tomos-pkg-test-root"
    marker_stat = marker.lstat()
    expected_tools = root / ".test-tools"
    tools_stat = expected_tools.lstat()
    root.relative_to(allowed_parent)
except (OSError, ValueError):
    raise SystemExit(1)
if tools != expected_tools or root.parent != allowed_parent or not root.name.startswith("tomos-pkg-test-"):
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
for name in ("audit", "codesign", "ditto", "git", "pkgbuild", "pkgutil", "plutil", "security"):
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
  DITTO="$CANONICAL_TEST_TOOLS_DIR/ditto"
  CODESIGN="$CANONICAL_TEST_TOOLS_DIR/codesign"
  PKGBUILD="$CANONICAL_TEST_TOOLS_DIR/pkgbuild"
  PKGUTIL="$CANONICAL_TEST_TOOLS_DIR/pkgutil"
  PLUTIL="$CANONICAL_TEST_TOOLS_DIR/plutil"
  SECURITY="$CANONICAL_TEST_TOOLS_DIR/security"
  GIT="$CANONICAL_TEST_TOOLS_DIR/git"
  AUDIT_RUNNER="$CANONICAL_TEST_TOOLS_DIR/audit"
  require_regular_file "$AUDIT_RUNNER" "test audit"
  require_regular_file "$CODESIGN" "test codesign"
  require_regular_file "$DITTO" "test ditto"
  require_regular_file "$PKGBUILD" "test pkgbuild"
  require_regular_file "$PKGUTIL" "test pkgutil"
  require_regular_file "$PLUTIL" "test plutil"
  require_regular_file "$SECURITY" "test security"
  [ -x "$AUDIT_RUNNER" ] && [ -x "$CODESIGN" ] && [ -x "$DITTO" ] && [ -x "$GIT" ] && [ -x "$PKGBUILD" ] && [ -x "$PKGUTIL" ] && [ -x "$PLUTIL" ] && [ -x "$SECURITY" ] || fail "test toolが実行可能ではありません"
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

validate_pkgroot() {
  "$PYTHON" - "$STAGING_ROOT" <<'PY'
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
applications = root / "Applications"
app = applications / "TOMOS AI.app"
try:
    root_entries = list(root.iterdir())
    app_entries = list(applications.iterdir())
    app_stat = app.lstat()
except OSError as exc:
    raise SystemExit("pkgroot is incomplete") from exc
if root_entries != [applications] or app_entries != [app]:
    raise SystemExit("pkgroot contains paths other than the TOMOS app")
if stat.S_ISLNK(app_stat.st_mode) or not stat.S_ISDIR(app_stat.st_mode):
    raise SystemExit("pkgroot app is not a real directory")
PY
}

copy_and_validate_manifest() {
  "$PYTHON" - "$SIGNED_MANIFEST" "$STAGING_MANIFEST" "$APP_VERSION" "$EXPECTED_BUNDLE_ID" "$PACKAGE_IDENTIFIER" <<'PY'
import json
import os
import stat
import sys
from pathlib import Path

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
expected_version, expected_bundle, expected_package = sys.argv[3:]
source_fd = destination_fd = -1
try:
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    source_stat = os.fstat(source_fd)
    if not stat.S_ISREG(source_stat.st_mode):
        raise ValueError("signed manifest is not regular")
    data = bytearray()
    while chunk := os.read(source_fd, 1024 * 1024):
        data.extend(chunk)
    manifest = json.loads(bytes(data).decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("signed manifest is not an object")
    if (
        manifest.get("appVersion") != expected_version
        or manifest.get("bundleId") != expected_bundle
        or manifest.get("pkgIdentifier") != expected_package
    ):
        raise ValueError("signed manifest does not match package contract")
    destination_fd = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    remaining = memoryview(data)
    while remaining:
        written = os.write(destination_fd, remaining)
        remaining = remaining[written:]
finally:
    if destination_fd >= 0:
        os.close(destination_fd)
    if source_fd >= 0:
        os.close(source_fd)
PY
}

link_staging_manifest_for_audit() {
  "$PYTHON" - "$STAGING_MANIFEST" "$STAGING_AUDIT_MANIFEST" <<'PY'
import os
import stat
import sys
from pathlib import Path

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
try:
    source_stat = source.lstat()
    if stat.S_ISLNK(source_stat.st_mode) or not stat.S_ISREG(source_stat.st_mode):
        raise ValueError("staging manifest is not regular")
    os.link(source, destination, follow_symlinks=False)
    destination_stat = destination.lstat()
    if (
        stat.S_ISLNK(destination_stat.st_mode)
        or not stat.S_ISREG(destination_stat.st_mode)
        or (source_stat.st_dev, source_stat.st_ino) != (destination_stat.st_dev, destination_stat.st_ino)
    ):
        raise ValueError("audit manifest was not fixed")
except (OSError, ValueError) as exc:
    raise SystemExit("audit manifest setup failed") from exc
PY
}

report_safe_audit_categories() {
  local raw_categories="$1"
  local safe_categories
  safe_categories="$(
    printf '%s' "$raw_categories" |
      "$PYTHON" -c '
import sys

allowed = {
    "app_bundle",
    "app_version",
    "architecture",
    "build_manifest",
    "bundle_identifier",
    "bundle_read_error",
    "bundle_symlink",
    "forbidden_payload",
    "info_plist",
    "manifest_architecture",
    "manifest_bundle_identifier",
    "manifest_version",
    "minimum_macos",
    "pkg_identifier",
    "python_runtime",
    "python_version",
    "resource_allowlist",
    "source_commit",
}
reported = sorted(set(sys.stdin.read().split(",")) & allowed)
print(",".join(reported) if reported else "audit_failure")
'
  )" || safe_categories="audit_failure"
  printf 'staging app audit errors: %s\n' "$safe_categories" >&2
}

run_staging_audit() {
  local audit_output=""
  if [ "$TEST_HOOK_ENABLED" -eq 1 ]; then
    if audit_output="$("$AUDIT_RUNNER" "$STAGING_APP" "$APP_VERSION" "$SOURCE_COMMIT" 2>/dev/null)"; then
      return 0
    fi
  else
    if audit_output="$(
      "$PYTHON" - "$ROOT/scripts" "$STAGING_APP" "$APP_VERSION" "$SOURCE_COMMIT" 2>/dev/null <<'PY'
import sys
from pathlib import Path

scripts = Path(sys.argv[1])
sys.path.insert(0, str(scripts))
from audit_macos_tauri_release import audit_signed_app

errors = audit_signed_app(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
if errors:
    print(",".join(errors))
    raise SystemExit(1)
PY
    )"; then
      return 0
    fi
  fi

  report_safe_audit_categories "$audit_output"
  fail "staging app auditに失敗しました"
}

validate_staging_app_signature() {
  local info_plist="$STAGING_APP/Contents/Info.plist"
  local bundle_id
  local bundle_version
  require_regular_file "$info_plist" "staging Info.plist"
  bundle_id="$("$PLUTIL" -extract CFBundleIdentifier raw "$info_plist" 2>/dev/null)" || fail "staging Bundle IDを読めません"
  bundle_version="$("$PLUTIL" -extract CFBundleShortVersionString raw "$info_plist" 2>/dev/null)" || fail "staging versionを読めません"
  [ "$bundle_id" = "$EXPECTED_BUNDLE_ID" ] || fail "staging Bundle IDが一致しません"
  [ "$bundle_version" = "$APP_VERSION" ] || fail "staging versionが一致しません"
  CODESIGN_VERIFY_OUTPUT="$("$CODESIGN" --verify --deep --strict --verbose=2 "$STAGING_APP" 2>&1)" || fail "staging appのcodesign verifyに失敗しました"
  CODESIGN_DETAILS="$("$CODESIGN" -dv --verbose=4 "$STAGING_APP" 2>&1)" || fail "staging appの署名情報を読めません"
  printf '%s\n' "$CODESIGN_DETAILS" | "$GREP" -Fqx "Identifier=$EXPECTED_BUNDLE_ID" || fail "staging app identifierが一致しません"
  printf '%s\n' "$CODESIGN_DETAILS" | "$GREP" -Fqx "TeamIdentifier=$EXPECTED_TEAM_ID" || fail "staging app Team IDが一致しません"
  printf '%s\n' "$CODESIGN_DETAILS" | "$GREP" -Fq "Authority=Developer ID Application:" || fail "staging appがDeveloper ID Applicationではありません"
  printf '%s\n' "$CODESIGN_DETAILS" | "$GREP" -Fq "flags=0x10000(runtime)" || fail "staging app hardened runtimeを確認できません"
  printf '%s\n' "$CODESIGN_DETAILS" | "$GREP" -Eq '^Timestamp=.+$' || fail "staging app secure timestampを確認できません"
}

validate_signing_identity() {
  local selector_kind
  [ -n "$SIGNING_IDENTITY" ] || fail "Developer ID Installer証明書の指定が必要です"
  if [ "${#SIGNING_IDENTITY}" -eq 40 ] && [[ "$SIGNING_IDENTITY" != *[!0-9A-Fa-f]* ]]; then
    selector_kind="fingerprint"
  else
    selector_kind="label"
    case "$SIGNING_IDENTITY" in
      "Developer ID Installer:"*"($EXPECTED_TEAM_ID)") ;;
      *) fail "Developer ID Installer証明書のTeam IDが一致しません" ;;
    esac
  fi
  SIGNING_FINGERPRINT="$(
    "$SECURITY" find-identity -v -p basic 2>/dev/null |
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
          prefix = "Developer ID Installer:"
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
  )" || fail "Developer ID Installer証明書を確認できません"
  [ -n "$SIGNING_FINGERPRINT" ] || fail "Developer ID Installer証明書を一意に特定できません"
}

publish_pkg_without_clobber() {
  "$PYTHON" - "$STAGING_PKG" "$CANDIDATE_DIR" "$OUT_NAME" <<'PY'
import errno
import os
import stat
import sys
from pathlib import Path

source = Path(sys.argv[1])
destination_dir = Path(sys.argv[2])
name = sys.argv[3]
if name != "TOMOS_AI-v0.8.233-mac-arm64.pkg" or "/" in name:
    raise SystemExit("invalid package destination")
try:
    source_stat = source.lstat()
    destination_stat = destination_dir.lstat()
    if stat.S_ISLNK(source_stat.st_mode) or not stat.S_ISREG(source_stat.st_mode):
        raise ValueError("staging package is not a regular file")
    if stat.S_ISLNK(destination_stat.st_mode) or not stat.S_ISDIR(destination_stat.st_mode):
        raise ValueError("candidate directory is not a real directory")
    destination_fd = os.open(destination_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
except (OSError, ValueError) as exc:
    raise SystemExit("candidate package publish precondition failed") from exc
try:
    try:
        os.link(source, name, dst_dir_fd=destination_fd, follow_symlinks=False)
    except FileExistsError as exc:
        raise SystemExit("candidate package already exists") from exc
    published_stat = os.stat(name, dir_fd=destination_fd, follow_symlinks=False)
    if (
        not stat.S_ISREG(published_stat.st_mode)
        or (published_stat.st_dev, published_stat.st_ino) != (source_stat.st_dev, source_stat.st_ino)
    ):
        raise SystemExit("candidate package publish verification failed")
    try:
        current_destination_stat = destination_dir.lstat()
    except OSError as exc:
        os.unlink(name, dir_fd=destination_fd)
        raise SystemExit("candidate package path changed during publish") from exc
    if (current_destination_stat.st_dev, current_destination_stat.st_ino) != (
        destination_stat.st_dev,
        destination_stat.st_ino,
    ):
        os.unlink(name, dir_fd=destination_fd)
        raise SystemExit("candidate package path changed during publish")
finally:
    os.close(destination_fd)
PY
}

configure_test_tools
require_real_directory "$ROOT" "repository root"
require_real_directory "$ROOT/dist" "dist directory"
require_real_directory "$SIGNED_DIR" "signed directory"
require_real_directory "$CANDIDATE_DIR" "candidate directory"
require_real_directory "$SIGNED_APP" "signed app"
if [ -e "$OUT_PKG" ] || [ -L "$OUT_PKG" ]; then
  fail "candidate PKGは上書きしません"
fi
validate_symlinks "$SIGNED_APP" || fail "signed appのsymlinkが不正です"
SOURCE_COMMIT="$("$GIT" -C "$ROOT" rev-parse HEAD 2>/dev/null)" || fail "source commitを読めません"
case "$SOURCE_COMMIT" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) fail "source commitが不正です" ;;
esac
validate_signing_identity

STAGING_DIR="$("$MKTEMP" -d "$ROOT/.tomos-pkg.XXXXXX")" || fail "private staging directoryを作成できません"
STAGING_DIR="$(cd "$STAGING_DIR" && /bin/pwd -P)"
trap cleanup_exit EXIT
trap 'cleanup_signal 129' HUP
trap 'cleanup_signal 130' INT
trap 'cleanup_signal 143' TERM
STAGING_ROOT="$STAGING_DIR/pkgroot"
STAGING_APP="$STAGING_ROOT/Applications/TOMOS AI.app"
STAGING_MANIFEST="$STAGING_DIR/build-manifest.json"
STAGING_PKG="$STAGING_DIR/$OUT_NAME"
copy_and_validate_manifest || fail "signed build manifestが不正です"
require_regular_file "$STAGING_MANIFEST" "staging build manifest"
"$MKDIR" -p "$STAGING_ROOT/Applications" || fail "PKG payload directoryを作成できません"
"$DITTO" "$SIGNED_APP" "$STAGING_APP" || fail "signed appをprivate payloadへcopyできません"
require_real_directory "$STAGING_APP" "staging app"
validate_symlinks "$STAGING_APP" || fail "staging appのsymlinkが不正です"
validate_staging_app_signature
STAGING_AUDIT_MANIFEST="$STAGING_APP/../build-manifest.json"
link_staging_manifest_for_audit || fail "staging audit manifestを固定できません"
run_staging_audit
"$RM" "$STAGING_AUDIT_MANIFEST" || fail "staging audit manifestを削除できません"
STAGING_AUDIT_MANIFEST=""
validate_pkgroot || fail "PKG payloadが不正です"
PKGBUILD_OUTPUT="$("$PKGBUILD" \
  --root "$STAGING_ROOT" \
  --identifier "$PACKAGE_IDENTIFIER" \
  --version "$APP_VERSION" \
  --install-location / \
  --sign "$SIGNING_FINGERPRINT" \
  "$STAGING_PKG" 2>&1)" || fail "pkgbuildに失敗しました"
require_regular_file "$STAGING_PKG" "staging PKG"
SIGNATURE_OUTPUT="$("$PKGUTIL" --check-signature "$STAGING_PKG" 2>&1)" || fail "PKG署名を確認できません"
printf '%s\n' "$SIGNATURE_OUTPUT" | "$GREP" -Fq "Developer ID Installer:" || fail "PKGのInstaller署名を確認できません"
printf '%s\n' "$SIGNATURE_OUTPUT" | "$GREP" -Fq "($EXPECTED_TEAM_ID)" || fail "PKGのInstaller Teamを確認できません"
publish_pkg_without_clobber || fail "candidate PKGのatomic publishに失敗しました"
require_regular_file "$OUT_PKG" "published candidate PKG"
PUBLISHED=1

echo "candidate PKG: $OUT_PKG"
