from __future__ import annotations

from datetime import date, timedelta
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path


VALID_AUTO_RENEW = {"yes", "no", "unknown"}
VALID_STATUS = {"active", "expired", "cancelled", "needs_review"}


def default_contract_db_path(root: Path) -> Path:
    return root / ".gemma4-data" / "contracts" / "contracts.sqlite"


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_records (
          id TEXT PRIMARY KEY,
          folder_id TEXT NOT NULL,
          source_path TEXT NOT NULL,
          contract_name TEXT DEFAULT '',
          counterparty_name TEXT DEFAULT '',
          owner_name TEXT DEFAULT '',
          start_date TEXT DEFAULT '',
          end_date TEXT DEFAULT '',
          auto_renew TEXT DEFAULT 'unknown',
          notice_deadline TEXT DEFAULT '',
          notice_period_days INTEGER,
          status TEXT DEFAULT 'needs_review',
          summary TEXT DEFAULT '',
          notes TEXT DEFAULT '',
          extraction_json TEXT DEFAULT '{}',
          confirmed INTEGER DEFAULT 0,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_contract_records_folder ON contract_records(folder_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_contract_records_notice ON contract_records(notice_deadline)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_contract_records_end ON contract_records(end_date)")
    connection.commit()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    ensure_schema(connection)
    return connection


def normalize_date(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"(20\d{2})[年/-]\s*(\d{1,2})[月/-]\s*(\d{1,2})日?", text)
    if not match:
        return ""
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return ""


def subtract_days(iso_date: str, days: int | None) -> str:
    if not iso_date or not days:
        return ""
    try:
        return (date.fromisoformat(iso_date) - timedelta(days=int(days))).isoformat()
    except ValueError:
        return ""


def normalize_contract_text(text: str) -> str:
    source = str(text or "")
    source = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", source)
    source = re.sub(r"[ \t\r\f\v]+", " ", source)
    source = re.sub(r"\n\s+", "\n", source)
    source = re.sub(r"\s+([、。，．）」』])", r"\1", source)
    source = re.sub(r"([「『（])\s+", r"\1", source)
    source = re.sub(r"(20\d{2})年\s*(\d{1,2})\s+(\d{1,2})\s*月\s*日付", r"\1年\2月\3日付", source)
    return source.strip()


def first_line_name(text: str) -> str:
    source = normalize_contract_text(text)
    contract_title = re.search(r"([^\s、。]{2,40}契約書)", source[:120])
    if contract_title:
        return contract_title.group(1)
    for line in source.splitlines():
        cleaned = line.strip(" 　#")
        if cleaned and len(cleaned) <= 80:
            return cleaned
    return ""


def extract_counterparty(text: str) -> str:
    source = normalize_contract_text(text)
    match = re.search(r"(株式会社[^\s（）()、。]{1,40})", source)
    return match.group(1).strip() if match else ""


def extract_term_note(text: str) -> str:
    source = normalize_contract_text(text).replace("\n", " ")
    patterns = [
        r"(業務委託契約終了日から\d+年間.{0,30}?効力を有する)",
        r"(契約終了日から\d+年間.{0,30}?効力を有する)",
        r"(本契約.{0,20}?有効期間.{0,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            phrase = match.group(1).strip(" 。")
            return re.sub(r"(?<=[ぁ-んァ-ン一-龥])\s+(?=[ぁ-んァ-ン一-龥])", "", phrase)
    return ""


def extract_period_dates(text: str) -> tuple[str, str]:
    dated_contract = re.search(r"(20\d{2}[年/-]\s*\d{1,2}[月/-]\s*\d{1,2}日?)\s*付の.{0,20}?契約書", text)
    if dated_contract:
        return normalize_date(dated_contract.group(1)), ""
    match = re.search(
        r"(20\d{2}[年/-]\s*\d{1,2}[月/-]\s*\d{1,2}日?).{0,20}?(?:から|より|開始).{0,40}?(20\d{2}[年/-]\s*\d{1,2}[月/-]\s*\d{1,2}日?)",
        text,
        re.S,
    )
    if match:
        return normalize_date(match.group(1)), normalize_date(match.group(2))
    dates = [normalize_date(value.group(0)) for value in re.finditer(r"20\d{2}[年/-]\s*\d{1,2}[月/-]\s*\d{1,2}日?", text)]
    dates = [value for value in dates if value]
    if len(dates) >= 2:
        return dates[0], dates[1]
    if len(dates) == 1:
        return "", dates[0]
    return "", ""


def extract_notice_days(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*日前.{0,20}(?:解約|解除|申入|通知)|(?:解約|解除|申入|通知).{0,20}(\d{1,3})\s*日前", text)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    return int(value)


def extract_auto_renew(text: str) -> str:
    if re.search(r"自動更新|同一条件で.{0,12}更新|更新する", text):
        return "yes"
    if re.search(r"更新しない|自動的に更新されない|期間満了により終了", text):
        return "no"
    return "unknown"


def extract_contract_candidate(folder_id: str, source_path: str, text: str) -> dict:
    source_text = normalize_contract_text(text)
    start_date, end_date = extract_period_dates(source_text)
    notice_period_days = extract_notice_days(source_text)
    notice_deadline = subtract_days(end_date, notice_period_days)
    auto_renew = extract_auto_renew(source_text)
    term_note = extract_term_note(source_text)
    extraction = {
        "startDate": start_date,
        "endDate": end_date,
        "autoRenew": auto_renew,
        "noticePeriodDays": notice_period_days,
        "noticeDeadline": notice_deadline,
        "termNote": term_note,
    }
    return {
        "id": "",
        "folderId": str(folder_id or ""),
        "sourcePath": str(source_path or ""),
        "contractName": first_line_name(source_text),
        "counterpartyName": extract_counterparty(source_text),
        "ownerName": "",
        "startDate": start_date,
        "endDate": end_date,
        "autoRenew": auto_renew,
        "noticeDeadline": notice_deadline,
        "noticePeriodDays": notice_period_days,
        "status": "needs_review",
        "summary": source_text.strip().replace("\n", " ")[:400],
        "notes": term_note,
        "extractionJson": extraction,
        "confirmed": 0,
    }


def row_to_contract(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "folderId": row["folder_id"],
        "sourcePath": row["source_path"],
        "contractName": row["contract_name"],
        "counterpartyName": row["counterparty_name"],
        "ownerName": row["owner_name"],
        "startDate": row["start_date"],
        "endDate": row["end_date"],
        "autoRenew": row["auto_renew"],
        "noticeDeadline": row["notice_deadline"],
        "noticePeriodDays": row["notice_period_days"],
        "status": row["status"],
        "summary": row["summary"],
        "notes": row["notes"],
        "extractionJson": json.loads(row["extraction_json"] or "{}"),
        "confirmed": int(row["confirmed"] or 0),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def validate_record(record: dict) -> dict:
    now = int(time.time() * 1000)
    auto_renew = record.get("autoRenew") if record.get("autoRenew") in VALID_AUTO_RENEW else "unknown"
    status = record.get("status") if record.get("status") in VALID_STATUS else "needs_review"
    notice_period = record.get("noticePeriodDays")
    notice_period = int(notice_period) if isinstance(notice_period, int) or str(notice_period or "").isdigit() else None
    return {
        "id": str(record.get("id") or uuid.uuid4()),
        "folder_id": str(record.get("folderId") or ""),
        "source_path": str(record.get("sourcePath") or ""),
        "contract_name": str(record.get("contractName") or ""),
        "counterparty_name": str(record.get("counterpartyName") or ""),
        "owner_name": str(record.get("ownerName") or ""),
        "start_date": normalize_date(str(record.get("startDate") or "")) or str(record.get("startDate") or ""),
        "end_date": normalize_date(str(record.get("endDate") or "")) or str(record.get("endDate") or ""),
        "auto_renew": auto_renew,
        "notice_deadline": normalize_date(str(record.get("noticeDeadline") or "")) or str(record.get("noticeDeadline") or ""),
        "notice_period_days": notice_period,
        "status": status,
        "summary": str(record.get("summary") or ""),
        "notes": str(record.get("notes") or ""),
        "extraction_json": json.dumps(record.get("extractionJson") or {}, ensure_ascii=False),
        "confirmed": 1 if record.get("confirmed") else 0,
        "created_at": int(record.get("createdAt") or now),
        "updated_at": now,
    }


def save_contract(db_path: Path, record: dict) -> dict:
    values = validate_record(record)
    with connect(db_path) as connection:
        duplicate_ids: list[str] = []
        if not record.get("id") and values["folder_id"] and values["source_path"]:
            existing_rows = connection.execute(
                """
                SELECT id, created_at FROM contract_records
                WHERE folder_id = ? AND source_path = ?
                ORDER BY updated_at DESC
                """,
                (values["folder_id"], values["source_path"]),
            ).fetchall()
            existing = existing_rows[0] if existing_rows else None
            if existing:
                values["id"] = existing["id"]
                values["created_at"] = existing["created_at"]
                duplicate_ids = [row["id"] for row in existing_rows[1:]]
        connection.execute(
            """
            INSERT INTO contract_records (
              id, folder_id, source_path, contract_name, counterparty_name, owner_name,
              start_date, end_date, auto_renew, notice_deadline, notice_period_days,
              status, summary, notes, extraction_json, confirmed, created_at, updated_at
            ) VALUES (
              :id, :folder_id, :source_path, :contract_name, :counterparty_name, :owner_name,
              :start_date, :end_date, :auto_renew, :notice_deadline, :notice_period_days,
              :status, :summary, :notes, :extraction_json, :confirmed, :created_at, :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
              folder_id=excluded.folder_id,
              source_path=excluded.source_path,
              contract_name=excluded.contract_name,
              counterparty_name=excluded.counterparty_name,
              owner_name=excluded.owner_name,
              start_date=excluded.start_date,
              end_date=excluded.end_date,
              auto_renew=excluded.auto_renew,
              notice_deadline=excluded.notice_deadline,
              notice_period_days=excluded.notice_period_days,
              status=excluded.status,
              summary=excluded.summary,
              notes=excluded.notes,
              extraction_json=excluded.extraction_json,
              confirmed=excluded.confirmed,
              updated_at=excluded.updated_at
            """,
            values,
        )
        if duplicate_ids:
            connection.executemany("DELETE FROM contract_records WHERE id = ?", [(item_id,) for item_id in duplicate_ids])
        row = connection.execute("SELECT * FROM contract_records WHERE id = ?", (values["id"],)).fetchone()
        return row_to_contract(row)


def list_contracts(db_path: Path, folder_id: str = "") -> list[dict]:
    with connect(db_path) as connection:
        if folder_id:
            rows = connection.execute(
                """
                SELECT * FROM contract_records
                WHERE folder_id = ?
                ORDER BY
                  CASE WHEN notice_deadline = '' THEN 1 ELSE 0 END,
                  notice_deadline ASC,
                  CASE WHEN end_date = '' THEN 1 ELSE 0 END,
                  end_date ASC,
                  updated_at DESC
                """,
                (folder_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM contract_records
                ORDER BY
                  CASE WHEN notice_deadline = '' THEN 1 ELSE 0 END,
                  notice_deadline ASC,
                  CASE WHEN end_date = '' THEN 1 ELSE 0 END,
                  end_date ASC,
                  updated_at DESC
                """
            ).fetchall()
        return [row_to_contract(row) for row in rows]


def delete_contract(db_path: Path, contract_id: str) -> dict:
    with connect(db_path) as connection:
        connection.execute("DELETE FROM contract_records WHERE id = ?", (str(contract_id),))
        return {"ok": True}
