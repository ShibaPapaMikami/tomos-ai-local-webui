(() => {
function gemmaTranslationBudget(text, configuredMaxTokens) {
  const sourceLength = gemmaTranslationSourceText(text).length;
  const numPredict = Math.min(4096, Math.max(configuredMaxTokens, 512, Math.ceil(sourceLength * 1.7)));
  const numCtx = Math.min(8192, Math.max(4096, Math.ceil(sourceLength * 2.4)));
  return { numPredict, numCtx };
}

function gemmaIsTranslationInstructionLine(line) {
  return /^\s*(?:日本語\s*に\s*(?:やく|訳|翻訳)?\s*して(?:ください|下さい)?|英語\s*に\s*(?:やく|訳|翻訳)?\s*して(?:ください|下さい)?|英訳|和訳|翻訳|訳|(?:please\s+)?translate(?:\s+(?:this|it|the\s+following|to\s+\w+|into\s+\w+))*)\s*[。.!！?？]*\s*(?:[:：-]\s*)?$/i.test(line);
}

function gemmaIsTranslationRequest(text) {
  const normalized = String(text || "").trim();
  if (/英訳|和訳|翻訳|訳して|translate/i.test(normalized)) return true;
  const firstLine = normalized.split(/\r?\n/)[0] || "";
  return gemmaIsTranslationInstructionLine(firstLine);
}

function gemmaTranslationSourceText(text) {
  const lines = String(text || "").trim().split(/\r?\n/);
  while (lines.length > 0 && (!lines[0].trim() || gemmaIsTranslationInstructionLine(lines[0]))) {
    lines.shift();
  }
  const source = lines.join("\n").trim();
  return source || String(text || "").replace(/^(翻訳して|英訳して|和訳して|translate)\s*/i, "").trim();
}

function gemmaTranslationTargetIsJapanese(text) {
  return /日本語\s*に|和訳|to\s+japanese|into\s+japanese/i.test(text);
}

function gemmaTranslationNeedsQuality(text) {
  const source = gemmaTranslationSourceText(text);
  return source.length > 220 || gemmaTranslationTargetIsJapanese(text);
}

window.GEMMA_TRANSLATION = {
  translationBudget: gemmaTranslationBudget,
  isTranslationRequest: gemmaIsTranslationRequest,
  isTranslationInstructionLine: gemmaIsTranslationInstructionLine,
  translationSourceText: gemmaTranslationSourceText,
  translationTargetIsJapanese: gemmaTranslationTargetIsJapanese,
  translationNeedsQuality: gemmaTranslationNeedsQuality,
};
})();
