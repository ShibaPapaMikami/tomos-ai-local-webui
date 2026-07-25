# TOMOSリアルタイム音声入力 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Complete Gate 1 before starting.

**Goal:** 現在の音声入力へ無音判定、発話終了、重複防止、localhost常駐Whisper経路を追加し、会話開始までの待ち時間を短くする。

**Architecture:** ブラウザーの音量判定は純粋な状態遷移として実装し、録音制御から分離する。STT backendは既存CLIを残し、設定済みlocalhost serverを第一候補、失敗時のCLI fallbackを1回だけ許可する。

**Tech Stack:** Web Audio API、MediaRecorder、JavaScript、Python 3.11、既存whisper.cpp経路。

---

## Safety Contract

- マイクはユーザーが音声ボタンを押した時だけ開始する。
- 録音データをMemory、Knowledge、ログ、ファイルへ自動保存しない。
- 常駐Whisper URLは `localhost`、`127.0.0.1`、`::1` だけ許可する。
- 常駐serverをTOMOSから自動インストール、自動起動、自動更新しない。
- 常駐server失敗時の既存CLI fallbackは1requestにつき1回だけ。
- 既存Nemotron、Whisper CLI、ブラウザーSpeechRecognitionを残す。
- 停止後に完了した古いresponseを入力欄へ反映しない。
- 外部音声APIを追加しない。

## State Contract

VADのstate:

```js
{
  phase: "idle",
  candidateStartedAtMs: null,
  speechStartedAtMs: null,
  lastAudibleAtMs: null,
}
```

`phase` は `idle | candidate | speaking` の3値だけ。

VADの戻り値:

```js
{
  state,
  action: "none",
}
```

`action` は `none | speech-start | speech-finalize` の3値だけ。

固定初期値:

```js
{
  minRms: 0.003,
  minPeak: 0.01,
  minSpeechMs: 180,
  silenceToFinalizeMs: 650,
}
```

設定画面で閾値を変更する機能はこのPhaseへ入れない。

## Task 1: VAD状態遷移をテスト先行で追加する

**Files:**

- Modify: `web/asr.js:760-850`
- Test: `scripts/test-asr-helpers.js`

- [ ] **Step 1: 失敗テストを追加する**

`scripts/test-asr-helpers.js` から `voiceActivityState` を読み、次を検証する。

```js
let vad = {
  phase: "idle",
  candidateStartedAtMs: null,
  speechStartedAtMs: null,
  lastAudibleAtMs: null,
};

let result = voiceActivityState({
  state: vad,
  nowMs: 0,
  rms: 0.02,
  peak: 0.08,
});
assert.equal(result.state.phase, "candidate");
assert.equal(result.action, "none");

result = voiceActivityState({
  state: result.state,
  nowMs: 200,
  rms: 0.02,
  peak: 0.08,
});
assert.equal(result.state.phase, "speaking");
assert.equal(result.action, "speech-start");

result = voiceActivityState({
  state: result.state,
  nowMs: 900,
  rms: 0,
  peak: 0,
});
assert.equal(result.action, "speech-finalize");
assert.equal(result.state.phase, "idle");
```

追加で次を検証する。

- 100msだけの音はspeech-startにならない。
- speaking中の短い300ms無音はfinalizeしない。
- stop後にidleへ戻せる。
- `NaN`、負数、空sampleは無音として扱う。

- [ ] **Step 2: 未実装失敗を確認する**

```bash
node scripts/test-asr-helpers.js
```

期待結果: `voiceActivityState is not a function`。

- [ ] **Step 3: 純粋関数を実装する**

`web/asr.js` に `voiceActivityState({ state, nowMs, rms, peak,
minRms = 0.003, minPeak = 0.01, minSpeechMs = 180,
silenceToFinalizeMs = 650 })` を追加し、`window.GEMMA_ASR` からexportする。

遷移規則:

1. RMSまたはpeakが閾値以上ならaudible。
2. idleでaudibleならcandidateへ進み時刻を保存する。
3. candidateが `minSpeechMs` 継続したらspeakingへ進み `speech-start`。
4. candidate中に無音へ戻ったらidle。
5. speaking中のaudibleは `lastAudibleAtMs` を更新する。
6. speaking中の無音が `silenceToFinalizeMs` 以上ならidleへ戻し `speech-finalize`。
7. state objectを直接変更せず、新しいobjectを返す。

- [ ] **Step 4: helper testを合格させる**

```bash
node scripts/test-asr-helpers.js
node --check web/asr.js
```

期待結果: 両方終了コード0。

## Task 2: 録音へVADと確定処理を接続する

**Files:**

- Modify: `web/asr.js:550-750`
- Modify: `web/asr.js:807-1005`
- Test: `scripts/test-asr-helpers.js`

- [ ] **Step 1: session世代と重複防止の失敗テストを追加する**

次のpure helperを先にテストする。

```js
const merged = mergeAsrTranscript({
  baseText: "明日の",
  partialText: "予定を",
  finalText: "予定を教えて",
});
assert.equal(merged, "明日の 予定を教えて");

assert.equal(
  shouldApplyAsrResult({ activeSessionId: 4, resultSessionId: 3, stopped: false }),
  false,
);
assert.equal(
  shouldApplyAsrResult({ activeSessionId: 4, resultSessionId: 4, stopped: true }),
  false,
);
```

- [ ] **Step 2: 未実装失敗を確認する**

```bash
node scripts/test-asr-helpers.js
```

期待結果: `mergeAsrTranscript` が未定義で失敗。

- [ ] **Step 3: 純粋helperを実装する**

`mergeAsrTranscript({ baseText, partialText, finalText })` と
`shouldApplyAsrResult({ activeSessionId, resultSessionId, stopped })` を追加し、
両方を `window.GEMMA_ASR` からexportする。

規則:

- 確定時はpartialを捨て、base + finalを1回だけ使う。
- 空白は既存の`mergeTranscript`規則へ合わせる。
- session不一致またはstop済みならfalse。

- [ ] **Step 4: `createWavPartialCapture()` へVADを接続する**

変更内容:

- 既存 `hasAudibleSignal()` は低レベル判定として残す。
- AudioContextから各chunkのRMSとpeakを計算する。
- `voiceActivityState()` へ時刻と値を渡す。
- `speech-start` まではSTT requestを送らない。
- speaking中だけ既存partial送信を行う。
- `speech-finalize` で録音captureだけを停止し、最後のWAVを1回送信する。
- 自動finalizeではfinal requestをabortせず、response反映後にsessionを終了する。
- 無音開始から650msで確定する。
- 最大録音時間の既存上限は残す。

- [ ] **Step 5: 停止処理を一本化する**

1sessionごとに次を保持する。

```js
{
  id,
  stopped,
  finalizing,
  mediaRecorder,
  mediaStream,
  audioContext,
  partialAbortController,
  finalAbortController,
  timers,
}
```

`stopVoiceCapture(session)` と `cancelVoiceSession(session)` を分ける。

`stopVoiceCapture()` はMediaRecorder、track、AudioContext、timerだけを終了し、final requestはabortしない。VADの自動finalizeだけが使う。

`cancelVoiceSession()` を `activeVoiceStop()` から呼ぶ。これは冪等にし、2回呼んでも例外を出さない。ユーザー停止時は次を全て行う。

1. `stopped=true`
2. `stopVoiceCapture(session)`
3. partial/final AbortController abort
4. 入力欄のpartial表示をbase textへ戻す
5. `activeVoiceStop=null`

自動finalize完了時はfinal responseをsession IDで検証し、入力欄へ1回反映してから `activeVoiceStop=null` にする。途中でユーザー停止された場合は反映しない。

- [ ] **Step 6: helper testと構文を合格させる**

```bash
node scripts/test-asr-helpers.js
node --check web/asr.js
```

期待結果: 終了コード0。

## Task 3: localhost常駐Whisper経路を追加する

**Files:**

- Modify: `server.py` のASR設定と `run_asr_transcription()`
- Test: `scripts/test_server_helpers.py`
- Modify: `docs/asr-roadmap.ja.md`

- [ ] **Step 1: localhost制限の失敗テストを追加する**

```python
def test_normalize_local_whisper_server_url() -> None:
    assert server.normalize_local_whisper_server_url("http://127.0.0.1:8178") == "http://127.0.0.1:8178"
    assert server.normalize_local_whisper_server_url("http://localhost:8178/") == "http://localhost:8178"
    assert server.normalize_local_whisper_server_url("https://example.com") == ""
    assert server.normalize_local_whisper_server_url("http://192.168.1.5:8178") == ""
```

- [ ] **Step 2: fallback回数の失敗テストを追加する**

既存fixtureに合わせ、次の呼び出し順を検証する。

```python
calls = []

def fail_server(*args, **kwargs):
    calls.append("server")
    raise RuntimeError("resident unavailable")

def succeed_cli(*args, **kwargs):
    calls.append("cli")
    return {"ok": True, "text": "こんにちは", "engine": "whisper.cpp"}
```

`run_asr_transcription()` の結果が成功し、`calls == ["server", "cli"]` であること。server再試行やCLI再試行がないこと。

- [ ] **Step 3: 未実装失敗を確認する**

```bash
python3 scripts/test_server_helpers.py
```

期待結果: `normalize_local_whisper_server_url` が未定義で失敗。

- [ ] **Step 4: URL検証を実装する**

環境変数:

```text
GEMMA_WHISPER_SERVER_URL
```

規則:

- schemeはhttpだけ。
- hostnameは `localhost`、`127.0.0.1`、`::1` だけ。
- username、password、query、fragmentを拒否する。
- 未設定または拒否時は空文字。

- [ ] **Step 5: resident requestを実装する**

`run_whisper_server_transcription(wav_bytes: bytes, language: str,
server_url: str) -> dict[str, object]` を追加する。

request:

- `POST {server_url}/inference`
- multipart field名 `file`
- filename `speech.wav`
- languageが空でなければfield `language`
- timeout 30秒

responseから文字列 `text` を読み、次を返す。

```json
{
  "ok": true,
  "text": "こんにちは",
  "engine": "whisper-server"
}
```

録音内容、response全文、ローカルパスをlogへ出さない。

- [ ] **Step 6: `run_asr_transcription()` の順序を変更する**

1. `GEMMA_WHISPER_SERVER_URL` が有効ならresidentを1回呼ぶ。
2. 成功なら返す。
3. 失敗なら既存Whisper CLIを1回呼ぶ。
4. CLIも失敗した時だけ既存errorを返す。
5. URL未設定時は現行CLIだけを呼ぶ。

NemotronとブラウザーSpeechRecognitionの選択規則は変更しない。

- [ ] **Step 7: server testを合格させる**

```bash
python3 scripts/test_server_helpers.py
python3 -m py_compile server.py
```

期待結果: 終了コード0。

- [ ] **Step 8: ロードマップを更新する**

`docs/asr-roadmap.ja.md` の項目21から25を次の状態で記録する。

- VADと発話終了: 実装済み
- 暫定・確定重複防止: 実装済み
- localhost常駐Whisper接続: 実装済み
- 常駐server自動起動: 未実装・別承認
- 長時間会議ASR: 未実装・将来枠

## Task 4: UI文言とPWA資産版を更新する

**Files:**

- Modify: `web/i18n.js`
- Modify: `web/index.html`
- Modify: `web/pwa.js`
- Modify: `web/sw.js`
- Modify: `scripts/test-pwa-assets.js`

- [ ] **Step 1: 状態文言を追加する**

追加key:

```text
composer.voiceWaitingForSpeech
composer.voiceSpeechDetected
composer.voiceFinalizing
composer.voiceStopped
composer.voiceResidentFallback
```

通常ユーザーへengine名や内部fallbackを強調しない。設定診断だけでresident/CLIの使用経路を確認できるようにする。

- [ ] **Step 2: 資産版を揃える**

`asr.js`、`i18n.js`、`pwa.js`、`web/sw.js` の対応値を `0.8.232-asr-vad` に揃える。`scripts/test-pwa-assets.js` に `VOICE_INPUT_ASSET_VERSION` を追加し、更新対象だけをこの定数で検証する。models、settings、styles、app、managementの既存版は変更しない。

- [ ] **Step 3: 資産testを合格させる**

```bash
node scripts/test-pwa-assets.js
```

期待結果: 終了コード0。

## Task 5: 回帰と実機確認を行う

- [ ] **Step 1: マスター計画のGlobal Verification Matrixを全実行する**

期待結果: 全コマンド終了コード0。

- [ ] **Step 2: PC幅とスマホ幅で次のケースを確認する**

| ケース | 期待結果 |
| --- | --- |
| 3秒無音 | STT request 0回、入力欄変更なし |
| 100msの環境音 | 発話開始にならない |
| 1秒発話後650ms無音 | 確定処理1回 |
| 発話中300ms無音 | 録音継続 |
| partial後final | 同じ語句が重複しない |
| 録音中に停止 | track、timer、requestが終了 |
| 停止後に古いresponse到着 | 入力欄へ反映しない |
| resident成功 | CLIを呼ばない |
| resident失敗 | CLIを1回だけ呼ぶ |
| server URLがLAN IP | 設定拒否、CLI継続 |

- [ ] **Step 3: 既存3経路を確認する**

- Nemotron設定時の録音。
- Whisper CLI設定時の録音。
- ブラウザーSpeechRecognition設定時の録音。

- [ ] **Step 4: Tauri appでマイク権限と停止を確認する**

`1280 × 820` と `960 × 640` で初回マイク許可、拒否後の案内、録音、VAD、停止、再許可を確認する。app終了後に録音track、timer、requestが残らないことを確認する。

## Gate 2

合格条件:

- 無音、短音、発話終了、重複、停止、stale responseの全testが合格。
- resident URLはlocalhost限定。
- fallbackは1回だけ。
- 音声データのMemory、Knowledge、永続ファイル保存が0件。
- 既存3経路が回帰していない。
- PC幅1440×900、Tauri app 1280×820 / 960×640、スマホ幅390×844が合格。

推奨commit message:

```text
feat: add voice activity finalization and local whisper fallback
```

Directorがcommitと次Phaseを承認した後だけ、`2026-07-23-tomos-tts-engine-boundary.md` へ進む。
