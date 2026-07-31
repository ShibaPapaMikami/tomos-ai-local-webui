# エンジニア向け実装指示: TOMOSデスクトップアプリ統合

## 件名

TOMOS Phase 0完了後のTauriデスクトップアプリ化

## 目的

現在のTOMOSを全面的に作り直さず、既存の `web/` と `server.py` を再利用して、PCではブラウザーを開かないTauri専用アプリへ段階移行してください。

スマートフォンPWAと問題調査用ブラウザー経路は残します。Knowledge、Memory、教材パック、Plugin権限、既存モデル、既存保存キーを壊さないことを最優先にしてください。

## 正本

必ず次の順で読んでください。

1. `AGENTS.md`
2. `DESIGN.md`
3. `VOICE.md`
4. `MEMORY.md`
5. `PLUGIN.md`
6. `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
7. `docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md`
8. `docs/superpowers/plans/2026-07-24-tomos-tauri-desktop-shell.md`

矛盾時は、上の順で先に書かれている文書を優先してください。工程別計画とマスター計画が矛盾する場合は実装を止め、マスター計画を先に修正してください。

次の旧計画は実行しないでください。

- `docs/superpowers/plans/2026-07-21-macos-app-launcher.md`

この旧計画から引き継ぐのは、Bundle ID、PKG identifier、既存データを削除しない方針、Mac署名・公証条件だけです。

## 現在の状態

- Phase 0基準HEAD: `c7b8bb13160c08ccb793586b4ceab218e00a2b6c`
- Phase 0 worktree: `.worktrees/phase0-baseline-stabilization`
- Phase 0 branch: `codex/phase0-baseline-stabilization`
- `scripts/test-management-helpers.js` の固定asset版assertは版数非依存へ修正済みです。
- `scripts/test_server_helpers.py` はSarashinaの正規状態 `needs_runner` を許容するよう、承認済みの1行修正を追加済みです。
- QR生成に必要なPython package `segno 1.6.6` は、Director承認後にユーザーPython 3.14領域へ導入済みです。
- 全9テスト、構文確認、PC幅、スマホ幅、Service Worker再読込後、Console error 0件を確認し、Gate 0は合格しました。
- Phase 0差分は `478e867e89664f7a8caa9d25d3d5ba098680f806` としてcommit済みです。
- Gate 0記録は `docs/tomos-phase0-gate0-report-2026-07-24.ja.md` です。
- Tauri依存追加とDesktop Phase A実装は承認済みです。
- `docs/director-tomos-desktop-phase-a-instructions-2026-07-24.ja.md` の指示に従ってください。
- push、配布、署名、公証は未承認です。

## 実装順序

順序を入れ替えたり、並行実装したりしないでください。

```text
Phase 0 基準線安定化
  -> Gate 0
Desktop Phase A Tauri最小Shell
  -> Gate A
Phase 1 PC診断
  -> Gate 1
Phase 2 音声入力
  -> Gate 2
Phase 3 TTS共通基盤
  -> Gate 3
Phase 4 Markdown Skill Manager
  -> Gate 4
任意のExperiment EまたはV
Desktop Phase B 製品runtime・API・保存境界
  -> Gate B
Desktop Phase C macOS署名・公証・PKG
  -> Gate C
Desktop Phase D Windows署名・MSI
  -> Gate D
```

Experiment EとVは任意です。Desktop Phase Bの必須条件ではありません。実行する場合も1つずつ進め、Desktop Phase Bと同時に作業しないでください。

## 直近の指示

### 1. Phase 0を閉じる

この項目は完了済みです。再実行が必要な場合だけ、以下の手順とGate 0記録を使ってください。

セットアップスクリプト全体はモデル取得やOllama起動へ進むため、Phase 0検証目的では実行しないでください。承認対象は `segno` 単体だけです。

導入後、次をすべて実行してください。

```bash
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-asr-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test_server_helpers.py
python3 scripts/test_study_pack_manager.py
python3 scripts/test_context_core.py
python3 scripts/test_knowledge_layer.py
node --check web/models.js
node --check web/settings.js
node --check web/asr.js
node --check web/management.js
node --check web/app.js
python3 -m py_compile server.py
git diff --check
git status --short --branch
```

期待結果:

- 9テストがすべて終了コード0。
- JavaScriptとPythonの構文確認が終了コード0。
- Phase 0の差分は `scripts/test-management-helpers.js` と `scripts/test_server_helpers.py` だけ。
- 機能コード、PWA資産版、Service Workerを変更していない。

続いてブラウザーで次を確認してください。

- PC幅 `1440 × 900`
- スマホ幅 `390 × 844`
- Service Worker更新後
- チャット、停止、モデル表示、PC診断、音声ボタン、教材パック、Knowledge、Memory
- Console errorなし

確認結果は `docs/tomos-phase0-gate0-report-2026-07-24.ja.md` に記録済みです。

### 2. Tauri依存追加の承認記録

次の依存はDirector承認済みです。

```text
tauri 2
tauri-build 2
tauri-plugin-single-instance 2
```

取得元はcrates.ioです。これ以外のcrateが必要になった場合は停止して再承認を取ってください。

### 3. Desktop Phase Aを専用worktreeで実装する

Gate 0の承認済みcommitを基準に、新しい専用worktreeを作ってください。

実装の正本:

- `docs/superpowers/plans/2026-07-24-tomos-tauri-desktop-shell.md`

最小成果物:

- `src-tauri/`
- `web/desktop-starting.html`
- `web/desktop-starting.js`
- `scripts/test-desktop-shell-contract.py`
- `.gitignore` の `src-tauri/target/`

この工程では次を変更しないでください。

- `server.py`
- 既存 `web/app.js`
- モデル構成
- 保存キー
- PWA資産版
- Mac PKG
- Windows MSI
- Python runtime同梱
- localhost API token
- データ移行

Gate Aでは次を確認してください。

- ブラウザーを開かず `TOMOS AI` windowに既存UIが表示される。
- 二重起動でserverが増えない。
- app終了時にappが起動したserverだけ終了する。
- 先に起動していた正規TOMOS serverを終了しない。
- 54876を使う別processを自動停止しない。
- `.command`、`.bat`、PWAが維持される。

## 安全停止条件

次の場合は、その場で実装を止めて報告してください。

- 基準線テストが別の理由で失敗する。
- shared fileに別担当の未コミット変更がある。
- 新しい依存、外部通信、モデル取得、秘密情報が必要になる。
- localhost以外への待受が必要になる。
- 別processの停止が必要になる。
- 既存 `gemma4.*` キーの変更が必要になる。
- Memoryへの自動保存が必要になる。
- TauriとPWAで既存UIを分岐しないと実現できない。

報告形式:

```text
[Vxxx / 工程名]

■ 実装者
- 変更ファイル
- 実装した境界

■ レビュー者
- 要件一致
- 安全境界
- 差し戻し

■ 検証者
- 実行コマンド
- 成功件数
- 手動確認

■ 承認者
- commit承認
- 次工程承認

■ 未完了
- 残作業
- 必要な外部確認
```

## 禁止事項

- Agent-Reach本体を変更しない。
- 依存、モデル、外部バイナリを無承認で取得しない。
- 外部API、SNS、Cookie、ログイン情報、外部書き込みを追加しない。
- モデル、Memory、Knowledge、教材パック、ユーザーデータを自動削除しない。
- 旧macOSブラウザー起動計画を実装しない。
- commit、push、配布、署名、公証、GitHub Release更新を無承認で行わない。
