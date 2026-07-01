# Local Contract Ledger MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only contract ledger MVP using the existing Knowledge Layer so users can find contract information, review extracted candidates, and save confirmed contract metadata to SQLite.

**Architecture:** Add a focused Python module for the contract ledger and deterministic extraction, expose narrow `/api/contracts/*` endpoints from `server.py`, then add a small management panel to the existing web UI. Reuse Knowledge Layer search and existing workspace reveal APIs instead of adding cloud services.

**Tech Stack:** Python stdlib SQLite, existing `knowledge_layer.py`, existing `server.py` HTTP handler, vanilla JS/CSS in `web/`, existing Node/Python test scripts.

---

## File Structure

- Create `contract_ledger.py`
  - Owns SQLite schema, record validation, sorting, deterministic candidate extraction, and public functions used by `server.py`.
- Create `scripts/test_contract_ledger.py`
  - Unit tests for schema creation, extraction, save/list/delete, and sorting.
- Modify `server.py`
  - Add `/api/contracts/list`, `/api/contracts/extract`, `/api/contracts/save`, `/api/contracts/delete`.
- Modify `web/index.html`
  - Add the `契約書管理` button and management panel.
- Modify `web/app.js`
  - Wire DOM elements, API calls, render contract list, render extraction review form, save/delete/reveal actions.
- Modify `web/i18n.js`
  - Add Japanese/English labels.
- Modify `web/styles.css`
  - Add compact table/form styles for contract management.
- Modify `web/sw.js` and script cache-busters in `web/index.html`
  - Ensure Safari/PWA picks up new files.
- Modify JS tests where cache-buster expectations exist.

## Task 1: Contract Ledger Module

**Files:**
- Create: `contract_ledger.py`
- Create: `scripts/test_contract_ledger.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/test_contract_ledger.py`:

```python
from pathlib import Path
import tempfile

from contract_ledger import (
    delete_contract,
    extract_contract_candidate,
    list_contracts,
    save_contract,
)


SAMPLE_TEXT = """
業務委託契約書
株式会社サンプル（以下「甲」）と株式会社Gugenka（以下「乙」）は、次の通り契約する。
契約期間は2026年7月1日から2027年6月30日までとする。
本契約は期間満了の30日前までに書面による解約申入れがない場合、同一条件で1年間自動更新する。
支払条件は月末締め翌月末払いとする。
"""


def test_extract_contract_candidate_from_text():
    candidate = extract_contract_candidate(
        folder_id="folder-1",
        source_path="sample-contract.txt",
        text=SAMPLE_TEXT,
    )
    assert candidate["folderId"] == "folder-1"
    assert candidate["sourcePath"] == "sample-contract.txt"
    assert candidate["contractName"] == "業務委託契約書"
    assert candidate["counterpartyName"] == "株式会社サンプル"
    assert candidate["startDate"] == "2026-07-01"
    assert candidate["endDate"] == "2027-06-30"
    assert candidate["autoRenew"] == "yes"
    assert candidate["noticePeriodDays"] == 30
    assert candidate["noticeDeadline"] == "2027-05-31"
    assert candidate["status"] == "needs_review"


def test_save_list_delete_contract():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "contracts.sqlite"
        record = extract_contract_candidate("folder-1", "sample-contract.txt", SAMPLE_TEXT)
        saved = save_contract(db_path, record)
        assert saved["id"]
        assert saved["confirmed"] == 0

        records = list_contracts(db_path, "folder-1")
        assert len(records) == 1
        assert records[0]["contractName"] == "業務委託契約書"
        assert records[0]["noticeDeadline"] == "2027-05-31"

        delete_contract(db_path, saved["id"])
        assert list_contracts(db_path, "folder-1") == []
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 scripts/test_contract_ledger.py
```

Expected: fails because `contract_ledger` does not exist.

- [ ] **Step 3: Implement `contract_ledger.py`**

Create `contract_ledger.py` with:

```python
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


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    ensure_schema(connection)
    return connection


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


def normalize_date(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"(20\d{2})[年/-]\s*(\d{1,2})[月/-]\s*(\d{1,2})日?", text)
    if not match:
        return ""
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def subtract_days(iso_date: str, days: int | None) -> str:
    if not iso_date or not days:
        return ""
    try:
        return (date.fromisoformat(iso_date) - timedelta(days=int(days))).isoformat()
    except ValueError:
        return ""


def first_line_name(text: str) -> str:
    for line in str(text or "").splitlines():
        cleaned = line.strip(" 　#")
        if cleaned and len(cleaned) <= 80:
            return cleaned
    return ""


def extract_counterparty(text: str) -> str:
    match = re.search(r"(株式会社[^\s（）()、。]{1,40})", text)
    return match.group(1) if match else ""


def extract_period_dates(text: str) -> tuple[str, str]:
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
    source_text = str(text or "")
    start_date, end_date = extract_period_dates(source_text)
    notice_period_days = extract_notice_days(source_text)
    notice_deadline = subtract_days(end_date, notice_period_days)
    auto_renew = extract_auto_renew(source_text)
    extraction = {
        "startDate": start_date,
        "endDate": end_date,
        "autoRenew": auto_renew,
        "noticePeriodDays": notice_period_days,
        "noticeDeadline": notice_deadline,
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
        "notes": "",
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 scripts/test_contract_ledger.py
```

Expected: `contract ledger tests passed`.

Add this line at the bottom of `scripts/test_contract_ledger.py`:

```python
print("contract ledger tests passed")
```

## Task 2: Server API

**Files:**
- Modify: `server.py`
- Test: `scripts/test_contract_ledger.py`

- [ ] **Step 1: Add imports and DB path**

At the top-level imports in `server.py`, add:

```python
from contract_ledger import (
    default_contract_db_path,
    delete_contract,
    extract_contract_candidate,
    list_contracts,
    save_contract,
)
```

Near `KNOWLEDGE_DB_PATH`, add:

```python
CONTRACT_DB_PATH = default_contract_db_path(ROOT)
```

- [ ] **Step 2: Add GET route**

In `do_GET`, near `/api/knowledge/status`, add:

```python
        if parsed.path == "/api/contracts/list":
            self.handle_contracts_list(parsed.query)
            return
```

- [ ] **Step 3: Add POST route**

In `do_POST`, near `/api/knowledge/`, add:

```python
        if self.path.startswith("/api/contracts/"):
            self.handle_contracts()
            return
```

- [ ] **Step 4: Add handlers**

Add methods to the handler class:

```python
    def handle_contracts_list(self, query: str) -> None:
        params = parse_qs(query)
        folder_id = str(params.get("folderId", [""])[0]).strip()
        try:
            json_response(self, 200, {"ok": True, "contracts": list_contracts(CONTRACT_DB_PATH, folder_id)})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_contracts(self) -> None:
        try:
            body = self.read_json()
            if self.path == "/api/contracts/extract":
                folder_id = str(body.get("folderId", "")).strip()
                query = str(body.get("query", "")).strip() or "契約期間 自動更新 解約通知期限"
                search_data = search_knowledge(
                    db_path=KNOWLEDGE_DB_PATH,
                    folder_id=folder_id,
                    query=query,
                    limit=5,
                )
                candidates = []
                for item in search_data.get("results", [])[:5]:
                    source_path = str(item.get("path", "")).strip()
                    snippet = str(item.get("snippet", "")).strip()
                    if source_path and snippet:
                        candidates.append(extract_contract_candidate(folder_id, source_path, snippet))
                json_response(self, 200, {"ok": True, "query": query, "results": search_data.get("results", []), "candidates": candidates})
            elif self.path == "/api/contracts/save":
                saved = save_contract(CONTRACT_DB_PATH, body.get("contract", body))
                json_response(self, 200, {"ok": True, "contract": saved})
            elif self.path == "/api/contracts/delete":
                result = delete_contract(CONTRACT_DB_PATH, str(body.get("id", "")))
                json_response(self, 200, result)
            else:
                json_response(self, 404, {"ok": False, "error": "Not Found"})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})
```

- [ ] **Step 5: Verify Python syntax**

Run:

```bash
python3 -m py_compile server.py contract_ledger.py scripts/test_contract_ledger.py
```

Expected: exit 0.

## Task 3: Frontend Contract Management Panel

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/i18n.js`
- Modify: `web/styles.css`
- Modify: `web/sw.js`
- Modify: cache-buster tests

- [ ] **Step 1: Add sidebar button and panel**

Add a new settings menu button near other extension buttons:

```html
<button class="ghost-button" id="contracts-toggle" type="button" data-i18n="management.contracts">契約書管理</button>
```

Add a management panel:

```html
<section class="management-panel" id="contracts-panel" hidden>
  <div class="management-panel-header">
    <div>
      <strong data-i18n="contracts.title">契約書管理</strong>
      <span data-i18n="contracts.description">このPC内の契約書フォルダーから終了日、解約通知期限、自動更新を探して台帳に保存します。</span>
    </div>
    <button class="ghost-button" id="contracts-close" type="button" data-i18n="common.close">閉じる</button>
  </div>
  <div class="management-panel-body contracts-panel-body">
    <div class="contract-actions">
      <button class="ghost-button" id="contracts-refresh" type="button" data-i18n="contracts.refresh">一覧を更新</button>
      <button class="ghost-button" id="contracts-extract" type="button" data-i18n="contracts.extract">候補を抽出</button>
      <span id="contracts-status" class="management-note"></span>
    </div>
    <div class="contract-template-row" id="contract-template-row"></div>
    <div id="contract-extraction-review"></div>
    <div id="contracts-list"></div>
  </div>
</section>
```

- [ ] **Step 2: Add DOM references and API helpers**

In `web/app.js`, add elements:

```javascript
contractsToggle: document.querySelector("#contracts-toggle"),
contractsPanel: document.querySelector("#contracts-panel"),
contractsClose: document.querySelector("#contracts-close"),
contractsRefresh: document.querySelector("#contracts-refresh"),
contractsExtract: document.querySelector("#contracts-extract"),
contractsStatus: document.querySelector("#contracts-status"),
contractTemplateRow: document.querySelector("#contract-template-row"),
contractExtractionReview: document.querySelector("#contract-extraction-review"),
contractsList: document.querySelector("#contracts-list"),
```

Add helpers:

```javascript
async function contractApi(path, payload = null) {
  const options = payload
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }
    : {};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || t("contracts.error"));
  return data;
}
```

- [ ] **Step 3: Render contract templates**

Add:

```javascript
const CONTRACT_TEMPLATES = [
  "終了日は？",
  "自動更新は？",
  "解約通知期限は？",
  "支払条件は？",
  "権利帰属は？",
];

function renderContractTemplates() {
  if (!els.contractTemplateRow) return;
  els.contractTemplateRow.innerHTML = "";
  for (const label of CONTRACT_TEMPLATES) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost-button";
    button.textContent = label;
    button.addEventListener("click", () => {
      els.prompt.value = label;
      resizePrompt();
      els.prompt.focus();
    });
    els.contractTemplateRow.append(button);
  }
}
```

- [ ] **Step 4: Render saved contracts**

Add:

```javascript
async function loadContracts() {
  if (!els.contractsList) return;
  const folderId = activeFolder()?.id || "";
  const data = await contractApi(`/api/contracts/list?folderId=${encodeURIComponent(folderId)}`);
  renderContractsList(data.contracts || []);
}

function renderContractsList(contracts) {
  if (!els.contractsList) return;
  if (!contracts.length) {
    els.contractsList.innerHTML = `<p class="management-note">${escapeHtml(t("contracts.empty"))}</p>`;
    return;
  }
  els.contractsList.innerHTML = `
    <table class="contract-table">
      <thead><tr>
        <th>${escapeHtml(t("contracts.contractName"))}</th>
        <th>${escapeHtml(t("contracts.counterparty"))}</th>
        <th>${escapeHtml(t("contracts.endDate"))}</th>
        <th>${escapeHtml(t("contracts.noticeDeadline"))}</th>
        <th>${escapeHtml(t("contracts.statusLabel"))}</th>
        <th>${escapeHtml(t("contracts.source"))}</th>
      </tr></thead>
      <tbody>
        ${contracts.map((contract) => `
          <tr>
            <td>${escapeHtml(contract.contractName || "")}</td>
            <td>${escapeHtml(contract.counterpartyName || "")}</td>
            <td>${escapeHtml(contract.endDate || "")}</td>
            <td>${escapeHtml(contract.noticeDeadline || "")}</td>
            <td>${escapeHtml(contract.status || "")}</td>
            <td><button class="ghost-button" type="button" data-contract-source="${escapeHtml(contract.sourcePath || "")}">${escapeHtml(t("workspace.revealPath"))}</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  els.contractsList.querySelectorAll("[data-contract-source]").forEach((button) => {
    button.addEventListener("click", () => revealWorkspaceSource({ path: button.dataset.contractSource || "" }));
  });
}
```

- [ ] **Step 5: Render extraction review and save**

Add:

```javascript
async function extractContractsForActiveFolder() {
  const folder = activeFolder();
  if (!folder?.id) return;
  const knowledge = folder.plugins?.knowledge || {};
  if (!knowledge.enabled || knowledge.status !== "ready") {
    els.contractsStatus.textContent = t("contracts.prepareKnowledgeFirst");
    return;
  }
  els.contractsStatus.textContent = t("contracts.extracting");
  const data = await contractApi("/api/contracts/extract", {
    folderId: folder.id,
    query: "契約期間 自動更新 解約通知期限",
  });
  renderContractExtractionReview(data.candidates?.[0] || null);
  els.contractsStatus.textContent = t("contracts.extracted", { count: data.candidates?.length || 0 });
}

function renderContractExtractionReview(candidate) {
  if (!els.contractExtractionReview) return;
  if (!candidate) {
    els.contractExtractionReview.innerHTML = `<p class="management-note">${escapeHtml(t("contracts.noCandidates"))}</p>`;
    return;
  }
  els.contractExtractionReview.innerHTML = `
    <div class="contract-review-card">
      <label>${escapeHtml(t("contracts.contractName"))}<input data-contract-field="contractName" value="${escapeHtml(candidate.contractName || "")}"></label>
      <label>${escapeHtml(t("contracts.counterparty"))}<input data-contract-field="counterpartyName" value="${escapeHtml(candidate.counterpartyName || "")}"></label>
      <label>${escapeHtml(t("contracts.startDate"))}<input data-contract-field="startDate" value="${escapeHtml(candidate.startDate || "")}" placeholder="YYYY-MM-DD"></label>
      <label>${escapeHtml(t("contracts.endDate"))}<input data-contract-field="endDate" value="${escapeHtml(candidate.endDate || "")}" placeholder="YYYY-MM-DD"></label>
      <label>${escapeHtml(t("contracts.noticeDeadline"))}<input data-contract-field="noticeDeadline" value="${escapeHtml(candidate.noticeDeadline || "")}" placeholder="YYYY-MM-DD"></label>
      <label>${escapeHtml(t("contracts.autoRenew"))}<select data-contract-field="autoRenew">
        <option value="unknown">unknown</option><option value="yes">yes</option><option value="no">no</option>
      </select></label>
      <label>${escapeHtml(t("contracts.statusLabel"))}<select data-contract-field="status">
        <option value="needs_review">needs_review</option><option value="active">active</option><option value="expired">expired</option><option value="cancelled">cancelled</option>
      </select></label>
      <button class="primary-button" id="contract-save-candidate" type="button">${escapeHtml(t("contracts.save"))}</button>
    </div>
  `;
  els.contractExtractionReview.querySelector('[data-contract-field="autoRenew"]').value = candidate.autoRenew || "unknown";
  els.contractExtractionReview.querySelector('[data-contract-field="status"]').value = candidate.status || "needs_review";
  els.contractExtractionReview.querySelector("#contract-save-candidate").addEventListener("click", async () => {
    const contract = { ...candidate, confirmed: 1 };
    els.contractExtractionReview.querySelectorAll("[data-contract-field]").forEach((input) => {
      contract[input.dataset.contractField] = input.value;
    });
    await contractApi("/api/contracts/save", { contract });
    els.contractsStatus.textContent = t("contracts.saved");
    await loadContracts();
  });
}
```

- [ ] **Step 6: Bind events**

Add:

```javascript
els.contractsToggle?.addEventListener("click", () => {
  openManagementPanel("contracts");
  renderContractTemplates();
  loadContracts();
});
els.contractsClose?.addEventListener("click", closeManagementPanels);
els.contractsRefresh?.addEventListener("click", loadContracts);
els.contractsExtract?.addEventListener("click", extractContractsForActiveFolder);
```

If `openManagementPanel` uses known panel IDs, add `contracts` to that switch/list.

## Task 4: Verification

**Files:**
- Existing tests and new tests.

- [ ] **Step 1: Run Python tests**

```bash
python3 -m py_compile server.py knowledge_layer.py contract_ledger.py scripts/test_contract_ledger.py
python3 scripts/test_contract_ledger.py
python3 scripts/test_knowledge_layer.py
python3 scripts/test_server_helpers.py
```

Expected: all pass.

- [ ] **Step 2: Run JS tests**

```bash
node --check web/app.js
node --check web/messages.js
node --check web/i18n.js
node scripts/test-model-selection.js
node scripts/test-pwa-assets.js
node scripts/test-management-helpers.js
node scripts/test-workspace-helpers.js
```

Expected: all pass.

- [ ] **Step 3: Manual Safari test**

1. Open `http://127.0.0.1:54876/` in Safari.
2. Choose a folder with a small contract-like text file.
3. Enable and prepare `資料検索`.
4. Open `契約書管理`.
5. Click `候補を抽出`.
6. Confirm that a review form appears.
7. Save it.
8. Confirm the saved record appears in the contract list.
9. Click Finder link and confirm it opens the source file.

## Out of Scope

- Supabase migration
- OpenAI API extraction
- Slack/email reminders
- image-only PDF OCR automation
- multi-user permissions
- cloud sync
