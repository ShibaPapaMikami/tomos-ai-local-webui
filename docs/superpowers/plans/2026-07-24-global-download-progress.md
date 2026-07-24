# 全画面共通ダウンロード進捗 実装計画

> **For Codex:** `superpowers:executing-plans` の手順に従い、各タスクをテスト先行で実行する。

**Goal:** AIモデルや追加機能のダウンロード状況を、どの画面を開いていても共通パネルで確認できるようにする。

**Architecture:** サーバー側で既存のモデル・ASR・OCR・Internet Layer・教材パックの状態を共通ジョブ形式へ正規化し、`/api/downloads/status` から返す。ブラウザー側は1つのポーラーと表示部品を持ち、全画面共通パネルと各機能の行内表示を同じジョブ情報から描画する。

**Tech Stack:** Python標準ライブラリ、TOMOS HTTPサーバー、Vanilla JavaScript、CSS、Node.jsテスト

---

### Task 1: 共通ジョブ形式と進捗解析

**Files:**
- Modify: `server.py`
- Test: `scripts/test_server_helpers.py`

1. Ollamaの進捗行から割合・転送済み量・総量を取り出す失敗テストを追加する。
2. 各セットアップジョブを共通形式へ変換する失敗テストを追加する。
3. テストを実行して意図した失敗を確認する。
4. 進捗解析関数と共通ジョブ変換関数を最小実装する。
5. テストを再実行して成功を確認する。

### Task 2: 教材パックの非同期ダウンロード

**Files:**
- Modify: `study_pack_manager.py`
- Modify: `server.py`
- Test: `scripts/test_study_pack_manager.py`

1. 分割読み込み時の進捗通知と上限維持を確認する失敗テストを追加する。
2. 教材パックの開始・状態取得を確認する失敗テストを追加する。
3. テストを実行して意図した失敗を確認する。
4. コールバック付き分割読み込みと非同期インストールジョブを実装する。
5. 既存インストールAPIは開始応答へ変更し、状態は共通APIから取得できるようにする。
6. テストを再実行して成功を確認する。

### Task 3: 共通進捗パネル

**Files:**
- Create: `web/download-progress.js`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `web/i18n.js`
- Modify: `web/sw.js`
- Modify: `web/pwa.js`
- Modify: `web/mobile.html`
- Create: `scripts/test-download-progress.js`

1. 状態正規化・完了表示時間・表示文言の失敗テストを追加する。
2. テストを実行して意図した失敗を確認する。
3. 共通ポーラー、固定パネル、再試行イベントを実装する。
4. パネルをアプリ最上位へ追加し、画面切替に依存せず表示する。
5. モバイル幅、ARIA、エラー継続表示をCSSとマークアップへ反映する。
6. テストを再実行して成功を確認する。

### Task 4: 各画面の行内進捗を共通化

**Files:**
- Modify: `web/settings.js`
- Modify: `web/asr.js`
- Modify: `web/management.js`
- Modify: `web/app.js`
- Test: `scripts/test-settings-helpers.js`
- Test: `scripts/test-management-helpers.js`
- Test: `scripts/test-asr-helpers.js`

1. モデル行と教材パック行が割合と状態を表示する失敗テストを追加する。
2. 既存のOCR・Internet Layer・ASR表示へ共通ジョブを渡す。
3. 教材パックの同期待ちをやめ、共通ジョブ完了後にカタログを更新する。
4. 関連テストを実行して成功を確認する。

### Task 5: 未取得モデル時の表示修正

**Files:**
- Modify: `web/app.js`
- Test: `scripts/test-model-selection.js`

1. AIモデル未取得時の案内に「コード理解」が付かない失敗テストを追加する。
2. モデルを呼ばない案内の `runMeta.codeUnderstanding` を常に `false` にする。
3. テストを再実行して成功を確認する。

### Task 6: バージョン更新と総合確認

**Files:**
- Modify: `server.py`
- Modify: `Gemma4_12B_Web.command`
- Modify: `Gemma4_12B_Web.bat`
- Modify: `Gemma4_12B_All_Start.bat`
- Modify: `Gemma4_12B_全部起動.command`
- Modify: `scripts/macos-app-launcher.sh`
- Modify: `scripts/test-agent-reach-routing-smoke.py`
- Modify: `scripts/test_macos_app_launcher.py`

1. アプリバージョンを `0.8.230` に統一する。
2. Python・Node関連テスト、構文チェック、`git diff --check` を実行する。
3. ローカルサーバーを起動し、デスクトップ幅とモバイル幅で共通パネルを確認する。
4. 変更ファイルと未解決事項を整理する。コミット・push・公開は行わない。
