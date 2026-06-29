(() => {
function gemmaDisplayModelName(model, task = "chat", helpers = {}) {
  const { t, modelIsInstalled } = helpers;
  const translate = typeof t === "function" ? t : (key) => key;
  const installed = typeof modelIsInstalled === "function" ? modelIsInstalled(model) : false;
  if (!model) return translate("model.serverDefault");
  if (model.includes("Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated")) {
    return `Huihui Gemma 4 Coder 12B Abliterated (${translate("model.experimental")}${installed ? "" : ` / ${translate("model.downloadRequired")}`})`;
  }
  if (model.includes("gemma-4-12B-agentic-fable5")) {
    return `Gemma 4 Agentic Coder 12B Q4 (${translate("model.coderRecommended")}${installed ? "" : ` / ${translate("model.downloadRequired")}`})`;
  }
  if (model.includes("gemma-4-12B-coder-fable5")) {
    return `Gemma 4 Coder 12B Q4 (${translate("model.coderRecommended")}${installed ? "" : ` / ${translate("model.downloadRequired")}`})`;
  }
  if (model.includes("Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced")) {
    return `HauhauCS Balanced 12B Q4${installed ? "" : ` (${translate("model.downloadRequired")})`}`;
  }
  if (model === "gemma4:12b") {
    if (task === "coding") return `Gemma 4 12B (${translate("model.gemmaCoding")})`;
    if (task === "translation") return `Gemma 4 12B (${translate("model.gemmaTranslation")})`;
    return `Gemma 4 12B (${translate("model.gemmaStandard")})`;
  }
  if (model === "qwen2.5:3b") {
    if (task === "translation") return `Qwen 2.5 3B (${translate("model.qwenTranslation")})`;
    return `Qwen 2.5 3B (${translate("model.qwenFast")})`;
  }
  if (model === "phi3:latest") return "Phi-3";
  if (model === "llama3:latest") return "Llama 3";
  if (model === "qwen3:4b") return "Qwen3 4B";
  return `${model}${installed ? "" : ` (${translate("model.missing")})`}`;
}

function gemmaShortModelName(model, task = "chat", helpers = {}) {
  return gemmaDisplayModelName(model, task, helpers)
    .replace(/（[^）]*）/g, "")
    .replace(/\s*\([^)]*\)/g, "");
}

function gemmaComposerModelLabel(model, helpers = {}) {
  const { t } = helpers;
  const translate = typeof t === "function" ? t : (key) => key;
  if (!model) return translate("model.auto");
  if (model.includes("Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated")) return "Huihui 実験";
  if (model.includes("gemma-4-12B-agentic-fable5")) return "Agentic Coder";
  if (model.includes("gemma-4-12B-coder-fable5")) return "Coder";
  if (model.includes("Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced")) return "HauhauCS";
  if (model === "gemma4:12b") return "Gemma 4";
  if (model === "qwen2.5:3b") return "Qwen";
  if (model === "phi3:latest") return "Phi-3";
  if (model === "llama3:latest") return "Llama";
  if (model === "qwen3:4b") return "Qwen3";
  return gemmaShortModelName(model, "chat", helpers);
}

function gemmaModelPurpose(model, task = "chat", helpers = {}) {
  const pullable = Array.isArray(helpers.pullable) ? helpers.pullable : [];
  const matched = pullable.find((item) => item && item.model === model);
  if (matched?.purpose) return matched.purpose;
  if (!model) return "";
  if (model.includes("Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated")) return "コード実験・制限弱め・上級者向け";
  if (model.includes("gemma-4-12B-agentic-fable5")) return "コード生成・修正・デバッグ";
  if (model.includes("gemma-4-12B-coder-fable5")) return "コード生成・修正・デバッグ";
  if (model.includes("Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced")) return "強化型チャット・制限弱め・PC負荷強";
  if (model === "gemma4:12b") return "標準チャット・画像理解";
  if (model === "qwen2.5:3b") return "高速チャット・翻訳";
  if (task === "coding") return "コード生成";
  if (task === "translation") return "翻訳";
  return "";
}

function gemmaTaskLabel(task, t) {
  if (task === "translation") return t("task.translation");
  if (task === "coding") return t("task.coding");
  return t("task.chat");
}

function gemmaResponseModeLabel(mode, t) {
  return {
    auto: t("mode.auto"),
    fast: t("mode.fast"),
    balanced: t("mode.balanced"),
    quality: t("mode.quality"),
  }[mode] || mode;
}

function gemmaModelIsInstalled(model, serverModels = {}) {
  return Array.isArray(serverModels.available) && serverModels.available.includes(model);
}

function gemmaModelForTask(task, options = {}) {
  const serverModels = options.serverModels || {};
  const overrides = options.modelOverrides || {};
  const composerModel = String(options.composerModel || "").trim();
  if (options.useComposer && composerModel) return composerModel;
  if (overrides[task]) return overrides[task];
  return serverModels[task] || serverModels.chat || "";
}

function gemmaFallbackCodingModel(options = {}) {
  const serverModels = options.serverModels || {};
  return serverModels.chat || "gemma4:12b";
}

function gemmaFastChatModel(options = {}) {
  const serverModels = options.serverModels || {};
  const isInstalled = typeof options.modelIsInstalled === "function"
    ? options.modelIsInstalled("qwen2.5:3b")
    : gemmaModelIsInstalled("qwen2.5:3b", serverModels);
  if (isInstalled || serverModels.translation === "qwen2.5:3b") return "qwen2.5:3b";
  return serverModels.chat || "gemma4:12b";
}

function gemmaModelForRequestTask(task, requestOptions = {}, options = {}) {
  const serverModels = options.serverModels || {};
  const overrides = options.modelOverrides || {};
  const composerModel = String(options.composerModel || "").trim();
  if (composerModel) return composerModel;
  if (task === "chat" && requestOptions.fastModel) return gemmaFastChatModel(options);
  if (task === "translation" && !overrides.translation && requestOptions.responseMode === "quality") {
    return serverModels.chat || "gemma4:12b";
  }
  return gemmaModelForTask(task, options);
}

window.GEMMA_MODELS = {
  displayModelName: gemmaDisplayModelName,
  shortModelName: gemmaShortModelName,
  composerModelLabel: gemmaComposerModelLabel,
  modelPurpose: gemmaModelPurpose,
  taskLabel: gemmaTaskLabel,
  responseModeLabel: gemmaResponseModeLabel,
  modelIsInstalled: gemmaModelIsInstalled,
  modelForTask: gemmaModelForTask,
  fallbackCodingModel: gemmaFallbackCodingModel,
  fastChatModel: gemmaFastChatModel,
  modelForRequestTask: gemmaModelForRequestTask,
};
})();
