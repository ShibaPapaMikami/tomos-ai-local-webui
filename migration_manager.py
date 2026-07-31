from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import struct
import time
import uuid
import zlib
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Callable, Iterator, Sequence

from app_paths import TomosPaths


@dataclass(frozen=True)
class MigrationSource:
    kind: str
    source: Path
    destination: Path
    _provenance: "_SourceProvenance | None" = field(
        default=None, init=False, repr=False, compare=False
    )


class MigrationError(RuntimeError):
    pass


class MigrationApprovalError(MigrationError):
    pass


class MigrationPreviewStaleError(MigrationError):
    pass


class MigrationValidationError(MigrationError):
    pass


class MigrationNotFoundError(MigrationError):
    pass


@dataclass(frozen=True)
class _LegacyLocation:
    kind: str
    relative: Path
    destination_name: str
    is_directory: bool


@dataclass(frozen=True)
class _SourceProvenance:
    root: Path
    location: _LegacyLocation
    destination: Path
    data_root: Path


@dataclass(frozen=True)
class _FileMetadata:
    relative_name: str
    size: int
    mtime: float
    mtime_ns: int
    device: int
    inode: int
    sha256: str


@dataclass(frozen=True)
class _PreviewState:
    roots: tuple[Path, ...]
    item_signatures: dict[str, str]
    available_kinds: frozenset[str]
    data_root: Path


@dataclass(frozen=True)
class _StagedItem:
    kind: str
    destination: Path
    staging: Path
    expected_digest: dict


@dataclass
class _LockedLegacySQLite:
    source: MigrationSource
    provenance: _SourceProvenance
    root_fd: int
    parent_fd: int
    file_fd: int
    connection: sqlite3.Connection


@dataclass
class _HeldLegacyDirectory:
    source: MigrationSource
    provenance: _SourceProvenance
    root_fd: int
    source_fd: int
    metadata: tuple[_FileMetadata, ...]
    file_fds: dict[str, int]


@dataclass
class _HeldSQLitePhysicalBundle:
    main_fd: int
    sidecar_fds: dict[str, int]


_LEGACY_LOCATIONS = (
    _LegacyLocation(
        "knowledge",
        Path(".gemma4-data/knowledge/index.sqlite"),
        "knowledge_db",
        False,
    ),
    _LegacyLocation(
        "context",
        Path(".gemma4-data/context/context.sqlite"),
        "context_db",
        False,
    ),
    _LegacyLocation(
        "contracts",
        Path(".gemma4-data/contracts/contracts.sqlite"),
        "contracts_db",
        False,
    ),
    _LegacyLocation(
        "study-packs",
        Path(".gemma4-data/study-packs"),
        "study_packs",
        True,
    ),
    _LegacyLocation(
        "person-photos", Path("data/person-photos"), "person_photos", True
    ),
)
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | os.O_DIRECTORY
    | os.O_NOFOLLOW
    | os.O_CLOEXEC
    | os.O_NONBLOCK
)
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
_WRITABLE_FILE_FLAGS = (
    os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
)
_PERSON_PHOTO_EXTENSIONS = {".jpg", ".png", ".webp"}
_SENSITIVE_NAME_PARTS = (
    "token",
    "password",
    "session",
    "cookie",
    "secret",
    "key",
)
_MAX_OFFICIAL_STUDY_FILE_BYTES = 1024 * 1024
_MAX_PERSON_PHOTO_BYTES = 2 * 1024 * 1024
_MAX_PNG_DECODED_BYTES = 4 * 1024 * 1024
_MAX_WEBP_DECODED_BYTES = 4 * 1024 * 1024
_MAX_RECORD_BYTES = 64 * 1024
_SQLITE_KINDS = frozenset({"knowledge", "context", "contracts"})
_SQLITE_HEADER = b"SQLite format 3\x00"
_SQLITE_SIDECARS = (
    ("wal", "-wal"),
    ("shm", "-shm"),
    ("journal", "-journal"),
)
_SQLITE_COMPONENT_PHASES = frozenset(
    {
        "quarantined",
        "main_published",
        "wal_published",
        "shm_published",
        "journal_published",
        "sidecars_cleaned",
        "retained_external_write_guard",
    }
)
_OFFICIAL_PACK_ID = "note-article-writing"
_OFFICIAL_PACK_DIRECTORY = "note-article-writing"
_OFFICIAL_PACK_VERSION = "0.1.0"
_OFFICIAL_PACK_VISIBILITY = "public"
_OFFICIAL_MODE_FILES = {
    "rewrite-for-note": "modes/rewrite-for-note.md",
    "continue-series": "modes/continue-series.md",
    "paste-ready": "modes/paste-ready.md",
    "prepublish-check": "modes/prepublish-check.md",
}
_OFFICIAL_STUDY_FILE_HASHES = {
    "pack.json": "df1672296c352366e08fb3f22305d8dd295483480a6812a3f03e510731ac0b64",
    "modes/continue-series.md": "a4fe0cbcb73ff2e11809185627e07894559868564f13fe11819ae41bb268e457",
    "modes/paste-ready.md": "e15a2892d5d49e154af85cc5c5183887f82ee64d0703b12cdd2a98bcc28f3d6c",
    "modes/prepublish-check.md": "e8c04370c54c2798ddb9a5784b8922c040163d45f26988530968d77f87d24ec0",
    "modes/rewrite-for-note.md": "fc94156ae1975e2214c4a56e48bd25d69d6cef646859b353b4ad3fd529132467",
}
_PREVIEW_REGISTRY: dict[str, _PreviewState] = {}


def detect_legacy_sources(
    known_roots: Sequence[Path], paths: TomosPaths
) -> list[MigrationSource]:
    """Return only non-overlapping allowlisted legacy locations."""
    data_root = _validate_tomos_layout(paths)
    sources: list[MigrationSource] = []
    seen_roots: set[Path] = set()
    for known_root in known_roots:
        root = _safe_known_root(known_root)
        if root is None or root in seen_roots:
            continue
        seen_roots.add(root)
        for location in _LEGACY_LOCATIONS:
            if not _source_exists(root, location):
                continue
            source = MigrationSource(
                location.kind,
                root / location.relative,
                getattr(paths, location.destination_name),
            )
            object.__setattr__(
                source,
                "_provenance",
                _SourceProvenance(
                    root, location, source.destination, data_root
                ),
            )
            sources.append(source)
    _validate_source_set(sources, data_root)
    return sources


def build_migration_preview(sources: Sequence[MigrationSource]) -> dict:
    """Build a content-bound, metadata-only preview without writing."""
    items: list[dict] = []
    files: list[dict] = []
    excluded_count = 0
    error_count = 0
    signature_items: list[dict] = []
    signatures_by_kind: dict[str, list[str]] = {}
    eligible_kinds: set[str] = set()
    roots: set[Path] = set()
    data_roots: set[Path] = set()
    for source in sources:
        provenance = _validated_provenance(source)
        if provenance is None:
            excluded_count += 1
            continue
        roots.add(provenance.root)
        data_roots.add(provenance.data_root)
        source_files, source_excluded, source_errors = _collect_source(
            provenance
        )
        file_items = [
            _file_preview(source, provenance.location.is_directory, item)
            for item in source_files
        ]
        source_signature = _source_signature_payload(source, source_files)
        signature_items.append(source_signature)
        signatures_by_kind.setdefault(source.kind, []).append(
            _digest_json(source_signature)
        )
        if source_files and source_errors == 0:
            eligible_kinds.add(source.kind)
        source_conflict = (
            provenance.location.is_directory
            and _destination_exists(source.destination)
        )
        source_conflict = source_conflict or any(
            item["conflict"] for item in file_items
        )
        items.append(
            {
                "kind": source.kind,
                "source": str(source.source),
                "destination": str(source.destination),
                "totalFiles": len(file_items),
                "totalBytes": sum(item["bytes"] for item in file_items),
                "latestMtime": _latest_mtime(file_items),
                "conflict": source_conflict,
                "excludedCount": source_excluded,
                "errorCount": source_errors,
            }
        )
        files.extend(file_items)
        excluded_count += source_excluded
        error_count += source_errors
    preview_id = _digest_json(
        sorted(signature_items, key=_signature_sort_key)
    )
    if len(data_roots) == 1:
        item_signatures = {
            kind: values[0]
            for kind, values in signatures_by_kind.items()
            if len(values) == 1
        }
        available_kinds = frozenset(
            kind
            for kind in eligible_kinds
            if len(signatures_by_kind.get(kind, ())) == 1
        )
        _PREVIEW_REGISTRY[preview_id] = _PreviewState(
            roots=tuple(sorted(roots, key=str)),
            item_signatures=item_signatures,
            available_kinds=available_kinds,
            data_root=next(iter(data_roots)),
        )
    return {
        "previewId": preview_id,
        "totalFiles": len(files),
        "totalBytes": sum(item["bytes"] for item in files),
        "latestMtime": _latest_mtime(files),
        "excludedCount": excluded_count,
        "errorCount": error_count,
        "items": items,
        "files": files,
    }


def apply_migration(
    preview_id: str, approved_items: Sequence[str], paths: TomosPaths
) -> dict:
    approved = _validated_approvals(approved_items)
    data_root = _validate_tomos_layout(paths)
    migration_id = _digest_json(
        {"previewId": preview_id, "approvedItems": list(approved)}
    )[:32]
    preexisting_completion = _validate_completed_migration_state(
        paths,
        migration_id,
        expected_preview_id=preview_id,
        expected_approved_items=approved,
    )
    state = _PREVIEW_REGISTRY.get(preview_id)
    if preexisting_completion is None:
        if state is None or state.data_root != data_root:
            raise MigrationPreviewStaleError(
                "migration preview is unavailable"
            )
        if not set(approved).issubset(state.available_kinds):
            raise MigrationApprovalError(
                "approved items do not match the preview"
            )
        prelock_sources = detect_legacy_sources(state.roots, paths)
        if (
            build_migration_preview(prelock_sources)["previewId"]
            != preview_id
        ):
            raise MigrationPreviewStaleError(
                "migration preview is stale"
            )
    with _data_root_lock(paths):
        cleanup_pending = _recover_locked(paths)
        _validate_tomos_layout(paths)
        completed = _validate_completed_migration_state(
            paths,
            migration_id,
            expected_preview_id=preview_id,
            expected_approved_items=approved,
        )
        if completed is not None:
            return _public_completion_record(completed, cleanup_pending)

        state = _PREVIEW_REGISTRY.get(preview_id)
        if state is None or state.data_root != data_root:
            raise MigrationPreviewStaleError(
                "migration preview is unavailable"
            )
        if not set(approved).issubset(state.available_kinds):
            raise MigrationApprovalError(
                "approved items do not match the preview"
            )

        current_sources = detect_legacy_sources(state.roots, paths)
        current_preview = build_migration_preview(current_sources)
        if current_preview["previewId"] != preview_id:
            raise MigrationPreviewStaleError("migration preview is stale")
        sources_by_kind: dict[str, list[MigrationSource]] = {}
        for source in current_sources:
            sources_by_kind.setdefault(source.kind, []).append(source)
        if any(
            len(sources_by_kind.get(kind, ())) != 1 for kind in approved
        ):
            raise MigrationPreviewStaleError("migration sources changed")

        snapshot_id = uuid.uuid4().hex
        staged_paths = [
            _staging_path(
                _destination_for_kind(paths, kind), migration_id
            )
            for kind in approved
        ]
        snapshot_paths = [
            _snapshot_path(
                _destination_for_kind(paths, kind), snapshot_id
            )
            for kind in approved
        ]
        apply_backup_paths = [
            _apply_backup_path(
                _destination_for_kind(paths, kind), migration_id
            )
            for kind in approved
            if _is_sqlite_kind(kind)
        ]
        retained_guard_paths = [
            _retained_external_write_guard_path(
                _destination_for_kind(paths, kind),
                migration_id,
                snapshot_id,
                kind,
            )
            for kind in approved
            if _is_sqlite_kind(kind)
        ]
        retained_guard_record_paths = [
            _retained_external_write_guard_record_path(
                paths,
                migration_id,
                snapshot_id,
                kind,
            )
            for kind in approved
            if _is_sqlite_kind(kind)
        ]
        transaction_paths = (
            staged_paths
            + snapshot_paths
            + apply_backup_paths
            + retained_guard_paths
            + retained_guard_record_paths
            + [
                _physical_restore_path(path)
                for path in apply_backup_paths
            ]
            + [
                _sqlite_displaced_path(path)
                for path in apply_backup_paths
            ]
            + [
                _completion_record_path(paths, migration_id),
                _snapshot_record_path(paths, snapshot_id),
                _journal_path(paths, migration_id),
            ]
        )
        approved_sources = [
            sources_by_kind[kind][0] for kind in approved
        ]
        _validate_transaction_paths(
            paths,
            approved_sources,
            transaction_paths,
        )
        for internal_path in (
            staged_paths
            + snapshot_paths
            + apply_backup_paths
            + retained_guard_paths
            + retained_guard_record_paths
            + [
                _physical_restore_path(path)
                for path in apply_backup_paths
            ]
            + [
                _sqlite_displaced_path(path)
                for path in apply_backup_paths
            ]
            + [
                _snapshot_record_path(paths, snapshot_id),
                _journal_path(paths, migration_id),
            ]
        ):
            if _destination_exists(internal_path):
                raise MigrationValidationError(
                    "migration internal path already exists"
                )
        staged: list[_StagedItem] = []
        try:
            for kind in approved:
                staged_item = _stage_source(
                    sources_by_kind[kind][0],
                    state.item_signatures[kind],
                    migration_id,
                )
                staged.append(staged_item)
        except Exception:
            for item in staged:
                _safe_remove_durable(item.staging)
            raise

        try:
            _validate_transaction_paths(
                paths, approved_sources, transaction_paths
            )
        except Exception:
            for item in staged:
                _safe_remove_durable(item.staging)
            raise
        source_snapshot_digest = _digest_json(
            [
                {
                    "kind": kind,
                    "signature": state.item_signatures[kind],
                    "digest": next(
                        item.expected_digest
                        for item in staged
                        if item.kind == kind
                    ),
                }
                for kind in approved
            ]
        )
        source_captured_at = time.time_ns()
        _fault_injection("after_source_capture", "maintenance")
        old_snapshot_ids = _existing_snapshot_ids(paths)
        journal_items: list[dict] = []
        prior_sqlite_images: dict[str, bytes] = {}
        for item in staged:
            destination_parent_fd = _open_directory_chain(
                item.destination.parent
            )
            try:
                replacement_physical_digest = (
                    _sqlite_physical_digest_at(
                        destination_parent_fd, item.staging.name
                    )
                    if _is_sqlite_kind(item.kind)
                    else None
                )
                had_destination = _entry_exists_at(
                    destination_parent_fd, item.destination.name
                )
                prior_physical_digest = None
                if had_destination and _is_sqlite_kind(item.kind):
                    apply_backup = _apply_backup_path(
                        item.destination, migration_id
                    )
                    probe = _physical_restore_path(apply_backup)
                    prior_physical_digest = (
                        _copy_sqlite_physical_at(
                            destination_parent_fd,
                            item.destination.name,
                            apply_backup.name,
                        )
                    )
                    try:
                        _copy_sqlite_physical_at(
                            destination_parent_fd,
                            apply_backup.name,
                            probe.name,
                        )
                        prior_image = _sqlite_logical_image_at(
                            destination_parent_fd,
                            probe.name,
                        )
                        prior_digest = _sqlite_image_digest(
                            prior_image
                        )
                        prior_sqlite_images[item.kind] = prior_image
                    finally:
                        _remove_sqlite_bundle_at(
                            destination_parent_fd, probe.name
                        )
                else:
                    prior_digest = (
                        _managed_digest_at(
                            destination_parent_fd,
                            item.destination.name,
                            sqlite_logical=False,
                        )
                        if had_destination
                        else None
                    )
            finally:
                os.close(destination_parent_fd)
            journal_item = {
                "kind": item.kind,
                "hadDestination": had_destination,
                "priorDigest": prior_digest,
                "phase": "prepared",
                "expectedDigest": item.expected_digest,
            }
            if prior_physical_digest is not None:
                journal_item["priorPhysicalDigest"] = (
                    prior_physical_digest
                )
            if replacement_physical_digest is not None:
                journal_item["replacementPhysicalDigest"] = (
                    replacement_physical_digest
                )
            journal_items.append(journal_item)
        journal = {
            "version": 1,
            "operation": "apply",
            "state": "prepared",
            "migrationId": migration_id,
            "snapshotId": snapshot_id,
            "previewId": preview_id,
            "approvedItems": list(approved),
            "pruneSnapshotIds": old_snapshot_ids,
            "items": journal_items,
            "sourceSnapshotDigest": source_snapshot_digest,
            "sourceCapturedAt": source_captured_at,
        }
        _fault_injection("before_apply_journal", "maintenance")
        _write_journal(paths, journal)
        try:
            expected_digests = {
                item.kind: item.expected_digest for item in staged
            }
            with _locked_legacy_sqlite_sources(
                approved_sources,
                state.item_signatures,
                expected_digests,
            ) as locked_sources:
                for staged_item, journal_item in zip(
                    staged, journal["items"], strict=True
                ):
                    published_anchor_aliases = [
                        (
                            _destination_for_kind(
                                paths, completed_item["kind"]
                            ),
                            _staging_path(
                                _destination_for_kind(
                                    paths, completed_item["kind"]
                                ),
                                migration_id,
                            ),
                        )
                        for completed_item in journal["items"]
                        if (
                            _is_sqlite_kind(completed_item["kind"])
                            and not completed_item["hadDestination"]
                            and completed_item.get(
                                "sqliteComponentPhase"
                            )
                            is not None
                        )
                    ]
                    _validate_transaction_paths(
                        paths,
                        approved_sources,
                        transaction_paths,
                        allowed_existing_alias_groups=(
                            published_anchor_aliases
                        ),
                    )
                    if _is_sqlite_kind(staged_item.kind):
                        _validate_locked_legacy_sqlite_source(
                            locked_sources[staged_item.kind],
                            state.item_signatures[staged_item.kind],
                            staged_item.expected_digest,
                            check_signature=False,
                        )
                    destination = staged_item.destination
                    snapshot = _snapshot_path(destination, snapshot_id)
                    _fault_injection(
                        "before_open_parent", staged_item.kind
                    )
                    destination_parent_fd = _open_directory_chain(
                        destination.parent
                    )
                    try:
                        current_exists = _entry_exists_at(
                            destination_parent_fd, destination.name
                        )
                        if (
                            current_exists
                            != journal_item["hadDestination"]
                        ):
                            raise MigrationValidationError(
                                "destination changed before migration publish"
                            )
                        if current_exists:
                            if _is_sqlite_kind(staged_item.kind):
                                if (
                                    _sqlite_physical_digest_at(
                                        destination_parent_fd,
                                        destination.name,
                                    )
                                    != journal_item[
                                        "priorPhysicalDigest"
                                    ]
                                ):
                                    raise MigrationValidationError(
                                        "destination changed before migration publish"
                                    )
                            elif _managed_digest_at(
                                destination_parent_fd,
                                destination.name,
                                sqlite_logical=False,
                            ) != journal_item["priorDigest"]:
                                raise MigrationValidationError(
                                    "destination changed before migration publish"
                                )
                        _fault_injection(
                            "before_publish", staged_item.kind
                        )
                        _ensure_directory_fd_matches_path(
                            destination_parent_fd, destination.parent
                        )
                        if journal_item["hadDestination"]:
                            journal_item["phase"] = "snapshot_pending"
                            _write_journal(paths, journal)
                            if _is_sqlite_kind(staged_item.kind):
                                apply_backup = _apply_backup_path(
                                    destination, migration_id
                                )
                                if (
                                    _sqlite_physical_digest_at(
                                        destination_parent_fd,
                                        apply_backup.name,
                                    )
                                    != journal_item[
                                        "priorPhysicalDigest"
                                    ]
                                ):
                                    raise MigrationValidationError(
                                        "SQLite physical snapshot changed"
                                    )
                                _write_new_file_at(
                                    destination_parent_fd,
                                    snapshot.name,
                                    prior_sqlite_images[
                                        staged_item.kind
                                    ],
                                )
                            else:
                                _replace_at(
                                    destination_parent_fd,
                                    destination.name,
                                    destination_parent_fd,
                                    snapshot.name,
                                )
                            journal_item["phase"] = "snapshotted"
                            _write_journal(paths, journal)
                        _fault_injection(
                            "after_staging_backup", staged_item.kind
                        )
                        if _is_sqlite_kind(staged_item.kind):
                            _validate_locked_legacy_sqlite_source(
                                locked_sources[staged_item.kind],
                                state.item_signatures[staged_item.kind],
                                staged_item.expected_digest,
                                check_signature=False,
                            )
                        if _is_sqlite_kind(staged_item.kind):
                            with ExitStack() as sqlite_stack:
                                if journal_item["hadDestination"]:
                                    journal_item["phase"] = (
                                        "ownership_pending"
                                    )
                                    _write_journal(paths, journal)
                                    held_current = (
                                        sqlite_stack.enter_context(
                                            _held_sqlite_physical_bundle_at(
                                                destination_parent_fd,
                                                destination.name,
                                            )
                                        )
                                    )
                                    _verify_held_sqlite_bundle_at(
                                        destination_parent_fd,
                                        destination.name,
                                        held_current,
                                        journal_item[
                                            "priorPhysicalDigest"
                                        ],
                                    )
                                    (
                                        connection,
                                        sqlite_file_fd,
                                        _current_image,
                                    ) = _prepare_sqlite_replacement_at(
                                        destination_parent_fd,
                                        destination.name,
                                        journal_item["priorDigest"],
                                        expected_file_fd=held_current.main_fd,
                                    )
                                    sqlite_stack.callback(
                                        _close_sqlite_replacement,
                                        connection,
                                        sqlite_file_fd,
                                    )
                                    _verify_held_sqlite_bundle_at(
                                        destination_parent_fd,
                                        destination.name,
                                        held_current,
                                        journal_item[
                                            "priorPhysicalDigest"
                                        ],
                                    )
                                    journal_item["phase"] = "owned"
                                    _write_journal(paths, journal)
                                    _fault_injection(
                                        "after_sqlite_ownership",
                                        staged_item.kind,
                                    )

                                held_replacement = (
                                    sqlite_stack.enter_context(
                                        _locked_sqlite_physical_bundle_at(
                                            destination_parent_fd,
                                            staged_item.staging.name,
                                            journal_item[
                                                "replacementPhysicalDigest"
                                            ],
                                        )
                                    )
                                )
                                journal_item["phase"] = "publish_pending"
                                journal_item.pop(
                                    "sqliteComponentPhase", None
                                )
                                _write_journal(paths, journal)

                                def record_component_phase(
                                    phase: str,
                                ) -> None:
                                    journal_item[
                                        "sqliteComponentPhase"
                                    ] = phase
                                    _write_journal(paths, journal)

                                _publish_locked_sqlite_bundle_at(
                                    destination_parent_fd,
                                    staged_item.staging.name,
                                    destination.name,
                                    held_replacement,
                                    journal_item[
                                        "replacementPhysicalDigest"
                                    ],
                                    record_component_phase,
                                    no_clobber_main=not journal_item[
                                        "hadDestination"
                                    ],
                                )
                                journal_item["publishedDigest"] = (
                                    staged_item.expected_digest
                                )
                                journal_item["phase"] = "published"
                                _write_journal(paths, journal)
                                published_digest = (
                                    staged_item.expected_digest
                                )
                        else:
                            journal_item["phase"] = "publish_pending"
                            _write_journal(paths, journal)
                            _replace_at(
                                destination_parent_fd,
                                staged_item.staging.name,
                                destination_parent_fd,
                                destination.name,
                            )
                            published_digest = _managed_digest_at(
                                destination_parent_fd,
                                destination.name,
                                sqlite_logical=False,
                            )
                    finally:
                        os.close(destination_parent_fd)
                    if published_digest != staged_item.expected_digest:
                        raise MigrationValidationError(
                            "published destination validation failed"
                        )
                    if not _is_sqlite_kind(staged_item.kind):
                        journal_item["publishedDigest"] = published_digest
                        journal_item["phase"] = "published"
                        _write_journal(paths, journal)
                    _fault_injection(
                        "after_publish", staged_item.kind
                    )

                for kind, locked_source in locked_sources.items():
                    _validate_locked_legacy_sqlite_source(
                        locked_source,
                        state.item_signatures[kind],
                        expected_digests[kind],
                        check_signature=False,
                    )
                _fault_injection(
                    "after_final_sqlite_validation", "maintenance"
                )
                snapshot_record = {
                    "version": 1,
                    "status": "available",
                    "snapshotId": snapshot_id,
                    "migrationId": migration_id,
                    "items": [
                        {
                            "kind": item["kind"],
                            "hadDestination": item["hadDestination"],
                            **(
                                {"priorDigest": item["priorDigest"]}
                                if item["hadDestination"]
                                else {}
                            ),
                            "publishedDigest": item["publishedDigest"],
                        }
                        for item in journal["items"]
                    ],
                }
                _write_record(
                    _snapshot_record_path(paths, snapshot_id),
                    snapshot_record,
                )
                completion_record = {
                    "status": "completed",
                    "migrationId": migration_id,
                    "snapshotId": snapshot_id,
                    "previewId": preview_id,
                    "approvedItems": list(approved),
                    "snapshotRecordDigest": _digest_json(snapshot_record),
                    "sourceSnapshotDigest": source_snapshot_digest,
                    "sourceCapturedAt": source_captured_at,
                }
                _write_record(
                    _completion_record_path(paths, migration_id),
                    completion_record,
                )
                journal["state"] = "committed"
                _write_journal(paths, journal)
        except Exception as error:
            try:
                _recover_apply_journal(paths, journal)
            except MigrationValidationError as recovery_error:
                raise MigrationValidationError(
                    "migration publish and recovery failed"
                ) from recovery_error
            if isinstance(error, MigrationError):
                raise
            raise MigrationValidationError(
                "migration publish failed"
            ) from error

        prune_completed = _resume_apply_cleanup(paths, journal)
        return _public_completion_record(
            completion_record, not prune_completed
        )


def rollback_migration(snapshot_id: str, paths: TomosPaths) -> dict:
    if not _valid_identifier(snapshot_id):
        raise MigrationNotFoundError(
            "migration snapshot was not found"
        )
    _validate_tomos_layout(paths)
    with _data_root_lock(paths):
        _recover_locked(paths)
        _validate_tomos_layout(paths)
        snapshot_record = _read_record(
            _snapshot_record_path(paths, snapshot_id)
        )
        if not snapshot_record:
            raise MigrationNotFoundError(
                "migration snapshot was not found"
            )
        snapshot_record = _validate_snapshot_record_schema(
            snapshot_id, snapshot_record
        )
        _validate_snapshot_completion(paths, snapshot_record)
        items: list[dict] = []
        for raw_item in snapshot_record["items"]:
            item = {
                "kind": raw_item["kind"],
                "hadDestination": raw_item["hadDestination"],
                "publishedDigest": raw_item["publishedDigest"],
                "phase": "prepared",
            }
            if raw_item["hadDestination"]:
                item["priorDigest"] = raw_item["priorDigest"]
            items.append(item)
        migration_id = snapshot_record["migrationId"]
        journal_id = f"rollback-{snapshot_id}"
        mutable_paths: list[Path] = [
            _rollback_backup_path(
                _destination_for_kind(paths, item["kind"]),
                snapshot_id,
            )
            for item in items
        ]
        mutable_paths.extend(
            _rollback_restore_path(
                _destination_for_kind(paths, item["kind"]),
                snapshot_id,
            )
            for item in items
            if _is_sqlite_kind(item["kind"])
        )
        mutable_paths.extend(
            _physical_restore_path(
                _rollback_backup_path(
                    _destination_for_kind(paths, item["kind"]),
                    snapshot_id,
                )
            )
            for item in items
            if _is_sqlite_kind(item["kind"])
        )
        mutable_paths.extend(
            _sqlite_displaced_path(
                _rollback_backup_path(
                    _destination_for_kind(paths, item["kind"]),
                    snapshot_id,
                )
            )
            for item in items
            if _is_sqlite_kind(item["kind"])
        )
        mutable_paths.append(_journal_path(paths, journal_id))
        _validate_transaction_paths(paths, [], mutable_paths)
        if any(_destination_exists(path) for path in mutable_paths):
            raise MigrationValidationError(
                "rollback internal path already exists"
            )
        try:
            for raw_item, item in zip(
                snapshot_record["items"], items, strict=True
            ):
                destination = _destination_for_kind(
                    paths, item["kind"]
                )
                destination_parent_fd = _open_directory_chain(
                    destination.parent
                )
                try:
                    if _is_sqlite_kind(item["kind"]):
                        _validate_rollback_snapshot_at(
                            destination_parent_fd,
                            destination,
                            snapshot_id,
                            raw_item,
                        )
                        backup = _rollback_backup_path(
                            destination, snapshot_id
                        )
                        probe = _physical_restore_path(backup)
                        physical = _copy_sqlite_physical_at(
                            destination_parent_fd,
                            destination.name,
                            backup.name,
                        )
                        try:
                            _copy_sqlite_physical_at(
                                destination_parent_fd,
                                backup.name,
                                probe.name,
                            )
                            image = _sqlite_logical_image_at(
                                destination_parent_fd, probe.name
                            )
                            if (
                                _sqlite_image_digest(image)
                                != item["publishedDigest"]
                            ):
                                raise MigrationValidationError(
                                    "published destination changed before rollback"
                                )
                        finally:
                            _remove_sqlite_bundle_at(
                                destination_parent_fd, probe.name
                            )
                        item["publishedPhysicalDigest"] = physical
                        if item["hadDestination"]:
                            restore = _rollback_restore_path(
                                destination, snapshot_id
                            )
                            restore_physical = (
                                _copy_sqlite_physical_at(
                                    destination_parent_fd,
                                    _snapshot_path(
                                        destination, snapshot_id
                                    ).name,
                                    restore.name,
                                )
                            )
                            _validate_sqlite_physical_and_logical_at(
                                destination_parent_fd,
                                restore.name,
                                restore_physical,
                                item["priorDigest"],
                                f"{restore.name}.probe",
                            )
                            item["restorePhysicalDigest"] = (
                                restore_physical
                            )
                    else:
                        _validate_rollback_item_at(
                            destination_parent_fd,
                            destination,
                            snapshot_id,
                            raw_item,
                        )
                finally:
                    os.close(destination_parent_fd)
        except Exception:
            for item in items:
                if not _is_sqlite_kind(item["kind"]):
                    continue
                destination = _destination_for_kind(
                    paths, item["kind"]
                )
                try:
                    parent_fd = _open_directory_chain(
                        destination.parent
                    )
                except OSError:
                    continue
                try:
                    backup = _rollback_backup_path(
                        destination, snapshot_id
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd, backup.name
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd,
                        _physical_restore_path(backup).name,
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd,
                        _rollback_restore_path(
                            destination, snapshot_id
                        ).name,
                    )
                finally:
                    os.close(parent_fd)
            raise
        journal = {
            "version": 1,
            "operation": "rollback",
            "state": "prepared",
            "journalId": journal_id,
            "migrationId": migration_id,
            "snapshotId": snapshot_id,
            "items": items,
        }
        _write_journal(paths, journal)
        try:
            for item in journal["items"]:
                destination = _destination_for_kind(
                    paths, item["kind"]
                )
                _validate_tomos_layout(paths)
                backup = _rollback_backup_path(
                    destination, snapshot_id
                )
                _fault_injection(
                    "before_open_rollback_parent", item["kind"]
                )
                destination_parent_fd = _open_directory_chain(
                    destination.parent
                )
                try:
                    if _is_sqlite_kind(item["kind"]):
                        item["phase"] = "ownership_pending"
                        _write_journal(paths, journal)
                    _fault_injection(
                        "before_rollback_replace", item["kind"]
                    )
                    _ensure_directory_fd_matches_path(
                        destination_parent_fd, destination.parent
                    )
                    if _is_sqlite_kind(item["kind"]):
                        if (
                            _sqlite_physical_digest_at(
                                destination_parent_fd,
                                destination.name,
                            )
                            != item["publishedPhysicalDigest"]
                            or _sqlite_physical_digest_at(
                                destination_parent_fd,
                                backup.name,
                            )
                            != item["publishedPhysicalDigest"]
                        ):
                            raise MigrationValidationError(
                                "published destination changed before rollback"
                            )
                        _validate_rollback_snapshot_at(
                            destination_parent_fd,
                            destination,
                            snapshot_id,
                            item,
                        )
                        restore = _rollback_restore_path(
                            destination, snapshot_id
                        )
                        with ExitStack() as sqlite_stack:
                            held_current = sqlite_stack.enter_context(
                                _held_sqlite_physical_bundle_at(
                                    destination_parent_fd,
                                    destination.name,
                                )
                            )
                            _verify_held_sqlite_bundle_at(
                                destination_parent_fd,
                                destination.name,
                                held_current,
                                item["publishedPhysicalDigest"],
                            )
                            (
                                connection,
                                sqlite_file_fd,
                                _current_image,
                            ) = _prepare_sqlite_replacement_at(
                                destination_parent_fd,
                                destination.name,
                                item["publishedDigest"],
                                expected_file_fd=held_current.main_fd,
                            )
                            sqlite_stack.callback(
                                _close_sqlite_replacement,
                                connection,
                                sqlite_file_fd,
                            )
                            _verify_held_sqlite_bundle_at(
                                destination_parent_fd,
                                destination.name,
                                held_current,
                                item["publishedPhysicalDigest"],
                            )
                            item["phase"] = "owned"
                            _write_journal(paths, journal)
                            _fault_injection(
                                "after_sqlite_rollback_ownership",
                                item["kind"],
                            )
                            item["phase"] = "backed_up"
                            _write_journal(paths, journal)
                            if item["hadDestination"]:
                                held_restore = (
                                    sqlite_stack.enter_context(
                                        _locked_sqlite_physical_bundle_at(
                                            destination_parent_fd,
                                            restore.name,
                                            item[
                                                "restorePhysicalDigest"
                                            ],
                                        )
                                    )
                                )
                                item["phase"] = "restore_pending"
                                item.pop(
                                    "sqliteComponentPhase", None
                                )
                                _write_journal(paths, journal)

                                def record_component_phase(
                                    phase: str,
                                ) -> None:
                                    item[
                                        "sqliteComponentPhase"
                                    ] = phase
                                    _write_journal(paths, journal)

                                _publish_locked_sqlite_bundle_at(
                                    destination_parent_fd,
                                    restore.name,
                                    destination.name,
                                    held_restore,
                                    item["restorePhysicalDigest"],
                                    record_component_phase,
                                )
                                item["phase"] = "restored"
                                _write_journal(paths, journal)
                            else:
                                _remove_sqlite_bundle_at(
                                    destination_parent_fd,
                                    destination.name,
                                )
                                item["phase"] = "absent"
                                _write_journal(paths, journal)
                    else:
                        _validate_rollback_item_at(
                            destination_parent_fd,
                            destination,
                            snapshot_id,
                            item,
                        )
                        item["phase"] = "backup_pending"
                        _write_journal(paths, journal)
                        _replace_at(
                            destination_parent_fd,
                            destination.name,
                            destination_parent_fd,
                            backup.name,
                        )
                        item["phase"] = "backed_up"
                        _write_journal(paths, journal)
                        if item["hadDestination"]:
                            item["phase"] = "restore_pending"
                            _write_journal(paths, journal)
                            _replace_at(
                                destination_parent_fd,
                                _snapshot_path(
                                    destination, snapshot_id
                                ).name,
                                destination_parent_fd,
                                destination.name,
                            )
                            item["phase"] = "restored"
                        else:
                            item["phase"] = "absent"
                    if not _is_sqlite_kind(item["kind"]):
                        _write_journal(paths, journal)
                finally:
                    os.close(destination_parent_fd)
                _fault_injection("after_rollback_item", item["kind"])
            journal["state"] = "commit_pending"
            _write_journal(paths, journal)
            cleanup_completed = _finish_rollback_commit(
                paths, journal
            )
        except Exception as error:
            if journal.get("state") in {
                "commit_pending",
                "committed",
                "cleanup_pending",
                "record_cleanup_pending",
            }:
                try:
                    cleanup_completed = _finish_rollback_commit(
                        paths, journal
                    )
                except (MigrationError, OSError) as recovery_error:
                    raise MigrationValidationError(
                        "migration rollback commit remains pending"
                    ) from recovery_error
                return {
                    "status": "rolled_back",
                    "snapshotId": snapshot_id,
                    "restoredItems": [
                        item["kind"] for item in journal["items"]
                    ],
                    "cleanupPending": not cleanup_completed,
                }
            try:
                _recover_rollback_journal(paths, journal)
            except MigrationValidationError as recovery_error:
                raise MigrationValidationError(
                    "migration rollback and recovery failed"
                ) from recovery_error
            if isinstance(error, MigrationError):
                raise
            raise MigrationValidationError(
                "migration rollback failed"
            ) from error
        return {
            "status": "rolled_back",
            "snapshotId": snapshot_id,
            "restoredItems": [
                item["kind"] for item in journal["items"]
            ],
            "cleanupPending": not cleanup_completed,
        }


def snapshot_id_for_migration(
    migration_id: str,
    paths: TomosPaths,
) -> str:
    """Resolve a current completed migration to its rollback snapshot."""
    if not _valid_identifier(migration_id):
        raise MigrationNotFoundError(
            "migration was not found"
        )
    try:
        _validate_tomos_layout(paths)
        completion = _read_valid_completion_record(
            paths,
            migration_id,
        )
        if not completion or completion["status"] != "completed":
            raise MigrationNotFoundError(
                "migration was not found"
            )
        snapshot = _read_valid_snapshot_record(
            paths,
            completion["snapshotId"],
        )
        _validate_snapshot_completion(paths, snapshot)
    except MigrationNotFoundError:
        raise
    except MigrationValidationError as error:
        raise MigrationNotFoundError(
            "migration was not found"
        ) from error
    return completion["snapshotId"]


def recover_migrations(paths: TomosPaths) -> dict:
    """Recover interrupted publish/rollback and retry durable cleanup."""
    _validate_tomos_layout(paths)
    with _data_root_lock(paths):
        pending = _recover_locked(paths)
    return {"status": "recovered", "cleanupPending": pending}


def has_pending_migrations(paths: TomosPaths) -> bool:
    """Detect journals without creating the managed-data root or lock."""
    _validate_tomos_layout(paths)
    journal_directory = paths.migration / "journals"
    try:
        directory_fd = _open_directory_chain(journal_directory)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise MigrationValidationError(
            "migration journal directory is unsafe"
        ) from error
    try:
        names, errors = _directory_names(directory_fd)
        if errors:
            raise MigrationValidationError(
                "migration journal directory is unreadable"
            )
        return any(name.endswith(".json") for name in names)
    finally:
        os.close(directory_fd)


def prepare_managed_data_startup(paths: TomosPaths) -> None:
    """Recover pending work before the server opens managed databases."""
    if not has_pending_migrations(paths):
        return
    result = recover_migrations(paths)
    if result["cleanupPending"] or has_pending_migrations(paths):
        raise MigrationValidationError(
            "migration recovery remains pending"
        )


@contextmanager
def managed_data_write(paths: TomosPaths) -> Iterator[None]:
    """Serialize normal managed-data writes with migration and rollback."""
    _validate_tomos_layout(paths)
    with _data_root_lock(paths):
        if _recover_locked(paths):
            raise MigrationValidationError(
                "migration cleanup remains pending"
            )
        yield


@contextmanager
def managed_data_write_for_path(
    managed_path: Path, kind: str
) -> Iterator[None]:
    """Apply the migration lock at the owning module's write boundary."""
    attribute_by_kind = {
        "knowledge": "knowledge_db",
        "context": "context_db",
        "contracts": "contracts_db",
        "study-packs": "study_packs",
    }
    attribute = attribute_by_kind.get(kind)
    if attribute is None:
        raise MigrationValidationError(
            "managed writer kind is invalid"
        )
    target = _comparison_path(_absolute_path(managed_path))
    owner: TomosPaths | None = None
    for candidate_root in target.parents:
        candidate = TomosPaths.from_root(candidate_root)
        if _comparison_path(getattr(candidate, attribute)) == target:
            owner = candidate
            break
    if owner is None:
        yield
        return
    with managed_data_write(owner):
        yield


def managed_database_writer(kind: str):
    """Decorate a DB writer so schema creation and mutation share the lock."""
    def decorate(operation):
        @wraps(operation)
        def locked(*args, **kwargs):
            db_path = kwargs.get("db_path")
            if db_path is None and args:
                db_path = args[0]
            if db_path is None:
                raise MigrationValidationError(
                    "managed database path is missing"
                )
            path = Path(db_path)
            with managed_data_write_for_path(path, kind):
                path.parent.mkdir(parents=True, exist_ok=True)
                return operation(*args, **kwargs)
        return locked
    return decorate


def _recover_locked(paths: TomosPaths) -> bool:
    pending_cleanup = False
    journal_directory = paths.migration / "journals"
    try:
        journal_fd = _open_directory_chain(journal_directory)
    except FileNotFoundError:
        journal_fd = -1
    except OSError as error:
        raise MigrationValidationError(
            "migration journal directory is unsafe"
        ) from error
    if journal_fd >= 0:
        try:
            names, errors = _directory_names(journal_fd)
            if errors:
                raise MigrationValidationError(
                    "migration journal directory is unreadable"
                )
            journal_names = sorted(
                name for name in names if name.endswith(".json")
            )
            for journal_name in journal_names:
                journal = _read_record_at(journal_fd, journal_name)
                if not journal:
                    raise MigrationValidationError(
                        "migration journal is unreadable"
                    )
                journal = _validate_journal_schema(
                    paths, journal_name, journal
                )
                operation = journal["operation"]
                state = journal["state"]
                if operation == "apply":
                    if state in {"committed", "prune_pending"}:
                        if not _resume_apply_cleanup(paths, journal):
                            pending_cleanup = True
                    else:
                        _recover_apply_journal(paths, journal)
                else:
                    if state in {
                        "commit_pending",
                        "committed",
                        "cleanup_pending",
                        "record_cleanup_pending",
                    }:
                        if not _finish_rollback_commit(paths, journal):
                            pending_cleanup = True
                    else:
                        _recover_rollback_journal(paths, journal)
        finally:
            os.close(journal_fd)
    _cleanup_orphan_internal_files(paths)
    return pending_cleanup


def _cleanup_new_only_sqlite_internal_at(
    parent_fd: int,
    staging_name: str,
    quarantine_name: str,
    replacement_physical: dict,
    recovery_physical: dict | None,
) -> None:
    expected_staging = {
        "main": replacement_physical["main"],
        **replacement_physical["sidecars"],
    }
    staging_components = _sqlite_existing_component_digests_at(
        parent_fd, staging_name
    )
    if any(
        expected_staging.get(key) != digest
        for key, digest in staging_components.items()
    ):
        raise MigrationValidationError(
            "SQLite no-clobber staging changed"
        )
    quarantine_components = _sqlite_existing_component_digests_at(
        parent_fd, quarantine_name
    )
    if quarantine_components:
        expected_quarantine = (
            {}
            if recovery_physical is None
            else {
                "main": recovery_physical["main"],
                **recovery_physical["sidecars"],
            }
        )
        if any(
            expected_quarantine.get(key) != digest
            for key, digest in quarantine_components.items()
        ):
            raise MigrationValidationError(
                "SQLite no-clobber quarantine changed"
            )
    for key in ("wal", "shm", "journal", "main"):
        if key in staging_components:
            _remove_entry_at(
                parent_fd,
                f"{staging_name}{_sqlite_component_suffix(key)}",
            )
    for key in ("wal", "shm", "journal", "main"):
        if key in quarantine_components:
            _remove_entry_at(
                parent_fd,
                f"{quarantine_name}{_sqlite_component_suffix(key)}",
            )


def _recover_new_only_sqlite_apply_item_at(
    paths: TomosPaths,
    journal: dict,
    item: dict,
    parent_fd: int,
    destination: Path,
    staging: Path,
) -> None:
    replacement_physical = item["replacementPhysicalDigest"]
    apply_backup = _apply_backup_path(
        destination, journal["migrationId"]
    )
    quarantine_name = _sqlite_displaced_path(apply_backup).name
    retained_guard = _retained_external_write_guard_path(
        destination,
        journal["migrationId"],
        journal["snapshotId"],
        item["kind"],
    )
    phase = item["phase"]
    component_phase = item.get("sqliteComponentPhase")
    recovery_physical = item.get(
        "recoveryCurrentPhysicalDigest"
    )

    current_components = _sqlite_existing_component_digests_at(
        parent_fd, destination.name
    )
    current_physical = _sqlite_physical_from_components(
        current_components
    )
    if phase == "prepared":
        item["phase"] = "recovered"
        _write_journal(paths, journal)
        _cleanup_new_only_sqlite_internal_at(
            parent_fd,
            staging.name,
            quarantine_name,
            replacement_physical,
            recovery_physical,
        )
        return

    if phase == "publish_pending" and component_phase is None:
        if (
            current_physical is not None
            and _paths_share_regular_inode_at(
                parent_fd, staging.name, destination.name
            )
        ):
            raise MigrationValidationError(
                "SQLite no-clobber publish ownership is ambiguous"
            )
        item["phase"] = "recovered"
        _write_journal(paths, journal)
        _cleanup_new_only_sqlite_internal_at(
            parent_fd,
            staging.name,
            quarantine_name,
            replacement_physical,
            recovery_physical,
        )
        return

    if current_physical is None:
        if current_components:
            raise MigrationValidationError(
                "SQLite external sidecars block no-clobber recovery"
            )
        if (
            phase == "recovery_pending"
            and component_phase == "quarantined"
            and recovery_physical is not None
        ):
            component_identities = item[
                "stagingOwnershipIdentities"
            ]
            quarantine_components = (
                _sqlite_existing_component_digests_at(
                    parent_fd, quarantine_name
                )
            )
            if (
                _sqlite_physical_from_components(
                    quarantine_components
                )
                != recovery_physical
            ):
                raise MigrationValidationError(
                    "SQLite no-clobber quarantine is incomplete"
                )
            if (
                _sqlite_physical_digest_at(
                    parent_fd, staging.name
                )
                != replacement_physical
                or _managed_digest_at(
                    parent_fd,
                    staging.name,
                    sqlite_logical=True,
                )
                != item["expectedDigest"]
                or _sqlite_physical_digest_at(
                    parent_fd, staging.name
                )
                != replacement_physical
            ):
                raise MigrationValidationError(
                    "SQLite no-clobber ownership anchor changed"
                )
            with _locked_sqlite_physical_bundle_at(
                parent_fd,
                staging.name,
                replacement_physical,
            ) as held_staging:
                _verify_held_sqlite_component_identities(
                    held_staging, component_identities
                )
                _link_held_sqlite_bundle_to_retained_guard_at(
                    parent_fd,
                    staging.name,
                    retained_guard.name,
                    held_staging,
                    replacement_physical,
                    component_identities,
                )
                guard_record = (
                    _retained_external_write_guard_record(
                        journal["migrationId"],
                        journal["snapshotId"],
                        item["kind"],
                        replacement_physical,
                        item["expectedDigest"],
                        component_identities,
                    )
                )
                _write_retained_external_write_guard_record(
                    paths, guard_record
                )
                item["phase"] = "recovered"
                item["sqliteComponentPhase"] = (
                    "retained_external_write_guard"
                )
                _write_journal(paths, journal)
                _fault_injection(
                    "after_new_only_sqlite_recovery_journal",
                    destination.name,
                )
                _remove_held_sqlite_bundle_at(
                    parent_fd,
                    staging.name,
                    held_staging,
                    replacement_physical,
                    fault_prefix="after_new_only_sqlite_staging",
                    fault_kind=destination.name,
                )
                _fault_injection(
                    "after_new_only_sqlite_staging_cleanup_before_unlock",
                    destination.name,
                )
            _cleanup_new_only_sqlite_internal_at(
                parent_fd,
                staging.name,
                quarantine_name,
                replacement_physical,
                recovery_physical,
            )
            return
        if (
            phase == "recovered"
            and component_phase
            == "retained_external_write_guard"
            and recovery_physical is not None
        ):
            guard_record = _verify_retained_external_write_guard_at(
                paths,
                parent_fd,
                retained_guard.name,
                journal["migrationId"],
                journal["snapshotId"],
                item["kind"],
            )
            _remove_retained_staging_aliases_at(
                parent_fd,
                staging.name,
                guard_record["componentIdentities"],
                fault_kind=destination.name,
            )
            _cleanup_new_only_sqlite_internal_at(
                parent_fd,
                staging.name,
                quarantine_name,
                replacement_physical,
                recovery_physical,
            )
            return
        if phase != "recovered" or recovery_physical is None:
            raise MigrationValidationError(
                "SQLite no-clobber current is missing"
            )
        raise MigrationValidationError(
            "SQLite retained external write guard is missing"
        )

    staging_components = _sqlite_existing_component_digests_at(
        parent_fd, staging.name
    )
    if (
        _sqlite_physical_from_components(staging_components)
        != replacement_physical
        or not _paths_share_regular_inode_at(
            parent_fd, staging.name, destination.name
        )
    ):
        raise MigrationValidationError(
            "SQLite no-clobber ownership anchor changed"
        )
    _verify_new_only_component_ownership_at(
        parent_fd,
        staging.name,
        destination.name,
        current_components,
        component_phase,
    )

    if recovery_physical is None:
        if not _sqlite_physical_is_expected_subset(
            current_physical, replacement_physical
        ):
            raise MigrationValidationError(
                "external SQLite current blocks no-clobber recovery"
            )
        recovery_physical = current_physical
        item["recoveryCurrentPhysicalDigest"] = recovery_physical
        item["phase"] = "recovery_pending"
        _write_journal(paths, journal)
    elif not _sqlite_physical_is_expected_subset(
        current_physical, recovery_physical
    ):
        raise MigrationValidationError(
            "external SQLite current blocks no-clobber recovery"
        )

    with _held_sqlite_physical_bundle_at(
        parent_fd, staging.name
    ) as held_staging:
        _verify_held_sqlite_bundle_at(
            parent_fd,
            staging.name,
            held_staging,
            replacement_physical,
        )
        component_identities = (
            _sqlite_component_identities_from_held(held_staging)
        )
        recorded_identities = item.get(
            "stagingOwnershipIdentities"
        )
        if (
            recorded_identities is not None
            and recorded_identities != component_identities
        ):
            raise MigrationValidationError(
                "SQLite no-clobber ownership anchor identity changed"
            )
        with _held_distinct_sqlite_quarantine_at(
            parent_fd,
            destination.name,
            quarantine_name,
            current_physical,
            recovery_physical,
        ) as held_quarantine:
            with _locked_sqlite_physical_bundle_at(
                parent_fd, destination.name, current_physical
            ) as held_current:
                _fault_injection(
                    "after_new_only_sqlite_current_lock",
                    destination.name,
                )
                _verify_new_only_held_component_ownership_at(
                    parent_fd,
                    staging.name,
                    destination.name,
                    held_staging,
                    held_current,
                    replacement_physical,
                    current_physical,
                    component_phase,
                )
                _verify_distinct_held_sqlite_quarantine_at(
                    parent_fd,
                    destination.name,
                    quarantine_name,
                    held_current,
                    held_quarantine,
                    current_physical,
                    recovery_physical,
                )
                item["stagingOwnershipIdentities"] = (
                    component_identities
                )
                item["sqliteComponentPhase"] = "quarantined"
                _write_journal(paths, journal)
                _fault_injection(
                    "after_new_only_sqlite_quarantine",
                    destination.name,
                )
                _remove_owned_new_only_sqlite_current_at(
                    parent_fd,
                    destination.name,
                    staging.name,
                    held_current,
                    current_physical,
                )
                _fault_injection(
                    "after_new_only_sqlite_destination_unlink",
                    destination.name,
                )
                _link_held_sqlite_bundle_to_retained_guard_at(
                    parent_fd,
                    staging.name,
                    retained_guard.name,
                    held_staging,
                    replacement_physical,
                    component_identities,
                )
                guard_record = (
                    _retained_external_write_guard_record(
                        journal["migrationId"],
                        journal["snapshotId"],
                        item["kind"],
                        replacement_physical,
                        item["expectedDigest"],
                        component_identities,
                    )
                )
                _write_retained_external_write_guard_record(
                    paths, guard_record
                )
                item["phase"] = "recovered"
                item["sqliteComponentPhase"] = (
                    "retained_external_write_guard"
                )
                _write_journal(paths, journal)
                _fault_injection(
                    "after_new_only_sqlite_recovery_journal",
                    destination.name,
                )
                _remove_held_sqlite_bundle_at(
                    parent_fd,
                    staging.name,
                    held_staging,
                    replacement_physical,
                    fault_prefix="after_new_only_sqlite_staging",
                    fault_kind=destination.name,
                )
                _fault_injection(
                    "after_new_only_sqlite_staging_cleanup_before_unlock",
                    destination.name,
                )

            _remove_held_sqlite_bundle_at(
                parent_fd,
                quarantine_name,
                held_quarantine,
                recovery_physical,
            )


def _recover_apply_journal(paths: TomosPaths, journal: dict) -> None:
    journal["state"] = "recovering"
    journal.pop("recoveryErrorCount", None)
    _write_journal(paths, journal)
    failures = 0
    for item in reversed(journal.get("items", [])):
        try:
            destination = _destination_for_kind(paths, item["kind"])
            snapshot = _snapshot_path(
                destination, journal["snapshotId"]
            )
            staging = _staging_path(
                destination, journal["migrationId"]
            )
            phase = item.get("phase")
            expected = item.get("expectedDigest")
            parent_fd = _open_directory_chain(destination.parent)
            try:
                if (
                    not item.get("hadDestination")
                    and _is_sqlite_kind(item["kind"])
                ):
                    _recover_new_only_sqlite_apply_item_at(
                        paths,
                        journal,
                        item,
                        parent_fd,
                        destination,
                        staging,
                    )
                    continue
                if (
                    item.get("hadDestination")
                    and _is_sqlite_kind(item["kind"])
                ):
                    apply_backup = _apply_backup_path(
                        destination, journal["migrationId"]
                    )
                    physical = item["priorPhysicalDigest"]
                    replacement_physical = item[
                        "replacementPhysicalDigest"
                    ]
                    displaced = _sqlite_displaced_path(
                        apply_backup
                    ).name
                    if phase == "recovered":
                        _validate_sqlite_physical_and_logical_at(
                            parent_fd,
                            destination.name,
                            physical,
                            item["priorDigest"],
                            f"{apply_backup.name}.current-probe",
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd, snapshot.name
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd, staging.name
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd, apply_backup.name
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd,
                            _physical_restore_path(
                                apply_backup
                            ).name,
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd, displaced
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd,
                            f"{apply_backup.name}.current-probe",
                        )
                        continue
                    destination_exists = _entry_exists_at(
                        parent_fd, destination.name
                    )
                    if not destination_exists:
                        raise MigrationValidationError(
                            "SQLite current is missing during recovery"
                        )
                    observed_physical = _sqlite_physical_digest_at(
                        parent_fd, destination.name
                    )
                    current_is_prior = observed_physical == physical
                    current_is_replacement = (
                        observed_physical == replacement_physical
                    )
                    current_is_publish_progress = (
                        _sqlite_physical_is_publish_progress(
                            observed_physical,
                            physical,
                            replacement_physical,
                        )
                    )
                    current_is_recovery_progress = (
                        phase == "recovery_pending"
                        and _sqlite_physical_is_expected_subset(
                            observed_physical, physical
                        )
                    )
                    if current_is_prior:
                        _validate_sqlite_physical_and_logical_at(
                            parent_fd,
                            destination.name,
                            physical,
                            item["priorDigest"],
                            f"{apply_backup.name}.current-probe",
                        )
                    elif current_is_replacement:
                        _validate_sqlite_physical_and_logical_at(
                            parent_fd,
                            destination.name,
                            replacement_physical,
                            expected,
                            f"{apply_backup.name}.current-probe",
                        )
                    preownership_phases = {
                        "prepared",
                        "snapshot_pending",
                        "snapshotted",
                        "ownership_pending",
                    }
                    if phase in preownership_phases:
                        if not current_is_prior:
                            raise MigrationValidationError(
                                "changed current blocks recovery before ownership"
                            )
                    elif current_is_prior:
                        pass
                    elif (
                        current_is_replacement
                        or current_is_publish_progress
                        or current_is_recovery_progress
                    ):
                        if not _entry_exists_at(
                            parent_fd, apply_backup.name
                        ):
                            raise MigrationValidationError(
                                "SQLite physical recovery snapshot is missing"
                            )
                        if "recoveryCurrentPhysicalDigest" not in item:
                            item[
                                "recoveryCurrentPhysicalDigest"
                            ] = observed_physical
                        quarantine_physical = item[
                            "recoveryCurrentPhysicalDigest"
                        ]
                        item["phase"] = "recovery_pending"
                        _write_journal(paths, journal)

                        def record_component_phase(
                            component: str,
                        ) -> None:
                            item["sqliteComponentPhase"] = component
                            _write_journal(paths, journal)

                        _restore_sqlite_physical_at(
                            parent_fd,
                            destination.name,
                            apply_backup.name,
                            physical,
                            item["priorDigest"],
                            expected_current_physical=observed_physical,
                            quarantine_physical=quarantine_physical,
                            component_phase=record_component_phase,
                        )
                    else:
                        raise MigrationValidationError(
                            "changed current blocks migration-owned recovery"
                        )
                    item["phase"] = "recovered"
                    _write_journal(paths, journal)
                    _remove_sqlite_bundle_at(
                        parent_fd, snapshot.name
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd, staging.name
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd, apply_backup.name
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd,
                        _physical_restore_path(apply_backup).name,
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd, displaced
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd,
                        f"{apply_backup.name}.current-probe",
                    )
                    continue
                if phase == "recovered":
                    _remove_entry_at(parent_fd, staging.name)
                    continue
                if item.get("hadDestination"):
                    if _entry_exists_at(parent_fd, snapshot.name):
                        if (
                            _managed_digest_at(
                                parent_fd,
                                snapshot.name,
                                sqlite_logical=_is_sqlite_kind(
                                    item["kind"]
                                ),
                            )
                            != item["priorDigest"]
                        ):
                            raise MigrationValidationError(
                                "changed snapshot blocks recovery"
                            )
                        if _entry_exists_at(
                            parent_fd, destination.name
                        ):
                            current_digest = _managed_digest_at(
                                parent_fd,
                                destination.name,
                                sqlite_logical=_is_sqlite_kind(
                                    item["kind"]
                                ),
                            )
                            if (
                                phase
                                in {
                                    "publish_pending",
                                    "published",
                                    "restore_pending",
                                }
                                and current_digest == expected
                            ):
                                _remove_entry_at(
                                    parent_fd, destination.name
                                )
                                if _is_sqlite_kind(item["kind"]):
                                    _remove_sqlite_sidecars_at(
                                        parent_fd, destination.name
                                    )
                            elif (
                                phase
                                in {
                                    "snapshot_pending",
                                    "snapshotted",
                                    "publish_pending",
                                }
                                and current_digest
                                == item["priorDigest"]
                            ):
                                _remove_entry_at(
                                    parent_fd, snapshot.name
                                )
                                item["phase"] = "recovered"
                                _write_journal(paths, journal)
                                _remove_entry_at(
                                    parent_fd, staging.name
                                )
                                continue
                            else:
                                raise MigrationValidationError(
                                    "changed current blocks recovery"
                                )
                        item["phase"] = "restore_pending"
                        _write_journal(paths, journal)
                        _replace_at(
                            parent_fd,
                            snapshot.name,
                            parent_fd,
                            destination.name,
                        )
                        if _is_sqlite_kind(item["kind"]):
                            _remove_sqlite_sidecars_at(
                                parent_fd, destination.name
                            )
                        item["phase"] = "recovered"
                        _write_journal(paths, journal)
                    elif (
                        phase == "restore_pending"
                        and _entry_exists_at(
                            parent_fd, destination.name
                        )
                        and _managed_digest_at(
                            parent_fd,
                            destination.name,
                            sqlite_logical=_is_sqlite_kind(
                                item["kind"]
                            ),
                        )
                        == item["priorDigest"]
                    ):
                        item["phase"] = "recovered"
                        _write_journal(paths, journal)
                    elif phase not in {
                        "prepared",
                        "snapshot_pending",
                    }:
                        raise MigrationValidationError(
                            "snapshot is missing during recovery"
                        )
                elif (
                    phase in {"publish_pending", "published"}
                    and _entry_exists_at(
                        parent_fd, destination.name
                    )
                ):
                    if (
                        _managed_digest_at(
                            parent_fd,
                            destination.name,
                            sqlite_logical=_is_sqlite_kind(
                                item["kind"]
                            ),
                        )
                        != expected
                    ):
                        raise MigrationValidationError(
                            "changed current blocks recovery"
                        )
                    _remove_entry_at(parent_fd, destination.name)
                    item["phase"] = "recovered"
                    _write_journal(paths, journal)
                elif not item.get("hadDestination"):
                    item["phase"] = "recovered"
                    _write_journal(paths, journal)
                _remove_entry_at(parent_fd, staging.name)
            finally:
                os.close(parent_fd)
        except (OSError, MigrationError, KeyError, TypeError):
            failures += 1
    if failures:
        journal["state"] = "restore_failed"
        journal["recoveryErrorCount"] = failures
        _write_journal(paths, journal)
        raise MigrationValidationError(
            "migration recovery remains pending"
        )
    _safe_remove_durable(
        _completion_record_path(paths, journal["migrationId"])
    )
    _safe_remove_durable(
        _snapshot_record_path(paths, journal["snapshotId"])
    )
    _safe_remove_durable(_journal_path(paths, journal["migrationId"]))


def _recover_rollback_journal(paths: TomosPaths, journal: dict) -> None:
    journal["state"] = "recovering"
    journal.pop("recoveryErrorCount", None)
    _write_journal(paths, journal)
    failures = 0
    for item in reversed(journal.get("items", [])):
        try:
            destination = _destination_for_kind(paths, item["kind"])
            snapshot = _snapshot_path(
                destination, journal["snapshotId"]
            )
            backup = _rollback_backup_path(
                destination, journal["snapshotId"]
            )
            parent_fd = _open_directory_chain(destination.parent)
            try:
                if _is_sqlite_kind(item["kind"]):
                    physical = item["publishedPhysicalDigest"]
                    restore_physical = item.get(
                        "restorePhysicalDigest"
                    )
                    restore = _rollback_restore_path(
                        destination, journal["snapshotId"]
                    )
                    displaced = _sqlite_displaced_path(backup).name
                    destination_exists = _entry_exists_at(
                        parent_fd, destination.name
                    )
                    observed_physical = (
                        _sqlite_physical_digest_at(
                            parent_fd, destination.name
                        )
                        if destination_exists
                        else None
                    )
                    current_is_published = (
                        observed_physical == physical
                    )
                    current_is_restored = (
                        item["hadDestination"]
                        and observed_physical == restore_physical
                    )
                    current_is_restore_progress = (
                        item["hadDestination"]
                        and observed_physical is not None
                        and _sqlite_physical_is_publish_progress(
                            observed_physical,
                            physical,
                            restore_physical,
                        )
                    )
                    current_is_recovery_progress = (
                        item["phase"] == "recovery_pending"
                        and observed_physical is not None
                        and _sqlite_physical_is_expected_subset(
                            observed_physical, physical
                        )
                    )
                    if current_is_published:
                        _validate_sqlite_physical_and_logical_at(
                            parent_fd,
                            destination.name,
                            physical,
                            item["publishedDigest"],
                            f"{backup.name}.current-probe",
                        )
                    elif current_is_restored:
                        _validate_sqlite_physical_and_logical_at(
                            parent_fd,
                            destination.name,
                            restore_physical,
                            item["priorDigest"],
                            f"{backup.name}.current-probe",
                        )
                    if item["phase"] in {
                        "prepared",
                        "ownership_pending",
                    }:
                        if not current_is_published:
                            raise MigrationValidationError(
                                "changed rollback current blocks recovery before ownership"
                            )
                    elif current_is_published:
                        pass
                    elif (
                        current_is_restored
                        or current_is_restore_progress
                        or current_is_recovery_progress
                    ):
                        if not _entry_exists_at(
                            parent_fd, backup.name
                        ):
                            raise MigrationValidationError(
                                "rollback physical backup is missing"
                            )
                        if "recoveryCurrentPhysicalDigest" not in item:
                            item[
                                "recoveryCurrentPhysicalDigest"
                            ] = observed_physical
                        quarantine_physical = item[
                            "recoveryCurrentPhysicalDigest"
                        ]
                        item["phase"] = "recovery_pending"
                        _write_journal(paths, journal)

                        def record_component_phase(
                            component: str,
                        ) -> None:
                            item["sqliteComponentPhase"] = component
                            _write_journal(paths, journal)

                        _restore_sqlite_physical_at(
                            parent_fd,
                            destination.name,
                            backup.name,
                            physical,
                            item["publishedDigest"],
                            expected_current_physical=observed_physical,
                            quarantine_physical=quarantine_physical,
                            component_phase=record_component_phase,
                        )
                    elif (
                        not item["hadDestination"]
                        and not destination_exists
                    ):
                        restore_name = (
                            f"{backup.name}.restore"
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd, restore_name
                        )
                        _copy_sqlite_physical_at(
                            parent_fd,
                            backup.name,
                            restore_name,
                            expected_physical=physical,
                        )
                        try:
                            with _locked_sqlite_physical_bundle_at(
                                parent_fd,
                                restore_name,
                                physical,
                            ) as held_restore:
                                if _entry_exists_at(
                                    parent_fd, destination.name
                                ):
                                    raise MigrationValidationError(
                                        "rollback destination changed during recovery"
                                    )

                                def record_component_phase(
                                    component: str,
                                ) -> None:
                                    item[
                                        "sqliteComponentPhase"
                                    ] = component
                                    _write_journal(paths, journal)

                                _publish_locked_sqlite_bundle_at(
                                    parent_fd,
                                    restore_name,
                                    destination.name,
                                    held_restore,
                                    physical,
                                    record_component_phase,
                                )
                        finally:
                            _remove_sqlite_bundle_at(
                                parent_fd, restore_name
                            )
                    else:
                        raise MigrationValidationError(
                            "changed rollback current blocks migration-owned recovery"
                        )
                    _remove_sqlite_bundle_at(
                        parent_fd, restore.name
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd, backup.name
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd,
                        _physical_restore_path(backup).name,
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd,
                        f"{backup.name}.current-probe",
                    )
                    _remove_sqlite_bundle_at(
                        parent_fd, displaced
                    )
                    continue
                if _entry_exists_at(parent_fd, backup.name):
                    if (
                        _managed_digest_at(
                            parent_fd,
                            backup.name,
                            sqlite_logical=_is_sqlite_kind(
                                item["kind"]
                            ),
                        )
                        != item["publishedDigest"]
                    ):
                        raise MigrationValidationError(
                            "changed rollback backup blocks recovery"
                        )
                    if (
                        item.get("hadDestination")
                        and _entry_exists_at(
                            parent_fd, destination.name
                        )
                    ):
                        if (
                            _managed_digest_at(
                                parent_fd,
                                destination.name,
                                sqlite_logical=_is_sqlite_kind(
                                    item["kind"]
                                ),
                            )
                            != item["priorDigest"]
                        ):
                            raise MigrationValidationError(
                                "changed restored snapshot blocks recovery"
                            )
                        if _entry_exists_at(parent_fd, snapshot.name):
                            raise MigrationValidationError(
                                "rollback snapshot collision"
                            )
                        _replace_at(
                            parent_fd,
                            destination.name,
                            parent_fd,
                            snapshot.name,
                        )
                    elif item.get("hadDestination"):
                        if (
                            not _entry_exists_at(
                                parent_fd, snapshot.name
                            )
                            or _managed_digest_at(
                                parent_fd,
                                snapshot.name,
                                sqlite_logical=_is_sqlite_kind(
                                    item["kind"]
                                ),
                            )
                            != item["priorDigest"]
                        ):
                            raise MigrationValidationError(
                                "changed snapshot blocks recovery"
                            )
                    elif _entry_exists_at(
                        parent_fd, destination.name
                    ):
                        raise MigrationValidationError(
                            "rollback destination collision"
                        )
                    elif _entry_exists_at(parent_fd, snapshot.name):
                        raise MigrationValidationError(
                            "unexpected rollback snapshot"
                        )
                    _replace_at(
                        parent_fd,
                        backup.name,
                        parent_fd,
                        destination.name,
                    )
                    if _is_sqlite_kind(item["kind"]):
                        _remove_sqlite_sidecars_at(
                            parent_fd, destination.name
                        )
            finally:
                os.close(parent_fd)
        except (OSError, MigrationError, KeyError, TypeError):
            failures += 1
    if failures:
        journal["state"] = "restore_failed"
        journal["recoveryErrorCount"] = failures
        _write_journal(paths, journal)
        raise MigrationValidationError(
            "rollback recovery remains pending"
        )
    _safe_remove_durable(_journal_path(paths, journal["journalId"]))


def _finish_rollback_commit(paths: TomosPaths, journal: dict) -> bool:
    completion = _validate_rollback_final_state(paths, journal)
    completion_path = _completion_record_path(paths, journal["migrationId"])
    if completion["status"] != "rolled_back":
        completion["status"] = "rolled_back"
        _write_record(completion_path, completion)
    if journal["state"] == "commit_pending":
        journal["state"] = "committed"
        _write_journal(paths, journal)
    return _resume_rollback_cleanup(paths, journal)


def _resume_apply_cleanup(paths: TomosPaths, journal: dict) -> bool:
    _validate_apply_final_state(paths, journal)
    try:
        pending_ids = list(journal.get("pruneSnapshotIds", []))
        for old_snapshot_id in pending_ids:
            if not _valid_identifier(old_snapshot_id):
                continue
            old_record_path = _snapshot_record_path(
                paths, old_snapshot_id
            )
            old_record = _read_record(old_record_path)
            if old_record:
                old_record = _validate_snapshot_record_schema(
                    old_snapshot_id, old_record
                )
                _validate_snapshot_completion(
                    paths,
                    old_record,
                    allowed_statuses=frozenset(
                        {"completed", "superseded"}
                    ),
                )
                old_migration_id = old_record.get("migrationId")
                if _valid_identifier(old_migration_id):
                    completion_path = _completion_record_path(
                        paths, old_migration_id
                    )
                    completion = _read_record(completion_path)
                    if completion:
                        completion["status"] = "superseded"
                        _write_record(completion_path, completion)
                for item in old_record.get("items", []):
                    if (
                        isinstance(item, dict)
                        and item.get("kind") in _known_kinds()
                        and item.get("hadDestination") is True
                    ):
                        destination = _destination_for_kind(
                            paths, item["kind"]
                        )
                        _remove_path_durable(
                            _snapshot_path(
                                destination, old_snapshot_id
                            )
                        )
                _remove_path_durable(old_record_path)
            journal["pruneSnapshotIds"].remove(old_snapshot_id)
            _write_journal(paths, journal)
        for item in journal["items"]:
            if not _is_sqlite_kind(item["kind"]):
                continue
            destination = _destination_for_kind(
                paths, item["kind"]
            )
            backup = _apply_backup_path(
                destination, journal["migrationId"]
            )
            parent_fd = _open_directory_chain(destination.parent)
            try:
                if not item["hadDestination"]:
                    _cleanup_new_only_sqlite_internal_at(
                        parent_fd,
                        _staging_path(
                            destination, journal["migrationId"]
                        ).name,
                        _sqlite_displaced_path(backup).name,
                        item["replacementPhysicalDigest"],
                        item.get("recoveryCurrentPhysicalDigest"),
                    )
                    continue
                if _entry_exists_at(parent_fd, backup.name):
                    if (
                        _sqlite_physical_digest_at(
                            parent_fd, backup.name
                        )
                        != item["priorPhysicalDigest"]
                    ):
                        raise MigrationValidationError(
                            "SQLite physical recovery snapshot changed"
                        )
                    _remove_sqlite_bundle_at(
                        parent_fd, backup.name
                    )
                _remove_sqlite_bundle_at(
                    parent_fd,
                    _physical_restore_path(backup).name,
                )
            finally:
                os.close(parent_fd)
        _remove_path_durable(
            _journal_path(paths, journal["migrationId"])
        )
        return True
    except (OSError, MigrationError, KeyError, TypeError):
        journal["state"] = "prune_pending"
        try:
            _write_journal(paths, journal)
        except (OSError, MigrationError):
            pass
        return False


def _resume_rollback_cleanup(paths: TomosPaths, journal: dict) -> bool:
    try:
        if journal["state"] != "record_cleanup_pending":
            if journal["state"] != "cleanup_pending":
                journal["state"] = "cleanup_pending"
                _write_journal(paths, journal)
            _validate_rollback_final_state(paths, journal)
            for item in journal["items"]:
                destination = _destination_for_kind(
                    paths, item["kind"]
                )
                if _is_sqlite_kind(item["kind"]):
                    parent_fd = _open_directory_chain(
                        destination.parent
                    )
                    try:
                        backup = _rollback_backup_path(
                            destination, journal["snapshotId"]
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd, backup.name
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd,
                            _physical_restore_path(backup).name,
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd,
                            _rollback_restore_path(
                                destination,
                                journal["snapshotId"],
                            ).name,
                        )
                        _remove_sqlite_bundle_at(
                            parent_fd,
                            _snapshot_path(
                                destination,
                                journal["snapshotId"],
                            ).name,
                        )
                    finally:
                        os.close(parent_fd)
                else:
                    _remove_path_durable(
                        _rollback_backup_path(
                            destination, journal["snapshotId"]
                        )
                    )
            journal["state"] = "record_cleanup_pending"
            _write_journal(paths, journal)
        _validate_rollback_final_state(paths, journal)
        _remove_path_durable(
            _snapshot_record_path(paths, journal["snapshotId"])
        )
        _remove_path_durable(
            _journal_path(paths, journal["journalId"])
        )
        return True
    except (OSError, MigrationError, KeyError, TypeError):
        if journal.get("state") != "record_cleanup_pending":
            journal["state"] = "cleanup_pending"
        try:
            _write_journal(paths, journal)
        except (OSError, MigrationError):
            pass
        return False


def _stage_source(
    source: MigrationSource, expected_signature: str, migration_id: str
) -> _StagedItem:
    provenance = _validated_provenance(source)
    if provenance is None:
        raise MigrationPreviewStaleError(
            "migration source is invalid"
    )
    destination = source.destination
    staging = _staging_path(destination, migration_id)
    destination_parent_fd = _open_directory_chain(
        destination.parent, create=True
    )
    if _entry_exists_at(destination_parent_fd, staging.name):
        os.close(destination_parent_fd)
        raise MigrationValidationError(
            "migration staging already exists"
        )
    root_fd = -1
    source_fd = -1
    staging_fd = -1
    try:
        try:
            root_fd = _open_directory_path(provenance.root)
            if provenance.location.is_directory:
                source_fd = _open_relative_directory(
                    root_fd, provenance.location.relative.parts
                )
            else:
                source_fd = _open_relative_file(
                    root_fd, provenance.location.relative.parts
                )
        except OSError as error:
            raise MigrationPreviewStaleError(
                "migration source cannot be opened"
            ) from error
        if provenance.location.is_directory:
            metadata, _excluded, errors = _collect_open_directory(
                provenance.location.kind, source_fd
            )
            if errors:
                raise MigrationPreviewStaleError(
                    "migration source cannot be read"
                )
            if (
                _digest_json(_source_signature_payload(source, metadata))
                != expected_signature
            ):
                raise MigrationPreviewStaleError(
                    "migration source changed"
                )
            os.mkdir(staging.name, 0o700, dir_fd=destination_parent_fd)
            os.fsync(destination_parent_fd)
            staging_fd = os.open(
                staging.name,
                _DIRECTORY_FLAGS,
                dir_fd=destination_parent_fd,
            )
            source_hashes = _copy_directory_files(
                provenance.location.kind,
                source_fd,
                metadata,
                staging_fd,
            )
            if _directory_manifest_fd(staging_fd) != source_hashes:
                raise MigrationValidationError(
                    "directory validation failed"
                )
            final_metadata, _excluded, final_errors = (
                _collect_open_directory(
                    provenance.location.kind, source_fd
                )
            )
            if (
                final_errors
                or _digest_json(
                    _source_signature_payload(source, final_metadata)
                )
                != expected_signature
            ):
                raise MigrationPreviewStaleError(
                    "migration directory changed during copy"
                )
            _fsync_tree_fd(staging_fd)
        else:
            source_parent_fd = _open_relative_directory(
                root_fd, provenance.location.relative.parts[:-1]
            )
            try:
                image = _sqlite_logical_image_at(
                    source_parent_fd,
                    provenance.location.relative.name,
                    expected_file_fd=source_fd,
                )
                metadata = _sqlite_metadata_from_image(
                    source_parent_fd,
                    provenance.location.relative.name,
                    provenance.location.relative.name,
                    source_fd,
                    image,
                )
                if (
                    _digest_json(
                        _source_signature_payload(source, [metadata])
                    )
                    != expected_signature
                ):
                    raise MigrationPreviewStaleError(
                        "migration source changed"
                    )
                _write_new_file_at(
                    destination_parent_fd, staging.name, image
                )
                staging_fd = os.open(
                    staging.name,
                    _FILE_FLAGS,
                    dir_fd=destination_parent_fd,
                )
                _validate_sqlite_fd(staging_fd)
            finally:
                os.close(source_parent_fd)
        expected_digest = _managed_digest_at(
            destination_parent_fd,
            staging.name,
            sqlite_logical=_is_sqlite_kind(source.kind),
        )
        os.fsync(destination_parent_fd)
    except Exception:
        try:
            _remove_entry_at(destination_parent_fd, staging.name)
        except (OSError, MigrationError):
            pass
        raise
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        if source_fd >= 0:
            os.close(source_fd)
        if root_fd >= 0:
            os.close(root_fd)
        os.close(destination_parent_fd)
    return _StagedItem(
        kind=source.kind,
        destination=destination,
        staging=staging,
        expected_digest=expected_digest,
    )


def _validate_source_after_staging(
    source: MigrationSource,
    expected_signature: str,
    expected_digest: dict,
) -> None:
    """Re-read the approved source immediately before publish."""
    provenance = _validated_provenance(source)
    if provenance is None:
        raise MigrationPreviewStaleError(
            "migration source is invalid"
        )
    root_fd = -1
    source_fd = -1
    parent_fd = -1
    try:
        root_fd = _open_directory_path(provenance.root)
        if provenance.location.is_directory:
            source_fd = _open_relative_directory(
                root_fd, provenance.location.relative.parts
            )
            metadata, _excluded, errors = _collect_open_directory(
                provenance.location.kind, source_fd
            )
            if errors:
                raise MigrationPreviewStaleError(
                    "migration source cannot be read"
                )
            observed_digest = {
                "type": "directory",
                "fileCount": len(metadata),
                "sha256": _digest_json(
                    [
                        {
                            "name": item.relative_name,
                            "sha256": item.sha256,
                        }
                        for item in sorted(
                            metadata,
                            key=lambda candidate: candidate.relative_name,
                        )
                    ]
                ),
            }
        else:
            parent_fd = _open_relative_directory(
                root_fd, provenance.location.relative.parts[:-1]
            )
            source_fd = _open_child_file(
                parent_fd, provenance.location.relative.name
            )
            image = _sqlite_logical_image_at(
                parent_fd,
                provenance.location.relative.name,
                expected_file_fd=source_fd,
            )
            metadata = [
                _sqlite_metadata_from_image(
                    parent_fd,
                    provenance.location.relative.name,
                    provenance.location.relative.name,
                    source_fd,
                    image,
                )
            ]
            observed_digest = _sqlite_image_digest(image)
        observed_signature = _digest_json(
            _source_signature_payload(source, metadata)
        )
        if (
            observed_signature != expected_signature
            or observed_digest != expected_digest
        ):
            raise MigrationPreviewStaleError(
                "migration source changed after staging"
            )
    except MigrationPreviewStaleError:
        raise
    except (OSError, MigrationError, sqlite3.Error) as error:
        raise MigrationPreviewStaleError(
            "migration source changed after staging"
        ) from error
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
        if root_fd >= 0:
            os.close(root_fd)


def _directory_digest_from_metadata(
    metadata: Sequence[_FileMetadata],
) -> dict:
    return {
        "type": "directory",
        "fileCount": len(metadata),
        "sha256": _digest_json(
            [
                {
                    "name": item.relative_name,
                    "sha256": item.sha256,
                }
                for item in sorted(
                    metadata,
                    key=lambda candidate: candidate.relative_name,
                )
            ]
        ),
    }


@contextmanager
def _held_legacy_directory_sources(
    sources: Sequence[MigrationSource],
    expected_signatures: dict[str, str],
    expected_digests: dict[str, dict],
) -> Iterator[dict[str, _HeldLegacyDirectory]]:
    held: list[_HeldLegacyDirectory] = []
    try:
        for source in sorted(
            (
                candidate
                for candidate in sources
                if not _is_sqlite_kind(candidate.kind)
            ),
            key=lambda candidate: (
                candidate.kind,
                str(candidate.source),
            ),
        ):
            provenance = _validated_provenance(source)
            if provenance is None or not provenance.location.is_directory:
                raise MigrationPreviewStaleError(
                    "migration source is invalid"
                )
            root_fd = -1
            source_fd = -1
            file_fds: dict[str, int] = {}
            try:
                root_fd = _open_directory_path(provenance.root)
                source_fd = _open_relative_directory(
                    root_fd, provenance.location.relative.parts
                )
                metadata, _excluded, errors = _collect_open_directory(
                    provenance.location.kind, source_fd
                )
                if (
                    errors
                    or _digest_json(
                        _source_signature_payload(source, metadata)
                    )
                    != expected_signatures[source.kind]
                    or _directory_digest_from_metadata(metadata)
                    != expected_digests[source.kind]
                ):
                    raise MigrationPreviewStaleError(
                        "migration directory changed after staging"
                    )
                for item in metadata:
                    file_fd = _open_relative_file(
                        source_fd, Path(item.relative_name).parts
                    )
                    observed = _metadata_from_fd(
                        item.relative_name, file_fd
                    )
                    if (
                        observed != item
                        or not _allowed_directory_file(
                            source.kind,
                            item.relative_name,
                            file_fd,
                            os.fstat(file_fd),
                        )
                    ):
                        os.close(file_fd)
                        raise MigrationPreviewStaleError(
                            "migration directory changed after staging"
                        )
                    file_fds[item.relative_name] = file_fd
                held.append(
                    _HeldLegacyDirectory(
                        source=source,
                        provenance=provenance,
                        root_fd=root_fd,
                        source_fd=source_fd,
                        metadata=tuple(metadata),
                        file_fds=file_fds,
                    )
                )
                root_fd = -1
                source_fd = -1
                file_fds = {}
            except MigrationPreviewStaleError:
                raise
            except (OSError, MigrationError) as error:
                raise MigrationPreviewStaleError(
                    "migration directory changed after staging"
                ) from error
            finally:
                for file_fd in file_fds.values():
                    os.close(file_fd)
                if source_fd >= 0:
                    os.close(source_fd)
                if root_fd >= 0:
                    os.close(root_fd)
        by_kind = {item.source.kind: item for item in held}
        for item in held:
            _validate_held_legacy_directory_source(
                item,
                expected_signatures[item.source.kind],
                expected_digests[item.source.kind],
            )
        yield by_kind
    finally:
        for item in reversed(held):
            for file_fd in item.file_fds.values():
                os.close(file_fd)
            os.close(item.source_fd)
            os.close(item.root_fd)


def _validate_held_legacy_directory_source(
    item: _HeldLegacyDirectory,
    expected_signature: str,
    expected_digest: dict,
) -> None:
    try:
        current_root_fd = _open_directory_path(item.provenance.root)
        try:
            current_root = os.fstat(current_root_fd)
            held_root = os.fstat(item.root_fd)
            if (
                current_root.st_dev != held_root.st_dev
                or current_root.st_ino != held_root.st_ino
            ):
                raise MigrationPreviewStaleError(
                    "migration directory root changed"
                )
        finally:
            os.close(current_root_fd)
        current_source_fd = _open_relative_directory(
            item.root_fd, item.provenance.location.relative.parts
        )
        try:
            current_source = os.fstat(current_source_fd)
            held_source = os.fstat(item.source_fd)
            if (
                current_source.st_dev != held_source.st_dev
                or current_source.st_ino != held_source.st_ino
            ):
                raise MigrationPreviewStaleError(
                    "migration directory changed"
                )
        finally:
            os.close(current_source_fd)
        expected_by_name = {
            metadata.relative_name: metadata
            for metadata in item.metadata
        }
        if set(item.file_fds) != set(expected_by_name):
            raise MigrationPreviewStaleError(
                "migration directory snapshot is invalid"
            )
        for relative_name, file_fd in item.file_fds.items():
            current_file_fd = _open_relative_file(
                item.source_fd, Path(relative_name).parts
            )
            try:
                current_stat = os.fstat(current_file_fd)
                held_stat = os.fstat(file_fd)
                if (
                    current_stat.st_dev != held_stat.st_dev
                    or current_stat.st_ino != held_stat.st_ino
                ):
                    raise MigrationPreviewStaleError(
                        "migration directory file was replaced"
                    )
            finally:
                os.close(current_file_fd)
            observed = _metadata_from_fd(relative_name, file_fd)
            if (
                observed != expected_by_name[relative_name]
                or not _allowed_directory_file(
                    item.source.kind,
                    relative_name,
                    file_fd,
                    os.fstat(file_fd),
                )
            ):
                raise MigrationPreviewStaleError(
                    "migration directory file changed"
                )
        metadata, _excluded, errors = _collect_open_directory(
            item.provenance.location.kind, item.source_fd
        )
        if (
            errors
            or _digest_json(
                _source_signature_payload(item.source, metadata)
            )
            != expected_signature
            or _directory_digest_from_metadata(metadata)
            != expected_digest
        ):
            raise MigrationPreviewStaleError(
                "migration directory changed before commit"
            )
    except MigrationPreviewStaleError:
        raise
    except (OSError, MigrationError) as error:
        raise MigrationPreviewStaleError(
            "migration directory changed before commit"
        ) from error


@contextmanager
def _locked_legacy_sqlite_sources(
    sources: Sequence[MigrationSource],
    expected_signatures: dict[str, str],
    expected_digests: dict[str, dict],
) -> Iterator[dict[str, _LockedLegacySQLite]]:
    """Hold every approved legacy SQLite writer boundary until commit."""
    locked: list[_LockedLegacySQLite] = []
    _fault_injection("before_legacy_source_locks", "maintenance")
    try:
        for source in sorted(
            (
                candidate
                for candidate in sources
                if _is_sqlite_kind(candidate.kind)
            ),
            key=lambda candidate: (
                candidate.kind,
                str(candidate.source),
            ),
        ):
            provenance = _validated_provenance(source)
            if provenance is None:
                raise MigrationPreviewStaleError(
                    "migration source is invalid"
                )
            root_fd = -1
            parent_fd = -1
            source_fd = -1
            connection: sqlite3.Connection | None = None
            file_fd = -1
            try:
                root_fd = _open_directory_path(provenance.root)
                parent_fd = _open_relative_directory(
                    root_fd,
                    provenance.location.relative.parts[:-1],
                )
                source_fd = _open_child_file(
                    parent_fd,
                    provenance.location.relative.name,
                )
                connection, file_fd = _open_sqlite_connection_at(
                    parent_fd,
                    provenance.location.relative.name,
                    writable=True,
                    expected_file_fd=source_fd,
                )
                os.close(source_fd)
                source_fd = -1
                connection.execute("BEGIN IMMEDIATE")
                _verify_sqlite_connection_identity(
                    connection,
                    parent_fd,
                    provenance.location.relative.name,
                    file_fd,
                )
                locked.append(
                    _LockedLegacySQLite(
                        source=source,
                        provenance=provenance,
                        root_fd=root_fd,
                        parent_fd=parent_fd,
                        file_fd=file_fd,
                        connection=connection,
                    )
                )
                root_fd = -1
                parent_fd = -1
                file_fd = -1
                connection = None
            except MigrationPreviewStaleError:
                raise
            except (OSError, MigrationError, sqlite3.Error) as error:
                raise MigrationValidationError(
                    "legacy SQLite source is busy or unsafe"
                ) from error
            finally:
                if connection is not None:
                    connection.close()
                if file_fd >= 0:
                    os.close(file_fd)
                if source_fd >= 0:
                    os.close(source_fd)
                if parent_fd >= 0:
                    os.close(parent_fd)
                if root_fd >= 0:
                    os.close(root_fd)

        _fault_injection("after_legacy_source_locks", "maintenance")
        by_kind = {item.source.kind: item for item in locked}
        for item in locked:
            _validate_locked_legacy_sqlite_source(
                item,
                expected_signatures[item.source.kind],
                expected_digests[item.source.kind],
            )
        yield by_kind
    finally:
        for item in reversed(locked):
            try:
                if item.connection.in_transaction:
                    item.connection.rollback()
            finally:
                try:
                    item.connection.close()
                finally:
                    os.close(item.file_fd)
                    os.close(item.parent_fd)
                    os.close(item.root_fd)


def _validate_locked_legacy_sqlite_source(
    item: _LockedLegacySQLite,
    expected_signature: str,
    expected_digest: dict,
    *,
    check_signature: bool = True,
) -> None:
    name = item.provenance.location.relative.name
    try:
        _verify_sqlite_connection_identity(
            item.connection,
            item.parent_fd,
            name,
            item.file_fd,
        )
        image = _sqlite_logical_image_from_locked_connection(
            item.connection
        )
        metadata = _sqlite_metadata_from_image(
            item.parent_fd,
            name,
            name,
            item.file_fd,
            image,
        )
        observed_signature = _digest_json(
            _source_signature_payload(item.source, [metadata])
        )
        observed_digest = _sqlite_image_digest(image)
    except (OSError, MigrationError, sqlite3.Error) as error:
        raise MigrationPreviewStaleError(
            "migration source changed before publish"
        ) from error
    if (
        (check_signature and observed_signature != expected_signature)
        or observed_digest != expected_digest
    ):
        raise MigrationPreviewStaleError(
            "migration source changed before publish"
        )


def _copy_directory_files(
    kind: str,
    source_fd: int,
    metadata: Sequence[_FileMetadata],
    staging_fd: int,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for item in sorted(metadata, key=lambda candidate: candidate.relative_name):
        parts = Path(item.relative_name).parts
        try:
            file_fd = _open_relative_file(source_fd, parts)
        except OSError as error:
            raise MigrationPreviewStaleError(
                "migration source changed"
            ) from error
        try:
            observed = _metadata_from_fd(item.relative_name, file_fd)
            if observed != item or not _allowed_directory_file(
                kind, item.relative_name, file_fd, os.fstat(file_fd)
            ):
                raise MigrationPreviewStaleError(
                    "migration source changed"
                )
            target_parent_fd = _open_relative_directory_create(
                staging_fd, parts[:-1]
            )
            try:
                copied_hash = _copy_open_file_at(
                    file_fd,
                    item,
                    target_parent_fd,
                    parts[-1],
                )
            finally:
                os.close(target_parent_fd)
            if copied_hash != item.sha256:
                raise MigrationPreviewStaleError(
                    "migration source content changed"
                )
            hashes[item.relative_name] = copied_hash
        finally:
            os.close(file_fd)
    return hashes


def _collect_source(
    provenance: _SourceProvenance,
) -> tuple[list[_FileMetadata], int, int]:
    try:
        root_fd = _open_directory_path(provenance.root)
    except OSError as error:
        return _source_open_failure(error)
    try:
        if provenance.location.is_directory:
            source_fd = _open_relative_directory(
                root_fd, provenance.location.relative.parts
            )
            try:
                return _collect_open_directory(
                    provenance.location.kind, source_fd
                )
            finally:
                os.close(source_fd)
        parent_fd = _open_relative_directory(
            root_fd, provenance.location.relative.parts[:-1]
        )
        try:
            source_fd = _open_child_file(
                parent_fd, provenance.location.relative.name
            )
            try:
                try:
                    image = _sqlite_logical_image_at(
                        parent_fd,
                        provenance.location.relative.name,
                        expected_file_fd=source_fd,
                    )
                    metadata = _sqlite_metadata_from_image(
                        parent_fd,
                        provenance.location.relative.name,
                        provenance.location.relative.name,
                        source_fd,
                        image,
                    )
                except MigrationValidationError:
                    metadata = _metadata_from_fd(
                        provenance.location.relative.name, source_fd
                    )
                return [metadata], 0, 0
            finally:
                os.close(source_fd)
        finally:
            os.close(parent_fd)
    except OSError as error:
        return _source_open_failure(error)
    finally:
        os.close(root_fd)


def _collect_open_directory(
    kind: str, source_fd: int
) -> tuple[list[_FileMetadata], int, int]:
    if kind == "study-packs":
        return _collect_study_packs(source_fd)
    return _collect_person_photos(source_fd)


def _collect_study_packs(
    root_fd: int,
) -> tuple[list[_FileMetadata], int, int]:
    names, errors = _directory_names(root_fd)
    files: list[_FileMetadata] = []
    excluded = 0
    for name in names:
        if name != _OFFICIAL_PACK_DIRECTORY or _is_sensitive_name(name):
            excluded += 1
            continue
        child_fd, status = _open_child(root_fd, name)
        if child_fd is None:
            if status == "excluded":
                excluded += 1
            else:
                errors += 1
            continue
        try:
            if not stat.S_ISDIR(os.fstat(child_fd).st_mode):
                excluded += 1
                continue
            manifest_status = _official_pack_status(child_fd)
            if manifest_status == "excluded":
                excluded += 1
                continue
            if manifest_status == "error":
                errors += 1
                continue
            child_files, child_excluded, child_errors = _scan_directory(
                child_fd,
                (name,),
                lambda relative_name, fd, file_stat: (
                    _is_official_study_pack_file(
                        relative_name.split("/", 1)[1],
                        fd,
                        file_stat,
                    )
                ),
            )
            files.extend(child_files)
            excluded += child_excluded
            errors += child_errors
        finally:
            os.close(child_fd)
    return files, excluded, errors


def _collect_person_photos(
    root_fd: int,
) -> tuple[list[_FileMetadata], int, int]:
    return _scan_directory(root_fd, (), _is_person_photo_file)


def _scan_directory(
    directory_fd: int,
    relative_parts: tuple[str, ...],
    allowed_file: Callable[[str, int, os.stat_result], bool],
) -> tuple[list[_FileMetadata], int, int]:
    names, errors = _directory_names(directory_fd)
    files: list[_FileMetadata] = []
    excluded = 0
    for name in names:
        if _is_sensitive_name(name):
            excluded += 1
            continue
        child_fd, status = _open_child(directory_fd, name)
        if child_fd is None:
            if status == "excluded":
                excluded += 1
            else:
                errors += 1
            continue
        try:
            child_stat = os.fstat(child_fd)
            child_relative = relative_parts + (name,)
            if stat.S_ISDIR(child_stat.st_mode):
                nested_files, nested_excluded, nested_errors = (
                    _scan_directory(
                        child_fd, child_relative, allowed_file
                    )
                )
                files.extend(nested_files)
                excluded += nested_excluded
                errors += nested_errors
            elif stat.S_ISREG(child_stat.st_mode):
                relative_name = "/".join(child_relative)
                if allowed_file(relative_name, child_fd, child_stat):
                    files.append(
                        _metadata_from_fd(relative_name, child_fd)
                    )
                else:
                    excluded += 1
            else:
                excluded += 1
        finally:
            os.close(child_fd)
    return files, excluded, errors


def _source_signature_payload(
    source: MigrationSource, files: Sequence[_FileMetadata]
) -> dict:
    provenance = source._provenance
    is_directory = bool(
        provenance and provenance.location.is_directory
    )
    return {
        "kind": source.kind,
        "source": str(source.source),
        "destination": str(source.destination),
        "files": [
            {
                "source": str(
                    source.source / item.relative_name
                    if is_directory
                    else source.source
                ),
                "size": item.size,
                "mtimeNs": item.mtime_ns,
                "device": item.device,
                "inode": item.inode,
                "sha256": item.sha256,
                "destination": str(
                    source.destination / item.relative_name
                    if is_directory
                    else source.destination
                ),
            }
            for item in sorted(
                files, key=lambda candidate: candidate.relative_name
            )
        ],
    }


def _metadata_from_fd(relative_name: str, file_fd: int) -> _FileMetadata:
    file_stat = os.fstat(file_fd)
    if not stat.S_ISREG(file_stat.st_mode):
        raise OSError(errno.EINVAL, "not a regular file")
    return _FileMetadata(
        relative_name=relative_name,
        size=file_stat.st_size,
        mtime=file_stat.st_mtime,
        mtime_ns=file_stat.st_mtime_ns,
        device=file_stat.st_dev,
        inode=file_stat.st_ino,
        sha256=_hash_open_file(file_fd),
    )


def _is_sqlite_kind(kind: str) -> bool:
    return kind in _SQLITE_KINDS


def _sqlite_metadata_from_image(
    parent_fd: int,
    name: str,
    relative_name: str,
    file_fd: int,
    image: bytes,
) -> _FileMetadata:
    file_stat = os.fstat(file_fd)
    if not stat.S_ISREG(file_stat.st_mode):
        raise OSError(errno.EINVAL, "not a regular file")
    latest_mtime = file_stat.st_mtime
    latest_mtime_ns = file_stat.st_mtime_ns
    try:
        wal_stat = os.stat(
            f"{name}-wal", dir_fd=parent_fd, follow_symlinks=False
        )
    except FileNotFoundError:
        wal_stat = None
    except OSError as error:
        raise MigrationValidationError(
            "SQLite WAL metadata cannot be read"
        ) from error
    if wal_stat is not None:
        if not stat.S_ISREG(wal_stat.st_mode):
            raise MigrationValidationError(
                "SQLite WAL has an invalid type"
            )
        if wal_stat.st_mtime_ns > latest_mtime_ns:
            latest_mtime = wal_stat.st_mtime
            latest_mtime_ns = wal_stat.st_mtime_ns
    digest = _sqlite_image_digest(image)
    return _FileMetadata(
        relative_name=relative_name,
        size=digest["bytes"],
        mtime=latest_mtime,
        mtime_ns=latest_mtime_ns,
        device=file_stat.st_dev,
        inode=file_stat.st_ino,
        sha256=digest["sha256"],
    )


def _write_new_file_at(
    parent_fd: int, name: str, payload: bytes
) -> None:
    try:
        file_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise MigrationValidationError(
            "staging file cannot be created"
        ) from error
    try:
        _write_all(file_fd, payload)
        os.fsync(file_fd)
    except BaseException:
        try:
            os.unlink(name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except OSError:
            pass
        raise
    finally:
        os.close(file_fd)
    os.fsync(parent_fd)


def _copy_open_file(
    source_fd: int, expected: _FileMetadata, destination: Path
) -> str:
    parent_fd = _open_directory_chain(destination.parent, create=True)
    try:
        return _copy_open_file_at(
            source_fd, expected, parent_fd, destination.name
        )
    finally:
        os.close(parent_fd)


def _copy_open_file_at(
    source_fd: int,
    expected: _FileMetadata,
    destination_parent_fd: int,
    destination_name: str,
) -> str:
    try:
        destination_fd = os.open(
            destination_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
            dir_fd=destination_parent_fd,
        )
    except OSError as error:
        raise MigrationValidationError(
            "staging file cannot be created"
        ) from error
    digest = hashlib.sha256()
    copied = 0
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
        while True:
            try:
                chunk = os.read(source_fd, 65536)
            except OSError as error:
                raise MigrationPreviewStaleError(
                    "migration source changed"
                ) from error
            if not chunk:
                break
            digest.update(chunk)
            copied += len(chunk)
            _write_all(destination_fd, chunk)
        os.fsync(destination_fd)
    finally:
        os.close(destination_fd)
    final_stat = os.fstat(source_fd)
    if (
        copied != expected.size
        or final_stat.st_dev != expected.device
        or final_stat.st_ino != expected.inode
        or final_stat.st_size != expected.size
        or final_stat.st_mtime_ns != expected.mtime_ns
        or digest.hexdigest() != expected.sha256
    ):
        raise MigrationPreviewStaleError(
            "migration source changed during copy"
        )
    return digest.hexdigest()


def _hash_open_file(file_fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(file_fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(file_fd, 65536)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _path_from_fd(file_fd: int) -> Path:
    try:
        if hasattr(fcntl, "F_GETPATH"):
            raw = fcntl.fcntl(
                file_fd, fcntl.F_GETPATH, b"\0" * 1024
            )
            path_bytes = raw.split(b"\0", 1)[0]
            if not path_bytes:
                raise OSError(errno.ENOENT, "file descriptor has no path")
            return Path(os.fsdecode(path_bytes))
        return Path(os.readlink(f"/proc/self/fd/{file_fd}"))
    except (OSError, ValueError) as error:
        raise MigrationValidationError(
            "SQLite path cannot be resolved safely"
        ) from error


def _verify_sqlite_connection_identity(
    connection: sqlite3.Connection,
    parent_fd: int,
    name: str,
    expected_file_fd: int,
) -> None:
    expected = os.fstat(expected_file_fd)
    try:
        current = os.stat(
            name, dir_fd=parent_fd, follow_symlinks=False
        )
        database_rows = connection.execute(
            "PRAGMA database_list"
        ).fetchall()
        database_name = next(
            row[2] for row in database_rows if row[1] == "main"
        )
        opened = os.stat(database_name, follow_symlinks=False)
    except (OSError, StopIteration, sqlite3.Error) as error:
        raise MigrationValidationError(
            "SQLite database identity cannot be verified"
        ) from error
    for observed in (current, opened):
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_dev != expected.st_dev
            or observed.st_ino != expected.st_ino
        ):
            raise MigrationValidationError(
                "SQLite database changed while opening"
            )


def _open_sqlite_connection_at(
    parent_fd: int,
    name: str,
    *,
    writable: bool,
    expected_file_fd: int | None = None,
) -> tuple[sqlite3.Connection, int]:
    if "/" in name or "\\" in name or name in {"", ".", ".."}:
        raise MigrationValidationError("SQLite name is invalid")
    owned_fd = (
        os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
        if expected_file_fd is None
        else os.dup(expected_file_fd)
    )
    try:
        entry_stat = os.fstat(owned_fd)
        if not stat.S_ISREG(entry_stat.st_mode):
            raise MigrationValidationError(
                "SQLite database has an invalid type"
            )
        directory_path = _path_from_fd(parent_fd)
        database_path = directory_path / name
        mode = "rw" if writable else "ro"
        connection = sqlite3.connect(
            f"{database_path.as_uri()}?mode={mode}",
            uri=True,
            timeout=0,
        )
        try:
            connection.execute("PRAGMA busy_timeout = 0")
            if not writable:
                connection.execute("PRAGMA query_only = ON")
            _verify_sqlite_connection_identity(
                connection, parent_fd, name, owned_fd
            )
        except BaseException:
            connection.close()
            raise
        return connection, owned_fd
    except BaseException:
        os.close(owned_fd)
        raise


def _sqlite_logical_image_from_connection(
    connection: sqlite3.Connection,
) -> bytes:
    target = sqlite3.connect(":memory:")
    try:
        def stop_if_busy(
            status: int, _remaining: int, _total: int
        ) -> None:
            if status in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise sqlite3.OperationalError(
                    "SQLite backup source is busy"
                )

        connection.backup(
            target, pages=-1, progress=stop_if_busy, sleep=0
        )
        result = target.execute("PRAGMA quick_check").fetchall()
        if result != [("ok",)]:
            raise MigrationValidationError(
                "SQLite validation failed"
            )
        image = bytearray(target.serialize())
    except sqlite3.Error as error:
        raise MigrationValidationError(
            "SQLite logical snapshot failed"
        ) from error
    finally:
        target.close()
    if len(image) < 100 or bytes(image[:16]) != _SQLITE_HEADER:
        raise MigrationValidationError("SQLite validation failed")
    image[18] = 1
    image[19] = 1
    return bytes(image)


def _sqlite_logical_image_from_locked_connection(
    connection: sqlite3.Connection,
) -> bytes:
    """Serialize without opening another FD that would release POSIX locks."""
    target = sqlite3.connect(":memory:")
    try:
        image = bytearray(connection.serialize())
        if len(image) < 100 or bytes(image[:16]) != _SQLITE_HEADER:
            raise MigrationValidationError(
                "SQLite validation failed"
            )
        image[18] = 1
        image[19] = 1
        target.deserialize(bytes(image))
        result = target.execute("PRAGMA quick_check").fetchall()
        if result != [("ok",)]:
            raise MigrationValidationError(
                "SQLite validation failed"
            )
        canonical = bytearray(target.serialize())
    except sqlite3.Error as error:
        raise MigrationValidationError(
            "SQLite logical snapshot failed"
        ) from error
    finally:
        target.close()
    if len(canonical) < 100 or bytes(canonical[:16]) != _SQLITE_HEADER:
        raise MigrationValidationError("SQLite validation failed")
    canonical[18] = 1
    canonical[19] = 1
    return bytes(canonical)


def _sqlite_logical_image_at(
    parent_fd: int,
    name: str,
    *,
    expected_file_fd: int | None = None,
) -> bytes:
    try:
        connection, file_fd = _open_sqlite_connection_at(
            parent_fd,
            name,
            writable=False,
            expected_file_fd=expected_file_fd,
        )
    except (OSError, sqlite3.Error) as error:
        raise MigrationValidationError(
            "SQLite database cannot be opened"
        ) from error
    try:
        image = _sqlite_logical_image_from_connection(connection)
        _verify_sqlite_connection_identity(
            connection, parent_fd, name, file_fd
        )
        return image
    finally:
        connection.close()
        os.close(file_fd)


def _sqlite_image_digest(image: bytes) -> dict:
    if len(image) < 100 or image[:16] != _SQLITE_HEADER:
        raise MigrationValidationError("SQLite validation failed")
    normalized = bytearray(image)
    normalized[18] = 1
    normalized[19] = 1
    normalized[24:28] = b"\0" * 4
    normalized[92:96] = b"\0" * 4
    return {
        "type": "file",
        "bytes": len(image),
        "sha256": hashlib.sha256(normalized).hexdigest(),
    }


def _file_digest_at(parent_fd: int, name: str) -> dict:
    try:
        file_fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        raise MigrationValidationError(
            "SQLite physical file cannot be opened"
        ) from error
    try:
        file_stat = os.fstat(file_fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise MigrationValidationError(
                "SQLite physical file has an invalid type"
            )
        return {
            "bytes": file_stat.st_size,
            "sha256": _hash_open_file(file_fd),
        }
    finally:
        os.close(file_fd)


def _file_digest_from_open_fd(file_fd: int) -> dict:
    before = os.fstat(file_fd)
    if not stat.S_ISREG(before.st_mode):
        raise MigrationValidationError(
            "SQLite physical file has an invalid type"
        )
    sha256 = _hash_open_file(file_fd)
    after = os.fstat(file_fd)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise MigrationValidationError(
            "SQLite physical source changed during validation"
        )
    return {"bytes": after.st_size, "sha256": sha256}


def _open_regular_file_at(
    parent_fd: int, name: str, *, writable: bool = False
) -> int:
    try:
        file_fd = os.open(
            name,
            _WRITABLE_FILE_FLAGS if writable else _FILE_FLAGS,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise MigrationValidationError(
            "SQLite physical file cannot be opened"
        ) from error
    try:
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise MigrationValidationError(
                "SQLite physical file has an invalid type"
            )
        return file_fd
    except BaseException:
        os.close(file_fd)
        raise


def _verify_open_file_identity_at(
    parent_fd: int, name: str, file_fd: int
) -> None:
    held = os.fstat(file_fd)
    try:
        current = os.stat(
            name, dir_fd=parent_fd, follow_symlinks=False
        )
    except OSError as error:
        raise MigrationValidationError(
            "SQLite physical bundle path changed"
        ) from error
    if (
        not stat.S_ISREG(current.st_mode)
        or current.st_dev != held.st_dev
        or current.st_ino != held.st_ino
    ):
        raise MigrationValidationError(
            "SQLite physical bundle path changed"
        )


@contextmanager
def _held_sqlite_physical_bundle_at(
    parent_fd: int, name: str, *, writable: bool = False
) -> Iterator[_HeldSQLitePhysicalBundle]:
    main_fd = _open_regular_file_at(
        parent_fd, name, writable=writable
    )
    sidecar_fds: dict[str, int] = {}
    try:
        for key, suffix in _SQLITE_SIDECARS:
            sidecar = f"{name}{suffix}"
            try:
                sidecar_fds[key] = _open_regular_file_at(
                    parent_fd, sidecar, writable=writable
                )
            except MigrationValidationError:
                try:
                    os.stat(
                        sidecar,
                        dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    continue
                raise
        held = _HeldSQLitePhysicalBundle(main_fd, sidecar_fds)
        _sqlite_physical_digest_from_held_at(parent_fd, name, held)
        yield held
    finally:
        for file_fd in sidecar_fds.values():
            os.close(file_fd)
        os.close(main_fd)


def _sqlite_physical_digest_from_held(
    held: _HeldSQLitePhysicalBundle,
) -> dict:
    sidecars = {
        key: _file_digest_from_open_fd(file_fd)
        for key, file_fd in held.sidecar_fds.items()
    }
    return {
        "type": "sqlite-physical",
        "main": _file_digest_from_open_fd(held.main_fd),
        "sidecars": sidecars,
    }


def _sqlite_physical_digest_from_held_at(
    parent_fd: int,
    name: str,
    held: _HeldSQLitePhysicalBundle,
) -> dict:
    _verify_open_file_identity_at(parent_fd, name, held.main_fd)
    observed_keys: set[str] = set()
    for key, suffix in _SQLITE_SIDECARS:
        sidecar = f"{name}{suffix}"
        try:
            sidecar_stat = os.stat(
                sidecar, dir_fd=parent_fd, follow_symlinks=False
            )
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MigrationValidationError(
                "SQLite physical sidecar cannot be inspected"
            ) from error
        if not stat.S_ISREG(sidecar_stat.st_mode):
            raise MigrationValidationError(
                "SQLite physical sidecar has an invalid type"
            )
        observed_keys.add(key)
    if observed_keys != set(held.sidecar_fds):
        raise MigrationValidationError(
            "SQLite physical bundle changed"
        )
    for key, suffix in _SQLITE_SIDECARS:
        file_fd = held.sidecar_fds.get(key)
        if file_fd is None:
            continue
        _verify_open_file_identity_at(
            parent_fd, f"{name}{suffix}", file_fd
        )
    return _sqlite_physical_digest_from_held(held)


@contextmanager
def _locked_sqlite_physical_bundle_at(
    parent_fd: int,
    name: str,
    expected_physical: dict,
) -> Iterator[_HeldSQLitePhysicalBundle]:
    """Hold whole-file POSIX locks without mutating a SQLite bundle."""
    with _held_sqlite_physical_bundle_at(
        parent_fd, name, writable=True
    ) as held:
        if (
            _sqlite_physical_digest_from_held_at(
                parent_fd, name, held
            )
            != expected_physical
        ):
            raise MigrationValidationError(
                "SQLite physical bundle changed before lock"
            )
        locked_fds: list[int] = []
        try:
            for file_fd in (
                held.main_fd,
                *held.sidecar_fds.values(),
            ):
                try:
                    fcntl.lockf(
                        file_fd,
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                        0,
                        0,
                        os.SEEK_SET,
                    )
                except OSError as error:
                    raise MigrationValidationError(
                        "SQLite physical bundle is busy"
                    ) from error
                locked_fds.append(file_fd)
            if (
                _sqlite_physical_digest_from_held_at(
                    parent_fd, name, held
                )
                != expected_physical
            ):
                raise MigrationValidationError(
                    "SQLite physical bundle changed while locking"
                )
            yield held
        finally:
            for file_fd in reversed(locked_fds):
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


def _sqlite_physical_digest_at(parent_fd: int, name: str) -> dict:
    with _held_sqlite_physical_bundle_at(parent_fd, name) as held:
        return _sqlite_physical_digest_from_held_at(
            parent_fd, name, held
        )


def _copy_open_regular_file_at(
    parent_fd: int,
    source_fd: int,
    destination_name: str,
) -> dict:
    destination_fd = -1
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise MigrationValidationError(
                "SQLite physical source has an invalid type"
            )
        destination_fd = os.open(
            destination_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
        digest = hashlib.sha256()
        copied = 0
        os.lseek(source_fd, 0, os.SEEK_SET)
        while True:
            chunk = os.read(source_fd, 65536)
            if not chunk:
                break
            digest.update(chunk)
            copied += len(chunk)
            _write_all(destination_fd, chunk)
        os.fsync(destination_fd)
        after = os.fstat(source_fd)
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or copied != before.st_size
        ):
            raise MigrationValidationError(
                "SQLite physical source changed during snapshot"
            )
        return {"bytes": copied, "sha256": digest.hexdigest()}
    except BaseException:
        try:
            os.unlink(destination_name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except OSError:
            pass
        raise
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)


def _remove_sqlite_bundle_at(parent_fd: int, name: str) -> None:
    for component in (
        name,
        f"{name}-wal",
        f"{name}-shm",
        f"{name}-journal",
    ):
        _remove_entry_at(parent_fd, component)


def _copy_sqlite_physical_at(
    parent_fd: int,
    source_name: str,
    destination_name: str,
    *,
    expected_physical: dict | None = None,
) -> dict:
    if any(
        _entry_exists_at(parent_fd, component)
        for component in (
            destination_name,
            f"{destination_name}-wal",
            f"{destination_name}-shm",
            f"{destination_name}-journal",
        )
    ):
        raise MigrationValidationError(
            "SQLite physical snapshot already exists"
        )
    try:
        with _held_sqlite_physical_bundle_at(
            parent_fd, source_name
        ) as held:
            expected = _sqlite_physical_digest_from_held_at(
                parent_fd, source_name, held
            )
            if (
                expected_physical is not None
                and expected != expected_physical
            ):
                raise MigrationValidationError(
                    "SQLite physical source does not match journal"
                )
            copied: dict[str, object] = {
                "type": "sqlite-physical",
                "main": _copy_open_regular_file_at(
                    parent_fd, held.main_fd, destination_name
                ),
                "sidecars": {},
            }
            for key, suffix in _SQLITE_SIDECARS:
                source_fd = held.sidecar_fds.get(key)
                if source_fd is None:
                    continue
                copied["sidecars"][key] = _copy_open_regular_file_at(
                    parent_fd,
                    source_fd,
                    f"{destination_name}{suffix}",
                )
            os.fsync(parent_fd)
            if copied != expected:
                raise MigrationValidationError(
                    "SQLite physical snapshot validation failed"
                )
            if (
                _sqlite_physical_digest_from_held_at(
                    parent_fd, source_name, held
                )
                != expected
            ):
                raise MigrationValidationError(
                    "SQLite physical source changed during snapshot"
                )
        if (
            _sqlite_physical_digest_at(parent_fd, destination_name)
            != expected
        ):
            raise MigrationValidationError(
                "SQLite physical snapshot validation failed"
            )
        return expected
    except BaseException:
        _remove_sqlite_bundle_at(parent_fd, destination_name)
        raise


def _validate_sqlite_physical_and_logical_at(
    parent_fd: int,
    name: str,
    expected_physical: dict,
    expected_logical: dict,
    probe_name: str,
) -> None:
    _remove_sqlite_bundle_at(parent_fd, probe_name)
    try:
        _copy_sqlite_physical_at(
            parent_fd,
            name,
            probe_name,
            expected_physical=expected_physical,
        )
        logical = _sqlite_image_digest(
            _sqlite_logical_image_at(parent_fd, probe_name)
        )
        if logical != expected_logical:
            raise MigrationValidationError(
                "SQLite physical bundle logical digest changed"
            )
        if (
            _sqlite_physical_digest_at(parent_fd, name)
            != expected_physical
        ):
            raise MigrationValidationError(
                "SQLite physical bundle changed during validation"
            )
    finally:
        _remove_sqlite_bundle_at(parent_fd, probe_name)


def _sqlite_physical_and_logical_snapshot_at(
    parent_fd: int,
    name: str,
    probe_name: str,
) -> tuple[dict, dict]:
    _remove_sqlite_bundle_at(parent_fd, probe_name)
    try:
        physical = _copy_sqlite_physical_at(
            parent_fd, name, probe_name
        )
        logical = _sqlite_image_digest(
            _sqlite_logical_image_at(parent_fd, probe_name)
        )
        return physical, logical
    finally:
        _remove_sqlite_bundle_at(parent_fd, probe_name)


def _sqlite_physical_is_expected_subset(
    observed: dict, expected: dict
) -> bool:
    if (
        observed.get("type") != "sqlite-physical"
        or observed.get("main") != expected.get("main")
        or not isinstance(observed.get("sidecars"), dict)
        or not isinstance(expected.get("sidecars"), dict)
    ):
        return False
    return all(
        expected["sidecars"].get(key) == digest
        for key, digest in observed["sidecars"].items()
    )


def _sqlite_physical_is_publish_progress(
    observed: dict, prior: dict, replacement: dict
) -> bool:
    if (
        observed.get("type") != "sqlite-physical"
        or observed.get("main") != replacement.get("main")
        or not isinstance(observed.get("sidecars"), dict)
        or not isinstance(prior.get("sidecars"), dict)
        or not isinstance(replacement.get("sidecars"), dict)
    ):
        return False
    for key, digest in observed["sidecars"].items():
        if (
            digest != prior["sidecars"].get(key)
            and digest != replacement["sidecars"].get(key)
        ):
            return False
    return True


def _sqlite_existing_component_digests_at(
    parent_fd: int, name: str
) -> dict[str, dict]:
    components: dict[str, dict] = {}
    for key in ("main", "wal", "shm", "journal"):
        component = f"{name}{_sqlite_component_suffix(key)}"
        try:
            component_stat = os.stat(
                component,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MigrationValidationError(
                "SQLite physical component cannot be inspected"
            ) from error
        if not stat.S_ISREG(component_stat.st_mode):
            raise MigrationValidationError(
                "SQLite physical component has an invalid type"
            )
        components[key] = _file_digest_at(parent_fd, component)
    return components


def _sqlite_physical_from_components(
    components: dict[str, dict],
) -> dict | None:
    main = components.get("main")
    if main is None:
        return None
    return {
        "type": "sqlite-physical",
        "main": main,
        "sidecars": {
            key: digest
            for key, digest in components.items()
            if key != "main"
        },
    }


def _paths_share_regular_inode_at(
    parent_fd: int, first: str, second: str
) -> bool:
    try:
        first_stat = os.stat(
            first, dir_fd=parent_fd, follow_symlinks=False
        )
        second_stat = os.stat(
            second, dir_fd=parent_fd, follow_symlinks=False
        )
    except FileNotFoundError:
        return False
    except OSError as error:
        raise MigrationValidationError(
            "SQLite physical path cannot be inspected"
        ) from error
    if (
        not stat.S_ISREG(first_stat.st_mode)
        or not stat.S_ISREG(second_stat.st_mode)
    ):
        raise MigrationValidationError(
            "SQLite physical path has an invalid type"
        )
    return (
        first_stat.st_dev == second_stat.st_dev
        and first_stat.st_ino == second_stat.st_ino
    )


def _verify_held_sqlite_bundle_at(
    parent_fd: int,
    name: str,
    held: _HeldSQLitePhysicalBundle,
    expected_physical: dict,
) -> None:
    if (
        _sqlite_physical_digest_from_held_at(
            parent_fd, name, held
        )
        != expected_physical
    ):
        raise MigrationValidationError(
            "SQLite physical bundle changed"
        )


def _sqlite_component_fd(
    held: _HeldSQLitePhysicalBundle, key: str
) -> int | None:
    return held.main_fd if key == "main" else held.sidecar_fds.get(key)


def _sqlite_component_suffix(key: str) -> str:
    if key == "main":
        return ""
    for candidate, suffix in _SQLITE_SIDECARS:
        if candidate == key:
            return suffix
    raise MigrationValidationError("SQLite component is invalid")


def _sqlite_component_identities_from_held(
    held: _HeldSQLitePhysicalBundle,
) -> dict[str, dict[str, int]]:
    identities: dict[str, dict[str, int]] = {}
    for key in ("main", "wal", "shm", "journal"):
        file_fd = _sqlite_component_fd(held, key)
        if file_fd is None:
            continue
        file_stat = os.fstat(file_fd)
        identities[key] = {
            "device": file_stat.st_dev,
            "inode": file_stat.st_ino,
        }
    return identities


def _valid_sqlite_component_identities(
    value: object, expected_physical: dict
) -> bool:
    if not isinstance(value, dict):
        return False
    expected_keys = {"main", *expected_physical["sidecars"]}
    if set(value) != expected_keys:
        return False
    return all(
        isinstance(identity, dict)
        and set(identity) == {"device", "inode"}
        and all(
            isinstance(identity[field], int)
            and not isinstance(identity[field], bool)
            and identity[field] >= 0
            for field in ("device", "inode")
        )
        for identity in value.values()
    )


def _verify_held_sqlite_component_identities(
    held: _HeldSQLitePhysicalBundle,
    expected_identities: dict[str, dict[str, int]],
) -> None:
    if (
        _sqlite_component_identities_from_held(held)
        != expected_identities
    ):
        raise MigrationValidationError(
            "SQLite ownership anchor identity changed"
        )


def _verify_component_path_identity_at(
    parent_fd: int,
    name: str,
    file_fd: int,
    expected_identity: dict[str, int],
) -> None:
    held = os.fstat(file_fd)
    try:
        observed = os.stat(
            name, dir_fd=parent_fd, follow_symlinks=False
        )
    except OSError as error:
        raise MigrationValidationError(
            "SQLite retained guard component is missing"
        ) from error
    if (
        not stat.S_ISREG(observed.st_mode)
        or (held.st_dev, held.st_ino)
        != (
            expected_identity["device"],
            expected_identity["inode"],
        )
        or (observed.st_dev, observed.st_ino)
        != (held.st_dev, held.st_ino)
    ):
        raise MigrationValidationError(
            "SQLite retained guard component identity changed"
        )


def _new_only_component_phase_proves(
    component_phase: str | None, key: str
) -> bool:
    if component_phase in {
        "quarantined",
        "retained_external_write_guard",
    }:
        return True
    ordered = (
        "main_published",
        "wal_published",
        "shm_published",
        "journal_published",
        "sidecars_cleaned",
    )
    required = {
        "main": "main_published",
        "wal": "wal_published",
        "shm": "shm_published",
        "journal": "journal_published",
    }
    try:
        return ordered.index(component_phase) >= ordered.index(
            required[key]
        )
    except (ValueError, KeyError):
        return False


def _verify_new_only_component_ownership_at(
    parent_fd: int,
    anchor_name: str,
    destination_name: str,
    current_components: dict[str, dict],
    component_phase: str | None,
) -> None:
    for key in current_components:
        suffix = _sqlite_component_suffix(key)
        if not _new_only_component_phase_proves(component_phase, key):
            raise MigrationValidationError(
                "SQLite no-clobber component ownership is ambiguous"
            )
        if not _paths_share_regular_inode_at(
            parent_fd,
            f"{anchor_name}{suffix}",
            f"{destination_name}{suffix}",
        ):
            raise MigrationValidationError(
                "SQLite no-clobber component ownership changed"
            )


def _verify_new_only_held_component_ownership_at(
    parent_fd: int,
    anchor_name: str,
    destination_name: str,
    held_anchor: _HeldSQLitePhysicalBundle,
    held_current: _HeldSQLitePhysicalBundle,
    anchor_physical: dict,
    current_physical: dict,
    component_phase: str | None,
) -> None:
    if (
        _sqlite_physical_digest_from_held_at(
            parent_fd, anchor_name, held_anchor
        )
        != anchor_physical
    ):
        raise MigrationValidationError(
            "SQLite no-clobber ownership anchor changed"
        )
    if (
        _sqlite_physical_digest_from_held_at(
            parent_fd, destination_name, held_current
        )
        != current_physical
    ):
        raise MigrationValidationError(
            "SQLite no-clobber current changed"
        )
    for key in ("main", "wal", "shm", "journal"):
        current_fd = _sqlite_component_fd(held_current, key)
        if current_fd is None:
            continue
        anchor_fd = _sqlite_component_fd(held_anchor, key)
        if anchor_fd is None:
            raise MigrationValidationError(
                "SQLite no-clobber ownership anchor is incomplete"
            )
        if not _new_only_component_phase_proves(component_phase, key):
            raise MigrationValidationError(
                "SQLite no-clobber component ownership is ambiguous"
            )
        current_stat = os.fstat(current_fd)
        anchor_stat = os.fstat(anchor_fd)
        if (
            current_stat.st_dev,
            current_stat.st_ino,
        ) != (
            anchor_stat.st_dev,
            anchor_stat.st_ino,
        ):
            raise MigrationValidationError(
                "SQLite no-clobber component ownership changed"
            )
        suffix = _sqlite_component_suffix(key)
        _verify_open_file_identity_at(
            parent_fd, f"{anchor_name}{suffix}", anchor_fd
        )
        _verify_open_file_identity_at(
            parent_fd, f"{destination_name}{suffix}", current_fd
        )


def _link_held_sqlite_bundle_to_retained_guard_at(
    parent_fd: int,
    source_name: str,
    guard_name: str,
    held_source: _HeldSQLitePhysicalBundle,
    expected_physical: dict,
    expected_identities: dict[str, dict[str, int]],
) -> None:
    _verify_held_sqlite_bundle_at(
        parent_fd,
        source_name,
        held_source,
        expected_physical,
    )
    _verify_held_sqlite_component_identities(
        held_source, expected_identities
    )
    expected_keys = set(expected_identities)
    for key in ("main", "wal", "shm", "journal"):
        suffix = _sqlite_component_suffix(key)
        source_component = f"{source_name}{suffix}"
        guard_component = f"{guard_name}{suffix}"
        source_fd = _sqlite_component_fd(held_source, key)
        if key not in expected_keys:
            if source_fd is not None or _entry_exists_at(
                parent_fd, guard_component
            ):
                raise MigrationValidationError(
                    "SQLite retained guard has an unexpected component"
                )
            continue
        if source_fd is None:
            raise MigrationValidationError(
                "SQLite retained guard source is incomplete"
            )
        _verify_component_path_identity_at(
            parent_fd,
            source_component,
            source_fd,
            expected_identities[key],
        )
        if not _entry_exists_at(parent_fd, guard_component):
            try:
                os.link(
                    source_component,
                    guard_component,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                os.fsync(parent_fd)
            except OSError as error:
                raise MigrationValidationError(
                    "SQLite retained guard cannot be created"
                ) from error
        _verify_component_path_identity_at(
            parent_fd,
            guard_component,
            source_fd,
            expected_identities[key],
        )
    _verify_held_sqlite_bundle_at(
        parent_fd,
        source_name,
        held_source,
        expected_physical,
    )


def _verify_retained_external_write_guard_at(
    paths: TomosPaths,
    parent_fd: int,
    guard_name: str,
    migration_id: str,
    snapshot_id: str,
    kind: str,
) -> dict:
    record_path = _retained_external_write_guard_record_path(
        paths, migration_id, snapshot_id, kind
    )
    record = _read_record(record_path)
    if record is None:
        raise MigrationValidationError(
            "retained external write guard record is missing"
        )
    record = _validate_retained_external_write_guard_record(record)
    if (
        record["migrationId"] != migration_id
        or record["snapshotId"] != snapshot_id
        or record["kind"] != kind
    ):
        raise MigrationValidationError(
            "retained external write guard record changed"
        )
    expected_identities = record["componentIdentities"]
    for key in ("main", "wal", "shm", "journal"):
        component = f"{guard_name}{_sqlite_component_suffix(key)}"
        try:
            observed = os.stat(
                component,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if key in expected_identities:
                raise MigrationValidationError(
                    "retained external write guard is incomplete"
                )
            continue
        except OSError as error:
            raise MigrationValidationError(
                "retained external write guard cannot be inspected"
            ) from error
        if (
            key not in expected_identities
            or not stat.S_ISREG(observed.st_mode)
            or (
                observed.st_dev,
                observed.st_ino,
            )
            != (
                expected_identities[key]["device"],
                expected_identities[key]["inode"],
            )
        ):
            raise MigrationValidationError(
                "retained external write guard identity changed"
            )
    observed_physical = _sqlite_physical_digest_at(
        parent_fd, guard_name
    )
    if {
        "main",
        *observed_physical["sidecars"],
    } != set(expected_identities):
        raise MigrationValidationError(
            "retained external write guard is incomplete"
        )
    _managed_digest_at(
        parent_fd,
        guard_name,
        sqlite_logical=True,
    )
    for key, identity in expected_identities.items():
        component = f"{guard_name}{_sqlite_component_suffix(key)}"
        observed = os.stat(
            component,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            observed.st_dev,
            observed.st_ino,
        ) != (identity["device"], identity["inode"]):
            raise MigrationValidationError(
                "retained external write guard changed during validation"
            )
    return record


def _remove_retained_staging_aliases_at(
    parent_fd: int,
    staging_name: str,
    component_identities: dict[str, dict[str, int]],
    *,
    fault_kind: str,
) -> None:
    for key in ("wal", "shm", "journal", "main"):
        component = f"{staging_name}{_sqlite_component_suffix(key)}"
        try:
            observed = os.stat(
                component,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MigrationValidationError(
                "SQLite retained staging alias cannot be inspected"
            ) from error
        identity = component_identities.get(key)
        if (
            identity is None
            or not stat.S_ISREG(observed.st_mode)
            or (
                observed.st_dev,
                observed.st_ino,
            )
            != (identity["device"], identity["inode"])
        ):
            raise MigrationValidationError(
                "SQLite retained staging alias changed"
            )
        os.unlink(component, dir_fd=parent_fd)
        _fault_injection(
            f"after_new_only_sqlite_staging_{key}_unlink",
            fault_kind,
        )
    os.fsync(parent_fd)


def _remove_held_sqlite_bundle_at(
    parent_fd: int,
    name: str,
    held: _HeldSQLitePhysicalBundle,
    expected_physical: dict,
    *,
    fault_prefix: str | None = None,
    fault_kind: str | None = None,
) -> None:
    """Unlink a verified held bundle without reopening any component."""
    if (
        _sqlite_physical_digest_from_held_at(parent_fd, name, held)
        != expected_physical
    ):
        raise MigrationValidationError(
            "SQLite held cleanup bundle changed"
        )
    expected_components = {
        "main": expected_physical["main"],
        **expected_physical["sidecars"],
    }
    for key in ("wal", "shm", "journal", "main"):
        file_fd = _sqlite_component_fd(held, key)
        if file_fd is None:
            continue
        if (
            _file_digest_from_open_fd(file_fd)
            != expected_components.get(key)
        ):
            raise MigrationValidationError(
                "SQLite held cleanup component changed"
            )
        component_name = f"{name}{_sqlite_component_suffix(key)}"
        _verify_open_file_identity_at(parent_fd, component_name, file_fd)
        os.unlink(component_name, dir_fd=parent_fd)
        if fault_prefix is not None:
            _fault_injection(
                f"{fault_prefix}_{key}_unlink",
                fault_kind or name,
            )
    os.fsync(parent_fd)
    if any(
        _entry_exists_at(
            parent_fd,
            f"{name}{_sqlite_component_suffix(key)}",
        )
        for key in ("main", "wal", "shm", "journal")
    ):
        raise MigrationValidationError(
            "SQLite held cleanup path was recreated"
        )
    if _sqlite_physical_digest_from_held(held) != expected_physical:
        raise MigrationValidationError(
            "SQLite held cleanup bundle changed"
        )


def _ensure_sqlite_quarantine_at(
    parent_fd: int,
    source_name: str,
    quarantine_name: str,
    held_source: _HeldSQLitePhysicalBundle,
    expected_physical: dict,
) -> None:
    """Copy every current component before replacing its pathname."""
    expected_keys = {"main", *expected_physical["sidecars"]}
    for key in ("main", "wal", "shm", "journal"):
        suffix = _sqlite_component_suffix(key)
        source_component = f"{source_name}{suffix}"
        quarantine_component = f"{quarantine_name}{suffix}"
        file_fd = _sqlite_component_fd(held_source, key)
        if key not in expected_keys:
            if _entry_exists_at(parent_fd, quarantine_component):
                raise MigrationValidationError(
                    "SQLite quarantine has an unexpected component"
                )
            continue
        if file_fd is None:
            raise MigrationValidationError(
                "SQLite quarantine source is incomplete"
            )
        _verify_open_file_identity_at(
            parent_fd, source_component, file_fd
        )
        if _entry_exists_at(parent_fd, quarantine_component):
            expected_component = (
                expected_physical["main"]
                if key == "main"
                else expected_physical["sidecars"][key]
            )
            if (
                _file_digest_at(
                    parent_fd, quarantine_component
                )
                != expected_component
            ):
                raise MigrationValidationError(
                    "SQLite recovery quarantine changed"
                )
            continue
        try:
            copied = _copy_open_regular_file_at(
                parent_fd,
                file_fd,
                quarantine_component,
            )
            os.fsync(parent_fd)
        except OSError as error:
            raise MigrationValidationError(
                "SQLite current cannot be quarantined"
            ) from error
        expected_component = (
            expected_physical["main"]
            if key == "main"
            else expected_physical["sidecars"][key]
        )
        if copied != expected_component:
            raise MigrationValidationError(
                "SQLite quarantine copy is invalid"
            )
    _verify_held_sqlite_bundle_at(
        parent_fd,
        source_name,
        held_source,
        expected_physical,
    )
    if (
        _sqlite_physical_digest_at(parent_fd, quarantine_name)
        != expected_physical
    ):
        raise MigrationValidationError(
            "SQLite recovery quarantine is invalid"
        )


@contextmanager
def _held_distinct_sqlite_quarantine_at(
    parent_fd: int,
    source_name: str,
    quarantine_name: str,
    observed_physical: dict,
    quarantine_physical: dict,
) -> Iterator[_HeldSQLitePhysicalBundle]:
    quarantine_exists = any(
        _entry_exists_at(
            parent_fd,
            f"{quarantine_name}{_sqlite_component_suffix(key)}",
        )
        for key in ("main", "wal", "shm", "journal")
    )
    if not quarantine_exists:
        if observed_physical != quarantine_physical:
            raise MigrationValidationError(
                "SQLite no-clobber quarantine cannot be reconstructed"
            )
        with _held_sqlite_physical_bundle_at(
            parent_fd, source_name
        ) as held_source:
            _verify_held_sqlite_bundle_at(
                parent_fd,
                source_name,
                held_source,
                observed_physical,
            )
            _ensure_sqlite_quarantine_at(
                parent_fd,
                source_name,
                quarantine_name,
                held_source,
                quarantine_physical,
            )

    with _held_sqlite_physical_bundle_at(
        parent_fd, quarantine_name
    ) as held_quarantine:
        if (
            _sqlite_physical_digest_from_held_at(
                parent_fd, quarantine_name, held_quarantine
            )
            != quarantine_physical
        ):
            raise MigrationValidationError(
                "SQLite no-clobber quarantine changed"
            )
        yield held_quarantine


def _verify_distinct_held_sqlite_quarantine_at(
    parent_fd: int,
    source_name: str,
    quarantine_name: str,
    held_source: _HeldSQLitePhysicalBundle,
    held_quarantine: _HeldSQLitePhysicalBundle,
    observed_physical: dict,
    quarantine_physical: dict,
) -> None:
    _verify_held_sqlite_bundle_at(
        parent_fd,
        source_name,
        held_source,
        observed_physical,
    )
    _verify_held_sqlite_bundle_at(
        parent_fd,
        quarantine_name,
        held_quarantine,
        quarantine_physical,
    )
    current_identities = {
        (file_stat.st_dev, file_stat.st_ino)
        for file_fd in (
            held_source.main_fd,
            *held_source.sidecar_fds.values(),
        )
        for file_stat in (os.fstat(file_fd),)
    }
    for file_fd in (
        held_quarantine.main_fd,
        *held_quarantine.sidecar_fds.values(),
    ):
        quarantine_stat = os.fstat(file_fd)
        if (
            quarantine_stat.st_dev,
            quarantine_stat.st_ino,
        ) in current_identities:
            raise MigrationValidationError(
                "SQLite no-clobber quarantine aliases current"
            )


def _remove_owned_new_only_sqlite_current_at(
    parent_fd: int,
    source_name: str,
    anchor_name: str,
    held_source: _HeldSQLitePhysicalBundle,
    expected_physical: dict,
) -> None:
    _verify_held_sqlite_bundle_at(
        parent_fd,
        source_name,
        held_source,
        expected_physical,
    )
    for key in ("wal", "shm", "journal", "main"):
        file_fd = _sqlite_component_fd(held_source, key)
        if file_fd is None:
            continue
        suffix = _sqlite_component_suffix(key)
        source_component = f"{source_name}{suffix}"
        anchor_component = f"{anchor_name}{suffix}"
        _verify_open_file_identity_at(
            parent_fd, source_component, file_fd
        )
        _verify_open_file_identity_at(
            parent_fd, anchor_component, file_fd
        )
        os.unlink(source_component, dir_fd=parent_fd)
        os.fsync(parent_fd)


def _assert_nofollow_entry_absent_at(
    parent_fd: int, name: str
) -> None:
    try:
        file_fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError:
        return
    except OSError as error:
        raise MigrationValidationError(
            "SQLite no-clobber destination cannot be inspected"
        ) from error
    else:
        os.close(file_fd)
    raise MigrationValidationError(
        "SQLite no-clobber destination component already exists"
    )


def _verify_new_only_publish_state_at(
    parent_fd: int,
    source_name: str,
    destination_name: str,
    held_source: _HeldSQLitePhysicalBundle,
    published_keys: set[str],
) -> None:
    for key in ("main", "wal", "shm", "journal"):
        suffix = _sqlite_component_suffix(key)
        source_fd = _sqlite_component_fd(held_source, key)
        destination_component = f"{destination_name}{suffix}"
        if key not in published_keys:
            _assert_nofollow_entry_absent_at(
                parent_fd, destination_component
            )
            continue
        if source_fd is None:
            raise MigrationValidationError(
                "SQLite no-clobber published component is invalid"
            )
        _verify_open_file_identity_at(
            parent_fd, f"{source_name}{suffix}", source_fd
        )
        _verify_open_file_identity_at(
            parent_fd, destination_component, source_fd
        )


def _publish_locked_sqlite_bundle_at(
    parent_fd: int,
    source_name: str,
    destination_name: str,
    held_source: _HeldSQLitePhysicalBundle,
    expected_physical: dict,
    component_phase: Callable[[str], None],
    *,
    no_clobber_main: bool = False,
) -> None:
    """Publish main and sidecars while the replacement inodes stay locked."""
    _verify_held_sqlite_bundle_at(
        parent_fd, source_name, held_source, expected_physical
    )
    _fault_injection(
        "after_sqlite_scratch_final_digest", source_name
    )
    _verify_held_sqlite_bundle_at(
        parent_fd, source_name, held_source, expected_physical
    )
    if no_clobber_main:
        published_keys: set[str] = set()
        _verify_new_only_publish_state_at(
            parent_fd,
            source_name,
            destination_name,
            held_source,
            published_keys,
        )
        try:
            os.link(
                source_name,
                destination_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as error:
            raise MigrationValidationError(
                "SQLite destination appeared before no-clobber publish"
            ) from error
        os.fsync(parent_fd)
        _verify_open_file_identity_at(
            parent_fd, destination_name, held_source.main_fd
        )
        published_keys.add("main")
        component_phase("main_published")
    else:
        _replace_at(
            parent_fd, source_name, parent_fd, destination_name
        )
        component_phase("main_published")
    _fault_injection("after_sqlite_main_publish", destination_name)

    for key, suffix in _SQLITE_SIDECARS:
        source_component = f"{source_name}{suffix}"
        destination_component = f"{destination_name}{suffix}"
        source_fd = held_source.sidecar_fds.get(key)
        if no_clobber_main:
            _verify_new_only_publish_state_at(
                parent_fd,
                source_name,
                destination_name,
                held_source,
                published_keys,
            )
            if source_fd is not None:
                try:
                    os.link(
                        source_component,
                        destination_component,
                        src_dir_fd=parent_fd,
                        dst_dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                except FileExistsError as error:
                    raise MigrationValidationError(
                        "SQLite destination sidecar appeared before publish"
                    ) from error
                os.fsync(parent_fd)
                _verify_open_file_identity_at(
                    parent_fd, destination_component, source_fd
                )
                published_keys.add(key)
        else:
            if source_fd is not None:
                _verify_open_file_identity_at(
                    parent_fd, source_component, source_fd
                )
                _replace_at(
                    parent_fd,
                    source_component,
                    parent_fd,
                    destination_component,
                )
            elif _entry_exists_at(parent_fd, destination_component):
                try:
                    component_stat = os.stat(
                        destination_component,
                        dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                except OSError as error:
                    raise MigrationValidationError(
                        "SQLite sidecar cannot be inspected"
                    ) from error
                if not stat.S_ISREG(component_stat.st_mode):
                    raise MigrationValidationError(
                        "SQLite sidecar has an invalid type"
                    )
                os.unlink(destination_component, dir_fd=parent_fd)
                os.fsync(parent_fd)
        component_phase(f"{key}_published")
        _fault_injection(
            f"after_sqlite_{key}_publish", destination_name
        )

    if no_clobber_main:
        _verify_new_only_publish_state_at(
            parent_fd,
            source_name,
            destination_name,
            held_source,
            published_keys,
        )
    _verify_held_sqlite_bundle_at(
        parent_fd,
        destination_name,
        held_source,
        expected_physical,
    )
    component_phase("sidecars_cleaned")


def _restore_sqlite_physical_at(
    parent_fd: int,
    destination_name: str,
    backup_name: str,
    expected_physical: dict,
    expected_logical: dict,
    *,
    expected_current_physical: dict,
    quarantine_physical: dict,
    component_phase: Callable[[str], None],
) -> None:
    restore_name = f"{backup_name}.restore"
    probe_name = f"{restore_name}.probe"
    quarantine_name = _sqlite_displaced_path(
        Path(backup_name)
    ).name
    _remove_sqlite_bundle_at(parent_fd, restore_name)
    _copy_sqlite_physical_at(
        parent_fd,
        backup_name,
        restore_name,
        expected_physical=expected_physical,
    )
    try:
        _validate_sqlite_physical_and_logical_at(
            parent_fd,
            restore_name,
            expected_physical,
            expected_logical,
            probe_name,
        )
        quarantine_ready = False
        if _entry_exists_at(parent_fd, quarantine_name):
            try:
                quarantine_ready = (
                    _sqlite_physical_digest_at(
                        parent_fd, quarantine_name
                    )
                    == quarantine_physical
                )
            except MigrationValidationError:
                quarantine_ready = False
            if (
                not quarantine_ready
                and expected_current_physical
                != quarantine_physical
            ):
                raise MigrationValidationError(
                    "SQLite recovery quarantine is incomplete"
                )

        with ExitStack() as stack:
            held_restore = stack.enter_context(
                _locked_sqlite_physical_bundle_at(
                    parent_fd, restore_name, expected_physical
                )
            )
            held_current = stack.enter_context(
                _locked_sqlite_physical_bundle_at(
                    parent_fd,
                    destination_name,
                    expected_current_physical,
                )
            )
            _verify_held_sqlite_bundle_at(
                parent_fd,
                restore_name,
                held_restore,
                expected_physical,
            )
            _verify_held_sqlite_bundle_at(
                parent_fd,
                destination_name,
                held_current,
                expected_current_physical,
            )
            _fault_injection(
                "before_sqlite_restore_publish", backup_name
            )
            _verify_held_sqlite_bundle_at(
                parent_fd,
                restore_name,
                held_restore,
                expected_physical,
            )
            _fault_injection(
                "after_sqlite_restore_final_digest", backup_name
            )
            _verify_held_sqlite_bundle_at(
                parent_fd,
                restore_name,
                held_restore,
                expected_physical,
            )
            _verify_held_sqlite_bundle_at(
                parent_fd,
                destination_name,
                held_current,
                expected_current_physical,
            )
            if not quarantine_ready:
                _ensure_sqlite_quarantine_at(
                    parent_fd,
                    destination_name,
                    quarantine_name,
                    held_current,
                    quarantine_physical,
                )
            component_phase("quarantined")
            _fault_injection(
                "after_sqlite_recovery_decision", backup_name
            )
            _verify_held_sqlite_bundle_at(
                parent_fd,
                destination_name,
                held_current,
                expected_current_physical,
            )
            _verify_held_sqlite_bundle_at(
                parent_fd,
                restore_name,
                held_restore,
                expected_physical,
            )
            _publish_locked_sqlite_bundle_at(
                parent_fd,
                restore_name,
                destination_name,
                held_restore,
                expected_physical,
                component_phase,
            )
    finally:
        _remove_sqlite_bundle_at(parent_fd, probe_name)
        _remove_sqlite_bundle_at(parent_fd, restore_name)


def _prepare_sqlite_replacement_at(
    parent_fd: int,
    name: str,
    expected_digest: dict,
    *,
    expected_file_fd: int | None = None,
) -> tuple[sqlite3.Connection, int, bytes]:
    try:
        connection, file_fd = _open_sqlite_connection_at(
            parent_fd,
            name,
            writable=True,
            expected_file_fd=expected_file_fd,
        )
        try:
            mode = connection.execute(
                "PRAGMA locking_mode = EXCLUSIVE"
            ).fetchone()
            if mode != ("exclusive",):
                raise MigrationValidationError(
                    "SQLite exclusive lock is unavailable"
                )
            connection.execute("BEGIN EXCLUSIVE")
            connection.commit()
            image = _sqlite_logical_image_from_connection(connection)
            if _sqlite_image_digest(image) != expected_digest:
                raise MigrationValidationError(
                    "SQLite destination changed"
                )
            _verify_sqlite_connection_identity(
                connection, parent_fd, name, file_fd
            )
            return connection, file_fd, image
        except BaseException:
            connection.close()
            os.close(file_fd)
            raise
    except (OSError, sqlite3.Error) as error:
        raise MigrationValidationError(
            "SQLite destination is busy or unsafe"
        ) from error


def _close_sqlite_replacement(
    connection: sqlite3.Connection, file_fd: int
) -> None:
    try:
        connection.close()
    finally:
        os.close(file_fd)


def _remove_sqlite_sidecars_at(parent_fd: int, name: str) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = f"{name}{suffix}"
        try:
            sidecar_stat = os.stat(
                sidecar, dir_fd=parent_fd, follow_symlinks=False
            )
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MigrationValidationError(
                "SQLite sidecar cannot be inspected"
            ) from error
        if not stat.S_ISREG(sidecar_stat.st_mode):
            raise MigrationValidationError(
                "SQLite sidecar has an invalid type"
            )
        os.unlink(sidecar, dir_fd=parent_fd)
        os.fsync(parent_fd)


def _managed_digest(
    path: Path, *, sqlite_logical: bool = False
) -> dict:
    if sqlite_logical:
        parent_fd = _open_directory_chain(path.parent)
        try:
            return _managed_digest_at(
                parent_fd, path.name, sqlite_logical=True
            )
        finally:
            os.close(parent_fd)
    path_stat = os.lstat(path)
    if stat.S_ISREG(path_stat.st_mode):
        return {
            "type": "file",
            "bytes": path_stat.st_size,
            "sha256": _sha256_file(path),
        }
    if stat.S_ISDIR(path_stat.st_mode):
        manifest = _directory_manifest(path)
        return {
            "type": "directory",
            "fileCount": len(manifest),
            "sha256": _digest_json(
                [
                    {"name": name, "sha256": digest}
                    for name, digest in sorted(manifest.items())
                ]
            ),
        }
    raise MigrationValidationError(
        "managed destination has an invalid type"
    )


def _entry_exists_at(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _managed_digest_at(
    parent_fd: int, name: str, *, sqlite_logical: bool = False
) -> dict:
    if sqlite_logical:
        return _sqlite_image_digest(
            _sqlite_logical_image_at(parent_fd, name)
        )
    try:
        entry_fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        raise MigrationValidationError(
            "managed destination cannot be opened"
        ) from error
    try:
        entry_stat = os.fstat(entry_fd)
        if stat.S_ISREG(entry_stat.st_mode):
            return {
                "type": "file",
                "bytes": entry_stat.st_size,
                "sha256": _hash_open_file(entry_fd),
            }
        if stat.S_ISDIR(entry_stat.st_mode):
            manifest = _directory_manifest_fd(entry_fd)
            return {
                "type": "directory",
                "fileCount": len(manifest),
                "sha256": _digest_json(
                    [
                        {"name": relative, "sha256": digest}
                        for relative, digest in sorted(manifest.items())
                    ]
                ),
            }
    finally:
        os.close(entry_fd)
    raise MigrationValidationError(
        "managed destination has an invalid type"
    )


def _directory_manifest_fd(
    root_fd: int, prefix: tuple[str, ...] = ()
) -> dict[str, str]:
    names, errors = _directory_names(root_fd)
    if errors:
        raise MigrationValidationError(
            "managed directory cannot be read"
        )
    hashes: dict[str, str] = {}
    for name in names:
        child_fd = os.open(name, _FILE_FLAGS, dir_fd=root_fd)
        try:
            child_stat = os.fstat(child_fd)
            relative = "/".join(prefix + (name,))
            if stat.S_ISDIR(child_stat.st_mode):
                hashes.update(
                    _directory_manifest_fd(
                        child_fd, prefix + (name,)
                    )
                )
            elif stat.S_ISREG(child_stat.st_mode):
                hashes[relative] = _hash_open_file(child_fd)
            else:
                raise MigrationValidationError(
                    "directory contains an invalid entry"
                )
        finally:
            os.close(child_fd)
    return hashes


def _replace_at(
    source_parent_fd: int,
    source_name: str,
    destination_parent_fd: int,
    destination_name: str,
) -> None:
    os.replace(
        source_name,
        destination_name,
        src_dir_fd=source_parent_fd,
        dst_dir_fd=destination_parent_fd,
    )
    os.fsync(source_parent_fd)
    if destination_parent_fd != source_parent_fd:
        os.fsync(destination_parent_fd)


def _ensure_directory_fd_matches_path(
    directory_fd: int, directory: Path
) -> None:
    try:
        current_fd = _open_directory_chain(directory)
    except OSError as error:
        raise MigrationValidationError(
            "managed destination parent changed"
        ) from error
    try:
        opened = os.fstat(directory_fd)
        current = os.fstat(current_fd)
        if (
            opened.st_dev != current.st_dev
            or opened.st_ino != current.st_ino
        ):
            raise MigrationValidationError(
                "managed destination parent changed"
            )
    finally:
        os.close(current_fd)


def _remove_entry_at(parent_fd: int, name: str) -> None:
    try:
        entry_stat = os.stat(
            name, dir_fd=parent_fd, follow_symlinks=False
        )
    except FileNotFoundError:
        return
    if stat.S_ISDIR(entry_stat.st_mode):
        directory_fd = os.open(
            name, _DIRECTORY_FLAGS, dir_fd=parent_fd
        )
        try:
            names, errors = _directory_names(directory_fd)
            if errors:
                raise MigrationValidationError(
                    "managed directory cannot be removed"
                )
            for child in names:
                _remove_entry_at(directory_fd, child)
        finally:
            os.close(directory_fd)
        os.rmdir(name, dir_fd=parent_fd)
    else:
        os.unlink(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def _directory_manifest(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(
        root.rglob("*"), key=lambda candidate: candidate.as_posix()
    ):
        path_stat = path.lstat()
        if stat.S_ISDIR(path_stat.st_mode):
            continue
        if not stat.S_ISREG(path_stat.st_mode):
            raise MigrationValidationError(
                "directory contains an invalid entry"
            )
        relative_name = path.relative_to(root).as_posix()
        hashes[relative_name] = _sha256_file(path)
    return hashes


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    fd = os.open(path, _FILE_FLAGS)
    try:
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
    finally:
        os.close(fd)


def _validate_sqlite(path: Path) -> None:
    try:
        connection = sqlite3.connect(
            f"{_absolute_path(path).as_uri()}?mode=ro", uri=True
        )
        try:
            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise MigrationValidationError(
            "SQLite validation failed"
        ) from error
    if result != [("ok",)]:
        raise MigrationValidationError("SQLite validation failed")


def _validate_sqlite_fd(file_fd: int) -> None:
    try:
        connection = sqlite3.connect(
            f"file:/dev/fd/{file_fd}?mode=ro&immutable=1",
            uri=True,
        )
        try:
            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise MigrationValidationError(
            "SQLite validation failed"
        ) from error
    if result != [("ok",)]:
        raise MigrationValidationError("SQLite validation failed")


def _validate_tomos_layout(paths: TomosPaths) -> Path:
    root = _absolute_path(paths.root)
    _assert_no_symlink_chain(root, include_leaf=True)
    mutable_roots = [
        paths.knowledge_db,
        paths.context_db,
        paths.contracts_db,
        paths.study_packs,
        paths.person_photos,
        paths.codegraph,
        paths.logs,
        paths.migration,
    ]
    normalized: list[Path] = []
    for candidate in mutable_roots:
        path = _absolute_path(candidate)
        _assert_inside(root, path)
        _assert_no_symlink_chain(path.parent, include_leaf=True)
        normalized.append(path)
    for index, path in enumerate(normalized):
        for other in normalized[index + 1 :]:
            if _paths_overlap(path, other) or _same_existing_object(
                path, other
            ):
                raise MigrationValidationError(
                    "managed destinations overlap"
                )
    return _comparison_path(root)


def _validate_source_set(
    sources: Sequence[MigrationSource], data_root: Path
) -> None:
    seen_kinds: set[str] = set()
    source_paths: list[Path] = []
    for source in sources:
        provenance = _validated_provenance(source)
        if provenance is None:
            raise MigrationValidationError(
                "migration source provenance is invalid"
            )
        if provenance.data_root != data_root:
            raise MigrationValidationError(
                "migration source data root changed"
            )
        if source.kind in seen_kinds:
            raise MigrationValidationError(
                "multiple sources target the same destination"
            )
        seen_kinds.add(source.kind)
        source_path = _absolute_path(source.source)
        if _paths_overlap(source_path, data_root):
            raise MigrationValidationError(
                "migration source overlaps managed data root"
            )
        for prior in source_paths:
            if _paths_overlap(
                source_path, prior
            ) or _same_existing_object(source_path, prior):
                raise MigrationValidationError(
                    "migration sources overlap"
                )
        if _same_existing_object(source_path, source.destination):
            raise MigrationValidationError(
                "migration source aliases destination"
            )
        source_paths.append(source_path)


def _validate_transaction_paths(
    paths: TomosPaths,
    sources: Sequence[MigrationSource],
    generated_paths: Sequence[Path],
    *,
    allowed_existing_alias_groups: Sequence[Sequence[Path]] = (),
) -> None:
    data_root = _validate_tomos_layout(paths)
    _validate_source_set(sources, data_root)
    allowed_aliases = {
        frozenset(
            (_absolute_path(first), _absolute_path(second))
        )
        for group in allowed_existing_alias_groups
        for index, first in enumerate(group)
        for second in group[index + 1 :]
    }

    def aliases_are_allowed(first: Path, second: Path) -> bool:
        return (
            frozenset(
                (_absolute_path(first), _absolute_path(second))
            )
            in allowed_aliases
        )

    normalized: list[Path] = []
    for generated in generated_paths:
        path = _absolute_path(generated)
        _assert_inside(data_root, path)
        _assert_no_symlink_chain(path.parent, include_leaf=True)
        if path.is_symlink():
            raise MigrationValidationError(
                "migration internal path is a symlink"
            )
        normalized.append(path)
    for index, path in enumerate(normalized):
        for other in normalized[index + 1 :]:
            if _paths_overlap(path, other) or (
                _same_existing_object(path, other)
                and not aliases_are_allowed(path, other)
            ):
                raise MigrationValidationError(
                    "migration internal paths overlap"
                )
    migration_destinations = [
        _absolute_path(getattr(paths, location.destination_name))
        for location in _LEGACY_LOCATIONS
    ]
    for generated in normalized:
        for destination in migration_destinations:
            if _paths_overlap(
                generated, destination
            ) or (
                _same_existing_object(generated, destination)
                and not aliases_are_allowed(
                    generated, destination
                )
            ):
                raise MigrationValidationError(
                    "migration internal path overlaps destination"
                )
    for source in sources:
        for generated in normalized:
            if _paths_overlap(
                source.source, generated
            ) or _same_existing_object(source.source, generated):
                raise MigrationValidationError(
                    "source overlaps migration internal path"
                )


def _absolute_path(path: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise MigrationValidationError(
            "migration path must be absolute"
        )
    return Path(os.path.abspath(candidate))


def _assert_inside(root: Path, path: Path) -> None:
    root = _comparison_path(root)
    path = _comparison_path(path)
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise MigrationValidationError(
            "migration path is outside managed data root"
        ) from error
    if not relative.parts:
        raise MigrationValidationError(
            "migration path must not replace data root"
        )


def _assert_no_symlink_chain(
    path: Path, *, include_leaf: bool
) -> None:
    candidate = _absolute_path(path)
    parts = candidate.parts
    current = Path(parts[0])
    limit = len(parts) if include_leaf else len(parts) - 1
    for part in parts[1:limit]:
        current /= part
        try:
            current_stat = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as error:
            raise MigrationValidationError(
                "migration path cannot be validated"
            ) from error
        if stat.S_ISLNK(current_stat.st_mode):
            if not _is_allowed_system_symlink(current):
                raise MigrationValidationError(
                    "migration parent chain contains a symlink"
                )
            continue
        if not stat.S_ISDIR(current_stat.st_mode):
            raise MigrationValidationError(
                "migration parent chain is not a directory"
            )


def _paths_overlap(left: Path, right: Path) -> bool:
    left_path = _comparison_path(left)
    right_path = _comparison_path(right)
    try:
        left_path.relative_to(right_path)
        return True
    except ValueError:
        pass
    try:
        right_path.relative_to(left_path)
        return True
    except ValueError:
        return False


def _same_existing_object(left: Path, right: Path) -> bool:
    try:
        left_stat = os.lstat(left)
        right_stat = os.lstat(right)
    except OSError:
        return False
    return (
        left_stat.st_dev == right_stat.st_dev
        and left_stat.st_ino == right_stat.st_ino
    )


def _comparison_path(path: Path) -> Path:
    absolute = _absolute_path(path)
    parts = absolute.parts
    aliases = {
        "var": ("private", "var"),
        "tmp": ("private", "tmp"),
        "etc": ("private", "etc"),
    }
    replacement = aliases.get(parts[1]) if len(parts) > 1 else None
    if replacement is None:
        return absolute
    return Path("/", *replacement, *parts[2:])


def _is_allowed_system_symlink(path: Path) -> bool:
    expected_targets = {
        Path("/var"): Path("/private/var"),
        Path("/tmp"): Path("/private/tmp"),
        Path("/etc"): Path("/private/etc"),
    }
    expected = expected_targets.get(path)
    if expected is None:
        return False
    try:
        target = Path(os.readlink(path))
    except OSError:
        return False
    if not target.is_absolute():
        target = Path(os.path.abspath(path.parent / target))
    return target == expected


@contextmanager
def _data_root_lock(paths: TomosPaths) -> Iterator[None]:
    _validate_tomos_layout(paths)
    _fault_injection("before_open_data_root", "maintenance")
    try:
        root_fd = _open_directory_chain(paths.root, create=True)
    except OSError as error:
        raise MigrationValidationError(
            "managed data root changed before lock"
        ) from error
    fd = -1
    try:
        for attempt in range(3):
            try:
                fd = os.open(
                    ".tomos-maintenance.lock",
                    os.O_RDWR
                    | os.O_CREAT
                    | os.O_NOFOLLOW
                    | os.O_CLOEXEC,
                    0o600,
                    dir_fd=root_fd,
                )
                break
            except FileNotFoundError:
                if attempt == 2:
                    raise
                os.close(root_fd)
                root_fd = _open_directory_chain(
                    paths.root, create=True
                )
        os.fsync(root_fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        _ensure_directory_fd_matches_path(root_fd, paths.root)
        _validate_tomos_layout(paths)
        yield
    finally:
        if fd >= 0:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        os.close(root_fd)


def _write_record(path: Path, payload: dict) -> None:
    serialized = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    if len(serialized) > _MAX_RECORD_BYTES:
        raise MigrationValidationError(
            "migration record is too large"
        )
    parent_fd = _open_directory_chain(path.parent, create=True)
    temporary = f".{path.name}.{uuid.uuid4().hex}.tmp"
    fd = -1
    try:
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
        _write_all(fd, serialized)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(
            temporary,
            path.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        os.fsync(parent_fd)
    except MigrationError:
        raise
    except OSError as error:
        raise MigrationValidationError(
            "migration record write failed"
        ) from error
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temporary, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except OSError:
            pass
        os.close(parent_fd)


def _write_all(fd: int, payload: bytes | memoryview) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise MigrationValidationError(
                "migration write made no progress"
            )
        view = view[written:]


def _read_record(path: Path) -> dict | None:
    try:
        parent_fd = _open_directory_chain(path.parent)
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        return _read_record_at(parent_fd, path.name)
    finally:
        os.close(parent_fd)


def _read_record_at(parent_fd: int, name: str) -> dict | None:
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
    except (FileNotFoundError, OSError):
        return None
    try:
        payload = _read_bounded_bytes(
            fd, os.fstat(fd), _MAX_RECORD_BYTES
        )
    finally:
        os.close(fd)
    if payload is None:
        return None
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _write_journal(paths: TomosPaths, journal: dict) -> None:
    journal_id = journal.get("journalId") or journal.get("migrationId")
    if not isinstance(journal_id, str):
        raise MigrationValidationError("migration journal id is invalid")
    _write_record(_journal_path(paths, journal_id), journal)


def _journal_path(paths: TomosPaths, journal_id: str) -> Path:
    if not (
        _valid_identifier(journal_id)
        or (
            journal_id.startswith("rollback-")
            and _valid_identifier(journal_id.removeprefix("rollback-"))
        )
    ):
        raise MigrationValidationError("migration journal id is invalid")
    return paths.migration / "journals" / f"{journal_id}.json"


def _completion_record_path(
    paths: TomosPaths, migration_id: str
) -> Path:
    return paths.migration / "records" / f"{migration_id}.json"


def _snapshot_record_path(
    paths: TomosPaths, snapshot_id: str
) -> Path:
    return paths.migration / "snapshots" / f"{snapshot_id}.json"


def _staging_path(destination: Path, migration_id: str) -> Path:
    return destination.parent / (
        f".{destination.name}.tomos-stage-{migration_id}"
    )


def _retained_external_write_guard_id(
    migration_id: str, snapshot_id: str, kind: str
) -> str:
    if (
        not _valid_identifier(migration_id)
        or not _valid_identifier(snapshot_id)
        or kind not in _SQLITE_KINDS
    ):
        raise MigrationValidationError(
            "retained external write guard id is invalid"
        )
    return _digest_json(
        {
            "migrationId": migration_id,
            "snapshotId": snapshot_id,
            "kind": kind,
        }
    )[:32]


def _retained_external_write_guard_path(
    destination: Path,
    migration_id: str,
    snapshot_id: str,
    kind: str,
) -> Path:
    guard_id = _retained_external_write_guard_id(
        migration_id, snapshot_id, kind
    )
    return destination.parent / (
        f".{destination.name}."
        f"tomos-retained-external-write-guard-{guard_id}"
    )


def _retained_external_write_guard_record_path(
    paths: TomosPaths,
    migration_id: str,
    snapshot_id: str,
    kind: str,
) -> Path:
    guard_id = _retained_external_write_guard_id(
        migration_id, snapshot_id, kind
    )
    return (
        paths.migration
        / "retained-external-write-guards"
        / f"{guard_id}.json"
    )


def _snapshot_path(destination: Path, snapshot_id: str) -> Path:
    return destination.parent / (
        f".{destination.name}.tomos-snapshot-{snapshot_id}"
    )


def _apply_backup_path(destination: Path, migration_id: str) -> Path:
    return destination.parent / (
        f".{destination.name}.tomos-apply-current-{migration_id}"
    )


def _rollback_backup_path(
    destination: Path, snapshot_id: str
) -> Path:
    return destination.parent / (
        f".{destination.name}.tomos-rollback-current-{snapshot_id}"
    )


def _rollback_restore_path(
    destination: Path, snapshot_id: str
) -> Path:
    return destination.parent / (
        f".{destination.name}.tomos-rollback-restore-{snapshot_id}"
    )


def _physical_restore_path(backup: Path) -> Path:
    return backup.with_name(f"{backup.name}.restore")


def _sqlite_displaced_path(backup: Path) -> Path:
    return backup.with_name(f"{backup.name}.displaced")


def _remove_path(path: Path) -> None:
    try:
        parent_fd = _open_directory_chain(path.parent)
    except FileNotFoundError:
        return
    try:
        _remove_entry_at(parent_fd, path.name)
    finally:
        os.close(parent_fd)


def _remove_path_durable(path: Path) -> None:
    _remove_path(path)


def _safe_remove_durable(path: Path) -> None:
    try:
        _remove_path_durable(path)
    except OSError:
        pass


def _cleanup_orphan_internal_files(paths: TomosPaths) -> None:
    for location in _LEGACY_LOCATIONS:
        destination = getattr(paths, location.destination_name)
        parent = destination.parent
        if not parent.exists():
            continue
        _assert_no_symlink_chain(parent, include_leaf=True)
        prefixes = (
            f".{destination.name}.tomos-stage-",
            f".{destination.name}.tomos-apply-current-",
            f".{destination.name}.tomos-rollback-current-",
            f".{destination.name}.tomos-rollback-restore-",
        )
        for candidate in parent.iterdir():
            if candidate.name.startswith(prefixes):
                _safe_remove_durable(candidate)
    for directory_name in (
        "records",
        "snapshots",
        "journals",
        "retained-external-write-guards",
    ):
        directory = paths.migration / directory_name
        if not directory.exists():
            continue
        for temporary in directory.glob(".*.tmp"):
            _safe_remove_durable(temporary)


def _existing_snapshot_ids(paths: TomosPaths) -> list[str]:
    directory = paths.migration / "snapshots"
    if not directory.exists():
        return []
    return sorted(
        path.stem
        for path in directory.glob("*.json")
        if _valid_identifier(path.stem)
    )


def _fsync_tree(root: Path) -> None:
    directories = [root]
    directories.extend(
        path
        for path in root.rglob("*")
        if path.is_dir() and not path.is_symlink()
    )
    for directory in sorted(
        directories,
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        _fsync_directory(directory)


def _fsync_tree_fd(root_fd: int) -> None:
    names, errors = _directory_names(root_fd)
    if errors:
        raise MigrationValidationError(
            "staging directory cannot be synchronized"
        )
    for name in names:
        child_fd = os.open(name, _FILE_FLAGS, dir_fd=root_fd)
        try:
            child_stat = os.fstat(child_fd)
            if stat.S_ISDIR(child_stat.st_mode):
                _fsync_tree_fd(child_fd)
            elif stat.S_ISREG(child_stat.st_mode):
                os.fsync(child_fd)
            else:
                raise MigrationValidationError(
                    "staging contains an invalid entry"
                )
        finally:
            os.close(child_fd)
    os.fsync(root_fd)


def _mkdir_durable(directory: Path) -> None:
    fd = _open_directory_chain(directory, create=True)
    os.fsync(fd)
    os.close(fd)


def _fsync_directory(directory: Path) -> None:
    fd = _open_directory_chain(directory)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _validated_approvals(
    approved_items: Sequence[str],
) -> tuple[str, ...]:
    if isinstance(approved_items, (str, bytes)):
        raise MigrationApprovalError(
            "approved items must be a non-empty list"
        )
    approved = tuple(approved_items)
    if (
        not approved
        or any(not isinstance(kind, str) for kind in approved)
        or len(set(approved)) != len(approved)
        or any(kind not in _known_kinds() for kind in approved)
    ):
        raise MigrationApprovalError("approved items are invalid")
    return tuple(sorted(approved))


def _known_kinds() -> frozenset[str]:
    return frozenset(location.kind for location in _LEGACY_LOCATIONS)


def _destination_for_kind(paths: TomosPaths, kind: str) -> Path:
    for location in _LEGACY_LOCATIONS:
        if location.kind == kind:
            return getattr(paths, location.destination_name)
    raise MigrationNotFoundError("migration item was not found")


def _public_completion_record(
    record: dict, cleanup_pending: bool
) -> dict:
    return {
        "status": "completed",
        "migrationId": record["migrationId"],
        "snapshotId": record["snapshotId"],
        "approvedItems": list(record["approvedItems"]),
        "cleanupPending": cleanup_pending,
    }


def _valid_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(
            character in "0123456789abcdef" for character in value
        )
    )


def _valid_digest(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    digest_type = value.get("type")
    sha256 = value.get("sha256")
    if not (
        isinstance(sha256, str)
        and len(sha256) == 64
        and all(character in "0123456789abcdef" for character in sha256)
    ):
        return False
    if digest_type == "file":
        return (
            set(value) == {"type", "bytes", "sha256"}
            and isinstance(value.get("bytes"), int)
            and not isinstance(value.get("bytes"), bool)
            and value["bytes"] >= 0
        )
    if digest_type == "directory":
        return (
            set(value) == {"type", "fileCount", "sha256"}
            and isinstance(value.get("fileCount"), int)
            and not isinstance(value.get("fileCount"), bool)
            and value["fileCount"] >= 0
        )
    return False


def _valid_digest_for_kind(kind: str, value: object) -> bool:
    if not _valid_digest(value):
        return False
    expected_type = "file" if _is_sqlite_kind(kind) else "directory"
    return value["type"] == expected_type


def _valid_file_physical_digest(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"bytes", "sha256"}
        and isinstance(value.get("bytes"), int)
        and not isinstance(value.get("bytes"), bool)
        and value["bytes"] >= 0
        and isinstance(value.get("sha256"), str)
        and len(value["sha256"]) == 64
        and all(
            character in "0123456789abcdef"
            for character in value["sha256"]
        )
    )


def _valid_sqlite_physical_digest(value: object) -> bool:
    if (
        not isinstance(value, dict)
        or set(value) != {"type", "main", "sidecars"}
        or value.get("type") != "sqlite-physical"
        or not _valid_file_physical_digest(value.get("main"))
        or not isinstance(value.get("sidecars"), dict)
        or set(value["sidecars"]) - {"wal", "shm", "journal"}
    ):
        return False
    return all(
        _valid_file_physical_digest(digest)
        for digest in value["sidecars"].values()
    )


def _retained_external_write_guard_record(
    migration_id: str,
    snapshot_id: str,
    kind: str,
    initial_physical: dict,
    initial_logical: dict,
    component_identities: dict[str, dict[str, int]],
) -> dict:
    return {
        "version": 1,
        "status": "retained_external_write_guard",
        "guardId": _retained_external_write_guard_id(
            migration_id, snapshot_id, kind
        ),
        "migrationId": migration_id,
        "snapshotId": snapshot_id,
        "kind": kind,
        "initialPhysicalDigest": initial_physical,
        "initialLogicalDigest": initial_logical,
        "componentIdentities": component_identities,
    }


def _validate_retained_external_write_guard_record(
    record: dict,
) -> dict:
    migration_id = record.get("migrationId")
    snapshot_id = record.get("snapshotId")
    kind = record.get("kind")
    initial_physical = record.get("initialPhysicalDigest")
    if (
        set(record)
        != {
            "version",
            "status",
            "guardId",
            "migrationId",
            "snapshotId",
            "kind",
            "initialPhysicalDigest",
            "initialLogicalDigest",
            "componentIdentities",
        }
        or record.get("version") != 1
        or record.get("status")
        != "retained_external_write_guard"
        or not _valid_identifier(migration_id)
        or not _valid_identifier(snapshot_id)
        or migration_id == snapshot_id
        or kind not in _SQLITE_KINDS
        or record.get("guardId")
        != _retained_external_write_guard_id(
            migration_id, snapshot_id, kind
        )
        or not _valid_sqlite_physical_digest(initial_physical)
        or not _valid_digest_for_kind(
            kind, record.get("initialLogicalDigest")
        )
        or not _valid_sqlite_component_identities(
            record.get("componentIdentities"),
            initial_physical,
        )
    ):
        raise MigrationValidationError(
            "retained external write guard record is invalid"
        )
    return record


def _write_retained_external_write_guard_record(
    paths: TomosPaths, expected: dict
) -> None:
    expected = _validate_retained_external_write_guard_record(expected)
    record_path = _retained_external_write_guard_record_path(
        paths,
        expected["migrationId"],
        expected["snapshotId"],
        expected["kind"],
    )
    observed = _read_record(record_path)
    if observed is not None:
        observed = _validate_retained_external_write_guard_record(
            observed
        )
        if observed != expected:
            raise MigrationValidationError(
                "retained external write guard record changed"
            )
        return
    if _destination_exists(record_path):
        raise MigrationValidationError(
            "retained external write guard record is invalid"
        )
    _write_record(record_path, expected)


def _validate_snapshot_record_schema(
    snapshot_id: str, record: dict
) -> dict:
    if (
        set(record)
        != {
            "version",
            "status",
            "snapshotId",
            "migrationId",
            "items",
        }
        or record.get("version") != 1
        or record.get("status") != "available"
        or record.get("snapshotId") != snapshot_id
        or not _valid_identifier(snapshot_id)
        or not _valid_identifier(record.get("migrationId"))
        or record["migrationId"] == snapshot_id
        or not isinstance(record.get("items"), list)
        or not record["items"]
    ):
        raise MigrationValidationError(
            "migration snapshot record is invalid"
        )
    seen: set[str] = set()
    for item in record["items"]:
        if not isinstance(item, dict):
            raise MigrationValidationError(
                "migration snapshot record is invalid"
            )
        kind = item.get("kind")
        had_destination = item.get("hadDestination")
        expected_fields = {
            "kind",
            "hadDestination",
            "publishedDigest",
        }
        if had_destination is True:
            expected_fields.add("priorDigest")
        if (
            set(item) != expected_fields
            or kind not in _known_kinds()
            or kind in seen
            or not isinstance(had_destination, bool)
            or not _valid_digest_for_kind(
                kind, item.get("publishedDigest")
            )
            or (
                had_destination
                and not _valid_digest_for_kind(
                    kind, item.get("priorDigest")
                )
            )
        ):
            raise MigrationValidationError(
                "migration snapshot record is invalid"
            )
        seen.add(kind)
    return record


def _validate_completion_record_schema(
    migration_id: str,
    completion: dict,
    *,
    allowed_statuses: frozenset[str] = frozenset(
        {"completed", "superseded", "rolled_back"}
    ),
) -> dict:
    approved = completion.get("approvedItems")
    preview_id = completion.get("previewId")
    snapshot_id = completion.get("snapshotId")
    snapshot_digest = completion.get("snapshotRecordDigest")
    source_snapshot_digest = completion.get("sourceSnapshotDigest")
    source_captured_at = completion.get("sourceCapturedAt")
    if (
        set(completion)
        != {
            "status",
            "migrationId",
            "snapshotId",
            "previewId",
            "approvedItems",
            "snapshotRecordDigest",
            "sourceSnapshotDigest",
            "sourceCapturedAt",
        }
        or completion.get("status") not in allowed_statuses
        or completion.get("migrationId") != migration_id
        or not _valid_identifier(migration_id)
        or not _valid_identifier(snapshot_id)
        or snapshot_id == migration_id
        or not isinstance(preview_id, str)
        or len(preview_id) != 64
        or any(
            character not in "0123456789abcdef"
            for character in preview_id
        )
        or not isinstance(approved, list)
        or not approved
        or approved != sorted(approved)
        or len(set(approved)) != len(approved)
        or any(kind not in _known_kinds() for kind in approved)
        or not isinstance(snapshot_digest, str)
        or len(snapshot_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in snapshot_digest
        )
        or not isinstance(source_snapshot_digest, str)
        or len(source_snapshot_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in source_snapshot_digest
        )
        or not isinstance(source_captured_at, int)
        or isinstance(source_captured_at, bool)
        or source_captured_at <= 0
        or migration_id
        != _digest_json(
            {
                "previewId": preview_id,
                "approvedItems": approved,
            }
        )[:32]
    ):
        raise MigrationValidationError(
            "migration completion record is invalid"
        )
    return completion


def _read_valid_completion_record(
    paths: TomosPaths,
    migration_id: str,
    *,
    allowed_statuses: frozenset[str] = frozenset(
        {"completed", "superseded", "rolled_back"}
    ),
) -> dict | None:
    completion_path = _completion_record_path(paths, migration_id)
    completion = _read_record(completion_path)
    if completion is None:
        if _destination_exists(completion_path):
            raise MigrationValidationError(
                "migration completion record is invalid"
            )
        return None
    return _validate_completion_record_schema(
        migration_id,
        completion,
        allowed_statuses=allowed_statuses,
    )


def _validate_snapshot_completion(
    paths: TomosPaths,
    snapshot_record: dict,
    *,
    allowed_statuses: frozenset[str] = frozenset({"completed"}),
) -> dict:
    migration_id = snapshot_record["migrationId"]
    completion = _read_valid_completion_record(
        paths,
        migration_id,
        allowed_statuses=allowed_statuses,
    )
    item_kinds = [item["kind"] for item in snapshot_record["items"]]
    if (
        not completion
        or completion.get("snapshotId")
        != snapshot_record["snapshotId"]
        or completion.get("approvedItems") != item_kinds
        or completion["snapshotRecordDigest"]
        != _digest_json(snapshot_record)
    ):
        raise MigrationValidationError(
            "migration snapshot completion is invalid"
        )
    return completion


def _read_valid_snapshot_record(
    paths: TomosPaths, snapshot_id: str
) -> dict:
    snapshot_path = _snapshot_record_path(paths, snapshot_id)
    snapshot_record = _read_record(snapshot_path)
    if snapshot_record is None:
        raise MigrationValidationError(
            "migration snapshot record is invalid"
        )
    return _validate_snapshot_record_schema(
        snapshot_id, snapshot_record
    )


def _validate_completed_migration_state(
    paths: TomosPaths,
    migration_id: str,
    *,
    expected_preview_id: str,
    expected_approved_items: Sequence[str],
) -> dict | None:
    completion = _read_valid_completion_record(paths, migration_id)
    if completion is None or completion["status"] != "completed":
        return None
    approved = list(expected_approved_items)
    if (
        completion["previewId"] != expected_preview_id
        or completion["approvedItems"] != approved
    ):
        raise MigrationValidationError(
            "migration completion record is inconsistent"
        )
    snapshot_record = _read_valid_snapshot_record(
        paths, completion["snapshotId"]
    )
    _validate_snapshot_completion(paths, snapshot_record)
    if [item["kind"] for item in snapshot_record["items"]] != approved:
        raise MigrationValidationError(
            "migration completion record is inconsistent"
        )
    for item in snapshot_record["items"]:
        destination = _destination_for_kind(paths, item["kind"])
        parent_fd = _open_directory_chain(destination.parent)
        try:
            _validate_rollback_item_at(
                parent_fd,
                destination,
                snapshot_record["snapshotId"],
                item,
            )
        finally:
            os.close(parent_fd)
    return completion


def _validate_apply_final_state(
    paths: TomosPaths, journal: dict
) -> dict:
    expected_snapshot = {
        "version": 1,
        "status": "available",
        "snapshotId": journal["snapshotId"],
        "migrationId": journal["migrationId"],
        "items": [
            {
                "kind": item["kind"],
                "hadDestination": item["hadDestination"],
                **(
                    {"priorDigest": item["priorDigest"]}
                    if item["hadDestination"]
                    else {}
                ),
                "publishedDigest": item["publishedDigest"],
            }
            for item in journal["items"]
        ],
    }
    observed_snapshot = _read_valid_snapshot_record(
        paths, journal["snapshotId"]
    )
    if observed_snapshot != expected_snapshot:
        raise MigrationValidationError(
            "migration final snapshot is inconsistent"
        )
    completion = _validate_completed_migration_state(
        paths,
        journal["migrationId"],
        expected_preview_id=journal["previewId"],
        expected_approved_items=journal["approvedItems"],
    )
    if (
        completion is None
        or completion["snapshotId"] != journal["snapshotId"]
        or completion["sourceSnapshotDigest"]
        != journal["sourceSnapshotDigest"]
        or completion["sourceCapturedAt"]
        != journal["sourceCapturedAt"]
    ):
        raise MigrationValidationError(
            "migration final completion is inconsistent"
        )
    return completion


def _expected_snapshot_from_final_journal(journal: dict) -> dict:
    return {
        "version": 1,
        "status": "available",
        "snapshotId": journal["snapshotId"],
        "migrationId": journal["migrationId"],
        "items": [
            {
                "kind": item["kind"],
                "hadDestination": item["hadDestination"],
                **(
                    {"priorDigest": item["priorDigest"]}
                    if item["hadDestination"]
                    else {}
                ),
                "publishedDigest": item["publishedDigest"],
            }
            for item in journal["items"]
        ],
    }


def _validate_rollback_final_state(
    paths: TomosPaths, journal: dict
) -> dict:
    state = journal["state"]
    expected_snapshot = _expected_snapshot_from_final_journal(journal)
    allowed_statuses = (
        frozenset({"completed", "rolled_back"})
        if state == "commit_pending"
        else frozenset({"rolled_back"})
    )
    if state == "record_cleanup_pending":
        completion = _read_valid_completion_record(
            paths,
            journal["migrationId"],
            allowed_statuses=allowed_statuses,
        )
        if (
            completion is None
            or completion["snapshotId"] != journal["snapshotId"]
            or completion["approvedItems"]
            != [item["kind"] for item in journal["items"]]
            or completion["snapshotRecordDigest"]
            != _digest_json(expected_snapshot)
        ):
            raise MigrationValidationError(
                "rollback final completion is inconsistent"
            )
    else:
        observed_snapshot = _read_valid_snapshot_record(
            paths, journal["snapshotId"]
        )
        if observed_snapshot != expected_snapshot:
            raise MigrationValidationError(
                "rollback final snapshot is inconsistent"
            )
        completion = _validate_snapshot_completion(
            paths,
            observed_snapshot,
            allowed_statuses=allowed_statuses,
        )

    for item in journal["items"]:
        destination = _destination_for_kind(paths, item["kind"])
        snapshot_name = _snapshot_path(
            destination, journal["snapshotId"]
        ).name
        backup_name = _rollback_backup_path(
            destination, journal["snapshotId"]
        ).name
        parent_fd = _open_directory_chain(destination.parent)
        try:
            destination_exists = _entry_exists_at(
                parent_fd, destination.name
            )
            if item["hadDestination"]:
                if (
                    not destination_exists
                    or _managed_digest_at(
                        parent_fd,
                        destination.name,
                        sqlite_logical=_is_sqlite_kind(
                            item["kind"]
                        ),
                    )
                    != item["priorDigest"]
                ):
                    raise MigrationValidationError(
                        "rollback final destination is inconsistent"
                    )
            elif destination_exists:
                raise MigrationValidationError(
                    "rollback final destination is inconsistent"
                )
            snapshot_exists = _entry_exists_at(
                parent_fd, snapshot_name
            )
            if _is_sqlite_kind(item["kind"]):
                if state == "record_cleanup_pending":
                    if snapshot_exists:
                        raise MigrationValidationError(
                            "rollback final snapshot is inconsistent"
                        )
                elif (
                    item["hadDestination"]
                    and state in {"commit_pending", "committed"}
                ):
                    if (
                        not snapshot_exists
                        or _managed_digest_at(
                            parent_fd,
                            snapshot_name,
                            sqlite_logical=True,
                        )
                        != item["priorDigest"]
                    ):
                        raise MigrationValidationError(
                            "rollback final snapshot is inconsistent"
                        )
                elif item["hadDestination"] and snapshot_exists:
                    if (
                        _managed_digest_at(
                            parent_fd,
                            snapshot_name,
                            sqlite_logical=True,
                        )
                        != item["priorDigest"]
                    ):
                        raise MigrationValidationError(
                            "rollback final snapshot is inconsistent"
                        )
                elif snapshot_exists:
                    raise MigrationValidationError(
                        "rollback final snapshot is inconsistent"
                    )
            elif snapshot_exists:
                raise MigrationValidationError(
                    "rollback final snapshot is inconsistent"
                )
            backup_exists = _entry_exists_at(parent_fd, backup_name)
            if backup_exists:
                if _is_sqlite_kind(item["kind"]):
                    if (
                        _sqlite_physical_digest_at(
                            parent_fd, backup_name
                        )
                        != item["publishedPhysicalDigest"]
                        or _managed_digest_at(
                            parent_fd,
                            backup_name,
                            sqlite_logical=True,
                        )
                        != item["publishedDigest"]
                    ):
                        raise MigrationValidationError(
                            "rollback final backup is inconsistent"
                        )
                elif _managed_digest_at(
                    parent_fd,
                    backup_name,
                    sqlite_logical=False,
                ) != item["publishedDigest"]:
                    raise MigrationValidationError(
                        "rollback final backup is inconsistent"
                    )
            if state in {"commit_pending", "committed"} and not backup_exists:
                raise MigrationValidationError(
                    "rollback final backup is missing"
                )
            if state == "record_cleanup_pending" and backup_exists:
                raise MigrationValidationError(
                    "rollback cleanup is inconsistent"
                )
        finally:
            os.close(parent_fd)
    return completion


def _validate_rollback_snapshot_at(
    parent_fd: int,
    destination: Path,
    snapshot_id: str,
    item: dict,
) -> None:
    snapshot_name = _snapshot_path(destination, snapshot_id).name
    snapshot_exists = _entry_exists_at(parent_fd, snapshot_name)
    if item["hadDestination"]:
        if (
            not snapshot_exists
            or _managed_digest_at(
                parent_fd,
                snapshot_name,
                sqlite_logical=_is_sqlite_kind(item["kind"]),
            )
            != item["priorDigest"]
        ):
            raise MigrationValidationError(
                "migration snapshot changed before rollback"
            )
    elif snapshot_exists or "priorDigest" in item:
        raise MigrationValidationError(
            "migration snapshot state is inconsistent"
        )


def _validate_rollback_item_at(
    parent_fd: int,
    destination: Path,
    snapshot_id: str,
    item: dict,
) -> None:
    if (
        not _entry_exists_at(parent_fd, destination.name)
        or _managed_digest_at(
            parent_fd,
            destination.name,
            sqlite_logical=_is_sqlite_kind(item["kind"]),
        )
        != item["publishedDigest"]
    ):
        raise MigrationValidationError(
            "published destination changed before rollback"
        )
    _validate_rollback_snapshot_at(
        parent_fd, destination, snapshot_id, item
    )


def _validate_journal_schema(
    paths: TomosPaths, file_name: str, journal: dict
) -> dict:
    if (
        "/" in file_name
        or "\\" in file_name
        or not file_name.endswith(".json")
    ):
        raise MigrationValidationError("migration journal name is invalid")
    operation = journal.get("operation")
    state = journal.get("state")
    items = journal.get("items")
    if (
        journal.get("version") != 1
        or operation not in {"apply", "rollback"}
        or not isinstance(items, list)
        or not items
    ):
        raise MigrationValidationError("migration journal schema is invalid")
    migration_id = journal.get("migrationId")
    snapshot_id = journal.get("snapshotId")
    if not _valid_identifier(migration_id) or not _valid_identifier(snapshot_id):
        raise MigrationValidationError("migration journal id is invalid")
    if migration_id == snapshot_id:
        raise MigrationValidationError("migration journal ids collide")
    allowed_common = {
        "version",
        "operation",
        "state",
        "migrationId",
        "snapshotId",
        "items",
        "recoveryErrorCount",
    }
    if "recoveryErrorCount" in journal and (
        not isinstance(journal["recoveryErrorCount"], int)
        or isinstance(journal["recoveryErrorCount"], bool)
        or journal["recoveryErrorCount"] <= 0
    ):
        raise MigrationValidationError("migration journal schema is invalid")
    if operation == "apply":
        expected_name = f"{migration_id}.json"
        allowed = allowed_common | {
            "previewId",
            "approvedItems",
            "pruneSnapshotIds",
            "sourceSnapshotDigest",
            "sourceCapturedAt",
        }
        allowed_states = {
            "prepared",
            "recovering",
            "restore_failed",
            "committed",
            "prune_pending",
        }
        allowed_phases = {
            "prepared",
            "snapshot_pending",
            "snapshotted",
            "ownership_pending",
            "owned",
            "publish_pending",
            "published",
            "restore_pending",
            "recovery_pending",
            "recovered",
        }
        approved = journal.get("approvedItems")
        prune_ids = journal.get("pruneSnapshotIds")
        if (
            not isinstance(journal.get("previewId"), str)
            or len(journal["previewId"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in journal["previewId"]
            )
            or not isinstance(approved, list)
            or not approved
            or len(set(approved)) != len(approved)
            or any(kind not in _known_kinds() for kind in approved)
            or not isinstance(prune_ids, list)
            or len(set(prune_ids)) != len(prune_ids)
            or any(not _valid_identifier(value) for value in prune_ids)
            or snapshot_id in prune_ids
        ):
            raise MigrationValidationError(
                "migration journal schema is invalid"
            )
        has_source_digest = "sourceSnapshotDigest" in journal
        has_captured_at = "sourceCapturedAt" in journal
        if (
            has_source_digest != has_captured_at
            or (
                has_source_digest
                and (
                    not isinstance(
                        journal["sourceSnapshotDigest"], str
                    )
                    or len(journal["sourceSnapshotDigest"]) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in journal[
                            "sourceSnapshotDigest"
                        ]
                    )
                    or not isinstance(
                        journal["sourceCapturedAt"], int
                    )
                    or isinstance(
                        journal["sourceCapturedAt"], bool
                    )
                    or journal["sourceCapturedAt"] <= 0
                )
            )
        ):
            raise MigrationValidationError(
                "migration journal commit point is invalid"
            )
    else:
        journal_id = journal.get("journalId")
        expected_name = f"rollback-{snapshot_id}.json"
        allowed = allowed_common | {"journalId"}
        allowed_states = {
            "prepared",
            "recovering",
            "restore_failed",
            "commit_pending",
            "committed",
            "cleanup_pending",
            "record_cleanup_pending",
        }
        allowed_phases = {
            "prepared",
            "ownership_pending",
            "owned",
            "backup_pending",
            "backed_up",
            "restore_pending",
            "recovery_pending",
            "restored",
            "absent",
        }
        if journal_id != f"rollback-{snapshot_id}":
            raise MigrationValidationError("migration journal id is invalid")
    if (
        file_name != expected_name
        or set(journal) - allowed
        or state not in allowed_states
    ):
        raise MigrationValidationError("migration journal schema is invalid")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise MigrationValidationError(
                "migration journal item is invalid"
            )
        kind = item.get("kind")
        required = {
            "kind",
            "hadDestination",
            "phase",
            "expectedDigest",
            "priorDigest",
        } if operation == "apply" else {
            "kind",
            "hadDestination",
            "phase",
            "publishedDigest",
        }
        if operation == "rollback" and item.get("hadDestination") is True:
            required.add("priorDigest")
        optional = (
            {
                "publishedDigest",
                "priorPhysicalDigest",
                "replacementPhysicalDigest",
                "recoveryCurrentPhysicalDigest",
                "sqliteComponentPhase",
                "stagingOwnershipIdentities",
            }
            if operation == "apply"
            else {
                "publishedPhysicalDigest",
                "restorePhysicalDigest",
                "recoveryCurrentPhysicalDigest",
                "sqliteComponentPhase",
            }
        )
        if (
            set(item) - required - optional
            or not required.issubset(item)
            or kind not in _known_kinds()
            or kind in seen
            or not isinstance(item["hadDestination"], bool)
            or item["phase"] not in allowed_phases
        ):
            raise MigrationValidationError(
                "migration journal item is invalid"
            )
        seen.add(kind)
        digest_key = (
            "expectedDigest" if operation == "apply" else "publishedDigest"
        )
        if not _valid_digest_for_kind(kind, item[digest_key]):
            raise MigrationValidationError(
                "migration journal digest is invalid"
            )
        if operation == "apply" and (
            (
                item["hadDestination"]
                and not _valid_digest_for_kind(
                    kind, item["priorDigest"]
                )
            )
            or (
                not item["hadDestination"]
                and item["priorDigest"] is not None
            )
        ):
            raise MigrationValidationError(
                "migration journal prior digest is invalid"
            )
        if "publishedDigest" in item and not _valid_digest_for_kind(
            kind, item["publishedDigest"]
        ):
            raise MigrationValidationError(
                "migration journal digest is invalid"
            )
        if "priorPhysicalDigest" in item and (
            operation != "apply"
            or not _is_sqlite_kind(kind)
            or not item["hadDestination"]
            or not _valid_sqlite_physical_digest(
                item["priorPhysicalDigest"]
            )
        ):
            raise MigrationValidationError(
                "migration journal physical digest is invalid"
            )
        if (
            operation == "apply"
            and _is_sqlite_kind(kind)
            and item["hadDestination"]
            and "priorPhysicalDigest" not in item
        ):
            raise MigrationValidationError(
                "migration journal physical state is inconsistent"
            )
        if "replacementPhysicalDigest" in item and (
            operation != "apply"
            or not _is_sqlite_kind(kind)
            or not _valid_sqlite_physical_digest(
                item["replacementPhysicalDigest"]
            )
        ):
            raise MigrationValidationError(
                "migration replacement state is invalid"
            )
        if (
            operation == "apply"
            and _is_sqlite_kind(kind)
            and "replacementPhysicalDigest" not in item
        ):
            raise MigrationValidationError(
                "migration replacement state is missing"
            )
        if "stagingOwnershipIdentities" in item and (
            operation != "apply"
            or not _is_sqlite_kind(kind)
            or item["hadDestination"]
            or not _valid_sqlite_component_identities(
                item["stagingOwnershipIdentities"],
                item["replacementPhysicalDigest"],
            )
        ):
            raise MigrationValidationError(
                "migration staging ownership state is invalid"
            )
        if "publishedPhysicalDigest" in item and (
            operation != "rollback"
            or not _is_sqlite_kind(kind)
            or not _valid_sqlite_physical_digest(
                item["publishedPhysicalDigest"]
            )
        ):
            raise MigrationValidationError(
                "migration journal physical digest is invalid"
            )
        if (
            operation == "rollback"
            and _is_sqlite_kind(kind)
            and "publishedPhysicalDigest" not in item
        ):
            raise MigrationValidationError(
                "migration journal physical state is inconsistent"
            )
        if "restorePhysicalDigest" in item and (
            operation != "rollback"
            or not _is_sqlite_kind(kind)
            or not item["hadDestination"]
            or not _valid_sqlite_physical_digest(
                item["restorePhysicalDigest"]
            )
        ):
            raise MigrationValidationError(
                "migration restore state is invalid"
            )
        if (
            operation == "rollback"
            and _is_sqlite_kind(kind)
            and item["hadDestination"]
            and "restorePhysicalDigest" not in item
        ):
            raise MigrationValidationError(
                "migration restore state is missing"
            )
        if "recoveryCurrentPhysicalDigest" in item and (
            not _is_sqlite_kind(kind)
            or not _valid_sqlite_physical_digest(
                item["recoveryCurrentPhysicalDigest"]
            )
        ):
            raise MigrationValidationError(
                "migration recovery current state is invalid"
            )
        if "recoveryCurrentPhysicalDigest" in item:
            recovery_physical = item[
                "recoveryCurrentPhysicalDigest"
            ]
            if operation == "apply":
                if item["hadDestination"]:
                    recovery_is_bound = (
                        _sqlite_physical_is_publish_progress(
                            recovery_physical,
                            item["priorPhysicalDigest"],
                            item["replacementPhysicalDigest"],
                        )
                    )
                else:
                    recovery_is_bound = (
                        _sqlite_physical_is_expected_subset(
                            recovery_physical,
                            item["replacementPhysicalDigest"],
                        )
                    )
            else:
                recovery_is_bound = (
                    item["hadDestination"]
                    and _sqlite_physical_is_publish_progress(
                        recovery_physical,
                        item["publishedPhysicalDigest"],
                        item["restorePhysicalDigest"],
                    )
                )
            if not recovery_is_bound:
                raise MigrationValidationError(
                    "migration recovery current state is inconsistent"
                )
        if "sqliteComponentPhase" in item and (
            not _is_sqlite_kind(kind)
            or item["sqliteComponentPhase"]
            not in _SQLITE_COMPONENT_PHASES
        ):
            raise MigrationValidationError(
                "migration SQLite component phase is invalid"
            )
        component_phase = item.get("sqliteComponentPhase")
        if component_phase is not None:
            component_allowed_phases = (
                {
                    "publish_pending",
                    "published",
                    "recovery_pending",
                    "recovered",
                }
                if operation == "apply"
                else {
                    "restore_pending",
                    "recovery_pending",
                    "restored",
                }
            )
            if item["phase"] not in component_allowed_phases:
                raise MigrationValidationError(
                    "migration SQLite component state is inconsistent"
                )
        if component_phase == "quarantined" and (
            item["phase"] not in {"recovery_pending", "recovered"}
            or "recoveryCurrentPhysicalDigest" not in item
            or (
                operation == "apply"
                and not item["hadDestination"]
                and "stagingOwnershipIdentities" not in item
            )
        ):
            raise MigrationValidationError(
                "migration SQLite quarantine state is inconsistent"
            )
        if component_phase == "retained_external_write_guard" and (
            operation != "apply"
            or item["hadDestination"]
            or item["phase"] != "recovered"
            or "recoveryCurrentPhysicalDigest" not in item
            or "stagingOwnershipIdentities" not in item
        ):
            raise MigrationValidationError(
                "migration retained guard state is inconsistent"
            )
        if (
            "stagingOwnershipIdentities" in item
            and component_phase
            not in {
                "quarantined",
                "retained_external_write_guard",
            }
        ):
            raise MigrationValidationError(
                "migration staging ownership phase is inconsistent"
            )
        if (
            operation == "apply"
            and _is_sqlite_kind(kind)
            and item["phase"] == "published"
            and component_phase != "sidecars_cleaned"
        ) or (
            operation == "rollback"
            and _is_sqlite_kind(kind)
            and item["hadDestination"]
            and item["phase"] == "restored"
            and component_phase != "sidecars_cleaned"
        ):
            raise MigrationValidationError(
                "migration SQLite publish state is incomplete"
            )
        if "recoveryCurrentPhysicalDigest" in item and item["phase"] not in {
            "recovery_pending",
            "recovered",
        }:
            raise MigrationValidationError(
                "migration recovery current phase is inconsistent"
            )
        if operation == "rollback" and (
            (
                item["hadDestination"]
                and not _valid_digest_for_kind(
                    kind, item.get("priorDigest")
                )
            )
            or (
                not item["hadDestination"]
                and "priorDigest" in item
            )
        ):
            raise MigrationValidationError(
                "migration journal prior digest is invalid"
            )
        phase = item["phase"]
        if phase in {"ownership_pending", "owned"} and (
            not _is_sqlite_kind(kind)
            or (
                operation == "apply"
                and not item["hadDestination"]
            )
        ):
            raise MigrationValidationError(
                "migration journal ownership phase is inconsistent"
            )
        if phase == "recovery_pending" and not _is_sqlite_kind(kind):
            raise MigrationValidationError(
                "migration journal recovery phase is inconsistent"
            )
        if operation == "apply":
            has_published = "publishedDigest" in item
            if (
                (phase == "published" and not has_published)
                or (
                    has_published
                    and phase
                    not in {
                        "published",
                        "restore_pending",
                        "recovery_pending",
                        "recovered",
                    }
                )
                or (
                    has_published
                    and item["publishedDigest"]
                    != item["expectedDigest"]
                )
                or (
                    not item["hadDestination"]
                    and phase
                    in {
                        "snapshot_pending",
                        "snapshotted",
                        "restore_pending",
                    }
                )
                or (
                    _is_sqlite_kind(kind)
                    and item["hadDestination"]
                    and phase
                    in {
                        "snapshotted",
                        "ownership_pending",
                        "owned",
                        "publish_pending",
                        "published",
                        "restore_pending",
                        "recovery_pending",
                        "recovered",
                    }
                    and "priorPhysicalDigest" not in item
                )
            ):
                raise MigrationValidationError(
                    "migration journal phase is inconsistent"
                )
        elif (
            item["hadDestination"]
            and phase == "absent"
        ) or (
            not item["hadDestination"]
            and phase in {"restore_pending", "restored"}
        ):
            raise MigrationValidationError(
                "migration journal phase is inconsistent"
            )
        if (
            operation == "rollback"
            and _is_sqlite_kind(kind)
            and phase
            in {
                "backed_up",
                "restore_pending",
                "recovery_pending",
                "restored",
                "absent",
            }
            and "publishedPhysicalDigest" not in item
        ):
            raise MigrationValidationError(
                "migration journal physical state is inconsistent"
            )
    if operation == "apply" and set(journal["approvedItems"]) != seen:
        raise MigrationValidationError("migration journal items are invalid")
    phases = {item["phase"] for item in items}
    if operation == "apply":
        if state in {"committed", "prune_pending"} and phases != {
            "published"
        }:
            raise MigrationValidationError(
                "migration journal state is inconsistent"
            )
        if state in {"committed", "prune_pending"} and (
            "sourceSnapshotDigest" not in journal
            or "sourceCapturedAt" not in journal
        ):
            raise MigrationValidationError(
                "migration journal commit point is missing"
            )
        if state == "prepared" and phases & {
            "restore_pending",
            "recovered",
        }:
            raise MigrationValidationError(
                "migration journal state is inconsistent"
            )
    else:
        final_phases = {
            "restored" if item["hadDestination"] else "absent"
            for item in items
        }
        if state in {
            "commit_pending",
            "committed",
            "cleanup_pending",
            "record_cleanup_pending",
        } and phases != final_phases:
            raise MigrationValidationError(
                "migration journal state is inconsistent"
            )
    if (
        state == "restore_failed"
        and "recoveryErrorCount" not in journal
    ) or (
        "recoveryErrorCount" in journal
        and state != "restore_failed"
    ):
        raise MigrationValidationError(
            "migration journal recovery state is inconsistent"
        )
    mutable_paths: list[Path] = [
        _journal_path(
            paths,
            journal.get("journalId") or migration_id,
        )
    ]
    for kind in seen:
        destination = _destination_for_kind(paths, kind)
        mutable_paths.extend(
            (
                _staging_path(destination, migration_id),
                _snapshot_path(destination, snapshot_id),
                _apply_backup_path(destination, migration_id),
                _physical_restore_path(
                    _apply_backup_path(destination, migration_id)
                ),
                _sqlite_displaced_path(
                    _apply_backup_path(destination, migration_id)
                ),
                _rollback_backup_path(destination, snapshot_id),
                _rollback_restore_path(destination, snapshot_id),
                _physical_restore_path(
                    _rollback_backup_path(destination, snapshot_id)
                ),
                _sqlite_displaced_path(
                    _rollback_backup_path(destination, snapshot_id)
                ),
            )
        )
    mutable_paths.extend(
        (
            _completion_record_path(paths, migration_id),
            _snapshot_record_path(paths, snapshot_id),
        )
    )
    allowed_alias_groups: list[tuple[Path, ...]] = []
    if operation == "apply":
        for item in items:
            if not (
                _is_sqlite_kind(item["kind"])
                and not item["hadDestination"]
                and item["phase"]
                in {
                    "publish_pending",
                    "published",
                    "recovery_pending",
                    "recovered",
                }
            ):
                continue
            destination = _destination_for_kind(
                paths, item["kind"]
            )
            allowed_alias_groups.append(
                (
                    destination,
                    _staging_path(destination, migration_id),
                )
            )
    _validate_transaction_paths(
        paths,
        [],
        mutable_paths,
        allowed_existing_alias_groups=allowed_alias_groups,
    )
    return journal


def _fault_injection(_point: str, _kind: str) -> None:
    return


def _safe_known_root(path: Path) -> Path | None:
    root = Path(path)
    if not root.is_absolute() or root.is_symlink():
        return None
    try:
        normalized = _comparison_path(root)
        _assert_no_symlink_chain(normalized, include_leaf=True)
        fd = _open_directory_chain(normalized)
    except (OSError, RuntimeError, MigrationValidationError):
        return None
    os.close(fd)
    return normalized


def _source_exists(root: Path, location: _LegacyLocation) -> bool:
    try:
        root_fd = _open_directory_path(root)
        try:
            if location.is_directory:
                source_fd = _open_relative_directory(
                    root_fd, location.relative.parts
                )
            else:
                source_fd = _open_relative_file(
                    root_fd, location.relative.parts
                )
            os.close(source_fd)
            return True
        finally:
            os.close(root_fd)
    except OSError:
        return False


def _validated_provenance(
    source: MigrationSource,
) -> _SourceProvenance | None:
    provenance = source._provenance
    if provenance is None:
        return None
    location = provenance.location
    if (
        source.kind != location.kind
        or source.source != provenance.root / location.relative
        or source.destination != provenance.destination
        or location not in _LEGACY_LOCATIONS
    ):
        return None
    try:
        if _paths_overlap(source.source, provenance.data_root):
            return None
        _assert_inside(
            provenance.data_root, _absolute_path(source.destination)
        )
    except MigrationValidationError:
        return None
    return provenance


def _source_open_failure(
    error: OSError,
) -> tuple[list[_FileMetadata], int, int]:
    return (
        ([], 1, 0)
        if _open_status(error) == "excluded"
        else ([], 0, 1)
    )


def _directory_names(directory_fd: int) -> tuple[list[str], int]:
    try:
        with os.scandir(directory_fd) as entries:
            return sorted(entry.name for entry in entries), 0
    except OSError:
        return [], 1


def _open_directory_path(path: Path) -> int:
    fd = _open_directory_chain(path)
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError(errno.ENOTDIR, "not a directory")
    return fd


def _open_directory_chain(path: Path, create: bool = False) -> int:
    """Open an absolute directory one no-follow component at a time."""
    absolute = _comparison_path(path)
    current_fd = os.open("/", _DIRECTORY_FLAGS)
    try:
        for part in absolute.parts[1:]:
            try:
                next_fd = os.open(
                    part, _DIRECTORY_FLAGS, dir_fd=current_fd
                )
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o700, dir_fd=current_fd)
                    os.fsync(current_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(
                    part, _DIRECTORY_FLAGS, dir_fd=current_fd
                )
                os.fsync(next_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _open_relative_directory(
    root_fd: int, parts: tuple[str, ...]
) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = os.open(
                part, _DIRECTORY_FLAGS, dir_fd=current_fd
            )
            if not stat.S_ISDIR(os.fstat(next_fd).st_mode):
                os.close(next_fd)
                raise OSError(errno.ENOTDIR, "not a directory")
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except OSError:
        os.close(current_fd)
        raise


def _open_relative_directory_create(
    root_fd: int, parts: tuple[str, ...]
) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            try:
                next_fd = os.open(
                    part, _DIRECTORY_FLAGS, dir_fd=current_fd
                )
            except FileNotFoundError:
                try:
                    os.mkdir(part, 0o700, dir_fd=current_fd)
                    os.fsync(current_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(
                    part, _DIRECTORY_FLAGS, dir_fd=current_fd
                )
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _open_relative_file(
    root_fd: int, parts: tuple[str, ...]
) -> int:
    parent_fd = _open_relative_directory(root_fd, parts[:-1])
    try:
        return _open_child_file(parent_fd, parts[-1])
    finally:
        os.close(parent_fd)


def _open_child(directory_fd: int, name: str) -> tuple[int | None, str]:
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
    except OSError as error:
        return None, _open_status(error)
    return fd, "valid"


def _open_child_file(directory_fd: int, name: str) -> int:
    fd = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError(errno.EINVAL, "not a regular file")
    return fd


def _open_status(error: OSError) -> str:
    return (
        "excluded"
        if error.errno in {errno.ELOOP, errno.EINVAL, errno.ENOTDIR}
        else "error"
    )


def _official_pack_status(directory_fd: int) -> str:
    try:
        manifest_fd = _open_child_file(directory_fd, "pack.json")
    except FileNotFoundError:
        return "excluded"
    except OSError as error:
        return _open_status(error)
    try:
        manifest_bytes = _read_bounded_bytes(
            manifest_fd,
            os.fstat(manifest_fd),
            _MAX_OFFICIAL_STUDY_FILE_BYTES,
        )
    finally:
        os.close(manifest_fd)
    if (
        manifest_bytes is None
        or _sha256(manifest_bytes)
        != _OFFICIAL_STUDY_FILE_HASHES["pack.json"]
    ):
        return "excluded"
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return "excluded"
    if not isinstance(manifest, dict):
        return "excluded"
    modes = manifest.get("modes")
    if (
        manifest.get("id") != _OFFICIAL_PACK_ID
        or manifest.get("version") != _OFFICIAL_PACK_VERSION
        or manifest.get("visibility") != _OFFICIAL_PACK_VISIBILITY
        or not isinstance(modes, list)
        or len(modes) != len(_OFFICIAL_MODE_FILES)
    ):
        return "excluded"
    observed_modes = {
        (mode.get("id"), mode.get("promptFile"))
        for mode in modes
        if isinstance(mode, dict)
    }
    return (
        "valid"
        if observed_modes == set(_OFFICIAL_MODE_FILES.items())
        else "excluded"
    )


def _allowed_directory_file(
    kind: str,
    relative_name: str,
    file_fd: int,
    file_stat: os.stat_result,
) -> bool:
    if kind == "person-photos":
        return _is_person_photo_file(
            relative_name, file_fd, file_stat
        )
    if kind == "study-packs":
        parts = relative_name.split("/", 1)
        return (
            len(parts) == 2
            and parts[0] == _OFFICIAL_PACK_DIRECTORY
            and _is_official_study_pack_file(
                parts[1], file_fd, file_stat
            )
        )
    return False


def _is_official_study_pack_file(
    relative_name: str,
    file_fd: int,
    file_stat: os.stat_result,
) -> bool:
    expected_hash = _OFFICIAL_STUDY_FILE_HASHES.get(relative_name)
    if expected_hash is None:
        return False
    payload = _read_bounded_bytes(
        file_fd, file_stat, _MAX_OFFICIAL_STUDY_FILE_BYTES
    )
    return (
        payload is not None and _sha256(payload) == expected_hash
    )


def _is_person_photo_file(
    relative_name: str,
    file_fd: int,
    file_stat: os.stat_result,
) -> bool:
    suffix = Path(relative_name).suffix.lower()
    if suffix not in _PERSON_PHOTO_EXTENSIONS:
        return False
    payload = _read_bounded_bytes(
        file_fd, file_stat, _MAX_PERSON_PHOTO_BYTES
    )
    if payload is None:
        return False
    validators = {
        ".jpg": _is_safe_jpeg,
        ".png": _is_safe_png,
        ".webp": _is_safe_webp,
    }
    return validators[suffix](payload)


def _is_sensitive_name(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".") or any(
        part in lower for part in _SENSITIVE_NAME_PARTS
    )


def _read_bounded_bytes(
    file_fd: int,
    file_stat: os.stat_result,
    maximum_bytes: int,
) -> bytes | None:
    if file_stat.st_size < 0 or file_stat.st_size > maximum_bytes:
        return None
    try:
        os.lseek(file_fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(file_fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
    except OSError:
        return None
    return payload if len(payload) <= maximum_bytes else None


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


_JPEG_START_OF_FRAME_MARKERS = frozenset(
    {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
)


def _is_safe_jpeg(payload: bytes) -> bool:
    if len(payload) < 4 or payload[:2] != b"\xff\xd8":
        return False
    position = 2
    seen_frame = False
    seen_scan = False
    while position < len(payload):
        marker_start = position
        if payload[position] != 0xFF:
            return False
        while position < len(payload) and payload[position] == 0xFF:
            position += 1
        if position >= len(payload):
            return False
        marker = payload[position]
        position += 1
        if marker == 0xD9:
            return seen_frame and seen_scan and position == len(payload)
        if (
            marker in {0x00, 0x01, 0xD8}
            or 0xD0 <= marker <= 0xD7
            or position + 2 > len(payload)
        ):
            return False
        segment_length = struct.unpack(
            ">H", payload[position : position + 2]
        )[0]
        if segment_length < 2:
            return False
        segment_end = position + segment_length
        if segment_end > len(payload):
            return False
        segment = payload[position + 2 : segment_end]
        if marker in _JPEG_START_OF_FRAME_MARKERS:
            if len(segment) < 6:
                return False
            height, width = struct.unpack(">HH", segment[1:5])
            components = segment[5]
            if (
                width == 0
                or height == 0
                or components == 0
                or len(segment) != 6 + 3 * components
            ):
                return False
            seen_frame = True
        elif marker == 0xDA:
            if len(segment) < 4:
                return False
            components = segment[0]
            if (
                not seen_frame
                or components == 0
                or len(segment) != 4 + 2 * components
            ):
                return False
            seen_scan = True
            position = segment_end
            while position < len(payload):
                marker_start = payload.find(b"\xff", position)
                if marker_start < 0 or marker_start + 1 >= len(payload):
                    return False
                marker_position = marker_start + 1
                while (
                    marker_position < len(payload)
                    and payload[marker_position] == 0xFF
                ):
                    marker_position += 1
                if marker_position >= len(payload):
                    return False
                scan_marker = payload[marker_position]
                if scan_marker == 0x00:
                    position = marker_position + 1
                    continue
                if 0xD0 <= scan_marker <= 0xD7:
                    position = marker_position + 1
                    continue
                position = marker_start
                break
            continue
        position = segment_end
    return False


def _is_safe_webp(payload: bytes) -> bool:
    if (
        len(payload) < 20
        or payload[:4] != b"RIFF"
        or payload[8:12] != b"WEBP"
    ):
        return False
    riff_size = struct.unpack("<I", payload[4:8])[0]
    if riff_size != len(payload) - 8:
        return False
    valid, image_count = _validate_webp_chunks(
        payload, 12, len(payload), nested=False
    )
    return (
        valid
        and image_count == 1
        and _decode_webp_image(payload)
    )


def _webp_dimensions_are_safe(width: int, height: int) -> bool:
    maximum_pixels = _MAX_WEBP_DECODED_BYTES // 4
    return (
        width > 0
        and height > 0
        and width <= maximum_pixels // height
    )


def _webp_decoded_layout_is_safe(
    width: int, height: int, bytes_per_row: int
) -> bool:
    return (
        _webp_dimensions_are_safe(width, height)
        and bytes_per_row > 0
        and bytes_per_row
        <= _MAX_WEBP_DECODED_BYTES // height
    )


def _decode_webp_image(payload: bytes) -> bool:
    framework_paths = (
        "/System/Library/Frameworks/"
        "CoreFoundation.framework/CoreFoundation",
        "/System/Library/Frameworks/ImageIO.framework/ImageIO",
        "/System/Library/Frameworks/"
        "CoreGraphics.framework/CoreGraphics",
    )
    try:
        core_foundation, image_io, core_graphics = (
            ctypes.CDLL(path) for path in framework_paths
        )
        core_foundation.CFDataCreate.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_long,
        )
        core_foundation.CFDataCreate.restype = ctypes.c_void_p
        core_foundation.CFDataGetLength.argtypes = (
            ctypes.c_void_p,
        )
        core_foundation.CFDataGetLength.restype = ctypes.c_long
        core_foundation.CFRelease.argtypes = (ctypes.c_void_p,)
        core_foundation.CFRelease.restype = None
        image_io.CGImageSourceCreateWithData.argtypes = (
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        image_io.CGImageSourceCreateWithData.restype = ctypes.c_void_p
        image_io.CGImageSourceGetCount.argtypes = (ctypes.c_void_p,)
        image_io.CGImageSourceGetCount.restype = ctypes.c_size_t
        image_io.CGImageSourceGetStatus.argtypes = (ctypes.c_void_p,)
        image_io.CGImageSourceGetStatus.restype = ctypes.c_int32
        image_io.CGImageSourceGetStatusAtIndex.argtypes = (
            ctypes.c_void_p,
            ctypes.c_size_t,
        )
        image_io.CGImageSourceGetStatusAtIndex.restype = ctypes.c_int32
        image_io.CGImageSourceCreateImageAtIndex.argtypes = (
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
        )
        image_io.CGImageSourceCreateImageAtIndex.restype = ctypes.c_void_p
        core_graphics.CGImageGetWidth.argtypes = (ctypes.c_void_p,)
        core_graphics.CGImageGetWidth.restype = ctypes.c_size_t
        core_graphics.CGImageGetHeight.argtypes = (ctypes.c_void_p,)
        core_graphics.CGImageGetHeight.restype = ctypes.c_size_t
        core_graphics.CGImageGetBytesPerRow.argtypes = (
            ctypes.c_void_p,
        )
        core_graphics.CGImageGetBytesPerRow.restype = ctypes.c_size_t
        core_graphics.CGImageGetDataProvider.argtypes = (
            ctypes.c_void_p,
        )
        core_graphics.CGImageGetDataProvider.restype = ctypes.c_void_p
        core_graphics.CGDataProviderCopyData.argtypes = (
            ctypes.c_void_p,
        )
        core_graphics.CGDataProviderCopyData.restype = ctypes.c_void_p
    except (AttributeError, OSError):
        return False

    payload_buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(
        payload
    )
    data = core_foundation.CFDataCreate(
        None, payload_buffer, len(payload)
    )
    if not data:
        return False
    source = None
    image = None
    decoded_data = None
    try:
        source = image_io.CGImageSourceCreateWithData(data, None)
        if (
            not source
            or image_io.CGImageSourceGetCount(source) != 1
            or image_io.CGImageSourceGetStatus(source) != 0
            or image_io.CGImageSourceGetStatusAtIndex(source, 0) != 0
        ):
            return False
        image = image_io.CGImageSourceCreateImageAtIndex(
            source, 0, None
        )
        if not image:
            return False
        width = core_graphics.CGImageGetWidth(image)
        height = core_graphics.CGImageGetHeight(image)
        bytes_per_row = core_graphics.CGImageGetBytesPerRow(image)
        if not _webp_decoded_layout_is_safe(
            width, height, bytes_per_row
        ):
            return False
        provider = core_graphics.CGImageGetDataProvider(image)
        if provider:
            decoded_data = core_graphics.CGDataProviderCopyData(
                provider
            )
        decoded_length = (
            core_foundation.CFDataGetLength(decoded_data)
            if decoded_data
            else 0
        )
        return (
            decoded_length == bytes_per_row * height
            and image_io.CGImageSourceGetStatus(source) == 0
            and image_io.CGImageSourceGetStatusAtIndex(source, 0) == 0
        )
    except (AttributeError, OSError, OverflowError):
        return False
    finally:
        if decoded_data:
            core_foundation.CFRelease(decoded_data)
        if image:
            core_foundation.CFRelease(image)
        if source:
            core_foundation.CFRelease(source)
        core_foundation.CFRelease(data)


def _validate_webp_chunks(
    payload: bytes, start: int, end: int, *, nested: bool
) -> tuple[bool, int]:
    position = start
    image_count = 0
    while position < end:
        if position + 8 > end:
            return False, 0
        chunk_type = payload[position : position + 4]
        chunk_size = struct.unpack(
            "<I", payload[position + 4 : position + 8]
        )[0]
        chunk_start = position + 8
        chunk_end = chunk_start + chunk_size
        padded_end = chunk_end + (chunk_size & 1)
        if chunk_end > end or padded_end > end:
            return False, 0
        if chunk_size & 1 and payload[chunk_end] != 0:
            return False, 0
        chunk = payload[chunk_start:chunk_end]
        if chunk_type == b"VP8 ":
            if not _is_safe_vp8_bitstream(chunk):
                return False, 0
            image_count += 1
        elif chunk_type == b"VP8L":
            if not _is_safe_vp8l_bitstream(chunk):
                return False, 0
            image_count += 1
        elif chunk_type == b"VP8X":
            if nested or not _is_safe_vp8x_header(chunk):
                return False, 0
        elif chunk_type == b"ANMF":
            if nested or len(chunk) < 16:
                return False, 0
            frame_width = (
                int.from_bytes(chunk[6:9], "little") + 1
            )
            frame_height = (
                int.from_bytes(chunk[9:12], "little") + 1
            )
            if not _webp_dimensions_are_safe(
                frame_width, frame_height
            ):
                return False, 0
            valid, frame_images = _validate_webp_chunks(
                chunk, 16, len(chunk), nested=True
            )
            if not valid or frame_images != 1:
                return False, 0
            image_count += 1
        elif chunk_type == b"ANIM":
            if nested or len(chunk) != 6:
                return False, 0
        elif chunk_type == b"ALPH":
            if not nested or not chunk:
                return False, 0
        elif chunk_type not in {b"ICCP", b"EXIF", b"XMP "}:
            return False, 0
        position = padded_end
    return position == end, image_count


def _is_safe_vp8_bitstream(payload: bytes) -> bool:
    if len(payload) < 10:
        return False
    frame_tag = int.from_bytes(payload[:3], "little")
    first_partition_size = frame_tag >> 5
    width = struct.unpack("<H", payload[6:8])[0] & 0x3FFF
    height = struct.unpack("<H", payload[8:10])[0] & 0x3FFF
    return (
        frame_tag & 1 == 0
        and payload[3:6] == b"\x9d\x01\x2a"
        and first_partition_size > 0
        and first_partition_size <= len(payload) - 10
        and _webp_dimensions_are_safe(width, height)
    )


def _is_safe_vp8l_bitstream(payload: bytes) -> bool:
    if len(payload) < 13 or payload[0] != 0x2F:
        return False
    header = int.from_bytes(payload[1:5], "little")
    width = (header & 0x3FFF) + 1
    height = ((header >> 14) & 0x3FFF) + 1
    version = header >> 29
    return (
        version == 0
        and _webp_dimensions_are_safe(width, height)
    )


def _is_safe_vp8x_header(payload: bytes) -> bool:
    if (
        len(payload) != 10
        or payload[0] & 0xC1
        or payload[1:4] != b"\x00\x00\x00"
    ):
        return False
    width = int.from_bytes(payload[4:7], "little") + 1
    height = int.from_bytes(payload[7:10], "little") + 1
    return _webp_dimensions_are_safe(width, height)


def _is_safe_png(payload: bytes) -> bool:
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    position = 8
    seen_ihdr = False
    seen_idat = False
    idat_chunks: list[bytes] = []
    width = height = channels = 0
    while position + 12 <= len(payload):
        length = struct.unpack(">I", payload[position : position + 4])[0]
        chunk_end = position + 12 + length
        if chunk_end > len(payload):
            return False
        chunk_type = payload[position + 4 : position + 8]
        chunk_data = payload[position + 8 : position + 8 + length]
        expected_crc = struct.unpack(
            ">I", payload[position + 8 + length : chunk_end]
        )[0]
        if (
            zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            != expected_crc
        ):
            return False
        if not seen_ihdr:
            if chunk_type != b"IHDR" or length != 13:
                return False
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filter_method,
                interlace,
            ) = struct.unpack(">IIBBBBB", chunk_data)
            if (
                width == 0
                or height == 0
                or bit_depth != 8
                or color_type not in {2, 6}
                or compression != 0
                or filter_method != 0
                or interlace != 0
            ):
                return False
            channels = 3 if color_type == 2 else 4
            seen_ihdr = True
        elif chunk_type == b"IDAT":
            if length == 0:
                return False
            seen_idat = True
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            if length != 0 or not seen_idat or chunk_end != len(payload):
                return False
            return _png_pixels_are_bounded_and_complete(
                b"".join(idat_chunks), width, height, channels
            )
        else:
            return False
        position = chunk_end
    return False


def _png_pixels_are_bounded_and_complete(
    compressed: bytes, width: int, height: int, channels: int
) -> bool:
    expected_size = height * (1 + width * channels)
    if expected_size > _MAX_PNG_DECODED_BYTES:
        return False
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, expected_size + 1)
        raw += decoder.flush()
    except zlib.error:
        return False
    if (
        not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
        or len(raw) != expected_size
    ):
        return False
    stride = 1 + width * channels
    return all(
        raw[offset] <= 4 for offset in range(0, len(raw), stride)
    )


def _file_preview(
    source: MigrationSource,
    is_directory: bool,
    metadata: _FileMetadata,
) -> dict:
    destination = (
        source.destination / metadata.relative_name
        if is_directory
        else source.destination
    )
    return {
        "kind": source.kind,
        "name": metadata.relative_name,
        "bytes": metadata.size,
        "mtime": metadata.mtime,
        "destination": str(destination),
        "conflict": _destination_exists(destination),
    }


def _destination_exists(destination: Path) -> bool:
    try:
        os.lstat(destination)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _latest_mtime(files: Sequence[dict]) -> float | None:
    return max(
        (file_item["mtime"] for file_item in files), default=None
    )


def _signature_sort_key(payload: dict) -> tuple[str, str, str]:
    return payload["kind"], payload["source"], payload["destination"]


def _digest_json(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
