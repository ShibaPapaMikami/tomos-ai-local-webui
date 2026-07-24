import hashlib
import json
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study_pack_manager
import server


def make_pack_zip(*, pack_id="note-article-writing", version="0.1.0", unsafe_path=None):
    manifest = {
        "id": pack_id,
        "name": "note記事作成サポート",
        "version": version,
        "description": "note向けの記事作成を支援します。",
        "visibility": "public",
        "modes": [
            {"id": "rewrite-for-note", "name": "note向けに整える", "promptFile": "modes/rewrite-for-note.md"},
            {"id": "continue-series", "name": "連載の続きを作る", "promptFile": "modes/continue-series.md"},
            {"id": "paste-ready", "name": "貼り付け用にする", "promptFile": "modes/paste-ready.md"},
            {"id": "prepublish-check", "name": "公開前に確認する", "promptFile": "modes/prepublish-check.md"},
        ],
    }
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        root = "note-article-writing-pack"
        archive.writestr(f"{root}/pack.json", json.dumps(manifest, ensure_ascii=False))
        for mode in manifest["modes"]:
            archive.writestr(f"{root}/{mode['promptFile']}", f"{mode['name']}の指示")
        if unsafe_path:
            archive.writestr(unsafe_path, "unsafe")
    return output.getvalue()


def test_install_and_remove_pack():
    archive = make_pack_zip()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        catalog = study_pack_manager.build_catalog(
            install_root=root,
            release_url="https://github.com/ShibaPapaMikami/tomos-ai-local-webui/releases/download/note-article-writing-v0.1.0/TOMOS-note-article-writing-v0.1.0.zip",
            sha256=hashlib.sha256(archive).hexdigest(),
        )
        assert catalog[0]["status"] == "not-installed"
        result = study_pack_manager.install_pack_bytes(archive, catalog[0], install_root=root)
        assert result["ok"] is True
        assert result["pack"]["status"] == "installed"
        assert len(result["definition"]["modes"]) == 4
        assert (root / "note-article-writing" / "pack.json").is_file()
        removed = study_pack_manager.remove_pack("note-article-writing", install_root=root)
        assert removed["ok"] is True
        assert not (root / "note-article-writing").exists()


def test_install_rejects_wrong_hash():
    archive = make_pack_zip()
    with tempfile.TemporaryDirectory() as tmp:
        catalog = study_pack_manager.build_catalog(
            install_root=Path(tmp),
            release_url="https://github.com/ShibaPapaMikami/tomos-ai-local-webui/releases/download/note-article-writing-v0.1.0/TOMOS-note-article-writing-v0.1.0.zip",
            sha256="0" * 64,
        )
        try:
            study_pack_manager.install_pack_bytes(archive, catalog[0], install_root=Path(tmp))
        except ValueError as exc:
            assert "配布ファイル" in str(exc)
        else:
            raise AssertionError("wrong hash must be rejected")


def test_install_rejects_unsafe_zip_path():
    archive = make_pack_zip(unsafe_path="../outside.txt")
    with tempfile.TemporaryDirectory() as tmp:
        catalog = study_pack_manager.build_catalog(
            install_root=Path(tmp),
            release_url="https://github.com/ShibaPapaMikami/tomos-ai-local-webui/releases/download/note-article-writing-v0.1.0/TOMOS-note-article-writing-v0.1.0.zip",
            sha256=hashlib.sha256(archive).hexdigest(),
        )
        try:
            study_pack_manager.install_pack_bytes(archive, catalog[0], install_root=Path(tmp))
        except ValueError as exc:
            assert "安全" in str(exc)
        else:
            raise AssertionError("unsafe zip path must be rejected")


def test_download_allows_only_configured_github_asset():
    try:
        study_pack_manager.download_pack_bytes(
            "https://example.com/pack.zip",
            allowed_url="https://github.com/ShibaPapaMikami/tomos-ai-local-webui/releases/download/note-article-writing-v0.1.0/TOMOS-note-article-writing-v0.1.0.zip",
        )
    except ValueError as exc:
        assert "配布元" in str(exc)
    else:
        raise AssertionError("untrusted URL must be rejected")


def test_download_reports_streaming_progress():
    archive = b"0123456789"
    response = mock.MagicMock()
    response.headers = {"Content-Length": str(len(archive))}
    response.read.side_effect = [archive[:4], archive[4:8], archive[8:], b""]
    response.__enter__.return_value = response
    progress = []
    with mock.patch("study_pack_manager.urllib.request.urlopen", return_value=response):
        data = study_pack_manager.download_pack_bytes(
            "https://github.com/example/release/pack.zip",
            allowed_url="https://github.com/example/release/pack.zip",
            progress_callback=lambda completed, total: progress.append((completed, total)),
            chunk_size=4,
        )
    assert data == archive
    assert progress == [(4, 10), (8, 10), (10, 10)]


def test_archive_rejects_excessive_expanded_size():
    archive = make_pack_zip()
    previous_limit = study_pack_manager.MAX_EXTRACTED_BYTES
    study_pack_manager.MAX_EXTRACTED_BYTES = 10
    try:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = study_pack_manager.build_catalog(
                install_root=Path(tmp),
                release_url="https://github.com/ShibaPapaMikami/tomos-ai-local-webui/releases/download/note-article-writing-v0.1.0/TOMOS-note-article-writing-v0.1.0.zip",
                sha256=hashlib.sha256(archive).hexdigest(),
            )
            try:
                study_pack_manager.install_pack_bytes(archive, catalog[0], install_root=Path(tmp))
            except ValueError as exc:
                assert "展開後" in str(exc)
            else:
                raise AssertionError("oversized extracted archive must be rejected")
    finally:
        study_pack_manager.MAX_EXTRACTED_BYTES = previous_limit


def test_server_catalog_uses_local_install_state():
    previous_root = server.STUDY_PACK_INSTALL_ROOT
    with tempfile.TemporaryDirectory() as tmp:
        try:
            server.STUDY_PACK_INSTALL_ROOT = Path(tmp)
            payload = server.study_pack_catalog_payload()
        finally:
            server.STUDY_PACK_INSTALL_ROOT = previous_root
    assert payload["ok"] is True
    assert payload["packs"][0]["id"] == "note-article-writing"
    assert payload["packs"][0]["status"] == "not-installed"
    server_source = Path("server.py").read_text(encoding="utf-8")
    assert '"/api/study-packs/catalog"' in server_source
    assert '"/api/downloads/status"' in server_source
    assert '"/api/study-packs/note-article/install"' in server_source
    assert '"/api/study-packs/note-article/remove"' in server_source


def test_server_starts_note_pack_install_as_background_job():
    class FakeThread:
        started = False

        def __init__(self, *, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            FakeThread.started = True

    with server.STUDY_PACK_INSTALL_LOCK:
        server.STUDY_PACK_INSTALL_JOB.clear()
    with mock.patch.object(server, "study_pack_catalog_payload", return_value={
        "packs": [{"sha256": "a" * 64}],
    }), mock.patch.object(server.threading, "Thread", FakeThread):
        payload = server.install_note_article_pack_payload()
    assert payload["ok"] is True
    assert payload["status"] == "running"
    assert FakeThread.started is True
    with server.STUDY_PACK_INSTALL_LOCK:
        assert server.STUDY_PACK_INSTALL_JOB["status"] == "queued"


if __name__ == "__main__":
    test_install_and_remove_pack()
    test_install_rejects_wrong_hash()
    test_install_rejects_unsafe_zip_path()
    test_download_allows_only_configured_github_asset()
    test_download_reports_streaming_progress()
    test_archive_rejects_excessive_expanded_size()
    test_server_catalog_uses_local_install_state()
    test_server_starts_note_pack_install_as_background_job()
    print("study pack manager tests passed")
