# TOMOS Windows無料開発配布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 個人開発中のTOMOSを、有料コード署名を契約せず、未署名Windows x64 MSIとして安全にbuild・実機試験できる状態にする。

**Architecture:** Windows配布を、現在使う「無料の開発・限定テスト経路」と、将来選択する「Microsoft Store」または「有料のWeb直接配布経路」に分離する。現在の経路では未署名MSIを公開候補にせず、artifact名、画面、文書で未署名であることを明示し、署名済みと誤認させない。既存のsupply-lock、runtime、WebView2、UpgradeCodeの読取証跡は削除せず、将来の有料署名経路だけがread-onlyで再利用する。

**Tech Stack:** Python 3.11標準ライブラリ、Rust / Tauri 2、WiX 4、PowerShell、GitHub Actions、Markdown。

## Global Constraints

- 申請主体は個人であり、DigiCert、KeyLocker、コード署名証明書を契約しない。
- DigiCert、SSL.com、Microsoft Artifact Signingを現在の必須dependencyにしない。
- 現在のWindows経路は`development_unsigned`と`private_test_unsigned`の2種類だけ。
- 未署名MSIを正式版、署名済み、安全性確認済み、SmartScreen回避済み、初心者向け正規版と表示しない。
- 未署名MSIはGitHub Releaseへ自動添付しない。外部公開はartifactごとの別承認を必須にする。
- `.github/workflows/build-installers.yml`は手動実行だけを正規入口とし、tag pushで未署名MSIを生成しない。
- build artifact名とMSI隣接のnoticeに`UNSIGNED`と`TEST ONLY`を明示する。
- Windowsが表示する警告を回避する操作や、利用者へセキュリティ機能の無効化を案内しない。
- Windows実機試験では警告の実表示、発行元表示、新規導入、更新、削除、再導入、データ保持を記録する。
- Microsoft Storeは将来候補としてread-only調査だけを行い、アカウント作成、本人確認、登録料支払い、package提出を行わない。
- 有料の直接配布署名は、個人での一般公開、企業導入、またはStore不採用が確定した場合だけ別計画として再開する。
- `scripts/windows_supply_lock.py`、`scripts/test_windows_supply_lock.py`、`docs/windows-release/**`の既存成果は削除、弱体化、署名済み判定への流用をしない。
- W1 private-testの実行後は`docs/windows-release/windows-unsigned-build-evidence.md`へsource version、source commit、tree、run ID、artifact name、size、SHA-256を記録する。M0 v1 0.8.234 manifestへW1 private-testの値を記録しない。
- Memory、Knowledge、教材、設定、chat、modelをuninstallで削除しない。
- secret、token、個人名、user名、full path、会話、Memory、Knowledgeをlogまたはartifactへ出さない。
- dependency追加、workflow変更、Actions実行、artifact download、実機install、外部公開、commit、pushは個別承認を得る。
- この計画の作成だけでは製品コード、workflow、版番号、artifact、Releaseを変更しない。

---

## Gate Order

```text
W0: 無料配布方針と誤公開防止契約
  → W1: 未署名MSIを手動buildし、非公開artifactとして固定
  → W2: Windows実機で限定テスト
  → Product laneを継続

将来の公開判断
  ├─ S0: Microsoft Store適格性・費用・package要件をread-only確認
  │    → 明示承認後だけStore登録計画
  └─ D0: 有料のWeb直接配布署名を再開
       → 別承認後だけ証明書契約・secret・署名
```

W0からW2は正式なWindows一般公開を許可しない。S0またはD0のどちらも選ばない場合、
TOMOSのWindows版は開発・限定テスト状態を維持する。

## File and Ownership Map

| Unit | Files | Responsibility |
| --- | --- | --- |
| 方針正本 | `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`、本計画 | W0からW2、将来のS0 / D0、承認境界 |
| 旧署名経路 | `docs/superpowers/plans/2026-08-01-tomos-windows-signed-msi.md`、`docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md` | 保留中の任意経路。現在は実行しない |
| Unsigned CI | `.github/workflows/build-installers.yml`、`scripts/test_windows_unsigned_distribution.py` | 手動build、誤公開防止、artifact表示 |
| MSI build | `scripts/make-windows-msi.py`、`scripts/test_windows_msi_launcher.py` | WiX生成、version、identity、launcher |
| 利用者文書 | `docs/native-installers.ja.md`、`docs/install-students.ja.md`、`docs/install-windows-students.ja.md`、`docs/release-checklist.ja.md` | 限定テストと正式公開を混同しない案内 |
| W1 build証跡 | `docs/windows-release/windows-unsigned-build-evidence.md` | source version、source commit、tree、run ID、artifact name、size、SHA-256 |
| 実機証跡 | `docs/windows-release/windows-unsigned-test-evidence.md` | MSI SHA、Windows版、警告、導入・更新・削除・再導入、データ保持 |
| 将来調査 | `docs/windows-release/microsoft-store-readonly-assessment.md` | 個人適格性、費用、MSI / MSIX要件、署名、審査、公開境界 |

`server.py`、`web/**`、Skill、Voice、Memory、Plugin、ModelはW0 / W1では変更しない。
W2で不具合を見つけた場合は、再現テストを作る別Taskへ返し、本計画の文書Taskへ混ぜない。

---

### Task 1: W0の無料配布方針を正本へ固定する

**Files:**
- Modify: `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- Modify: `docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md`
- Modify: `docs/superpowers/plans/2026-08-01-tomos-post-gate-c-program.md`
- Modify: `docs/superpowers/plans/2026-08-01-tomos-beginner-install-docs.md`
- Modify: `docs/superpowers/plans/2026-08-01-tomos-windows-signed-msi.md`
- Modify: `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md`
- Modify: `docs/windows-release/windows-supply-evidence.md`
- Create: `docs/superpowers/plans/2026-08-03-tomos-windows-free-distribution.md`

**Interfaces:**
- Consumes: ユーザー判断「個人配布」「DigiCertを契約しない」
- Produces: W0 / W1 / W2、将来S0 / D0、Gate 4を有料署名から分離した正本

- [ ] **Step 1: 最新mainと既存変更をreadbackする**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git rev-parse origin/main
```

Expected: 専用branch、clean baseline、`HEAD == origin/main`。

- [ ] **Step 2: マスター計画をW0 / W1 / W2へ更新する**

固定する状態:

```text
Gate W0 = 無料配布方針
Gate W1 = 未署名の非公開MSI artifact
Gate W2 = Windows実機限定テスト
Gate D0〜D3 = 任意の有料Web直接配布経路として保留
Gate S0 = 将来のMicrosoft Store read-only調査
Gate 4 entry = U0、M0、W0
```

- [ ] **Step 3: 旧署名計画を保留状態へ変更する**

旧計画の実装済みsupply evidenceは保持し、certificate購入、secret、signing job、
signed candidate、DigiCert provider選定をactive taskから外す。

- [ ] **Step 4: 文書整合を確認する**

Run:

```bash
rg -n "Gate W0|Gate W1|Gate W2|Gate S0|有料署名.*保留|DigiCert.*契約しない" \
  docs/superpowers/plans/2026-07-23-tomos-evolution-master.md \
  docs/superpowers/plans/2026-08-03-tomos-windows-free-distribution.md
git diff --check
```

Expected: 全Gateと停止理由が確認でき、whitespace errorなし。

- [ ] **Step 5: commit stop**

文書だけをstage対象として一覧確認し、commitは別承認まで実行しない。

---

### Task 2: 手動の未署名MSI workflowをfail-closedにする

**Files:**
- Create: `scripts/test_windows_unsigned_distribution.py`
- Modify: `.github/workflows/build-installers.yml`

**Interfaces:**
- Consumes: W0の`development_unsigned | private_test_unsigned`
- Produces: tagで起動せず、Releaseへ公開せず、`UNSIGNED-TEST-ONLY` artifactだけを作るworkflow

- [ ] **Step 1: workflow変更の個別承認で停止する**

Directorは変更file、trigger、job、artifact名、外部通信、Actions課金範囲を示す。
承認前に`.github/workflows/build-installers.yml`を変更しない。

- [ ] **Step 2: 失敗するworkflow境界testを書く**

Create `scripts/test_windows_unsigned_distribution.py`:

```python
#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-installers.yml"


def test_unsigned_workflow_is_manual_and_non_public() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = workflow_section(text)
    uploads = artifact_upload_sections(text)
    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert "tags:" not in trigger
    assert len(uploads) == 1
    upload = uploads[0]
    assert "actions/upload-artifact@" in upload
    assert artifact_upload_paths(upload) == [
        "dist/TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.msi"
    ]
    assert "TOMOS_AI-v0.8.233-windows.msi" not in upload
    assert "gh release" not in text
    assert "actions/create-release" not in text
    assert "softprops/action-gh-release" not in text


def workflow_section(text: str) -> str:
    return text.split("jobs:", 1)[0]


def artifact_upload_sections(text: str) -> list[str]:
    marker = "actions/upload-artifact@"
    sections = []
    cursor = 0
    while True:
        start = text.find(marker, cursor)
        if start == -1:
            return sections
        next_step = text.find("\n      - name:", start)
        end = len(text) if next_step == -1 else next_step
        sections.append(text[start:end])
        cursor = end


def artifact_upload_paths(section: str) -> list[str]:
    paths = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("path:"):
            paths.append(stripped.split(":", 1)[1].strip().strip("'\""))
    return paths


if __name__ == "__main__":
    test_unsigned_workflow_is_manual_and_non_public()
    print("Windows unsigned distribution contract tests passed")
```

- [ ] **Step 3: REDを確認する**

Run:

```bash
python3 scripts/test_windows_unsigned_distribution.py
```

Expected: 現行tag triggerまたは`UNSIGNED-TEST-ONLY`欠落でFAIL。

- [ ] **Step 4: workflowを最小修正する**

次を固定する。

```yaml
on:
  workflow_dispatch:
    inputs:
      version:
        description: "Test app version. This does not publish a Release."
        required: true
      channel:
        description: "development_unsigned or private_test_unsigned"
        required: true
        default: "development_unsigned"
```

artifact名:

```text
TOMOS-AI-UNSIGNED-TEST-ONLY-development_unsigned-0.8.233
TOMOS-AI-UNSIGNED-TEST-ONLY-private_test_unsigned-0.8.233
```

MSIはbuild後、upload前に次の限定テスト名へcopyし、通常名をartifactへ含めない。

```text
TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.msi
```

入力channelが2つの許可値以外ならbuild前に停止する。secret、Environment、
signing command、Release uploadを追加しない。

- [ ] **Step 5: GREENと既存回帰を確認する**

Run:

```bash
python3 scripts/test_windows_unsigned_distribution.py
python3 scripts/test_windows_msi_launcher.py
python3 scripts/test-desktop-release-version.py
git diff --check
```

Expected: 全command exit 0。

- [ ] **Step 6: commit stop**

workflowとtestだけをstage候補として示し、commit、push、Actions実行は別承認まで停止する。

---

### Task 3: 限定テスト用の案内を正式公開文書から分離する

**Files:**
- Create: `docs/install-windows-students.ja.md`
- Modify: `docs/install-students.ja.md`
- Modify: `docs/native-installers.ja.md`
- Modify: `docs/release-checklist.ja.md`

**Interfaces:**
- Consumes: W0の未署名表示契約
- Produces: 開発者・限定テスター用手順と、正式公開が未承認であることの明示

- [ ] **Step 1: 既存文書の誤認箇所をreadbackする**

Run:

```bash
rg -n "Windows|MSI|署名|正式|推奨|GitHub Release" \
  docs/install-students.ja.md \
  docs/native-installers.ja.md \
  docs/release-checklist.ja.md
```

Expected: 現在の未署名MSIを初心者向け公開物と誤認し得る行を一覧化。

- [ ] **Step 2: Windows限定テスト手順を作る**

必須見出し:

```text
対象
未署名であること
確認するSHA-256
Windows警告
インストール
最初の質問
アンインストール
データ保持確認
結果報告
正式公開との違い
```

「Windowsの保護機能を無効にする」「警告を常に無視する」「発行元を確認せず実行する」
という案内を禁止する。テスターはDirectorから受け取ったartifact名とSHAが一致した場合だけ進む。

- [ ] **Step 3: 共通学生ガイドを分岐させる**

Macの公開導線とWindows限定テスト導線を同じ「推奨」にしない。
Windows一般利用者には「正式なWindows公開経路は準備中」と表示する。

- [ ] **Step 4: 文書readbackを行う**

Run:

```bash
rg -n "UNSIGNED|未署名|限定テスト|正式なWindows公開経路は準備中" \
  docs/install-students.ja.md \
  docs/install-windows-students.ja.md \
  docs/native-installers.ja.md \
  docs/release-checklist.ja.md
git diff --check
```

Expected: 限定テスト、警告、正式公開停止が確認でき、whitespace errorなし。

- [ ] **Step 5: commit stop**

文書だけをstage候補として示し、commitと公開は別承認まで停止する。

---

### Task 4: W1の未署名MSIを非公開artifactとしてbuildする

**Files:**
- Read: `.github/workflows/build-installers.yml`
- Read: `scripts/make-windows-msi.py`
- Create after approved run: `docs/windows-release/windows-unsigned-build-evidence.md`

**Interfaces:**
- Consumes: W0合格、`codex/windows-unsigned-w1`のTask 2 workflow commit、固定version / source commit / tree
- Produces: `docs/windows-release/windows-unsigned-build-evidence.md`へ記録するsource version、source commit、tree、run ID、artifact name、size、SHA-256

W1 private-testの証跡はこの専用evidenceへだけ記録する。M0 v1 0.8.234 manifestへW1 private-testのversion、commit、tree、run ID、artifact name、size、SHA-256を記録しない。`scripts/release_manifest.py`は変更しない。

- [ ] **Step 1: Actions実行前readbackを行う**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git fetch origin codex/windows-unsigned-w1
git rev-parse origin/codex/windows-unsigned-w1
python3 scripts/test-desktop-release-version.py
```

Expected: clean、version整合、実行対象commitとtreeを表示し、`origin/codex/windows-unsigned-w1`が承認済みHEADと一致する。一致しない場合はActionsを実行しない。

- [ ] **Step 2: Actions実行の個別承認で停止する**

Directorはworkflow、version、channel、Windows runner、想定artifact名、保持期間、
課金有無を示す。承認前に`gh workflow run`を実行しない。

- [ ] **Step 3: 承認後だけworkflowを手動実行する**

Run:

```bash
gh workflow run build-installers.yml \
  --ref codex/windows-unsigned-w1 \
  -f version=0.8.233 \
  -f channel=private_test_unsigned
```

上記branchとversionがStep 1のreadbackと一致しない場合はworkflowを実行せず、
本計画を最新の確定値へ更新してから再承認を得る。

- [ ] **Step 4: runとartifactをread-only確認する**

Run:

```bash
TOMOS_RUN_ID="$(gh run list \
  --workflow build-installers.yml \
  --branch codex/windows-unsigned-w1 \
  --event workflow_dispatch \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')"
gh run view "$TOMOS_RUN_ID" --json status,conclusion,headSha,event,workflowName
gh run view "$TOMOS_RUN_ID" --json artifacts
```

Expected: `workflow_dispatch`、approved head SHA、success、
`TOMOS-AI-UNSIGNED-TEST-ONLY-private_test_unsigned-0.8.233`。内部file名は
`TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.msi`だけ。

- [ ] **Step 5: artifact downloadの別承認で停止する**

download先、容量上限、期待artifact名、実行禁止、削除方法を示す。
承認前にartifactを取得しない。

- [ ] **Step 6: 承認後にsize / SHAを記録する**

取得したMSIは実行せず、name、size、SHA-256をbuild evidenceへ記録する。
GitHub Releaseへ添付せず、公開URLを作らない。

---

### Task 5: W2のWindows実機限定テストを行う

**Files:**
- Read: `docs/install-windows-students.ja.md`
- Create: `docs/windows-release/windows-unsigned-test-evidence.md`

**Interfaces:**
- Consumes: W1のMSI SHA、既存データsnapshot、テスト用Windows 11端末
- Produces: 警告、新規、更新、削除、再導入、データ保持、最初の質問の実測結果

- [ ] **Step 1: 実機変更前の個別承認で停止する**

Directorは対象端末、現在のTOMOS版、MSI SHA、既存データ件数と容量、
install / uninstall / reinstall範囲を示す。

- [ ] **Step 2: install前snapshotをread-only取得する**

記録するのは件数、合計容量、metadata SHAだけ。会話本文、ファイル名、user名、
full pathを証跡へ保存しない。

- [ ] **Step 3: Windows警告を記録する**

警告の種類、表示された発行元、続行可否を記録する。
警告が表示されなかった場合も「署名済み」と推測せず、MSI署名状態をPowerShellで確認する。

Run on Windows:

```powershell
Get-AuthenticodeSignature .\TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.msi |
  Select-Object Status, StatusMessage
```

Expected: 未署名status。証明書subjectは存在しない。

- [ ] **Step 4: 新規導入と最初の質問を確認する**

TOMOS専用window、単一起動、Ollama案内、モデル取得状態、最初の質問、終了時process所有権を確認する。

- [ ] **Step 5: update / uninstall / reinstallを確認する**

既存データを削除せず、再導入後に件数、容量、metadata SHAが期待どおりであることを確認する。
schema変更がある場合は移行後snapshotを別値として記録し、同値を強制しない。

- [ ] **Step 6: W2判定を記録する**

W2合格は「限定テストに使える」を意味し、一般公開、署名済み、SmartScreen回避、
Microsoft Store適合を意味しない。

---

### Task 6: Gate S0でMicrosoft Storeをread-only評価する

**Files:**
- Create: `docs/windows-release/microsoft-store-readonly-assessment.md`

**Interfaces:**
- Consumes: 申請主体が個人、現行Tauri / WiX MSI、W2実測
- Produces: 個人適格性、登録費用、MSI / MSIX、署名、審査、更新、データ保持のconfirmed / unresolved / blocked表

- [ ] **Step 1: 調査範囲を固定する**

公式Microsoft LearnとPartner Center公開情報だけを使用する。アカウント作成、
ログイン、本人確認、登録、支払い、package提出、問い合わせ送信を行わない。

- [ ] **Step 2: 必須項目をread-only確認する**

```text
日本居住の個人アカウント適格性
登録費用と更新費用
実名またはpublisher表示
MSI提出可否
MSIX変換要否
Microsoftによる再署名
SmartScreenとSmart App Control
審査に送信されるデータ
更新、rollback、段階公開
既存GitHub Releaseとの併用
```

- [ ] **Step 3: 事実を3状態で保存する**

公式公開情報で確認できたものを`confirmed`、公開情報で確認できないものを`unresolved`、
アカウントまたは支払いが必要な確認を`blocked`とする。価格と要件を推測しない。

- [ ] **Step 4: Store登録の別承認で停止する**

S0だけではアカウント作成、本人確認、費用発生、package変換、提出を許可しない。

---

### Task 7: Windows一般公開経路を選択する

**Files:**
- Modify after decision: `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- Create after decision: 選択経路専用のimplementation plan

**Interfaces:**
- Consumes: W2実測、S0 read-only評価、利用者層、公開範囲、費用上限
- Produces: `store`、`direct_signed`、`private_test_only`のexact 1値

- [ ] **Step 1: 3経路を同じ表で比較する**

| 経路 | 費用 | 実名表示 | 利用者の警告 | 更新 | 必要な追加作業 |
| --- | --- | --- | --- | --- | --- |
| `store` | Gate S0で`confirmed`になった値だけを使用。未確認なら`blocked` | Gate S0で`confirmed`になった表示だけを使用 | Gate S0の公式確認結果 | Store契約 | Partner Center、package、審査 |
| `direct_signed` | D0再承認時の書面見積だけを使用。現在は`blocked` | 証明書subject | 署名後のWindows実測 | GitHub等 | 証明書、HSM、CI secret、署名 |
| `private_test_only` | 署名費用0 | 発行者なし | 未署名警告 | 手動 | 限定テスター管理 |

- [ ] **Step 2: 費用または個人情報を伴う経路の承認で停止する**

`store`はアカウント作成・登録費用、`direct_signed`は証明書契約・本人確認・secretを
それぞれ別承認にする。一つの承認でまとめて実行しない。

- [ ] **Step 3: 選択した経路だけを計画化する**

未選択経路をdependency、CI、公開文書へ混ぜない。
`private_test_only`を選ぶ場合、Gate REL0のWindows一般公開は停止したまま維持する。

---

## Verification Matrix

| Gate | 必須証拠 | 許可すること | 許可しないこと |
| --- | --- | --- | --- |
| W0 | 正本、旧署名経路の保留、承認境界 | 無料経路の実装 | build、公開、契約 |
| W1 | Actions run、head SHA、MSI name / size / SHA | 非公開artifactの取得準備 | Release公開、署名済み表示 |
| W2 | Windows警告、新規・更新・削除・再導入、データ保持 | 開発・限定テスト継続 | 一般公開、SmartScreen回避表明 |
| S0 | Microsoft公式のread-only表 | Store採否の判断 | アカウント作成、支払い、提出 |
| D0再開 | 必要性、費用上限、個人適格性、正式見積 | 有料署名の別計画 | 自動契約、secret入力 |

## Plan Completion

- W0からW2が合格し、個人開発中のWindows版を無料で実機確認できる。
- 未署名MSIが正式版、署名済み、初心者向け正規版として表示・公開されない。
- DigiCert / KeyLockerの契約、trial、本人確認、secret登録、署名が0件である。
- 既存supply evidenceとUpgradeCode証跡が将来用に保持される。
- Gate 4以降の製品開発が有料コード署名を待たずに進められる。
- 一般公開経路はS0またはD0の別判断まで停止し、未確認を完了扱いにしない。
