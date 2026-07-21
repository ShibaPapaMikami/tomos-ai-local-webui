# macOS App Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TOMOS AIを`/Applications/TOMOS AI.app`から起動し、ローカルサーバーの重複を防ぎながら既定ブラウザーで既存UIを開ける、公証可能なmacOSアプリ形式にする。

**Architecture:** 既存のブラウザーUIとPythonサーバーは変更せず、薄いmacOSランチャーと標準的な`.app`バンドルを追加する。アプリ本体は`Developer ID Application`、配布PKGは`Developer ID Installer`で個別に署名し、既存の公証処理へ渡す。

**Tech Stack:** Bash、Python unittest、macOS app bundle、`PlistBuddy`、`sips`、`iconutil`、`codesign`、`pkgbuild`、`notarytool`

## Global Constraints

- 次の配布バージョンは`0.8.220`とする。
- インストール先は`/Applications/TOMOS AI.app`とする。
- アプリのBundle IDは`com.shibapapastudio.tomos-ai`とする。
- PKGの既存identifier `jp.local.gemma4-12b`はアップグレード互換のため変更しない。
- 現在の`/Applications/Gemma4_12B`をインストーラーから自動削除しない。
- Ollamaモデル、ブラウザー保存データ、長期記憶、教材パックの保存キーを変更しない。
- 公開用`.app`は`Developer ID Application`、PKGは`Developer ID Installer`で署名する。
- 証明書、秘密鍵、APIキー、キーチェーン内容をリポジトリへ保存しない。
- 未署名または公証未完了のPKGをGitHub Releaseへ公開しない。
- 既存の未コミット文書を変更、削除、コミットしない。

## File Map

- Create: `scripts/macos-app-launcher.sh` — `.app`からサーバーを起動し、正常起動後にブラウザーを開く。
- Create: `scripts/make-mac-app.sh` — app bundle、Info.plist、ICNSを生成し、Application証明書で署名する。
- Create: `scripts/test_macos_app_launcher.py` — ランチャーの起動済み、未起動、失敗動作をテストする。
- Create: `scripts/test_macos_app_bundle.py` — app bundle構造、plist、アイコン、署名必須条件をテストする。
- Modify: `Gemma4_12B_Web.command` — アプリランチャーから呼ぶ場合だけブラウザー自動表示を抑止する。
- Modify: `scripts/make-mac-pkg.sh` — 旧フォルダーではなく`TOMOS AI.app`をPKGへ格納する。
- Modify: `scripts/test_mac_pkg_signing.py` — PKGがapp bundleを取り込む条件を追加する。
- Modify: `docs/native-installers.ja.md` — アイコン起動、旧フォルダー移行、2種類の証明書を説明する。
- Modify: `docs/github-release-guide.ja.md` — app署名を含む公開前確認を追加する。

---

### Task 1: Browser-open control and app launcher

**Files:**
- Create: `scripts/macos-app-launcher.sh`
- Create: `scripts/test_macos_app_launcher.py`
- Modify: `Gemma4_12B_Web.command`

**Interfaces:**
- Consumes: `GET http://127.0.0.1:54876/api/health`、`Start_Mac.command`
- Produces: `TOMOS_RESOURCE_ROOT`、`TOMOS_WEB_URL`、`TOMOS_OPEN_COMMAND`、`TOMOS_START_COMMAND`でテスト可能なランチャー

- [ ] **Step 1: Write the failing launcher tests**

`scripts/test_macos_app_launcher.py`に一時コマンドを使うunittestを追加する。

```python
class MacosAppLauncherTests(unittest.TestCase):
    def test_running_server_only_opens_browser(self):
        result = self.run_launcher(health_sequence=[True])
        self.assertEqual(result.open_count, 1)
        self.assertEqual(result.start_count, 0)

    def test_stopped_server_starts_once_then_opens_browser(self):
        result = self.run_launcher(health_sequence=[False, False, True])
        self.assertEqual(result.start_count, 1)
        self.assertEqual(result.open_count, 1)

    def test_start_timeout_shows_japanese_error_without_opening(self):
        result = self.run_launcher(health_sequence=[False] * 5)
        self.assertEqual(result.open_count, 0)
        self.assertIn("TOMOS AIを起動できませんでした", result.dialog_text)
```

- [ ] **Step 2: Run the tests and verify the failure**

Run: `python3 scripts/test_macos_app_launcher.py`

Expected: FAIL because `scripts/macos-app-launcher.sh` does not exist.

- [ ] **Step 3: Add browser suppression to the existing web launcher**

`Gemma4_12B_Web.command`のブラウザー起動部分を次に置き換える。

```bash
if [ "${GEMMA_SKIP_BROWSER_OPEN:-0}" != "1" ]; then
  (sleep 1; open "$WEB_URL" >/dev/null 2>&1 || true) &
fi
python3 server.py --host "$WEB_HOST" --port "$WEB_PORT"
```

- [ ] **Step 4: Implement the focused app launcher**

`scripts/macos-app-launcher.sh`は次の契約を満たす。

```bash
RESOURCE_ROOT="${TOMOS_RESOURCE_ROOT:-$(cd "$(dirname "$0")/../Resources/Gemma4_12B" && pwd)}"
WEB_URL="${TOMOS_WEB_URL:-http://127.0.0.1:54876}"
START_COMMAND="${TOMOS_START_COMMAND:-$RESOURCE_ROOT/Start_Mac.command}"
OPEN_COMMAND="${TOMOS_OPEN_COMMAND:-open}"
LOG_DIR="${TOMOS_LOG_DIR:-$HOME/Library/Logs/TOMOS AI}"

health_ok() {
  curl -fsS "$WEB_URL/api/health" >/dev/null 2>&1
}
```

起動済みなら`OPEN_COMMAND "$WEB_URL"`だけを実行する。未起動なら`GEMMA_SKIP_BROWSER_OPEN=1 nohup /bin/bash "$START_COMMAND"`を1回だけ実行し、1秒間隔で最大30回healthを確認する。成功後にブラウザーを開き、失敗時は`osascript`で「TOMOS AIを起動できませんでした。Ollamaが起動しているか確認してください。」と表示する。

- [ ] **Step 5: Run the launcher tests**

Run: `python3 scripts/test_macos_app_launcher.py`

Expected: `macOS app launcher tests: OK`

- [ ] **Step 6: Commit Task 1**

```bash
git add Gemma4_12B_Web.command scripts/macos-app-launcher.sh scripts/test_macos_app_launcher.py
git commit -m "macOSアプリ用ランチャーを追加"
```

---

### Task 2: Build a standard TOMOS AI.app bundle

**Files:**
- Create: `scripts/make-mac-app.sh`
- Create: `scripts/test_macos_app_bundle.py`
- Modify: `scripts/make-release-archives.sh`

**Interfaces:**
- Consumes: `dist/TOMOS_AI-vX.X.X-mac.zip`、`web/icons/icon-512.png`、`scripts/macos-app-launcher.sh`
- Produces: `scripts/make-mac-app.sh VERSION OUTPUT_APP`、`/Applications/TOMOS AI.app`互換bundle

- [ ] **Step 1: Write failing bundle contract tests**

`scripts/test_macos_app_bundle.py`へ次を追加する。

```python
def test_bundle_script_declares_required_structure():
    script = Path("scripts/make-mac-app.sh").read_text(encoding="utf-8")
    assert "Contents/MacOS" in script
    assert "Contents/Resources/Gemma4_12B" in script
    assert "Contents/Info.plist" in script
    assert "com.shibapapastudio.tomos-ai" in script
    assert "Developer ID Application:" in script
    assert 'codesign --force --options runtime --timestamp' in script

def test_release_archive_contains_launcher_source():
    script = Path("scripts/make-release-archives.sh").read_text(encoding="utf-8")
    assert 'copy_if_exists "scripts/macos-app-launcher.sh"' in script
```

- [ ] **Step 2: Run the bundle tests and verify failure**

Run: `python3 scripts/test_macos_app_bundle.py`

Expected: FAIL because `scripts/make-mac-app.sh` does not exist.

- [ ] **Step 3: Implement app bundle generation**

`scripts/make-mac-app.sh VERSION OUTPUT_APP`で次を生成する。

```text
TOMOS AI.app/
  Contents/
    Info.plist
    MacOS/TOMOS AI
    Resources/TOMOS.icns
    Resources/Gemma4_12B/...
```

Info.plistには次を設定する。

```xml
<key>CFBundleDisplayName</key><string>TOMOS AI</string>
<key>CFBundleExecutable</key><string>TOMOS AI</string>
<key>CFBundleIconFile</key><string>TOMOS</string>
<key>CFBundleIdentifier</key><string>com.shibapapastudio.tomos-ai</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>${APP_VERSION}</string>
<key>CFBundleVersion</key><string>${APP_VERSION}</string>
<key>LSMinimumSystemVersion</key><string>13.0</string>
```

`web/icons/icon-512.png`から16、32、128、256、512の1x/2x PNGを`sips`で作り、`iconutil`で`TOMOS.icns`を生成する。`TOMOS_MAC_APPLICATION_IDENTITY`が未指定なら、重複除外した`Developer ID Application`を1件だけ検出する。公開用証明書がない場合は停止する。テスト時だけ`TOMOS_MAC_APPLICATION_IDENTITY=-`でad-hoc署名を許可する。

- [ ] **Step 4: Include the launcher in release inputs**

`scripts/make-release-archives.sh`のMac用コピーへ次を追加する。

```bash
copy_if_exists "scripts/macos-app-launcher.sh" "$MAC_ROOT/scripts/"
```

- [ ] **Step 5: Run bundle tests and build an ad-hoc test app**

```bash
python3 scripts/test_macos_app_bundle.py
TOMOS_MAC_APPLICATION_IDENTITY=- bash scripts/make-mac-app.sh 0.8.220 /tmp/TOMOS\ AI.app
plutil -lint "/tmp/TOMOS AI.app/Contents/Info.plist"
codesign --verify --deep --strict --verbose=2 "/tmp/TOMOS AI.app"
```

Expected: tests pass, plist reports `OK`, and codesign verification exits 0.

- [ ] **Step 6: Commit Task 2**

```bash
git add scripts/make-mac-app.sh scripts/test_macos_app_bundle.py scripts/make-release-archives.sh
git commit -m "TOMOS AI.appの生成処理を追加"
```

---

### Task 3: Package TOMOS AI.app instead of the legacy folder

**Files:**
- Modify: `scripts/make-mac-pkg.sh`
- Modify: `scripts/test_mac_pkg_signing.py`

**Interfaces:**
- Consumes: `scripts/make-mac-app.sh VERSION OUTPUT_APP`
- Produces: `dist/TOMOS_AI-v0.8.220-mac.pkg` containing `/Applications/TOMOS AI.app`

- [ ] **Step 1: Add the failing package contract**

`scripts/test_mac_pkg_signing.py`へ次を追加する。

```python
def test_pkg_contains_signed_app_bundle_instead_of_legacy_folder() -> None:
    script = (ROOT / "scripts" / "make-mac-pkg.sh").read_text(encoding="utf-8")
    assert 'make-mac-app.sh" "$APP_VERSION" "$WORK_DIR/pkgroot/Applications/TOMOS AI.app"' in script
    assert 'pkgroot/Applications/Gemma4_12B' not in script
```

- [ ] **Step 2: Run the package test and verify failure**

Run: `python3 scripts/test_mac_pkg_signing.py`

Expected: FAIL because the legacy folder copy remains.

- [ ] **Step 3: Replace the legacy payload copy**

`scripts/make-mac-pkg.sh`からZIP展開と`Applications/Gemma4_12B`へのコピーを削除し、次を追加する。

```bash
mkdir -p "$WORK_DIR/pkgroot/Applications"
bash "$ROOT_DIR/scripts/make-mac-app.sh" \
  "$APP_VERSION" \
  "$WORK_DIR/pkgroot/Applications/TOMOS AI.app"
```

既存のPKG identifier、Installer証明書検出、署名検証は維持する。

- [ ] **Step 4: Run package and syntax tests**

```bash
python3 scripts/test_mac_pkg_signing.py
bash -n scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/macos-app-launcher.sh
```

Expected: tests pass and shell syntax check exits 0.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/make-mac-pkg.sh scripts/test_mac_pkg_signing.py
git commit -m "macOS PKGへTOMOS AI.appを格納"
```

---

### Task 4: Student-facing migration and release documentation

**Files:**
- Modify: `docs/native-installers.ja.md`
- Modify: `docs/github-release-guide.ja.md`

**Interfaces:**
- Consumes: Task 2 and Task 3 distribution behavior
- Produces: Exact installation, migration, signing, and release instructions

- [ ] **Step 1: Update the installer guide**

`docs/native-installers.ja.md`へ次の内容を追加する。

```markdown
インストール後は「アプリケーション」にある「TOMOS AI」を開きます。Launchpadからも起動できます。

以前の`/Applications/Gemma4_12B`は自動削除されません。新しい「TOMOS AI」で設定、長期記憶、教材パックを確認した後に、古いフォルダーをゴミ箱へ移動してください。
```

署名手順では、app bundleに`Developer ID Application`、PKGに`Developer ID Installer`が必要なことを明記する。

- [ ] **Step 2: Update the GitHub release gate**

`docs/github-release-guide.ja.md`へ次の確認コマンドを追加する。

```bash
codesign --verify --deep --strict --verbose=2 "/Applications/TOMOS AI.app"
pkgutil --check-signature dist/TOMOS_AI-vX.X.X-mac.pkg
xcrun stapler validate dist/TOMOS_AI-vX.X.X-mac.pkg
spctl -a -vv -t install dist/TOMOS_AI-vX.X.X-mac.pkg
```

- [ ] **Step 3: Validate documentation and commit**

```bash
git diff --check -- docs/native-installers.ja.md docs/github-release-guide.ja.md
git add docs/native-installers.ja.md docs/github-release-guide.ja.md
git commit -m "macOSアプリ版の利用手順を追加"
```

Expected: `git diff --check` exits 0.

---

### Task 5: Version alignment, local integration, signing, and notarization

**Files:**
- Modify: `server.py`
- Modify: `Gemma4_12B_Web.command`
- Modify: `Gemma4_12B_全部起動.command`
- Modify: `Gemma4_12B_Web.bat`
- Modify: `Gemma4_12B_All_Start.bat`
- Modify: `scripts/test-agent-reach-routing-smoke.py`

**Interfaces:**
- Consumes: completed `.app` and PKG build pipeline
- Produces: signed and notarized `dist/TOMOS_AI-v0.8.220-mac.pkg`

- [ ] **Step 1: Align every application version to 0.8.220**

既存のバージョン整合テストが読む6ファイルを`0.8.220`へ更新し、`scripts/test-agent-reach-routing-smoke.py`の`EXPECTED_APP_VERSION`も`0.8.220`へ更新する。

- [ ] **Step 2: Run all targeted automated tests**

```bash
python3 scripts/test_macos_app_launcher.py
python3 scripts/test_macos_app_bundle.py
python3 scripts/test_mac_pkg_signing.py
node scripts/test-pwa-assets.js
python3 scripts/test_server_helpers.py
python3 scripts/test-agent-reach-routing-smoke.py
bash -n scripts/macos-app-launcher.sh scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/notarize-mac-pkg.sh
python3 -m py_compile server.py
git diff --check
```

Expected: every test prints its pass message or exits 0.

- [ ] **Step 3: Confirm the Application signing prerequisite**

Run:

```bash
security find-identity -v -p codesigning | grep "Developer ID Application: Masafumi Mikami (AJK3HH9G22)"
```

Expected: exactly one personal Developer ID Application identity. If none exists, stop before release build and create/install it through Apple Developer Certificates. Do not substitute an Apple Development certificate.

- [ ] **Step 4: Build and inspect the signed app package**

```bash
bash scripts/make-release-archives.sh 0.8.220
bash scripts/make-mac-pkg.sh 0.8.220
pkgutil --expand-full dist/TOMOS_AI-v0.8.220-mac.pkg /tmp/tomos-pkg-expanded
codesign --verify --deep --strict --verbose=2 "/tmp/tomos-pkg-expanded/Payload/Applications/TOMOS AI.app"
```

Expected: the app bundle is present and signed by the personal Developer ID Application identity.

- [ ] **Step 5: Notarize, staple, and pass Gatekeeper**

```bash
bash scripts/notarize-mac-pkg.sh dist/TOMOS_AI-v0.8.220-mac.pkg
pkgutil --check-signature dist/TOMOS_AI-v0.8.220-mac.pkg
xcrun stapler validate dist/TOMOS_AI-v0.8.220-mac.pkg
spctl -a -vv -t install dist/TOMOS_AI-v0.8.220-mac.pkg
```

Expected: notarization is `Accepted`, stapler validation works, and `spctl` reports `source=Notarized Developer ID`.

- [ ] **Step 6: Perform manual migration QA**

1. Keep the existing`/Applications/Gemma4_12B` folder installed.
2. Install the new PKG and confirm `/Applications/TOMOS AI.app` appears with the TOMOS icon.
3. Launch from Finder and Launchpad; confirm the browser opens and the app shows version`0.8.220`.
4. Launch a second time; confirm the existing server is reused.
5. Confirm existing model state, settings, long-term memory, and study packs remain available.
6. Quit TOMOS, remove only the old`/Applications/Gemma4_12B` folder, and relaunch the new app.

- [ ] **Step 7: Commit version and integration changes**

```bash
git add server.py Gemma4_12B_Web.command Gemma4_12B_全部起動.command Gemma4_12B_Web.bat Gemma4_12B_All_Start.bat scripts/test-agent-reach-routing-smoke.py
git commit -m "TOMOS AI v0.8.220へ更新"
```

Do not push, upload release assets, or modify GitHub Release until the director explicitly approves publication.
