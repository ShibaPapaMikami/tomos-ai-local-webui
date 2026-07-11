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
const gemmaMlx = "gemma4:12b-mlx";
const qwen2507 = "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL";
const baseModels = {
  chat: "gemma4:12b",
  coding: coder,
  translation: "qwen2.5:3b",
  available: ["gemma4:12b", "qwen2.5:3b", coder],
};
const mlxModels = {
  ...baseModels,
  available: ["gemma4:12b", gemmaMlx, "qwen2.5:3b", coder],
};

assert.equal(
  modelForTask("chat", { serverModels: baseModels, modelOverrides: {} }),
  "gemma4:12b",
);

assert.equal(
  modelForTask("chat", { serverModels: mlxModels, modelOverrides: {} }),
  gemmaMlx,
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
  fastChatModel({ serverModels: mlxModels }),
  gemmaMlx,
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
  modelForRequestTask("chat", { fastModel: true }, {
    serverModels: mlxModels,
    modelOverrides: {},
  }),
  gemmaMlx,
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
    serverModels: mlxModels,
    modelOverrides: {},
  }),
  gemmaMlx,
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
assert.equal(modelPurpose(gemmaMlx), "Apple Silicon向け高速チャット・コード生成");
assert.equal(modelPurpose("qwen2.5:3b"), "高速チャット・翻訳");
assert.equal(modelPurpose(qwen2507), "軽量標準・資料検索・学習パック");
assert.equal(displayModelName(qwen2507), "Qwen3 4B Instruct 2507");
assert.equal(composerModelLabel(qwen2507, { t: (key) => key }), "Qwen3 2507");
assert.equal(displayModelName("qwen3:4b"), "Qwen3 4B");
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
const appSource = fs.readFileSync("web/app.js", "utf8");
const codingCandidatesBlock = serverSource.match(/CODING_MODEL_CANDIDATES = \[[\s\S]*?\]\n/)?.[0] || "";
assert.match(serverSource, /gemma-4-12B-agentic-fable5-composer2\.5-v2-3\.5x-tau2-GGUF:Q4_K_M/);
assert.match(serverSource, /GEMMA_MLX_MODEL = "gemma4:12b-mlx"/);
assert.match(serverSource, /Gemma 4 12B MLX 高速版/);
assert.match(serverSource, /requiresOllama/);
assert.doesNotMatch(serverSource, /CODING_MODEL_CANDIDATES = \[\s*"hf\.co\/yuxinlu1\/gemma-4-12B-coder-fable5-composer2\.5-v1-GGUF:Q4_K_M"/);
assert.match(serverSource, /HauhauCS\/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M/);
assert.match(serverSource, /hf\.co\/unsloth\/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL/);
assert.doesNotMatch(serverSource, /"model": "Qwen\/Qwen3-4B-Instruct-2507"[\s\S]{0,400}"pullable": False/);
assert.match(serverSource, /"defaultContext": 8192/);
assert.match(serverSource, /"maxContext": 32768/);
assert.match(serverSource, /"advancedContext": 262144/);
assert.match(serverSource, /PULLABLE_MODEL_NAMES = \{item\["model"\] for item in PULLABLE_MODELS if item\["model"\] and item\.get\("pullable"\) is not False\}/);
assert.match(serverSource, /Huihui-gemma-4-12B-coder-fable5-composer2\.5-v1-abliterated-GGUF:Q4_K_M/);
assert.match(serverSource, /"experimental": True/);
assert.match(serverSource, /"defaultVisible": False/);
assert.match(serverSource, /"allowAutoSelect": False/);
assert.match(serverSource, /"safetyLevel": "low"/);
assert.match(serverSource, /"external-send-check"/);
assert.doesNotMatch(codingCandidatesBlock, /Huihui-gemma-4-12B-coder-fable5-composer2\.5-v1-abliterated/);
assert.doesNotMatch(serverSource, /recommendedCodingModels[\s\S]{0,260}Huihui-gemma-4-12B-coder-fable5-composer2\.5-v1-abliterated/);
assert.match(indexSource, /\/i18n\.js\?v=0\.8\.212-local-ai-status/);
assert.match(indexSource, /\/utils\.js\?v=0\.8\.209-tomos53/);
assert.match(indexSource, /\/models\.js\?v=0\.8\.209-tomos53/);
assert.match(indexSource, /\/settings\.js\?v=0\.8\.209-tomos53/);
assert.match(indexSource, /\/management\.js\?v=0\.8\.209-tomos53/);
assert.match(indexSource, /\/app\.js\?v=0\.8\.212-local-ai-status/);
assert.match(serviceWorkerSource, /gemma4-pwa-0\.8\.212-local-ai-status/);
assert.match(serviceWorkerSource, /\/i18n\.js\?v=0\.8\.212-local-ai-status/);
assert.match(serviceWorkerSource, /\/utils\.js\?v=0\.8\.209-tomos53/);
assert.match(serviceWorkerSource, /\/models\.js\?v=0\.8\.209-tomos53/);
assert.match(serviceWorkerSource, /\/settings\.js\?v=0\.8\.209-tomos53/);
assert.match(serviceWorkerSource, /\/management\.js\?v=0\.8\.209-tomos53/);
assert.match(serviceWorkerSource, /\/app\.js\?v=0\.8\.212-local-ai-status/);
assert.match(fs.readFileSync("web/i18n.js", "utf8"), /"settings\.chatModel": "通常チャットAIモデル"/);
assert.match(fs.readFileSync("web/i18n.js", "utf8"), /"settings\.codingModel": "プログラミング用AIモデル"/);
assert.match(fs.readFileSync("web/i18n.js", "utf8"), /"settings\.translationModel": "翻訳AIモデル"/);
assert.match(stylesSource, /\.settings-panel \.model-experimental-toggle/);
assert.match(stylesSource, /\.management-panel \.model-experimental-toggle/);
assert.match(stylesSource, /\.model-installer > \.model-experimental-toggle/);
assert.match(stylesSource, /\.model-experimental-toggle-inline/);
assert.match(stylesSource, /input\[type="checkbox"\]/);
assert.match(stylesSource, /width: 13px/);
assert.match(stylesSource, /white-space: nowrap/);
assert.match(stylesSource, /gap: 4px/);
assert.match(stylesSource, /margin: 0/);

const indexHtml = fs.readFileSync("web/index.html", "utf8");
const i18nSource = fs.readFileSync("web/i18n.js", "utf8");
assert.match(indexHtml, /別のローカルAIを使う/);
assert.match(indexHtml, /<details class="external-llm-details">/);
assert.match(indexHtml, /TOMOS標準のローカルAIを使用中/);
assert.match(i18nSource, /"settings\.externalLlmTitle": "別のローカルAIを使う"/);
assert.match(i18nSource, /"settings\.externalLlmClear": "標準に戻す"/);
assert.match(i18nSource, /"settings\.externalLlmPending": "保存済みです。接続を確認してください。"/);
assert.match(
  appSource,
  /state\.externalLlmUrl \? t\("settings\.externalLlmPending"\) : t\("settings\.externalLlmIdle"\)/,
);
assert.match(indexHtml, /<details class="external-llm-details">[\s\S]*external-llm-guide/);
assert.doesNotMatch(indexHtml, /外部LLM接続/);
assert.doesNotMatch(i18nSource, /外部LLM接続/);

const experimentalPullable = [
  { model: "gemma4:12b", label: "Gemma 4 12B", purpose: "標準チャット・画像理解", family: "Gemma系" },
  { model: gemmaMlx, label: "Gemma 4 12B MLX 高速版", purpose: "Apple Silicon向け高速チャット・コード生成", family: "Gemma系" },
  { model: coder, label: "Gemma 4 Agentic Coder 12B Q4", purpose: "コード生成・修正・デバッグ", family: "Gemma系" },
  { model: "qwen2.5:3b", label: "Qwen 2.5 3B", purpose: "高速チャット・翻訳", family: "Qwen系" },
  {
    model: qwen2507,
    label: "Qwen3 4B Instruct 2507",
    purpose: "軽量標準・資料検索・学習パック",
    family: "Qwen系",
    note: "Qwen公式モデルのUnsloth GGUF量子化版です。既存の qwen3:4b とは別候補です。",
  },
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
const installerT = (key) => ({
  "settings.modelDownload": "モデルをダウンロード",
  "model.installed": "ダウンロード済み",
  "model.downloading": "ダウンロード中",
  "model.download": "ダウンロード",
  "error.prefix": "エラー",
}[key] || key);
const hiddenInstaller = new FakeElement("section");
renderInstaller({
  composerModelLabel,
  els: { modelInstaller: hiddenInstaller },
  modelIsInstalled: (model) => model === "qwen2.5:3b" || model === gemmaMlx || model === coder,
  state: {
    language: "ja",
    appInfo: { pcDiagnostics: { system: { isAppleSilicon: true } } },
    serverModels: { pullable: experimentalPullable },
    modelPullJobs: {},
    showExperimentalModels: false,
  },
  t: installerT,
});
assert.doesNotMatch(hiddenInstaller.innerHTML, /Huihui Gemma 4 Coder 12B Abliterated[\s\S]{0,240}model-recommended-card/);
assert.match(hiddenInstaller.innerHTML, /おすすめモデル/);
assert.match(hiddenInstaller.innerHTML, /軽量AIモデル/);
assert.match(hiddenInstaller.innerHTML, /Qwen 2.5 3B/);
assert.match(hiddenInstaller.innerHTML, /高性能AIモデル/);
assert.match(hiddenInstaller.innerHTML, /Gemma 4 12B MLX 高速版/);
assert.match(hiddenInstaller.innerHTML, /プログラミング用AIモデル/);
assert.match(hiddenInstaller.innerHTML, /Gemma 4 Agentic Coder 12B Q4/);
assert.match(hiddenInstaller.innerHTML, /翻訳AIモデル/);
assert.match(hiddenInstaller.innerHTML, /ダウンロード済み/);
assert.doesNotMatch(hiddenInstaller.innerHTML, /使用中/);
assert.match(hiddenInstaller.innerHTML, /アンインストール/);
assert.doesNotMatch(hiddenInstaller.innerHTML, /Qwen3 4B Instruct 2507[\s\S]{0,240}model-recommended-card/);
assert.match(hiddenInstaller.innerHTML, /詳細モデルを表示/);
assert.match(hiddenInstaller.innerHTML, /実験モデルを表示/);
assert.match(hiddenInstaller.innerHTML, /Qwen3 4B Instruct 2507/);
assert.match(hiddenInstaller.innerHTML, /軽量標準・資料検索・学習パック/);
assert.match(hiddenInstaller.innerHTML, /Qwen公式モデルのUnsloth GGUF量子化版です。既存の qwen3:4b とは別候補です。/);
assert.match(hiddenInstaller.innerHTML, /Qwen3 4B Instruct 2507[\s\S]{0,500}ダウンロード/);

const visibleInstaller = new FakeElement("section");
renderInstaller({
  composerModelLabel,
  els: { modelInstaller: visibleInstaller },
  modelIsInstalled: () => false,
  state: { language: "ja", serverModels: { pullable: experimentalPullable }, modelPullJobs: {}, showExperimentalModels: true },
  t: installerT,
});
assert.match(visibleInstaller.innerHTML, /Huihui Gemma 4 Coder 12B Abliterated/);
assert.match(visibleInstaller.innerHTML, /コード実験・制限弱め・上級者向け/);
assert.match(visibleInstaller.innerHTML, /学生向け標準、社内文書、外部送信前チェックには推奨しません/);

const windowsInstaller = new FakeElement("section");
renderInstaller({
  composerModelLabel,
  els: { modelInstaller: windowsInstaller },
  modelIsInstalled: (model) => model === "qwen2.5:3b",
  state: {
    language: "ja",
    appInfo: { pcDiagnostics: { system: { isAppleSilicon: false } } },
    serverModels: { pullable: experimentalPullable },
    modelPullJobs: {},
    showExperimentalModels: false,
  },
  t: installerT,
});
assert.match(windowsInstaller.innerHTML, /高性能AIモデル/);
assert.match(windowsInstaller.innerHTML, /Gemma 4 12B/);
const windowsRecommendedOnly = windowsInstaller.innerHTML.split("詳細モデルを表示")[0];
assert.doesNotMatch(windowsRecommendedOnly, /MLX 高速版/);
const hiddenComposerCandidates = settingsContext.window.GEMMA_SETTINGS.composerModelCandidates({
  state: {
    composerModel: huihuiAbliterated,
    serverModels: {
      chat: "gemma4:12b",
      coding: coder,
      translation: "qwen2.5:3b",
      recommendedCoding: [gemmaMlx, coder],
      pullable: experimentalPullable,
    },
    showExperimentalModels: false,
  },
  modelIsInstalled: (model) => model === huihuiAbliterated || model === "gemma4:12b" || model === coder || model === "qwen2.5:3b",
});
assert.equal(hiddenComposerCandidates.includes(huihuiAbliterated), false);
assert.equal(hiddenComposerCandidates.includes(gemmaMlx), true);
assert.equal(hiddenComposerCandidates.includes(qwen2507), false);
const visibleComposerCandidates = settingsContext.window.GEMMA_SETTINGS.composerModelCandidates({
  state: {
    composerModel: "",
    serverModels: {
      chat: "gemma4:12b",
      coding: coder,
      translation: "qwen2.5:3b",
      recommendedCoding: [gemmaMlx, coder],
      pullable: experimentalPullable,
    },
    showExperimentalModels: true,
  },
  modelIsInstalled: (model) => model === huihuiAbliterated || model === "gemma4:12b" || model === coder || model === "qwen2.5:3b",
});
assert.equal(visibleComposerCandidates.includes(huihuiAbliterated), true);
assert.equal(visibleComposerCandidates.includes(qwen2507), false);
assert.equal(composerModelLabel(gemmaMlx, { t: (key) => key }), "Gemma 4 MLX");
assert.equal(composerModelLabel(huihuiAbliterated, { t: (key) => key }), "Huihui 実験");

const chatSelect = new FakeElement("select");
settingsContext.window.GEMMA_SETTINGS.renderModelSettingsSelects({
  composerModelLabel,
  displayModelName,
  els: {
    chatModel: chatSelect,
    codingModel: new FakeElement("select"),
    translationModel: new FakeElement("select"),
    composerModel: new FakeElement("select"),
  },
  modelIsInstalled: (model) => model === gemmaMlx || model === "gemma4:12b" || model === "qwen2.5:3b",
  state: {
    composerModel: "",
    modelOverrides: {},
    serverModels: {
      chat: "gemma4:12b",
      coding: coder,
      translation: "qwen2.5:3b",
      recommendedCoding: [gemmaMlx, coder],
      pullable: experimentalPullable,
    },
    showExperimentalModels: false,
  },
  t: (key) => key,
});
assert.equal(chatSelect.children.some((option) => option.value === gemmaMlx), true);
assert.equal(chatSelect.children.some((option) => option.value === qwen2507), false);

const chatSelectWithQwen = new FakeElement("select");
settingsContext.window.GEMMA_SETTINGS.renderModelSettingsSelects({
  composerModelLabel,
  displayModelName,
  els: {
    chatModel: chatSelectWithQwen,
    codingModel: new FakeElement("select"),
    translationModel: new FakeElement("select"),
    composerModel: new FakeElement("select"),
  },
  modelIsInstalled: (model) => model === gemmaMlx || model === "gemma4:12b" || model === "qwen2.5:3b" || model === qwen2507,
  state: {
    composerModel: "",
    modelOverrides: {},
    serverModels: {
      chat: "gemma4:12b",
      coding: coder,
      translation: "qwen2.5:3b",
      recommendedCoding: [gemmaMlx, coder],
      pullable: experimentalPullable,
    },
    showExperimentalModels: false,
  },
  t: (key) => key,
});
assert.equal(chatSelectWithQwen.children.some((option) => option.value === qwen2507), true);

console.log("model selection tests passed");
