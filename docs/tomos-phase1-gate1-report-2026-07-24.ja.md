# TOMOS Phase 1 Gate 1報告

[V013 / Phase 1]

## 判定

- Gate 1: 合格
- 基準HEAD: `eec53329aae99a9be950e92e842b9121c511a14d`
- branch: `codex/phase1-pc-diagnostics`
- worktree: `.worktrees/phase1-pc-diagnostics`
- 依存追加: なし
- commit / push / 配布: 未実施

## 実装者

- CPU、macOS・Linux・WindowsのRAM、GPU名、vendor、VRAMまたは統合メモリをローカル診断へ追加した。
- 理論推薦を `basis: theoretical` として返し、実測値とは別の一時状態に限定した。
- 取得済みかつ `allowAutoSelect` が有効なモデルだけを、明示クリック後に固定条件で短時間測定するようにした。
- 同時実行をHTTP 409、許可外モデルとlocalhost以外のOllama URLをHTTP 400で拒否するようにした。
- モデル取得・削除・自動選択、Memory・Knowledge・localStorage保存、外部送信は追加していない。

## レビュー者

- 初回指摘: localhost外のOllama URL、サーバー側同時実行、UIテスト不足、OS分岐テスト不足。
- 修正後再レビュー: Critical 0件、Important 0件。
- 追加の軽微指摘だったエラー表示も、同時実行・localhost限定・許可外モデルを区別する文言へ修正した。

## 検証者

- parser tests: 合格。macOS、Linux、Windows、NVIDIA、Apple Silicon、GPU未検出、取得失敗を確認した。
- benchmark tests: 合格。許可済み200、許可外400、localhost外400、同時実行409、固定条件、タイミング値のみ返却を確認した。
- settings tests: 合格。未実行から実行中・完了への遷移、二重クリック防止、古い応答破棄、選択モデル不変、保存なしを実コードで確認した。
- 既存tests: 合格。Tauri contract、Cargo 5件、model selection、ASR、management、PWA、server、study pack、context、Knowledge、JavaScript/Python構文、`git diff --check` を確認した。
- Mac診断: Apple M3 Max、36GB RAM、Apple Silicon GPU、36GB統合メモリ、Ollama 0.32.1を取得した。
- Windows fixture: PowerShell RAM、NVIDIA VRAM、AMD GPU、VRAM不明、GPU未検出を確認した。
- 明示クリック: 1回のクリックで実測が完了し、選択モデルは前後とも「モデル自動」のまま、要求回数は1回だった。
- ブラウザー/PWA: 1440×900、390×844、1280×820、960×640で横はみ出しなし。理論表示、GPU情報、速度テスト操作を確認した。
- Tauri app: 起動、localhost資産読込、所有サーバー起動を確認した。終了後は所有サーバーだけが停止し、OllamaはHTTP 200のまま残った。正確な2サイズはTauri contractと同一画面の1280×820・960×640表示で確認した。
- 復旧: 検証後、インストール済みTOMOS AI 0.8.230を`/Applications/TOMOS AI.app`から再起動した。

## 承認者

- Gate 1判定: 合格
- commit承認: 未承認
- 次Phase承認: 未承認

## 未完了

- Phase 1変更のcommit。
- Phase 2のDirector指示と開始承認。
