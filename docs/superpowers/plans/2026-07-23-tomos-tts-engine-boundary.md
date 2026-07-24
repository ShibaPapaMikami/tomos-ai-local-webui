# TOMOS TTS共通基盤・比較PoC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Complete Gate 2 before starting.

**Goal:** TTSが未導入でもTOMOSを壊さない共通境界を作り、VibeVoice RealtimeとQwen3-TTSを後から安全に比較できるようにする。

**Architecture:** TOMOS本体はengine固有ライブラリをimportせず、JSON Lines workerだけを呼ぶ。Web UIは手動再生を初期値にし、request IDとAbortControllerで古い音声を破棄する。

**Tech Stack:** Python 3.11標準ライブラリ、JSON Lines、Web Audio/HTMLAudioElement、既存TOMOS Web UI。

---

## Initial Scope

実装する:

- TTS status、synthesize、stream、cancelの共通contract
- localhost subprocess worker境界
- 手動の読み上げ、停止、再生し直し
- unavailable時の安全な無効表示
- テスト用fixture worker
- 比較結果を手動記録できるlocal-only表

実装しない:

- VibeVoiceまたはQwen3-TTSの依存取得
- モデルdownload
- 自動読み上げの初期ON
- VoiceDesign
- ボイスクローン
- 許諾音声の登録
- ZONOS2
- 外部TTS API
- 音声のMemory、Knowledge保存

## Public Contract

環境変数:

```text
GEMMA_TTS_ENGINE=off
GEMMA_TTS_WORKER=
GEMMA_TTS_WORKER_PYTHON=
```

`GEMMA_TTS_ENGINE` は `off | vibevoice | qwen3-tts | fixture` の4値だけ。未設定は `off`。

`GET /api/tts/status`:

```json
{
  "ok": true,
  "tts": {
    "enabled": false,
    "engine": "off",
    "ready": false,
    "supportsStreaming": false,
    "supportsCancel": true,
    "reason": "not_configured"
  }
}
```

`POST /api/tts/synthesize`:

```json
{
  "requestId": "tts-1730000000000-1",
  "text": "こんにちは",
  "voice": "default",
  "language": "ja"
}
```

成功response:

```json
{
  "ok": true,
  "requestId": "tts-1730000000000-1",
  "audio": {
    "mimeType": "audio/wav",
    "base64": "UklGRg==",
    "durationMs": 720,
    "sampleRate": 24000
  }
}
```

`POST /api/tts/stream` はsynthesizeと同じrequestを受け、`application/x-ndjson` を返す。

```json
{"type":"start","requestId":"tts-1730000000000-1","mimeType":"audio/pcm;codec=s16le","sampleRate":24000,"channels":1}
{"type":"audio","requestId":"tts-1730000000000-1","sequence":0,"audioBase64":"AAAAAA=="}
{"type":"done","requestId":"tts-1730000000000-1","chunks":1,"durationMs":720}
```

stream規則:

- event typeは `start | audio | done | error`。
- startは最初に1回、doneまたはerrorは最後に1回。
- sequenceは0から1ずつ増える。
- PCMはsigned 16-bit little-endian、mono。
- sampleRateは16000、22050、24000、44100、48000のいずれか。
- 1 chunkのdecode後は最大1 MiB、全chunk合計は最大10 MiB。
- requestId不一致、sequence欠落、上限超過でworkerを停止しerror eventを返す。
- `supportsStreaming=false` のengineへstreamを要求した時はHTTP 409と `tts_streaming_unsupported`。

`POST /api/tts/cancel`:

```json
{
  "requestId": "tts-1730000000000-1"
}
```

成功response:

```json
{
  "ok": true,
  "requestId": "tts-1730000000000-1",
  "cancelled": true
}
```

制限:

- textは1文字以上1000文字以下。
- voiceは `[A-Za-z0-9._-]` の1から64文字。
- languageは `ja | en | auto`。
- non-stream audio MIMEは `audio/wav | audio/mpeg | audio/ogg`。
- decoded audioは最大10 MiB。
- HTTP responseとlogへworker path、stack trace、環境変数を出さない。

## Worker Contract

TOMOSからworkerへ1行:

```json
{"op":"synthesize","requestId":"tts-1730000000000-1","engine":"fixture","text":"こんにちは","voice":"default","language":"ja","stream":false}
```

workerからTOMOSへ1行:

```json
{"ok":true,"requestId":"tts-1730000000000-1","mimeType":"audio/wav","audioBase64":"UklGRg==","durationMs":720,"sampleRate":24000}
```

stream=trueの時はPublic Contractのstart、audio、done eventを1行ずつ返す。

規則:

- stdoutはJSON Lines専用。
- 人向けlogはstderr。
- 1行最大15 MiB。
- requestId不一致のresponseを破棄する。
- worker commandは単一の実在ファイルpathとして検証し、shellで実行しない。
- workerはlocalhost以外をlistenしない。初期実装はlistenせずstdin/stdoutだけを使う。
- 1 synthesisにつき1 worker processとし、cancelはrequestIdに対応するprocessをterminateする。

## Task 1: TTS contract parserをテスト先行で追加する

**Files:**

- Create: `tts_engine.py`
- Create: `scripts/test_tts_engine.py`

- [ ] **Step 1: 失敗テストを作成する**

`scripts/test_tts_engine.py` に次を含める。

```python
from tts_engine import (
    normalize_tts_config,
    validate_tts_request,
    validate_worker_event,
    validate_worker_response,
)


def test_tts_defaults_to_off() -> None:
    config = normalize_tts_config({}, worker_path="")
    assert config["engine"] == "off"
    assert config["enabled"] is False
    assert config["ready"] is False


def test_tts_request_rejects_long_text() -> None:
    result = validate_tts_request({
        "requestId": "tts-1",
        "text": "あ" * 1001,
        "voice": "default",
        "language": "ja",
    })
    assert result["ok"] is False
    assert result["error"] == "tts_text_too_long"


def test_worker_response_rejects_oversized_audio() -> None:
    result = validate_worker_response({
        "ok": True,
        "requestId": "tts-1",
        "mimeType": "audio/wav",
        "audioBase64": "A" * 14_000_004,
        "durationMs": 1,
        "sampleRate": 24000,
    }, expected_request_id="tts-1")
    assert result["ok"] is False


def test_worker_event_rejects_skipped_sequence() -> None:
    result = validate_worker_event({
        "type": "audio",
        "requestId": "tts-1",
        "sequence": 2,
        "audioBase64": "AAAAAA==",
    }, expected_request_id="tts-1", expected_sequence=1)
    assert result["ok"] is False
    assert result["error"] == "tts_stream_sequence_invalid"
```

- [ ] **Step 2: 未実装失敗を確認する**

```bash
python3 scripts/test_tts_engine.py
```

期待結果: `ModuleNotFoundError: No module named 'tts_engine'`。

- [ ] **Step 3: `tts_engine.py` を実装する**

公開関数:

- `normalize_tts_config(env: dict[str, str], worker_path: str) -> dict[str, object]`
- `validate_tts_request(payload: dict[str, object]) -> dict[str, object]`
- `validate_worker_response(payload: dict[str, object], expected_request_id: str) -> dict[str, object]`
- `validate_worker_event(payload: dict[str, object], expected_request_id: str, expected_sequence: int) -> dict[str, object]`
- `run_tts_worker(config: dict[str, object], request: dict[str, object], timeout_seconds: int = 60) -> dict[str, object]`
- `iter_tts_worker_events(config: dict[str, object], request: dict[str, object], timeout_seconds: int = 60)`
- `cancel_tts_request(request_id: str) -> bool`

実装規則:

- Python標準ライブラリだけを使う。
- base64はvalidateしてdecodeサイズを確認する。
- worker pathが実在ファイルでない時はready=false。
- worker Python未設定時は `sys.executable` を使う。
- worker Python設定時は実在する実行可能fileだけを許可し、directory、shell文字列、追加引数を拒否する。
- `subprocess.Popen([worker_python, worker_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)` の引数配列で実行する。
- shellを使わない。
- timeout時はworkerをterminateし、3秒で終了しなければkillする。
- active processはrequestIdをkeyにしたlock保護dictで保持する。
- cancelは対象processだけを終了する。
- textとaudioをlogへ出さない。

- [ ] **Step 4: テストを合格させる**

```bash
python3 scripts/test_tts_engine.py
python3 -m py_compile tts_engine.py
```

期待結果: 終了コード0。

## Task 2: fixture workerとserver APIを追加する

**Files:**

- Create: `scripts/tts_fixture_worker.py`
- Modify: `server.py`
- Modify: `scripts/test_server_helpers.py`
- Test: `scripts/test_tts_engine.py`

- [ ] **Step 1: fixture workerを作る**

fixtureは依存なしで、stream=falseでは44-byte WAV headerと短い無音PCMを返す。stream=trueではstart、2つのaudio、doneを順番に返す。engineが `fixture` 以外ならerrorを返す。外部通信とファイル保存をしない。

- [ ] **Step 2: fixture integration testを追加する**

追加するtest関数名は `test_fixture_worker_round_trip()` とする。

検証内容:

- requestIdが一致する。
- MIMEがaudio/wav。
- base64 decode後が `RIFF` で始まる。
- stream eventがstart、audio sequence 0、audio sequence 1、doneの順になる。
- 10 MiB以下。
- workerが終了コード0。

- [ ] **Step 3: server helper testを追加する**

`scripts/test_server_helpers.py` に次を追加する。

- `tts_status_payload()` は未設定時enabled=false。
- 長文requestはworkerを呼ばずHTTP 400相当payload。
- ready fixtureは成功responseを返す。
- stream非対応engineをHTTP 409で拒否する。
- fixture streamはNDJSONを順番通り返す。
- sequence欠落時はerror eventで終了する。
- requestId不一致を拒否する。
- cancelは対象requestだけに作用する。

- [ ] **Step 4: server APIを実装する**

`server.py` から `tts_engine` をimportし、
`tts_status_payload() -> dict[str, object]`、
`tts_synthesize_payload(payload: dict[str, object]) -> tuple[int, dict[str, object]]`、
`tts_stream_response(handler, payload: dict[str, object]) -> None`、
`tts_cancel_payload(payload: dict[str, object]) -> tuple[int, dict[str, object]]`
を追加する。

route:

- GET `/api/tts/status`
- POST `/api/tts/synthesize`
- POST `/api/tts/stream`
- POST `/api/tts/cancel`

TTSがoffまたはunavailableの時、synthesizeとstreamはHTTP 503と `tts_unavailable`。stream responseは各eventごとにflushする。client切断時は対応workerをterminateする。チャットAPIの状態とresponseは変更しない。

- [ ] **Step 5: Python testを合格させる**

```bash
python3 scripts/test_tts_engine.py
python3 scripts/test_server_helpers.py
python3 -m py_compile tts_engine.py server.py scripts/tts_fixture_worker.py
```

期待結果: 全て終了コード0。

## Task 3: Web TTS controllerをテスト先行で追加する

**Files:**

- Create: `web/tts.js`
- Create: `scripts/test-tts-helpers.js`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/i18n.js`
- Modify: `web/styles.css`
- Modify: `web/pwa.js`
- Modify: `web/sw.js`
- Modify: `scripts/test-pwa-assets.js`

- [ ] **Step 1: controllerの失敗テストを追加する**

`scripts/test-tts-helpers.js` で次を検証する。

```js
assert.equal(normalizeTtsText("  こんにちは\\n\\n世界  "), "こんにちは\n世界");
assert.equal(shouldApplyTtsResult({
  activeRequestId: "tts-2",
  resultRequestId: "tts-1",
  stopped: false,
}), false);
assert.equal(shouldApplyTtsResult({
  activeRequestId: "tts-2",
  resultRequestId: "tts-2",
  stopped: true,
}), false);
assert.equal(defaultTtsSettings().autoPlay, false);
assert.equal(validateTtsStreamEvent({
  type: "audio",
  requestId: "tts-2",
  sequence: 1,
  audioBase64: "AAAAAA==",
}, {
  activeRequestId: "tts-2",
  expectedSequence: 0,
}).ok, false);
```

- [ ] **Step 2: 未実装失敗を確認する**

```bash
node scripts/test-tts-helpers.js
```

期待結果: `ENOENT` または `normalizeTtsText` 未定義。

- [ ] **Step 3: `web/tts.js` を実装する**

export:

```js
window.GEMMA_TTS = {
  createTtsController,
  defaultTtsSettings,
  normalizeTtsText,
  shouldApplyTtsResult,
  validateTtsStreamEvent,
};
```

controller API:

```js
const controller = createTtsController({
  fetchImpl,
  AudioClass,
  AudioContextClass,
  URLImpl,
});
await controller.play({
  requestId,
  text,
  voice,
  language,
  supportsStreaming,
});
controller.stop();
controller.replay();
controller.dispose();
```

規則:

- play開始時に前requestをstopする。
- fetch AbortControllerとAudio objectを1つずつ保持する。
- supportsStreaming=falseではbase64からBlob URLを作る。
- supportsStreaming=trueでは `/api/tts/stream` のresponse readerをTextDecoderで行分割し、NDJSONを1eventずつparseする。
- PCM chunkをInt16ArrayからFloat32Arrayへ変換し、AudioContextのmono AudioBufferへ入れる。
- chunkは `max(audioContext.currentTime + 0.03, nextStartTime)` に順番通りscheduleする。
- streaming replay用chunkは現在のmessage分だけメモリ保持し、次のplayまたはdisposeで破棄する。
- stop/disposeでpause、currentTime=0、abort、scheduled source stop、AudioContext close、revokeObjectURLを行う。
- stop時は `/api/tts/cancel` を同じrequestIdで1回呼び、cancel失敗をチャットerrorにしない。
- requestId不一致またはstop済みresponseを破棄する。
- sequence欠落、decode失敗、10 MiB超で再生を停止する。
- autoplayは行わない。
- audio dataをlocalStorageへ保存しない。

- [ ] **Step 4: UIを接続する**

assistant messageの操作列へ次を追加する。

- `読み上げ`
- `停止`
- 読み上げ完了後の `もう一度`

表示規則:

- status.ready=falseではdisabled。
- status.supportsStreaming=trueならstream、falseならsynthesizeを使う。
- 生成中は同じmessageのbuttonだけdisabled。
- 新しいユーザー送信、音声入力開始、会話停止、画面遷移で `controller.stop()`。
- assistant response確定前にはTTSを呼ばない。
- 自動読み上げ設定は初期OFF。Phase 3ではON toggleを追加しない。

- [ ] **Step 5: 文言を追加する**

key:

```text
chat.ttsPlay
chat.ttsStop
chat.ttsReplay
chat.ttsPreparing
chat.ttsUnavailable
chat.ttsError
settings.ttsTitle
settings.ttsEngine
settings.ttsManualOnly
```

- [ ] **Step 6: Web testと構文を合格させる**

```bash
node scripts/test-tts-helpers.js
node --check web/tts.js
node --check web/app.js
```

期待結果: 終了コード0。

- [ ] **Step 7: PWA資産版を更新する**

`tts.js`、`app.js`、`i18n.js`、`styles.css`、`pwa.js`、`web/sw.js` を `0.8.233-tts-boundary` に揃える。`scripts/test-pwa-assets.js` に `TTS_ASSET_VERSION` を追加し、更新対象だけをこの定数で検証する。models、settings、asr、managementの既存版は変更しない。

```bash
node scripts/test-pwa-assets.js
```

期待結果: 終了コード0。

## Task 4: 比較PoCの記録様式を固定する

**Files:**

- Create: `docs/tts-comparison-protocol.ja.md`
- Create: `docs/tts-comparison-results.ja.md`

- [ ] **Step 1: 比較条件を固定する**

両engineへ同じ10文を使う。

評価項目:

- 最初の音声までのms
- 全体生成時間ms
- real-time factor
- peak RAM
- peak VRAM
- LLM同時実行時のtokens/sec低下率
- 日本語の読み間違い数
- 5段階の自然さ
- 停止から無音までのms
- Windows CPUのみ、Windows GPU、Apple Siliconの成否

- [ ] **Step 2: 合格基準を固定する**

標準音声候補の合格条件:

- 最初の音声まで1500ms以下。
- 停止から無音まで300ms以下。
- 10文中の読み間違い2件以下。
- LLM同時実行時のtokens/sec低下率40%以下。
- Windowsで外部APIなしに動作。

オリジナル音声候補の合格条件:

- 最初の音声まで2500ms以下。
- 停止から無音まで300ms以下。
- 10文中の読み間違い2件以下。
- 許諾のない音声を使わない。

- [ ] **Step 3: 実engine導入Gateを明記する**

VibeVoiceまたはQwen3-TTSを実際に取得する前にDirectorへ次を提示する。

```text
取得元:
commitまたはrelease:
license:
model license:
download size:
追加依存:
対応OS:
外部通信:
削除方法:
```

全項目が埋まり、依存追加とモデル取得が承認されるまでfixture以外を実行しない。

## Task 5: 回帰とブラウザー確認を行う

- [ ] **Step 1: マスター計画のGlobal Verification Matrixへ次を追加して全実行する**

```bash
node scripts/test-tts-helpers.js
python3 scripts/test_tts_engine.py
node --check web/tts.js
python3 -m py_compile tts_engine.py scripts/tts_fixture_worker.py
```

- [ ] **Step 2: TTS offで確認する**

- チャット送信、停止、履歴が通常通り動く。
- 読み上げbuttonはdisabled。
- Console errorなし。
- TTS API failureがチャットerrorにならない。

- [ ] **Step 3: fixtureで確認する**

- 1messageを手動再生できる。
- fixture streamではdoneを待たず最初のaudio chunkから再生が始まる。
- 停止できる。
- もう一度再生できる。
- 新しい入力で古い音が止まる。
- 読み上げ中にマイクを開始すると古い音が止まり、音声入力が始まる。
- 連打しても同時再生しない。
- 画面遷移で止まる。

- [ ] **Step 4: PC幅とスマホ幅で確認する**

1440×900と390×844でbuttonがmessage本文を隠さず、横方向へはみ出さない。

- [ ] **Step 5: Tauri appで再生と終了を確認する**

`1280 × 820` と `960 × 640` でplay、stop、replay、マイク開始時interruptを確認する。app終了時にaudio、worker、requestが残らず、TTS engine未導入でもappが終了できることを確認する。

## Gate 3

合格条件:

- TTS offで既存チャットが完全に動く。
- fixtureのplay、stop、replay、interrupt、stale破棄が合格。
- streaming fixtureのevent順、chunk早期再生、sequence検証、上限検証が合格。
- 自動読み上げOFF。
- stdout JSON Lines、stderr logの境界が維持される。
- audio、text、voiceがMemory、Knowledge、localStorageへ保存されない。
- 実engine依存とモデルの追加が0件。
- Tauri appでplay、stop、interrupt、終了cleanupが合格。

推奨commit message:

```text
feat: add opt-in local TTS worker boundary
```

Directorがcommitと次Phaseを承認した後だけ、`2026-07-23-tomos-markdown-skill-manager.md` へ進む。
