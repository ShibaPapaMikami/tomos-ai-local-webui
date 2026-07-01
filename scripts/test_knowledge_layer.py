#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge_layer import index_folder, knowledge_status, search_knowledge


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "契約期間は2026年7月1日から2026年12月31日までです。終了日は12月31日です。"
    return path.read_text(encoding="utf-8", errors="replace")


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

print("knowledge layer tests passed")
