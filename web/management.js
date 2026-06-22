window.GEMMA_MANAGEMENT = (() => {
  const PLUGIN_CANDIDATES = {
    whisper: { implemented: true, integrated: true, version: "0.1.0" },
    ocr: { implemented: true, version: "0.1.0" },
    "fast-search": { implemented: true, version: "0.1.0" },
    "tree-sitter": { implemented: false },
  };
  const PLUGIN_CANDIDATE_IDS = Object.keys(PLUGIN_CANDIDATES);

  function readJsonStorage(key, fallback) {
    try {
      return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    } catch {
      return fallback;
    }
  }

  function loadStudyPacks() {
    return readJsonStorage("gemma4.studyPacks", {});
  }

  function saveStudyPacks(studyPacks) {
    localStorage.setItem("gemma4.studyPacks", JSON.stringify(studyPacks || {}));
  }

  function loadPlugins() {
    return readJsonStorage("gemma4.plugins", {});
  }

  function savePlugins(plugins) {
    localStorage.setItem("gemma4.plugins", JSON.stringify(plugins || {}));
  }

  function formatPluginSearchCapabilities({ capabilities = {}, t }) {
    if (!capabilities || Object.keys(capabilities).length === 0) {
      return t("management.pluginSearchChecking");
    }
    const supported = [];
    const unsupported = [];
    if (capabilities.text) supported.push(t("management.pluginSearchText"));
    if (capabilities.docx) supported.push(t("management.pluginSearchWord"));
    if (capabilities.pdf) {
      supported.push(t("management.pluginSearchPdfReady", { backend: capabilities.pdfBackend || "PDF" }));
    } else if (capabilities.filenameFallback) {
      supported.push(t("management.pluginSearchPdfFilenameOnly"));
    }
    if (capabilities.imageOcr) {
      supported.push(t("management.pluginSearchImageOcr"));
    } else {
      unsupported.push(t("management.pluginSearchImageOcrUnsupported"));
    }
    const supportedLabel = supported.length > 0 ? supported.join(" / ") : t("management.pluginSearchNone");
    const unsupportedLabel = unsupported.length > 0 ? ` / ${t("management.pluginSearchUnsupported", { targets: unsupported.join(" / ") })}` : "";
    return t("management.pluginSearchCurrent", { targets: supportedLabel }) + unsupportedLabel;
  }

  function ocrCapabilities(state) {
    return state.appInfo?.searchCapabilities?.ocr || {};
  }

  function isOcrReady(state) {
    const capabilities = ocrCapabilities(state);
    return Boolean(capabilities.image || capabilities.pdf || state.appInfo?.searchCapabilities?.imageOcr);
  }

  function isPluginImplemented(state, pluginId) {
    if (pluginId === "ocr") return isOcrReady(state);
    return Boolean(PLUGIN_CANDIDATES[pluginId]?.implemented);
  }

  function renderOcrPluginState({ state, t }) {
    const card = document.querySelector('[data-plugin-card="ocr"]');
    const badge = document.querySelector('[data-plugin-kind="ocr"]');
    const note = document.querySelector('[data-plugin-note="ocr"]');
    const meta = document.querySelector("#plugin-ocr-capabilities");
    const setupMeta = document.querySelector("#plugin-ocr-setup-status");
    const setupButton = document.querySelector("#ocr-plugin-setup");
    const progress = document.querySelector("#plugin-ocr-progress");
    const progressLabel = document.querySelector("#plugin-ocr-progress-label");
    const progressBar = document.querySelector("#plugin-ocr-progress-bar");
    const progressLog = document.querySelector("#plugin-ocr-log");
    if (!card && !badge && !note && !meta && !setupMeta && !setupButton) return;
    const capabilities = ocrCapabilities(state);
    const ready = isOcrReady(state);
    const job = state.ocrSetupJob || {};
    const running = job.status === "queued" || job.status === "running";
    const missing = Array.isArray(capabilities.missing) ? capabilities.missing.join(" / ") : "";
    card?.classList.toggle("plugin-available", ready);
    card?.classList.toggle("plugin-planned", !ready);
    if (badge) {
      badge.textContent = ready ? t("management.pluginReadyNow") : t("management.pluginOcrMissing");
    }
    if (note) {
      note.textContent = ready
        ? t("management.pluginOcrReadyNote")
        : t("management.pluginOcrMissingNote");
    }
    if (meta) {
      const engine = capabilities.engine || t("management.pluginOcrNoEngine");
      const language = capabilities.language || "-";
      meta.textContent = ready
        ? t("management.pluginOcrCurrent", { engine, language })
        : t("management.pluginOcrNeeds", { missing: missing || "Tesseract / Poppler" });
    }
    if (setupMeta) {
      setupMeta.textContent = job.message
        ? t("management.pluginOcrSetupStatus", { message: job.message })
        : t("management.pluginOcrSetupHelp");
    }
    if (setupButton) {
      setupButton.textContent = running ? t("management.pluginOcrSetupRunning") : t("management.pluginOcrSetup");
      setupButton.disabled = ready || running;
    }
    if (progress) {
      const logs = Array.isArray(job.logs) ? job.logs : [];
      const percent = Math.max(0, Math.min(100, Number(job.percent || (running ? 5 : 0))));
      progress.hidden = !running && logs.length === 0;
      if (progressLabel) {
        const step = Number(job.step || 0);
        const total = Number(job.total || 0);
        progressLabel.textContent = total > 0
          ? t("management.pluginSetupProgressValue", { percent, step, total })
          : `${percent}%`;
      }
      if (progressBar) {
        progressBar.style.width = `${percent}%`;
      }
      if (progressLog) {
        progressLog.innerHTML = "";
        logs.slice(-5).forEach((line) => {
          const item = document.createElement("li");
          item.textContent = String(line);
          progressLog.appendChild(item);
        });
      }
    }
  }

  async function reloadAppInfo(state) {
    const response = await fetch("/api/health");
    const payload = await response.json();
    if (payload?.ok || payload?.appVersion) {
      state.appInfo = payload;
    }
    return payload;
  }

  async function reloadOcrSetupStatus(state) {
    const response = await fetch("/api/ocr/setup/status");
    const payload = await response.json();
    if (payload?.ok) {
      state.ocrSetupJob = payload.job || {};
      state.appInfo = {
        ...(state.appInfo || {}),
        searchCapabilities: {
          ...(state.appInfo?.searchCapabilities || {}),
          ocr: payload.ocr || {},
          imageOcr: Boolean(payload.ocr?.image),
          pdfOcr: Boolean(payload.ocr?.pdf),
        },
      };
    }
    return payload;
  }

  async function refreshOcrPlugin({ state, els, t }) {
    try {
      await reloadAppInfo(state);
      await reloadOcrSetupStatus(state);
    } catch (error) {
      state.ocrSetupJob = { status: "error", message: String(error?.message || error) };
    }
    renderPluginsPanel({ state, els, t });
  }

  async function startOcrSetup({ state, els, t }) {
    if (!window.confirm(t("management.pluginOcrSetupConfirm"))) return;
    state.ocrSetupJob = { status: "queued", message: t("management.pluginOcrSetupRunning") };
    renderPluginsPanel({ state, els, t });
    try {
      const response = await fetch("/api/ocr/setup", { method: "POST" });
      const payload = await response.json();
      state.ocrSetupJob = {
        status: payload.status || (payload.ok ? "running" : "error"),
        message: payload.message || payload.error || "",
      };
    } catch (error) {
      state.ocrSetupJob = { status: "error", message: String(error?.message || error) };
    }
    renderPluginsPanel({ state, els, t });
    const startedAt = Date.now();
    const timer = window.setInterval(async () => {
      await refreshOcrPlugin({ state, els, t });
      const status = state.ocrSetupJob?.status;
      if (!["queued", "running"].includes(status) || Date.now() - startedAt > 10 * 60 * 1000) {
        window.clearInterval(timer);
      }
    }, 2000);
  }

  function closeManagementPanels({ els, except = null }) {
    [
      els.settingsPanel,
      els.responseSettingsPanel,
      els.asrPanel,
      els.characterPanel,
      els.studyPacksPanel,
      els.trainingManagementPanel,
      els.pluginsPanel,
      els.languageModelsPanel,
    ].forEach((panel) => {
      if (panel && panel !== except) panel.hidden = true;
    });
    syncManagementLayout({ els });
  }

  function syncManagementLayout({ els }) {
    const visible = visibleManagementPanels(els).length > 0;
    els.workspace?.classList.toggle("management-open", visible);
  }

  function setSidebarSettingsMode({ els, open }) {
    els.sidebar?.classList.toggle("settings-mode", Boolean(open));
    if (els.sidebarSettingsMenu) {
      els.sidebarSettingsMenu.hidden = !open;
    }
  }

  function openManagementPanel({ els, panel }) {
    if (!panel) return;
    const nextHidden = !panel.hidden;
    closeManagementPanels({ els, except: nextHidden ? null : panel });
    panel.hidden = nextHidden;
    syncManagementLayout({ els });
  }

  function visibleManagementPanels(els) {
    return [
      els.settingsPanel,
      els.responseSettingsPanel,
      els.asrPanel,
      els.characterPanel,
      els.studyPacksPanel,
      els.trainingManagementPanel,
      els.pluginsPanel,
      els.languageModelsPanel,
    ].filter((panel) => panel && !panel.hidden);
  }

  function handleEscapeKey({ els, state, onRender }) {
    const visiblePanels = visibleManagementPanels(els);
    if (visiblePanels.length > 0) {
      closeManagementPanels({ els });
      return "management";
    }
    if (state.workspaceOpen) {
      state.workspaceOpen = false;
      onRender?.();
      return "workspace";
    }
    if (els.sidebar?.classList.contains("settings-mode")) {
      setSidebarSettingsMode({ els, open: false });
      return "sidebar-settings";
    }
    return "";
  }

  function setupManagementPanels({ els, renderStudyPacksPanel, renderPluginsPanel }) {
    const trainingPanel = document.querySelector(".training-panel");
    if (trainingPanel && els.trainingManagementBody && trainingPanel.parentElement !== els.trainingManagementBody) {
      els.trainingManagementBody.appendChild(trainingPanel);
    }
    if (els.modelInstaller && els.languageModelDownloadView && els.modelInstaller.parentElement !== els.languageModelDownloadView) {
      els.languageModelDownloadView.appendChild(els.modelInstaller);
    }
    if (els.externalLlmSettings && els.languageModelExternalView && els.externalLlmSettings.parentElement !== els.languageModelExternalView) {
      els.languageModelExternalView.appendChild(els.externalLlmSettings);
    }
    renderStudyPacksPanel();
    renderPluginsPanel();
  }

  function renderStudyPacksPanel({ state, t }) {
    const installed = Boolean(state.studyPacks?.["sample-basic"]?.installed);
    const button = document.querySelector("[data-study-pack-toggle='sample-basic']");
    if (!button) return;
    button.textContent = installed ? t("management.remove") : t("management.add");
    button.setAttribute("aria-pressed", String(installed));
  }

  function toggleSampleStudyPack({ state, t }) {
    state.studyPacks = state.studyPacks || {};
    const current = Boolean(state.studyPacks["sample-basic"]?.installed);
    state.studyPacks["sample-basic"] = {
      installed: !current,
      version: "0.1.0",
      status: !current ? "ready" : "removed",
    };
    saveStudyPacks(state.studyPacks);
    renderStudyPacksPanel({ state, t });
  }

  function renderPluginsPanel({ state, els, t }) {
    const codegraph = state.plugins?.codegraph || {};
    const installed = Boolean(codegraph.installed);
    const searchCapabilities = document.querySelector("#plugin-search-capabilities");
    if (searchCapabilities) {
      searchCapabilities.textContent = formatPluginSearchCapabilities({
        capabilities: state.appInfo?.searchCapabilities || {},
        t,
      });
    }
    renderOcrPluginState({ state, t });
    if (els.codegraphPluginStatus) {
      els.codegraphPluginStatus.textContent = installed ? t("management.needsFolderSetup") : t("management.notAdded");
      els.codegraphPluginStatus.dataset.pluginState = installed ? "ready" : "off";
    }
    if (els.codegraphPluginToggle) {
      els.codegraphPluginToggle.textContent = installed ? t("management.remove") : t("management.add");
      els.codegraphPluginToggle.setAttribute("aria-pressed", String(installed));
    }
    document.querySelectorAll('[data-plugin-workspace="codegraph"]').forEach((button) => {
      button.disabled = !installed;
      button.title = installed ? t("management.openFolderSettings") : t("management.addFirst");
    });
    PLUGIN_CANDIDATE_IDS.forEach((pluginId) => {
      const implemented = isPluginImplemented(state, pluginId);
      const integrated = Boolean(PLUGIN_CANDIDATES[pluginId]?.integrated);
      const installed = Boolean(state.plugins?.[pluginId]?.installed);
      const planned = Boolean(state.plugins?.[pluginId]?.planned);
      const active = integrated || (implemented ? installed : planned);
      const status = document.querySelector(`[data-plugin-candidate-status="${pluginId}"]`);
      const button = document.querySelector(`[data-plugin-candidate-toggle="${pluginId}"]`);
      if (status) {
        status.textContent = integrated
          ? t("management.integrated")
          : !implemented
            ? planned ? t("management.candidateSaved") : t("management.notImplementedCandidate")
          : installed && pluginId === "fast-search"
            ? t("management.ready")
            : installed && pluginId === "codegraph"
              ? t("management.needsFolderSetup")
            : installed
              ? t("management.added")
              : t("management.notAdded");
        status.dataset.pluginState = integrated
          ? "integrated"
          : implemented && installed
            ? "ready"
            : planned
              ? "planned"
              : "off";
      }
      if (button) {
        button.textContent = implemented
          ? active ? t("management.remove") : t("management.add")
          : active ? t("management.removeCandidate") : t("management.addCandidate");
        button.setAttribute("aria-pressed", String(active));
        button.disabled = integrated || (pluginId === "ocr" && !implemented);
      }
      document.querySelectorAll(`[data-plugin-workspace="${pluginId}"]`).forEach((workspaceButton) => {
        workspaceButton.disabled = !active || integrated || !implemented;
        workspaceButton.title = active ? t("management.openFolderSettings") : t("management.addFirst");
        if (pluginId === "fast-search") {
          workspaceButton.textContent = active ? t("management.openSearch") : t("management.openFolderSettings");
        }
        if (pluginId === "codegraph") {
          workspaceButton.textContent = active ? t("management.prepareCodeUnderstanding") : t("management.openFolderSettings");
        }
      });
    });
  }

  function toggleCodegraphPlugin({ state, els, t }) {
    state.plugins = state.plugins || {};
    const current = Boolean(state.plugins.codegraph?.installed);
    state.plugins.codegraph = {
      installed: !current,
      version: "0.1.0",
      status: !current ? "ready" : "removed",
    };
    savePlugins(state.plugins);
    renderPluginsPanel({ state, els, t });
  }

  function togglePluginCandidate({ state, els, t, pluginId }) {
    if (!PLUGIN_CANDIDATE_IDS.includes(pluginId)) return;
    const implemented = isPluginImplemented(state, pluginId);
    if (pluginId === "ocr" && !implemented) {
      renderPluginsPanel({ state, els, t });
      return;
    }
    state.plugins = state.plugins || {};
    const active = implemented ? Boolean(state.plugins[pluginId]?.installed) : Boolean(state.plugins[pluginId]?.planned);
    state.plugins[pluginId] = {
      ...(state.plugins[pluginId] || {}),
      installed: implemented ? !active : false,
      planned: implemented ? false : !active,
      version: PLUGIN_CANDIDATES[pluginId]?.version || "0.1.0",
      status: !active ? (implemented ? "ready" : "candidate") : "removed",
      updatedAt: new Date().toISOString(),
    };
    savePlugins(state.plugins);
    renderPluginsPanel({ state, els, t });
  }

  function bindManagementEvents({ els, state, t, onOpenSettings, onOpenCharacter, onOpenWorkspace, onPluginsChanged }) {
    els.settingsMenuToggle?.addEventListener("click", () => {
      setSidebarSettingsMode({ els, open: true });
    });
    els.settingsMenuBack?.addEventListener("click", () => {
      setSidebarSettingsMode({ els, open: false });
      closeManagementPanels({ els });
    });
    els.settingsToggle?.addEventListener("click", () => {
      openManagementPanel({ els, panel: els.settingsPanel });
      onOpenSettings?.();
    });
    els.settingsClose?.addEventListener("click", () => {
      if (els.settingsPanel) els.settingsPanel.hidden = true;
      syncManagementLayout({ els });
    });
    els.responseSettingsToggle?.addEventListener("click", () => {
      openManagementPanel({ els, panel: els.responseSettingsPanel });
    });
    els.responseSettingsClose?.addEventListener("click", () => {
      if (els.responseSettingsPanel) els.responseSettingsPanel.hidden = true;
      syncManagementLayout({ els });
    });
    els.asrToggle?.addEventListener("click", () => {
      openManagementPanel({ els, panel: els.asrPanel });
      onOpenSettings?.("asr");
    });
    els.asrClose?.addEventListener("click", () => {
      if (els.asrPanel) els.asrPanel.hidden = true;
      syncManagementLayout({ els });
    });

    els.characterToggle?.addEventListener("click", () => {
      openManagementPanel({ els, panel: els.characterPanel });
      onOpenCharacter?.();
    });
    els.characterClose?.addEventListener("click", () => {
      if (els.characterPanel) els.characterPanel.hidden = true;
      syncManagementLayout({ els });
    });

    els.studyPacksToggle?.addEventListener("click", () => openManagementPanel({ els, panel: els.studyPacksPanel }));
    els.studyPacksClose?.addEventListener("click", () => {
      if (els.studyPacksPanel) els.studyPacksPanel.hidden = true;
      syncManagementLayout({ els });
    });
    document
      .querySelector("[data-study-pack-toggle='sample-basic']")
      ?.addEventListener("click", () => toggleSampleStudyPack({ state, t }));

    els.trainingManagementToggle?.addEventListener("click", () => {
      openManagementPanel({ els, panel: els.trainingManagementPanel });
    });
    els.trainingManagementClose?.addEventListener("click", () => {
      if (els.trainingManagementPanel) els.trainingManagementPanel.hidden = true;
      syncManagementLayout({ els });
    });

    els.pluginsToggle?.addEventListener("click", () => openManagementPanel({ els, panel: els.pluginsPanel }));
    els.pluginsClose?.addEventListener("click", () => {
      if (els.pluginsPanel) els.pluginsPanel.hidden = true;
      syncManagementLayout({ els });
    });
    els.languageModelsToggle?.addEventListener("click", () => {
      openManagementPanel({ els, panel: els.languageModelsPanel });
    });
    els.languageModelsClose?.addEventListener("click", () => {
      if (els.languageModelsPanel) els.languageModelsPanel.hidden = true;
      syncManagementLayout({ els });
    });
    els.codegraphPluginToggle?.addEventListener("click", () => {
      toggleCodegraphPlugin({ state, els, t });
      onPluginsChanged?.();
    });
    document.querySelectorAll("[data-plugin-candidate-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        togglePluginCandidate({ state, els, t, pluginId: button.dataset.pluginCandidateToggle });
        onPluginsChanged?.();
      });
    });
    document.querySelector("#ocr-plugin-refresh")?.addEventListener("click", () => {
      refreshOcrPlugin({ state, els, t });
    });
    document.querySelector("#ocr-plugin-setup")?.addEventListener("click", () => {
      startOcrSetup({ state, els, t });
    });
    document.querySelectorAll("[data-plugin-settings]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.pluginSettings || "";
        openManagementPanel({ els, panel: target === "asr" ? els.asrPanel : els.settingsPanel });
        onOpenSettings?.(target);
      });
    });
    document.querySelectorAll("[data-plugin-workspace]").forEach((button) => {
      button.addEventListener("click", () => {
        closeManagementPanels({ els });
        onOpenWorkspace?.(button.dataset.pluginWorkspace);
      });
    });
  }

  return {
    loadStudyPacks,
    saveStudyPacks,
    loadPlugins,
    savePlugins,
    formatPluginSearchCapabilities,
    closeManagementPanels,
    setSidebarSettingsMode,
    handleEscapeKey,
    openManagementPanel,
    setupManagementPanels,
    renderStudyPacksPanel,
    toggleSampleStudyPack,
    renderPluginsPanel,
    toggleCodegraphPlugin,
    togglePluginCandidate,
    bindManagementEvents,
  };
})();
