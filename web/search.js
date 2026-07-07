(() => {
function normalizeSearchResults(results) {
  if (!Array.isArray(results)) return [];
  return results
    .map((result) => ({
      title: String(result?.title || result?.url || "").trim(),
      url: String(result?.url || "").trim(),
      snippet: String(result?.snippet || "").trim(),
    }))
    .filter((result) => result.url);
}

function searchEnabledForChat({ codingMode, webSearch }) {
  return !codingMode && Boolean(webSearch);
}

function availableInternetLayerChannels(appInfo = {}) {
  const channels = appInfo?.internetLayer?.channels || {};
  return Object.entries(channels)
    .filter(([, value]) => value?.status === "ready")
    .map(([channel]) => channel);
}

function searchPayloadOptions(options, resultCount = 4) {
  const enabled = searchEnabledForChat(options);
  return {
    web_search: enabled,
    search_results: resultCount,
    internet_layer_channels: enabled ? availableInternetLayerChannels(options.appInfo) : [],
  };
}

function renderWebSearchToggle({ button, enabled }) {
  if (!button) return;
  button.classList.toggle("active", Boolean(enabled));
  button.setAttribute("aria-pressed", String(Boolean(enabled)));
}

function toggleWebSearch(state) {
  state.webSearch = !state.webSearch;
  return state.webSearch;
}

function applySearchBudget({ codingMode, webSearch, maxTokens, contextSize, historyTurns }) {
  if (codingMode) {
    return {
      numPredict: Math.max(maxTokens, 4096),
      numCtx: Math.max(contextSize, 8192),
      historyTurns: Math.max(historyTurns, 6),
    };
  }
  if (webSearch) {
    return {
      numPredict: Math.max(maxTokens, 512),
      numCtx: Math.max(contextSize, 4096),
      historyTurns: Math.min(Math.max(historyTurns, 3), 4),
    };
  }
  return {
    numPredict: Math.max(maxTokens, 256),
    numCtx: contextSize,
    historyTurns,
  };
}

function searchResultsFromEvent(event, currentResults = []) {
  const nextResults = normalizeSearchResults(event?.search?.results);
  return nextResults.length > 0 ? nextResults : normalizeSearchResults(currentResults);
}

function searchResultsFromResponse(data) {
  return normalizeSearchResults(data?.search?.results);
}

window.GEMMA_SEARCH = {
  normalizeSearchResults,
  applySearchBudget,
  availableInternetLayerChannels,
  renderWebSearchToggle,
  searchEnabledForChat,
  searchPayloadOptions,
  searchResultsFromEvent,
  searchResultsFromResponse,
  toggleWebSearch,
};
})();
