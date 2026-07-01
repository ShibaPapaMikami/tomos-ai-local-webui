const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const storage = new Map();
storage.set("gemma4.character", JSON.stringify({
  name: "しばぱぱ",
  userName: "まさふみ",
  selfName: "ぼく",
  tonePreset: "calm",
  personality: "やさしく短く返す",
}));
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
  compactStudyPackPrompt,
  shouldApplyStudyPackForText,
  studyPackSelectionModel,
  studyPackMultiSelectionModel,
  toggleStudyPackModeValue,
  studyPackMenuGroups,
  openManagementPanel,
  renderMobileConnectInfo,
  summarizeMobileImportPayload,
  mobileImportPayloadToSession,
  renderPluginsPanel,
  togglePluginCandidate,
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
  "management.needsFolderSetup": "フォルダー編集で有効にしてください",
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

const indexHtml = fs.readFileSync("web/index.html", "utf8");
const i18nJs = fs.readFileSync("web/i18n.js", "utf8");
const stylesCss = fs.readFileSync("web/styles.css", "utf8");
const appJs = fs.readFileSync("web/app.js", "utf8");

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
context.document.querySelectorAll = (selector) => {
  return [];
};
const pluginEls = {
  codegraphPluginStatus: { textContent: "", dataset: {} },
  codegraphPluginToggle: { textContent: "", setAttribute(name, value) { this[name] = value; } },
  contractsToggle: { hidden: false },
};
renderPluginsPanel({
  els: pluginEls,
  state: {
    appInfo: { searchCapabilities: { text: true, docx: true, pdf: true, pdfBackend: "Spotlight", imageOcr: false } },
    plugins: { codegraph: { installed: true }, ocr: { planned: true }, contracts: { installed: false } },
  },
  t,
});
assert.equal(pluginEls.codegraphPluginStatus.textContent, "フォルダー編集で有効にしてください");
assert.match(searchCapabilitiesElement.textContent, /PDF本文/);
assert.equal(ocrCandidateStatus.textContent, "検討リスト入り（まだ使えません）");
assert.equal(ocrCandidateToggle.textContent, "検討リストから外す");
assert.equal(pluginEls.contractsToggle.hidden, true);
assert.match(indexHtml, /data-plugin-candidate-status="contracts"/);
assert.match(indexHtml, /data-plugin-candidate-toggle="contracts"/);
assert.match(indexHtml, /data-i18n="management\.pluginContractsTitle"/);
assert.match(indexHtml, /追加DLなし（内蔵機能）/);
assert.match(i18nJs, /"management\.pluginContractsSize": "追加DLなし（内蔵機能）"/);
assert.match(indexHtml, /id="contracts-toggle"[^>]*hidden/);
const contractAppState = { plugins: { contracts: { installed: false } } };
togglePluginCandidate({ state: contractAppState, els: pluginEls, t, pluginId: "contracts" });
assert.equal(contractAppState.plugins.contracts.installed, true);
assert.equal(pluginEls.contractsToggle.hidden, false);

const codingPack = studyPackById("coding-assist-basic");
assert.equal(codingPack.nameKey, "management.codingAssistPack");
assert.equal(codingPack.modes.length, 5);
assert.equal(codingPack.modes[0].id, "code-review");
assert.equal(
  studyPackMenuGroups({ packs: [codingPack], selectedValue: "coding-assist-basic:code-review", t })[0].modes[0].label,
  "コードレビュー",
);
assert.match(i18nJs, /"management\.needsFolderSetup": "フォルダー編集で有効にしてください"/);
assert.match(i18nJs, /"management\.prepareCodeUnderstanding": "準備する"/);
assert.match(indexHtml, /src="\/i18n\.js\?v=0\.8\.198-mlx17"/);
assert.match(indexHtml, /href="\/styles\.css\?v=0\.8\.198-mlx17"/);
const codegraphCardStart = indexHtml.indexOf('data-i18n="management.codeUnderstanding"');
const codegraphCardEnd = indexHtml.indexOf('id="codegraph-plugin-toggle"', codegraphCardStart);
assert.equal(indexHtml.slice(codegraphCardStart, codegraphCardEnd).includes('data-plugin-workspace="codegraph"'), false);
const mobileConnectMenuIndex = indexHtml.indexOf('id="mobile-connect-toggle"');
const basicSettingsMenuIndex = indexHtml.indexOf('id="settings-toggle"');
assert.notEqual(mobileConnectMenuIndex, -1);
assert.notEqual(basicSettingsMenuIndex, -1);
assert.ok(mobileConnectMenuIndex < basicSettingsMenuIndex, "mobile connection should be the first settings item");
assert.match(indexHtml, /id="mobile-connect-toggle"[^>]*disabled/);
assert.match(indexHtml, /class="ghost-button is-testing" id="mobile-connect-toggle"/);
assert.match(indexHtml, /data-i18n="management\.mobileConnectTesting"/);
assert.match(i18nJs, /"management\.mobileConnectTesting": "スマホ接続（テスト中）"/);
assert.match(stylesCss, /\.sidebar-settings-menu \.ghost-button:disabled/);
assert.match(stylesCss, /\.sidebar-settings-menu \.ghost-button\.is-testing:disabled/);
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
assert.match(indexHtml, /id="contracts-toggle"[^>]*hidden/);
assert.doesNotMatch(indexHtml, /id="experiments-toggle"/);
assert.doesNotMatch(indexHtml, /id="experiments-panel"/);
assert.match(indexHtml, /id="contract-pdf-import-status"/);
assert.match(indexHtml, /id="contract-pdf-import-path" type="hidden"/);
assert.match(indexHtml, /id="contract-pdf-import-selected"/);
assert.match(indexHtml, /data-i18n="contracts\.pdfImportNoFile"/);
assert.doesNotMatch(indexHtml, /data-i18n="contracts\.pdfImportPath"/);
assert.doesNotMatch(indexHtml, /data-i18n="contracts\.pdfImportPathHelp"/);
assert.ok(
  indexHtml.indexOf('data-i18n="contracts.pdfImportAdvanced"') < indexHtml.indexOf('id="contract-pdf-import-page"'),
  "page number should be available only in detailed checks",
);
assert.match(indexHtml, /id="contract-pdf-import-pick-pdf"/);
assert.match(indexHtml, /id="contract-pdf-import-auto"/);
assert.match(indexHtml, /id="contract-pdf-import-connection-test"/);
assert.match(indexHtml, /id="contract-pdf-import-try"/);
assert.doesNotMatch(indexHtml, /id="contract-pdf-import-try" disabled/);
assert.match(indexHtml, /id="contract-pdf-import-sarashina"/);
assert.match(indexHtml, /id="contract-pdf-import-send-contract"/);
assert.match(indexHtml, /id="contract-pdf-import-result"/);
assert.match(indexHtml, /id="contracts-panel"/);
assert.match(indexHtml, /id="contract-pdf-import"/);
assert.match(indexHtml, /data-i18n="contracts\.pdfImportTitle"/);
assert.match(indexHtml, /class="contract-section-title"/);
assert.doesNotMatch(indexHtml, /id="contracts-extract"/);
assert.match(indexHtml, /class="contract-pdf-import-status-row"/);
assert.match(indexHtml, /class="contract-pdf-import-button-row contract-import-action-row"/);
assert.match(indexHtml, /class="ghost-button contract-import-action-button"[\s\S]{0,120}id="contract-pdf-import-pick-pdf"/);
assert.match(indexHtml, /class="ghost-button contract-import-action-button"[\s\S]{0,120}id="contract-pdf-import-auto"/);
assert.match(indexHtml, /id="contracts-gap-check"/);
assert.match(indexHtml, /class="ghost-button contract-import-action-button"[\s\S]{0,120}id="contracts-gap-check"/);
assert.match(indexHtml, /id="contracts-gap-list"/);
assert.ok(
  indexHtml.indexOf('id="contract-pdf-import-auto"') < indexHtml.indexOf('id="contracts-gap-check"'),
  "gap check should appear below PDF import button",
);
assert.ok(
  indexHtml.indexOf('id="contracts-gap-check"') < indexHtml.indexOf('id="contract-pdf-import-result"'),
  "gap check should stay inside the PDF import area",
);
assert.doesNotMatch(indexHtml, /data-i18n="contracts\.gapCheckHelp"/);
assert.doesNotMatch(indexHtml, /class="management-card contract-gap-check"/);
assert.match(indexHtml, /id="contracts-export-csv"/);
assert.match(indexHtml, /id="contracts-export-json"/);
assert.match(indexHtml, /id="contracts-import-json"/);
assert.match(indexHtml, /id="contracts-import-input"/);
assert.match(indexHtml, /class="contract-ledger-actions"/);
assert.match(indexHtml, /class="contract-ledger-admin-actions"/);
assert.match(indexHtml, /data-i18n="contracts\.adminActions"/);
assert.match(indexHtml, /id="contracts-delete-dummies"[^>]*hidden/);
assert.match(indexHtml, /data-i18n="contracts\.menu"/);
assert.match(i18nJs, /"contracts\.title": "契約書管理"/);
assert.match(i18nJs, /"contracts\.localOnly": "契約書一覧"/);
assert.match(i18nJs, /"contracts\.sourcePdfImport": "契約書取り込みから追加"/);
assert.match(i18nJs, /"contracts\.sourceOcrExperiment": "旧PDF取り込みから追加"/);
assert.doesNotMatch(i18nJs, /experiments\./);
assert.match(i18nJs, /"contracts\.exportCsv": "CSV書き出し"/);
assert.match(i18nJs, /"contracts\.importJson": "JSON取り込み"/);
assert.match(i18nJs, /"contracts\.pdfImportTitle": "契約書取り込み"/);
assert.match(i18nJs, /"contracts\.pdfImportConnectionTest": "接続テスト"/);
assert.match(i18nJs, /"contracts\.pdfImportNoFile": "契約書未選択"/);
assert.match(i18nJs, /"contracts\.pdfImportSelectedFile": "選択中: \{path\}"/);
assert.doesNotMatch(i18nJs, /"contracts\.pdfImportPath"/);
assert.doesNotMatch(i18nJs, /"contracts\.pdfImportPathHelp"/);
assert.match(i18nJs, /"contracts\.pdfImportPickPdf": "契約書を選択"/);
assert.match(i18nJs, /"contracts\.pdfImportAuto": "契約書を取り込み"/);
assert.match(i18nJs, /"contracts\.pdfImportTryOnePage": "1ページだけ試す"/);
assert.match(i18nJs, /"contracts\.pdfImportSarashinaCompare": "Sarashina OCRで比較"/);
assert.match(i18nJs, /"contracts\.pdfImportSendContract": "契約書管理に送る"/);
assert.doesNotMatch(i18nJs, /"contracts\.extract": "現在のフォルダーから抽出"/);
assert.match(i18nJs, /"contracts\.gapCheck": "取り込み漏れチェック"/);
assert.doesNotMatch(i18nJs, /"contracts\.gapCheckHelp"/);
assert.match(appJs, /\/api\/contracts\/import-gaps/);
assert.match(appJs, /\/api\/contracts\/pdf-import\/status/);
assert.match(appJs, /\/api\/contracts\/pdf-import\/test/);
assert.match(appJs, /\/api\/contracts\/pdf-import\/pick-pdf/);
assert.match(appJs, /contractPdfImportSelected/);
assert.match(appJs, /\/api\/contracts\/pdf-import\/auto/);
assert.match(appJs, /\/api\/contracts\/pdf-import\/try-page/);
assert.match(stylesCss, /\.primary-action \{/);
assert.match(stylesCss, /background: var\(--accent\)/);
assert.match(stylesCss, /color: var\(--accent-ink\)/);
assert.match(indexHtml, /class="contract-pdf-import-button-row contract-import-action-row"/);
assert.match(stylesCss, /\.contract-import-action-row/);
assert.match(stylesCss, /\.contract-import-action-button/);
assert.match(stylesCss, /flex: 0 0 180px/);
assert.match(stylesCss, /width: 180px/);
assert.match(stylesCss, /\.contract-ledger-actions/);
assert.match(stylesCss, /\.contract-ledger-admin-actions/);
assert.match(stylesCss, /\.contract-section-title/);
assert.match(stylesCss, /\.workspace\.management-open \.topbar/);
assert.match(stylesCss, /display: none/);
assert.match(stylesCss, /\.workspace\.management-open \.settings-panel/);
assert.match(stylesCss, /\.workspace\.management-open \{/);
assert.match(stylesCss, /overflow: auto/);
assert.match(stylesCss, /background: transparent/);
assert.match(stylesCss, /border: 0/);
assert.match(stylesCss, /max-height: none/);
assert.match(appJs, /\/api\/contracts\/pdf-import\/sarashina\/compare-page/);
assert.doesNotMatch(appJs, /\/api\/experiments\/contract-pdf-import/);
assert.match(appJs, /contractPdfImportPage/);
assert.doesNotMatch(appJs, /renderExperimentsPanel/);
assert.match(appJs, /async function runContractPdfImportConnectionTest/);
assert.match(appJs, /async function pickContractPdfImportPdf/);
assert.match(appJs, /async function runContractPdfImportAuto/);
assert.match(appJs, /async function runContractPdfImportTryPage/);
assert.match(appJs, /async function runContractPdfImportSarashinaCompare/);
assert.match(appJs, /function sendContractPdfImportCandidate/);
assert.match(appJs, /function contractSourceLabel/);
assert.match(appJs, /function isBusinessEmailDraft/);
assert.match(appJs, /function isImplicitStudyPackWritingRequest/);
assert.match(appJs, /isBusinessEmailDraft\(text\)\) return false/);
assert.match(appJs, /isStudyPackRewriteRequest\(text\) \|\| isImplicitStudyPackWritingRequest\(text\)/);
assert.match(appJs, /function isCasualStateChatRequest/);
assert.match(appJs, /はらへった/);
assert.match(appJs, /isCasualPreferenceQuestion\(text\) \|\| isCasualStateChatRequest\(text\) \? "fast" : "balanced"/);
assert.match(appJs, /contracts\.sourcePdfImport/);
assert.match(appJs, /contracts\.sourceOcrExperiment/);
assert.match(appJs, /function exportContractsCsv/);
assert.match(appJs, /function importContractsJsonFile/);

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
const qrProfile = JSON.parse(new URL(qrTarget).searchParams.get("p"));
assert.equal(qrProfile.name, "しばぱぱ");
assert.equal(qrProfile.userName, "まさふみ");
assert.equal(qrProfile.selfName, "ぼく");
assert.equal(qrProfile.tonePreset, "calm");
assert.equal(qrProfile.personality, "やさしく短く返す");
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
  assert.equal(multiSelectionModel.summaryLabel, "教材パックを選択（2）");
  assert.equal(multiSelectionModel.groups[0].modes[0].checked, true);
  assert.equal(multiSelectionModel.groups[1].modes[0].checked, true);
  assert.deepEqual(Array.from(toggleStudyPackModeValue(["a:one"], "b:two", true)), ["a:one", "b:two"]);
  assert.deepEqual(Array.from(toggleStudyPackModeValue(["a:one", "b:two"], "a:one", false)), ["b:two"]);
  const compactPrompt = compactStudyPackPrompt({
    modeName: "メールを整える",
    mode: {
      prompt: "社外向けメールとして、結論、背景、確認事項が分かるように整えてください。必要以上に硬くしすぎないでください。",
      examples: [
        { input: "長い入力例", output: "長い出力例" },
      ],
    },
    outputPrompt: "出力はまず「修正版:」として、対象本文そのものを書き換えてください。必要な場合だけ、最後に「変更点:」を2〜3個添えてください。",
    includeExamples: false,
  });
  assert.match(compactPrompt, /結論、背景、確認事項/);
  assert.match(compactPrompt, /修正版/);
  assert.doesNotMatch(compactPrompt, /長い入力例|長い出力例/);
  assert.ok(compactPrompt.length < 260);
  assert.equal(shouldApplyStudyPackForText("リライトして\n本文です", { hasSelection: true }), true);
  assert.equal(shouldApplyStudyPackForText("このメールを添削して", { hasSelection: true }), true);
  assert.equal(shouldApplyStudyPackForText("以下につづく返信文を考えて", { hasSelection: true }), true);
  assert.match(appJs, /返信文\|返信案\|返信メール\|メール返信/);
  assert.match(appJs, /function isReplyDraftRequest/);
  assert.match(appJs, /返信本文案:/);
  assert.match(appJs, /studyPackModeOutputPrompt\(selected, requestText = ""\)/);
  assert.match(appJs, /すぐコピペできる返信本文だけ/);
  assert.match(appJs, /hasQuotedMail && hasReplyOpening/);
  assert.match(appJs, /件名案、変更した理由、送信前の確認事項/);
  assert.match(appJs, /studyPackContextSystemPrompt\(text\)/);
  assert.match(appJs, /numPredict: 900/);
  assert.equal(shouldApplyStudyPackForText("ガンダム好き？", { hasSelection: true }), false);
  assert.equal(shouldApplyStudyPackForText("しばぱぱはどの機体が好き？", { hasSelection: true }), false);
  assert.equal(shouldApplyStudyPackForText("ニューガンダムだよ", { hasSelection: true }), false);
  assert.match(appJs, /localStorage\.getItem\("gemma4\.selectedStudyPackModes"\)/);
  assert.match(appJs, /localStorage\.setItem\("gemma4\.selectedStudyPackModes"/);
  assert.doesNotMatch(appJs, /appliedStudyPackModes\.length > 0/);
}

runImportTests().then(() => {
  console.log("management helper tests passed");
});
