#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import sys
import time
import hashlib
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_paths import TomosPaths, ensure_data_directories
from knowledge_layer import index_folder, knowledge_status, search_knowledge


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "契約期間は2026年7月1日から2026年12月31日までです。終了日は12月31日です。"
    return path.read_text(encoding="utf-8", errors="replace")


with tempfile.TemporaryDirectory() as tmp:
    paths = TomosPaths.from_root(Path(tmp) / "app-data")
    expected_status = {
        "ok": True,
        "lastIndexedAt": 0,
        "fileCount": 0,
        "textCount": 0,
        "failedCount": 0,
    }
    assert knowledge_status(db_path=paths.knowledge_db, folder_id="folder-1") == expected_status
    assert search_knowledge(
        db_path=paths.knowledge_db,
        folder_id="folder-1",
        query="契約",
    ) == {"ok": True, "query": "契約", "results": []}
    assert not paths.root.exists()
    ensure_data_directories(paths)
    assert knowledge_status(db_path=paths.knowledge_db, folder_id="folder-1") == expected_status
    assert search_knowledge(
        db_path=paths.knowledge_db,
        folder_id="folder-1",
        query="契約",
    ) == {"ok": True, "query": "契約", "results": []}
    assert not paths.knowledge_db.exists()
    docs = Path(tmp) / "docs"
    docs.mkdir()
    (docs / "memo.md").write_text("# 契約\n確認事項です。\n", encoding="utf-8")
    index_folder(db_path=paths.knowledge_db, folder_id="folder-1", root_path=docs, extract_text=extract_text)
    before_read = hashlib.sha256(paths.knowledge_db.read_bytes()).hexdigest()
    assert knowledge_status(db_path=paths.knowledge_db, folder_id="folder-1")["fileCount"] == 1
    assert search_knowledge(db_path=paths.knowledge_db, folder_id="folder-1", query="契約")["results"]
    assert hashlib.sha256(paths.knowledge_db.read_bytes()).hexdigest() == before_read


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "docs"
    root.mkdir()
    db_path = Path(tmp) / "index.sqlite"
    (root / "memo.md").write_text("# 議事録\n次回の確認事項は教材パックです。\n", encoding="utf-8")
    (root / "contract.pdf").write_bytes(b"%PDF-1.4 fake")
    (root / "skip.csv").write_text("name,value\n", encoding="utf-8")

    first = index_folder(db_path=db_path, folder_id="folder-1", root_path=root, extract_text=extract_text)
    assert first["ok"] is True
    assert first["indexed"] == 2
    assert first["skipped"] == 0
    assert first["failed"] == 0
    assert first["fileCount"] == 2
    assert first["textCount"] == 2

    second = index_folder(db_path=db_path, folder_id="folder-1", root_path=root, extract_text=extract_text)
    assert second["indexed"] == 0
    assert second["skipped"] == 2

    result = search_knowledge(db_path=db_path, folder_id="folder-1", query="契約終了日", limit=5)
    assert result["ok"] is True
    assert result["results"]
    assert result["results"][0]["path"] == "contract.pdf"
    assert "12月31日" in result["results"][0]["snippet"]

    (root / "memo.md").write_text("# 議事録\n次回の確認事項はKnowledge Layerです。\n", encoding="utf-8")
    next_time = time.time() + 3
    (root / "memo.md").touch()
    import os
    os.utime(root / "memo.md", (next_time, next_time))
    third = index_folder(db_path=db_path, folder_id="folder-1", root_path=root, extract_text=extract_text)
    assert third["indexed"] == 1
    assert third["skipped"] == 1

    (root / "contract.pdf").unlink()
    fourth = index_folder(db_path=db_path, folder_id="folder-1", root_path=root, extract_text=extract_text)
    assert fourth["deleted"] == 1
    status = knowledge_status(db_path=db_path, folder_id="folder-1")
    assert status["fileCount"] == 1


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "docs"
    root.mkdir()
    db_path = Path(tmp) / "index.sqlite"
    (root / "memo.md").write_text(
        "# WAL\n最新コミットの確認です。\n",
        encoding="utf-8",
    )
    index_folder(
        db_path=db_path,
        folder_id="folder-wal",
        root_path=root,
        extract_text=extract_text,
    )
    writer = sqlite3.connect(db_path)
    try:
        assert writer.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute(
            "UPDATE knowledge_files SET status = 'deleted' WHERE folder_id = ?",
            ("folder-wal",),
        )
        writer.commit()
        assert Path(f"{db_path}-wal").is_file()
        assert knowledge_status(
            db_path=db_path,
            folder_id="folder-wal",
        )["fileCount"] == 0
    finally:
        writer.close()


print("knowledge layer tests passed")
