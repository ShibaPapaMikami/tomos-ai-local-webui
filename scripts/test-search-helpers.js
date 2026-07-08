const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/search.js", "utf8"), context, { filename: "web/search.js" });

const {
  applySearchBudget,
  normalizeSearchResults,
  renderWebSearchToggle,
  searchEnabledForChat,
  searchPayloadOptions,
  searchResultsFromEvent,
  searchResultsFromResponse,
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

assert.equal(searchEnabledForChat({ codingMode: false, webSearch: true }), true);
assert.equal(searchEnabledForChat({ codingMode: true, webSearch: true }), false);
assert.equal(searchEnabledForChat({ codingMode: false, webSearch: false }), false);
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

console.log("search helper tests passed");
