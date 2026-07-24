from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath


PACK_ID = "note-article-writing"
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_EXTRACTED_BYTES = 16 * 1024 * 1024
REQUIRED_MODE_IDS = {
    "rewrite-for-note",
    "continue-series",
    "paste-ready",
    "prepublish-check",
}


def _pack_dir(install_root: Path, pack_id: str = PACK_ID) -> Path:
    return Path(install_root) / pack_id


def _installed_manifest(install_root: Path) -> dict | None:
    path = _pack_dir(install_root) / "pack.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _definition_from_folder(folder: Path, manifest: dict) -> dict:
    modes = []
    for mode in manifest.get("modes", []):
        prompt_file = str(mode.get("promptFile", "")).strip()
        prompt_path = folder / prompt_file
        modes.append({
            "id": str(mode.get("id", "")).strip(),
            "name": str(mode.get("name", "")).strip(),
            "promptFile": prompt_file,
            "prompt": prompt_path.read_text(encoding="utf-8").strip(),
        })
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "version": manifest["version"],
        "description": str(manifest.get("description", "")),
        "visibility": "public",
        "modes": modes,
    }


def _installed_definition(install_root: Path) -> dict | None:
    manifest = _installed_manifest(install_root)
    if not manifest:
        return None
    try:
        _validate_manifest(_pack_dir(install_root), manifest, str(manifest.get("version", "")))
        return _definition_from_folder(_pack_dir(install_root), manifest)
    except (OSError, ValueError):
        return None


def build_catalog(*, install_root: Path, release_url: str, sha256: str, version: str = "0.1.0") -> list[dict]:
    installed = _installed_manifest(install_root)
    installed_version = str(installed.get("version", "")) if installed else ""
    status = "not-installed"
    if installed_version:
        status = "installed" if installed_version == version else "update-available"
    return [{
        "id": PACK_ID,
        "name": "note記事作成サポート",
        "description": "note向けの記事構成、本文整理、公開前確認を支援します。",
        "version": version,
        "installedVersion": installed_version,
        "status": status,
        "releaseUrl": release_url,
        "sha256": sha256,
        "definition": _installed_definition(install_root),
    }]


def download_pack_bytes(
    url: str,
    *,
    allowed_url: str,
    max_bytes: int = MAX_ARCHIVE_BYTES,
    progress_callback=None,
    chunk_size: int = 64 * 1024,
) -> bytes:
    if url != allowed_url or not url.startswith("https://github.com/"):
        raise ValueError("許可されていない配布元です。")
    request = urllib.request.Request(url, headers={"User-Agent": "TOMOS-study-pack-installer"})
    with urllib.request.urlopen(request, timeout=30) as response:
        length = int(response.headers.get("Content-Length", "0") or 0)
        if length > max_bytes:
            raise ValueError("配布ファイルのサイズが上限を超えています。")
        chunks = []
        completed = 0
        while True:
            chunk = response.read(min(chunk_size, max_bytes + 1 - completed))
            if not chunk:
                break
            chunks.append(chunk)
            completed += len(chunk)
            if completed > max_bytes:
                raise ValueError("配布ファイルのサイズが上限を超えています。")
            if progress_callback:
                progress_callback(completed, length)
        data = b"".join(chunks)
    if len(data) > max_bytes:
        raise ValueError("配布ファイルのサイズが上限を超えています。")
    return data


def _safe_archive_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if sum(member.file_size for member in members) > MAX_EXTRACTED_BYTES:
        raise ValueError("ZIPの展開後サイズが上限を超えています。")
    for member in members:
        path = PurePosixPath(member.filename)
        mode = member.external_attr >> 16
        if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode):
            raise ValueError("安全性を確認できないZIPです。")
    return members


def _find_pack_folder(extract_root: Path) -> Path:
    manifests = list(extract_root.glob("*/pack.json"))
    if len(manifests) != 1:
        raise ValueError("pack.jsonを確認できませんでした。")
    return manifests[0].parent


def _validate_manifest(folder: Path, manifest: dict, expected_version: str) -> None:
    if manifest.get("id") != PACK_ID or manifest.get("version") != expected_version:
        raise ValueError("教材パックのIDまたはバージョンが一致しません。")
    if not str(manifest.get("name", "")).strip():
        raise ValueError("教材パック名がありません。")
    modes = manifest.get("modes")
    if not isinstance(modes, list) or {mode.get("id") for mode in modes} != REQUIRED_MODE_IDS:
        raise ValueError("必要な4種類のモードを確認できません。")
    for mode in modes:
        prompt_file = str(mode.get("promptFile", "")).strip()
        prompt_path = (folder / prompt_file).resolve()
        if not prompt_file or not prompt_path.is_relative_to(folder.resolve()) or not prompt_path.is_file():
            raise ValueError("モード本文を確認できません。")
        if not prompt_path.read_text(encoding="utf-8").strip():
            raise ValueError("モード本文が空です。")


def install_pack_bytes(data: bytes, catalog_entry: dict, *, install_root: Path) -> dict:
    expected_hash = str(catalog_entry.get("sha256", "")).lower()
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError("配布ファイルを確認できませんでした。")
    install_root = Path(install_root)
    install_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tomos-study-pack-", dir=install_root.parent) as tmp:
        extract_root = Path(tmp) / "extract"
        extract_root.mkdir()
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                _safe_archive_members(archive)
                archive.extractall(extract_root)
        except zipfile.BadZipFile as exc:
            raise ValueError("配布ファイルを展開できませんでした。") from exc
        source = _find_pack_folder(extract_root)
        try:
            manifest = json.loads((source / "pack.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("pack.jsonを読み取れませんでした。") from exc
        _validate_manifest(source, manifest, str(catalog_entry.get("version", "")))
        staged = install_root / f".{PACK_ID}.new"
        backup = install_root / f".{PACK_ID}.old"
        target = _pack_dir(install_root)
        shutil.rmtree(staged, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        shutil.copytree(source, staged)
        if target.exists():
            target.replace(backup)
        try:
            staged.replace(target)
        except Exception:
            if backup.exists():
                backup.replace(target)
            raise
        shutil.rmtree(backup, ignore_errors=True)
    pack = build_catalog(
        install_root=install_root,
        release_url=str(catalog_entry.get("releaseUrl", "")),
        sha256=expected_hash,
        version=str(catalog_entry.get("version", "")),
    )[0]
    return {"ok": True, "pack": pack, "definition": pack["definition"]}


def install_pack(catalog_entry: dict, *, install_root: Path, progress_callback=None) -> dict:
    data = download_pack_bytes(
        str(catalog_entry.get("releaseUrl", "")),
        allowed_url=str(catalog_entry.get("releaseUrl", "")),
        progress_callback=progress_callback,
    )
    return install_pack_bytes(data, catalog_entry, install_root=install_root)


def remove_pack(pack_id: str, *, install_root: Path) -> dict:
    if pack_id != PACK_ID:
        raise ValueError("削除できない教材パックです。")
    shutil.rmtree(_pack_dir(install_root, pack_id), ignore_errors=True)
    return {"ok": True, "id": pack_id, "status": "not-installed"}
