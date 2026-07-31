from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
from typing import BinaryIO


@dataclass(frozen=True)
class RuntimeArtifact:
    name: str
    url: str
    sha256: str
    size: int


ARTIFACT = RuntimeArtifact(
    name="cpython-3.11.15+20260718-aarch64-apple-darwin-install_only.tar.gz",
    url=(
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        "20260718/cpython-3.11.15%2B20260718-aarch64-apple-darwin-install_only.tar.gz"
    ),
    sha256="125587d03495bebdf30ec9e549a8469c97c0925d863ff401f24f157fd44d91d6",
    size=27241978,
)


ALLOWED_SYMLINKS = {
    "python/bin/2to3": "2to3-3.11",
    "python/bin/idle3": "idle3.11",
    "python/bin/pydoc3": "pydoc3.11",
    "python/bin/python": "python3.11",
    "python/bin/python3": "python3.11",
    "python/bin/python3-config": "python3.11-config",
    "python/lib/pkgconfig/python3-embed.pc": "python-3.11-embed.pc",
    "python/lib/pkgconfig/python3.pc": "python-3.11.pc",
    "python/share/man/man1/python3.1": "python3.11.1",
}


def verify_artifact(path: Path, artifact: RuntimeArtifact) -> None:
    if not path.is_file():
        raise ValueError(f"artifactが見つかりません: {path}")
    with path.open("rb") as source:
        verify_artifact_file(source, artifact)


def verify_artifact_file(source: BinaryIO, artifact: RuntimeArtifact) -> None:
    if os.fstat(source.fileno()).st_size != artifact.size:
        raise ValueError("artifactのサイズが固定値と一致しません")
    source.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
    if digest.hexdigest() != artifact.sha256:
        raise ValueError("SHA-256が固定値と一致しません")
    source.seek(0)


def _validated_member_path(member: tarfile.TarInfo) -> PurePosixPath:
    name = PurePosixPath(member.name)
    if (
        name.is_absolute()
        or ".." in name.parts
        or member.islnk()
        or not (member.isdir() or member.isfile() or member.issym())
    ):
        raise ValueError(f"安全でないtar memberを拒否しました: {member.name}")
    if not name.parts or name.parts[0] != "python":
        raise ValueError(f"安全でないruntime layoutを拒否しました: {member.name}")
    if member.issym():
        target = PurePosixPath(member.linkname)
        resolved_target = name.parent / target
        if (
            target.is_absolute()
            or ".." in target.parts
            or ALLOWED_SYMLINKS.get(member.name) != member.linkname
            or not resolved_target.parts
            or resolved_target.parts[0] != "python"
            or ".." in resolved_target.parts
        ):
            raise ValueError(f"安全でないtar symlinkを拒否しました: {member.name}")
    return name


def _ensure_runtime_directory(path: Path, staging_root: Path) -> None:
    """Create runtime directories with deterministic modes, independent of umask."""
    try:
        relative = path.relative_to(staging_root)
    except ValueError as exc:
        raise ValueError("runtime directoryがstaging外です") from exc
    current = staging_root
    for part in relative.parts:
        current /= part
        try:
            current.mkdir()
        except FileExistsError:
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("runtime directory pathが不正です")
        else:
            os.chmod(current, 0o755)


def stage_runtime(archive: BinaryIO, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        archive.seek(0)
        with tarfile.open(fileobj=archive, mode="r:gz") as tar:
            members = tar.getmembers()
            paths = [_validated_member_path(member) for member in members]
            for member, member_path in zip(members, paths):
                relative_path = Path(*member_path.parts[1:])
                if not relative_path.parts:
                    continue
                target = staging_root / relative_path
                if member.isdir():
                    _ensure_runtime_directory(target, staging_root)
                    os.chmod(target, member.mode & 0o777)
                    continue
                if member.issym():
                    _ensure_runtime_directory(target.parent, staging_root)
                    os.symlink(member.linkname, target)
                    continue
                _ensure_runtime_directory(target.parent, staging_root)
                source = tar.extractfile(member)
                if source is None:
                    raise ValueError(f"tar memberを読み込めません: {member.name}")
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                os.chmod(target, member.mode & 0o777)

        python = staging_root / "bin/python3"
        license_file = staging_root / "lib/python3.11/LICENSE.txt"
        if not python.is_file() or not os.access(python, os.X_OK):
            raise ValueError("展開したruntimeにpython/bin/python3がありません")
        if not license_file.is_file():
            raise ValueError("展開したruntimeにPython LICENSEがありません")
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return staging_root


def publish_runtime(staging_root: Path, destination: Path) -> Path:
    if destination.exists():
        raise ValueError(f"展開先が既に存在します: {destination}")
    os.replace(staging_root, destination)
    return destination


def runtime_tree_entries(root: Path) -> dict[str, tuple[str, int, str]]:
    """Return the exact, stream-hashed runtime tree without following links."""
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise ValueError("Python runtime rootがありません") from exc
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        raise ValueError("Python runtime rootが不正です")

    entries: dict[str, tuple[str, int, str]] = {}

    def digest_file(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise ValueError("Python runtime fileを読み取れません") from exc
        return digest.hexdigest()

    def visit(directory: Path, relative: Path) -> None:
        try:
            with os.scandir(directory) as children:
                items = list(children)
        except OSError as exc:
            raise ValueError("Python runtime directoryを読み取れません") from exc
        for child in items:
            path = Path(child.path)
            child_relative = relative / child.name
            try:
                metadata = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValueError("Python runtime entryを読み取れません") from exc
            mode = stat.S_IMODE(metadata.st_mode)
            key = child_relative.as_posix()
            if stat.S_ISLNK(metadata.st_mode):
                try:
                    entries[key] = ("symlink", 0, os.readlink(path))
                except OSError as exc:
                    raise ValueError("Python runtime symlinkを読み取れません") from exc
            elif stat.S_ISDIR(metadata.st_mode):
                entries[key] = ("directory", mode, "")
                visit(path, child_relative)
            elif stat.S_ISREG(metadata.st_mode):
                entries[key] = ("file", mode, digest_file(path))
            else:
                raise ValueError("Python runtimeに通常file以外があります")

    visit(root, Path())
    return entries


def normalized_runtime_tree_entries(
    root: Path,
    entries: dict[str, tuple[str, int, str]],
    approved_symlinks: dict[str, str],
) -> dict[str, tuple[str, int, str]]:
    """Normalize only expected symlinks to their materialized file entries."""
    normalized = entries.copy()
    resolved_root = root.resolve(strict=True)
    for name, target in approved_symlinks.items():
        if normalized.get(name) != ("symlink", 0, target):
            continue
        try:
            target_path = (root / name).parent.joinpath(target).resolve(strict=True)
            target_path.relative_to(resolved_root)
            target_stat = target_path.stat()
        except (OSError, ValueError) as exc:
            raise ValueError("Python runtime symlink targetが不正です") from exc
        if not stat.S_ISREG(target_stat.st_mode):
            raise ValueError("Python runtime symlink targetがfileではありません")
        digest = hashlib.sha256()
        try:
            with target_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise ValueError("Python runtime symlink targetを読み取れません") from exc
        normalized[name] = ("file", stat.S_IMODE(target_stat.st_mode), digest.hexdigest())
    return normalized


def extract_runtime(archive: Path, destination: Path) -> Path:
    with archive.open("rb") as source:
        staging_root = stage_runtime(source, destination)
    try:
        return publish_runtime(staging_root, destination)
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
