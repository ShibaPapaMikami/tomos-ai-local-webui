# TOMOS 初回4段階オンボーディング Implementation Plan

**Gate:** U1

**Owner:** ユーザー対応

**Entry:** Gate U0、Gate M0、Gate D0がすべて合格

**Goal:** Ollama未導入・停止時も10.0秒以内に案内を表示し、PC確認から最初の質問まで
4段階で進める。

**Architecture:** `/api/health`と既存モデル取得APIを変更せず利用し、
`web/onboarding.js`へ状態機械を分離する。`web/app.js`は接着に限定し、初期表示を
health応答でblockしない。

## Source of Truth

- `AGENTS.md`
- `DESIGN.md`
- `VOICE.md`
- `MEMORY.md`
- `PLUGIN.md`
- `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- `docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md`
- `docs/tomos-post-gate-c-r0-gate-report-2026-08-01.ja.md`
- `docs/superpowers/plans/2026-08-01-tomos-post-gate-c-program.md`
- `docs/superpowers/plans/2026-08-01-tomos-beginner-install-docs.md`
- `docs/superpowers/plans/2026-08-01-tomos-release-traceability.md`
- `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md`

U2は`docs/superpowers/plans/2026-08-01-tomos-support-diagnostics.md`へ分離する。

## Scope

### Owned files

```text
web/onboarding.js
scripts/test-first-run-onboarding.js
web/index.html
web/styles.css
web/i18n.js
web/app.js
web/sw.js
scripts/test-pwa-assets.js
scripts/test-desktop-shell-contract.py
```

U1実装中だけユーザー対応を上記shared fileの唯一のownerとする。

### Read-only references

```text
server.py
web/models.js
web/settings.js
web/desktop-starting.html
web/desktop-starting.js
src-tauri/src/runtime.rs
```

既存APIで契約を満たせない場合は勝手に変更せず、Directorへowner変更を申請する。

### Prohibited changes

- U2の診断allowlist、コピー、第三者試験票
- server、Tauri runtime、installer、Windows runtime
- Memory、Knowledge、Skillのschema
- Ollama、モデル、依存の自動download
- 版、manifest、署名、公証、artifact、公開

## Interfaces

### Consumes

- U0合格の初心者向け用語
- M0合格のversion / source表示契約
- D0合格のWindows runtime / WebView2 / 保存先契約
- `/api/health`のPC、Ollama、model状態
- `/api/models/pull`と`/api/models/pull/status`
- Desktop B3の確認、承認copy、元に戻す導線

### Produces

- `PCを確認 → Ollamaを確認 → 標準AIを取得 → 試しに質問`の4状態
- 現在位置、完了、不足、再試行中の表示
- 不足理由、Ollama公式導入先、再診断、終了
- AI回答だけを安全に止める状態
- U2が接続する安定したerror / onboarding状態境界

## Fixed Decisions

1. 案内shellはhealth promise完了を待たず表示する。
2. 起動から10,000ms以内に不足理由と操作を表示する。
3. Ollama確認はbackgroundでtimeout可能にする。
4. 公式Ollama linkはユーザー操作時だけ開く。
5. 標準AI取得は通信量説明とユーザー操作後だけ開始する。
6. Ollamaまたは標準AI不足時は新しいAI回答だけをdisabledにする。
7. 既存チャット、Memory、Knowledge、設定、Skill管理は閲覧・管理可能にする。
8. 同梱Python版ではPython手動操作を要求しない。
9. 旧データは既存B3のpreview、承認copy、rollbackへ接続する。
10. 診断収集はU2まで実装しない。

## Approval Stops

- U0、M0、D0のいずれかが未合格なら開始しない。
- 製品UI shared fileはDirectorがU1へownerを固定した後だけ編集する。
- 外部linkを実際に開く、モデルを取得する、アプリを起動する手動試験は個別承認を得る。
- 依存追加、server/Tauri変更、runtime/installer変更が必要なら停止する。
- commit、pushは明示承認まで行わない。

## Tasks

### Task 1: U1基準線と既存interfaceを固定する

- [ ] U0、M0、D0の合格をreadbackする。
- [ ] 更新済み正本からU1専用worktreeを作る。
- [ ] Owned filesのownerがユーザー対応一名であることを記録する。
- [ ] health、model pull、B3導線をread-onlyで確認する。
- [ ] 現行Tauri windowの終了interfaceをreadbackし、UI adapterが呼ぶ既存callback名と
  成功・失敗時の挙動をU1実装証跡へ記録する。
- [ ] 既存interfaceだけで安全に終了できない場合は、ブラウザー用代替を推測せず、
  Tauri owner変更が必要として停止する。
- [ ] 既存回帰を実行し、baseline failureを記録する。

Run:

```bash
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test-desktop-shell-contract.py
git status --short --branch
```

Expected: 既知failureと新規failureを分離できる。

### Task 2: 失敗する状態機械testを書く

**Create:** `scripts/test-first-run-onboarding.js`

- [ ] 4段階の順序と完了条件をfixtureで固定する。
- [ ] Ollama missing、offline、timeout、runningを固定する。
- [ ] health未解決でも10,000ms以内に案内が見えることをfake timerで検査する。
- [ ] 標準AIの未取得、取得中、成功、失敗、再試行を検査する。
- [ ] 二重取得、未完了時の回答送信を拒否する。
- [ ] AI送信以外の既存データ閲覧と管理を維持する。
- [ ] 公式導入、再診断、終了、最初の質問focusを検査する。
- [ ] 日本語literal、aria-live、disabled理由を検査する。

Run:

```bash
node scripts/test-first-run-onboarding.js
```

Expected: `web/onboarding.js`未作成でFAIL。

### Task 3: 純粋なonboarding helperを実装する

**Create:** `web/onboarding.js`

- [ ] health payloadを4段階へ変換する純粋関数を作る。
- [ ] 画面表示deadlineとhealth timeoutを別にする。
- [ ] model pullの状態遷移とrequest中lockを実装する。
- [ ] `canSendNewAiRequest`と閲覧可能状態を分離する。
- [ ] DOM、fetch、localStorageを純粋判定から分離する。

Run:

```bash
node scripts/test-first-run-onboarding.js
node --check web/onboarding.js
```

Expected: helper契約がexit 0。

### Task 4: UIへ最小接続する

- [ ] `index.html`へ4段階regionと操作を追加する。
- [ ] `i18n.js`へ日本語正本と英語fallbackを追加する。
- [ ] `styles.css`へPC / 390px幅、focus、disabled、statusを追加する。
- [ ] `app.js`はhealth、model pull、chat送信との接着だけにする。
- [ ] 状態機械へ`requestExit` callbackを注入し、Task 1で確認した既存Tauri
  window終了interfaceだけへ接続する。
- [ ] `sw.js`とPWA資産testへ`onboarding.js`を追加する。
- [ ] Ollama不足時も管理画面と既存データ経路を隠さない。
- [ ] 旧データ検出時はB3画面へ案内し、移行を自動開始しない。

### Task 5: 10秒・失敗・回帰契約を合格させる

Run:

```bash
node scripts/test-first-run-onboarding.js
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test-desktop-shell-contract.py
node --check web/onboarding.js
node --check web/app.js
git diff --check
git status --short --branch
```

Expected:

- 全command exit 0。
- 10,000ms契約をfake timerで再現可能。
- 差分はOwned filesだけ。

### Task 6: 承認付きアプリ手動試験へ引き渡す

ユーザー承認後だけ、アプリ版で次を確認する。

- [ ] Ollamaなし、停止、起動済み。
- [ ] 標準AIなし、取得済み。
- [ ] 旧データあり。
- [ ] 案内表示までの実測が10.0秒以内。
- [ ] 不足時も既存データ閲覧とSkill管理が可能。
- [ ] 外部linkとmodel取得は各操作前に意図を確認。

手動試験でデータ削除、Memory自動保存、未承認downloadを行わない。

## Verification

```bash
node scripts/test-first-run-onboarding.js
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test-desktop-shell-contract.py
node --check web/onboarding.js
node --check web/app.js
git diff --check
git diff --name-only
git status --short --branch
```

## Handoff

- U2へ4段階とstable error stateを渡す。
- U2はU1 merge後の正本から専用worktreeを作る。
- U2開始時に重複するWeb shared fileのownerをユーザー対応へ移管する。
- U0Fへ初回導線の確定用語だけを返し、artifact値は返さない。
- M1/M2、D1〜D3のinstaller試験は別planへ渡す。

## Stop Rules

- U0、M0、D0の未合格。
- 10.0秒達成にTauri runtime所有権の変更が必要。
- 「終了」を接続できる既存Tauri interfaceがなく、Tauri owner変更が必要。
- U2診断、M1/M2、D1〜D3、U0Fへ範囲が広がる。
- dependency、外部取得、実機変更が未承認。
- 同じWeb shared fileを別ownerが変更中。
- baseline failureと新規failureを分離できない。

停止時は確認済み、未確認、必要owner、必要承認をDirectorへ返す。
