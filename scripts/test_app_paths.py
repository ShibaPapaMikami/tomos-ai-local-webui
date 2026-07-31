#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import os
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_paths import TomosPaths, ensure_data_directories, tomos_data_root
from knowledge_layer import connect as connect_knowledge_db


def test_default_data_root_is_application_support() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = tomos_data_root(env={}, home=Path(tmp))
        assert root == Path(tmp) / "Library/Application Support/com.shibapapastudio.tomos-ai"


def test_absolute_data_root_override_is_used() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        override = Path(tmp) / "external-data"
        assert tomos_data_root(env={"TOMOS_DATA_ROOT": str(override)}, home=Path(tmp)) == override


def test_paths_keep_user_data_outside_resource_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = TomosPaths.from_root(Path(tmp) / "app-data")
        assert paths.knowledge_db == Path(tmp) / "app-data/data/knowledge/index.sqlite"
        assert paths.context_db == Path(tmp) / "app-data/data/memory/context.sqlite"
        assert paths.contracts_db == Path(tmp) / "app-data/data/contracts/contracts.sqlite"
        assert paths.study_packs == Path(tmp) / "app-data/data/study-packs"
        assert paths.person_photos == Path(tmp) / "app-data/data/person-photos"
        assert paths.codegraph == Path(tmp) / "app-data/data/codegraph"
        assert paths.logs == Path(tmp) / "app-data/logs"
        assert paths.migration == Path(tmp) / "app-data/migration"


def test_paths_do_not_create_directories_until_explicitly_ensured() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "app-data"
        paths = TomosPaths.from_root(root)
        assert not root.exists()
        ensure_data_directories(paths)
        assert paths.knowledge_db.parent.is_dir()
        assert paths.context_db.parent.is_dir()
        assert paths.contracts_db.parent.is_dir()
        assert paths.study_packs.is_dir()
        assert paths.person_photos.is_dir()
        assert paths.codegraph.is_dir()
        assert paths.logs.is_dir()
        assert paths.migration.is_dir()


def test_importing_server_does_not_create_data_directories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp) / "app-data"
        env = os.environ.copy()
        env["TOMOS_DATA_ROOT"] = str(data_root)
        completed = subprocess.run(
            [sys.executable, "-c", "import server"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert not data_root.exists()


def test_server_startup_does_not_create_data_directories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp) / "app-data"
        env = os.environ.copy()
        env["TOMOS_DATA_ROOT"] = str(data_root)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import server, sys; "
                "server.ThreadingHTTPServer = type('NoopServer', (), "
                "{'__init__': lambda self, *args: None, 'serve_forever': lambda self: None}); "
                "sys.argv = ['server.py']; server.main()",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert not data_root.exists()


def test_new_profile_read_does_not_create_context_database_or_directories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp) / "app-data"
        env = os.environ.copy()
        env["TOMOS_DATA_ROOT"] = str(data_root)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import server; "
                "payload = server.context_memory_profile_payload({}); "
                "assert payload == {'ok': True, 'stableFacts': [], 'recentActivities': []}",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert not data_root.exists()


def test_explicit_memory_save_initializes_managed_data_directories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp) / "app-data"
        env = os.environ.copy()
        env["TOMOS_DATA_ROOT"] = str(data_root)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import server; "
                "payload = server.context_memory_save_payload({'item': {'text': '保存する記憶'}}); "
                "assert payload['ok']; "
                "assert server.CONTEXT_DB_PATH.is_file()",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert TomosPaths.from_root(data_root).context_db.is_file()


def test_database_connections_do_not_create_uninitialized_data_directories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = TomosPaths.from_root(Path(tmp) / "app-data")
        try:
            connect_knowledge_db(paths.knowledge_db)
        except sqlite3.OperationalError:
            pass
        else:
            raise AssertionError("database connection must require initialized data directories")
        assert not paths.root.exists()


def test_data_root_rejects_empty_and_relative_overrides() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        for value in ("", "relative-data"):
            try:
                tomos_data_root(env={"TOMOS_DATA_ROOT": value}, home=home)
            except ValueError:
                continue
            raise AssertionError(f"override must be rejected: {value!r}")


def test_data_root_rejects_symlink_that_returns_to_resource_bundle() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        link = Path(tmp) / "bundle-link"
        link.symlink_to(ROOT, target_is_directory=True)
        try:
            tomos_data_root(env={"TOMOS_DATA_ROOT": str(link)}, home=Path(tmp))
        except ValueError:
            return
        raise AssertionError("symlinked resource bundle override must be rejected")


if __name__ == "__main__":
    test_default_data_root_is_application_support()
    test_absolute_data_root_override_is_used()
    test_paths_keep_user_data_outside_resource_root()
    test_paths_do_not_create_directories_until_explicitly_ensured()
    test_importing_server_does_not_create_data_directories()
    test_server_startup_does_not_create_data_directories()
    test_new_profile_read_does_not_create_context_database_or_directories()
    test_explicit_memory_save_initializes_managed_data_directories()
    test_database_connections_do_not_create_uninitialized_data_directories()
    test_data_root_rejects_empty_and_relative_overrides()
    test_data_root_rejects_symlink_that_returns_to_resource_bundle()
    print("app paths tests passed")
