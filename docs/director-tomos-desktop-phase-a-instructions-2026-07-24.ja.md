# ディレクター向け実行指示: TOMOS Desktop Phase A

## 件名

TOMOSを既存ブラウザーUIからTauri専用デスクトップアプリへ移行するPhase Aの開始

## 現在地

- Gate 0: 合格
- Phase 0 commit: `478e867e89664f7a8caa9d25d3d5ba098680f806`
- Phase 0 branch: `codex/phase0-baseline-stabilization`
- Rust: `1.94.1`
- Cargo: `1.94.1`
- Python: `3.14.4`
- Tauri依存取得: Director承認済み
- push、配布、署名、公証: 未承認

## ディレクターの指示

エンジニアは、次の正本を順番どおり読み、Desktop Phase Aだけを実装してください。

1. `AGENTS.md`
2. `DESIGN.md`
3. `VOICE.md`
4. `MEMORY.md`
5. `PLUGIN.md`
6. `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
7. `docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md`
8. `docs/superpowers/plans/2026-07-24-tomos-tauri-desktop-shell.md`
9. `docs/engineer-tomos-desktop-app-instructions-2026-07-24.ja.md`

旧 `docs/superpowers/plans/2026-07-21-macos-app-launcher.md` は実行しないでください。

## 実装対象

- `src-tauri/**`
- `web/desktop-starting.html`
- `web/desktop-starting.js`
- `scripts/test-desktop-shell-contract.py`
- `.gitignore` の `src-tauri/target/` 追加

## 実装しないもの

- `server.py` と既存Web機能の変更
- PWA資産版とService Workerの変更
- Python同梱
- モデル、音声モデル、追加Python依存の取得
- 任意shell実行権限
- 外部API、Memory自動保存
- PKG、MSI、署名、公証、GitHub Release
- push

## 必須の進め方

1. `478e867e89664f7a8caa9d25d3d5ba098680f806` を基準に専用worktreeを作る。
2. `scripts/test-desktop-shell-contract.py` を先に追加し、期待した理由で失敗することを確認する。
3. 1つの契約だけを満たす最小実装を追加する。
4. Python契約テストとRust testを合格させてから次のTaskへ進む。
5. ポート競合時に別プロセスを停止しない。
6. アプリ終了時はTauriが起動したPython子プロセスだけを停止する。
7. 既存TOMOSが起動済みなら再利用し、終了時も維持する。
8. 各Taskのcommitは今回の承認範囲で実行できる。pushは行わない。

## 取得を承認した依存

取得元はcrates.ioに限定します。

- `tauri 2`
- `tauri-build 2`
- `tauri-plugin-single-instance 2`

これ以外のcrate、npm package、Python packageが必要になった場合は停止し、Directorへ再申請してください。

## Gate Aの合格条件

- ブラウザーを自動起動せず、`TOMOS AI` 専用windowに既存UIが表示される。
- 単一起動が機能する。
- owned serverだけを停止し、reused serverを停止しない。
- TOMOS以外の54876番プロセスを停止しない。
- Python契約テスト、Rust test、既存9テスト、構文確認がすべて合格する。
- `1280 × 820`、`960 × 640`、スマートフォンPWA `390 × 844` で重大回帰がない。
- Tauri capabilityにshell権限、任意外部書き込み権限がない。

## 停止条件

- `server.py` または既存Web機能の変更が必要になる。
- localhost以外の待受が必要になる。
- 未承認依存が必要になる。
- 既存localStorageキーの変更が必要になる。
- 別プロセスを停止しないと動作しない。
- 既存テストまたはブラウザー/PWAに回帰が出る。

停止時は回避実装を追加せず、原因、影響範囲、最小の選択肢をDirectorへ報告してください。

## 報告形式

```text
[Desktop Phase A / Gate A]
基準HEAD:
変更ファイル:
依存追加承認:
Rust tests:
既存9 tests:
Mac専用window:
ブラウザー自動起動なし:
単一起動:
owned server停止:
reused server維持:
ポート競合:
ブラウザーfallback:
スマートフォンPWA:
Console error:
未完了:
```

空欄を残さず、`合格`、`不合格`、または実際のエラーを記入してください。
