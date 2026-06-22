const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/models.js", "utf8"), context, { filename: "web/models.js" });

const {
  modelForTask,
  modelForRequestTask,
  fastChatModel,
  fallbackCodingModel,
} = context.window.GEMMA_MODELS;

const coder = "hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M";
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

console.log("model selection tests passed");
