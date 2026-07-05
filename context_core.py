from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


ACTIVE_STATUS = {"active"}
MEMORY_TYPES = {"fact", "preference", "activity", "temporary"}
SENSITIVE_PATTERNS = (
    "apiキー",
    "api key",
    "password",
    "パスワード",
    "secret",
    "sk-",
)


def now_ms() -> int:
    return int(time.time() * 1000)


def stable_record_id(*parts: object) -> str:
    source = "\n".join(str(part or "") for part in parts)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]


def context_db_path(root: Path) -> Path:
    return root / ".gemma4-data" / "context" / "context.sqlite"


@dataclass
class ContextRecord:
    id: str
    text: str
    snippet: str
    sourceType: str
    sourceId: str
    scopeType: str
    scopeId: str
    ownerType: str = "user"
    ownerId: str = "local"
    visibility: str = "private"
    projectId: str = ""
    sourcePath: str = ""
    page: int | None = None
    heading: str = ""
    score: float = 0.0
    confidence: float = 1.0
    status: str = "active"
    expiresAt: int | None = None
    createdAt: int = field(default_factory=now_ms)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_scope(scope: dict[str, object] | None) -> dict[str, str]:
    scope = scope if isinstance(scope, dict) else {}
    return {
        "scopeType": str(scope.get("scopeType") or "").strip(),
        "scopeId": str(scope.get("scopeId") or "").strip(),
    }


def record_is_active(record: ContextRecord, *, current_time_ms: int | None = None) -> bool:
    if record.status not in ACTIVE_STATUS:
        return False
    if record.expiresAt is not None and record.expiresAt <= (current_time_ms or now_ms()):
        return False
    return True


def record_matches_scope(record: ContextRecord, scope: dict[str, object] | None) -> bool:
    normalized = normalize_scope(scope)
    scope_type = normalized["scopeType"]
    scope_id = normalized["scopeId"]
    if scope_type and record.scopeType != scope_type:
        return False
    if scope_id and record.scopeId != scope_id:
        return False
    return True


def scope_value(scope: dict[str, object] | None, key: str, default: str = "") -> str:
    scope = scope if isinstance(scope, dict) else {}
    return str(scope.get(key) or default).strip()


def contains_sensitive_text(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(pattern in lowered for pattern in SENSITIVE_PATTERNS)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    ensure_schema(connection)
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS context_records (
          id TEXT PRIMARY KEY,
          text TEXT NOT NULL,
          snippet TEXT NOT NULL,
          source_type TEXT NOT NULL,
          source_id TEXT NOT NULL,
          scope_type TEXT NOT NULL,
          scope_id TEXT NOT NULL,
          owner_type TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          visibility TEXT NOT NULL,
          project_id TEXT DEFAULT '',
          source_path TEXT DEFAULT '',
          page INTEGER,
          heading TEXT DEFAULT '',
          score REAL DEFAULT 0,
          confidence REAL DEFAULT 1,
          status TEXT NOT NULL,
          expires_at INTEGER,
          created_at INTEGER NOT NULL,
          metadata_json TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_context_records_scope ON context_records(scope_type, scope_id, status);
        CREATE INDEX IF NOT EXISTS idx_context_records_owner ON context_records(owner_type, owner_id);
        CREATE INDEX IF NOT EXISTS idx_context_records_source ON context_records(source_type, source_id);
        """
    )
    connection.commit()


def record_from_dict(value: dict[str, object]) -> ContextRecord:
    return ContextRecord(**value)


def row_to_record(row: sqlite3.Row) -> ContextRecord:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return ContextRecord(
        id=row["id"],
        text=row["text"],
        snippet=row["snippet"],
        sourceType=row["source_type"],
        sourceId=row["source_id"],
        scopeType=row["scope_type"],
        scopeId=row["scope_id"],
        ownerType=row["owner_type"],
        ownerId=row["owner_id"],
        visibility=row["visibility"],
        projectId=row["project_id"] or "",
        sourcePath=row["source_path"] or "",
        page=row["page"],
        heading=row["heading"] or "",
        score=float(row["score"] or 0),
        confidence=float(row["confidence"] or 1),
        status=row["status"],
        expiresAt=row["expires_at"],
        createdAt=row["created_at"],
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def record_values(record: dict[str, object] | ContextRecord) -> dict[str, object]:
    target = record if isinstance(record, ContextRecord) else record_from_dict(record)
    return {
        "id": target.id,
        "text": target.text,
        "snippet": target.snippet,
        "source_type": target.sourceType,
        "source_id": target.sourceId,
        "scope_type": target.scopeType,
        "scope_id": target.scopeId,
        "owner_type": target.ownerType,
        "owner_id": target.ownerId,
        "visibility": target.visibility,
        "project_id": target.projectId,
        "source_path": target.sourcePath,
        "page": target.page,
        "heading": target.heading,
        "score": target.score,
        "confidence": target.confidence,
        "status": target.status,
        "expires_at": target.expiresAt,
        "created_at": target.createdAt,
        "metadata_json": json.dumps(target.metadata or {}, ensure_ascii=False, sort_keys=True),
    }


def knowledge_result_to_records(
    search_result: dict[str, object],
    *,
    scope_type: str,
    scope_id: str,
    owner_type: str = "user",
    owner_id: str = "local",
    visibility: str = "private",
    project_id: str = "",
) -> list[ContextRecord]:
    rows = search_result.get("results") if isinstance(search_result, dict) else []
    if not isinstance(rows, list):
        return []
    records: list[ContextRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_path = str(row.get("path") or row.get("sourcePath") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        if not source_path or not snippet:
            continue
        page = row.get("page")
        page_value = int(page) if isinstance(page, int) else None
        source_type = str(row.get("sourceType") or "knowledge").strip() or "knowledge"
        record_id = stable_record_id(scope_type, scope_id, source_type, source_path, page_value, snippet)
        records.append(
            ContextRecord(
                id=record_id,
                text=snippet,
                snippet=snippet,
                sourceType=source_type,
                sourceId=source_path,
                sourcePath=source_path,
                page=page_value,
                heading=str(row.get("heading") or ""),
                score=float(row.get("score") or 0.0),
                confidence=float(row.get("confidence") or 1.0),
                scopeType=str(scope_type),
                scopeId=str(scope_id),
                ownerType=str(owner_type),
                ownerId=str(owner_id),
                visibility=str(visibility or "private"),
                projectId=str(project_id or ""),
                metadata={"query": search_result.get("query", "")},
            )
        )
    return records


def build_context(
    records: list[ContextRecord],
    *,
    query: str = "",
    scope: dict[str, object] | None = None,
    limit: int = 5,
) -> dict[str, object]:
    limit = max(1, min(int(limit or 5), 20))
    active = [
        record
        for record in records
        if isinstance(record, ContextRecord)
        and record_is_active(record)
        and record_matches_scope(record, scope)
    ]
    active.sort(key=lambda item: item.score, reverse=True)
    selected = active[:limit]
    lines = [
        "以下はローカル資料から取得した文脈です。原文根拠がある範囲だけで回答してください。",
        f"検索語: {query}" if query else "",
    ]
    for record in selected:
        page = f" p.{record.page}" if record.page else ""
        heading = f" [{record.heading}]" if record.heading else ""
        lines.append(f"- {record.sourcePath or record.sourceId}{page}{heading}: {record.snippet}")
    return {
        "ok": True,
        "query": query,
        "records": [record.to_dict() for record in selected],
        "text": "\n".join(line for line in lines if line),
    }


def remember(item: dict[str, object], *, scope: dict[str, object] | None = None) -> dict[str, object]:
    text = str(item.get("text") or "").strip() if isinstance(item, dict) else ""
    if not text:
        return {"ok": False, "error": "記憶する内容がありません。"}
    if contains_sensitive_text(text):
        return {
            "ok": False,
            "needsReview": True,
            "reason": "センシティブ情報の可能性があるため自動保存しません。",
        }
    memory_type = str(item.get("memoryType") or "fact").strip() if isinstance(item, dict) else "fact"
    if memory_type not in MEMORY_TYPES:
        memory_type = "fact"
    source_type = str(item.get("sourceType") or "manual").strip()
    source_id = str(item.get("sourceId") or source_type).strip()
    expires_at = item.get("expiresAt") if isinstance(item, dict) else None
    expires_at_value = int(expires_at) if isinstance(expires_at, int) else None
    scope_type = scope_value(scope, "scopeType", "user")
    scope_id = scope_value(scope, "scopeId", "local")
    owner_type = scope_value(scope, "ownerType", "user")
    owner_id = scope_value(scope, "ownerId", "local")
    project_id = scope_value(scope, "projectId", "")
    record = ContextRecord(
        id=stable_record_id("memory", scope_type, scope_id, owner_type, owner_id, memory_type, source_type, source_id, text),
        text=text,
        snippet=text,
        sourceType="memory",
        sourceId=source_id,
        scopeType=scope_type,
        scopeId=scope_id,
        ownerType=owner_type,
        ownerId=owner_id,
        projectId=project_id,
        expiresAt=expires_at_value,
        metadata={
            "memoryType": memory_type,
            "sourceType": source_type,
            "sourceId": source_id,
        },
    )
    return {"ok": True, "record": record.to_dict()}


def profile(records: list[dict[str, object] | ContextRecord], *, scope: dict[str, object] | None = None) -> dict[str, object]:
    normalized: list[ContextRecord] = []
    for record in records:
        if isinstance(record, ContextRecord):
            normalized.append(record)
        elif isinstance(record, dict):
            try:
                normalized.append(ContextRecord(**record))
            except TypeError:
                continue
    visible = [
        record
        for record in normalized
        if record.sourceType == "memory"
        and record_is_active(record)
        and record_matches_scope(record, scope)
    ]
    stable: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    for record in sorted(visible, key=lambda item: item.createdAt, reverse=True):
        memory_type = str(record.metadata.get("memoryType") or "fact")
        if memory_type == "activity":
            recent.append(record.to_dict())
        elif memory_type in {"fact", "preference"}:
            stable.append(record.to_dict())
    return {
        "ok": True,
        "stableFacts": stable,
        "recentActivities": recent,
    }


def forget(record: dict[str, object] | ContextRecord, *, reason: str = "") -> dict[str, object]:
    target = record if isinstance(record, ContextRecord) else ContextRecord(**record)
    metadata = dict(target.metadata or {})
    metadata["deleteReason"] = str(reason or "")
    metadata["hardDeleteEligible"] = True
    target.status = "deleted"
    target.metadata = metadata
    return {"ok": True, "record": target.to_dict()}


def save_context_record(db_path: Path, record: dict[str, object] | ContextRecord) -> dict[str, object]:
    values = record_values(record)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO context_records (
              id, text, snippet, source_type, source_id, scope_type, scope_id,
              owner_type, owner_id, visibility, project_id, source_path, page,
              heading, score, confidence, status, expires_at, created_at, metadata_json
            )
            VALUES (
              :id, :text, :snippet, :source_type, :source_id, :scope_type, :scope_id,
              :owner_type, :owner_id, :visibility, :project_id, :source_path, :page,
              :heading, :score, :confidence, :status, :expires_at, :created_at, :metadata_json
            )
            ON CONFLICT(id) DO UPDATE SET
              text=excluded.text,
              snippet=excluded.snippet,
              source_type=excluded.source_type,
              source_id=excluded.source_id,
              scope_type=excluded.scope_type,
              scope_id=excluded.scope_id,
              owner_type=excluded.owner_type,
              owner_id=excluded.owner_id,
              visibility=excluded.visibility,
              project_id=excluded.project_id,
              source_path=excluded.source_path,
              page=excluded.page,
              heading=excluded.heading,
              score=excluded.score,
              confidence=excluded.confidence,
              status=excluded.status,
              expires_at=excluded.expires_at,
              created_at=excluded.created_at,
              metadata_json=excluded.metadata_json
            """,
            values,
        )
    return {"ok": True, "id": values["id"]}


def list_context_records(
    db_path: Path,
    *,
    scope: dict[str, object] | None = None,
    include_inactive: bool = False,
    limit: int = 100,
) -> list[ContextRecord]:
    normalized = normalize_scope(scope)
    conditions: list[str] = []
    params: list[object] = []
    if normalized["scopeType"]:
        conditions.append("scope_type = ?")
        params.append(normalized["scopeType"])
    if normalized["scopeId"]:
        conditions.append("scope_id = ?")
        params.append(normalized["scopeId"])
    if not include_inactive:
        conditions.append("status = 'active'")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit = max(1, min(int(limit or 100), 500))
    with connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM context_records
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    records = [row_to_record(row) for row in rows]
    if include_inactive:
        return records
    return [record for record in records if record_is_active(record)]


def forget_context_record(db_path: Path, record_id: str, *, reason: str = "") -> dict[str, object]:
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM context_records WHERE id = ?", (str(record_id),)).fetchone()
        if row is None:
            return {"ok": False, "error": "記憶が見つかりません。"}
        forgotten = forget(row_to_record(row), reason=reason)["record"]
        values = record_values(forgotten)
        connection.execute(
            """
            UPDATE context_records
            SET status = :status, metadata_json = :metadata_json
            WHERE id = :id
            """,
            values,
        )
    return {"ok": True, "record": forgotten}


def update_context_record(db_path: Path, record_id: str, updates: dict[str, object]) -> dict[str, object]:
    text = str(updates.get("text") or "").strip() if isinstance(updates, dict) else ""
    if not text:
        return {"ok": False, "error": "記憶する内容がありません。"}
    if contains_sensitive_text(text):
        return {
            "ok": False,
            "needsReview": True,
            "reason": "センシティブ情報の可能性があるため自動保存しません。",
        }
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM context_records WHERE id = ?", (str(record_id),)).fetchone()
        if row is None:
            return {"ok": False, "error": "記憶が見つかりません。"}
        record = row_to_record(row)
        metadata = dict(record.metadata or {})
        memory_type = str(updates.get("memoryType") or metadata.get("memoryType") or "fact")
        if memory_type not in MEMORY_TYPES:
            memory_type = "fact"
        metadata["memoryType"] = memory_type
        if updates.get("sourceType"):
            metadata["sourceType"] = str(updates.get("sourceType"))
        if updates.get("sourceId"):
            metadata["sourceId"] = str(updates.get("sourceId"))
            record.sourceId = str(updates.get("sourceId"))
        record.text = text
        record.snippet = text
        record.metadata = metadata
        values = record_values(record)
        connection.execute(
            """
            UPDATE context_records
            SET text = :text,
                snippet = :snippet,
                source_id = :source_id,
                metadata_json = :metadata_json
            WHERE id = :id
            """,
            values,
        )
    return {"ok": True, "record": record.to_dict()}
