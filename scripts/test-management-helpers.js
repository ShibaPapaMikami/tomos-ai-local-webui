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
  renderMobileConnectInfo,
  summarizeMobileImportPayload,
  mobileImportPayloadToSession,
  renderPluginsPanel,
  studyPackById,
} = context.window.GEMMA_MANAGEMENT;

const els = {
  settingsPanel: { hidden: false },
  mobileConnectPanel: { hidden: true },
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

openManagementPanel({ els, panel: els.mobileConnectPanel });
assert.equal(els.pluginsPanel.hidden, true);
assert.equal(els.mobileConnectPanel.hidden, false);

openManagementPanel({ els, panel: els.studyPacksPanel });
assert.equal(els.mobileConnectPanel.hidden, true);
assert.equal(els.pluginsPanel.hidden, true);
assert.equal(els.studyPacksPanel.hidden, false);

const labels = {
  "management.add": "追加",
  "management.added": "追加済み",
  "management.addCandidate": "あとで検討に入れる",
  "management.addFirst": "先に追加してください",
  "management.codingAssistPack": "コーディング支援",
  "management.mobileConnectError": "接続情報を取得できませんでした。",
  "management.mobileConnectExpires": "有効期限: {time}",
  "management.mobileConnectNoLan": "今はPC内だけで待ち受けています。",
  "management.mobileConnectPairingPending": "コード表示のみです。",
  "management.mobileConnectQrAlt": "スマホで開くQRコード",
  "management.mobileConnectQrPending": "QRはペアリングコード実装時にここへ表示します",
  "management.mobileConnectReady": "ペアリングコードを発行しました。",
  "management.mobileImportInvalid": "スマホチャットJSONではありません。",
  "management.mobileImportInvalidJson": "JSONの形式が正しくありません。",
  "management.mobileImportApply": "PCへ取り込み",
  "management.mobileImportApplied": "{count}件をPCのチャット履歴に取り込みました。",
  "management.mobileImportPending": "スマホ受信を確認",
  "management.mobileImportPendingLoading": "スマホから届いたチャットを確認中...",
  "management.mobileImportPendingEmpty": "スマホから届いた未取り込みチャットはありません。",
  "management.mobileImportPendingApplied": "スマホから届いた{count}件をPCのチャット履歴に取り込みました。",
  "management.mobileImportPendingError": "スマホ受信の確認に失敗しました: {error}",
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
const mobileConnectMenuIndex = indexHtml.indexOf('id="mobile-connect-toggle"');
const basicSettingsMenuIndex = indexHtml.indexOf('id="settings-toggle"');
assert.notEqual(mobileConnectMenuIndex, -1);
assert.notEqual(basicSettingsMenuIndex, -1);
assert.ok(mobileConnectMenuIndex < basicSettingsMenuIndex, "mobile connection should be the first settings item");
assert.match(indexHtml, /id="mobile-connect-panel"/);
assert.match(indexHtml, /id="mobile-connect-code"/);
assert.match(indexHtml, /id="mobile-connect-hosts"/);
assert.match(indexHtml, /id="mobile-connect-qr-image"/);
assert.match(indexHtml, /id="mobile-connect-qr-text"/);
assert.match(indexHtml, /id="mobile-import-json"/);
assert.match(indexHtml, /id="mobile-import-preview"/);
assert.match(indexHtml, /id="mobile-import-preview-button"/);
assert.match(indexHtml, /id="mobile-import-apply-button"/);
assert.match(indexHtml, /id="mobile-import-pending-button"/);
assert.match(indexHtml, /data-i18n="management\.mobileConnect"/);
assert.match(indexHtml, /data-i18n="management\.mobileConnectLocalOnly"/);
assert.match(indexHtml, /data-i18n="management\.mobileConnectQrPending"/);
assert.match(indexHtml, /data-i18n="management\.mobileConnectCode"/);
assert.match(indexHtml, /data-study-pack-toggle="coding-assist-basic"/);
assert.match(indexHtml, /data-i18n="management\.codingAssistPack"/);
assert.match(indexHtml, /data-i18n="studyPack\.mode\.releaseCheckShort"/);

const mobileConnectEls = {
  mobileConnectCode: { textContent: "" },
  mobileConnectExpires: { textContent: "" },
  mobileConnectHosts: { textContent: "" },
  mobileConnectStatus: { textContent: "" },
  mobileConnectQrImage: { src: "", hidden: true, alt: "" },
  mobileConnectQrText: { textContent: "" },
};
renderMobileConnectInfo({
  els: mobileConnectEls,
  t,
  info: {
    ok: true,
    pairingCode: "123456",
    expiresAt: "2026-06-27T10:00:00Z",
    pairingEnabled: false,
    hostCandidates: ["http://192.168.1.20:54876"],
  },
});
assert.equal(mobileConnectEls.mobileConnectCode.textContent, "123456");
assert.equal(mobileConnectEls.mobileConnectStatus.textContent, "コード表示のみです。");
assert.equal(mobileConnectEls.mobileConnectHosts.textContent, "http://192.168.1.20:54876");
assert.equal(mobileConnectEls.mobileConnectQrImage.hidden, false);
assert.match(mobileConnectEls.mobileConnectQrImage.src, /\/api\/mobile\/qr\.svg\?text=/);
assert.match(decodeURIComponent(mobileConnectEls.mobileConnectQrImage.src), /http:\/\/192\.168\.1\.20:54876\/m/);
const qrTarget = new URL(mobileConnectEls.mobileConnectQrImage.src, "http://127.0.0.1").searchParams.get("text");
assert.match(qrTarget, /http:\/\/192\.168\.1\.20:54876\/m/);
assert.equal(new URL(qrTarget).searchParams.get("h"), "http://192.168.1.20:54876");
assert.equal(new URL(qrTarget).searchParams.get("c"), "123456");
assert.equal(new URL(mobileConnectEls.mobileConnectQrImage.src, "http://127.0.0.1").searchParams.get("v"), "123456");
assert.match(mobileConnectEls.mobileConnectQrText.textContent, /mobile\.html/);
assert.match(mobileConnectEls.mobileConnectExpires.textContent, /2026-06-27T10:00:00Z/);

const mobileImportSummary = summarizeMobileImportPayload({
  type: "gemma4-mobile-chat",
  messages: [
    { role: "user", text: "こんにちは", createdAt: "2026-06-27T10:00:00Z" },
    { role: "assistant", text: "こんにちは。", createdAt: "2026-06-27T10:00:01Z" },
    { role: "user", text: "学習メモ", createdAt: "2026-06-27T10:00:02Z" },
  ],
});
assert.equal(mobileImportSummary.ok, true);
assert.equal(mobileImportSummary.total, 3);
assert.equal(mobileImportSummary.user, 2);
assert.equal(mobileImportSummary.assistant, 1);
assert.match(mobileImportSummary.label, /3件/);
assert.equal(summarizeMobileImportPayload({ type: "wrong", messages: [] }).ok, false);

const mobileImportSession = mobileImportPayloadToSession({
  payload: {
    type: "gemma4-mobile-chat",
    messages: [
      { role: "user", text: "こんにちは", createdAt: "2026-06-27T10:00:00Z" },
      { role: "assistant", text: "こんにちは。", createdAt: "2026-06-27T10:00:01Z" },
      { role: "system", text: "無視", createdAt: "2026-06-27T10:00:02Z" },
    ],
  },
  folderId: "folder-1",
  createId: () => "mobile-session-1",
  now: () => 1234567890,
});
assert.equal(mobileImportSession.ok, true);
assert.equal(mobileImportSession.session.id, "mobile-session-1");
assert.equal(mobileImportSession.session.folderId, "folder-1");
assert.match(mobileImportSession.session.title, /スマホチャット/);
assert.deepEqual(JSON.parse(JSON.stringify(mobileImportSession.session.messages)), [
  { role: "user", content: "こんにちは" },
  { role: "assistant", content: "こんにちは。" },
]);
assert.equal(mobileImportPayloadToSession({ payload: { type: "wrong", messages: [] } }).ok, false);

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
