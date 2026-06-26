window.GEMMA_MANAGEMENT = (() => {
  const IMPORTED_STUDY_PACK_DEFINITIONS_KEY = "gemma4.importedStudyPackDefinitions";
  const STUDY_PACK_DEFINITIONS = {
    "sample-basic": {
      id: "sample-basic",
      version: "0.1.0",
      nameKey: "management.samplePack",
      helpKey: "management.samplePackHelp",
      modes: [],
    },
    "ja-report-writing-basic": {
      id: "ja-report-writing-basic",
      version: "0.1.0",
      nameKey: "management.reportWritingPack",
      helpKey: "management.reportWritingPackHelp",
      sourceNotes: [
        "Inspired by f4ah6o/tech-write-ja and k16shikano japanese-tech-writing. Do not copy source text until license/permission is confirmed.",
      ],
      modes: [
        {
          id: "make-readable",
          nameKey: "studyPack.mode.makeReadable",
          shortKey: "studyPack.mode.makeReadableShort",
          prompt:
            "渡された本文そのものを読みやすく整えてください。意味は変えず、長すぎる文を分け、同じ内容の繰り返しを減らしてください。",
          examples: [
            {
              input: "昨日学校に行きましたそして先生に質問して課題を直しました。",
              output: "昨日、学校で先生に質問し、課題を直しました。",
            },
          ],
        },
        {
          id: "logic-gap-check",
          nameKey: "studyPack.mode.logicGap",
          shortKey: "studyPack.mode.logicGapShort",
          prompt:
            "渡された本文の主張、理由、例、結論のつながりを確認してください。説明不足、飛躍、曖昧な指示語、根拠の弱い断定を指摘してください。",
          examples: [
            {
              input: "この商品は便利です。だから多くの人に使われると思います。",
              output:
                "気になる点:\n- 何が便利なのか、誰にとって便利なのかが不足しています。\n直し方:\n- 利用場面と具体的な理由を1つ追加すると、主張が伝わりやすくなります。",
            },
          ],
        },
        {
          id: "reduce-ai-tone",
          nameKey: "studyPack.mode.reduceAiTone",
          shortKey: "studyPack.mode.reduceAiToneShort",
          prompt:
            "渡された本文そのものを、AIが書いたような定型句、過剰な強調、抽象的すぎる表現を減らして、具体的で自然な日本語に整えてください。",
          examples: [
            {
              input: "本取り組みは多角的な観点から価値創出を実現するものです。",
              output: "この取り組みでは、複数の視点から課題を整理し、具体的な成果につなげます。",
            },
          ],
        },
        {
          id: "report-style",
          nameKey: "studyPack.mode.reportStyle",
          shortKey: "studyPack.mode.reportStyleShort",
          prompt:
            "渡された本文そのものを学生レポートとして読みやすい構成に整えてください。主張、理由、具体例、まとめの流れを明確にしてください。",
          examples: [
            {
              input: "環境問題は大切です。みんなで気をつけるべきです。",
              output:
                "環境問題への対策は、個人の行動と社会全体の仕組みの両方から考える必要があります。例えば、節電やごみの分別は個人で取り組める一方、再生可能エネルギーの整備には社会的な仕組みが必要です。",
            },
          ],
        },
      ],
    },
    "coding-assist-basic": {
      id: "coding-assist-basic",
      version: "0.1.0",
      nameKey: "management.codingAssistPack",
      helpKey: "management.codingAssistPackHelp",
      modes: [
        {
          id: "code-review",
          nameKey: "studyPack.mode.codeReview",
          shortKey: "studyPack.mode.codeReviewShort",
          prompt:
            "コードや差分をレビューしてください。最初に重大度順の指摘を出し、ファイル名・関数名・該当箇所が分かる形で、バグ、破壊的変更、セキュリティ、テスト不足を優先してください。問題がない場合は、その旨と残るリスクだけを短く伝えてください。",
        },
        {
          id: "bug-fix",
          nameKey: "studyPack.mode.bugFix",
          shortKey: "studyPack.mode.bugFixShort",
          prompt:
            "不具合の原因を切り分けて修正方針を出してください。症状、再現条件、原因候補、確認コマンド、最小修正、追加すべきテストの順で整理してください。事実として確認できていないことは推測として分けてください。",
        },
        {
          id: "tdd",
          nameKey: "studyPack.mode.tdd",
          shortKey: "studyPack.mode.tddShort",
          prompt:
            "TDDの流れで支援してください。まず期待する振る舞いを1つの失敗するテストとして表現し、次に最小実装、最後にリファクタリング観点を示してください。既存テストや既存パターンを優先し、過剰な抽象化は避けてください。",
        },
        {
          id: "error-debug",
          nameKey: "studyPack.mode.errorDebug",
          shortKey: "studyPack.mode.errorDebugShort",
          prompt:
            "エラーログや失敗したコマンドを解析してください。エラーの直接原因、根本原因の候補、追加で見るべきログやファイル、次に実行する確認コマンドを分けてください。ログにない事実を断定しないでください。",
        },
        {
          id: "release-check",
          nameKey: "studyPack.mode.releaseCheck",
          shortKey: "studyPack.mode.releaseCheckShort",
          prompt:
            "リリース前チェックとして確認してください。変更概要、影響範囲、必要なテスト、バージョン更新、配布物、ロールバック方法、未解決リスクを短いチェックリストで整理してください。未確認項目は未確認として明記してください。",
        },
      ],
    },
  };

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

  function studyPackDefinitions() {
    return {
      ...STUDY_PACK_DEFINITIONS,
      ...loadImportedStudyPackDefinitions(),
    };
  }

  function studyPackById(id) {
    return studyPackDefinitions()[id] || null;
  }

  function installedStudyPackDefinitions(studyPacks = {}) {
    return Object.values(studyPackDefinitions()).filter((pack) => Boolean(studyPacks?.[pack.id]?.installed));
  }

  function studyPackMenuGroups({ packs = [], selectedValue = "", t }) {
    return packs.map((pack) => ({
      id: pack.id,
      label: t?.(pack.nameKey) || pack.name || pack.id,
      modes: (pack.modes || []).map((mode) => {
        const value = `${pack.id}:${mode.id}`;
        return {
          id: mode.id,
          value,
          label: t?.(mode.shortKey) || t?.(mode.nameKey) || mode.name || mode.id,
          active: selectedValue === value,
        };
      }),
    })).filter((group) => group.modes.length > 0);
  }

  function studyPackSelectionModel({ packs = [], selectedPackId = "", selectedValue = "", t }) {
    const groups = studyPackMenuGroups({ packs, selectedValue, t });
    const selectedValuePackId = String(selectedValue || "").split(":")[0] || "";
    const hasPack = (packId) => groups.some((group) => group.id === packId);
    const activePackId = hasPack(selectedPackId)
      ? selectedPackId
      : hasPack(selectedValuePackId)
        ? selectedValuePackId
        : "";
    const activeGroup = groups.find((group) => group.id === activePackId) || null;
    return {
      activePackId,
      packOptions: groups.map((group) => ({
        id: group.id,
        value: group.id,
        label: group.label,
        active: group.id === activePackId,
      })),
      modeOptions: activeGroup?.modes || [],
    };
  }

  function studyPackMultiSelectionModel({ packs = [], selectedValues = [], t }) {
    const selectedSet = new Set((selectedValues || []).filter(Boolean));
    const groups = studyPackMenuGroups({ packs, selectedValue: "", t }).map((group) => ({
      ...group,
      modes: group.modes.map((mode) => ({
        ...mode,
        checked: selectedSet.has(mode.value),
      })),
    }));
    const selectedCount = groups.reduce(
      (count, group) => count + group.modes.filter((mode) => mode.checked).length,
      0,
    );
    return {
      groups,
      selectedCount,
      summaryLabel: selectedCount > 0
        ? `教材パック ${selectedCount}件`
        : "教材パックを選択",
    };
  }

  function toggleStudyPackModeValue(selectedValues = [], value = "", checked = false) {
    const selected = new Set((selectedValues || []).filter(Boolean));
    if (checked) selected.add(value);
    else selected.delete(value);
    return Array.from(selected);
  }

  function loadImportedStudyPackDefinitions() {
    return readJsonStorage(IMPORTED_STUDY_PACK_DEFINITIONS_KEY, {});
  }

  function saveImportedStudyPackDefinitions(definitions) {
    localStorage.setItem(IMPORTED_STUDY_PACK_DEFINITIONS_KEY, JSON.stringify(definitions || {}));
  }

  function filePathOf(file) {
    return String(file?.webkitRelativePath || file?.name || "").replace(/^\/+/, "");
  }

  function normalizePackRelativePath(path) {
    const clean = String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
    const parts = clean.split("/").filter(Boolean);
    const packIndex = parts.findIndex((part) => part === "pack.json");
    if (packIndex >= 0) return parts.slice(packIndex).join("/");
    if (parts.length > 1 && parts[0].endsWith("-pack")) return parts.slice(1).join("/");
    return parts.join("/");
  }

  async function readStudyPackFiles(files) {
    const map = new Map();
    for (const file of Array.from(files || [])) {
      const normalized = normalizePackRelativePath(filePathOf(file));
      if (!normalized) continue;
      map.set(normalized, await file.text());
    }
    return map;
  }

  function importedStudyPackNameKey(id) {
    return `importedStudyPack.${id}.name`;
  }

  function importedStudyPackHelpKey(id) {
    return `importedStudyPack.${id}.help`;
  }

  function importedStudyPackModeNameKey(packId, modeId) {
    return `importedStudyPack.${packId}.mode.${modeId}.name`;
  }

  function importedStudyPackModeShortKey(packId, modeId) {
    return `importedStudyPack.${packId}.mode.${modeId}.short`;
  }

  function registerImportedStudyPackTranslations(definition) {
    window.GEMMA_IMPORTED_STUDY_PACK_LABELS = window.GEMMA_IMPORTED_STUDY_PACK_LABELS || {};
    window.GEMMA_IMPORTED_STUDY_PACK_LABELS[definition.nameKey] = definition.name || definition.id;
    window.GEMMA_IMPORTED_STUDY_PACK_LABELS[definition.helpKey] = definition.description || "";
    (definition.modes || []).forEach((mode) => {
      window.GEMMA_IMPORTED_STUDY_PACK_LABELS[mode.nameKey] = mode.name || mode.id;
      window.GEMMA_IMPORTED_STUDY_PACK_LABELS[mode.shortKey] = mode.shortName || mode.name || mode.id;
    });
  }

  function registerImportedStudyPackTranslationsForAll() {
    Object.values(loadImportedStudyPackDefinitions()).forEach(registerImportedStudyPackTranslations);
  }

  function validateImportedStudyPackManifest(manifest) {
    if (!manifest || typeof manifest !== "object") return "pack.json が正しくありません。";
    if (!String(manifest.id || "").trim()) return "pack.json に id が必要です。";
    if (STUDY_PACK_DEFINITIONS[manifest.id]) return "内蔵教材パックと同じ id は使えません。";
    if (!String(manifest.name || "").trim()) return "pack.json に name が必要です。";
    if (!Array.isArray(manifest.modes) || manifest.modes.length === 0) return "pack.json に modes が必要です。";
    return "";
  }

  function buildImportedStudyPackDefinition({ manifest, fileMap }) {
    const packId = String(manifest.id).trim();
    const modes = manifest.modes.map((mode) => {
      const modeId = String(mode.id || "").trim();
      const promptFile = String(mode.promptFile || "").trim();
      const prompt = String(mode.prompt || (promptFile ? fileMap.get(promptFile) : "") || "").trim();
      if (!modeId || !prompt) return null;
      return {
        id: modeId,
        name: String(mode.name || modeId),
        nameKey: importedStudyPackModeNameKey(packId, modeId),
        shortKey: importedStudyPackModeShortKey(packId, modeId),
        prompt,
        promptFile: promptFile || "",
        examples: Array.isArray(mode.examples) ? mode.examples : [],
      };
    }).filter(Boolean);
    if (modes.length === 0) return null;
    return {
      id: packId,
      version: String(manifest.version || "0.1.0"),
      name: String(manifest.name || packId),
      nameKey: importedStudyPackNameKey(packId),
      helpKey: importedStudyPackHelpKey(packId),
      description: String(manifest.description || ""),
      visibility: String(manifest.visibility || "private"),
      private: String(manifest.visibility || "private") === "private",
      imported: true,
      importedAt: new Date().toISOString(),
      modes,
    };
  }

  async function importStudyPackFromFiles({ state, files, t }) {
    const fileMap = await readStudyPackFiles(files);
    const manifestText = fileMap.get("pack.json");
    if (!manifestText) {
      return { ok: false, error: t?.("management.studyPackImportMissingManifest") || "pack.json が見つかりません。" };
    }
    let manifest = null;
    try {
      manifest = JSON.parse(manifestText);
    } catch {
      return { ok: false, error: t?.("management.studyPackImportInvalidJson") || "pack.json のJSONが正しくありません。" };
    }
    const validationError = validateImportedStudyPackManifest(manifest);
    if (validationError) return { ok: false, error: validationError };
    const definition = buildImportedStudyPackDefinition({ manifest, fileMap });
    if (!definition) {
      return { ok: false, error: t?.("management.studyPackImportMissingPrompt") || "読み込めるモード本文がありません。" };
    }
    const definitions = loadImportedStudyPackDefinitions();
    definitions[definition.id] = definition;
    saveImportedStudyPackDefinitions(definitions);
    registerImportedStudyPackTranslations(definition);
    state.studyPacks = state.studyPacks || {};
    state.studyPacks[definition.id] = {
      installed: true,
      version: definition.version,
      status: "ready",
      source: "imported",
    };
    saveStudyPacks(state.studyPacks);
    return { ok: true, definition };
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
      els.mobileConnectPanel,
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
      els.mobileConnectPanel,
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

  function renderMobileConnectInfo({ els, t, info }) {
    if (!info?.ok) {
      if (els.mobileConnectStatus) els.mobileConnectStatus.textContent = t("management.mobileConnectError");
      return;
    }
    if (els.mobileConnectCode) {
      els.mobileConnectCode.textContent = info.pairingCode || "------";
    }
    if (els.mobileConnectExpires) {
      els.mobileConnectExpires.textContent = info.expiresAt
        ? t("management.mobileConnectExpires", { time: info.expiresAt })
        : "";
    }
    if (els.mobileConnectStatus) {
      els.mobileConnectStatus.textContent = info.pairingEnabled
        ? t("management.mobileConnectReady")
        : t("management.mobileConnectPairingPending");
    }
    if (els.mobileConnectHosts) {
      const hosts = Array.isArray(info.hostCandidates) ? info.hostCandidates : [];
      els.mobileConnectHosts.textContent = hosts.length > 0
        ? hosts.join("\n")
        : t("management.mobileConnectNoLan");
    }
  }

  async function refreshMobileConnectInfo({ els, t }) {
    if (els.mobileConnectStatus) els.mobileConnectStatus.textContent = t("management.mobileConnectLoading");
    try {
      const response = await fetch("/api/mobile/connect-info");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const info = await response.json();
      renderMobileConnectInfo({ els, t, info });
      return info;
    } catch {
      if (els.mobileConnectStatus) els.mobileConnectStatus.textContent = t("management.mobileConnectError");
      if (els.mobileConnectHosts) els.mobileConnectHosts.textContent = t("management.mobileConnectNoLan");
      return null;
    }
  }

  function renderStudyPacksPanel({ state, t }) {
    registerImportedStudyPackTranslationsForAll();
    document.querySelectorAll("[data-study-pack-toggle]").forEach((button) => {
      const packId = button.dataset.studyPackToggle || "";
      const installed = Boolean(state.studyPacks?.[packId]?.installed);
      button.textContent = installed ? t("management.remove") : t("management.add");
      button.setAttribute("aria-pressed", String(installed));
    });
    const list = document.querySelector("#imported-study-pack-list");
    if (!list) return;
    const imported = Object.values(loadImportedStudyPackDefinitions());
    list.innerHTML = "";
    imported.forEach((pack) => {
      const card = document.createElement("div");
      card.className = "management-card study-pack-card";
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = t(pack.nameKey) || pack.name || pack.id;
      const help = document.createElement("span");
      help.textContent = t(pack.helpKey) || pack.description || t("management.studyPackImportedHelp");
      const modeList = document.createElement("div");
      modeList.className = "study-pack-mode-list";
      modeList.setAttribute("aria-label", t("management.studyPackModes"));
      (pack.modes || []).forEach((mode) => {
        const item = document.createElement("span");
        item.textContent = t(mode.shortKey) || t(mode.nameKey) || mode.id;
        modeList.appendChild(item);
      });
      const source = document.createElement("small");
      source.textContent = pack.private
        ? t("management.studyPackPrivateImported")
        : t("management.studyPackImported");
      body.append(title, help, modeList, source);
      const button = document.createElement("button");
      button.className = "ghost-button";
      button.type = "button";
      button.dataset.studyPackToggle = pack.id;
      card.append(body, button);
      list.appendChild(card);
    });
    list.querySelectorAll("[data-study-pack-toggle]").forEach((button) => {
      const packId = button.dataset.studyPackToggle || "";
      const installed = Boolean(state.studyPacks?.[packId]?.installed);
      button.textContent = installed ? t("management.remove") : t("management.add");
      button.setAttribute("aria-pressed", String(installed));
    });
  }

  function toggleStudyPack({ state, t, packId }) {
    const definition = studyPackById(packId);
    if (!definition) return;
    state.studyPacks = state.studyPacks || {};
    const current = Boolean(state.studyPacks[packId]?.installed);
    state.studyPacks[packId] = {
      installed: !current,
      version: definition.version || "0.1.0",
      status: !current ? "ready" : "removed",
    };
    saveStudyPacks(state.studyPacks);
    renderStudyPacksPanel({ state, t });
  }

  function toggleSampleStudyPack({ state, t }) {
    toggleStudyPack({ state, t, packId: "sample-basic" });
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
    els.mobileConnectToggle?.addEventListener("click", () => {
      openManagementPanel({ els, panel: els.mobileConnectPanel });
      refreshMobileConnectInfo({ els, t });
    });
    els.mobileConnectClose?.addEventListener("click", () => {
      if (els.mobileConnectPanel) els.mobileConnectPanel.hidden = true;
      syncManagementLayout({ els });
    });
    els.mobileConnectRefresh?.addEventListener("click", () => {
      refreshMobileConnectInfo({ els, t });
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
    els.studyPacksPanel?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-study-pack-toggle]");
      if (!button) return;
      toggleStudyPack({ state, t, packId: button.dataset.studyPackToggle || "" });
      onPluginsChanged?.();
    });
    els.studyPackImportButton?.addEventListener("click", () => els.studyPackImportInput?.click());
    els.studyPackImportInput?.addEventListener("change", async () => {
      const result = await importStudyPackFromFiles({ state, files: els.studyPackImportInput.files, t });
      if (els.studyPackImportStatus) {
        els.studyPackImportStatus.textContent = result.ok
          ? t("management.studyPackImportDone", { name: t(result.definition.nameKey) || result.definition.name })
          : result.error;
      }
      if (els.studyPackImportInput) els.studyPackImportInput.value = "";
      renderStudyPacksPanel({ state, t });
      onPluginsChanged?.();
    });

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
    loadImportedStudyPackDefinitions,
    saveImportedStudyPackDefinitions,
    studyPackDefinitions,
    studyPackById,
    installedStudyPackDefinitions,
    studyPackMenuGroups,
    studyPackSelectionModel,
    studyPackMultiSelectionModel,
    toggleStudyPackModeValue,
    importStudyPackFromFiles,
    loadPlugins,
    savePlugins,
    formatPluginSearchCapabilities,
    closeManagementPanels,
    setSidebarSettingsMode,
    handleEscapeKey,
    openManagementPanel,
    setupManagementPanels,
    renderMobileConnectInfo,
    refreshMobileConnectInfo,
    renderStudyPacksPanel,
    toggleSampleStudyPack,
    toggleStudyPack,
    renderPluginsPanel,
    toggleCodegraphPlugin,
    togglePluginCandidate,
    bindManagementEvents,
  };
})();
