#!/usr/bin/env python3
"""Behavior contracts for the TOMOS signed-app macOS PKG entrypoint."""
from __future__ import annotations

import os
import json
import hashlib
import plistlib
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make-macos-tauri-pkg.sh"
NOTARIZE_SCRIPT = ROOT / "scripts" / "notarize-mac-pkg.sh"
IDENTITY = "Developer ID Installer: TOMOS Test (AJK3HH9G22)"
FINGERPRINT_A = "0123456789ABCDEF0123456789ABCDEF01234567"
FINGERPRINT_B = "FEDCBA9876543210FEDCBA9876543210FEDCBA98"
OUTPUT_NAME = "TOMOS_AI-v0.8.233-mac-arm64.pkg"
RELEASE_GATE = ROOT / "scripts" / "release-gate-macos-tauri.sh"
RELEASE_PROFILE_SECRET = "private-notary-profile"
RELEASE_RAW_SECRET = "raw-notary-secret"
RELEASE_CANDIDATE_BYTES = b"candidate package bytes\n"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@contextmanager
def _test_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="tomos-pkg-test-", dir="/private/tmp"))
    root.chmod(0o700)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _make_fake_tools(directory: Path) -> None:
    _write_executable(
        directory / "ditto",
        """#!/usr/bin/env bash
set -euo pipefail
/bin/cp -R "$1" "$2"
if [ "${FAKE_DITTO_REPLACE_AFTER_COPY:-0}" = "1" ]; then
  /usr/bin/touch "$2/Contents/.copy-replaced"
fi
if [ "${FAKE_DITTO_REPLACE_WITH_VALID_OTHER_BUNDLE:-0}" = "1" ]; then
  printf 'other signed bundle resource\\n' > "$2/Contents/Resources/tomos/server.py"
fi
""",
    )
    _write_executable(
        directory / "security",
        """#!/usr/bin/env bash
set -euo pipefail
case "${FAKE_IDENTITY_MODE:-good}" in
  good) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Installer: TOMOS Test (AJK3HH9G22)"\\n' ;;
  duplicate_same) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Installer: TOMOS Test (AJK3HH9G22)"\\n  2) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Installer: TOMOS Test (AJK3HH9G22)"\\n' ;;
  ambiguous) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Installer: TOMOS Test (AJK3HH9G22)"\\n  2) FEDCBA9876543210FEDCBA9876543210FEDCBA98 "Developer ID Installer: TOMOS Test (AJK3HH9G22)"\\n' ;;
  other_team) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Installer: TOMOS Test (OTHERTEAM)"\\n' ;;
  empty) : ;;
  *) exit 64 ;;
esac
""",
    )
    _write_executable(
        directory / "pkgbuild",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "${FAKE_PKG_LOG:?}"
printf 'pkgbuild signing %s\\n' "$*"
root=""
while [ "$#" -gt 1 ]; do
  if [ "$1" = "--root" ]; then
    root="$2"
    break
  fi
  shift
done
[ -n "$root" ]
[ -d "$root/Applications/TOMOS AI.app" ]
[ "$(/usr/bin/find "$root" -mindepth 1 -maxdepth 1 -print | /usr/bin/wc -l | /usr/bin/tr -d ' ')" = "1" ]
[ ! -e "$root/Applications/Gemma4_12B" ]
out="${!#}"
if [ "${FAKE_PKGBUILD_FAIL:-0}" = "1" ]; then
  /usr/bin/touch "$out"
  exit 71
fi
/usr/bin/touch "$out"
""",
    )
    _write_executable(
        directory / "pkgutil",
        """#!/usr/bin/env bash
set -euo pipefail
case "$1" in
  --check-signature) printf 'Developer ID Installer: TOMOS Test (AJK3HH9G22)\\n' ;;
  *) exit 64 ;;
esac
""",
    )
    _write_executable(
        directory / "plutil",
        """#!/usr/bin/env bash
set -euo pipefail
field="$2"
case "${FAKE_APP_MODE:-good}" in
  wrong_bundle) [ "$field" = "CFBundleIdentifier" ] && printf 'com.example.wrong\\n' || printf '0.8.233\\n' ;;
  wrong_version) [ "$field" = "CFBundleIdentifier" ] && printf 'com.shibapapastudio.tomos-ai\\n' || printf '9.9.9\\n' ;;
  *) [ "$field" = "CFBundleIdentifier" ] && printf 'com.shibapapastudio.tomos-ai\\n' || printf '0.8.233\\n' ;;
esac
""",
    )
    _write_executable(
        directory / "codesign",
        """#!/usr/bin/env bash
set -euo pipefail
target="${!#}"
if [ "${1:-}" = "--verify" ]; then
  [ "${FAKE_APP_MODE:-good}" != "unsigned" ]
  [ ! -e "$target/Contents/.copy-replaced" ]
  exit 0
fi
if [ "${1:-}" = "-dv" ]; then
  [ "${FAKE_APP_MODE:-good}" != "unsigned" ]
  [ ! -e "$target/Contents/.copy-replaced" ]
  printf 'Identifier=com.shibapapastudio.tomos-ai\\n'
  case "${FAKE_APP_MODE:-good}" in
    wrong_team) printf 'TeamIdentifier=OTHERTEAM\\n' ;;
    *) printf 'TeamIdentifier=AJK3HH9G22\\n' ;;
  esac
  printf 'Authority=Developer ID Application: TOMOS Test (AJK3HH9G22)\\n'
  [ "${FAKE_APP_MODE:-good}" = "no_runtime" ] || printf 'flags=0x10000(runtime)\\n'
  [ "${FAKE_APP_MODE:-good}" = "no_timestamp" ] || printf 'Timestamp=Jul 29, 2026 at 22:49:20\\n'
  exit 0
fi
exit 64
""",
    )
    _write_executable(
        directory / "git",
        "#!/usr/bin/env bash\nset -euo pipefail\nprintf '%040d\\n' 0 | /usr/bin/tr '0' 'a'\n",
    )
    _write_executable(
        directory / "audit",
        """#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path

if diagnostic := os.environ.get("FAKE_AUDIT_FAILURE_OUTPUT"):
    print(diagnostic)
    raise SystemExit(65)

app = Path(sys.argv[1])
expected_version = sys.argv[2]
expected_commit = sys.argv[3]
try:
    manifest = json.loads((app.parent / "build-manifest.json").read_text(encoding="utf-8"))
    resource_root = app / "Contents" / "Resources" / "tomos"
    expected_files = manifest["files"]
    expected_hashes = manifest["resourceHashes"]
    actual_files = sorted(
        path.relative_to(resource_root).as_posix()
        for path in resource_root.rglob("*")
        if path.is_file()
    )
    if (
        manifest["appVersion"] != expected_version
        or manifest["architecture"] != "arm64"
        or manifest["sourceCommit"] != expected_commit
        or manifest["pythonVersion"] != "3.11.15"
        or not manifest["pythonArtifact"]["name"].startswith("cpython-3.11.15")
        or sorted(expected_files) != actual_files
        or sorted(expected_hashes) != actual_files
    ):
        raise ValueError("audit contract mismatch")
    for name in actual_files:
        digest = hashlib.sha256((resource_root / name).read_bytes()).hexdigest()
        if expected_hashes[name] != digest:
            raise ValueError("resource hash mismatch")
except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
    raise SystemExit(1)
""",
    )


def _make_fixture(tmp: Path, marker: bool = True) -> tuple[Path, Path]:
    fixture = tmp
    scripts = fixture / "scripts"
    tools = fixture / ".test-tools"
    scripts.mkdir(parents=True)
    tools.mkdir()
    tools.chmod(0o700)
    shutil.copy2(SCRIPT, scripts / SCRIPT.name)
    (scripts / SCRIPT.name).chmod(0o755)
    if marker:
        marker_path = fixture / ".tomos-pkg-test-root"
        marker_path.write_text("test only\n", encoding="utf-8")
        marker_path.chmod(0o600)
    signed_app = fixture / "dist" / "signed" / "TOMOS AI.app"
    (signed_app / "Contents" / "MacOS").mkdir(parents=True)
    executable = signed_app / "Contents" / "MacOS" / "tomos-desktop"
    executable.write_bytes(b"signed fixture")
    executable.chmod(0o755)
    with (signed_app / "Contents" / "Info.plist").open("wb") as destination:
        plistlib.dump(
            {
                "CFBundleIdentifier": "com.shibapapastudio.tomos-ai",
                "CFBundleShortVersionString": "0.8.233",
            },
            destination,
        )
    resource_root = signed_app / "Contents" / "Resources" / "tomos"
    resource_root.mkdir(parents=True)
    resource = resource_root / "server.py"
    resource.write_bytes(b"signed fixture resource\n")
    resource_hash = hashlib.sha256(resource.read_bytes()).hexdigest()
    (signed_app.parent / "build-manifest.json").write_text(
        json.dumps(
            {
                "appVersion": "0.8.233",
                "architecture": "arm64",
                "bundleId": "com.shibapapastudio.tomos-ai",
                "pkgIdentifier": "jp.local.gemma4-12b",
                "sourceCommit": "a" * 40,
                "pythonVersion": "3.11.15",
                "pythonArtifact": {"name": "cpython-3.11.15-test"},
                "files": ["server.py"],
                "resourceHashes": {"server.py": resource_hash},
            }
        ),
        encoding="utf-8",
    )
    (fixture / "dist" / "candidate").mkdir()
    _make_fake_tools(tools)
    return fixture, tools


def _run(
    fixture: Path,
    tools: Path,
    *,
    identity: str = IDENTITY,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    log = fixture / ".pkg.log"
    environment = os.environ.copy()
    environment.update(
        {
            "TOMOS_MAC_INSTALLER_IDENTITY": identity,
            "TOMOS_PKG_TEST_TOOLS_DIR": str(tools),
            "FAKE_PKG_LOG": str(log),
        }
    )
    if extra_env:
        environment.update(extra_env)
    result = subprocess.run(
        ["/bin/bash", str(fixture / "scripts" / SCRIPT.name)],
        cwd=fixture,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    return result, log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _assert_failure_is_isolated(result: subprocess.CompletedProcess[str], fixture: Path) -> None:
    assert result.returncode != 0, result.stdout + result.stderr
    assert not (fixture / "dist" / "candidate" / OUTPUT_NAME).exists()
    assert not list(fixture.glob(".tomos-pkg.*"))


@contextmanager
def _release_gate_test_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="tomos-release-gate-test-", dir="/private/tmp"))
    root.chmod(0o700)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _make_release_gate_fake_tools(directory: Path) -> None:
    _write_executable(
        directory / "audit",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'audit\\n' >> "${FAKE_RELEASE_LOG:?}"
[ "${FAKE_RELEASE_AUDIT_MODE:-good}" = "good" ]
""",
    )
    _write_executable(
        directory / "git",
        """#!/usr/bin/env bash
set -euo pipefail
case "$*" in
  *"rev-parse HEAD"*) printf '%040d\\n' 0 | /usr/bin/tr '0' 'a' ;;
  *"status --porcelain"*) [ "${FAKE_RELEASE_GIT_MODE:-clean}" = "clean" ] || printf ' M dirty\\n' ;;
  *) exit 64 ;;
esac
""",
    )
    _write_executable(
        directory / "codesign",
        """#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = "--verify" ]; then
  printf 'codesign-verify\\n' >> "${FAKE_RELEASE_LOG:?}"
  [ "${FAKE_RELEASE_APP_MODE:-good}" = "good" ]
  exit
fi
if [ "${1:-}" = "-dv" ]; then
  printf 'codesign-details\\n' >> "${FAKE_RELEASE_LOG:?}"
  printf 'Authority=Developer ID Application: Test\\n'
  printf 'TeamIdentifier=AJK3HH9G22\\n'
  printf 'flags=0x10000(runtime)\\n'
  printf 'Timestamp=Jul 29, 2026 at 22:49:20\\n'
  exit
fi
exit 64
""",
    )
    _write_executable(
        directory / "pkgutil",
        """#!/usr/bin/env bash
set -euo pipefail
case "$1" in
  --check-signature)
    printf 'pkgutil-signature\\n' >> "${FAKE_RELEASE_LOG:?}"
    if [ "${FAKE_RELEASE_PKG_MODE:-good}" = "stage_mutation" ]; then
      printf 'mutated staging bytes\\n' >> "$2"
      exit 65
    fi
    [ "${FAKE_RELEASE_PKG_MODE:-good}" != "bad_signature" ] || exit 65
    if [ "${FAKE_RELEASE_PKG_MODE:-good}" = "wrong_team" ]; then
      printf 'Developer ID Installer: Test (OTHERTEAM)\\n'
    else
      printf 'Developer ID Installer: Test (AJK3HH9G22)\\n'
    fi
    ;;
  --payload-files)
    printf 'pkgutil-payload\\n' >> "${FAKE_RELEASE_LOG:?}"
    if [ "${FAKE_RELEASE_PKG_MODE:-good}" = "bad_payload" ]; then
      printf 'Library/Unexpected\\n'
    elif [ "${FAKE_RELEASE_PKG_MODE:-good}" = "path_traversal" ]; then
      printf '../../Applications/TOMOS AI.app/Contents/Info.plist\\n'
    else
      printf 'Applications/TOMOS AI.app\\nApplications/TOMOS AI.app/Contents/Info.plist\\n'
    fi
    ;;
  --expand)
    printf 'pkgutil-expand\\n' >> "${FAKE_RELEASE_LOG:?}"
    destination="$3"
    /bin/mkdir "$destination"
    identifier="jp.local.gemma4-12b"
    version="0.8.233"
    install_location="/"
    case "${FAKE_RELEASE_EXPAND_MODE:-good}" in
      wrong_identifier) identifier="com.example.wrong" ;;
      wrong_version) version="9.9.9" ;;
      wrong_install_location) install_location="/tmp" ;;
    esac
    printf '<pkg-info identifier="%s" version="%s" install-location="%s">' "$identifier" "$version" "$install_location" > "$destination/PackageInfo"
    if [ "${FAKE_RELEASE_EXPAND_MODE:-good}" = "scripts" ]; then
      printf '<scripts><postinstall file="./postinstall"/></scripts>' >> "$destination/PackageInfo"
    fi
    printf '</pkg-info>\\n' >> "$destination/PackageInfo"
    printf 'payload fixture\\n' > "$destination/Payload"
    printf 'bom fixture\\n' > "$destination/Bom"
    if [ "${FAKE_RELEASE_EXPAND_MODE:-good}" = "extra_entry" ]; then
      printf 'unexpected\\n' > "$destination/Unexpected"
    fi
    ;;
  *) exit 64 ;;
esac
""",
    )
    _write_executable(
        directory / "ditto",
        """#!/usr/bin/env bash
set -euo pipefail
[ "$1" = "-x" ] && [ "$2" = "-z" ] || exit 64
printf 'ditto-payload\\n' >> "${FAKE_RELEASE_LOG:?}"
destination="$4"
/bin/mkdir -p "$destination/Applications"
/bin/cp -pR "${FAKE_RELEASE_ROOT:?}/dist/signed/TOMOS AI.app" "$destination/Applications/TOMOS AI.app"
case "${FAKE_RELEASE_PAYLOAD_MODE:-good}" in
  app_bytes) printf 'different app bytes\\n' > "$destination/Applications/TOMOS AI.app/Contents/Info.plist" ;;
  external_symlink) /bin/ln -s /private/tmp "$destination/Applications/TOMOS AI.app/Contents/external" ;;
  extra_payload) /bin/mkdir "$destination/Library" ;;
  path_traversal) printf 'escaped\\n' > "$destination/../escape" ;;
esac
""",
    )
    _write_executable(
        directory / "xcrun",
        """#!/usr/bin/env bash
set -euo pipefail
if [ "$1" = "notarytool" ] && [ "$2" = "history" ]; then
  printf 'notary-history\\n' >> "${FAKE_RELEASE_LOG:?}"
  printf '{"history":[],"private":"%s"}\\n' "${FAKE_RELEASE_RAW_SECRET:?}"
  printf 'history stderr %s\\n' "${FAKE_RELEASE_RAW_SECRET:?}" >&2
  [ "${FAKE_RELEASE_PROFILE_MODE:-good}" = "good" ]
  exit
fi
if [ "$1" = "notarytool" ] && [ "$2" = "submit" ]; then
  printf 'notary-submit\\n' >> "${FAKE_RELEASE_LOG:?}"
  printf '{"status":"%s","private":"%s"}\\n' "${FAKE_RELEASE_NOTARY_STATUS:-Accepted}" "${FAKE_RELEASE_RAW_SECRET:?}"
  printf 'submit stderr %s\\n' "${FAKE_RELEASE_RAW_SECRET:?}" >&2
  exit
fi
if [ "$1" = "stapler" ] && [ "$2" = "staple" ]; then
  printf 'stapler-staple\\n' >> "${FAKE_RELEASE_LOG:?}"
  printf 'stapled\\n' >> "$3"
  exit
fi
if [ "$1" = "stapler" ] && [ "$2" = "validate" ]; then
  printf 'stapler-validate\\n' >> "${FAKE_RELEASE_LOG:?}"
  exit
fi
exit 64
""",
    )
    _write_executable(
        directory / "spctl",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'spctl\\n' >> "${FAKE_RELEASE_LOG:?}"
[ "${FAKE_RELEASE_SPCTL_MODE:-good}" = "good" ] || exit 65
printf 'source=Notarized Developer ID\\n'
""",
    )


def _make_release_gate_fixture(
    root: Path,
    *,
    marker: bool = True,
) -> tuple[Path, Path, Path]:
    scripts = root / "scripts"
    tools = root / ".test-tools"
    scripts.mkdir(parents=True)
    tools.mkdir()
    tools.chmod(0o700)
    shutil.copy2(RELEASE_GATE, scripts / RELEASE_GATE.name)
    (scripts / RELEASE_GATE.name).chmod(0o755)
    if marker:
        marker_path = root / ".tomos-release-gate-test-root"
        marker_path.write_text("test only\n", encoding="utf-8")
        marker_path.chmod(0o600)
    candidate = root / "dist" / "candidate" / OUTPUT_NAME
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(RELEASE_CANDIDATE_BYTES)
    app = root / "dist" / "signed" / "TOMOS AI.app"
    (app / "Contents").mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_bytes(b"current signed app bytes\n")
    (app.parent / "build-manifest.json").write_text(
        json.dumps({"sourceCommit": "a" * 40}),
        encoding="utf-8",
    )
    (root / "dist" / "notarized").mkdir()
    (root / "dist" / "rejected").mkdir()
    _make_release_gate_fake_tools(tools)
    return candidate, tools, scripts / RELEASE_GATE.name


def _run_release_gate(
    root: Path,
    candidate: Path,
    tools: Path,
    script: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    log = root / ".release.log"
    environment = os.environ.copy()
    environment.update(
        {
            "TOMOS_NOTARY_PROFILE": RELEASE_PROFILE_SECRET,
            "TOMOS_RELEASE_GATE_TEST_TOOLS_DIR": str(tools),
            "FAKE_RELEASE_LOG": str(log),
            "FAKE_RELEASE_RAW_SECRET": RELEASE_RAW_SECRET,
            "FAKE_RELEASE_ROOT": str(root),
        }
    )
    if extra_env:
        environment.update(extra_env)
    result = subprocess.run(
        ["/bin/bash", str(script), str(candidate.relative_to(root))],
        cwd=root,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    return result, log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_pkg_script_installs_tauri_app() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "TOMOS AI.app" in script
    assert 'jp.local.gemma4-12b' in script
    assert "Developer ID Installer:" in script
    assert "/Applications/Gemma4_12B" not in script
    assert "postinstall" not in script
    assert "0.8.233" in script
    assert OUTPUT_NAME in script


def test_pkg_builds_only_signed_app_with_atomic_no_clobber_publish() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        source = fixture / "dist" / "signed" / "TOMOS AI.app" / "Contents" / "MacOS" / "tomos-desktop"
        result, log = _run(fixture, tools)
        output = fixture / "dist" / "candidate" / OUTPUT_NAME
        assert result.returncode == 0, result.stdout + result.stderr
        assert output.is_file()
        assert source.read_bytes() == b"signed fixture"
        assert len(log) == 1
        assert "--identifier jp.local.gemma4-12b" in log[0]
        assert "--version 0.8.233" in log[0]
        assert "--install-location /" in log[0]
        assert f"--sign {FINGERPRINT_A}" in log[0]
        assert IDENTITY not in result.stdout + result.stderr
        assert "AJK3HH9G22" not in result.stdout + result.stderr
        assert FINGERPRINT_A not in result.stdout + result.stderr
        assert not list(fixture.glob(".tomos-pkg.*"))


def test_rejects_untrusted_or_mismatched_signed_payload_before_pkgbuild() -> None:
    for mode in ("unsigned", "wrong_bundle", "wrong_version", "wrong_team", "no_runtime", "no_timestamp"):
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            result, log = _run(fixture, tools, extra_env={"FAKE_APP_MODE": mode})
            _assert_failure_is_isolated(result, fixture)
            assert not log

    for key, value in (("appVersion", "9.9.9"), ("bundleId", "com.example.wrong")):
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            manifest = fixture / "dist" / "signed" / "build-manifest.json"
            contents = json.loads(manifest.read_text(encoding="utf-8"))
            contents[key] = value
            manifest.write_text(json.dumps(contents), encoding="utf-8")
            result, log = _run(fixture, tools)
            _assert_failure_is_isolated(result, fixture)
            assert not log


def test_revalidates_staging_app_when_copy_replaces_signed_input() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(fixture, tools, extra_env={"FAKE_DITTO_REPLACE_AFTER_COPY": "1"})
        _assert_failure_is_isolated(result, fixture)
        assert not log


def test_audit_rejects_incomplete_or_mismatched_manifest_and_resources() -> None:
    required = ("architecture", "sourceCommit", "pythonVersion", "pythonArtifact", "files", "resourceHashes")
    for key in required:
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            manifest = fixture / "dist" / "signed" / "build-manifest.json"
            contents = json.loads(manifest.read_text(encoding="utf-8"))
            del contents[key]
            manifest.write_text(json.dumps(contents), encoding="utf-8")
            result, log = _run(fixture, tools)
            _assert_failure_is_isolated(result, fixture)
            assert not log

    for key, value in (("architecture", "x86_64"), ("sourceCommit", "b" * 40)):
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            manifest = fixture / "dist" / "signed" / "build-manifest.json"
            contents = json.loads(manifest.read_text(encoding="utf-8"))
            contents[key] = value
            manifest.write_text(json.dumps(contents), encoding="utf-8")
            result, log = _run(fixture, tools)
            _assert_failure_is_isolated(result, fixture)
            assert not log

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        resource = fixture / "dist" / "signed" / "TOMOS AI.app" / "Contents" / "Resources" / "tomos" / "server.py"
        resource.write_bytes(b"mismatched resource\n")
        result, log = _run(fixture, tools)
        _assert_failure_is_isolated(result, fixture)
        assert not log


def test_audit_rejects_validly_signed_other_bundle_replaced_during_copy() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(fixture, tools, extra_env={"FAKE_DITTO_REPLACE_WITH_VALID_OTHER_BUNDLE": "1"})
        _assert_failure_is_isolated(result, fixture)
        assert not log


def test_audit_failure_reports_only_safe_categories_before_generic_failure() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        private_path = "/private/tmp/private-payload"
        raw_diagnostic = (
            f"python_runtime,build_manifest,not_allowed,{FINGERPRINT_B},{private_path}"
        )
        result, log = _run(
            fixture,
            tools,
            extra_env={"FAKE_AUDIT_FAILURE_OUTPUT": raw_diagnostic},
        )

        _assert_failure_is_isolated(result, fixture)
        assert not log
        assert result.stdout == ""
        assert result.stderr.splitlines()[-2:] == [
            "staging app audit errors: build_manifest,python_runtime",
            "macOS PKG作成を停止しました: staging app auditに失敗しました",
        ]
        assert "not_allowed" not in result.stderr
        assert FINGERPRINT_B not in result.stderr
        assert private_path not in result.stderr
        assert IDENTITY not in result.stderr


def test_identity_duplicate_rows_normalize_but_ambiguous_or_wrong_team_rejects() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(fixture, tools, extra_env={"FAKE_IDENTITY_MODE": "duplicate_same"})
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(log) == 1
        assert f"--sign {FINGERPRINT_A}" in log[0]

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(fixture, tools, identity=FINGERPRINT_A.lower())
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(log) == 1
        assert f"--sign {FINGERPRINT_A}" in log[0]

    for identity, mode in ((IDENTITY, "ambiguous"), (IDENTITY, "other_team"), ("", "good"), (IDENTITY, "empty")):
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            result, log = _run(fixture, tools, identity=identity, extra_env={"FAKE_IDENTITY_MODE": mode})
            _assert_failure_is_isolated(result, fixture)
            assert not log
            assert IDENTITY not in result.stdout + result.stderr
            assert "AJK3HH9G22" not in result.stdout + result.stderr
            assert FINGERPRINT_A not in result.stdout + result.stderr
            assert FINGERPRINT_B not in result.stdout + result.stderr

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(
            fixture,
            tools,
            identity=FINGERPRINT_A,
            extra_env={"FAKE_IDENTITY_MODE": "other_team"},
        )
        _assert_failure_is_isolated(result, fixture)
        assert not log


def test_rejects_output_or_symlinked_input_without_clobbering() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        output = fixture / "dist" / "candidate" / OUTPUT_NAME
        output.write_text("keep", encoding="utf-8")
        result, log = _run(fixture, tools)
        assert result.returncode != 0
        assert output.read_text(encoding="utf-8") == "keep"
        assert not log

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        output = fixture / "dist" / "candidate" / OUTPUT_NAME
        external = fixture / "external-package.pkg"
        external.write_text("keep", encoding="utf-8")
        output.symlink_to(external)
        result, log = _run(fixture, tools)
        assert result.returncode != 0
        assert output.is_symlink()
        assert external.read_text(encoding="utf-8") == "keep"
        assert not log

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        source = fixture / "dist" / "signed" / "TOMOS AI.app"
        external = fixture / "external-app"
        source.rename(external)
        source.symlink_to(external, target_is_directory=True)
        result, log = _run(fixture, tools)
        _assert_failure_is_isolated(result, fixture)
        assert not log

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        candidate = fixture / "dist" / "candidate"
        external = fixture / "external-candidate"
        candidate.rename(external)
        candidate.symlink_to(external, target_is_directory=True)
        result, log = _run(fixture, tools)
        _assert_failure_is_isolated(result, fixture)
        assert not log


def test_pkgbuild_failure_leaves_no_candidate_pkg_or_staging() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(fixture, tools, extra_env={"FAKE_PKGBUILD_FAIL": "1"})
        _assert_failure_is_isolated(result, fixture)
        assert len(log) == 1


def test_test_tool_hook_requires_marked_private_temporary_root() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary, marker=False)
        result, log = _run(fixture, tools)
        _assert_failure_is_isolated(result, fixture)
        assert not log
        assert "test tool hook" in result.stderr

    with tempfile.TemporaryDirectory() as temporary:
        fixture, tools = _make_fixture(Path(temporary))
        result, log = _run(fixture, tools)
        _assert_failure_is_isolated(result, fixture)
        assert not log
        assert "test tool hook" in result.stderr


def test_script_uses_private_staging_and_absolute_production_tools() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'umask 077' in script
    assert 'MKTEMP="/usr/bin/mktemp"' in script
    assert 'PKGBUILD="/usr/bin/pkgbuild"' in script
    assert 'PKGUTIL="/usr/sbin/pkgutil"' in script
    assert 'SECURITY="/usr/bin/security"' in script
    assert 'CODESIGN="/usr/bin/codesign"' in script
    assert 'PLUTIL="/usr/bin/plutil"' in script
    assert 'DITTO="/usr/bin/ditto"' in script
    assert 'PYTHON="/usr/bin/python3"' in script
    assert '"$MKTEMP" -d "$ROOT/.tomos-pkg.XXXXXX"' in script
    assert '${TMPDIR' not in script
    assert 'os.link(' in script
    assert 'os.O_NOFOLLOW' in script
    assert 'from audit_macos_tauri_release import audit_signed_app' in script


def test_notarization_script_verifies_every_release_gate() -> None:
    script = NOTARIZE_SCRIPT.read_text(encoding="utf-8")
    assert 'pkgutil --check-signature "$PKG_PATH"' in script
    assert 'notarytool submit "$PKG_PATH"' in script
    assert '--keychain-profile "$NOTARY_PROFILE"' in script
    assert "--wait" in script
    assert 'stapler staple "$PKG_PATH"' in script
    assert 'stapler validate "$PKG_PATH"' in script
    assert 'spctl -a -vv -t install "$PKG_PATH"' in script


def test_github_actions_builds_windows_only_and_keeps_mac_signing_local() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build-installers.yml").read_text(
        encoding="utf-8"
    )
    assert "windows-msi:" in workflow
    assert "make-windows-msi.py" in workflow
    assert "mac-pkg:" not in workflow
    assert "make-mac-pkg.sh" not in workflow


def test_release_gate_orders_signed_audit_notarization_and_atomic_publish() -> None:
    script = RELEASE_GATE.read_text(encoding="utf-8")
    ordered = (
        "audit_signed_app",
        '--verify --deep --strict',
        '--check-signature',
        '--payload-files',
        'notarytool submit',
        '--wait',
        'Accepted',
        'stapler staple',
        'stapler validate',
        '"$SPCTL" -a -vv -t install',
        'hashlib.sha256',
    )
    positions = [script.index(value) for value in ordered]
    assert positions == sorted(positions)
    assert 'dist/notarized' in script
    assert 'dist/rejected' in script
    assert 'os.link(' in script
    assert 'TOMOS AI.app' in script
    assert 'postinstall' not in script


def test_release_gate_behavior_success_orders_gates_and_publishes_verified_pair() -> None:
    with _release_gate_test_root() as root:
        candidate, tools, script = _make_release_gate_fixture(root)
        original = candidate.read_bytes()
        result, log = _run_release_gate(root, candidate, tools, script)

        assert result.returncode == 0, result.stdout + result.stderr
        assert log == [
            "audit",
            "codesign-verify",
            "codesign-details",
            "pkgutil-signature",
            "pkgutil-payload",
            "pkgutil-expand",
            "ditto-payload",
            "notary-history",
            "notary-submit",
            "stapler-staple",
            "stapler-validate",
            "spctl",
        ]
        published = root / "dist" / "notarized" / OUTPUT_NAME
        digest = published.with_name(f"{OUTPUT_NAME}.sha256")
        assert published.read_bytes() == original + b"stapled\n"
        expected_hash = hashlib.sha256(published.read_bytes()).hexdigest()
        assert digest.read_text(encoding="utf-8") == f"{expected_hash}  {OUTPUT_NAME}\n"
        assert candidate.read_bytes() == original
        assert not list(root.glob(".tomos-notary.*"))
        combined = result.stdout + result.stderr
        assert RELEASE_PROFILE_SECRET not in combined
        assert RELEASE_RAW_SECRET not in combined
        assert FINGERPRINT_A not in combined


def test_release_gate_rejects_nonaccepted_and_staging_copy_mutation() -> None:
    cases = (
        ({"FAKE_RELEASE_NOTARY_STATUS": "Rejected"}, "notary-submit"),
        ({"FAKE_RELEASE_PKG_MODE": "stage_mutation"}, "pkgutil-signature"),
    )
    for extra_env, last_gate in cases:
        with _release_gate_test_root() as root:
            candidate, tools, script = _make_release_gate_fixture(root)
            original = candidate.read_bytes()
            result, log = _run_release_gate(
                root,
                candidate,
                tools,
                script,
                extra_env=extra_env,
            )

            assert result.returncode != 0
            assert log[-1] == last_gate
            assert not list((root / "dist" / "notarized").iterdir())
            rejected = list((root / "dist" / "rejected").iterdir())
            assert len(rejected) == 1
            assert (rejected[0] / OUTPUT_NAME).is_file()
            assert candidate.read_bytes() == original
            combined = result.stdout + result.stderr
            assert RELEASE_PROFILE_SECRET not in combined
            assert RELEASE_RAW_SECRET not in combined


def test_release_gate_rejects_pkg_signature_team_and_payload_before_notary() -> None:
    for mode in ("bad_signature", "wrong_team", "bad_payload", "path_traversal"):
        with _release_gate_test_root() as root:
            candidate, tools, script = _make_release_gate_fixture(root)
            original = candidate.read_bytes()
            result, log = _run_release_gate(
                root,
                candidate,
                tools,
                script,
                extra_env={"FAKE_RELEASE_PKG_MODE": mode},
            )

            assert result.returncode != 0
            assert "notary-history" not in log
            assert "notary-submit" not in log
            assert not list((root / "dist" / "notarized").iterdir())
            assert candidate.read_bytes() == original


def test_release_gate_rejects_package_metadata_and_payload_not_bound_to_current_app() -> None:
    cases = (
        ({"FAKE_RELEASE_EXPAND_MODE": "wrong_identifier"}, "pkgutil-expand"),
        ({"FAKE_RELEASE_EXPAND_MODE": "wrong_version"}, "pkgutil-expand"),
        ({"FAKE_RELEASE_EXPAND_MODE": "wrong_install_location"}, "pkgutil-expand"),
        ({"FAKE_RELEASE_EXPAND_MODE": "scripts"}, "pkgutil-expand"),
        ({"FAKE_RELEASE_EXPAND_MODE": "extra_entry"}, "pkgutil-expand"),
        ({"FAKE_RELEASE_PAYLOAD_MODE": "app_bytes"}, "ditto-payload"),
        ({"FAKE_RELEASE_PAYLOAD_MODE": "external_symlink"}, "ditto-payload"),
        ({"FAKE_RELEASE_PAYLOAD_MODE": "extra_payload"}, "ditto-payload"),
        ({"FAKE_RELEASE_PAYLOAD_MODE": "path_traversal"}, "ditto-payload"),
    )
    for extra_env, last_gate in cases:
        with _release_gate_test_root() as root:
            candidate, tools, script = _make_release_gate_fixture(root)
            original = candidate.read_bytes()
            result, log = _run_release_gate(
                root,
                candidate,
                tools,
                script,
                extra_env=extra_env,
            )

            assert result.returncode != 0, extra_env
            assert log[-1] == last_gate
            assert "notary-history" not in log
            assert "notary-submit" not in log
            assert not list((root / "dist" / "notarized").iterdir())
            assert candidate.read_bytes() == original


def test_release_gate_preflight_failures_stop_before_notary_without_leaks() -> None:
    cases = (
        ({"FAKE_RELEASE_GIT_MODE": "dirty"}, []),
        ({"FAKE_RELEASE_AUDIT_MODE": "bad"}, ["audit"]),
        (
            {"FAKE_RELEASE_APP_MODE": "bad"},
            ["audit", "codesign-verify"],
        ),
        (
            {"FAKE_RELEASE_PROFILE_MODE": "bad"},
            [
                "audit",
                "codesign-verify",
                "codesign-details",
                "pkgutil-signature",
                "pkgutil-payload",
                "pkgutil-expand",
                "ditto-payload",
                "notary-history",
            ],
        ),
    )
    for extra_env, expected_log in cases:
        with _release_gate_test_root() as root:
            candidate, tools, script = _make_release_gate_fixture(root)
            original = candidate.read_bytes()
            result, log = _run_release_gate(
                root,
                candidate,
                tools,
                script,
                extra_env=extra_env,
            )

            assert result.returncode != 0, extra_env
            assert log == expected_log
            assert "notary-submit" not in log
            assert candidate.read_bytes() == original
            assert not list((root / "dist" / "notarized").iterdir())
            combined = result.stdout + result.stderr
            assert RELEASE_PROFILE_SECRET not in combined
            assert RELEASE_RAW_SECRET not in combined
            assert FINGERPRINT_A not in combined


def test_release_gate_rejects_notarized_and_rejected_symlink_roots() -> None:
    for directory_name in ("notarized", "rejected"):
        with _release_gate_test_root() as root, tempfile.TemporaryDirectory(
            prefix="tomos-release-external-",
            dir="/private/tmp",
        ) as external_directory:
            candidate, tools, script = _make_release_gate_fixture(root)
            original = candidate.read_bytes()
            target = root / "dist" / directory_name
            target.rmdir()
            target.symlink_to(external_directory, target_is_directory=True)

            result, log = _run_release_gate(root, candidate, tools, script)

            assert result.returncode != 0
            assert not log
            assert candidate.read_bytes() == original
            assert not list(Path(external_directory).iterdir())
            combined = result.stdout + result.stderr
            assert RELEASE_PROFILE_SECRET not in combined
            assert RELEASE_RAW_SECRET not in combined


def test_release_gate_second_publish_failure_rolls_back_and_preserves_existing_sha() -> None:
    with _release_gate_test_root() as root:
        candidate, tools, script = _make_release_gate_fixture(root)
        original = candidate.read_bytes()
        notarized = root / "dist" / "notarized"
        existing_sha = notarized / f"{OUTPUT_NAME}.sha256"
        existing_sha.write_text("keep existing sha\n", encoding="utf-8")

        result, log = _run_release_gate(root, candidate, tools, script)

        assert result.returncode != 0
        assert log[-1] == "spctl"
        assert not (notarized / OUTPUT_NAME).exists()
        assert existing_sha.read_text(encoding="utf-8") == "keep existing sha\n"
        assert candidate.read_bytes() == original
        rejected = list((root / "dist" / "rejected").iterdir())
        assert len(rejected) == 1
        assert (rejected[0] / OUTPUT_NAME).is_file()
        assert (rejected[0] / f"{OUTPUT_NAME}.sha256").is_file()


def test_release_gate_rejected_quarantine_is_unique_and_no_clobber() -> None:
    with _release_gate_test_root() as root:
        candidate, tools, script = _make_release_gate_fixture(root)
        collision = root / "dist" / "rejected" / "rejected-collision"
        collision.mkdir()
        sentinel = collision / OUTPUT_NAME
        sentinel.write_text("keep rejected artifact\n", encoding="utf-8")

        result, _log = _run_release_gate(
            root,
            candidate,
            tools,
            script,
            extra_env={
                "FAKE_RELEASE_NOTARY_STATUS": "Invalid",
                "TZSTAMP": "rejected",
            },
        )

        assert result.returncode != 0
        assert sentinel.read_text(encoding="utf-8") == "keep rejected artifact\n"
        rejected = list((root / "dist" / "rejected").iterdir())
        assert len(rejected) == 2
        created = next(path for path in rejected if path != collision)
        assert created.name.startswith("rejected-")
        assert (created / OUTPUT_NAME).is_file()


def test_release_gate_test_hook_rejects_invalid_roots_markers_modes_and_symlinks() -> None:
    with _release_gate_test_root() as root:
        candidate, tools, script = _make_release_gate_fixture(root, marker=False)
        result, log = _run_release_gate(root, candidate, tools, script)
        assert result.returncode != 0
        assert "test tool hook" in result.stderr
        assert not log

    with _release_gate_test_root() as root:
        candidate, tools, script = _make_release_gate_fixture(root)
        root.chmod(0o755)
        result, log = _run_release_gate(root, candidate, tools, script)
        assert result.returncode != 0
        assert "test tool hook" in result.stderr
        assert not log

    with _release_gate_test_root() as root:
        candidate, tools, script = _make_release_gate_fixture(root)
        (tools / "xcrun").unlink()
        (tools / "xcrun").symlink_to("/usr/bin/true")
        result, log = _run_release_gate(root, candidate, tools, script)
        assert result.returncode != 0
        assert "test tool hook" in result.stderr
        assert not log

    with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        candidate, tools, script = _make_release_gate_fixture(root)
        result, log = _run_release_gate(root, candidate, tools, script)
        assert result.returncode != 0
        assert "test tool hook" in result.stderr
        assert not log


if __name__ == "__main__":
    test_pkg_script_installs_tauri_app()
    test_pkg_builds_only_signed_app_with_atomic_no_clobber_publish()
    test_rejects_untrusted_or_mismatched_signed_payload_before_pkgbuild()
    test_revalidates_staging_app_when_copy_replaces_signed_input()
    test_audit_rejects_incomplete_or_mismatched_manifest_and_resources()
    test_audit_rejects_validly_signed_other_bundle_replaced_during_copy()
    test_audit_failure_reports_only_safe_categories_before_generic_failure()
    test_identity_duplicate_rows_normalize_but_ambiguous_or_wrong_team_rejects()
    test_rejects_output_or_symlinked_input_without_clobbering()
    test_pkgbuild_failure_leaves_no_candidate_pkg_or_staging()
    test_test_tool_hook_requires_marked_private_temporary_root()
    test_script_uses_private_staging_and_absolute_production_tools()
    test_notarization_script_verifies_every_release_gate()
    test_github_actions_builds_windows_only_and_keeps_mac_signing_local()
    test_release_gate_orders_signed_audit_notarization_and_atomic_publish()
    test_release_gate_behavior_success_orders_gates_and_publishes_verified_pair()
    test_release_gate_rejects_nonaccepted_and_staging_copy_mutation()
    test_release_gate_rejects_pkg_signature_team_and_payload_before_notary()
    test_release_gate_rejects_package_metadata_and_payload_not_bound_to_current_app()
    test_release_gate_preflight_failures_stop_before_notary_without_leaks()
    test_release_gate_rejects_notarized_and_rejected_symlink_roots()
    test_release_gate_second_publish_failure_rolls_back_and_preserves_existing_sha()
    test_release_gate_rejected_quarantine_is_unique_and_no_clobber()
    test_release_gate_test_hook_rejects_invalid_roots_markers_modes_and_symlinks()
    print("macOS PKG signing tests: OK")
