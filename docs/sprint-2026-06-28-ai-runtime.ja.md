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
   - [ ] 軽量標準候補として `Qwen/Qwen3-4B-Instruct-2507` を追加する
   - [ ] 既定のコード候補は `qwen2.5-coder:14b`
   - [ ] 実験モデル、abliterated系、大人モード向けモデルは自動選択しない
   - [ ] 契約書、社内資料、外部送信前チェックでは実験モデルを候補から外す

4. ルールベースの簡易ルーティング
   - [ ] チャット通常: 軽量標準モデルまたは標準モデル
   - [ ] コード理解/コード修正: コードモデル
   - [ ] 資料検索: 軽量標準モデルまたは標準モデル + Knowledge Layer検索
   - [ ] 契約書管理: 契約書確認向けモデル + 原文根拠表示
   - [ ] キャラクター会話: キャラクター向けモデル
   - [ ] 大人モード: 18歳以上確認済み、かつ明示ONのときだけ対象モデルを候補に出す

### Task 7: Qwen3 4B Instruct 2507 追加指示

目的: 学生PCでも使いやすい軽量標準モデルとして `Qwen/Qwen3-4B-Instruct-2507` を追加する。

公式確認済みの前提:

- [x] Hugging Face ID: `Qwen/Qwen3-4B-Instruct-2507`
- [x] ライセンス: Apache-2.0
- [x] パラメータ規模: 4B
- [x] non-thinking mode専用で、通常は `<think>` ブロックを出さない
- [x] 長文コンテキストは最大262,144 tokens対応。ただしローカルMVPでは32K以下を初期上限にする
- [x] Ollama、LM Studio、llama.cpp系アプリで使える量子化導線がある
- [x] Ollama実行名候補: `hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL`

アプリ内の扱い:

- [ ] 表示名: `Qwen3 4B Instruct`
- [ ] 詳細名または内部メモ: `Qwen3-4B-Instruct-2507`
- [ ] 用途ラベル: `軽量標準`、`資料検索`、`学習パック`
- [ ] 非推奨用途: `コード標準`、`大人モード専用`、`契約書の最終判断`
- [ ] モデル一覧では、Gemma 4 12Bより軽い標準候補として表示する
- [ ] 既存の `qwen3:4b` 表示と混同しない。2507版が使える場合は別エントリにする

導入手順:

1. まずローカル実行名を確認する
   - [x] Ollama公式または実行環境で、2507版のpull名を確認する
   - [x] `hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL` をアプリ内のダウンロード候補に使う
   - [ ] GGUF/llama.cpp導線は、量子化ファイルの配布元、量子化方式、ライセンスを確認してから追加する

2. モデル定義へ追加する
   - [ ] `web/models.js` の表示名、family、purposeに追加する
   - [ ] `web/settings.js` のインストール候補またはモデル説明に追加する
   - [ ] 必要なら `server.py` のモデル候補、既定値、health/metaへ追加する
   - [ ] 既存の `gemma4.*` localStorageキーは変更しない

3. ルーティングへ追加する
   - [ ] 通常チャットの軽量候補にする
   - [ ] 資料検索ONのフォルダーでは、軽い回答候補にする
   - [ ] 教材パック利用時の軽量候補にする
   - [ ] コード修正やCodeGraph本格利用では `qwen2.5-coder:14b` を優先する
   - [ ] 契約書管理では、必ず原文根拠表示を維持し、モデル回答だけで確定しない

4. 推奨パラメータ
   - [ ] temperature: `0.7`
   - [ ] top_p: `0.8`
   - [ ] top_k: `20`
   - [ ] context: 初期は `8192` から始め、上限候補を `32768` にする
   - [ ] 256K contextは上級設定に隠し、低メモリPCでは自動選択しない

5. テスト
   - [ ] `node scripts/test-model-selection.js`
   - [ ] `node --check web/models.js`
   - [ ] `node --check web/settings.js`
   - [ ] `python3 -m py_compile server.py`
   - [ ] Safariでモデル一覧に `Qwen3 4B Instruct` が表示されることを確認する
   - [ ] Safariで通常チャット、資料検索、教材パック利用時に選択できることを確認する

受け入れ条件:

- [ ] モデル一覧で `Qwen3 4B Instruct` が軽量標準として表示される
- [ ] 既存の `qwen3:4b` と2507版の違いが内部的に区別される
- [ ] インストール名が未確定の場合、壊れたDLボタンを出さない
- [ ] 学生向け標準候補として表示される
- [ ] コード標準や大人モード専用モデルとして自動選択されない

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

### Task 8: Supermemory参考のLocal Context Core設計

目的: Supermemoryの「Memory + Profile + Hybrid Search + Connectorsを1つのContext APIで扱う」思想を参考にしつつ、TOMOSではローカルSQLite、原文根拠、Dating reality showへの再利用を優先した共通基盤を設計する。

このタスクでは、Supermemory本体を直接導入しない。
既存のKnowledge Layer MVPを壊さず、その上に載る次段の設計として扱う。

#### まず作る設計メモ

- [ ] `docs/local-context-core-roadmap.ja.md` を作る
- [ ] `RAG`、`Memory`、`Profile`、`Graph`、`Context` の責務を分ける
- [ ] `search()` / `remember()` / `forget()` / `profile()` / `context()` の最小APIを定義する
- [ ] `scopeType`、`scopeId`、`ownerType`、`ownerId`、`visibility`、`projectId` を先に固定する
- [ ] Entity/Relationより前に `ContextRecord` 共通型を定義する
- [ ] 既存の `knowledge_layer.py`、キャラクター記憶、学習セット、契約書管理、CodeGraphとの接続点を書く
- [ ] Dating reality showで再利用できる範囲と、使わない範囲を書く

#### MVPの実装順

1. 現状維持
   - [ ] 既存のSQLite/n-gram資料検索MVPを壊さない
   - [ ] 検索結果には `sourcePath`、`page`、`snippet`、`sourceType` を必ず残す
   - [ ] 契約書や会社資料は、Graphだけで判断しない

2. ContextRecord共通型を追加
   - [ ] `ContextRecord` に `recordType`、`sourceType`、`sourceId`、`sourcePath`、`page`、`snippet`、`confidence`、`scope` を持たせる
   - [ ] `deletedAt`、`deleteReason`、`hardDeleteEligible` を持たせる
   - [ ] 既存DBはすぐ移行せず、adapterで共通形式へ変換する
   - [ ] `context()` は削除済み、期限切れ、別scopeのrecordを返さない

3. Entity抽出テーブルを追加
   - [ ] 最初はSQLiteで `context_entities` を作る
   - [ ] Entity typeは `person`、`company`、`project`、`document`、`contract`、`repository`、`character` から始める
   - [ ] `name`、`aliases`、`sourceType`、`sourceId`、`confidence`、`scope` を持たせる
   - [ ] LLM抽出ではなく、まずファイル名、契約書候補、CSV列、明示保存された記憶から作る

4. Relation抽出テーブルを追加
   - [ ] 最初はSQLiteで `context_relations` を作る
   - [ ] Relation typeは `mentions`、`belongs_to`、`works_on`、`relates_to`、`source_of`、`supersedes` から始める
   - [ ] Relationの向きは `fromEntityId -> relationType -> toEntityId` として固定する
   - [ ] Relationには必ず `fromEntityId`、`toEntityId`、`relationType`、`sourceId`、`snippet`、`confidence`、`deletedAt` を持たせる
   - [ ] 誤抽出を削除/無効化できるように `deletedAt`、`deleteReason`、`hardDeleteEligible` を持たせる

5. Memory/Profileを分ける
   - [ ] Memory typeは `fact`、`preference`、`activity`、`temporary` に分ける
   - [ ] Memory statusは `active`、`expired`、`superseded`、`deleted`、`conflict` に分ける
   - [ ] 期限付き記憶には `expiresAt` を持たせる
   - [ ] 古い情報を上書きせず、`supersedes` で追跡する
   - [ ] `profile()` は安定した事実と最近の活動を分けて返す
   - [ ] `remember()` はセンシティブ情報を自動保存せず、保存前確認に回す

6. Unified Context APIの薄い実装
   - [ ] `search(query, scope)` はまずKnowledge Layer検索を呼ぶだけでよい
   - [ ] `remember(item, scope)` は既存のキャラクター記憶/学習セット保存へ橋渡しするだけでよい
   - [ ] `forget(id, reason)` は論理削除から始め、将来の物理削除候補として `hardDeleteEligible` を扱う
   - [ ] `profile(scope)` はキャラクター記憶または学習セットから要約候補を返す
   - [ ] `context(query, scope)` はAIへ渡す文脈を最小化する

#### Dating reality showで使いやすくする条件

- [ ] Context CoreはUI、Firebase、DB、LLM providerへ直接依存しない
- [ ] Dating側では `@tomos-ai/character-core` と同じく、packageまたはadapterで受け取れる形にする
- [ ] Dating側の対象はキャラクター記憶、口調候補、理想返答/NG返答、Prompt version、AI同士模擬チャット評価に限定する
- [ ] 共通型を作る場合は `ContextEntity`、`ContextRelation`、`ContextMemory` のようにゲーム固有名を避ける

#### やらないこと

- [ ] Supermemory本体の組み込み
- [ ] 外部Memory API依存
- [ ] Neo4jなど重いGraph DBの導入
- [ ] LLMによる全自動Entity抽出
- [ ] Graphだけを根拠にした契約書判断
- [ ] Dating側の本番DB/Firebase/AGO/決済への接続

#### 受け入れ条件

- [ ] `docs/local-context-core-roadmap.ja.md` に設計がまとまっている
- [ ] Knowledge Layer MVPとの境界が明確
- [ ] Graph導入がSQLiteから始まる
- [ ] 原文根拠を必ず保持する方針が明記されている
- [ ] scope定義が明記されている
- [ ] Entity/Relationより前に `ContextRecord` が定義されている
- [ ] `context()` は削除済み、期限切れ、別scopeの記憶を返さない
- [ ] 契約書、会社資料の回答では必ず原文snippet/source/pageを返す
- [ ] `profile()` は安定事実と最近の活動を混ぜない
- [ ] `remember()` はセンシティブ情報を自動保存しない、または保存前確認に回す
- [ ] Dating reality showで再利用する対象/しない対象が明記されている
- [ ] 既存機能を壊す実装に進んでいない

### Task 8.5: Agent-Reach参考のInternet Layer設計

目的: Agent-Reachの「AI Agentに外部調査能力を追加する」考え方を参考にし、TOMOSのInternet Layer候補として整理する。

このタスクでは、Agent-Reach本体を直接同梱しない。
まず、CodeGraph、Knowledge Layer、Memoryと分けた外部調査レイヤーとして扱う。

#### まず作る設計メモ

- [ ] Agent-ReachをInternet Layer候補としてdocsに追記する
- [ ] Internet LayerをCodeGraph、Knowledge Layer、Memoryと分ける
- [ ] Web、GitHub、YouTube字幕、RSS、Reddit、Xなどを調査チャンネルとして整理する
- [ ] `doctor` 的な接続診断を、将来のPC診断/プラグイン診断へ接続できるようにする
- [ ] Cookieやログイン状態を使う機能は、標準ONにしない方針を書く

#### MVPの実装順

1. docs反映
   - [ ] Internet Layerの責務を明記する
   - [ ] Agent-Reachは設計参考または任意プラグイン候補として扱う
   - [ ] 外部調査結果をMemoryへ自動保存しない

2. 調査チャンネル設計
   - [ ] Webページを読む
   - [ ] GitHubリポジトリを調べる
   - [ ] YouTube字幕を要約する
   - [ ] RSSを読む
   - [ ] Reddit/XなどSNS系は権限と利用規約確認後に扱う

3. 診断設計
   - [ ] 利用可能なチャンネルを表示する
   - [ ] 未設定、未インストール、ログイン必要、利用不可を分けて表示する
   - [ ] ユーザーが次に何をすればよいかを短く出す

#### やらないこと

- [ ] Agent-Reach本体の即時同梱
- [ ] Cookieやログイン状態の無断利用
- [ ] 外部サイトへの投稿、フォーム送信、操作自動化
- [ ] 外部調査結果のMemory自動保存
- [ ] 社内資料、教材パック、契約書と外部検索結果の自動混合

#### 受け入れ条件

- [ ] Agent-Reachの位置づけがInternet Layerとして明記されている
- [ ] Knowledge Layer、Memory、CodeGraphとの境界が明確
- [ ] 標準同梱ではなく任意プラグイン候補として扱われている
- [ ] Cookie、ログイン、SNS利用は明示許可制になっている
- [ ] 外部調査結果を勝手に長期記憶へ保存しない方針が明記されている

### Task 9: 人物・関係メモアプリ設計

目的: Monicaの考え方を参考に、友達、恋愛、家族、仕事の人物情報をローカルに保存し、相性メモと返信支援に使えるアプリを設計する。

このタスクでは、外部SNS連携やLINE/Discord送信までは実装しない。
まずTOMOS内の人物データ、関係データ、チャット返信支援への接続点を定義する。

#### まず作る設計メモ

- [ ] `docs/person-relationship-app-roadmap.ja.md` を作る
- [ ] アプリ枠として扱い、プラグイン枠にしない理由を書く
- [ ] 友達、恋愛、家族、仕事の4カテゴリを固定する
- [ ] 登録項目を自分の情報、姓名、表示名、呼び名、写真、関係、詳細関係、生年月日、性別、血液型、MBTI、自分との関係メモに絞る
- [ ] MBTIは公式診断ではなく、任意入力の16タイプメモとして扱う
- [ ] 送り先を選んで返信文を作る導線を書く
- [ ] Discord、LINE、Slack、メールなどのプラグインが人物データを参照する境界を書く

#### MVPの実装順

1. 人物プロフィール
   - [ ] 人物一覧を表示する
   - [ ] 人物を追加、編集、削除できる
   - [ ] 自分の情報を登録し、関係図の中心に表示する
   - [ ] 写真はローカル保存またはブラウザ保存から始める
   - [ ] MBTI表記を避け、画面では `MBTI` と表示する

2. 関係メモ
   - [ ] 関係カテゴリは `友達`、`恋愛`、`家族`、`仕事` にする
   - [ ] 子供、配偶者、上司、取引先などの詳細関係を選べるようにする
   - [ ] 自分との関係、距離感、注意点をメモできる
   - [ ] 自動推測した情報は保存前確認に回す

3. 相性メモ
   - [ ] 登録情報から会話のコツを表示する
   - [ ] 断定的な相性診断ではなく、参考メモとして表示する
   - [ ] 採用、評価、医療、法的判断に使わない注意を内部仕様に入れる

4. チャット返信支援
   - [ ] チャット入力の補助で `送り先` を選べるようにする
   - [ ] 選んだ人物の詳細関係、自分との関係メモ、MBTI参考を文脈に入れる
   - [ ] 個人情報を過剰にプロンプトへ渡さない
   - [ ] 返信案は送信せず、ユーザーが確認して使う

5. Context Core連携
   - [ ] 人物は `ContextEntity` の `person` として扱う
   - [ ] 関係は `ContextRelation` として扱う
   - [ ] Relation typeに `friend`、`romantic_interest`、`family`、`work_contact` を追加候補にする
   - [ ] `scopeType` は個人利用なら `user`、仕事利用なら `company` または `project` に分ける

#### やらないこと

- [ ] 外部SNSへの自動送信
- [ ] 公式診断としての提供
- [ ] 他人の属性の自動断定保存
- [ ] 採用、評価、医療、法的判断への利用
- [ ] クラウド同期前提の設計

#### 受け入れ条件

- [ ] 人物・関係メモがアプリ枠として定義されている
- [ ] 友達、恋愛、家族、仕事の4カテゴリが明記されている
- [ ] プラグインは人物データを参照する側として整理されている
- [ ] チャット返信支援で送り先を選ぶ導線が明記されている
- [ ] MBTIの扱いが断定や公式診断になっていない
- [ ] Local Context Coreとの接続点が明記されている

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
