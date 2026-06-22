(() => {
function gemmaEscapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function gemmaNumberValue(input, fallback) {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
}

function gemmaTextSnippet(value, maxLength = 420) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

function gemmaTimestampForFilename() {
  const date = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function gemmaSlugForFilename(value, fallback = "export") {
  const safe = String(value || "")
    .normalize("NFKC")
    .replace(/[\\/:*?"<>|#%&{}$!'@+`=\s]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
  return safe || fallback;
}

function gemmaDownloadTextFile(filename, content, type = "application/jsonl") {
  const blob = new Blob([content], { type: `${type};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function gemmaFormatDuration(seconds, language) {
  const suffix = language === "en" ? "s" : "秒";
  if (seconds < 10) return `${seconds.toFixed(1)}${suffix}`;
  return `${Math.round(seconds)}${suffix}`;
}

window.GEMMA_UTILS = {
  downloadTextFile: gemmaDownloadTextFile,
  escapeHtml: gemmaEscapeHtml,
  formatDuration: gemmaFormatDuration,
  numberValue: gemmaNumberValue,
  slugForFilename: gemmaSlugForFilename,
  textSnippet: gemmaTextSnippet,
  timestampForFilename: gemmaTimestampForFilename,
};
})();
