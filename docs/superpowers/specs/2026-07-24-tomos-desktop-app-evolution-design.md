# TOMOSデスクトップアプリ統合進化 設計

## 決定

TOMOSのPC版は、ブラウザーを標準画面にする構成から、Tauriによる独立したデスクトップアプリへ段階移行する。

全面的な作り直しは行わない。現在の `web/`、`server.py`、Ollama連携、Knowledge、Memory、教材パック、Plugin権限を維持し、Tauriは次の責務だけを持つ。

- TOMOS専用ウィンドウを表示する。
- ローカルサーバーを1回だけ起動する。
- サーバーの準備完了後に既存UIをアプリ内へ表示する。
- アプリ終了時に、アプリが起動した子プロセスだけを停止する。
- macOSとWindowsの署名済み配布物を作る土台になる。

スマートフォン向けPWAと、問題調査用のブラウザー起動経路は残す。PCの一般利用ではアプリ版を標準にし、ブラウザー版を削除しない。

## 採用理由

### 採用: Tauriで既存UIを包む

- 既存のHTML、CSS、JavaScriptを再利用できる。
- Electronより配布サイズと常駐負荷を小さくしやすい。
- macOSとWindowsで同じアプリ境界を持てる。
- 将来、マイク、通知、ファイル選択、単一起動、更新、署名をアプリ側で管理できる。
- PythonとOllamaを一度に置き換えず、現在動いている経路を保てる。

### 不採用: アイコンからブラウザーを開くmacOSランチャー

`docs/superpowers/specs/2026-07-21-macos-app-launcher-design.md` は、`.app`を押すとブラウザーを開く設計である。インストール体験は改善するが、TOMOS専用ウィンドウ、アプリ終了、単一起動、マイク権限、アプリ内更新の責務を持てないため、PC版の最終構成には採用しない。

ただし、次の判断は新しいアプリ設計へ引き継ぐ。

- Bundle IDは `com.shibapapastudio.tomos-ai`。
- 既存PKG identifier `jp.local.gemma4-12b` はアップグレード互換のため維持する。
- `/Applications/Gemma4_12B` を自動削除しない。
- app bundleはDeveloper ID Application、PKGはDeveloper ID Installerで署名する。
- 公開前に公証、staple、Gatekeeper確認を行う。

### 不採用: Electronで全面移行

実装速度は高いが、現在のUIを表示するだけの初期段階にNode.jsランタイム全体を同梱する利点が小さい。Tauriで実現できない必須要件が実機PoCで確認された場合だけ、同じ設計境界を保ったまま再評価する。

## 現在から完成形への対応

| 領域 | 現在 | 最初のアプリ版 | 完成形 |
| --- | --- | --- | --- |
| PC画面 | Safari、Chromeなどのブラウザー | Tauri専用ウィンドウ | Tauri専用ウィンドウ |
| スマートフォン | PWA | 変更なし | PWAを維持 |
| Web UI | `web/`を `server.py` が配信 | 同じUIをアプリ内表示 | 同じUIとアプリ専用adapter |
| Python | 利用者PCのPythonで起動 | 利用者PCのPythonでPoC | 署名対象の同梱runtime |
| Ollama | 外部アプリ | 外部アプリ | 初期は外部アプリを維持 |
| 起動 | `.command`、`.bat`、ブラウザー | Tauriがサーバーを起動 | 単一起動と状態表示 |
| 終了 | ターミナルまたはプロセス停止 | アプリが自分の子だけ停止 | バックグラウンド動作を明示選択 |
| 設定保存 | ブラウザーの `localStorage` | 既存キーを維持 | 承認済み移行後にアプリ管理保存 |
| 配布 | Mac PKG、Windows MSIのランチャー | 開発用app PoC | 署名済みPKGとMSI |
| 更新 | GitHub Releaseから手動 | 手動 | 署名検証付き更新通知から段階導入 |

## アーキテクチャ

```text
TOMOS Desktop (Tauri)
  ├─ Window Manager
  │    └─ http://127.0.0.1:54876 をアプリ内WebViewへ表示
  ├─ Runtime Supervisor
  │    ├─ Python server.pyを子プロセスとして1回だけ起動
  │    ├─ /api/healthを待つ
  │    └─ アプリ終了時に自分の子だけ停止
  ├─ Permission Boundary
  │    ├─ localhost以外を初期拒否
  │    ├─ 外部URLは既定ブラウザーへ明示遷移
  │    └─ マイク・ファイル操作を必要時だけ許可
  └─ Existing TOMOS
       ├─ web/
       ├─ server.py
       ├─ Ollama
       ├─ Knowledge / Memory
       ├─ Study Pack / Skill
       └─ Plugin permission
```

### Desktop Shell

Tauriは見た目の再実装をしない。起動中はWebViewを非表示にし、`server.py` のhealthが成功した後に `http://127.0.0.1:54876/` を読み込んで表示する。

初期PoCではシステムのPython 3.11と既存Ollamaを利用する。Python同梱、アプリ管理データ、更新機能はPoC合格後の別工程に分ける。

### Runtime Supervisor

起動状態は次の有限状態で管理する。

```text
idle
  -> starting
  -> ready
  -> stopping
  -> stopped

starting
  -> failed_timeout
  -> failed_missing_python
  -> failed_port_in_use
  -> failed_server_exit
```

固定ポートは既存保存キーとブラウザーfallbackとの互換性を優先して `54876` を使う。ポートが別プロセスに使われている場合、そのプロセスを自動停止しない。`/api/health` のTOMOS識別情報が一致した場合だけ既存サーバーを再利用し、一致しなければ日本語エラーで停止する。

### Window and Navigation

- アプリのウィンドウ名は `TOMOS AI`。
- 初期サイズは `1280 × 820`、最小サイズは `960 × 640`。
- Desktop Phase Aでは外部の `http` / `https` 遷移を拒否し、TOMOS画面が外部サイトへ置き換わらないことを先に保証する。
- Desktop Phase Bで、許可した `http` / `https` リンクだけをユーザー操作時に既定ブラウザーへ渡す。
- `127.0.0.1:54876`、`localhost:54876` 以外へのWebView遷移を拒否する。
- 複数起動時は新しいサーバーを作らず、既存ウィンドウを前面へ戻す。
- 初期PoCではメニューバー常駐とバックグラウンド常駐を入れない。ウィンドウを閉じるとアプリを終了する。

### Data and Migration

最初のアプリ版では `gemma4.*` のlocalStorageキー、Knowledge、Memory、教材パックの保存形式を変更しない。

TauriのWebView保存領域と既存ブラウザーの保存領域は同一とは限らないため、配布版へ進む前に明示的な移行工程を設ける。

移行原則:

- 読み取り、プレビュー、ユーザー承認、コピー、検証の順で進める。
- 元データを自動削除しない。
- 既存ブラウザー側のデータを上書きしない。
- Memoryへ自動登録しない。
- 移行に失敗してもブラウザー版へ戻れる。
- 移行後も `gemma4.*` キーの互換読込期間を設ける。

## セキュリティ境界

### 初期PoC

- `server.py` は `127.0.0.1` だけで待ち受ける。
- Tauri capabilityはmain windowと必要最小限の操作だけへ限定する。
- shellの任意コマンド実行を許可しない。
- Python起動引数はアプリ内の固定値だけを使う。
- 外部API、モデル取得、依存追加、ファイル削除は行わない。

### 配布前必須

- localhost APIへ起動ごとのセッショントークンを追加する。
- WebViewからの状態変更APIはトークン不一致を拒否する。
- Origin、Host、Content-Typeを検証する。
- アプリが起動したプロセスのPIDと開始時刻を保持し、他プロセスを停止しない。
- ログへ会話本文、Memory本文、APIキー、Cookieを出さない。
- macOSとWindowsそれぞれで権限表示と署名を実機確認する。

## 既存計画との統合順序

```text
Phase 0 既存基準線の安定化
  -> Gate 0
Desktop Phase A Tauri最小shell
  -> Gate A
Phase 1 PC診断と短時間ベンチ
  -> Gate 1
Phase 2 音声入力のVADと常駐経路
  -> Gate 2
Phase 3 TTS共通基盤
  -> Gate 3
Phase 4 Markdown Skill Manager
  -> Gate 4
Experiment E / V
  -> 個別承認
Desktop Phase B runtime・API・保存境界の製品化
  -> Gate B
Desktop Phase C macOS署名・公証・PKG
  -> Gate C
Desktop Phase D Windows署名・MSI
  -> Gate D
```

Desktop Phase AをPhase 1より先に置く。これにより、PC診断、音声、TTS、Skillを追加する各工程で、ブラウザーとデスクトップアプリの両方を回帰確認できる。

Experiment E / Vは任意であり、Desktop Phase Bの必須条件ではない。実行する場合はDesktop Phase Bと同時に進めず、選んだ実験のGateを閉じてからDesktop Phase Bへ進む。

## Gate

### Gate 0

既存のPhase 0計画をそのまま使う。全9テスト、構文確認、PC幅、スマホ幅、Service Worker確認が合格するまでDesktop Phase Aを開始しない。

### Gate A: Tauri最小shell

- 新しい依存追加をDirectorが承認している。
- macOSでTOMOSがブラウザーを開かず専用ウィンドウに表示される。
- 二重起動でサーバーが増えない。
- アプリ終了時にアプリが起動したサーバーだけが終了する。
- ポート競合時に別プロセスを停止しない。
- 既存 `.command`、`.bat`、PWA、全基準テストが維持される。
- Windows向けコードがコンパイル可能な境界になっている。

### Gate 1からGate 4

既存のPC診断、音声入力、TTS、Skill Manager計画を使う。各Gateへ、Macアプリウィンドウでの確認を追加する。PWA確認は削除しない。

### Gate B: 製品runtimeと保存境界

- 利用者にPythonの事前インストールを要求しない。
- localhost APIにセッショントークンがある。
- app-managed data directoryと移行プレビューがある。
- 既存データを自動削除しない。
- オフライン時に既存ローカル機能が動く。
- ブラウザーfallbackが維持される。

### Gate C: macOS配布

- `TOMOS AI.app` がDeveloper ID Applicationで署名されている。
- PKGがDeveloper ID Installerで署名されている。
- 公証がAccepted、staplerとGatekeeperが合格する。
- 既存 `/Applications/Gemma4_12B` を自動削除しない。
- 新規Mac相当と既存利用者環境の両方で移行確認が合格する。

### Gate D: Windows配布

- MSIがTauriアプリをインストールする。
- Windowsコード署名を確認できる。
- WebView2、同梱Python、Ollama不足を日本語で案内する。
- 既存ランチャー版から設定を読み取り専用で検出できる。
- アンインストールでユーザーデータとモデルを削除しない。

## エラー表示

技術用語を利用者へ直接出さず、次の分類で案内する。

| 内部状態 | 利用者向け表示 |
| --- | --- |
| `failed_missing_python` | 「TOMOSの実行環境を確認できませんでした。再インストールしてください。」 |
| `failed_port_in_use` | 「TOMOSが使う場所を別のアプリが使用しています。ほかのTOMOSを終了して、もう一度開いてください。」 |
| `failed_timeout` | 「TOMOSの起動に時間がかかっています。Ollamaを確認して、もう一度開いてください。」 |
| `failed_server_exit` | 「TOMOSを起動できませんでした。診断情報を開いてください。」 |
| Ollamaなし | 「ローカルAIの準備が必要です。Ollamaをインストールまたは起動してください。」 |

詳細はユーザーが「診断情報を表示」を押した時だけ表示し、秘密情報と本文を除外したログをコピーできるようにする。

## 検証方針

### 自動

- Rustの状態遷移、子プロセス所有、ポート競合、URL許可判定を単体テストする。
- Tauri設定、capability、bundle ID、外部URL拒否を契約テストする。
- 既存9本の基準テストとJavaScript/Python構文確認を毎Gateで実行する。
- `git diff --check` と対象ファイル一覧を確認する。

### 手動

- macOS: 未起動、起動済み、Ollamaなし、Pythonなし、ポート競合、2回起動、終了、再起動。
- Windows: Gate Dで同じ項目を実機確認する。
- PC幅: `1280 × 820` と最小 `960 × 640`。
- スマートフォン: PWAの `390 × 844` を維持する。
- マイク、音声停止、ファイル選択、外部リンクを各機能Phaseでアプリ内確認する。

## 完了条件

- PCの標準導線でブラウザーが開かない。
- TOMOS専用ウィンドウで既存機能が動く。
- スマートフォンPWAとブラウザーfallbackが残っている。
- 既存のKnowledge、Memory、教材パック、Plugin権限を壊していない。
- macOSとWindowsの配布物が署名されている。
- 既存ユーザーデータとモデルを自動削除しない。
- Phase 0、Desktop A、Phase 1から4、Desktop BからDの全Gateが合格している。
