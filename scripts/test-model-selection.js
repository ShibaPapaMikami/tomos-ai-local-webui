const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/models.js", "utf8"), context, { filename: "web/models.js" });

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.dataset = {};
    this.className = "";
    this.textContent = "";
    this.type = "";
    this.checked = false;
    this.disabled = false;
  }
  append(...items) {
    this.children.push(...items);
  }
  set innerHTML(value) {
    this.children = [];
    this._innerHTML = String(value);
  }
  get innerHTML() {
    return `${this._innerHTML || ""}${this.textContent || ""}${this.children.map((child) => (
      typeof child === "string" ? child : child.innerHTML
    )).join("")}`;
  }
}

const settingsContext = {
  window: {},
  document: { createElement: (tag) => new FakeElement(tag) },
  console,
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) }),
};
vm.createContext(settingsContext);
vm.runInContext(fs.readFileSync("web/settings.js", "utf8"), settingsContext, { filename: "web/settings.js" });

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
const huihuiAbliterated = "hf.co/mradermacher/Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated-GGUF:Q4_K_M";
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
const indexSource = fs.readFileSync("web/index.html", "utf8");
const serviceWorkerSource = fs.readFileSync("web/sw.js", "utf8");
const stylesSource = fs.readFileSync("web/styles.css", "utf8");
const codingCandidatesBlock = serverSource.match(/CODING_MODEL_CANDIDATES = \[[\s\S]*?\]\n/)?.[0] || "";
assert.match(serverSource, /gemma-4-12B-agentic-fable5-composer2\.5-v2-3\.5x-tau2-GGUF:Q4_K_M/);
assert.doesNotMatch(serverSource, /CODING_MODEL_CANDIDATES = \[\s*"hf\.co\/yuxinlu1\/gemma-4-12B-coder-fable5-composer2\.5-v1-GGUF:Q4_K_M"/);
assert.match(serverSource, /HauhauCS\/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M/);
assert.match(serverSource, /Huihui-gemma-4-12B-coder-fable5-composer2\.5-v1-abliterated-GGUF:Q4_K_M/);
assert.match(serverSource, /"experimental": True/);
assert.match(serverSource, /"defaultVisible": False/);
assert.match(serverSource, /"allowAutoSelect": False/);
assert.match(serverSource, /"safetyLevel": "low"/);
assert.match(serverSource, /"external-send-check"/);
assert.doesNotMatch(codingCandidatesBlock, /Huihui-gemma-4-12B-coder-fable5-composer2\.5-v1-abliterated/);
assert.doesNotMatch(serverSource, /recommendedCodingModels[\s\S]{0,260}Huihui-gemma-4-12B-coder-fable5-composer2\.5-v1-abliterated/);
assert.match(indexSource, /\/i18n\.js\?v=0\.8\.197-huihui-composer1/);
assert.match(indexSource, /\/utils\.js\?v=0\.8\.197-japanese-spacing1/);
assert.match(indexSource, /\/models\.js\?v=0\.8\.197-huihui-composer1/);
assert.match(indexSource, /\/settings\.js\?v=0\.8\.197-huihui-composer1/);
assert.match(indexSource, /\/management\.js\?v=0\.8\.197-study-pack-persist1/);
assert.match(indexSource, /\/app\.js\?v=0\.8\.197-study-pack-persist1/);
assert.match(serviceWorkerSource, /gemma4-pwa-0\.8\.197-study-pack-persist1/);
assert.match(serviceWorkerSource, /\/i18n\.js\?v=0\.8\.197-huihui-composer1/);
assert.match(serviceWorkerSource, /\/utils\.js\?v=0\.8\.197-japanese-spacing1/);
assert.match(serviceWorkerSource, /\/models\.js\?v=0\.8\.197-huihui-composer1/);
assert.match(serviceWorkerSource, /\/settings\.js\?v=0\.8\.197-huihui-composer1/);
assert.match(serviceWorkerSource, /\/management\.js\?v=0\.8\.197-study-pack-persist1/);
assert.match(serviceWorkerSource, /\/app\.js\?v=0\.8\.197-study-pack-persist1/);
assert.match(stylesSource, /\.settings-panel \.model-experimental-toggle/);
assert.match(stylesSource, /\.management-panel \.model-experimental-toggle/);
assert.match(stylesSource, /\.model-installer > \.model-experimental-toggle/);
assert.match(stylesSource, /\.model-experimental-toggle-inline/);
assert.match(stylesSource, /input\[type="checkbox"\]/);
assert.match(stylesSource, /width: 13px/);
assert.match(stylesSource, /white-space: nowrap/);
assert.match(stylesSource, /gap: 4px/);
assert.match(stylesSource, /margin: 0/);

const experimentalPullable = [
  { model: "gemma4:12b", label: "Gemma 4 12B", purpose: "標準チャット・画像理解", family: "Gemma系" },
  {
    model: huihuiAbliterated,
    label: "Huihui Gemma 4 Coder 12B Abliterated",
    purpose: "コード実験・制限弱め・上級者向け",
    family: "実験モデル",
    role: "coding-experimental",
    experimental: true,
    defaultVisible: false,
    allowAutoSelect: false,
    safetyLevel: "low",
    blockedFor: ["student-default", "company-documents", "external-send-check", "study-pack-default", "adult-mode-default"],
    warning: "通常の安全調整が弱い可能性があります。学生向け標準、社内文書、外部送信前チェックには推奨しません。",
  },
];
const renderInstaller = settingsContext.window.GEMMA_SETTINGS.renderModelInstaller;
const hiddenInstaller = new FakeElement("section");
renderInstaller({
  composerModelLabel,
  els: { modelInstaller: hiddenInstaller },
  modelIsInstalled: () => false,
  state: { language: "ja", serverModels: { pullable: experimentalPullable }, modelPullJobs: {}, showExperimentalModels: false },
  t: (key) => key,
});
assert.doesNotMatch(hiddenInstaller.innerHTML, /Huihui Gemma 4 Coder 12B Abliterated/);
assert.match(hiddenInstaller.innerHTML, /実験モデルを表示/);

const visibleInstaller = new FakeElement("section");
renderInstaller({
  composerModelLabel,
  els: { modelInstaller: visibleInstaller },
  modelIsInstalled: () => false,
  state: { language: "ja", serverModels: { pullable: experimentalPullable }, modelPullJobs: {}, showExperimentalModels: true },
  t: (key) => key,
});
assert.match(visibleInstaller.innerHTML, /Huihui Gemma 4 Coder 12B Abliterated/);
assert.match(visibleInstaller.innerHTML, /コード実験・制限弱め・上級者向け/);
assert.match(visibleInstaller.innerHTML, /学生向け標準、社内文書、外部送信前チェックには推奨しません/);
const hiddenComposerCandidates = settingsContext.window.GEMMA_SETTINGS.composerModelCandidates({
  state: {
    composerModel: huihuiAbliterated,
    serverModels: {
      chat: "gemma4:12b",
      coding: coder,
      translation: "qwen2.5:3b",
      recommendedCoding: [coder],
      pullable: experimentalPullable,
    },
    showExperimentalModels: false,
  },
  modelIsInstalled: (model) => model === huihuiAbliterated || model === "gemma4:12b" || model === coder || model === "qwen2.5:3b",
});
assert.equal(hiddenComposerCandidates.includes(huihuiAbliterated), false);
const visibleComposerCandidates = settingsContext.window.GEMMA_SETTINGS.composerModelCandidates({
  state: {
    composerModel: "",
    serverModels: {
      chat: "gemma4:12b",
      coding: coder,
      translation: "qwen2.5:3b",
      recommendedCoding: [coder],
      pullable: experimentalPullable,
    },
    showExperimentalModels: true,
  },
  modelIsInstalled: (model) => model === huihuiAbliterated || model === "gemma4:12b" || model === coder || model === "qwen2.5:3b",
});
assert.equal(visibleComposerCandidates.includes(huihuiAbliterated), true);
assert.equal(composerModelLabel(huihuiAbliterated, { t: (key) => key }), "Huihui 実験");

console.log("model selection tests passed");
