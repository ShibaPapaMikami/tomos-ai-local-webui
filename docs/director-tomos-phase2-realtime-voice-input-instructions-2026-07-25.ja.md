# ディレクター向け実行指示: TOMOS Phase 2 リアルタイム音声入力

## 件名

Gate 1合格版を基準に、VAD、発話終了、重複防止、localhost常駐Whisper経路を実装する。

## 現在地

- Gate 1: 合格
- 基準HEAD: `016c52d352b544c04b319418941a36330e990771`
- 基準branch: `codex/phase1-pc-diagnostics`
- Phase 2 branch: `codex/phase2-realtime-voice-input`
- Phase 2 worktree: `.worktrees/phase2-realtime-voice-input`
- 依存追加、外部音声API、Whisper server自動起動、モデル取得・削除、commit、push、配布: 未承認

## ディレクターの指示

エンジニアは次の正本を順番どおり読み、Phase 2だけを実装してください。

1. `AGENTS.md`
2. `DESIGN.md`
3. `VOICE.md`
4. `MEMORY.md`
5. `PLUGIN.md`
6. `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
7. `docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md`
8. `docs/superpowers/plans/2026-07-23-tomos-realtime-voice-input.md`

## 実装対象

- `web/asr.js`
- `scripts/test-asr-helpers.js`
- `server.py`
- `scripts/test_server_helpers.py`
- `web/i18n.js`
- `web/index.html`
- `web/pwa.js`
- `web/sw.js`
- `scripts/test-pwa-assets.js`
- `docs/asr-roadmap.ja.md`
- Phase 2の指示書、進行台帳、Gate報告

## 実装しないもの

- 新しい依存、外部音声API、クラウドSTT
- Whisper serverの自動インストール、自動起動、自動更新
- 音声データ、暫定文、確定文のMemory・Knowledge・ログ・永続ファイル保存
- 既存Nemotron、Whisper CLI、ブラウザーSpeechRecognitionの削除
- 音声の自動送信、TTS、Skill、Agent-Reachの変更
- commit、push、配布、署名、公証

## 必須の進め方

1. Gate 1 commitから専用worktreeを作り、既存テストを先に通す。
2. VAD純粋関数の失敗テストを作り、未実装失敗を確認してから実装する。
3. session世代、停止、重複防止の失敗テストを作ってから録音制御へ接続する。
4. localhost URL制限と1回fallbackの失敗テストを作ってから常駐Whisper経路を追加する。
5. 常駐Whisperへ渡す内容は、既存変換処理で生成した実際のWAV bytesにする。
6. 自動finalizeは録音captureだけを停止し、final requestを中断しない。
7. ユーザー停止はcapture、track、timer、partial/final requestを冪等に停止する。
8. 停止後または古いsessionのresponseを入力欄へ反映しない。
9. UIとPWA資産版を `0.8.232-asr-vad` に揃え、既存版を不要に変更しない。
10. Gate 2判定後もcommitせず、Director承認を待つ。

## Gate 2の合格条件

- 無音、100ms短音、発話開始、300ms短無音、650ms発話終了の状態遷移が合格する。
- partial後のfinalで語句が重複しない。
- ユーザー停止後と古いsessionのresponseが反映されない。
- 常駐Whisper URLはHTTPのlocalhost、127.0.0.1、::1だけを許可する。
- 常駐Whisper失敗時のCLI fallbackは1requestにつき1回だけである。
- 音声の永続保存、外部送信、自動送信、自動インストールが0件である。
- Nemotron、Whisper CLI、ブラウザーSpeechRecognitionの既存経路が合格する。
- 1440×900、1280×820、960×640、390×844で操作と状態表示が確認できる。

## 停止条件

- 新しい依存または外部音声APIが必要になる。
- localhost以外への音声送信が必要になる。
- モデル取得・削除、保存形式変更、Tauri runtime変更が必要になる。
- 既存3経路のいずれかを削除しないと実装できない。
- 別プロセスを停止しないと検証できない。

停止時は回避実装を追加せず、原因、影響範囲、最小の選択肢をDirectorへ報告してください。

## 報告形式

```text
[Phase 2 / Gate 2]
基準HEAD:
変更ファイル:
依存追加:
VAD tests:
session tests:
resident tests:
既存tests:
Mac実機:
PC幅:
スマホ幅:
既存3経路:
保存・外部送信:
未完了:
```

空欄を残さず、`合格`、`不合格`、または実際の制約を記入してください。
