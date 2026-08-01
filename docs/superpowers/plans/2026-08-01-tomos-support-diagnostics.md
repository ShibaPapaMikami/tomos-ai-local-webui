# TOMOS 安全なサポート診断 Implementation Plan

**Gate:** U2

**Owner:** ユーザー対応

**Entry:** Gate U1合格

**Goal:** 固定allowlistだけからローカル診断情報を生成し、main window起動失敗時も
ユーザー操作で安全にコピーできるようにする。

**Architecture:** Tauri側の純粋なallowlist builderを診断正本にし、main windowと
軽量な起動失敗画面が同じformatterを使う。任意dictや生logを後からredactしない。

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
- `docs/superpowers/plans/2026-08-01-tomos-first-run-onboarding.md`
- `docs/superpowers/plans/2026-08-01-tomos-release-traceability.md`
- `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md`

## Scope

### Owned files

```text
src-tauri/src/support_diagnostics.rs
web/support-diagnostics.js
scripts/test-support-diagnostics.js
scripts/test-support-diagnostics-contract.py
docs/tomos-third-party-install-test-sheet.ja.md
src-tauri/src/lib.rs
web/desktop-starting.html
web/desktop-starting.js
web/index.html
web/styles.css
web/i18n.js
web/app.js
web/sw.js
scripts/test-desktop-shell-contract.py
scripts/test-pwa-assets.js
```

U1 merge後に上記Web shared fileのownerをU2へ移管し、並行編集しない。

### Read-only references

```text
server.py
app_paths.py
migration_manager.py
scripts/test_migration_manager.py
scripts/test-local-storage-transfer.js
```

### Prohibited changes

- U1の4段階状態機械と10.0秒契約
- telemetry、cloud support、診断自動送信
- 会話、Memory、Knowledge、ファイル内容の収集
- installer、署名、公証、artifact、公開
- M1/M2、D1〜D3の実機操作
- dependencyの無承認追加

## Interfaces

### Consumes

- U1合格のonboarding / stable error状態
- M0のversion、source commit、installer種別
- D0のWindows runtime、WebView2、保存先契約
- 既存PC診断
- Desktop B3のmigration preview、承認copy、rollback状態

### Produces

- 固定allowlistのdiagnostics objectと表示文
- main windowと起動失敗画面の同一診断
- 明示button操作によるclipboard copy
- Mac / Windows第三者試験票
- U0F、M2、D3へ渡すinstaller SHAと試験結果の記録欄

## Fixed Allowlist

収集可能:

```text
TOMOS version
source commit
OS name / build
CPU architecture / safe CPU label
memory size
installer kind
Ollama version / running state
bundled Python version / runtime state
standard model installed boolean
stable error code
port 54876 state
occurred-at timestamp
```

収集禁止:

```text
conversation body
file name
user name
absolute path / full save location
environment variables
token / Cookie / API key / secret
Memory / Knowledge / chat contents
raw stdout / stderr / stack trace
```

未知keyは除去でなく失敗にする。コピー対象はallowlist objectから生成した固定文字列だけ。

## Approval Stops

- U1合格とU1 merge後の専用worktreeをreadbackするまで開始しない。
- 新しいRust / JS / Python dependencyが必要なら停止し承認を得る。
- 診断範囲拡張、外部送信、Memory保存、自動永続化は仕様変更承認まで禁止する。
- 実機install、update、uninstall、第三者試験は対象とrollbackを示して個別承認を得る。
- commit、pushは明示承認まで行わない。

## Tasks

### Task 1: U2基準線とowner移管を固定する

- [ ] U1合格commitを含む更新済み正本から専用worktreeを作る。
- [ ] M0 / D0の版、installer、Windows境界をreadbackする。
- [ ] U1と重なるshared fileのownerをU2へ一意に移管する。
- [ ] migration / rollbackの既存回帰を実行する。
- [ ] dependency追加なしで安全なOS情報を取得できる範囲を固定する。

Run:

```bash
python3 scripts/test-desktop-shell-contract.py
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test_migration_manager.py
node scripts/test-local-storage-transfer.js
git status --short --branch
```

### Task 2: 失敗するallowlist契約testを書く

**Create:** Rust、Node、Python契約test

- [ ] schemaの完全一致と未知key拒否を検査する。
- [ ] user名、Mac/Windows path、env、token、Cookie、API key fixtureを拒否する。
- [ ] 会話、file名、Memory、raw error、stack trace fixtureを拒否する。
- [ ] stable error codeだけが表示されることを検査する。
- [ ] 初期表示、Memory、localStorage、fileへ自動保存しないことを検査する。
- [ ] fetch、sendBeacon、uploadを行わないことを検査する。
- [ ] main windowと失敗画面が同じformatterを使うことを検査する。

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml support_diagnostics
python3 scripts/test-support-diagnostics-contract.py
node scripts/test-support-diagnostics.js
```

Expected: 新規module未作成でFAIL。

### Task 3: Tauri allowlist builderを実装する

**Create:** `src-tauri/src/support_diagnostics.rs`

- [ ] 型付きfieldだけを受け取るbuilderを作る。
- [ ] error codeを既存固定値へ限定する。
- [ ] path、生log、任意JSONをinterfaceへ渡さない。
- [ ] server停止時もローカルで構築できる。
- [ ] dependencyを追加せず取得できない値は`unknown`として固定する。
- [ ] `lib.rs`へ最小command接着を追加する。

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml support_diagnostics
python3 scripts/test-support-diagnostics-contract.py
```

Expected: Rust / contract test exit 0。

### Task 4: 2画面の表示と明示copyを実装する

**Create:** `web/support-diagnostics.js`

- [ ] allowlist objectだけを整形する純粋formatterを作る。
- [ ] main windowへ「診断情報を表示」「コピー」を追加する。
- [ ] 起動失敗画面へ表示、コピー、再試行、終了を追加する。
- [ ] copyはbutton click handler内だけで実行する。
- [ ] 日本語literal、aria-live、disabled理由、copy成功/失敗を表示する。
- [ ] `sw.js`とPWA資産契約へ新規JSを追加する。

Run:

```bash
node scripts/test-support-diagnostics.js
node --check web/support-diagnostics.js
node --check web/desktop-starting.js
node --check web/app.js
```

### Task 5: 第三者試験票をTDDで固定する

**Create:** `docs/tomos-third-party-install-test-sheet.ja.md`

必須欄:

- clean / updateの初期状態
- OS build、CPU、RAM、空き容量
- installer名、version、SHA
- Ollama、Python、WebView2の初期状態
- 最初の回答までの時間、支援回数、合否
- 失敗手順、画面、error code、復旧結果
- 新規、更新、削除・再導入、復旧
- data、設定、app版rollbackの別欄
- 初回Windows署名版でapp rollbackが対象外となる条件
- 再build時に新SHAでsmokeをやり直す記録

静的testを先に失敗させ、必須欄を追加後に合格させる。

### Task 6: 全回帰と差分境界を確認する

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml
python3 scripts/test-support-diagnostics-contract.py
node scripts/test-support-diagnostics.js
python3 scripts/test-desktop-shell-contract.py
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test_migration_manager.py
node scripts/test-local-storage-transfer.js
node --check web/support-diagnostics.js
node --check web/desktop-starting.js
node --check web/app.js
git diff --check
git status --short --branch
```

Expected: 全command exit 0、差分はOwned filesだけ。

### Task 7: 承認付き第三者試験へ引き渡す

自動test合格後に停止する。Directorが対象installer、保存データ、rollback、安全条件を
示し、ユーザーが承認した場合だけ実機試験を行う。

## Verification

- allowlistのfield数と名前をRust / JS / Pythonで一致させる。
- 禁止fixtureが出力に1文字も含まれないことを確認する。
- main windowを起動できないfixtureでも同じ診断が作れることを確認する。
- copy前後でMemory、localStorage、file、networkに変更がないことを確認する。
- baseline failureと変更起因failureを別記録にする。

## Handoff

- U0Fへ公開文面用の第三者試験結果と最終installer SHAを渡す。
- M2 / D3へOS別試験票と復旧結果を渡す。
- 初回Windows署名版はapp rollback対象外を明記する。
- 再build時は当該platformの第三者smokeを再実行する。
- U2は診断を外部送信する後続機能を自動起票しない。

## Stop Rules

- U1未合格またはshared file移管未完了。
- 新dependency、証明書、secret、外部API、外部通信が必要。
- allowlistへpath、会話、環境変数、秘密情報を追加する必要。
- 実機install、update、uninstall、第三者試験が未承認。
- U1または別ownerが同じshared fileを変更中。
- baseline failureと新規failureを分離できない。

停止時は診断内容を増やさず、必要な変更とリスクをDirectorへ返す。
