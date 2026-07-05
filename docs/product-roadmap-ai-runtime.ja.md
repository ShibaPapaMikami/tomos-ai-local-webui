# まなびパル Product Roadmap: Local AI Runtime

目的: まなびパルを単なるAIチャットアプリではなく、Windows/Macで動くローカルAI Runtimeとして育てる。

この文書は、エンジニアと学習パック制作担当が同じ方向で進めるための上位ロードマップです。
実装の細かい分割は `docs/refactor-roadmap.ja.md` を参照してください。
直近スプリントの実行指示は `docs/sprint-2026-06-28-ai-runtime.ja.md` を参照してください。

## 基本方針

- ユーザー向けの顔は「まなびパル / AIバディ」のままにする。
- 内部設計は「Local AI Runtime」として作る。
- 将来の法人向け説明では「Company Memory OS」を使えるようにする。
- Knowledge Graphまで育った段階では、法人向け説明を「Company Knowledge OS」へ広げる。
- `AI OS` という言葉は、現時点では一般ユーザー向けUIに出さない。
- 学生・個人・小規模チームが、モデル、記憶、教材パック、フォルダー、プラグインを組み合わせて使える基盤にする。

## ポジション

```text
ユーザー向け:
まなびパル = 学習・作業・生活を助けるAIバディ

内部設計:
Local AI Runtime = モデル、記憶、教材、プラグイン、フォルダーをつなぐ実行基盤

将来の法人向け:
Company Memory OS = 社内文書、MVV、議事録、名簿、契約書、業務知識を扱うローカル記憶基盤

将来の拡張:
Company Knowledge OS = コード、契約書、PDF、メール、Slack、GitHub、人物、プロジェクトを原文根拠つきでつなぐローカル知識基盤
```

## 採用する考え方

- Any Model: Gemma、Qwen、Mistral、OpenAI、Claudeなどを用途別に選べる構造にする。
- Memory: チャット履歴だけではなく、ユーザー、作業、教材、会社文脈を記憶する。
- Knowledge: PDF、Markdown、CSV、Excel、議事録、契約書などを検索・要約・参照できるようにする。
- Folder: ローカルフォルダーを読み、必要な文脈だけAIに渡せるようにする。
- Plugin: CodeGraphなどの追加機能を、アプリ本体と分けて導入できるようにする。
- Study Pack: 学習・社内ルール・文章規範を読み取り専用パックとして配布できるようにする。
- Smartphone PWA: スマホ単体でメモ・学習ノートを使い、PCにはQR/コードで取り込む。
- Unified Context API: ユーザーは `search()` / `remember()` / `forget()` / `profile()` / `context()` だけを意識し、裏側で資料検索、記憶、CodeGraph、OCR、Graphを切り替える。

### PilotDeckを参考にする範囲

PilotDeckは、WorkSpace、Memory、Plugin/MCP、Routingの考え方が近い。
ただしAGPL-3.0のコードを直接取り込まず、設計上の参考に留める。

採用する考え方:

- WorkSpace単位: フォルダー、アプリ、教材、記憶を作業単位で分ける。
- White-box Memory: 記憶はブラックボックスにせず、ユーザーが読める、編集できる、忘れられる形にする。
- Smart Routing: 用途に応じて標準、コード、資料検索、契約書、キャラクター向けモデルを選びやすくする。
- Plugin/MCP境界: アプリ本体、アプリ機能、プラグイン、外部ツール連携を混ぜない。

採用しないもの:

- PilotDeck本体コードの組み込み
- 常駐・自律実行エージェント
- クラウドLLM前提のルーティング
- ユーザー確認なしのファイル操作

### Supermemoryを参考にする範囲

Supermemoryは、Memory、User Profile、Hybrid Search、Connectors、File Processingを1つのContext APIで扱う考え方が近い。
ただしTOMOSでは、クラウドMemory APIを中核にせず、ローカルSQLite、原文根拠、CodeGraph、将来のGraph Layerを優先する。

採用する考え方:

- MemoryとRAGを分ける: 文書chunk検索と、ユーザー/作業/期限付き事実の記憶を同じものとして扱わない。
- User Profile: 安定した事実、最近の作業、好みを分けて保持する。
- Hybrid Search: 文書検索、記憶検索、プロフィール、コード理解を1つの検索体験にまとめる。
- Automatic Forgetting: 一時的な情報、期限切れ情報、矛盾した情報を永久記憶にしない。
- Container Scope: 個人、フォルダー、プロジェクト、キャラクター、会社単位で記憶を分離する。

採用しないもの:

- Supermemory本体の直接組み込み
- 最初から外部クラウドMemory APIに依存する設計
- 最初から重いGraph DBを必須にする設計
- 原文根拠なしで抽出したGraphだけを信じる設計

## すぐには採用しないもの

- UI-TARSによるPC操作
- 常駐エージェント
- AIAvatarKitなどの本格アバター
- 音声秘書の完全実装
- カレンダー/メールの深い外部連携
- 契約書AIの高度な自動判断
- クラウド同期
- 複数PC間同期

これらは将来の上位レイヤーに置く。
初期実装では、記憶、教材、フォルダー、プラグイン、スマホPWAの安定を優先する。

## フェーズ

### Phase 1: ManabiPal Core

対象: 学生・個人向けの基本体験。

- [ ] アプリ表示名を `まなびパル / ManabiPal` に統一する
- [ ] モデル名としての `Gemma 4 12B` は残し、サービス名とは分ける
- [ ] チャット、モデル切替、キャラクター設定を安定させる
- [ ] 学習セットを独立パネルで扱う
- [ ] 学習セットを読めるノートとして表示する
- [ ] 教材パックを追加・有効化できるようにする
- [ ] キャラクター記憶を確認・編集・削除できるようにする
- [ ] スマホPWAでチャットメモ、学習ノート、キャラ設定を使えるようにする
- [ ] PCへのQR/コード取り込みを実装する

### Phase 2: Local AI Runtime

対象: モデル、記憶、プラグイン、フォルダーをつなぐ実行基盤。

- [ ] モデル一覧を用途別に見せる
- [ ] `標準`、`高速`、`コード標準`、`会話・キャラ向け` の役割を持たせる
- [ ] 軽量標準モデル候補に `Qwen/Qwen3-4B-Instruct-2507` を入れる
- [ ] コード標準モデル候補に `qwen2.5-coder:14b` を入れる
- [ ] 会話・キャラ向け候補に `mistral-nemo:12b` を入れる
- [ ] 任意上級者向け候補に `dolphin-mistral:7b` を置く
- [ ] CodeGraphを最初のプラグインとして扱う
- [ ] CodeGraphの表示名は `コード理解` にする
- [ ] フォルダー単位でプラグインON/OFFを扱う
- [ ] 記憶と設定は将来的にSQLiteへ移せる構造にする
- [ ] `localStorage` の既存キーは壊さず、移行は段階的に行う
- [ ] 記憶、資料、契約書、スマホ取り込みデータに `sourceType`、`sourceId`、`scopeType` を持たせる
- [ ] `global`、`folder`、`character`、`studyPack`、`app` のスコープをUIで見分けられるようにする
- [ ] モデル選択に用途ラベルを持たせ、実験モデルや大人モード用モデルは自動選択しない

### Phase 3: Knowledge Layer

対象: 学習・社内文書・個人資料を扱う知識基盤。

- [ ] コードはCodeGraph、文書・契約書・名簿・PDFはKnowledge Layerとして分ける
- [ ] 日本語検索はSQLite FTS5単体に依存せず、trigram/n-gram検索をMVPから入れる
- [ ] ファイルパス、更新日時、ファイルサイズ、ハッシュを保存し、変更があったファイルだけ再処理する
- [ ] TXT/MD/PDFテキスト抽出を最初に扱う
- [ ] 検索結果をAI回答へ早めに接続し、ユーザー価値を確認する
- [ ] CSV/ExcelはVector DBではなくSQLiteテーブル化する
- [ ] 契約書は最初は本文検索、後段でMarkdown化、条項分割、重要項目JSON抽出を追加する
- [ ] 契約書のJSON抽出結果だけを信じず、必ず原文該当箇所も一緒に保存・表示する
- [ ] 議事録はテキスト保存から始め、音声認識と要約は後段にする
- [ ] RAG/Embeddingは後から差し込める構造にする
- [ ] LanceDBなどのVector DBは、SQLite/n-gram全文検索で足りなくなってから検討する

#### Knowledge Layer MVP

最初のMVPは、ローカル資料を素早く探せることを優先する。

```text
ローカルフォルダー
↓
ファイル一覧取得
↓
拡張子判定
↓
本文抽出
↓
SQLiteに保存
↓
FTS / n-gram検索
↓
関連箇所だけAIへ渡す
```

MVPで保存するメタデータ:

- ファイルパス
- 更新日時
- ファイルサイズ
- ハッシュ
- 抽出状態
- 抽出エラー
- 最終索引化日時

MVPのUI:

```text
[ ] 資料検索を使う
    このフォルダー内のPDF、テキスト、CSVを検索できるようにします。
    [準備する] [再準備]

最終更新: 2026/xx/xx xx:xx
登録ファイル数: 128件
検索可能テキスト: 125件
失敗: 3件
```

対象別処理:

| 対象 | 最初の処理 | 後で追加 |
| --- | --- | --- |
| TXT / MD | そのまま抽出 | なし |
| PDF | テキスト抽出 | OCR |
| 画像PDF | 最初は対象外でも可 | OCR |
| CSV | SQLiteテーブル化 | 列意味推定 |
| Excel | SQLiteテーブル化 | 複数シート対応 |
| 契約書 | 本文検索 | JSON抽出 |
| 議事録 | テキスト保存 | 音声認識 |
| コード | 対象外 | CodeGraph連携 |

Knowledge Layerの段階:

1. ファイル一覧 + メタデータ保存
2. TXT / MD / PDFテキスト抽出
3. SQLite FTS / n-gram検索
4. 検索結果をAI回答に接続
5. CSV / ExcelをSQLite化
6. OCR対応
7. 契約書JSON抽出
8. Embedding / LanceDB

契約書の後段設計:

```text
契約書PDF
↓
テキスト/OCR
↓
Markdown化
↓
条項ごとに分割
↓
重要項目をJSON抽出
↓
原文位置も保存
```

契約書で抽出する候補項目:

- 契約先
- 契約開始日
- 契約終了日
- 自動更新
- 解約通知期限
- 秘密保持
- 成果物帰属
- 損害賠償
- 再委託
- 準拠法
- 反社条項

名簿の扱い:

- CSV/ExcelからSQLiteテーブルへ取り込む
- 部署、名前、メール、役職で正確検索する
- 名簿は意味検索より正確検索を優先し、Vector DBへ入れない

### Phase 3.5: Local Context Core / Memory Graph

対象: Knowledge Layer、キャラクター記憶、学習セット、契約書管理、CodeGraphを1つのContext APIで扱う共通基盤。

この段階はSupermemoryの思想を参考にするが、TOMOSではローカル実行、SQLite、原文根拠、プロジェクト横断利用を優先する。
まずはGraph DBを入れず、SQLiteテーブルでEntity/Relationを表現する。

- [ ] `search()` で文書、記憶、プロフィール、コード理解、契約書を横断検索できる設計にする
- [ ] `remember()` でユーザーの明示保存、キャラクター記憶、スマホ取り込み、学習セット候補を保存できる設計にする
- [ ] `forget()` で記憶、期限切れ情報、誤った抽出、不要な関係を削除または論理削除できる設計にする
- [ ] `profile()` で安定した事実、最近の活動、好み、作業中プロジェクトを分けて返す
- [ ] `context()` でAIへ渡す最小文脈だけを組み立てる
- [ ] Entity抽出は `person`、`company`、`project`、`document`、`contract`、`repository`、`character` から始める
- [ ] Relationは `mentions`、`belongs_to`、`works_on`、`relates_to`、`source_of`、`supersedes` から始める
- [ ] Graphは抽出結果だけを信じず、必ず `sourcePath`、`page`、`snippet`、`sourceType` を残す
- [ ] 期限付き記憶には `expiresAt` を持たせ、期限切れ後に `profile()` へ混ぜない
- [ ] 矛盾する記憶には `supersedes` または `replaces` を持たせ、古い情報を上書きせず追跡できるようにする

#### Dating reality show との共通化

Local Context Coreは、まなびパル/TOMOS本体だけでなく、Dating reality showのキャラクター再現性にも使えるようにする。
Dating側では `@tomos-ai/character-core` と同じ考え方で、UI、Firebase、DB、LLM providerに依存しない軽量packageまたはadapterとして扱う。

Dating側で使う対象:

- キャラクター記憶
- 口調候補
- 理想返答/NG返答
- Prompt version
- AI同士模擬チャット評価
- キャラ同士の口調混線チェック
- ユーザーとの関係段階

Dating側で使わないもの:

- 契約書管理
- 会社文書検索
- 本番DB/Rules/Secrets
- 決済/AGO/Firebase固有処理

### Phase 4: Agent Layer

対象: 承認付きでファイル生成・コード修正・作業支援を行う。

- [ ] Aider/OpenCodeはプラグイン候補として扱う
- [ ] 最初から中核に入れない
- [ ] コード修正はユーザー確認つきにする
- [ ] ファイル保存や削除は確認を必須にする
- [ ] 作業ログを残す
- [ ] CodeGraphと連携して、影響範囲確認やコード説明を行う

### Phase 5: Company Memory OS / Company Knowledge OS

対象: 社内利用、企業文書、MVV、部署別ルール。

- [ ] 社内用教材パックをprivate教材として扱う
- [ ] メール、Slack、依頼文、報告文、外部送信前チェックをモード化する
- [ ] 学習セットにたまった修正例を、担当者レビュー後に教材パックへ反映する
- [ ] 社内文書は匿名化と機密情報除去を必須にする
- [ ] 部署別パック、共有学習セット、権限管理は後段で検討する
- [ ] 人物、会社、プロジェクト、契約書、Slack、メール、GitHubの関係をGraphとして扱う
- [ ] Graphの表示では、必ず元文書、元メッセージ、元ファイルへの参照を出す
- [ ] 企業向け名称は、Memory中心なら `Company Memory OS`、文書/人物/契約/コードまで扱う段階では `Company Knowledge OS` を使う

### Phase 6: Personal JARVIS

対象: 音声、PC操作、アバター、外部連携。

- [ ] 音声入力・読み上げを整理する
- [ ] 常駐音声秘書は後回しにする
- [ ] PC操作AIは危険度が高いため、承認付きの限定機能から検討する
- [ ] アバターは画像アイコンとキャラ表示を安定させてから検討する
- [ ] カレンダー/メール連携はクラウドや認証が絡むため後回しにする

## エンジニア向け指示

### 優先順位

1. 既存データを壊さない。
2. 学習セット、教材パック、キャラクター記憶を独立した概念として維持する。
3. プラグインはアプリ本体に混ぜず、追加機能として扱う。
4. スマホはクラウド同期ではなく、単体PWA + PC QR取り込みにする。
5. `AI OS` として広げすぎず、まずLocal AI Runtimeの土台を小さく作る。
6. PilotDeck的な発想は、まず「見える記憶」「WorkSpace単位」「用途別モデル選択」だけを小さく入れる。
7. 常駐エージェント、バックグラウンド自律実行、外部MCP連携は安定後に回す。
8. Supermemory的な発想は、まず「RAGとMemoryの分離」「Profile」「Hybrid Search」「忘れる機能」だけを小さく入れる。
9. Graphは最終形だが、MVPではSQLite/n-gram検索と原文根拠を優先する。

### アーキテクチャ上の分離

```text
Model Runtime
- Ollama
- llama.cpp/MLXは将来候補

Memory
- チャット履歴
- 学習セット
- キャラクター記憶
- 将来SQLiteへ移行可能にする

Knowledge
- 教材パック
- ローカル文書
- CSV/Excel/PDF/Markdown

Context Core
- Unified Context API
- Memory Graph
- Entity/Relation
- Profile
- Automatic forgetting

Plugins
- CodeGraph
- 将来 Aider/OpenCode
- 将来 MCP

UI
- PC Web
- Smartphone PWA
- 将来 Tauri/Electron
```

### WorkSpaceとMemoryの最小データ方針

PilotDeckを参考に、記憶や取り込みデータには出どころと有効範囲を必ず持たせる。
これにより、キャラクター記憶、教材パック、学習セット、契約書、スマホ取り込みが混ざる事故を防ぐ。

推奨フィールド:

```text
id
sourceType    chat / character / studyPack / learningSet / knowledge / contract / mobile
sourceId
scopeType     global / folder / character / studyPack / app
scopeId
title
content
createdAt
updatedAt
pinned
archived
deletedAt
```

注意:

- 削除は可能なら `deletedAt` による論理削除から始める。
- 重要な記憶は `pinned` で保護できるようにする。
- 契約書、会社資料、スマホ取り込みは、必ず元データや確認元を表示できるようにする。
- 自動保存された記憶は、ユーザーが後から一覧で確認・修正・削除できることを必須にする。

### Local Context Coreの最小API方針

SupermemoryのOne API思想を参考にするが、TOMOSではローカル実行と原文根拠を優先する。
最初はHTTP API化せず、サーバー内部関数または小さなmoduleとして始める。

推奨API:

```text
search(query, scope)
remember(item, scope)
forget(id, reason)
profile(scope)
context(query, scope)
```

scope定義:

```text
scopeType     global / user / folder / project / character / studyPack / app / company
scopeId
ownerType     user / company / app / character
ownerId
visibility    private / shared / internal
projectId
```

最小データ:

```text
records
- id
- recordType    document / memory / profile / entity / relation / code / contract / character
- sourceType
- sourceId
- sourcePath
- page
- snippet
- confidence
- scope
- deletedAt
- deleteReason
- hardDeleteEligible

entities
- id
- type          person / company / project / document / contract / repository / character
- name
- aliases
- sourceType
- sourceId
- confidence
- scope

relations
- id
- fromEntityId
- relationType  mentions / belongs_to / works_on / relates_to / source_of / supersedes
- toEntityId
- sourceType
- sourceId
- snippet
- confidence
- deletedAt
```

注意:

- MVPではSQLiteで始める。Neo4jなどのGraph DBは入れない。
- Entity/Relationへ進む前に、まず `ContextRecord` 共通型で出どころ、scope、原文根拠をそろえる。
- `expired` と `contradiction` はMemory typeではなくstatusとして扱う。
- `forget()` はMVPでは論理削除でよいが、将来の物理削除候補として `hardDeleteEligible` を持たせる。
- Graph抽出は検索補助であり、契約書や社内資料の最終判断には使わない。
- Dating reality showにも使えるよう、Context CoreはUI/DB/provider非依存のadapter境界を持つ。
- キャラクター記憶と会社文書Graphは同じAPI思想で扱うが、保存先とスコープは必ず分ける。

### 実装時の注意

- `gemma4.*` のlocalStorageキーは当面維持する。
- 新しい保存構造へ移行する場合は、読み取り互換と一回限りのコピー処理を入れる。
- 教材パック本体は読み取り専用にする。
- `修正して学習` は教材パックではなく、学習セットへ保存する。
- スマホ側にはAPIキー、PCのOSパス、ローカルファイル全文、CodeGraph内部データを渡さない。
- CodeGraphの削除や `.codegraph/` 削除は確認を必須にする。
- 大人モードは初期OFF、18歳以上確認、禁止ルール付きにする。
- 契約書管理は「アプリ」として扱い、PDF/OCR/CodeGraphのような差し替え部品は「プラグイン」または「エンジン」として扱う。
- 用途別モデル選択は最初はルールベースでよい。自動ルーティングは、実験モデルや大人モード用モデルを勝手に選ばない。
- `Qwen/Qwen3-4B-Instruct-2507` は軽量標準モデルとして扱う。学生PC、資料検索、学習パック利用の候補に入れるが、コード標準は引き続き `qwen2.5-coder:14b` を優先する。

### 直近の実装候補

- [ ] `docs/refactor-roadmap.ja.md` の未完了項目を小さく進める
- [ ] 教材パックの有効化とモード選択を安定させる
- [ ] CodeGraphの状態表示とSafari QAを固める
- [ ] スマホ単体PWAの保存とPC取り込みを実装する
- [ ] キャラクター記憶の一覧/編集/削除を整える
- [ ] モデル一覧に用途ラベルを追加する
- [ ] 記憶と取り込みデータにスコープ表示を追加する
- [ ] Local Context Coreの `search()` / `remember()` / `forget()` / `profile()` / `context()` の設計メモを作る
- [ ] Dating reality showでも使えるよう、Context Coreの型とAPIをUI/DB/provider非依存に保つ

## 学習パック制作担当向け指示

### 役割

学習パック制作担当は、AIモデルを学習させるのではなく、AIが参照する読み取り専用の教材パックを作る。

教材パックは以下をまとめる。

- 目的
- 対象ユーザー
- 使う場面
- モード
- 文章ルール
- 用語集
- 禁止事項
- 良い例/悪い例
- 出典/ライセンス/社内利用条件

### 最初に作るパック


目的:

- 依頼、相談、報告、謝罪、お礼、外部送信前チェックを支援する
- 冷たすぎず、回りくどすぎず、相手が次に何をすればよいか分かる文章にする

### 推奨フォルダー構成

```text
  pack.json
  README.md
  mvv.md
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

### 制作ルール

- 実メール、実Slackは必ず匿名化する。
- 個人名、会社名、クライアント名、金額、契約情報、未公開プロジェクト名、URL、APIキー、パスワード、個人情報は入れない。
- 良い例/悪い例は、可能なら自作のサンプルにする。
- 迷う情報は入れず、社内確認する。
- 既存GitHub/Gistの文章規範は参考に留め、ライセンス不明の本文をそのままコピーしない。
- 修正例や好みは教材パック本体ではなく、まず学習セットへ保存する。
- 学習セットに良い修正例がたまったら、担当者がレビューして教材パックへ反映する。

### v0.1 完成条件

- [ ] `pack.json` がある
- [ ] `mvv.md` がある
- [ ] `tone-guide.md` がある
- [ ] `avoid-phrases.md` がある
- [ ] 5つのモードがある
- [ ] Slack例が3件ある
- [ ] メール例が3件ある
- [ ] 禁止事項が書かれている
- [ ] 実データが匿名化されている
- [ ] `visibility` が `private` になっている

## 判断基準

迷った時は以下を優先する。

1. ローカルで動くこと。
2. 学生・個人が分かるUIであること。
3. 企業利用でも機密情報を守れること。
4. 既存データを壊さないこと。
5. 大きな機能はプラグインまたは後段フェーズに逃がすこと。
