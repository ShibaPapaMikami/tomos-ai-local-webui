from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import BinaryIO, Callable, Iterator
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener

from macos_python_runtime import (
    ARTIFACT,
    publish_runtime,
    stage_runtime,
    verify_artifact_file,
)


ALLOWED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


def _require_allowed_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"許可されていないdownload hostです: {parsed.hostname}")


class AllowedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _require_allowed_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_into(response, target: BinaryIO) -> None:
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, ARTIFACT.size + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > ARTIFACT.size:
            raise ValueError("downloadが固定サイズを超えました")
        target.write(chunk)
    if total != ARTIFACT.size:
        raise ValueError("downloadのサイズが固定値と一致しません")


@contextmanager
def open_verified_artifact(cache_directory: Path) -> Iterator[BinaryIO]:
    cache_directory.mkdir(parents=True, exist_ok=True)
    archive = cache_directory / ARTIFACT.name
    if archive.exists():
        with archive.open("rb") as source:
            verify_artifact_file(source, ARTIFACT)
            yield source
        return

    _require_allowed_host(ARTIFACT.url)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{ARTIFACT.name}.", dir=cache_directory
    )
    temporary = Path(temporary_name)
    try:
        opener = build_opener(AllowedRedirectHandler())
        with os.fdopen(descriptor, "w+b") as output, opener.open(ARTIFACT.url) as response:
            _require_allowed_host(response.geturl())
            _download_into(response, output)
            output.flush()
            os.fsync(output.fileno())
            verify_artifact_file(output, ARTIFACT)
            temporary.replace(archive)
            yield output
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def verify_runtime_cpu_and_version(python: Path) -> str:
    cpu = subprocess.run(
        ["file", "-b", str(python)], check=True, text=True, capture_output=True
    ).stdout.strip()
    if "arm64" not in cpu.lower():
        raise ValueError(f"runtimeのCPU architectureがarm64ではありません: {cpu}")
    version = subprocess.run(
        [str(python), "--version"], check=True, text=True, capture_output=True
    ).stdout.strip()
    if not version.startswith("Python 3.11."):
        raise ValueError(f"runtimeのPython versionが3.11ではありません: {version}")
    print(f"SHA-256: {ARTIFACT.sha256}")
    print(f"Mach-O: {cpu}")
    print(version)
    return version


def install_verified_runtime(
    archive: BinaryIO,
    destination: Path,
    runtime_verifier: Callable[[Path], str] = verify_runtime_cpu_and_version,
) -> Path:
    staging_root = stage_runtime(archive, destination)
    try:
        runtime_verifier(staging_root / "bin/python3")
        return publish_runtime(staging_root, destination)
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _require_real_directory(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label}が見つかりません: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} symlinkは許可されません: {path}")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label}はdirectoryではありません: {path}")


def replace_with_verified_runtime(
    archive: BinaryIO,
    destination: Path,
    runtime_verifier: Callable[[Path], str] = verify_runtime_cpu_and_version,
) -> Path:
    """Atomically replace an existing runtime with a freshly verified extraction.

    The archive descriptor has already been hash-verified by
    ``open_verified_artifact``.  Staging beside the destination and replacing it
    only after CPU/version checks prevents a previously ignored runtime tree from
    becoming the Tauri resource source.
    """
    destination = Path(destination)
    _require_real_directory(destination.parent, "runtime parent")
    try:
        destination_stat = destination.lstat()
    except FileNotFoundError:
        return install_verified_runtime(archive, destination, runtime_verifier)
    if stat.S_ISLNK(destination_stat.st_mode):
        raise ValueError(f"runtime destination symlinkは許可されません: {destination}")
    if not stat.S_ISDIR(destination_stat.st_mode):
        raise ValueError(f"runtime destinationはdirectoryではありません: {destination}")

    staging_root = stage_runtime(archive, destination)
    backup_root: Path | None = None
    try:
        runtime_verifier(staging_root / "bin/python3")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.backup.", dir=destination.parent
        )
        os.close(descriptor)
        backup_root = Path(temporary_name)
        backup_root.unlink()
        os.replace(destination, backup_root)
        try:
            os.replace(staging_root, destination)
        except Exception:
            os.replace(backup_root, destination)
            raise
        shutil.rmtree(backup_root)
        return destination
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="固定macOS Python runtimeを取得・検証します")
    parser.add_argument("--archive-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="既存runtimeを固定artifactからfresh extractionへatomicに置き換える。",
    )
    args = parser.parse_args()

    with open_verified_artifact(args.archive_cache) as archive:
        if args.replace_existing:
            replace_with_verified_runtime(archive, args.output)
        else:
            install_verified_runtime(archive, args.output)


if __name__ == "__main__":
    main()
