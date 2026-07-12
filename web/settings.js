(() => {
function renderGemmaSettingsMeta(deps) {
  const {
    els,
    escapeHtml,
    state,
  } = deps;
  if (!els.settingsMeta) return;
  const unknown = state.language === "en" ? "unknown" : "不明";
  const version = state.appInfo.version || unknown;
  const commit = state.appInfo.commit || unknown;
  const languageLabel = state.language === "en" ? "English" : "日本語";
  const themeLabel = {
    dark: state.language === "en" ? "Dark" : "ダーク",
    light: state.language === "en" ? "Light" : "ライト",
    green: state.language === "en" ? "Green" : "グリーン",
  }[state.theme] || state.theme;
  const lines = [
    `<div>${state.language === "en" ? "App" : "アプリ版"}: ${escapeHtml(version)} / commit ${escapeHtml(commit)}</div>`,
    `<div>${state.language === "en" ? "Language" : "表示言語"}: ${escapeHtml(languageLabel)}</div>`,
    `<div>${state.language === "en" ? "Theme" : "テーマ"}: ${escapeHtml(themeLabel)}</div>`,
  ];
  const pcLabel = state.appInfo?.pcDiagnostics?.recommendation?.label;
  if (pcLabel) {
    lines.push(`<div>${state.language === "en" ? "PC diagnosis" : "PC診断"}: ${escapeHtml(pcLabel)}</div>`);
  }
  els.settingsMeta.innerHTML = lines.join("");
}

function renderSearchCapabilitiesPanel(deps) {
  const { els, escapeHtml, state, t } = deps;
  if (!els.searchCapabilities) return;
  const capabilities = state.appInfo.searchCapabilities;
  if (!capabilities) {
    els.searchCapabilities.innerHTML = "";
    return;
  }
  const items = [
    { ok: Boolean(capabilities.text), label: t("settings.searchText") },
    { ok: Boolean(capabilities.docx), label: t("settings.searchWord") },
    {
      ok: Boolean(capabilities.pdf),
      label: capabilities.pdf
        ? t("settings.searchPdfReady", { backend: capabilities.pdfBackend || "PDF" })
        : t("settings.searchPdfFilenameOnly"),
    },
    { ok: Boolean(capabilities.imageOcr), label: t("settings.searchImageOcr") },
  ];
  const note = capabilities.pdf
    ? t("settings.searchCapabilitiesReadyHelp")
    : t("settings.searchPdfSetupHelp");
  els.searchCapabilities.innerHTML = `
    <div class="search-capabilities-title">
      <strong>${escapeHtml(t("settings.workspaceSearch"))}</strong>
      <span>${escapeHtml(t("settings.searchCapabilitiesHelp"))}</span>
    </div>
    <div class="search-capability-list">
      ${items.map((item) => `
        <span class="search-capability ${item.ok ? "ok" : "missing"}">
          <span aria-hidden="true">${item.ok ? "✓" : "–"}</span>
          ${escapeHtml(item.label)}
        </span>
      `).join("")}
    </div>
    <div class="search-capabilities-note">${escapeHtml(note)}</div>
  `;
}

function renderPcDiagnosticsPanel(deps) {
  const {
    els,
    escapeHtml,
    state,
  } = deps;
  if (!els.pcDiagnostics) return;
  const diagnostics = state.appInfo?.pcDiagnostics;
  if (!diagnostics?.ok) {
    els.pcDiagnostics.innerHTML = "";
    return;
  }
  const language = state.language === "en" ? "en" : "ja";
  const system = diagnostics.system || {};
  const recommendation = diagnostics.recommendation || {};
  const recommended = recommendation.recommended || {};
  const label = recommendation.label || (language === "en" ? "Unknown" : "不明");
  const title = language === "en" ? "PC diagnosis" : "PC診断";
  const summary = recommendation.summary || "";
  const memory = Number(system.memoryGb || 0);
  const specLine = [
    system.cpu || system.machine || "",
    memory ? `${memory}GB RAM` : "",
    system.ollamaVersion ? `Ollama ${system.ollamaVersion}` : "",
  ].filter(Boolean).join(" / ");
  const ollamaVersionParts = String(system.ollamaVersion || "")
    .split(".")
    .map((part) => Number.parseInt(part, 10) || 0);
  const ollamaOutdated = Boolean(system.ollamaVersion)
    && (
      ollamaVersionParts[0] < 0
      || (ollamaVersionParts[0] === 0 && ollamaVersionParts[1] < 31)
    );
  const availableModels = new Set(Array.isArray(system.availableModels) ? system.availableModels : []);
  const environmentChecks = [
    {
      label: "CPU",
      value: system.cpu || system.machine || (language === "en" ? "Unknown" : "不明"),
      ok: Boolean(system.cpu || system.machine),
    },
    {
      label: "GPU",
      value: system.hasGpu ? (system.gpu || (language === "en" ? "Available" : "あり")) : (language === "en" ? "None" : "なし"),
      ok: Boolean(system.hasGpu),
    },
    {
      label: language === "en" ? "Memory" : "メモリ",
      value: memory ? `${memory}GB` : (language === "en" ? "Unknown" : "不明"),
      ok: memory >= 12,
    },
    {
      label: "Ollama",
      value: system.ollamaVersion || (language === "en" ? "Not detected" : "未検出"),
      ok: Boolean(system.ollamaVersion),
    },
    {
      label: "Apple Silicon",
      value: system.isAppleSilicon ? "対応" : "未確認",
      ok: Boolean(system.isAppleSilicon),
    },
  ];
  const modelChecks = [
    {
      label: "軽量AIモデル",
      value: availableModels.has(recommended.light) || availableModels.has("qwen2.5:3b") ? "利用可能" : "未取得",
      ok: availableModels.has(recommended.light) || availableModels.has("qwen2.5:3b"),
    },
    {
      label: "高性能AIモデル",
      value: availableModels.has("gemma4:12b-mlx") || availableModels.has("gemma4:12b") ? "利用可能" : "未取得",
      ok: availableModels.has("gemma4:12b-mlx") || availableModels.has("gemma4:12b"),
    },
    {
      label: "プログラミング用AIモデル",
      value: availableModels.has(recommended.coding) ? "利用可能" : "未取得",
      ok: availableModels.has(recommended.coding),
    },
  ];
  const warnings = Array.isArray(recommendation.warnings) ? recommendation.warnings.filter(Boolean) : [];
  els.pcDiagnostics.innerHTML = `
    <div class="pc-diagnostics-title">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(language === "en" ? "Checks whether local AI is ready on this computer." : "ローカルAIを使う準備状況を確認します。")}</span>
      </div>
      <div class="pc-diagnostics-actions">
        <span class="pc-diagnostics-badge ${escapeHtml(recommendation.level || "unknown")}">${escapeHtml(label)}</span>
        <button class="ghost-button pc-diagnostics-refresh" type="button" data-pc-diagnostics-refresh>${escapeHtml(language === "en" ? "Check again" : "再診断")}</button>
      </div>
    </div>
    ${summary ? `<p>${escapeHtml(summary)}</p>` : ""}
    ${specLine ? `<small>${escapeHtml(specLine)}</small>` : ""}
    <div class="pc-diagnostics-section-title">${escapeHtml(language === "en" ? "Computer" : "PC環境")}</div>
    <div class="pc-diagnostics-checks">
      ${environmentChecks.map((item) => `
        <div class="${item.ok ? "ok" : "missing"}">
          <span>${item.ok ? "✓" : "!"}</span>
          <strong>${escapeHtml(item.label)}</strong>
          <small>${escapeHtml(item.value)}</small>
        </div>
      `).join("")}
    </div>
    <div class="pc-diagnostics-section-title">${escapeHtml(language === "en" ? "Available AI models" : "利用できるAIモデル")}</div>
    <div class="pc-diagnostics-model-checks">
      ${modelChecks.map((item, index) => `
        ${index > 0 ? `<div class="pc-diagnostics-divider" aria-hidden="true"></div>` : ""}
        <div class="${item.ok ? "ok" : "missing"}">
          <span>${item.ok ? "✓" : "!"}</span>
          <strong>${escapeHtml(item.label)}</strong>
          <small>${escapeHtml(item.value)}</small>
        </div>
      `).join("")}
    </div>
    ${ollamaOutdated ? `
      <div class="pc-diagnostics-update">
        <strong>${escapeHtml(language === "en" ? "Ollama update recommended" : "Ollamaの更新をおすすめします")}</strong>
        <span>${escapeHtml(language === "en" ? "Gemma 4 MLX works best with Ollama 0.31 or later." : "Gemma 4 MLX高速版を安定して使うには Ollama 0.31以降がおすすめです。")}</span>
        <a class="ghost-button" href="https://ollama.com/download" target="_blank" rel="noopener">${escapeHtml(language === "en" ? "Open Ollama download" : "Ollama公式ページを開く")}</a>
      </div>
    ` : ""}
    ${warnings.length ? `<ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : ""}
  `;
}

function renderModelInstaller(deps) {
  const {
    composerModelLabel,
    els,
    modelIsInstalled,
    state,
    t,
  } = deps;
  if (!els.modelInstaller) return;
  const pullable = state.serverModels.pullable || [];
  if (pullable.length === 0) {
    els.modelInstaller.innerHTML = "";
    return;
  }
  els.modelInstaller.innerHTML = "";
  const language = state.language === "en" ? "en" : "ja";
  const title = document.createElement("div");
  title.className = "model-installer-title";
  const titleStrong = document.createElement("strong");
  titleStrong.textContent = t("settings.modelDownload");
  const titleHelp = document.createElement("span");
  titleHelp.textContent = state.language === "en"
    ? "Download Ollama models without Terminal. First downloads can use several GB of data."
    : "ターミナルを使わずにOllamaモデルを取得します。初回は数GBの通信が発生します。";
  title.append(titleStrong, titleHelp);
  els.modelInstaller.append(title);

  const byModel = new Map(pullable.filter((item) => item?.model).map((item) => [item.model, item]));
  const findModel = (predicate) => pullable.find((item) => item?.model && predicate(item)) || null;
  const qwenLight = byModel.get("qwen2.5:3b") || { model: "qwen2.5:3b", label: "Qwen 2.5 3B", purpose: language === "en" ? "Fast chat and translation" : "高速チャット・翻訳" };
  const gemmaMlx = byModel.get("gemma4:12b-mlx") || null;
  const gemmaStandard = byModel.get("gemma4:12b") || null;
  const qwen2507 = findModel((item) => item.model.includes("Qwen3-4B-Instruct-2507-GGUF"));
  const agenticCoder = findModel((item) => item.model.includes("gemma-4-12B-agentic-fable5-composer2.5-v2"));
  const isAppleSilicon = Boolean(state.appInfo?.pcDiagnostics?.system?.isAppleSilicon);
  const highPerformance = isAppleSilicon
    ? (gemmaMlx || gemmaStandard || qwen2507)
    : (gemmaStandard || qwen2507 || gemmaMlx);
  const codingModel = agenticCoder || gemmaMlx || gemmaStandard;
  const recommendedCards = [
    {
      role: language === "en" ? "Light AI model" : "軽量AIモデル",
      item: qwenLight,
      fallbackModel: "qwen2.5:3b",
      help: language === "en" ? "Fast chat and translation" : "高速チャット・翻訳向け",
    },
    {
      role: language === "en" ? "High-performance AI model" : "高性能AIモデル",
      item: highPerformance,
      fallbackModel: highPerformance?.model || "",
      help: language === "en" ? "Standard chat and document search" : "標準チャット・資料検索向け",
    },
    {
      role: language === "en" ? "Programming AI model" : "プログラミング用AIモデル",
      item: codingModel,
      fallbackModel: codingModel?.model || "",
      help: language === "en" ? "Code generation, fixes, and debugging" : "コード生成・修正・デバッグ向け",
    },
    {
      role: language === "en" ? "Translation AI model" : "翻訳AIモデル",
      item: qwenLight,
      fallbackModel: "qwen2.5:3b",
      help: language === "en" ? "Fast translation and rewriting" : "翻訳・言い換え向け",
    },
  ].filter((card) => card.item?.model || card.fallbackModel);
  const recommendedIds = new Set(recommendedCards.map((card) => card.item?.model || card.fallbackModel).filter(Boolean));

  const heading = document.createElement("div");
  heading.className = "model-section-heading";
  heading.textContent = language === "en" ? "Recommended models" : "おすすめモデル";
  els.modelInstaller.append(heading);
  const recommendedList = document.createElement("div");
  recommendedList.className = "model-recommended-list";
  for (const card of recommendedCards) {
    recommendedList.append(renderModelRow({
      item: card.item,
      model: card.item?.model || card.fallbackModel,
      title: card.role,
      help: `${card.item?.label || composerModelLabel(card.fallbackModel)}\n${card.help}`,
      recommended: true,
    }));
  }
  els.modelInstaller.append(recommendedList);

  const detailItems = pullable.filter((item) => (
    item?.model
    && !item.experimental
    && !recommendedIds.has(item.model)
  ));
  if (detailItems.length > 0) {
    const details = document.createElement("details");
    details.className = "model-details";
    const summary = document.createElement("summary");
    summary.textContent = language === "en" ? "Show detailed models" : "詳細モデルを表示";
    details.append(summary);
    let lastFamily = "";
    for (const item of detailItems) {
      const family = modelFamilyLabel(item, state.language);
      if (family && family !== lastFamily) {
        const familyHeading = document.createElement("div");
        familyHeading.className = "model-family-heading compact";
        familyHeading.textContent = family;
        details.append(familyHeading);
        lastFamily = family;
      }
      details.append(renderModelRow({ item, model: item.model, detail: true }));
    }
    els.modelInstaller.append(details);
  }

  const experimentalItems = pullable.filter((item) => item?.experimental);
  if (experimentalItems.length > 0) {
    const details = document.createElement("details");
    details.className = "model-details experimental";
    const summary = document.createElement("summary");
    summary.textContent = language === "en" ? "Show experimental models" : "実験モデルを表示";
    details.append(summary);
    for (const item of experimentalItems) {
      details.append(renderModelRow({ item, model: item.model, experimental: true }));
    }
    els.modelInstaller.append(details);
  }

  function renderModelRow({ item = {}, model = "", title = "", help = "", recommended = false, experimental = false }) {
    const modelId = item.model || model;
    const installed = modelIsInstalled(modelId);
    const job = state.modelPullJobs[modelId] || null;
    const row = document.createElement("div");
    row.className = `${recommended ? "model-recommended-card" : "model-install-row"}${experimental || item.experimental ? " experimental" : ""}`;
    const info = document.createElement("div");
    info.className = "model-install-info";
    const name = document.createElement("strong");
    name.textContent = title || item.label || composerModelLabel(modelId);
    if (experimental || item.experimental) {
      const badge = document.createElement("span");
      badge.className = "model-experimental-badge";
      badge.textContent = language === "en" ? "Experimental" : "実験";
      name.append(" ", badge);
    }
    const detail = document.createElement("span");
    detail.textContent = help || item.purpose || modelId;
    info.append(name, detail);
    if (experimental || item.experimental) {
      const warning = document.createElement("small");
      warning.className = "model-experimental-warning";
      warning.textContent = item.warning || (language === "en"
        ? "This model may have weaker safety tuning. Do not use it for student defaults, company documents, or external-send checks."
        : "このモデルは通常の安全調整が弱い可能性があります。学生向け標準、社内文書、外部送信前チェックには推奨しません。");
      info.append(warning);
    }
    if (item.pullable === false) {
      const unavailable = document.createElement("small");
      unavailable.className = "model-experimental-warning";
      unavailable.textContent = language === "en"
        ? item.note || "Shown for reference only. It cannot be selected until the local runtime name is confirmed."
        : item.note || "情報表示のみです。ローカル実行名が確定するまで、選択やダウンロードはできません。";
      info.append(unavailable);
      row.append(info);
      return row;
    }
    if (item.note) {
      const note = document.createElement("small");
      note.className = "model-experimental-warning";
      note.textContent = item.note;
      info.append(note);
    }
    const status = document.createElement(installed ? "div" : job?.status === "running" || job?.status === "queued" || job?.status === "error" ? "span" : "button");
    if (installed) {
      status.className = "model-install-actions";
      const badge = document.createElement("span");
      badge.className = "model-installed-badge";
      badge.textContent = t("model.installed");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "ghost-button model-remove-button";
      remove.dataset.modelRemove = modelId;
      remove.textContent = language === "en" ? "Uninstall" : "アンインストール";
      status.append(badge, remove);
    } else if (job?.status === "running" || job?.status === "queued") {
      status.className = "model-installed-badge";
      status.textContent = t("model.downloading");
    } else if (job?.status === "error") {
      status.className = "model-installed-badge error";
      status.textContent = t("error.prefix");
    } else {
      status.type = "button";
      status.className = "ghost-button model-install-button";
      status.dataset.modelPull = modelId;
      if (experimental || item.experimental) status.dataset.experimentalModel = "true";
      status.textContent = t("model.download");
    }
    row.append(info, status);
    return row;
  }
}

function modelFamilyLabel(item, language) {
  const family = item?.family || "";
  if (!family) return "";
  if (language === "en") {
    if (family.includes("Gemma")) return "Gemma family";
    if (family.includes("Qwen")) return "Qwen family";
  }
  return family;
}

async function fetchModelPullStatus() {
  const response = await fetch("/api/models/pull/status");
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "");
  }
  return data;
}

async function requestModelPull(model) {
  const response = await fetch("/api/models/pull", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "");
  }
  return data;
}

async function requestModelRemove(model) {
  const response = await fetch("/api/models/remove", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "");
  }
  return data;
}

function renderModelSelect({
  select,
  task,
  models,
  current,
  displayModelName,
  t,
}) {
  if (!select) return;
  select.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = task === "translation" ? t("model.serverAuto") : t("model.serverDefault");
  select.append(defaultOption);
  const uniqueModels = [...new Set(models.filter(Boolean))];
  if (current && !uniqueModels.includes(current)) uniqueModels.unshift(current);
  for (const model of uniqueModels) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = displayModelName(model, task);
    option.title = model;
    select.append(option);
  }
  select.value = current || "";
}

function renderComposerModelSelect({
  select,
  models,
  current,
  composerModelLabel,
  displayModelName,
  language,
  t,
}) {
  if (!select) return;
  const uniqueModels = [...new Set(models.filter(Boolean))];
  if (current && !uniqueModels.includes(current)) uniqueModels.unshift(current);
  select.innerHTML = "";
  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = t("model.auto");
  autoOption.title = language === "en"
    ? "Automatically chooses the chat, coding, or translation model by task"
    : "用途に応じて通常・コード・翻訳モデルを自動で使い分けます";
  select.append(autoOption);
  for (const model of uniqueModels) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = composerModelLabel(model);
    option.title = displayModelName(model, "chat");
    select.append(option);
  }
  select.value = current || "";
}

function externalLlmCheckStatusKey(errorCode) {
  if (errorCode === "invalid_url") return "settings.externalLlmInvalidUrl";
  if (errorCode === "non_local_url") return "settings.externalLlmLocalOnly";
  return "settings.externalLlmError";
}

function installedOrCurrentModels({ models, task, state, modelIsInstalled }) {
  const current = state.modelOverrides?.[task] || "";
  const recommendedCoding = state.serverModels?.recommendedCoding || [];
  return models.filter((model) => (
    model &&
    (
      modelIsInstalled(model) ||
      model === current ||
      model === state.composerModel ||
      recommendedCoding.includes(model)
    )
  ));
}

const COMPOSER_OPTIONAL_MODEL_IDS = [
  "hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M",
  "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL",
];

function isComposerModelCandidate(model) {
  if (!model) return false;
  return (
    model === "gemma4:12b" ||
    model === "gemma4:12b-mlx" ||
    model === "qwen2.5:3b" ||
    model.includes("Qwen3-4B-Instruct-2507-GGUF") ||
    model.includes("gemma-4-12B-agentic-fable5-composer2.5-v2") ||
    model.includes("Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced")
  );
}

function experimentalComposerModelCandidates({ state }) {
  if (!state.showExperimentalModels) return [];
  const pullable = state.serverModels?.pullable || [];
  return pullable
    .filter((item) => item?.experimental && item?.allowAutoSelect === false && item?.role === "coding-experimental")
    .map((item) => item.model)
    .filter(Boolean);
}

function composerModelCandidates({ state, modelIsInstalled }) {
  const installed = (models, task) => installedOrCurrentModels({
    models,
    task,
    state,
    modelIsInstalled,
  });
  const candidates = installed([
    state.serverModels.chat,
    state.serverModels.coding,
    state.serverModels.translation,
    ...state.serverModels.recommendedCoding,
    ...COMPOSER_OPTIONAL_MODEL_IDS,
    ...experimentalComposerModelCandidates({ state }),
    "gemma4:12b-mlx",
    "gemma4:12b",
    "qwen2.5:3b",
    isComposerModelCandidate(state.composerModel) ? state.composerModel : "",
  ].filter((model) => isComposerModelCandidate(model) || experimentalComposerModelCandidates({ state }).includes(model)), "chat");
  const uniqueCandidates = [...new Set(candidates)];
  if (state.composerModelVisibleModelsSaved !== true) return uniqueCandidates;
  const visible = Array.isArray(state.composerModelVisibleModels) ? state.composerModelVisibleModels.filter(Boolean) : [];
  const visibleSet = new Set(visible);
  return uniqueCandidates.filter((model) => visibleSet.has(model));
}

function renderComposerModelVisibility({
  composerModelLabel,
  els,
  models,
  state,
}) {
  if (!els.composerModelVisibility) return;
  const language = state.language === "en" ? "en" : "ja";
  const uniqueModels = [...new Set((models || []).filter(Boolean))];
  if (uniqueModels.length === 0) {
    els.composerModelVisibility.innerHTML = "";
    return;
  }
  const savedVisibleModels = Array.isArray(state.composerModelVisibleModels)
    ? state.composerModelVisibleModels.filter(Boolean)
    : [];
  const selected = new Set(state.composerModelVisibleModelsSaved === true ? savedVisibleModels : uniqueModels);
  els.composerModelVisibility.innerHTML = `
    <div class="composer-model-visibility-title">
      <strong>${language === "en" ? "Models shown in chat" : "チャット欄に表示するAIモデル"}</strong>
      <span>${language === "en" ? "Auto is always shown. Choose which downloaded models appear in the chat model menu." : "自動は常に表示されます。チャット欄のモデルメニューに出すダウンロード済みAIモデルを選べます。"}</span>
    </div>
    <div class="composer-model-visibility-list">
      ${uniqueModels.map((model) => {
        const isSelected = selected.has(model);
        return `
        <label class="${isSelected ? "is-selected" : ""}">
          <input type="checkbox" data-composer-model-visible="${model}" ${isSelected ? "checked" : ""} />
          <span>${composerModelLabel(model)}</span>
        </label>
      `;
      }).join("")}
    </div>
  `;
}

function renderModelSettingsSelects({
  composerModelLabel,
  displayModelName,
  els,
  modelIsInstalled,
  state,
  t,
}) {
  const installed = (models, task) => installedOrCurrentModels({
    models,
    task,
    state,
    modelIsInstalled,
  });
  renderModelSelect({
    select: els.chatModel,
    task: "chat",
    models: installed([
      state.serverModels.chat,
      "gemma4:12b-mlx",
      "gemma4:12b",
      "qwen2.5:3b",
      "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL",
    ], "chat"),
    current: state.modelOverrides.chat || "",
    displayModelName,
    t,
  });
  renderModelSelect({
    select: els.codingModel,
    task: "coding",
    models: installed([
      state.serverModels.coding,
      ...state.serverModels.recommendedCoding,
      "gemma4:12b",
    ], "coding"),
    current: state.modelOverrides.coding || "",
    displayModelName,
    t,
  });
  renderModelSelect({
    select: els.translationModel,
    task: "translation",
    models: installed([
      state.serverModels.translation,
      "qwen2.5:3b",
      "gemma4:12b",
    ], "translation"),
    current: state.modelOverrides.translation || "",
    displayModelName,
    t,
  });
  const composerModels = composerModelCandidates({ state, modelIsInstalled });
  const allComposerModels = composerModelCandidates({
    state: { ...state, composerModelVisibleModels: [], composerModelVisibleModelsSaved: false },
    modelIsInstalled,
  });
  renderComposerModelSelect({
    select: els.composerModel,
    models: composerModels,
    current: state.composerModel,
    composerModelLabel,
    displayModelName,
    language: state.language,
    t,
  });
  renderComposerModelVisibility({
    composerModelLabel,
    els,
    models: allComposerModels,
    state,
  });
}

function bindSettingsEvents({
  els,
  onThemeChange,
  onLanguageChange,
  onResponseModeChange,
  onComposerModelChange,
  onThinkingModeChange,
  onModelOverrideChange,
  onEnterToSendChange,
}) {
  els.themeSelect?.addEventListener("change", () => onThemeChange?.(els.themeSelect.value));
  els.languageSelect?.addEventListener("change", () => onLanguageChange?.(els.languageSelect.value));
  els.responseMode?.addEventListener("change", () => onResponseModeChange?.(els.responseMode.value));
  els.composerResponseMode?.addEventListener("change", () => onResponseModeChange?.(els.composerResponseMode.value));
  els.composerModel?.addEventListener("change", () => onComposerModelChange?.(els.composerModel.value));
  els.thinkingMode?.addEventListener("change", () => onThinkingModeChange?.(els.thinkingMode.value));
  els.chatModel?.addEventListener("change", () => onModelOverrideChange?.("chat", els.chatModel.value));
  els.codingModel?.addEventListener("change", () => onModelOverrideChange?.("coding", els.codingModel.value));
  els.translationModel?.addEventListener("change", () => onModelOverrideChange?.("translation", els.translationModel.value));
  els.enterToSend?.addEventListener("change", () => onEnterToSendChange?.(els.enterToSend.checked));
}

window.GEMMA_SETTINGS = {
  bindSettingsEvents,
  composerModelCandidates,
  externalLlmCheckStatusKey,
  fetchModelPullStatus,
  installedOrCurrentModels,
  renderComposerModelSelect,
  renderComposerModelVisibility,
  renderModelInstaller,
  renderModelSelect,
  renderModelSettingsSelects,
  renderPcDiagnosticsPanel,
  renderSearchCapabilitiesPanel,
  renderSettingsMeta: renderGemmaSettingsMeta,
  requestModelPull,
  requestModelRemove,
};
})();
