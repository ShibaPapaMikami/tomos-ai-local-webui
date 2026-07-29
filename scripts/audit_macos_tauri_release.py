#!/usr/bin/env python3
"""Static safety checks for a TOMOS macOS release-candidate app bundle."""
from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import stat
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from macos_python_runtime import (
    ARTIFACT,
    normalized_runtime_tree_entries,
    runtime_tree_entries,
    stage_runtime,
    verify_artifact_file,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BUNDLE_ID = "com.shibapapastudio.tomos-ai"
EXPECTED_PKG_ID = "jp.local.gemma4-12b"
EXPECTED_MINIMUM_MACOS = "13.0"
EXPECTED_PYTHON_VERSION = "3.11.15"
MAX_METADATA_BYTES = 1024 * 1024
MAX_FAT_ARCHITECTURES = 128
MACHO_TOOL_TIMEOUT_SECONDS = 5
_FORBIDDEN_PARTS = frozenset(
    {
        ".git",
        ".gemma4-data",
        "models",
        "model",
        "logs",
        "log",
    }
)
_SECRET_SUFFIXES = (".key", ".p12", ".pem", ".pfx")
_MODEL_SUFFIXES = (".ckpt", ".gguf", ".mlmodel", ".model", ".onnx", ".pt", ".pth", ".safetensors", ".tflite")
_DATABASE_NAME = re.compile(r"\.(?:db|sqlite|sqlite3)(?:-(?:shm|wal))?$", re.IGNORECASE)
_LOG_NAME = re.compile(r"\.log(?:\.\d+)?(?:\.(?:gz|zip))?$", re.IGNORECASE)
_NAME_TOKEN = re.compile(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+")


def _add(errors: list[str], value: str) -> None:
    if value not in errors:
        errors.append(value)


def _open_regular(path: Path) -> int | None:
    try:
        initial = path.lstat()
    except OSError:
        return None
    if stat.S_ISLNK(initial.st_mode) or not stat.S_ISREG(initial.st_mode):
        return None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            return None
    except OSError:
        os.close(descriptor)
        return None
    return descriptor


def _read_regular_metadata(path: Path) -> bytes | None:
    descriptor = _open_regular(path)
    if descriptor is None:
        return None
    try:
        if os.fstat(descriptor).st_size > MAX_METADATA_BYTES:
            return None
        with os.fdopen(descriptor, "rb", closefd=True) as source:
            descriptor = -1
            data = source.read(MAX_METADATA_BYTES + 1)
        return data if len(data) <= MAX_METADATA_BYTES else None
    except OSError:
        return None
    finally:
        if descriptor != -1:
            os.close(descriptor)


def _read_json_object(path: Path) -> dict[str, Any] | None:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    raw = _read_regular_metadata(path)
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _walk_regular_tree(root: Path, excluded_root: Path | None = None) -> tuple[list[Path], str | None]:
    try:
        root_status = root.lstat()
    except OSError:
        return [], "read_error"
    if stat.S_ISLNK(root_status.st_mode):
        return [], "symlink"
    if not stat.S_ISDIR(root_status.st_mode):
        return [], "read_error"

    files: list[Path] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as scanner:
                children = list(scanner)
        except OSError:
            return files, "read_error"
        for child in children:
            path = Path(child.path)
            try:
                child_status = child.stat(follow_symlinks=False)
            except OSError:
                return files, "read_error"
            if stat.S_ISLNK(child_status.st_mode):
                return files, "symlink"
            if excluded_root is not None and path == excluded_root:
                if not stat.S_ISDIR(child_status.st_mode):
                    return files, "read_error"
                continue
            if stat.S_ISDIR(child_status.st_mode):
                pending.append(path)
            elif stat.S_ISREG(child_status.st_mode):
                files.append(path)
            else:
                return files, "read_error"
    return files, None


def _fat_architecture_count_is_bounded(path: Path) -> bool:
    descriptor = _open_regular(path)
    if descriptor is None:
        return False
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as source:
            descriptor = -1
            header = source.read(8)
        if len(header) != 8:
            return False
        if header[:4] not in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
            return True
        return struct.unpack(">I", header[4:])[0] <= MAX_FAT_ARCHITECTURES
    except OSError:
        return False
    finally:
        if descriptor != -1:
            os.close(descriptor)


def _run_macho_tool(arguments: list[str]) -> str | None:
    try:
        result = subprocess.run(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=MACHO_TOOL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _is_arm64_macho(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    executable_bits = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or not metadata.st_mode & executable_bits
        or not _fat_architecture_count_is_bounded(path)
    ):
        return False
    absolute_path = os.path.abspath(path)
    architectures = _run_macho_tool(["/usr/bin/lipo", "-archs", absolute_path])
    if architectures is None or architectures.strip() != "arm64":
        return False
    header = _run_macho_tool(["/usr/bin/otool", "-hv", absolute_path])
    load_commands = _run_macho_tool(["/usr/bin/otool", "-l", absolute_path])
    header_rows = [line.split() for line in header.splitlines()] if header is not None else []
    valid_header = any(
        len(row) >= 5
        and row[0] == "MH_MAGIC_64"
        and row[1] == "ARM64"
        and row[4] == "EXECUTE"
        for row in header_rows
    )
    return (
        valid_header
        and load_commands is not None
        and "UNKNOWN LOAD COMMAND" not in load_commands.upper()
    )


def _file_sha256(path: Path) -> str | None:
    descriptor = _open_regular(path)
    if descriptor is None:
        return None
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as source:
            descriptor = -1
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
    finally:
        if descriptor != -1:
            os.close(descriptor)


def _resource_allowlist_matches(root: Path, manifest: dict[str, Any]) -> bool:
    files = manifest.get("files")
    hashes = manifest.get("resourceHashes")
    if not isinstance(files, list) or not isinstance(hashes, dict):
        return False
    expected: set[str] = set()
    for value in files:
        if not isinstance(value, str):
            return False
        relative = Path(value)
        if not value or relative.is_absolute() or ".." in relative.parts:
            return False
        normalized = relative.as_posix()
        if normalized in expected:
            return False
        expected.add(normalized)
    actual_files, problem = _walk_regular_tree(root)
    if problem is not None:
        return False
    actual = {path.relative_to(root).as_posix() for path in actual_files}
    if actual != expected or set(hashes) != expected:
        return False
    for relative in expected:
        digest = hashes.get(relative)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            return False
        if _file_sha256(root / relative) != digest:
            return False
    return True


def _python_runtime_verification(python_root: Path) -> tuple[bool, bool]:
    """Return (matches artifact, has unapproved candidate symlink)."""
    try:
        metadata = python_root.lstat()
    except OSError:
        return False, False
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        return False, stat.S_ISLNK(metadata.st_mode)
    archive = ROOT / "build" / "cache" / ARTIFACT.name
    try:
        with tempfile.TemporaryDirectory() as temporary:
            expected_destination = Path(temporary) / "python"
            with archive.open("rb") as source:
                verify_artifact_file(source, ARTIFACT)
                expected_root = stage_runtime(source, expected_destination)
            expected_entries = runtime_tree_entries(expected_root)
            candidate_entries = runtime_tree_entries(python_root)
            approved_symlinks = {
                name: target
                for name, (kind, _mode, target) in expected_entries.items()
                if kind == "symlink"
            }
            has_unapproved_symlink = any(
                kind == "symlink" and approved_symlinks.get(name) != target
                for name, (kind, _mode, target) in candidate_entries.items()
            )
            matches = normalized_runtime_tree_entries(
                python_root, candidate_entries, approved_symlinks
            ) == normalized_runtime_tree_entries(
                expected_root, expected_entries, approved_symlinks
            )
            return matches, has_unapproved_symlink
    except (OSError, ValueError):
        return False, False


def _python_runtime_matches_verified_artifact(python_root: Path) -> bool:
    return _python_runtime_verification(python_root)[0]


def _is_forbidden_name(relative: Path) -> bool:
    parts = {part.casefold() for part in relative.parts}
    name = relative.name.casefold()
    tokens = [
        token.casefold()
        for path_component in relative.parts
        for component in re.split(r"[._-]+", path_component)
        for token in _NAME_TOKEN.findall(component)
    ]
    compact_tokens = {
        component.casefold()
        for path_component in relative.parts
        for component in re.split(r"[._-]+", path_component)
        if component
    }
    secret_tokens = {"credential", "credentials", "secret", "secrets", "token", "tokens"}
    secret_pairs = {
        ("access", "token"),
        ("api", "key"),
        ("client", "secret"),
        ("private", "key"),
        ("refresh", "token"),
    }
    compact_secret_tokens = {
        "accesstoken",
        "apikey",
        "clientsecret",
        "privatekey",
        "refreshtoken",
    }
    token_pairs = set(zip(tokens, tokens[1:]))
    return bool(
        ".git" in parts
        or name.startswith(".env")
        or parts & _FORBIDDEN_PARTS
        or name.endswith(_SECRET_SUFFIXES)
        or name.endswith(_MODEL_SUFFIXES)
        or _DATABASE_NAME.search(name)
        or _LOG_NAME.search(name)
        or secret_tokens.intersection(tokens)
        or secret_pairs.intersection(token_pairs)
        or compact_secret_tokens.intersection(compact_tokens)
    )


def _scan_bundle_payload(app_path: Path, python_root: Path) -> tuple[bool, str | None]:
    files, problem = _walk_regular_tree(app_path, excluded_root=python_root)
    if problem is not None:
        return False, problem
    return any(_is_forbidden_name(path.relative_to(app_path)) for path in files), None


def _python_version_matches(manifest: dict[str, Any]) -> bool:
    if manifest.get("pythonVersion") != EXPECTED_PYTHON_VERSION:
        return False
    artifact = manifest.get("pythonArtifact")
    name = artifact.get("name") if isinstance(artifact, dict) else artifact
    return isinstance(name, str) and bool(re.fullmatch(r"cpython-3\.11\.15(?:[+-].+)?", name))


def audit_app(app_path: Path, expected_version: str, expected_commit: str) -> list[str]:
    """Return stable error categories for an unsigned TOMOS app-bundle audit.

    This audit reads bounded metadata and file names for policy checks; it never
    prints payload contents and it does not sign, notarize, install, or modify.
    """
    app_path = Path(app_path)
    errors: list[str] = []
    try:
        app_status = app_path.lstat()
    except OSError:
        return ["app_bundle"]
    if not stat.S_ISDIR(app_status.st_mode) or stat.S_ISLNK(app_status.st_mode):
        return ["app_bundle"]

    contents = app_path / "Contents"
    python = contents / "Resources" / "python"
    forbidden_payload, tree_problem = _scan_bundle_payload(app_path, python)
    if tree_problem == "symlink":
        _add(errors, "bundle_symlink")
    elif tree_problem is not None:
        _add(errors, "bundle_read_error")
    if forbidden_payload:
        _add(errors, "forbidden_payload")
    python_runtime_matches, python_has_unapproved_symlink = _python_runtime_verification(python)
    if python_has_unapproved_symlink:
        _add(errors, "bundle_symlink")
    if not python_runtime_matches:
        _add(errors, "python_runtime")

    raw_info = _read_regular_metadata(contents / "Info.plist")
    try:
        info = plistlib.loads(raw_info) if raw_info is not None else None
    except (plistlib.InvalidFileException, ValueError):
        info = None
    if not isinstance(info, dict):
        _add(errors, "info_plist")
    else:
        if info.get("CFBundleIdentifier") != EXPECTED_BUNDLE_ID:
            _add(errors, "bundle_identifier")
        if info.get("CFBundleShortVersionString") != expected_version:
            _add(errors, "app_version")
        if info.get("LSMinimumSystemVersion") != EXPECTED_MINIMUM_MACOS:
            _add(errors, "minimum_macos")

    executable = contents / "MacOS" / "tomos-desktop"
    python_executable = python / "bin" / "python3"
    verified_python_executable = python_executable.resolve() if python_runtime_matches else python_executable
    if not _is_arm64_macho(executable) or not _is_arm64_macho(verified_python_executable):
        _add(errors, "architecture")

    manifest = _read_json_object(app_path.parent / "build-manifest.json")
    if manifest is None:
        _add(errors, "build_manifest")
    else:
        if manifest.get("appVersion") != expected_version:
            _add(errors, "manifest_version")
        if manifest.get("architecture") != "arm64":
            _add(errors, "manifest_architecture")
        if manifest.get("bundleId") != EXPECTED_BUNDLE_ID:
            _add(errors, "manifest_bundle_identifier")
        if manifest.get("pkgIdentifier") != EXPECTED_PKG_ID:
            _add(errors, "pkg_identifier")
        source_commit = manifest.get("sourceCommit")
        if (
            source_commit != expected_commit
            or not isinstance(source_commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}", source_commit)
        ):
            _add(errors, "source_commit")
        if not _python_version_matches(manifest):
            _add(errors, "python_version")
        if not _resource_allowlist_matches(contents / "Resources" / "tomos", manifest):
            _add(errors, "resource_allowlist")
    return errors
