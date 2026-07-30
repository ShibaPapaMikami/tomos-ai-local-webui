#!/usr/bin/env python3
"""Tests for the TOMOS macOS release-candidate static audit."""
from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import stat
import struct
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from macos_python_runtime import ARTIFACT, stage_runtime, verify_artifact_file


ARM64_CPU_TYPE = 0x0100000C
ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_TEMPORARY = tempfile.TemporaryDirectory()
_RUNTIME_FIXTURE: Path | None = None


def _write_invalid_arm64_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<IIIIIIII", 0xFEEDFACF, ARM64_CPU_TYPE, 0, 2, 1, 8, 0, 0)
    path.write_bytes(header + struct.pack("<II", 0, 8))
    path.chmod(0o755)


def _verified_runtime_fixture() -> Path:
    global _RUNTIME_FIXTURE
    if _RUNTIME_FIXTURE is None:
        destination = Path(_RUNTIME_TEMPORARY.name) / "python"
        with (ROOT / "build" / "cache" / ARTIFACT.name).open("rb") as source:
            verify_artifact_file(source, ARTIFACT)
            _RUNTIME_FIXTURE = stage_runtime(source, destination)
    return _RUNTIME_FIXTURE


def make_app_fixture(
    root: Path,
    *,
    bundle_id: str = "com.shibapapastudio.tomos-ai",
    extra_files: list[str] | None = None,
    runtime_symlinks: bool = True,
) -> Path:
    app = root / "TOMOS AI.app"
    contents = app / "Contents"
    executable = contents / "MacOS" / "tomos-desktop"
    python = contents / "Resources" / "python" / "bin" / "python3"
    tomos = contents / "Resources" / "tomos"
    shutil.copytree(_verified_runtime_fixture(), python.parent.parent, symlinks=runtime_symlinks)
    executable.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(python, executable)
    (tomos / "server.py").parent.mkdir(parents=True, exist_ok=True)
    (tomos / "server.py").write_text("APP_VERSION = 'fixture'\n", encoding="utf-8")
    (tomos / "web").mkdir()
    (tomos / "web" / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
    with (contents / "Info.plist").open("wb") as output:
        plistlib.dump(
            {
                "CFBundleIdentifier": bundle_id,
                "CFBundleShortVersionString": "0.8.233",
                "LSMinimumSystemVersion": "13.0",
            },
            output,
        )

    files = ["server.py", "web/index.html"]
    resource_hashes = {
        relative: hashlib.sha256((tomos / relative).read_bytes()).hexdigest()
        for relative in files
    }
    (app.parent / "build-manifest.json").write_text(
        json.dumps(
            {
                "appVersion": "0.8.233",
                "architecture": "arm64",
                "bundleId": "com.shibapapastudio.tomos-ai",
                "pkgIdentifier": "jp.local.gemma4-12b",
                "pythonVersion": "3.11.15",
                "pythonArtifact": {
                    "name": "cpython-3.11.15+fixture-aarch64-apple-darwin-install_only.tar.gz"
                },
                "sourceCommit": "a" * 40,
                "files": files,
                "resourceHashes": resource_hashes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for relative in extra_files or []:
        extra = app / relative
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b"fixture")
    return app


def _audit(app: Path) -> list[str]:
    from audit_macos_tauri_release import audit_app

    return audit_app(app, "0.8.233", "a" * 40)


def _audit_signed(app: Path) -> list[str]:
    from audit_macos_tauri_release import audit_signed_app

    return audit_signed_app(app, "0.8.233", "a" * 40)


def _manifest(root: Path) -> tuple[Path, dict[str, object]]:
    path = root / "build-manifest.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_accepts_matching_release_candidate() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        assert _audit(make_app_fixture(Path(temporary))) == []


def test_signed_audit_accepts_runtime_macho_changes_but_rejects_non_macho_mutation() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        python = app / "Contents" / "Resources" / "python"
        signed_binary = python / "bin" / "python3"
        signed_binary.write_bytes(signed_binary.read_bytes() + b"signed-runtime-mutation")
        signed_macho = lambda path: Path(path).name in {"python3", "python3.11", "tomos-desktop"}
        with patch("audit_macos_tauri_release._is_arm64_macho_code", side_effect=signed_macho):
            assert _audit_signed(app) == []

        license_file = python / "lib" / "python3.11" / "LICENSE.txt"
        license_file.write_bytes(b"unexpected mutation")
        with patch("audit_macos_tauri_release._is_arm64_macho_code", side_effect=signed_macho):
            assert "python_runtime" in _audit_signed(app)


def test_signed_audit_rejects_archive_non_macho_replaced_by_arm64_macho() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        python = app / "Contents" / "Resources" / "python"
        license_file = python / "lib" / "python3.11" / "LICENSE.txt"
        original_mode = stat.S_IMODE(license_file.stat().st_mode)
        shutil.copyfile(python / "bin" / "python3", license_file)
        license_file.chmod(original_mode)

        assert "python_runtime" in _audit_signed(app)


def test_signed_production_audit_accepts_current_signed_app() -> None:
    from audit_macos_tauri_release import audit_signed_app

    commit = subprocess.run(
        ["/usr/bin/git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    signed = ROOT / "dist" / "signed" / "TOMOS AI.app"
    assert audit_signed_app(signed, "0.8.233", commit) == []


def test_signed_production_audit_accepts_current_signed_app_under_private_umask() -> None:
    from audit_macos_tauri_release import audit_signed_app

    commit = subprocess.run(
        ["/usr/bin/git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    signed = ROOT / "dist" / "signed" / "TOMOS AI.app"
    previous_umask = os.umask(0o077)
    try:
        assert audit_signed_app(signed, "0.8.233", commit) == []
    finally:
        os.umask(previous_umask)


def test_signed_audit_rejects_unapproved_runtime_symlink() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary), runtime_symlinks=False)
        _replace_materialized_runtime_file_with_symlink(app)
        assert "python_runtime" in _audit_signed(app)


def test_signed_audit_rejects_stale_source_commit() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        from audit_macos_tauri_release import audit_signed_app

        assert "source_commit" in audit_signed_app(app, "0.8.233", "b" * 40)


def test_rejects_wrong_bundle_identifier() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary), bundle_id="example.invalid")
        assert "bundle_identifier" in _audit(app)


def test_rejects_incomplete_and_non_executable_macho() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        executable = app / "Contents" / "MacOS" / "tomos-desktop"
        executable.write_bytes(bytes.fromhex("cffaedfe0c000001"))
        executable.chmod(0o755)
        assert "architecture" in _audit(app)

        shutil.copy2(app / "Contents" / "Resources" / "python" / "bin" / "python3", executable)
        executable.chmod(0o644)
        assert "architecture" in _audit(app)


def test_rejects_fat_count_over_limit_before_tool_parse() -> None:
    import audit_macos_tauri_release as audit_module

    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        executable = app / "Contents" / "MacOS" / "tomos-desktop"
        executable.write_bytes(b"\xca\xfe\xba\xbe" + struct.pack(">I", 129))
        executable.chmod(0o755)
        with patch.object(audit_module, "_run_macho_tool", side_effect=AssertionError("tool should not run")):
            assert "architecture" in _audit(app)


def test_rejects_invalid_load_command_id() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        executable = app / "Contents" / "MacOS" / "tomos-desktop"
        _write_invalid_arm64_executable(executable)
        assert "architecture" in _audit(app)


def test_rejects_dylib_even_when_path_contains_execute() -> None:
    from audit_macos_tauri_release import _is_arm64_macho

    with tempfile.TemporaryDirectory() as temporary:
        source = _verified_runtime_fixture() / "lib" / "libpython3.11.dylib"
        target = Path(temporary) / "EXECUTE.dylib"
        shutil.copy2(source, target)
        target.chmod(0o755)
        assert not _is_arm64_macho(target)


def test_rejects_fat_binary_with_later_invalid_entry() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        executable = app / "Contents" / "MacOS" / "tomos-desktop"
        arm64 = (app / "Contents" / "Resources" / "python" / "bin" / "python3").read_bytes()
        offset = 48
        executable.write_bytes(
            b"\xca\xfe\xba\xbe"
            + struct.pack(">I", 2)
            + struct.pack(">IIIII", ARM64_CPU_TYPE, 0, offset, len(arm64), 0)
            + struct.pack(">IIIII", ARM64_CPU_TYPE, 0, len(arm64) + offset + 1, 64, 0)
            + arm64
        )
        executable.chmod(0o755)
        assert "architecture" in _audit(app)


def test_rejects_external_symlinks_for_metadata_and_executables() -> None:
    cases = (
        ("Contents/Info.plist", "info_plist"),
        ("Contents/MacOS/tomos-desktop", "architecture"),
        ("Contents/Resources/python/bin/python3", "architecture"),
        ("build-manifest.json", "build_manifest"),
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for index, (relative, expected) in enumerate(cases):
            case_root = root / str(index)
            app = make_app_fixture(case_root)
            target = case_root / relative if relative == "build-manifest.json" else app / relative
            external = root / f"external-{index}"
            shutil.copy2(target, external)
            target.unlink()
            target.symlink_to(external)
            assert expected in _audit(app)


def test_rejects_any_internal_bundle_symlink() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = make_app_fixture(root)
        external = root / "external-resource"
        external.mkdir()
        (app / "Contents" / "Resources" / "extra").symlink_to(external, target_is_directory=True)
        assert "bundle_symlink" in _audit(app)


def test_rejects_private_mutable_and_model_payloads() -> None:
    cases = (
        "Contents/Resources/tomos/.git/config",
        "Contents/Resources/gemma.gguf",
        "Contents/Resources/customer.db-wal",
        "Contents/Resources/tomos/service.log.1",
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for index, relative in enumerate(cases):
            app = make_app_fixture(root / str(index), extra_files=[relative])
            assert "forbidden_payload" in _audit(app)


def test_allows_only_standard_library_token_name() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(
            Path(temporary) / "detokenizer",
            extra_files=["Contents/Resources/tomos/detokenizer.py"],
        )
        assert "forbidden_payload" not in _audit(app)


def test_rejects_runtime_tree_mutation_and_allows_verified_runtime() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        assert _audit(app) == []

        app = make_app_fixture(
            Path(temporary) / "mutated",
            extra_files=["Contents/Resources/python/injected.txt"],
        )
        assert "python_runtime" in _audit(app)


def test_accepts_runtime_with_ditto_normalized_symlinks() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary), runtime_symlinks=False)
        assert _audit(app) == []


def _replace_materialized_runtime_file_with_symlink(app: Path) -> Path:
    python_root = app / "Contents" / "Resources" / "python"
    pip = python_root / "bin" / "pip"
    pip3 = python_root / "bin" / "pip3"
    assert not pip.is_symlink() and not pip3.is_symlink()
    assert pip.read_bytes() == pip3.read_bytes()
    assert (pip.stat().st_mode & 0o777) == (pip3.stat().st_mode & 0o777)
    pip3.unlink()
    pip3.symlink_to("pip")
    return python_root


def test_rejects_new_runtime_symlink_at_artifact_regular_file() -> None:
    from audit_macos_tauri_release import _python_runtime_matches_verified_artifact

    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary), runtime_symlinks=False)
        python_root = _replace_materialized_runtime_file_with_symlink(app)
        assert not _python_runtime_matches_verified_artifact(python_root)


def test_audit_reports_new_runtime_symlink_at_artifact_regular_file() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary), runtime_symlinks=False)
        _replace_materialized_runtime_file_with_symlink(app)
        result = _audit(app)
        assert "bundle_symlink" in result
        assert "python_runtime" in result


def test_accepts_existing_candidate_runtime() -> None:
    from audit_macos_tauri_release import _python_runtime_matches_verified_artifact

    candidate = ROOT / "dist" / "candidate" / "TOMOS AI.app" / "Contents" / "Resources" / "python"
    assert _python_runtime_matches_verified_artifact(candidate)


def _assert_secret_name_is_rejected(name: str) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(
            Path(temporary), extra_files=[f"Contents/Resources/{name}.json"]
        )
        assert "forbidden_payload" in _audit(app)


def test_rejects_access_token_name() -> None:
    _assert_secret_name_is_rejected("accessToken")


def test_rejects_openai_api_key_name() -> None:
    _assert_secret_name_is_rejected("openaiApiKey")


def test_rejects_private_key_name() -> None:
    _assert_secret_name_is_rejected("privateKey")


def test_rejects_client_secret_name() -> None:
    _assert_secret_name_is_rejected("clientSecret")


def test_rejects_refresh_token_name() -> None:
    _assert_secret_name_is_rejected("refreshToken")


def test_rejects_credentials_name() -> None:
    _assert_secret_name_is_rejected("credentials")


def test_rejects_secrets_name() -> None:
    _assert_secret_name_is_rejected("secrets")


def _assert_secret_path_is_rejected(relative: str) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(
            Path(temporary), extra_files=[f"Contents/Resources/{relative}"]
        )
        assert "forbidden_payload" in _audit(app)


def test_rejects_compact_api_key_file_name() -> None:
    _assert_secret_path_is_rejected("apikey.json")


def test_rejects_secret_terms_in_directory_components() -> None:
    for relative in (
        "secrets/config.json",
        "clientSecret/config.json",
        "token-store/config.json",
        "api_key/config.json",
    ):
        _assert_secret_path_is_rejected(relative)


def test_allows_secret_and_token_partial_words() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(
            Path(temporary),
            extra_files=[
                "Contents/Resources/detokenizer.json",
                "Contents/Resources/secretary.json",
            ],
        )
        assert "forbidden_payload" not in _audit(app)


def test_rejects_actual_allowlist_extra_and_hash_tampering() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = make_app_fixture(root, extra_files=["Contents/Resources/tomos/unlisted.py"])
        assert "resource_allowlist" in _audit(app)

        app = make_app_fixture(root / "hash")
        (app / "Contents" / "Resources" / "tomos" / "server.py").write_text("changed\n", encoding="utf-8")
        assert "resource_allowlist" in _audit(app)


def test_rejects_manifest_path_traversal_pkg_id_and_types() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = make_app_fixture(root)
        path, manifest = _manifest(root)
        manifest["files"] = ["../server.py"]
        manifest["pkgIdentifier"] = "example.invalid"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        result = _audit(app)
        assert "resource_allowlist" in result
        assert "pkg_identifier" in result

        app = make_app_fixture(root / "types")
        path, manifest = _manifest(root / "types")
        manifest["resourceHashes"] = []
        path.write_text(json.dumps(manifest), encoding="utf-8")
        assert "resource_allowlist" in _audit(app)


def test_rejects_read_failure_during_tree_audit() -> None:
    import audit_macos_tauri_release as audit_module

    with tempfile.TemporaryDirectory() as temporary:
        app = make_app_fixture(Path(temporary))
        blocked = app / "Contents" / "Resources" / "tomos" / "blocked"
        blocked.mkdir()
        original_scandir = audit_module.os.scandir

        def denied(path):
            if isinstance(path, int):
                return original_scandir(path)
            if Path(path) == blocked:
                raise PermissionError("fixture permission error")
            return original_scandir(path)

        with patch.object(audit_module.os, "scandir", denied):
            assert "bundle_read_error" in _audit(app)


def test_rejects_manifest_source_commit_and_exact_python_version() -> None:
    from audit_macos_tauri_release import audit_app

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = make_app_fixture(root)
        path, manifest = _manifest(root)
        manifest["sourceCommit"] = "z" * 40
        path.write_text(json.dumps(manifest), encoding="utf-8")
        result = audit_app(app, "0.8.233", "z" * 40)
        assert "source_commit" in result


def test_rejects_python_version_mutation_alone() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = make_app_fixture(root)
        path, manifest = _manifest(root)
        manifest["pythonVersion"] = "3.11.150"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        assert "python_version" in _audit(app)


def test_rejects_oversized_metadata_and_streams_large_resource_hashes() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = make_app_fixture(root)
        manifest_path = root / "build-manifest.json"
        manifest_path.write_bytes(manifest_path.read_bytes() + b" " * (1024 * 1024))
        assert "build_manifest" in _audit(app)

        app = make_app_fixture(root / "resource")
        resource = app / "Contents" / "Resources" / "tomos" / "large.txt"
        resource.write_bytes(b"x" * (2 * 1024 * 1024))
        path, manifest = _manifest(root / "resource")
        manifest["files"].append("large.txt")
        manifest["resourceHashes"]["large.txt"] = hashlib.sha256(resource.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest), encoding="utf-8")
        assert _audit(app) == []


def main() -> None:
    test_accepts_matching_release_candidate()
    test_signed_audit_accepts_runtime_macho_changes_but_rejects_non_macho_mutation()
    test_signed_audit_rejects_archive_non_macho_replaced_by_arm64_macho()
    test_signed_production_audit_accepts_current_signed_app()
    test_signed_production_audit_accepts_current_signed_app_under_private_umask()
    test_signed_audit_rejects_unapproved_runtime_symlink()
    test_signed_audit_rejects_stale_source_commit()
    test_rejects_wrong_bundle_identifier()
    test_rejects_incomplete_and_non_executable_macho()
    test_rejects_fat_count_over_limit_before_tool_parse()
    test_rejects_invalid_load_command_id()
    test_rejects_dylib_even_when_path_contains_execute()
    test_rejects_fat_binary_with_later_invalid_entry()
    test_rejects_external_symlinks_for_metadata_and_executables()
    test_rejects_any_internal_bundle_symlink()
    test_rejects_private_mutable_and_model_payloads()
    test_allows_only_standard_library_token_name()
    test_rejects_runtime_tree_mutation_and_allows_verified_runtime()
    test_accepts_runtime_with_ditto_normalized_symlinks()
    test_rejects_new_runtime_symlink_at_artifact_regular_file()
    test_audit_reports_new_runtime_symlink_at_artifact_regular_file()
    test_accepts_existing_candidate_runtime()
    test_rejects_access_token_name()
    test_rejects_openai_api_key_name()
    test_rejects_private_key_name()
    test_rejects_client_secret_name()
    test_rejects_refresh_token_name()
    test_rejects_credentials_name()
    test_rejects_secrets_name()
    test_rejects_compact_api_key_file_name()
    test_rejects_secret_terms_in_directory_components()
    test_allows_secret_and_token_partial_words()
    test_rejects_actual_allowlist_extra_and_hash_tampering()
    test_rejects_manifest_path_traversal_pkg_id_and_types()
    test_rejects_read_failure_during_tree_audit()
    test_rejects_manifest_source_commit_and_exact_python_version()
    test_rejects_python_version_mutation_alone()
    test_rejects_oversized_metadata_and_streams_large_resource_hashes()
    print("macOS Tauri release audit tests passed")


if __name__ == "__main__":
    main()
