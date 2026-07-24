# TOMOS基準線安定化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Do not start feature work until Gate 0 passes.

**Goal:** 現在のTOMOSを変更前の比較基準として固定し、クリーンworktreeで判明した既知のテスト契約不整合だけを解消する。

**Architecture:** 機能テストとPWA資産版テストの責務を分離する。機能テストは必要なscriptの存在、PWA資産版テストは版番号とService Workerの整合性を検証する。

**Tech Stack:** Node.js標準モジュール、Python 3.11、既存TOMOS Web UI。

---

## Scope

変更する:

- `scripts/test-management-helpers.js`
- `scripts/test_server_helpers.py`

読み取りと検証だけ:

- `scripts/test-pwa-assets.js`
- `web/index.html`
- `web/sw.js`
- `web/management.js`
- `web/app.js`

変更しない:

- TOMOSの画面機能
- モデル、PC診断、ASR、TTS、Skill
- 現在の未コミット変更
- 依存関係
- Service Workerの版番号
- Sarashina OCR実装
- QR生成実装

## Entry Conditions

- [ ] Directorが実装開始を承認している。
- [ ] `superpowers:using-git-worktrees` で専用worktreeを作成している。
- [ ] 基準commitをDirectorが指定している。
- [ ] `git status --short --branch` の結果をGate記録へ保存している。
- [ ] 対象worktreeにこの計画とマスター計画が存在する。

基準確認:

```bash
git status --short --branch
git diff --check
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 -c "import segno"
```

期待結果:

- `git diff --check` は無出力で終了コード0。
- management helper testだけが `/i18n.js?v=0.8.222-note-pack-error` の固定値で失敗する。
- PWA asset testは成功する。
- `segno` が未導入の場合は依存追加承認を取り、`segno` 単体だけを対象Pythonへ導入する。モデル取得へ進む `scripts/setup-mac.sh` 全体は実行しない。
- 異なる失敗なら変更せず、Gate 0を停止する。

## Task 1: 資産版の責務を機能テストから分離する

**Files:**

- Modify: `scripts/test-management-helpers.js:490`
- Verify: `scripts/test-pwa-assets.js:1-90`
- Verify: `web/index.html:1330-1365`
- Verify: `web/sw.js:1-80`

- [ ] **Step 1: 既知の失敗を再現する**

```bash
node scripts/test-management-helpers.js
```

期待結果:

```text
AssertionError
```

失敗行が `scripts/test-management-helpers.js:490` で、古いi18n資産版の固定値を期待していることを確認する。

- [ ] **Step 2: 機能テストの期待値を版番号非依存にする**

次の2つの固定値検証:

```js
assert.match(indexHtml, /src="\/i18n\.js\?v=0\.8\.222-note-pack-error"/);
assert.match(indexHtml, /href="\/styles\.css\?v=0\.8\.221-note-pack-install"/);
```

を次へ置き換える:

```js
assert.match(
  indexHtml,
  /src="\/i18n\.js\?v=[^"]+"/,
  "management UI should load the shared i18n script",
);
assert.match(
  indexHtml,
  /href="\/styles\.css\?v=[^"]+"/,
  "management UI should load the shared stylesheet",
);
```

他のassertion、資産版、実装コードは変更しない。

- [ ] **Step 3: 対象テストを合格させる**

```bash
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
```

期待結果:

- 両方が終了コード0。
- management helper testは管理画面機能を検証する。
- PWA asset testは `0.8.229-student-model-routing` と `0.8.230-greeting-context` の整合性を検証する。

- [ ] **Step 4: 変更範囲を確認する**

```bash
git diff -- scripts/test-management-helpers.js
git diff --check
```

期待結果:

- 差分はi18nとstylesheetの固定版assertionを版番号非依存へ変えた2箇所だけ。
- `git diff --check` は無出力。

- [ ] **Step 5: commitは承認がある場合だけ行う**

推奨commit message:

```text
test: separate management UI checks from asset versions
```

Directorのcommit承認がない場合はcommitせず、差分をhandoffする。

## Task 1B: クリーン環境のSarashina状態を許容する

**Files:**

- Modify: `scripts/test_server_helpers.py:82`
- Verify: `sarashina_ocr_runner.py:76-94`

- [ ] **Step 1: クリーンworktreeで既知の失敗を再現する**

```bash
python3 scripts/test_server_helpers.py
```

期待結果: `test_sarashina_ocr_status_payload_shape()` が、実値 `needs_runner` を許容していないため失敗する。

- [ ] **Step 2: 正規状態を許容集合へ追加する**

```python
assert payload["status"] in {"ready", "needs_runner", "needs_dependencies", "needs_model_download"}
```

Sarashina実装、runner、依存、モデルは変更しない。

- [ ] **Step 3: 対象失敗を通過する**

```bash
python3 scripts/test_server_helpers.py
```

`needs_runner` のassertionを通過する。後続で `segno is not installed` が出た場合はこの修正の失敗ではなく、検証環境の必須依存不足として停止する。

- [ ] **Step 4: 変更範囲を確認する**

```bash
git diff -- scripts/test_server_helpers.py
git diff --check
```

期待結果: `needs_runner` を許容集合へ追加した1行だけ。

## Task 2: 全体基準線を固定する

**Files:**

- Test: `scripts/test-model-selection.js`
- Test: `scripts/test-settings-helpers.js`
- Test: `scripts/test-asr-helpers.js`
- Test: `scripts/test-management-helpers.js`
- Test: `scripts/test-pwa-assets.js`
- Test: `scripts/test_server_helpers.py`
- Test: `scripts/test_study_pack_manager.py`
- Test: `scripts/test_context_core.py`
- Test: `scripts/test_knowledge_layer.py`

- [ ] **Step 1: JavaScriptテストを実行する**

```bash
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-asr-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
```

期待結果: 5コマンドすべて終了コード0。

- [ ] **Step 2: Pythonテストを実行する**

```bash
python3 scripts/test_server_helpers.py
python3 scripts/test_study_pack_manager.py
python3 scripts/test_context_core.py
python3 scripts/test_knowledge_layer.py
```

期待結果: 4コマンドすべて終了コード0。

`scripts/test_server_helpers.py` がsandboxのlocalhost bind制限だけで失敗した場合は、同じコマンドだけを承認付きで再実行する。`python3 -m unittest scripts.test_server_helpers` は使わない。

- [ ] **Step 3: 構文を確認する**

```bash
node --check web/models.js
node --check web/settings.js
node --check web/asr.js
node --check web/management.js
node --check web/app.js
python3 -m py_compile server.py
```

期待結果: 全コマンドが無出力、終了コード0。

- [ ] **Step 4: 差分を確認する**

```bash
git diff --check
git status --short --branch
```

期待結果:

- `git diff --check` は無出力。
- 新規差分はTask 1とTask 1Bのテスト2ファイルだけ。
- 基準commitに含まれていた変更はそのまま。

## Task 3: ブラウザー基準線を記録する

**Files:**

- Verify: `web/index.html`
- Verify: `web/app.js`
- Verify: `web/management.js`
- Verify: `web/settings.js`

- [ ] **Step 1: 既存の起動手順でローカルTOMOSを起動する**

```bash
python3 server.py --host 127.0.0.1 --port 54876
```

期待結果: `http://127.0.0.1:54876/` でTOMOSが表示できる。新しい依存取得は発生しない。

- [ ] **Step 2: PC幅を確認する**

ブラウザーを1440×900にし、次を確認する。

- チャット送信と停止が動く。
- モデル表示にQwen3 4Bが出る。
- 取得済みAgentic Coder v2がコード用途に出る。
- PC診断が表示される。
- 音声ボタンが既存状態で表示される。
- 教材パック、Knowledge、Memoryを開ける。

- [ ] **Step 3: スマホ幅を確認する**

ブラウザーを390×844にし、同じ項目が横方向へはみ出さず操作できることを確認する。

- [ ] **Step 4: Service Worker更新後を確認する**

ブラウザーで再読込し、古い資産版エラーがなく、チャットと管理画面が再度開くことを確認する。

- [ ] **Step 5: 記録する**

Gate報告へ次を記載する。

```text
PC幅:
スマホ幅:
Service Worker更新後:
Console error:
対象外の既存問題:
```

各項目には `合格` または実際のエラー全文を入れる。空欄を残さない。

## Gate 0

合格条件:

- 全9テストが終了コード0。
- 全5 JavaScript構文確認とPython構文確認が終了コード0。
- PC幅、スマホ幅、Service Worker更新後が合格。
- 差分がテスト2ファイルだけ。
- 機能コードと資産版を変更していない。

停止条件:

- 既知以外のテストが失敗する。
- ブラウザーでチャット、管理、設定の回帰がある。
- shared fileの未コミット変更と競合する。

Gate 0合格後は、先に `2026-07-24-tomos-tauri-desktop-shell.md` のEntry Gate A0へ進む。Gate A合格後だけ `2026-07-23-tomos-pc-diagnostics-benchmark.md` へ進む。
