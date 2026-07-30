#!/usr/bin/env bash
set -euo pipefail

umask 077

ROOT="$(cd "$(/usr/bin/dirname "$0")/.." && /bin/pwd -P)"
VERSION="0.8.233"
TEAM_ID="AJK3HH9G22"
APP="$ROOT/dist/signed/TOMOS AI.app"
MANIFEST="$ROOT/dist/signed/build-manifest.json"
OUTPUT_NAME="TOMOS_AI-v${VERSION}-mac-arm64.pkg"
CANDIDATE="$ROOT/dist/candidate/$OUTPUT_NAME"
NOTARIZED_DIR="$ROOT/dist/notarized"
REJECTED_DIR="$ROOT/dist/rejected"
NOTARY_PROFILE="${TOMOS_NOTARY_PROFILE:-tomos-notary}"
TEST_TOOLS_DIR="${TOMOS_RELEASE_GATE_TEST_TOOLS_DIR:-}"
TEST_HOOK_ENABLED=0
AUDIT_RUNNER=""

CODESIGN="/usr/bin/codesign"
DITTO="/usr/bin/ditto"
GIT="/usr/bin/git"
MKDIR="/bin/mkdir"
MKTEMP="/usr/bin/mktemp"
PKGUTIL="/usr/sbin/pkgutil"
PYTHON="/usr/bin/python3"
RM="/bin/rm"
SECURITY="/usr/bin/security"
SHASUM="/usr/bin/shasum"
SPCTL="/usr/sbin/spctl"
XCRUN="/usr/bin/xcrun"
DATE="/bin/date"
STAGE=""
STAGE_PKG=""
STAGE_SHA=""
STAGE_EXPANDED=""
STAGE_PAYLOAD_CONTAINER=""
STAGE_PAYLOAD=""
PUBLISHED=0

fail() { echo "macOS release gateを停止しました: $*" >&2; exit 1; }

configure_test_tools() {
  local canonical_tools
  [ -n "$TEST_TOOLS_DIR" ] || return 0
  canonical_tools="$("$PYTHON" - "$ROOT" "$TEST_TOOLS_DIR" <<'PY'
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
    marker = root / ".tomos-release-gate-test-root"
    marker_stat = marker.lstat()
    expected_tools = root / ".test-tools"
    tools_stat = expected_tools.lstat()
    root.relative_to(allowed_parent)
except (OSError, ValueError):
    raise SystemExit(1)
if (
    tools != expected_tools
    or root.parent != allowed_parent
    or not root.name.startswith("tomos-release-gate-test-")
):
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
for name in ("audit", "codesign", "ditto", "git", "pkgutil", "spctl", "xcrun"):
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
  AUDIT_RUNNER="$canonical_tools/audit"
  CODESIGN="$canonical_tools/codesign"
  DITTO="$canonical_tools/ditto"
  GIT="$canonical_tools/git"
  PKGUTIL="$canonical_tools/pkgutil"
  SPCTL="$canonical_tools/spctl"
  XCRUN="$canonical_tools/xcrun"
  TEST_HOOK_ENABLED=1
}

validate_release_directories() {
  "$PYTHON" - "$ROOT/dist" <<'PY' || fail "release出力先が安全ではありません"
import os
import stat
import sys

dist = sys.argv[1]
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
fd = os.open(dist, flags)
try:
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise SystemExit(1)
    for name in ("notarized", "rejected"):
        try:
            os.mkdir(name, 0o700, dir_fd=fd)
        except FileExistsError:
            pass
        child = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if (
            not stat.S_ISDIR(child.st_mode)
            or child.st_uid != os.geteuid()
            or child.st_mode & 0o022
        ):
            raise SystemExit(1)
finally:
    os.close(fd)
PY
}

quarantine() {
  [ -n "$STAGE_PKG" ] && [ -f "$STAGE_PKG" ] && [ -n "$STAGE" ] || return 0
  "$PYTHON" - "$REJECTED_DIR" "$STAGE_PKG" "$STAGE_SHA" "$OUTPUT_NAME" <<'PY'
import os, secrets, stat, sys
from pathlib import Path
root, pkg, digest, name = map(Path, sys.argv[1:])
root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
target_fd = -1
try:
    info = os.fstat(root_fd)
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise SystemExit(1)
    for _ in range(16):
        target_name = f"rejected-{secrets.token_hex(8)}"
        try:
            os.mkdir(target_name, 0o700, dir_fd=root_fd)
        except FileExistsError:
            continue
        target_fd = os.open(
            target_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=root_fd,
        )
        break
    else:
        raise SystemExit(1)
    for source, leaf in ((pkg, name.name), (digest, f"{name.name}.sha256")):
        try:
            source_info = source.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(source_info.st_mode):
            os.link(source, leaf, dst_dir_fd=target_fd, follow_symlinks=False)
finally:
    if target_fd >= 0:
        os.close(target_fd)
    os.close(root_fd)
PY
}

cleanup() {
  local code=$?
  trap - EXIT HUP INT TERM
  if [ "$PUBLISHED" -ne 1 ]; then quarantine || code=1; fi
  if [ -n "$STAGE" ] && [ -d "$STAGE" ]; then "$RM" -rf "$STAGE"; fi
  exit "$code"
}

validate_signed_app() {
  local commit details
  commit="$("$GIT" -C "$ROOT" rev-parse HEAD 2>/dev/null)" || fail "HEADを読めません"
  if [ "$TEST_HOOK_ENABLED" -eq 1 ]; then
    "$AUDIT_RUNNER" "$APP" "$VERSION" "$commit" >/dev/null 2>&1 || fail "signed app auditに失敗しました"
  else
    "$PYTHON" - "$ROOT/scripts" "$APP" "$VERSION" "$commit" <<'PY' || fail "signed app auditに失敗しました"
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from audit_macos_tauri_release import audit_signed_app
raise SystemExit(0 if not audit_signed_app(Path(sys.argv[2]), sys.argv[3], sys.argv[4]) else 1)
PY
  fi
  "$CODESIGN" --verify --deep --strict --verbose=2 "$APP" >/dev/null 2>&1 || fail "app codesign verifyに失敗しました"
  details="$("$CODESIGN" -dv --verbose=4 "$APP" 2>&1)" || fail "app署名情報を読めません"
  printf '%s\n' "$details" | /usr/bin/grep -Fqx "TeamIdentifier=$TEAM_ID" || fail "app Team IDが一致しません"
  printf '%s\n' "$details" | /usr/bin/grep -Fq 'Authority=Developer ID Application:' || fail "app Developer IDを確認できません"
  printf '%s\n' "$details" | /usr/bin/grep -Fq 'flags=0x10000(runtime)' || fail "app runtimeを確認できません"
  printf '%s\n' "$details" | /usr/bin/grep -Eq '^Timestamp=.+$' || fail "app timestampを確認できません"
}

validate_pkg() {
  local signature payload
  signature="$("$PKGUTIL" --check-signature "$STAGE_PKG" 2>&1)" || fail "PKG署名を読めません"
  printf '%s\n' "$signature" | /usr/bin/grep -Fq 'Developer ID Installer:' || fail "PKG Installer署名を確認できません"
  printf '%s\n' "$signature" | /usr/bin/grep -Fq "($TEAM_ID)" || fail "PKG Team IDが一致しません"
  payload="$("$PKGUTIL" --payload-files "$STAGE_PKG" 2>&1)" || fail "PKG payloadを読めません"
  "$PYTHON" - "$payload" <<'PY' || fail "PKG payloadが不正です"
import sys
from pathlib import PurePosixPath

paths = []
for line in sys.argv[1].splitlines():
    path = line.strip()
    if not path:
        continue
    while path.startswith("./"):
        path = path[2:]
    parsed = PurePosixPath(path)
    if not path or parsed.is_absolute() or any(part in ("", ".", "..") for part in parsed.parts):
        raise SystemExit(1)
    paths.append(str(parsed))
if not paths or any(not (path == "Applications/TOMOS AI.app" or path.startswith("Applications/TOMOS AI.app/")) for path in paths):
    raise SystemExit(1)
PY
}

validate_pkg_contents() {
  "$PKGUTIL" --expand "$STAGE_PKG" "$STAGE_EXPANDED" >/dev/null 2>&1 || fail "PKG展開に失敗しました"
  "$PYTHON" - "$STAGE_EXPANDED" <<'PY' || fail "PackageInfoが不正です"
import os
import stat
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(sys.argv[1])
root_info = root.lstat()
if (
    not stat.S_ISDIR(root_info.st_mode)
    or root_info.st_uid != os.geteuid()
    or stat.S_IMODE(root_info.st_mode) != 0o700
):
    raise SystemExit(1)
entries = {item.name for item in root.iterdir()}
if not {"PackageInfo", "Payload"}.issubset(entries) or not entries <= {
    "PackageInfo",
    "Payload",
    "Bom",
}:
    raise SystemExit(1)
for name in entries:
    info = (root / name).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
        raise SystemExit(1)
package_info = root / "PackageInfo"
if package_info.stat().st_size > 1024 * 1024:
    raise SystemExit(1)
document = ET.parse(package_info)
element = document.getroot()
local_name = lambda tag: tag.rsplit("}", 1)[-1].lower()
if (
    local_name(element.tag) != "pkg-info"
    or element.get("identifier") != "jp.local.gemma4-12b"
    or element.get("version") != "0.8.233"
    or element.get("install-location") != "/"
    or any(local_name(item.tag) == "scripts" for item in element.iter())
):
    raise SystemExit(1)
PY
  "$MKDIR" -m 700 "$STAGE_PAYLOAD_CONTAINER" || fail "Payload検証領域を作成できません"
  "$DITTO" -x -z "$STAGE_EXPANDED/Payload" "$STAGE_PAYLOAD" >/dev/null 2>&1 || fail "Payload展開に失敗しました"
  "$PYTHON" - "$STAGE_PAYLOAD_CONTAINER" "$STAGE_PAYLOAD" "$APP" <<'PY' || fail "PKG内容がcurrent signed appと一致しません"
from hashlib import sha256
import os
import stat
import sys
from pathlib import Path

container, extracted, signed_app = map(Path, sys.argv[1:])
if [item.name for item in container.iterdir()] != [extracted.name]:
    raise SystemExit(1)
if not stat.S_ISDIR(extracted.lstat().st_mode):
    raise SystemExit(1)
if {item.name for item in extracted.iterdir()} != {"Applications"}:
    raise SystemExit(1)
applications = extracted / "Applications"
if not stat.S_ISDIR(applications.lstat().st_mode):
    raise SystemExit(1)
if {item.name for item in applications.iterdir()} != {"TOMOS AI.app"}:
    raise SystemExit(1)
payload_app = applications / "TOMOS AI.app"
if not stat.S_ISDIR(payload_app.lstat().st_mode):
    raise SystemExit(1)

def within(root, target):
    try:
        target.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        raise SystemExit(1)

def digest(path):
    result = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()

def inventory(root):
    result = {}
    pending = [(Path("."), root)]
    while pending:
        relative, path = pending.pop()
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISDIR(info.st_mode):
            result[str(relative)] = ("dir", mode)
            for child in sorted(path.iterdir(), key=lambda item: item.name, reverse=True):
                pending.append((relative / child.name, child))
        elif stat.S_ISREG(info.st_mode):
            result[str(relative)] = ("file", mode, digest(path))
        elif stat.S_ISLNK(info.st_mode):
            within(root, path)
            result[str(relative)] = ("symlink", mode, os.readlink(path))
        else:
            raise SystemExit(1)
    return result

if inventory(signed_app) != inventory(payload_app):
    raise SystemExit(1)
PY
}

publish_no_clobber() {
  "$PYTHON" - "$STAGE_PKG" "$STAGE_SHA" "$NOTARIZED_DIR" "$OUTPUT_NAME" <<'PY'
import os
import sys
from pathlib import Path

pkg, digest, directory, name = map(Path, sys.argv[1:])
directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
created = []
try:
    info = os.fstat(directory_fd)
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise OSError
    for source, target in ((pkg, name.name), (digest, f"{name.name}.sha256")):
        os.link(source, target, dst_dir_fd=directory_fd, follow_symlinks=False)
        created.append(target)
except OSError:
    for target in created:
        try: os.unlink(target, dir_fd=directory_fd)
        except OSError: pass
    raise SystemExit(1)
finally:
    os.close(directory_fd)
PY
}

configure_test_tools
[ "$#" -eq 1 ] || fail "candidate PKG pathが不正です"
CANDIDATE="$("$PYTHON" - "$ROOT" "$1" <<'PY'
import sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(strict=True); item=Path(sys.argv[2]).resolve(strict=True)
expected=root/'dist/candidate/TOMOS_AI-v0.8.233-mac-arm64.pkg'
if item != expected: raise SystemExit(1)
print(item)
PY
)" || fail "candidate PKG pathが不正です"
[ -f "$CANDIDATE" ] && [ ! -L "$CANDIDATE" ] || fail "candidate PKGがありません"
[ -d "$APP" ] && [ ! -L "$APP" ] || fail "signed appがありません"
[ -f "$MANIFEST" ] && [ ! -L "$MANIFEST" ] || fail "signed manifestがありません"
validate_release_directories
[ -z "$("$GIT" -C "$ROOT" status --porcelain)" ] || fail "source worktreeがcleanではありません"
trap cleanup EXIT HUP INT TERM
validate_signed_app
STAGE="$("$MKTEMP" -d "$ROOT/.tomos-notary.XXXXXX")" || fail "private stagingを作成できません"
STAGE_PKG="$STAGE/$OUTPUT_NAME"
STAGE_SHA="$STAGE/$OUTPUT_NAME.sha256"
STAGE_EXPANDED="$STAGE/expanded"
STAGE_PAYLOAD_CONTAINER="$STAGE/payload-container"
STAGE_PAYLOAD="$STAGE_PAYLOAD_CONTAINER/extracted"
"$PYTHON" - "$CANDIDATE" "$STAGE_PKG" <<'PY' || fail "candidate copyに失敗しました"
import os, stat, sys
src, dst = sys.argv[1:]; sfd=os.open(src, os.O_RDONLY|os.O_NOFOLLOW); dfd=-1
try:
 st=os.fstat(sfd)
 if not stat.S_ISREG(st.st_mode): raise ValueError
 dfd=os.open(dst, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
 while True:
  chunk=os.read(sfd, 1024*1024)
  if not chunk: break
  os.write(dfd, chunk)
finally:
 if dfd>=0: os.close(dfd)
 os.close(sfd)
PY
[ -f "$STAGE_PKG" ] && [ ! -L "$STAGE_PKG" ] || fail "staging PKGが不正です"
validate_pkg
validate_pkg_contents
"$XCRUN" notarytool history --keychain-profile "$NOTARY_PROFILE" --output-format json >/dev/null 2>&1 || fail "notary profileが使えません"
notary_json="$STAGE/notary.json"
"$XCRUN" notarytool submit "$STAGE_PKG" --keychain-profile "$NOTARY_PROFILE" --wait --output-format json > "$notary_json" 2>/dev/null || fail "notary submitに失敗しました"
"$PYTHON" - "$notary_json" <<'PY' || fail "notary statusがAcceptedではありません"
import json,sys
from pathlib import Path
path=Path(sys.argv[1])
if path.stat().st_size > 1024 * 1024: raise SystemExit(1)
data=json.loads(path.read_text(encoding='utf-8'))
raise SystemExit(0 if isinstance(data,dict) and data.get('status') == 'Accepted' else 1)
PY
"$XCRUN" stapler staple "$STAGE_PKG" >/dev/null 2>&1 || fail "stapler stapleに失敗しました"
"$XCRUN" stapler validate "$STAGE_PKG" >/dev/null 2>&1 || fail "stapler validateに失敗しました"
spctl_output="$("$SPCTL" -a -vv -t install "$STAGE_PKG" 2>&1)" || fail "Gatekeeper確認に失敗しました"
printf '%s\n' "$spctl_output" | /usr/bin/grep -Fq 'Notarized Developer ID' || fail "GatekeeperがNotarized Developer IDではありません"
"$PYTHON" - "$STAGE_PKG" "$STAGE_SHA" "$OUTPUT_NAME" <<'PY'
import hashlib,re,sys
from pathlib import Path
pkg, out, name=map(Path,sys.argv[1:])
h=hashlib.sha256()
with pkg.open('rb') as f:
 for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
out.write_text(f"{h.hexdigest()}  {name.name}\n",encoding='utf-8')
PY
publish_no_clobber || fail "notarized publishに失敗しました"
PUBLISHED=1
echo "notarized PKG: $NOTARIZED_DIR/$OUTPUT_NAME"
