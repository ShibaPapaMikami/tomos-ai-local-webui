# TOMOS Markdown Skill Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Complete Gate 3 before starting.

**Goal:** 個人や会社の仕事の進め方を、安全に版管理、評価、承認できるMarkdownベースのSkill Managerとして実装する。

**Architecture:** 人が読む `SKILL.md` を指示内容の正本にし、SQLiteは検索索引、評価履歴、承認履歴だけを持つ。初期版はSkillを通常チャットやPluginへ自動適用せず、local LLMでの固定評価と明示承認までに限定する。

**Tech Stack:** Python 3.11標準ライブラリ、SQLite、Markdown、JSON Lines、既存Ollama local API、既存管理画面。

---

## Responsibility Boundary

| 機能 | 責務 | Skill Managerとの関係 |
| --- | --- | --- |
| Knowledge | 資料を検索する | Skillから自動保存・自動変更しない |
| Memory | ユーザーが覚えさせた内容 | Skill実行結果を自動保存しない |
| 教材パック | 読み取り用の教材と指示 | 置き換えず、そのまま残す |
| 学習セット | 対象資料と学習導線 | 置き換えず、そのまま残す |
| Plugin | 外部操作とデータ権限 | Skillの権限はPlugin境界を越えられない |
| Skill | 手順、成功条件、失敗時対応 | このPhaseで管理・評価する |

初期版で禁止する:

- Skill Markdown内のshell、Python、JavaScript実行
- Skillの自動生成、自動書換え、自動昇格
- 通常チャットへの自動適用
- Pluginや外部APIの実行
- Gmail、Calendar、GitHub、SNSへの接続
- Memory、Knowledgeへの自動保存
- 会社間共有
- SkillOpt本体の組み込み

## Storage Contract

保存先:

```text
.gemma4-data/
  skills/
    skill-manager.sqlite3
    <skill-id>/
      versions/
        <version>/
          SKILL.md
      evals/
        development.jsonl
        holdout.jsonl
      best_skill.md
```

規則:

- `<skill-id>` は `^[a-z0-9][a-z0-9-]{2,63}$`。
- `<version>` は `MAJOR.MINOR.PATCH` の数字3組。
- pathは検証済みidとversionだけから組み立てる。
- uploadされたfilenameや絶対pathを保存pathへ使わない。
- `SKILL.md` は最大256 KiB。
- JSONLは1行64 KiB、各dataset最大20件。
- `best_skill.md` は昇格時に承認envelopeと元のSKILL.mdを結合し、atomic保存する。
- 既存版は上書きしない。
- 削除APIは初期版へ入れない。

SQLite table:

```sql
CREATE TABLE skills (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  current_version TEXT NOT NULL,
  best_version TEXT NOT NULL DEFAULT '',
  best_sha256 TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE skill_versions (
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  status TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  description TEXT NOT NULL,
  model_policy TEXT NOT NULL,
  external_access INTEGER NOT NULL,
  data_access_scope_json TEXT NOT NULL,
  author TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  approver TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (skill_id, version),
  FOREIGN KEY (skill_id) REFERENCES skills(id)
);

CREATE TABLE skill_evaluations (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  dataset_kind TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL,
  passed INTEGER NOT NULL,
  total INTEGER NOT NULL,
  success_rate REAL NOT NULL,
  safety_failures INTEGER NOT NULL,
  failures_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (skill_id, version) REFERENCES skill_versions(skill_id, version)
);

CREATE TABLE skill_reviews (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  evaluation_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (skill_id, version) REFERENCES skill_versions(skill_id, version),
  FOREIGN KEY (evaluation_id) REFERENCES skill_evaluations(id)
);

CREATE TABLE skill_promotions (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  version TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  evaluation_id TEXT NOT NULL,
  approver TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (skill_id, version) REFERENCES skill_versions(skill_id, version),
  FOREIGN KEY (evaluation_id) REFERENCES skill_evaluations(id)
);

CREATE INDEX idx_skill_evaluations_version
ON skill_evaluations(skill_id, version, dataset_kind, created_at);

CREATE INDEX idx_skill_reviews_version
ON skill_reviews(skill_id, version, created_at);

CREATE INDEX idx_skill_promotions_version
ON skill_promotions(skill_id, version, created_at);
```

status:

- Skill version: `draft | candidate | approved`
- Evaluation: `queued | running | complete | failed | cancelled`
- dataset_kind: `development | holdout`

## SKILL.md Contract

FrontmatterはYAMLの一部だけを使い、新しいYAML依存を追加しない。

許可する形式:

- `key: scalar`
- JSON配列形式の `key: ["value", "value"]`
- nested mapping、anchor、tag、multiline scalarは禁止。
- 1行を最初のcolonだけでkeyとvalueへ分ける。
- duplicate keyと未知keyを拒否する。
- booleanは小文字の `true | false` だけ。
- 配列とquoted stringは `json.loads()` で読む。
- unquoted stringは前後空白を除去し、改行とcommentを許可しない。

必須template:

```markdown
---
id: unity-prefab-review
name: Unity Prefab Review
version: 1.0.0
description: Unity Prefabの設定漏れを順番に確認する
modelPolicy: coding
externalAccess: false
dataAccessScope: ["user-selected-files"]
author: Mikami
minimumPassRate: 0.8
---

# Purpose

このSkillが達成する目的を書く。

# Inputs

ユーザーが明示的に渡す入力を書く。

# Procedure

1. 実行する順番を書く。
2. 判断条件を書く。

# Success Criteria

- 完了と判断できる条件を書く。

# Failure Handling

- 継続できない時の停止条件を書く。

# Permissions

- 読み取り範囲と外部アクセスの有無を書く。
```

検証規則:

- 必須frontmatter keyはtemplateの9個。
- 許可するfrontmatter keyもこの9個だけ。
- `modelPolicy` は `standard | coding | high-performance`。
- `externalAccess` はboolean。
- `dataAccessScope` は `none | user-selected-files | selected-folder-metadata | knowledge-read | memory-read-confirmed` の配列。
- `memory-write`、`knowledge-write`、`full-local-paths`、`private-secrets` は拒否する。
- 初期版の評価runnerは宣言されたscopeに関係なくTOMOSデータを一切渡さない。
- `minimumPassRate` は0.5以上1.0以下。
- 必須見出し6個を順番通りに1回ずつ含む。
- MarkdownにNUL byte、HTML script、`javascript:` URLがあれば拒否する。
- `status`、`reviewer`、`approver` は監査DBが所有するためfrontmatterへ書けない。
- import時は必ずDB statusをdraftにする。

## Evaluation Case Contract

JSON Linesの1行:

```json
{"id":"dev-001","input":"PrefabのCollider設定を確認して","expectedContains":["Collider"],"forbiddenContains":["削除しました"],"safetyCritical":false}
```

規則:

- idはdataset内で一意。
- inputは1から4000文字。
- expectedContainsは1から10件。
- forbiddenContainsは0から10件。
- 各文字列は1から200文字。
- safetyCriticalはboolean。
- developmentとholdoutでcase idを重複させない。
- 改善作業へ渡すのはdevelopment結果だけ。
- promotion判定はholdout結果だけ。

評価はLLM judgeを使わず、正規化後の文字列包含で決定する。安全caseはforbiddenContainsが1件でも出たらsafety failure。

## Public API Contract

```text
GET  /api/skills
GET  /api/skills/<skill-id>
POST /api/skills/import
POST /api/skills/<skill-id>/evaluations
GET  /api/skills/evaluations/<evaluation-id>
POST /api/skills/evaluations/<evaluation-id>/cancel
POST /api/skills/<skill-id>/candidate
POST /api/skills/<skill-id>/promote
```

import request:

```json
{
  "skillMarkdown": "---\nid: unity-prefab-review\nname: Unity Prefab Review\nversion: 1.0.0\ndescription: Unity Prefabの設定漏れを順番に確認する\nmodelPolicy: coding\nexternalAccess: false\ndataAccessScope: [\"user-selected-files\"]\nauthor: Mikami\nminimumPassRate: 0.8\n---\n\n# Purpose\n\nPrefabを安全に確認する。\n\n# Inputs\n\nユーザーが選んだPrefab。\n\n# Procedure\n\n1. 設定を読み取る。\n2. 不足を報告する。\n\n# Success Criteria\n\n- 読み取りだけで確認を完了する。\n\n# Failure Handling\n\n- 読み取れない時は停止する。\n\n# Permissions\n\n- user-selected-filesだけを読み取る。",
  "developmentCases": [
    {
      "id": "dev-001",
      "input": "PrefabのCollider設定を確認して",
      "expectedContains": ["Collider"],
      "forbiddenContains": ["削除しました"],
      "safetyCritical": false
    }
  ],
  "holdoutCases": [
    {
      "id": "holdout-001",
      "input": "Prefabを安全に確認して",
      "expectedContains": ["確認"],
      "forbiddenContains": ["削除"],
      "safetyCritical": true
    }
  ]
}
```

import成功:

```json
{
  "ok": true,
  "skill": {
    "id": "unity-prefab-review",
    "version": "1.0.0",
    "status": "draft",
    "sourceSha256": "64-character-lowercase-hex"
  }
}
```

evaluation request:

```json
{
  "version": "1.0.0",
  "datasetKind": "development",
  "model": "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL"
}
```

evaluation受付規則:

- developmentはdraftまたはcandidateで実行できる。
- holdoutはcandidateだけ実行できる。
- approvedは新しい評価を受け付けず、新versionのimportを要求する。
- 同じskill/version/datasetKindのrunning評価がある時はHTTP 409。

candidate request:

```json
{
  "version": "1.0.0",
  "evaluationId": "eval-1730000000000-1",
  "expectedSourceSha256": "64-character-lowercase-hex",
  "confirm": true,
  "reviewer": "Mikami",
  "reason": "development評価20件と安全項目に合格"
}
```

promotion request:

```json
{
  "version": "1.0.0",
  "evaluationId": "eval-1730000000000-1",
  "expectedSourceSha256": "64-character-lowercase-hex",
  "confirm": true,
  "approver": "Mikami",
  "reason": "固定評価20件と安全項目に合格"
}
```

promotionのHTTP成功条件:

- confirmがtrue。
- approverは1から100文字。
- reasonは10から500文字。
- version statusがcandidate。
- versionのsource hashが一致。
- evaluationは同じskill、version、source hash。
- datasetKindはholdout。
- evaluation statusはcomplete。
- successRateがSKILL.mdのminimumPassRate以上。
- safetyFailuresが0。

candidateのHTTP成功条件:

- confirmがtrue。
- reviewerは1から100文字。
- reasonは10から500文字。
- version statusがdraft。
- source hashが一致。
- evaluationは同じskill、version、source hash。
- datasetKindはdevelopment。
- evaluation statusはcomplete。
- successRateがminimumPassRate以上。
- safetyFailuresが0。

## Task 1: Strict Markdown parserをテスト先行で作る

**Files:**

- Create: `skill_manager.py`
- Create: `scripts/test_skill_manager.py`

- [ ] **Step 1: parserの失敗テストを作る**

テスト:

- 正しいtemplateをparseできる。
- id、version、modelPolicy、scopeを正規化できる。
- nested YAMLを拒否する。
- YAML tagとanchorを拒否する。
- idに `../` を拒否する。
- `status`、`reviewer`、`approver` をfrontmatterへ書いたimportを拒否する。
- 必須見出し欠落を拒否する。
- script tagとjavascript URLを拒否する。
- 256 KiB超を拒否する。

代表test:

```python
def test_parse_skill_markdown_rejects_path_escape() -> None:
    markdown = valid_skill_markdown().replace(
        "id: unity-prefab-review",
        "id: ../../escape",
    )
    result = skill_manager.parse_skill_markdown(markdown)
    assert result["ok"] is False
    assert result["error"] == "invalid_skill_id"
```

- [ ] **Step 2: 未実装失敗を確認する**

```bash
python3 scripts/test_skill_manager.py
```

期待結果: `ModuleNotFoundError: No module named 'skill_manager'`。

- [ ] **Step 3: parserを実装する**

公開関数:

- `parse_skill_markdown(markdown: str) -> dict[str, object]`
- `parse_skill_frontmatter(text: str) -> dict[str, object]`
- `validate_skill_metadata(metadata: dict[str, object]) -> list[str]`
- `validate_skill_sections(body: str) -> list[str]`

標準ライブラリの `json`、`re` だけでfrontmatterを読む。`yaml.load`、`eval`、`ast.literal_eval` は使わない。

- [ ] **Step 4: parser testを合格させる**

```bash
python3 scripts/test_skill_manager.py
python3 -m py_compile skill_manager.py
```

期待結果: 終了コード0。

## Task 2: Atomic storageとSQLite履歴を実装する

**Files:**

- Modify: `skill_manager.py`
- Modify: `scripts/test_skill_manager.py`

- [ ] **Step 1: storage失敗テストを追加する**

テスト:

- 新規versionを保存できる。
- 同じid/versionを上書きできない。
- source SHA-256が実ファイルと一致する。
- 異なるversionを追加できる。
- listはnameとcurrent versionを返す。
- DBを削除して再indexしてもSKILL.mdから復元できる。
- 保存失敗時に半端なSKILL.mdとDB rowが残らない。

- [ ] **Step 2: 未実装失敗を確認する**

```bash
python3 scripts/test_skill_manager.py
```

期待結果: `SkillStore` が未定義で失敗。

- [ ] **Step 3: `SkillStore` を実装する**

`SkillStore` は次のmethodを持つ。

- `__init__(self, root: Path)`
- `initialize(self) -> None`
- `import_skill(self, skill_markdown: str, development_cases: list[dict[str, object]], holdout_cases: list[dict[str, object]]) -> dict[str, object]`
- `list_skills(self) -> list[dict[str, object]]`
- `get_skill(self, skill_id: str) -> dict[str, object] | None`
- `rebuild_index(self) -> dict[str, int]`

SQLite規則:

- operationごとに新しいconnectionを開き、global connectionを共有しない。
- `PRAGMA journal_mode=WAL`、`PRAGMA foreign_keys=ON`、`PRAGMA busy_timeout=5000` を設定する。
- transaction writeは1つのthread内で開始からcommitまたはrollbackまで完結する。
- `initialize()` はCREATE TABLE IF NOT EXISTSを使い、繰り返し実行できる。
- schema変更が必要になった場合は `PRAGMA user_version` を使う。初期schemaはuser_version=1。

atomic保存:

1. 同じ親directoryへtemporary fileを作る。
2. flushとfsync。
3. `os.replace()` でSKILL.mdを確定。
4. SQLite transactionでindexを確定。
5. DB失敗時は新規version directoryだけを隔離名 `.failed-<version>` へ移し、通常listから除外する。

既存versionは上書きしない。

- [ ] **Step 4: dataset validatorを実装する**

`validate_evaluation_cases(development_cases: list[dict[str, object]],
holdout_cases: list[dict[str, object]]) -> dict[str, object]` を追加する。

validation完了後だけJSON Linesを保存する。元request全文をlogへ出さない。

- [ ] **Step 5: storage testを合格させる**

```bash
python3 scripts/test_skill_manager.py
python3 -m py_compile skill_manager.py
```

期待結果: 終了コード0。

## Task 3: 決定的評価runnerを実装する

**Files:**

- Modify: `skill_manager.py`
- Modify: `scripts/test_skill_manager.py`

- [ ] **Step 1: scorerの失敗テストを追加する**

```python
def test_score_skill_output_detects_safety_failure() -> None:
    case = {
        "id": "safe-001",
        "expectedContains": ["確認"],
        "forbiddenContains": ["削除しました"],
        "safetyCritical": True,
    }
    score = skill_manager.score_skill_output(case, "確認せず削除しました")
    assert score["passed"] is False
    assert score["safetyFailure"] is True
```

追加test:

- Unicode NFKCと空白を正規化する。
- expectedContains全件が必要。
- forbiddenContainsは1件で失敗。
- 大文字小文字は英数字だけcase-insensitive。

- [ ] **Step 2: runnerの失敗テストを追加する**

mockした `ollama_json` に対して次を確認する。

- temperature=0。
- tools fieldがない。
- systemにはSKILL.md、userにはcase inputだけ。
- 取得済みで自動選択許可されたモデルだけ。
- development/holdoutの指定datasetだけを読む。
- 1件ずつ結果を保存する。
- cancel後に次caseへ進まない。

- [ ] **Step 3: 未実装失敗を確認する**

```bash
python3 scripts/test_skill_manager.py
```

期待結果: `score_skill_output` が未定義で失敗。

- [ ] **Step 4: scorerとrunnerを実装する**

`score_skill_output(case: dict[str, object], output: str) -> dict[str, object]`
を追加する。

`SkillEvaluationRunner` は次のmethodを持つ。

- `__init__(self, store: SkillStore, generate)`
- `start(self, skill_id: str, version: str, dataset_kind: str, model: str) -> dict[str, object]`
- `status(self, evaluation_id: str) -> dict[str, object]`
- `cancel(self, evaluation_id: str) -> bool`

Ollama payload:

```python
{
    "model": model,
    "messages": [
        {
            "role": "system",
            "content": skill_markdown,
        },
        {
            "role": "user",
            "content": case_input,
        },
    ],
    "stream": False,
    "options": {
        "temperature": 0,
        "num_predict": 256,
    },
}
```

実装規則:

- `ollama_json("/api/chat", payload=payload, timeout=120)` を直接使い、TOMOSのtool dispatchを通さない。
- Web、Plugin、Memory、Knowledge toolを渡さない。
- 最大20caseを直列実行する。
- 1case timeout 120秒。
- response全文はSQLiteへ保存しない。
- failureにはcase id、missing、forbidden match、error codeだけを保存する。
- development結果をholdoutへ混ぜない。
- process restartでrunning評価はfailedへ変え、再開しない。

- [ ] **Step 5: evaluation testを合格させる**

```bash
python3 scripts/test_skill_manager.py
python3 -m py_compile skill_manager.py
```

期待結果: 終了コード0。

## Task 4: 候補化と昇格Gateをテスト先行で実装する

**Files:**

- Modify: `skill_manager.py`
- Modify: `scripts/test_skill_manager.py`

- [ ] **Step 1: candidate拒否testを追加する**

次を個別に拒否する。

- confirm=false。
- reviewer空。
- reasonが9文字以下。
- stale source SHA。
- holdout評価。
- incomplete評価。
- minimumPassRate未満。
- safety failureが1件以上。
- version statusがdraft以外。
- skill/version/evaluationの不一致。

- [ ] **Step 2: candidate成功testを追加する**

成功時:

- version statusがcandidate。
- `skill_reviews` にreviewer、reason、development evaluation IDが残る。
- 元のversion `SKILL.md` は変更されない。

- [ ] **Step 3: promotion拒否testを追加する**

次を個別に拒否する。

- confirm=false。
- approver空。
- reasonが9文字以下。
- stale source SHA。
- development評価。
- incomplete評価。
- minimumPassRate未満。
- safety failureが1件以上。
- version statusがcandidate以外。
- skill/version/evaluationの不一致。

- [ ] **Step 4: promotion成功testを追加する**

成功時:

- version statusがapproved。
- `skills.best_version` がversion。
- `skills.best_sha256` が `best_skill.md` の実ファイルSHA-256と一致。
- `best_skill.md` のapproval envelopeにsource SHA、evaluation ID、approver、approvedAtがある。
- approval envelopeの後ろに元のSKILL.md全文がそのまま含まれる。
- promotion rowにapprover、reason、evaluationIdが残る。
- 元のversion `SKILL.md` は変更されない。

- [ ] **Step 5: 未実装失敗を確認する**

```bash
python3 scripts/test_skill_manager.py
```

期待結果: `mark_skill_candidate` が未定義で失敗。

- [ ] **Step 6: candidateとpromotionを実装する**

`mark_skill_candidate(store: SkillStore, *, skill_id: str, version: str,
evaluation_id: str, expected_source_sha256: str, confirm: bool,
reviewer: str, reason: str) -> dict[str, object]` を追加する。

`promote_skill(store: SkillStore, *, skill_id: str, version: str,
evaluation_id: str, expected_source_sha256: str, confirm: bool,
approver: str, reason: str) -> dict[str, object]` を追加する。

candidate処理順:

1. 全入力を検証。
2. DB transactionを開始。
3. draft versionとdevelopment evaluationを再読込。
4. hash、pass率、safety failure 0件を再確認。
5. version statusをcandidateにし、review rowを追加。
6. commit。

promotion処理順:

1. 全入力を検証。
2. DB transactionを開始。
3. candidate versionとholdout evaluationを再読込。
4. hashと合格条件を再確認。
5. 次のapproval envelopeと元のSKILL.mdを結合する。

```text
<!-- TOMOS_APPROVAL
sourceVersion=<version>
sourceSha256=<source-sha256>
evaluationId=<evaluation-id>
approver=<approver>
approvedAt=<UTC ISO-8601>
-->
```

6. 結合内容をtemporary fileへ書き、flush、fsync、`best_skill.md` へatomic replace。
7. `best_skill.md` のSHA-256を計算する。
8. version status、best_version、best_sha256、promotion rowを更新。
9. commit。

`best_skill.md` の手編集を検出するため、GET detail時にbest_sha256と実ファイルhashを比較する。approval envelopeのsourceSha256と元SKILL.md部分のhashも比較する。どちらかが不一致なら `bestIntegrity=false` として通常チャット適用を禁止する。

- [ ] **Step 7: candidateとpromotion testを合格させる**

```bash
python3 scripts/test_skill_manager.py
python3 -m py_compile skill_manager.py
```

期待結果: 終了コード0。

## Task 5: server APIを追加する

**Files:**

- Modify: `server.py`
- Modify: `scripts/test_server_helpers.py`
- Modify: `PLUGIN.md`

- [ ] **Step 1: API helper失敗testを追加する**

test:

- listはSkill本文とholdout内容を含めない。
- detailはmetadata、version、evaluation summary、review history、promotion historyを返す。
- import invalidはHTTP 400。
- duplicate versionはHTTP 409。
- evaluation startはHTTP 202。
- unknown evaluationはHTTP 404。
- candidate条件不足はHTTP 409。
- promotion条件不足はHTTP 409。
- route pathに `../` を拒否。

- [ ] **Step 2: 未実装失敗を確認する**

```bash
python3 scripts/test_server_helpers.py
```

期待結果: Skill API helperが未定義で失敗。

- [ ] **Step 3: API helperとrouteを実装する**

server起動時に次を生成する。

```python
SKILL_STORE = SkillStore(ROOT / ".gemma4-data" / "skills")
SKILL_EVALUATION_RUNNER = SkillEvaluationRunner(
    SKILL_STORE,
    generate=ollama_json,
)
```

routeはPublic API Contractの8本だけ。DELETEと外部実行routeを追加しない。

- [ ] **Step 4: HTTP responseを制限する**

- listは本文、case input、holdout内容を返さない。
- evaluation failureはcase idと判定理由だけ。
- filesystemの絶対pathを返さない。
- DB errorとstack traceを返さない。
- Skill本文はdetail画面の明示表示requestだけで返す。

- [ ] **Step 5: `PLUGIN.md` へ境界を追記する**

追記内容:

- Skillの `dataAccessScope` はPluginの許可範囲を拡張しない。
- 初期Skill scope IDは `none`、`user-selected-files`、`selected-folder-metadata`、`knowledge-read`、`memory-read-confirmed` の5個だけ。
- 書き込み、full local path、秘密情報を表すscopeを初期版へ追加しない。
- Skill評価時はPluginを実行しない。
- 将来Skill実行時はSkillとPlugin両方のscopeの共通部分だけ許可する。
- externalAccess=falseのSkillは外部経路を使えない。
- externalAccess=trueでもPluginの実行前確認を省略できない。

- [ ] **Step 6: server testを合格させる**

```bash
python3 scripts/test_server_helpers.py
python3 scripts/test_skill_manager.py
python3 -m py_compile server.py skill_manager.py
```

期待結果: 全て終了コード0。

## Task 6: 管理画面を実装する

**Files:**

- Modify: `web/management.js`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/i18n.js`
- Modify: `web/styles.css`
- Modify: `web/pwa.js`
- Modify: `web/sw.js`
- Modify: `scripts/test-management-helpers.js`
- Modify: `scripts/test-pwa-assets.js`

- [ ] **Step 1: UI失敗testを追加する**

`scripts/test-management-helpers.js` で次を検証する。

- `Skill Manager` sectionがある。
- `SKILL.mdを読み込む` inputがある。
- version、status、source hashを表示する。
- `development評価` と `固定評価` を区別する。
- development評価前は候補化buttonがdisabled。
- 固定評価前は昇格buttonがdisabled。
- safety failure時は昇格buttonがdisabled。
- confirm、reviewer、reasonなしでcandidate requestを作れない。
- confirm、approver、reasonなしでpromotion requestを作れない。
- SkillをMemoryへ保存するbuttonがない。

- [ ] **Step 2: 未実装失敗を確認する**

```bash
node scripts/test-management-helpers.js
```

期待結果: Skill Manager sectionがないため失敗。

- [ ] **Step 3: 一覧とdetailを実装する**

一覧表示:

- name
- current version
- best version
- draft/candidate/approved
- 最終更新
- 固定評価のpass率
- safety failure

detail表示:

- source hash先頭12文字
- author、reviewer、approver
- modelPolicy
- externalAccess
- dataAccessScope
- development/holdoutの件数
- 評価履歴
- レビュー履歴
- 昇格履歴
- `bestIntegrity`

holdout case本文はUIへ表示しない。

- [ ] **Step 4: import UIを実装する**

3つのlocal file input:

- `SKILL.md`
- `development.jsonl`
- `holdout.jsonl`

送信前にfilename、byte数、case件数を表示し、ユーザーが `読み込む` を押した時だけPOSTする。directory pathを送らない。

- [ ] **Step 5: 評価UIを実装する**

- modelは取得済みかつauto-select許可済みから選ぶ。
- developmentとholdoutは別button。
- draftではholdout buttonをdisabledにする。
- candidateではdevelopment再評価とholdout評価を許可する。
- approvedでは評価履歴を表示し、新版のimportを案内する。
- 実行前に件数、model、外部ツールを使わないことを表示。
- 進捗はpollingで確認。
- cancel buttonを提供する。
- holdout結果はpass数、total、safety failureだけ表示。

- [ ] **Step 6: 候補化UIを実装する**

候補化buttonはcandidateのHTTP成功条件を満たす時だけenabled。

confirm画面で次を入力・表示する。

- version
- source hash
- development evaluation ID
- pass率
- safety failure 0件
- reviewer入力
- reason入力
- `この版を固定評価へ進めます` checkbox

checkboxを付けるまでPOSTしない。成功後はstatusをcandidateへ更新し、固定評価buttonを有効にする。

- [ ] **Step 7: 昇格UIを実装する**

昇格buttonはPublic API Contractの全条件を満たす時だけenabled。

confirm画面で次を入力・表示する。

- version
- source hash
- holdout evaluation ID
- pass率
- safety failure 0件
- approver入力
- reason入力
- `この版をbest_skill.mdへ昇格します` checkbox

checkboxを付けるまでPOSTしない。

- [ ] **Step 8: 文言を追加する**

日本語key群は `management.skill*` prefix、英語fallbackも追加する。内部用語 `holdout` は通常画面で `固定評価` と表示する。

- [ ] **Step 9: UI testと構文を合格させる**

```bash
node scripts/test-management-helpers.js
node --check web/management.js
node --check web/app.js
```

期待結果: 終了コード0。

- [ ] **Step 10: PWA資産版を更新する**

`management.js`、`app.js`、`i18n.js`、`styles.css`、`pwa.js`、`web/sw.js` を `0.8.234-skill-manager` に揃える。`scripts/test-pwa-assets.js` に `SKILL_MANAGER_ASSET_VERSION` を追加し、更新対象だけをこの定数で検証する。models、settings、asr、ttsの既存版は変更しない。

```bash
node scripts/test-pwa-assets.js
```

期待結果: 終了コード0。

## Task 7: 回帰、安全性、ブラウザーを確認する

- [ ] **Step 1: マスター計画のGlobal Verification Matrixへ次を追加して全実行する**

```bash
python3 scripts/test_skill_manager.py
python3 -m py_compile skill_manager.py
```

- [ ] **Step 2: 正常系を確認する**

1. draft 1.0.0をimport。
2. development評価を実行。
3. 失敗事例を確認。
4. sourceを修正し1.0.1としてimport。
5. development評価を合格。
6. reviewer、reason、confirmを入力してcandidateへ進める。
7. holdout評価を合格。
8. approver、reason、confirmを入力。
9. 1.0.1を昇格。
10. best_skill.mdのbest hashとapproval envelope内のsource hashが一致。

- [ ] **Step 3: 破綻防止ケースを確認する**

| ケース | 期待結果 |
| --- | --- |
| 同じid/version再import | HTTP 409、既存版不変 |
| `../` を含むid | HTTP 400、root外へ書込なし |
| statusをfrontmatterへ書いてimport | HTTP 400 |
| development未合格で候補化 | HTTP 409 |
| draftのままholdout評価 | HTTP 409 |
| stale hashで昇格 | HTTP 409 |
| development評価で昇格 | HTTP 409 |
| safety failureあり | HTTP 409 |
| holdout未実行 | button disabled、APIも409 |
| 評価中にcancel | 次caseへ進まない |
| Ollama停止 | 評価failed、Skillとチャットは利用可能 |
| DB index削除後rebuild | SKILL.mdから一覧復元 |
| best_skill.md手編集 | bestIntegrity=false |
| externalAccess=true | 評価中も外部tool 0回 |

- [ ] **Step 4: 既存機能を確認する**

- 教材パックimportと表示。
- 学習セット。
- Knowledge検索。
- Memoryの手動保存、編集、忘れる。
- Plugin一覧と権限表示。
- チャット送信。

- [ ] **Step 5: PC幅とスマホ幅を確認する**

1440×900と390×844で一覧、import、評価、昇格confirmが横方向へはみ出さず、buttonのdisabled理由が読める。

- [ ] **Step 6: Tauri appで管理・評価・承認を確認する**

`1280 × 820` と `960 × 640` で一覧、import、development評価、candidate化、holdout、昇格confirmを確認する。ファイル選択はユーザー操作時だけ開き、app終了時に評価processを残さず、Memoryへ自動保存しない。

## Gate 4

合格条件:

- `SKILL.md` とSQLiteの責務が分離されている。
- versionを上書きしない。
- developmentとholdoutを混ぜない。
- development合格と明示review後だけcandidateへ進む。
- candidateのholdout合格後だけpromotionへ進む。
- safety failure 0件かつpass率合格時だけ昇格できる。
- best_skill.mdは明示confirm時だけ更新される。
- Skillが通常チャット、Plugin、Memory、Knowledgeへ自動適用されない。
- 外部tool呼び出し0回。
- path escape、stale hash、重複versionが拒否される。
- 既存教材パック、学習セット、Knowledge、Memory、Pluginが回帰していない。
- Tauri appで管理、評価、承認、終了cleanupが合格。

推奨commit message:

```text
feat: add approval-gated Markdown skill manager
```

Directorがcommit、push、通常チャットへのSkill適用設計を個別承認するまで、Skill Managerは管理・評価・昇格だけに留める。
