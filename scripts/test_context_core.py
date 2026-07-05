#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from context_core import (
    ContextRecord,
    build_context,
    context_db_path,
    forget,
    forget_context_record,
    knowledge_result_to_records,
    list_context_records,
    profile,
    remember,
    save_context_record,
    update_context_record,
)
from knowledge_layer import index_folder, search_knowledge


def extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "docs"
    root.mkdir()
    db_path = Path(tmp) / "index.sqlite"
    (root / "memo.md").write_text(
        "# 議事録\n教材パックの確認は本日中に行います。\n",
        encoding="utf-8",
    )
    index_folder(db_path=db_path, folder_id="folder-1", root_path=root, extract_text=extract_text)

    search_result = search_knowledge(db_path=db_path, folder_id="folder-1", query="教材パック", limit=5)
    records = knowledge_result_to_records(
        search_result,
        scope_type="folder",
        scope_id="folder-1",
        owner_type="user",
        owner_id="local-user",
        project_id="project-a",
    )

    assert records
    first = records[0]
    assert isinstance(first, ContextRecord)
    assert first.scopeType == "folder"
    assert first.scopeId == "folder-1"
    assert first.ownerType == "user"
    assert first.ownerId == "local-user"
    assert first.visibility == "private"
    assert first.projectId == "project-a"
    assert first.sourceType == "knowledge"
    assert first.sourceId == "memo.md"
    assert first.sourcePath == "memo.md"
    assert first.snippet
    assert "教材パック" in first.snippet
    assert first.status == "active"

    inactive = ContextRecord(
        id="inactive",
        text="削除済みの記憶",
        snippet="削除済みの記憶",
        sourceType="memory",
        sourceId="memory-1",
        scopeType="folder",
        scopeId="folder-1",
        ownerType="user",
        ownerId="local-user",
        status="deleted",
    )
    other_scope = ContextRecord(
        id="other",
        text="別フォルダーの記憶",
        snippet="別フォルダーの記憶",
        sourceType="memory",
        sourceId="memory-2",
        scopeType="folder",
        scopeId="folder-2",
        ownerType="user",
        ownerId="local-user",
    )
    expired = ContextRecord(
        id="expired",
        text="期限切れの記憶",
        snippet="期限切れの記憶",
        sourceType="memory",
        sourceId="memory-3",
        scopeType="folder",
        scopeId="folder-1",
        ownerType="user",
        ownerId="local-user",
        expiresAt=1,
    )
    context = build_context(
        records + [inactive, other_scope, expired],
        query="教材パック",
        scope={"scopeType": "folder", "scopeId": "folder-1"},
        limit=3,
    )

    assert context["ok"] is True
    assert len(context["records"]) == 1
    assert context["records"][0]["sourcePath"] == "memo.md"
    assert "削除済み" not in context["text"]
    assert "別フォルダー" not in context["text"]
    assert "期限切れ" not in context["text"]
    assert "memo.md" in context["text"]

    remembered = remember(
        {
            "text": "ユーザーは短い箇条書きを好む",
            "memoryType": "preference",
            "sourceType": "manual",
            "sourceId": "manual-1",
        },
        scope={
            "scopeType": "folder",
            "scopeId": "folder-1",
            "ownerType": "user",
            "ownerId": "local-user",
            "projectId": "project-a",
        },
    )
    assert remembered["ok"] is True
    memory_record = remembered["record"]
    assert memory_record["sourceType"] == "memory"
    assert memory_record["metadata"]["memoryType"] == "preference"
    assert memory_record["scopeId"] == "folder-1"
    assert memory_record["projectId"] == "project-a"

    sensitive = remember(
        {
            "text": "APIキーは sk-123456 です",
            "memoryType": "fact",
            "sourceType": "chat",
            "sourceId": "message-1",
        },
        scope={"scopeType": "folder", "scopeId": "folder-1"},
    )
    assert sensitive["ok"] is False
    assert sensitive["needsReview"] is True
    assert "センシティブ" in sensitive["reason"]

    character_memory = remember(
        {
            "id": "character:character-memory-default:memory-1",
            "text": "ユーザーは短い説明を好む",
            "memoryType": "preference",
            "sourceType": "character",
            "sourceId": "memory-1",
        },
        scope={
            "scopeType": "character",
            "scopeId": "character-memory-default",
            "ownerType": "character",
            "ownerId": "default-character",
        },
    )
    assert character_memory["ok"] is True
    assert character_memory["record"]["id"] == "character:character-memory-default:memory-1"
    assert character_memory["record"]["scopeType"] == "character"
    assert character_memory["record"]["ownerType"] == "character"

    activity = remember(
        {
            "text": "今日は契約書の確認を進めた",
            "memoryType": "activity",
            "sourceType": "chat",
            "sourceId": "message-2",
        },
        scope={"scopeType": "folder", "scopeId": "folder-1"},
    )["record"]
    prof = profile(
        [memory_record, activity],
        scope={"scopeType": "folder", "scopeId": "folder-1"},
    )
    assert prof["ok"] is True
    assert prof["stableFacts"][0]["snippet"] == "ユーザーは短い箇条書きを好む"
    assert prof["recentActivities"][0]["snippet"] == "今日は契約書の確認を進めた"

    forgotten = forget(memory_record, reason="ユーザーが削除")
    assert forgotten["ok"] is True
    assert forgotten["record"]["status"] == "deleted"
    assert forgotten["record"]["metadata"]["deleteReason"] == "ユーザーが削除"
    assert forgotten["record"]["metadata"]["hardDeleteEligible"] is True

    context_db = context_db_path(Path(tmp))
    save_result = save_context_record(context_db, memory_record)
    assert save_result["ok"] is True
    assert context_db.exists()

    other_memory = remember(
        {
            "text": "別フォルダーでは長めの説明を好む",
            "memoryType": "preference",
            "sourceType": "manual",
            "sourceId": "manual-2",
        },
        scope={"scopeType": "folder", "scopeId": "folder-2"},
    )["record"]
    save_context_record(context_db, other_memory)

    saved_records = list_context_records(
        context_db,
        scope={"scopeType": "folder", "scopeId": "folder-1"},
    )
    assert len(saved_records) == 1
    assert saved_records[0].snippet == "ユーザーは短い箇条書きを好む"

    forget_saved = forget_context_record(context_db, saved_records[0].id, reason="不要になった")
    assert forget_saved["ok"] is True
    assert forget_saved["record"]["status"] == "deleted"
    assert forget_saved["record"]["metadata"]["hardDeleteEligible"] is True
    assert list_context_records(context_db, scope={"scopeType": "folder", "scopeId": "folder-1"}) == []
    inactive_records = list_context_records(
        context_db,
        scope={"scopeType": "folder", "scopeId": "folder-1"},
        include_inactive=True,
    )
    assert len(inactive_records) == 1
    assert inactive_records[0].metadata["deleteReason"] == "不要になった"

    save_context_record(context_db, memory_record)
    updated = update_context_record(
        context_db,
        memory_record["id"],
        {
            "text": "ユーザーは短く具体的な箇条書きを好む",
            "memoryType": "preference",
            "sourceType": "manual",
            "sourceId": "manual-1",
        },
    )
    assert updated["ok"] is True
    assert updated["record"]["snippet"] == "ユーザーは短く具体的な箇条書きを好む"
    assert updated["record"]["metadata"]["memoryType"] == "preference"

    rejected_update = update_context_record(
        context_db,
        memory_record["id"],
        {"text": "パスワードは secret です"},
    )
    assert rejected_update["ok"] is False
    assert rejected_update["needsReview"] is True

print("context core tests passed")
