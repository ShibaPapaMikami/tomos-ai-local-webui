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
  contextMemoryListModel,
} = context.window.GEMMA_MANAGEMENT;

const els = {
  settingsPanel: { hidden: false },
  mobileConnectPanel: { hidden: true },
  studyPacksPanel: { hidden: true },
  trainingManagementPanel: { hidden: true },
  contextMemoryPanel: { hidden: true },
  personRelationshipPanel: { hidden: true },
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

openManagementPanel({ els, panel: els.contextMemoryPanel });
assert.equal(els.studyPacksPanel.hidden, true);
assert.equal(els.contextMemoryPanel.hidden, false);

openManagementPanel({ els, panel: els.personRelationshipPanel });
assert.equal(els.contextMemoryPanel.hidden, true);
assert.equal(els.personRelationshipPanel.hidden, false);

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
  "management.internetLayerReady": "利用可能",
  "management.internetLayerMissing": "未検出",
  "management.internetLayerPermissionRequired": "明示許可が必要",
  "management.internetLayerToolReady": "エージェントリーチ: 検出済み",
  "management.internetLayerToolMissing": "エージェントリーチ: 未導入",
  "management.internetLayerOverallNotInstalled": "未導入",
  "management.internetLayerOverallInstalled": "導入済み",
  "management.internetLayerOverallPartial": "一部利用可能",
  "management.internetLayerOverallReady": "利用可能",
  "management.internetLayerSetupGuide": "導入案内",
  "management.internetLayerSetupNote": "未導入の場合は、この画面のボタンからTOMOS内の専用環境へ安全導入できます。",
  "management.internetLayerStepInstall": "「TOMOSで安全導入」を押します。",
  "management.internetLayerStepRestart": "導入が終わるまで、この画面で進行状況を確認します。",
  "management.internetLayerStepDoctor": "必要に応じて「診断を実行」で利用可能か確認します。",
  "management.internetLayerStepUse": "チャット欄の「外部調査」をONにして送信します。",
  "management.internetLayerSetupInTomos": "TOMOSで安全導入",
  "management.internetLayerSetupConfirm": "エージェントリーチをTOMOS内の専用環境に導入します。GitHubからのダウンロードが発生します。開始しますか？",
  "management.internetLayerSetupRunning": "安全導入中",
  "management.internetLayerSetupQueued": "安全導入を開始しました",
  "management.internetLayerSetupDone": "安全導入が完了しました",
  "management.internetLayerSetupError": "安全導入エラー: {error}",
  "management.internetLayerApiMissing": "このアプリ本体はインターネットレイヤー導入APIに未対応です。最新版へ更新してから再度お試しください。",
  "management.internetLayerContract": "連携仕様",
  "management.internetLayerDoctorCommand": "診断コマンド: agent-reach doctor",
  "management.internetLayerResultSchema": "返却形式: tomos-internet-layer-result-v0.1",
  "management.internetLayerPolicy": "自動インストールなし / 送信前確認あり / 長期記憶へ自動保存なし",
  "management.internetLayerRunDoctor": "診断を実行",
  "management.internetLayerDoctorRunning": "診断中",
  "management.internetLayerDoctorReady": "診断完了",
  "management.internetLayerDoctorProgress": "診断進行状況",
  "management.internetLayerDoctorStarted": "診断を開始しました",
  "management.internetLayerDoctorMissing": "エージェントリーチ未導入",
  "management.internetLayerDoctorError": "診断エラー: {error}",
  "management.internetLayerApiMissingShort": "アプリ本体の更新が必要です",
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
const personRelationshipJs = fs.readFileSync("web/person-relationship.js", "utf8");
const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const searchCapabilitiesElement = { textContent: "" };
const ocrCandidateStatus = { textContent: "", dataset: {} };
const ocrCandidateToggle = {
  textContent: "",
  disabled: false,
  setAttribute(name, value) { this[name] = value; },
};
const internetToolStatus = { textContent: "", dataset: {} };
const internetChannelStatus = {};
context.document.querySelector = (selector) => {
  if (selector === "#plugin-search-capabilities") return searchCapabilitiesElement;
  if (selector === '[data-plugin-candidate-status="ocr"]') return ocrCandidateStatus;
  if (selector === '[data-plugin-candidate-toggle="ocr"]') return ocrCandidateToggle;
  if (selector === "#internet-layer-tool-status") return internetToolStatus;
  const internetChannelMatch = selector.match(/^\[data-internet-channel="([^"]+)"\]$/);
  if (internetChannelMatch) {
    const channel = internetChannelMatch[1];
    internetChannelStatus[channel] = internetChannelStatus[channel] || { textContent: "", dataset: {} };
    return {
      dataset: {},
      querySelector: (innerSelector) => innerSelector === "span" ? internetChannelStatus[channel] : null,
    };
  }
  return null;
};
context.document.querySelectorAll = (selector) => {
  return [];
};
const pluginEls = {
  codegraphPluginStatus: { textContent: "", dataset: {} },
  codegraphPluginToggle: { textContent: "", setAttribute(name, value) { this[name] = value; } },
  appsGroup: { hidden: true },
  personRelationshipToggle: { hidden: false },
  contractsToggle: { hidden: false },
};
renderPluginsPanel({
  els: pluginEls,
  state: {
    appInfo: {
      searchCapabilities: { text: true, docx: true, pdf: true, pdfBackend: "Spotlight", imageOcr: false },
      internetLayer: {
        installed: true,
        channels: {
          web: { status: "ready" },
          github: { status: "ready" },
          youtube: { status: "ready" },
          rss: { status: "ready" },
          sns: { status: "permission-required" },
        },
      },
    },
    plugins: { codegraph: { installed: true }, ocr: { planned: true }, contracts: { installed: false } },
  },
  t,
});
assert.equal(pluginEls.codegraphPluginStatus.textContent, "フォルダー編集で有効にしてください");
assert.match(searchCapabilitiesElement.textContent, /PDF本文/);
assert.equal(ocrCandidateStatus.textContent, "検討リスト入り（まだ使えません）");
assert.equal(ocrCandidateToggle.textContent, "検討リストから外す");
assert.equal(internetToolStatus.textContent, "利用可能");
assert.equal(internetChannelStatus.web.textContent, "利用可能");
assert.equal(internetChannelStatus.sns.textContent, "明示許可が必要");
assert.equal(pluginEls.contractsToggle.hidden, true);
assert.equal(pluginEls.appsGroup.hidden, false);
assert.match(indexHtml, /data-plugin-candidate-status="contracts"/);
assert.match(indexHtml, /data-plugin-candidate-toggle="contracts"/);
assert.match(indexHtml, /data-i18n="management\.pluginContractsTitle"/);
assert.match(indexHtml, /追加DLなし（内蔵機能）/);
assert.match(i18nJs, /"management\.pluginContractsSize": "追加DLなし（内蔵機能）"/);
assert.match(indexHtml, /id="contracts-toggle"[^>]*hidden/);
assert.match(indexHtml, /id="person-relationship-toggle"/);
assert.match(indexHtml, /id="person-relationship-panel"/);
assert.match(indexHtml, /data-person-tab="self"/);
assert.match(indexHtml, /data-person-tab="register"/);
assert.match(indexHtml, /data-person-tab="map"/);
assert.match(indexHtml, /data-person-tab-panel="self" hidden/);
assert.match(indexHtml, /data-person-tab-panel="register"/);
assert.match(indexHtml, /data-person-tab-panel="map" hidden/);
assert.doesNotMatch(indexHtml, /person\.relationshipMapHelp/);
assert.match(indexHtml, /class="person-editor person-register-editor"/);
assert.doesNotMatch(indexHtml, /class="management-card person-editor/);
assert.doesNotMatch(indexHtml, /class="management-card person-map-card/);
assert.doesNotMatch(indexHtml, /class="management-card person-biorhythm-card/);
assert.match(indexHtml, /id="person-list"/);
assert.match(indexHtml, /id="self-last-name"/);
assert.match(indexHtml, /self-field-left/);
assert.match(indexHtml, /self-field-right/);
assert.match(indexHtml, /id="self-personality-summary"/);
assert.ok(indexHtml.indexOf('id="self-notes"') < indexHtml.indexOf('id="self-personality-summary"'));
assert.match(indexHtml, /class="person-self-summary-text" id="self-personality-summary"/);
assert.doesNotMatch(indexHtml, /<textarea id="self-personality-summary"/);
assert.match(indexHtml, /id="self-save"/);
assert.match(indexHtml, /id="self-save-status"/);
assert.match(indexHtml, /id="person-last-name"/);
assert.match(indexHtml, /id="person-first-name"/);
assert.match(indexHtml, /id="person-display-name"/);
assert.match(indexHtml, /id="person-relation-detail"/);
assert.match(indexHtml, /id="person-relationship-map"/);
assert.match(indexHtml, /id="composer-recipient"/);
assert.match(indexHtml, /id="internet-layer-diagnostics"/);
assert.match(indexHtml, /data-internet-channel="web"/);
assert.match(indexHtml, /data-internet-channel="github"/);
assert.match(indexHtml, /data-internet-channel="youtube"/);
assert.match(indexHtml, /data-internet-channel="rss"/);
assert.match(indexHtml, /data-internet-channel="sns"/);
assert.match(indexHtml, /id="internet-layer-tool-status"/);
assert.match(indexHtml, /data-i18n="management\.internetLayerSetupGuide"/);
assert.doesNotMatch(indexHtml, /id="internet-layer-install-prompt"/);
assert.doesNotMatch(indexHtml, /id="internet-layer-copy-install"/);
assert.doesNotMatch(indexHtml, /Codex|Claude Code|依頼文をコピー/);
assert.match(indexHtml, /id="internet-layer-setup"/);
assert.match(indexHtml, /id="internet-layer-setup-status"/);
assert.match(indexHtml, /id="internet-layer-setup-progress"/);
assert.match(indexHtml, /data-i18n="management\.internetLayerStepUse"/);
assert.match(indexHtml, /data-i18n="management\.internetLayerContract"/);
assert.match(indexHtml, /tomos-internet-layer-result-v0\.1/);
assert.match(indexHtml, /id="internet-layer-doctor"/);
assert.match(indexHtml, /id="internet-layer-doctor-status"/);
assert.match(indexHtml, /id="internet-layer-doctor-progress"/);
assert.match(indexHtml, /id="internet-layer-doctor-progress-bar"/);
assert.match(indexHtml, /id="internet-layer-doctor-log"/);
assert.match(indexHtml, /id="composer-external-research"/);
assert.match(indexHtml, /src="\/person-relationship\.js\?v=0\.8\.206-tomos48"/);
assert.match(indexHtml, /src="\/person-name-fortune\.js\?v=0\.8\.206-tomos48"/);
assert.match(i18nJs, /"management\.personRelationship": "人物・関係メモ"/);
assert.match(i18nJs, /"management\.actions": "操作"/);
assert.match(i18nJs, /"person\.selfProfile": "自分の情報"/);
assert.match(i18nJs, /"person\.selfPersonalitySummary": "自分の性格総括"/);
assert.match(i18nJs, /"person\.relationshipMap": "自分との関係図"/);
assert.match(i18nJs, /"person\.biorhythm": "バイオリズム"/);
assert.match(i18nJs, /"person\.personalityType": "MBTI"/);
assert.match(i18nJs, /"person\.photoHelp": "画像はこのPC内の規定フォルダに保存されます。"/);
const personI18nKeys = Array.from(indexHtml.matchAll(/data-i18n(?:-[a-z-]+)?="(person\.[^"]+)"/g))
  .map((match) => match[1]);
for (const key of personI18nKeys) {
  assert.match(i18nJs, new RegExp(`"${escapeRegExp(key)}"`), `${key} should exist in i18n.js`);
}
assert.match(i18nJs, /"management\.internetLayerTitle": "インターネットレイヤー診断"/);
assert.match(i18nJs, /"management\.internetLayerReady": "利用可能"/);
assert.match(i18nJs, /"management\.internetLayerMissing": "未検出"/);
assert.match(i18nJs, /"management\.internetLayerToolReady": "エージェントリーチ: 検出済み"/);
assert.match(i18nJs, /"management\.internetLayerOverallNotInstalled": "未導入"/);
assert.match(i18nJs, /"management\.internetLayerOverallPartial": "一部利用可能"/);
assert.match(i18nJs, /"management\.internetLayerSetupGuide": "導入案内"/);
assert.match(i18nJs, /"management\.internetLayerStepInstall": "「TOMOSで安全導入」を押します。"/);
assert.doesNotMatch(i18nJs, /CodexやClaude Code/);
assert.match(i18nJs, /"management\.internetLayerSetupInTomos": "TOMOSで安全導入"/);
assert.match(i18nJs, /"management\.internetLayerSetupConfirm": "エージェントリーチをTOMOS内の専用環境に導入します。/);
assert.match(i18nJs, /"management\.internetLayerSetupQueued": "安全導入を開始しました"/);
assert.match(i18nJs, /"management\.internetLayerSetupError": "安全導入エラー: \{error\}"/);
assert.match(i18nJs, /"management\.internetLayerApiMissing": "このアプリ本体はインターネットレイヤー導入APIに未対応です。/);
assert.match(i18nJs, /"management\.internetLayerDoctorCommand": "診断コマンド: agent-reach doctor"/);
assert.match(i18nJs, /"management\.internetLayerResultSchema": "返却形式: tomos-internet-layer-result-v0\.1"/);
assert.match(i18nJs, /"management\.internetLayerRunDoctor": "診断を実行"/);
assert.match(i18nJs, /"management\.internetLayerDoctorProgress": "診断進行状況"/);
assert.match(i18nJs, /"management\.internetLayerDoctorStarted": "診断を開始しました"/);
assert.match(i18nJs, /"management\.internetLayerDoctorMissing": "エージェントリーチ未導入"/);
assert.match(i18nJs, /"management\.internetLayerMemoryNote": "外部調査結果は、自動で長期記憶に保存されません。"/);
assert.match(i18nJs, /"composer\.externalResearch": "外部調査"/);
assert.match(i18nJs, /"composer\.externalResearchConfirm": "外部調査を使います。/);
assert.match(i18nJs, /"chat\.webSources": "外部調査の出典"/);
assert.match(stylesCss, /\.person-card/);
assert.match(stylesCss, /\.person-tabs/);
assert.match(stylesCss, /\.person-tab-button\.is-active/);
assert.match(stylesCss, /\.person-register-editor\s*\{[^}]*grid-template-columns: minmax\(0, 1fr\);/s);
assert.match(stylesCss, /\.person-list-header/);
assert.match(stylesCss, /\.person-card-actions/);
assert.match(stylesCss, /\.person-relationship-map/);
assert.match(stylesCss, /\.person-map-ranking-header/);
assert.match(stylesCss, /\.person-rank-number/);
assert.match(stylesCss, /\.person-rank-mark/);
assert.match(stylesCss, /\.person-compatibility-section/);
assert.match(stylesCss, /\.person-map-compatibility/);
assert.match(stylesCss, /\.person-map-compatibility-list/);
assert.match(stylesCss, /\.person-biorhythm-view/);
assert.match(stylesCss, /\.person-biorhythm-card/);
assert.match(stylesCss, /\.person-photo-picker/);
assert.match(stylesCss, /\.inline-save-status/);
assert.match(stylesCss, /\.person-editor \.setting-field/);
assert.match(stylesCss, /\.person-editor \.setting-wide/);
assert.match(stylesCss, /\.person-self-editor \.self-field-left/);
assert.match(stylesCss, /\.person-self-editor \.self-field-right/);
assert.match(stylesCss, /\.internet-diagnostics/);
assert.match(stylesCss, /\.internet-diagnostics\s*\{[^}]*grid-template-columns: minmax\(0, 1fr\);/s);
assert.match(stylesCss, /data-internet-status="ready"/);
assert.match(stylesCss, /data-internet-layer-state="partial"/);
assert.match(stylesCss, /\.internet-layer-steps/);
assert.doesNotMatch(stylesCss, /#internet-layer-install-prompt/);
assert.match(stylesCss, /\.composer-external-toggle/);
assert.match(stylesCss, /\.management-panel:not\(\[hidden\]\) ~ \.messages/);
assert.match(appJs, /function tWithDomFallback/);
assert.match(appJs, /composerExternalResearch/);
assert.match(appJs, /renderWebSearchToggle\(\{ button: els\.composerExternalResearch, enabled: state\.webSearch \}\)/);
assert.match(appJs, /searchPayloadOptions\?\.\(\{ \.\.\.requestOptions, appInfo: state\.appInfo \}, 4\)/);
assert.match(appJs, /function confirmExternalResearchIfNeeded/);
assert.match(appJs, /window\.confirm\(t\("composer\.externalResearchConfirm"\)\)/);
assert.match(appJs, /tWithDomFallback\(element\.dataset\.i18n, element\.textContent\.trim\(\)\)/);
assert.match(appJs, /function setPersonRelationshipTab/);
assert.match(appJs, /function renderPersonProfileSelects/);
assert.match(appJs, /function updateSelfPersonalitySummary/);
assert.match(appJs, /selfPersonalityType\?\.addEventListener\("change", updateSelfPersonalitySummary\)/);
assert.match(appJs, /selfPersonalitySummary\.textContent/);
assert.doesNotMatch(appJs, /selfPersonalitySummary\.value/);
assert.match(appJs, /function handlePersonPhotoFileChange/);
assert.match(appJs, /function relationshipMapPeople/);
assert.match(appJs, /relationshipRankingModel/);
assert.match(appJs, /renderPersonBiorhythm/);
assert.doesNotMatch(appJs, /node\.biorhythm/);
assert.doesNotMatch(personRelationshipJs, /biorhythmPairMonthlyModel/);
assert.match(appJs, /person-ranking-sort/);
assert.match(appJs, /<details class="person-map-link/);
assert.match(appJs, /<summary class="person-rank-summary">/);
assert.match(appJs, /person-rank-mark/);
assert.match(appJs, /person-compatibility-section/);
assert.doesNotMatch(appJs, /person-map-center/);
assert.match(appJs, /currentPersonEditorInput/);
assert.match(appJs, /person-map-compatibility/);
assert.match(appJs, /person-map-compatibility-list/);
assert.match(appJs, /item\.source/);
assert.match(fs.readFileSync("web/person-name-fortune.js", "utf8"), /calculateFiveGrids/);
assert.match(indexHtml, /id="person-photo-file" type="file"/);
assert.match(appJs, /personTabButtons\?\.\forEach|personTabButtons.*forEach/);
assert.match(appJs, /renderPersonRelationshipPanel,\n  \}\);/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /personRelationshipToggle\?\.\addEventListener\("click"/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /internetLayerDiagnosticsModel/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /runInternetLayerDoctor/);
assert.doesNotMatch(fs.readFileSync("web/management.js", "utf8"), /copyInternetLayerInstallPrompt/);
assert.doesNotMatch(fs.readFileSync("web/management.js", "utf8"), /navigator\.clipboard\.writeText/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /startInternetLayerSetup/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /function fetchInternetLayerJson/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /content-type/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /management\.internetLayerApiMissing/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /\/api\/internet-layer\/setup/);
assert.match(fs.readFileSync("web/management.js", "utf8"), /\/api\/internet-layer\/doctor/);
assert.match(fs.readFileSync("web/search.js", "utf8"), /function availableInternetLayerChannels/);
assert.match(fs.readFileSync("web/search.js", "utf8"), /internet_layer_channels/);
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
assert.match(indexHtml, /src="\/i18n\.js\?v=0\.8\.206-tomos48"/);
assert.match(indexHtml, /href="\/styles\.css\?v=0\.8\.206-tomos48"/);
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
assert.doesNotMatch(indexHtml, /id="context-memory-toggle"/);
assert.match(indexHtml, /id="context-memory-panel"/);
assert.match(indexHtml, /id="context-memory-list"/);
assert.match(indexHtml, /id="context-memory-refresh"/);
assert.match(indexHtml, /data-i18n="management\.contextMemory"/);
assert.match(i18nJs, /"management\.contextMemory": "長期記憶"/);
assert.doesNotMatch(i18nJs, /"management\.contextMemory": "追懐"/);
assert.match(i18nJs, /"character\.memoryTitle": "マイキャラの記憶"/);
assert.match(i18nJs, /"character\.memoryHelp": "このPC内に保存されるマイキャラの長期記憶です。保護された記憶は通常会話には自動で混ぜません。"/);
assert.match(i18nJs, /"character\.tabMemory": "マイキャラの記憶"/);
assert.match(indexHtml, /for="character-tab-memory" data-i18n="character\.tabMemory">マイキャラの記憶<\/label>/);
assert.match(i18nJs, /"character\.memoryCategoryNormal": "通常の記憶"/);
assert.match(i18nJs, /"character\.memoryCategoryProtected": "保護された記憶"/);
assert.match(i18nJs, /"character\.memoryAutoSavedNotice": "マイキャラの記憶として保存されました"/);
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

const contextMemoryRows = contextMemoryListModel({
  records: [
    {
      id: "mem-1",
      text: "ユーザーは短い返信を好む",
      sourceType: "memory",
      memoryType: "preference",
      status: "active",
      updatedAt: 100,
      createdAt: 100,
    },
    {
      id: "mem-2",
      text: "削除済み",
      sourceType: "memory",
      status: "deleted",
      createdAt: 90,
    },
  ],
  t,
});
assert.equal(contextMemoryRows.length, 1);
assert.equal(contextMemoryRows[0].id, "mem-1");
assert.equal(contextMemoryRows[0].canEdit, true);
assert.equal(contextMemoryRows[0].canDelete, true);
assert.equal(contextMemoryRows[0].text, "ユーザーは短い返信を好む");
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
assert.match(appJs, /function personRelationshipContextSystemPrompt/);
assert.match(appJs, /personRelationshipContextSystemPrompt\(\)/);
assert.match(appJs, /人物・関係メモ、学習セット、ユーザー提供文/);
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
