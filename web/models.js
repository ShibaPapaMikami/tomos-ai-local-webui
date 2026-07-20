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
  if (model === "gemma4:12b-mlx") {
    return `Gemma 4 12B MLX 高速版 (${translate("model.gemmaMlxFast")}${installed ? "" : ` / ${translate("model.downloadRequired")}`})`;
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
  if (model === "Qwen/Qwen3-4B-Instruct-2507" || model.includes("Qwen3-4B-Instruct-2507-GGUF")) return "Qwen3 4B Instruct 2507";
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
  if (model === "gemma4:12b-mlx") return "Gemma 4 MLX";
  if (model === "gemma4:12b") return "Gemma 4";
  if (model === "qwen2.5:3b") return "Qwen";
  if (model === "Qwen/Qwen3-4B-Instruct-2507" || model.includes("Qwen3-4B-Instruct-2507-GGUF")) return "Qwen3 2507";
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
  if (model === "gemma4:12b-mlx") return "Apple Silicon向け高速チャット・コード生成";
  if (model === "gemma4:12b") return "標準チャット・画像理解";
  if (model === "qwen2.5:3b") return "低スペックPC・移行用の予備";
  if (model === "Qwen/Qwen3-4B-Instruct-2507" || model.includes("Qwen3-4B-Instruct-2507-GGUF")) return "標準AI・資料検索・学習パック";
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

const GEMMA_QWEN3_2507_MODEL = "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL";
const GEMMA_AGENTIC_CODER_MODEL = "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M";

function gemmaModelClassification(model, serverModels = {}) {
  const pullable = Array.isArray(serverModels.pullable) ? serverModels.pullable : [];
  return pullable.find((item) => item?.model === model) || null;
}

function gemmaModelHasUnsafeClassification(model, serverModels = {}) {
  const classification = gemmaModelClassification(model, serverModels);
  if (!classification) return false;
  const category = [classification.role, classification.tier, classification.family]
    .map((value) => String(value || "").toLowerCase())
    .join(" ");
  return /(experimental|enterprise|hidden|adult|uncensored|abliterated)/.test(category);
}

function gemmaIsStudentHiddenModel(model = "", serverModels = {}) {
  const value = String(model || "");
  return value.includes("Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced")
    || value.includes("Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated")
    || /(^|[/:._-])(enterprise|experimental)(?=$|[/:._-])/i.test(value)
    || gemmaModelHasUnsafeClassification(value, serverModels);
}

function gemmaSafeSavedModel(model = "", serverModels = {}) {
  const value = String(model || "").trim();
  return gemmaIsStudentHiddenModel(value, serverModels) ? "" : value;
}

function gemmaModelCanAutoSelect(model, serverModels = {}) {
  const value = String(model || "").trim();
  const classification = gemmaModelClassification(value, serverModels);
  const knownAllowed = [
    GEMMA_QWEN3_2507_MODEL,
    "qwen2.5:3b",
    "gemma4:12b",
    "gemma4:12b-mlx",
    GEMMA_AGENTIC_CODER_MODEL,
  ].includes(value);
  return Boolean(value)
    && (knownAllowed || classification?.allowAutoSelect === true)
    && !gemmaIsStudentHiddenModel(value, serverModels);
}

function gemmaCoreModel(options = {}) {
  const serverModels = options.serverModels || {};
  const installed = typeof options.modelIsInstalled === "function"
    ? options.modelIsInstalled
    : (model) => gemmaModelIsInstalled(model, serverModels);
  if (
    (installed(GEMMA_QWEN3_2507_MODEL) || serverModels.chat === GEMMA_QWEN3_2507_MODEL)
    && gemmaModelCanAutoSelect(GEMMA_QWEN3_2507_MODEL, serverModels)
  ) {
    return GEMMA_QWEN3_2507_MODEL;
  }
  if (installed("qwen2.5:3b") && gemmaModelCanAutoSelect("qwen2.5:3b", serverModels)) return "qwen2.5:3b";
  return gemmaModelCanAutoSelect(serverModels.chat, serverModels) ? serverModels.chat : "gemma4:12b";
}

function gemmaModelForTask(task, options = {}) {
  const serverModels = options.serverModels || {};
  const overrides = options.modelOverrides || {};
  if (options.useComposer && gemmaIsStudentHiddenModel(options.composerModel, serverModels)) return gemmaCoreModel(options);
  const composerModel = gemmaSafeSavedModel(options.composerModel, serverModels);
  if (options.useComposer && composerModel) return composerModel;
  if (gemmaIsStudentHiddenModel(overrides[task], serverModels)) return gemmaCoreModel(options);
  const override = gemmaSafeSavedModel(overrides[task], serverModels);
  if (override) return override;
  if (task === "coding") {
    const installed = typeof options.modelIsInstalled === "function"
      ? options.modelIsInstalled
      : (model) => gemmaModelIsInstalled(model, serverModels);
    if (installed(GEMMA_AGENTIC_CODER_MODEL) && gemmaModelCanAutoSelect(GEMMA_AGENTIC_CODER_MODEL, serverModels)) {
      return GEMMA_AGENTIC_CODER_MODEL;
    }
  }
  return gemmaCoreModel(options);
}

function gemmaFallbackCodingModel(options = {}) {
  return gemmaCoreModel(options);
}

function gemmaFastChatModel(options = {}) {
  return gemmaCoreModel(options);
}

function gemmaModelForRequestTask(task, requestOptions = {}, options = {}) {
  const serverModels = options.serverModels || {};
  const overrides = options.modelOverrides || {};
  const installed = typeof options.modelIsInstalled === "function"
    ? options.modelIsInstalled
    : (model) => gemmaModelIsInstalled(model, serverModels);
  if (requestOptions.hasImages === true) {
    if (installed("gemma4:12b-mlx")) return "gemma4:12b-mlx";
    if (installed("gemma4:12b")) return "gemma4:12b";
    return "";
  }
  if (gemmaIsStudentHiddenModel(options.composerModel, serverModels)) return gemmaCoreModel(options);
  const composerModel = gemmaSafeSavedModel(options.composerModel, serverModels);
  if (composerModel) return composerModel;
  if (task === "chat" && requestOptions.fastModel) return gemmaFastChatModel(options);
  if (task === "translation" && !overrides.translation && requestOptions.responseMode === "quality") {
    return gemmaCoreModel(options);
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
  coreModel: gemmaCoreModel,
  modelCanAutoSelect: gemmaModelCanAutoSelect,
  isStudentHiddenModel: gemmaIsStudentHiddenModel,
  safeSavedModel: gemmaSafeSavedModel,
  modelForTask: gemmaModelForTask,
  fallbackCodingModel: gemmaFallbackCodingModel,
  fastChatModel: gemmaFastChatModel,
  modelForRequestTask: gemmaModelForRequestTask,
};
})();
