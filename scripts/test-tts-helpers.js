const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = {
  AbortController,
  Blob,
  TextDecoder,
  TextEncoder,
  Uint8Array,
  Int16Array,
  Float32Array,
  atob,
  window: { atob },
  console,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/tts.js", "utf8"), context, { filename: "web/tts.js" });

const {
  createTtsController,
  defaultTtsSettings,
  normalizeTtsText,
  shouldApplyTtsResult,
  validateTtsStreamEvent,
} = context.window.GEMMA_TTS;

assert.equal(normalizeTtsText("  こんにちは\n\n世界  "), "こんにちは\n世界");
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
assert.equal(validateTtsStreamEvent({
  type: "done",
  requestId: "tts-2",
  chunks: 1,
}, {
  activeRequestId: "tts-2",
  expectedSequence: 2,
}).ok, false);

async function testStopCancelsOnlyOnce() {
  const calls = [];
  const controller = createTtsController({
    fetchImpl: async (url, options = {}) => {
      calls.push({ url, options });
      if (url === "/api/tts/synthesize") {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            requestId: "tts-1",
            audio: {
              mimeType: "audio/wav",
              base64: "UklGRg==",
              durationMs: 1,
              sampleRate: 24000,
            },
          }),
        };
      }
      return { ok: true, json: async () => ({ ok: true }) };
    },
    AudioClass: class {
      play() { return Promise.resolve(); }
      pause() {}
    },
    URLImpl: {
      createObjectURL: () => "blob:tts",
      revokeObjectURL() {},
    },
  });
  await controller.play({
    requestId: "tts-1",
    text: "こんにちは",
    voice: "default",
    language: "ja",
    supportsStreaming: false,
  });
  controller.stop();
  controller.stop();
  await Promise.resolve();
  const cancels = calls.filter((call) => call.url === "/api/tts/cancel");
  assert.equal(cancels.length, 1);
}

async function testStreamingCompletesAfterScheduledAudioEnds() {
  const states = [];
  const sources = [];
  class FakeAudioContext {
    constructor() {
      this.currentTime = 0;
      this.destination = {};
    }
    createBuffer(_channels, length, sampleRate) {
      return {
        duration: length / sampleRate,
        copyToChannel() {},
      };
    }
    createBufferSource() {
      const source = {
        connect() {},
        start() {},
        stop() {},
        onended: null,
      };
      sources.push(source);
      return source;
    }
    close() { return Promise.resolve(); }
  }
  const lines = [
    { type: "start", requestId: "tts-stream", mimeType: "audio/pcm;codec=s16le", sampleRate: 24000, channels: 1 },
    { type: "audio", requestId: "tts-stream", sequence: 0, audioBase64: "AAAAAA==" },
    { type: "done", requestId: "tts-stream", chunks: 1, durationMs: 1 },
  ].map((event) => JSON.stringify(event)).join("\n") + "\n";
  let read = false;
  const controller = createTtsController({
    fetchImpl: async (url) => {
      if (url === "/api/tts/cancel") return { ok: true, json: async () => ({ ok: true }) };
      return {
        ok: true,
        body: {
          getReader: () => ({
            read: async () => {
              if (read) return { value: undefined, done: true };
              read = true;
              return { value: new TextEncoder().encode(lines), done: false };
            },
          }),
        },
      };
    },
    AudioContextClass: FakeAudioContext,
    onStateChange: ({ status }) => states.push(status),
  });
  await controller.play({
    requestId: "tts-stream",
    text: "こんにちは",
    voice: "default",
    language: "ja",
    supportsStreaming: true,
  });
  assert.equal(states.at(-1), "playing");
  sources.at(-1).onended();
  assert.equal(states.at(-1), "completed");
}

async function testStreamingRejectsMissingDone() {
  const lines = [
    { type: "start", requestId: "tts-incomplete", mimeType: "audio/pcm;codec=s16le", sampleRate: 24000, channels: 1 },
  ].map((event) => JSON.stringify(event)).join("\n") + "\n";
  let read = false;
  const controller = createTtsController({
    fetchImpl: async (url) => {
      if (url === "/api/tts/cancel") return { ok: true, json: async () => ({ ok: true }) };
      return {
        ok: true,
        body: {
          getReader: () => ({
            read: async () => {
              if (read) return { value: undefined, done: true };
              read = true;
              return { value: new TextEncoder().encode(lines), done: false };
            },
          }),
        },
      };
    },
  });
  await assert.rejects(controller.play({
    requestId: "tts-incomplete",
    text: "こんにちは",
    voice: "default",
    language: "ja",
    supportsStreaming: true,
  }), /tts_stream_incomplete/);
}

async function testStreamingRejectsEventAfterDone() {
  const lines = [
    { type: "start", requestId: "tts-terminal", mimeType: "audio/pcm;codec=s16le", sampleRate: 24000, channels: 1 },
    { type: "done", requestId: "tts-terminal", chunks: 0, durationMs: 0 },
    { type: "done", requestId: "tts-terminal", chunks: 0, durationMs: 0 },
  ].map((event) => JSON.stringify(event)).join("\n") + "\n";
  let read = false;
  const controller = createTtsController({
    fetchImpl: async (url) => {
      if (url === "/api/tts/cancel") return { ok: true, json: async () => ({ ok: true }) };
      return {
        ok: true,
        body: {
          getReader: () => ({
            read: async () => {
              if (read) return { value: undefined, done: true };
              read = true;
              return { value: new TextEncoder().encode(lines), done: false };
            },
          }),
        },
      };
    },
  });
  await assert.rejects(controller.play({
    requestId: "tts-terminal",
    text: "こんにちは",
    voice: "default",
    language: "ja",
    supportsStreaming: true,
  }), /tts_stream_terminal_invalid/);
}

Promise.all([
  testStopCancelsOnlyOnce(),
  testStreamingCompletesAfterScheduledAudioEnds(),
  testStreamingRejectsMissingDone(),
  testStreamingRejectsEventAfterDone(),
])
  .then(() => console.log("tts helper tests passed"))
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
