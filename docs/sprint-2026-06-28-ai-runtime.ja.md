# Sprint 2026-06-28: Local AI Runtime 接続

目的: 上位ロードマップを、直近で動く実装・制作タスクへ落とす。

対象:

- エンジニア
- 学習パック制作担当

## 今回の焦点

2. 教材パックのインポート、追加、有効化、モード選択、チャット反映を安定させる。
3. 学習セットと教材パックの責務を混ぜない。
4. 次の実装として、スマホPWA/PC取り込み、CodeGraph、キャラクター記憶へ進める準備をする。

## 現状確認


このフォルダーは `.gitignore` で除外されているため、社内情報やprivate教材をGitHubへ誤って入れにくい。

現在の構成:

```text
  pack.json
  README.md
  mvv.md
  value-writing-rules.md
  coordinator-communication-rules.md
  tone-guide.md
  avoid-phrases.md
  glossary.csv
  modes/
    slack-rewrite.md
    email-rewrite.md
    request-rewrite.md
    report-rewrite.md
    external-check.md
  examples/
    slack-examples.md
    email-examples.md
```

`pack.json` には5つのモードが定義済み。

- Slackを整える
- メールを整える
- 依頼文を整える
- 報告文を整える
- 外部送信前チェック

## 実施済み確認

- [x] `pack.json` が正しいJSONとして読める
- [x] `visibility: "private"` が維持されている
- [x] 5つのモードが定義されている
- [x] `modes/*.md` の参照先がすべて存在する
- [x] 各modeの本文が空ではない
- [x] 配信HTMLに「教材パック」「学習セット」「プラグイン」の設定メニューが含まれる
- [x] `node scripts/test-management-helpers.js` が通る
- [x] `node --check web/management.js` が通る
- [x] `node --check web/app.js` が通る
- [x] `python3 -m py_compile server.py` が通る

未確認:

- [ ] Safari上で設定メニューを開き、教材パックパネルを目視確認する
- [ ] インポート後に5モードがチャット入力欄の教材パック選択へ出ることを確認する

Safariの自動操作は、`Allow JavaScript from Apple Events` とアクセシビリティ権限の制約で自動実行できなかったため、手動確認として残す。

## 2026-07-01 現状再確認

コード上は、当初ロードマップより先に進んでいる箇所がある。
次の担当者は、新規実装を重ねる前に以下を前提として扱う。

- [x] `knowledge_layer.py` があり、SQLite + n-gram/FTS系の資料検索基盤が追加されている
- [x] `/api/knowledge/status`、`/api/knowledge/index`、`/api/knowledge/search` の導線がある
- [x] フォルダー編集UIに `資料検索` のON/OFF、準備、状態表示の文言がある
- [x] `server.py` のチャット文脈生成で、資料検索が有効ならKnowledge Layer検索結果を使う導線がある
- [x] `contract_ledger.py` と契約書管理UI/APIの導線が追加されている
- [x] 管理画面に `アプリ` 区分と `契約書管理` の追加導線がある
- [x] キャラクター記憶は、PC側で一覧、検索、追加、編集、削除のMVPがある
- [x] スマホPWAとPC QR取り込みは、チャット履歴の送受信までは進んでいる

残っている確認:

- [ ] これらの追加ファイルが意図した差分としてGit管理されるか確認する
- [ ] Safariで、資料検索ON、準備、検索、チャット回答反映まで手動確認する
- [ ] Safariで、契約書管理のPDF取り込み、候補確認、保存まで手動確認する
- [ ] スマホ取り込み先をチャット履歴以外にも分けるUIは未実装として扱う
- [ ] CodeGraphは外部CodeGraph本体ではなく、現状はアプリ内の簡易コード理解として扱う

## エンジニア向けタスク

### Task 1: 教材パック読み込みの回帰確認

目的: private教材パックが既存インポート機能で問題なく扱えることを確認する。

確認項目:

- [ ] `pack.json` が正しいJSONとして読める
- [ ] `modes/*.md` がすべて存在する
- [ ] 各modeの本文が空ではない
- [ ] `visibility: "private"` が維持されている
- [ ] インポート後、教材パック一覧に表示される
- [ ] 追加後、チャット入力欄の教材パック選択に5モードが出る
- [ ] 複数モード選択時に、チャットのシステム指示へ統合される
- [ ] 教材パック本体はユーザー操作で書き換わらない
- [ ] `修正して学習` は学習セットへ保存される

推奨確認コマンド:

```sh
node scripts/test-management-helpers.js
node --check web/management.js
node --check web/app.js
python3 -m py_compile server.py
git diff --check
```

### Task 2: 教材パック利用UXの確認


確認項目:

- [ ] 「教材パック」パネルを開ける
- [ ] private教材であることが分かる表示がある
- [ ] チャット画面で `Slackを整える` などのモードを選べる
- [ ] モード未選択時は、通常チャットに過剰干渉しない

UI文言の注意:

- `教材パック` は維持する
- `プロンプト` や `system prompt` は一般ユーザー向けに出しすぎない
- `private` は「この端末のみ」「社外共有しない」という説明にする

### Task 3: 学習セットとの接続


仕様:

```text
= 基本ルール、MVV、トーン、モード

= 実際に使って出た修正例、好み、追加ルール
```

実装/確認:

- [ ] 保存先として通常の学習セットを選べる
- [ ] 教材パック本体には保存しない
- [ ] 学習ノート表示で、元質問、保存した正しい回答、元AI回答、元チャット名を読める

### Task 4: 次スプリントの技術準備

次スプリント候補:

- [ ] CodeGraphのフォルダー単位ON/OFF
- [ ] Knowledge Layerの資料検索MVP調査
- [ ] スマホPWAの単体保存
- [ ] PC QR取り込み
- [ ] キャラクター記憶の一覧/編集/削除
- [ ] モデル一覧の用途ラベル

このスプリントでは着手しすぎない。
まず教材パックの実利用導線を固める。

Knowledge Layerの調査範囲:

- [ ] SQLite FTS5 + trigram/n-gram検索の実装方針を確認する
- [ ] ファイルパス、更新日時、ファイルサイズ、ハッシュによる差分更新の設計を作る
- [ ] TXT/MD/PDFテキスト抽出の最小パイプラインを確認する
- [ ] 検索結果をAI回答へ渡す最小UI/APIを設計する
- [ ] CSV/ExcelはVector DBではなくSQLiteテーブル化する方針を確認する
- [ ] CodeGraphとは別の「資料検索」機能として扱う

### Task 5: Knowledge Layer MVP 実装指示

目的: フォルダー内の資料を素早く検索し、関連箇所だけをAI回答へ渡せる最小基盤を作る。

このタスクはCodeGraphとは分ける。
CodeGraphはコード構造、Knowledge Layerは文書、PDF、名簿、契約書、議事録を扱う。

#### MVPの対象

最初に扱うもの:

- [ ] TXT
- [ ] Markdown
- [ ] テキスト抽出できるPDF

後で扱うもの:

- [ ] CSV
- [ ] Excel
- [ ] OCRが必要なPDF
- [ ] 契約書JSON抽出
- [ ] Embedding / LanceDB

#### 保存先

まずはアプリ管理データ領域にSQLite DBを作る。
既存の `localStorage` 学習セットとは混ぜない。

候補:

```text
.gemma4-data/knowledge/index.sqlite
```

将来 `ManabiPal` 名へ移行してもよいが、今回は既存の `.gemma4-data/` を壊さない。

#### SQLiteテーブル案

```sql
CREATE TABLE knowledge_files (
  id TEXT PRIMARY KEY,
  folder_id TEXT NOT NULL,
  path TEXT NOT NULL,
  extension TEXT NOT NULL,
  mtime INTEGER NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT DEFAULT '',
  indexed_at INTEGER NOT NULL
);

CREATE TABLE knowledge_chunks (
  id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  start_offset INTEGER,
  end_offset INTEGER,
  page INTEGER,
  heading TEXT DEFAULT '',
  FOREIGN KEY(file_id) REFERENCES knowledge_files(id)
);

CREATE VIRTUAL TABLE knowledge_fts USING fts5(
  text,
  file_id UNINDEXED,
  chunk_id UNINDEXED,
  tokenize = 'trigram'
);
```

SQLite環境によって `tokenize = 'trigram'` が使えない場合は、アプリ側で2-gram/3-gramキーを作る補助テーブルにフォールバックする。
MeCabやSudachiはMVPでは入れない。

#### 差分更新

「準備する」「再準備」で毎回全件再処理しない。

各ファイルについて以下を保存し、変更があるものだけ再処理する。

- ファイルパス
- 更新日時
- ファイルサイズ
- SHA-256

判定:

```text
path + mtime + size が同じ
→ 原則スキップ

mtime または size が変わった
→ sha256 を計算し、変わっていれば再処理

DBに存在するが実ファイルが消えた
→ status = deleted またはDBから削除
```

#### チャンク分割

MVPでは単純分割でよい。

- 1チャンク: 800〜1200文字程度
- オーバーラップ: 100〜200文字程度
- Markdown見出しが取れる場合は `heading` に保存
- PDFはページ番号が取れる場合は `page` に保存

#### API案

```text
POST /api/knowledge/index
```

入力:

```json
{
  "folderId": "folder-1",
  "path": "/path/to/folder",
  "force": false
}
```

出力:

```json
{
  "ok": true,
  "indexed": 12,
  "skipped": 116,
  "failed": 3,
  "total": 131
}
```

```text
GET /api/knowledge/status?folderId=folder-1
```

出力:

```json
{
  "ok": true,
  "lastIndexedAt": 1780000000000,
  "fileCount": 128,
  "textCount": 125,
  "failedCount": 3
}
```

```text
POST /api/knowledge/search
```

入力:

```json
{
  "folderId": "folder-1",
  "query": "契約終了日",
  "limit": 5
}
```

出力:

```json
{
  "ok": true,
  "results": [
    {
      "path": "docs/sample.pdf",
      "page": 3,
      "heading": "契約期間",
      "snippet": "...",
      "score": 0.82
    }
  ]
}
```

#### UI案

フォルダー編集に追加する。

```text
[ ] 資料検索を使う
    このフォルダー内のPDF、テキスト、Markdownを検索できるようにします。
    [準備する] [再準備]

最終更新: 2026/xx/xx xx:xx
登録ファイル数: 128件
検索可能テキスト: 125件
失敗: 3件
```

チャット側:

- [ ] 「この資料から探して」「フォルダー内を検索して」などの依頼でKnowledge検索を使う
- [ ] 検索結果の上位3〜5件だけをAI文脈へ渡す
- [ ] 回答には参照元ファイル名、ページ、見出しを出す
- [ ] 検索結果がない場合は、推測で答えず「見つかりませんでした」と返す

#### 受け入れ条件

- [ ] フォルダー編集で「資料検索を使う」をONにできる
- [ ] 「準備する」でTXT/MD/PDFテキストを索引化できる
- [ ] 2回目の準備では未変更ファイルをスキップする
- [ ] 更新したファイルだけ再処理される
- [ ] 日本語キーワードで検索できる
- [ ] 検索結果にファイル名と抜粋が出る
- [ ] チャット回答に検索結果の関連箇所だけが渡る
- [ ] CodeGraphの設定やデータと混ざらない
- [ ] CSV/Excel/OCR/契約書JSON抽出はMVPでは未実装でもよい

### Task 6: PilotDeck参考要素の最小導入

目的: PilotDeckの良い考え方だけを取り入れ、アプリをLocal AI Runtimeとして整理する。
PilotDeck本体コードは取り込まない。

実装しやすい順:

1. 既存データの表示整理
   - [ ] 記憶、学習セット、教材パック、資料検索、契約書、スマホ取り込みを別カテゴリとして表示する
   - [ ] ユーザー向けには `Memory` ではなく `記憶`、`Knowledge` ではなく `資料検索` を使う
   - [ ] 契約書管理は `アプリ`、CodeGraph/PDF/OCRは `プラグイン` または `エンジン` として整理する

2. スコープ表示の追加
   - [ ] 記憶や取り込み候補に `全体`、`このフォルダー`、`このキャラ`、`教材パック`、`アプリ` のどれに効くかを表示する
   - [ ] まずはUI表示と内部コメントから始め、保存形式の破壊的変更はしない
   - [ ] 将来SQLite化するときのフィールド名は `sourceType`、`sourceId`、`scopeType`、`scopeId` を候補にする

3. モデル用途ラベル
   - [ ] モデル一覧に `標準`、`高速`、`コード`、`資料検索`、`契約書確認`、`キャラクター`、`実験` の用途を持たせる
   - [ ] 既定のコード候補は `qwen2.5-coder:14b`
   - [ ] 実験モデル、abliterated系、大人モード向けモデルは自動選択しない
   - [ ] 契約書、社内資料、外部送信前チェックでは実験モデルを候補から外す

4. ルールベースの簡易ルーティング
   - [ ] チャット通常: 標準モデル
   - [ ] コード理解/コード修正: コードモデル
   - [ ] 資料検索: 標準モデルまたは高速モデル + Knowledge Layer検索
   - [ ] 契約書管理: 契約書確認向けモデル + 原文根拠表示
   - [ ] キャラクター会話: キャラクター向けモデル
   - [ ] 大人モード: 18歳以上確認済み、かつ明示ONのときだけ対象モデルを候補に出す

5. White-box MemoryのQA
   - [ ] 自動保存された記憶が一覧で読める
   - [ ] 編集できる
   - [ ] 削除または忘れる操作ができる
   - [ ] どの会話、どのスマホ取り込み、どのフォルダーから来た記憶か分かる
   - [ ] センシティブ情報は自動保存しない

今回はやらない:

- PilotDeck本体の導入
- AGPLコードのコピー
- 常駐エージェント
- バックグラウンド自律実行
- 外部MCPの本格接続
- ユーザー確認なしのファイル作成、変更、削除

## 学習パック制作担当向けタスク

### Task 1: MVV本文の社内確認

`mvv.md` のMission/Vision/Valueを確認する。

- [ ] Missionが最新か
- [ ] Visionが最新か
- [ ] Valueが最新か
- [ ] 社外共有してよい範囲か
- [ ] 「評価（社内のみ）」に該当する内容が混ざっていないか

確認が必要な場合は、ファイル内に追記せず、別メモで確認事項として残す。

### Task 2: 例文の追加

`examples/slack-examples.md` と `examples/email-examples.md` を育てる。

追加条件:

- [ ] Slack例を最低3件
- [ ] メール例を最低3件
- [ ] Before/After/理由をセットにする
- [ ] 実文面を使う場合は匿名化する
- [ ] 個人名、会社名、金額、契約、未公開案件名、URLを入れない

おすすめ例:

- 進行確認
- 依頼
- 相談
- 報告
- お礼
- 謝罪
- 外部送信前チェック

### Task 3: モード別チェック

各modeを1回ずつ実文に近い匿名サンプルで試す。

- [ ] Slackを整える
- [ ] メールを整える
- [ ] 依頼文を整える
- [ ] 報告文を整える
- [ ] 外部送信前チェック

評価観点:

- [ ] Gugenkaらしいか
- [ ] 丁寧すぎて重くないか
- [ ] 冷たすぎないか
- [ ] 次の行動が分かるか
- [ ] 事実を勝手に追加していないか
- [ ] 社外秘や未確定情報を出していないか

### Task 4: 学習セットへ保存するもの

教材パック本体にすぐ反映せず、まず学習セットに保存する。

保存してよいもの:

- 「Gugenkaではこの言い方を好む」
- 「この場面では結論を先に出す」
- 「この表現は冷たく見えるので避ける」
- 「外部送信前は未確定情報を確認事項に分ける」

保存しないもの:

- 実名
- 会社名
- 契約内容
- 金額
- 未公開案件
- 個人情報
- 実Slack/実メールの未匿名化本文

## 完了条件

このスプリントの完了条件:

- [ ] 5つのモードがチャット画面で選べる
- [ ] 1つ以上のモードで実際にリライトできる
- [ ] `修正して学習` が学習セットに保存される
- [ ] 学習セットのノート表示で保存内容を読める
- [ ] Slack例3件、メール例3件が匿名化済みで入っている
- [ ] `node scripts/test-management-helpers.js` が通る

## やらないこと

- クラウド同期
- 外部API連携
- 教材パック本体への自動書き込み
- 実メール/実Slackの未匿名化保存
- CodeGraph解析結果の本格統合
- スマホ単体LLM
- PC操作AI
