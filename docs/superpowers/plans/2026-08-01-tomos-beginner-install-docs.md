# TOMOS 初心者向け導入文書 Implementation Plan

**Gate:** U0

**Owner:** ユーザー対応

**Entry:** Gate R0合格

**Goal:** Macの公証済みPKGと、Windowsの限定テスト・将来の正式公開を混同しない
OS別内部draftと静的文書契約を作る。

**Architecture:** 共通入口からOS別1ページへ分岐し、未確定artifact値を本文へ埋め込まず、
U0Fで最終artifact名、URL、SHAを反映できる文書構造にする。

## Source of Truth

- `AGENTS.md`
- `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- `docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md`
- `docs/tomos-post-gate-c-r0-gate-report-2026-08-01.ja.md`
- `docs/superpowers/plans/2026-08-01-tomos-post-gate-c-program.md`
- `docs/superpowers/plans/2026-08-01-tomos-first-run-onboarding.md`
- `docs/superpowers/plans/2026-08-01-tomos-support-diagnostics.md`
- `docs/superpowers/plans/2026-08-01-tomos-release-traceability.md`
- `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md`
- `docs/superpowers/plans/2026-08-03-tomos-windows-free-distribution.md`

矛盾時はマスター計画とGate R0報告を優先し、推測でartifact情報を補わない。

## Scope

### Owned files

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

### Read-only references

- M0のversion、source、artifact追跡契約
- W0からW2のWindows未署名限定テスト状態
- Gate S0またはD0からD3の選択済みWindows公開状態
- Gate Cで確認済みのMac v0.8.233事実
- U1の初回4段階とU2の診断用語

### Prohibited changes

- 製品UI、初回導線、診断収集
- PKG/MSI生成、署名、公証、公開
- 版番号、Release、tag、artifact
- ZIP、`.command`、`.bat`経路自体の削除
- U0Fの最終artifact readback

## Interfaces

### Consumes

- Gate R0合格報告
- M0の版・source・artifact追跡契約
- W0からW2のWindows未署名限定テスト判定
- 選択済みWindows公開経路の判定
- Mac署名・公証の確認済み表現

### Produces

- Mac / WindowsのOS別1ページ
- Mac PKG、Windows限定テスト、将来のWindows正式公開を分けた内部draft
- U1 / U2が再利用する短い日本語用語
- U0Fが最終artifact名、URL、SHAを反映する挿入位置
- `scripts/test-student-install-docs.py`による静的契約

## Fixed Decisions

1. Mac正規導線はDeveloper ID署名・Apple公証済みPKGだけ。
2. Windowsの現在経路は未署名MSIによる開発・限定テストだけとし、初心者向け正規導線と表示しない。
3. Windows正式公開はGate S0後のMicrosoft Storeまたは明示再承認したD0からD3の
   有料直接配布のどちらか一つが合格するまで準備中と表示する。
4. ZIP、`.command`、`.bat`、GitHubの`Source code`を初心者へ選ばせない。
5. Ollama本体とモデルは別途必要と明記する。
6. 同梱Python版ではPythonの手動導入やターミナル操作を要求しない。
7. 未署名MSIでは警告、発行元なし、SHA確認、限定テストであることを同じ画面に表示する。
8. U0合格は内部draftと静的文書契約まで。
9. 実在しない版、artifact名、URL、SHAを確定値として書かない。
10. 選択済みWindows公開経路の合格後に、最終値反映と公開文面確定をU0Fで行う。

## Approval Stops

- 本計画のDirector reviewとユーザー承認前は実装しない。
- 実在artifact名、SHA、Release URLが必要になったらU0Fまで停止する。
- GitHub Release更新、外部公開、実機installは個別承認まで停止する。
- U1 UI、U2診断、M0/D0配布実装が必要なら担当へ返す。
- commit、pushはそれぞれ明示承認まで行わない。

## Tasks

### Task 1: 専用worktreeと現状矛盾を固定する

**Read:** Owned filesの既存8文書

- [ ] 更新済み`origin/main`からU0専用worktreeを作る。
- [ ] `HEAD`、`HEAD^{tree}`、`origin/main`、statusを記録する。
- [ ] ZIP、script、OS警告回避、旧launcherの初心者向け記述を一覧化する。
- [ ] Mac PKG方針とWindows未署名状態の確認済み記述を分ける。
- [ ] 別ownerがOwned filesを変更中なら停止する。

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git rev-parse origin/main
```

Expected: clean、HEADとorigin/mainが一致。

### Task 2: 失敗する静的文書契約を書く

**Create:** `scripts/test-student-install-docs.py`

- [ ] 必須9ファイルの存在を検査する。
- [ ] READMEと共通入口がOS別ページへ到達できることを検査する。
- [ ] PKG / MSI、署名、公証、Ollama別途必要を必須tokenにする。
- [ ] 初心者向け手順がZIP、`.command`、`.bat`、`Source code`を選択肢に
  していないことを検査する。
- [ ] Windows D3前の正式版表現を拒否する。
- [ ] 実在値に見える未確認SHA、URL、artifact名を拒否する。
- [ ] OS、CPU、空き容量、通信量、更新、復旧の項目を検査する。

Run:

```bash
python3 scripts/test-student-install-docs.py
```

Expected: 旧導線または未作成OS別ページによりFAIL。

### Task 3: 共通入口とOS別1ページを最小修正する

**Modify:** README、共通学生ガイド、既存Release文書

**Create:** Mac / Windows学生ガイド

- [ ] 共通入口をMac / Windowsの2択にする。
- [ ] Macは署名・公証済みPKGの取得、導入、初回起動、更新、復旧を記述する。
- [ ] Windowsは未署名MSIの限定テストdraftとし、選択済み公開経路の合格前は
  「正式なWindows公開経路は準備中」と表示する。
- [ ] GitHubの自動生成`Source code`を選ばない注意を記述する。
- [ ] Ollama、必要容量、通信量、標準AI取得を事前条件として明示する。
- [ ] 旧ZIP / scriptは開発・復旧用の既存経路として残し、初心者の正規手順から外す。
- [ ] 未確定値は「U0Fでreadback後に確定」と文章で示し、架空値を置かない。

### Task 4: 文書契約を合格させる

Run:

```bash
python3 scripts/test-student-install-docs.py
python3 scripts/test_post_gate_c_master.py
python3 -m py_compile scripts/test-student-install-docs.py
git diff --check
git status --short --branch
```

Expected:

- 全command exit 0。
- 差分はOwned filesだけ。
- 製品コード、版番号、artifactに差分なし。

### Task 5: U0判定とhandoffを作る

- [ ] 内部draftであることを各入口に明記する。
- [ ] Mac/Windowsの用語をU1/U2へ渡す。
- [ ] M0のsource契約とD0〜D3状態を確定値として先取りしていないことをreviewする。
- [ ] U0合格後も公開せず、U0F待ちとして停止する。
- [ ] Director review後、commit承認を得る。

## Verification

```bash
python3 scripts/test-student-install-docs.py
python3 scripts/test_post_gate_c_master.py
git diff --check
git diff --name-only
git status --short --branch
```

手動readbackでは、学生役がREADMEから自分のOSページへ迷わず移動でき、PKG/MSI以外を
選ばないことを文面だけで確認する。Release操作やinstaller実行は行わない。

## Handoff

- U1へ4段階で使う初心者向け用語を渡す。
- U2へ復旧と問い合わせの用語を渡す。
- M0へ公開文書が必要とするmanifest項目を返す。
- D3後、U0Fへ最終artifact名、URL、SHAのreadbackを依頼する。
- U0Fは公開SHAと第三者試験SHAの一致後にだけ文面を確定する。

## Stop Rules

- M0の版/source対応またはD3の署名状態を確定値として必要とする。
- U1、U2、M0、D0のOwned filesへ変更が必要。
- 未承認artifact、外部公開、実機操作、依存追加が必要。
- baseline failureと変更起因failureを分離できない。
- 同じOwned filesを別ownerが変更中。

この場合は正本を広げず、Directorへ対象、理由、必要な承認を返す。
