from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import context_core
from packages import local_context_core


assert context_core.ContextRecord is local_context_core.ContextRecord
assert context_core.remember is local_context_core.remember
assert context_core.profile is local_context_core.profile

with tempfile.TemporaryDirectory() as tmp:
    db_path = Path(tmp) / "context.sqlite"
    scope = {
        "scopeType": "character",
        "scopeId": "character-memory-default",
        "ownerType": "character",
        "ownerId": "default-character",
    }
    result = local_context_core.remember(
        {
            "id": "character:character-memory-default:memory-1",
            "text": "ユーザーは短い説明を好む",
            "memoryType": "preference",
            "sourceType": "character",
            "sourceId": "memory-1",
            "sensitivity": "normal",
        },
        scope=scope,
    )
    assert result["ok"] is True
    local_context_core.save_context_record(db_path, result["record"])
    records = local_context_core.list_context_records(db_path, scope=scope)
    assert len(records) == 1
    assert records[0].metadata["sensitivity"] == "normal"

    protected = local_context_core.remember(
        {
            "id": "character:character-memory-default:protected-1",
            "text": "APIキーは sk-test",
            "memoryType": "fact",
            "sourceType": "character",
            "sourceId": "protected-1",
            "sensitivity": "protected",
        },
        scope=scope,
    )
    assert protected["ok"] is True
    local_context_core.save_context_record(db_path, protected["record"])
    updated = local_context_core.update_context_record(
        db_path,
        "character:character-memory-default:protected-1",
        {"text": "APIキーは sk-updated", "sensitivity": "protected"},
    )
    assert updated["ok"] is True
    assert updated["record"]["metadata"]["sensitivity"] == "protected"

print("local context core package tests passed")
