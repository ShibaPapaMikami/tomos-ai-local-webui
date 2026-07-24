# TOMOS安全進化マスター Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 現在動いているTOMOSを壊さず、専用デスクトップアプリ、PC適応、低遅延音声、Skill蓄積へ順番に進化させる。

**Architecture:** 現行の `web/` と `server.py` をTauri専用ウィンドウで包み、Model Router、PC診断、ASR、Knowledge、Memory、教材パック、Plugin権限を置き換えず各工程を既存境界へ接続する。共有ファイルを複数工程で同時編集せず、工程ごとに専用worktree、テスト、デスクトップアプリ・ブラウザー・PWA確認、Director Gateを完了してから次へ進む。

**Tech Stack:** Rust、Tauri 2、Python 3.11標準ライブラリ、JavaScript、Node.js既存テスト、SQLite、Ollama、whisper.cpp、既存TOMOS Web UI。

## Global Constraints

- 正本の構想は `docs/tomos-adoption-candidates-research-2026-07-23.ja.md` とする。
- デスクトップアプリの正本設計は `docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md` とする。
- 全体順序と工程の入口はこのファイルを唯一の正本とする。
- 各工程の実装詳細は、このファイルから参照する工程別計画を正本とする。
- 現在の未コミット変更を編集、整形、削除、移動、commit対象へ追加しない。
- 実装開始時は `superpowers:using-git-worktrees` を使い、Directorが指定した基準commitから専用worktreeを作る。
- `main` と `origin/main` のahead/behindは工程開始時に再確認し、自動でrebase、merge、pull、pushしない。
- 依存追加、モデル取得、外部バイナリ実行、外部API、本番変更、公開、commit、pushは事前承認を必須にする。
- Agent-Reach本体、認証、Cookie、SNS、外部書き込みは変更しない。
- モデルを自動削除しない。
- 外部通信は初期OFFまたは実行前確認を必須にする。
- Knowledge、Memory、Skill、Pluginの責務を混ぜない。
- Memory保存は既存の確認経路を通し、ユーザー確認なしで保存しない。
- `gemma4.*` の既存localStorageキーを変更しない。
- 実験モデル、Enterpriseモデル、大人向けモデル、制限を弱めたモデルを自動選択しない。
- Qwen3 4Bを標準AI、取得済みAgentic Coder v2をコード作業、Gemma 4 12Bを任意の高性能・画像AIとして維持する。
- PCの標準画面はTauri専用ウィンドウへ移行し、スマートフォンPWAと問題調査用ブラウザー経路は削除しない。
- `docs/superpowers/plans/2026-07-21-macos-app-launcher.md` のブラウザーを開くTaskは実行しない。
- Tauri PoCはGate 0合格後、Phase 1より前に直列実行する。
- Python同梱、API token、保存移行、署名配布はTauri PoCへ混ぜず、Desktop Phase B以降へ分離する。
- UI文言は日本語を正とし、`DESIGN.md`、`VOICE.md`、`MEMORY.md`、`PLUGIN.md` に従う。
- 1工程につき実装担当は1名とし、同じ工程内でも `server.py`、`web/app.js`、`web/index.html`、`web/sw.js` を複数担当が同時編集しない。
- 各Taskは失敗テスト、最小実装、合格テスト、差分確認の順で進める。
- Commit手順はDirectorが明示承認した場合だけ実行する。未承認時は変更、テスト結果、推奨commit messageをhandoffする。

---

## Source of Truth

| 種別 | 正本 | 用途 |
| --- | --- | --- |
| 構想 | `docs/tomos-adoption-candidates-research-2026-07-23.ja.md` | 何を目指すか |
| 全体順序 | `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md` | どの順で進むか |
| デスクトップアプリ設計 | `docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md` | PC版の完成形と安全境界 |
| Tauri最小Shell | `docs/superpowers/plans/2026-07-24-tomos-tauri-desktop-shell.md` | ブラウザーを開かない最小アプリ |
| 現行モデルルーター | `web/models.js`、`server.py` | モデル選択と分類 |
| PC診断 | `server.py::local_pc_system_info()`、`pc_diagnostics_recommendation()` | 理論診断 |
| 音声入力 | `web/asr.js`、`server.py::run_asr_transcription()` | STT経路 |
| Knowledge | `knowledge_layer.py` | フォルダー別検索 |
| Memory | `context_core.py`、`server.py` の `/api/context/memory/*` | 保存・編集・削除 |
| 教材パック | `web/management.js`、`study_pack_manager.py` | 読み取り用指示パック |
| Plugin権限 | `PLUGIN.md` | 外部アクセスとデータ参照境界 |
| UI | `DESIGN.md` | 表示と操作 |
| 会話 | `VOICE.md` | キャラクターと文章 |

矛盾時の優先順位:

1. `AGENTS.md`
2. ユーザーの最新指示
3. `DESIGN.md`、`VOICE.md`、`MEMORY.md`、`PLUGIN.md`
4. このマスター計画
5. 工程別計画
6. 古いロードマップと過去の計画

工程別計画とこのマスター計画が矛盾した場合は実装を停止し、このマスター計画を先に修正する。

## 現在から完成形への対応表

| 領域 | 現在 | この計画後 | 工程 | 変えないもの |
| --- | --- | --- | --- | --- |
| PCアプリ | `.command`、`.bat`、ランチャーからブラウザーを開く | Tauri専用ウィンドウ、単一起動、owned processだけ終了、署名済みMac/Windows配布 | Desktop A / B / C / D | 既存Web UI、ブラウザーfallback |
| スマートフォン | PWA | PWAを維持 | 全Phase | 390×844の既存操作 |
| モデル選択 | Qwen3 4Bを標準、Agentic Coder v2を開発、Gemma 4 12Bを任意で選べる | 同じ構成を維持し、PC理論値と実測値を選択材料として表示。追加候補は本体外ラボで比較 | Phase 1 / Experiment E | 学生画面の安全な候補、既存保存値 |
| PC診断 | CPU、macOS RAM、Apple Silicon、Ollama、取得済みモデル、RAM 3段階。Windows RAM/GPU/VRAMと実測は未対応 | Windows/Linux RAM、GPU名、ベンダー、VRAMまたは統合メモリ、承認付き短時間ベンチを追加 | Phase 1 | 自動download、自動削除、自動モデル変更をしない |
| 音声入力 | マイク、device選択、Whisper/Nemotron、途中文字起こし、停止 | VAD、発話終了、重複防止、localhost常駐WhisperとCLI fallback | Phase 2 | 既存3経路と手動停止 |
| 音声出力 | TTS実装なし | 初期OFFの共通worker、手動再生、停止、割り込み。候補engineは隔離ラボで比較 | Phase 3 / Experiment V | TTSなしでも動くチャット |
| Skill | 教材パックはあるが汎用Skill版管理はない | SKILL.md、版、development/固定評価、承認履歴、best_skill.md | Phase 4 | 教材パック、学習セット、Knowledge、Memory |
| Knowledge | SQLite検索が動く | 変更しない。Skillからの自動保存を禁止 | 全Phase | フォルダー別検索 |
| Memory | 手動確認付きCRUDが動く | 変更しない。音声とSkillからの自動保存を禁止 | 全Phase | ユーザー確認 |
| Plugin安全性 | `PLUGIN.md` に必須権限項目がある | Skill scopeとPlugin scopeの共通部分だけを将来許可 | Phase 4 | 外部アクセス初期OFFまたは実行前確認 |
| P2P / 会社共有 | 実装なし | Phase 4後も自動着手せず、別設計と承認を要求 | 将来Gate | ローカルデータ境界 |
| VRM / キャラクター | 統合なし | 音声とSkillが安定するまで保留 | 将来Gate | TOMOSを個人AI秘書として見せる方針 |

## 固定する判断

この計画の実行中は次を再選定しない。変更する場合は、実装より先にこのマスター計画と該当工程計画を更新し、Director承認を取る。

1. 標準モデルはQwen3-4B-Instruct-2507。
2. 開発モデルは取得済みAgentic Coder v2。
3. Gemma 4 12Bは任意の高性能・画像枠。
4. PC診断は理論値と実測値を別表示する。
5. STT、LLM、TTSを分離する。
6. TTSの初期状態はOFF、再生は手動。
7. 初期Skill Managerは管理、評価、昇格だけで、通常チャットへ自動適用しない。
8. Skillの固定評価にLLM judgeを使わず、明示した文字列条件で判定する。
9. Memoryへ自動保存しない。
10. PC版はTauri、スマートフォン版はPWAとする。
11. Tauriは既存 `web/` と `server.py` を再利用し、UIを全面的に作り直さない。
12. Desktop AとPhase 1からPhase 4を並行実装しない。

## 進行台帳

| Gate | 入力 | 成果物 | 合格後に許可される工程 | 現在状態 |
| --- | --- | --- | --- | --- |
| Gate 0 | 現在のrepoと既知のテスト不整合 | 全体基準線、ブラウザー基準線 | Desktop Phase A | 合格 |
| Gate A0 | Gate 0合格版と依存承認 | Tauri 2依存の承認記録 | Desktop Phase A実装 | 合格 |
| Gate A | Gate A0承認版 | Tauri専用window、単一起動、runtime所有権 | Phase 1 | 合格 |
| Gate 1 | Gate A合格版 | GPU診断、理論推薦、承認付き実測 | Phase 2 | 合格 |
| Gate 2 | Gate 1合格版 | VAD、確定処理、localhost Whisper fallback | Phase 3 | 停止 |
| Gate 3 | Gate 2合格版 | TTS共通境界、fixture、手動再生 | Phase 4 | 停止 |
| Gate 4 | Gate 3合格版 | Markdown Skill Manager、固定評価、承認昇格 | Experiment E/VまたはDesktop B | 停止 |
| Gate V0 / V1 | Gate 4合格版とcandidate承認 | 隔離音声adapter、実測、人評価 | 音声採用の別計画 | 停止 |
| Gate E0 / E1 | Gate 4合格版とartifact承認 | local-onlyモデル比較結果 | モデル採用の別計画 | 停止 |
| Gate B | Gate 4合格版 | Python同梱、API token、app data移行 | Desktop C | 停止 |
| Gate C | Gate B合格版 | 署名・公証済みMac PKG | Desktop D | 停止 |
| Gate D | Gate C合格版 | 署名済みWindows MSI | PCアプリ正式候補 | 停止 |

台帳の状態は `未着手 | 実装中 | 検証中 | 差し戻し | 合格 | 停止` の6値だけを使う。工程開始時とGate判定時にこの表を更新する。状態変更だけのcommitもDirector承認がない限り作成しない。

## Ownership Boundary

| 工程 | 主担当ファイル | 同時に触らないファイル |
| --- | --- | --- |
| Phase 0 基準線安定化 | `scripts/test-management-helpers.js`、資産テスト | 新機能コード全般 |
| Desktop A Tauri Shell | `src-tauri/**`、`web/desktop-starting.*`、desktop契約テスト | `server.py`、既存Web機能、PWA資産版 |
| Phase 1 PC診断 | `server.py`、`web/settings.js`、診断テスト | `web/asr.js`、Skill実装 |
| Phase 2 音声入力 | `web/asr.js`、ASR部分の`server.py` | PC診断、TTS、Skill実装 |
| Phase 3 TTS | 新規TTSファイル、TTS部分の`server.py`、`web/app.js` | PC診断、ASR内部、Skill実装 |
| Phase 4 Skill Manager | 新規Skillファイル、`web/management.js`、`web/app.js` | Voice、PC診断 |
| Desktop B 製品化 | `src-tauri/**`、runtime packaging、API token、移行adapter | モデル・音声engine採用 |
| Desktop C Mac配布 | Tauri bundle、Mac署名、公証、PKG文書 | Windows配布、機能コード |
| Desktop D Windows配布 | Tauri MSI、Windows署名、移行文書 | Mac配布、機能コード |

共有ファイルを触る工程は必ず直列に実行する。Desktop A、Phase 1からPhase 4、Desktop BからDを並行実装しない。

## Phase Order

```text
Phase 0 基準線安定化
  -> Gate 0 全テスト合格・ブラウザー基準確認
  -> Gate A0 Tauri依存追加承認
  -> Desktop Phase A Tauri最小Shell
  -> Gate A 専用window・単一起動・終了所有権確認
  -> Phase 1 PC診断と実測ベンチ
  -> Gate 1 アプリ/ブラウザーで読み取り専用・承認付きベンチ確認
  -> Phase 2 音声入力のVADと常駐経路
  -> Gate 2 アプリ/PWAでSTT回帰・無音・重複・停止確認
  -> Phase 3 TTS共通基盤と比較PoC
  -> Gate 3 アプリ/PWAで手動再生・停止・割り込み・外部通信確認
  -> Phase 4 Markdown Skill Manager
  -> Gate 4 手動承認・固定評価・Memory非自動保存確認
  -> Director承認時だけ任意で Experiment V または Experiment E
  -> 実験する場合は選んだ実験のGateを閉じる
  -> Desktop Phase B Python同梱・API token・保存移行
  -> Gate B 製品runtimeとデータ境界確認
  -> Desktop Phase C macOS署名・公証・PKG
  -> Gate C Mac新規/移行実機確認
  -> Desktop Phase D Windows署名・MSI
  -> Gate D Windows新規/移行実機確認
  -> 将来Gate P2P / Company Memory / VRMを別設計
```

Experiment E / Vは任意で、Desktop Phase Bの必須条件ではない。実験する場合は1つずつ実行し、Desktop Phase Bと同時に進めない。実験を見送る場合はGate 4からDesktop Phase Bの設計承認へ直接進む。

## PWA資産版の進め方

| 工程 | 新しい版 | この版へ更新する資産 | 以前の版を維持する資産 |
| --- | --- | --- | --- |
| Phase 0 | 変更なし | なし | 全資産 |
| Desktop A | 変更なし | `desktop-starting.html`、`desktop-starting.js` はTauri同梱資産。既存PWA queryは変更しない | 全PWA資産 |
| Phase 1 | `0.8.231-pc-benchmark` | settings、i18n、styles、app、pwa、Service Worker cache | models、asr、management |
| Phase 2 | `0.8.232-asr-vad` | asr、i18n、pwa、Service Worker cache | models、settings、styles、app、management |
| Phase 3 | `0.8.233-tts-boundary` | 新規tts、i18n、styles、app、pwa、Service Worker cache | models、settings、asr、management |
| Phase 4 | `0.8.234-skill-manager` | management、i18n、styles、app、pwa、Service Worker cache | models、settings、asr、tts |

各工程で `scripts/test-pwa-assets.js` に工程専用定数を1つ追加し、更新対象だけをその定数で検証する。過去工程の定数を新しい版へ一括置換しない。`web/index.html`、`web/sw.js`、`web/pwa.js` の3箇所を同じTaskで更新し、Service Worker登録queryとcache名を工程の新しい版へ揃える。

## Phase Plans

### Phase 0: 基準線安定化

正本:

`docs/superpowers/plans/2026-07-23-tomos-baseline-stabilization.md`

完了条件:

- 現在成功しているテストを維持する。
- `node scripts/test-management-helpers.js` の資産版不一致を解消する。
- 資産版の正確性は `scripts/test-pwa-assets.js` が所有し、機能テストへ重複させない。
- PC幅、スマホ幅、Service Worker更新後の表示を確認する。
- 現在の未コミット変更を混ぜない。

現在の状態:

- 基準HEADは `c7b8bb13160c08ccb793586b4ceab218e00a2b6c`。
- 専用worktreeは `.worktrees/phase0-baseline-stabilization`。
- `scripts/test-management-helpers.js` の固定資産版assertは版数非依存へ修正済み。
- Sarashina OCRの正規状態 `needs_runner` を許容する1行修正はDirector承認後に追加済み。
- `segno 1.6.6` はDirector承認後、ユーザーPython 3.14領域へ単体導入済み。
- 全9テスト、JavaScript構文確認5本、Python構文確認、`git diff --check` は合格済み。
- PC幅、スマホ幅、Service Worker再読込後、Console error 0件を確認済み。
- Gate 0記録は `docs/tomos-phase0-gate0-report-2026-07-24.ja.md`。
- Phase 0差分は `478e867e89664f7a8caa9d25d3d5ba098680f806` としてcommit済み。
- Tauri 2関連crateの取得とDesktop Phase A開始はDirector承認済み。
- Desktop Phase Aは `docs/director-tomos-desktop-phase-a-instructions-2026-07-24.ja.md` を実行指示として進行する。

### Desktop Phase A: Tauri最小Shell

正本:

`docs/superpowers/plans/2026-07-24-tomos-tauri-desktop-shell.md`

開始条件:

- Gate 0が合格している。
- Tauri 2、tauri-build 2、tauri-plugin-single-instance 2の取得をDirectorが承認している。
- Gate 0の合格commitを基準に専用worktreeを作成している。

完了条件:

- macOSでブラウザーを開かず `TOMOS AI` 専用windowに既存UIを表示する。
- Tauriは既存 `server.py` を `127.0.0.1:54876` で起動する。
- 二重起動時は既存windowを前面へ戻し、serverを増やさない。
- アプリ終了時はTauriが起動した子プロセスだけを停止する。
- TOMOS以外のポート競合プロセスを停止しない。
- 既存 `.command`、`.bat`、PWA、保存キー、Web機能を変更しない。
- Rust test、desktop契約テスト、既存9テスト、Mac実機確認が合格する。
- bundle、署名、公証、MSI、Python同梱を実行しない。

### Phase 1: PC診断と短時間ベンチ

正本:

`docs/superpowers/plans/2026-07-23-tomos-pc-diagnostics-benchmark.md`

追加開始条件:

- Gate Aが合格している。
- Phase 1の実装担当はブラウザー確認に加え、Tauri appの `1280 × 820` と `960 × 640` を確認する。

完了条件:

- CPU、RAM、GPU名、GPUベンダー、VRAMまたは統合メモリをローカルで診断する。
- 理論推薦と実測結果を別フィールドで返す。
- ベンチマークはユーザーがボタンを押した時だけ動く。
- ベンチマーク対象は取得済みかつ自動選択許可済みモデルだけに限定する。
- モデル取得、削除、外部送信を行わない。
- Windows、Apple Silicon、GPU未検出をそれぞれテストする。

### Phase 2: 音声入力のVADと常駐経路

正本:

`docs/superpowers/plans/2026-07-23-tomos-realtime-voice-input.md`

完了条件:

- 無音区間を送らない。
- 発話終了を検出して確定文字起こしへ進める。
- 暫定文字と確定文字を重複させない。
- 停止操作で録音、途中処理、ネットワークリクエストを終了する。
- Whisperの常駐経路はlocalhost限定で、失敗時は既存CLIへ一度だけ戻る。
- 既存のNemotron、Whisper、ブラウザー音声認識を壊さない。

### Phase 3: TTS共通基盤と比較PoC

正本:

`docs/superpowers/plans/2026-07-23-tomos-tts-engine-boundary.md`

完了条件:

- TTS未導入でもチャットが完全に動く。
- 初期状態は自動読み上げOFF。
- ユーザー操作で読み上げ、停止、再生し直しができる。
- 新しい入力、停止操作、画面遷移で古い音声を破棄する。
- TTS workerはlocalhost・JSON Lines境界で分離する。
- VibeVoiceとQwen3-TTSのモデル取得・依存追加は別承認まで実行しない。
- 音声クローンを初期PoCへ入れない。

### Phase 4: Markdown Skill Manager

正本:

`docs/superpowers/plans/2026-07-23-tomos-markdown-skill-manager.md`

完了条件:

- `SKILL.md` を人間が読む正本にする。
- 教材パック、学習セット、Memory、Pluginを置き換えない。
- Skillの版、使用モデル、成功条件、失敗事例、評価セット、作成者、レビュー者、承認者を記録する。
- 改善用事例と固定評価事例を分ける。
- `best_skill.md` は明示承認時だけ更新する。
- Skill実行結果をMemoryへ自動保存しない。
- 外部通信・書き込み権限は `PLUGIN.md` と同じ境界で確認する。

### Experiment E: モデル比較ラボ

正本:

`docs/superpowers/plans/2026-07-23-tomos-model-evaluation-lab.md`

開始条件:

- Phase 4までの製品基準線が合格している。
- 取得元、revision SHA、license、容量が埋まったartifactだけをDirectorがrow単位で承認する。
- model downloadの空き容量と実行PCを確認している。

完了条件:

- Qwen3基準とGemma 4 12B、E4B、E2B、Ornith 9B候補を同じ20 caseで比較する。
- 公式とUnsloth、GGUF、MLX、QAT、NVFP4を同一結果として混ぜない。
- TOMOS本体、Model Router、学生画面を変更しない。
- 結果を `採用候補 | 実験継続 | 不採用 | 証拠不足` の4値で保存する。
- `採用候補` でも別計画と承認なしに本体へ追加しない。

### Experiment V: 音声engine比較ラボ

正本:

`docs/superpowers/plans/2026-07-23-tomos-voice-engine-evaluation-lab.md`

開始条件:

- Gate 4までの製品工程が合格している。
- Experiment Eと同時実行しない。
- code、model、voice presetのrevision、license、容量をDirectorがcandidate単位で承認する。

完了条件:

- VibeVoice Realtime 0.5B、Qwen3-TTS 0.6B、1.7Bを隔離venvとworkerで比較する。
- 日本語10文、first audio、停止、LLM同時負荷、人評価を同じ条件で記録する。
- VoiceDesign、clone、reference audioを扱わない。
- default engineをoffのまま維持する。
- 結果を `標準音声候補 | オリジナル音声候補 | 実験継続 | 不採用` の4値で保存する。
- 候補になっても別計画と承認なしにinstallerや標準設定へ入れない。

### Desktop Phase B: 製品runtime・API・保存境界

正本設計:

`docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md`

開始条件:

- Gate 4が合格している。
- Experiment EまたはVを実行中でない。
- Python runtime同梱方法、再配布license、容量、macOS/Windowsのbuild方法を別設計書で固定している。
- localhost API tokenと既存ブラウザーfallbackの両立方法を別設計書で固定している。
- localStorage移行の読み取り元、書き込み先、プレビュー、rollbackを別設計書で固定している。
- Desktop Phase B専用の実装計画を作成し、Directorが承認している。

完了条件:

- 利用者へPythonの事前インストールを要求しない。
- app runtimeは署名対象の固定artifactとしてmacOS/Windows別に生成する。
- localhostの状態変更APIは起動ごとのsession token不一致を拒否する。
- Host、Origin、Content-Typeを検証し、localhost以外へ待ち受けない。
- app-managed data directoryを導入し、移行前に件数と対象をプレビューする。
- 移行はユーザー承認後のコピー方式で、元データを削除しない。
- 既存ブラウザーfallbackと `gemma4.*` 互換読込を維持する。
- アプリ終了時はowned processだけを停止する。
- runtime、API、移行、rollbackのMac/Windows自動テストが合格する。

### Desktop Phase C: macOS署名・公証・PKG

引き継ぐ既存条件:

- Bundle IDは `com.shibapapastudio.tomos-ai`。
- PKG identifierは `jp.local.gemma4-12b`。
- app bundleはDeveloper ID Application、PKGはDeveloper ID Installerで署名する。
- `/Applications/Gemma4_12B` を自動削除しない。

開始条件:

- Gate Bが合格している。
- `docs/superpowers/plans/2026-07-21-macos-app-launcher.md` は実行せず、署名・移行条件だけを参照する。
- Tauri app bundle用の新しいMac配布計画を作成し、Directorが承認している。
- 署名、公証、保存済みnotary profileの使用をDirectorが個別承認している。

完了条件:

- `/Applications/TOMOS AI.app` が専用windowを開き、ブラウザーを自動表示しない。
- Developer ID Application、Developer ID Installer、公証Accepted、stapler、Gatekeeperが合格する。
- 新規Mac相当と既存利用者環境で設定、Memory、Knowledge、教材パックを確認する。
- 旧フォルダーと元データをインストーラーが削除しない。
- 公開前の再ダウンロード、SHA-256、署名、公証readback手順がある。
- 公開はDirectorの別承認まで行わない。

### Desktop Phase D: Windows署名・MSI

開始条件:

- Gate Cが合格している。
- Windows code signing証明書、署名方法、WebView2、同梱Pythonの再配布条件を別設計書で固定している。
- 既存 `tools/windows-launcher/Gemma4Launcher.cs` からTauri MSIへ移行する専用計画を作成し、Directorが承認している。
- Windows runnerまたはWindows実機を検証者が利用できる。

完了条件:

- MSIがTauri版 `TOMOS AI` をインストールし、ブラウザーを自動表示しない。
- Windows code signatureをreadbackできる。
- WebView2、Ollama、runtime不足を日本語で案内する。
- 二重起動、owned process停止、ポート競合、アンインストールをWindows実機で確認する。
- アンインストールでモデル、Knowledge、Memory、教材パック、ユーザーデータを削除しない。
- GitHub Releaseへ載せる候補はMac PKGとWindows MSIだけにする。
- 公開はDirectorの別承認まで行わない。

## Deferred Scope

次はPhase 4完了後も自動着手しない。

- AlterSendまたは別P2P基盤の統合
- Company Memory
- 会社内Skill共有
- 企業サーバー接続
- VRM、MMD、表情、モーション
- VibeVoice ASR 7Bの会議録統合
- ZONOS2
- SkillOptによるSkill自動改善
- モデルの自動削除
- Agent-Reach本体変更

着手条件:

1. Phase 0、Desktop A、Phase 1から4、Desktop BからDの全Gateが合格している。
2. 専用の設計書と実装計画がある。
3. データ境界、外部通信、認証、失効、監査ログをDirectorが承認する。

## Global Verification Matrix

各Phase完了時に該当テストだけでなく、次をすべて実行する。

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

Gate A以後は次も追加する。

```bash
python3 scripts/test-desktop-shell-contract.py
cargo test --manifest-path src-tauri/Cargo.toml
node --check web/desktop-starting.js
```

Cargo commandはGate A0で依存追加が承認され、`Cargo.lock` が固定されたworktreeだけで実行する。

期待結果:

- 各テストが成功メッセージを表示して終了コード0。
- `node --check` と `py_compile` が無出力で終了コード0。
- `git diff --check` が無出力で終了コード0。
- `git status` に対象工程以外の新規変更がない。

`scripts/test_server_helpers.py` がsandboxのlocalhost bind制限で失敗した場合は、同じコマンドだけを承認付きで再実行する。`python3 -m unittest scripts.test_server_helpers` は0件実行になるため使用しない。

## Browser Verification Matrix

| 画面 | ブラウザーPC幅 | Tauri app | スマホPWA | 必須確認 |
| --- | --- | --- | --- | --- |
| チャット | 1440×900 | 1280×820 / 960×640 | 390×844 | 送信、停止、モデル表示、入力欄 |
| PC診断 | 1440×900 | 1280×820 / 960×640 | 390×844 | 理論値、実測値、承認ボタン、エラー |
| 音声認識 | 1440×900 | 1280×820 / 960×640 | 390×844 | マイク権限、録音、停止、無音、途中表示、確定 |
| TTS | 1440×900 | 1280×820 / 960×640 | 390×844 | 再生、停止、割り込み、自動再生OFF |
| Skill | 1440×900 | 1280×820 / 960×640 | 390×844 | 一覧、版、評価、承認、無効状態 |
| Knowledge / Memory | 1440×900 | 1280×820 / 960×640 | 390×844 | 新機能からの自動保存がない |

Service Workerを変更した工程では、通常再読込だけでなくキャッシュ更新後の表示を確認する。
Tauri app確認では、ブラウザーが自動表示されないこと、外部リンクがアプリ内画面を置換しないこと、終了時にowned processだけが停止することも確認する。

## Failure and Stop Rules

次の場合は、そのTaskで停止してDirectorへ報告する。

- 基準線テストが実装前から失敗し、原因が対象工程外にある。
- Gate 0未合格のままTauri依存追加が必要になった。
- Tauri、Python runtime、署名tool、WebView2など未承認の依存取得が必要になった。
- shared fileに別担当の未コミット変更があり、同じ行を変更する必要がある。
- モデルID、ライセンス、再配布条件、取得元を確認できない。
- 新しい依存、モデル取得、外部通信、秘密情報が必要になった。
- Memoryへ自動保存しないと機能要件を満たせない。
- localhost以外への待ち受けが必要になった。
- ポート競合を解消するため別プロセスの停止が必要になった。
- Tauri appとPWAの両立に既存Web UIの分岐が必要になった。
- 既存保存キーの変更または移行が必要になった。
- 失敗時に既存経路へ一度だけ戻せない。
- UI仕様がPCとスマホで大きく分岐する。

報告形式:

```text
[工程 / Task]
確認できた事実:
停止理由:
影響する既存機能:
安全に続けられる範囲:
必要な承認:
```

## Rollback Rules

- 各工程は機能フラグまたは未設定時無効で追加する。
- 新しい設定キーは既存キーを置換しない。
- 新しいデータ保存先は `.gemma4-data` 配下の工程専用ディレクトリに分離する。
- Desktop Aは `src-tauri/` を削除すれば既存ブラウザー/PWAへ戻れる状態を維持する。
- Desktop Bの保存移行はコピー方式とし、元データを削除せずrollback可能にする。
- Desktop C/DのアンインストールはユーザーデータとOllamaモデルを削除しない。
- ロールバック時に既存モデル、Knowledge、Memory、教材パックを削除しない。
- Service Worker変更は資産版を1つ進め、旧キャッシュをactivation時に削除する既存方式を維持する。
- TTS worker、Whisper server、ベンチマークはプロセス停止だけで無効化できるようにする。
- Skill Managerは無効化しても `SKILL.md` と評価履歴を削除しない。

## Review Gates

各Gateの担当:

- 実装者: Taskのテスト先行実装と自己確認
- レビュー者: 要件、保存境界、外部通信、既存回帰を確認
- 検証者: 自動テストとPC・スマホ確認
- 承認者: Director。commit、push、モデル取得、依存追加、次Phase開始を承認

Gate報告:

```text
[Vxxx / Phase名]

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
- 次Phase承認

■ 未完了
- 残作業
- 外部確認
```

## Commit Strategy

実装時はTaskごとに次のcommit単位を推奨する。ただし実行はDirector承認後に限る。

```text
test: lock TOMOS baseline asset contracts
test: define TOMOS desktop shell contract
feat: add TOMOS Tauri desktop shell
feat: add hardware-aware local diagnostics
feat: add explicit local model benchmark
feat: add voice activity detection
feat: add optional resident whisper route
feat: add local TTS engine boundary
feat: add manual TTS playback controls
feat: add Markdown skill manager
feat: add reviewed skill promotion
docs: record TOMOS evolution verification
```

## Master Completion Criteria

- Phase 0、Desktop A、Phase 1から4、Desktop BからDの全Gateが合格している。
- PCの標準導線でブラウザーが開かず、Tauri専用windowにTOMOSが表示される。
- スマートフォンPWAと問題調査用ブラウザーfallbackが維持されている。
- アプリ終了時にowned processだけを停止し、ポート競合プロセスを停止しない。
- macOSとWindowsの配布物が署名され、Macは公証も合格している。
- Python runtime、localhost API token、app-managed data migrationがGate Bを通過している。
- 現行Model Router、Knowledge、Memory、教材パック、Plugin権限を再利用している。
- モデル、外部通信、依存、保存、削除にユーザー承認境界がある。
- TTSとSkillを無効にしても既存チャットが動く。
- PC診断の理論値と実測値が混ざっていない。
- 音声入力の暫定文字と確定文字が重複しない。
- Skillが明示承認なしで `best_skill.md` へ昇格しない。
- すべての自動テストとPC・スマホ確認が合格している。
- 未確認事項を完了扱いにしていない。
