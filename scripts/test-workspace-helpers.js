const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const source = fs.readFileSync("web/workspace.js", "utf8");
const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(source, context, { filename: "web/workspace.js" });

const {
  extractJsonObject,
  formatSearchResults,
  inferSimpleTextSave,
  isWorkspaceSourceContentFollowup,
  normalizeWorkspacePlan,
  parseWorkspaceGeneration,
  renderWorkspacePanel,
} = context.window.GEMMA_WORKSPACE;

function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

assert.deepEqual(
  plain(inferSimpleTextSave({
    text: "三上昌史についてというテキストファイルをtestフォルダに保存して",
    hasWorkspace: true,
  })),
  {
    path: "三上昌史について.txt",
    content: "三上昌史について\n",
  },
);

assert.deepEqual(
  plain(inferSimpleTextSave({
    text: "hello.txtにhelloと記載して保存して",
    hasWorkspace: true,
  })),
  {
    path: "hello.txt",
    content: "hello\n",
  },
);

assert.equal(
  inferSimpleTextSave({
    text: "フォルダー内にシンプルなWebサイトを作って保存して",
    hasWorkspace: true,
  }),
  null,
);

assert.equal(
  inferSimpleTextSave({
    text: "三上昌史についてというテキストファイルを保存して",
    hasWorkspace: false,
  }),
  null,
);

assert.equal(
  isWorkspaceSourceContentFollowup?.("内容を教えて", { hasWorkspaceRoot: true }),
  true,
);

assert.equal(
  isWorkspaceSourceContentFollowup?.(
    `リライトして

飯嶋様

ご共有いただいたプレスリリース原稿およびメッセージ原稿、誠にありがとうございます。
こちら拝見し、内容を確認させていただきます。`,
    {
      hasWorkspaceRoot: true,
      isExcludedRequest: (value) => /リライト|添削|校正|書き直|書き換/.test(value),
    },
  ),
  false,
);

assert.deepEqual(
  plain(extractJsonObject('```json\n{summary: "ok", files: [{"path":"index.html","content":"<html></html>"}],}\n```')),
  {
    summary: "ok",
    files: [{ path: "index.html", content: "<html></html>" }],
  },
);

assert.deepEqual(
  plain(parseWorkspaceGeneration('{"summary":"保存","files":[{"path":"./index.html","content":"<!doctype html>\\n"}],"notes":["確認"]}')),
  {
    summary: "保存",
    notes: ["確認"],
    files: [{ path: "index.html", content: "<!doctype html>\n" }],
  },
);

assert.deepEqual(
  plain(parseWorkspaceGeneration('index.html\n```html\n<!doctype html>\n<html></html>\n```')),
  {
    summary: "コードブロックからファイルを生成しました。",
    notes: ["JSONが不完全な場合は、コードブロック形式から保存します。"],
    files: [{ path: "index.html", content: "<!doctype html>\n<html></html>\n" }],
  },
);

assert.deepEqual(
  plain(normalizeWorkspacePlan({
    summary: "2ファイル",
    files: [
      { path: "./index.html", purpose: "画面" },
      { path: "src/app.js" },
      { path: "README.md", purpose: "説明" },
      { path: "extra.txt", purpose: "無視" },
    ],
  })),
  {
    summary: "2ファイル",
    files: [
      { path: "index.html", purpose: "画面" },
      { path: "src/app.js", purpose: "このファイルを実装します。" },
      { path: "README.md", purpose: "説明" },
    ],
  },
);

const t = (key) => ({
  "workspace.searchNoResults": "一致するテキストは見つかりませんでした。",
  "workspace.searchMore": "ほか {count} 件",
  "workspace.searchSourceText": "テキスト",
  "workspace.searchSourceWord": "Word",
  "workspace.searchSourcePdf": "PDF",
  "workspace.searchSourceHtml": "HTML",
  "workspace.searchMatchBody": "本文",
  "workspace.searchMatchFilename": "ファイル名",
  "workspace.searchPdfUnreadable": "{count}件のPDFは本文を読み取れませんでした（{backend}）。",
}[key] || key).replace("{count}", "1").replace("{backend}", "Spotlight");
const searchHtml = formatSearchResults({
  data: {
    pdfUnreadable: 1,
    pdfBackend: "Spotlight",
    results: [{
      path: "契約書.pdf",
      line: 3,
      preview: "秘密保持契約の本文です。",
      sourceKind: "pdf",
      matchType: "body",
    }, {
      path: "契約書.txt",
      line: 1,
      preview: "ファイル名に検索語が含まれています。",
      sourceKind: "txt",
      matchType: "filename",
    }],
  },
  t,
});
assert.match(searchHtml, /PDF/);
assert.match(searchHtml, /本文/);
assert.match(searchHtml, /ファイル名/);
assert.match(searchHtml, /PDFは本文を読み取れませんでした/);

const codegraphStatusT = (key, values = {}) => ({
  "workspace.noFolder": "フォルダーなし",
  "workspace.codeUnderstandingOff": "OFFです。使う場合はチェックしてから準備してください。",
  "workspace.codeUnderstandingNotReady": "有効です。準備すると使えます。",
  "workspace.codeUnderstandingPreparing": "コード理解を準備中...",
  "workspace.codeUnderstandingReady": "使用できます: {files}件のコードを解析しました。",
  "workspace.codeUnderstandingError": "準備できませんでした。もう一度準備してください: {error}",
  "workspace.knowledgeSearchOff": "資料検索OFF",
  "workspace.knowledgeSearchNotReady": "資料検索ON",
  "workspace.knowledgeSearchPreparing": "資料検索準備中",
  "workspace.knowledgeSearchReady": "資料検索OK {files}/{texts}/{failed}",
  "workspace.knowledgeSearchError": "資料検索エラー {error}",
  "workspace.notConfigured": "{name}のフォルダーを設定してください。",
  "workspace.loaded": "{name}を読み込みました。",
}[key] || key)
  .replace("{files}", values.files ?? "")
  .replace("{texts}", values.texts ?? "")
  .replace("{failed}", values.failed ?? "")
  .replace("{error}", values.error ?? "")
  .replace("{name}", values.name ?? "");

const workspaceEls = {
  workspacePanel: { hidden: false },
  workspaceFolderName: { textContent: "" },
  workspaceFolderTitle: { value: "" },
  workspaceRoot: { value: "" },
  workspaceCodegraphRow: { hidden: true },
  workspaceCodegraphEnabled: { checked: false },
  workspaceCodegraphPrepare: { disabled: false },
  workspaceCodegraphStatus: { textContent: "" },
  workspaceCodegraphFiles: { hidden: false, innerHTML: "" },
  workspaceKnowledgeEnabled: { checked: false },
  workspaceKnowledgePrepare: { disabled: false },
  workspaceKnowledgeStatus: { textContent: "" },
  workspaceSearchRow: { hidden: true },
  workspaceSearchStatus: { textContent: "", dataset: {} },
  workspaceStatus: { textContent: "" },
  workspaceFiles: { innerHTML: "", append() {} },
};

renderWorkspacePanel({
  activeFolder: {
    name: "テスト",
    plugins: {
      codegraph: { enabled: true, status: "not-ready" },
      knowledge: { enabled: true, status: "ready", fileCount: 3, textCount: 2, failedCount: 1 },
    },
  },
  els: workspaceEls,
  state: {
    plugins: { codegraph: { installed: true } },
    workspaceOpen: true,
    workspaceRoot: "/tmp/project",
    selectedFiles: new Set(),
    workspaceFiles: [],
  },
  t: codegraphStatusT,
});
assert.equal(workspaceEls.workspaceCodegraphStatus.textContent, "有効です。準備すると使えます。");
assert.equal(workspaceEls.workspaceKnowledgeEnabled.checked, true);
assert.equal(workspaceEls.workspaceKnowledgePrepare.disabled, false);
assert.equal(workspaceEls.workspaceKnowledgeStatus.textContent, "資料検索OK 3/2/1");

console.log("workspace helper tests passed");
