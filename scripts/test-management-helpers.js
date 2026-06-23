const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const storage = new Map();
const context = {
  window: {},
  document: {
    querySelector: () => null,
  },
  localStorage: {
    getItem: (key) => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, String(value)),
  },
  console,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/management.js", "utf8"), context, { filename: "web/management.js" });

const {
  formatPluginSearchCapabilities,
  handleEscapeKey,
  importStudyPackFromFiles,
  studyPackSelectionModel,
  studyPackMultiSelectionModel,
  toggleStudyPackModeValue,
  studyPackMenuGroups,
  openManagementPanel,
  renderPluginsPanel,
  studyPackById,
} = context.window.GEMMA_MANAGEMENT;

const els = {
  settingsPanel: { hidden: false },
  studyPacksPanel: { hidden: true },
  trainingManagementPanel: { hidden: true },
  pluginsPanel: { hidden: true },
};
const state = { workspaceOpen: true };
let renderCount = 0;

assert.equal(handleEscapeKey({ els, state, onRender: () => { renderCount += 1; } }), "management");
assert.equal(els.settingsPanel.hidden, true);
assert.equal(state.workspaceOpen, true);
assert.equal(renderCount, 0);

assert.equal(handleEscapeKey({ els, state, onRender: () => { renderCount += 1; } }), "workspace");
assert.equal(state.workspaceOpen, false);
assert.equal(renderCount, 1);

assert.equal(handleEscapeKey({ els, state, onRender: () => { renderCount += 1; } }), "");
assert.equal(renderCount, 1);

openManagementPanel({ els, panel: els.pluginsPanel });
assert.equal(els.pluginsPanel.hidden, false);
assert.equal(els.settingsPanel.hidden, true);

openManagementPanel({ els, panel: els.studyPacksPanel });
assert.equal(els.pluginsPanel.hidden, true);
assert.equal(els.studyPacksPanel.hidden, false);

const labels = {
  "management.add": "追加",
  "management.added": "追加済み",
  "management.addCandidate": "あとで検討に入れる",
  "management.addFirst": "先に追加してください",
  "management.codingAssistPack": "コーディング支援",
  "management.reportWritingPack": "日本語レポート添削",
  "management.candidateSaved": "検討リスト入り（まだ使えません）",
  "management.notAdded": "未追加",
  "management.notImplementedCandidate": "未対応（まだ使えません）",
  "management.openFolderSettings": "フォルダー設定へ",
  "management.remove": "削除",
  "management.removeCandidate": "検討リストから外す",
  "management.needsFolderSetup": "フォルダー設定が必要",
  "management.ready": "利用可能",
  "management.pluginSearchChecking": "検索対象を確認中",
  "management.pluginSearchCurrent": "現在の検索対象: {targets}",
  "management.pluginSearchUnsupported": "未対応: {targets}",
  "management.pluginSearchText": "テキスト",
  "management.pluginSearchWord": "Word",
  "management.pluginSearchPdfReady": "PDF本文（{backend}）",
  "management.pluginSearchPdfFilenameOnly": "PDFはファイル名のみ",
  "management.pluginSearchImageOcrUnsupported": "画像内文字",
  "management.pluginSearchNone": "未確認",
  "studyPack.mode.codeReviewShort": "コードレビュー",
  "studyPack.mode.makeReadableShort": "読みやすくする",
};
const t = (key, vars = {}) => Object.entries(vars).reduce(
  (text, [name, value]) => text.replace(`{${name}}`, value),
  labels[key] || context.window.GEMMA_IMPORTED_STUDY_PACK_LABELS?.[key] || key,
);
assert.equal(
  formatPluginSearchCapabilities({ capabilities: {}, t }),
  "検索対象を確認中",
);
assert.equal(
  formatPluginSearchCapabilities({
    capabilities: { text: true, docx: true, pdf: false, filenameFallback: true, imageOcr: false },
    t,
  }),
  "現在の検索対象: テキスト / Word / PDFはファイル名のみ / 未対応: 画像内文字",
);

const searchCapabilitiesElement = { textContent: "" };
const ocrCandidateStatus = { textContent: "", dataset: {} };
const ocrCandidateToggle = {
  textContent: "",
  disabled: false,
  setAttribute(name, value) { this[name] = value; },
};
context.document.querySelector = (selector) => {
  if (selector === "#plugin-search-capabilities") return searchCapabilitiesElement;
  if (selector === '[data-plugin-candidate-status="ocr"]') return ocrCandidateStatus;
  if (selector === '[data-plugin-candidate-toggle="ocr"]') return ocrCandidateToggle;
  return null;
};
context.document.querySelectorAll = () => [];
const pluginEls = {
  codegraphPluginStatus: { textContent: "", dataset: {} },
  codegraphPluginToggle: { textContent: "", setAttribute(name, value) { this[name] = value; } },
};
renderPluginsPanel({
  els: pluginEls,
  state: {
    appInfo: { searchCapabilities: { text: true, docx: true, pdf: true, pdfBackend: "Spotlight", imageOcr: false } },
    plugins: { codegraph: { installed: true }, ocr: { planned: true } },
  },
  t,
});
assert.equal(pluginEls.codegraphPluginStatus.textContent, "フォルダー設定が必要");
assert.match(searchCapabilitiesElement.textContent, /PDF本文/);
assert.equal(ocrCandidateStatus.textContent, "検討リスト入り（まだ使えません）");
assert.equal(ocrCandidateToggle.textContent, "検討リストから外す");

const codingPack = studyPackById("coding-assist-basic");
assert.equal(codingPack.nameKey, "management.codingAssistPack");
assert.equal(codingPack.modes.length, 5);
assert.equal(codingPack.modes[0].id, "code-review");
assert.equal(
  studyPackMenuGroups({ packs: [codingPack], selectedValue: "coding-assist-basic:code-review", t })[0].modes[0].label,
  "コードレビュー",
);
const indexHtml = fs.readFileSync("web/index.html", "utf8");
assert.match(indexHtml, /data-study-pack-toggle="coding-assist-basic"/);
assert.match(indexHtml, /data-i18n="management\.codingAssistPack"/);
assert.match(indexHtml, /data-i18n="studyPack\.mode\.releaseCheckShort"/);

async function runImportTests() {
  const makeFile = (name, content) => ({
    name,
    async text() {
      return content;
    },
  });
  const stateForImport = { studyPacks: {} };
  const result = await importStudyPackFromFiles({
    state: stateForImport,
    files: [
      makeFile("pack.json", JSON.stringify({
        version: "0.1.0",
        visibility: "private",
        modes: [
          { id: "slack-rewrite", name: "Slackを整える", promptFile: "modes/slack-rewrite.md" },
        ],
      })),
    ],
    t,
  });
  assert.equal(result.ok, true);
  assert.equal(result.definition.imported, true);
  assert.equal(result.definition.private, true);

  const groups = studyPackMenuGroups({
    packs: [
      {
        id: "ja-report-writing-basic",
        nameKey: "management.reportWritingPack",
        modes: [
          { id: "make-readable", shortKey: "studyPack.mode.makeReadableShort" },
        ],
      },
      result.definition,
    ],
    t,
  });
  assert.equal(groups.length, 2);
  assert.equal(groups[0].label, "日本語レポート添削");
  assert.equal(groups[1].modes[0].active, true);

  const selectionModel = studyPackSelectionModel({
    packs: [
      {
        id: "ja-report-writing-basic",
        nameKey: "management.reportWritingPack",
        modes: [
          { id: "make-readable", shortKey: "studyPack.mode.makeReadableShort" },
        ],
      },
      result.definition,
    ],
    selectedPackId: "",
    t,
  });
  assert.equal(selectionModel.modeOptions.length, 1);
  assert.equal(selectionModel.modeOptions[0].label, "Slackを整える");
  assert.equal(selectionModel.modeOptions[0].active, true);

  const multiSelectionModel = studyPackMultiSelectionModel({
    packs: [
      {
        id: "ja-report-writing-basic",
        nameKey: "management.reportWritingPack",
        modes: [
          { id: "make-readable", shortKey: "studyPack.mode.makeReadableShort" },
        ],
      },
      result.definition,
    ],
    selectedValues: [
      "ja-report-writing-basic:make-readable",
    ],
    t,
  });
  assert.equal(multiSelectionModel.selectedCount, 2);
  assert.equal(multiSelectionModel.summaryLabel, "教材パック 2件");
  assert.equal(multiSelectionModel.groups[0].modes[0].checked, true);
  assert.equal(multiSelectionModel.groups[1].modes[0].checked, true);
  assert.deepEqual(Array.from(toggleStudyPackModeValue(["a:one"], "b:two", true)), ["a:one", "b:two"]);
  assert.deepEqual(Array.from(toggleStudyPackModeValue(["a:one", "b:two"], "a:one", false)), ["b:two"]);
}

runImportTests().then(() => {
  console.log("management helper tests passed");
});
