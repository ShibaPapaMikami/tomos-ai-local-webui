#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LOCAL_IMPORT_FILES = {
    "agent_reach_adapter.py",
    "app_paths.py",
    "context_core.py",
    "contract_ledger.py",
    "knowledge_layer.py",
    "migration_manager.py",
    "packages/local_context_core/__init__.py",
    "pdf_reader.py",
    "sarashina_ocr_runner.py",
    "search_tools.py",
    "server.py",
    "study_pack_manager.py",
    "tts_engine.py",
}
RUNTIME_SCRIPTS = {
    "scripts/asr_nemotron_runner.py",
    "scripts/asr_nemotron_worker.py",
    "scripts/sarashina_ocr_page.py",
    "scripts/setup-asr-nemotron-mac.sh",
    "scripts/setup-ocr-mac.sh",
}
MAJOR_STATIC_URLS = {
    "/app.js",
    "/docs/ocr-setup.ja.md",
    "/icons/icon-192.png",
    "/icons/icon.svg",
    "/manifest.webmanifest",
    "/mobile.html",
    "/offline.html",
    "/pwa.js",
    "/styles.css",
}
EXPECTED_ARTIFACT = {
    "name": "cpython-3.11.15+20260718-aarch64-apple-darwin-install_only.tar.gz",
    "sha256": "125587d03495bebdf30ec9e549a8469c97c0925d863ff401f24f157fd44d91d6",
    "size": 27241978,
}


def _load_stage_module():
    path = ROOT / "scripts" / "stage-macos-tomos-resources.py"
    spec = importlib.util.spec_from_file_location("stage_macos_tomos_resources", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_path(root: Path, module_name: str) -> Path | None:
    parts = module_name.split(".")
    module_path = root.joinpath(*parts).with_suffix(".py")
    if module_path.is_file():
        return module_path
    package_path = root.joinpath(*parts, "__init__.py")
    return package_path if package_path.is_file() else None


def _server_local_import_graph(root: Path) -> set[str]:
    pending = ["server"]
    visited: set[str] = set()
    files: set[str] = set()
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        visited.add(module_name)
        module_path = _module_path(root, module_name)
        if module_path is None:
            continue
        files.add(module_path.relative_to(root).as_posix())
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                pending.append(node.module)
    return files


def _copy_stageable_root(module, temporary: Path) -> Path:
    temporary.mkdir(parents=True, exist_ok=True)
    source = temporary / "source"
    source.mkdir()
    support_files = (
        "scripts/macos_python_runtime.py",
        "scripts/make-mac-pkg.sh",
        "src-tauri/tauri.conf.json",
    )
    for relative_name in (*module.RESOURCE_FILES, *support_files):
        original = ROOT / relative_name
        copied = source / relative_name
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, copied)
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=TOMOS Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"],
        cwd=source,
        check=True,
    )
    return source


def _assert_rejected(action, expected: str) -> None:
    try:
        action()
    except ValueError as exc:
        assert expected in str(exc).lower(), str(exc)
    else:
        raise AssertionError("unsafe source was accepted")


def test_allowlist_contains_server_graph_web_static_urls_and_runtime_scripts() -> None:
    module = _load_stage_module()
    resources = set(module.RESOURCE_FILES)
    assert _server_local_import_graph(ROOT) == EXPECTED_LOCAL_IMPORT_FILES
    assert EXPECTED_LOCAL_IMPORT_FILES <= resources
    assert "packages/__init__.py" in resources
    web_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "web").rglob("*")
        if path.is_file()
    }
    assert web_files <= resources
    assert RUNTIME_SCRIPTS <= resources
    for url in MAJOR_STATIC_URLS:
        assert f"web/{url.lstrip('/')}" in resources


def test_staged_tree_excludes_private_state_and_records_fixed_release_metadata() -> None:
    module = _load_stage_module()
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary) / "tomos"
        result = module.stage_resources(ROOT, destination)
        names = set(result["files"])
        manifest = json.loads((destination.parent / "build-manifest.json").read_text(encoding="utf-8"))
        staged_hashes = {
            name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
            for name in result["files"]
        }

    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    assert names == set(module.RESOURCE_FILES)
    assert not any(name.startswith(".git/") for name in names)
    assert not any(name.endswith((".sqlite", ".db")) for name in names)
    assert not any("/models/" in f"/{name}/" for name in names)
    assert not any("/.gemma4-data/" in f"/{name}/" for name in names)
    assert not any("/data/" in f"/{name}/" for name in names)
    assert not any(name.endswith(".log") for name in names)
    assert manifest["sourceCommit"] == expected_commit
    assert len(manifest["sourceCommit"]) == 40
    assert manifest["appVersion"] == "0.8.233"
    assert manifest["architecture"] == "arm64"
    assert manifest["bundleId"] == "com.shibapapastudio.tomos-ai"
    assert manifest["pkgIdentifier"] == "jp.local.gemma4-12b"
    assert {name: manifest["pythonArtifact"][name] for name in EXPECTED_ARTIFACT} == EXPECTED_ARTIFACT
    assert manifest["resourceHashes"] == staged_hashes
    assert set(manifest["resourceHashes"]) == names
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in manifest["resourceHashes"].values())


def test_staged_tree_can_import_server() -> None:
    module = _load_stage_module()
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary) / "tomos"
        data_root = Path(temporary) / "app-data"
        module.stage_resources(ROOT, destination)
        result = subprocess.run(
            [sys.executable, "-c", "import server"],
            cwd=destination,
            env={**os.environ, "TOMOS_DATA_ROOT": str(data_root)},
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, result.stderr


def test_stage_rejects_leaf_parent_and_root_symlinks() -> None:
    module = _load_stage_module()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        leaf_root = _copy_stageable_root(module, temporary_path / "leaf")
        external_leaf = leaf_root / "external-server.py"
        external_leaf.write_text((leaf_root / "server.py").read_text(encoding="utf-8"), encoding="utf-8")
        (leaf_root / "server.py").unlink()
        (leaf_root / "server.py").symlink_to(external_leaf)
        _assert_rejected(lambda: module.stage_resources(leaf_root, temporary_path / "leaf-output"), "server.py")

        parent_root = _copy_stageable_root(module, temporary_path / "parent")
        external_web = parent_root / "external-web"
        shutil.copytree(parent_root / "web", external_web)
        shutil.rmtree(parent_root / "web")
        (parent_root / "web").symlink_to(external_web, target_is_directory=True)
        _assert_rejected(lambda: module.stage_resources(parent_root, temporary_path / "parent-output"), "symlink")

        root_source = _copy_stageable_root(module, temporary_path / "root")
        root_link = temporary_path / "root-link"
        root_link.symlink_to(root_source, target_is_directory=True)
        _assert_rejected(lambda: module.stage_resources(root_link, temporary_path / "root-output"), "symlink")


def test_forbidden_components_are_case_insensitive() -> None:
    module = _load_stage_module()
    for unsafe_path in ("DATA/file.txt", ".GIT/config", "SECRETS/key.txt", "MODELS/model.bin", "CACHE/item"):
        _assert_rejected(lambda path=unsafe_path: module._validate_resource_path(path), "forbidden")


def test_manifest_publish_failure_rolls_back_tree() -> None:
    module = _load_stage_module()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        source = _copy_stageable_root(module, temporary_path / "fixture")
        destination = temporary_path / "output" / "tomos"
        manifest_target = destination.parent / "build-manifest.json"
        real_replace = module.os.replace

        def fail_manifest_publish(source_path, target_path) -> None:
            if Path(source_path).name == "build-manifest.json":
                raise OSError("forced manifest publish failure")
            real_replace(source_path, target_path)

        module.os.replace = fail_manifest_publish
        try:
            try:
                module.stage_resources(source, destination)
            except OSError as exc:
                assert "manifest" in str(exc).lower()
            else:
                raise AssertionError("manifest publish failure was accepted")
        finally:
            module.os.replace = real_replace
        assert not destination.exists()
        assert not manifest_target.exists()


def test_release_mode_rejects_dirty_worktree() -> None:
    module = _load_stage_module()
    with tempfile.TemporaryDirectory() as temporary:
        source = _copy_stageable_root(module, Path(temporary))
        (source / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        _assert_rejected(lambda: module.require_clean_release_worktree(source), "dirty")


def main() -> None:
    test_allowlist_contains_server_graph_web_static_urls_and_runtime_scripts()
    test_staged_tree_excludes_private_state_and_records_fixed_release_metadata()
    test_staged_tree_can_import_server()
    test_stage_rejects_leaf_parent_and_root_symlinks()
    test_forbidden_components_are_case_insensitive()
    test_manifest_publish_failure_rolls_back_tree()
    test_release_mode_rejects_dirty_worktree()
    print("macOS TOMOS resource staging tests passed")


if __name__ == "__main__":
    main()
