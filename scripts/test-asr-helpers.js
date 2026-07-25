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
  micCaptureDebugState,
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
  createWavPartialCapture,
  recordLiveSpeech,
  recordAudio,
  hasAudibleSignal,
  mergeAsrTranscript,
  requestActiveVoiceStop,
  shouldApplyAsrResult,
  voiceActivityState,
  voiceSignalLevel,
  supportedAudioMimeType,
  transcribeAudio,
  wavBlobFromFloat32,
} = context.window.GEMMA_ASR;

assert.equal(
  micCaptureDebugState(
    { readyState: "live", muted: false, enabled: true },
    { state: "running" },
  ),
  "live / unmuted / enabled / audio: running",
);

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

function createVadHarness() {
  const intervals = new Map();
  const timeouts = new Map();
  let nextTimerId = 1;
  const harness = {
    nowMs: 0,
    processor: null,
    closeCount: 0,
    trackStopCount: 0,
  };
  class FakeAudioContext {
    constructor() {
      this.sampleRate = 1000;
      this.destination = {};
    }
    createMediaStreamSource() {
      return { connect() {}, disconnect() {} };
    }
    createScriptProcessor() {
      harness.processor = { connect() {}, disconnect() {}, onaudioprocess: null };
      return harness.processor;
    }
    createGain() {
      return { gain: { value: 1 }, connect() {}, disconnect() {} };
    }
    resume() {}
    close() {
      harness.closeCount += 1;
    }
  }
  harness.root = {
    AudioContext: FakeAudioContext,
    performance: {
      now: () => harness.nowMs,
    },
    setInterval(callback, ms) {
      const id = nextTimerId++;
      intervals.set(id, { callback, ms });
      return id;
    },
    clearInterval(id) {
      intervals.delete(id);
    },
    setTimeout(callback, ms) {
      const id = nextTimerId++;
      timeouts.set(id, { callback, ms });
      return id;
    },
    clearTimeout(id) {
      timeouts.delete(id);
    },
  };
  harness.stream = {
    getTracks() {
      return [{
        stop() {
          harness.trackStopCount += 1;
        },
      }];
    },
  };
  harness.feed = (nowMs, value, length = 500) => {
    harness.nowMs = nowMs;
    const samples = new Float32Array(length);
    samples.fill(value);
    harness.processor.onaudioprocess({
      inputBuffer: { getChannelData: () => samples },
    });
  };
  harness.fireIntervals = () => {
    Array.from(intervals.values()).forEach(({ callback }) => callback());
  };
  harness.activeTimerCount = () => intervals.size + timeouts.size;
  return harness;
}

class FakeMediaRecorder {
  constructor(stream) {
    this.stream = stream;
    this.state = "inactive";
    this.mimeType = "audio/webm";
    this.listeners = {};
    this.stopCount = 0;
  }
  addEventListener(name, handler) {
    this.listeners[name] = handler;
  }
  start() {
    this.state = "recording";
  }
  stop() {
    if (this.state === "inactive") return;
    this.stopCount += 1;
    this.state = "inactive";
    this.listeners.stop?.();
  }
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
assert.equal(mergeAsrTranscript({
  baseText: "明日の",
  partialText: "予定を",
  finalText: "予定を教えて",
}), "明日の 予定を教えて");
assert.equal(mergeAsrTranscript({
  baseText: "明日の",
  partialText: "予定を",
  finalText: "",
}), "明日の 予定を");
assert.equal(shouldApplyAsrResult({
  activeSessionId: 4,
  resultSessionId: 3,
  stopped: false,
}), false);
assert.equal(shouldApplyAsrResult({
  activeSessionId: 4,
  resultSessionId: 4,
  stopped: true,
}), false);
assert.equal(shouldApplyAsrResult({
  activeSessionId: 4,
  resultSessionId: 4,
  stopped: false,
}), true);
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
assert.equal(voiceSignalLevel({ rms: 0, peak: 0, phase: "idle" }), 0);
assert.equal(voiceSignalLevel({ rms: 0.0015, peak: 0.005, phase: "idle" }), 1);
assert.equal(voiceSignalLevel({ rms: 0.003, peak: 0.01, phase: "candidate" }), 2);
assert.equal(voiceSignalLevel({ rms: 0.004, peak: 0.015, phase: "speaking" }), 3);
assert.equal(voiceSignalLevel({ rms: 0.012, peak: 0.04, phase: "speaking" }), 4);
assert.equal(voiceSignalLevel({ rms: Number.NaN, peak: -1, phase: "bad" }), 0);
assert.equal(hasAudibleSignal(new Float32Array([0, 0.001, -0.001])), false);
assert.equal(hasAudibleSignal(new Float32Array([0, 0.03, 0])), true);
assert.equal(
  hasAudibleSignal(new Float32Array([0, 0, 0, 0, 0.012, 0, 0, 0])),
  true,
);
const wavBlob = wavBlobFromFloat32(new Float32Array([0, 0.5, -0.5]), 16000, Blob);
assert.equal(wavBlob.type, "audio/wav");
assert.equal(wavBlob.size, 50);

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
assert.equal(vad.phase, "idle");

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

const measuredMacVoice = voiceActivityState({
  state: vad,
  nowMs: 0,
  rms: 0.0035,
  peak: 0.012,
});
assert.equal(measuredMacVoice.state.phase, "candidate");
assert.equal(measuredMacVoice.action, "none");

let shortSound = voiceActivityState({ state: vad, nowMs: 0, rms: 0.02, peak: 0.08 });
shortSound = voiceActivityState({ state: shortSound.state, nowMs: 100, rms: 0.02, peak: 0.08 });
assert.equal(shortSound.state.phase, "candidate");
assert.equal(shortSound.action, "none");

const briefSilence = voiceActivityState({
  state: result.state = {
    phase: "speaking",
    candidateStartedAtMs: 0,
    speechStartedAtMs: 200,
    lastAudibleAtMs: 200,
  },
  nowMs: 500,
  rms: 0,
  peak: 0,
});
assert.equal(briefSilence.state.phase, "speaking");
assert.equal(briefSilence.action, "none");

const stopped = voiceActivityState({
  state: briefSilence.state,
  nowMs: 900,
  rms: 0,
  peak: 0,
});
assert.equal(stopped.state.phase, "idle");
assert.equal(stopped.action, "speech-finalize");

for (const value of [NaN, -0.02, undefined]) {
  const silent = voiceActivityState({ state: vad, nowMs: 0, rms: value, peak: value });
  assert.equal(silent.state.phase, "idle");
  assert.equal(silent.action, "none");
}

const silentHarness = createVadHarness();
let silentPartialCount = 0;
let silentFinalCount = 0;
const silentCapture = createWavPartialCapture({
  stream: silentHarness.stream,
  root: silentHarness.root,
  intervalSeconds: 3,
  now: () => silentHarness.nowMs,
  onPartialBlob: () => {
    silentPartialCount += 1;
  },
  onFinalBlob: () => {
    silentFinalCount += 1;
  },
});
silentCapture.start();
silentHarness.feed(0, 0);
silentHarness.feed(900, 0);
silentHarness.fireIntervals();
silentCapture.stop();
assert.equal(silentPartialCount + silentFinalCount, 0);

const shortHarness = createVadHarness();
let shortRequestCount = 0;
const shortCapture = createWavPartialCapture({
  stream: shortHarness.stream,
  root: shortHarness.root,
  intervalSeconds: 3,
  now: () => shortHarness.nowMs,
  onPartialBlob: () => {
    shortRequestCount += 1;
  },
  onFinalBlob: () => {
    shortRequestCount += 1;
  },
});
shortCapture.start();
shortHarness.feed(0, 0.05);
shortHarness.feed(100, 0.05);
shortHarness.feed(180, 0);
shortHarness.fireIntervals();
shortCapture.stop();
assert.equal(shortRequestCount, 0);

const speechHarness = createVadHarness();
let speechPartialCount = 0;
let speechFinalCount = 0;
const speechCapture = createWavPartialCapture({
  stream: speechHarness.stream,
  root: speechHarness.root,
  intervalSeconds: 3,
  now: () => speechHarness.nowMs,
  onPartialBlob: (blob) => {
    assert.equal(blob.type, "audio/wav");
    speechPartialCount += 1;
  },
  onFinalBlob: (blob) => {
    assert.equal(blob.type, "audio/wav");
    speechFinalCount += 1;
  },
});
speechCapture.start();
speechHarness.feed(0, 0.05);
speechHarness.fireIntervals();
assert.equal(speechPartialCount, 0);
speechHarness.feed(200, 0.05);
speechHarness.fireIntervals();
assert.equal(speechPartialCount, 1);
speechHarness.feed(500, 0);
assert.equal(speechFinalCount, 0);
speechHarness.feed(850, 0);
assert.equal(speechFinalCount, 1);
speechHarness.feed(1600, 0);
speechHarness.fireIntervals();
assert.equal(speechFinalCount, 1);
speechCapture.stop();

let unsupportedVadCloseCount = 0;
class UnsupportedVadAudioContext {
  constructor() {
    this.sampleRate = 1000;
  }
  createMediaStreamSource() {
    return { connect() {}, disconnect() {} };
  }
  close() {
    unsupportedVadCloseCount += 1;
  }
}
const unsupportedVadCapture = createWavPartialCapture({
  stream: { getTracks: () => [] },
  root: { AudioContext: UnsupportedVadAudioContext },
  onFinalBlob() {},
});
assert.equal(unsupportedVadCapture, null);
assert.equal(unsupportedVadCloseCount, 1);

renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "checking" });
assert.equal(statusEl.textContent, "composer.voiceChecking:");
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "recording", seconds: 3 });
assert.equal(statusEl.textContent, "composer.voiceRecording:3");
assert.equal(voiceInput.classList.enabled.has("recording"), true);
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "partial", seconds: 4 });
assert.equal(statusEl.textContent, "composer.voicePartialTranscribing:4");
assert.equal(voiceInput.classList.enabled.has("recording"), true);
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "waiting" });
assert.equal(statusEl.textContent, "composer.voiceWaitingForSpeech:");
assert.equal(voiceInput.classList.enabled.has("recording"), true);
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "speech" });
assert.equal(statusEl.textContent, "composer.voiceSpeechDetected:");
assert.equal(voiceInput.classList.enabled.has("recording"), true);
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "finalizing" });
assert.equal(statusEl.textContent, "composer.voiceFinalizing:");
assert.equal(voiceInput.classList.enabled.has("recording"), false);
renderAsrStatus({ els: { composerStatus: statusEl, voiceInput }, t, status: "stopped" });
assert.equal(statusEl.textContent, "composer.voiceStopped:");
assert.equal(voiceInput.classList.enabled.has("recording"), false);
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

  const vadFinalHarness = createVadHarness();
  let vadFinalRecorder = null;
  let vadFinalRequestCount = 0;
  let vadFinalTranscript = "";
  const vadFinalStatusEl = { textContent: "", hidden: true };
  const vadFinalResultPromise = handleVoiceInputClick({
    els: {
      prompt: { value: "議事録", focus() {} },
      voiceInput: boundVoiceButton,
      composerStatus: vadFinalStatusEl,
    },
    t,
    getPartialMode: () => "off",
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: (options) => recordAudio({
      ...options,
      root: vadFinalHarness.root,
      navigatorImpl: {
        mediaDevices: {
          getUserMedia: async () => vadFinalHarness.stream,
        },
      },
      mediaRecorderFactory: (stream) => {
        vadFinalRecorder = new FakeMediaRecorder(stream);
        return vadFinalRecorder;
      },
    }),
    base64Encoder: async () => "vad-final",
    fetchImpl: async (url) => {
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
      vadFinalRequestCount += 1;
      return {
        ok: true,
        json: async () => ({ ok: true, text: "確定結果" }),
      };
    },
    onTranscript: (text) => {
      vadFinalTranscript = text;
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  vadFinalHarness.feed(0, 0.05);
  vadFinalHarness.feed(200, 0.05);
  assert.equal(vadFinalStatusEl.textContent, "composer.voiceSpeechDetected:");
  vadFinalHarness.fireIntervals();
  assert.equal(vadFinalRequestCount, 0);
  vadFinalHarness.feed(500, 0);
  assert.equal(vadFinalRequestCount, 0);
  vadFinalHarness.feed(850, 0);
  assert.equal(vadFinalStatusEl.textContent, "composer.voiceFinalizing:");
  const vadFinalResult = await vadFinalResultPromise;
  assert.equal(vadFinalResult.text, "確定結果");
  assert.equal(vadFinalRequestCount, 1);
  assert.equal(vadFinalTranscript, "確定結果");
  assert.equal(vadFinalRecorder.stopCount, 1);
  assert.equal(vadFinalHarness.trackStopCount, 1);
  assert.equal(vadFinalHarness.closeCount, 1);

  const browserFinalizeHarness = createVadHarness();
  let browserFinalizeRecognition = null;
  let browserFinalizePreviewPromise = null;
  let browserFinalizeSignal = null;
  class BrowserFinalizeRecognition {
    constructor() {
      this.stopCount = 0;
      browserFinalizeRecognition = this;
    }
    start() {}
    stop() {
      this.stopCount += 1;
      this.onend?.();
    }
  }
  browserFinalizeHarness.root.webkitSpeechRecognition = BrowserFinalizeRecognition;
  const browserFinalizePromise = handleVoiceInputClick({
    els: {
      prompt: { value: "ブラウザ", focus() {} },
      voiceInput: boundVoiceButton,
      composerStatus: { textContent: "", hidden: true },
    },
    t,
    speechRoot: browserFinalizeHarness.root,
    getPartialMode: () => "browser",
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: (options) => recordAudio({
      ...options,
      root: browserFinalizeHarness.root,
      navigatorImpl: {
        mediaDevices: {
          getUserMedia: async () => browserFinalizeHarness.stream,
        },
      },
      mediaRecorderFactory: (stream) => new FakeMediaRecorder(stream),
    }),
    liveRecorder: (options) => {
      browserFinalizePreviewPromise = recordLiveSpeech(options);
      return browserFinalizePreviewPromise;
    },
    base64Encoder: async () => "browser-final",
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
      browserFinalizeSignal = options.signal;
      return {
        ok: true,
        json: async () => ({ ok: true, text: "ブラウザ確定" }),
      };
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  browserFinalizeHarness.feed(0, 0.05);
  browserFinalizeHarness.feed(200, 0.05);
  browserFinalizeHarness.feed(850, 0);
  await browserFinalizePromise;
  assert.equal(browserFinalizeRecognition.stopCount, 1);
  await browserFinalizePreviewPromise;
  assert.equal(browserFinalizeSignal.aborted, false);
  assert.equal(browserFinalizeHarness.activeTimerCount(), 0);

  const cancelHarness = createVadHarness();
  let cancelRequestCount = 0;
  const cancelPrompt = { value: "元の入力", focus() {} };
  const cancelStatusEl = { textContent: "", hidden: true };
  const cancelResultPromise = handleVoiceInputClick({
    els: {
      prompt: cancelPrompt,
      voiceInput: boundVoiceButton,
      composerStatus: cancelStatusEl,
    },
    t,
    getPartialMode: () => "off",
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: (options) => recordAudio({
      ...options,
      root: cancelHarness.root,
      navigatorImpl: {
        mediaDevices: {
          getUserMedia: async () => cancelHarness.stream,
        },
      },
      mediaRecorderFactory: (stream) => new FakeMediaRecorder(stream),
    }),
    fetchImpl: async (url) => {
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
      cancelRequestCount += 1;
      return { ok: true, json: async () => ({ ok: true, text: "反映禁止" }) };
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  cancelHarness.feed(0, 0);
  cancelHarness.feed(900, 0);
  assert.equal(requestActiveVoiceStop(), true);
  assert.equal(requestActiveVoiceStop(), false);
  await cancelResultPromise;
  assert.equal(cancelRequestCount, 0);
  assert.equal(cancelPrompt.value, "元の入力");
  assert.equal(cancelStatusEl.textContent, "composer.voiceStopped:");
  assert.equal(cancelHarness.trackStopCount, 1);
  assert.equal(cancelHarness.closeCount, 1);

  const pendingPermissionHarness = createVadHarness();
  let resolvePendingStream = null;
  let pendingRecorderStartCount = 0;
  const pendingStreamPromise = new Promise((resolve) => {
    resolvePendingStream = resolve;
  });
  const pendingPermissionPromise = handleVoiceInputClick({
    els: {
      prompt: { value: "権限待ち", focus() {} },
      voiceInput: boundVoiceButton,
      composerStatus: { textContent: "", hidden: true },
    },
    t,
    getPartialMode: () => "off",
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: (options) => recordAudio({
      ...options,
      root: pendingPermissionHarness.root,
      navigatorImpl: {
        mediaDevices: {
          getUserMedia: () => pendingStreamPromise,
        },
      },
      mediaRecorderFactory: (stream) => {
        pendingRecorderStartCount += 1;
        return new FakeMediaRecorder(stream);
      },
    }),
    fetchImpl: async (url) => {
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
      throw new Error("停止後にSTT requestを送ってはいけない");
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(requestActiveVoiceStop(), true);
  resolvePendingStream(pendingPermissionHarness.stream);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(pendingRecorderStartCount, 0);
  const pendingPermissionResult = await pendingPermissionPromise;
  assert.equal(pendingPermissionResult.stopped, true);
  assert.equal(pendingPermissionHarness.trackStopCount, 1);
  assert.equal(pendingPermissionHarness.activeTimerCount(), 0);

  const browserCancelHarness = createVadHarness();
  let browserCancelRecognition = null;
  let browserCancelPreviewPromise = null;
  class BrowserCancelRecognition {
    constructor() {
      this.stopCount = 0;
      browserCancelRecognition = this;
    }
    start() {}
    stop() {
      this.stopCount += 1;
      this.onend?.();
    }
  }
  browserCancelHarness.root.webkitSpeechRecognition = BrowserCancelRecognition;
  const browserCancelPromise = handleVoiceInputClick({
    els: {
      prompt: { value: "取消", focus() {} },
      voiceInput: boundVoiceButton,
      composerStatus: { textContent: "", hidden: true },
    },
    t,
    speechRoot: browserCancelHarness.root,
    getPartialMode: () => "browser",
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: (options) => recordAudio({
      ...options,
      root: browserCancelHarness.root,
      navigatorImpl: {
        mediaDevices: {
          getUserMedia: async () => browserCancelHarness.stream,
        },
      },
      mediaRecorderFactory: (stream) => new FakeMediaRecorder(stream),
    }),
    liveRecorder: (options) => {
      browserCancelPreviewPromise = recordLiveSpeech(options);
      return browserCancelPreviewPromise;
    },
    fetchImpl: async (url) => {
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
      throw new Error("cancel後にfinal requestを送ってはいけない");
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(requestActiveVoiceStop(), true);
  await browserCancelPromise;
  assert.equal(browserCancelRecognition.stopCount, 1);
  await browserCancelPreviewPromise;
  assert.equal(browserCancelHarness.activeTimerCount(), 0);

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
      await onPartialBlob({ type: "audio/webm", size: 12, marker: "partial-1" });
      assert.equal(previewPrompt.value, "既存 予定を");
      await onPartialBlob({ type: "audio/webm", size: 12, marker: "partial-2" });
      assert.equal(previewPrompt.value, "既存 予定を教えて");
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
          text: body.audioBase64 === "partial-1"
            ? "予定を"
            : body.audioBase64 === "partial-2"
              ? "予定を教えて"
              : "最終結果",
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

  let resolveStoppedFinalResponse = null;
  let stoppedFinalSignal = null;
  let stoppedTranscriptCount = 0;
  const stoppedPrompt = { value: "下書き", focus() {} };
  const stoppedFinalPending = new Promise((resolve) => {
    resolveStoppedFinalResponse = resolve;
  });
  const stoppedFinalPromise = handleVoiceInputClick({
    els: { prompt: stoppedPrompt, voiceInput: boundVoiceButton, composerStatus: voiceStatusEl },
    t,
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    getPartialMode: () => "local",
    recorder: async ({ onPartialBlob }) => {
      await onPartialBlob({ type: "audio/webm", size: 12, marker: "stopped-partial" });
      assert.equal(stoppedPrompt.value, "下書き 途中");
      return { type: "audio/webm", size: 24, marker: "stopped-final" };
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
      const body = JSON.parse(options.body);
      if (body.audioBase64 === "stopped-partial") {
        return { ok: true, json: async () => ({ ok: true, text: "途中" }) };
      }
      stoppedFinalSignal = options.signal;
      return stoppedFinalPending;
    },
    onTranscript: () => {
      stoppedTranscriptCount += 1;
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(requestActiveVoiceStop(), true);
  assert.equal(requestActiveVoiceStop(), false);
  assert.equal(stoppedPrompt.value, "下書き");
  assert.equal(stoppedFinalSignal.aborted, true);
  resolveStoppedFinalResponse({
    ok: true,
    json: async () => ({ ok: true, text: "停止後の結果" }),
  });
  await stoppedFinalPromise;
  assert.equal(stoppedTranscriptCount, 0);
  assert.equal(stoppedPrompt.value, "下書き");

  let resolveStaleResponse = null;
  let resolveNewRecorder = null;
  let staleTranscriptCount = 0;
  const staleResponsePending = new Promise((resolve) => {
    resolveStaleResponse = resolve;
  });
  const oldSessionPromise = handleVoiceInputClick({
    els: { prompt: { value: "旧", focus() {} }, voiceInput: boundVoiceButton, composerStatus: voiceStatusEl },
    t,
    getPartialMode: () => "off",
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: async () => ({ type: "audio/webm", size: 24, marker: "old-final" }),
    base64Encoder: async (blob) => blob.marker,
    fetchImpl: async (url) => {
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
      return staleResponsePending;
    },
    onTranscript: () => {
      staleTranscriptCount += 1;
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  const newSessionPromise = handleVoiceInputClick({
    els: { prompt: { value: "新", focus() {} }, voiceInput: boundVoiceButton, composerStatus: voiceStatusEl },
    t,
    getPartialMode: () => "off",
    getSelectedModel: () => "nvidia/nemotron-3.5-asr-streaming-0.6b",
    recorder: () => new Promise((resolve) => {
      resolveNewRecorder = resolve;
    }),
    fetchImpl: async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        available: true,
        runnableModels: ["nvidia/nemotron-3.5-asr-streaming-0.6b"],
        recommendedModel: "nvidia/nemotron-3.5-asr-streaming-0.6b",
      }),
    }),
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  resolveStaleResponse({
    ok: true,
    json: async () => ({ ok: true, text: "古い結果" }),
  });
  await oldSessionPromise;
  assert.equal(staleTranscriptCount, 0);
  assert.equal(requestActiveVoiceStop(), true);
  resolveNewRecorder(null);
  await newSessionPromise;

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

  let delayedRecognition = null;
  class FakeDelayedRecognition {
    constructor() {
      delayedRecognition = this;
    }
    start() {}
    stop() {
      this.onend?.();
    }
  }
  const delayedPrompt = { value: "停止前", focus() {} };
  let allowDelayedPreview = true;
  const delayedResultPromise = recordLiveSpeech({
    els: { prompt: delayedPrompt, voiceInput: liveButton, composerStatus: voiceStatusEl },
    t,
    root: context.window,
    recognitionFactory: FakeDelayedRecognition,
    shouldApplyResult: () => allowDelayedPreview,
  });
  allowDelayedPreview = false;
  delayedRecognition.onresult({
    resultIndex: 0,
    results: [{
      0: { transcript: "停止後の途中結果" },
      length: 1,
      isFinal: true,
    }],
  });
  delayedRecognition.onend();
  await delayedResultPromise;
  assert.equal(delayedPrompt.value, "停止前");

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

  let stoppedStandaloneRecognition = null;
  let stoppedStandaloneHandler = null;
  class FakeStoppedStandaloneRecognition {
    constructor() {
      stoppedStandaloneRecognition = this;
    }
    start() {}
    stop() {}
  }
  const stoppedStandalonePrompt = { value: "停止済み", focus() {} };
  const stoppedStandalonePromise = recordLiveSpeech({
    els: { prompt: stoppedStandalonePrompt, voiceInput: liveButton, composerStatus: voiceStatusEl },
    t,
    root: context.window,
    recognitionFactory: FakeStoppedStandaloneRecognition,
    stopElement: {
      addEventListener(name, handler) {
        if (name === "click") stoppedStandaloneHandler = handler;
      },
      removeEventListener() {},
    },
  });
  stoppedStandaloneHandler();
  stoppedStandaloneRecognition.onresult({
    resultIndex: 0,
    results: [{
      0: { transcript: "遅延結果" },
      length: 1,
      isFinal: true,
    }],
  });
  assert.equal(stoppedStandalonePrompt.value, "停止済み");
  stoppedStandaloneRecognition.onend();
  await stoppedStandalonePromise;

  let settledStandaloneRecognition = null;
  class FakeSettledStandaloneRecognition {
    constructor() {
      settledStandaloneRecognition = this;
    }
    start() {}
    stop() {}
  }
  const settledStandalonePrompt = { value: "完了済み", focus() {} };
  const settledStandalonePromise = recordLiveSpeech({
    els: { prompt: settledStandalonePrompt, voiceInput: liveButton, composerStatus: voiceStatusEl },
    t,
    root: context.window,
    recognitionFactory: FakeSettledStandaloneRecognition,
  });
  settledStandaloneRecognition.onend();
  await settledStandalonePromise;
  settledStandaloneRecognition.onresult({
    resultIndex: 0,
    results: [{
      0: { transcript: "完了後の遅延結果" },
      length: 1,
      isFinal: true,
    }],
  });
  assert.equal(settledStandalonePrompt.value, "完了済み");

  let unsupportedVadTrackStopCount = 0;
  let unsupportedVadRecordStartCount = 0;
  const unsupportedVadStream = {
    getTracks() {
      return [{
        stop() {
          unsupportedVadTrackStopCount += 1;
        },
      }];
    },
  };
  await assert.rejects(recordAudio({
    root: {
      AudioContext: UnsupportedVadAudioContext,
      setInterval,
      clearInterval,
      setTimeout,
      clearTimeout,
    },
    navigatorImpl: {
      mediaDevices: {
        getUserMedia: async () => unsupportedVadStream,
      },
    },
    mediaRecorderFactory: (stream) => {
      const recorder = new FakeMediaRecorder(stream);
      const originalStart = recorder.start.bind(recorder);
      recorder.start = () => {
        unsupportedVadRecordStartCount += 1;
        originalStart();
      };
      return recorder;
    },
  }), /voice activity detection/i);
  assert.equal(unsupportedVadRecordStartCount, 0);
  assert.equal(unsupportedVadTrackStopCount, 1);
  assert.equal(unsupportedVadCloseCount, 2);

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
