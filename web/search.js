(() => {
const SAFE_YOUTUBE_TRANSCRIPT_ERROR = "YouTube字幕を取得できませんでした。";

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

function normalizeSearchDiagnostics(diagnostics) {
  if (!Array.isArray(diagnostics)) return [];
  return diagnostics
    .map((item) => {
      const diagnostic = {
        type: String(item?.type || "").trim(),
        status: String(item?.status || "").trim(),
        label: String(item?.label || "").trim(),
        message: String(item?.message || "").trim(),
        howToSucceed: String(item?.howToSucceed || "").trim(),
      };
      if (diagnostic.type !== "route") {
        return diagnostic.type === "youtube-transcript" && item?.error === SAFE_YOUTUBE_TRANSCRIPT_ERROR
          ? { ...diagnostic, error: SAFE_YOUTUBE_TRANSCRIPT_ERROR }
          : diagnostic;
      }
      const backend = String(item?.backend || "").trim();
      const channel = String(item?.channel || "").trim();
      const errorCode = String(item?.errorCode || "").trim();
      return {
        ...diagnostic,
        backend: ["Jina", "Exa", "YouTube字幕", "GitHub", "RSS", "TOMOS標準検索"].includes(backend) ? backend : "",
        fallback: Boolean(item?.fallback),
        errorCode: ["", "priority-failed", "route-failed", "fallback-failed"].includes(errorCode) ? errorCode : "",
        channel: ["web", "youtube", "github", "rss"].includes(channel) ? channel : "",
      };
    })
    .filter((item) => item.label || item.message);
}

function formatSearchDiagnosticsForDisplay(diagnostics, translate) {
  if (!Array.isArray(diagnostics)) return [];
  const supportedBackends = new Set(["Jina", "Exa", "YouTube字幕", "GitHub", "RSS", "TOMOS標準検索"]);
  const t = typeof translate === "function" ? translate : (key) => key;
  return diagnostics.map((item) => {
    if (item?.type !== "route") return item;
    const hasKnownBackend = supportedBackends.has(item.backend);
    const backend = hasKnownBackend ? item.backend : "TOMOS標準検索";
    const fallbackFailed = item.errorCode === "fallback-failed";
    const routeFailed = item.errorCode === "route-failed";
    const fallback = hasKnownBackend && Boolean(item.fallback);
    const message = fallbackFailed
      ? t("chat.searchRouteFailed", { backend })
      : routeFailed
        ? t("chat.searchRouteRouteFailed", { backend })
        : fallback
          ? t("chat.searchRouteFallback", { backend })
          : t("chat.searchRouteUsed", { backend });
    const howToSucceed = fallbackFailed || routeFailed
      ? t("chat.searchRouteRetryHelp")
      : fallback
        ? t("chat.searchRouteFallbackHelp")
        : t("chat.searchRouteUsedHelp");
    return {
      ...item,
      label: t("chat.searchRouteLabel"),
      message,
      howToSucceed,
      error: "",
    };
  });
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

function shouldAutoUseExternalResearch(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return false;
  const hasSupportedUrl = /https?:\/\/(?:www\.)?(?:youtube\.com\/(?:watch\?|shorts\/|live\/)|youtu\.be\/|github\.com\/|[^\s<>"、。]+\/[^\s<>"、。]*)/i.test(normalized);
  if (!hasSupportedUrl) return false;
  return /(分析|調べ|調査|要約|解説|説明|見て|読んで|確認|評価|比較|まとめ|analy[sz]e|summari[sz]e|explain|review|check|research)/i.test(normalized);
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

function searchDiagnosticsFromEvent(event, currentDiagnostics = []) {
  const nextDiagnostics = normalizeSearchDiagnostics(event?.search?.diagnostics);
  return nextDiagnostics.length > 0 ? nextDiagnostics : normalizeSearchDiagnostics(currentDiagnostics);
}

function searchResultsFromResponse(data) {
  return normalizeSearchResults(data?.search?.results);
}

function searchDiagnosticsFromResponse(data) {
  return normalizeSearchDiagnostics(data?.search?.diagnostics);
}

window.GEMMA_SEARCH = {
  normalizeSearchResults,
  normalizeSearchDiagnostics,
  formatSearchDiagnosticsForDisplay,
  applySearchBudget,
  availableInternetLayerChannels,
  renderWebSearchToggle,
  searchEnabledForChat,
  searchPayloadOptions,
  searchDiagnosticsFromEvent,
  searchDiagnosticsFromResponse,
  searchResultsFromEvent,
  searchResultsFromResponse,
  shouldAutoUseExternalResearch,
  toggleWebSearch,
};
})();
