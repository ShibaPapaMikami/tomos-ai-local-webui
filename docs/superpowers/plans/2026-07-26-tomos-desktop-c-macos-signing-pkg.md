# TOMOS Desktop C macOS Signing, Notarization, and PKG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate B3合格版から、Developer ID署名・Apple公証・Gatekeeper確認済みのApple Silicon用`TOMOS_AI-v0.8.233-mac-arm64.pkg`を作る。

**Architecture:** build候補のnested Mach-Oを内側から署名し、Tauri app bundleをDeveloper ID Application、PKGをDeveloper ID Installerで署名する。署名・公証・staple・Gatekeeper・内容物監査・SHA-256を一つのrelease gate scriptで実行し、失敗成果物を配布候補から隔離する。

**Tech Stack:** Bash、Python、`codesign`、`pkgbuild`、`pkgutil`、`notarytool`、`stapler`、`spctl`

## Global Constraints

- Gate B1、B2、B3がすべて合格していること。
- version `0.8.233`、Bundle ID `com.shibapapastudio.tomos-ai`、PKG identifier `jp.local.gemma4-12b`。
- appはDeveloper ID Application、PKGはDeveloper ID Installerで署名する。
- hardened runtimeとtimestampを有効にする。
- notary profileはKeychain保存済み`tomos-notary`を使う。
- 署名、公証、staple、Gatekeeperのいずれかが失敗した成果物を配布しない。
- `/Applications/TOMOS AI.app`をこの工程では上書きしない。
- GitHub Releaseへ公開しない。
- commit、実機インストール、公開はそれぞれ別承認を必要とする。

---

### Task 1: release候補の静的監査を固定

**Files:**
- Create: `scripts/audit_macos_tauri_release.py`
- Create: `scripts/test_audit_macos_tauri_release.py`

**Interfaces:**
- Produces: `audit_app(app_path: Path, expected_version: str, expected_commit: str) -> list[str]`。

- [x] **Step 1: identifier、CPU、禁止fileの失敗testを書く**

```python
def test_rejects_wrong_bundle_identifier(tmp_path):
    app = make_app_fixture(tmp_path, bundle_id="example.invalid")
    assert "bundle_identifier" in audit_app(app, "0.8.233", "a" * 40)

def test_rejects_private_or_mutable_payload(tmp_path):
    app = make_app_fixture(tmp_path, extra_files=["Contents/Resources/tomos/.git/config"])
    assert "forbidden_payload" in audit_app(app, "0.8.233", "a" * 40)
```

- [x] **Step 2: REDを確認する**

Run: `python3 scripts/test_audit_macos_tauri_release.py`

Expected: audit module未作成で失敗。

- [x] **Step 3: auditを実装する**

Info.plist、Mach-O architecture、Python version、build manifest、source commit、resource allowlist、`.git`、`.env`、DB、log、model、token-like fileを確認する。ファイル本文をterminalへ表示しない。

- [x] **Step 4: GREENを確認する**

Run: `python3 scripts/test_audit_macos_tauri_release.py`

Expected: 全件合格。

---

### Task 2: nested codeとappの署名

**Files:**
- Create: `scripts/sign-macos-tauri-app.sh`
- Create: `scripts/test_sign_macos_tauri_app.py`
- Create: `src-tauri/Entitlements.plist`

**Interfaces:**
- Consumes: `dist/candidate/TOMOS AI.app`。
- Produces: `dist/signed/TOMOS AI.app`。

- [x] **Step 1: 署名順序と必須optionのcontract testを書く**

```python
def test_signs_nested_code_before_app():
    script = SIGN_SCRIPT.read_text(encoding="utf-8")
    assert script.index("Resources/python") < script.index('\"$SIGNED_APP\"')
    assert "--options runtime" in script
    assert "--timestamp" in script
    assert "Developer ID Application:" in script
```

- [x] **Step 2: REDを確認する**

Run: `python3 scripts/test_sign_macos_tauri_app.py`

Expected: sign script未作成で失敗。

- [x] **Step 3: 明示的nested signingを実装する**

`find`で実行可能file、`.dylib`、`.so`を収集し、pathをsortして内側から署名する。symlinkは署名対象にせず、解決先がapp外なら失敗する。最後にmain executableとapp bundleを署名する。`--deep`は検証補助にだけ使い、署名処理を`--deep`任せにしない。

- [x] **Step 4: app署名をreadbackする**

Run:

```bash
codesign --verify --deep --strict --verbose=2 dist/signed/TOMOS\ AI.app
codesign -dv --verbose=4 dist/signed/TOMOS\ AI.app
```

Expected: identifier、TeamIdentifier `AJK3HH9G22`、runtime flag、
secure timestampを確認できる。

---

### Task 3: Tauri appをPKGへ格納してInstaller署名

**Files:**
- Create: `scripts/make-macos-tauri-pkg.sh`
- Modify: `scripts/test_mac_pkg_signing.py`

**Interfaces:**
- Consumes: `dist/signed/TOMOS AI.app`。
- Produces: `dist/candidate/TOMOS_AI-v0.8.233-mac-arm64.pkg`。

- [x] **Step 1: payloadとidentifier contract testを書く**

```python
def test_pkg_script_installs_tauri_app():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "TOMOS AI.app" in script
    assert 'jp.local.gemma4-12b' in script
    assert "Developer ID Installer:" in script
    assert "/Applications/Gemma4_12B" not in script
```

- [x] **Step 2: REDを確認する**

Run: `python3 scripts/test_mac_pkg_signing.py`

Expected: new PKG script契約で失敗。

- [x] **Step 3: PKG生成を実装する**

一時pkgrootの`Applications/TOMOS AI.app`へ署名済みappをcopyし、`pkgbuild --root ... --identifier jp.local.gemma4-12b --version 0.8.233 --install-location / --sign`を実行する。旧folderやuser dataをpostinstall scriptで操作しない。

- [x] **Step 4: PKG内容と署名を確認する**

Run:

```bash
pkgutil --check-signature dist/candidate/TOMOS_AI-v0.8.233-mac-arm64.pkg
pkgutil --payload-files dist/candidate/TOMOS_AI-v0.8.233-mac-arm64.pkg
```

Expected: Developer ID Installer `AJK3HH9G22`、`Applications/TOMOS AI.app`のみを確認する。

---

### Task 4: 公証・staple・Gatekeeper gate

**Files:**
- Modify: `scripts/notarize-mac-pkg.sh`
- Create: `scripts/release-gate-macos-tauri.sh`
- Modify: `scripts/test_mac_pkg_signing.py`

**Interfaces:**
- Produces: `dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg`と`dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg.sha256`。

- [x] **Step 1: release gate順序testを書く**

testは`audit -> app signature -> pkg signature -> notary submit --wait -> staple -> validate -> spctl -> sha256`の順序を固定する。

- [x] **Step 2: REDを確認する**

Run: `python3 scripts/test_mac_pkg_signing.py`

Expected: release gate script未作成で失敗。

- [x] **Step 3: 失敗隔離付きgate scriptを実装する**

開始時にsource worktree clean、HEAD、version、CPU、署名identity、notary profileを確認する。途中失敗時は成果物を`dist/rejected/<timestamp>/`へ移し、`dist/notarized/`へ残さない。

- [x] **Step 4: 公証を実行する**

Run:

```bash
bash scripts/release-gate-macos-tauri.sh \
  dist/candidate/TOMOS_AI-v0.8.233-mac-arm64.pkg
```

Expected: notary result `Accepted`、stapler validate成功、`spctl`が`Notarized Developer ID`。

- [x] **Step 5: SHA-256をreadbackする**

`.sha256`の値と`shasum -a 256`の値が一致することを確認する。

---

### Task 5: Gate Cとインストール前handoff

**Files:**
- Modify: `docs/release-checklist.ja.md`
- Modify: `docs/github-release-guide.ja.md`
- Modify: `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`

- [x] **Step 1: release文書をTauri PKGへ更新する**

学生向けMac成果物は`TOMOS_AI-v0.8.233-mac-arm64.pkg`と明記する。Apple Silicon専用、旧data非削除、Ollamaは別途必要、公証済みであることを書く。ZIPを初心者向けassetにしない。

- [x] **Step 2: 全自動testをfresh実行する**

Run:

```bash
python3 scripts/test-desktop-release-version.py
python3 scripts/test_macos_python_runtime.py
python3 scripts/test_macos_tomos_resources.py
python3 scripts/test_macos_tauri_bundle.py dist/candidate/TOMOS\ AI.app
python3 scripts/test_desktop_api_session.py
python3 scripts/test_app_paths.py
python3 scripts/test_migration_manager.py
python3 scripts/test_audit_macos_tauri_release.py
python3 scripts/test_sign_macos_tauri_app.py
python3 scripts/test_mac_pkg_signing.py
cargo test --manifest-path src-tauri/Cargo.toml
git diff --check
```

Expected: 全件exit 0。

- [x] **Step 3: 署名・公証をfresh readbackする**

Run:

```bash
pkgutil --check-signature dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg
xcrun stapler validate dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg
spctl -a -vv -t install dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg
codesign --verify --deep --strict --verbose=2 dist/signed/TOMOS\ AI.app
codesign -dv --verbose=4 dist/signed/TOMOS\ AI.app
shasum -a 256 dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg
```

- [x] **Step 4: Gate C判定**

全検証成功後だけマスター台帳のGate Cを`合格`へ更新する。PKG path、byte size、SHA-256、source commit、notary submission IDを記録する。

- [x] **Step 5: インストール承認を依頼する**

この工程では`installer`、`open /Applications/TOMOS AI.app`、既存app停止・上書きを実行しない。Directorへ現在Macへの上書きインストールを別途申請する。
