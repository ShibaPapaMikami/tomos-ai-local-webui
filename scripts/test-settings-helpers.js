const fs = require("node:fs");
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/settings.js", "utf8"), context, { filename: "web/settings.js" });

const {
  composerModelCandidates,
  externalLlmCheckStatusKey,
  installedOrCurrentModels,
  renderComposerModelVisibility,
  renderModelInstaller,
  renderModelSettingsSelects,
  renderPcDiagnosticsPanel,
} = context.window.GEMMA_SETTINGS;
const { renderSettingsMeta } = context.window.GEMMA_SETTINGS;

const serverPullableModels = JSON.parse(execFileSync(
  "python3",
  ["-c", "import json; import server; print(json.dumps(server.PULLABLE_MODELS))"],
  { encoding: "utf8" },
));
const modelById = new Map(serverPullableModels.map((item) => [item.model, item]));
const qwen2507 = serverPullableModels.find((item) => item.role === "core")?.model;
const agenticCoder = serverPullableModels.find((item) => item.role === "developer")?.model;
const legacyCoder = "hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M";
const hauhauBalanced = serverPullableModels.find((item) => item.model.includes("HauhauCS"))?.model;
const huihuiAbliterated = serverPullableModels.find((item) => item.model.includes("Huihui"))?.model;
assert.equal(modelById.get(hauhauBalanced)?.role, "developer-hidden");
assert.equal(modelById.get(huihuiAbliterated)?.role, "coding-experimental");
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
    pullable: serverPullableModels,
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
  ["gemma4:12b", "qwen2.5:3b"],
);

assert.deepEqual(
  installedOrCurrentModels({
    models: ["missing-coder:latest", agenticCoder, "llama3:latest"],
    task: "coding",
    state,
    modelIsInstalled,
  }),
  ["missing-coder:latest", agenticCoder],
);

const composerCandidates = composerModelCandidates({ state, modelIsInstalled });
assert.ok(
  composerCandidates.includes(agenticCoder),
  "agentic coder should be available in the composer model menu",
);
assert.equal(
  composerCandidates.includes(hauhauBalanced),
  false,
  "student-hidden models should stay out of the composer model menu",
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
assert.equal(
  experimentalComposerCandidates.includes(huihuiAbliterated),
  false,
  "取得済みHuihuiは実験表示状態でも学生の通常チャット候補へ出さない",
);

const filteredComposerCandidates = composerModelCandidates({
  state: {
    ...state,
    composerModelVisibleModels: ["qwen2.5:3b"],
    composerModelVisibleModelsSaved: true,
  },
  modelIsInstalled,
});
assert.equal(JSON.stringify(filteredComposerCandidates), JSON.stringify(["qwen2.5:3b"]));

const clearedComposerCandidates = composerModelCandidates({
  state: {
    ...state,
    composerModelVisibleModels: [],
    composerModelVisibleModelsSaved: true,
  },
  modelIsInstalled,
});
assert.equal(JSON.stringify(clearedComposerCandidates), JSON.stringify(["qwen2.5:3b"]));

assert.equal(externalLlmCheckStatusKey("invalid_url"), "settings.externalLlmInvalidUrl");
assert.equal(externalLlmCheckStatusKey("non_local_url"), "settings.externalLlmLocalOnly");
assert.equal(externalLlmCheckStatusKey("connection_failed"), "settings.externalLlmError");
assert.equal(externalLlmCheckStatusKey("unexpected"), "settings.externalLlmError");

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.attributes = {};
    this.textContent = "";
    this._innerHTML = "";
  }
  set innerHTML(value) {
    this._innerHTML = String(value);
    this.children = [];
  }
  get innerHTML() {
    return `${this._innerHTML}${this.children.map((child) => child.outerHTML || child.textContent || "").join("")}`;
  }
  append(...children) {
    this.children.push(...children);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  get outerHTML() {
    const classAttr = this.className ? ` class="${this.className}"` : "";
    return `<${this.tagName.toLowerCase()}${classAttr}>${this.textContent}${this.innerHTML}</${this.tagName.toLowerCase()}>`;
  }
}

context.document = {
  createElement(tagName) {
    return new FakeElement(tagName);
  },
};

const enterpriseHealthModel = "enterprise:health-model";
const healthModelIds = [hauhauBalanced, huihuiAbliterated, enterpriseHealthModel];
const healthState = {
  ...state,
  composerModel: "",
  modelOverrides: {},
  serverModels: {
    ...state.serverModels,
    available: [...state.serverModels.available, enterpriseHealthModel],
    chat: hauhauBalanced,
    coding: huihuiAbliterated,
    translation: enterpriseHealthModel,
    recommendedCoding: [hauhauBalanced, huihuiAbliterated, enterpriseHealthModel, agenticCoder],
    pullable: [
      ...serverPullableModels,
      {
        model: enterpriseHealthModel,
        role: "enterprise",
        tier: "enterprise",
        defaultVisible: false,
        allowAutoSelect: false,
      },
    ],
  },
};
const healthChatSelect = new FakeElement("select");
const healthCodingSelect = new FakeElement("select");
const healthTranslationSelect = new FakeElement("select");
renderModelSettingsSelects({
  composerModelLabel: (model) => model,
  displayModelName: (model) => model,
  els: {
    chatModel: healthChatSelect,
    codingModel: healthCodingSelect,
    translationModel: healthTranslationSelect,
    composerModel: new FakeElement("select"),
  },
  modelIsInstalled: (model) => healthState.serverModels.available.includes(model),
  state: healthState,
  t: (key) => key,
});
for (const select of [healthChatSelect, healthCodingSelect, healthTranslationSelect]) {
  for (const model of healthModelIds) {
    assert.equal(
      select.children.some((option) => option.value === model),
      false,
      `health由来の学生非表示モデル ${model} を通常候補へ表示しない`,
    );
  }
}

const unclassifiedEnterpriseModels = ["glm-5:latest", "gpt-oss:120b", "deepseek-r1:latest"];
const unclassifiedEnterpriseHealthState = {
  ...state,
  composerModel: "",
  modelOverrides: {
    chat: unclassifiedEnterpriseModels[0],
    coding: unclassifiedEnterpriseModels[1],
    translation: unclassifiedEnterpriseModels[2],
  },
  serverModels: {
    ...state.serverModels,
    available: [...state.serverModels.available, ...unclassifiedEnterpriseModels],
    chat: unclassifiedEnterpriseModels[0],
    coding: unclassifiedEnterpriseModels[1],
    translation: unclassifiedEnterpriseModels[2],
    recommendedCoding: [...unclassifiedEnterpriseModels],
    pullable: serverPullableModels,
  },
};
const unknownChatSelect = new FakeElement("select");
const unknownCodingSelect = new FakeElement("select");
const unknownTranslationSelect = new FakeElement("select");
renderModelSettingsSelects({
  composerModelLabel: (model) => model,
  displayModelName: (model) => model,
  els: {
    chatModel: unknownChatSelect,
    codingModel: unknownCodingSelect,
    translationModel: unknownTranslationSelect,
    composerModel: new FakeElement("select"),
  },
  modelIsInstalled: (model) => unclassifiedEnterpriseHealthState.serverModels.available.includes(model),
  state: unclassifiedEnterpriseHealthState,
  t: (key) => key,
});
for (const select of [unknownChatSelect, unknownCodingSelect, unknownTranslationSelect]) {
  for (const model of unclassifiedEnterpriseModels) {
    assert.equal(
      select.children.some((option) => option.value === model),
      false,
      `分類なしのEnterprise候補 ${model} を通常候補へ表示しない`,
    );
  }
}

const explicitNormalModel = "llama3:latest";
const explicitNormalSelect = new FakeElement("select");
renderModelSettingsSelects({
  composerModelLabel: (model) => model,
  displayModelName: (model) => model,
  els: {
    chatModel: explicitNormalSelect,
    codingModel: new FakeElement("select"),
    translationModel: new FakeElement("select"),
    composerModel: new FakeElement("select"),
  },
  modelIsInstalled: (model) => model === explicitNormalModel,
  state: {
    ...state,
    modelOverrides: { chat: explicitNormalModel },
  },
  t: (key) => key,
});
assert.equal(
  explicitNormalSelect.children.some((option) => option.value === explicitNormalModel),
  true,
  "既存の通常モデルの明示選択は維持する",
);

const otherExperimentalModel = "experimental:health-model";
const experimentalHealthState = {
  ...healthState,
  showExperimentalModels: true,
  serverModels: {
    ...healthState.serverModels,
    available: [...healthState.serverModels.available, otherExperimentalModel],
    pullable: [
      ...healthState.serverModels.pullable,
      {
        model: otherExperimentalModel,
        role: "coding-experimental",
        experimental: true,
        allowAutoSelect: false,
      },
    ],
  },
};
assert.equal(
  composerModelCandidates({
    state: experimentalHealthState,
    modelIsInstalled: (model) => experimentalHealthState.serverModels.available.includes(model),
  }).includes(otherExperimentalModel),
  false,
  "Huihui以外の実験モデルをチャット欄候補へ表示しない",
);

function descendantElements(element) {
  return [element, ...element.children.flatMap((child) => (
    child instanceof FakeElement ? descendantElements(child) : []
  ))];
}

function renderInstaller({ installedModels = [], language = "ja", studentModelRoutingMigrated = false, showExperimentalModels = false } = {}) {
  const modelInstaller = new FakeElement("section");
  renderModelInstaller({
    composerModelLabel: (model) => model,
    els: { modelInstaller },
    modelIsInstalled: (model) => installedModels.includes(model),
    state: {
      language,
      serverModels: { pullable: serverPullableModels },
      modelPullJobs: {},
      showExperimentalModels,
      studentModelRoutingMigrated,
    },
    t: (key) => ({
      "settings.modelDownload": "モデルをダウンロード",
      "settings.studentModelRoutingMigrated": language === "en"
        ? "Previous model settings were switched to safe automatic selection."
        : "以前のモデル設定を安全な自動選択へ切り替えました。",
      "model.installed": "ダウンロード済み",
      "model.downloading": "ダウンロード中",
      "model.download": "ダウンロード",
      "error.prefix": "エラー",
    }[key] || key),
  });
  return modelInstaller;
}

const installerHtml = renderInstaller().innerHTML;
assert.match(installerHtml, /標準AI/);
assert.match(installerHtml, /コード作業/);
assert.match(installerHtml, /高性能AI/);
assert.doesNotMatch(installerHtml, /翻訳AIモデル/);
assert.doesNotMatch(installerHtml, /HauhauCS/);
assert.doesNotMatch(installerHtml, /Huihui/);

const migratedInstallerHtml = renderInstaller({ studentModelRoutingMigrated: true }).innerHTML;
assert.match(migratedInstallerHtml, /以前のモデル設定を安全な自動選択へ切り替えました。/);
assert.ok(
  migratedInstallerHtml.indexOf("以前のモデル設定を安全な自動選択へ切り替えました。") < migratedInstallerHtml.indexOf("おすすめモデル"),
  "移行案内はおすすめモデルより前に表示する",
);
const migratedEnglishInstallerHtml = renderInstaller({ language: "en", studentModelRoutingMigrated: true }).innerHTML;
assert.match(migratedEnglishInstallerHtml, /Previous model settings were switched to safe automatic selection\./);

const hiddenModelsNotInstalledEl = renderInstaller();
assert.doesNotMatch(
  hiddenModelsNotInstalledEl.innerHTML,
  /HauhauCS Balanced 12B Q4/,
  "HauhauCS should stay out of the normal model details when not installed",
);
const hiddenModelsNotInstalledElements = descendantElements(hiddenModelsNotInstalledEl);
for (const model of [hauhauBalanced, huihuiAbliterated]) {
  assert.equal(
    hiddenModelsNotInstalledElements.some((element) => element.dataset.modelPull === model),
    false,
    `student-hidden model ${model} should not expose a download action`,
  );
}

const hiddenModelsInstalledEl = renderInstaller({ installedModels: [hauhauBalanced] });
const hiddenModelsInstalledElements = descendantElements(hiddenModelsInstalledEl);
assert.equal(
  hiddenModelsInstalledElements.some((element) => element.dataset.modelRemove === hauhauBalanced),
  true,
  "取得済みHauhauCSは削除操作を維持する",
);
assert.equal(
  hiddenModelsInstalledElements.some((element) => element.dataset.modelPull === hauhauBalanced),
  false,
  "取得済みHauhauCSはダウンロード操作を表示しない",
);

const experimentalInstalledEl = renderInstaller({
  installedModels: [huihuiAbliterated],
  showExperimentalModels: false,
});
const experimentalInstalledElements = descendantElements(experimentalInstalledEl);
assert.equal(
  experimentalInstalledElements.some((element) => element.dataset.modelRemove === huihuiAbliterated),
  true,
  "初期状態でも取得済みHuihuiの削除操作へ到達できる",
);
const hiddenInstalledDetails = experimentalInstalledElements.find((element) => element.className.includes("hidden-installed"));
assert.ok(hiddenInstalledDetails, "取得済みHuihuiは非表示モデル管理に含める");
assert.equal(
  descendantElements(hiddenInstalledDetails).some((element) => element.dataset.modelRemove === huihuiAbliterated),
  true,
  "Huihuiの削除操作は非表示モデル管理の内側に置く",
);

const composerVisibilityEl = new FakeElement("section");
renderComposerModelVisibility({
  composerModelLabel: (model) => model === "qwen2.5:3b" ? "Qwen" : model,
  els: { composerModelVisibility: composerVisibilityEl },
  models: ["qwen2.5:3b", agenticCoder],
  state: { language: "ja", composerModelVisibleModels: ["qwen2.5:3b"], composerModelVisibleModelsSaved: true },
});
assert.match(composerVisibilityEl.innerHTML, /チャット欄に表示するAIモデル/);
assert.match(composerVisibilityEl.innerHTML, /Qwen/);
assert.match(composerVisibilityEl.innerHTML, /data-composer-model-visible="qwen2.5:3b"/);
assert.match(composerVisibilityEl.innerHTML, /checked/);
const checkedVisibilityHtml = composerVisibilityEl.innerHTML;
assert.match(checkedVisibilityHtml, /data-composer-model-visible="qwen2\.5:3b" checked/);
assert.doesNotMatch(checkedVisibilityHtml, new RegExp(`data-composer-model-visible="${agenticCoder.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}" checked`));
function visibilityLabelForModel(html, model) {
  const marker = `data-composer-model-visible="${model}"`;
  const inputStart = html.indexOf(marker);
  assert.notEqual(inputStart, -1, `モデル ${model} のチェック欄が必要です`);
  const labelStart = html.lastIndexOf("<label", inputStart);
  const labelEnd = html.indexOf("</label>", inputStart);
  assert.notEqual(labelStart, -1, `モデル ${model} のラベル開始タグが必要です`);
  assert.notEqual(labelEnd, -1, `モデル ${model} のラベル終了タグが必要です`);
  return html.slice(labelStart, labelEnd + "</label>".length);
}

assert.match(visibilityLabelForModel(checkedVisibilityHtml, "qwen2.5:3b"), /class="is-selected"/);
assert.doesNotMatch(visibilityLabelForModel(checkedVisibilityHtml, agenticCoder), /\bis-selected\b/);

const defaultVisibilityEl = new FakeElement("section");
renderComposerModelVisibility({
  composerModelLabel: (model) => model,
  els: { composerModelVisibility: defaultVisibilityEl },
  models: ["qwen2.5:3b", agenticCoder],
  state: { language: "ja", composerModelVisibleModels: [], composerModelVisibleModelsSaved: false },
});
assert.equal((defaultVisibilityEl.innerHTML.match(/ checked/g) || []).length, 2);

const clearedVisibilityEl = new FakeElement("section");
renderComposerModelVisibility({
  composerModelLabel: (model) => model,
  els: { composerModelVisibility: clearedVisibilityEl },
  models: ["qwen2.5:3b", agenticCoder],
  state: { language: "ja", composerModelVisibleModels: [], composerModelVisibleModelsSaved: true },
});
assert.equal((clearedVisibilityEl.innerHTML.match(/ checked/g) || []).length, 0);
assert.doesNotMatch(clearedVisibilityEl.innerHTML, /class="is-selected"/);

const currentChatVisibilityEl = new FakeElement("section");
renderComposerModelVisibility({
  composerModelLabel: (model) => model === "gemma4:12b-mlx" ? "Gemma 4 MLX" : model,
  els: { composerModelVisibility: currentChatVisibilityEl },
  models: ["gemma4:12b-mlx", "qwen2.5:3b", agenticCoder],
  state: {
    language: "ja",
    composerModelVisibleModels: ["qwen2.5:3b"],
    composerModelVisibleModelsSaved: true,
    composerModel: "",
    modelOverrides: { chat: "" },
    serverModels: { chat: "gemma4:12b-mlx" },
  },
});
assert.match(
  visibilityLabelForModel(currentChatVisibilityEl.innerHTML, "gemma4:12b-mlx"),
  /\bchecked\b/,
  "自動選択中の現在チャットAIモデルは表示チェックを付ける",
);
assert.match(
  visibilityLabelForModel(currentChatVisibilityEl.innerHTML, "gemma4:12b-mlx"),
  /\bis-selected\b/,
  "自動選択中の現在チャットAIモデルは選択状態にする",
);

const pcDiagnosticsEl = new FakeElement("section");
renderPcDiagnosticsPanel({
  composerModelLabel: (model) => model.includes("Qwen3-4B") ? "Qwen3 2507" : model,
  els: { pcDiagnostics: pcDiagnosticsEl },
  escapeHtml: (value) => String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[char])),
  state: {
    language: "ja",
    appInfo: {
      pcDiagnostics: {
        ok: true,
        system: {
          os: "macOS",
          cpu: "Apple M2",
          memoryGb: 32,
          isAppleSilicon: true,
          gpu: "Apple Silicon GPU",
          hasGpu: true,
          ollamaVersion: "0.31.1",
          availableModels: [qwen2507, agenticCoder, "custom:high-performance"],
        },
        recommendation: {
          level: "comfortable",
          label: "快適",
          summary: "このPCでは12B系も使いやすいです。",
          recommended: {
            standard: qwen2507,
            coding: agenticCoder,
            light: "missing:legacy-light",
            translation: qwen2507,
            highPerformance: "custom:high-performance",
          },
          warnings: [],
        },
      },
    },
  },
  t: (key) => key,
});
assert.match(pcDiagnosticsEl.innerHTML, /PC診断/);
assert.match(pcDiagnosticsEl.innerHTML, /快適/);
assert.match(pcDiagnosticsEl.innerHTML, /再診断/);
assert.doesNotMatch(pcDiagnosticsEl.innerHTML, /<span>標準<\/span>/);
assert.doesNotMatch(pcDiagnosticsEl.innerHTML, /<span>コード<\/span>/);
assert.doesNotMatch(pcDiagnosticsEl.innerHTML, /Qwen3 2507/);
assert.match(pcDiagnosticsEl.innerHTML, /PC環境/);
assert.match(pcDiagnosticsEl.innerHTML, /利用できるAIモデル/);
assert.match(pcDiagnosticsEl.innerHTML, /CPU/);
assert.match(pcDiagnosticsEl.innerHTML, /GPU/);
assert.match(pcDiagnosticsEl.innerHTML, /Apple Silicon GPU/);
assert.match(pcDiagnosticsEl.innerHTML, /メモリ/);
assert.match(pcDiagnosticsEl.innerHTML, /Ollama/);
assert.match(pcDiagnosticsEl.innerHTML, /Apple Silicon/);
assert.match(pcDiagnosticsEl.innerHTML, /標準AI/);
assert.match(pcDiagnosticsEl.innerHTML, /コード作業/);
assert.match(pcDiagnosticsEl.innerHTML, /高性能AI/);
assert.doesNotMatch(pcDiagnosticsEl.innerHTML, /軽量AIモデル/);
assert.doesNotMatch(pcDiagnosticsEl.innerHTML, /プログラミング用AIモデル/);
assert.ok(
  pcDiagnosticsEl.innerHTML.indexOf("標準AI") < pcDiagnosticsEl.innerHTML.indexOf("コード作業"),
  "標準AI should appear before コード作業",
);
assert.ok(
  pcDiagnosticsEl.innerHTML.indexOf("コード作業") < pcDiagnosticsEl.innerHTML.indexOf("高性能AI"),
  "コード作業 should appear before 高性能AI",
);
function pcModelCheckHtml(label) {
  const labelIndex = pcDiagnosticsEl.innerHTML.indexOf(`<strong>${label}</strong>`);
  assert.notEqual(labelIndex, -1, `${label} の診断行が必要です`);
  const rowStart = pcDiagnosticsEl.innerHTML.lastIndexOf('<div class="', labelIndex);
  const rowEnd = pcDiagnosticsEl.innerHTML.indexOf("</div>", labelIndex);
  return pcDiagnosticsEl.innerHTML.slice(rowStart, rowEnd + "</div>".length);
}
for (const label of ["標準AI", "コード作業", "高性能AI"]) {
  assert.match(pcModelCheckHtml(label), /<div class="ok">/);
  assert.match(pcModelCheckHtml(label), /<small>利用可能<\/small>/);
}
assert.match(pcDiagnosticsEl.innerHTML, /pc-diagnostics-model-checks/);
assert.match(pcDiagnosticsEl.innerHTML, /pc-diagnostics-divider/);

const pcDiagnosticsFallbackEl = new FakeElement("section");
renderPcDiagnosticsPanel({
  els: { pcDiagnostics: pcDiagnosticsFallbackEl },
  escapeHtml: (value) => String(value),
  state: {
    language: "ja",
    appInfo: {
      pcDiagnostics: {
        ok: true,
        system: { cpu: "Intel CPU", memoryGb: 16, isAppleSilicon: false, hasGpu: false, ollamaVersion: "0.31.1", availableModels: [] },
        recommendation: {
          level: "comfortable",
          label: "快適",
          recommended: { standard: "gemma4:12b-mlx" },
        },
      },
    },
  },
});
assert.match(pcDiagnosticsFallbackEl.innerHTML, /再診断/);
assert.match(pcDiagnosticsFallbackEl.innerHTML, /GPU/);
assert.match(pcDiagnosticsFallbackEl.innerHTML, /なし/);

const pcDiagnosticsOldOllamaEl = new FakeElement("section");
renderPcDiagnosticsPanel({
  els: { pcDiagnostics: pcDiagnosticsOldOllamaEl },
  escapeHtml: (value) => String(value),
  state: {
    language: "ja",
    appInfo: {
      pcDiagnostics: {
        ok: true,
        system: { cpu: "Apple M2", memoryGb: 32, isAppleSilicon: true, ollamaVersion: "0.30.7", availableModels: [] },
        recommendation: {
          level: "heavy",
          label: "重い",
          recommended: {},
        },
      },
    },
  },
});
assert.match(pcDiagnosticsOldOllamaEl.innerHTML, /Ollamaの更新をおすすめします/);
assert.match(pcDiagnosticsOldOllamaEl.innerHTML, /Ollama公式ページを開く/);

const settingsMetaEl = new FakeElement("section");
renderSettingsMeta({
  els: { settingsMeta: settingsMetaEl },
  escapeHtml: (value) => String(value),
  state: {
    language: "ja",
    appInfo: {
      version: "0.8.209",
      commit: "test",
      pcDiagnostics: {
        recommendation: { label: "快適" },
      },
    },
    theme: "light",
  },
});
assert.match(settingsMetaEl.innerHTML, /PC診断: 快適/);

console.log("settings helper tests passed");
