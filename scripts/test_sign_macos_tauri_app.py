#!/usr/bin/env python3
"""Behavior contracts for the TOMOS macOS app signing entrypoint."""
from __future__ import annotations

import os
import plistlib
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIGN_SOURCE = ROOT / "scripts" / "sign-macos-tauri-app.sh"
ENTITLEMENTS_SOURCE = ROOT / "src-tauri" / "Entitlements.plist"
PUBLISHER_SOURCE = ROOT / "scripts" / "macos-atomic-publish.py"
IDENTITY = "Developer ID Application: TOMOS Test (AJK3HH9G22)"
FINGERPRINT_A = "0123456789ABCDEF0123456789ABCDEF01234567"
FINGERPRINT_B = "FEDCBA9876543210FEDCBA9876543210FEDCBA98"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@contextmanager
def _test_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="tomos-sign-test-", dir="/private/tmp"))
    root.chmod(0o700)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _make_fake_tools(directory: Path) -> None:
    _write_executable(
        directory / "uname",
        "#!/usr/bin/env bash\nprintf 'arm64\\n'\n",
    )
    _write_executable(
        directory / "ditto",
        "#!/usr/bin/env bash\nset -euo pipefail\n/bin/cp -R \"$1\" \"$2\"\n",
    )
    _write_executable(
        directory / "security",
        """#!/usr/bin/env bash
set -euo pipefail
case "${FAKE_IDENTITY_MODE:-good}" in
  good) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Application: TOMOS Test (AJK3HH9G22)"\\n' ;;
  duplicate_same) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Application: TOMOS Test (AJK3HH9G22)"\\n  2) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Application: TOMOS Test (AJK3HH9G22)"\\n' ;;
  ambiguous) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Application: TOMOS Test (AJK3HH9G22)"\\n  2) FEDCBA9876543210FEDCBA9876543210FEDCBA98 "Developer ID Application: TOMOS Test (AJK3HH9G22)"\\n' ;;
  other_team) printf '  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Application: TOMOS Test (OTHERTEAM)"\\n' ;;
  empty) : ;;
  *) exit 64 ;;
esac
""",
    )
    _write_executable(
        directory / "file",
        """#!/usr/bin/env bash
set -euo pipefail
target="${!#}"
if [ "${FAKE_MAIN_NOT_MACHO:-0}" = "1" ] && [[ "$target" == */tomos-desktop ]]; then
  printf 'ASCII text\\n'
elif [[ "$target" == *non-macho.dylib || "$target" == *text-executable ]]; then
  printf 'ASCII text\\n'
elif [[ "$target" == *x86-only.dylib ]]; then
  printf 'Mach-O 64-bit executable x86_64\\n'
elif [[ "$target" == */tomos-desktop || "$target" == *.dylib || "$target" == *.so ]]; then
  printf 'Mach-O 64-bit executable arm64\\n'
else
  printf 'ASCII text\\n'
fi
""",
    )
    _write_executable(
        directory / "codesign",
        """#!/usr/bin/env bash
set -euo pipefail
target="${!#}"
if [ "${1:-}" = "--verify" ]; then
  phase=verify
elif [[ "$target" == */tomos-desktop ]]; then
  phase=main
elif [[ "$target" == *.app ]]; then
  phase=app
else
  phase=nested
fi
printf '%s|%s\\n' "$phase" "$*" >> "${FAKE_SIGN_LOG:?}"
if [ "${FAKE_SIGNAL_PHASE:-}" = "$phase" ]; then
  /bin/kill -"${FAKE_SIGNAL_NAME:-TERM}" "$PPID"
fi
if [ "${FAKE_FAIL_PHASE:-}" = "$phase" ]; then
  exit 71
fi
""",
    )


def _make_fixture(tmp: Path, marker: bool = True) -> tuple[Path, Path]:
    fixture = tmp
    scripts = fixture / "scripts"
    tools = fixture / ".test-tools"
    scripts.mkdir(parents=True)
    tools.mkdir()
    tools.chmod(0o700)
    shutil.copy2(SIGN_SOURCE, scripts / SIGN_SOURCE.name)
    (scripts / SIGN_SOURCE.name).chmod(0o755)
    entitlements = fixture / "src-tauri" / "Entitlements.plist"
    entitlements.parent.mkdir(parents=True)
    shutil.copy2(ENTITLEMENTS_SOURCE, entitlements)
    if PUBLISHER_SOURCE.is_file():
        shutil.copy2(PUBLISHER_SOURCE, scripts / PUBLISHER_SOURCE.name)
    if marker:
        marker_path = fixture / ".tomos-sign-test-root"
        marker_path.write_text("test only\n", encoding="utf-8")
        marker_path.chmod(0o600)

    app = fixture / "dist" / "candidate" / "TOMOS AI.app"
    macos = app / "Contents" / "MacOS"
    python = app / "Contents" / "Resources" / "python" / "lib"
    macos.mkdir(parents=True)
    python.mkdir(parents=True)
    with (app / "Contents" / "Info.plist").open("wb") as destination:
        plistlib.dump({"CFBundleExecutable": "tomos-desktop"}, destination)
    main = macos / "tomos-desktop"
    main.write_bytes(b"fixture main executable")
    main.chmod(0o755)
    (python / "libnested.dylib").write_bytes(b"fixture nested library")
    outer = app / "Contents" / "Resources" / "outer.dylib"
    outer.write_bytes(b"fixture outer library")
    (app / "Contents" / "Resources" / "text-executable").write_bytes(b"text")
    (app / "Contents" / "Resources" / "text-executable").chmod(0o755)
    (app / "Contents" / "Resources" / "non-macho.dylib").write_bytes(b"not macho")
    (app / "Contents" / "Resources" / "x86-only.dylib").write_bytes(b"x86 only")
    (app / "Contents" / "Resources" / "readme.txt").write_text("not code", encoding="utf-8")
    _make_fake_tools(tools)
    return fixture, tools


def _run(
    fixture: Path,
    tools: Path,
    *,
    identity: str = IDENTITY,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    log = fixture / ".sign.log"
    environment = os.environ.copy()
    environment.update(
        {
            "TOMOS_MAC_APPLICATION_IDENTITY": identity,
            "TOMOS_SIGN_TEST_TOOLS_DIR": str(tools),
            "FAKE_SIGN_LOG": str(log),
        }
    )
    if extra_env:
        environment.update(extra_env)
    result = subprocess.run(
        ["bash", str(fixture / "scripts" / SIGN_SOURCE.name)],
        cwd=fixture,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    return result, log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _assert_failure_has_no_final_app(result: subprocess.CompletedProcess[str], fixture: Path) -> None:
    assert result.returncode != 0, result.stdout + result.stderr
    assert not (fixture / "dist" / "signed" / "TOMOS AI.app").exists()
    assert not list(fixture.glob(".tomos-signing.*"))


def test_signs_real_bundle_main_after_nested_before_app_and_verify() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        candidate_main = fixture / "dist" / "candidate" / "TOMOS AI.app" / "Contents" / "MacOS" / "tomos-desktop"
        result, log = _run(fixture, tools)
        assert result.returncode == 0, result.stdout + result.stderr
        assert candidate_main.read_bytes() == b"fixture main executable"
        assert (fixture / "dist" / "signed" / "TOMOS AI.app").is_dir()
        phases = [line.split("|", 1)[0] for line in log]
        assert phases == ["nested", "nested", "main", "app", "verify"], log
        assert "libnested.dylib" in log[0]
        assert "outer.dylib" in log[1]
        assert "tomos-desktop" in log[2]
        assert "--entitlements" in log[2]
        assert "--entitlements" in log[3]
        assert all("--options runtime" in line and "--timestamp" in line for line in log[:4])
        assert all("--deep" not in line for line in log[:4])
        assert all(f"--sign {FINGERPRINT_A}" in line for line in log[:4])
        assert all(IDENTITY not in line for line in log)
        assert "--deep" in log[4]
        assert all("text-executable" not in line and "non-macho.dylib" not in line and "x86-only.dylib" not in line for line in log)
        public_output = result.stdout + result.stderr
        assert IDENTITY not in public_output
        assert "AJK3HH9G22" not in public_output
        assert FINGERPRINT_A not in public_output


def test_duplicate_rows_for_same_label_and_fingerprint_are_one_certificate() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(
            fixture,
            tools,
            extra_env={"FAKE_IDENTITY_MODE": "duplicate_same"},
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (fixture / "dist" / "signed" / "TOMOS AI.app").is_dir()
        assert all(f"--sign {FINGERPRINT_A}" in line for line in log[:4])
        assert all(IDENTITY not in line for line in log)


def test_same_label_with_different_fingerprints_is_rejected() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(
            fixture,
            tools,
            extra_env={"FAKE_IDENTITY_MODE": "ambiguous"},
        )
        _assert_failure_has_no_final_app(result, fixture)
        assert not log
        public_output = result.stdout + result.stderr
        assert IDENTITY not in public_output
        assert "AJK3HH9G22" not in public_output
        assert FINGERPRINT_A not in public_output
        assert FINGERPRINT_B not in public_output


def test_explicit_fingerprint_is_normalized_and_restricted_to_expected_certificate() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(fixture, tools, identity=FINGERPRINT_A.lower())
        assert result.returncode == 0, result.stdout + result.stderr
        assert all(f"--sign {FINGERPRINT_A}" in line for line in log[:4])

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, log = _run(
            fixture,
            tools,
            identity=FINGERPRINT_A,
            extra_env={"FAKE_IDENTITY_MODE": "other_team"},
        )
        _assert_failure_has_no_final_app(result, fixture)
        assert not log


def test_rejects_existing_signed_app_without_overwriting_it() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        final = fixture / "dist" / "signed" / "TOMOS AI.app"
        final.mkdir(parents=True)
        sentinel = final / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        result, log = _run(fixture, tools)
        assert result.returncode != 0
        assert sentinel.read_text(encoding="utf-8") == "keep"
        assert not log


def test_keeps_final_path_absent_when_nested_main_app_or_verify_fails() -> None:
    for phase in ("nested", "main", "app", "verify"):
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            result, _log = _run(fixture, tools, extra_env={"FAKE_FAIL_PHASE": phase})
            _assert_failure_has_no_final_app(result, fixture)


def test_rejects_empty_other_team_and_ambiguous_identity_before_signing() -> None:
    cases = (
        ("", {}),
        ("Developer ID Application: TOMOS Test (OTHERTEAM)", {}),
        (IDENTITY, {"FAKE_IDENTITY_MODE": "empty"}),
    )
    for identity, extra_env in cases:
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            result, log = _run(fixture, tools, identity=identity, extra_env=extra_env)
            _assert_failure_has_no_final_app(result, fixture)
            assert not log


def test_rejects_external_symlink_and_invalid_main_macho_or_mode() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        nested = fixture / "dist" / "candidate" / "TOMOS AI.app" / "Contents" / "Resources" / "python" / "lib" / "libnested.dylib"
        external = fixture / "external.dylib"
        external.write_bytes(b"external")
        nested.unlink()
        nested.symlink_to(external)
        result, _log = _run(fixture, tools)
        _assert_failure_has_no_final_app(result, fixture)

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, _log = _run(fixture, tools, extra_env={"FAKE_MAIN_NOT_MACHO": "1"})
        _assert_failure_has_no_final_app(result, fixture)

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        main = fixture / "dist" / "candidate" / "TOMOS AI.app" / "Contents" / "MacOS" / "tomos-desktop"
        main.chmod(0o644)
        result, _log = _run(fixture, tools)
        _assert_failure_has_no_final_app(result, fixture)


def test_test_tool_hook_requires_temporary_marked_root() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary, marker=False)
        result, _log = _run(fixture, tools)
        _assert_failure_has_no_final_app(result, fixture)
        assert "test tool hook" in result.stderr


def test_rejects_forged_tmpdir_for_non_temporary_production_copy() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        fixture, tools = _make_fixture(Path(temporary))
        result, _log = _run(fixture, tools, extra_env={"TMPDIR": str(fixture.parent)})
        _assert_failure_has_no_final_app(result, fixture)
        assert "test tool hook" in result.stderr


def test_each_signal_has_fixed_nonzero_status_and_keeps_final_path_absent() -> None:
    for signal_name, expected_status in (("HUP", 129), ("INT", 130), ("TERM", 143)):
        with _test_root() as temporary:
            fixture, tools = _make_fixture(temporary)
            result, _log = _run(
                fixture,
                tools,
                extra_env={"FAKE_SIGNAL_PHASE": "nested", "FAKE_SIGNAL_NAME": signal_name},
            )
            assert result.returncode == expected_status
            _assert_failure_has_no_final_app(result, fixture)


def test_normal_exit_before_publish_is_forced_to_fail() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        result, _log = _run(fixture, tools, extra_env={"TOMOS_SIGN_TEST_EXIT_BEFORE_PUBLISH": "1"})
        assert result.returncode == 1
        _assert_failure_has_no_final_app(result, fixture)


def test_rejects_tool_directories_escaping_root_by_dotdot_or_symlink() -> None:
    with _test_root() as temporary:
        fixture, _tools = _make_fixture(temporary)
        escaped = fixture.parent / f"{fixture.name}-escaped-tools"
        escaped.mkdir(mode=0o700)
        _make_fake_tools(escaped)
        try:
            result, _log = _run(fixture, fixture / ".." / escaped.name)
            _assert_failure_has_no_final_app(result, fixture)
            assert "test tool hook" in result.stderr
        finally:
            shutil.rmtree(escaped, ignore_errors=True)

    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        escaped = fixture.parent / f"{fixture.name}-escaped-tools"
        escaped.mkdir(mode=0o700)
        _make_fake_tools(escaped)
        tools.rename(fixture / ".test-tools-original")
        tools.symlink_to(escaped, target_is_directory=True)
        try:
            result, _log = _run(fixture, tools)
            _assert_failure_has_no_final_app(result, fixture)
            assert "test tool hook" in result.stderr
        finally:
            shutil.rmtree(escaped, ignore_errors=True)

    with _test_root() as temporary:
        fixture, _tools = _make_fixture(temporary)
        escaped = fixture.parent / f"{fixture.name}-escaped-tools"
        escaped.mkdir(mode=0o700)
        _make_fake_tools(escaped)
        link = fixture / "tool-link"
        link.symlink_to(escaped, target_is_directory=True)
        try:
            result, _log = _run(fixture, link)
            _assert_failure_has_no_final_app(result, fixture)
            assert "test tool hook" in result.stderr
        finally:
            shutil.rmtree(escaped, ignore_errors=True)


def test_rejects_signed_parent_symlink() -> None:
    with _test_root() as temporary:
        fixture, tools = _make_fixture(temporary)
        signed = fixture / "dist" / "signed"
        external = fixture / "external-signed"
        external.mkdir()
        signed.symlink_to(external, target_is_directory=True)
        result, _log = _run(fixture, tools)
        _assert_failure_has_no_final_app(result, fixture)


def test_atomic_publish_detects_signed_parent_replacement() -> None:
    with _test_root() as temporary:
        fixture, _tools = _make_fixture(temporary)
        stage = fixture / ".tomos-signing.publish-test"
        app = stage / "TOMOS AI.app"
        app.mkdir(parents=True)
        stage.chmod(0o700)
        result = subprocess.run(
            [
                "/usr/bin/python3",
                str(fixture / "scripts" / PUBLISHER_SOURCE.name),
                "--root",
                str(fixture),
                "--stage-name",
                stage.name,
                "--app-name",
                "TOMOS AI.app",
                "--test-replace-signed-parent",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "signed parent directory" in result.stderr
        assert app.is_dir()
        assert not (fixture / "dist" / "signed" / "TOMOS AI.app").exists()


def test_collects_nested_candidates_with_absolute_find() -> None:
    script = SIGN_SOURCE.read_text(encoding="utf-8")
    assert 'FIND="/usr/bin/find"' in script
    assert '"$FIND" "$STAGING_APP" -type f -print0 > "$path_list" || return 1' in script
    assert 'collect_regular_paths_inner_first > "$sorted_path_list"' in script


def test_publish_uses_dirfd_rename_exclusive_helper_and_absolute_tools() -> None:
    script = SIGN_SOURCE.read_text(encoding="utf-8")
    assert 'PUBLISHER="$ROOT/scripts/macos-atomic-publish.py"' in script
    assert '"$PYTHON" "$PUBLISHER"' in script
    assert PUBLISHER_SOURCE.is_file()
    publisher = PUBLISHER_SOURCE.read_text(encoding="utf-8")
    assert "os.O_NOFOLLOW" in publisher
    assert "renameatx_np" in publisher
    assert "RENAME_EXCL" in publisher
    for assignment in (
        'CODESIGN="/usr/bin/codesign"',
        'DITTO="/usr/bin/ditto"',
        'FILE="/usr/bin/file"',
        'FIND="/usr/bin/find"',
        'MKTEMP="/usr/bin/mktemp"',
        'RM="/bin/rm"',
        'PLUTIL="/usr/bin/plutil"',
        'PYTHON="/usr/bin/python3"',
        'SECURITY="/usr/bin/security"',
        'UNAME="/usr/bin/uname"',
        'AWK="/usr/bin/awk"',
    ):
        assert assignment in script
    assert "${TMPDIR" not in script


if __name__ == "__main__":
    test_signs_real_bundle_main_after_nested_before_app_and_verify()
    test_duplicate_rows_for_same_label_and_fingerprint_are_one_certificate()
    test_same_label_with_different_fingerprints_is_rejected()
    test_explicit_fingerprint_is_normalized_and_restricted_to_expected_certificate()
    test_rejects_existing_signed_app_without_overwriting_it()
    test_keeps_final_path_absent_when_nested_main_app_or_verify_fails()
    test_rejects_empty_other_team_and_ambiguous_identity_before_signing()
    test_rejects_external_symlink_and_invalid_main_macho_or_mode()
    test_test_tool_hook_requires_temporary_marked_root()
    test_rejects_forged_tmpdir_for_non_temporary_production_copy()
    test_each_signal_has_fixed_nonzero_status_and_keeps_final_path_absent()
    test_normal_exit_before_publish_is_forced_to_fail()
    test_rejects_tool_directories_escaping_root_by_dotdot_or_symlink()
    test_rejects_signed_parent_symlink()
    test_atomic_publish_detects_signed_parent_replacement()
    test_collects_nested_candidates_with_absolute_find()
    test_publish_uses_dirfd_rename_exclusive_helper_and_absolute_tools()
    print("macOS Tauri app signing tests: OK")
