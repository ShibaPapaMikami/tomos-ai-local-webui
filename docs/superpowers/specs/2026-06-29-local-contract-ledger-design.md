# Local Contract Ledger MVP Design

## Goal
Gemma4に、g-contractの中核である「契約書検索、AI抽出候補、人による確定、契約台帳」をクラウドなしで導入する。

## Scope
このMVPはPC内完結を前提にする。Supabase、OpenAI API、Slack通知、メール通知、クラウド同期、外部公開は含めない。対象は締結済み契約書のPDF、テキスト、Markdownで、スキャン画像PDFのOCRは自動実行しない。

## User Flow
1. ユーザーは左カラムのフォルダー設定で契約書フォルダーを指定する。
2. 資料検索を準備し、契約書PDFやテキストをKnowledge Layerへ索引化する。
3. 契約書管理画面で「契約書を抽出」を押す。
4. アプリは索引済み文書から契約名、取引先、開始日、終了日、自動更新、解約通知期限、ステータス候補を作る。
5. ユーザーが候補を確認し、必要に応じて編集してSQLite台帳へ保存する。
6. 契約一覧で終了日と解約通知期限が近い順に確認できる。
7. 根拠カードまたは台帳の原本リンクからFinderで契約書を開ける。

## Data Model
SQLiteに `contract_records` を追加する。保存先は既存の `.gemma4-data/knowledge/index.sqlite` とは分け、`.gemma4-data/contracts/contracts.sqlite` とする。

Columns:
- `id`: text primary key
- `folder_id`: text
- `source_path`: text
- `contract_name`: text
- `counterparty_name`: text
- `owner_name`: text
- `start_date`: text, ISO date or empty
- `end_date`: text, ISO date or empty
- `auto_renew`: text, one of `yes`, `no`, `unknown`
- `notice_deadline`: text, ISO date or empty
- `notice_period_days`: integer nullable
- `status`: text, one of `active`, `expired`, `cancelled`, `needs_review`
- `summary`: text
- `notes`: text
- `extraction_json`: text
- `confirmed`: integer, 0 or 1
- `created_at`: integer epoch ms
- `updated_at`: integer epoch ms

## Backend API
- `GET /api/contracts/list?folderId=...`
  - Returns saved contract records sorted by notice deadline, then end date.
- `POST /api/contracts/extract`
  - Input: `folderId`, `query`.
  - Uses Knowledge Layer search to find candidate contract documents.
  - Returns extraction candidates and source snippets.
- `POST /api/contracts/save`
  - Input: contract record fields.
  - Validates enum fields and stores the record.
- `POST /api/contracts/delete`
  - Input: `id`.
  - Deletes one local record.

## Extraction Strategy
Extraction is deterministic-first. It uses regex and Japanese keyword windows before asking the chat model. Initial MVP does not call an external API. Candidate extraction handles:
- dates: `YYYY年M月D日`, `YYYY/MM/DD`, `YYYY-MM-DD`
- end date keywords: `終了日`, `契約期間`, `満了`, `有効期間`
- notice keywords: `解約`, `解除`, `申入`, `通知`, `日前`, `か月前`
- auto-renew keywords: `自動更新`, `更新する`, `更新しない`

If a value is uncertain, it stays empty or `unknown`, and `status` becomes `needs_review`.

## Frontend
Add a management panel named `契約書管理`. It includes:
- selected folder name and contract folder path
- buttons: `契約書を検索`, `候補を抽出`, `保存`
- templates: `終了日は？`, `自動更新は？`, `解約通知期限は？`, `支払条件は？`, `権利帰属は？`
- contract list table with contract name, counterparty, end date, notice deadline, status, source path, Finder button
- extraction review form where users edit candidate values before saving

## Error Handling
- If Knowledge Layer is not ready, show `先に資料検索を準備してください。`
- If no candidate files are found, show `契約書候補が見つかりませんでした。`
- If extraction is uncertain, save is still allowed but `confirmed` defaults to 0 and `status` defaults to `needs_review`.
- Image-only PDFs are not OCRed automatically; they appear as extraction failures or empty candidates.

## Acceptance Criteria
- A local folder with contract-like text can be indexed and searched.
- `契約終了日` or `解約通知期限` queries return relevant source snippets.
- A candidate contract record can be reviewed and saved to SQLite.
- Saved contracts appear in a list sorted by upcoming notice deadline/end date.
- Finder can open the source document from the contract list.
- No Supabase, cloud sync, external AI API, Slack, or email integration is added.
