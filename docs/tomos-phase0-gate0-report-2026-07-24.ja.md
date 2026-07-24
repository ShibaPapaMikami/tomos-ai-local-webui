# TOMOS Phase 0 / Gate 0 検証報告

## 判定

`合格`

Phase 0差分はcommit済みです。Desktop Phase Aは、承認済みのディレクター向け実行指示を基準に開始します。

## 基準

- 基準HEAD: `c7b8bb13160c08ccb793586b4ceab218e00a2b6c`
- Gate 0 commit: `478e867e89664f7a8caa9d25d3d5ba098680f806`
- worktree: `.worktrees/phase0-baseline-stabilization`
- branch: `codex/phase0-baseline-stabilization`
- Python: `3.14.4`
- QR依存: `segno 1.6.6`
- `segno` 配置先: `/Users/masafumimikami/Library/Python/3.14/lib/python/site-packages`

## 変更範囲

- `scripts/test-management-helpers.js`
  - i18nとstylesheetの固定asset版assertを版数非依存へ変更。
- `scripts/test_server_helpers.py`
  - Sarashina OCRの正規状態 `needs_runner` を許容集合へ追加。

機能コード、PWA資産版、Service Workerは変更していません。

## 自動検証

| 項目 | 結果 |
| --- | --- |
| JavaScriptテスト 5本 | 合格 |
| Pythonテスト 4本 | 合格 |
| JavaScript構文確認 5本 | 合格 |
| `server.py` 構文確認 | 合格 |
| `git diff --check` | 合格 |
| Phase 0 worktreeの変更範囲 | 対象テスト2ファイルだけ |

`scripts/test_server_helpers.py` はsandbox内のlocalhost bind制限だけで一度停止したため、計画どおり同じコマンドを制限外で再実行し、`server helper tests passed` を確認しました。

## ブラウザー基準線

| 確認項目 | 結果 | 確認内容 |
| --- | --- | --- |
| PC幅 `1440 × 900` | 合格 | 横はみ出しなし、チャット送信、生成停止、Qwen3 4B、Agentic Coder v2、PC診断、音声入力、教材パック、Knowledge、Memoryを確認 |
| スマホ幅 `390 × 844` | 合格 | 横はみ出しなし、チャット、設定、PC診断、教材パック、Knowledge、Memoryを確認 |
| Service Worker更新後 | 合格 | 再読込後にチャットと教材パックを再度開き、対象assetと `sw.js` のHTTP 200を確認 |
| Console error | 合格 | error・warningとも0件 |

生成停止は、長文依頼の生成中に停止操作を行い、画面へ `停止しました。` が表示されることまで確認しました。

## 対象外の既存状態

- `127.0.0.1:54876` は `/Applications/TOMOS AI.app` が使用中でした。
- 既存アプリを停止せず、Phase 0 worktreeは空いている `127.0.0.1:54877` で検証しました。
- 音声入力画面にはPyTorch、Cython、packaging、NVIDIA NeMo ASRの不足が表示されます。Phase 0では音声依存を追加せず、既存表示と導線だけを確認しました。

## 承認状態

| 項目 | 状態 |
| --- | --- |
| `segno` の外部取得とユーザーPython領域への導入 | 承認済み・実施済み |
| Phase 0差分のcommit | 承認済み・実施済み |
| push | 未承認 |
| Tauri 2関連crateの取得 | 承認済み |
| Desktop Phase A実装 | ディレクター向け指示を基準に開始 |

## 次のGate

1. 承認済みPhase 0 commitを基準にDesktop Phase A専用worktreeを作成する。
2. `docs/director-tomos-desktop-phase-a-instructions-2026-07-24.ja.md` に従う。
3. `docs/superpowers/plans/2026-07-24-tomos-tauri-desktop-shell.md` を順番どおり実行する。
