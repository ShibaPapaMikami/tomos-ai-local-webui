# TOMOS Desktop B3 App Data and Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TOMOSの書き込みデータをapp bundleからApplication Supportへ分離し、旧データをプレビュー・承認・検証付きコピーで移行する。

**Architecture:** `app_paths.py`を唯一のdata root解決境界とし、既存DB・教材パック・写真・cacheのpathをそこへ集約する。`migration_manager.py`は既知pathだけを読み、stagingへのコピー、hash検証、atomic renameを担当する。管理画面は件数・容量・更新日時を表示し、ユーザーが押した時だけ移行する。

**Tech Stack:** Python 3.11、SQLite、`pathlib`、JSON、既存JavaScript管理画面

## Global Constraints

- Gate B2合格版を基準にする。
- 保存先は`~/Library/Application Support/com.shibapapastudio.tomos-ai/`。
- 元データを削除、移動、上書きしない。
- APIキー、password、session tokenを移行しない。
- プレビュー前に書き込みを行わない。
- Memory、Knowledge、契約書、教材パックの責務とscopeを変えない。
- localStorageは明示export/importだけを許可し、ブラウザー領域を直接探索しない。
- localStorage transfer fileはserverへ送信せず、`docs/superpowers/specs/2026-07-27-tomos-localstorage-transfer-design.md`の完全一致allowlistだけを扱う。
- 未知key、API key、password、session token、Cookie、secret、workspace path、microphone device ID、外部LLM URL、plugin認証、mobile接続情報をlocalStorage移行へ含めない。
- UIは`DESIGN.md`、保存境界は`MEMORY.md`に従う。
- commitはDirectorの明示承認後だけ実行する。

---

### Task 1: app data rootを一元化

**Files:**
- Create: `app_paths.py`
- Create: `scripts/test_app_paths.py`
- Modify: `server.py`
- Modify: `knowledge_layer.py`
- Modify: `packages/local_context_core/__init__.py`
- Modify: `contract_ledger.py`

**Interfaces:**
- Produces:
  - `tomos_data_root(env: Mapping[str, str] | None = None, home: Path | None = None) -> Path`
  - `TomosPaths.from_root(root: Path) -> TomosPaths`
  - `knowledge_db`、`context_db`、`contracts_db`、`study_packs`、`person_photos`、`codegraph`、`logs`、`migration`

- [ ] **Step 1: default、override、bundle外保存のtestを書く**

```python
def test_default_data_root_is_application_support(tmp_path):
    root = tomos_data_root(env={}, home=tmp_path)
    assert root == tmp_path / "Library/Application Support/com.shibapapastudio.tomos-ai"

def test_paths_keep_user_data_outside_resource_root(tmp_path):
    paths = TomosPaths.from_root(tmp_path / "app-data")
    assert paths.knowledge_db == tmp_path / "app-data/data/knowledge/index.sqlite"
    assert paths.context_db == tmp_path / "app-data/data/memory/context.sqlite"
```

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_app_paths.py`

Expected: `app_paths` module未作成で失敗。

- [ ] **Step 3: immutable path objectを実装する**

`TOMOS_DATA_ROOT`はdesktop child processからの明示overrideに使う。空文字、相対path、symlinkでapp bundle内へ戻るpathを拒否する。directory作成は`ensure_data_directories(paths)`だけが担当する。

- [ ] **Step 4: serverのglobal pathを置き換える**

`ROOT`はresource読取専用rootとして維持し、DB、教材パック、写真、codegraphだけを`TomosPaths`へ置き換える。workspace、ユーザー指定folder、モデルpathは勝手にdata rootへ移動しない。

- [ ] **Step 5: GREENと既存DB testを確認する**

Run:

```bash
python3 scripts/test_app_paths.py
python3 scripts/test_context_core.py
python3 scripts/test_knowledge_layer.py
python3 scripts/test_study_pack_manager.py
python3 -m py_compile server.py app_paths.py
```

Expected: 全件合格。

---

### Task 2: 読み取り専用migration preview

**Files:**
- Create: `migration_manager.py`
- Create: `scripts/test_migration_manager.py`

**Interfaces:**
- Produces:
  - `MigrationSource(kind: str, source: Path, destination: Path)`
  - `detect_legacy_sources(known_roots: Sequence[Path], paths: TomosPaths) -> list[MigrationSource]`
  - `build_migration_preview(sources: Sequence[MigrationSource]) -> dict`

- [ ] **Step 1: 既知path限定とzero-write testを書く**

```python
def test_preview_only_reads_known_legacy_roots(tmp_path):
    legacy = make_legacy_fixture(tmp_path / "legacy")
    preview = build_migration_preview(detect_legacy_sources([legacy], make_paths(tmp_path)))
    assert preview["totalFiles"] > 0
    assert preview["items"][0]["kind"] == "knowledge"
    assert not (tmp_path / "app-data").exists()

def test_preview_excludes_secrets_and_unknown_files(tmp_path):
    legacy = make_legacy_fixture(tmp_path / "legacy", extras=[".env", "token.txt", "unknown.db"])
    preview = preview_fixture(legacy)
    assert {item["name"] for item in preview["files"]}.isdisjoint({".env", "token.txt", "unknown.db"})
```

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_migration_manager.py`

Expected: `migration_manager`未作成で失敗。

- [ ] **Step 3: 明示allowlistで検出と集計を実装する**

対象は旧HOMEの`~/.gemma4-data/knowledge/index.sqlite`、`~/.gemma4-data/context/context.sqlite`、`~/.gemma4-data/contracts/contracts.sqlite`、`~/.gemma4-data/study-packs/`と、旧resource rootの`data/person-photos/`だけとする。検出rootにはHOMEと旧resource rootを渡し、同じkindが複数rootに存在する場合は黙って選ばず明示エラーにする。fixtureはこの旧default path契約を独立した期待値として固定する。件数、byte数、最新mtime、移行先、衝突状態を返し、本文やDB row内容はpreview responseへ含めない。

人物写真はserverの保存形式と同じ`.jpg`、`.png`、`.webp`だけを対象にする。JPEGはEOI、PNGはCRC付きIEND、WebPはRIFF宣言長と最終chunkまで構造を検証し、末尾付加、途中欠落、壊れた形式を除外する。

- [ ] **Step 4: GREENを確認する**

Run: `python3 scripts/test_migration_manager.py`

Expected: preview test全件合格、previewだけではdestination未作成。

---

### Task 3: 承認付きcopy・検証・rollback

**Files:**
- Modify: `migration_manager.py`
- Modify: `scripts/test_migration_manager.py`

**Interfaces:**
- Produces:
  - `apply_migration(preview_id: str, approved_items: Sequence[str], paths: TomosPaths) -> dict`
  - `rollback_migration(snapshot_id: str, paths: TomosPaths) -> dict`

- [ ] **Step 1: staging、hash、再実行、失敗rollback testを書く**

```python
def test_apply_copies_after_explicit_approval(tmp_path):
    manager, preview = migration_fixture(tmp_path)
    result = manager.apply(preview["previewId"], ["knowledge"])
    assert result["status"] == "completed"
    assert manager.paths.knowledge_db.is_file()
    assert manager.legacy_knowledge_db.is_file()

def test_failed_validation_keeps_current_and_source(tmp_path):
    manager, preview = migration_fixture(tmp_path, corrupt_after_copy=True)
    with raises(MigrationValidationError):
        manager.apply(preview["previewId"], ["knowledge"])
    assert manager.current_hash() == manager.before_hash
    assert manager.legacy_knowledge_db.is_file()
```

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_migration_manager.py`

Expected: apply未定義で失敗。

- [ ] **Step 3: staging copyと検証を実装する**

preview IDはsource path、size、mtime、destinationのdigestから作る。apply時に同じdigestを再計算し、変化していれば再previewを要求する。SQLiteは`PRAGMA quick_check`、directoryはfile countとSHA-256一覧を検証する。非協調writerが動くdirectoryに原子的な単一時点を仮定せず、allowlist対象をstagingへ安全にコピーしてhash検証を完了した時点をcapture boundaryとする。capture中に検出できた変更はstaleとして停止し、capture完了後は検証済みstagingを今回の正本として反映する。その後の旧source更新は今回のコピーへ混在させず、次回previewの差分として扱う。完了記録には`sourceSnapshotDigest`と`sourceCapturedAt`だけを保存し、「全sourceを同一時点で停止した」という意味は持たせない。

- [ ] **Step 4: atomic反映と1世代snapshotを実装する**

既存destinationがある場合、directoryは同じfilesystem上のsnapshotへrenameし、検証済みstagingをdestinationへrenameする。SQLiteはcurrentをcheckpointまたは`journal_mode = DELETE`へ変更せず、別fileへlogical snapshotを作り、main・WAL・SHM・journalの物理recovery bundleをdurable journalへdigest固定する。currentを変更する前にSQLite exclusive境界内でphysical・logical digestを再照合し、durableなownership phaseを記録する。replacement / restore scratchもmainと全sidecarをheld FDへ固定し、whole-file lockを取得したままpathnameへpublishする。destination未作成のSQLiteは、main・WAL・SHM・journalの全pathnameが不存在であることを`dir_fd`と`O_NOFOLLOW`で確認してから、locked staging inodeをhard linkでatomic no-clobber publishする。main反映後も各sidecar反映前に未知pathnameの出現を再確認し、上書きや削除を行わず安全停止する。stagingのmainとsidecarはtransactionのcommitted journalがdurableになるまでownership anchorとして保持し、component phaseで反映済みと証明できる同一inodeだけをnew-only recoveryの破壊対象にする。new-only recoveryがdestination pathnameを削除する場合は、current lockを解放する前にmain・WAL・SHM・journalの全staging inodeへ固定名の`retained_external_write_guard` hard linkを作り、`migrationId`・`snapshotId`・既知kindだけから導出したguard ID、componentのdev・inode、初期physical・logical digestをclosed recordへdurable保存する。待機済みFDが存在するかPOSIX lock APIでは証明できないため、このguardの最後のsame-inode pathnameを自動recovery、通常cleanup、orphan cleanup、snapshot pruneで削除しない。guardは通常destinationとは別名なのでmanaged writerによるdestination新規作成を妨げず、main・WAL・SHM・journalを同じbase名で再openして確認できる。後日の削除は外部writerとの調整後にユーザーが明示承認する別工程だけで行い、1世代rollback snapshotとは別の安全artifactとして扱う。`recovery_pending / quarantined`でcurrentが欠落した再開は、記録済みdev・inodeと一致するfull staging component集合、physical digest、logical digest、安全quarantineがすべて一致する場合だけ`recovered / retained_external_write_guard`へ進める。欠落・partial・同一byte別inode・置換・logical不一致はjournalとquarantineを保持して安全停止する。すでにclosed retained guardがdurableな`recovered`だけは、guardとのsame-inodeを確認しながらpartial staging alias cleanupを再開できる。同じ待機FDのlock解放後write＋`fsync`はguardから到達可能でなければならず、同じSQLite connectionが`SQLITE_READONLY_DBMOVED`を返す場合は明示的失敗として扱い、guardの保持済みbytesを失わない。recovery quarantineはheld FDから別inodeへdurable copyし、既存のmain・全sidecarもcurrent lock取得前に`O_NOFOLLOW`のheld FDへ固定する。lock内ではheld quarantine FDからdigestを計算し、pathname identityを`stat`で再確認して、全current FDとのdev・inode不一致を必須にする。quarantine pathnameの差替えまたはhard-link aliasはcurrent変更前に安全停止し、lock中にquarantine pathを別FDでopen・closeしない。main、WAL、SHM、journalの各反映後はparent directoryを`fsync`し、closedなcomponent phaseをdurable journalへ保存する。ownership前のcurrent不一致は他者更新として一切復元せず停止する。復元時はcurrentもheld FDとlockの内側で最終physical stateを再照合し、安全copyをquarantineへ保持してからrestore scratchをpublishする。tamperまたは途中失敗時にcurrentを単純削除せず、byte一致復旧または安全停止できた場合だけrecovery bundleとquarantineを削除する。完了記録とretained guard recordに本文、full path、tokenを含めない。

- [ ] **Step 5: GREENを確認する**

Run: `python3 scripts/test_migration_manager.py`

Expected: copy、失敗、再実行、rollback test全件合格。

---

### Task 4: migration APIをsession guard配下へ追加

**Files:**
- Modify: `server.py`
- Modify: `scripts/test_server_helpers.py`

**Interfaces:**
- Produces:
  - `GET /api/desktop/migration/preview`
  - `POST /api/desktop/migration/apply`
  - `POST /api/desktop/migration/rollback`

- [ ] **Step 1: API contract testを書く**

previewは読み取り専用で件数・容量・mtimeだけを返す。applyは`previewId`と`approvedItems`を必須にし、空配列を400にする。rollbackは存在する`migrationId`だけを受け付ける。

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_server_helpers.py`

Expected: endpoint未実装で失敗。

- [ ] **Step 3: handlerを実装する**

POSTはGate B2のsession guardを必ず通す。error responseは`migration_preview_stale`、`migration_approval_required`、`migration_validation_failed`、`migration_not_found`の固定codeへ変換し、local path全文をresponseへ出さない。

- [ ] **Step 4: GREENを確認する**

Run:

```bash
python3 scripts/test_server_helpers.py
python3 scripts/test_desktop_api_session.py
```

Expected: APIとsession test全件合格。

---

### Task 5: 管理画面へ移行確認UIを追加

**Files:**
- Modify: `web/management.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Modify: `web/i18n.js`
- Modify: `scripts/test-management-helpers.js`
- Modify: `scripts/test-pwa-assets.js`

**Interfaces:**
- Produces: `古いTOMOSデータ`セクション、`内容を確認`、`選択したデータをコピー`、`元に戻す`。

- [ ] **Step 1: 状態と文言のhelper testを書く**

```js
assert.equal(migrationActionLabel("idle"), "内容を確認");
assert.equal(migrationActionLabel("ready"), "選択したデータをコピー");
assert.equal(migrationActionLabel("copying"), "コピーしています");
assert.equal(migrationActionLabel("completed"), "コピーが完了しました");
```

- [ ] **Step 2: REDを確認する**

Run: `node scripts/test-management-helpers.js`

Expected: migration helper未定義で失敗。

- [ ] **Step 3: preview UIを実装する**

右カラムへ入れ子カードを増やさず、対象名、件数、容量、更新日時、衝突状態を行表示する。初期状態でapplyボタンをdisabledにする。個人情報やDB本文を表示しない。

- [ ] **Step 4: 確認dialogと独立statusを実装する**

apply前に「元データは削除されません」を表示する。成功・失敗をボタン内だけに入れず、独立したstatus領域へ表示する。コピー中の二重送信を無効化する。

- [ ] **Step 5: GREENとresponsive確認**

Run:

```bash
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
node --check web/management.js
```

Browser確認: `1280×820`、`960×640`、`390×844`で文字の重なり・横overflow 0件。

---

### Task 6: localStorageの明示export/import

**Files:**
- Create: `web/local-storage-transfer.js`
- Create: `scripts/test-local-storage-transfer.js`
- Modify: `web/management.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Modify: `web/i18n.js`
- Modify: `scripts/test-management-helpers.js`
- Modify: `scripts/test-pwa-assets.js`

**Interfaces:**
- Produces:
  - `TOMOS_LOCAL_STORAGE_EXPORT_TYPE = "tomos-local-storage-export"`
  - `TOMOS_LOCAL_STORAGE_EXPORT_VERSION = 1`
  - `TOMOS_LOCAL_STORAGE_ALLOWED_KEYS`
  - `buildTomosLocalStorageExport(storage, nowIso) -> object`
  - `previewTomosLocalStorageImport(payload) -> {status, acceptedKeys, rejectedCount, exportedAt}`
  - `applyTomosLocalStorageImport(storage, preview, approved) -> {status, importedCount}`

- [ ] **Step 1: allowlist、zero-write、rollback testを書く**

```js
const payload = buildTomosLocalStorageExport(storage, "2026-07-27T00:00:00.000Z");
assert.equal(payload.type, "tomos-local-storage-export");
assert.equal(payload.version, 1);
assert.equal(payload.values["gemma4.theme"], "light");
assert.equal(payload.values["gemma4.externalLlmUrl"], undefined);

const preview = previewTomosLocalStorageImport({
  type: "tomos-local-storage-export",
  version: 1,
  exportedAt: "2026-07-27T00:00:00.000Z",
  values: {
    "gemma4.theme": "dark",
    "gemma4.unknownFutureKey": "ignored",
    "gemma4.sessionToken": "ignored"
  }
});
assert.deepEqual(preview.acceptedKeys, ["gemma4.theme"]);
assert.equal(preview.rejectedCount, 2);
assert.equal(storage.writes.length, 0);
```

write途中で例外を発生させ、反映前snapshotへ戻るtestも同じfileへ追加する。

- [ ] **Step 2: REDを確認する**

Run: `node scripts/test-local-storage-transfer.js`

Expected: `web/local-storage-transfer.js`未作成で失敗。

- [ ] **Step 3: pure helperを実装する**

allowlistは設計書記載の33 keyを完全一致で定義する。exportはallowlist対象かつ文字列valueだけを返す。previewはfile形式、version、文字列valueを検証し、未知keyの値をreturnしない。applyは`approved === true`だけを許可し、現在値snapshotとwrite失敗時rollbackを実装する。

- [ ] **Step 4: 管理画面へ手動transfer UIを追加する**

旧ブラウザー側のexportは同一画面のlocalStorageだけを利用者click時に読み、JSON fileをdownloadする。importは利用者が選んだfileをbrowser memory内だけでparseする。server API、WebKit profile探索、ブラウザーprofile探索を使わない。

previewには対象件数、除外件数、file作成日時だけを表示する。export前に「会話や設定がファイルへ含まれます」、import前に「現在のアプリ設定へ上書きされます」を表示する。成功・失敗は独立status領域へ出し、二重送信を無効化する。

- [ ] **Step 5: GREENとresponsive確認**

Run:

```bash
node scripts/test-local-storage-transfer.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
node --check web/local-storage-transfer.js
node --check web/management.js
```

Browser確認: `1280×820`、`960×640`、`390×844`で文字の重なり・横overflow 0件。

---

### Task 7: Gate B3

- [x] **Step 1: 新規profileを確認する**

空の一時HOMEで起動し、Application Support配下だけへDBが作成されることを確認する。

- [x] **Step 2: 旧データ移行を確認する**

fixtureでpreview、選択、copy、検証、再起動後readbackを確認する。元data hashが前後一致することを記録する。

- [x] **Step 3: 失敗とrollbackを確認する**

copy途中失敗、stale preview、壊れたSQLite、同じ移行の再実行を確認する。

- [x] **Step 4: 全回帰testを実行する**

Run:

```bash
python3 scripts/test_app_paths.py
python3 scripts/test_migration_manager.py
python3 scripts/test_server_helpers.py
python3 scripts/test_context_core.py
python3 scripts/test_knowledge_layer.py
python3 scripts/test_study_pack_manager.py
node scripts/test-local-storage-transfer.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
git diff --check
```

- [x] **Step 5: Gate判定**

全件合格後だけマスター台帳のGate B3を`合格`へ更新し、Desktop Cを許可する。
