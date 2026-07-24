# TOMOS Desktop Phase A Gate A報告

[V012 / Director]

## 判定

**Gate Aは合格。**

専用macOSウィンドウ、既存TOMOSサーバーの安全な再利用、owned server停止、異種HTTP server競合、最小権限、既存機能の自動回帰を確認した。
検証後はインストール版TOMOS `0.8.230` を再起動し、`/Applications/TOMOS AI.app` 配下のserverへ復旧した。

## Gate A記録

| 項目 | 結果 | 証拠・補足 |
|---|---|---|
| 基準HEAD | 合格 | `c14f29556396ee7bbc1362f727f8789a246ddb91` |
| 作業ブランチ | 合格 | `codex/desktop-tauri-shell` |
| 変更ファイル | 合格 | `.gitignore`、`src-tauri/**`、起動画面2ファイル、契約テスト、Tauri計画差分、本報告 |
| 依存追加承認 | 合格 | 承認済みの `tauri 2`、`tauri-build 2`、`tauri-plugin-single-instance 2` のみ。lock解決値は順に `2.11.5`、`2.6.3`、`2.4.3` |
| Rust tests | 合格 | `cargo test --manifest-path src-tauri/Cargo.toml`、5件成功 |
| Desktop契約テスト | 合格 | `python3 scripts/test-desktop-shell-contract.py` |
| 既存9 tests | 合格 | Node 5系統、Python 4系統が成功。`test_server_helpers.py` はlocalhost許可下で成功 |
| 構文・差分 | 合格 | `node --check`、`py_compile`、`git diff --check` が成功 |
| Mac専用window | 合格 | `TOMOS AI` 専用ウィンドウを実機表示。初期値 `1280 × 820`、`800 × 500` への縮小操作が `960 × 640` で停止することを実測 |
| ブラウザー自動起動なし | 合格 | `cargo run` から専用WebViewを生成し、ブラウザー起動API・Shell権限は未導入 |
| 単一起動 | 合格 | 2回目は終了コード0。1process・1window・1serverを維持。macOSの終了直後focus競合に対し250ms後の再focusを追加し、内部focusとOS前面化を実測 |
| owned server停止 | 合格 | Tauriが起動したworktree server PID `52142`、再確認PID `58320` はCommand-Q後に終了し、54876番が空いた |
| reused server維持 | 合格 | 既存server PID `8954` を再利用し、Tauri終了後も維持。全検証後はインストール版PID `59019`、version `0.8.230` へ復旧 |
| ポート競合 | 合格 | 標準HTTP server PID `55444` の404応答を異種serverと判定。固定日本語エラーを画面確認し、TOMOS終了後も同PIDを維持。確認後はテストserverだけを通常終了 |
| ブラウザーfallback | 合格 | 既存 `server.py` と `web/` は変更せず、既存9 testsが成功 |
| スマートフォンPWA | 合格 | Desktop専用ファイル以外のPWA実装は変更せず、`test-pwa-assets.js` が成功 |
| Console error | 合格 | Cargo実行中にpanic・capability errorなし。capabilityは `core:default` のみに固定し、通常画面と固定エラー画面を実機表示 |
| commit | 承認済み | 全自動テストと本報告を同じDesktop Phase A commitへ収録 |
| push・署名・公証・配布 | 対象外 | 未承認のため実施していない |

## 実装した安全境界

- 接続先は `127.0.0.1:54876` の正規TOMOSだけ。
- 異なるHTTP応答なら固定エラーを表示し、processを停止しない。
- Tauriが起動した子processだけを終了対象にする。
- 外部URL、Shell、外部書き込み権限を許可しない。
- main windowのcloseまたはdestroyでowned childを片付ける。
- 起動画面のload完了後にだけruntime判定を始め、早すぎるエラー通知を防ぐ。
- macOSの二重起動時は即時focusに加え、2つ目のprocess終了後にも再focusする。

## 次のEntry Gate

1. Desktop Phase A commit後もworktreeとbranchを保持する。
2. bundle、署名、公証、配布は別承認があるまで開始しない。
3. 配布工程ではPKG実体の署名、公証、Gatekeeper、再ダウンロード検証を別Gateで行う。
