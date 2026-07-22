# Local Context Core Roadmap

目的: TOMOSのKnowledge Layer、Memory、Profile、Graph、CodeGraph、契約書管理、キャラクター記憶を、将来的に1つのContext APIで扱えるようにする。

Supermemoryは設計参考に留める。TOMOSではローカル実行、SQLite、原文根拠、プロジェクト横断利用を優先する。

## 判断

- Supermemory本体は直接組み込まない。
- まず既存のSQLite/n-gram Knowledge Layerを完成させる。
- 次にEntity/RelationをSQLiteで追加する。
- Graph DB、外部Memory API、全自動LLM抽出は後段にする。
- Dating reality showにも使いやすいよう、UI/DB/provider非依存の型とadapter境界を守る。

## 基本概念

```text
RAG
= 文書chunkや原文箇所を探す

Memory
= ユーザー、キャラクター、作業、好み、期限付き事実を覚える

Profile
= 安定した事実と最近の活動をまとめる

Graph
= 人物、会社、契約、文書、コード、キャラクターの関係をつなぐ

Context
= AIへ渡す最小文脈を組み立てる

Internet Layer
= Web、GitHub、YouTube字幕、RSS、SNSなどの外部公開情報を調べる
```

## Internet Layerとの境界

Agent-Reachの考え方は、Internet Layerの設計参考として扱う。
ただし、Local Context CoreやMemoryとは責務を分ける。

- Internet Layerは外部公開情報を読む、検索する、要約する。
- Knowledge Layerはローカル資料、PDF、契約書、教材、会社資料を扱う。
- Memoryはユーザー、キャラクター、好み、作業履歴を保存する。
- CodeGraphはローカルコード構造を扱う。
- Internet Layerの取得結果は、ユーザー確認なしでMemoryへ保存しない。
- Cookie、ログイン状態、SNS閲覧は任意設定かつ明示許可制にする。
- Dating scopeでは、外部調査結果とキャラクター記憶を自動混合しない。

## 最小API

```text
search(query, scope)
remember(item, scope)
forget(id, reason)
profile(scope)
context(query, scope)
```

最初はHTTP APIではなく、サーバー内部moduleとして実装する。

## Scope定義

記憶や検索結果が個人用、会社用、Dating用で混ざらないよう、先にscopeを固定する。

```text
ContextScope
- scopeType     global / user / folder / project / character / studyPack / app / company
- scopeId
- ownerType     user / company / app / character
- ownerId
- visibility    private / shared / internal
- projectId
```

ルール:

- `scopeType` と `scopeId` は必須にする。
- `ownerType` と `ownerId` は、誰の管理下にある記憶かを示す。
- `visibility` は共有範囲を示し、検索時のフィルタに使う。
- Dating側のキャラ記憶は `scopeType: character` を基本にする。
- 会社文書や契約書は `scopeType: company` または `project` を基本にする。

## ContextRecord共通型

Entity/Relationへ進む前に、まず全データの出どころをそろえる。

```text
ContextRecord
- id
- recordType    document / memory / profile / entity / relation / code / contract / character
- sourceType    file / chat / mobile / knowledge / contract / codegraph / character / simulation
- sourceId
- sourcePath
- page
- snippet
- confidence
- scope
- createdAt
- updatedAt
- deletedAt
- deleteReason
- hardDeleteEligible
```

ルール:

- `sourceType`、`sourceId`、`scope` は必須にする。
- 契約書、会社資料、PDF由来の回答では `sourcePath`、`page`、`snippet` をできる限り残す。
- `deletedAt` は論理削除、`hardDeleteEligible` は将来の物理削除候補を示す。
- MVPでは物理削除を実装しなくてよいが、設計上は逃げ道を残す。

## 実装順

### Phase 1: Knowledge Layerを安定させる

- [ ] SQLite/n-gram検索を維持する
- [ ] 検索結果に `ContextRecord` として `sourcePath`、`page`、`snippet`、`sourceType`、`scope` を残す
- [ ] AI回答へ渡す文脈を上位3〜5件に制限する
- [ ] 契約書や会社資料では原文根拠を必ず表示する

### Phase 2: ContextRecord Layer

- [ ] Knowledge Layer、キャラクター記憶、学習セット、契約書管理の保存結果を `ContextRecord` として読めるようにする
- [ ] 既存DBをすぐ移行せず、まずadapterで共通形式へ変換する
- [ ] `scopeType`、`scopeId`、`ownerType`、`ownerId`、`visibility`、`projectId` を検索条件として使えるようにする
- [ ] `context()` は削除済み、期限切れ、別scopeのrecordを返さない

### Phase 3: Entity Layer

- [ ] `context_entities` をSQLiteに追加する
- [ ] Entity typeは `person`、`company`、`project`、`document`、`contract`、`repository`、`character` から始める
- [ ] `name`、`aliases`、`sourceType`、`sourceId`、`confidence`、`scope` を持たせる
- [ ] 最初はファイル名、CSV列、契約書候補、明示保存された記憶から抽出する

### Phase 4: Relation Layer

- [ ] `context_relations` をSQLiteに追加する
- [ ] Relation typeは `mentions`、`belongs_to`、`works_on`、`relates_to`、`source_of`、`supersedes` から始める
- [ ] `fromEntityId`、`toEntityId`、`relationType`、`sourceId`、`snippet`、`confidence`、`deletedAt` を明記する
- [ ] Relationの向きは `fromEntityId -> relationType -> toEntityId` として固定する
- [ ] 誤抽出を消せるように `deletedAt`、`deleteReason`、`hardDeleteEligible` を持たせる

### Phase 5: Memory/Profile Layer

- [ ] Memory typeを `fact`、`preference`、`activity`、`temporary` に分ける
- [ ] Memory statusを `active`、`expired`、`superseded`、`deleted`、`conflict` に分ける
- [ ] 期限付き記憶には `expiresAt` を持たせる
- [ ] 矛盾する記憶は上書きせず、`supersedes` で追跡する
- [ ] `profile()` は安定事実と最近の活動を分けて返す
- [ ] `remember()` はセンシティブ情報を自動保存せず、保存前確認に回す

### Phase 6: Unified Context API

- [ ] `search()` はKnowledge Layer、Memory、CodeGraph、Contractを横断する
- [ ] `remember()` はキャラクター記憶、学習セット、スマホ取り込み、明示保存へ橋渡しする
- [ ] `forget()` は論理削除から始め、将来の物理削除候補として `hardDeleteEligible` を扱う
- [ ] `context()` はAIへ渡す文脈を最小化する

## Dating reality showでの再利用

Dating側では、Local Context Coreをキャラクター再現性のために使う。
`@tomos-ai/character-core` と同じく、UI、Firebase、DB、LLM providerには依存させない。

使う対象:

- キャラクター記憶
- 口調候補
- 理想返答/NG返答
- Prompt version
- AI同士模擬チャット評価
- キャラ同士の口調混線チェック
- ユーザーとの関係段階

使わない対象:

- 契約書管理
- 会社資料検索
- 社内専用教材パック
- 本番DB/Rules/Secrets
- 決済/AGO/Firebase固有処理

Dating側エンジニアへの指示:

- [ ] 既存の `packages/character-core/` とは別に、Context Coreへ依存しすぎない
- [ ] まず `ContextEntity`、`ContextRelation`、`ContextMemory` の型だけ合わせる
- [ ] キャラ記憶は `scopeType: character`、`sourceType: character` または `chat` として扱う
- [ ] AI同士模擬チャット評価は `sourceType: simulation` として扱う
- [ ] 実キャラ、実ユーザー、権利キャラのsampleを共通packageに入れない

## 人物・関係メモアプリでの利用

人物・関係メモアプリでは、Local Context Coreを人物プロフィールと関係性の保存に使う。
Monicaの思想を参考にするが、TOMOSではローカル保存、返信支援、プラグイン参照を優先する。

使う対象:

- 友達
- 恋愛
- 家族
- 仕事
- 自分のプロフィール
- 人物プロフィール
- 自分との詳細関係
- 自分との関係メモ
- 関係図
- 送り先別の返信支援

ContextEntity:

- `entityType: person`
- `name`
- `firstName`
- `lastName`
- `displayName`
- `aliases`
- `photoRef`
- `birthdate`
- `gender`
- `bloodType`
- `personalityType`
- `personalityTypeSource`
- `notes`
- `scope`

ContextRelation:

- `fromEntityId`: 自分または所有者
- `toEntityId`: 登録した人物
- `relationType`: `friend`、`romantic_interest`、`family`、`work_contact`
- `relationDetail`: `child`、`spouse`、`manager`、`client` など
- `snippet`: 関係メモ
- `confidence`
- `scope`

制約:

- [ ] MBTIは公式診断として扱わない
- [ ] MBTIの根拠は `self_reported`、`user_reported`、`estimated`、`unknown` に分ける
- [ ] AIが他人の属性を勝手に確定保存しない
- [ ] 保存前確認なしにセンシティブ情報を `remember()` しない
- [ ] チャット返信支援では必要な人物メモだけを `context()` に渡す
- [ ] 採用、評価、医療、法的判断には使わない

## やらないこと

- Supermemory本体の組み込み
- 外部Memory API依存
- Neo4jなど重いGraph DBの導入
- LLMによる全自動Entity抽出
- Graphだけを根拠にした契約書判断
- Dating側の本番DB/Firebase/AGO/決済への接続

## 受け入れ条件

- [ ] 既存Knowledge Layer MVPを壊していない
- [ ] 原文根拠を保持する方針が明記されている
- [ ] SQLiteから始める設計になっている
- [ ] `scopeType`、`scopeId`、`ownerType`、`ownerId`、`visibility`、`projectId` の扱いが明記されている
- [ ] Entity/Relationより前に `ContextRecord` 共通型が定義されている
- [ ] `search()` / `remember()` / `forget()` / `profile()` / `context()` の責務が分かれている
- [ ] `context()` は削除済み、期限切れ、別scopeの記憶を返さない
- [ ] Dating scopeでは社内専用教材、契約書、会社資料が返らない
- [ ] 契約書、会社資料の回答では必ず原文snippet/source/pageを返す
- [ ] `profile()` は安定事実と最近の活動を混ぜない
- [ ] `remember()` はセンシティブ情報を自動保存しない、または保存前確認に回す
- [ ] Dating reality showで再利用する範囲としない範囲が明確
