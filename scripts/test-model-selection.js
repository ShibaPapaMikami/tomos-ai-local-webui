const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/models.js", "utf8"), context, { filename: "web/models.js" });

const {
  displayModelName,
  composerModelLabel,
  modelPurpose,
  modelForTask,
  modelForRequestTask,
  fastChatModel,
  fallbackCodingModel,
} = context.window.GEMMA_MODELS;

const coder = "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M";
const hauhauBalanced = "hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M";
const baseModels = {
  chat: "gemma4:12b",
  coding: coder,
  translation: "qwen2.5:3b",
  available: ["gemma4:12b", "qwen2.5:3b", coder],
};

assert.equal(
  modelForTask("chat", { serverModels: baseModels, modelOverrides: {} }),
  "gemma4:12b",
);

assert.equal(
  modelForTask("coding", { serverModels: baseModels, modelOverrides: {} }),
  coder,
);

assert.equal(
  modelForTask("coding", {
    serverModels: baseModels,
    modelOverrides: { coding: "gemma4:12b" },
  }),
  "gemma4:12b",
);

assert.equal(
  modelForTask("chat", {
    useComposer: true,
    composerModel: "qwen2.5:3b",
    serverModels: baseModels,
    modelOverrides: {},
  }),
  "qwen2.5:3b",
);

assert.equal(
  fallbackCodingModel({ serverModels: { chat: "gemma4:12b" } }),
  "gemma4:12b",
);

assert.equal(
  fastChatModel({ serverModels: baseModels }),
  "qwen2.5:3b",
);

assert.equal(
  fastChatModel({ serverModels: { chat: "gemma4:12b", available: ["gemma4:12b"] } }),
  "gemma4:12b",
);

assert.equal(
  modelForRequestTask("chat", { fastModel: true }, {
    serverModels: baseModels,
    modelOverrides: {},
  }),
  "qwen2.5:3b",
);

assert.equal(
  modelForRequestTask("translation", { responseMode: "quality" }, {
    serverModels: baseModels,
    modelOverrides: {},
  }),
  "gemma4:12b",
);

assert.equal(
  modelForRequestTask("translation", { responseMode: "quality" }, {
    serverModels: baseModels,
    modelOverrides: { translation: "qwen2.5:3b" },
  }),
  "qwen2.5:3b",
);

assert.equal(
  modelForRequestTask("coding", { responseMode: "quality" }, {
    composerModel: "gemma4:12b",
    serverModels: baseModels,
    modelOverrides: {},
  }),
  "gemma4:12b",
);

assert.match(
  displayModelName(coder, "coding", { t: (key) => key, modelIsInstalled: () => false }),
  /Gemma 4 Agentic Coder 12B Q4/,
);
assert.equal(composerModelLabel(coder, { t: (key) => key }), "Agentic Coder");
assert.match(
  displayModelName(hauhauBalanced, "chat", { t: (key) => key, modelIsInstalled: () => false }),
  /HauhauCS Balanced 12B Q4/,
);
assert.match(
  displayModelName(hauhauBalanced, "chat", { t: (key) => key, modelIsInstalled: () => false }),
  /model.downloadRequired/,
);
assert.equal(
  displayModelName(hauhauBalanced, "chat", { t: (key) => key, modelIsInstalled: () => true }),
  "HauhauCS Balanced 12B Q4",
);
assert.equal(composerModelLabel(hauhauBalanced, { t: (key) => key }), "HauhauCS");
assert.equal(typeof modelPurpose, "function");
assert.equal(modelPurpose("gemma4:12b"), "標準チャット・画像理解");
assert.equal(modelPurpose("qwen2.5:3b"), "高速チャット・翻訳");
assert.equal(modelPurpose(coder), "コード生成・修正・デバッグ");
assert.equal(
  modelPurpose("hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M"),
  "コード生成・修正・デバッグ",
);
assert.equal(modelPurpose(hauhauBalanced), "強化型チャット・制限弱め・PC負荷強");
assert.equal(
  modelPurpose("custom:latest", "chat", { pullable: [{ model: "custom:latest", purpose: "独自モデル" }] }),
  "独自モデル",
);

const serverSource = fs.readFileSync("server.py", "utf8");
assert.match(serverSource, /gemma-4-12B-agentic-fable5-composer2\.5-v2-3\.5x-tau2-GGUF:Q4_K_M/);
assert.doesNotMatch(serverSource, /CODING_MODEL_CANDIDATES = \[\s*"hf\.co\/yuxinlu1\/gemma-4-12B-coder-fable5-composer2\.5-v1-GGUF:Q4_K_M"/);
assert.match(serverSource, /HauhauCS\/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M/);

console.log("model selection tests passed");
