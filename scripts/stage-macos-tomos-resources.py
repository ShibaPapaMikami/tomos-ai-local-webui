#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


# This is deliberately a file-by-file allowlist. Do not replace it with a
# repository-wide copy: TOMOS stores models and user data beside the app.
RESOURCE_FILES: tuple[str, ...] = (
    "agent_reach_adapter.py",
    "app_paths.py",
    "context_core.py",
    "contract_ledger.py",
    "knowledge_layer.py",
    "migration_manager.py",
    "packages/__init__.py",
    "packages/local_context_core/__init__.py",
    "pdf_reader.py",
    "sarashina_ocr_runner.py",
    "scripts/asr_nemotron_runner.py",
    "scripts/asr_nemotron_worker.py",
    "scripts/sarashina_ocr_page.py",
    "scripts/setup-asr-nemotron-mac.sh",
    "scripts/setup-ocr-mac.sh",
    "search_tools.py",
    "server.py",
    "study_pack_manager.py",
    "tts_engine.py",
    "web/app.js",
    "web/apple-touch-icon-precomposed.png",
    "web/apple-touch-icon.png",
    "web/asr.js",
    "web/attachments.js",
    "web/character-core-adapter.js",
    "web/character.js",
    "web/composer.js",
    "web/desktop-starting.html",
    "web/desktop-starting.js",
    "web/docs/ocr-setup.en.md",
    "web/docs/ocr-setup.ja.md",
    "web/i18n.js",
    "web/icons/icon-192.png",
    "web/icons/icon-512.png",
    "web/icons/icon.svg",
    "web/image-tools.js",
    "web/index.html",
    "web/local-storage-transfer.js",
    "web/local-tools.js",
    "web/management.js",
    "web/manifest.webmanifest",
    "web/messages.js",
    "web/mobile-check.html",
    "web/mobile-standalone.js",
    "web/mobile.html",
    "web/models.js",
    "web/offline.html",
    "web/person-name-fortune.js",
    "web/person-relationship.js",
    "web/pwa.js",
    "web/reset-cache.html",
    "web/router.js",
    "web/search.js",
    "web/settings.js",
    "web/sidebar.js",
    "web/styles.css",
    "web/sw.js",
    "web/tomos-character-core.js",
    "web/training.js",
    "web/translation.js",
    "web/tts.js",
    "web/utils.js",
    "web/weather.js",
    "web/workspace.js",
)

FORBIDDEN_PARTS = frozenset({
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
})
FORBIDDEN_SUFFIXES = (".db", ".key", ".log", ".p12", ".pem", ".pfx", ".sqlite", ".sqlite3")


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "git command failed"
        raise ValueError(f"git情報を取得できません: {message}")
    return result.stdout.strip()


def require_clean_release_worktree(root: Path) -> None:
    if _run_git(root, "status", "--porcelain"):
        raise ValueError("release staging requires a clean git worktree (dirty worktree)")


def _is_forbidden(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or path.name.casefold() in {".env", "id_rsa"}:
        return True
    for part in path.parts:
        lowered = part.casefold()
        if lowered in FORBIDDEN_PARTS or lowered.startswith(".venv"):
            return True
        if lowered.startswith(".env") or "secret" in lowered or "credential" in lowered:
            return True
    return path.name.casefold().endswith(FORBIDDEN_SUFFIXES)


def _validate_resource_path(relative_path: str) -> PurePosixPath:
    path = PurePosixPath(relative_path)
    if not relative_path or str(path) != relative_path or _is_forbidden(relative_path):
        raise ValueError(f"forbidden resource path: {relative_path}")
    return path


def _load_python_artifact(root: Path) -> dict[str, Any]:
    module_path = root / "scripts" / "macos_python_runtime.py"
    spec = importlib.util.spec_from_file_location("tomos_macos_python_runtime", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("macOS Python artifact definitionを読み込めません")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        artifact = module.ARTIFACT
        return {
            "name": artifact.name,
            "url": artifact.url,
            "sha256": artifact.sha256,
            "size": artifact.size,
        }
    finally:
        sys.modules.pop(spec.name, None)


def _read_app_version(root: Path) -> str:
    text = (root / "server.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION = os\.environ\.get\("GEMMA_APP_VERSION", "([^"]+)"\)', text)
    if not match:
        raise ValueError("server.pyからAPP_VERSIONを読み取れません")
    return match.group(1)


def _read_bundle_metadata(root: Path) -> tuple[str, str]:
    config = json.loads((root / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    bundle_id = str(config.get("identifier") or "").strip()
    if not bundle_id:
        raise ValueError("Tauri Bundle IDを読み取れません")

    package_script = (root / "scripts" / "make-mac-pkg.sh").read_text(encoding="utf-8")
    match = re.search(r'--identifier\s+"([^"]+)"', package_script)
    if not match:
        raise ValueError("PKG identifierを読み取れません")
    return bundle_id, match.group(1)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_manifest(root: Path, files: list[str], resource_hashes: dict[str, str]) -> dict[str, Any]:
    bundle_id, pkg_identifier = _read_bundle_metadata(root)
    return {
        "appVersion": _read_app_version(root),
        "architecture": "arm64",
        "bundleId": bundle_id,
        "pkgIdentifier": pkg_identifier,
        "pythonArtifact": _load_python_artifact(root),
        "sourceCommit": _run_git(root, "rev-parse", "HEAD"),
        "files": files,
        "resourceHashes": resource_hashes,
        "hostArchitecture": platform.machine(),
    }


def _lstat(path: Path, label: str) -> os.stat_result:
    try:
        return path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label}が見つかりません: {path}") from exc


def _require_safe_source_root(root: Path) -> None:
    root_stat = _lstat(root, "source root")
    if stat.S_ISLNK(root_stat.st_mode):
        raise ValueError(f"source root symlinkは許可されません: {root}")
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ValueError(f"source rootはdirectoryではありません: {root}")


def _require_safe_source_file(root: Path, relative_name: str) -> Path:
    current = root
    parts = _validate_resource_path(relative_name).parts
    for index, part in enumerate(parts):
        current = current / part
        source_stat = _lstat(current, "allowlisted resource")
        if stat.S_ISLNK(source_stat.st_mode):
            raise ValueError(f"allowlisted resourceのsymlinkは許可されません: {relative_name}")
        is_leaf = index == len(parts) - 1
        if is_leaf and not stat.S_ISREG(source_stat.st_mode):
            raise ValueError(f"allowlisted resourceは通常fileではありません: {relative_name}")
        if not is_leaf and not stat.S_ISDIR(source_stat.st_mode):
            raise ValueError(f"allowlisted resourceのparentはdirectoryではありません: {relative_name}")
    return current


def _require_unused_publish_target(path: Path, label: str) -> None:
    try:
        target_stat = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISDIR(target_stat.st_mode):
        kind = "directory"
    elif stat.S_ISLNK(target_stat.st_mode):
        kind = "symlink"
    else:
        kind = "file"
    raise ValueError(f"{label} publish target collision ({kind}): {path}")


def stage_resources(root: Path, destination: Path) -> dict[str, Any]:
    root = Path(os.path.abspath(root))
    destination = Path(os.path.abspath(destination))
    _require_safe_source_root(root)
    manifest_target = destination.parent / "build-manifest.json"
    _require_unused_publish_target(destination, "resource tree")
    _require_unused_publish_target(manifest_target, "build manifest")

    validated_files = [str(_validate_resource_path(item)) for item in RESOURCE_FILES]
    if len(validated_files) != len(set(validated_files)):
        raise ValueError("RESOURCE_FILESに重複があります")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage.", dir=destination.parent))
    staging = staging_root / destination.name
    staging.mkdir()
    manifest_staging = staging_root / "build-manifest.json"
    tree_published = False
    try:
        for relative_name in validated_files:
            source = _require_safe_source_file(root, relative_name)
            target = staging / relative_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        files = sorted(path.relative_to(staging).as_posix() for path in staging.rglob("*") if path.is_file())
        if files != sorted(validated_files) or any(_is_forbidden(name) for name in files):
            raise ValueError("staging resource allowlist検証に失敗しました")
        resource_hashes = {name: _sha256_file(staging / name) for name in files}
        if set(resource_hashes) != set(files) or any(
            not re.fullmatch(r"[0-9a-f]{64}", digest) for digest in resource_hashes.values()
        ):
            raise ValueError("staging resource hash検証に失敗しました")
        manifest = _build_manifest(root, files, resource_hashes)
        manifest_staging.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(staging, destination)
        tree_published = True
        try:
            os.replace(manifest_staging, manifest_target)
        except Exception as publish_error:
            try:
                shutil.rmtree(destination)
            except Exception as rollback_error:
                raise RuntimeError(
                    f"build manifest publish failed and resource tree rollback failed: {rollback_error}"
                ) from publish_error
            raise
        return {"files": files, "manifest": manifest}
    finally:
        if not tree_published:
            shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(staging_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage the allowlisted TOMOS resources for the macOS runtime.")
    parser.add_argument("--output", type=Path, default=Path("build/macos-runtime/tomos"))
    parser.add_argument("--release", action="store_true", help="Reject a dirty worktree before staging.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.release:
        require_clean_release_worktree(root)
    result = stage_resources(root, args.output)
    print(json.dumps({"files": len(result["files"]), "manifest": str(args.output.parent / "build-manifest.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
