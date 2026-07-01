from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
import time
import uuid
from pathlib import Path
from typing import Callable


SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf"}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".DS_Store",
    ".codegraph",
    ".gemma4-data",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
}
MAX_INDEX_FILE_BYTES = 16 * 1024 * 1024
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 160


TextExtractor = Callable[[Path], str]


def default_db_path(root: Path) -> Path:
    return root / ".gemma4-data" / "knowledge" / "index.sqlite"


def now_ms() -> int:
    return int(time.time() * 1000)


def file_id(folder_id: str, relative_path: str) -> str:
    digest = hashlib.sha256(f"{folder_id}\n{relative_path}".encode("utf-8")).hexdigest()
    return digest[:32]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def ngrams(value: str) -> list[str]:
    text = re.sub(r"\s+", "", str(value or "").lower())
    if not text:
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    if len(text) <= 3:
        tokens.append(text)
        seen.add(text)
    for size in (2, 3):
        if len(text) < size:
            continue
        for index in range(0, len(text) - size + 1):
            token = text[index : index + size]
            if token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens[:64]


def normalize_text(text: str) -> str:
    text = str(text or "").replace("\r", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def heading_for_chunk(prefix: str) -> str:
    headings = re.findall(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*$", prefix)
    return headings[-1].strip()[:160] if headings else ""


def chunk_text(text: str) -> list[dict[str, object]]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    chunks: list[dict[str, object]] = []
    start = 0
    index = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + CHUNK_SIZE)
        if end < len(cleaned):
            boundary = max(cleaned.rfind("\n\n", start, end), cleaned.rfind("。", start, end))
            if boundary > start + 320:
                end = boundary + 1
        part = cleaned[start:end].strip()
        if part:
            chunks.append({
                "index": index,
                "text": part,
                "start": start,
                "end": end,
                "heading": heading_for_chunk(cleaned[:start]),
            })
            index += 1
        if end >= len(cleaned):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_schema(connection)
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_files (
          id TEXT PRIMARY KEY,
          folder_id TEXT NOT NULL,
          path TEXT NOT NULL,
          extension TEXT NOT NULL,
          mtime INTEGER NOT NULL,
          size INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          status TEXT NOT NULL,
          error TEXT DEFAULT '',
          indexed_at INTEGER NOT NULL,
          UNIQUE(folder_id, path)
        );

        CREATE TABLE IF NOT EXISTS knowledge_chunks (
          id TEXT PRIMARY KEY,
          file_id TEXT NOT NULL,
          folder_id TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          text TEXT NOT NULL,
          start_offset INTEGER,
          end_offset INTEGER,
          page INTEGER,
          heading TEXT DEFAULT '',
          FOREIGN KEY(file_id) REFERENCES knowledge_files(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS knowledge_ngrams (
          token TEXT NOT NULL,
          chunk_id TEXT NOT NULL,
          folder_id TEXT NOT NULL,
          PRIMARY KEY(token, chunk_id),
          FOREIGN KEY(chunk_id) REFERENCES knowledge_chunks(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_files_folder ON knowledge_files(folder_id);
        CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_file ON knowledge_chunks(file_id);
        CREATE INDEX IF NOT EXISTS idx_knowledge_ngrams_folder_token ON knowledge_ngrams(folder_id, token);
        """
    )
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
              text,
              file_id UNINDEXED,
              chunk_id UNINDEXED,
              folder_id UNINDEXED,
              tokenize = 'trigram'
            )
            """
        )
    except sqlite3.OperationalError:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
              text,
              file_id UNINDEXED,
              chunk_id UNINDEXED,
              folder_id UNINDEXED
            )
            """
        )
    connection.commit()


def iter_supported_files(root_path: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, filenames in os.walk(root_path):
        dirs[:] = sorted(name for name in dirs if name not in IGNORED_DIRS and not name.startswith("."))
        for filename in sorted(filenames):
            if filename == ".DS_Store":
                continue
            path = Path(current) / filename
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                info = path.stat()
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode) and info.st_size <= MAX_INDEX_FILE_BYTES:
                files.append(path)
    return files


def index_folder(
    *,
    db_path: Path,
    folder_id: str,
    root_path: Path,
    extract_text: TextExtractor,
    force: bool = False,
) -> dict[str, object]:
    root_path = root_path.expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError("フォルダーが見つかりません。")
    indexed = skipped = failed = deleted = 0
    seen_paths: set[str] = set()
    with connect(db_path) as connection:
      for path in iter_supported_files(root_path):
        rel = path.relative_to(root_path).as_posix()
        seen_paths.add(rel)
        info = path.stat()
        mtime = int(info.st_mtime)
        size = int(info.st_size)
        fid = file_id(folder_id, rel)
        current = connection.execute(
            "SELECT mtime, size, sha256, status FROM knowledge_files WHERE folder_id = ? AND path = ?",
            (folder_id, rel),
        ).fetchone()
        if current and not force and int(current["mtime"]) == mtime and int(current["size"]) == size and current["status"] == "ready":
            skipped += 1
            continue
        digest = sha256_file(path)
        if current and not force and int(current["mtime"]) != mtime and int(current["size"]) == size and current["sha256"] == digest and current["status"] == "ready":
            connection.execute(
                "UPDATE knowledge_files SET mtime = ?, indexed_at = ? WHERE id = ?",
                (mtime, now_ms(), fid),
            )
            skipped += 1
            continue
        connection.execute("DELETE FROM knowledge_chunks WHERE file_id = ?", (fid,))
        connection.execute("DELETE FROM knowledge_fts WHERE file_id = ?", (fid,))
        try:
            text = extract_text(path)
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("テキストを抽出できませんでした。")
            connection.execute(
                """
                INSERT INTO knowledge_files(id, folder_id, path, extension, mtime, size, sha256, status, error, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ready', '', ?)
                ON CONFLICT(id) DO UPDATE SET
                  extension = excluded.extension,
                  mtime = excluded.mtime,
                  size = excluded.size,
                  sha256 = excluded.sha256,
                  status = 'ready',
                  error = '',
                  indexed_at = excluded.indexed_at
                """,
                (fid, folder_id, rel, path.suffix.lower(), mtime, size, digest, now_ms()),
            )
            for chunk in chunks:
                cid = uuid.uuid5(uuid.NAMESPACE_URL, f"{fid}:{chunk['index']}").hex
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks(id, file_id, folder_id, chunk_index, text, start_offset, end_offset, page, heading)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (cid, fid, folder_id, int(chunk["index"]), str(chunk["text"]), int(chunk["start"]), int(chunk["end"]), str(chunk["heading"])),
                )
                connection.execute(
                    "INSERT INTO knowledge_fts(text, file_id, chunk_id, folder_id) VALUES (?, ?, ?, ?)",
                    (str(chunk["text"]), fid, cid, folder_id),
                )
                for token in ngrams(str(chunk["text"])):
                    connection.execute(
                        "INSERT OR IGNORE INTO knowledge_ngrams(token, chunk_id, folder_id) VALUES (?, ?, ?)",
                        (token, cid, folder_id),
                    )
            indexed += 1
        except Exception as exc:
            connection.execute(
                """
                INSERT INTO knowledge_files(id, folder_id, path, extension, mtime, size, sha256, status, error, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'error', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  extension = excluded.extension,
                  mtime = excluded.mtime,
                  size = excluded.size,
                  sha256 = excluded.sha256,
                  status = 'error',
                  error = excluded.error,
                  indexed_at = excluded.indexed_at
                """,
                (fid, folder_id, rel, path.suffix.lower(), mtime, size, digest, str(exc)[:500], now_ms()),
            )
            failed += 1
      existing = connection.execute(
          "SELECT id, path FROM knowledge_files WHERE folder_id = ? AND status != 'deleted'",
          (folder_id,),
      ).fetchall()
      for row in existing:
          if row["path"] not in seen_paths:
              connection.execute("UPDATE knowledge_files SET status = 'deleted', indexed_at = ? WHERE id = ?", (now_ms(), row["id"]))
              deleted += 1
      connection.commit()
      status = knowledge_status(db_path=db_path, folder_id=folder_id, connection=connection)
    return {
        "ok": True,
        "indexed": indexed,
        "skipped": skipped,
        "failed": failed,
        "deleted": deleted,
        "total": indexed + skipped + failed,
        **status,
    }


def knowledge_status(*, db_path: Path, folder_id: str, connection: sqlite3.Connection | None = None) -> dict[str, object]:
    close = False
    if connection is None:
        connection = connect(db_path)
        close = True
    try:
        row = connection.execute(
            """
            SELECT
              MAX(indexed_at) AS last_indexed_at,
              SUM(CASE WHEN status != 'deleted' THEN 1 ELSE 0 END) AS file_count,
              SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) AS text_count,
              SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS failed_count
            FROM knowledge_files
            WHERE folder_id = ?
            """,
            (folder_id,),
        ).fetchone()
        return {
            "ok": True,
            "lastIndexedAt": int(row["last_indexed_at"] or 0),
            "fileCount": int(row["file_count"] or 0),
            "textCount": int(row["text_count"] or 0),
            "failedCount": int(row["failed_count"] or 0),
        }
    finally:
        if close:
            connection.close()


def snippet(text: str, query: str, length: int = 220) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= length:
        return clean
    query = normalize_query(query)
    location = clean.lower().find(query.lower()) if query else -1
    start = max(0, location - 70) if location >= 0 else 0
    end = min(len(clean), start + length)
    return f"{'...' if start else ''}{clean[start:end].strip()}{'...' if end < len(clean) else ''}"


def search_knowledge(*, db_path: Path, folder_id: str, query: str, limit: int = 5) -> dict[str, object]:
    query = normalize_query(query)
    if not query:
        raise ValueError("検索キーワードを入力してください。")
    limit = max(1, min(int(limit or 5), 20))
    tokens = ngrams(query)
    with connect(db_path) as connection:
        rows: list[sqlite3.Row] = []
        if tokens:
            placeholders = ",".join("?" for _ in tokens)
            rows = connection.execute(
                f"""
                SELECT c.id, c.file_id, c.text, c.heading, c.page, f.path, COUNT(n.token) AS hits
                FROM knowledge_ngrams n
                JOIN knowledge_chunks c ON c.id = n.chunk_id
                JOIN knowledge_files f ON f.id = c.file_id
                WHERE n.folder_id = ? AND n.token IN ({placeholders}) AND f.status = 'ready'
                GROUP BY c.id
                ORDER BY hits DESC, length(c.text) ASC
                LIMIT ?
                """,
                (folder_id, *tokens, limit),
            ).fetchall()
        if not rows:
            rows = connection.execute(
                """
                SELECT c.id, c.file_id, c.text, c.heading, c.page, f.path, 1 AS hits
                FROM knowledge_chunks c
                JOIN knowledge_files f ON f.id = c.file_id
                WHERE c.folder_id = ? AND f.status = 'ready' AND c.text LIKE ?
                ORDER BY f.path, c.chunk_index
                LIMIT ?
                """,
                (folder_id, f"%{query}%", limit),
            ).fetchall()
        results = [
            {
                "path": row["path"],
                "page": row["page"],
                "heading": row["heading"] or "",
                "snippet": snippet(row["text"], query),
                "score": min(1.0, round(float(row["hits"] or 1) / max(len(tokens), 1), 3)),
                "sourceType": "knowledge",
            }
            for row in rows
        ]
    return {"ok": True, "query": query, "results": results}
