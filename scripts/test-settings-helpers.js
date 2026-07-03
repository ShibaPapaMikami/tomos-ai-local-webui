const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/settings.js", "utf8"), context, { filename: "web/settings.js" });

const { composerModelCandidates, installedOrCurrentModels, renderComposerModelVisibility, renderPcDiagnosticsPanel } = context.window.GEMMA_SETTINGS;
const { renderSettingsMeta } = context.window.GEMMA_SETTINGS;

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

const filteredComposerCandidates = composerModelCandidates({
  state: {
    ...state,
    composerModelVisibleModels: ["qwen2.5:3b"],
  },
  modelIsInstalled,
});
assert.equal(JSON.stringify(filteredComposerCandidates), JSON.stringify(["qwen2.5:3b"]));

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

const composerVisibilityEl = new FakeElement("section");
renderComposerModelVisibility({
  composerModelLabel: (model) => model === "qwen2.5:3b" ? "Qwen" : model,
  els: { composerModelVisibility: composerVisibilityEl },
  models: ["qwen2.5:3b", agenticCoder],
  state: { language: "ja", composerModelVisibleModels: ["qwen2.5:3b"] },
});
assert.match(composerVisibilityEl.innerHTML, /チャット欄に表示するAIモデル/);
assert.match(composerVisibilityEl.innerHTML, /Qwen/);
assert.match(composerVisibilityEl.innerHTML, /data-composer-model-visible="qwen2.5:3b"/);
assert.match(composerVisibilityEl.innerHTML, /checked/);

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
          availableModels: ["gemma4:12b-mlx", agenticCoder, "qwen2.5:3b"],
        },
        recommendation: {
          level: "comfortable",
          label: "快適",
          summary: "このPCでは12B系も使いやすいです。",
          recommended: {
            standard: "gemma4:12b-mlx",
            coding: agenticCoder,
            light: "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL",
            translation: "qwen2.5:3b",
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
assert.match(pcDiagnosticsEl.innerHTML, /軽量AIモデル/);
assert.match(pcDiagnosticsEl.innerHTML, /高性能AIモデル/);
assert.match(pcDiagnosticsEl.innerHTML, /プログラミング用AIモデル/);
assert.ok(
  pcDiagnosticsEl.innerHTML.indexOf("軽量AIモデル") < pcDiagnosticsEl.innerHTML.indexOf("高性能AIモデル"),
  "軽量AIモデル should appear before 高性能AIモデル",
);
assert.ok(
  pcDiagnosticsEl.innerHTML.indexOf("高性能AIモデル") < pcDiagnosticsEl.innerHTML.indexOf("プログラミング用AIモデル"),
  "高性能AIモデル should appear before プログラミング用AIモデル",
);
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
      version: "0.8.205",
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
