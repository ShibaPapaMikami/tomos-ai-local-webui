const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/settings.js", "utf8"), context, { filename: "web/settings.js" });

const { composerModelCandidates, installedOrCurrentModels } = context.window.GEMMA_SETTINGS;

const agenticCoder = "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-GGUF:Q4_K_M";
const legacyCoder = "hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M";
const hauhauBalanced = "hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M";
const huihuiAbliterated = "hf.co/mradermacher/Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated-GGUF:Q4_K_M";
const state = {
  composerModel: "qwen2.5:3b",
  showExperimentalModels: false,
  modelOverrides: {
    chat: "",
    coding: "missing-coder:latest",
    translation: "",
  },
  serverModels: {
    available: [
      "gemma4:12b",
      "qwen2.5:3b",
      agenticCoder,
      hauhauBalanced,
      huihuiAbliterated,
      legacyCoder,
      "llama3:latest",
      "phi3:latest",
      "qwen3:4b",
    ],
    chat: "gemma4:12b",
    coding: agenticCoder,
    translation: "qwen2.5:3b",
    recommendedCoding: [agenticCoder],
    pullable: [{
      model: huihuiAbliterated,
      experimental: true,
      allowAutoSelect: false,
      role: "coding-experimental",
    }],
  },
};
const modelIsInstalled = (model) => state.serverModels.available.includes(model);

assert.deepEqual(
  installedOrCurrentModels({
    models: ["gemma4:12b", "qwen2.5:3b", "llama3:latest"],
    task: "chat",
    state,
    modelIsInstalled,
  }),
  ["gemma4:12b", "qwen2.5:3b", "llama3:latest"],
);

assert.deepEqual(
  installedOrCurrentModels({
    models: ["missing-coder:latest", agenticCoder, "llama3:latest"],
    task: "coding",
    state,
    modelIsInstalled,
  }),
  ["missing-coder:latest", agenticCoder, "llama3:latest"],
);

const composerCandidates = composerModelCandidates({ state, modelIsInstalled });
assert.ok(
  composerCandidates.includes(agenticCoder),
  "agentic coder should be available in the composer model menu",
);
assert.ok(
  composerCandidates.includes(hauhauBalanced),
  "downloaded optional models should be shown in the composer model menu",
);
assert.equal(
  composerCandidates.includes(legacyCoder),
  false,
  "legacy coder should stay out of the composer model menu",
);
assert.equal(
  composerCandidates.includes("llama3:latest"),
  false,
  "llama should stay out of the composer model menu",
);
assert.equal(
  composerCandidates.includes("phi3:latest"),
  false,
  "phi-3 should stay out of the composer model menu",
);
assert.equal(
  composerCandidates.includes("qwen3:4b"),
  false,
  "qwen3 should stay out of the composer model menu",
);
assert.equal(
  composerCandidates.includes(huihuiAbliterated),
  false,
  "experimental models should stay hidden when the experimental toggle is off",
);

const experimentalComposerCandidates = composerModelCandidates({
  state: { ...state, showExperimentalModels: true },
  modelIsInstalled,
});
assert.ok(
  experimentalComposerCandidates.includes(huihuiAbliterated),
  "downloaded experimental models should be shown in the composer model menu only when enabled",
);

console.log("settings helper tests passed");
