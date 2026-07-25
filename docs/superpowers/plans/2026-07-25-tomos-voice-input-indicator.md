# TOMOS Voice Input Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 会話欄へ入力音量に連動する5段階メーターと状態文を追加し、マイク入力・声判定・確定処理をユーザーが区別できるようにする。

**Architecture:** 既存VADが算出するRMS、peak、phaseから表示レベルを返す純粋関数を`web/asr.js`へ追加する。録音処理は最大10回/秒の`onAudioLevel` callbackだけをUIへ渡し、`composer-status`の文字とCSS変数を更新する。音声値は保存せず、VAD閾値とASR経路も変更しない。

**Tech Stack:** JavaScript、Web Audio API、既存TOMOS ASR helper tests、CSS、Tauri WebView。

## Global Constraints

- 表示レベルは整数 `0 | 1 | 2 | 3 | 4` だけ。
- VAD開始条件はRMS 0.003またはpeak 0.01のまま変更しない。
- 強い入力の表示境界はRMS 0.012またはpeak 0.04。
- 表示更新は最大10回/秒。
- 通常画面に数値パーセントを表示しない。
- 音声chunk、RMS、peak、最大値をMemory、Knowledge、localStorage、ログ、ファイルへ保存しない。
- 停止後またはsession ID不一致の更新を表示しない。
- 依存関係を追加しない。
- 既存の未コミットPhase 2変更を戻さない。

---

### Task 1: 入力レベルを求める純粋関数

**Files:**

- Modify: `web/asr.js`
- Test: `scripts/test-asr-helpers.js`

**Interfaces:**

- Consumes: `rms: number`、`peak: number`、`phase: "idle" | "candidate" | "speaking"`
- Produces: `voiceSignalLevel({ rms, peak, phase }): 0 | 1 | 2 | 3 | 4`

- [ ] **Step 1: failing testを追加する**

`scripts/test-asr-helpers.js`の`window.GEMMA_ASR`分割代入へ
`voiceSignalLevel`を加え、既存`voiceActivityState` testの直前へ次を追加する。

```js
assert.equal(voiceSignalLevel({ rms: 0, peak: 0, phase: "idle" }), 0);
assert.equal(voiceSignalLevel({ rms: 0.0015, peak: 0.005, phase: "idle" }), 1);
assert.equal(voiceSignalLevel({ rms: 0.003, peak: 0.01, phase: "candidate" }), 2);
assert.equal(voiceSignalLevel({ rms: 0.004, peak: 0.015, phase: "speaking" }), 3);
assert.equal(voiceSignalLevel({ rms: 0.012, peak: 0.04, phase: "speaking" }), 4);
assert.equal(voiceSignalLevel({ rms: Number.NaN, peak: -1, phase: "bad" }), 0);
```

- [ ] **Step 2: 未実装失敗を確認する**

Run:

```bash
node scripts/test-asr-helpers.js
```

Expected: `voiceSignalLevel is not a function`で終了コード1。

- [ ] **Step 3: 最小実装を追加する**

`web/asr.js`の`audioSignalStats()`直後へ追加する。

```js
function voiceSignalLevel({ rms = 0, peak = 0, phase = "idle" } = {}) {
  const safeRms = Number.isFinite(Number(rms)) && Number(rms) > 0 ? Number(rms) : 0;
  const safePeak = Number.isFinite(Number(peak)) && Number(peak) > 0 ? Number(peak) : 0;
  const safePhase = ["idle", "candidate", "speaking"].includes(phase) ? phase : "idle";
  if (safePhase === "speaking" && (safeRms >= 0.012 || safePeak >= 0.04)) return 4;
  if (safePhase === "speaking") return 3;
  if (safePhase === "candidate") return 2;
  if (safeRms >= 0.001 || safePeak >= 0.004) return 1;
  return 0;
}
```

`window.GEMMA_ASR` exportへ`voiceSignalLevel`を追加する。

- [ ] **Step 4: helper testと構文を確認する**

Run:

```bash
node scripts/test-asr-helpers.js
node --check web/asr.js
```

Expected: 両方終了コード0。

- [ ] **Step 5: 差分を確認する**

Run:

```bash
git diff --check -- web/asr.js scripts/test-asr-helpers.js
git diff -- web/asr.js scripts/test-asr-helpers.js
```

Expected: 空白エラー0件。Phase 2の既存差分が保持されている。

- [ ] **Step 6: helperと既存VADをcommitする**

```bash
git add web/asr.js scripts/test-asr-helpers.js
git commit -m "feat: add voice activity finalization and signal levels"
```

Expected: Task 1と同じファイルにある承認済みPhase 2 VAD差分を含めてcommit成功。

### Task 2: 録音処理から安全に表示値を渡す

**Files:**

- Modify: `web/asr.js`
- Test: `scripts/test-asr-helpers.js`

**Interfaces:**

- Consumes: Task 1の`voiceSignalLevel()`
- Produces: `onAudioLevel({ level, rms, peak, phase }): void`
- Produces: `renderAsrStatus({ els, t, status, seconds, message, signalLevel })`

- [ ] **Step 1: callbackとstale破棄のfailing testを追加する**

既存`createWavPartialCapture()` testへ次の観測配列を加える。

```js
const signalUpdates = [];
```

capture生成引数へ追加する。

```js
onAudioLevel: (value) => signalUpdates.push(value),
```

無音chunk、candidate chunk、200ms後のspeaking chunkを既存fake processorへ渡した後に確認する。

```js
assert.equal(signalUpdates.at(0).level, 0);
assert.equal(signalUpdates.some((item) => item.level === 2), true);
assert.equal(signalUpdates.some((item) => item.level === 3), true);
assert.equal(signalUpdates.every((item) => (
  Number.isFinite(item.rms)
  && Number.isFinite(item.peak)
  && ["idle", "candidate", "speaking"].includes(item.phase)
)), true);
```

100ms未満に10chunkを渡すtestでは、`signalUpdates.length <= 2`を確認する。

- [ ] **Step 2: callback未実装失敗を確認する**

Run:

```bash
node scripts/test-asr-helpers.js
```

Expected: `signalUpdates`が空のため終了コード1。

- [ ] **Step 3: `createWavPartialCapture()`へcallbackを追加する**

引数へ追加する。

```js
onAudioLevel,
```

内部状態へ追加する。

```js
let lastAudioLevelAtMs = Number.NEGATIVE_INFINITY;
```

`processor.onaudioprocess`でVAD遷移を求めた直後に追加する。

```js
const signalLevel = voiceSignalLevel({
  rms: stats.rms,
  peak: stats.peak,
  phase: vadState.phase,
});
if (
  typeof onAudioLevel === "function"
  && (
    currentNow - lastAudioLevelAtMs >= 100
    || transition.action !== "none"
    || previousPhase !== vadState.phase
  )
) {
  lastAudioLevelAtMs = currentNow;
  onAudioLevel({
    level: signalLevel,
    rms: stats.rms,
    peak: stats.peak,
    phase: vadState.phase,
  });
}
```

このblockで使う時刻は、VAD呼び出し前に`const currentNow = now();`として1回だけ取得する。

- [ ] **Step 4: `recordAudio()`から会話UIへ接続する**

`recordAudio()`引数へ`onAudioLevel`を追加し、
`createWavPartialCapture()`へ同名callbackを渡す。

`handleVoiceInputClick()`のsessionへ追加する。

```js
lastSignalLevel: 0,
lastSignalStatus: "waiting",
```

`recorder()`引数へ追加する。

```js
onAudioLevel: ({ level, phase }) => {
  if (
    session.stopped
    || session.finalizing
    || activeVoiceSession?.id !== session.id
  ) return;
  session.lastSignalLevel = level;
  session.lastSignalStatus = phase === "candidate" || phase === "speaking"
    ? "speech"
    : (level > 0 ? "input" : "waiting");
  renderAsrStatus({
    els,
    t,
    status: session.lastSignalStatus,
    signalLevel: level,
  });
},
```

既存`onTick`は`session.lastSignalStatus`と`session.lastSignalLevel`を使い、
1秒tickで表示を`waiting`へ戻さない。

- [ ] **Step 5: 停止時の片付けを追加する**

`cancelVoiceSession()`、`completeVoiceSession()`、error表示では
`signalLevel: null`を渡す。停止後のcallbackはStep 4のsession条件で破棄する。

- [ ] **Step 6: helper testと構文を確認する**

Run:

```bash
node scripts/test-asr-helpers.js
node --check web/asr.js
```

Expected: 両方終了コード0。

- [ ] **Step 7: callback接続をcommitする**

```bash
git add web/asr.js scripts/test-asr-helpers.js
git commit -m "feat: connect live voice input feedback"
```

Expected: Task 2差分だけを追加commit。

### Task 3: 5段階メーターと状態文を表示する

**Files:**

- Modify: `web/asr.js`
- Modify: `web/i18n.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Modify: `web/pwa.js`
- Modify: `web/sw.js`
- Modify: `scripts/test-asr-helpers.js`
- Modify: `scripts/test-pwa-assets.js`
- Modify: `scripts/test-model-selection.js`

**Interfaces:**

- Consumes: Task 2の`signalLevel`
- Produces: `composer-status[data-voice-level="0"..."4"]`
- Produces: i18n key `composer.voiceInputDetected`

- [ ] **Step 1: 表示契約のfailing testを追加する**

`scripts/test-asr-helpers.js`へ追加する。

```js
const signalStatus = fakeComposerStatus();
renderAsrStatus({
  els: { composerStatus: signalStatus, voiceInput: fakeVoiceButton() },
  t: (key) => key,
  status: "input",
  signalLevel: 1,
});
assert.equal(signalStatus.textContent, "composer.voiceInputDetected");
assert.equal(signalStatus.dataset.voiceLevel, "1");
```

停止表示testへ次を追加する。

```js
assert.equal("voiceLevel" in signalStatus.dataset, false);
```

`scripts/test-pwa-assets.js`の音声入力資産版を
`0.8.232-asr-vad.3`へ変更する。

- [ ] **Step 2: 未実装失敗を確認する**

Run:

```bash
node scripts/test-asr-helpers.js
node scripts/test-pwa-assets.js
```

Expected: 新しい`input`表示または資産版不一致で終了コード1。

- [ ] **Step 3: 状態文とdatasetを実装する**

`web/i18n.js`へ追加する。

```js
"composer.voiceInputDetected": "音を受け取っています。",
```

英語辞書へ追加する。

```js
"composer.voiceInputDetected": "Microphone input detected.",
```

`renderAsrStatus()`引数へ`signalLevel = null`を追加する。
録音中だけ`composerStatus.dataset.voiceLevel`へ0から4を設定し、
停止、失敗、idleでは属性を削除する。`status === "input"`では
`composer.voiceInputDetected`を表示する。

- [ ] **Step 4: 5本バーをCSSで実装する**

既存`.composer-status.recording::before`を、5本の縦線を持つ
multiple backgroundへ置き換える。

```css
.composer-status.recording::before {
  content: "";
  display: block;
  width: 38px;
  height: 14px;
  background:
    linear-gradient(currentColor, currentColor) 0 50% / 4px var(--voice-bar-1, 2px) no-repeat,
    linear-gradient(currentColor, currentColor) 8px 50% / 4px var(--voice-bar-2, 2px) no-repeat,
    linear-gradient(currentColor, currentColor) 16px 50% / 4px var(--voice-bar-3, 2px) no-repeat,
    linear-gradient(currentColor, currentColor) 24px 50% / 4px var(--voice-bar-4, 2px) no-repeat,
    linear-gradient(currentColor, currentColor) 32px 50% / 4px var(--voice-bar-5, 2px) no-repeat;
  opacity: 0.78;
}
```

`data-voice-level`ごとに高さを定義する。

```css
.composer-status[data-voice-level="0"] { --voice-bar-1: 2px; --voice-bar-2: 2px; --voice-bar-3: 2px; --voice-bar-4: 2px; --voice-bar-5: 2px; }
.composer-status[data-voice-level="1"] { --voice-bar-1: 4px; --voice-bar-2: 6px; --voice-bar-3: 4px; --voice-bar-4: 6px; --voice-bar-5: 4px; }
.composer-status[data-voice-level="2"] { --voice-bar-1: 6px; --voice-bar-2: 10px; --voice-bar-3: 8px; --voice-bar-4: 10px; --voice-bar-5: 6px; }
.composer-status[data-voice-level="3"] { --voice-bar-1: 10px; --voice-bar-2: 14px; --voice-bar-3: 12px; --voice-bar-4: 14px; --voice-bar-5: 10px; }
.composer-status[data-voice-level="4"] { --voice-bar-1: 14px; --voice-bar-2: 14px; --voice-bar-3: 14px; --voice-bar-4: 14px; --voice-bar-5: 14px; }
```

`web/index.html`の`#composer-status`へ`aria-live="polite"`を追加する。

- [ ] **Step 5: 音声入力資産版を揃える**

次だけを`0.8.232-asr-vad.3`へ変更する。

- `web/index.html`: `i18n.js`、`asr.js`、`pwa.js`
- `web/pwa.js`: Service Worker登録URL
- `web/sw.js`: `CACHE_NAME`、`i18n.js`、`asr.js`、`pwa.js`
- `scripts/test-pwa-assets.js`: `VOICE_INPUT_ASSET_VERSION`
- `scripts/test-model-selection.js`: 対応する正規表現

`styles.css`も表示変更対象のため、同じ資産版で`index.html`と
`web/sw.js`から参照する。その他の資産版は変更しない。

- [ ] **Step 6: 表示契約と資産testを確認する**

Run:

```bash
node scripts/test-asr-helpers.js
node scripts/test-pwa-assets.js
node scripts/test-model-selection.js
node --check web/asr.js
node --check web/i18n.js
```

Expected: 全コマンド終了コード0。

- [ ] **Step 7: UIと資産版をcommitする**

```bash
git add web/asr.js \
  web/i18n.js \
  web/index.html \
  web/styles.css \
  web/pwa.js \
  web/sw.js \
  scripts/test-asr-helpers.js \
  scripts/test-pwa-assets.js \
  scripts/test-model-selection.js
git commit -m "feat: show live voice input meter"
```

Expected: 5段階メーター、状態文、資産版のcommit成功。

### Task 4: 実機検証、報告更新、Phase 2 commit

**Files:**

- Modify: `docs/tomos-phase2-gate2-report-2026-07-25.ja.md`
- Modify: `docs/superpowers/plans/2026-07-23-tomos-realtime-voice-input.md`
- Verify: Phase 2で変更した全ファイル

**Interfaces:**

- Consumes: Task 1から3の表示と既存Phase 2実装
- Produces: Gate 2の実測結果、通常版復旧状態、Phase 2 commit

- [ ] **Step 1: Global Verification Matrixを再実行する**

Run:

```bash
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-asr-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test-desktop-shell-contract.py
python3 scripts/test_server_helpers.py
python3 scripts/test_study_pack_manager.py
python3 scripts/test_context_core.py
python3 scripts/test_knowledge_layer.py
python3 -m py_compile server.py
cargo test --manifest-path src-tauri/Cargo.toml
cargo build --release --manifest-path src-tauri/Cargo.toml
git diff --check
```

Expected: 全コマンド終了コード0。`test_server_helpers.py`はlocalhost一時ポートを使うため必要なら承認付きで実行する。

- [ ] **Step 2: Tauriアプリ実声テストを行う**

ad-hoc署名した一時app bundleで次を確認する。

1. 録音開始直後はレベル0と「音声を待っています」。
2. 小さな環境音でレベル1と「音を受け取っています」。
3. 人の声でレベル2以上と「声を認識しています」。
4. 発話終了後に「音声を確定しています」へ進む。
5. ASRランナー未設定時は既存の安全なエラーへ進む。
6. 停止後にメーターが消え、録音trackとtimerが残らない。

- [ ] **Step 3: 画面幅を確認する**

PC幅1440×900、Tauriアプリ1280×820、スマートフォン幅390×844で、
メーター、状態文、マイク、送信ボタンが重ならず横スクロールしないことを確認する。

- [ ] **Step 4: Gate報告を更新する**

`docs/tomos-phase2-gate2-report-2026-07-25.ja.md`へ実測した
レベル変化、状態文、自動停止、ASR結果を記録する。確認できなかった項目を
合格と書かない。

- [ ] **Step 5: 通常版を復旧する**

一時appとworktree serverを終了し、一時bundleだけを削除する。
`/Applications/TOMOS AI.app`を再起動して次をreadbackする。

```text
appVersion = 0.8.230
server cwd = /Applications/TOMOS AI.app/Contents/Resources/Gemma4_12B
macOS input volume = 27
gemma4.micGain = 1
```

- [ ] **Step 6: 最終差分を確認する**

Run:

```bash
git status --short --branch
git diff --stat
git diff --check
```

Expected: 関係するPhase 2ファイルだけが変更され、空白エラー0件。

- [ ] **Step 7: Phase 2実装をcommitする**

Directorのcommit承認を確認した上で、Phase 2対象ファイルだけをstageする。

```bash
git add docs/asr-roadmap.ja.md \
  docs/superpowers/plans/2026-07-23-tomos-evolution-master.md \
  docs/superpowers/plans/2026-07-23-tomos-realtime-voice-input.md \
  docs/superpowers/plans/2026-07-25-tomos-voice-input-indicator.md \
  docs/director-tomos-phase2-realtime-voice-input-instructions-2026-07-25.ja.md \
  docs/tomos-phase2-gate2-report-2026-07-25.ja.md \
  scripts/test-asr-helpers.js \
  scripts/test-desktop-shell-contract.py \
  scripts/test-model-selection.js \
  scripts/test-pwa-assets.js \
  scripts/test_server_helpers.py \
  server.py \
  src-tauri/Info.plist \
  src-tauri/tauri.conf.json \
  web/asr.js \
  web/i18n.js \
  web/index.html \
  web/pwa.js \
  web/styles.css \
  web/sw.js
git commit -m "feat: add voice activity finalization and input feedback"
```

Expected: commit成功。push、PR、署名配布、公証は行わない。
