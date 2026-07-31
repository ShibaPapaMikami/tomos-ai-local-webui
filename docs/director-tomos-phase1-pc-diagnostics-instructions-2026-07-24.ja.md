# ディレクター向け実行指示: TOMOS Phase 1 PC診断

## 件名

Gate A合格版を基準に、PC診断とユーザー承認付き短時間ベンチを実装する。

## 現在地

- Gate A: 合格
- 基準HEAD: `eec53329aae99a9be950e92e842b9121c511a14d`
- 基準branch: `codex/desktop-tauri-shell`
- Phase 1 branch: `codex/phase1-pc-diagnostics`
- Phase 1 worktree: `.worktrees/phase1-pc-diagnostics`
- 依存追加、モデル取得・削除、push、配布、署名、公証: 未承認

## ディレクターの指示

エンジニアは次の正本を順番どおり読み、Phase 1だけを実装してください。

1. `AGENTS.md`
2. `DESIGN.md`
3. `MEMORY.md`
4. `PLUGIN.md`
5. `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
6. `docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md`
7. `docs/superpowers/plans/2026-07-23-tomos-pc-diagnostics-benchmark.md`

## 実装対象

- `server.py`
- `scripts/test_server_helpers.py`
- `web/settings.js`
- `web/app.js`
- `web/index.html`
- `web/mobile.html`
- `web/i18n.js`
- `web/styles.css`
- `web/pwa.js`
- `web/sw.js`
- `scripts/test-settings-helpers.js`
- `scripts/test-model-selection.js`
- `scripts/test-pwa-assets.js`
- Phase 1の指示書、進行台帳、Gate報告

## 実装しないもの

- llmfit本体、外部バイナリ、追加依存の導入
- モデルのdownload、update、delete
- 推奨結果によるモデルの自動変更
- 診断値、prompt、生成文のMemory・Knowledge・localStorageへの保存
- localhost以外への診断値またはベンチ結果の送信
- Agent-Reach本体と外部サービス認証
- Tauri runtime、音声、Skillの機能変更
- commit、push、配布、署名、公証

## 必須の進め方

1. 基準HEADから専用worktreeを作り、既存テストを先に通す。
2. CPU・RAM・GPU情報のparser testを先に失敗させ、最小実装で合格させる。
3. 許可モデル判定とlocalhost benchmark testを先に失敗させ、最小実装で合格させる。
4. 設定画面の表示・明示操作・状態遷移testを先に失敗させ、最小実装で合格させる。
5. benchmarkはユーザーがボタンを押した場合だけ、取得済みかつ `allowAutoSelect` が有効なモデルで実行する。
6. benchmark後も選択モデルと保存データを変更しない。
7. 既存ブラウザー、PWA、Tauri appの回帰を確認する。
8. Gate 1判定後もcommitせず、Director承認を待つ。

## Gate 1の合格条件

- macOS、Linux、WindowsのRAM取得が失敗時を含め安全に処理される。
- GPU名、vendor、VRAMまたは統合メモリ、confidence、sourceが表示できる。
- 理論推薦と実測結果が混同されず、benchmarkは初期状態で未実行である。
- benchmarkは明示した1回のクリックだけで開始し、同時実行を拒否する。
- 未取得または許可外モデルはHTTP 400で拒否する。
- モデル取得・削除、自動モデル変更、外部送信、Memory・Knowledge保存が0件である。
- Python、設定画面、PWA資産、既存機能、Tauri appの関連検証が合格する。

## 停止条件

- 新しい依存が必要になる。
- localhost以外への通信が必要になる。
- モデル取得・削除または保存形式変更が必要になる。
- 既存localStorageキーの変更が必要になる。
- Tauri runtimeまたは音声・Skillの変更が必要になる。
- 別プロセスを停止しないと検証できない。

停止時は回避実装を追加せず、原因、影響範囲、最小の選択肢をDirectorへ報告してください。

## 報告形式

```text
[Phase 1 / Gate 1]
基準HEAD:
変更ファイル:
依存追加:
parser tests:
benchmark tests:
settings tests:
既存tests:
Mac診断:
Windows fixture:
unknown fallback:
明示クリック:
選択モデル不変:
保存・外部送信:
Tauri app:
ブラウザー/PWA:
未完了:
```

空欄を残さず、`合格`、`不合格`、または実際のエラーを記入してください。
