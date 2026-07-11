const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/search.js", "utf8"), context, { filename: "web/search.js" });

const {
  applySearchBudget,
  formatSearchDiagnosticsForDisplay,
  normalizeSearchDiagnostics,
  normalizeSearchResults,
  renderWebSearchToggle,
  searchEnabledForChat,
  searchDiagnosticsFromEvent,
  searchDiagnosticsFromResponse,
  searchPayloadOptions,
  searchResultsFromEvent,
  searchResultsFromResponse,
  shouldAutoUseExternalResearch,
  toggleWebSearch,
} = context.window.GEMMA_SEARCH;

const plain = (value) => JSON.parse(JSON.stringify(value));

assert.deepEqual(
  plain(normalizeSearchResults([
    { title: "Open-Meteo", url: "https://open-meteo.com/", snippet: "weather" },
    { title: "No URL", url: "" },
    { url: "https://example.com/" },
  ])),
  [
    { title: "Open-Meteo", url: "https://open-meteo.com/", snippet: "weather" },
    { title: "https://example.com/", url: "https://example.com/", snippet: "" },
  ],
);

const routeDiagnostics = [
  {
    type: "route",
    status: "success",
    label: "使用経路",
    message: "Jinaを使用しました。",
    howToSucceed: "利用可能な経路で確認しています。",
    backend: "Jina",
    fallback: false,
    errorCode: "",
    channel: "web",
    error: "stderr=/Users/name/token",
    command: ["internal"],
  },
  {
    type: "route",
    status: "warning",
    label: "使用経路",
    message: "ExaからTOMOS標準検索へ切り替えました。",
    howToSucceed: "TOMOS標準検索で確認しています。",
    backend: "Exa",
    fallback: true,
    errorCode: "priority-failed",
    channel: "web",
  },
  {
    type: "route",
    status: "error",
    label: "使用経路",
    message: "YouTube字幕で確認できませんでした。",
    howToSucceed: "時間をおいて再送信してください。",
    backend: "YouTube字幕",
    fallback: false,
    errorCode: "route-failed",
    channel: "youtube",
  },
  {
    type: "route",
    status: "error",
    label: "使用経路",
    message: "ExaとTOMOS標準検索で結果を取得できませんでした。",
    howToSucceed: "時間をおいて再送信してください。",
    backend: "Exa",
    fallback: true,
    errorCode: "fallback-failed",
    channel: "web",
  },
  {
    type: "route",
    status: "error",
    label: "使用経路",
    message: "経路を確認できませんでした。",
    howToSucceed: "時間をおいて再送信してください。",
    backend: "stderr=/Users/name/.config/token",
    fallback: "yes",
    errorCode: "internal-command-failed",
    channel: "private",
    error: "cookie=secret",
    localPath: "/Users/name/private",
  },
];
const expectedRouteDiagnostics = [
  {
    type: "route",
    status: "success",
    label: "使用経路",
    message: "Jinaを使用しました。",
    howToSucceed: "利用可能な経路で確認しています。",
    backend: "Jina",
    fallback: false,
    errorCode: "",
    channel: "web",
  },
  {
    type: "route",
    status: "warning",
    label: "使用経路",
    message: "ExaからTOMOS標準検索へ切り替えました。",
    howToSucceed: "TOMOS標準検索で確認しています。",
    backend: "Exa",
    fallback: true,
    errorCode: "priority-failed",
    channel: "web",
  },
  {
    type: "route",
    status: "error",
    label: "使用経路",
    message: "YouTube字幕で確認できませんでした。",
    howToSucceed: "時間をおいて再送信してください。",
    backend: "YouTube字幕",
    fallback: false,
    errorCode: "route-failed",
    channel: "youtube",
  },
  {
    type: "route",
    status: "error",
    label: "使用経路",
    message: "ExaとTOMOS標準検索で結果を取得できませんでした。",
    howToSucceed: "時間をおいて再送信してください。",
    backend: "Exa",
    fallback: true,
    errorCode: "fallback-failed",
    channel: "web",
  },
  {
    type: "route",
    status: "error",
    label: "使用経路",
    message: "経路を確認できませんでした。",
    howToSucceed: "時間をおいて再送信してください。",
    backend: "",
    fallback: true,
    errorCode: "",
    channel: "",
  },
];
assert.deepEqual(plain(normalizeSearchDiagnostics(routeDiagnostics)), expectedRouteDiagnostics);
assert.deepEqual(
  plain(searchDiagnosticsFromEvent({ search: { diagnostics: routeDiagnostics } })),
  expectedRouteDiagnostics,
);
assert.deepEqual(
  plain(searchDiagnosticsFromResponse({ search: { diagnostics: routeDiagnostics } })),
  expectedRouteDiagnostics,
);

const safeYoutubeError = "YouTube字幕を取得できませんでした。";
assert.deepEqual(
  plain(normalizeSearchDiagnostics([
    {
      type: "youtube-transcript",
      status: "error",
      label: "YouTube字幕取得",
      message: "失敗。字幕本文を取得できませんでした。",
      howToSucceed: "時間をおいて再送信してください。",
      error: safeYoutubeError,
    },
    {
      type: "youtube-transcript",
      status: "error",
      label: "YouTube字幕取得",
      message: "失敗。字幕本文を取得できませんでした。",
      howToSucceed: "時間をおいて再送信してください。",
      error: "stderr=/Users/name/.config/token",
    },
  ])),
  [
    {
      type: "youtube-transcript",
      status: "error",
      label: "YouTube字幕取得",
      message: "失敗。字幕本文を取得できませんでした。",
      howToSucceed: "時間をおいて再送信してください。",
      error: safeYoutubeError,
    },
    {
      type: "youtube-transcript",
      status: "error",
      label: "YouTube字幕取得",
      message: "失敗。字幕本文を取得できませんでした。",
      howToSucceed: "時間をおいて再送信してください。",
    },
  ],
);

const routeDisplayTemplates = {
  "chat.searchRouteLabel": "使用経路",
  "chat.searchRouteUsed": "{backend}を使用しました。",
  "chat.searchRouteUsedHelp": "利用可能な経路で確認しています。",
  "chat.searchRouteFallback": "{backend}からTOMOS標準検索へ切り替えました。",
  "chat.searchRouteFallbackHelp": "優先経路が使えなかったため、TOMOS標準検索で確認しています。",
  "chat.searchRouteFailed": "{backend}とTOMOS標準検索で結果を取得できませんでした。",
  "chat.searchRouteRouteFailed": "{backend}で確認できませんでした。",
  "chat.searchRouteRetryHelp": "時間をおいて再送信してください。",
};
const translateRouteDiagnostic = (key, values = {}) => String(routeDisplayTemplates[key] || key).replace(
  /\{(\w+)\}/g,
  (_, name) => String(values[name] || ""),
);
const existingDiagnostic = {
  type: "youtube-transcript",
  label: "YouTube字幕取得",
  message: "字幕本文を使って分析しています。",
  howToSucceed: "要約に使えます。",
  error: safeYoutubeError,
};
const formattedDiagnostics = formatSearchDiagnosticsForDisplay(
  [...expectedRouteDiagnostics, existingDiagnostic],
  translateRouteDiagnostic,
);
assert.equal(formattedDiagnostics[0].message, "Jinaを使用しました。");
assert.equal(formattedDiagnostics[0].howToSucceed, "利用可能な経路で確認しています。");
assert.equal(formattedDiagnostics[1].message, "ExaからTOMOS標準検索へ切り替えました。");
assert.equal(formattedDiagnostics[1].howToSucceed, "優先経路が使えなかったため、TOMOS標準検索で確認しています。");
assert.equal(formattedDiagnostics[2].message, "YouTube字幕で確認できませんでした。");
assert.equal(formattedDiagnostics[2].howToSucceed, "時間をおいて再送信してください。");
assert.equal(formattedDiagnostics[3].message, "ExaとTOMOS標準検索で結果を取得できませんでした。");
assert.equal(formattedDiagnostics[3].howToSucceed, "時間をおいて再送信してください。");
assert.equal(formattedDiagnostics[4].message, "TOMOS標準検索を使用しました。");
assert.equal(formattedDiagnostics[4].howToSucceed, "利用可能な経路で確認しています。");
assert.strictEqual(formattedDiagnostics[5], existingDiagnostic);

assert.equal(searchEnabledForChat({ codingMode: false, webSearch: true }), true);
assert.equal(searchEnabledForChat({ codingMode: true, webSearch: true }), false);
assert.equal(searchEnabledForChat({ codingMode: false, webSearch: false }), false);
assert.equal(shouldAutoUseExternalResearch("https://www.youtube.com/watch?v=zfN4QApep6s この動画を分析して"), true);
assert.equal(shouldAutoUseExternalResearch("https://youtu.be/abc123 を要約して"), true);
assert.equal(shouldAutoUseExternalResearch("https://github.com/openai/codex を調べて"), true);
assert.equal(shouldAutoUseExternalResearch("https://www.youtube.com/watch?v=zfN4QApep6s"), false);
assert.deepEqual(plain(searchPayloadOptions({ codingMode: false, webSearch: true }, 6)), {
  web_search: true,
  search_results: 6,
  internet_layer_channels: [],
});
assert.deepEqual(plain(searchPayloadOptions({ codingMode: true, webSearch: true }, 4)), {
  web_search: false,
  search_results: 4,
  internet_layer_channels: [],
});
assert.deepEqual(plain(searchPayloadOptions({
  codingMode: false,
  webSearch: true,
  appInfo: {
    internetLayer: {
      channels: {
        youtube: { status: "ready" },
        rss: { status: "missing" },
      },
    },
  },
}, 4)), {
  web_search: true,
  search_results: 4,
  internet_layer_channels: ["youtube"],
});
assert.deepEqual(plain(applySearchBudget({
  codingMode: false,
  webSearch: true,
  maxTokens: 96,
  contextSize: 2048,
  historyTurns: 8,
})), {
  numPredict: 512,
  numCtx: 4096,
  historyTurns: 4,
});
assert.deepEqual(plain(applySearchBudget({
  codingMode: true,
  webSearch: true,
  maxTokens: 96,
  contextSize: 2048,
  historyTurns: 2,
})), {
  numPredict: 4096,
  numCtx: 8192,
  historyTurns: 6,
});

const fakeButton = {
  active: false,
  attrs: {},
  classList: {
    toggle(name, enabled) {
      if (name === "active") fakeButton.active = enabled;
    },
  },
  setAttribute(name, value) {
    fakeButton.attrs[name] = value;
  },
};
renderWebSearchToggle({ button: fakeButton, enabled: true });
assert.equal(fakeButton.active, true);
assert.equal(fakeButton.attrs["aria-pressed"], "true");
const searchState = { webSearch: false };
assert.equal(toggleWebSearch(searchState), true);
assert.equal(searchState.webSearch, true);

const previous = [{ title: "Previous", url: "https://previous.example/", snippet: "" }];
assert.deepEqual(plain(searchResultsFromEvent({ type: "chunk" }, previous)), previous);
assert.deepEqual(
  plain(searchResultsFromEvent({ search: { results: [{ title: "Next", url: "https://next.example/" }] } }, previous)),
  [{ title: "Next", url: "https://next.example/", snippet: "" }],
);
assert.deepEqual(
  plain(searchResultsFromResponse({ search: { results: [{ title: "Result", url: "https://result.example/" }] } })),
  [{ title: "Result", url: "https://result.example/", snippet: "" }],
);

const appSource = fs.readFileSync("web/app.js", "utf8");
const i18nSource = fs.readFileSync("web/i18n.js", "utf8");
assert.match(appSource, /formatSearchDiagnosticsForDisplay,/);
assert.match(appSource, /formatSearchDiagnosticsForDisplay\(streamSearchDiagnostics, t\)/);
assert.match(appSource, /formatSearchDiagnosticsForDisplay\(searchDiagnosticsFromResponse\?\.\(data\) \|\| \[\], t\)/);
assert.doesNotMatch(appSource, /function displaySearchDiagnostics\(/);
assert.match(i18nSource, /"chat\.searchRouteLabel": "使用経路"/);
assert.match(i18nSource, /"chat\.searchRouteRouteFailed": "\{backend\}で確認できませんでした。"/);
assert.match(i18nSource, /"chat\.searchRouteRouteFailed": "Could not verify with \{backend\}\."/);

console.log("search helper tests passed");
