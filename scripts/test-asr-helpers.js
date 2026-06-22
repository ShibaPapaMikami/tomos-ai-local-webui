const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = {
  Blob,
  window: { setTimeout, clearTimeout, setInterval, clearInterval },
  console,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/asr.js", "utf8"), context, { filename: "web/asr.js" });

const {
  appendTranscriptToPrompt,
  audioConstraintsForDevice,
  asrUnavailableMessage,
  asrSettingsHtml,
  bindAsrUi,
  fetchAsrSetupStatus,
  fetchAsrStatus,
  handleVoiceInputClick,
  concreteAudioInputCount,
  defaultAudioInputLooksVirtual,
  isVirtualAudioDeviceLabel,
  listAudioInputDevices,
  preferredRealAudioInputDevice,
  renderAsrStatus,
  requestAsrSetup,
  setComposerStatus,
  composeLivePromptValue,
  formatMicGain,
  mergeFloat32Chunks,
  normalizeAudioInputDevices,
  normalizeMicGain,
  normalizePartialTranscriptionMode,
  liveSpeechRecognitionAvailable,
  PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS,
  audioSignalStats,
  recordLiveSpeech,
  hasAudibleSignal,
  supportedAudioMimeType,
  transcribeAudio,
  wavBlobFromFloat32,
} = context.window.GEMMA_ASR;

function fakeClassList() {
  const enabled = new Set();
  return {
    enabled,
    toggle(name, value) {
      if (value) enabled.add(name);
      else enabled.delete(name);
    },
  };
}

const statusEl = { textContent: "", hidden: true };
setComposerStatus({ els: { composerStatus: statusEl }, message: "準備中" });
assert.equal(statusEl.textContent, "準備中");
assert.equal(statusEl.hidden, false);
setComposerStatus({ els: { composerStatus: statusEl }, message: "" });
assert.equal(statusEl.hidden, true);

const voiceInput = { classList: fakeClassList() };
const t = (key, params = {}) => `${key}:${params.seconds ?? params.missing ?? params.error ?? ""}`;
const settingsHtml = asrSettingsHtml({
  selectedModel: "nvidia/nemotron-3.5-asr-streaming-0.6b",
  status: {
    available: false,
    status: "not_configured",
    message: "音声入力は未設定です。",
    nextStep: "ASRサーバーを接続します。",
    requirementsOk: false,
    dependenciesOk: false,
    runnableModels: ["nvidia/nemotron-3.5-asr-streaming-0.6b"],
    requirements: [
      { id: "python", label: "Python 3.11+", ok: true, detail: "3.11.9" },
      { id: "nemo", label: "NVIDIA NeMo ASR", ok: false, hint: "nemo_toolkit[asr] が必要です。" },
    ],
    candidates: [
      {
        model: "nvidia/nemotron-3.5-asr-streaming-0.6b",
        label: "Nemotron ASR",
        purpose: "高品質",
        note: "重い可能性あり",
        weight: "heavy",
        source: "https://example.com/asr",
        implemented: true,
      },
      {
        model: "whisper.cpp",
        label: "whisper.cpp",
        purpose: "今後対応",
        note: "軽量候補",
        weight: "medium",
        source: "https://example.com/whisper",
        implemented: false,
      },
    ],
  },
  micGain: 1.8,
  micDeviceId: "mic-2",
  partialIntervalSeconds: 6,
  partialMode: "browser",
  micDevices: [
    { kind: "audioinput", deviceId: "mic-1", label: "内蔵マイク" },
    { kind: "audioinput", deviceId: "mic-2", label: "USB Mic" },
    { kind: "videoinput", deviceId: "camera-1", label: "Camera" },
  ],
  setupJob: { status: "running", message: "依存を取得中" },
  t,
});
assert.match(settingsHtml, /settings\.asrTitle/);
assert.match(settingsHtml, /settings\.asrModelSelect/);
assert.match(settingsHtml, /data-asr-model/);
assert.match(settingsHtml, /data-asr-mic-gain/);
assert.match(settingsHtml, /1\.8x/);
assert.match(settingsHtml, /data-asr-partial-mode/);
assert.match(settingsHtml, /value="browser" selected/);
assert.match(settingsHtml, /data-asr-partial-interval/);
assert.match(settingsHtml, /value="6" selected/);
assert.match(settingsHtml, /data-asr-mic-device/);
assert.match(settingsHtml, /USB Mic/);
assert.doesNotMatch(settingsHtml, /Camera/);
assert.match(settingsHtml, /data-asr-mic-check/);
assert.doesNotMatch(settingsHtml, /data-asr-copy-mic-settings/);
assert.match(settingsHtml, /data-asr-level-bar/);
assert.match(settingsHtml, /data-asr-stop-mic/);
assert.match(settingsHtml, /selected>Nemotron ASR \/ settings\.asrWeightHeavy/);
assert.match(settingsHtml, /settings\.asrRequirements/);
assert.match(settingsHtml, /Python 3\.11\+/);
assert.match(settingsHtml, /NVIDIA NeMo ASR/);
assert.match(settingsHtml, /settings\.asrRequirementMissing/);
assert.match(settingsHtml, /settings\.asrSetupStatus/);
assert.match(settingsHtml, /依存を取得中/);
assert.match(settingsHtml, /data-asr-setup disabled/);
assert.match(settingsHtml, /音声入力は未設定です。/);
assert.match(settingsHtml, /Nemotron ASR/);
assert.match(settingsHtml, /settings\.asrWeightHeavy/);
assert.match(settingsHtml, /settings\.asrRunnableCandidates/);
assert.match(settingsHtml, /settings\.asrFutureCandidates/);
assert.match(settingsHtml, /settings\.asrCandidateReady/);
assert.match(settingsHtml, /settings\.asrCandidateFuture/);
assert.match(settingsHtml, /https:\/\/example\.com\/asr/);
assert.match(settingsHtml, /data-asr-refresh/);
assert.match(settingsHtml, /whisper\.cpp/);

context.MediaRecorder = {
  isTypeSupported: (type) => type === "audio/mp4",
};
assert.equal(supportedAudioMimeType(), "audio/mp4");
assert.equal(JSON.stringify(audioConstraintsForDevice("mic-2")), JSON.stringify({
  audio: {
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: true,
    deviceId: { exact: "mic-2" },
  },
}));
assert.equal(JSON.stringify(audioConstraintsForDevice("")), JSON.stringify({
  audio: {
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: true,
  },
}));
assert.equal(JSON.stringify(normalizeAudioInputDevices([
  { kind: "audioinput", deviceId: "a", label: "A" },
  { kind: "audiooutput", deviceId: "b", label: "B" },
])), JSON.stringify([{ deviceId: "a", groupId: "", label: "A", index: 1 }]));
assert.equal(concreteAudioInputCount([
  { kind: "audioinput", deviceId: "default", label: "Default - MacBook Pro Microphone" },
  { kind: "audioinput", deviceId: "real", label: "MacBook Pro Microphone" },
]), 1);
assert.equal(isVirtualAudioDeviceLabel("Microsoft Teams Audio Device (Virtual)"), true);
assert.equal(isVirtualAudioDeviceLabel("MacBook Air Microphone"), false);
assert.equal(defaultAudioInputLooksVirtual([
  { kind: "audioinput", deviceId: "default", label: "Default - Microsoft Teams Audio Device (Virtual)" },
  { kind: "audioinput", deviceId: "real", label: "MacBook Air Microphone" },
]), true);
assert.equal(preferredRealAudioInputDevice([
  { kind: "audioinput", deviceId: "default", label: "Default - Microsoft Teams Audio Device (Virtual)" },
  { kind: "audioinput", deviceId: "teams", label: "Microsoft Teams Audio Device (Virtual)" },
  { kind: "audioinput", deviceId: "real", label: "MacBook Air Microphone" },
]).deviceId, "real");

const defaultOnlyMicHtml = asrSettingsHtml({
  status: { status: "not_configured", candidates: [] },
  micDevices: [{ kind: "audioinput", deviceId: "default", label: "Default - Microsoft Teams Audio Device (Virtual)" }],
  t,
});
assert.match(defaultOnlyMicHtml, /data-asr-open-mic-settings/);
assert.match(defaultOnlyMicHtml, /data-asr-copy-mic-settings/);
assert.match(defaultOnlyMicHtml, /chrome:\/\/settings\/content\/microphone/);
assert.equal(composeLivePromptValue("既存", "音声", ""), "既存\n音声");
assert.equal(composeLivePromptValue("", "", "途中"), "途中");
assert.equal(normalizeMicGain(9), 3);
assert.equal(normalizeMicGain(0.1), 0.5);
assert.equal(normalizeMicGain("1.26"), 1.3);
assert.equal(normalizePartialTranscriptionMode("local"), "local");
assert.equal(normalizePartialTranscriptionMode("nemotron"), "local");
assert.equal(normalizePartialTranscriptionMode("bad-value"), "browser");
assert.equal(formatMicGain(2), "2.0x");
assert.equal(liveSpeechRecognitionAvailable({}), false);
assert.equal(liveSpeechRecognitionAvailable({ webkitSpeechRecognition: function Fake() {} }), true);
assert.equal(PARTIAL_TRANSCRIPTION_INTERVAL_SECONDS, 3);
assert.deepEqual(Array.from(mergeFloat32Chunks([new Float32Array([0.1]), new Float32Array([-0.2, 0.3])])), [0.10000000149011612, -0.20000000298023224, 0.30000001192092896]);
const audioStats = audioSignalStats(new Float32Array([0, 0.5, -0.25]));
assert.equal(audioStats.peak, 0.5);
assert.equal(audioStats.rms, Math.sqrt((0.25 + 0.0625) / 3));
assert.equal(audioStats.samples, 3);
assert.equal(hasAudibleSignal(new Float32Array([0, 0.001, -0.001])), false);
assert.equal(hasAudibleSignal(new Float32Array([0, 0.03, 0])), true);
const wavBlob = wavBlobFromFloat32(new Float32Array([0, 0.5, -0.5]), 16000, Blob);
assert.equal(wavBlob.type, "audio/wav");
assert.equal(wavBlob.size, 50);

renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "checking" });
assert.equal(statusEl.textContent, "composer.voiceChecking:");
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "recording", seconds: 3 });
assert.equal(statusEl.textContent, "composer.voiceRecording:3");
assert.equal(voiceInput.classList.enabled.has("recording"), true);
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "partial", seconds: 4 });
assert.equal(statusEl.textContent, "composer.voicePartialTranscribing:4");
assert.equal(voiceInput.classList.enabled.has("recording"), true);
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "idle" });
assert.equal(statusEl.hidden, true);
assert.equal(voiceInput.classList.enabled.has("recording"), false);

const needsSetupMessage = asrUnavailableMessage({
  status: "needs_dependencies",
  requirementsOk: false,
  requirements: [
    { label: "Cython", ok: false },
    { label: "NVIDIA NeMo ASR", ok: false },
    { label: "ffmpeg", ok: true },
  ],
}, t);
assert.equal(needsSetupMessage, "composer.voiceNeedsSetup:Cython、NVIDIA NeMo ASR");

let resized = false;
let focused = false;
const prompt = {
  value: "こんにちは",
  focus() {
    focused = true;
  },
};
assert.equal(appendTranscriptToPrompt({
  els: { prompt },
  text: "音声の内容",
  onResize: () => {
    resized = true;
  },
}), true);
assert.equal(prompt.value, "こんにちは\n音声の内容");
assert.equal(resized, true);
assert.equal(focused, true);
assert.equal(appendTranscriptToPrompt({ els: { prompt }, text: "   " }), false);

let clickHandler = null;
const boundVoiceButton = {
  dataset: {},
  classList: fakeClassList(),
  addEventListener(name, handler) {
    if (name === "click") clickHandler = handler;
  },
};
const boundStatusEl = { textContent: "", hidden: true };
const fetchImpl = async () => ({
  ok: true,
  json: async () => ({ ok: true, available: false, message: "ASRは未接続です。" }),
});
bindAsrUi({
  els: { voiceInput: boundVoiceButton, composerStatus: boundStatusEl },
  t,
  onResize: () => {},
  fetchImpl,
});
assert.equal(boundVoiceButton.dataset.asrBound, "true");
assert.equal(boundVoiceButton.dataset.asrResize, "true");
clickHandler({ preventDefault() {} });

(async () => {
  let enumerateCount = 0;
  let stoppedPermissionStream = false;
  const listedDevices = await listAudioInputDevices({
    root: { setTimeout: (callback) => callback() },
    retries: 2,
    retryDelayMs: 0,
    navigatorImpl: {
      mediaDevices: {
        async enumerateDevices() {
          enumerateCount += 1;
          if (enumerateCount < 3) {
            return [{ kind: "audioinput", deviceId: "default", label: "Default - MacBook Pro Microphone" }];
          }
          return [
            { kind: "audioinput", deviceId: "default", label: "Default - MacBook Pro Microphone" },
            { kind: "audioinput", deviceId: "built-in", label: "MacBook Pro Microphone" },
            { kind: "audioinput", deviceId: "usb", label: "USB Mic" },
          ];
        },
        async getUserMedia() {
          return { getTracks: () => [{ stop: () => { stoppedPermissionStream = true; } }] };
        },
      },
    },
  });
  assert.equal(stoppedPermissionStream, true);
  assert.equal(listedDevices.length, 3);
  assert.equal(listedDevices[1].deviceId, "built-in");

  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(boundStatusEl.textContent, "ASRは未接続です。");
  const status = await fetchAsrStatus({ fetchImpl });
  assert.equal(status.available, false);

  const setupStatus = await fetchAsrSetupStatus({
    fetchImpl: async () => ({
      ok: true,
      json: async () => ({ ok: true, job: { status: "running", message: "setup" } }),
    }),
  });
  assert.equal(setupStatus.job.status, "running");

  const setupRequest = await requestAsrSetup({
    fetchImpl: async (url, options = {}) => {
      assert.equal(url, "/api/asr/setup");
      assert.equal(options.method, "POST");
      return {
        ok: true,
        json: async () => ({ ok: true, status: "running", message: "started" }),
      };
    },
  });
  assert.equal(setupRequest.status, "running");

  const clickStatusEl = { textContent: "", hidden: true };
  const clickResult = await handleVoiceInputClick({
    els: { voiceInput: boundVoiceButton, composerStatus: clickStatusEl },
    t,
    fetchImpl,
  });
  assert.equal(clickResult.available, false);
  assert.equal(clickStatusEl.textContent, "ASRは未接続です。");

  let postedBody = null;
  const transcribeResult = await transcribeAudio({
    audioBlob: { type: "audio/webm" },
    model: "nvidia/nemotron-3.5-asr-streaming-0.6b",
    base64Encoder: async () => "abc123",
    fetchImpl: async (url, options) => {
      assert.equal(url, "/api/asr/transcribe");
      postedBody = JSON.parse(options.body);
      return {
        ok: true,
        json: async () => ({ ok: true, text: "音声テキスト" }),
      };
    },
  });
  assert.equal(transcribeResult.text, "音声テキスト");
  assert.equal(postedBody.model, "nvidia/nemotron-3.5-asr-streaming-0.6b");
  assert.equal(postedBody.audioBase64, "abc123");

  let recorderCalled = false;
  const voiceStatusEl = { textContent: "", hidden: true };
  const needsSetupResult = await handleVoiceInputClick({
    els: { voiceInput: boundVoiceButton, composerStatus: voiceStatusEl },
    t,
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: async () => {
      recorderCalled = true;
      return { type: "audio/webm" };
    },
    fetchImpl: async (url) => {
      assert.equal(url, "/api/asr/status");
      return {
        ok: true,
        json: async () => ({
          ok: true,
          available: false,
          status: "needs_dependencies",
          requirementsOk: false,
          requirements: [
            { label: "Cython", ok: false },
            { label: "NVIDIA NeMo ASR", ok: false },
          ],
          recommendedModel: "nvidia/nemotron-3.5-asr-streaming-0.6b",
        }),
      };
    },
  });
  assert.equal(needsSetupResult.status, "needs_dependencies");
  assert.equal(recorderCalled, false);
  assert.equal(voiceStatusEl.textContent, "composer.voiceNeedsSetup:Cython、NVIDIA NeMo ASR");

  let transcript = "";
  let recordedMicGain = null;
  let recordedMicDeviceId = null;
  voiceStatusEl.textContent = "";
  voiceStatusEl.hidden = true;
  const voiceResult = await handleVoiceInputClick({
    els: { voiceInput: boundVoiceButton, composerStatus: voiceStatusEl },
    t,
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    getMicGain: () => 2.2,
    getMicDeviceId: () => "mic-2",
    recorder: async ({ micGain, micDeviceId }) => {
      recordedMicGain = micGain;
      recordedMicDeviceId = micDeviceId;
      return { type: "audio/webm" };
    },
    base64Encoder: async () => "voiceBase64",
    fetchImpl: async (url, options = {}) => {
      if (url === "/api/asr/status") {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            available: true,
            model: "nvidia/nemotron-3.5-asr-streaming-0.6b",
          }),
        };
      }
      assert.equal(url, "/api/asr/transcribe");
      assert.equal(JSON.parse(options.body).model, "nvidia/nemotron-3.5-asr-streaming-0.6b");
      return {
        ok: true,
        json: async () => ({ ok: true, text: "録音結果" }),
      };
    },
    onTranscript: (text) => {
      transcript = text;
    },
  });
  assert.equal(voiceResult.text, "録音結果");
  assert.equal(transcript, "録音結果");
  assert.equal(recordedMicGain, 2.2);
  assert.equal(recordedMicDeviceId, "mic-2");
  assert.equal(voiceStatusEl.hidden, true);

  let previewTranscript = "";
  let previewResizeCount = 0;
  const previewPrompt = { value: "既存", focus() {} };
  const previewResult = await handleVoiceInputClick({
    els: { prompt: previewPrompt, voiceInput: boundVoiceButton, composerStatus: voiceStatusEl },
    t,
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    getPartialMode: () => "nemotron",
    recorder: async ({ onPartialBlob, partialIntervalSeconds }) => {
      assert.equal(partialIntervalSeconds, 3);
      await onPartialBlob({ type: "audio/webm", size: 12, marker: "partial" });
      assert.equal(previewPrompt.value, "既存\n途中結果");
      return { type: "audio/webm", size: 24, marker: "final" };
    },
    base64Encoder: async (blob) => blob.marker,
    fetchImpl: async (url, options = {}) => {
      if (url === "/api/asr/status") {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            available: true,
            runnableModels: ["nvidia/nemotron-3.5-asr-streaming-0.6b"],
            recommendedModel: "nvidia/nemotron-3.5-asr-streaming-0.6b",
          }),
        };
      }
      assert.equal(url, "/api/asr/transcribe");
      const body = JSON.parse(options.body);
      return {
        ok: true,
        json: async () => ({
          ok: true,
          text: body.audioBase64 === "partial" ? "途中結果" : "最終結果",
        }),
      };
    },
    onResize: () => {
      previewResizeCount += 1;
    },
    onTranscript: (text) => {
      assert.equal(previewPrompt.value, "既存");
      previewTranscript = text;
      previewPrompt.value = `${previewPrompt.value}\n${text}`;
    },
  });
  assert.equal(previewResult.text, "最終結果");
  assert.equal(previewTranscript, "最終結果");
  assert.equal(previewPrompt.value, "既存\n最終結果");
  assert.equal(previewResizeCount >= 2, true);

  let liveResizeCount = 0;
  const livePrompt = { value: "メモ", focus() {} };
  const liveButton = {
    dataset: {},
    classList: fakeClassList(),
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeRecognition {
    start() {
      setTimeout(() => {
        this.onresult?.({
          resultIndex: 0,
          results: [
            {
              0: { transcript: "リアルタイム入力" },
              length: 1,
              isFinal: true,
            },
          ],
        });
        this.onend?.();
      }, 0);
    }
    stop() {
      this.onend?.();
    }
  }

  let serverTranscript = "";
  let serverRecorderCalled = false;
  let liveRecorderCalledForServer = false;
  context.window.webkitSpeechRecognition = FakeRecognition;
  const serverPreferredResult = await handleVoiceInputClick({
    els: { prompt: { value: "", focus() {} }, voiceInput: liveButton, composerStatus: voiceStatusEl },
    t,
    speechRoot: context.window,
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: async () => {
      serverRecorderCalled = true;
      return { type: "audio/webm" };
    },
    liveRecorder: async () => {
      liveRecorderCalledForServer = true;
      return { ok: true, text: "リアルタイム入力", live: true };
    },
    base64Encoder: async () => "serverVoiceBase64",
    fetchImpl: async (url, options = {}) => {
      if (url === "/api/asr/status") {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            available: true,
            runnableModels: ["nvidia/nemotron-3.5-asr-streaming-0.6b"],
            recommendedModel: "nvidia/nemotron-3.5-asr-streaming-0.6b",
          }),
        };
      }
      assert.equal(url, "/api/asr/transcribe");
      assert.equal(JSON.parse(options.body).audioBase64, "serverVoiceBase64");
      return {
        ok: true,
        json: async () => ({ ok: true, text: "サーバー文字起こし" }),
      };
    },
    onTranscript: (text) => {
      serverTranscript = text;
    },
  });
  assert.equal(serverPreferredResult.text, "サーバー文字起こし");
  assert.equal(serverTranscript, "サーバー文字起こし");
  assert.equal(serverRecorderCalled, true);
  assert.equal(liveRecorderCalledForServer, true);

  const liveResult = await recordLiveSpeech({
    els: { prompt: livePrompt, voiceInput: liveButton, composerStatus: voiceStatusEl },
    t,
    root: context.window,
    recognitionFactory: FakeRecognition,
    onResize: () => {
      liveResizeCount += 1;
    },
  });
  assert.equal(liveResult.text, "リアルタイム入力");
  assert.equal(livePrompt.value, "メモ\nリアルタイム入力");
  assert.equal(liveResizeCount > 0, true);

  let liveStopHandler = null;
  let stopCalledWithoutEnd = false;
  class FakeRecognitionWithoutEnd {
    start() {}
    stop() {
      stopCalledWithoutEnd = true;
    }
  }
  const forcedStopResultPromise = recordLiveSpeech({
    els: { prompt: { value: "", focus() {} }, voiceInput: liveButton, composerStatus: voiceStatusEl },
    t,
    root: {
      setInterval: () => 1,
      clearInterval() {},
      setTimeout(callback, ms) {
        if (ms === 800) callback();
        return 1;
      },
      clearTimeout() {},
    },
    recognitionFactory: FakeRecognitionWithoutEnd,
    stopElement: {
      addEventListener(name, handler) {
        if (name === "click") liveStopHandler = handler;
      },
      removeEventListener() {},
    },
  });
  liveStopHandler();
  const forcedStopResult = await forcedStopResultPromise;
  assert.equal(stopCalledWithoutEnd, true);
  assert.equal(forcedStopResult.live, true);
  assert.equal(forcedStopResult.ok, false);

  let liveFetchCalled = false;
  const liveClickPrompt = { value: "", focus() {} };
  const liveClickStatus = { textContent: "", hidden: true };
  const liveClickResult = await handleVoiceInputClick({
    els: { prompt: liveClickPrompt, voiceInput: liveButton, composerStatus: liveClickStatus },
    t,
    speechRoot: context.window,
    fetchImpl: async () => {
      liveFetchCalled = true;
      throw new Error("ASR server is offline");
    },
    onResize: () => {},
  });
  assert.equal(liveClickResult.live, true);
  assert.equal(liveClickPrompt.value, "リアルタイム入力");
  assert.equal(liveFetchCalled, true);

  console.log("asr helper tests passed");
})();
