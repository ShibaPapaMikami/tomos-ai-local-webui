# TOMOS Desktop Gate B3 検証報告

[V255 / B3最終Gate再検証]

## 最終判定

- Gate B3: **合格**
- Desktop C: **開始許可**（署名・公証・PKG作成は別承認まで未実施）
- マスター台帳: `Gate B3 = 合格`、`Gate C = 停止`
- C1、I1、I2は独立最終再レビューで解消確認済み。新規Critical / Importantは0件。
- 対象HEAD: `85a63d7`を基準とする未コミットB3実装

## I2修正後のfresh evidence

| 項目 | 結果 |
| --- | --- |
| Python 3.14系 非localhost Gate suite | 9 / 9 PASS |
| Python 3.11.9 非localhost Gate suite | 9 / 9 PASS |
| localhost統合（両Python各2本） | 4 / 4 PASS |
| Node関連回帰 | 19 / 19 PASS |
| Rust | 22 passed / 0 failed |
| Python両環境 `py_compile` / `git diff --check` | PASS |
| I2独立最終再レビュー | PASS |

WebPはVP8 / VP8L / VP8X / ANMFの寸法をImageIO実行前に4 MiB上限で拒否し、native画像もdata provider取得・copy前に再確認する。有効な1025×1025の高圧縮VP8 / VP8Lとprovider呼出順序の回帰testが成功した。

UI差分はなく、前回の実ブラウザー3幅、横overflow 0、file chooser、zero-write preview、cancel、confirm、再読込、console error 0の証跡を維持する。`scripts/test-mobile-css.js`の既存契約不一致はB3差分外として分離する。

## I2修正前の判定（履歴）

[V016 / B3追加修正・独立再レビュー]

## 当時の判定

- Gate B3: **差し戻し（追加修正の独立再レビュー不合格）**
- Desktop C: **開始不可**
- マスター台帳: `Gate B3 = 差し戻し`、`Gate C = 停止`
- 前回のC1（通常HOME包含関係）とI1（復号不能WebP）は解消済み。
- 新規Important I2として、WebPの4 MiB上限を全画素復号後に判定しており、preview時の巨大メモリ消費を事前に防げない問題を確認した。
- ImageIO実行前の寸法上限、decoded provider copy前の再確認、回帰testが追加されるまでGate B3を合格へ戻さず、Desktop Cを開始しない。

## 追加修正waveの検証

- Python 3.14系 / 3.11.9のGate suite、localhost統合、Node関連19件、Rust 22件、構文、差分確認は成功した。
- C1とI1について、独立再レビューは`ADDRESSED`と判定した。
- 新規Criticalは0件、新規ImportantはI2の1件。
- `scripts/test-mobile-css.js`の既存契約不一致はB3差分外として分離した。

## 追加修正前の判定（履歴）

[V013 / B3最終再レビュー]

## 当時の判定

- Gate B3: **差し戻し（最終再レビュー不合格）**
- Desktop C: **開始許可を取り消し**
- マスター台帳: `Gate B3 = 差し戻し`、`Gate C = 停止`
- 最終コードレビューで、旧HOMEのcontext・contracts・study-packsが検出されないC1と、正常JPEG / WebP人物写真が除外されるI1を確認した。
- 1回の最終修正と独立再レビューを実施したが、通常HOMEが移行先を内包する構成を誤って拒否するC1と、復号不能WebPを許可するI1が残った。
- 自動testは成功しているが、本番と同じHOME包含関係と、RIFF長が正しい壊れたWebPの回帰testが不足していた。追加修正waveが承認されるまでGate B3を合格へ戻さず、Desktop Cを開始しない。

## 最終修正後の再レビュー（履歴）

[V012 / B3最終レビュー修正]

- C1初回指摘に対し旧default path 5種へ修正し、I1初回指摘に対しJPEG / PNG / WebP validatorを追加した。
- Python両環境のGate suite、localhost統合、Node関連、Rust、構文、差分確認は成功した。
- 独立再レビューで、HOME包含関係とWebP bitstream検証の不足が見つかったため、合格には戻していない。

## 最終レビュー前の判定（履歴）

[V011 / B3最終検証]

## 最終判定

- Gate B3: **合格**
- Desktop C: **開始許可**（署名・公証・PKG作成は別承認まで未実施）
- マスター台帳: `Gate B3 = 合格`へ更新し、`Gate C = 停止`を維持
- 対象HEAD: `85a63d7`を基準とする未コミットB3実装
- 検証日: 2026-07-29
- 対象worktree: `.worktrees/phase1-pc-diagnostics`

## 最終再検証

| 項目 | 結果 |
| --- | --- |
| Python 3.14系 Gate suite | 11 / 11 PASS |
| Python 3.11.9 Gate suite | 11 / 11 PASS |
| Node B3・関連回帰 | 19 / 19 PASS |
| Rust | 22 passed / 0 failed |
| Python 3.14系 / 3.11.9 `py_compile` | PASS |
| `git diff --check` | PASS |
| ブラウザーconsole error | 0件 |

localhostを使う`test_server_helpers.py`と`test_desktop_api_session.py`は、権限付きローカル実行で両Pythonとも成功した。Mac resource stagingには`web/local-storage-transfer.js`が含まれ、asset / PWA識別子は`0.8.234-local-storage-transfer`へ統一されている。

実ブラウザーでは、`1280×820`、`960×640`、`390×844`の3幅を確認した。全幅で`documentElement.scrollWidth = innerWidth`かつ`body.scrollWidth = innerWidth`となり、横overflowは0件だった。初期、preview完了、API error、取り込み確認、完了の各状態を確認し、console errorは0件だった。

実file chooser経路は、利用者が押す表示ボタンからブラウザーの`filechooser` eventを発生させ、実JSON fileを選択して確認した。対象2件・除外1件のpreview、confirm前zero-write、cancel、confirm後2件反映、再読込後の言語・テーマ反映、元設定への復元まで成功した。未知の`token` keyは除外された。

`scripts/test-mobile-css.js`だけは今回のB3差分外にある既存契約不一致で失敗する。HEADの`web/styles.css`にもmobile composerの5列定義が存在し、B3差分はcomposerを変更していないため、Gate B3の不合格要因にはしない。

## Fix1後の状態（履歴）

[V010 / B3実装修正]

- Gate B3: **BLOCKED（実装修正済み、再検証待ち）**
- Desktop C: **許可しない**
- 実装blocker 2件はFix1で修正した。Mac resource stagingへ`web/local-storage-transfer.js`を追加し、asset / PWA正本を`0.8.234-local-storage-transfer`へ統一した。

## 初回Gate判定（履歴）

[V009 / B3検証]

### 判定

- Gate B3: **BLOCKED（不合格）**
- Desktop C: **許可しない**
- マスター台帳: `Gate B3 = 停止`、`Gate C = 停止`を維持
- 対象HEAD: `85a63d7`を基準とする未コミットB3実装
- 検証日: 2026-07-29
- 対象worktree: `.worktrees/phase1-pc-diagnostics`

Gate B3の主要条件を満たすmigration本体とlocalStorage helperはfresh testで合格した。一方、Mac同梱resourceから新規client helperが欠落し、Global Node回帰も1本失敗した。さらにlocalhost結合test、fresh screenshot、実file chooser操作を現環境で完了できなかったため、Gateを合格へ変更しない。

## Scopeと安全境界

- 空の`mktemp` HOME、`TOMOS_DATA_ROOT`、legacy fixtureだけを使用した。
- ユーザーの実データ、既存Application Support、本番、署名、Apple公証、PKG、外部APIへ触れていない。
- Tauri本番appの起動、install、bundle生成、commit、push、依存追加は行っていない。
- コード問題は修正せず、検証報告とSDD台帳だけを変更した。

## 実行環境

```text
HEAD: 85a63d7
branch: codex/phase1-pc-diagnostics
Python 3.14.4
Python 3.11.9
Node.js v22.17.0
cargo 1.94.1
rustc 1.94.1
```

## Gate条件の判定

| 項目 | 判定 | fresh evidence |
| --- | --- | --- |
| 新規profile / startup zero-write | 合格 | fresh processの`prepare_managed_data_startup()`後もdata root不存在。preview後も不存在 |
| Application Supportだけへの反映 | 合格 | apply後のmanaged dataは一時`TOMOS_DATA_ROOT`だけ。resource tree hash前後一致 |
| preview metadata / 秘密・path非表示 | 合格 | API payload keyは件数、容量、mtime、衝突、除外、errorだけ。fixture pathと秘密marker 0件 |
| 明示選択copy / 元data不変 | 合格 | `knowledge`と`study-packs`だけをcopy。legacy SHA-256前後一致 |
| SQLite / directory検証 | 合格 | Python 3.14 / 3.11でmigration manager 126 test関数が全件成功 |
| fresh process readback | 合格 | SQLite値と教材packを別processでreadback |
| stale / corrupt / idempotent / rollback / WAL / crash | 合格（自動test） | migration manager 126 test関数を両Pythonで成功。代表live fixtureでも同一apply再実行とnew-only rollback成功 |
| API session / Content-Type / fixed error | 一部合格 | pure guardと固定error mappingは成功。HTTP localhost結合suiteはsandbox制約で未完了 |
| UI状態 / 二重送信 / dialog | 一部合格 | Node DOM test成功。fresh browser screenshotは未完了 |
| localStorage 33-key client-only transfer | 合格（Node DOM） | allowlist 33、4-field envelope、zero-write preview、秘密・未知key除外、承認、rollback、10 MiB、basename消去、fetch禁止が成功 |
| Mac app resource同梱 | **不合格** | `web/local-storage-transfer.js`が`RESOURCE_FILES`に含まれずresource test失敗 |
| Global Node回帰 | **不合格** | `node scripts/test-model-selection.js`がasset version契約不一致で失敗 |
| 実file chooser | 未確認 | simulated DOM / FileReaderは成功。利用者clickによるnative chooserは未確認 |

## 新規profileと代表live fixture

一時fixture:

```text
/private/tmp/tomos-b3-gate-live.BSqd5E
```

実行内容:

1. fresh HOMEでstartup recovery境界を実行。
2. valid SQLite、正式fixture教材pack、未知file、秘密markerを一時legacy rootへ作成。
3. previewだけを実行し、managed data rootが作成されないことを確認。
4. path-freeなAPI previewを確認。
5. `knowledge`と`study-packs`だけを明示copy。
6. 同じpreviewを再実行。
7. 別Python processでmanaged SQLiteと教材packをreadback。
8. 別processでnew-only rollback。

結果:

```json
{
  "startupFreshRootExistsAfterRecoveryCheck": false,
  "previewManagedRootExists": false,
  "previewKinds": ["knowledge", "study-packs"],
  "previewPathFree": true,
  "previewSecretFree": true,
  "approvedKinds": ["knowledge", "study-packs"],
  "applyStatus": "completed",
  "idempotentRerun": true,
  "freshProcessReadback": true,
  "studyPackReadback": true,
  "rollbackStatus": "rolled_back",
  "newOnlyKnowledgeRemoved": true,
  "newOnlyStudyPacksRemoved": true,
  "sourceUnchangedByRollback": true
}
```

fixture hash:

```text
legacy source before: b194dbf605006c68e1744062e8e58ba7bbdef814e9bc6fb268dd0991dcee756c
legacy source after:  b194dbf605006c68e1744062e8e58ba7bbdef814e9bc6fb268dd0991dcee756c
resource tree before: 012ea0e5bfa89ca6a7f81bbe2a52cedd4dbf25d03c70a55772506188786fa0a8
resource tree after:  012ea0e5bfa89ca6a7f81bbe2a52cedd4dbf25d03c70a55772506188786fa0a8
```

## 失敗・recovery coverage

`scripts/test_migration_manager.py`は126 test関数を直接実行し、Python 3.14と3.11の両方で`migration manager tests passed`、exit 0だった。

主な固定test:

- copy / recovery / validation failure: 42件（名前に`fail`、`crash`、`recover`を含む）
- stale: 4件
- idempotent: 2件
- rollback: 23件
- new-only: 22件
- existing / snapshot: 20件
- WAL: 17件
- crash / restart recovery: 31件

代表例:

```text
test_failed_sqlite_validation_keeps_current_source_and_cleans_staging
test_apply_rejects_stale_preview_when_source_metadata_changes
test_apply_is_idempotent_and_rollback_restores_existing_snapshot_once
test_new_only_and_mixed_migrations_have_rollback_handles
test_apply_main_publish_crash_recovers_wal_bundle_byte_exact
test_restart_recovery_survives_crash_after_restore_pending
test_rollback_rejects_corrupt_snapshot_without_data_loss
```

## API evidence

HTTP bindを使わないpure guardをfresh processで実行した。

```text
POST /api/desktop/migration/apply
POST /api/desktop/migration/rollback

tokenなし      -> desktop_session_required
誤token        -> desktop_session_required
text/plain     -> desktop_json_required
正token + JSON -> accepted
```

固定error:

```text
MigrationApprovalError     -> 400 migration_approval_required
MigrationPreviewStaleError -> 409 migration_preview_stale
MigrationValidationError   -> 400 migration_validation_failed
MigrationNotFoundError     -> 404 migration_not_found
```

代表live API previewはfull path、SQLite本文、秘密markerを返さず、衝突情報を含むclosed metadataだけを返した。

## localStorage evidence

fresh Node test:

```text
node scripts/test-local-storage-transfer.js
local storage transfer tests passed
exit=0

node scripts/test-management-helpers.js
management helper tests passed
exit=0

node scripts/test-pwa-assets.js
pwa asset tests passed
exit=0
```

確認済み:

- 完全一致allowlistは設計どおり33 key。
- export envelopeは`type`、`version`、`exportedAt`、`values`の4 fieldだけ。
- 文字列valueだけをexportする。
- 未知、token、workspace path、device ID、外部URL、plugin、mobile keyをexport/importしない。
- previewはlocalStorage read / write 0件。
- cancel時もread / write 0件。
- confirm後だけ1回applyし、二重confirmを抑止する。
- write失敗時は存在・不存在を含むsnapshotへ戻す。
- rollback自体が失敗した場合は`rollback-failed`を独立表示する。
- 10 MiBちょうどは`FileReader`へ進み、10 MiB + 1、欠落、負数、小数、NaNはreader前に拒否する。
- visible buttonからhidden file inputを1回開き、選択直後にinput valueを空へ戻す。
- basename、値、秘密markerをvisible text / valueへ残さない。
- DOM harnessの`fetch`は呼ばれた時点で失敗する設定で、全transfer testが成功した。

未確認:

- 実ブラウザーのnative file chooserを利用者clickで開き、実fileを選ぶ操作。
- simulated DOM / FileReaderは実行済みだが、実chooserの成功とは扱わない。

## fresh suite

### Python 3.14

一時HOMEと一時`TOMOS_DATA_ROOT`で11 commandを実行。

| command | 結果 |
| --- | --- |
| `python3 scripts/test_app_paths.py` | PASS — `app paths tests passed` |
| `python3 scripts/test_migration_manager.py` | PASS — `migration manager tests passed` |
| `python3 scripts/test_server_helpers.py` | 未完了 — localhost bindが`PermissionError: [Errno 1] Operation not permitted` |
| `python3 scripts/test_context_core.py` | PASS — `context core tests passed` |
| `python3 scripts/test_knowledge_layer.py` | PASS — `knowledge layer tests passed` |
| `python3 scripts/test_study_pack_manager.py` | PASS — `study pack manager tests passed` |
| `python3 scripts/test_contract_ledger.py` | PASS — `contract ledger tests passed` |
| `python3 scripts/test_desktop_api_session.py` | 未完了 — localhost bindが`PermissionError: [Errno 1] Operation not permitted` |
| `python3 scripts/test_local_context_core_package.py` | PASS — `local context core package tests passed` |
| `python3 scripts/test_macos_tomos_resources.py` | **FAIL** — `assert web_files <= resources` |
| `python3 scripts/test-desktop-shell-contract.py` | PASS — `desktop shell contract tests passed` |

集計: PASS 8 / FAIL 1 / 環境制約で未完了 2。

### Python 3.11

同じ11 commandをfresh一時環境で実行し、同じ結果だった。

```text
python311_suite_pass=8 fail=3
```

内訳は実装fail 1、localhost bind制約 2。app pathsとmigration managerは3.11でも成功した。

### Node

16 command中15 commandがexit 0、1 commandが失敗した。

成功:

```text
node scripts/test-local-storage-transfer.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
node scripts/test-settings-helpers.js
node scripts/test-asr-helpers.js
node scripts/test-tts-helpers.js
node --check web/local-storage-transfer.js
node --check web/management.js
node --check web/i18n.js
node --check web/sw.js
node --check web/models.js
node --check web/settings.js
node --check web/asr.js
node --check web/app.js
node --check web/desktop-starting.js
```

失敗:

```text
node scripts/test-model-selection.js
AssertionError [ERR_ASSERTION]:
The input did not match the regular expression /\/i18n\.js\?v=0\.8\.233-tts-boundary/
scripts/test-model-selection.js:1354
exit=1
```

### Rust

`CARGO_TARGET_DIR`を一時HOME内へ分離して実行した。

```text
cargo test --manifest-path src-tauri/Cargo.toml
running 22 tests
test result: ok. 22 passed; 0 failed; 0 ignored
```

### 構文と差分

```text
python3 -m py_compile server.py app_paths.py migration_manager.py contract_ledger.py knowledge_layer.py study_pack_manager.py packages/local_context_core/__init__.py scripts/stage-macos-tomos-resources.py
exit=0

python3.11 -m py_compile server.py app_paths.py migration_manager.py contract_ledger.py knowledge_layer.py study_pack_manager.py packages/local_context_core/__init__.py scripts/stage-macos-tomos-resources.py
exit=0

git diff --check
exit=0
```

## BLOCKED理由

### 1. Mac app resourceから新規client helperが欠落

再現:

```text
python3 scripts/test_macos_tomos_resources.py
AssertionError
scripts/test_macos_tomos_resources.py:142
assert web_files <= resources
```

差分診断:

```text
missing_web_resources= ['web/local-storage-transfer.js']
unexpected_allowlist_web= []
```

`web/index.html`と`web/sw.js`は`/local-storage-transfer.js`を要求するが、`scripts/stage-macos-tomos-resources.py`の`RESOURCE_FILES`に存在しない。現状のMac resource stagingではapp版localStorage transfer helperを同梱できないため、Gate B3のアプリ側file transfer条件を満たさない。

### 2. Global Node回帰が失敗

`web/index.html`の`i18n.js`、styles、management、localStorage helperと`web/sw.js` cacheは`0.8.234-local-storage-transfer`へ進んだ。一方、Global回帰`test-model-selection.js`は`i18n.js?v=0.8.233-tts-boundary`を期待して失敗する。

併せて次の識別子不一致をreadbackした。

```text
web/sw.js CACHE_NAME: 0.8.234-local-storage-transfer
web/pwa.js service worker registration: 0.8.233-tts-boundary
web/sw.js cached pwa.js URL: 0.8.233-tts-boundary
```

Task 6単体test 3本は成功するが、マスターGlobal Verification Matrixは失敗しているためGateを閉じられない。

### 3. localhost結合testをfresh完走できない

`test_server_helpers.py`と`test_desktop_api_session.py`はsandbox内でlocalhost bindを拒否された。指定どおり一時HOME / 一時data rootだけの権限付き再実行を2回申請したが、実行環境側が`/private/tmp`への書込みを理由に拒否した。迂回していない。

pure guard、固定error、path-free live previewは確認したが、HTTP integration suiteの代替にはしない。

### 4. fresh screenshotと実file chooserが未確認

`1280×820`、`960×640`、`390×844`のfresh screenshotを取得するためsafe local data pageを開こうとしたが、browser URL policyがdata URLを拒否した。localhost serverも上記bind制約で起動できないため、指定3幅のfresh screenshot、numeric overflow、initial / ready / error / confirmの実ブラウザー表示を完了していない。

Node実DOM fixtureでは初期、ready、error、confirm、二重送信、FileReader成功・失敗、basename非表示、横overflow用CSS契約を確認したが、実ブラウザー操作・目視の代替としてGate合格には使わない。

## 修正後の再検証条件

コード修正は検証担当では行わない。実装担当へ次を差し戻す。

1. Mac resource allowlistへ新規client helperを正しく含め、`scripts/test_macos_tomos_resources.py`を3.14 / 3.11で成功させる。
2. PWA / asset versionの正本とGlobal testを整合させ、`test-model-selection.js`を含む全Node回帰を成功させる。
3. localhost bind可能な承認済み環境で`test_server_helpers.py`と`test_desktop_api_session.py`を両Pythonでfresh再実行する。
4. safe local app / browser test環境で3幅、4状態、実file chooserを確認する。
5. 全suite、`py_compile`、Rust 22 test、`git diff --check`を再実行する。

## Rollback

- Gate台帳は変更していないため、台帳rollbackは不要。
- 本検証で作成したデータは一時fixtureだけで、ユーザーdataは変更していない。
- 作成したreportとTask 7台帳だけを戻せば検証差分を撤回できる。
