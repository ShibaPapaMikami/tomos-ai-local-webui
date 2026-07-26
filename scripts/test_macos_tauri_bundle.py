#!/usr/bin/env python3
"""Static contract checks for the TOMOS macOS portable app bundle."""
from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from macos_python_runtime import ARTIFACT, stage_runtime, verify_artifact_file


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.8.233"
EXPECTED_BUNDLE_ID = "com.shibapapastudio.tomos-ai"
FORBIDDEN_PARTS = frozenset(
    {
        ".git",
        "__pycache__",
        "cache",
        "data",
        "dist",
        "logs",
        "models",
        "private-content",
        "secrets",
        "credentials",
        ".gemma4-data",
    }
)
FORBIDDEN_SUFFIXES = (".db", ".key", ".log", ".p12", ".pem", ".pfx", ".sqlite", ".sqlite3")


def test_tauri_bundle_contains_portable_resources() -> None:
    config = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    resources = config["bundle"]["resources"]
    assert resources["../build/macos-runtime/python/"] == "python/"
    assert resources["../build/macos-runtime/tomos/"] == "tomos/"
    assert config["bundle"]["targets"] == ["app"]
    assert config["bundle"]["macOS"]["minimumSystemVersion"] == "13.0"
    assert config["version"] == EXPECTED_VERSION
    assert config["identifier"] == EXPECTED_BUNDLE_ID


def test_source_info_plist_contains_microphone_usage_reason() -> None:
    with (ROOT / "src-tauri" / "Info.plist").open("rb") as source:
        info = plistlib.load(source)
    assert info["NSMicrophoneUsageDescription"] == "音声入力と文字起こしのためにマイクを使用します。"


def _require_arm64(path: Path) -> None:
    result = subprocess.run(["file", str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "arm64" in result.stdout, result.stdout


def _is_forbidden(relative: Path) -> bool:
    parts = {part.casefold() for part in relative.parts}
    name = relative.name.casefold()
    if parts & {".git", ".gemma4-data", "private-content", "secrets", "credentials"}:
        return True
    # Python's standard library and pip legitimately contain names such as
    # ``models`` and immutable ``__pycache__`` files. TOMOS resources must not.
    is_tomos_resource = relative.parts[:3] == ("Contents", "Resources", "tomos")
    return is_tomos_resource and (
        bool(parts & FORBIDDEN_PARTS)
        or name.endswith(FORBIDDEN_SUFFIXES)
        or name.startswith(".env")
    )


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    assert value and not path.is_absolute() and ".." not in path.parts, f"不正なmanifest path: {value}"
    return path


def _load_build_manifest(path: Path) -> dict[str, object]:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AssertionError(f"build manifestの重複keyを拒否しました: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    assert isinstance(value, dict), "build manifest rootがobjectではありません"
    return value


def _tree_entries(root: Path, label: str) -> dict[str, tuple[str, int, str]]:
    try:
        root_stat = root.lstat()
    except FileNotFoundError as exc:
        raise AssertionError(f"{label}がありません: {root}") from exc
    assert stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode), f"{label} rootが不正です"

    entries: dict[str, tuple[str, int, str]] = {}

    def visit(directory: Path, relative: Path) -> None:
        with os.scandir(directory) as children:
            for child in children:
                child_path = Path(child.path)
                child_relative = relative / child.name
                child_stat = child_path.lstat()
                mode = stat.S_IMODE(child_stat.st_mode)
                key = child_relative.as_posix()
                if stat.S_ISLNK(child_stat.st_mode):
                    # Tauri/ditto can normalize symlink mode bits. Target and
                    # type are the integrity-relevant values for a symlink.
                    entries[key] = ("symlink", 0, os.readlink(child_path))
                elif stat.S_ISDIR(child_stat.st_mode):
                    entries[key] = ("directory", mode, "")
                    visit(child_path, child_relative)
                elif stat.S_ISREG(child_stat.st_mode):
                    digest = hashlib.sha256(child_path.read_bytes()).hexdigest()
                    entries[key] = ("file", mode, digest)
                else:
                    raise AssertionError(f"{label}に通常file以外があります: {key}")

    visit(root, Path())
    return entries


def _assert_tomos_files_match_manifest(
    tomos: Path, manifest_files: object, resource_hashes: object
) -> None:
    assert isinstance(manifest_files, list), "build manifestのfilesがlistではありません"
    expected = [_safe_relative_path(value).as_posix() for value in manifest_files if isinstance(value, str)]
    assert len(expected) == len(manifest_files), "build manifestのfilesに不正な値があります"
    assert len(expected) == len(set(expected)), "build manifestのfilesに重複があります"
    assert isinstance(resource_hashes, dict), "build manifestのresourceHashesがmapではありません"
    normalized_hashes: dict[str, str] = {}
    for name, digest in resource_hashes.items():
        assert isinstance(name, str), "build manifestのresource hash pathが文字列ではありません"
        safe_name = _safe_relative_path(name).as_posix()
        assert isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), (
            f"build manifestのresource hashが不正です: {name}"
        )
        normalized_hashes[safe_name] = digest
    assert set(normalized_hashes) == set(expected), "build manifestのresource hash pathがfilesと一致しません"
    actual_entries = _tree_entries(tomos, "TOMOS resource")
    actual_hashes: dict[str, str] = {}
    for name, (kind, _mode, value) in actual_entries.items():
        assert kind != "symlink", f"TOMOS resource symlinkを拒否しました: {name}"
        if kind == "file":
            actual_hashes[name] = value
    assert set(actual_hashes) == set(expected), (
        "TOMOS resource allowlistがmanifestと一致しません: "
        f"extra={sorted(set(actual_hashes) - set(expected))}, missing={sorted(set(expected) - set(actual_hashes))}"
    )
    assert actual_hashes == normalized_hashes, "TOMOS resource hashがmanifestと一致しません"


def _require_real_directory(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label}がありません: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} symlinkは許可されません: {path}")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label}はdirectoryではありません: {path}")


def _create_real_child(parent: Path, name: str, label: str) -> Path:
    path = parent / name
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        os.mkdir(path)
    else:
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"{label} symlinkは許可されません: {path}")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{label}はdirectoryではありません: {path}")
    _require_real_directory(path, label)
    return path


def _reject_existing_leaf(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} symlinkは許可されません: {path}")
    raise ValueError(f"{label}は上書きしません: {path}")


def _validate_candidate_destination(root: Path) -> Path:
    _require_real_directory(root, "repository root")
    dist = _create_real_child(root, "dist", "dist")
    candidate = _create_real_child(dist, "candidate", "candidate directory")
    _reject_existing_leaf(candidate / "TOMOS AI.app", "candidate app")
    _reject_existing_leaf(candidate / "build-manifest.json", "candidate manifest")
    return candidate


def _assert_python_runtime_matches_verified_archive(python_root: Path) -> None:
    archive = ROOT / "build" / "cache" / ARTIFACT.name
    assert archive.is_file(), f"検証済みPython artifact cacheがありません: {archive}"
    with tempfile.TemporaryDirectory() as temporary:
        expected_destination = Path(temporary) / "python"
        with archive.open("rb") as source:
            verify_artifact_file(source, ARTIFACT)
            expected_root = stage_runtime(source, expected_destination)
        try:
            actual = _tree_entries(python_root, "bundle Python")
            expected = _tree_entries(expected_root, "verified Python")
            expected_root_resolved = expected_root.resolve(strict=True)
            for name, (kind, _mode, target) in tuple(expected.items()):
                if kind != "symlink":
                    continue
                target_path = (expected_root / name).parent.joinpath(target).resolve(strict=True)
                try:
                    target_path.relative_to(expected_root_resolved)
                except ValueError as exc:
                    raise AssertionError(f"verified Python symlinkがroot外です: {name}") from exc
                target_stat = target_path.stat()
                assert stat.S_ISREG(target_stat.st_mode), f"verified Python symlink targetがfileではありません: {name}"
                expected[name] = (
                    "file",
                    stat.S_IMODE(target_stat.st_mode),
                    hashlib.sha256(target_path.read_bytes()).hexdigest(),
                )
            assert actual == expected, (
                "bundle Pythonが検証済みarchive由来のruntime treeと一致しません: "
                f"extra={sorted(actual.keys() - expected.keys())[:5]}, "
                f"missing={sorted(expected.keys() - actual.keys())[:5]}, "
                f"changed={sorted(name for name in actual.keys() & expected.keys() if actual[name] != expected[name])[:5]}"
            )
        finally:
            shutil.rmtree(expected_root, ignore_errors=True)


def test_manifest_file_list_rejects_extra_file_and_symlink() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "tomos"
        root.mkdir()
        (root / "server.py").write_text("server", encoding="utf-8")
        server_hash = hashlib.sha256(b"server").hexdigest()
        _assert_tomos_files_match_manifest(root, ["server.py"], {"server.py": server_hash})

        (root / "customer-notes.txt").write_text("private", encoding="utf-8")
        try:
            _assert_tomos_files_match_manifest(root, ["server.py"], {"server.py": server_hash})
        except AssertionError as exc:
            assert "allowlist" in str(exc)
        else:
            raise AssertionError("allowlist外fileが許可されました")

        (root / "customer-notes.txt").unlink()
        (root / "linked.py").symlink_to("server.py")
        try:
            _assert_tomos_files_match_manifest(root, ["server.py"], {"server.py": server_hash})
        except AssertionError as exc:
            assert "symlink" in str(exc)
        else:
            raise AssertionError("TOMOS resource symlinkが許可されました")


def test_manifest_resource_hashes_reject_invalid_and_mismatched_values() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "tomos"
        root.mkdir()
        (root / "server.py").write_text("server", encoding="utf-8")
        valid_hash = hashlib.sha256(b"server").hexdigest()

        _assert_tomos_files_match_manifest(root, ["server.py"], {"server.py": valid_hash})
        for hashes in (
            {"server.py": "not-a-hash"},
            {"../server.py": valid_hash},
            {"server.py": hashlib.sha256(b"different").hexdigest()},
        ):
            try:
                _assert_tomos_files_match_manifest(root, ["server.py"], hashes)
            except AssertionError as exc:
                assert "hash" in str(exc).lower() or "manifest" in str(exc).lower(), str(exc)
            else:
                raise AssertionError("不正なresource hashが許可されました")


def test_manifest_json_rejects_duplicate_hash_keys() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        manifest_path = Path(temporary) / "build-manifest.json"
        manifest_path.write_text(
            '{"files":["server.py"],"resourceHashes":{"server.py":"a",'
            '"server.py":"b"}}',
            encoding="utf-8",
        )
        try:
            _load_build_manifest(manifest_path)
        except AssertionError as exc:
            assert "重複" in str(exc)
        else:
            raise AssertionError("重複したresource hash keyが許可されました")


def test_candidate_destination_rejects_parent_and_dangling_leaf_symlinks() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()
        external = Path(temporary) / "external"
        external.mkdir()
        (root / "dist").symlink_to(external, target_is_directory=True)
        try:
            _validate_candidate_destination(root)
        except ValueError as exc:
            assert "symlink" in str(exc)
        else:
            raise AssertionError("candidate parent symlinkが許可されました")

        (root / "dist").unlink()
        dist = root / "dist"
        dist.mkdir()
        candidate = dist / "candidate"
        candidate.symlink_to(external, target_is_directory=True)
        try:
            _validate_candidate_destination(root)
        except ValueError as exc:
            assert "symlink" in str(exc)
        else:
            raise AssertionError("candidate directory symlinkが許可されました")

        candidate.unlink()
        candidate.mkdir()
        (candidate / "TOMOS AI.app").symlink_to(external / "missing-app")
        try:
            _validate_candidate_destination(root)
        except ValueError as exc:
            assert "symlink" in str(exc)
        else:
            raise AssertionError("dangling candidate app symlinkが許可されました")

        (candidate / "TOMOS AI.app").unlink()
        (candidate / "build-manifest.json").symlink_to(external / "missing-manifest")
        try:
            _validate_candidate_destination(root)
        except ValueError as exc:
            assert "symlink" in str(exc)
        else:
            raise AssertionError("dangling candidate manifest symlinkが許可されました")


def test_candidate_bundle(candidate: Path) -> None:
    contents = candidate / "Contents"
    executable = contents / "MacOS" / "tomos-desktop"
    resources = contents / "Resources"
    python = resources / "python" / "bin" / "python3"
    tomos = resources / "tomos"
    manifest_path = candidate.parent / "build-manifest.json"

    assert candidate.is_dir(), f"candidate appがありません: {candidate}"
    assert executable.is_file(), f"desktop executableがありません: {executable}"
    assert python.is_file(), f"同梱Pythonがありません: {python}"
    assert (tomos / "server.py").is_file(), "server.pyがありません"
    assert (tomos / "web" / "index.html").is_file(), "web/index.htmlがありません"
    _require_arm64(executable)
    _require_arm64(python.resolve())

    with (contents / "Info.plist").open("rb") as source:
        info = plistlib.load(source)
    assert info["CFBundleIdentifier"] == EXPECTED_BUNDLE_ID
    assert info["CFBundleShortVersionString"] == EXPECTED_VERSION
    assert info["LSMinimumSystemVersion"] == "13.0"
    assert info["NSMicrophoneUsageDescription"] == "音声入力と文字起こしのためにマイクを使用します。"

    assert manifest_path.is_file(), f"build manifestがありません: {manifest_path}"
    manifest = _load_build_manifest(manifest_path)
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert manifest["sourceCommit"] == expected_commit
    assert manifest["appVersion"] == EXPECTED_VERSION
    assert manifest["architecture"] == "arm64"
    assert manifest["bundleId"] == EXPECTED_BUNDLE_ID
    _assert_tomos_files_match_manifest(tomos, manifest["files"], manifest["resourceHashes"])
    _assert_python_runtime_matches_verified_archive(resources / "python")

    version = subprocess.run([str(python), "--version"], capture_output=True, text=True, check=False)
    assert version.returncode == 0, version.stderr
    assert version.stdout.strip().startswith("Python 3.11."), version.stdout

    for path in candidate.rglob("*"):
        relative = path.relative_to(candidate)
        assert not _is_forbidden(relative), f"禁止fileがbundleにあります: {relative}"


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--prepare-candidate-dir":
        print(_validate_candidate_destination(Path(sys.argv[2])))
        return
    if len(sys.argv) > 2:
        raise SystemExit("usage: test_macos_tauri_bundle.py [candidate-app]")
    test_tauri_bundle_contains_portable_resources()
    test_source_info_plist_contains_microphone_usage_reason()
    test_manifest_file_list_rejects_extra_file_and_symlink()
    test_manifest_resource_hashes_reject_invalid_and_mismatched_values()
    test_manifest_json_rejects_duplicate_hash_keys()
    test_candidate_destination_rejects_parent_and_dangling_leaf_symlinks()
    if len(sys.argv) > 1:
        test_candidate_bundle(Path(sys.argv[1]).resolve())
    print("macOS Tauri bundle tests passed")


if __name__ == "__main__":
    main()
