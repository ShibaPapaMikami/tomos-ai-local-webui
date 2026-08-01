# TOMOS Gate C後 実行統制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 承認済みGate C後設計をマスター計画へ反映し、正本・担当・検証条件を一本化してU0、M0、D0を安全に開始できる状態にする。

**Architecture:** 最初のtrancheは文書と文書契約テストだけを変更し、製品コード、版番号、成果物には触れない。R0合格後はU0、M0、D0を別worktree・別計画で進め、Gate 4以降は既存のSkill、Voice、Model計画へ引き渡す。

**Tech Stack:** Markdown、Python 3.11標準ライブラリ、Git、既存TOMOSテスト。

## Global Constraints

- 開始基準は`origin/main@6df62c09cb64044ed76480e417706ca2167a72ae`。
- 承認済み設計commitは`94d3926`。
- 設計正本は`docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md`。
- 作業branchは`codex/post-gate-c-roadmap`、worktreeは`.worktrees/post-gate-c-roadmap`。
- 第一trancheはdoc-only。`server.py`、`web/**`、`src-tauri/**`、`app_paths.py`、版番号、成果物を変更しない。
- 既存Skill、Voice、Model詳細planは変更・複製しない。
- 依存追加、artifact取得、署名、公証、実機変更、外部通信、公開を行わない。
- commitはTaskごとにDirectorが差分と検証結果を確認し、ユーザーが明示承認した場合だけ実行する。
- shared fileの実装担当はTask開始時にDirectorが一人だけ指定する。
- `git diff --check`と対象テストが合格するまでGateを進めない。

## Files and Ownership

| File | Responsibility | Owner |
| --- | --- | --- |
| `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md` | 全体順序とGate状態の唯一の正本 | 追加機能担当 |
| `scripts/test_post_gate_c_master.py` | マスター計画と承認済み設計の契約 | 追加機能担当 |
| `docs/tomos-post-gate-c-r0-gate-report-2026-08-01.ja.md` | R0の開始点、基準線、ownership、未実行条件 | Director |
| `docs/superpowers/plans/2026-08-01-tomos-beginner-install-docs.md` | U0文書一本化の実装計画 | ユーザー対応 |
| `docs/superpowers/plans/2026-08-01-tomos-release-traceability.md` | M0版・source・manifest対応の実装計画 | エンジニア2 |
| `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md` | D0で承認するWindows配布契約 | エンジニア2 |

---

### Task 1: マスター順序の失敗テストを追加する

**Files:**
- Create: `scripts/test_post_gate_c_master.py`
- Read: `docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md`
- Read: `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`

**Interfaces:**
- Consumes: 承認済み設計のGate名`R0`, `U0`, `M0`, `D0`, `REL0`, `Gate 4`, `V0 / V1`, `E0 / E1`
- Produces: `python3 scripts/test_post_gate_c_master.py`で実行できる文書契約

- [ ] **Step 1: 現在の開始点をreadbackする**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Expected:

- branchは`codex/post-gate-c-roadmap`
- `HEAD`には承認済み設計commit `94d3926`が含まれる
- 既存未コミット変更は本計画ファイルだけ

- [ ] **Step 2: 失敗する文書契約テストを書く**

Create `scripts/test_post_gate_c_master.py`:

```python
#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs/superpowers/plans/2026-07-23-tomos-evolution-master.md"
DESIGN = ROOT / "docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md"


def require_in_order(text: str, tokens: list[str]) -> None:
    cursor = -1
    for token in tokens:
        next_cursor = text.find(token, cursor + 1)
        assert next_cursor >= 0, f"missing token: {token}"
        assert next_cursor > cursor, f"out of order: {token}"
        cursor = next_cursor


def test_post_gate_c_source_of_truth() -> None:
    master = MASTER.read_text(encoding="utf-8")
    design_reference = (
        "docs/superpowers/specs/"
        "2026-08-01-tomos-post-gate-c-program-design.md"
    )
    assert design_reference in master
    for gate in (
        "Gate R0",
        "Gate U0",
        "Gate U1 / U2",
        "Gate U0F",
        "Gate M0",
        "Gate M1 / M2",
        "Gate D0",
        "Gate D1 / D2 / D3",
        "Gate REL0",
    ):
        assert gate in master


def test_post_gate_c_phase_order() -> None:
    master = MASTER.read_text(encoding="utf-8")
    phase_order = master.split("## Phase Order", 1)[1].split(
        "## PWA資産版の進め方", 1
    )[0]
    require_in_order(
        phase_order,
        [
            "Gate C",
            "Gate R0",
            "Gate U0",
            "Gate M0",
            "Gate D0",
        ],
    )
    require_in_order(
        phase_order,
        [
            "Release lane",
            "Gate M1 / M2",
            "Gate D1 / D2 / D3",
            "Final Mac M1 / M2",
            "Gate REL0",
        ],
    )
    require_in_order(
        phase_order,
        [
            "Support lane",
            "Gate U1",
            "Gate U2",
            "Gate U0F",
            "Gate REL0",
        ],
    )
    require_in_order(
        phase_order,
        [
            "Product lane",
            "Gate 4",
            "Gate V0 / V1",
            "Gate E0 / E1",
        ],
    )


def test_existing_detail_plans_remain_referenced() -> None:
    master = MASTER.read_text(encoding="utf-8")
    for filename in (
        "2026-07-23-tomos-markdown-skill-manager.md",
        "2026-07-23-tomos-voice-engine-evaluation-lab.md",
        "2026-07-23-tomos-model-evaluation-lab.md",
    ):
        assert filename in master
    assert DESIGN.is_file()


if __name__ == "__main__":
    test_post_gate_c_source_of_truth()
    test_post_gate_c_phase_order()
    test_existing_detail_plans_remain_referenced()
    print("post-Gate-C master contract tests passed")
```

- [ ] **Step 3: テストが意図どおり失敗することを確認する**

Run:

```bash
python3 scripts/test_post_gate_c_master.py
```

Expected: FAIL with `missing token: Gate R0`または設計参照の不足。

- [ ] **Step 4: 構文だけを確認する**

Run:

```bash
python3 -m py_compile scripts/test_post_gate_c_master.py
```

Expected: exit 0。

- [ ] **Step 5: Task差分を確認する**

Run:

```bash
git diff --check
git status --short
```

Expected: 新規テストと本計画だけが表示される。

このTaskではcommitしない。失敗テストとTask 2のマスター修正を同じreview単位にする。

### Task 2: マスター計画を承認済み設計へ同期する

**Files:**
- Modify: `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- Test: `scripts/test_post_gate_c_master.py`

**Interfaces:**
- Consumes: Task 1の文書契約
- Produces: Gate C後の唯一のPhase Orderと進行台帳

- [ ] **Step 1: Source of Truthへ承認済み設計を追加する**

`Source of Truth`表へ次の行を追加する:

```markdown
| Gate C後の統合設計 | `docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md` | R0、配布、サポート、Skill、Voice、Model、将来Gateの順序と承認境界 |
```

`Global Constraints`へ次を追加する:

```markdown
- Gate C後は承認済み統合設計に従い、R0で正本・担当・検証条件を固定してからU0、M0、D0へ進む。
- 初心者向け正式ReleaseはGate REL0まで公開しない。OS単独previewは固有prerelease tagと別承認を必須にする。
- Gate 4はU0、M0、D0合格後に実装を開始し、配布shared file統合後だけ製品へ統合する。
```

- [ ] **Step 2: 進行台帳を更新する**

Gate Cの直後へ次の行を追加する:

```markdown
| Gate R0 | Gate C合格版と承認済み統合設計 | 正本、ownership、release manifest項目、baseline条件 | U0 / M0 / D0 | 検証中 |
| Gate U0 | Gate R0合格版 | OS別初心者ガイドの内部draftと文書契約 | U1 / U2 | 停止 |
| Gate U1 / U2 | U0、M0、D0合格版 | 10秒以内の初回案内、安全な診断、第三者試験票 | Gate U0F | 停止 |
| Gate U0F | U1、U2、M2、D3合格版 | 最終artifact名・SHAを反映した公開文書 | Gate REL0 | 停止 |
| Gate M0 | Gate R0合格版 | 版、source commit、tree、成果物manifestの一意対応 | Mac M1 / M2 | 停止 |
| Gate M1 / M2 | Gate M0合格版 | Mac再生成、署名、公証、第三者試験 | Gate REL0 | 停止 |
| Gate D0 | Gate R0合格版 | Windows署名、runtime、WebView2、保存先、rollback契約 | Windows D1 / D2 / D3 | 停止 |
| Gate D1 / D2 / D3 | Gate D0合格版 | Windows署名CI、実機、第三者試験 | Gate REL0 | 停止 |
| Gate REL0 | Final Mac M2、D3、U0Fの合格版 | 同一版PKG/MSI、第三者smoke、公開物readback | 正式PCアプリ | 停止 |
```

既存の`Gate D`行は削除し、上記`Gate D0`と`Gate D1 / D2 / D3`へ置き換える。

Gate 4の入力を次へ変更する:

```markdown
| Gate 4 | U0、M0、D0合格版 | Markdown Skill Manager、固定評価、承認昇格 | Experiment V、その後Experiment E | 停止 |
```

- [ ] **Step 3: Phase Orderを置き換える**

Gate C以降を次へ置き換える:

```text
  -> Gate C Mac新規/移行実機確認
  -> Gate R0 正本・ownership・release manifest・baseline条件を固定
  -> Gate U0 OS別初心者ガイドを一本化
  -> Gate M0 Mac版・source・成果物対応を固定
  -> Gate D0 Windows署名・runtime・保存・rollback設計を固定
  -> Release lane:
       Gate M1 / M2 Mac内部候補・第三者試験
       Gate D1 / D2 / D3 Windows署名CI・実機・第三者試験
       Final Mac M1 / M2 Windows最終release commitからMacを再生成・再試験
  -> Support lane:
       Gate U1 10秒以内の初回4段階案内
       Gate U2 安全な診断・起動失敗表示・第三者試験票
       Gate U0F 最終artifact名・SHAで公開文書を確定
  -> Product lane:
       Phase 4 Markdown Skill Manager
       Gate 4 手動承認・固定評価・Memory非自動保存確認
       Director承認時だけ Experiment V
       Gate V0 / V1 candidate承認・隔離実測・人評価
       Director承認時だけ Experiment E
       Gate E0 / E1 artifact承認・local-only比較
  -> Release laneのFinal Mac M2、D3とSupport laneのU0Fをreadback
  -> Gate REL0 同一版PKG/MSI・第三者smoke・公開物readback
  -> Product laneの必要Gateを別にreadback
  -> 将来Gate Company Memory / P2P / VRMを別設計
```

- [ ] **Step 4: Ownership Boundaryを追加する**

```markdown
| Gate R0 正本同期 | master計画、文書契約テスト、R0報告 | 製品コード、版番号、成果物 |
| Gate U0 初心者文書 | README、OS別導入ガイド、Release文書テスト | installer、runtime、製品UI |
| Gate M0 Mac追跡 | version、release manifest、Mac release文書 | Windows署名、Skill、Voice、Model |
| Gate D0 Windows設計 | Windows配布spec、path/upgrade/rollback契約 | Mac署名、Skill、Voice、Model |
```

- [ ] **Step 5: Deferred Scopeと完了条件を同期する**

次を明記する:

```markdown
- Company Memoryのspec起票はGate REL0とGate 4の合格後。
- P2Pのspec起票はGate REL0、Gate 4、CM0の合格後。
- VRM0のspec起票はGate REL0合格後。Voice/Model比較は入口条件にしない。
- VRM1はVRM0合格後、Phase 3 contractまたは別採用Gate承認済みengineだけを使う。
```

Master Completion Criteriaへ次を追加する:

```markdown
- 初心者向け正式ReleaseのPKG/MSIは同じ版、tag、source commitから生成され、公開SHAと第三者試験SHAが一致している。
- Ollama停止時も既存データ閲覧とSkill管理ができ、新しいAI回答は開始せず復旧案内を表示する。
- データ・設定rollbackと、対象版が存在する場合のアプリ版rollbackを実証している。
```

- [ ] **Step 6: 固定判断・PWA版・完了条件を同期する**

`固定する判断`の配布判断を次へ置き換える:

```markdown
13. `0.8.233`はGate C検証済み成果物として保持し、現在の`origin/main`由来の正式配布物とは扱わない。
14. 次の正式候補版は`0.8.234`以降とし、M0で版・source・tree・artifact manifestを固定する。
15. Release laneとProduct laneは別worktreeで準備できるが、shared fileの実装とmergeはDirectorが直列化する。
```

PWA資産版表のPhase 4は、M0の`0.8.234`と衝突しないよう次へ更新する:

```markdown
| Phase 4 | `0.8.235-skill-manager` | management、i18n、styles、app、pwa、Service Worker cache | models、settings、asr、tts |
```

Master Completion Criteriaの`Gate D`表記は`Gate D0からD3とGate REL0`へ置き換える。

- [ ] **Step 7: 文書契約を合格させる**

Run:

```bash
python3 scripts/test_post_gate_c_master.py
```

Expected: `post-Gate-C master contract tests passed`。

- [ ] **Step 8: 既存詳細planが不変であることを確認する**

Run:

```bash
git diff --exit-code 94d3926 -- \
  docs/superpowers/plans/2026-07-23-tomos-markdown-skill-manager.md \
  docs/superpowers/plans/2026-07-23-tomos-voice-engine-evaluation-lab.md \
  docs/superpowers/plans/2026-07-23-tomos-model-evaluation-lab.md
```

Expected: exit 0、出力なし。

- [ ] **Step 9: 差分を検証する**

Run:

```bash
git diff --check
git diff --stat
git status --short
```

Expected: 本計画、文書契約テスト、マスター計画だけが対象。

- [ ] **Step 10: Director review後にcommitする**

停止条件: ユーザーのcommit承認がない場合は実行しない。

```bash
git add \
  docs/superpowers/plans/2026-08-01-tomos-post-gate-c-program.md \
  docs/superpowers/plans/2026-07-23-tomos-evolution-master.md \
  scripts/test_post_gate_c_master.py
git commit -m "docs: align TOMOS master with post-Gate-C program"
```

- [ ] **Step 11: 統合承認を得る**

Directorがcommit SHA、diff、テスト結果をユーザーへ提示する。push、PR、mergeはそれぞれ別承認を得てから実行し、merge後の`origin/main`をTask 3の唯一の開始点にする。

### Task 3: Gate R0の証跡を保存する

**Files:**
- Create: `docs/tomos-post-gate-c-r0-gate-report-2026-08-01.ja.md`
- Modify: `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- Test: `scripts/test_post_gate_c_master.py`

**Interfaces:**
- Consumes: Task 2のマスター正本
- Produces: U0、M0、D0の開始判断に使うR0報告

- [ ] **Step 1: Task 2を統合してR0専用worktreeを作る**

停止条件:

- Task 2のcommit、push、PR、merge承認がない場合は停止。
- merge後の`origin/main`をreadbackできない場合は停止。

Task 2をmerge後、`superpowers:using-git-worktrees`を使い、更新済み`origin/main`から次を作る:

```bash
git -C /Users/masafumimikami/Documents/desktop/Gemma4_12B fetch origin main
git -C /Users/masafumimikami/Documents/desktop/Gemma4_12B worktree add \
  /Users/masafumimikami/Documents/desktop/Gemma4_12B/.worktrees/post-gate-c-r0 \
  -b codex/post-gate-c-r0 \
  origin/main
```

以後のTask 3は`.worktrees/post-gate-c-r0`で実行する。R0報告へ40桁の`origin/main` commitを記録し、`HEAD`と完全一致しなければ合格にしない。

- [ ] **Step 2: Git基準線をreadbackする**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse HEAD^{tree}
git rev-parse origin/main
```

報告にはcommandの実出力をそのまま記載し、推測値を書かない。

- [ ] **Step 3: baselineを実行する**

Run:

```bash
python3 scripts/test_post_gate_c_master.py
python3 scripts/test-desktop-release-version.py
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-asr-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
node scripts/test-tts-helpers.js
python3 scripts/test_server_helpers.py
python3 scripts/test_study_pack_manager.py
python3 scripts/test_context_core.py
python3 scripts/test_knowledge_layer.py
python3 scripts/test_tts_engine.py
python3 scripts/test-desktop-shell-contract.py
node --check web/models.js
node --check web/settings.js
node --check web/asr.js
node --check web/management.js
node --check web/app.js
node --check web/tts.js
node --check web/desktop-starting.js
python3 -m py_compile \
  server.py \
  tts_engine.py \
  scripts/tts_fixture_worker.py \
  scripts/test_post_gate_c_master.py
cargo test --manifest-path src-tauri/Cargo.toml
git diff --check
git status --short --branch
```

Expected:

- 全commandがexit 0。
- `cargo test`が`../build/macos-runtime/tomos`不足で停止した場合は、コード不良とせず「生成runtime準備前」と記録し、R0を`検証中`のまま維持する。
- 生成runtime準備に外部取得、ユーザーPython領域への書込み、署名資源が必要なら、操作内容を示して承認を得る。
- 未実行または失敗が1件でもあればR0を合格にしない。

- [ ] **Step 4: ownershipを記録する**

報告へ次を記載する:

```markdown
| Track | Owner | Shared files | Start condition |
| --- | --- | --- | --- |
| U0 | ユーザー対応 | READMEと導入文書だけ | R0合格 |
| M0 | エンジニア2 | versionとrelease manifest | R0合格 |
| D0 | エンジニア2 | Windows配布specだけ | R0合格 |
| Gate 4監査 | 追加機能担当 | 既存計画のread-only差分監査 | R0合格 |
```

- [ ] **Step 5: release manifest必須項目を記録する**

```markdown
- release version
- tag対象commitとtree SHA
- clean / dirty
- CI run、toolchain
- runtime取得元、SHA-256、license
- artifact名、platform、size、SHA-256
- 署名者、timestamp
- Mac notary submission ID
- 第三者試験済みSHA
```

- [ ] **Step 6: 確認済み・未確認を分けて報告を書く**

報告は次の見出しを必須にする:

```markdown
# TOMOS Gate R0 検証報告

## 開始点
## Ownership
## Release manifest contract
## 実行して合格
## Baselineで失敗
## 環境不足で未実行
## 承認待ち
## Gate判定
```

- [ ] **Step 7: R0を判定する**

合格条件:

- masterと承認済み設計のPhase Orderが一致。
- U0、M0、D0のownerとshared fileが一意。
- release manifest必須項目が固定。
- baseline failureと環境不足が分離。
- Global Verification Matrixとdesktop testがすべてexit 0。
- 製品コード、版番号、成果物を変更していない。

合格時だけマスター台帳のGate R0を`検証中`から`合格`へ変更する。

- [ ] **Step 8: 最終検証を実行する**

Run:

```bash
python3 scripts/test_post_gate_c_master.py
git diff --check
git status --short --branch
```

Expected: 文書契約が合格し、差分はR0報告とマスター台帳だけ。

- [ ] **Step 9: Director review後にcommitする**

停止条件: ユーザーのcommit承認がない場合は実行しない。

```bash
git add \
  docs/tomos-post-gate-c-r0-gate-report-2026-08-01.ja.md \
  docs/superpowers/plans/2026-07-23-tomos-evolution-master.md
git commit -m "docs: record TOMOS post-Gate-C Gate R0"
```

### Task 4: U0・M0・D0を担当へ引き渡す

**Files:**
- Create: `docs/superpowers/plans/2026-08-01-tomos-beginner-install-docs.md`
- Create: `docs/superpowers/plans/2026-08-01-tomos-first-run-onboarding.md`
- Create: `docs/superpowers/plans/2026-08-01-tomos-support-diagnostics.md`
- Create: `docs/superpowers/plans/2026-08-01-tomos-release-traceability.md`
- Create: `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md`

**Interfaces:**
- Consumes: Gate R0合格報告
- Produces: U0、U1、U2、M0の独立implementation plan、D0の承認用design

- [ ] **Step 1: ユーザー対応へU0計画を指示する**

U0計画の必須範囲:

```text
README.ja.md
README.en.md
docs/install-students.ja.md
docs/install-macos-students.ja.md
docs/install-windows-students.ja.md
docs/github-release-guide.ja.md
docs/native-installers.ja.md
docs/release-checklist.ja.md
scripts/test-student-install-docs.py
```

必須条件:

- Macは公証済みPKG、Windowsは署名済みMSI。
- ZIP、`.command`、`.bat`を初心者向け正規導線にしない。
- GitHubの`Source code`を選ばない。
- Ollamaは別途必要。
- Windows署名済みMSIがGate D3に合格するまで正式版と表示しない。
- U1のUI実装、U2の診断実装はこの計画へ混ぜない。
- U0は内部draftと静的文書契約までで合格とし、実在しない版・SHAを書かない。
- D3のartifact名・SHA readback後、U0Fで最終公開文面を確定する。

- [ ] **Step 2: ユーザー対応へU1 / U2計画を指示する**

U1計画`docs/superpowers/plans/2026-08-01-tomos-first-run-onboarding.md`:

- Ownerはユーザー対応。
- 入口はU0、M0、D0合格。
- 「PC確認→Ollama→標準AI→最初の質問」の4段階。
- Ollama未導入・停止でも10.0秒以内に案内画面を表示。
- 新しいAI回答は止めるが、既存データ閲覧とSkill管理を止めない。
- U2の診断収集を混ぜない。

U2計画`docs/superpowers/plans/2026-08-01-tomos-support-diagnostics.md`:

- Ownerはユーザー対応。
- 入口はU1合格。
- 固定allowlistだけから診断情報を作り、会話、path、環境変数、secretを含めない。
- main window起動失敗時もローカルで診断情報を取得できる。
- 第三者試験票、新規、更新、削除・再導入、rollbackを含む。
- 外部送信、Memory保存、自動永続化をしない。

- [ ] **Step 3: エンジニア2へM0計画を指示する**

M0計画の必須範囲:

```text
server.py
Gemma4_12B_Web.command
Gemma4_12B_全部起動.command
Gemma4_12B_Web.bat
Gemma4_12B_All_Start.bat
src-tauri/Cargo.toml
src-tauri/Cargo.lock
src-tauri/tauri.conf.json
scripts/test-desktop-release-version.py
scripts/test-pwa-assets.js
scripts/test-agent-reach-routing-smoke.py
scripts/release_manifest.py
scripts/test_release_manifest.py
scripts/make-macos-tauri-pkg.sh
scripts/release-gate-macos-tauri.sh
scripts/make-windows-msi.py
scripts/test_macos_tauri_bundle.py
scripts/test_macos_tomos_resources.py
scripts/test_mac_pkg_signing.py
scripts/test_audit_macos_tauri_release.py
scripts/test_sign_macos_tauri_app.py
docs/releases/
```

必須条件:

- 次の正式候補版は`0.8.234`。
- version、tag、source commit、tree SHA、artifact SHAを一意に対応。
- manifest validatorはPython標準ライブラリだけを使う。
- M0では署名、公証、artifact生成、公開を行わない。
- 現v0.8.233 PKGを`origin/main`由来として再利用しない。

- [ ] **Step 4: エンジニア2へD0設計を指示する**

D0設計の必須判断:

```text
Windows code-signing証明書とtimestamp
Windows Python runtimeの取得元・license・SHA
WebView2の導入/検出
%LOCALAPPDATA%\ShibaPapa Studio\TOMOS AI
旧Library\Application Support保存先の検出と承認コピー
stable UpgradeCode / version別ProductCode
初回署名版と次版以降のrollback差
署名secretを使うCIの承認境界
```

D0設計だけではcertificate取得、secret登録、workflow実行、実機installを行わない。

- [ ] **Step 5: 後続plan名と入口を固定する**

| Plan | Entry | Approval stop |
| --- | --- | --- |
| `2026-08-01-tomos-macos-v0.8.234-release.md` | M0合格 | Developer ID、公証、install、第三者試験 |
| `2026-08-01-tomos-windows-signed-msi.md` | D0設計承認 | 依存、runtime取得、署名secret CI |
| `2026-08-01-tomos-windows-real-machine-release.md` | D1合格 | install、uninstall、第三者試験 |
| `2026-08-01-tomos-v0.8.234-release-publication.md` | Final Mac M2、D3、U0F合格 | tag、push、Release公開 |

Windows D3後は最終release commitからMac M1/M2を再実行し、固定した最終PKG/MSIのSHAで第三者smokeを行う。再buildしたplatformは第三者smokeをやり直す。

- [ ] **Step 6: Directorが5文書の境界を確認する**

確認条件:

- 同じshared fileを複数planが所有していない。
- U0は文書だけ、M0は追跡契約だけ、D0はWindows設計だけ。
- U1とU2は別planであり、M1/M2、D1、D2/D3、REL0も上表の別plan。
- commit、依存、署名、実機、公開の停止点がある。

- [ ] **Step 7: ユーザーへ5文書の承認をまとめて依頼する**

このTaskでは各Gateの実装・commitを行わない。5文書が完成してDirector reviewに合格した時点で停止し、承認後だけU0、U1、U2、M0、D0を各専用worktreeで開始する。

## Existing Plan Handoffs

### Gate 4

入口:

```text
R0合格
  → Skill差分監査・テスト設計
U0 + M0 + D0合格
  → Skill専用worktreeで実装開始
配布shared file統合 + baseline再合格
  → Skill変更を製品へ統合
```

正本:

`docs/superpowers/plans/2026-07-23-tomos-markdown-skill-manager.md`

### Voice V0 / V1

入口: Gate 4合格後。candidate取得前に個別承認。

正本:

`docs/superpowers/plans/2026-07-23-tomos-voice-engine-evaluation-lab.md`

### Model E0 / E1

入口: Gate 4合格後。artifact取得前に個別承認。Voiceと同時実行しない。VoiceとModelを両方実施する場合だけGate V1後にModelを開始する。

正本:

`docs/superpowers/plans/2026-07-23-tomos-model-evaluation-lab.md`

### Stage X

- Company Memory: Gate REL0とGate 4後にspecから開始。
- P2P: Gate REL0、Gate 4、CM0後にfixture-only specから開始。
- VRM0: Gate REL0後に初期OFF・表示専用specから開始。
- VRM1: VRM0後にPhase 3 contractまたは別採用Gate承認済みengineだけを接続。

## Program Stop Rules

次の場合は担当者が停止し、Directorへ返す。

- `HEAD`、版、source、artifactの対応が一意でない。
- masterと承認済み設計のPhase Orderが一致しない。
- shared fileを別担当が変更中。
- 未承認の依存、artifact、証明書、secret、実機変更が必要。
- baseline failureと新規失敗を分離できない。
- 既存Skill、Voice、Model詳細planの変更が必要。
- U0、M0、D0の範囲を越える製品変更が必要。

## First Tranche Completion

- `scripts/test_post_gate_c_master.py`が合格。
- masterと承認済み設計の順序が一致。
- R0報告に開始commit、tree、clean状態、ownership、baseline、未実行、承認待ちがある。
- 製品コード、版番号、成果物、既存Skill/Voice/Model planに差分がない。
- Gate R0が`合格`。
- U0、M0、D0の次担当と別文書境界が確定。
