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
  let lastFamily = "";
  let firstInFamily = false;
  for (const item of pullable) {
    const model = item.model;
    const installed = modelIsInstalled(model);
    const job = state.modelPullJobs[model] || null;
    const family = modelFamilyLabel(item, state.language);
    if (family && family !== lastFamily) {
      const heading = document.createElement("div");
      heading.className = `model-family-heading${lastFamily ? "" : " first-family"}`;
      heading.textContent = family;
      els.modelInstaller.append(heading);
      lastFamily = family;
      firstInFamily = true;
    }
    const row = document.createElement("div");
    row.className = `model-install-row${firstInFamily ? " first-in-family" : ""}`;
    firstInFamily = false;
    const info = document.createElement("div");
    info.className = "model-install-info";
    const name = document.createElement("strong");
    name.textContent = item.label || composerModelLabel(model);
    const detail = document.createElement("span");
    detail.textContent = installed
      ? `${t("model.installed")} ・ ${item.purpose || model}`
      : job?.status === "running" || job?.status === "queued"
        ? `${t("model.downloading")} ・ ${job.message || ""}`
        : job?.status === "error"
          ? `${t("error.prefix")} ・ ${job.message || ""}`
          : item.purpose || model;
    info.append(name, detail);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost-button model-install-button";
    button.dataset.modelPull = model;
    button.disabled = installed || job?.status === "running" || job?.status === "queued";
    button.textContent = installed ? t("model.installed") : job?.status === "running" || job?.status === "queued" ? t("model.downloading") : t("model.download");
    row.append(info, button);
    els.modelInstaller.append(row);
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
      "gemma4:12b",
      "qwen2.5:3b",
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
  const composerModels = installed([
    state.serverModels.chat,
    state.serverModels.coding,
    state.serverModels.translation,
    ...state.serverModels.recommendedCoding,
    "gemma4:12b",
    "qwen2.5:3b",
  ], "chat");
  renderComposerModelSelect({
    select: els.composerModel,
    models: composerModels,
    current: state.composerModel,
    composerModelLabel,
    displayModelName,
    language: state.language,
    t,
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
  fetchModelPullStatus,
  installedOrCurrentModels,
  renderComposerModelSelect,
  renderModelInstaller,
  renderModelSelect,
  renderModelSettingsSelects,
  renderSearchCapabilitiesPanel,
  renderSettingsMeta: renderGemmaSettingsMeta,
  requestModelPull,
};
})();
