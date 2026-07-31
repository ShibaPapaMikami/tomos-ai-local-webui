#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import os
import fcntl
import base64
import shutil
import json
import hashlib
import multiprocessing
import sqlite3
import struct
import zlib
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_paths import TomosPaths
from contract_ledger import save_contract
from context_core import remember, save_context_record
from knowledge_layer import index_folder
from study_pack_manager import remove_pack
import migration_manager
from migration_manager import (
    MigrationApprovalError,
    MigrationNotFoundError,
    MigrationPreviewStaleError,
    MigrationSource,
    MigrationValidationError,
    apply_migration,
    build_migration_preview,
    detect_legacy_sources,
    has_pending_migrations,
    managed_data_write,
    prepare_managed_data_startup,
    recover_migrations,
    rollback_migration,
    snapshot_id_for_migration,
)

OFFICIAL_PACK = ROOT / "study-packs/note-article-writing-pack"
OFFICIAL_PACK_NAME = "note-article-writing"
VALID_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAASABIAAD/4QBMRXhpZgAATU0AKgAAAAgAAYdpAAQAAAAB"
    "AAAAGgAAAAAAA6ABAAMAAAABAAEAAKACAAQAAAABAAAAAaADAAQAAAABAAAAAQAA"
    "AAD/7QA4UGhvdG9zaG9wIDMuMAA4QklNBAQAAAAAAAA4QklNBCUAAAAAABDUHYzZ"
    "jwCyBOmACZjs+EJ+/8AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAA"
    "AAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFB"
    "BhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNE"
    "RUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqi"
    "o6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz"
    "9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIB"
    "AgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy"
    "0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpz"
    "dHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
    "x8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/bAEMAAgICAgICAwICAwUD"
    "AwMFBgUFBQUGCAYGBgYGCAoICAgICAgKCgoKCgoKCgwMDAwMDA4ODg4ODw8PDw8P"
    "Dw8PD//bAEMBAgICBAQEBwQEBxALCQsQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBA"
    "QEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEP/dAAQAAf/aAAwDAQACEQMRAD8A+g"
    "KKKK5wP//Z"
)
VALID_WEBP_BASE64 = "UklGRiYAAABXRUJQVlA4IBoAAAAwAQCdASoBAAEAAgA0JZwAA3AA/uu3qPwAAA=="
VALID_LOSSLESS_WEBP_BASE64 = (
    "UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA=="
)
OVERSIZED_VALID_VP8_BASE64 = (
    "UklGRl4IAABXRUJQVlA4IFIIAADw6ACdASoBBAEEPtFosVMoJaSioAgBABoJaW7hd2Eff6B7ABPY"
    "B77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZORJg3Vz2BKZ9L3nXpXyBe6ZYI3JLqzutACDdXPYEp"
    "n0vedelfF94+xdQX1rTQvsJoxub9hRWx76H7wG+v+lt+NkXXbU4YJVwlLSoFku14uTkPfbJyHvtk"
    "5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe/AEA99snIe+2TkPfbJyHvtk5D32"
    "ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe"
    "+2TkPfbJyHwH6Xa8XJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2Tk"
    "PfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32yciIHk5D32ych77ZOQ99snIe+2TkPfbJ"
    "yHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77"
    "ZOQ99snOIi5OQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ9"
    "9snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbMZae2TkPfbJyHvtk5D32ych77ZOQ99snI"
    "e+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk"
    "5D34AgHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32"
    "ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ+hfS7Xi5OQ99snIe+2TkPfbJyHvtk5D32ych7"
    "7ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2Tk"
    "f88nIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJ"
    "yHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtlAy8XJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvt"
    "k5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77cy/T"
    "2ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snI"
    "e+2TkPfbJyHvtk5D32ych77ZOQ99snIfAfpdrxcnIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2T"
    "kPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyIgeTkPfb"
    "JyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych7"
    "7ZOQ99snIe+2TkPfbJyHvtk5D32yc4iLk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ"
    "99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99sxlp7ZOQ99sn"
    "Ie+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvt"
    "k5D32ych77ZOQ99snIe+2TkPfgCAe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D3"
    "2ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D6F9LteLk5D32ych"
    "77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2T"
    "kPfbJyHvtk5D32ych77ZOR/zych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfb"
    "JyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2UDLxcnIe+2TkPfbJyHv"
    "tk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ"
    "99snIe+2TkPfbJyHvtzL9PbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99sn"
    "Ie+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych8B+l2vFych77ZOQ99snIe+2"
    "TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D3"
    "2ych77ZOQ99snCgA/v+pef+reZOkjP/g209ZWY9q2k1dW0mrq2k1dW0mrq2k1dW0mrq2k1dW0mrq"
    "2k1dW0mrq2k1dW0mrq2k1dW0mrq2k1dWY7HAdYDrAdYDrAdYDrAdYDrAdYDrAdYDrAdYDrAdYE7A"
    "8OBAPGBBJtWBA80A/YEAAB8BQG9AgAAPgKA3oEAAB8BQG9AgAAPgKA3oEAAB8BQG9AgAAPgKA3oE"
    "AAB8BQG9AgAAPgKA3oEAAB8BQG9AgAAPgKA3oEAAB8BQG9AgAAPgKA3oEAAB8BQG9AgAAPgKA3oE"
    "AAB8BQG9AgAAPgKA3oEAAB8BQG9AgAAPgKA3oEAAB8BQG9AgAAAAAAA="
)
OVERSIZED_VALID_VP8L_BASE64 = (
    "UklGRlAAAABXRUJQVlA4TEQAAAAvAAQAAQdQ547Wvf8BAUnS//2BEf3P+M9//vOf//znP//5z3/+"
    "85///Oc///nPf/7zn//85z//+c9//vOf//znP///BA=="
)


def make_valid_png() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00\xff")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def make_valid_jpeg() -> bytes:
    return base64.b64decode(VALID_JPEG_BASE64, validate=True)


def make_valid_webp() -> bytes:
    return base64.b64decode(VALID_WEBP_BASE64, validate=True)


def make_valid_lossless_webp() -> bytes:
    return base64.b64decode(
        VALID_LOSSLESS_WEBP_BASE64, validate=True
    )


def make_oversized_valid_webps() -> tuple[bytes, bytes]:
    return (
        base64.b64decode(
            OVERSIZED_VALID_VP8_BASE64, validate=True
        ),
        base64.b64decode(
            OVERSIZED_VALID_VP8L_BASE64, validate=True
        ),
    )


def make_webp_container(*chunks: bytes) -> bytes:
    contents = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(contents)) + contents


def make_webp_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        kind
        + struct.pack("<I", len(payload))
        + payload
        + (b"\x00" if len(payload) & 1 else b"")
    )


def make_oversized_vp8x_webp() -> bytes:
    maximum_safe_dimension = 1024
    header = (
        b"\x00\x00\x00\x00"
        + maximum_safe_dimension.to_bytes(3, "little")
        + maximum_safe_dimension.to_bytes(3, "little")
    )
    return make_webp_container(
        make_webp_chunk(b"VP8X", header),
        make_valid_webp()[12:],
    )


def make_oversized_anmf_webp() -> bytes:
    maximum_safe_dimension = 1024
    frame_header = (
        b"\x00" * 6
        + maximum_safe_dimension.to_bytes(3, "little")
        + maximum_safe_dimension.to_bytes(3, "little")
        + b"\x00" * 4
    )
    return make_webp_container(
        make_webp_chunk(
            b"ANMF", frame_header + make_valid_webp()[12:]
        )
    )


def make_riff_consistent_undecodable_webp() -> bytes:
    bitstream = b"\x2f\x00\x00\x00\x00\x00"
    contents = (
        b"WEBP"
        + b"VP8L"
        + struct.pack("<I", len(bitstream))
        + bitstream
    )
    return b"RIFF" + struct.pack("<I", len(contents)) + contents


def make_riff_consistent_undecodable_vp8_webp() -> bytes:
    bitstream = (
        b"\x20\x00\x00"
        + b"\x9d\x01\x2a"
        + b"\x01\x00"
        + b"\x01\x00"
        + b"\x00"
    )
    contents = (
        b"WEBP"
        + b"VP8 "
        + struct.pack("<I", len(bitstream))
        + bitstream
        + b"\x00"
    )
    return b"RIFF" + struct.pack("<I", len(contents)) + contents


def make_paths(tmp_path: Path) -> TomosPaths:
    return TomosPaths.from_root(tmp_path / "app-data")


def make_legacy_fixture(root: Path, extras: list[str] | None = None) -> Path:
    files = {
        ".gemma4-data/knowledge/index.sqlite": b"knowledge database",
        ".gemma4-data/context/context.sqlite": b"context database",
        ".gemma4-data/contracts/contracts.sqlite": b"contracts database",
        "data/person-photos/person.png": make_valid_png(),
    }
    for relative_path, contents in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    shutil.copytree(
        OFFICIAL_PACK,
        root / ".gemma4-data/study-packs" / OFFICIAL_PACK_NAME,
    )
    for extra in extras or []:
        target = root / extra
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("must not appear", encoding="utf-8")
    return root


def preview_fixture(legacy: Path, tmp_path: Path | None = None) -> dict:
    destination_root = (tmp_path or legacy.parent) / "app-data"
    return build_migration_preview(
        detect_legacy_sources([legacy], TomosPaths.from_root(destination_root))
    )


def make_sqlite_database(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample(value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def make_sqlite_database_with_persistent_journal(
    path: Path, value: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm", "-journal"):
        candidate = path.with_name(f"{path.name}{suffix}")
        if candidate.exists():
            candidate.unlink()
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "PRAGMA journal_mode = PERSIST"
        ).fetchone() == ("persist",)
        connection.execute(
            "CREATE TABLE sample (value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sample(value) VALUES (?)", (value,)
        )
        connection.commit()
    finally:
        connection.close()
    assert path.with_name(f"{path.name}-journal").is_file()


def read_sample_value(path: Path) -> str:
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro", uri=True
    )
    try:
        row = connection.execute("SELECT value FROM sample").fetchone()
    finally:
        connection.close()
    assert row is not None
    return str(row[0])


def leave_wal_commit_worker(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("UPDATE sample SET value = ?", (value,))
    connection.commit()
    os._exit(0)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sqlite_physical_state(path: Path) -> dict[str, bytes | None]:
    return {
        suffix or "main": (
            candidate.read_bytes() if candidate.exists() else None
        )
        for suffix in ("", "-wal", "-shm", "-journal")
        for candidate in (path.with_name(f"{path.name}{suffix}"),)
    }


def assert_sqlite_wal_physical_state(
    path: Path, expected: dict[str, bytes | None]
) -> None:
    assert sqlite_physical_state(path) == expected
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone() == (
            "wal",
        )
    finally:
        connection.close()


def raises(expected: type[BaseException], operation) -> BaseException:
    try:
        operation()
    except expected as error:
        return error
    raise AssertionError(f"{expected.__name__} was not raised")


def apply_fixture(tmp_path: Path) -> tuple[Path, TomosPaths, dict]:
    legacy = make_legacy_fixture(tmp_path / "legacy")
    make_sqlite_database(legacy / ".gemma4-data/knowledge/index.sqlite", "legacy")
    make_sqlite_database(legacy / ".gemma4-data/context/context.sqlite", "legacy")
    make_sqlite_database(legacy / ".gemma4-data/contracts/contracts.sqlite", "legacy")
    paths = make_paths(tmp_path)
    preview = build_migration_preview(detect_legacy_sources([legacy], paths))
    return legacy, paths, preview


class SimulatedProcessCrash(BaseException):
    pass


def leave_new_only_quarantine_fixture(
    tmp_path: Path,
) -> tuple[TomosPaths, Path]:
    _legacy, paths, preview = apply_fixture(tmp_path)

    def crash_after_main(point: str, kind: str) -> None:
        if (
            point == "after_sqlite_main_publish"
            and kind == paths.knowledge_db.name
        ):
            raise SimulatedProcessCrash()

    with patch(
        "migration_manager._fault_injection",
        side_effect=crash_after_main,
    ):
        raises(
            SimulatedProcessCrash,
            lambda: apply_migration(
                preview["previewId"], ["knowledge"], paths
            ),
        )

    def crash_after_quarantine(point: str, kind: str) -> None:
        if (
            point == "after_new_only_sqlite_quarantine"
            and kind == paths.knowledge_db.name
        ):
            raise SimulatedProcessCrash()

    with patch(
        "migration_manager._fault_injection",
        side_effect=crash_after_quarantine,
    ):
        raises(
            SimulatedProcessCrash,
            lambda: recover_migrations(paths),
        )

    quarantine = next(
        paths.knowledge_db.parent.glob(
            ".*.tomos-apply-current-*.displaced"
        )
    )
    return paths, quarantine


def leave_new_only_main_publish_crash(
    tmp_path: Path,
) -> tuple[TomosPaths, Path]:
    _legacy, paths, preview = apply_fixture(tmp_path)

    def crash_after_main(point: str, kind: str) -> None:
        if (
            point == "after_sqlite_main_publish"
            and kind == paths.knowledge_db.name
        ):
            raise SimulatedProcessCrash()

    with patch(
        "migration_manager._fault_injection",
        side_effect=crash_after_main,
    ):
        raises(
            SimulatedProcessCrash,
            lambda: apply_migration(
                preview["previewId"], ["knowledge"], paths
            ),
        )
    staging = next(
        paths.knowledge_db.parent.glob(".*.tomos-stage-*")
    )
    return paths, staging


def add_complete_wal_staging_bundle(
    paths: TomosPaths, staging: Path, value: str
) -> dict:
    context = multiprocessing.get_context("spawn")
    writer = context.Process(
        target=leave_wal_commit_worker,
        args=(staging, value),
    )
    writer.start()
    writer.join(timeout=10)
    assert writer.exitcode == 0
    assert staging.with_name(f"{staging.name}-wal").is_file()
    assert staging.with_name(f"{staging.name}-shm").is_file()
    staging.with_name(f"{staging.name}-journal").write_bytes(bytes(512))

    parent_fd = os.open(
        staging.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
    )
    try:
        expected_digest = migration_manager._managed_digest_at(
            parent_fd,
            staging.name,
            sqlite_logical=True,
        )
        replacement_physical = (
            migration_manager._sqlite_physical_digest_at(
                parent_fd, staging.name
            )
        )
    finally:
        os.close(parent_fd)

    journal_path = next(paths.migration.glob("journals/*.json"))
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["items"][0]["expectedDigest"] = expected_digest
    journal["items"][0][
        "replacementPhysicalDigest"
    ] = replacement_physical
    journal_path.write_text(
        json.dumps(journal, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return replacement_physical


def crash_new_only_recovery_after_destination_unlink(
    paths: TomosPaths,
) -> tuple[Path, Path]:
    def crash_after_destination_unlink(
        point: str, kind: str
    ) -> None:
        if (
            point == "after_new_only_sqlite_destination_unlink"
            and kind == paths.knowledge_db.name
        ):
            raise SimulatedProcessCrash()

    with patch(
        "migration_manager._fault_injection",
        side_effect=crash_after_destination_unlink,
    ):
        raises(
            SimulatedProcessCrash,
            lambda: recover_migrations(paths),
        )
    journal_path = next(paths.migration.glob("journals/*.json"))
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert journal["items"][0]["phase"] == "recovery_pending"
    assert (
        journal["items"][0]["sqliteComponentPhase"]
        == "quarantined"
    )
    quarantine = next(
        paths.knowledge_db.parent.glob(
            ".*.tomos-apply-current-*.displaced"
        )
    )
    return journal_path, quarantine


def retained_external_write_guard(
    paths: TomosPaths,
) -> tuple[Path, dict, Path]:
    records = list(
        (
            paths.migration / "retained-external-write-guards"
        ).glob("*.json")
    )
    assert len(records) == 1, records
    record_path = records[0]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["status"] == "retained_external_write_guard"
    assert record["kind"] == "knowledge"
    guard = paths.knowledge_db.with_name(
        f".{paths.knowledge_db.name}."
        f"tomos-retained-external-write-guard-{record['guardId']}"
    )
    return record_path, record, guard


def leave_published_apply_journal(
    tmp_path: Path,
) -> tuple[TomosPaths, str]:
    _legacy, paths, preview = apply_fixture(tmp_path)
    make_sqlite_database(paths.knowledge_db, "current")
    before_hash = file_sha256(paths.knowledge_db)

    def crash_after_publish(point: str, _kind: str) -> None:
        if point == "after_publish":
            raise SimulatedProcessCrash()

    with patch(
        "migration_manager._fault_injection",
        side_effect=crash_after_publish,
    ):
        raises(
            SimulatedProcessCrash,
            lambda: apply_migration(
                preview["previewId"], ["knowledge"], paths
            ),
        )
    assert len(list(paths.migration.glob("journals/*.json"))) == 1
    return paths, before_hash


def concurrent_apply_worker(
    preview_id: str, paths: TomosPaths, ready, start, results
) -> None:
    ready.put(True)
    start.wait()
    try:
        results.put(("ok", apply_migration(preview_id, ["knowledge"], paths)))
    except BaseException as error:
        results.put(("error", type(error).__name__, str(error)))


def managed_writer_worker(
    paths: TomosPaths, ready, release, value: str
) -> None:
    try:
        with managed_data_write(paths):
            make_sqlite_database(paths.knowledge_db, value)
            ready.put(("locked", file_sha256(paths.knowledge_db)))
            release.wait()
    except BaseException as error:
        ready.put(("error", type(error).__name__, str(error)))


def rollback_worker(snapshot_id: str, paths: TomosPaths, results) -> None:
    try:
        results.put(("ok", rollback_migration(snapshot_id, paths)))
    except BaseException as error:
        results.put(("error", type(error).__name__, str(error)))


def legacy_sqlite_writer_attempt(
    database: Path, value: str, results
) -> None:
    connection = sqlite3.connect(database, timeout=0)
    try:
        connection.execute(
            "UPDATE sample SET value = ?",
            (value,),
        )
        connection.commit()
        results.put(("committed", value))
    except sqlite3.OperationalError as error:
        results.put(("blocked", str(error)))
    finally:
        connection.close()


def whole_file_writer_lock_attempt_worker(
    database: Path, blocked, acquired
) -> None:
    file_fd = os.open(
        database,
        os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        try:
            fcntl.lockf(
                file_fd,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
                0,
                0,
                os.SEEK_SET,
            )
        except BlockingIOError:
            blocked.set()
            fcntl.lockf(
                file_fd,
                fcntl.LOCK_EX,
                0,
                0,
                os.SEEK_SET,
            )
        acquired.set()
    finally:
        try:
            fcntl.lockf(
                file_fd,
                fcntl.LOCK_UN,
                0,
                0,
                os.SEEK_SET,
            )
        except OSError:
            pass
        os.close(file_fd)


def waiting_fd_fsync_after_unlink_worker(
    database: Path, blocked, acquired, fsynced, results
) -> None:
    file_fd = os.open(
        database,
        os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        try:
            fcntl.lockf(
                file_fd,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
                0,
                0,
                os.SEEK_SET,
            )
        except BlockingIOError:
            blocked.set()
            fcntl.lockf(
                file_fd,
                fcntl.LOCK_EX,
                0,
                0,
                os.SEEK_SET,
            )
        acquired.set()
        link_count = os.fstat(file_fd).st_nlink
        user_version = 20_260_728
        os.pwrite(file_fd, struct.pack(">I", user_version), 60)
        os.fsync(file_fd)
        observed = struct.unpack(">I", os.pread(file_fd, 4, 60))[0]
        fsynced.set()
        results.put(("fsynced", link_count, observed))
    finally:
        try:
            fcntl.lockf(
                file_fd,
                fcntl.LOCK_UN,
                0,
                0,
                os.SEEK_SET,
            )
        except OSError:
            pass
        os.close(file_fd)


def waiting_sqlite_connection_after_unlink_worker(
    database: Path, opened, attempting, results
) -> None:
    try:
        connection = sqlite3.connect(database, timeout=15)
        try:
            connection.execute("PRAGMA busy_timeout = 15000")
            opened.set()
            attempting.set()
            connection.execute(
                "UPDATE sample SET value = ?",
                ("external-same-connection",),
            )
            connection.commit()
            results.put(("committed",))
        except sqlite3.OperationalError as error:
            results.put(
                (
                    "error",
                    getattr(error, "sqlite_errorcode", None),
                    getattr(error, "sqlite_errorname", None),
                    str(error),
                )
            )
        finally:
            connection.close()
    except BaseException as error:
        results.put(("error", type(error).__name__, str(error)))


def create_external_wal_database_worker(
    database: Path, value: str, ready, release
) -> None:
    connection = sqlite3.connect(database, timeout=0)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            "CREATE TABLE sample (value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sample(value) VALUES (?)", (value,)
        )
        connection.commit()
        ready.put(("ready", value))
        release.wait()
    except BaseException as error:
        ready.put(("error", type(error).__name__, str(error)))
    finally:
        connection.close()


def test_preview_only_reads_known_legacy_roots() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        preview = build_migration_preview(detect_legacy_sources([legacy], make_paths(tmp_path)))
        assert preview["totalFiles"] > 0
        assert preview["items"][0]["kind"] == "knowledge"
        assert not (tmp_path / "app-data").exists()


def test_detect_legacy_sources_matches_pre_b3_default_storage_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy_home = tmp_path / "home"
        legacy_root = tmp_path / "old-root"
        paths = make_paths(tmp_path)
        expected_sources = {
            "knowledge": legacy_home / ".gemma4-data/knowledge/index.sqlite",
            "context": legacy_home / ".gemma4-data/context/context.sqlite",
            "contracts": legacy_home / ".gemma4-data/contracts/contracts.sqlite",
            "study-packs": legacy_home / ".gemma4-data/study-packs",
            "person-photos": legacy_root / "data/person-photos",
        }
        for kind in ("knowledge", "context", "contracts"):
            source = expected_sources[kind]
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(f"{kind} database".encode("utf-8"))
        shutil.copytree(
            OFFICIAL_PACK,
            expected_sources["study-packs"] / OFFICIAL_PACK_NAME,
        )
        expected_sources["person-photos"].mkdir(parents=True)
        (
            expected_sources["person-photos"] / "person.png"
        ).write_bytes(make_valid_png())
        expected_sources = {
            kind: source.resolve()
            for kind, source in expected_sources.items()
        }

        sources = detect_legacy_sources(
            [legacy_home, legacy_root], paths
        )

        assert {source.kind: source.source for source in sources} == (
            expected_sources
        )


def test_default_home_containing_managed_root_previews_and_applies_all_legacy_sources() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy_home = tmp_path / "home"
        legacy_root = tmp_path / "old-resource-root"
        paths = TomosPaths.from_root(
            legacy_home
            / "Library/Application Support/com.shibapapastudio.tomos-ai"
        )
        database_sources = {
            "knowledge": legacy_home
            / ".gemma4-data/knowledge/index.sqlite",
            "context": legacy_home
            / ".gemma4-data/context/context.sqlite",
            "contracts": legacy_home
            / ".gemma4-data/contracts/contracts.sqlite",
        }
        for kind, source in database_sources.items():
            make_sqlite_database(source, f"legacy-{kind}")
        shutil.copytree(
            OFFICIAL_PACK,
            legacy_home
            / ".gemma4-data/study-packs"
            / OFFICIAL_PACK_NAME,
        )
        person_photo = legacy_root / "data/person-photos/person.webp"
        person_photo.parent.mkdir(parents=True)
        person_photo.write_bytes(make_valid_webp())

        sources = detect_legacy_sources(
            [legacy_home, legacy_root], paths
        )
        assert {source.kind for source in sources} == {
            "knowledge",
            "context",
            "contracts",
            "study-packs",
            "person-photos",
        }
        preview = build_migration_preview(sources)

        assert preview["totalFiles"] > 0
        assert not paths.root.exists()
        result = apply_migration(
            preview["previewId"],
            [source.kind for source in sources],
            paths,
        )

        assert result["status"] == "completed"
        assert read_sample_value(paths.knowledge_db) == "legacy-knowledge"
        assert read_sample_value(paths.context_db) == "legacy-context"
        assert read_sample_value(paths.contracts_db) == "legacy-contracts"
        assert (
            paths.study_packs / OFFICIAL_PACK_NAME / "pack.json"
        ).read_bytes() == (OFFICIAL_PACK / "pack.json").read_bytes()
        assert (
            paths.person_photos / person_photo.name
        ).read_bytes() == make_valid_webp()


def test_detect_rejects_same_kind_in_home_and_old_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy_home = tmp_path / "home"
        legacy_root = tmp_path / "old-root"
        for root in (legacy_home, legacy_root):
            source = root / ".gemma4-data/context/context.sqlite"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"context database")

        raises(
            MigrationValidationError,
            lambda: detect_legacy_sources(
                [legacy_home, legacy_root], make_paths(tmp_path)
            ),
        )


def test_preview_excludes_secrets_and_unknown_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        legacy = make_legacy_fixture(
            Path(tmp) / "legacy", extras=[".env", "token.txt", "unknown.db"]
        )
        preview = preview_fixture(legacy)
        assert {item["name"] for item in preview["files"]}.isdisjoint(
            {".env", "token.txt", "unknown.db"}
        )


def test_preview_excludes_nested_secrets_and_unknown_directory_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        for relative_path in (
            f".gemma4-data/study-packs/{OFFICIAL_PACK_NAME}/.env",
            f".gemma4-data/study-packs/{OFFICIAL_PACK_NAME}/token.txt",
            f".gemma4-data/study-packs/{OFFICIAL_PACK_NAME}/nested/session.json",
            f".gemma4-data/study-packs/{OFFICIAL_PACK_NAME}/unknown.exe",
            "data/person-photos/.hidden.png",
            "data/person-photos/api-key.jpg",
            "data/person-photos/person.txt",
            "data/person-photos/person.jpeg",
        ):
            target = legacy / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("must not appear", encoding="utf-8")

        preview = preview_fixture(legacy)
        names = {item["name"] for item in preview["files"]}

        assert f"{OFFICIAL_PACK_NAME}/pack.json" in names
        assert "person.png" in names
        assert names.isdisjoint(
            {
                f"{OFFICIAL_PACK_NAME}/.env",
                f"{OFFICIAL_PACK_NAME}/token.txt",
                f"{OFFICIAL_PACK_NAME}/nested/session.json",
                f"{OFFICIAL_PACK_NAME}/unknown.exe",
                ".hidden.png",
                "api-key.jpg",
                "person.txt",
                "person.jpeg",
            }
        )
        assert preview["excludedCount"] >= 8


def test_preview_excludes_study_pack_without_pack_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        stray_pack = legacy / ".gemma4-data/study-packs/stray-pack"
        stray_pack.mkdir()
        (stray_pack / "notes.md").write_text("must not migrate", encoding="utf-8")

        preview = preview_fixture(legacy)

        assert "stray-pack/notes.md" not in {item["name"] for item in preview["files"]}
        assert preview["excludedCount"] >= 1


def test_preview_accepts_only_official_study_pack_files_with_reference_hashes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        preview = preview_fixture(legacy)
        names = {item["name"] for item in preview["files"]}
        expected_paths = set(migration_manager._OFFICIAL_STUDY_FILE_HASHES)
        expected_names = {f"{OFFICIAL_PACK_NAME}/{path}" for path in expected_paths}
        reference_hashes = {
            path: hashlib.sha256((OFFICIAL_PACK / path).read_bytes()).hexdigest()
            for path in expected_paths
        }

        assert migration_manager._OFFICIAL_STUDY_FILE_HASHES == reference_hashes
        assert expected_names.issubset(names)


def test_preview_rejects_official_study_pack_cloned_under_unexpected_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        unexpected_name = "renamed-official-pack"
        shutil.copytree(
            legacy / ".gemma4-data/study-packs" / OFFICIAL_PACK_NAME,
            legacy / ".gemma4-data/study-packs" / unexpected_name,
        )

        preview = preview_fixture(legacy)
        names = {item["name"] for item in preview["files"]}

        assert f"{OFFICIAL_PACK_NAME}/pack.json" in names
        assert not any(name.startswith(f"{unexpected_name}/") for name in names)


def test_preview_rejects_modified_and_custom_study_packs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        official = legacy / ".gemma4-data/study-packs" / OFFICIAL_PACK_NAME
        modified = official / "modes/rewrite-for-note.md"
        modified.write_bytes(modified.read_bytes() + b"x")
        custom = legacy / ".gemma4-data/study-packs/custom-pack"
        custom.mkdir()
        (custom / "pack.json").write_text(
            json.dumps({"id": "custom", "version": "0.1.0", "visibility": "public", "modes": []}),
            encoding="utf-8",
        )

        preview = preview_fixture(legacy)
        names = {item["name"] for item in preview["files"]}

        assert f"{OFFICIAL_PACK_NAME}/modes/rewrite-for-note.md" not in names
        assert not any(name.startswith("custom-pack/") for name in names)


def test_preview_rejects_photo_extension_with_invalid_magic_bytes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        (legacy / "data/person-photos/fake.png").write_bytes(b"not-an-image")

        preview = preview_fixture(legacy)

        assert "fake.png" not in {item["name"] for item in preview["files"]}
        assert "person.png" in {item["name"] for item in preview["files"]}


def test_preview_rejects_png_with_trailing_credential_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        (legacy / "data/person-photos/portrait.png").write_bytes(
            make_valid_png() + b"AIzaSyA-not-an-image-payload"
        )

        preview = preview_fixture(legacy)

        assert "portrait.png" not in {item["name"] for item in preview["files"]}


def test_preview_and_apply_accept_strict_server_person_photo_formats() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        photo_root = legacy / "data/person-photos"
        expected = {
            "person.jpg": make_valid_jpeg(),
            "person.png": make_valid_png(),
            "person.webp": make_valid_webp(),
            "person-lossless.webp": make_valid_lossless_webp(),
        }
        for name, payload in expected.items():
            (photo_root / name).write_bytes(payload)
        paths = make_paths(tmp_path)
        preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )

        assert expected.keys() <= {
            item["name"] for item in preview["files"]
        }
        result = apply_migration(
            preview["previewId"], ["person-photos"], paths
        )

        assert result["status"] == "completed"
        assert {
            name: (paths.person_photos / name).read_bytes()
            for name in expected
        } == expected


def test_preview_excludes_trailing_and_corrupt_server_photo_formats() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        photo_root = legacy / "data/person-photos"
        valid_by_extension = {
            ".jpg": make_valid_jpeg(),
            ".png": make_valid_png(),
            ".webp": make_valid_webp(),
        }
        invalid_names: set[str] = set()
        for extension, payload in valid_by_extension.items():
            trailing_name = f"trailing{extension}"
            corrupt_name = f"corrupt{extension}"
            (photo_root / trailing_name).write_bytes(
                payload + b"credential-payload"
            )
            (photo_root / corrupt_name).write_bytes(payload[:-2])
            invalid_names.update({trailing_name, corrupt_name})

        preview = preview_fixture(legacy)
        names = {item["name"] for item in preview["files"]}

        assert names.isdisjoint(invalid_names)
        assert preview["excludedCount"] >= len(invalid_names)


def test_preview_excludes_riff_consistent_undecodable_webp_without_writing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        photo_root = legacy / "data/person-photos"
        (photo_root / "undecodable-lossless.webp").write_bytes(
            make_riff_consistent_undecodable_webp()
        )
        (photo_root / "undecodable-lossy.webp").write_bytes(
            make_riff_consistent_undecodable_vp8_webp()
        )
        paths = make_paths(tmp_path)

        preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )
        names = {item["name"] for item in preview["files"]}

        assert names.isdisjoint(
            {
                "undecodable-lossless.webp",
                "undecodable-lossy.webp",
            }
        )
        assert "person.png" in names
        assert preview["excludedCount"] >= 2
        assert not paths.root.exists()


def test_webp_validation_fails_closed_when_native_decoder_is_unavailable() -> None:
    with patch(
        "migration_manager._decode_webp_image",
        return_value=False,
        create=True,
    ):
        assert migration_manager._is_safe_webp(make_valid_webp()) is False


def test_oversized_webp_headers_reject_before_native_decoder() -> None:
    oversized_vp8, oversized_vp8l = make_oversized_valid_webps()
    assert len(oversized_vp8) == 2150
    assert len(oversized_vp8l) == 88

    def reject_unexpected_decoder_call(_payload: bytes) -> bool:
        raise AssertionError(
            "native decoder called for oversized WebP header"
        )

    with patch(
        "migration_manager._decode_webp_image",
        side_effect=reject_unexpected_decoder_call,
    ):
        for payload in (
            oversized_vp8,
            oversized_vp8l,
            make_oversized_vp8x_webp(),
            make_oversized_anmf_webp(),
        ):
            assert migration_manager._is_safe_webp(payload) is False


def test_native_webp_layout_rejects_before_provider_copy() -> None:
    provider_events: list[str] = []

    class NativeFunction:
        def __init__(self, operation) -> None:
            self.operation = operation

        def __call__(self, *args):
            return self.operation(*args)

    class NativeLibrary:
        pass

    def fixed(value):
        return NativeFunction(lambda *_args: value)

    core_foundation = NativeLibrary()
    core_foundation.CFDataCreate = fixed(1)
    core_foundation.CFDataGetLength = fixed(4)
    core_foundation.CFRelease = fixed(None)

    image_io = NativeLibrary()
    image_io.CGImageSourceCreateWithData = fixed(2)
    image_io.CGImageSourceGetCount = fixed(1)
    image_io.CGImageSourceGetStatus = fixed(0)
    image_io.CGImageSourceGetStatusAtIndex = fixed(0)
    image_io.CGImageSourceCreateImageAtIndex = fixed(3)

    def get_provider(*_args):
        provider_events.append("provider")
        return 4

    def copy_provider(*_args):
        provider_events.append("copy")
        return 5

    core_graphics = NativeLibrary()
    core_graphics.CGImageGetWidth = fixed(1025)
    core_graphics.CGImageGetHeight = fixed(1025)
    core_graphics.CGImageGetBytesPerRow = fixed(4100)
    core_graphics.CGImageGetDataProvider = NativeFunction(
        get_provider
    )
    core_graphics.CGDataProviderCopyData = NativeFunction(
        copy_provider
    )

    with patch(
        "migration_manager.ctypes.CDLL",
        side_effect=(core_foundation, image_io, core_graphics),
    ):
        assert (
            migration_manager._decode_webp_image(make_valid_webp())
            is False
        )

    assert provider_events == []


def test_preview_skips_fifo_without_blocking() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        fifo = legacy / "data/person-photos/blocked.png"
        os.mkfifo(fifo)

        preview = preview_fixture(legacy)

        assert "blocked.png" not in {item["name"] for item in preview["files"]}
        assert preview["excludedCount"] >= 1


def test_preview_reports_only_metadata_and_destination_conflicts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        paths = make_paths(tmp_path)
        paths.knowledge_db.parent.mkdir(parents=True)
        paths.knowledge_db.write_bytes(b"existing")

        preview = build_migration_preview(detect_legacy_sources([legacy], paths))

        knowledge = next(item for item in preview["items"] if item["kind"] == "knowledge")
        assert knowledge["destination"] == str(paths.knowledge_db)
        assert knowledge["conflict"] is True
        assert all(set(item).isdisjoint({"content", "rows", "text", "secret"}) for item in preview["files"])
        assert preview["totalBytes"] == sum(item["bytes"] for item in preview["files"])
        assert preview["latestMtime"] == max(item["mtime"] for item in preview["files"])


def test_preview_marks_existing_directory_file_and_symlink_destinations_as_conflicts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        paths = make_paths(tmp_path)
        paths.study_packs.mkdir(parents=True)
        paths.person_photos.symlink_to(tmp_path / "missing-person-photos", target_is_directory=True)

        preview = build_migration_preview(detect_legacy_sources([legacy], paths))

        conflicts = {item["kind"]: item["conflict"] for item in preview["items"]}
        assert conflicts["study-packs"] is True
        assert conflicts["person-photos"] is True

        file_paths = TomosPaths.from_root(tmp_path / "file-app-data")
        file_paths.study_packs.parent.mkdir(parents=True)
        file_paths.study_packs.write_bytes(b"not a directory")
        file_preview = build_migration_preview(detect_legacy_sources([legacy], file_paths))
        file_conflicts = {item["kind"]: item["conflict"] for item in file_preview["items"]}
        assert file_conflicts["study-packs"] is True


def test_preview_rejects_directly_constructed_source_without_provenance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        outside = tmp_path / "outside.sqlite"
        outside.write_bytes(b"must not be previewed")
        preview = build_migration_preview(
            [MigrationSource("knowledge", outside, make_paths(tmp_path).knowledge_db)]
        )

        assert preview["items"] == []
        assert preview["files"] == []
        assert preview["totalFiles"] == 0
        assert preview["excludedCount"] == 1


def test_preview_rejects_symlinks_and_path_escape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        escaped = tmp_path / "outside.sqlite"
        escaped.write_bytes(b"outside")
        (legacy / ".gemma4-data/knowledge/index.sqlite").unlink()
        (legacy / ".gemma4-data/knowledge/index.sqlite").symlink_to(escaped)
        (legacy / ".gemma4-data/study-packs/escaped").symlink_to(
            tmp_path, target_is_directory=True
        )

        preview = build_migration_preview(detect_legacy_sources([legacy], make_paths(tmp_path)))

        assert {item["kind"] for item in preview["items"]} == {
            "context",
            "contracts",
            "study-packs",
            "person-photos",
        }
        assert all("outside.sqlite" not in item["name"] for item in preview["files"])


def test_preview_does_not_follow_directory_replacement_during_walk() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        replaced_directory = (
            legacy
            / ".gemma4-data/study-packs"
            / OFFICIAL_PACK_NAME
            / "nested"
        )
        replaced_directory.mkdir()
        (replaced_directory / "safe.md").write_text("safe", encoding="utf-8")
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "leaked.md").write_text("outside", encoding="utf-8")
        original_scandir = os.scandir
        replaced = False

        def replace_before_path_scan(path):
            nonlocal replaced
            if not replaced and isinstance(path, (str, Path)) and Path(path) == replaced_directory:
                shutil.rmtree(replaced_directory)
                replaced_directory.symlink_to(outside, target_is_directory=True)
                replaced = True
            return original_scandir(path)

        with patch("migration_manager.os.scandir", side_effect=replace_before_path_scan):
            preview = preview_fixture(legacy, tmp_path)

        assert f"{OFFICIAL_PACK_NAME}/nested/leaked.md" not in {item["name"] for item in preview["files"]}


def test_preview_counts_source_replacement_as_excluded() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        paths = make_paths(tmp_path)
        sources = detect_legacy_sources([legacy], paths)
        study_source = next(source for source in sources if source.kind == "study-packs")
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "leaked.md").write_text("outside", encoding="utf-8")
        shutil.rmtree(study_source.source)
        study_source.source.symlink_to(outside, target_is_directory=True)

        preview = build_migration_preview(sources)

        study = next(item for item in preview["items"] if item["kind"] == "study-packs")
        assert study["totalFiles"] == 0
        assert study["excludedCount"] == 1
        assert "leaked.md" not in {item["name"] for item in preview["files"]}


def test_preview_counts_files_that_disappear_during_walk() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        photo = legacy / "data/person-photos/person.png"
        original_open = os.open
        removed = False

        def remove_before_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal removed
            if not removed and path == "person.png":
                photo.unlink()
                removed = True
            return original_open(path, flags, mode, dir_fd=dir_fd)

        with patch("migration_manager.os.open", side_effect=remove_before_open):
            preview = preview_fixture(legacy, tmp_path)

        assert "person.png" not in {item["name"] for item in preview["files"]}
        assert preview["errorCount"] >= 1


def test_preview_counts_permission_changes_without_error_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        original_open = os.open

        def deny_photo_open(path, flags, mode=0o777, *, dir_fd=None):
            if path == "person.png":
                raise PermissionError("permission changed")
            return original_open(path, flags, mode, dir_fd=dir_fd)

        with patch("migration_manager.os.open", side_effect=deny_photo_open):
            preview = preview_fixture(legacy, tmp_path)

        assert "person.png" not in {item["name"] for item in preview["files"]}
        assert preview["errorCount"] >= 1
        assert all("error" not in item for item in preview["files"])


def test_preview_id_is_deterministic_and_bound_to_verified_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        same_preview = build_migration_preview(detect_legacy_sources([legacy], paths))

        assert preview["previewId"] == same_preview["previewId"]
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        source.write_bytes(source.read_bytes() + b"changed")
        changed_preview = build_migration_preview(detect_legacy_sources([legacy], paths))
        assert changed_preview["previewId"] != preview["previewId"]


def test_apply_copies_only_after_explicit_exact_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        source_hash = file_sha256(source)

        result = apply_migration(preview["previewId"], ["knowledge"], paths)

        assert result["status"] == "completed"
        assert result["approvedItems"] == ["knowledge"]
        assert file_sha256(paths.knowledge_db) == source_hash
        assert file_sha256(source) == source_hash
        assert not paths.context_db.exists()
        assert not paths.contracts_db.exists()


def test_apply_copies_latest_legacy_wal_commit_while_writer_is_open() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, _preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        writer = sqlite3.connect(source)
        try:
            assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == (
                "wal",
            )
            writer.execute(
                "UPDATE sample SET value = 'legacy-wal-latest'"
            )
            writer.commit()
            assert source.with_name(f"{source.name}-wal").stat().st_size > 0

            preview = build_migration_preview(
                detect_legacy_sources([legacy], paths)
            )
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )

            assert result["status"] == "completed"
            assert read_sample_value(paths.knowledge_db) == (
                "legacy-wal-latest"
            )
            assert read_sample_value(source) == "legacy-wal-latest"
        finally:
            writer.close()


def test_legacy_wal_only_commit_invalidates_existing_preview() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, _preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        writer = sqlite3.connect(source)
        try:
            assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == (
                "wal",
            )
            preview = build_migration_preview(
                detect_legacy_sources([legacy], paths)
            )
            main_hash = file_sha256(source)
            writer.execute(
                "UPDATE sample SET value = 'newer-wal-preview'"
            )
            writer.commit()
            assert file_sha256(source) == main_hash

            changed = build_migration_preview(
                detect_legacy_sources([legacy], paths)
            )

            assert changed["previewId"] != preview["previewId"]
            raises(
                MigrationPreviewStaleError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )
            assert not paths.root.exists()
        finally:
            writer.close()


def test_apply_blocks_legacy_commit_after_staging_backup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        make_sqlite_database(paths.knowledge_db, "current")
        current_before = paths.knowledge_db.read_bytes()
        attempt: tuple[str, str] | None = None

        def commit_after_backup(point: str, kind: str) -> None:
            nonlocal attempt
            if (
                point == "after_staging_backup"
                and kind == "knowledge"
                and attempt is None
            ):
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(source, "legacy-after-backup", results),
                )
                writer.start()
                attempt = results.get(timeout=10)
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=commit_after_backup,
        ):
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )

        assert result["status"] == "completed"
        assert attempt is not None and attempt[0] == "blocked", attempt
        assert read_sample_value(source) == "legacy"
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert paths.knowledge_db.read_bytes() != current_before
        assert not list(
            paths.knowledge_db.parent.glob(".*.tomos-stage-*")
        )
        assert not list(paths.migration.glob("journals/*.json"))
        assert len(
            list(paths.migration.glob("snapshots/*.json"))
        ) == 1


def test_apply_blocks_wal_only_commit_after_staging_backup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        make_sqlite_database(paths.knowledge_db, "current")
        current_before = paths.knowledge_db.read_bytes()
        writer = sqlite3.connect(source)
        attempt: tuple[str, str] | None = None
        try:
            assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == (
                "wal",
            )
            writer.execute(
                "UPDATE sample SET value = 'wal-before-backup'"
            )
            writer.commit()
            assert source.with_name(
                f"{source.name}-wal"
            ).stat().st_size > 0
            preview = build_migration_preview(
                detect_legacy_sources([legacy], paths)
            )
            main_hash = file_sha256(source)

            def commit_after_backup(point: str, kind: str) -> None:
                nonlocal attempt
                if (
                    point == "after_staging_backup"
                    and kind == "knowledge"
                    and attempt is None
                ):
                    context = multiprocessing.get_context("spawn")
                    results = context.Queue()
                    process = context.Process(
                        target=legacy_sqlite_writer_attempt,
                        args=(source, "wal-after-backup", results),
                    )
                    process.start()
                    attempt = results.get(timeout=10)
                    process.join(timeout=10)
                    assert process.exitcode == 0

            with patch(
                "migration_manager._fault_injection",
                side_effect=commit_after_backup,
            ):
                result = apply_migration(
                    preview["previewId"], ["knowledge"], paths
                )

            assert result["status"] == "completed"
            assert attempt is not None and attempt[0] == "blocked", attempt
            assert file_sha256(source) == main_hash
            assert read_sample_value(source) == "wal-before-backup"
            assert read_sample_value(paths.knowledge_db) == (
                "wal-before-backup"
            )
            assert paths.knowledge_db.read_bytes() != current_before
            assert not list(
                paths.knowledge_db.parent.glob(".*.tomos-stage-*")
            )
            assert not list(paths.migration.glob("journals/*.json"))
            assert len(
                list(paths.migration.glob("snapshots/*.json"))
            ) == 1
        finally:
            writer.close()


def test_stale_legacy_source_keeps_existing_wal_destination_unchanged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        make_sqlite_database(paths.knowledge_db, "current")
        current = sqlite3.connect(paths.knowledge_db)
        source_writer = sqlite3.connect(source)
        changed = False
        try:
            assert current.execute("PRAGMA journal_mode = WAL").fetchone() == (
                "wal",
            )
            current.execute(
                "UPDATE sample SET value = 'current-wal-state'"
            )
            current.commit()
            current_wal = paths.knowledge_db.with_name(
                f"{paths.knowledge_db.name}-wal"
            )
            assert current_wal.stat().st_size > 0
            before_main = paths.knowledge_db.read_bytes()
            before_wal = current_wal.read_bytes()

            def change_source_before_lock(point: str, kind: str) -> None:
                nonlocal changed
                if (
                    point == "before_apply_journal"
                    and kind == "maintenance"
                    and not changed
                ):
                    source_writer.execute(
                        "UPDATE sample SET value = 'stale-before-lock'"
                    )
                    source_writer.commit()
                    changed = True

            with patch(
                "migration_manager._fault_injection",
                side_effect=change_source_before_lock,
            ):
                raises(
                    MigrationPreviewStaleError,
                    lambda: apply_migration(
                        preview["previewId"], ["knowledge"], paths
                    ),
                )

            assert changed is True
            assert current.execute("PRAGMA journal_mode").fetchone() == (
                "wal",
            )
            assert current.execute(
                "SELECT value FROM sample"
            ).fetchone() == ("current-wal-state",)
            assert paths.knowledge_db.read_bytes() == before_main
            assert current_wal.read_bytes() == before_wal
            assert not list(paths.migration.glob("journals/*.json"))
            assert not list(
                paths.knowledge_db.parent.glob(".*.tomos-snapshot-*")
            )
        finally:
            source_writer.close()
            current.close()


def test_wal_current_is_byte_exact_after_snapshot_pending_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        context = multiprocessing.get_context("fork")
        process = context.Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-wal"] is not None
        original_write = migration_manager._write_new_file_at

        def fail_snapshot(parent_fd: int, name: str, payload: bytes) -> None:
            if ".tomos-snapshot-" in name:
                raise OSError("snapshot write failed")
            original_write(parent_fd, name, payload)

        with patch(
            "migration_manager._write_new_file_at",
            side_effect=fail_snapshot,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert_sqlite_wal_physical_state(paths.knowledge_db, before)


def test_wal_current_is_byte_exact_after_apply_publish_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        context = multiprocessing.get_context("fork")
        process = context.Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-wal"] is not None

        def fail_after_publish(point: str, kind: str) -> None:
            if point == "after_publish" and kind == "knowledge":
                raise OSError("publish failed")

        with patch(
            "migration_manager._fault_injection",
            side_effect=fail_after_publish,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert_sqlite_wal_physical_state(paths.knowledge_db, before)


def test_wal_current_is_byte_exact_after_completion_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        context = multiprocessing.get_context("fork")
        process = context.Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-wal"] is not None
        original_write = migration_manager._write_record
        failed = False

        def fail_completion(path: Path, payload: dict) -> None:
            nonlocal failed
            if path.parent.name == "records" and not failed:
                failed = True
                raise OSError("completion failed")
            original_write(path, payload)

        with patch(
            "migration_manager._write_record",
            side_effect=fail_completion,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert_sqlite_wal_physical_state(paths.knowledge_db, before)


def test_apply_never_overwrites_external_commit_after_physical_backup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        committed_state: dict[str, bytes | None] | None = None
        committed = False

        def commit_before_ownership(point: str, kind: str) -> None:
            nonlocal committed, committed_state
            if (
                point == "before_publish"
                and kind == "knowledge"
                and not committed
            ):
                writer = sqlite3.connect(paths.knowledge_db)
                try:
                    writer.execute(
                        "UPDATE sample SET value = 'external-after-backup'"
                    )
                    writer.commit()
                finally:
                    writer.close()
                committed_state = sqlite_physical_state(paths.knowledge_db)
                committed = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=commit_before_ownership,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert committed is True
        assert committed_state is not None
        assert read_sample_value(paths.knowledge_db) == (
            "external-after-backup"
        )
        assert sqlite_physical_state(paths.knowledge_db) == committed_state
        assert list(paths.migration.glob("journals/*.json"))
        assert list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*"
            )
        )


def test_rollback_never_overwrites_external_commit_after_physical_backup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "pre-migration")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        committed_state: dict[str, bytes | None] | None = None
        committed = False

        def commit_before_ownership(point: str, kind: str) -> None:
            nonlocal committed, committed_state
            if (
                point == "before_rollback_replace"
                and kind == "knowledge"
                and not committed
            ):
                writer = sqlite3.connect(paths.knowledge_db)
                try:
                    writer.execute(
                        "UPDATE sample SET value = "
                        "'external-before-rollback'"
                    )
                    writer.commit()
                finally:
                    writer.close()
                committed_state = sqlite_physical_state(paths.knowledge_db)
                committed = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=commit_before_ownership,
        ):
            raises(
                MigrationValidationError,
                lambda: rollback_migration(
                    result["snapshotId"], paths
                ),
            )

        assert committed is True
        assert committed_state is not None
        assert read_sample_value(paths.knowledge_db) == (
            "external-before-rollback"
        )
        assert sqlite_physical_state(paths.knowledge_db) == committed_state
        assert list(paths.migration.glob("journals/*.json"))
        assert list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-rollback-current-*"
            )
        )


def test_new_only_apply_atomically_refuses_external_sqlite_after_absence_check() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        context = multiprocessing.get_context("spawn")
        ready = context.Queue()
        release = context.Event()
        external = None
        external_before: dict[str, bytes | None] | None = None

        def create_after_absence_check(point: str, kind: str) -> None:
            nonlocal external, external_before
            if (
                point == "after_staging_backup"
                and kind == "knowledge"
                and external is None
            ):
                external = context.Process(
                    target=create_external_wal_database_worker,
                    args=(
                        paths.knowledge_db,
                        "external-after-absence",
                        ready,
                        release,
                    ),
                )
                external.start()
                response = ready.get(timeout=10)
                assert response == (
                    "ready",
                    "external-after-absence",
                ), response
                external_before = sqlite_physical_state(
                    paths.knowledge_db
                )
                assert external_before["main"] is not None
                assert external_before["-wal"] is not None
                assert external_before["-shm"] is not None

        try:
            with patch(
                "migration_manager._fault_injection",
                side_effect=create_after_absence_check,
            ):
                raises(
                    MigrationValidationError,
                    lambda: apply_migration(
                        preview["previewId"],
                        ["knowledge"],
                        paths,
                    ),
                )

            assert external is not None
            assert external_before is not None
            assert (
                sqlite_physical_state(paths.knowledge_db)
                == external_before
            )
            assert read_sample_value(paths.knowledge_db) == (
                "external-after-absence"
            )
            assert not list(
                paths.migration.glob("journals/*.json")
            )
        finally:
            release.set()
            if external is not None:
                external.join(timeout=10)
                assert external.exitcode == 0


def test_new_only_apply_refuses_preexisting_sidecars_without_main() -> None:
    cases = (
        ("-wal",),
        ("-shm",),
        ("-journal",),
        ("-wal", "-shm", "-journal"),
    )
    for suffixes in cases:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)
            paths.knowledge_db.parent.mkdir(parents=True, exist_ok=True)
            expected: dict[str, bytes] = {}
            for suffix in suffixes:
                payload = f"external{suffix}".encode("utf-8")
                sidecar = paths.knowledge_db.with_name(
                    f"{paths.knowledge_db.name}{suffix}"
                )
                sidecar.write_bytes(payload)
                expected[suffix] = payload

            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

            state = sqlite_physical_state(paths.knowledge_db)
            assert state["main"] is None
            for suffix, payload in expected.items():
                assert state[suffix] == payload
            assert not list(paths.migration.glob("journals/*.json"))


def test_new_only_apply_refuses_sidecars_appearing_after_main_link() -> None:
    cases = (
        ("-wal",),
        ("-shm",),
        ("-journal",),
        ("-wal", "-shm", "-journal"),
    )
    for suffixes in cases:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)
            expected: dict[str, bytes] = {}

            def add_sidecars_after_main(point: str, kind: str) -> None:
                if (
                    point == "after_sqlite_main_publish"
                    and kind == paths.knowledge_db.name
                    and not expected
                ):
                    for suffix in suffixes:
                        payload = f"external{suffix}".encode("utf-8")
                        sidecar = paths.knowledge_db.with_name(
                            f"{paths.knowledge_db.name}{suffix}"
                        )
                        sidecar.write_bytes(payload)
                        expected[suffix] = payload

            with patch(
                "migration_manager._fault_injection",
                side_effect=add_sidecars_after_main,
            ):
                raises(
                    MigrationValidationError,
                    lambda: apply_migration(
                        preview["previewId"], ["knowledge"], paths
                    ),
                )

            state = sqlite_physical_state(paths.knowledge_db)
            assert state["main"] is not None
            for suffix, payload in expected.items():
                assert state[suffix] == payload
            assert list(paths.migration.glob("journals/*.json"))
            assert list(
                paths.knowledge_db.parent.glob(".*.tomos-stage-*")
            )


def test_new_only_apply_main_crash_preserves_same_logical_external_wal_bundle() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        def crash_after_main(point: str, kind: str) -> None:
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_main,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        external = sqlite3.connect(paths.knowledge_db)
        try:
            assert external.execute(
                "PRAGMA journal_mode = WAL"
            ).fetchone() == ("wal",)
            external.execute(
                "UPDATE sample SET value = value"
            )
            external.commit()
            external_before = sqlite_physical_state(
                paths.knowledge_db
            )
            assert external_before["-wal"] is not None
            assert external_before["-shm"] is not None

            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )

            assert (
                sqlite_physical_state(paths.knowledge_db)
                == external_before
            )
            assert external.execute(
                "SELECT value FROM sample"
            ).fetchone() == ("legacy",)
            assert list(paths.migration.glob("journals/*.json"))
        finally:
            external.close()


def test_new_only_apply_recovery_quarantines_before_full_bundle_removal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        def crash_after_main(point: str, kind: str) -> None:
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_main,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        def crash_after_quarantine(point: str, kind: str) -> None:
            if (
                point == "after_new_only_sqlite_quarantine"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_quarantine,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: recover_migrations(paths),
            )

        assert paths.knowledge_db.is_file()
        assert list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*.displaced"
            )
        )
        recover_migrations(paths)

        assert sqlite_physical_state(paths.knowledge_db) == {
            "main": None,
            "-wal": None,
            "-shm": None,
            "-journal": None,
        }
        assert not list(paths.migration.glob("journals/*.json"))
        assert not list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*"
            )
        )
        assert not list(
            paths.knowledge_db.parent.glob(".*.tomos-stage-*")
        )


def test_new_only_link_crash_without_durable_phase_safely_stops() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        original_write_journal = migration_manager._write_journal
        crashed = False

        def crash_before_component_phase_is_durable(
            target_paths: TomosPaths, journal: dict
        ) -> None:
            nonlocal crashed
            item = journal["items"][0]
            if (
                item.get("sqliteComponentPhase")
                == "main_published"
                and not item["hadDestination"]
                and not crashed
            ):
                crashed = True
                raise SimulatedProcessCrash()
            original_write_journal(target_paths, journal)

        with patch(
            "migration_manager._write_journal",
            side_effect=crash_before_component_phase_is_durable,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert crashed is True
        staging = next(
            paths.knowledge_db.parent.glob(".*.tomos-stage-*")
        )
        destination_stat = paths.knowledge_db.stat()
        staging_stat = staging.stat()
        assert (
            destination_stat.st_dev,
            destination_stat.st_ino,
        ) == (staging_stat.st_dev, staging_stat.st_ino)

        raises(
            MigrationValidationError,
            lambda: recover_migrations(paths),
        )

        assert paths.knowledge_db.exists()
        assert staging.exists()
        assert list(paths.migration.glob("journals/*.json"))


def test_new_only_anchor_survives_until_committed_cleanup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        with patch(
            "migration_manager._resume_apply_cleanup",
            side_effect=SimulatedProcessCrash(),
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        staging = next(
            paths.knowledge_db.parent.glob(".*.tomos-stage-*")
        )
        assert (
            paths.knowledge_db.stat().st_dev,
            paths.knowledge_db.stat().st_ino,
        ) == (staging.stat().st_dev, staging.stat().st_ino)
        journal_path = next(paths.migration.glob("journals/*.json"))
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal["state"] == "committed"

        recover_migrations(paths)

        assert paths.knowledge_db.is_file()
        assert not staging.exists()
        assert not list(paths.migration.glob("journals/*.json"))


def test_new_only_recovery_requires_persistent_matching_anchor() -> None:
    for mode in ("missing", "different", "same-bytes-different-inode"):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)

            def crash_after_main(point: str, kind: str) -> None:
                if (
                    point == "after_sqlite_main_publish"
                    and kind == paths.knowledge_db.name
                ):
                    raise SimulatedProcessCrash()

            with patch(
                "migration_manager._fault_injection",
                side_effect=crash_after_main,
            ):
                raises(
                    SimulatedProcessCrash,
                    lambda: apply_migration(
                        preview["previewId"], ["knowledge"], paths
                    ),
                )

            staging = next(
                paths.knowledge_db.parent.glob(".*.tomos-stage-*")
            )
            destination_before = paths.knowledge_db.read_bytes()
            if mode == "missing":
                staging.unlink()
            elif mode == "different":
                staging.unlink()
                staging.write_bytes(b"external-anchor")
            else:
                replacement = staging.with_name(f"{staging.name}.replacement")
                replacement.write_bytes(destination_before)
                os.replace(replacement, paths.knowledge_db)
                assert (
                    paths.knowledge_db.stat().st_dev,
                    paths.knowledge_db.stat().st_ino,
                ) != (staging.stat().st_dev, staging.stat().st_ino)

            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )

            assert paths.knowledge_db.read_bytes() == destination_before
            if mode == "different":
                assert staging.read_bytes() == b"external-anchor"
            assert list(paths.migration.glob("journals/*.json"))


def test_new_only_external_staging_hardlink_is_not_owned_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        original_link = os.link
        linked_externally = False

        def external_link_before_migration_link(
            source: str,
            destination: str,
            *,
            src_dir_fd: int,
            dst_dir_fd: int,
            follow_symlinks: bool,
        ) -> None:
            nonlocal linked_externally
            if (
                not linked_externally
                and ".tomos-stage-" in source
                and destination == paths.knowledge_db.name
            ):
                linked_externally = True
                original_link(
                    source,
                    destination,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                    follow_symlinks=follow_symlinks,
                )
            original_link(
                source,
                destination,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=dst_dir_fd,
                follow_symlinks=follow_symlinks,
            )

        with patch(
            "migration_manager.os.link",
            side_effect=external_link_before_migration_link,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert linked_externally is True
        staging = next(
            paths.knowledge_db.parent.glob(".*.tomos-stage-*")
        )
        assert paths.knowledge_db.is_file()
        assert (
            paths.knowledge_db.stat().st_dev,
            paths.knowledge_db.stat().st_ino,
        ) == (staging.stat().st_dev, staging.stat().st_ino)
        assert list(paths.migration.glob("journals/*.json"))


def test_new_only_recovery_keeps_writer_locked_through_cleanup_journal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        def crash_after_main(point: str, kind: str) -> None:
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_main,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        attempts: dict[str, tuple[str, str]] = {}

        def attempt_writer_while_recovering(
            point: str, kind: str
        ) -> None:
            if (
                point != "after_new_only_sqlite_quarantine"
                or kind != paths.knowledge_db.name
                or point in attempts
            ):
                return
            context = multiprocessing.get_context("spawn")
            results = context.Queue()
            writer = context.Process(
                target=legacy_sqlite_writer_attempt,
                args=(
                    paths.knowledge_db,
                    f"external-{point}",
                    results,
                ),
            )
            writer.start()
            attempts[point] = results.get(timeout=10)
            writer.join(timeout=10)
            assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=attempt_writer_while_recovering,
        ):
            recover_migrations(paths)

        assert attempts == {
            "after_new_only_sqlite_quarantine": (
                "blocked",
                "database is locked",
            ),
        }, attempts
        assert not paths.knowledge_db.exists()
        assert not list(paths.migration.glob("journals/*.json"))


def test_new_only_recovery_retains_waiting_fd_update_after_unlock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        def crash_after_main(point: str, kind: str) -> None:
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_main,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        context = multiprocessing.get_context("spawn")
        blocked = context.Event()
        acquired = context.Event()
        fsynced = context.Event()
        results = context.Queue()
        writer = None
        checkpoints: list[str] = []

        def observe_waiting_writer(point: str, kind: str) -> None:
            nonlocal writer
            if kind != paths.knowledge_db.name:
                return
            if point == "after_new_only_sqlite_quarantine":
                writer = context.Process(
                    target=waiting_fd_fsync_after_unlink_worker,
                    args=(
                        paths.knowledge_db,
                        blocked,
                        acquired,
                        fsynced,
                        results,
                    ),
                )
                writer.start()
                assert blocked.wait(timeout=10)
            if point in {
                "after_new_only_sqlite_quarantine",
                "after_new_only_sqlite_recovery_journal",
                "after_new_only_sqlite_destination_unlink",
                "after_new_only_sqlite_staging_cleanup_before_unlock",
            }:
                assert acquired.is_set() is False
                assert fsynced.is_set() is False
                checkpoints.append(point)

        with patch(
            "migration_manager._fault_injection",
            side_effect=observe_waiting_writer,
        ):
            recover_migrations(paths)

        assert writer is not None
        writer.join(timeout=10)
        assert writer.exitcode == 0
        assert acquired.is_set() is True
        assert fsynced.is_set() is True
        status, link_count, user_version = results.get(timeout=10)
        assert status == "fsynced"
        assert link_count >= 1
        assert user_version == 20_260_728
        assert checkpoints == [
            "after_new_only_sqlite_quarantine",
            "after_new_only_sqlite_destination_unlink",
            "after_new_only_sqlite_recovery_journal",
            "after_new_only_sqlite_staging_cleanup_before_unlock",
        ]
        _record_path, _record, guard = retained_external_write_guard(paths)
        connection = sqlite3.connect(
            f"{guard.resolve().as_uri()}?mode=ro", uri=True
        )
        try:
            assert connection.execute(
                "PRAGMA user_version"
            ).fetchone() == (20_260_728,)
            assert connection.execute(
                "PRAGMA quick_check"
            ).fetchall() == [("ok",)]
        finally:
            connection.close()
        assert read_sample_value(guard) == "legacy"
        assert not paths.knowledge_db.exists()
        assert not list(paths.migration.glob("journals/*.json"))


def test_new_only_recovery_same_sqlite_connection_fails_explicitly_if_moved() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths, _staging = leave_new_only_main_publish_crash(Path(tmp))
        context = multiprocessing.get_context("spawn")
        opened = context.Event()
        attempting = context.Event()
        results = context.Queue()
        writer = None

        def start_waiting_sqlite_connection(
            point: str, kind: str
        ) -> None:
            nonlocal writer
            if (
                point != "after_new_only_sqlite_quarantine"
                or kind != paths.knowledge_db.name
                or writer is not None
            ):
                return
            writer = context.Process(
                target=waiting_sqlite_connection_after_unlink_worker,
                args=(
                    paths.knowledge_db,
                    opened,
                    attempting,
                    results,
                ),
            )
            writer.start()
            assert opened.wait(timeout=10)
            assert attempting.wait(timeout=10)

        with patch(
            "migration_manager._fault_injection",
            side_effect=start_waiting_sqlite_connection,
        ):
            recover_migrations(paths)

        assert writer is not None
        writer.join(timeout=20)
        assert writer.exitcode == 0
        result = results.get(timeout=10)
        assert result[0] == "error", result
        assert result[1] == sqlite3.SQLITE_READONLY_DBMOVED, result
        assert result[2] == "SQLITE_READONLY_DBMOVED", result
        assert "readonly" in result[3].lower(), result
        _record_path, _record, guard = retained_external_write_guard(paths)
        assert read_sample_value(guard) == "legacy"
        assert not paths.knowledge_db.exists()


def test_new_only_recovery_resumes_after_each_sidecar_anchor_unlink() -> None:
    for crash_key in ("wal", "shm", "journal"):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)

            def crash_after_main(point: str, kind: str) -> None:
                if (
                    point == "after_sqlite_main_publish"
                    and kind == paths.knowledge_db.name
                ):
                    raise SimulatedProcessCrash()

            with patch(
                "migration_manager._fault_injection",
                side_effect=crash_after_main,
            ):
                raises(
                    SimulatedProcessCrash,
                    lambda: apply_migration(
                        preview["previewId"], ["knowledge"], paths
                    ),
                )

            staging = next(
                paths.knowledge_db.parent.glob(".*.tomos-stage-*")
            )
            add_complete_wal_staging_bundle(
                paths,
                staging,
                f"retained-crash-{crash_key}",
            )

            def crash_after_sidecar_anchor(
                point: str, kind: str
            ) -> None:
                if (
                    point
                    == f"after_new_only_sqlite_staging_{crash_key}_unlink"
                    and kind == paths.knowledge_db.name
                ):
                    raise SimulatedProcessCrash()

            with patch(
                "migration_manager._fault_injection",
                side_effect=crash_after_sidecar_anchor,
            ):
                raises(
                    SimulatedProcessCrash,
                    lambda: recover_migrations(paths),
                )

            assert not paths.knowledge_db.exists()
            assert staging.exists()
            recover_migrations(paths)

            assert not staging.exists()
            assert not any(
                staging.with_name(
                    f"{staging.name}{suffix}"
                ).exists()
                for suffix in ("-wal", "-shm", "-journal")
            )
            assert not list(paths.migration.glob("journals/*.json"))


def test_new_only_recovery_resumes_after_destination_unlink_before_journal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        def crash_after_main(point: str, kind: str) -> None:
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_main,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        def crash_after_destination_unlink(
            point: str, kind: str
        ) -> None:
            if (
                point == "after_new_only_sqlite_destination_unlink"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_destination_unlink,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: recover_migrations(paths),
            )

        staging = next(
            paths.knowledge_db.parent.glob(".*.tomos-stage-*")
        )
        assert not paths.knowledge_db.exists()
        assert staging.exists()
        assert list(paths.migration.glob("journals/*.json"))

        recover_migrations(paths)

        assert not staging.exists()
        assert not list(paths.migration.glob("journals/*.json"))


def test_new_only_current_missing_full_anchor_becomes_reachable_guard() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths, staging = leave_new_only_main_publish_crash(Path(tmp))
        add_complete_wal_staging_bundle(
            paths, staging, "retained-full-bundle"
        )
        crash_new_only_recovery_after_destination_unlink(paths)

        recover_migrations(paths)

        record_path, record, guard = retained_external_write_guard(paths)
        assert record_path.is_file()
        assert record["initialLogicalDigest"]["type"] == "file"
        assert set(record["componentIdentities"]) == {
            "main",
            "wal",
            "shm",
            "journal",
        }
        assert (
            migration_manager
            ._validate_retained_external_write_guard_record(record)
            == record
        )
        tampered_record = json.loads(json.dumps(record))
        tampered_record["path"] = str(guard)
        raises(
            MigrationValidationError,
            lambda: migration_manager
            ._validate_retained_external_write_guard_record(
                tampered_record
            ),
        )
        assert not paths.knowledge_db.exists()
        assert not staging.exists()
        assert all(
            guard.with_name(
                f"{guard.name}{suffix}"
            ).is_file()
            for suffix in ("", "-wal", "-shm", "-journal")
        )
        assert read_sample_value(guard) == "retained-full-bundle"
        guard_state = sqlite_physical_state(guard)
        assert all(value is not None for value in guard_state.values())
        serialized = record_path.read_text(encoding="utf-8").lower()
        assert all(
            forbidden not in serialized
            for forbidden in ('"path"', '"content"', '"text"', '"token"')
        )

        assert recover_migrations(paths) == {
            "status": "recovered",
            "cleanupPending": False,
        }
        prepare_managed_data_startup(paths)
        assert sqlite_physical_state(guard) == guard_state

        with managed_data_write(paths):
            make_sqlite_database(paths.knowledge_db, "new-managed")
        assert read_sample_value(paths.knowledge_db) == "new-managed"
        assert read_sample_value(guard) == "retained-full-bundle"
        assert sqlite_physical_state(guard) == guard_state


def test_new_only_current_missing_requires_full_original_anchor_bundle() -> None:
    for mode in ("missing", "partial", "replaced"):
        with tempfile.TemporaryDirectory() as tmp:
            paths, staging = leave_new_only_main_publish_crash(Path(tmp))
            add_complete_wal_staging_bundle(
                paths, staging, f"retained-{mode}"
            )
            journal_path, quarantine = (
                crash_new_only_recovery_after_destination_unlink(paths)
            )
            quarantine_before = sqlite_physical_state(quarantine)

            if mode == "missing":
                for suffix in ("", "-wal", "-shm", "-journal"):
                    component = staging.with_name(
                        f"{staging.name}{suffix}"
                    )
                    if component.exists():
                        component.unlink()
            elif mode == "partial":
                staging.with_name(f"{staging.name}-journal").unlink()
            else:
                replacement = staging.with_name(
                    f"{staging.name}.replacement"
                )
                shutil.copyfile(staging, replacement)
                os.replace(replacement, staging)

            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )

            assert not paths.knowledge_db.exists()
            assert journal_path.is_file()
            assert sqlite_physical_state(quarantine) == quarantine_before
            assert not list(
                (
                    paths.migration
                    / "retained-external-write-guards"
                ).glob("*.json")
            )
            if mode == "partial":
                assert staging.is_file()
                assert not staging.with_name(
                    f"{staging.name}-journal"
                ).exists()
            elif mode == "replaced":
                assert staging.is_file()


def test_new_only_recovery_resumes_after_staging_cleanup_before_unlock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        def crash_after_main(point: str, kind: str) -> None:
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_main,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        def crash_after_staging_cleanup(
            point: str, kind: str
        ) -> None:
            if (
                point
                == "after_new_only_sqlite_staging_cleanup_before_unlock"
                and kind == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_staging_cleanup,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: recover_migrations(paths),
            )

        assert not paths.knowledge_db.exists()
        assert not list(
            paths.knowledge_db.parent.glob(".*.tomos-stage-*")
        )
        assert list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*.displaced"
            )
        )
        assert list(paths.migration.glob("journals/*.json"))

        recover_migrations(paths)

        assert not list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*"
            )
        )
        assert not list(paths.migration.glob("journals/*.json"))


def test_new_only_recovery_rejects_existing_quarantine_hardlink() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths, quarantine = leave_new_only_quarantine_fixture(Path(tmp))
        destination_before = sqlite_physical_state(paths.knowledge_db)
        original_write_journal = migration_manager._write_journal
        swapped = False

        def install_hardlink_before_recovery_lock(
            target_paths: TomosPaths, journal: dict
        ) -> None:
            nonlocal swapped
            original_write_journal(target_paths, journal)
            if journal["state"] == "recovering" and not swapped:
                quarantine.unlink()
                os.link(paths.knowledge_db, quarantine)
                swapped = True

        with patch(
            "migration_manager._write_journal",
            side_effect=install_hardlink_before_recovery_lock,
        ):
            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )

        assert swapped is True
        assert (
            paths.knowledge_db.stat().st_dev,
            paths.knowledge_db.stat().st_ino,
        ) == (quarantine.stat().st_dev, quarantine.stat().st_ino)
        assert sqlite_physical_state(paths.knowledge_db) == (
            destination_before
        )
        assert list(paths.migration.glob("journals/*.json"))


def test_new_only_recovery_detects_quarantine_swap_after_current_lock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths, quarantine = leave_new_only_quarantine_fixture(Path(tmp))
        destination_before = sqlite_physical_state(paths.knowledge_db)
        swapped = False

        def swap_after_current_lock(point: str, kind: str) -> None:
            nonlocal swapped
            if (
                point == "after_new_only_sqlite_current_lock"
                and kind == paths.knowledge_db.name
                and not swapped
            ):
                quarantine.unlink()
                os.link(paths.knowledge_db, quarantine)
                swapped = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=swap_after_current_lock,
        ):
            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )

        assert swapped is True
        assert (
            paths.knowledge_db.stat().st_dev,
            paths.knowledge_db.stat().st_ino,
        ) == (quarantine.stat().st_dev, quarantine.stat().st_ino)
        assert sqlite_physical_state(paths.knowledge_db) == (
            destination_before
        )
        assert list(paths.migration.glob("journals/*.json"))


def test_sqlite_quarantine_all_components_use_distinct_inodes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        current_name = "current.sqlite"
        quarantine_name = "quarantine.sqlite"
        payloads = {
            "": b"main",
            "-wal": b"wal",
            "-shm": b"shm",
            "-journal": b"journal",
        }
        for suffix, payload in payloads.items():
            (directory / f"{current_name}{suffix}").write_bytes(payload)
        parent_fd = os.open(
            directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
        )
        try:
            current_physical = (
                migration_manager._sqlite_physical_digest_at(
                    parent_fd, current_name
                )
            )
            with migration_manager._held_distinct_sqlite_quarantine_at(
                parent_fd,
                current_name,
                quarantine_name,
                current_physical,
                current_physical,
            ) as held_quarantine:
                with migration_manager._held_sqlite_physical_bundle_at(
                    parent_fd, current_name
                ) as held_current:
                    for key in ("main", "wal", "shm", "journal"):
                        current_fd = migration_manager._sqlite_component_fd(
                            held_current, key
                        )
                        quarantine_fd = (
                            migration_manager._sqlite_component_fd(
                                held_quarantine, key
                            )
                        )
                        assert current_fd is not None
                        assert quarantine_fd is not None
                        current_stat = os.fstat(current_fd)
                        quarantine_stat = os.fstat(quarantine_fd)
                        assert (
                            current_stat.st_dev,
                            current_stat.st_ino,
                        ) != (
                            quarantine_stat.st_dev,
                            quarantine_stat.st_ino,
                        )
        finally:
            os.close(parent_fd)


def test_external_writer_is_blocked_after_apply_ownership_marker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        attempt: tuple[str, str] | None = None

        def attempt_after_ownership(point: str, kind: str) -> None:
            nonlocal attempt
            if (
                point == "after_sqlite_ownership"
                and kind == "knowledge"
                and attempt is None
            ):
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(
                        paths.knowledge_db,
                        "external-after-ownership",
                        results,
                    ),
                )
                writer.start()
                attempt = results.get(timeout=10)
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=attempt_after_ownership,
        ):
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )

        assert result["status"] == "completed"
        assert attempt is not None and attempt[0] == "blocked", attempt
        assert read_sample_value(paths.knowledge_db) == "legacy"


def test_external_writer_is_blocked_after_apply_main_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        original_replace = migration_manager._replace_at
        attempt: tuple[str, str] | None = None

        def attempt_after_main_publish(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            nonlocal attempt
            original_replace(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )
            if (
                ".tomos-stage-" in source_name
                and destination_name == paths.knowledge_db.name
                and attempt is None
            ):
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(
                        paths.knowledge_db,
                        "external-after-main-publish",
                        results,
                    ),
                )
                writer.start()
                attempt = results.get(timeout=10)
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._replace_at",
            side_effect=attempt_after_main_publish,
        ):
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )

        assert result["status"] == "completed"
        assert attempt is not None and attempt[0] == "blocked", attempt
        assert read_sample_value(paths.knowledge_db) == "legacy"


def test_external_writer_is_blocked_after_rollback_main_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "pre-migration")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        original_replace = migration_manager._replace_at
        attempt: tuple[str, str] | None = None

        def attempt_after_main_publish(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            nonlocal attempt
            original_replace(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )
            if (
                ".tomos-rollback-restore-" in source_name
                and destination_name == paths.knowledge_db.name
                and attempt is None
            ):
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(
                        paths.knowledge_db,
                        "external-after-rollback-main",
                        results,
                    ),
                )
                writer.start()
                attempt = results.get(timeout=10)
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._replace_at",
            side_effect=attempt_after_main_publish,
        ):
            rollback = rollback_migration(result["snapshotId"], paths)

        assert rollback["status"] == "rolled_back"
        assert attempt is not None and attempt[0] == "blocked", attempt
        assert read_sample_value(paths.knowledge_db) == "pre-migration"


def test_apply_main_publish_crash_recovers_wal_bundle_byte_exact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        process = multiprocessing.get_context("fork").Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-wal"] is not None
        original_replace = migration_manager._replace_at

        def crash_after_main_publish(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            original_replace(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )
            if (
                ".tomos-stage-" in source_name
                and destination_name == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._replace_at",
            side_effect=crash_after_main_publish,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        recover_migrations(paths)

        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == "current-wal"
        assert not list(paths.migration.glob("journals/*.json"))


def test_apply_each_sidecar_cleanup_crash_recovers_byte_exact() -> None:
    for suffix in ("-wal", "-shm"):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)
            make_sqlite_database(paths.knowledge_db, "current")
            process = multiprocessing.get_context("fork").Process(
                target=leave_wal_commit_worker,
                args=(paths.knowledge_db, "current-wal"),
            )
            process.start()
            process.join(timeout=10)
            assert process.exitcode == 0
            before = sqlite_physical_state(paths.knowledge_db)
            assert before[suffix] is not None
            original_unlink = migration_manager.os.unlink
            crashed = False

            def crash_after_component(
                name: str, *args, **kwargs
            ) -> None:
                nonlocal crashed
                original_unlink(name, *args, **kwargs)
                if (
                    name == f"{paths.knowledge_db.name}{suffix}"
                    and not crashed
                ):
                    crashed = True
                    raise SimulatedProcessCrash()

            with patch(
                "migration_manager.os.unlink",
                side_effect=crash_after_component,
            ):
                raises(
                    SimulatedProcessCrash,
                    lambda: apply_migration(
                        preview["previewId"], ["knowledge"], paths
                    ),
                )

            assert crashed is True
            recover_migrations(paths)
            assert sqlite_physical_state(paths.knowledge_db) == before
            assert read_sample_value(paths.knowledge_db) == "current-wal"


def test_apply_recovery_rollback_journal_rename_crash_recovers_byte_exact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database_with_persistent_journal(
            paths.knowledge_db, "current-persist"
        )
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-journal"] is not None
        original_replace = migration_manager._replace_at
        crashed = False

        def crash_after_journal_rename(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            nonlocal crashed
            original_replace(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )
            if (
                ".tomos-apply-current-" in source_name
                and source_name.endswith(".restore-journal")
                and destination_name
                == f"{paths.knowledge_db.name}-journal"
                and not crashed
            ):
                crashed = True
                raise SimulatedProcessCrash()

        def fail_after_publish(point: str, kind: str) -> None:
            if point == "after_publish" and kind == "knowledge":
                raise OSError("force apply recovery")

        with patch(
            "migration_manager._replace_at",
            side_effect=crash_after_journal_rename,
        ), patch(
            "migration_manager._fault_injection",
            side_effect=fail_after_publish,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert crashed is True
        recover_migrations(paths)
        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == (
            "current-persist"
        )


def test_apply_recovery_revalidates_commit_before_current_replace() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")

        def crash_after_publish(point: str, kind: str) -> None:
            if point == "after_publish" and kind == "knowledge":
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_publish,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        original_restore = migration_manager._restore_sqlite_physical_at
        committed_state: dict[str, bytes | None] | None = None
        committed = False

        def commit_before_restore(*args, **kwargs) -> None:
            nonlocal committed, committed_state
            if not committed:
                writer = sqlite3.connect(paths.knowledge_db)
                try:
                    writer.execute(
                        "UPDATE sample SET value = "
                        "'external-during-recovery'"
                    )
                    writer.commit()
                finally:
                    writer.close()
                committed_state = sqlite_physical_state(
                    paths.knowledge_db
                )
                committed = True
            original_restore(*args, **kwargs)

        with patch(
            "migration_manager._restore_sqlite_physical_at",
            side_effect=commit_before_restore,
        ):
            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )

        assert committed is True
        assert committed_state is not None
        assert sqlite_physical_state(paths.knowledge_db) == committed_state
        assert read_sample_value(paths.knowledge_db) == (
            "external-during-recovery"
        )
        assert list(paths.migration.glob("journals/*.json"))


def test_apply_recovery_blocks_writer_after_locked_decision() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before = sqlite_physical_state(paths.knowledge_db)

        def crash_after_publish(point: str, kind: str) -> None:
            if point == "after_publish" and kind == "knowledge":
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_publish,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        attempt: tuple[str, str] | None = None

        def attempt_after_decision(point: str, kind: str) -> None:
            nonlocal attempt
            if (
                point == "after_sqlite_recovery_decision"
                and ".tomos-apply-current-" in kind
                and attempt is None
            ):
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(
                        paths.knowledge_db,
                        "external-after-recovery-decision",
                        results,
                    ),
                )
                writer.start()
                attempt = results.get(timeout=10)
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=attempt_after_decision,
        ):
            recover_migrations(paths)

        assert attempt is not None and attempt[0] == "blocked", attempt
        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == "current"


def test_physical_restore_blocks_writer_after_wal_main_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        process = multiprocessing.get_context("fork").Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        attempt: tuple[str, str] | None = None

        def fail_then_attempt(point: str, kind: str) -> None:
            nonlocal attempt
            if point == "after_publish" and kind == "knowledge":
                raise OSError("force recovery")
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
                and attempt is None
            ):
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(
                        paths.knowledge_db,
                        "external-after-wal-main",
                        results,
                    ),
                )
                writer.start()
                attempt = results.get(timeout=10)
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=fail_then_attempt,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert attempt is not None and attempt[0] == "blocked", attempt
        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == "current-wal"


def test_rollback_main_publish_crash_recovers_wal_bundle_byte_exact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "pre-migration")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        process = multiprocessing.get_context("fork").Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "legacy"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-wal"] is not None
        original_replace = migration_manager._replace_at

        def crash_after_main_publish(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            original_replace(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )
            if (
                ".tomos-rollback-restore-" in source_name
                and destination_name == paths.knowledge_db.name
            ):
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._replace_at",
            side_effect=crash_after_main_publish,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: rollback_migration(
                    result["snapshotId"], paths
                ),
            )

        recover_migrations(paths)

        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert not list(paths.migration.glob("journals/*.json"))


def test_rollback_each_sidecar_cleanup_crash_recovers_byte_exact() -> None:
    for suffix in ("-wal", "-shm"):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)
            make_sqlite_database(paths.knowledge_db, "pre-migration")
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )
            process = multiprocessing.get_context("fork").Process(
                target=leave_wal_commit_worker,
                args=(paths.knowledge_db, "legacy"),
            )
            process.start()
            process.join(timeout=10)
            assert process.exitcode == 0
            before = sqlite_physical_state(paths.knowledge_db)
            assert before[suffix] is not None
            original_unlink = migration_manager.os.unlink
            crashed = False

            def crash_after_component(
                name: str, *args, **kwargs
            ) -> None:
                nonlocal crashed
                original_unlink(name, *args, **kwargs)
                if (
                    name == f"{paths.knowledge_db.name}{suffix}"
                    and not crashed
                ):
                    crashed = True
                    raise SimulatedProcessCrash()

            with patch(
                "migration_manager.os.unlink",
                side_effect=crash_after_component,
            ):
                raises(
                    SimulatedProcessCrash,
                    lambda: rollback_migration(
                        result["snapshotId"], paths
                    ),
                )

            assert crashed is True
            recover_migrations(paths)
            assert sqlite_physical_state(paths.knowledge_db) == before
            assert read_sample_value(paths.knowledge_db) == "legacy"


def test_rollback_journal_cleanup_crash_recovers_byte_exact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "pre-migration")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        connection = sqlite3.connect(paths.knowledge_db)
        try:
            assert connection.execute(
                "PRAGMA journal_mode = PERSIST"
            ).fetchone() == ("persist",)
            connection.execute(
                "UPDATE sample SET value = 'temporary'"
            )
            connection.rollback()
        finally:
            connection.close()
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-journal"] is not None
        original_unlink = migration_manager.os.unlink
        crashed = False

        def crash_after_journal_cleanup(
            name: str, *args, **kwargs
        ) -> None:
            nonlocal crashed
            original_unlink(name, *args, **kwargs)
            if (
                name == f"{paths.knowledge_db.name}-journal"
                and not crashed
            ):
                crashed = True
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager.os.unlink",
            side_effect=crash_after_journal_cleanup,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: rollback_migration(
                    result["snapshotId"], paths
                ),
            )

        assert crashed is True
        recover_migrations(paths)
        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == "legacy"


def test_rollback_recovery_blocks_writer_after_locked_decision() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "pre-migration")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        published = sqlite_physical_state(paths.knowledge_db)

        def crash_after_item(point: str, kind: str) -> None:
            if point == "after_rollback_item" and kind == "knowledge":
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_item,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: rollback_migration(
                    result["snapshotId"], paths
                ),
            )

        attempt: tuple[str, str] | None = None

        def attempt_after_decision(point: str, kind: str) -> None:
            nonlocal attempt
            if (
                point == "after_sqlite_recovery_decision"
                and ".tomos-rollback-current-" in kind
                and attempt is None
            ):
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(
                        paths.knowledge_db,
                        "external-after-rollback-decision",
                        results,
                    ),
                )
                writer.start()
                attempt = results.get(timeout=10)
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=attempt_after_decision,
        ):
            recover_migrations(paths)

        assert attempt is not None and attempt[0] == "blocked", attempt
        assert sqlite_physical_state(paths.knowledge_db) == published
        assert read_sample_value(paths.knowledge_db) == "legacy"


def test_restore_sidecar_swap_after_main_publish_retries_from_quarantine() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        process = multiprocessing.get_context("fork").Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        swapped = False

        def fail_then_swap(point: str, kind: str) -> None:
            nonlocal swapped
            if point == "after_publish" and kind == "knowledge":
                raise OSError("force recovery")
            if (
                point == "after_sqlite_main_publish"
                and kind == paths.knowledge_db.name
                and not swapped
            ):
                restore_wal = next(
                    paths.knowledge_db.parent.glob(
                        ".*.tomos-apply-current-*.restore-wal"
                    )
                )
                replacement = restore_wal.with_name(
                    f"{restore_wal.name}.tampered"
                )
                replacement.write_bytes(b"tampered sidecar")
                os.replace(replacement, restore_wal)
                swapped = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=fail_then_swap,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert swapped is True
        assert list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*.displaced"
            )
        )
        recover_migrations(paths)

        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == "current-wal"


def test_restore_scratch_swap_at_current_handoff_keeps_current() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        swapped = False
        current_before: dict[str, bytes | None] | None = None

        def fail_after_publish(point: str, kind: str) -> None:
            nonlocal swapped, current_before
            if point == "after_publish" and kind == "knowledge":
                raise OSError("force recovery")
            if (
                point == "after_sqlite_restore_final_digest"
                and ".tomos-apply-current-" in kind
                and not swapped
            ):
                current_before = sqlite_physical_state(
                    paths.knowledge_db
                )
                restore = paths.knowledge_db.parent / (
                    f"{kind}.restore"
                )
                make_sqlite_database(restore, "tampered-at-handoff")
                swapped = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=fail_after_publish,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert swapped is True
        assert current_before is not None
        assert sqlite_physical_state(paths.knowledge_db) == current_before
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert list(paths.migration.glob("journals/*.json"))


def test_apply_recovery_rejects_bundle_swap_before_restore_copy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        original_copy = migration_manager._copy_sqlite_physical_at
        swapped = False
        recovery_started = False
        current_before_recovery: dict[str, bytes | None] | None = None

        def swap_bundle_before_restore_copy(
            parent_fd: int,
            source_name: str,
            destination_name: str,
            *args,
            **kwargs,
        ):
            nonlocal swapped, current_before_recovery
            if (
                recovery_started
                and ".tomos-apply-current-" in source_name
                and destination_name.endswith(".restore")
                and not swapped
            ):
                current_before_recovery = sqlite_physical_state(
                    paths.knowledge_db
                )
                make_sqlite_database(
                    paths.knowledge_db.parent / source_name,
                    "swapped-backup",
                )
                swapped = True
            return original_copy(
                parent_fd,
                source_name,
                destination_name,
                *args,
                **kwargs,
            )

        def fail_after_publish(point: str, kind: str) -> None:
            nonlocal recovery_started
            if point == "after_publish" and kind == "knowledge":
                recovery_started = True
                raise OSError("force recovery")

        with patch(
            "migration_manager._copy_sqlite_physical_at",
            side_effect=swap_bundle_before_restore_copy,
        ), patch(
            "migration_manager._fault_injection",
            side_effect=fail_after_publish,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert swapped is True
        assert current_before_recovery is not None
        assert sqlite_physical_state(paths.knowledge_db) == (
            current_before_recovery
        )
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert list(paths.migration.glob("journals/*.json"))


def test_recovery_binds_tampered_bundle_to_original_logical_digest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")

        def crash_after_publish(point: str, kind: str) -> None:
            if point == "after_publish" and kind == "knowledge":
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_publish,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        journal_path = next(paths.migration.glob("journals/*.json"))
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        backup = next(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*"
            )
        )
        make_sqlite_database(backup, "journal-and-bundle-tamper")
        parent_fd = migration_manager._open_directory_chain(
            backup.parent
        )
        try:
            journal["items"][0]["priorPhysicalDigest"] = (
                migration_manager._sqlite_physical_digest_at(
                    parent_fd, backup.name
                )
            )
        finally:
            os.close(parent_fd)
        journal_path.write_text(
            json.dumps(journal, sort_keys=True), encoding="utf-8"
        )
        current_before = sqlite_physical_state(paths.knowledge_db)

        raises(
            MigrationValidationError,
            lambda: recover_migrations(paths),
        )

        assert sqlite_physical_state(paths.knowledge_db) == current_before
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert journal_path.exists()
        assert backup.exists()


def test_restore_copy_swap_is_detected_before_current_removal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        current_before_restore: dict[str, bytes | None] | None = None
        swapped = False

        def fail_then_swap_restore(point: str, kind: str) -> None:
            nonlocal current_before_restore, swapped
            if point == "after_publish" and kind == "knowledge":
                raise OSError("force recovery")
            if (
                point == "before_sqlite_restore_publish"
                and ".tomos-apply-current-" in kind
                and not swapped
            ):
                current_before_restore = sqlite_physical_state(
                    paths.knowledge_db
                )
                restore = paths.knowledge_db.parent / f"{kind}.restore"
                make_sqlite_database(restore, "swapped-restore-copy")
                swapped = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=fail_then_swap_restore,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert swapped is True
        assert current_before_restore is not None
        assert sqlite_physical_state(paths.knowledge_db) == (
            current_before_restore
        )
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert list(paths.migration.glob("journals/*.json"))


def test_physical_copy_detects_source_change_before_restore_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        original_copy_file = migration_manager._copy_open_regular_file_at
        recovery_started = False
        changed = False
        current_before_recovery: dict[str, bytes | None] | None = None

        def change_after_copy(
            parent_fd: int, source_fd: int, destination_name: str
        ):
            nonlocal changed, current_before_recovery
            copied = original_copy_file(
                parent_fd, source_fd, destination_name
            )
            if (
                recovery_started
                and destination_name.endswith(".restore")
                and not changed
            ):
                current_before_recovery = sqlite_physical_state(
                    paths.knowledge_db
                )
                source_path = migration_manager._path_from_fd(source_fd)
                mutation_fd = os.open(source_path, os.O_RDWR)
                try:
                    first = os.read(mutation_fd, 1)
                    os.lseek(mutation_fd, 0, os.SEEK_SET)
                    os.write(mutation_fd, bytes([first[0] ^ 1]))
                    os.fsync(mutation_fd)
                finally:
                    os.close(mutation_fd)
                changed = True
            return copied

        def fail_after_publish(point: str, kind: str) -> None:
            nonlocal recovery_started
            if point == "after_publish" and kind == "knowledge":
                recovery_started = True
                raise OSError("force recovery")

        with patch(
            "migration_manager._copy_open_regular_file_at",
            side_effect=change_after_copy,
        ), patch(
            "migration_manager._fault_injection",
            side_effect=fail_after_publish,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert changed is True
        assert current_before_recovery is not None
        assert sqlite_physical_state(paths.knowledge_db) == (
            current_before_recovery
        )
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert list(paths.migration.glob("journals/*.json"))


def test_physical_restore_retries_after_sidecar_publish_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        context = multiprocessing.get_context("fork")
        process = context.Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-wal"] is not None
        original_replace = migration_manager._replace_at
        failed = False

        def fail_first_restore_sidecar(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            nonlocal failed
            if (
                ".tomos-apply-current-" in source_name
                and source_name.endswith(".restore-wal")
                and not failed
            ):
                failed = True
                raise OSError("restore WAL publish failed")
            original_replace(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )

        def fail_after_publish(point: str, kind: str) -> None:
            if point == "after_publish" and kind == "knowledge":
                raise OSError("force recovery")

        with patch(
            "migration_manager._replace_at",
            side_effect=fail_first_restore_sidecar,
        ), patch(
            "migration_manager._fault_injection",
            side_effect=fail_after_publish,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert failed is True
        journal_path = next(paths.migration.glob("journals/*.json"))
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal["items"][0]["phase"] == "recovery_pending"

        recover_migrations(paths)

        assert sqlite_physical_state(paths.knowledge_db) == before
        assert read_sample_value(paths.knowledge_db) == "current-wal"
        assert not list(paths.migration.glob("journals/*.json"))


def test_legacy_writer_is_blocked_from_final_capture_until_commit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        attempts: list[tuple[str, str]] = []
        attempted = False

        def attempt_during_publish(point: str, kind: str) -> None:
            nonlocal attempted
            if (
                point == "after_staging_backup"
                and kind == "knowledge"
                and not attempted
            ):
                attempted = True
                context = multiprocessing.get_context("spawn")
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(source, "must-wait-for-migration", results),
                )
                writer.start()
                attempts.append(results.get(timeout=10))
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=attempt_during_publish,
        ):
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )

        assert result["status"] == "completed"
        assert attempted is True
        assert attempts and attempts[0][0] == "blocked", attempts
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert read_sample_value(source) == "legacy"


def test_all_legacy_sqlite_writers_stay_blocked_across_multi_item_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        databases = (
            legacy / ".gemma4-data/knowledge/index.sqlite",
            legacy / ".gemma4-data/context/context.sqlite",
        )
        attempts: list[tuple[str, str]] = []
        attempted = False

        def attempt_after_first_publish(point: str, _kind: str) -> None:
            nonlocal attempted
            if point != "after_publish" or attempted:
                return
            attempted = True
            context = multiprocessing.get_context("spawn")
            for index, database in enumerate(databases):
                results = context.Queue()
                writer = context.Process(
                    target=legacy_sqlite_writer_attempt,
                    args=(database, f"late-{index}", results),
                )
                writer.start()
                attempts.append(results.get(timeout=10))
                writer.join(timeout=10)
                assert writer.exitcode == 0

        with patch(
            "migration_manager._fault_injection",
            side_effect=attempt_after_first_publish,
        ):
            result = apply_migration(
                preview["previewId"],
                ["knowledge", "context"],
                paths,
            )

        assert result["status"] == "completed"
        assert attempted is True
        assert [attempt[0] for attempt in attempts] == [
            "blocked",
            "blocked",
        ], attempts
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert read_sample_value(paths.context_db) == "legacy"


def test_apply_rejects_empty_unknown_and_duplicate_approvals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)

        for approved in ([], ["unknown"], ["knowledge", "knowledge"]):
            raises(
                MigrationApprovalError,
                lambda approved=approved: apply_migration(
                    preview["previewId"], approved, paths
                ),
            )
        assert not paths.root.exists()


def test_apply_rejects_stale_preview_when_source_metadata_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        source.write_bytes(source.read_bytes() + b"changed")

        raises(
            MigrationPreviewStaleError,
            lambda: apply_migration(preview["previewId"], ["knowledge"], paths),
        )

        assert source.is_file()
        assert not paths.root.exists()


def test_apply_does_not_follow_source_replaced_after_revalidation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / "data/person-photos/person.png"
        outside = tmp_path / "outside.png"
        outside.write_bytes(make_valid_png())
        original_open = os.open
        opens = 0

        def replace_before_copy(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal opens
            if path == "person.png":
                opens += 1
                if opens == 3:
                    source.unlink()
                    source.symlink_to(outside)
            return original_open(path, flags, mode, dir_fd=dir_fd)

        with patch("migration_manager.os.open", side_effect=replace_before_copy):
            raises(
                MigrationPreviewStaleError,
                lambda: apply_migration(
                    preview["previewId"], ["person-photos"], paths
                ),
            )

        assert outside.read_bytes() == make_valid_png()
        assert not paths.person_photos.exists()
        assert not list(paths.person_photos.parent.glob(".*.tomos-stage-*"))


def test_apply_copies_and_verifies_directory_file_hashes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source_root = (
            legacy / ".gemma4-data/study-packs" / OFFICIAL_PACK_NAME
        )

        result = apply_migration(preview["previewId"], ["study-packs"], paths)

        assert result["status"] == "completed"
        source_hashes = {
            relative_name: file_sha256(source_root / relative_name)
            for relative_name in migration_manager._OFFICIAL_STUDY_FILE_HASHES
        }
        destination_root = paths.study_packs / OFFICIAL_PACK_NAME
        destination_hashes = {
            path.relative_to(destination_root).as_posix(): file_sha256(path)
            for path in destination_root.rglob("*")
            if path.is_file()
        }
        assert destination_hashes == source_hashes
        assert source_root.is_dir()


def test_failed_sqlite_validation_keeps_current_source_and_cleans_staging() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        source.write_bytes(b"not a sqlite database")
        paths = make_paths(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)
        preview = build_migration_preview(detect_legacy_sources([legacy], paths))

        raises(
            MigrationValidationError,
            lambda: apply_migration(preview["previewId"], ["knowledge"], paths),
        )

        assert file_sha256(paths.knowledge_db) == before_hash
        assert source.is_file()
        assert not list(paths.knowledge_db.parent.glob(".*.tomos-stage-*"))


def test_publish_failure_restores_current_and_removes_staging() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)
        original_replace = os.replace

        def fail_staging_publish(source, destination, **kwargs):
            if (
                ".tomos-stage-" in Path(source).name
                and Path(destination).name == paths.knowledge_db.name
            ):
                raise OSError("publish failed")
            return original_replace(source, destination, **kwargs)

        with patch("migration_manager.os.replace", side_effect=fail_staging_publish):
            raises(
                MigrationValidationError,
                lambda: apply_migration(preview["previewId"], ["knowledge"], paths),
            )

        assert file_sha256(paths.knowledge_db) == before_hash
        assert (legacy / ".gemma4-data/knowledge/index.sqlite").is_file()
        assert not list(paths.knowledge_db.parent.glob(".*.tomos-stage-*"))


def test_apply_is_idempotent_and_rollback_restores_existing_snapshot_once() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)

        result = apply_migration(preview["previewId"], ["knowledge"], paths)
        second_result = apply_migration(preview["previewId"], ["knowledge"], paths)

        assert second_result == result
        assert result["snapshotId"]
        assert file_sha256(paths.knowledge_db) != before_hash
        rollback = rollback_migration(result["snapshotId"], paths)
        assert rollback["status"] == "rolled_back"
        assert file_sha256(paths.knowledge_db) == before_hash
        assert (legacy / ".gemma4-data/knowledge/index.sqlite").is_file()
        raises(
            MigrationNotFoundError,
            lambda: rollback_migration(result["snapshotId"], paths),
        )


def test_snapshot_id_for_migration_resolves_only_current_completed_record() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, paths, preview = apply_fixture(tmp_path)
        result = apply_migration(
            preview["previewId"],
            ["knowledge"],
            paths,
        )

        assert (
            snapshot_id_for_migration(result["migrationId"], paths)
            == result["snapshotId"]
        )

        rollback_migration(result["snapshotId"], paths)
        raises(
            MigrationNotFoundError,
            lambda: snapshot_id_for_migration(
                result["migrationId"],
                paths,
            ),
        )


def test_snapshot_id_for_migration_hides_unknown_or_tampered_record() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, paths, preview = apply_fixture(tmp_path)
        result = apply_migration(
            preview["previewId"],
            ["knowledge"],
            paths,
        )
        completion_path = (
            paths.migration
            / "records"
            / f"{result['migrationId']}.json"
        )
        completion = json.loads(completion_path.read_text("utf-8"))
        completion["snapshotId"] = "f" * 32
        completion_path.write_text(
            json.dumps(completion),
            encoding="utf-8",
        )

        raises(
            MigrationNotFoundError,
            lambda: snapshot_id_for_migration(
                result["migrationId"],
                paths,
            ),
        )
        raises(
            MigrationNotFoundError,
            lambda: snapshot_id_for_migration("0" * 32, paths),
        )


def test_snapshot_id_for_migration_rejects_superseded_record() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        first = apply_migration(
            preview["previewId"],
            ["knowledge"],
            paths,
        )
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        connection = sqlite3.connect(source)
        try:
            connection.execute(
                "UPDATE sample SET value = 'legacy-updated'"
            )
            connection.commit()
        finally:
            connection.close()
        second_preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )
        second = apply_migration(
            second_preview["previewId"],
            ["knowledge"],
            paths,
        )

        raises(
            MigrationNotFoundError,
            lambda: snapshot_id_for_migration(
                first["migrationId"],
                paths,
            ),
        )
        assert (
            snapshot_id_for_migration(second["migrationId"], paths)
            == second["snapshotId"]
        )


def test_new_apply_keeps_only_one_snapshot_generation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        make_sqlite_database(paths.knowledge_db, "current")
        first = apply_migration(preview["previewId"], ["knowledge"], paths)

        connection = sqlite3.connect(source)
        try:
            connection.execute("UPDATE sample SET value = 'legacy-updated'")
            connection.commit()
        finally:
            connection.close()
        second_preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )
        second = apply_migration(
            second_preview["previewId"], ["knowledge"], paths
        )

        snapshot_records = list((paths.migration / "snapshots").glob("*.json"))
        assert [path.stem for path in snapshot_records] == [second["snapshotId"]]
        raises(
            MigrationNotFoundError,
            lambda: rollback_migration(first["snapshotId"], paths),
        )


def test_completed_records_do_not_store_source_paths_contents_or_tokens() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)

        apply_migration(preview["previewId"], ["knowledge"], paths)

        records = list(paths.migration.rglob("*.json"))
        assert records
        serialized = "\n".join(path.read_text(encoding="utf-8") for path in records)
        assert str(legacy) not in serialized
        assert "legacy" not in serialized
        assert all(
            forbidden not in serialized.lower()
            for forbidden in ('"path"', '"content"', '"text"', '"token"')
        )


def test_detect_rejects_source_destination_overlap_without_writing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp) / "legacy"
        legacy = make_legacy_fixture(data_root)
        paths = TomosPaths.from_root(data_root)
        before = sorted(path.relative_to(data_root) for path in data_root.rglob("*"))

        raises(
            MigrationValidationError,
            lambda: detect_legacy_sources([legacy], paths),
        )

        after = sorted(path.relative_to(data_root) for path in data_root.rglob("*"))
        assert after == before
        assert not paths.migration.exists()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, _preview = apply_fixture(tmp_path)
        paths.knowledge_db.parent.mkdir(parents=True)
        os.link(
            legacy / ".gemma4-data/knowledge/index.sqlite",
            paths.knowledge_db,
        )
        raises(
            MigrationValidationError,
            lambda: detect_legacy_sources([legacy], paths),
        )


def test_detect_rejects_destination_outside_root_and_symlinked_parent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = make_legacy_fixture(tmp_path / "legacy")
        paths = make_paths(tmp_path)
        outside_paths = replace(
            paths, knowledge_db=tmp_path / "outside/index.sqlite"
        )
        raises(
            MigrationValidationError,
            lambda: detect_legacy_sources([legacy], outside_paths),
        )

        real_root = tmp_path / "real-app-data"
        real_root.mkdir()
        linked_root = tmp_path / "linked-app-data"
        linked_root.symlink_to(real_root, target_is_directory=True)
        raises(
            MigrationValidationError,
            lambda: detect_legacy_sources(
                [legacy], TomosPaths.from_root(linked_root)
            ),
        )
        assert list(real_root.iterdir()) == []

        real_parent = tmp_path / "real-parent"
        real_parent.mkdir()
        linked_parent = tmp_path / "linked-parent"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        raises(
            MigrationValidationError,
            lambda: detect_legacy_sources(
                [legacy],
                TomosPaths.from_root(linked_parent / "app-data"),
            ),
        )
        assert list(real_parent.iterdir()) == []


def test_apply_rechecks_parent_chain_before_any_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        outside = tmp_path / "outside-app-data"
        outside.mkdir()
        paths.root.symlink_to(outside, target_is_directory=True)

        raises(
            MigrationValidationError,
            lambda: apply_migration(
                preview["previewId"], ["knowledge"], paths
            ),
        )

        assert (legacy / ".gemma4-data/knowledge/index.sqlite").is_file()
        assert list(outside.iterdir()) == []


def test_source_inode_and_content_are_bound_even_when_size_mtime_match() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        source_stat = source.stat()
        replacement = tmp_path / "replacement.sqlite"
        shutil.copyfile(source, replacement)
        replacement_bytes = bytearray(replacement.read_bytes())
        replacement_bytes[-1] ^= 1
        replacement.write_bytes(replacement_bytes)
        os.utime(
            replacement,
            ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
        )
        os.replace(replacement, source)
        assert source.stat().st_size == source_stat.st_size
        assert source.stat().st_mtime_ns == source_stat.st_mtime_ns

        raises(
            MigrationPreviewStaleError,
            lambda: apply_migration(preview["previewId"], ["knowledge"], paths),
        )
        assert not paths.knowledge_db.exists()


def test_directory_addition_after_copy_is_rejected_as_stale() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        original_copy = migration_manager._copy_directory_files
        added = False

        def add_after_copy(*args, **kwargs):
            nonlocal added
            result = original_copy(*args, **kwargs)
            if not added:
                added = True
                (legacy / "data/person-photos/added.png").write_bytes(
                    make_valid_png()
                )
            return result

        with patch(
            "migration_manager._copy_directory_files",
            side_effect=add_after_copy,
        ):
            raises(
                MigrationPreviewStaleError,
                lambda: apply_migration(
                    preview["previewId"], ["person-photos"], paths
                ),
            )

        assert not paths.person_photos.exists()
        assert (legacy / "data/person-photos/added.png").is_file()


def test_directory_change_after_capture_is_next_preview_data() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        paths.person_photos.mkdir(parents=True)
        (paths.person_photos / "current.png").write_bytes(
            make_valid_png()
        )
        changed = False

        def change_after_capture(point: str, kind: str) -> None:
            nonlocal changed
            if (
                point == "after_source_capture"
                and kind == "maintenance"
            ):
                changed = True
                (
                    legacy / "data/person-photos/after-capture.png"
                ).write_bytes(make_valid_png())

        with patch(
            "migration_manager._fault_injection",
            side_effect=change_after_capture,
        ):
            result = apply_migration(
                preview["previewId"],
                ["person-photos", "study-packs"],
                paths,
            )

        assert result["status"] == "completed"
        assert changed is True
        assert not (
            paths.person_photos / "after-capture.png"
        ).exists()
        assert paths.study_packs.is_dir()
        assert (
            legacy / "data/person-photos/after-capture.png"
        ).is_file()
        next_preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )
        assert next_preview["previewId"] != preview["previewId"]


def test_directory_capture_record_uses_capture_boundary_names() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        changed = False

        def change_after_capture(point: str, kind: str) -> None:
            nonlocal changed
            if (
                point == "after_source_capture"
                and kind == "maintenance"
                and not changed
            ):
                changed = True
                (
                    legacy / "data/person-photos/after-commit.png"
                ).write_bytes(make_valid_png())

        with patch(
            "migration_manager._fault_injection",
            side_effect=change_after_capture,
        ):
            result = apply_migration(
                preview["previewId"], ["person-photos"], paths
            )

        assert result["status"] == "completed"
        assert changed is True
        assert not (
            paths.person_photos / "after-commit.png"
        ).exists()
        next_preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )
        assert next_preview["previewId"] != preview["previewId"]
        completion = json.loads(
            (
                paths.migration
                / "records"
                / f"{result['migrationId']}.json"
            ).read_text(encoding="utf-8")
        )
        assert len(completion["sourceSnapshotDigest"]) == 64
        assert completion["sourceCapturedAt"] > 0
        assert "sourceValidatedAt" not in completion


def test_directory_replacement_after_capture_does_not_change_staging() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / "data/person-photos/person.png"
        replaced = False

        def replace_after_capture(
            point: str, kind: str
        ) -> None:
            nonlocal replaced
            if (
                point == "after_source_capture"
                and kind == "maintenance"
                and not replaced
            ):
                replacement = tmp_path / "replacement.png"
                replacement.write_bytes(source.read_bytes())
                os.replace(replacement, source)
                replaced = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=replace_after_capture,
        ):
            result = apply_migration(
                preview["previewId"], ["person-photos"], paths
            )

        assert result["status"] == "completed"
        assert replaced is True
        assert (
            paths.person_photos / "person.png"
        ).read_bytes() == source.read_bytes()
        assert source.is_file()


def test_new_only_and_mixed_migrations_have_rollback_handles() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        new_only = apply_migration(preview["previewId"], ["knowledge"], paths)
        assert new_only["snapshotId"]
        rollback_migration(new_only["snapshotId"], paths)
        assert not paths.knowledge_db.exists()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)
        mixed = apply_migration(
            preview["previewId"], ["knowledge", "context"], paths
        )
        assert mixed["snapshotId"]
        rollback_migration(mixed["snapshotId"], paths)
        assert file_sha256(paths.knowledge_db) == before_hash
        assert not paths.context_db.exists()


def test_second_item_publish_failure_restores_all_items() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current-knowledge")
        make_sqlite_database(paths.context_db, "current-context")
        before = {
            "knowledge": file_sha256(paths.knowledge_db),
            "context": file_sha256(paths.context_db),
        }
        original_replace = os.replace
        publishes = 0

        def fail_second_publish(source, destination, **kwargs):
            nonlocal publishes
            if ".tomos-stage-" in Path(source).name:
                publishes += 1
                if publishes == 2:
                    raise OSError("second publish failed")
            return original_replace(source, destination, **kwargs)

        with patch(
            "migration_manager.os.replace", side_effect=fail_second_publish
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge", "context"], paths
                ),
            )

        assert file_sha256(paths.knowledge_db) == before["knowledge"]
        assert file_sha256(paths.context_db) == before["context"]
        assert not list(paths.migration.glob("journals/*.json"))


def test_restore_failure_keeps_journal_for_retry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current-knowledge")
        make_sqlite_database(paths.context_db, "current-context")
        before = {
            "knowledge": file_sha256(paths.knowledge_db),
            "context": file_sha256(paths.context_db),
        }
        original_replace = os.replace
        publishes = 0
        restore_failed = False

        def fail_publish_and_first_restore(source, destination, **kwargs):
            nonlocal publishes, restore_failed
            source_path = Path(source)
            if ".tomos-stage-" in source_path.name:
                publishes += 1
                if publishes == 2:
                    raise OSError("second publish failed")
            if (
                ".tomos-apply-current-" in source_path.name
                and source_path.name.endswith(".restore")
                and not restore_failed
            ):
                restore_failed = True
                raise OSError("restore failed")
            return original_replace(source, destination, **kwargs)

        with patch(
            "migration_manager.os.replace",
            side_effect=fail_publish_and_first_restore,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge", "context"], paths
                ),
            )

        journals = list(paths.migration.glob("journals/*.json"))
        assert len(journals) == 1
        assert "restore_failed" in journals[0].read_text(encoding="utf-8")
        recover_migrations(paths)
        assert file_sha256(paths.knowledge_db) == before["knowledge"]
        assert file_sha256(paths.context_db) == before["context"]
        assert not list(paths.migration.glob("journals/*.json"))


def test_restart_recovery_rolls_back_partial_publish() -> None:
    class SimulatedCrash(BaseException):
        pass

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current-knowledge")
        make_sqlite_database(paths.context_db, "current-context")
        before = {
            "knowledge": file_sha256(paths.knowledge_db),
            "context": file_sha256(paths.context_db),
        }
        crashed = False

        def crash_after_first_publish(point, _kind):
            nonlocal crashed
            if point == "after_publish" and not crashed:
                crashed = True
                raise SimulatedCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_first_publish,
        ):
            raises(
                SimulatedCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge", "context"], paths
                ),
            )

        assert list(paths.migration.glob("journals/*.json"))
        migration_manager._PREVIEW_REGISTRY.clear()
        recover_migrations(paths)
        assert file_sha256(paths.knowledge_db) == before["knowledge"]
        assert file_sha256(paths.context_db) == before["context"]
        assert not list(paths.migration.glob("journals/*.json"))


def test_restart_recovery_survives_crash_after_restore_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths, before_hash = leave_published_apply_journal(Path(tmp))
        original_write_journal = migration_manager._write_journal
        crashed = False

        def crash_after_restore_pending(
            target_paths: TomosPaths, journal: dict
        ) -> None:
            nonlocal crashed
            original_write_journal(target_paths, journal)
            if (
                not crashed
                and journal.get("state") == "recovering"
                and journal["items"][0].get("phase")
                == "recovery_pending"
            ):
                crashed = True
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._write_journal",
            side_effect=crash_after_restore_pending,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: recover_migrations(paths),
            )

        journal_path = next(paths.migration.glob("journals/*.json"))
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
        assert payload["state"] == "recovering"
        assert payload["items"][0]["phase"] == "recovery_pending"
        assert payload["items"][0]["publishedDigest"]
        assert read_sample_value(paths.knowledge_db) == "legacy"

        migration_manager._PREVIEW_REGISTRY.clear()
        recover_migrations(paths)
        assert file_sha256(paths.knowledge_db) == before_hash
        assert not list(paths.migration.glob("journals/*.json"))


def test_restart_recovery_retries_restore_failed_snapshot_rename() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths, before_hash = leave_published_apply_journal(Path(tmp))
        original_replace_at = migration_manager._replace_at
        original_write_journal = migration_manager._write_journal
        restore_failed = False
        crashed = False

        def fail_snapshot_restore(
            source_parent_fd: int,
            source_name: str,
            destination_parent_fd: int,
            destination_name: str,
        ) -> None:
            nonlocal restore_failed
            if (
                not restore_failed
                and ".tomos-apply-current-" in source_name
                and source_name.endswith(".restore")
            ):
                restore_failed = True
                raise OSError("snapshot restore failed")
            original_replace_at(
                source_parent_fd,
                source_name,
                destination_parent_fd,
                destination_name,
            )

        def crash_after_restore_failed(
            target_paths: TomosPaths, journal: dict
        ) -> None:
            nonlocal crashed
            original_write_journal(target_paths, journal)
            if (
                not crashed
                and journal.get("state") == "restore_failed"
            ):
                crashed = True
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._replace_at",
            side_effect=fail_snapshot_restore,
        ), patch(
            "migration_manager._write_journal",
            side_effect=crash_after_restore_failed,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: recover_migrations(paths),
            )

        journal_path = next(paths.migration.glob("journals/*.json"))
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
        assert payload["state"] == "restore_failed"
        assert payload["recoveryErrorCount"] == 1
        assert payload["items"][0]["phase"] == "recovery_pending"
        assert payload["items"][0]["publishedDigest"]
        assert paths.knowledge_db.exists()
        assert read_sample_value(paths.knowledge_db) == "legacy"
        assert list(
            paths.knowledge_db.parent.glob(
                ".*.tomos-apply-current-*.displaced"
            )
        )

        migration_manager._PREVIEW_REGISTRY.clear()
        recover_migrations(paths)
        assert file_sha256(paths.knowledge_db) == before_hash
        assert not list(paths.migration.glob("journals/*.json"))


def test_completion_record_failure_rolls_back_and_cleans_tmp() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)
        original_write_record = migration_manager._write_record
        failed = False

        def fail_completion_record(path, payload):
            nonlocal failed
            if path.parent.name == "records" and not failed:
                failed = True
                raise OSError("completion record failed")
            return original_write_record(path, payload)

        with patch(
            "migration_manager._write_record",
            side_effect=fail_completion_record,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert file_sha256(paths.knowledge_db) == before_hash
        assert not list(paths.migration.rglob("*.tmp"))
        assert not list(paths.migration.glob("journals/*.json"))


def test_idempotent_apply_rejects_inconsistent_completion_state() -> None:
    mutations = ("completion", "snapshot", "current")
    for mutation in mutations:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )
            migration_id = result["migrationId"]
            snapshot_id = result["snapshotId"]
            completion_path = (
                paths.migration / "records" / f"{migration_id}.json"
            )
            snapshot_record_path = (
                paths.migration / "snapshots" / f"{snapshot_id}.json"
            )
            if mutation == "completion":
                completion = json.loads(
                    completion_path.read_text(encoding="utf-8")
                )
                completion["unknown"] = True
                completion_path.write_text(
                    json.dumps(completion, sort_keys=True),
                    encoding="utf-8",
                )
            elif mutation == "snapshot":
                snapshot = json.loads(
                    snapshot_record_path.read_text(encoding="utf-8")
                )
                snapshot["items"][0]["publishedDigest"]["sha256"] = (
                    "f" * 64
                )
                snapshot_record_path.write_text(
                    json.dumps(snapshot, sort_keys=True),
                    encoding="utf-8",
                )
            else:
                make_sqlite_database(paths.knowledge_db, "changed-current")

            current_before = paths.knowledge_db.read_bytes()
            completion_before = completion_path.read_bytes()
            snapshot_before = snapshot_record_path.read_bytes()
            migration_manager._PREVIEW_REGISTRY.clear()

            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

            assert paths.knowledge_db.read_bytes() == current_before
            assert completion_path.read_bytes() == completion_before
            assert snapshot_record_path.read_bytes() == snapshot_before


def test_apply_recovery_validates_new_final_state_before_old_snapshot_prune() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        make_sqlite_database(paths.knowledge_db, "original-current")
        first = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        first_snapshot = paths.knowledge_db.with_name(
            f".{paths.knowledge_db.name}.tomos-snapshot-"
            f"{first['snapshotId']}"
        )
        first_record = (
            paths.migration
            / "snapshots"
            / f"{first['snapshotId']}.json"
        )
        source_writer = sqlite3.connect(source)
        try:
            source_writer.execute(
                "UPDATE sample SET value = 'second-legacy'"
            )
            source_writer.commit()
        finally:
            source_writer.close()
        second_preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )
        original_remove = migration_manager._remove_path_durable
        failed = False

        def fail_old_snapshot_once(path: Path) -> None:
            nonlocal failed
            if path == first_snapshot and not failed:
                failed = True
                raise OSError("defer old snapshot prune")
            original_remove(path)

        with patch(
            "migration_manager._remove_path_durable",
            side_effect=fail_old_snapshot_once,
        ):
            second = apply_migration(
                second_preview["previewId"], ["knowledge"], paths
            )
        assert second["cleanupPending"] is True
        assert failed is True
        journal_path = next(paths.migration.glob("journals/*.json"))
        assert first_snapshot.exists()
        assert first_record.exists()

        make_sqlite_database(paths.knowledge_db, "unexpected-current")
        current_before = paths.knowledge_db.read_bytes()
        first_snapshot_before = first_snapshot.read_bytes()
        first_record_before = first_record.read_bytes()
        journal_before = journal_path.read_bytes()

        raises(
            MigrationValidationError,
            lambda: recover_migrations(paths),
        )

        assert paths.knowledge_db.read_bytes() == current_before
        assert first_snapshot.read_bytes() == first_snapshot_before
        assert first_record.read_bytes() == first_record_before
        assert journal_path.read_bytes() == journal_before


def test_rollback_stops_when_published_destination_changed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        result = apply_migration(preview["previewId"], ["knowledge"], paths)
        connection = sqlite3.connect(paths.knowledge_db)
        try:
            connection.execute("UPDATE sample SET value = 'user-change'")
            connection.commit()
        finally:
            connection.close()
        changed_hash = file_sha256(paths.knowledge_db)

        raises(
            MigrationValidationError,
            lambda: rollback_migration(result["snapshotId"], paths),
        )

        assert file_sha256(paths.knowledge_db) == changed_hash
        assert list(paths.migration.glob("snapshots/*.json"))


def test_rollback_refuses_destination_change_committed_only_to_wal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        writer = sqlite3.connect(paths.knowledge_db)
        try:
            assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == (
                "wal",
            )
            before_main_hash = file_sha256(paths.knowledge_db)
            writer.execute(
                "UPDATE sample SET value = 'post-migration-wal'"
            )
            writer.commit()
            assert paths.knowledge_db.with_name(
                f"{paths.knowledge_db.name}-wal"
            ).stat().st_size > 0
            assert file_sha256(paths.knowledge_db) == before_main_hash

            raises(
                MigrationValidationError,
                lambda: rollback_migration(result["snapshotId"], paths),
            )

            assert read_sample_value(paths.knowledge_db) == (
                "post-migration-wal"
            )
            assert list(paths.migration.glob("snapshots/*.json"))
        finally:
            writer.close()


def test_snapshot_and_rollback_preserve_abandoned_wal_latest_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        context = multiprocessing.get_context("fork")
        process = context.Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "current-wal-latest"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        assert paths.knowledge_db.with_name(
            f"{paths.knowledge_db.name}-wal"
        ).stat().st_size > 0
        assert read_sample_value(paths.knowledge_db) == "current-wal-latest"

        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        assert read_sample_value(paths.knowledge_db) == "legacy"

        rollback = rollback_migration(result["snapshotId"], paths)

        assert rollback["status"] == "rolled_back"
        assert read_sample_value(paths.knowledge_db) == (
            "current-wal-latest"
        )


def test_wal_current_is_byte_exact_after_rollback_publish_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "pre-migration")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        context = multiprocessing.get_context("fork")
        process = context.Process(
            target=leave_wal_commit_worker,
            args=(paths.knowledge_db, "published-wal"),
        )
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        snapshot_record = (
            paths.migration
            / "snapshots"
            / f"{result['snapshotId']}.json"
        )
        payload = json.loads(snapshot_record.read_text(encoding="utf-8"))
        payload["items"][0]["publishedDigest"] = (
            migration_manager._managed_digest(
                paths.knowledge_db, sqlite_logical=True
            )
        )
        snapshot_record.write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8"
        )
        completion_path = (
            paths.migration
            / "records"
            / f"{result['migrationId']}.json"
        )
        completion = json.loads(
            completion_path.read_text(encoding="utf-8")
        )
        completion["snapshotRecordDigest"] = (
            migration_manager._digest_json(payload)
        )
        completion_path.write_text(
            json.dumps(completion, sort_keys=True), encoding="utf-8"
        )
        before = sqlite_physical_state(paths.knowledge_db)
        assert before["-wal"] is not None

        def fail_restore(point: str, kind: str) -> None:
            if point == "after_rollback_item" and kind == "knowledge":
                raise OSError("rollback publish failed")

        with patch(
            "migration_manager._fault_injection",
            side_effect=fail_restore,
        ):
            raises(
                MigrationValidationError,
                lambda: rollback_migration(
                    result["snapshotId"], paths
                ),
            )

        assert_sqlite_wal_physical_state(paths.knowledge_db, before)


def test_rollback_refuses_database_with_active_external_wal_reader() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        external = sqlite3.connect(paths.knowledge_db)
        try:
            assert external.execute("PRAGMA journal_mode = WAL").fetchone() == (
                "wal",
            )
            external.execute("BEGIN")
            assert external.execute(
                "SELECT value FROM sample"
            ).fetchone() == ("legacy",)

            raises(
                MigrationValidationError,
                lambda: rollback_migration(result["snapshotId"], paths),
            )

            assert read_sample_value(paths.knowledge_db) == "legacy"
            assert list(paths.migration.glob("snapshots/*.json"))
        finally:
            external.close()


def test_rollback_rejects_tampered_snapshot_record_without_data_loss() -> None:
    mutations = (
        lambda record: record["items"][0].update(
            {"hadDestination": False}
        ),
        lambda record: record["items"][0].pop("priorDigest"),
        lambda record: record["items"][0].update(
            {"priorDigest": record["items"][0]["publishedDigest"]}
        ),
        lambda record: record["items"][0].update({"unknown": True}),
        lambda record: record.update({"unknown": True}),
        lambda record: record.update({"status": "rolled_back"}),
        lambda record: record.update({"migrationId": "f" * 32}),
        lambda record: record["items"].append(
            dict(record["items"][0])
        ),
        lambda record: record["items"][0].update({"kind": "unknown"}),
        lambda record: record["items"][0].update(
            {
                "publishedDigest": {
                    "type": "directory",
                    "fileCount": 1,
                    "sha256": record["items"][0]["publishedDigest"][
                        "sha256"
                    ],
                }
            }
        ),
        lambda record: record["items"][0].update(
            {"publishedDigest": record["items"][0]["priorDigest"]}
        ),
    )
    for mutate in mutations:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _legacy, paths, preview = apply_fixture(tmp_path)
            make_sqlite_database(paths.knowledge_db, "current")
            result = apply_migration(
                preview["previewId"], ["knowledge"], paths
            )
            snapshot_id = result["snapshotId"]
            snapshot_path = paths.knowledge_db.with_name(
                f".{paths.knowledge_db.name}.tomos-snapshot-{snapshot_id}"
            )
            record_path = (
                paths.migration / "snapshots" / f"{snapshot_id}.json"
            )
            record = json.loads(record_path.read_text(encoding="utf-8"))
            assert record["items"][0]["priorDigest"]
            mutate(record)
            record_path.write_text(
                json.dumps(record, sort_keys=True), encoding="utf-8"
            )
            current_before = paths.knowledge_db.read_bytes()
            snapshot_before = snapshot_path.read_bytes()
            record_before = record_path.read_bytes()

            raises(
                MigrationValidationError,
                lambda: rollback_migration(snapshot_id, paths),
            )

            assert paths.knowledge_db.read_bytes() == current_before
            assert snapshot_path.read_bytes() == snapshot_before
            assert record_path.read_bytes() == record_before


def test_rollback_rejects_valid_database_replacing_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        snapshot_id = result["snapshotId"]
        snapshot_path = paths.knowledge_db.with_name(
            f".{paths.knowledge_db.name}.tomos-snapshot-{snapshot_id}"
        )
        record_path = (
            paths.migration / "snapshots" / f"{snapshot_id}.json"
        )
        make_sqlite_database(snapshot_path, "different-valid-snapshot")
        current_before = paths.knowledge_db.read_bytes()
        snapshot_before = snapshot_path.read_bytes()
        record_before = record_path.read_bytes()

        raises(
            MigrationValidationError,
            lambda: rollback_migration(snapshot_id, paths),
        )

        assert paths.knowledge_db.read_bytes() == current_before
        assert snapshot_path.read_bytes() == snapshot_before
        assert record_path.read_bytes() == record_before


def test_rollback_rejects_corrupt_snapshot_without_data_loss() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        snapshot_id = result["snapshotId"]
        snapshot_path = paths.knowledge_db.with_name(
            f".{paths.knowledge_db.name}.tomos-snapshot-{snapshot_id}"
        )
        record_path = (
            paths.migration / "snapshots" / f"{snapshot_id}.json"
        )
        snapshot_path.write_bytes(b"corrupt snapshot")
        current_before = paths.knowledge_db.read_bytes()
        snapshot_before = snapshot_path.read_bytes()
        record_before = record_path.read_bytes()

        raises(
            MigrationValidationError,
            lambda: rollback_migration(snapshot_id, paths),
        )

        assert paths.knowledge_db.read_bytes() == current_before
        assert snapshot_path.read_bytes() == snapshot_before
        assert record_path.read_bytes() == record_before


def test_new_only_snapshot_record_forbids_prior_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        snapshot_id = result["snapshotId"]
        snapshot_path = paths.knowledge_db.with_name(
            f".{paths.knowledge_db.name}.tomos-snapshot-{snapshot_id}"
        )
        record_path = (
            paths.migration / "snapshots" / f"{snapshot_id}.json"
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        item = record["items"][0]
        assert item["hadDestination"] is False
        assert "priorDigest" not in item
        assert not snapshot_path.exists()
        make_sqlite_database(snapshot_path, "unexpected-prior")
        current_before = paths.knowledge_db.read_bytes()
        snapshot_before = snapshot_path.read_bytes()
        record_before = record_path.read_bytes()

        raises(
            MigrationValidationError,
            lambda: rollback_migration(snapshot_id, paths),
        )

        assert paths.knowledge_db.read_bytes() == current_before
        assert snapshot_path.read_bytes() == snapshot_before
        assert record_path.read_bytes() == record_before


def test_final_rollback_recovery_validates_new_only_state_before_cleanup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        snapshot_id = result["snapshotId"]

        def crash_after_rollback_item(point: str, kind: str) -> None:
            if point == "after_rollback_item" and kind == "knowledge":
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_rollback_item,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: rollback_migration(snapshot_id, paths),
            )

        journal_path = (
            paths.migration
            / "journals"
            / f"rollback-{snapshot_id}.json"
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal["items"][0]["phase"] == "absent"
        journal["state"] = "commit_pending"
        journal_path.write_text(
            json.dumps(journal, sort_keys=True), encoding="utf-8"
        )
        backup = paths.knowledge_db.with_name(
            f".{paths.knowledge_db.name}.tomos-rollback-current-"
            f"{snapshot_id}"
        )
        assert backup.exists()
        make_sqlite_database(paths.knowledge_db, "unexpected-current")
        snapshot_record = (
            paths.migration / "snapshots" / f"{snapshot_id}.json"
        )
        destination_before = paths.knowledge_db.read_bytes()
        backup_before = backup.read_bytes()
        record_before = snapshot_record.read_bytes()

        raises(
            MigrationValidationError,
            lambda: recover_migrations(paths),
        )

        assert paths.knowledge_db.read_bytes() == destination_before
        assert backup.read_bytes() == backup_before
        assert snapshot_record.read_bytes() == record_before
        assert journal_path.exists()


def test_final_rollback_recovery_validates_existing_state_before_cleanup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "prior-current")
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        snapshot_id = result["snapshotId"]

        def crash_after_rollback_item(point: str, kind: str) -> None:
            if point == "after_rollback_item" and kind == "knowledge":
                raise SimulatedProcessCrash()

        with patch(
            "migration_manager._fault_injection",
            side_effect=crash_after_rollback_item,
        ):
            raises(
                SimulatedProcessCrash,
                lambda: rollback_migration(snapshot_id, paths),
            )

        journal_path = (
            paths.migration
            / "journals"
            / f"rollback-{snapshot_id}.json"
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal["items"][0]["phase"] == "restored"
        journal["state"] = "commit_pending"
        journal_path.write_text(
            json.dumps(journal, sort_keys=True), encoding="utf-8"
        )
        backup = paths.knowledge_db.with_name(
            f".{paths.knowledge_db.name}.tomos-rollback-current-"
            f"{snapshot_id}"
        )
        assert backup.exists()
        make_sqlite_database(paths.knowledge_db, "wrong-prior")
        snapshot_record = (
            paths.migration / "snapshots" / f"{snapshot_id}.json"
        )
        destination_before = paths.knowledge_db.read_bytes()
        backup_before = backup.read_bytes()
        record_before = snapshot_record.read_bytes()

        raises(
            MigrationValidationError,
            lambda: recover_migrations(paths),
        )

        assert paths.knowledge_db.read_bytes() == destination_before
        assert backup.read_bytes() == backup_before
        assert snapshot_record.read_bytes() == record_before
        assert journal_path.exists()


def test_rollback_cleanup_recovers_after_snapshot_record_was_removed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        snapshot_id = result["snapshotId"]
        snapshot_record = (
            paths.migration / "snapshots" / f"{snapshot_id}.json"
        )
        original_remove = migration_manager._remove_path_durable
        failed = False

        def remove_record_then_fail(path: Path) -> None:
            nonlocal failed
            if path == snapshot_record and not failed:
                original_remove(path)
                failed = True
                raise OSError("crash after snapshot record removal")
            original_remove(path)

        with patch(
            "migration_manager._remove_path_durable",
            side_effect=remove_record_then_fail,
        ):
            rollback = rollback_migration(snapshot_id, paths)

        assert rollback["cleanupPending"] is True
        assert failed is True
        assert not snapshot_record.exists()
        assert list(paths.migration.glob("journals/*.json"))

        recovered = recover_migrations(paths)

        assert recovered["cleanupPending"] is False
        assert not list(paths.migration.glob("journals/*.json"))
        assert not paths.knowledge_db.exists()


def test_concurrent_apply_uses_one_data_root_lock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        context = multiprocessing.get_context("fork")
        ready = context.Queue()
        start = context.Event()
        results = context.Queue()
        processes = [
            context.Process(
                target=concurrent_apply_worker,
                args=(preview["previewId"], paths, ready, start, results),
            )
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        ready.get(timeout=5)
        ready.get(timeout=5)
        start.set()
        responses = [results.get(timeout=10) for _ in processes]
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0

        assert all(response[0] == "ok" for response in responses), responses
        assert responses[0][1] == responses[1][1]
        assert len(list(paths.migration.glob("snapshots/*.json"))) == 1


def test_prune_failure_is_journaled_and_retried() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy, paths, preview = apply_fixture(tmp_path)
        source = legacy / ".gemma4-data/knowledge/index.sqlite"
        make_sqlite_database(paths.knowledge_db, "current")
        first = apply_migration(preview["previewId"], ["knowledge"], paths)
        connection = sqlite3.connect(source)
        try:
            connection.execute("UPDATE sample SET value = 'new-source'")
            connection.commit()
        finally:
            connection.close()
        second_preview = build_migration_preview(
            detect_legacy_sources([legacy], paths)
        )
        original_remove = migration_manager._remove_path
        failed = False

        def fail_old_snapshot_once(path):
            nonlocal failed
            if (
                first["snapshotId"] in Path(path).name
                and ".tomos-snapshot-" in Path(path).name
                and not failed
            ):
                failed = True
                raise OSError("prune failed")
            return original_remove(path)

        with patch(
            "migration_manager._remove_path", side_effect=fail_old_snapshot_once
        ):
            second = apply_migration(
                second_preview["previewId"], ["knowledge"], paths
            )

        assert second["cleanupPending"] is True
        assert list(paths.migration.glob("journals/*.json"))
        recover_migrations(paths)
        assert not list(paths.migration.glob("journals/*.json"))
        assert [
            path.stem for path in paths.migration.glob("snapshots/*.json")
        ] == [second["snapshotId"]]


def test_record_zero_write_cleans_temporary_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        record = root / "records/test.json"
        original_write = os.write
        returned_zero = False

        def zero_once(fd, payload):
            nonlocal returned_zero
            if not returned_zero:
                returned_zero = True
                return 0
            return original_write(fd, payload)

        with patch("migration_manager.os.write", side_effect=zero_once):
            raises(
                MigrationValidationError,
                lambda: migration_manager._write_record(
                    record, {"status": "test"}
                ),
            )
        assert not list(record.parent.glob("*.tmp"))


def test_parent_symlink_swap_before_publish_never_writes_outside_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)
        parent = paths.knowledge_db.parent
        held_parent = parent.with_name("knowledge-held")
        outside = tmp_path / "outside"
        outside.mkdir()
        swapped = False

        def swap_parent(point: str, kind: str) -> None:
            nonlocal swapped
            if point == "before_publish" and kind == "knowledge":
                os.rename(parent, held_parent)
                parent.symlink_to(outside, target_is_directory=True)
                swapped = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=swap_parent,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert swapped
        assert list(outside.iterdir()) == []
        parent.unlink()
        os.rename(held_parent, parent)
        recover_migrations(paths)
        assert file_sha256(paths.knowledge_db) == before_hash


def test_parent_symlink_swap_before_fd_open_never_writes_outside_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)
        parent = paths.knowledge_db.parent
        held_parent = parent.with_name("knowledge-held")
        outside = tmp_path / "outside"
        outside.mkdir()
        swapped = False

        def swap_before_open(point: str, kind: str) -> None:
            nonlocal swapped
            if point == "before_open_parent" and kind == "knowledge":
                os.rename(parent, held_parent)
                parent.symlink_to(outside, target_is_directory=True)
                swapped = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=swap_before_open,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )

        assert swapped
        assert list(outside.iterdir()) == []
        parent.unlink()
        os.rename(held_parent, parent)
        recover_migrations(paths)
        assert file_sha256(paths.knowledge_db) == before_hash


def test_data_root_symlink_swap_before_fd_open_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()
        swapped = False

        def swap_root(point: str, _kind: str) -> None:
            nonlocal swapped
            if point == "before_open_data_root" and not swapped:
                paths.root.symlink_to(outside, target_is_directory=True)
                swapped = True

        with patch(
            "migration_manager._fault_injection",
            side_effect=swap_root,
        ):
            raises(
                MigrationValidationError,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )
        assert swapped
        assert list(outside.iterdir()) == []


def test_normal_writer_is_serialized_with_apply_and_preserved_by_rollback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        context = multiprocessing.get_context("fork")
        ready = context.Queue()
        release = context.Event()
        writer = context.Process(
            target=managed_writer_worker,
            args=(paths, ready, release, "normal-writer"),
        )
        writer.start()
        writer_state = ready.get(timeout=5)
        assert writer_state[0] == "locked", writer_state

        apply_ready = context.Queue()
        apply_start = context.Event()
        apply_results = context.Queue()
        applying = context.Process(
            target=concurrent_apply_worker,
            args=(
                preview["previewId"],
                paths,
                apply_ready,
                apply_start,
                apply_results,
            ),
        )
        applying.start()
        apply_ready.get(timeout=5)
        apply_start.set()
        release.set()
        writer.join(timeout=10)
        applying.join(timeout=10)
        assert writer.exitcode == 0
        assert applying.exitcode == 0
        response = apply_results.get(timeout=5)
        assert response[0] == "ok", response
        rollback_migration(response[1]["snapshotId"], paths)
        assert file_sha256(paths.knowledge_db) == writer_state[1]


def test_normal_writer_change_wins_lock_and_blocks_rollback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        result = apply_migration(
            preview["previewId"], ["knowledge"], paths
        )
        context = multiprocessing.get_context("fork")
        ready = context.Queue()
        release = context.Event()
        writer = context.Process(
            target=managed_writer_worker,
            args=(paths, ready, release, "writer-change"),
        )
        writer.start()
        writer_state = ready.get(timeout=5)
        assert writer_state[0] == "locked", writer_state
        rollback_results = context.Queue()
        rollback_process = context.Process(
            target=rollback_worker,
            args=(result["snapshotId"], paths, rollback_results),
        )
        rollback_process.start()
        release.set()
        writer.join(timeout=10)
        rollback_process.join(timeout=10)
        assert writer.exitcode == 0
        assert rollback_process.exitcode == 0
        response = rollback_results.get(timeout=5)
        assert response[:2] == (
            "error",
            "MigrationValidationError",
        ), response
        assert file_sha256(paths.knowledge_db) == writer_state[1]


def journal_logical_digest(character: str = "a") -> dict:
    return {
        "type": "file",
        "bytes": 1,
        "sha256": character * 64,
    }


def journal_physical_digest(
    character: str = "b",
    *,
    sidecars: tuple[str, ...] = (),
) -> dict:
    return {
        "type": "sqlite-physical",
        "main": {
            "bytes": 1,
            "sha256": character * 64,
        },
        "sidecars": {
            key: {
                "bytes": 1,
                "sha256": chr(ord(character) + index + 1) * 64,
            }
            for index, key in enumerate(sidecars)
        },
    }


def journal_component_identities(physical: dict) -> dict:
    return {
        key: {"device": 1, "inode": index + 10}
        for index, key in enumerate(
            ("main", *physical["sidecars"])
        )
    }


def valid_apply_journal(*, had_destination: bool = False) -> dict:
    item = {
        "kind": "knowledge",
        "hadDestination": had_destination,
        "priorDigest": (
            journal_logical_digest("c")
            if had_destination
            else None
        ),
        "phase": "prepared",
        "expectedDigest": journal_logical_digest(),
        "replacementPhysicalDigest": journal_physical_digest("b"),
    }
    if had_destination:
        item["priorPhysicalDigest"] = journal_physical_digest("c")
    return {
        "version": 1,
        "operation": "apply",
        "state": "prepared",
        "migrationId": "1" * 32,
        "snapshotId": "2" * 32,
        "previewId": "3" * 64,
        "approvedItems": ["knowledge"],
        "pruneSnapshotIds": [],
        "items": [item],
    }


def valid_rollback_journal() -> dict:
    return {
        "version": 1,
        "operation": "rollback",
        "state": "prepared",
        "journalId": f"rollback-{'2' * 32}",
        "migrationId": "1" * 32,
        "snapshotId": "2" * 32,
        "items": [
            {
                "kind": "knowledge",
                "hadDestination": True,
                "phase": "prepared",
                "publishedDigest": journal_logical_digest(),
                "priorDigest": journal_logical_digest("c"),
                "publishedPhysicalDigest": journal_physical_digest(
                    "b"
                ),
                "restorePhysicalDigest": journal_physical_digest("c"),
            }
        ],
    }


def journal_file_name(payload: dict) -> str:
    journal_id = payload.get("journalId") or payload["migrationId"]
    return f"{journal_id}.json"


def assert_valid_journal_fixture(paths: TomosPaths, payload: dict) -> None:
    assert (
        migration_manager._validate_journal_schema(
            paths, journal_file_name(payload), payload
        )
        == payload
    )


def test_valid_apply_and_rollback_journal_fixtures_pass_closed_schema() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        fixtures = [
            valid_apply_journal(),
            valid_apply_journal(had_destination=True),
            valid_rollback_journal(),
        ]

        published = valid_apply_journal()
        published["items"][0].update(
            {
                "phase": "published",
                "publishedDigest": published["items"][0][
                    "expectedDigest"
                ],
                "sqliteComponentPhase": "sidecars_cleaned",
            }
        )
        fixtures.append(published)

        recovering = valid_apply_journal(had_destination=True)
        recovering["state"] = "recovering"
        recovering["items"][0].update(
            {
                "phase": "recovery_pending",
                "publishedDigest": recovering["items"][0][
                    "expectedDigest"
                ],
                "recoveryCurrentPhysicalDigest": recovering[
                    "items"
                ][0]["replacementPhysicalDigest"],
                "sqliteComponentPhase": "quarantined",
            }
        )
        fixtures.append(recovering)

        retained = valid_apply_journal()
        retained["state"] = "recovering"
        retained_physical = retained["items"][0][
            "replacementPhysicalDigest"
        ]
        retained["items"][0].update(
            {
                "phase": "recovered",
                "recoveryCurrentPhysicalDigest": retained_physical,
                "sqliteComponentPhase": (
                    "retained_external_write_guard"
                ),
                "stagingOwnershipIdentities": (
                    journal_component_identities(retained_physical)
                ),
            }
        )
        fixtures.append(retained)

        rollback_committed = valid_rollback_journal()
        rollback_committed["state"] = "committed"
        rollback_committed["items"][0].update(
            {
                "phase": "restored",
                "sqliteComponentPhase": "sidecars_cleaned",
            }
        )
        fixtures.append(rollback_committed)

        for payload in fixtures:
            assert_valid_journal_fixture(paths, payload)


def test_tampered_journals_are_rejected_before_path_construction() -> None:
    base = valid_apply_journal()
    mutations = (
        ("migrationId", "../outside"),
        ("snapshotId", "bad/name"),
        ("kind", "unknown"),
        ("phase", "unknown"),
    )
    for target, value in mutations:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = make_paths(tmp_path)
            journals = paths.migration / "journals"
            journals.mkdir(parents=True)
            payload = json.loads(json.dumps(base))
            if target in {"kind", "phase"}:
                payload["items"][0][target] = value
            else:
                payload[target] = value
            journal_path = journals / f"{'1' * 32}.json"
            journal_path.write_text(json.dumps(payload), encoding="utf-8")
            outside = tmp_path / "outside-sentinel"
            outside.write_text("safe", encoding="utf-8")

            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )
            raises(
                MigrationValidationError,
                lambda: prepare_managed_data_startup(paths),
            )
            entered = False

            def attempt_writer() -> None:
                nonlocal entered
                with managed_data_write(paths):
                    entered = True

            raises(MigrationValidationError, attempt_writer)

            assert outside.read_text(encoding="utf-8") == "safe"
            assert journal_path.exists()
            assert entered is False


def test_semantically_inconsistent_journals_are_rejected() -> None:
    cases: list[tuple[dict, dict]] = []

    apply_base = valid_apply_journal()
    committed_prepared = json.loads(json.dumps(apply_base))
    committed_prepared["state"] = "committed"
    cases.append((apply_base, committed_prepared))

    published_base = valid_apply_journal()
    published_base["items"][0].update(
        {
            "phase": "published",
            "publishedDigest": published_base["items"][0][
                "expectedDigest"
            ],
            "sqliteComponentPhase": "sidecars_cleaned",
        }
    )
    published_without_digest = json.loads(
        json.dumps(published_base)
    )
    published_without_digest["items"][0].pop("publishedDigest")
    cases.append((published_base, published_without_digest))

    false_with_snapshot_phase = json.loads(json.dumps(apply_base))
    false_with_snapshot_phase["items"][0]["phase"] = "snapshot_pending"
    cases.append((apply_base, false_with_snapshot_phase))

    self_prune = json.loads(json.dumps(apply_base))
    self_prune["pruneSnapshotIds"] = [self_prune["snapshotId"]]
    cases.append((apply_base, self_prune))

    wrong_published_digest = json.loads(
        json.dumps(published_base)
    )
    wrong_published_digest["items"][0]["publishedDigest"] = {
        **journal_logical_digest(),
        "sha256": "b" * 64,
    }
    cases.append((published_base, wrong_published_digest))

    missing_replacement_physical = json.loads(json.dumps(apply_base))
    missing_replacement_physical["items"][0].pop(
        "replacementPhysicalDigest"
    )
    cases.append((apply_base, missing_replacement_physical))

    component_base = valid_apply_journal()
    component_base["items"][0].update(
        {
            "phase": "publish_pending",
            "sqliteComponentPhase": "main_published",
        }
    )
    unknown_component = json.loads(json.dumps(component_base))
    unknown_component["items"][0]["sqliteComponentPhase"] = "unknown"
    cases.append((component_base, unknown_component))

    regressed_component = json.loads(json.dumps(published_base))
    regressed_component["items"][0]["sqliteComponentPhase"] = (
        "main_published"
    )
    cases.append((published_base, regressed_component))

    recovery_base = valid_apply_journal(had_destination=True)
    recovery_base["state"] = "recovering"
    recovery_base["items"][0].update(
        {
            "phase": "recovery_pending",
            "publishedDigest": recovery_base["items"][0][
                "expectedDigest"
            ],
            "recoveryCurrentPhysicalDigest": recovery_base["items"][0][
                "replacementPhysicalDigest"
            ],
            "sqliteComponentPhase": "quarantined",
        }
    )
    inconsistent_recovery_digest = json.loads(
        json.dumps(recovery_base)
    )
    inconsistent_recovery_digest["items"][0][
        "recoveryCurrentPhysicalDigest"
    ] = journal_physical_digest("d")
    cases.append((recovery_base, inconsistent_recovery_digest))

    new_only_quarantine = valid_apply_journal()
    new_only_quarantine["state"] = "recovering"
    new_only_physical = new_only_quarantine["items"][0][
        "replacementPhysicalDigest"
    ]
    new_only_quarantine["items"][0].update(
        {
            "phase": "recovery_pending",
            "recoveryCurrentPhysicalDigest": new_only_physical,
            "sqliteComponentPhase": "quarantined",
            "stagingOwnershipIdentities": (
                journal_component_identities(new_only_physical)
            ),
        }
    )
    missing_anchor_identities = json.loads(
        json.dumps(new_only_quarantine)
    )
    missing_anchor_identities["items"][0].pop(
        "stagingOwnershipIdentities"
    )
    cases.append((new_only_quarantine, missing_anchor_identities))

    retained_guard = json.loads(json.dumps(new_only_quarantine))
    retained_guard["items"][0].update(
        {
            "phase": "recovered",
            "sqliteComponentPhase": (
                "retained_external_write_guard"
            ),
        }
    )
    retained_without_closed_state = json.loads(
        json.dumps(retained_guard)
    )
    retained_without_closed_state["items"][0].pop(
        "stagingOwnershipIdentities"
    )
    cases.append((retained_guard, retained_without_closed_state))

    restore_failed_base = json.loads(json.dumps(recovery_base))
    restore_failed_base["state"] = "restore_failed"
    restore_failed_base["recoveryErrorCount"] = 1
    restore_failed_without_count = json.loads(
        json.dumps(restore_failed_base)
    )
    restore_failed_without_count.pop("recoveryErrorCount")
    cases.append((restore_failed_base, restore_failed_without_count))

    restore_failed_with_zero_count = json.loads(
        json.dumps(restore_failed_base)
    )
    restore_failed_with_zero_count["recoveryErrorCount"] = 0
    cases.append((restore_failed_base, restore_failed_with_zero_count))

    recovering_with_error_count = json.loads(json.dumps(recovery_base))
    recovering_with_error_count["recoveryErrorCount"] = 1
    cases.append((recovery_base, recovering_with_error_count))

    rollback_base = valid_rollback_journal()
    missing_rollback_physical = json.loads(json.dumps(rollback_base))
    missing_rollback_physical["items"][0].pop(
        "publishedPhysicalDigest"
    )
    cases.append((rollback_base, missing_rollback_physical))

    rollback_committed = json.loads(json.dumps(rollback_base))
    rollback_committed["state"] = "committed"
    rollback_committed["items"][0].update(
        {
            "phase": "restored",
            "sqliteComponentPhase": "sidecars_cleaned",
        }
    )
    rollback_committed_prepared = json.loads(
        json.dumps(rollback_committed)
    )
    rollback_committed_prepared["items"][0]["phase"] = "prepared"
    cases.append((rollback_committed, rollback_committed_prepared))

    for valid_payload, invalid_payload in cases:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_paths(Path(tmp))
            assert_valid_journal_fixture(paths, valid_payload)
            raises(
                MigrationValidationError,
                lambda: migration_manager._validate_journal_schema(
                    paths,
                    journal_file_name(invalid_payload),
                    invalid_payload,
                ),
            )
            journals = paths.migration / "journals"
            journals.mkdir(parents=True)
            journal_id = (
                invalid_payload.get("journalId")
                or invalid_payload["migrationId"]
            )
            journal_path = journals / f"{journal_id}.json"
            journal_path.write_text(
                json.dumps(invalid_payload), encoding="utf-8"
            )
            raises(
                MigrationValidationError,
                lambda: recover_migrations(paths),
            )
            assert journal_path.exists()


def test_module_writers_block_on_pending_invalid_journal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        paths = make_paths(tmp_path)
        journals = paths.migration / "journals"
        journals.mkdir(parents=True)
        journal_path = journals / f"{'1' * 32}.json"
        journal_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "operation": "apply",
                    "state": "committed",
                    "migrationId": "1" * 32,
                    "snapshotId": "2" * 32,
                    "previewId": "3" * 64,
                    "approvedItems": ["knowledge"],
                    "pruneSnapshotIds": [],
                    "items": [
                        {
                            "kind": "knowledge",
                            "hadDestination": False,
                            "priorDigest": None,
                            "phase": "prepared",
                            "expectedDigest": {
                                "type": "file",
                                "bytes": 1,
                                "sha256": "a" * 64,
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "note.md").write_text("text", encoding="utf-8")
        memory = remember(
            {"text": "保存してはいけない"},
            scope={"scopeType": "user", "scopeId": "local"},
        )["record"]
        operations = (
            lambda: index_folder(
                db_path=paths.knowledge_db,
                folder_id="folder",
                root_path=docs,
                extract_text=lambda path: path.read_text(
                    encoding="utf-8"
                ),
            ),
            lambda: save_contract(paths.contracts_db, {}),
            lambda: save_context_record(paths.context_db, memory),
            lambda: remove_pack(
                "note-article-writing",
                install_root=paths.study_packs,
            ),
        )
        for operation in operations:
            raises(MigrationValidationError, operation)
        assert not paths.knowledge_db.exists()
        assert not paths.contracts_db.exists()
        assert not paths.context_db.exists()
        assert not paths.study_packs.exists()


def test_startup_pending_detection_is_zero_write_and_recovers_before_use() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        assert has_pending_migrations(paths) is False
        prepare_managed_data_startup(paths)
        assert not paths.root.exists()

    class SimulatedCrash(BaseException):
        pass

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _legacy, paths, preview = apply_fixture(tmp_path)
        make_sqlite_database(paths.knowledge_db, "current")
        before_hash = file_sha256(paths.knowledge_db)

        def crash(point: str, _kind: str) -> None:
            if point == "after_publish":
                raise SimulatedCrash()

        with patch(
            "migration_manager._fault_injection", side_effect=crash
        ):
            raises(
                SimulatedCrash,
                lambda: apply_migration(
                    preview["previewId"], ["knowledge"], paths
                ),
            )
        assert has_pending_migrations(paths) is True
        prepare_managed_data_startup(paths)
        assert file_sha256(paths.knowledge_db) == before_hash
        assert has_pending_migrations(paths) is False


if __name__ == "__main__":
    test_preview_only_reads_known_legacy_roots()
    test_detect_legacy_sources_matches_pre_b3_default_storage_contract()
    test_default_home_containing_managed_root_previews_and_applies_all_legacy_sources()
    test_detect_rejects_same_kind_in_home_and_old_root()
    test_preview_excludes_secrets_and_unknown_files()
    test_preview_excludes_nested_secrets_and_unknown_directory_content()
    test_preview_excludes_study_pack_without_pack_manifest()
    test_preview_accepts_only_official_study_pack_files_with_reference_hashes()
    test_preview_rejects_official_study_pack_cloned_under_unexpected_name()
    test_preview_rejects_modified_and_custom_study_packs()
    test_preview_rejects_photo_extension_with_invalid_magic_bytes()
    test_preview_rejects_png_with_trailing_credential_payload()
    test_preview_and_apply_accept_strict_server_person_photo_formats()
    test_preview_excludes_trailing_and_corrupt_server_photo_formats()
    test_preview_excludes_riff_consistent_undecodable_webp_without_writing()
    test_webp_validation_fails_closed_when_native_decoder_is_unavailable()
    test_oversized_webp_headers_reject_before_native_decoder()
    test_native_webp_layout_rejects_before_provider_copy()
    test_preview_skips_fifo_without_blocking()
    test_preview_reports_only_metadata_and_destination_conflicts()
    test_preview_marks_existing_directory_file_and_symlink_destinations_as_conflicts()
    test_preview_rejects_directly_constructed_source_without_provenance()
    test_preview_rejects_symlinks_and_path_escape()
    test_preview_does_not_follow_directory_replacement_during_walk()
    test_preview_counts_source_replacement_as_excluded()
    test_preview_counts_files_that_disappear_during_walk()
    test_preview_counts_permission_changes_without_error_paths()
    test_preview_id_is_deterministic_and_bound_to_verified_metadata()
    test_apply_copies_only_after_explicit_exact_approval()
    test_apply_copies_latest_legacy_wal_commit_while_writer_is_open()
    test_legacy_wal_only_commit_invalidates_existing_preview()
    test_apply_blocks_legacy_commit_after_staging_backup()
    test_apply_blocks_wal_only_commit_after_staging_backup()
    test_stale_legacy_source_keeps_existing_wal_destination_unchanged()
    test_wal_current_is_byte_exact_after_snapshot_pending_failure()
    test_wal_current_is_byte_exact_after_apply_publish_failure()
    test_wal_current_is_byte_exact_after_completion_failure()
    test_apply_never_overwrites_external_commit_after_physical_backup()
    test_rollback_never_overwrites_external_commit_after_physical_backup()
    test_new_only_apply_atomically_refuses_external_sqlite_after_absence_check()
    test_new_only_apply_refuses_preexisting_sidecars_without_main()
    test_new_only_apply_refuses_sidecars_appearing_after_main_link()
    test_new_only_apply_main_crash_preserves_same_logical_external_wal_bundle()
    test_new_only_apply_recovery_quarantines_before_full_bundle_removal()
    test_new_only_link_crash_without_durable_phase_safely_stops()
    test_new_only_anchor_survives_until_committed_cleanup()
    test_new_only_recovery_requires_persistent_matching_anchor()
    test_new_only_external_staging_hardlink_is_not_owned_publish()
    test_new_only_recovery_keeps_writer_locked_through_cleanup_journal()
    test_new_only_recovery_retains_waiting_fd_update_after_unlock()
    test_new_only_recovery_same_sqlite_connection_fails_explicitly_if_moved()
    test_new_only_recovery_resumes_after_each_sidecar_anchor_unlink()
    test_new_only_recovery_resumes_after_destination_unlink_before_journal()
    test_new_only_current_missing_full_anchor_becomes_reachable_guard()
    test_new_only_current_missing_requires_full_original_anchor_bundle()
    test_new_only_recovery_resumes_after_staging_cleanup_before_unlock()
    test_new_only_recovery_rejects_existing_quarantine_hardlink()
    test_new_only_recovery_detects_quarantine_swap_after_current_lock()
    test_sqlite_quarantine_all_components_use_distinct_inodes()
    test_external_writer_is_blocked_after_apply_ownership_marker()
    test_external_writer_is_blocked_after_apply_main_publish()
    test_external_writer_is_blocked_after_rollback_main_publish()
    test_apply_main_publish_crash_recovers_wal_bundle_byte_exact()
    test_apply_each_sidecar_cleanup_crash_recovers_byte_exact()
    test_apply_recovery_rollback_journal_rename_crash_recovers_byte_exact()
    test_apply_recovery_revalidates_commit_before_current_replace()
    test_apply_recovery_blocks_writer_after_locked_decision()
    test_physical_restore_blocks_writer_after_wal_main_publish()
    test_rollback_main_publish_crash_recovers_wal_bundle_byte_exact()
    test_rollback_each_sidecar_cleanup_crash_recovers_byte_exact()
    test_rollback_journal_cleanup_crash_recovers_byte_exact()
    test_rollback_recovery_blocks_writer_after_locked_decision()
    test_restore_sidecar_swap_after_main_publish_retries_from_quarantine()
    test_restore_scratch_swap_at_current_handoff_keeps_current()
    test_apply_recovery_rejects_bundle_swap_before_restore_copy()
    test_recovery_binds_tampered_bundle_to_original_logical_digest()
    test_restore_copy_swap_is_detected_before_current_removal()
    test_physical_copy_detects_source_change_before_restore_publish()
    test_physical_restore_retries_after_sidecar_publish_failure()
    test_legacy_writer_is_blocked_from_final_capture_until_commit()
    test_all_legacy_sqlite_writers_stay_blocked_across_multi_item_publish()
    test_apply_rejects_empty_unknown_and_duplicate_approvals()
    test_apply_rejects_stale_preview_when_source_metadata_changes()
    test_apply_does_not_follow_source_replaced_after_revalidation()
    test_apply_copies_and_verifies_directory_file_hashes()
    test_failed_sqlite_validation_keeps_current_source_and_cleans_staging()
    test_publish_failure_restores_current_and_removes_staging()
    test_apply_is_idempotent_and_rollback_restores_existing_snapshot_once()
    test_snapshot_id_for_migration_resolves_only_current_completed_record()
    test_snapshot_id_for_migration_hides_unknown_or_tampered_record()
    test_snapshot_id_for_migration_rejects_superseded_record()
    test_new_apply_keeps_only_one_snapshot_generation()
    test_completed_records_do_not_store_source_paths_contents_or_tokens()
    test_detect_rejects_source_destination_overlap_without_writing()
    test_detect_rejects_destination_outside_root_and_symlinked_parent()
    test_apply_rechecks_parent_chain_before_any_write()
    test_source_inode_and_content_are_bound_even_when_size_mtime_match()
    test_directory_addition_after_copy_is_rejected_as_stale()
    test_directory_change_after_capture_is_next_preview_data()
    test_directory_capture_record_uses_capture_boundary_names()
    test_directory_replacement_after_capture_does_not_change_staging()
    test_new_only_and_mixed_migrations_have_rollback_handles()
    test_second_item_publish_failure_restores_all_items()
    test_restore_failure_keeps_journal_for_retry()
    test_restart_recovery_rolls_back_partial_publish()
    test_restart_recovery_survives_crash_after_restore_pending()
    test_restart_recovery_retries_restore_failed_snapshot_rename()
    test_completion_record_failure_rolls_back_and_cleans_tmp()
    test_idempotent_apply_rejects_inconsistent_completion_state()
    test_apply_recovery_validates_new_final_state_before_old_snapshot_prune()
    test_rollback_stops_when_published_destination_changed()
    test_rollback_refuses_destination_change_committed_only_to_wal()
    test_snapshot_and_rollback_preserve_abandoned_wal_latest_state()
    test_wal_current_is_byte_exact_after_rollback_publish_failure()
    test_rollback_refuses_database_with_active_external_wal_reader()
    test_rollback_rejects_tampered_snapshot_record_without_data_loss()
    test_rollback_rejects_valid_database_replacing_snapshot()
    test_rollback_rejects_corrupt_snapshot_without_data_loss()
    test_new_only_snapshot_record_forbids_prior_snapshot()
    test_final_rollback_recovery_validates_new_only_state_before_cleanup()
    test_final_rollback_recovery_validates_existing_state_before_cleanup()
    test_rollback_cleanup_recovers_after_snapshot_record_was_removed()
    test_concurrent_apply_uses_one_data_root_lock()
    test_prune_failure_is_journaled_and_retried()
    test_record_zero_write_cleans_temporary_file()
    test_parent_symlink_swap_before_publish_never_writes_outside_root()
    test_parent_symlink_swap_before_fd_open_never_writes_outside_root()
    test_data_root_symlink_swap_before_fd_open_is_rejected()
    test_normal_writer_is_serialized_with_apply_and_preserved_by_rollback()
    test_normal_writer_change_wins_lock_and_blocks_rollback()
    test_valid_apply_and_rollback_journal_fixtures_pass_closed_schema()
    test_tampered_journals_are_rejected_before_path_construction()
    test_semantically_inconsistent_journals_are_rejected()
    test_module_writers_block_on_pending_invalid_journal()
    test_startup_pending_detection_is_zero_write_and_recovers_before_use()
    print("migration manager tests passed")
