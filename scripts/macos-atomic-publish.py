#!/usr/bin/env python3
"""Publish a signed app through pinned Darwin directory descriptors."""
from __future__ import annotations

import argparse
import ctypes
import errno
import os
import secrets
import stat
import sys
from pathlib import Path


RENAME_EXCL = 0x00000004
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def fail(message: str) -> None:
    raise SystemExit(f"atomic publishを停止しました: {message}")


def open_directory(name: str, parent_fd: int) -> int:
    try:
        return os.open(name, DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        fail(f"directoryを安全に開けません: {name}: {exc.strerror}")


def same_directory(path: Path, descriptor: int) -> bool:
    try:
        path_stat = path.lstat()
    except OSError:
        return False
    descriptor_stat = os.fstat(descriptor)
    return (
        stat.S_ISDIR(path_stat.st_mode)
        and not stat.S_ISLNK(path_stat.st_mode)
        and (path_stat.st_dev, path_stat.st_ino) == (descriptor_stat.st_dev, descriptor_stat.st_ino)
    )


def same_descriptor(first: int, second: int) -> bool:
    first_stat = os.fstat(first)
    second_stat = os.fstat(second)
    return (first_stat.st_dev, first_stat.st_ino) == (second_stat.st_dev, second_stat.st_ino)


def require_leaf_directory(name: str, parent_fd: int, label: str) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        fail(f"{label}がありません: {exc.strerror}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        fail(f"{label}がdirectoryではありません")


def require_leaf_regular_file(name: str, parent_fd: int, label: str) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        fail(f"{label}がありません: {exc.strerror}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        fail(f"{label}が通常fileではありません")


def require_test_root(root: Path) -> None:
    marker = root / ".tomos-sign-test-root"
    try:
        root_stat = root.lstat()
        marker_stat = marker.lstat()
    except OSError as exc:
        fail(f"test rootを読めません: {exc.strerror}")
    if (
        root.parent != Path("/private/tmp")
        or not root.name.startswith("tomos-sign-test-")
        or stat.S_ISLNK(root_stat.st_mode)
        or not stat.S_ISDIR(root_stat.st_mode)
        or root_stat.st_uid != os.geteuid()
        or stat.S_IMODE(root_stat.st_mode) != 0o700
        or stat.S_ISLNK(marker_stat.st_mode)
        or not stat.S_ISREG(marker_stat.st_mode)
        or marker_stat.st_uid != os.geteuid()
        or stat.S_IMODE(marker_stat.st_mode) != 0o600
    ):
        fail("test hookは専用temporary rootでのみ使用できます")


def rename_exclusive_result(
    source_fd: int, source_name: str, destination_fd: int, destination_name: str
) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameatx_np = libc.renameatx_np
    except AttributeError:
        fail("renameatx_npが利用できません")
    renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameatx_np.restype = ctypes.c_int
    result = renameatx_np(
        source_fd, source_name.encode(), destination_fd, destination_name.encode(), RENAME_EXCL
    )
    return 0 if result == 0 else ctypes.get_errno()


def rename_exclusive(source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
    error = rename_exclusive_result(source_fd, source_name, destination_fd, destination_name)
    if error == 0:
        return
    if error == errno.EEXIST:
        fail("signed distribution は上書きしません")
    fail(f"renameatx_npに失敗しました: {os.strerror(error)}")


def quarantine_unverified_signed(dist_fd: int) -> None:
    for _ in range(16):
        quarantine_name = f".tomos-rejected-{secrets.token_hex(16)}"
        error = rename_exclusive_result(dist_fd, "signed", dist_fd, quarantine_name)
        if error == 0 or error == errno.ENOENT:
            return
        if error != errno.EEXIST:
            fail(f"unverified signed distributionを隔離できません: {os.strerror(error)}")
    fail("unverified signed distributionの隔離先を確保できません")


def replace_signed_before_open_for_test(root: Path, root_fd: int, dist_fd: int, app_name: str) -> None:
    require_test_root(root)
    replacement = root / "replacement-signed-parent"
    (replacement / app_name).mkdir(parents=True, mode=0o700)
    (replacement / "build-manifest.json").write_text("{}\n", encoding="utf-8")
    os.rename("signed", "signed-before-replacement", src_dir_fd=dist_fd, dst_dir_fd=dist_fd)
    os.rename("replacement-signed-parent", "signed", src_dir_fd=root_fd, dst_dir_fd=dist_fd)


def publish(
    root: Path,
    stage_name: str,
    payload_name: str,
    app_name: str,
    replace_signed_parent: bool,
    replace_signed_before_open: bool,
) -> None:
    if Path(stage_name).name != stage_name or not stage_name.startswith(".tomos-signing."):
        fail("private staging directoryが不正です")
    if Path(app_name).name != app_name or app_name != "TOMOS AI.app":
        fail("publish app名が不正です")
    if Path(payload_name).name != payload_name or payload_name != "payload":
        fail("publish payload名が不正です")

    root_fd = os.open(root, DIRECTORY_FLAGS)
    dist_fd = signed_fd = stage_fd = payload_fd = -1
    try:
        dist_fd = open_directory("dist", root_fd)
        stage_fd = open_directory(stage_name, root_fd)
        require_leaf_directory(payload_name, stage_fd, "publish payload")
        payload_fd = open_directory(payload_name, stage_fd)
        require_leaf_directory(app_name, payload_fd, "publish app")
        require_leaf_regular_file("build-manifest.json", payload_fd, "publish build manifest")
        rename_exclusive(stage_fd, payload_name, dist_fd, "signed")
        if replace_signed_before_open:
            replace_signed_before_open_for_test(root, root_fd, dist_fd, app_name)
        try:
            signed_fd = os.open("signed", DIRECTORY_FLAGS, dir_fd=dist_fd)
        except OSError as exc:
            quarantine_unverified_signed(dist_fd)
            fail(f"published signed directoryを安全に開けません: {exc.strerror}")
        signed_path = root / "dist" / "signed"
        if not same_descriptor(payload_fd, signed_fd):
            quarantine_unverified_signed(dist_fd)
            fail("published payload directoryが差し替えられました")
        if not same_directory(signed_path, signed_fd):
            quarantine_unverified_signed(dist_fd)
            fail("signed parent directoryが差し替えられました")
        require_leaf_directory(app_name, signed_fd, "published signed app")
        require_leaf_regular_file("build-manifest.json", signed_fd, "published signed build manifest")
        if replace_signed_parent:
            require_test_root(root)
            replacement = root / "replacement-signed-parent"
            replacement.mkdir(mode=0o700)
            os.rename("signed", "signed-before-replacement", src_dir_fd=dist_fd, dst_dir_fd=dist_fd)
            os.symlink(replacement, "signed", dir_fd=dist_fd)
            if not same_directory(signed_path, signed_fd):
                quarantine_unverified_signed(dist_fd)
                fail("signed parent directoryが差し替えられました")
    finally:
        for descriptor in (payload_fd, stage_fd, signed_fd, dist_fd, root_fd):
            if descriptor >= 0:
                os.close(descriptor)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--stage-name", required=True)
    parser.add_argument("--payload-name", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--test-replace-signed-parent", action="store_true")
    parser.add_argument("--test-replace-signed-before-open", action="store_true")
    arguments = parser.parse_args()
    root = Path(arguments.root)
    try:
        metadata = root.lstat()
    except OSError as exc:
        fail(f"repository rootを読めません: {exc.strerror}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        fail("repository rootがdirectoryではありません")
    publish(
        root,
        arguments.stage_name,
        arguments.payload_name,
        arguments.app_name,
        arguments.test_replace_signed_parent,
        arguments.test_replace_signed_before_open,
    )


if __name__ == "__main__":
    main()
