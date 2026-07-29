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
    print("macOS PKG signing tests: OK")
