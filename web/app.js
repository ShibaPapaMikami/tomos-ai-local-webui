function initialAsrPartialMode() {
  const saved = localStorage.getItem("gemma4.asrPartialMode") || "";
  const migrationKey = "gemma4.asrPartialModeMigratedToLocal";
  if (localStorage.getItem(migrationKey) !== "true" && (!saved || saved === "browser" || saved === "nemotron")) {
    localStorage.setItem(migrationKey, "true");
    localStorage.setItem("gemma4.asrPartialMode", "local");
    return "local";
  }
  const normalized = window.GEMMA_ASR?.normalizePartialTranscriptionMode?.(saved || "local") || "local";
  if (saved && saved !== normalized) {
    localStorage.setItem("gemma4.asrPartialMode", normalized);
  }
  return normalized;
}

const state = {
  folders: loadFolders(),
  sessions: loadSessions(),
  trainingSets: loadTrainingSets(),
  character: window.GEMMA_CHARACTER?.loadCharacter?.() || { name: "Gemma" },
  characterMemorySets: window.GEMMA_CHARACTER?.loadMemorySets?.() || [],
  characterMemoryFilter: "all",
  characterMemoryQuery: "",
  studyPacks: window.GEMMA_MANAGEMENT?.loadStudyPacks?.() || {},
  selectedStudyPackMode: "",
  selectedStudyPackModes: [],
  plugins: window.GEMMA_MANAGEMENT?.loadPlugins?.() || {},
  activeId: null,
  activeFolderId: localStorage.getItem("gemma4.activeFolderId") || null,
  busy: false,
  webSearch: false,
  startedAt: 0,
  timerId: null,
  abortController: null,
  progressLabel: "生成中",
  progressReason: "",
  progressElapsedSeconds: 0,
  workspaceOpen: false,
  workspaceRoot: "",
  workspaceFiles: [],
  workspaceNote: "",
  workspacePreviewSearchIndex: 0,
  selectedFiles: new Set(),
  editingFolderId: null,
  editingSessionId: null,
  sidebarQuery: "",
  collapsedFolderIds: new Set(loadCollapsedFolderIds()),
  sidebarHidden: window.GEMMA_SIDEBAR?.shouldStartSidebarHidden?.({
    isMobile: window.matchMedia("(max-width: 760px)").matches,
    storedValue: localStorage.getItem("gemma4.sidebarHidden"),
  }) ?? localStorage.getItem("gemma4.sidebarHidden") === "true",
  sidebarWidth: Number(localStorage.getItem("gemma4.sidebarWidth")) || 268,
  language: localStorage.getItem("gemma4.language") || "ja",
  theme: localStorage.getItem("gemma4.theme") || "light",
  responseMode: localStorage.getItem("gemma4.responseMode") || "auto",
  thinkingMode: localStorage.getItem("gemma4.thinkingMode") || "auto",
  modelOverrides: {
    chat: localStorage.getItem("gemma4.model.chat") || "",
    coding: localStorage.getItem("gemma4.model.coding") || "",
    translation: localStorage.getItem("gemma4.model.translation") || "",
  },
  composerModel: localStorage.getItem("gemma4.composerModel") || "",
  externalLlmUrl: localStorage.getItem("gemma4.externalLlmUrl") || "",
  externalLlmStatus: "",
  activeTrainingSetId: localStorage.getItem("gemma4.activeTrainingSetId") || "",
  serverModels: {
    chat: "gemma4:12b",
    coding: "gemma4:12b",
    translation: "gemma4:12b",
    available: [],
    recommendedCoding: [],
    pullable: [],
    codingInstalled: true,
  },
  modelPullJobs: {},
  modelPullTimer: null,
  appInfo: {
    version: "",
    commit: "",
    searchCapabilities: null,
  },
  asrStatus: {
    status: "checking",
    candidates: [],
  },
  asrModel: localStorage.getItem("gemma4.asrModel") || "",
  micGain: Number(localStorage.getItem("gemma4.micGain")) || 1,
  micDeviceId: localStorage.getItem("gemma4.micDeviceId") || "",
  partialIntervalSeconds: Number(localStorage.getItem("gemma4.asrPartialIntervalSeconds")) || 3,
  partialMode: initialAsrPartialMode(),
  micDevices: [],
  asrSetupJob: {},
  asrSetupTimer: null,
  enterToSend: localStorage.getItem("gemma4.enterToSend") === "true",
  weatherLocation: window.GEMMA_WEATHER?.loadSavedWeatherLocation?.() || null,
  lastDeleted: null,
  pendingImages: [],
  pendingFiles: [],
  correctionDraft: null,
  memoryCandidate: null,
};

let stopMicLevelMonitor = null;

const WORKSPACE_PLAN_TIMEOUT_MS = 120000;
const WORKSPACE_FILE_TIMEOUT_MS = 300000;
const SIMPLE_WORKSPACE_FILE_TIMEOUT_MS = 120000;

const SYSTEM_PROMPTS = {
  ja: "あなたは簡潔で有用なAIです。前置きなしで自然に短く答えてください。箇条書きは、比較・手順・整理が必要な場合だけ使ってください。",
  en: "You are a concise and helpful assistant. Answer directly and naturally. Use bullet points only when comparison, steps, or structured explanation are useful.",
};

const SYSTEM_PROMPT_TEMPLATES = {
  default: {
    ja: SYSTEM_PROMPTS.ja,
    en: SYSTEM_PROMPTS.en,
  },
  teacher: {
    ja: "あなたは学生を支えるAIです。マイキャラ設定の名前と話し方を使いながら、やさしい先生のように説明してください。難しい言葉はかみ砕き、必要な時だけ例を入れてください。正確でないことは作らず、分からない時は確認をすすめてください。",
    en: "You are an AI that supports students. Use the configured character name and speaking style, while explaining like a friendly teacher. Rephrase difficult terms simply and add examples only when useful. Do not invent uncertain facts; suggest verification when needed.",
  },
  concise: {
    ja: "あなたは簡潔で有用なAIです。マイキャラ設定の名前と話し方を使いながら、前置きなしで短く答えてください。箇条書きは、比較・手順・整理が必要な場合だけ使ってください。分からないことは作らず、分からないと伝えてください。",
    en: "You are a concise and helpful AI. Use the configured character name and speaking style, while answering briefly without preamble. Use bullets only for comparisons, steps, or structured explanations. Do not invent unknown facts; say when you do not know.",
  },
  detailed: {
    ja: "あなたは学生を支えるAIです。マイキャラ設定の名前と話し方を使いながら、理由・手順・注意点を分かりやすく説明してください。長くなりすぎないように区切り、正確でないことは作らず、必要ならWeb検索や学習セットへの登録を提案してください。",
    en: "You are an AI that supports students. Use the configured character name and speaking style, while explaining reasons, steps, and cautions clearly. Keep long answers segmented. Do not invent uncertain facts; suggest web search or adding a learning-set correction when useful.",
  },
};

const AUTO_SAVE_SETTING_KEYS = {
  systemPrompt: "gemma4.systemPrompt",
  temperature: "gemma4.temperature",
  topP: "gemma4.topP",
  topK: "gemma4.topK",
  numPredict: "gemma4.numPredict",
  numCtx: "gemma4.numCtx",
  historyTurns: "gemma4.historyTurns",
};

const I18N = window.GEMMA_I18N || {};
const {
  attachmentKind,
  supportedAttachmentFile,
  extractAttachmentContents,
  attachmentContextFromResults,
  isVagueAttachmentQuestion,
  isAttachmentTranscriptRequest,
  messageWithAttachmentContext,
  attachmentPreviewLines,
  attachmentSummarySources,
  attachmentAnswerLooksBroken,
  lastReadableAttachment,
  lastAttachmentReference,
  directAttachmentAnswer,
  directAttachmentTranscriptAnswer,
  unreadablePreviousAttachmentAnswer,
  isAttachmentFollowupRequest,
} = window.GEMMA_ATTACHMENTS || {};

const els = {
  workspace: document.querySelector(".workspace"),
  sidebar: document.querySelector("#sidebar"),
  sidebarResizer: document.querySelector("#sidebar-resizer"),
  sidebarToggle: document.querySelector("#sidebar-toggle"),
  sidebarCollapse: document.querySelector("#sidebar-collapse"),
  settingsMenuToggle: document.querySelector("#settings-menu-toggle"),
  settingsMenuBack: document.querySelector("#settings-menu-back"),
  sidebarSettingsMenu: document.querySelector("#sidebar-settings-menu"),
  responseSettingsToggle: document.querySelector("#response-settings-toggle"),
  responseSettingsPanel: document.querySelector("#response-settings-panel"),
  responseSettingsClose: document.querySelector("#response-settings-close"),
  responseSettingsBody: document.querySelector("#response-settings-body"),
  responseSettingsGrid: document.querySelector("#response-settings-grid"),
  languageModelSettingsGrid: document.querySelector("#language-model-settings-grid"),
  languageModelDownloadView: document.querySelector("#language-model-download-view"),
  languageModelExternalView: document.querySelector("#language-model-external-view"),
  sidebarSearch: document.querySelector("#sidebar-search"),
  messages: document.querySelector("#messages"),
  prompt: document.querySelector("#prompt"),
  composer: document.querySelector("#composer"),
  progressLine: document.querySelector("#progress-line"),
  progressText: document.querySelector("#progress-text"),
  imageStrip: document.querySelector("#image-strip"),
  studyPackModeRow: document.querySelector("#study-pack-mode-row"),
  imageInput: document.querySelector("#image-input"),
  attachImage: document.querySelector("#attach-image"),
  voiceInput: document.querySelector("#voice-input"),
  composerStatus: document.querySelector("#composer-status"),
  send: document.querySelector("#send"),
  stop: document.querySelector("#stop"),
  newFolder: document.querySelector("#new-folder"),
  folderList: document.querySelector("#folder-list"),
  sessionList: document.querySelector("#session-list"),
  chatTitle: document.querySelector("#chat-title"),
  chatMeta: document.querySelector("#chat-meta"),
  sidebarAppVersion: document.querySelector("#sidebar-app-version"),
  statusDot: document.querySelector("#status-dot"),
  statusText: document.querySelector("#status-text"),
  clearChat: document.querySelector("#clear-chat"),
  webSearchToggle: document.querySelector("#web-search-toggle"),
  workspacePanel: document.querySelector("#workspace-panel"),
  workspaceClose: document.querySelector("#workspace-close"),
  workspaceFolderName: document.querySelector("#workspace-folder-name"),
  workspaceFolderTitle: document.querySelector("#workspace-folder-title"),
  workspaceRoot: document.querySelector("#workspace-root"),
  workspacePick: document.querySelector("#workspace-pick"),
  workspaceLoad: document.querySelector("#workspace-load"),
  workspaceTrainingSet: document.querySelector("#workspace-training-set"),
  workspaceCodegraphRow: document.querySelector("#workspace-codegraph-row"),
  workspaceCodegraphEnabled: document.querySelector("#workspace-codegraph-enabled"),
  workspaceCodegraphPrepare: document.querySelector("#workspace-codegraph-prepare"),
  workspaceCodegraphStatus: document.querySelector("#workspace-codegraph-status"),
  workspaceSearchRow: document.querySelector("#workspace-search-row"),
  workspaceSearchQuery: document.querySelector("#workspace-search-query"),
  workspaceSearchRun: document.querySelector("#workspace-search-run"),
  workspaceSearchStatus: document.querySelector("#workspace-search-status"),
  workspaceSearchResults: document.querySelector("#workspace-search-results"),
  workspaceStatus: document.querySelector("#workspace-status"),
  workspaceFiles: document.querySelector("#workspace-files"),
  workspacePreview: document.querySelector("#workspace-preview"),
  workspacePreviewPath: document.querySelector("#workspace-preview-path"),
  workspacePreviewSearch: document.querySelector("#workspace-preview-search"),
  workspacePreviewSearchCount: document.querySelector("#workspace-preview-search-count"),
  workspacePreviewPrev: document.querySelector("#workspace-preview-prev"),
  workspacePreviewNext: document.querySelector("#workspace-preview-next"),
  workspacePreviewContent: document.querySelector("#workspace-preview-content"),
  writePath: document.querySelector("#write-path"),
  writeContent: document.querySelector("#write-content"),
  writeFile: document.querySelector("#write-file"),
  revealPath: document.querySelector("#reveal-path"),
  undoToast: document.querySelector("#undo-toast"),
  undoText: document.querySelector("#undo-text"),
  undoDelete: document.querySelector("#undo-delete"),
  undoClose: document.querySelector("#undo-close"),
  settingsToggle: document.querySelector("#settings-toggle"),
  settingsClose: document.querySelector("#settings-close"),
  settingsPanel: document.querySelector("#settings-panel"),
  mobileConnectToggle: document.querySelector("#mobile-connect-toggle"),
  mobileConnectPanel: document.querySelector("#mobile-connect-panel"),
  mobileConnectClose: document.querySelector("#mobile-connect-close"),
  mobileConnectCode: document.querySelector("#mobile-connect-code"),
  mobileConnectExpires: document.querySelector("#mobile-connect-expires"),
  mobileConnectHosts: document.querySelector("#mobile-connect-hosts"),
  mobileConnectQrImage: document.querySelector("#mobile-connect-qr-image"),
  mobileConnectQrText: document.querySelector("#mobile-connect-qr-text"),
  mobileConnectStatus: document.querySelector("#mobile-connect-status"),
  mobileConnectRefresh: document.querySelector("#mobile-connect-refresh"),
  mobileImportJson: document.querySelector("#mobile-import-json"),
  mobileImportPreview: document.querySelector("#mobile-import-preview"),
  mobileImportPreviewButton: document.querySelector("#mobile-import-preview-button"),
  mobileImportApplyButton: document.querySelector("#mobile-import-apply-button"),
  mobileImportPendingButton: document.querySelector("#mobile-import-pending-button"),
  asrToggle: document.querySelector("#asr-toggle"),
  asrPanel: document.querySelector("#asr-panel"),
  asrClose: document.querySelector("#asr-close"),
  characterToggle: document.querySelector("#character-toggle"),
  characterPanel: document.querySelector("#character-panel"),
  characterClose: document.querySelector("#character-close"),
  characterName: document.querySelector("#character-name"),
  characterUserName: document.querySelector("#character-user-name"),
  characterSelfName: document.querySelector("#character-self-name"),
  characterGender: document.querySelector("#character-gender"),
  characterAvatar: document.querySelector("#character-avatar"),
  characterAvatarPreview: document.querySelector("#character-avatar-preview"),
  characterChatPreviewAvatar: document.querySelector("#character-chat-preview-avatar"),
  characterChatPreviewName: document.querySelector("#character-chat-preview-name"),
  characterChatPreviewText: document.querySelector("#character-chat-preview-text"),
  characterAvatarPick: document.querySelector("#character-avatar-pick"),
  characterAvatarClear: document.querySelector("#character-avatar-clear"),
  characterAvatarFile: document.querySelector("#character-avatar-file"),
  characterTone: document.querySelector("#character-tone"),
  characterMemoryMode: document.querySelector("#character-memory-mode"),
  characterMemoryModeChoices: document.querySelectorAll("input[name='character-memory-mode-choice']"),
  characterPersonality: document.querySelector("#character-personality"),
  characterSystemAddon: document.querySelector("#character-system-addon"),
  characterSave: document.querySelector("#character-save"),
  characterMemoryNew: document.querySelector("#character-memory-new"),
  characterMemoryAdd: document.querySelector("#character-memory-add"),
  characterMemoryFilters: document.querySelector("#character-memory-filters"),
  characterMemorySearch: document.querySelector("#character-memory-search"),
  characterMemoryList: document.querySelector("#character-memory-list"),
  studyPacksToggle: document.querySelector("#study-packs-toggle"),
  studyPacksPanel: document.querySelector("#study-packs-panel"),
  studyPacksClose: document.querySelector("#study-packs-close"),
  studyPackImportButton: document.querySelector("#study-pack-import-button"),
  studyPackImportInput: document.querySelector("#study-pack-import-input"),
  studyPackImportStatus: document.querySelector("#study-pack-import-status"),
  trainingManagementToggle: document.querySelector("#training-panel-toggle"),
  trainingManagementPanel: document.querySelector("#training-management-panel"),
  trainingManagementClose: document.querySelector("#training-management-close"),
  trainingManagementBody: document.querySelector("#training-management-body"),
  pluginsToggle: document.querySelector("#plugins-toggle"),
  pluginsPanel: document.querySelector("#plugins-panel"),
  pluginsClose: document.querySelector("#plugins-close"),
  languageModelsToggle: document.querySelector("#language-models-toggle"),
  languageModelsPanel: document.querySelector("#language-models-panel"),
  languageModelsClose: document.querySelector("#language-models-close"),
  languageModelsBody: document.querySelector("#language-models-body"),
  codegraphPluginToggle: document.querySelector("#codegraph-plugin-toggle"),
  codegraphPluginStatus: document.querySelector("#codegraph-plugin-status"),
  settingsMeta: document.querySelector("#settings-meta"),
  searchCapabilities: document.querySelector("#search-capabilities"),
  asrSettings: document.querySelector("#asr-settings"),
  weatherLocationUse: document.querySelector("#weather-location-use"),
  weatherLocationStatus: document.querySelector("#weather-location-status"),
  modelInstaller: document.querySelector("#model-installer"),
  externalLlmSettings: document.querySelector("#external-llm-settings"),
  externalLlmUrl: document.querySelector("#external-llm-url"),
  externalLlmCheck: document.querySelector("#external-llm-check"),
  externalLlmClear: document.querySelector("#external-llm-clear"),
  externalLlmCopyModel: document.querySelector("#external-llm-copy-model"),
  externalLlmStatus: document.querySelector("#external-llm-status"),
  languageSelect: document.querySelector("#language-select"),
  themeSelect: document.querySelector("#theme-select"),
  responseMode: document.querySelector("#response-mode"),
  composerResponseMode: document.querySelector("#composer-response-mode"),
  composerModel: document.querySelector("#composer-model"),
  thinkingMode: document.querySelector("#thinking-mode"),
  chatModel: document.querySelector("#chat-model"),
  codingModel: document.querySelector("#coding-model"),
  translationModel: document.querySelector("#translation-model"),
  systemPromptTemplate: document.querySelector("#system-prompt-template"),
  systemPrompt: document.querySelector("#system-prompt"),
  temperature: document.querySelector("#temperature"),
  topP: document.querySelector("#top-p"),
  topK: document.querySelector("#top-k"),
  numPredict: document.querySelector("#num-predict"),
  numCtx: document.querySelector("#num-ctx"),
  historyTurns: document.querySelector("#history-turns"),
  enterToSend: document.querySelector("#enter-to-send"),
  trainingSetName: document.querySelector("#training-set-name"),
  trainingSetCreate: document.querySelector("#training-set-create"),
  trainingSetSelect: document.querySelector("#training-set-select"),
  trainingSetRename: document.querySelector("#training-set-rename"),
  trainingSetDelete: document.querySelector("#training-set-delete"),
  trainingExportScope: document.querySelector("#training-export-scope"),
  trainingExport: document.querySelector("#training-export"),
  trainingSetSummary: document.querySelector("#training-set-summary"),
  trainingExamples: document.querySelector("#training-examples"),
  trainingExampleList: document.querySelector("#training-example-list"),
  trainingStatus: document.querySelector("#training-status"),
  correctionModal: document.querySelector("#correction-modal"),
  correctionTrainingSet: document.querySelector("#correction-training-set"),
  correctionText: document.querySelector("#correction-text"),
  correctionClose: document.querySelector("#correction-close"),
  correctionCancel: document.querySelector("#correction-cancel"),
  correctionSave: document.querySelector("#correction-save"),
  memoryCandidateModal: document.querySelector("#memory-candidate-modal"),
  memoryCandidateText: document.querySelector("#memory-candidate-text"),
  memoryCandidateClose: document.querySelector("#memory-candidate-close"),
  memoryCandidateDiscard: document.querySelector("#memory-candidate-discard"),
  memoryCandidateSave: document.querySelector("#memory-candidate-save"),
};

function t(key, params = {}) {
  const dictionary = I18N[state.language] || I18N.ja;
  let text = dictionary[key] || I18N.ja[key] || window.GEMMA_IMPORTED_STUDY_PACK_LABELS?.[key] || key;
  for (const [name, value] of Object.entries(params)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

function applyI18n() {
  document.documentElement.lang = state.language;
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.setAttribute("title", t(element.dataset.i18nTitle));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
  if (els.languageSelect) els.languageSelect.value = state.language;
}

function moveSettingsSections() {
  const moveField = (source, target) => {
    const field = source?.closest?.(".setting-field");
    if (field && target && field.parentElement !== target) target.append(field);
  };

  if (els.responseSettingsBody) {
    moveField(els.systemPrompt, els.responseSettingsBody);
  }
  [
    els.responseMode,
    els.thinkingMode,
    els.temperature,
    els.topP,
    els.topK,
    els.numPredict,
    els.numCtx,
    els.historyTurns,
    els.enterToSend,
  ].forEach((control) => moveField(control, els.responseSettingsGrid));

  [
    els.chatModel,
    els.codingModel,
    els.translationModel,
  ].forEach((control) => moveField(control, els.languageModelSettingsGrid));

  if (els.languageModelDownloadView && els.modelInstaller && els.modelInstaller.parentElement !== els.languageModelDownloadView) {
    els.languageModelDownloadView.append(els.modelInstaller);
  }
  if (els.languageModelExternalView && els.externalLlmSettings && els.externalLlmSettings.parentElement !== els.languageModelExternalView) {
    els.languageModelExternalView.append(els.externalLlmSettings);
  }

  if (els.pluginsPanel && els.searchCapabilities && els.searchCapabilities.parentElement !== els.pluginsPanel) {
    const pluginBody = els.pluginsPanel.querySelector(".plugin-candidates");
    els.pluginsPanel.insertBefore(els.searchCapabilities, pluginBody || els.pluginsPanel.lastElementChild);
  }

  if (els.trainingManagementPanel && els.trainingSetName) {
    const trainingPanel = els.trainingSetName.closest(".training-panel");
    const target = els.trainingManagementBody;
    if (trainingPanel && target && trainingPanel.parentElement !== target) {
      target.append(trainingPanel);
    }
  }
}

function allSystemPromptTemplateTexts() {
  return Object.values(SYSTEM_PROMPT_TEMPLATES)
    .flatMap((template) => Object.values(template));
}

function systemPromptTemplateText(templateId, language = state.language) {
  const template = SYSTEM_PROMPT_TEMPLATES[templateId] || SYSTEM_PROMPT_TEMPLATES.default;
  return template[language] || template.ja || SYSTEM_PROMPTS.ja;
}

function detectSystemPromptTemplate(value) {
  const text = (value || "").trim();
  for (const [id, template] of Object.entries(SYSTEM_PROMPT_TEMPLATES)) {
    if (Object.values(template).some((candidate) => candidate.trim() === text)) return id;
  }
  return "custom";
}

function syncSystemPromptTemplate() {
  if (!els.systemPromptTemplate || !els.systemPrompt) return;
  els.systemPromptTemplate.value = detectSystemPromptTemplate(els.systemPrompt.value);
}

function saveSystemPromptSetting() {
  if (!els.systemPrompt) return;
  localStorage.setItem(AUTO_SAVE_SETTING_KEYS.systemPrompt, els.systemPrompt.value);
}

function applySystemPromptTemplate(templateId) {
  if (!els.systemPrompt) return;
  if (templateId === "custom") {
    syncSystemPromptTemplate();
    return;
  }
  els.systemPrompt.value = systemPromptTemplateText(templateId);
  syncSystemPromptTemplate();
  saveSystemPromptSetting();
}

function restoreSelectSetting(select, storageKey) {
  if (!select) return;
  const saved = localStorage.getItem(storageKey);
  if (!saved) return;
  const hasOption = [...select.options].some((option) => option.value === saved);
  if (hasOption) select.value = saved;
}

function restoreAutoSavedSettings() {
  if (els.systemPrompt) {
    const savedPrompt = localStorage.getItem(AUTO_SAVE_SETTING_KEYS.systemPrompt);
    if (savedPrompt) els.systemPrompt.value = savedPrompt;
  }
  restoreSelectSetting(els.temperature, AUTO_SAVE_SETTING_KEYS.temperature);
  restoreSelectSetting(els.topP, AUTO_SAVE_SETTING_KEYS.topP);
  restoreSelectSetting(els.topK, AUTO_SAVE_SETTING_KEYS.topK);
  restoreSelectSetting(els.numPredict, AUTO_SAVE_SETTING_KEYS.numPredict);
  restoreSelectSetting(els.numCtx, AUTO_SAVE_SETTING_KEYS.numCtx);
  restoreSelectSetting(els.historyTurns, AUTO_SAVE_SETTING_KEYS.historyTurns);
  syncSystemPromptTemplate();
}

function saveSelectSetting(select, storageKey) {
  if (!select) return;
  localStorage.setItem(storageKey, select.value);
}

function setLanguage(language) {
  const next = I18N[language] ? language : "ja";
  const currentPrompt = els.systemPrompt?.value || "";
  state.language = next;
  localStorage.setItem("gemma4.language", state.language);
  const currentTemplate = detectSystemPromptTemplate(currentPrompt);
  if (els.systemPrompt && currentTemplate !== "custom") {
    els.systemPrompt.value = systemPromptTemplateText(currentTemplate, state.language);
    saveSystemPromptSetting();
  }
  syncSystemPromptTemplate();
  applyI18n();
  syncModelInputs();
  renderSettingsMeta();
  renderModelInstaller();
  renderAsrSettingsPanel();
  renderStudyPacksPanel();
  renderPluginsPanel();
  renderWeatherLocationStatus();
  render();
}

function loadSessions() {
  try {
    return JSON.parse(localStorage.getItem("gemma4.sessions") || "[]");
  } catch {
    return [];
  }
}

function loadFolders() {
  try {
    return JSON.parse(localStorage.getItem("gemma4.folders") || "[]");
  } catch {
    return [];
  }
}

function loadCollapsedFolderIds() {
  try {
    return JSON.parse(localStorage.getItem("gemma4.collapsedFolderIds") || "[]");
  } catch {
    return [];
  }
}

function loadTrainingSets() {
  return window.GEMMA_TRAINING?.loadTrainingSets?.() || [];
}

function saveSessions() {
  localStorage.setItem("gemma4.sessions", JSON.stringify(state.sessions));
}

function saveFolders() {
  localStorage.setItem("gemma4.folders", JSON.stringify(state.folders));
  localStorage.setItem("gemma4.activeFolderId", state.activeFolderId || "");
  localStorage.setItem("gemma4.foldersInitialized", "true");
}

function saveCollapsedFolders() {
  localStorage.setItem("gemma4.collapsedFolderIds", JSON.stringify([...state.collapsedFolderIds]));
}

function saveTrainingSets() {
  window.GEMMA_TRAINING?.saveTrainingSets?.({
    sets: state.trainingSets,
    activeTrainingSetId: state.activeTrainingSetId,
  });
}

function saveCharacterState() {
  state.character = window.GEMMA_CHARACTER?.saveCharacter?.(state.character) || state.character;
  state.characterMemorySets = window.GEMMA_CHARACTER?.saveMemorySets?.(state.characterMemorySets) || state.characterMemorySets;
}

function saveWorkspacePrefs() {
  const folder = activeFolder();
  if (!folder) return;
  folder.workspaceRoot = state.workspaceRoot;
  folder.selectedFiles = [...state.selectedFiles];
  saveFolders();
}

function createFolder(name = t("folder.new")) {
  const folderState = window.GEMMA_SIDEBAR.createFolderInState({
    state,
    name,
    createId: () => crypto.randomUUID(),
    now: () => Date.now(),
  });
  state.folders = folderState.folders;
  state.activeFolderId = folderState.activeFolderId;
  syncWorkspaceFromActiveFolder();
  saveFolders();
  return folderState.folder;
}

function activeFolder() {
  return state.folders.find((folder) => folder.id === state.activeFolderId) || state.folders[0] || null;
}

function characterAddressPrefix() {
  const userName = String(state.character?.userName || "").trim();
  return userName ? `${userName}、` : "";
}

function characterUncertainAnswer() {
  const prefix = characterAddressPrefix();
  return `${prefix}正確な情報を持っていないから、ここでは答えきれないよ。「Web検索」をONにするか、「修正して学習」で正しい情報を教えてね。`;
}

function applyCharacterToneToToolReply(content) {
  const text = String(content || "").trim();
  if (!text || state.language === "en") return text;
  if (text === t("training.uncertainAnswer")) return characterUncertainAnswer();
  const normalized = text.replace(/\s+/g, "").replace(/[。.!！]+$/g, "");
  if (/^(確認できません|わかりません|分かりません|不明です|確認できない)$/.test(normalized)) {
    return characterUncertainAnswer();
  }
  const prefix = characterAddressPrefix();
  if (!prefix || text.startsWith(prefix)) return text;
  return `${prefix}${text}`;
}

function workspaceFileKindFromText(text) {
  return workspaceFileKindFromTextApi?.(text, {
    hasLookupIntent: hasExplicitWorkspaceLookupIntent,
    isExcludedRequest: isCharacterPreferenceRequest,
  }) || "";
}

function attachmentReplyOptions() {
  return {
    toneReply: applyCharacterToneToToolReply,
    compactContent: compactWorkspaceContent,
    isCharacterPreference: isCharacterPreferenceRequest,
  };
}

function pushAssistantReply(session, { content, sources, durationSeconds, runMeta }) {
  session.messages.push({
    role: "assistant",
    content,
    ...(sources ? { sources } : {}),
    durationSeconds,
    runMeta,
  });
}

function attachmentRunMeta(requestOptions, modelReason) {
  return {
    model: "attachment-reader",
    modelLabel: "添付ファイル読み取り",
    task: "attachment",
    taskLabel: "添付ファイル",
    responseMode: requestOptions.responseMode,
    responseModeLabel: responseModeLabel(requestOptions.responseMode),
    thinkingMode: requestOptions.thinkingMode,
    modelReason,
    codeUnderstanding: false,
  };
}

function workspaceFileKindAnswer(text) {
  const kind = workspaceFileKindFromText(text);
  if (!kind || !state.workspaceRoot || !Array.isArray(state.workspaceFiles)) {
    return null;
  }
  const matches = state.workspaceFiles.filter((file) => workspaceFileMatchesKind(file, kind));
  const folderName = activeFolder()?.name || "このフォルダー";
  const label = workspaceFileKindLabel(kind);
  const sources = matches.slice(0, 8).map((file) => ({
    type: "workspace",
    title: file.path,
    path: file.path,
    line: "",
    snippet: `${label}ファイル`,
  }));
  if (!matches.length) {
    return {
      content: applyCharacterToneToToolReply(`${folderName}フォルダーには${label}ファイルは見つからなかったよ。`),
      sources,
    };
  }
  const visible = matches.slice(0, 8).map((file) => {
    const size = workspaceFormatBytes(file.size);
    return `- ${file.path}${size ? ` (${size})` : ""}`;
  });
  const more = matches.length > visible.length ? `\nほかに${matches.length - visible.length}件あるよ。` : "";
  return {
    content: applyCharacterToneToToolReply(`${folderName}フォルダーには${label}ファイルが${matches.length}件あるよ。\n${visible.join("\n")}${more}`),
    sources,
  };
}

function workspaceFilesForKind(kind) {
  if (!kind || !Array.isArray(state.workspaceFiles)) return [];
  return state.workspaceFiles.filter((file) => workspaceFileMatchesKind(file, kind));
}

function isWorkspaceFileContentRequest(text) {
  const normalized = String(text || "").trim();
  if (!normalized || isCharacterPreferenceRequest(normalized)) return false;
  return /(情報|内容|中身|本文|要約|説明|読んで|開いて|見せて|何が書いて|どんなこと|どんな内容|どんな中身|教えて|おしえて|文字起こし|全文|書き起こし)/i.test(normalized);
}

function isWorkspaceTranscriptRequest(text) {
  const normalized = String(text || "").trim();
  return /(文字起こし|書き起こし|全文|本文をそのまま|そのまま表示|原文)/i.test(normalized);
}

function workspaceSourceKind(source) {
  const path = String(source?.path || source?.title || "").toLowerCase();
  const snippet = String(source?.snippet || "").toLowerCase();
  if (path.endsWith(".pdf") || snippet.includes("pdf")) return "pdf";
  if (/\.(doc|docx)$/.test(path) || snippet.includes("word")) return "word";
  if (/\.(txt|md|csv|json|html?|css|js|ts|py)$/.test(path)) return "text";
  return "";
}

function isReadableWorkspaceSource(source) {
  return source?.type === "workspace"
    && source?.path
    && source?.sourceType !== "codegraph"
    && Boolean(workspaceSourceKind(source));
}

function lastReadableWorkspaceSource(session) {
  const messages = Array.isArray(session?.messages) ? session.messages : [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const sources = Array.isArray(messages[index]?.sources) ? messages[index].sources : [];
    const readable = sources.find((source) => isReadableWorkspaceSource(source));
    if (readable) return readable;
  }
  return null;
}

function isWorkspaceSourceContentFollowup(text) {
  const normalized = String(text || "").trim();
  if (!normalized || !state.workspaceRoot || isCharacterPreferenceRequest(normalized)) return false;
  return /^(どんな内容|どんな中身|内容[は？?]*|中身[は？?]*|要約|要約して|読んで|開いて|見せて|何が書いて|何が入って|どんなこと)/.test(normalized)
    || /(内容|中身|要約|本文).{0,12}(教えて|知りたい|見せて|読んで|確認)/.test(normalized)
    || /この(?:PDF|ファイル|資料|文書)|さっきの(?:PDF|ファイル|資料|文書)|それの(?:内容|中身|要約)/.test(normalized);
}

async function readWorkspaceSourceContent(source) {
  const path = String(source?.path || "").trim();
  if (!state.workspaceRoot || !path) throw new Error(t("workspace.sourceOpenError"));
  const response = await fetch("/api/workspace/read", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ root: state.workspaceRoot, path }),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || t("workspace.sourceOpenError"));
  return data;
}

function workspaceTranscriptAction({ path, content }) {
  return buildWorkspaceTranscriptAction?.({
    root: state.workspaceRoot,
    path,
    content,
  }) || null;
}

async function handleWorkspaceSourceFollowup(text) {
  let session = activeSession();
  if (!isWorkspaceSourceContentFollowup(text)) return false;
  if (!session) {
    newSession();
    session = activeSession();
  }
  const source = lastReadableWorkspaceSource(session);
  if (!source) return false;

  session.messages.push({ role: "user", content: text });
  updateSessionTitle(session, text);
  state.busy = true;
  startProgressTimer("ファイルを読んでいます", source.path);
  saveSessions();
  render();

  try {
    const data = await readWorkspaceSourceContent(source);
    const transcriptMode = isWorkspaceTranscriptRequest(text);
    const sourceContent = data.content || "";
    const summary = transcriptMode
      ? workspaceContentTranscript(data.content || "")
      : workspaceContentSummary(data.content || "");
    const path = data.path || source.path;
    const transcriptAction = transcriptMode ? workspaceTranscriptAction({ path, content: sourceContent }) : null;
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    const readLabel = transcriptMode ? "文字起こししたよ" : "内容を読んだよ";
    const content = summary
      ? characterizeToolAnswer(`${path} の${readLabel}。\n\n${summary}`, { type: "workspace" })
      : characterizeToolAnswer(`${path} は見つけたよ。ただ、本文はうまく読み取れなかったんだ。画像だけのPDF、保護されたPDF、特殊な文字埋め込みのPDFだと、OCRが必要になることがあるよ。`, { type: "workspace" });
    session.messages.push({
      role: "assistant",
      content,
      sources: [{
        type: "workspace",
        title: path,
        path,
        line: source.line || "",
        snippet: summary ? summary.slice(0, 180) : source.snippet || "",
      }],
      workspaceTranscript: transcriptAction,
      durationSeconds,
      runMeta: {
        model: "local-file-reader",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: state.responseMode,
        responseModeLabel: responseModeLabel(state.responseMode),
        thinkingMode: state.thinkingMode,
        modelReason: t("model.reasonWorkspaceLookup"),
        codeUnderstanding: false,
      },
    });
  } catch (error) {
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    session.messages.push({
      role: "assistant",
      content: characterizeToolAnswer(`${source.path} は見つけたよ。ただ、本文はうまく読み取れなかったんだ。画像だけのPDF、保護されたPDF、特殊な文字埋め込みのPDFだと、OCRが必要になることがあるよ。`, { type: "workspace" }),
      sources: [{
        type: "workspace",
        title: source.title || source.path,
        path: source.path,
        line: source.line || "",
        snippet: source.snippet || "",
      }],
      durationSeconds,
      runMeta: {
        model: "local-file-reader",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: state.responseMode,
        responseModeLabel: responseModeLabel(state.responseMode),
        thinkingMode: state.thinkingMode,
        modelReason: error?.message || t("workspace.sourceOpenError"),
        codeUnderstanding: false,
      },
    });
  } finally {
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
  return true;
}

async function handleWorkspaceFileKindContentRequest(text, requestOptions) {
  if (requestOptions?.codingMode || requestOptions?.translationMode) return false;
  if (!state.workspaceRoot || !isWorkspaceLookupRequest(text) || !isWorkspaceFileContentRequest(text)) return false;
  const kind = workspaceFileKindFromText(text);
  if (!kind) return false;
  if (!state.workspaceFiles.length) await loadWorkspace();
  const matches = workspaceFilesForKind(kind);
  if (!matches.length) return false;

  const session = activeSession();
  const label = workspaceFileKindLabel(kind);
  const visibleSources = matches.slice(0, 8).map((file) => ({
    type: "workspace",
    title: file.path,
    path: file.path,
    line: "",
    snippet: `${label}ファイル`,
  }));

  if (matches.length > 1) {
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    const visible = matches.slice(0, 8).map((file) => {
      const size = workspaceFormatBytes(file.size);
      return `- ${file.path}${size ? ` (${size})` : ""}`;
    });
    const more = matches.length > visible.length ? `\nほかに${matches.length - visible.length}件あるよ。` : "";
    session.messages.push({
      role: "assistant",
      content: applyCharacterToneToToolReply(`${label}ファイルが${matches.length}件あるよ。どのファイルの内容を読むか、ファイル名で教えてね。\n${visible.join("\n")}${more}`),
      sources: visibleSources,
      durationSeconds,
      runMeta: {
        model: "local-fast-search",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: requestOptions.responseMode,
        responseModeLabel: responseModeLabel(requestOptions.responseMode),
        thinkingMode: requestOptions.thinkingMode,
        modelReason: t("model.reasonWorkspaceLookup"),
        codeUnderstanding: false,
      },
    });
    return true;
  }

  const file = matches[0];
  startProgressTimer("ファイルを読んでいます", file.path);
  try {
    const data = await readWorkspaceSourceContent({ path: file.path });
    const transcriptMode = isWorkspaceTranscriptRequest(text);
    const path = data.path || file.path;
    const sourceContent = data.content || "";
    const summary = transcriptMode
      ? workspaceContentTranscript(sourceContent)
      : workspaceContentSummary(data.content || "");
    const transcriptAction = transcriptMode ? workspaceTranscriptAction({ path, content: sourceContent }) : null;
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    const readLabel = transcriptMode ? "文字起こししたよ" : "内容を読んだよ";
    const content = summary
      ? characterizeToolAnswer(`${path} の${readLabel}。\n\n${summary}`, { type: "workspace" })
      : characterizeToolAnswer(`${path} は見つけたよ。ただ、本文はうまく読み取れなかったんだ。画像だけのPDF、保護されたPDF、特殊な文字埋め込みのPDFだと、OCRが必要になることがあるよ。`, { type: "workspace" });
    session.messages.push({
      role: "assistant",
      content,
      sources: [{
        type: "workspace",
        title: path,
        path,
        line: "",
        snippet: summary ? summary.slice(0, 180) : `${label}ファイル`,
      }],
      workspaceTranscript: transcriptAction,
      durationSeconds,
      runMeta: {
        model: "local-file-reader",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: requestOptions.responseMode,
        responseModeLabel: responseModeLabel(requestOptions.responseMode),
        thinkingMode: requestOptions.thinkingMode,
        modelReason: t("model.reasonWorkspaceLookup"),
        codeUnderstanding: false,
      },
    });
  } catch {
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    session.messages.push({
      role: "assistant",
      content: characterizeToolAnswer(`${file.path} は見つけたよ。ただ、本文はうまく読み取れなかったんだ。画像だけのPDF、保護されたPDF、特殊な文字埋め込みのPDFだと、OCRが必要になることがあるよ。`, { type: "workspace" }),
      sources: visibleSources,
      durationSeconds,
      runMeta: {
        model: "local-file-reader",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: requestOptions.responseMode,
        responseModeLabel: responseModeLabel(requestOptions.responseMode),
        thinkingMode: requestOptions.thinkingMode,
        modelReason: t("workspace.sourceOpenError"),
        codeUnderstanding: false,
      },
    });
  }
  return true;
}

async function handleWorkspaceSearchContentRequest(text, sources, requestOptions) {
  if (requestOptions?.codingMode || requestOptions?.translationMode) return false;
  if (!state.workspaceRoot || !isWorkspaceLookupRequest(text) || !isWorkspaceFileContentRequest(text)) return false;
  const readableSources = (Array.isArray(sources) ? sources : [])
    .filter((source) => isReadableWorkspaceSource(source));
  if (!readableSources.length) return false;

  const session = activeSession();
  const transcriptMode = isWorkspaceTranscriptRequest(text);
  const pdfSources = readableSources.filter((source) => workspaceSourceKind(source) === "pdf");
  const candidates = pdfSources.length ? pdfSources : readableSources;

  if (candidates.length > 1 && !/この|それ|さっき|先ほど|1件|ひとつ|一つ/i.test(String(text || ""))) {
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    const visible = candidates.slice(0, 8).map((source) => `- ${source.path}`);
    const more = candidates.length > visible.length ? `\nほかに${candidates.length - visible.length}件あるよ。` : "";
    session.messages.push({
      role: "assistant",
      content: applyCharacterToneToToolReply(`読めそうなファイルが${candidates.length}件あるよ。どれを読むか、ファイル名で教えてね。\n${visible.join("\n")}${more}`),
      sources: candidates.slice(0, 8),
      durationSeconds,
      runMeta: {
        model: "local-fast-search",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: requestOptions.responseMode,
        responseModeLabel: responseModeLabel(requestOptions.responseMode),
        thinkingMode: requestOptions.thinkingMode,
        modelReason: t("model.reasonWorkspaceLookup"),
        codeUnderstanding: false,
      },
    });
    return true;
  }

  const source = candidates[0];
  startProgressTimer("ファイルを読んでいます", source.path);
  try {
    const data = await readWorkspaceSourceContent(source);
    const path = data.path || source.path;
    const sourceContent = data.content || "";
    const summary = transcriptMode
      ? workspaceContentTranscript(sourceContent)
      : workspaceContentSummary(sourceContent);
    const transcriptAction = transcriptMode ? workspaceTranscriptAction({ path, content: sourceContent }) : null;
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    const readLabel = transcriptMode ? "文字起こししたよ" : "内容を読んだよ";
    const content = summary
      ? characterizeToolAnswer(`${path} の${readLabel}。\n\n${summary}`, { type: "workspace" })
      : characterizeToolAnswer(`${path} は見つけたよ。ただ、本文はうまく読み取れなかったんだ。画像だけのPDF、保護されたPDF、特殊な文字埋め込みのPDFだと、OCRが必要になることがあるよ。`, { type: "workspace" });
    session.messages.push({
      role: "assistant",
      content,
      sources: [{
        ...source,
        title: path,
        path,
        line: "",
        snippet: summary ? summary.slice(0, 180) : source.snippet || "",
      }],
      workspaceTranscript: transcriptAction,
      durationSeconds,
      runMeta: {
        model: "local-file-reader",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: requestOptions.responseMode,
        responseModeLabel: responseModeLabel(requestOptions.responseMode),
        thinkingMode: requestOptions.thinkingMode,
        modelReason: t("model.reasonWorkspaceLookup"),
        codeUnderstanding: false,
      },
    });
  } catch {
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    session.messages.push({
      role: "assistant",
      content: characterizeToolAnswer(`${source.path} は見つけたよ。ただ、本文はうまく読み取れなかったんだ。画像だけのPDF、保護されたPDF、特殊な文字埋め込みのPDFだと、OCRが必要になることがあるよ。`, { type: "workspace" }),
      sources: [source],
      durationSeconds,
      runMeta: {
        model: "local-file-reader",
        modelLabel: t("workspace.chatSearchModel"),
        task: "search",
        taskLabel: t("workspace.fastSearch"),
        responseMode: requestOptions.responseMode,
        responseModeLabel: responseModeLabel(requestOptions.responseMode),
        thinkingMode: requestOptions.thinkingMode,
        modelReason: t("workspace.sourceOpenError"),
        codeUnderstanding: false,
      },
    });
  } finally {
    stopProgressTimer();
    state.busy = false;
    saveSessions();
    render();
  }
  return true;
}

function workspaceSearchQueryFromText(text) {
  const folder = activeFolder();
  const fastSearchReady = Boolean(state.plugins?.["fast-search"]?.installed);
  if (!state.workspaceRoot || !fastSearchReady || !folder) return "";
  if ((isWorkspaceBuildRequest(text) && !isWorkspaceLookupRequest(text)) || isTranslationRequest(text)) return "";
  const normalized = String(text || "").trim();
  if (!hasExplicitWorkspaceLookupIntent(normalized) || isCharacterPreferenceRequest(normalized)) {
    return "";
  }
  const fileKind = workspaceFileKindFromText(normalized);
  if (fileKind) return fileKind === "word" ? "doc" : fileKind;
  const quoted = normalized.match(/[「『"']([^「」『』"']{1,80})[」』"']/);
  if (quoted?.[1]) return quoted[1].trim();
  const fileName = normalized.match(/\b([A-Za-z0-9_.-]+\.(?:txt|md|pdf|docx?|html|css|js|jsx|ts|tsx|py|json|csv))\b/i);
  if (fileName?.[1]) return fileName[1].trim();
  const documentType = normalized.match(/(契約書|請求書|仕様書|見積書|領収書|議事録|PDF|pdf|Word|ワード|docx?|contract|agreement|invoice|specification|spec|estimate|quotation|receipt|minutes)/i);
  if (documentType?.[1]) return documentType[1].trim();
  const beforeFileWord = normalized.match(/([A-Za-z0-9_.-]{2,80}|[ぁ-んァ-ヶ一-龠ー]{2,40})\s*(?:という|の)?\s*(?:ファイル|file)/i);
  if (beforeFileWord?.[1]) return beforeFileWord[1].trim();
  const beforeFile = normalized.match(/([A-Za-z0-9_.-]{2,80}|[ぁ-んァ-ヶ一-龠ー]{2,40})\s*(?:は|って|が|を)?\s*(?:どの|どこ|含ま|書か|記載|検索|探)/i);
  if (beforeFile?.[1]) return beforeFile[1].trim();
  const afterSearch = normalized.match(/(?:検索|探|find|search)\s*(?:して|する|している|for)?\s*[:：]?\s*([A-Za-z0-9_.-]{2,80}|[ぁ-んァ-ヶ一-龠ー]{2,40})/i);
  if (afterSearch?.[1]) return afterSearch[1].trim();
  return "";
}

function workspacePayload(text = "") {
  const codegraph = activeFolder()?.plugins?.codegraph || {};
  return {
    root: state.workspaceRoot,
    files: [...state.selectedFiles],
    codegraph: Boolean(codegraph.enabled && codegraph.status === "ready"),
    searchQuery: workspaceSearchQueryFromText(text),
  };
}

async function workspaceSearchSourcesForChat(workspace) {
  if (!workspace?.root || !workspace?.searchQuery) return [];
  try {
    const response = await fetch("/api/workspace/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root: workspace.root, query: workspace.searchQuery }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok || !Array.isArray(data.results)) return [];
    return data.results.slice(0, 8).map((item) => ({
      type: "workspace",
      title: item.matchType === "body" && item.line ? `${item.path || ""}:${item.line || ""}` : String(item.path || ""),
      path: String(item.path || ""),
      line: item.matchType === "body" ? (item.line || "") : "",
      snippet: String(item.preview || ""),
      matchType: String(item.matchType || ""),
      sourceKind: String(item.sourceKind || ""),
    })).filter((source) => source.path);
  } catch {
    return [];
  }
}

function workspaceSearchAnswer(workspace, sources) {
  if (!workspace?.searchQuery) return "";
  if (!sources.length) {
    return applyCharacterToneToToolReply(t("workspace.chatSearchNoResults", { query: workspace.searchQuery }));
  }
  const visible = sources.slice(0, 6);
  const filenameOnly = visible.every((source) => source.matchType === "filename");
  const lines = visible.map((source) => {
    const location = source.line ? `${source.path}:${source.line}` : source.path;
    const matchLabel = source.matchType === "filename" ? "（ファイル名）" : "";
    const snippet = source.snippet && source.matchType !== "filename" ? ` - ${source.snippet}` : "";
    return `- ${location}${matchLabel}${snippet}`;
  });
  const summary = filenameOnly
    ? `フォルダー内検索で「${workspace.searchQuery}」がファイル名に含まれるファイルが見つかりました。本文の中ではなく、ファイル名で見つかった結果です。`
    : t("workspace.chatSearchFound", { query: workspace.searchQuery });
  const more = sources.length > visible.length
    ? `\n${t("workspace.chatSearchMore", { count: sources.length - visible.length })}`
    : "";
  return applyCharacterToneToToolReply(`${summary}\n${lines.join("\n")}${more}`);
}

function codegraphSourcesForChat(limit = 5) {
  const codegraph = activeFolder()?.plugins?.codegraph || {};
  if (!codegraph.enabled || codegraph.status !== "ready") return [];
  const files = Array.isArray(codegraph.summary?.files) ? codegraph.summary.files : [];
  return files.slice(0, limit).map((item) => {
    const symbols = Array.isArray(item.symbols) ? item.symbols.slice(0, 4).filter(Boolean) : [];
    const imports = Array.isArray(item.imports) ? item.imports.slice(0, 3).filter(Boolean) : [];
    const detail = [
      symbols.length ? `${t("workspace.codeSymbols")}: ${symbols.join(", ")}` : "",
      imports.length ? `${t("workspace.codeImports")}: ${imports.join(", ")}` : "",
    ].filter(Boolean).join(" / ");
    return {
      type: "workspace",
      sourceType: "codegraph",
      title: item.path || "",
      path: String(item.path || ""),
      line: "",
      snippet: detail || t("workspace.codeUnderstanding"),
    };
  }).filter((source) => source.path);
}

function workspaceLookupAnswer(workspace, searchSources, codegraphSources) {
  if (searchSources.length) {
    return workspaceSearchAnswer(workspace, searchSources);
  }
  if (workspace?.searchQuery) {
    return workspaceSearchAnswer(workspace, []);
  }
  const folderName = activeFolder()?.name || "このフォルダー";
  const fileNames = [...state.selectedFiles].slice(0, 8);
  if (fileNames.length) {
    return applyCharacterToneToToolReply(`${folderName}には以下のファイルがあります。\n${fileNames.map((name) => `- ${name}`).join("\n")}`);
  }
  if (codegraphSources.length) {
    const lines = codegraphSources.slice(0, 6).map((source) => `- ${source.path}${source.snippet ? ` - ${source.snippet}` : ""}`);
    return applyCharacterToneToToolReply(`${folderName}のコードを確認しました。\n${lines.join("\n")}`);
  }
  return applyCharacterToneToToolReply("このフォルダーで参照できるファイルはまだ読み込まれていません。フォルダー設定で再読み込みしてください。");
}

function renderWorkspacePreviewContent(content, activeLine = "") {
  renderWorkspacePreviewContentView?.(els.workspacePreviewContent, content, activeLine);
}

function updateWorkspacePreviewSearch({ jump = false, direction = 0 } = {}) {
  updateWorkspacePreviewSearchView?.({
    contentTarget: els.workspacePreviewContent,
    searchInput: els.workspacePreviewSearch,
    countTarget: els.workspacePreviewSearchCount,
    previousButton: els.workspacePreviewPrev,
    nextButton: els.workspacePreviewNext,
    state,
    t,
    jump,
    direction,
  });
}

async function openWorkspaceSource(source) {
  const path = String(source?.path || "").trim();
  if (!state.workspaceRoot || !path) return;
  try {
    const response = await fetch("/api/workspace/read", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root: state.workspaceRoot, path }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Could not read file.");
    state.workspaceOpen = true;
    if (els.workspacePreview) els.workspacePreview.hidden = false;
    if (els.workspacePreviewPath) {
      els.workspacePreviewPath.textContent = source?.line
        ? `${data.path || path}:${source.line}`
        : data.path || path;
    }
    renderWorkspacePreviewContent(data.content || "", source?.line);
    if (els.workspacePreviewSearch) {
      els.workspacePreviewSearch.value = "";
      state.workspacePreviewSearchIndex = 0;
      updateWorkspacePreviewSearch();
    }
    if (els.workspaceStatus) {
      els.workspaceStatus.textContent = t("workspace.sourceOpened", { path: data.path || path });
    }
    render();
    window.requestAnimationFrame(() => {
      els.workspacePreview?.scrollIntoView({ block: "nearest" });
      els.workspacePanel?.scrollIntoView({ block: "nearest" });
    });
  } catch (error) {
    if (els.workspaceStatus) {
      els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message || t("workspace.sourceOpenError")}`;
    }
    state.workspaceOpen = true;
    render();
  }
}

function ensureFolderData() {
  const initialized = localStorage.getItem("gemma4.foldersInitialized") === "true";
  if (state.folders.length === 0 && !initialized) {
    state.folders.push({
      id: crypto.randomUUID(),
      name: t("folder.default"),
      workspaceRoot: localStorage.getItem("gemma4.workspaceRoot") || "",
      selectedFiles: JSON.parse(localStorage.getItem("gemma4.selectedFiles") || "[]"),
      createdAt: Date.now(),
    });
  }
  if (state.folders.length === 0) {
    state.activeFolderId = null;
    state.activeId = null;
    saveFolders();
    saveSessions();
    return;
  }
  if (!state.folders.some((folder) => folder.id === state.activeFolderId)) {
    state.activeFolderId = state.folders[0].id;
  }
  for (const folder of state.folders) {
    if (!Array.isArray(folder.selectedFiles)) folder.selectedFiles = [];
    if (typeof folder.workspaceRoot !== "string") folder.workspaceRoot = "";
    if (typeof folder.trainingSetId !== "string") folder.trainingSetId = "";
    if (!folder.plugins || typeof folder.plugins !== "object" || Array.isArray(folder.plugins)) folder.plugins = {};
    if (!folder.plugins.codegraph || typeof folder.plugins.codegraph !== "object" || Array.isArray(folder.plugins.codegraph)) {
      folder.plugins.codegraph = {};
    }
    folder.plugins.codegraph.enabled = Boolean(folder.plugins.codegraph.enabled);
    if (typeof folder.plugins.codegraph.status !== "string") folder.plugins.codegraph.status = "not-ready";
    if (!folder.name) folder.name = t("folder.untitled");
  }
  ensureTrainingSets();
  for (const session of state.sessions) {
    if (!session.folderId || !state.folders.some((folder) => folder.id === session.folderId)) {
      session.folderId = state.activeFolderId;
    }
  }
  saveFolders();
  saveSessions();
}

function ensureTrainingSets() {
  state.activeTrainingSetId = window.GEMMA_TRAINING?.normalizeTrainingSets?.({
    sets: state.trainingSets,
    folders: state.folders,
    activeTrainingSetId: state.activeTrainingSetId,
    defaultName: t("settings.trainingSetDefault"),
    createId: () => crypto.randomUUID(),
    now: () => Date.now(),
  }) || "";
  saveTrainingSets();
}

function syncWorkspaceFromActiveFolder() {
  const folder = activeFolder();
  state.workspaceRoot = folder?.workspaceRoot || "";
  state.selectedFiles = new Set(folder?.selectedFiles || []);
  state.workspaceFiles = [];
  state.workspaceNote = "";
}

function sessionsForActiveFolder() {
  return state.sessions.filter((session) => session.folderId === state.activeFolderId);
}

function sessionsForFolder(folderId) {
  return state.sessions.filter((session) => session.folderId === folderId);
}

function selectFirstSessionInActiveFolder() {
  const sessions = sessionsForActiveFolder();
  state.activeId = sessions[0]?.id || null;
}

function setTheme(theme) {
  state.theme = ["dark", "light", "green"].includes(theme) ? theme : "light";
  document.body.dataset.theme = state.theme;
  localStorage.setItem("gemma4.theme", state.theme);
  if (els.themeSelect) els.themeSelect.value = state.theme;
}

function openInitialManagementPanelFromUrl() {
  const params = new URLSearchParams(window.location.search || "");
  const panel = window.location.pathname === "/pc-mobile-connect"
    ? "mobile-connect"
    : params.get("panel") || window.location.hash.replace(/^#/, "");
  if (panel !== "mobile-connect") return;
  window.GEMMA_MANAGEMENT?.setSidebarSettingsMode?.({ els, open: true });
  window.GEMMA_MANAGEMENT?.openManagementPanel?.({ els, panel: els.mobileConnectPanel });
  window.GEMMA_MANAGEMENT?.refreshMobileConnectInfo?.({ els, t });
}

function setLanguageFromControl(language) {
  setLanguage(language);
}

function setResponseMode(mode) {
  state.responseMode = ["auto", "fast", "balanced", "quality"].includes(mode) ? mode : "auto";
  localStorage.setItem("gemma4.responseMode", state.responseMode);
  if (els.responseMode) els.responseMode.value = state.responseMode;
  if (els.composerResponseMode) els.composerResponseMode.value = state.responseMode;
}

function setThinkingMode(mode) {
  state.thinkingMode = ["auto", "low", "medium", "high"].includes(mode) ? mode : "auto";
  localStorage.setItem("gemma4.thinkingMode", state.thinkingMode);
  if (els.thinkingMode) els.thinkingMode.value = state.thinkingMode;
}

function setModelOverride(task, value) {
  if (!["chat", "coding", "translation"].includes(task)) return;
  state.modelOverrides[task] = String(value || "").trim();
  localStorage.setItem(`gemma4.model.${task}`, state.modelOverrides[task]);
}

function setComposerModel(value) {
  state.composerModel = String(value || "").trim();
  localStorage.setItem("gemma4.composerModel", state.composerModel);
  if (els.composerModel) els.composerModel.value = state.composerModel;
}

function modelForTask(task, useComposer = false) {
  return window.GEMMA_MODELS.modelForTask(task, {
    useComposer,
    composerModel: state.composerModel,
    modelOverrides: state.modelOverrides,
    serverModels: state.serverModels,
  });
}

function fallbackCodingModel() {
  return window.GEMMA_MODELS.fallbackCodingModel({ serverModels: state.serverModels });
}

function fastChatModel() {
  return window.GEMMA_MODELS.fastChatModel({
    serverModels: state.serverModels,
    modelIsInstalled,
  });
}

function modelIsInstalled(model) {
  return state.serverModels.available.includes(model);
}

function displayModelName(model, task = "chat") {
  return window.GEMMA_MODELS.displayModelName(model, task, { t, modelIsInstalled });
}

function shortModelName(model, task = "chat") {
  return window.GEMMA_MODELS.shortModelName(model, task, { t, modelIsInstalled });
}

function composerModelLabel(model) {
  return window.GEMMA_MODELS.composerModelLabel(model, { t, modelIsInstalled });
}

function taskLabel(task) {
  return window.GEMMA_MODELS.taskLabel(task, t);
}

function responseModeLabel(mode) {
  return window.GEMMA_MODELS.responseModeLabel(mode, t);
}

function messageRunMeta(requestOptions, model, overrides = {}) {
  const task = requestOptions.translationMode ? "translation" : requestOptions.codingMode ? "coding" : "chat";
  const codegraph = activeFolder()?.plugins?.codegraph || {};
  return {
    model: model || modelForTask(task),
    modelLabel: shortModelName(model || modelForTask(task), task),
    task,
    taskLabel: taskLabel(task),
    responseMode: requestOptions.responseMode,
    responseModeLabel: responseModeLabel(requestOptions.responseMode),
    thinkingMode: requestOptions.thinkingMode,
    modelReason: requestOptions.modelReason || "",
    codeUnderstanding: Boolean(codegraph.enabled && codegraph.status === "ready"),
    ...overrides,
  };
}

function modelForRequestTask(task, requestOptions) {
  return window.GEMMA_MODELS.modelForRequestTask(task, requestOptions, {
    composerModel: state.composerModel,
    modelOverrides: state.modelOverrides,
    serverModels: state.serverModels,
    modelIsInstalled,
  });
}

function syncModelInputs() {
  return window.GEMMA_SETTINGS.renderModelSettingsSelects({
    composerModelLabel,
    displayModelName,
    els,
    modelIsInstalled,
    state,
    t,
  });
}

function renderModelInstaller() {
  return window.GEMMA_SETTINGS.renderModelInstaller({
    composerModelLabel,
    els,
    modelIsInstalled,
    state,
    t,
  });
}

function renderAsrSettingsPanel() {
  renderAsrSettings?.({
    container: els.asrSettings,
    status: state.asrStatus,
    selectedModel: state.asrModel,
    setupJob: state.asrSetupJob,
    micGain: state.micGain,
    micDevices: state.micDevices,
    micDeviceId: state.micDeviceId,
    partialIntervalSeconds: state.partialIntervalSeconds,
    partialMode: state.partialMode,
    t,
  });
}

function setAsrModel(model) {
  state.asrModel = model || "";
  localStorage.setItem("gemma4.asrModel", state.asrModel);
  renderAsrSettingsPanel();
}

function setMicGain(value, { render = true } = {}) {
  const normalized = normalizeMicGain?.(value) ?? Math.min(3, Math.max(0.5, Number(value) || 1));
  state.micGain = normalized;
  localStorage.setItem("gemma4.micGain", String(normalized));
  const output = els.asrSettings?.querySelector("[data-asr-mic-gain-value]");
  if (output) output.textContent = formatMicGain?.(normalized) || `${normalized.toFixed(1)}x`;
  if (render) renderAsrSettingsPanel();
}

function setMicDevice(deviceId, { render = true } = {}) {
  state.micDeviceId = deviceId || "";
  localStorage.setItem("gemma4.micDeviceId", state.micDeviceId);
  if (render) renderAsrSettingsPanel();
}

function setPartialIntervalSeconds(value, { render = true } = {}) {
  const normalized = normalizePartialIntervalSeconds?.(value) || 3;
  state.partialIntervalSeconds = normalized;
  localStorage.setItem("gemma4.asrPartialIntervalSeconds", String(normalized));
  if (render) renderAsrSettingsPanel();
}

function setPartialMode(value, { render = true } = {}) {
  const normalized = normalizePartialTranscriptionMode?.(value) || "browser";
  state.partialMode = normalized;
  localStorage.setItem("gemma4.asrPartialMode", normalized);
  if (render) renderAsrSettingsPanel();
}

function setMicLevelMessage(message, { error = false } = {}) {
  const status = els.asrSettings?.querySelector("[data-asr-level-status]");
  if (!status) return;
  status.textContent = message || "";
  status.classList.toggle("error", Boolean(error));
}

function stopMicLevelPreview() {
  if (!stopMicLevelMonitor) return;
  stopMicLevelMonitor();
  stopMicLevelMonitor = null;
  setMicLevelMessage(t("settings.asrMicLevelIdle"));
}

async function startMicLevelPreview() {
  if (!startMicLevelMonitor) return;
  stopMicLevelPreview();
  try {
    stopMicLevelMonitor = await startMicLevelMonitor({
      rootElement: els.asrSettings,
      deviceId: state.micDeviceId,
      micGain: state.micGain,
      t,
    });
  } catch (error) {
    setMicLevelMessage(t("settings.asrMicLevelError", { error: error.message || t("composer.voiceError") }), { error: true });
  }
}

async function refreshMicDevices({ startMonitor = false } = {}) {
  if (!listAudioInputDevices) return;
  try {
    state.micDevices = await listAudioInputDevices();
    if (!state.micDeviceId && window.GEMMA_ASR?.defaultAudioInputLooksVirtual?.(state.micDevices)) {
      const realDevice = window.GEMMA_ASR?.preferredRealAudioInputDevice?.(state.micDevices);
      if (realDevice?.deviceId) {
        state.micDeviceId = realDevice.deviceId;
        localStorage.setItem("gemma4.micDeviceId", state.micDeviceId);
      }
    }
    renderAsrSettingsPanel();
    if (state.micDeviceId && window.GEMMA_ASR?.defaultAudioInputLooksVirtual?.(state.micDevices)) {
      const activeDevice = state.micDevices.find((device) => device.deviceId === state.micDeviceId);
      setMicLevelMessage(t("settings.asrMicAutoSelectedRealDevice", {
        device: activeDevice?.label || t("settings.asrMicSavedDevice"),
      }));
    }
    if (startMonitor) await startMicLevelPreview();
  } catch (error) {
    setMicLevelMessage(t("settings.asrMicLevelError", { error: error.message || t("composer.voiceError") }), { error: true });
  }
}

async function refreshAsrStatus() {
  try {
    state.asrStatus = await fetchAsrStatus?.() || { status: "not_configured", candidates: [] };
    const runnableModels = new Set(Array.isArray(state.asrStatus.runnableModels) ? state.asrStatus.runnableModels : []);
    if ((!state.asrModel || !runnableModels.has(state.asrModel)) && state.asrStatus.recommendedModel) {
      setAsrModel(state.asrStatus.recommendedModel);
      return;
    }
  } catch (error) {
    state.asrStatus = {
      ok: false,
      available: false,
      status: "error",
      message: error.message || t("composer.voiceError"),
      candidates: [],
      nextStep: "",
    };
  }
  renderAsrSettingsPanel();
}

async function refreshAsrSetupStatus() {
  try {
    const data = await fetchAsrSetupStatus?.();
    state.asrSetupJob = data?.job || {};
    renderAsrSettingsPanel();
    const running = state.asrSetupJob.status === "running" || state.asrSetupJob.status === "queued";
    if (!running && state.asrSetupTimer) {
      window.clearInterval(state.asrSetupTimer);
      state.asrSetupTimer = null;
      refreshAsrStatus();
    }
  } catch {
    // ASR status polling will surface connectivity issues.
  }
}

function ensureAsrSetupPolling() {
  if (state.asrSetupTimer) return;
  state.asrSetupTimer = window.setInterval(refreshAsrSetupStatus, 1500);
}

async function startAsrSetup() {
  const ok = window.confirm(t("settings.asrSetupConfirm"));
  if (!ok) return;
  try {
    const data = await requestAsrSetup?.();
    state.asrSetupJob = {
      status: data?.status || "running",
      message: data?.message || t("settings.asrSetupRunning"),
    };
    renderAsrSettingsPanel();
    ensureAsrSetupPolling();
  } catch (error) {
    window.alert(error.message || t("composer.voiceError"));
  }
}

async function refreshModelPullStatus() {
  try {
    const data = await window.GEMMA_SETTINGS.fetchModelPullStatus();
    state.modelPullJobs = data.jobs || {};
    if (Array.isArray(data.availableModels)) {
      state.serverModels.available = data.availableModels;
    }
    renderModelInstaller();
    const running = Object.values(state.modelPullJobs).some((job) => job.status === "running" || job.status === "queued");
    if (!running && state.modelPullTimer) {
      window.clearInterval(state.modelPullTimer);
      state.modelPullTimer = null;
      checkHealth();
    }
  } catch {
    // Health polling will surface offline state.
  }
}

function ensureModelPullPolling() {
  if (state.modelPullTimer) return;
  state.modelPullTimer = window.setInterval(refreshModelPullStatus, 1500);
}

async function startModelPull(model) {
  const ok = window.confirm(state.language === "en"
    ? "Download this model? It can take time and use several GB of data."
    : "モデルをダウンロードします。数GBの通信と時間がかかる場合があります。開始しますか？");
  if (!ok) return;
  try {
    const data = await window.GEMMA_SETTINGS.requestModelPull(model).catch((error) => {
      throw new Error(error.message || (state.language === "en" ? "Could not start model download." : "モデルのダウンロードを開始できませんでした。"));
    });
    state.modelPullJobs[model] = {
      model,
      status: data.status || "running",
      message: data.message || (state.language === "en" ? "Download started." : "ダウンロードを開始しました。"),
    };
    renderModelInstaller();
    ensureModelPullPolling();
  } catch (error) {
    window.alert(error.message);
  }
}

function renderSettingsMeta() {
  if (els.sidebarAppVersion) {
    const version = state.appInfo.version || "0.8.197";
    els.sidebarAppVersion.textContent = state.language === "en" ? `App ${version}` : `アプリ版 ${version}`;
  }
  const deps = {
    displayModelName,
    els,
    escapeHtml,
    modelForTask,
    modelIsInstalled,
    state,
    t,
  };
  window.GEMMA_SETTINGS.renderSettingsMeta(deps);
  window.GEMMA_SETTINGS.renderSearchCapabilitiesPanel?.(deps);
  renderExternalLlmSettings();
}

function renderExternalLlmSettings(message = "") {
  if (els.externalLlmUrl) els.externalLlmUrl.value = state.externalLlmUrl || "";
  if (els.externalLlmStatus) {
    els.externalLlmStatus.textContent = message || state.externalLlmStatus || t("settings.externalLlmIdle");
  }
}

function setExternalLlmUrl(value) {
  state.externalLlmUrl = String(value || "").trim();
  localStorage.setItem("gemma4.externalLlmUrl", state.externalLlmUrl);
  state.externalLlmStatus = state.externalLlmUrl ? t("settings.externalLlmSaved") : t("settings.externalLlmIdle");
  renderExternalLlmSettings();
}

function clearExternalLlmSettings() {
  state.externalLlmUrl = "";
  localStorage.removeItem("gemma4.externalLlmUrl");
  state.externalLlmStatus = t("settings.externalLlmCleared");
  renderExternalLlmSettings();
}

function copyExternalLlmModelName() {
  const modelName = "YTan2000/Qwen3.6-27B-MTP-TQ3_4S";
  navigator.clipboard?.writeText(modelName)
    .then(() => {
      state.externalLlmStatus = t("settings.externalLlmModelCopied");
      renderExternalLlmSettings();
    })
    .catch(() => {
      state.externalLlmStatus = modelName;
      renderExternalLlmSettings();
    });
}

async function checkExternalLlmServer() {
  if (!els.externalLlmCheck) return;
  setExternalLlmUrl(els.externalLlmUrl?.value || "");
  els.externalLlmCheck.disabled = true;
  state.externalLlmStatus = t("settings.externalLlmChecking");
  renderExternalLlmSettings();
  try {
    const response = await fetch("/api/llm/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: state.externalLlmUrl }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.error || t("settings.externalLlmError"));
    const modelCount = Array.isArray(data.models) ? data.models.length : 0;
    state.externalLlmStatus = t("settings.externalLlmReady", {
      version: data.version || "-",
      count: String(modelCount),
    });
  } catch (error) {
    state.externalLlmStatus = `${t("error.prefix")}: ${error.message || t("settings.externalLlmError")}`;
  } finally {
    els.externalLlmCheck.disabled = false;
    renderExternalLlmSettings();
  }
}

function renderWeatherLocationStatus(message = "") {
  if (!els.weatherLocationStatus) return;
  if (message) {
    els.weatherLocationStatus.textContent = message;
    return;
  }
  if (!state.weatherLocation) {
    els.weatherLocationStatus.textContent = t("settings.weatherLocationHelp");
    return;
  }
  const updated = state.weatherLocation.updatedAt
    ? new Date(state.weatherLocation.updatedAt).toLocaleString(state.language === "en" ? "en-US" : "ja-JP")
    : "";
  const accuracy = state.weatherLocation.accuracy ? ` / ±${Math.round(state.weatherLocation.accuracy)}m` : "";
  els.weatherLocationStatus.textContent = `${t("settings.weatherLocationSaved")}${updated ? ` (${updated}${accuracy})` : ""}`;
}

async function useBrowserWeatherLocation() {
  if (!navigator.geolocation) {
    renderWeatherLocationStatus(t("settings.weatherLocationUnavailable"));
    return;
  }
  if (els.weatherLocationUse) els.weatherLocationUse.disabled = true;
  renderWeatherLocationStatus(state.language === "en" ? "Requesting location permission..." : "位置情報の許可を確認しています...");
  try {
    const position = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 12000,
        maximumAge: 600000,
      });
    });
    state.weatherLocation = saveWeatherLocation({
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy,
      updatedAt: new Date().toISOString(),
    });
    renderWeatherLocationStatus();
  } catch {
    renderWeatherLocationStatus(t("settings.weatherLocationDenied"));
  } finally {
    if (els.weatherLocationUse) els.weatherLocationUse.disabled = false;
  }
}

function sessionsForTrainingScope(scope) {
  return window.GEMMA_TRAINING.sessionsForTrainingScope({
    scope,
    sessions: state.sessions,
    activeFolderId: state.activeFolderId,
    activeSessionId: state.activeId,
  });
}

function folderNameForSession(session) {
  const folder = state.folders.find((item) => item.id === session.folderId);
  return folder?.name || "";
}

function cleanTrainingContent(message) {
  return window.GEMMA_TRAINING.cleanTrainingContent(message);
}

function buildTrainingExamples(scope) {
  if (scope === "set") return buildTrainingExamplesFromSet(activeTrainingSet());
  return window.GEMMA_TRAINING.buildTrainingExamplesFromSessions({
    sessions: sessionsForTrainingScope(scope),
    scope,
    systemPrompt: SYSTEM_PROMPTS[state.language] || SYSTEM_PROMPTS.ja,
    language: state.language,
    folderNameForSession,
    nowIso: () => new Date().toISOString(),
  });
}

function buildTrainingExamplesFromSet(set) {
  return window.GEMMA_TRAINING.buildTrainingExamplesFromSet({
    set,
    systemPrompt: SYSTEM_PROMPTS[state.language] || SYSTEM_PROMPTS.ja,
    nowIso: () => new Date().toISOString(),
  });
}

function activeTrainingSet() {
  return window.GEMMA_TRAINING?.activeTrainingSet?.(state.trainingSets, state.activeTrainingSetId) || null;
}

function createTrainingSet(name) {
  const result = window.GEMMA_TRAINING.createAndSelectTrainingSet({
    sets: state.trainingSets,
    name,
    defaultName: t("settings.trainingSetDefault"),
    createId: () => crypto.randomUUID(),
    now: () => Date.now(),
  });
  const set = window.GEMMA_TRAINING.applyCreatedTrainingSet(state, result);
  saveTrainingSets();
  renderTrainingSetControls();
  return set;
}

function setActiveTrainingSet(id) {
  window.GEMMA_TRAINING.applyTrainingSetSelection(state, id);
  saveTrainingSets();
  renderTrainingSetControls();
}

function renameActiveTrainingSet() {
  const set = activeTrainingSet();
  if (!set) return;
  const nextName = window.prompt(t("settings.trainingSetRenamePrompt"), set.name);
  const renamed = window.GEMMA_TRAINING.renameTrainingSet({
    set,
    name: nextName,
    now: () => Date.now(),
  });
  if (!renamed) return;
  saveTrainingSets();
  renderTrainingSetControls();
  render();
  if (els.trainingStatus) {
    els.trainingStatus.textContent = t("settings.trainingSetRenamed", { name: set.name });
  }
}

function deleteActiveTrainingSet() {
  const set = activeTrainingSet();
  if (!set) return;
  const ok = window.confirm(t("settings.trainingSetDeleteConfirm", { name: set.name }));
  if (!ok) return;
  const result = window.GEMMA_TRAINING.deleteTrainingSetAndSelectNext({
    sets: state.trainingSets,
    folders: state.folders,
    id: set.id,
  });
  const deletedName = window.GEMMA_TRAINING.applyDeletedTrainingSet(state, result);
  saveTrainingSets();
  saveFolders();
  renderTrainingSetControls();
  render();
  if (els.trainingStatus) {
    els.trainingStatus.textContent = t("settings.trainingSetDeleted", { name: deletedName });
  }
}

function applyTrainingSetToActiveFolder(id) {
  const folder = activeFolder();
  const applied = window.GEMMA_TRAINING.setFolderTrainingSet({ folder, trainingSetId: id });
  if (!applied) return;
  saveFolders();
  renderTrainingSetControls();
  const set = window.GEMMA_TRAINING?.trainingSetById?.(state.trainingSets, id);
  if (els.trainingStatus) {
    els.trainingStatus.textContent = set
      ? t("training.applied", { name: set.name })
      : t("settings.trainingSetNone");
  }
}

function correctionTrainingSetForActiveFolder() {
  const folder = activeFolder();
  let set = activeFolderTrainingSet();
  if (set) return set;
  set = activeTrainingSet();
  if (set && folder) {
    folder.trainingSetId = set.id;
    saveFolders();
  }
  return set;
}

function renderTrainingSetOptions(select, value, includeNone = false) {
  renderTrainingSetOptionsView({
    select,
    sets: state.trainingSets,
    value,
    includeNone,
    t,
  });
}

function renderTrainingSetControls() {
  ensureTrainingSets();
  const activeSet = activeTrainingSet();
  if (activeSet && !state.activeTrainingSetId) {
    state.activeTrainingSetId = activeSet.id;
    saveTrainingSets();
  }
  renderTrainingControlsView({
    els,
    sets: state.trainingSets,
    activeSet,
    activeTrainingSetId: state.activeTrainingSetId,
    folderTrainingSetId: activeFolder()?.trainingSetId || "",
    folders: state.folders,
    t,
  });
}

function flashSavedButton(button, label = t("common.saved")) {
  if (!button) return;
  const originalText = button.textContent;
  button.classList.add("saved-flash");
  button.textContent = label || "保存しました";
  button.disabled = true;
  window.setTimeout(() => {
    button.textContent = originalText;
    button.classList.remove("saved-flash");
    button.disabled = false;
  }, 1200);
}

function saveTrainingExampleEdit(exampleId, button = null) {
  const set = activeTrainingSet();
  if (!set) return;
  const textarea = els.trainingExampleList?.querySelector(`textarea[data-example-id="${CSS.escape(exampleId)}"]`);
  if (!textarea) return;
  const updated = window.GEMMA_TRAINING.updateTrainingExample({
    set,
    exampleId,
    assistant: textarea.value,
    nowIso: () => new Date().toISOString(),
    now: () => Date.now(),
  });
  if (!updated) return;
  saveTrainingSets();
  flashSavedButton(button);
  window.setTimeout(renderTrainingSetControls, 450);
  if (els.trainingStatus) els.trainingStatus.textContent = t("settings.trainingExampleSaved");
}

function addCorrectionToTrainingSet(messageIndex) {
  const session = activeSession();
  const correction = window.GEMMA_TRAINING.correctionDraftFromMessage({
    session,
    messageIndex,
    cleanContent: cleanTrainingContent,
  });
  if (!correction) return;
  let set = correctionTrainingSetForActiveFolder();
  if (!set) {
    const ok = window.confirm(`${t("training.noSet")}\n${t("settings.trainingSetCreate")} ?`);
    if (!ok) return;
    set = createTrainingSet(t("settings.trainingSetDefault"));
    const folder = activeFolder();
    if (folder) {
      folder.trainingSetId = set.id;
      saveFolders();
    }
  }
  state.correctionDraft = {
    ...correction.draft,
    setId: set.id,
  };
  window.GEMMA_TRAINING.openCorrectionDialog({
    els,
    sets: state.trainingSets,
    set,
    draft: state.correctionDraft,
    assistantContent: correction.assistantContent,
    t,
  });
}

function closeCorrectionDialog() {
  state.correctionDraft = null;
  window.GEMMA_TRAINING.closeCorrectionDialog({ els });
}

function saveCorrectionDraft() {
  const draft = state.correctionDraft;
  if (!draft) return;
  const corrected = els.correctionText.value.trim();
  if (!corrected) return;
  const selectedSetId = els.correctionTrainingSet?.value || draft.setId;
  const result = window.GEMMA_TRAINING.saveCorrectionToSet({
    sets: state.trainingSets,
    selectedSetId,
    draft,
    assistant: corrected,
    defaultName: t("settings.trainingSetDefault"),
    createId: () => crypto.randomUUID(),
    nowIso: () => new Date().toISOString(),
    now: () => Date.now(),
  });
  if (!result) return;
  const set = window.GEMMA_TRAINING.applyCorrectionSaveResult(state, result);
  saveTrainingSets();
  renderTrainingSetControls();
  if (els.trainingStatus) els.trainingStatus.textContent = t("training.saved", { name: set.name });
  closeCorrectionDialog();
}

function activeFolderTrainingSet() {
  const id = activeFolder()?.trainingSetId || "";
  return window.GEMMA_TRAINING?.trainingSetById?.(state.trainingSets, id) || null;
}

function trainingContextSystemPrompt() {
  return window.GEMMA_TRAINING.buildTrainingContextPrompt({
    set: activeFolderTrainingSet(),
    t,
    textSnippet,
  });
}

function activeCharacterMemorySet() {
  return window.GEMMA_CHARACTER?.activeMemorySet?.(state.characterMemorySets, state.character) || null;
}

function characterContextSystemPrompt() {
  const characterPrompt = window.GEMMA_CHARACTER?.buildCharacterSystemPrompt?.(state.character) || "";
  const memoryPrompt = state.character?.memoryMode === "off"
    ? ""
    : (window.GEMMA_CHARACTER?.buildMemorySystemPrompt?.(activeCharacterMemorySet()) || "");
  return `${characterPrompt}${memoryPrompt}`;
}

function installedStudyPacks() {
  return window.GEMMA_MANAGEMENT?.installedStudyPackDefinitions?.(state.studyPacks) || [];
}

function selectedStudyPackMode() {
  const [packId, modeId] = String(state.selectedStudyPackMode || "").split(":");
  if (!packId || !modeId) return null;
  const pack = window.GEMMA_MANAGEMENT?.studyPackById?.(packId);
  const mode = pack?.modes?.find((item) => item.id === modeId);
  if (!pack || !mode || !state.studyPacks?.[pack.id]?.installed) return null;
  return { pack, mode };
}

function selectedStudyPackModes() {
  const values = Array.isArray(state.selectedStudyPackModes) ? state.selectedStudyPackModes : [];
  return values.map((value) => {
    const [packId, modeId] = String(value || "").split(":");
    if (!packId || !modeId) return null;
    const pack = window.GEMMA_MANAGEMENT?.studyPackById?.(packId);
    const mode = pack?.modes?.find((item) => item.id === modeId);
    if (!pack || !mode || !state.studyPacks?.[pack.id]?.installed) return null;
    return { pack, mode, value };
  }).filter(Boolean);
}

function studyPackModeDisplayLabel(selected = selectedStudyPackMode()) {
  if (!selected) return "";
  return t(selected.mode.shortKey) || t(selected.mode.nameKey) || selected.mode.id;
}

function studyPackModesDisplayLabel(selectedItems = selectedStudyPackModes()) {
  if (!selectedItems.length) return "";
  if (selectedItems.length === 1) return studyPackModeDisplayLabel(selectedItems[0]);
  return `教材パック ${selectedItems.length}件`;
}

function studyPackModeOutputPrompt(selected) {
  const modeId = selected?.mode?.id || "";
  if (modeId === "logic-gap-check") {
    return "出力は「気になる点」「直し方」「必要なら修正版」の順にしてください。指摘だけで十分な場合は、無理に全文を書き換えないでください。ファイル保存やダウンロード案内は、ユーザーが明示しない限り行わないでください。";
  }
  if (modeId === "reduce-ai-tone") {
    return "出力はまず「修正版:」として、対象本文そのものを自然な日本語に書き換えてください。ユーザーの依頼文をプロンプト化したり、AI向け指示に変換したりしないでください。必要な場合だけ、最後に「変更点:」を2〜3個添えてください。ファイル保存やダウンロード案内は、ユーザーが明示しない限り行わないでください。";
  }
  if (modeId === "make-readable" || modeId === "report-style") {
    return "出力はまず「修正版:」として、対象本文そのものを書き換えてください。必要な場合だけ、最後に「変更点:」を2〜3個添えてください。ファイル保存やダウンロード案内は、ユーザーが明示しない限り行わないでください。";
  }
  return "出力は、ユーザーの依頼に合わせてチャット内に返してください。ファイル保存やダウンロード案内は、ユーザーが明示しない限り行わないでください。";
}

function studyPackModeExamplePrompt(selected) {
  const examples = Array.isArray(selected?.mode?.examples) ? selected.mode.examples : [];
  const lines = examples.slice(0, 2).map((example, index) => {
    const input = String(example?.input || "").trim();
    const output = String(example?.output || "").trim();
    if (!input || !output) return "";
    return `例${index + 1}:\n入力: ${input}\n出力: ${output}`;
  }).filter(Boolean);
  if (!lines.length) return "";
  return `良い出力例です。内容をコピーせず、形式と粒度だけ参考にしてください。\n${lines.join("\n")}\n`;
}

function studyPackContextSystemPrompt() {
  const selectedItems = selectedStudyPackModes();
  const selected = selectedItems[0] || selectedStudyPackMode();
  const packs = installedStudyPacks().filter((pack) => pack.modes?.length);
  if (selectedItems.length === 0 && !selected && packs.length === 0) return "";
  const names = packs.map((pack) => t(pack.nameKey) || pack.id).join("、");
  const activeLine = names ? `\n有効な教材パック: ${names}\n` : "";
  if (selectedItems.length === 0 && !selected) {
    return `${activeLine}ユーザーが文章添削、論理チェック、レポート改善を求めた場合だけ、教材パックの考え方を参考にしてください。教材パック本体は書き換えず、ユーザーの修正は学習セットに保存します。\n`;
  }
  const selectedForPrompt = selectedItems.length > 0 ? selectedItems : [selected];
  const modePrompts = selectedForPrompt.map((item, index) => {
    const packName = t(item.pack.nameKey) || item.pack.id;
    const modeName = t(item.mode.nameKey) || item.mode.id;
    return `教材${index + 1}: ${packName} / ${modeName}\n指示: ${item.mode.prompt}\n${studyPackModeOutputPrompt(item)}\n${studyPackModeExamplePrompt(item)}`;
  }).join("\n---\n");
  return `${activeLine}選択された教材パックのモードを次の回答に使います。\n${modePrompts}複数の教材が選択されている場合は、矛盾しない範囲で統合し、最終回答を1つにまとめてください。教材パック本体は書き換えません。\n`;
}

function renderCharacterPanel() {
  if (els.characterName) els.characterName.value = state.character?.name || "Gemma";
  if (els.characterUserName) els.characterUserName.value = state.character?.userName || "";
  if (els.characterSelfName) els.characterSelfName.value = state.character?.selfName || "";
  if (els.characterGender) els.characterGender.value = state.character?.gender || "unspecified";
  if (els.characterAvatar) els.characterAvatar.value = state.character?.avatar || "";
  renderCharacterPreview();
  if (els.characterTone) els.characterTone.value = state.character?.tonePreset || "friendly";
  if (els.characterMemoryMode) els.characterMemoryMode.value = state.character?.memoryMode || "suggest";
  els.characterMemoryModeChoices?.forEach((input) => {
    input.checked = input.value === (state.character?.memoryMode || "suggest");
  });
  if (els.characterPersonality) els.characterPersonality.value = state.character?.personality || "";
  if (els.characterSystemAddon) els.characterSystemAddon.value = state.character?.systemPromptAddon || "";
  if (els.characterMemorySearch) els.characterMemorySearch.value = state.characterMemoryQuery || "";
  renderCharacterMemoryList();
}

function renderAvatarElement(target, { large = false } = {}) {
  if (!target) return;
  const src = state.character?.avatar || "";
  target.innerHTML = "";
  if (src) {
    const image = document.createElement("img");
    image.src = src;
    image.alt = "";
    target.append(image);
  } else {
    target.textContent = String(state.character?.name || "G").trim().slice(0, large ? 3 : 2).toUpperCase();
  }
}

function renderCharacterPreview() {
  renderAvatarElement(els.characterAvatarPreview);
  renderAvatarElement(els.characterChatPreviewAvatar, { large: true });
  const name = state.character?.name || "Gemma";
  if (els.characterChatPreviewName) els.characterChatPreviewName.textContent = name;
  if (els.characterChatPreviewText) {
    els.characterChatPreviewText.textContent = characterPreviewText();
  }
}

function characterPreviewText() {
  const userName = String(state.character?.userName || "").trim();
  const selfName = String(state.character?.selfName || "").trim();
  if (userName && selfName) return `${userName}、${selfName}が手伝うね。`;
  if (userName) return `${userName}、今日は何を手伝おうか？`;
  if (selfName) return `${selfName}が手伝うね。`;
  return "今日は何を手伝おうか？";
}

function characterAddressPrefix() {
  const userName = String(state.character?.userName || "").trim();
  return userName ? `${userName}、` : "";
}

function characterSelfLabel() {
  return String(state.character?.selfName || state.character?.name || "").trim();
}

function characterizeToolAnswer(answer, { type = "" } = {}) {
  const text = String(answer || "").trim();
  if (!text) return "";
  const address = characterAddressPrefix();
  const selfLabel = characterSelfLabel();
  if (type === "weather") {
    const intro = `${address}${selfLabel ? `${selfLabel}が` : ""}いまの天気を調べたよ。`;
    return `${intro}\n${text}`;
  }
  return address ? `${address}${text}` : text;
}

function characterMemoryCategories() {
  return [
    { id: "all", label: t("character.memoryCategoryAll") },
    { id: "profile", label: t("character.memoryCategoryProfile") },
    { id: "preference", label: t("character.memoryCategoryPreference") },
    { id: "study", label: t("character.memoryCategoryStudy") },
    { id: "settings", label: t("character.memoryCategorySettings") },
  ];
}

function classifyCharacterMemory(memory) {
  return window.GEMMA_CHARACTER?.classifyMemory?.(memory) || "profile";
}

function renderCharacterMemoryFilters(memories) {
  if (!els.characterMemoryFilters) return;
  const counts = memories.reduce((acc, memory) => {
    const category = classifyCharacterMemory(memory);
    acc[category] = (acc[category] || 0) + 1;
    acc.all += 1;
    return acc;
  }, { all: 0, profile: 0, preference: 0, study: 0, settings: 0 });
  els.characterMemoryFilters.innerHTML = characterMemoryCategories().map((category) => `
    <button
      class="memory-filter${state.characterMemoryFilter === category.id ? " active" : ""}"
      type="button"
      data-memory-filter="${escapeHtml(category.id)}"
      aria-pressed="${state.characterMemoryFilter === category.id ? "true" : "false"}"
    >${escapeHtml(category.label)} <span>${counts[category.id] || 0}</span></button>
  `).join("");
}

function saveCharacterSettings() {
  const checkedMemoryMode = [...(els.characterMemoryModeChoices || [])].find((input) => input.checked)?.value || "";
  state.character = window.GEMMA_CHARACTER?.normalizeCharacter?.({
    ...state.character,
    name: els.characterName?.value || "Gemma",
    userName: els.characterUserName?.value || "",
    selfName: els.characterSelfName?.value || "",
    gender: els.characterGender?.value || "unspecified",
    avatar: els.characterAvatar?.value || "",
    tonePreset: els.characterTone?.value || "friendly",
    memoryMode: checkedMemoryMode || els.characterMemoryMode?.value || "suggest",
    personality: els.characterPersonality?.value || "",
    systemPromptAddon: els.characterSystemAddon?.value || "",
  }) || state.character;
  saveCharacterState();
  renderCharacterPanel();
  renderMessages();
  flashSavedButton(els.characterSave);
  if (els.trainingStatus) els.trainingStatus.textContent = t("character.saved");
}

function pickCharacterAvatarFile() {
  els.characterAvatarFile?.click();
}

function clearCharacterAvatar() {
  state.character = window.GEMMA_CHARACTER?.normalizeCharacter?.({
    ...state.character,
    avatar: "",
  }) || state.character;
  if (els.characterAvatar) els.characterAvatar.value = "";
  if (els.characterAvatarFile) els.characterAvatarFile.value = "";
  saveCharacterState();
  renderCharacterPanel();
  renderMessages();
}

function handleCharacterAvatarFileChange() {
  const file = els.characterAvatarFile?.files?.[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    window.alert(t("character.avatarTooLarge"));
    els.characterAvatarFile.value = "";
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    const result = String(reader.result || "");
    if (!result.startsWith("data:image/")) return;
    state.character = window.GEMMA_CHARACTER?.normalizeCharacter?.({
      ...state.character,
      avatar: result,
    }) || state.character;
    if (els.characterAvatar) els.characterAvatar.value = result;
    saveCharacterState();
    renderCharacterPanel();
    renderMessages();
  });
  reader.readAsDataURL(file);
}

function renderCharacterMemoryList() {
  if (!els.characterMemoryList) return;
  const set = activeCharacterMemorySet();
  const memories = set?.memories || [];
  renderCharacterMemoryFilters(memories);
  if (!memories.length) {
    els.characterMemoryList.innerHTML = `<div class="management-note">${escapeHtml(t("character.memoryEmpty"))}</div>`;
    return;
  }
  const query = (state.characterMemoryQuery || "").trim().toLowerCase();
  const visibleMemories = memories.filter((memory) => {
    const categoryMatches = state.characterMemoryFilter === "all" || classifyCharacterMemory(memory) === state.characterMemoryFilter;
    const queryMatches = !query || `${memory?.text || ""} ${(memory?.tags || []).join(" ")}`.toLowerCase().includes(query);
    return categoryMatches && queryMatches;
  });
  if (!visibleMemories.length) {
    els.characterMemoryList.innerHTML = `<div class="management-note">${escapeHtml(t("character.memoryEmptyFiltered"))}</div>`;
    return;
  }
  els.characterMemoryList.innerHTML = visibleMemories.map((memory, index) => {
    const category = characterMemoryCategories().find((item) => item.id === classifyCharacterMemory(memory));
    return `
    <div class="character-memory-item" data-memory-id="${escapeHtml(memory.id)}">
      <div class="character-memory-summary">
        <div>
          <strong>${index + 1}. ${escapeHtml(state.character?.name || "Gemma")}${escapeHtml(t("character.memorySuffix"))}</strong>
          <p>${escapeHtml(memory.text)}</p>
        </div>
        <div class="character-memory-actions">
          <button class="ghost-button" type="button" data-memory-edit="${escapeHtml(memory.id)}">${escapeHtml(t("common.edit"))}</button>
          <button class="ghost-button" type="button" data-memory-delete="${escapeHtml(memory.id)}">${escapeHtml(t("character.forgetMemory"))}</button>
        </div>
      </div>
      <div class="character-memory-meta">
        <span class="memory-tag">${escapeHtml(category?.label || t("character.memoryTagGeneral"))}</span>
        <span>${escapeHtml(t("character.memorySource"))}: ${escapeHtml(memory.sourceSessionId ? t("character.memorySourceChat") : t("character.memorySourceManual"))}</span>
      </div>
      <div class="character-memory-edit" hidden>
        <textarea rows="2">${escapeHtml(memory.text)}</textarea>
        <div class="character-memory-actions">
          <button class="ghost-button" type="button" data-memory-cancel="${escapeHtml(memory.id)}">${escapeHtml(t("common.cancel"))}</button>
          <button class="ghost-button" type="button" data-memory-save="${escapeHtml(memory.id)}">${escapeHtml(t("common.save"))}</button>
        </div>
      </div>
    </div>
  `;
  }).join("");
}

function addManualCharacterMemory() {
  const text = els.characterMemoryNew?.value || "";
  if (!text.trim()) return;
  state.characterMemorySets = window.GEMMA_CHARACTER?.addMemory?.({
    memorySets: state.characterMemorySets,
    character: state.character,
    text,
    sourceSessionId: activeSession()?.id || "",
    sourceFolderId: activeFolder()?.id || "",
    createId: () => crypto.randomUUID(),
    nowIso: () => new Date().toISOString(),
  }) || state.characterMemorySets;
  if (els.characterMemoryNew) els.characterMemoryNew.value = "";
  flashSavedButton(els.characterMemoryAdd);
  renderCharacterMemoryList();
  if (els.trainingStatus) els.trainingStatus.textContent = t("character.memorySaved");
}

function saveCharacterMemoryEdit(memoryId, button = null) {
  const set = activeCharacterMemorySet();
  const item = [...(els.characterMemoryList?.querySelectorAll("[data-memory-id]") || [])]
    .find((element) => element.dataset.memoryId === memoryId);
  const text = item?.querySelector("textarea")?.value || "";
  if (!set || !text.trim()) return;
  state.characterMemorySets = window.GEMMA_CHARACTER?.updateMemory?.({
    memorySets: state.characterMemorySets,
    memorySetId: set.id,
    memoryId,
    text,
    nowIso: () => new Date().toISOString(),
  }) || state.characterMemorySets;
  flashSavedButton(button);
  window.setTimeout(renderCharacterMemoryList, 450);
  if (els.trainingStatus) els.trainingStatus.textContent = t("character.memoryUpdated");
}

function deleteCharacterMemory(memoryId) {
  const set = activeCharacterMemorySet();
  if (!set) return;
  state.characterMemorySets = window.GEMMA_CHARACTER?.deleteMemory?.({
    memorySets: state.characterMemorySets,
    memorySetId: set.id,
    memoryId,
  }) || state.characterMemorySets;
  renderCharacterMemoryList();
  if (els.trainingStatus) els.trainingStatus.textContent = t("character.memoryDeleted");
}

function openMemoryCandidate(candidate) {
  if (!candidate || state.character?.memoryMode === "off") return;
  const memoryMode = state.character?.memoryMode || "suggest";
  const text = String(candidate.text || "").trim();
  const unsafe = window.GEMMA_CHARACTER?.isSensitiveMemoryText?.(text);
  if (memoryMode === "auto" && text && !unsafe) {
    state.characterMemorySets = window.GEMMA_CHARACTER?.addMemory?.({
      memorySets: state.characterMemorySets,
      character: state.character,
      text,
      sourceSessionId: activeSession()?.id || "",
      sourceFolderId: activeFolder()?.id || "",
      createId: () => crypto.randomUUID(),
      nowIso: () => new Date().toISOString(),
    }) || state.characterMemorySets;
    renderCharacterMemoryList();
    if (els.trainingStatus) els.trainingStatus.textContent = t("character.memoryAutoSaved");
    return;
  }
  state.memoryCandidate = {
    ...candidate,
    sourceSessionId: activeSession()?.id || "",
    sourceFolderId: activeFolder()?.id || "",
  };
  if (els.memoryCandidateText) els.memoryCandidateText.value = candidate.text || "";
  renderMessages();
}

function editMemoryCandidate() {
  if (!state.memoryCandidate) return;
  if (els.memoryCandidateText) els.memoryCandidateText.value = state.memoryCandidate.text || "";
  if (els.memoryCandidateModal) els.memoryCandidateModal.hidden = false;
}

function closeMemoryCandidate() {
  state.memoryCandidate = null;
  if (els.memoryCandidateText) els.memoryCandidateText.value = "";
  if (els.memoryCandidateModal) els.memoryCandidateModal.hidden = true;
}

function saveMemoryCandidate(textOverride = "") {
  const text = textOverride || els.memoryCandidateText?.value || "";
  if (!state.memoryCandidate || !text.trim()) return;
  state.characterMemorySets = window.GEMMA_CHARACTER?.addMemory?.({
    memorySets: state.characterMemorySets,
    character: state.character,
    text,
    sourceSessionId: state.memoryCandidate.sourceSessionId || "",
    sourceFolderId: state.memoryCandidate.sourceFolderId || "",
    createId: () => crypto.randomUUID(),
    nowIso: () => new Date().toISOString(),
  }) || state.characterMemorySets;
  closeMemoryCandidate();
  renderCharacterMemoryList();
  renderMessages();
}

function exportTrainingData() {
  const scope = els.trainingExportScope?.value || "active";
  const examples = buildTrainingExamples(scope);
  const trainingExport = window.GEMMA_TRAINING.createTrainingExport({
    scope,
    examples,
    activeSet: activeTrainingSet(),
    activeFolder: activeFolder(),
    activeSession: activeSession(),
    slugForFilename,
    timestampForFilename,
  });
  if (!trainingExport) {
    if (els.trainingStatus) els.trainingStatus.textContent = t("settings.trainingStatusEmpty");
    return;
  }
  downloadTextFile(trainingExport.filename, trainingExport.jsonl);
  if (els.trainingStatus) {
    els.trainingStatus.textContent = t("settings.trainingStatusDoneNext", {
      count: trainingExport.count,
      name: trainingExport.filename,
    });
  }
}

function setEnterToSend(enabled) {
  state.enterToSend = Boolean(enabled);
  localStorage.setItem("gemma4.enterToSend", String(state.enterToSend));
  if (els.enterToSend) els.enterToSend.checked = state.enterToSend;
}

function openFolderEditor(folder) {
  Object.assign(state, window.GEMMA_SIDEBAR.selectFolderInState({
    state,
    folderId: folder.id,
    openWorkspace: true,
  }));
  syncWorkspaceFromActiveFolder();
  saveFolders();
  render();
  if (state.workspaceRoot) loadWorkspace();
  requestAnimationFrame(() => els.workspaceFolderTitle?.focus());
}

function saveActiveFolderTitle() {
  const folder = activeFolder();
  if (!folder) return;
  const rename = window.GEMMA_SIDEBAR.renameFolderInState({
    state,
    folderId: folder.id,
    value: els.workspaceFolderTitle.value,
  });
  if (!rename.changed) {
    els.workspaceFolderTitle.value = folder.name;
    return;
  }
  state.editingFolderId = rename.editingFolderId;
  state.folders = rename.folders;
  saveFolders();
  render();
}

function applyCodegraphToActiveFolder(enabled) {
  const folder = activeFolder();
  if (!folder) return;
  folder.plugins = folder.plugins && typeof folder.plugins === "object" && !Array.isArray(folder.plugins)
    ? folder.plugins
    : {};
  folder.plugins.codegraph = folder.plugins.codegraph && typeof folder.plugins.codegraph === "object" && !Array.isArray(folder.plugins.codegraph)
    ? folder.plugins.codegraph
    : {};
  folder.plugins.codegraph.enabled = Boolean(enabled);
  folder.plugins.codegraph.status = enabled
    ? folder.plugins.codegraph.status && folder.plugins.codegraph.status !== "off"
      ? folder.plugins.codegraph.status
      : "not-ready"
    : "off";
  saveFolders();
  render();
}

async function prepareCodegraphForActiveFolder() {
  const folder = activeFolder();
  if (!folder || !state.workspaceRoot) return;
  folder.plugins = folder.plugins && typeof folder.plugins === "object" && !Array.isArray(folder.plugins)
    ? folder.plugins
    : {};
  folder.plugins.codegraph = folder.plugins.codegraph && typeof folder.plugins.codegraph === "object" && !Array.isArray(folder.plugins.codegraph)
    ? folder.plugins.codegraph
    : {};
  folder.plugins.codegraph.enabled = true;
  folder.plugins.codegraph.status = "running";
  folder.plugins.codegraph.error = "";
  saveFolders();
  render();
  try {
    const data = await window.GEMMA_WORKSPACE.prepareCodegraph({ root: state.workspaceRoot });
    const stats = data.summary?.stats || {};
    folder.plugins.codegraph.status = "ready";
    folder.plugins.codegraph.files = Number(stats.files) || 0;
    folder.plugins.codegraph.skipped = Number(stats.skipped) || 0;
    folder.plugins.codegraph.path = data.path || ".codegraph/summary.json";
    folder.plugins.codegraph.storage = data.storage || "workspace";
    folder.plugins.codegraph.summary = data.summary || null;
    folder.plugins.codegraph.indexedAt = data.summary?.generatedAt || new Date().toISOString();
  } catch (error) {
    folder.plugins.codegraph.status = "error";
    folder.plugins.codegraph.error = error.message || "原因不明のエラーです。アプリを再起動してもう一度お試しください。";
  }
  saveFolders();
  render();
}

function showUndo(kind, label) {
  const target = kind === "folder" ? t("sidebar.folderButton") : t("task.chat");
  els.undoText.textContent = t("undo.deleted", { target, label });
  els.undoToast.hidden = false;
}

function hideUndo() {
  els.undoToast.hidden = true;
}

function restoreLastDeleted() {
  const restored = window.GEMMA_SIDEBAR.restoreDeletedToState({ state });
  if (!restored) return;
  const {
    shouldLoadWorkspace,
    shouldSaveFolders,
    shouldSaveSessions,
    shouldSyncWorkspace,
    ...nextState
  } = restored;
  Object.assign(state, nextState);
  if (shouldSyncWorkspace) {
    syncWorkspaceFromActiveFolder();
  }
  if (shouldSaveFolders) {
    saveFolders();
  }
  if (shouldSaveSessions) {
    saveSessions();
  }
  if (shouldLoadWorkspace && state.workspaceRoot) {
    loadWorkspace();
  }
  hideUndo();
  render();
}

function commitFolderRename(folder, value) {
  const rename = window.GEMMA_SIDEBAR.renameFolderInState({ state, folderId: folder.id, value });
  state.editingFolderId = rename.editingFolderId;
  state.folders = rename.folders;
  if (rename.changed) {
    saveFolders();
  }
  render();
}

function commitSessionRename(session, value) {
  const rename = window.GEMMA_SIDEBAR.renameSessionInState({ state, sessionId: session.id, value });
  state.editingSessionId = rename.editingSessionId;
  state.sessions = rename.sessions;
  if (rename.changed) {
    saveSessions();
  }
  render();
}

function startFolderRename(folder) {
  openFolderEditor(folder);
}

function startSessionRename(session) {
  Object.assign(state, window.GEMMA_SIDEBAR.startSessionRenameInState({ sessionId: session.id }));
  render();
  requestAnimationFrame(() => {
    const input = document.querySelector(`[data-session-edit="${session.id}"]`);
    input?.focus();
    input?.select();
  });
}

function deleteFolder(folder) {
  const count = state.sessions.filter((session) => session.folderId === folder.id).length;
  const ok = window.confirm(t("folder.deleteConfirm", { name: folder.name, count }));
  if (!ok) return;
  Object.assign(state, window.GEMMA_SIDEBAR.deleteFolderFromState({ state, folder }));
  syncWorkspaceFromActiveFolder();
  selectFirstSessionInActiveFolder();
  saveFolders();
  saveSessions();
  render();
  showUndo("folder", folder.name);
  if (state.workspaceRoot) loadWorkspace();
}

function deleteSession(session) {
  const ok = window.confirm(t("chat.deleteConfirm", { name: session.title }));
  if (!ok) return;
  const deletion = window.GEMMA_SIDEBAR.deleteSessionFromState({ state, session });
  state.lastDeleted = deletion.lastDeleted;
  state.sessions = deletion.sessions;
  if (deletion.shouldSelectFirstSession) {
    selectFirstSessionInActiveFolder();
  }
  saveSessions();
  render();
  showUndo("session", session.title);
}

function newSession(folderId = state.activeFolderId) {
  const sessionState = window.GEMMA_SIDEBAR.createSessionInState({
    state,
    folderId,
    folderName: t("folder.new"),
    sessionTitle: t("chat.new"),
    createId: () => crypto.randomUUID(),
    now: () => Date.now(),
  });
  state.folders = sessionState.folders;
  state.sessions = sessionState.sessions;
  state.activeFolderId = sessionState.activeFolderId;
  state.activeId = sessionState.activeId;
  syncWorkspaceFromActiveFolder();
  saveSessions();
  saveFolders();
  render();
}

function importMobileChatJson() {
  let payload = null;
  try {
    payload = JSON.parse(els.mobileImportJson?.value || "{}");
  } catch {
    if (els.mobileImportPreview) els.mobileImportPreview.textContent = t("management.mobileImportInvalidJson");
    return;
  }
  if (!state.activeFolderId && state.folders.length === 0) {
    createFolder(t("folder.default"));
  }
  if (!state.activeFolderId && state.folders.length > 0) {
    state.activeFolderId = state.folders[0].id;
    saveFolders();
  }
  const result = window.GEMMA_MANAGEMENT?.mobileImportPayloadToSession?.({
    payload,
    folderId: state.activeFolderId,
    createId: () => crypto.randomUUID(),
    now: () => Date.now(),
  });
  if (!result?.ok || !result.session) {
    if (els.mobileImportPreview) els.mobileImportPreview.textContent = t("management.mobileImportInvalid");
    return;
  }
  state.sessions = [result.session, ...state.sessions];
  state.activeId = result.session.id;
  saveSessions();
  render();
  if (els.mobileImportPreview) {
    els.mobileImportPreview.textContent = t("management.mobileImportApplied", {
      count: result.summary?.total || result.session.messages.length,
    });
  }
}

async function importPendingMobileChats() {
  if (els.mobileImportPreview) els.mobileImportPreview.textContent = t("management.mobileImportPendingLoading");
  try {
    const response = await fetch("/api/mobile/imports");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const imports = Array.isArray(data.imports) ? data.imports : [];
    if (imports.length === 0) {
      if (els.mobileImportPreview) els.mobileImportPreview.textContent = t("management.mobileImportPendingEmpty");
      return;
    }
    if (!state.activeFolderId && state.folders.length === 0) {
      createFolder(t("folder.default"));
    }
    if (!state.activeFolderId && state.folders.length > 0) {
      state.activeFolderId = state.folders[0].id;
      saveFolders();
    }
    const importedSessions = [];
    const importedIds = [];
    for (const item of imports) {
      const result = window.GEMMA_MANAGEMENT?.mobileImportPayloadToSession?.({
        payload: item.payload,
        folderId: state.activeFolderId,
        createId: () => crypto.randomUUID(),
        now: () => Date.now(),
      });
      if (result?.ok && result.session) {
        importedSessions.push(result.session);
        importedIds.push(item.id);
      }
    }
    if (importedSessions.length === 0) {
      if (els.mobileImportPreview) els.mobileImportPreview.textContent = t("management.mobileImportInvalid");
      return;
    }
    state.sessions = [...importedSessions, ...state.sessions];
    state.activeId = importedSessions[0].id;
    saveSessions();
    render();
    await fetch("/api/mobile/imports/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: importedIds }),
    });
    if (els.mobileImportPreview) {
      const count = importedSessions.reduce((total, session) => total + session.messages.length, 0);
      els.mobileImportPreview.textContent = t("management.mobileImportPendingApplied", {
        count,
      });
    }
  } catch (error) {
    if (els.mobileImportPreview) {
      els.mobileImportPreview.textContent = t("management.mobileImportPendingError", {
        error: error.message,
      });
    }
  }
}

function activeSession() {
  return state.sessions.find((session) => session.id === state.activeId && session.folderId === state.activeFolderId);
}

function renderFolders() {
  return window.GEMMA_SIDEBAR.renderFolders({
    commitFolderRename,
    commitSessionRename,
    deleteFolder,
    deleteSession,
    els,
    loadWorkspace,
    newSession,
    render,
    saveCollapsedFolders,
    saveFolders,
    selectFirstSessionInActiveFolder,
    startFolderRename,
    startSessionRename,
    state,
    syncWorkspaceFromActiveFolder,
    t,
    sessionsForFolder,
  });
}

function renderMessages() {
  return window.GEMMA_MESSAGES.renderMessages({
    activeSession,
    addCorrectionToTrainingSet,
    closeMemoryCandidate,
    editMemoryCandidate,
    els,
    escapeHtml,
    formatDuration,
    modelForTask,
    openWorkspaceSource,
    saveMemoryCandidate,
    saveWorkspaceTranscript,
    state,
    t,
  });
}

function render() {
  document.body.dataset.theme = state.theme;
  window.GEMMA_SIDEBAR?.applySidebarLayout?.({ els, state, t });
  renderFolders();
  renderMessages();
  renderWorkspace();
  renderTrainingSetControls();
  if (els.characterPanel && !els.characterPanel.hidden) renderCharacterPanel();
  els.send.disabled = false;
  els.send.hidden = state.busy;
  els.stop.hidden = !state.busy;
  els.stop.disabled = !state.abortController;
  renderPendingImages();
  renderStudyPackModeRow();
  renderWebSearchToggle({ button: els.webSearchToggle, enabled: state.webSearch });
  els.progressLine.hidden = true;
}

function renderPendingImages() {
  renderPendingImagesView({
    state,
    els,
    t,
    onRemoveImage: (index) => {
      state.pendingImages.splice(index, 1);
      render();
    },
    onRemoveFile: (index) => {
      state.pendingFiles.splice(index, 1);
      render();
    },
  });
}

function renderStudyPackModeRow() {
  if (!els.studyPackModeRow) return;
  const packs = installedStudyPacks().filter((pack) => pack.modes?.length);
  els.studyPackModeRow.querySelectorAll(".study-pack-picker[open]").forEach((picker) => {
    picker.open = false;
  });
  els.studyPackModeRow.innerHTML = "";
  if (packs.length === 0) {
    state.selectedStudyPackMode = "";
    state.selectedStudyPackModes = [];
    els.studyPackModeRow.hidden = true;
    return;
  }
  const selectionModel = window.GEMMA_MANAGEMENT?.studyPackMultiSelectionModel?.({
    packs,
    selectedValues: state.selectedStudyPackModes,
    t,
  }) || { groups: [], selectedCount: 0, summaryLabel: t("studyPack.selectPack") };
  const validValues = new Set(selectionModel.groups.flatMap((group) => group.modes.map((mode) => mode.value)));
  state.selectedStudyPackModes = (state.selectedStudyPackModes || []).filter((value) => validValues.has(value));
  state.selectedStudyPackMode = state.selectedStudyPackModes[0] || "";

  const details = document.createElement("details");
  details.className = "study-pack-picker";
  const summary = document.createElement("summary");
  summary.className = "study-pack-picker-summary";
  const updatePickerSummary = () => {
    const count = state.selectedStudyPackModes?.length || 0;
    summary.textContent = count > 0
      ? t("studyPack.selectedCount", { count })
      : t("studyPack.selectPack");
    const clear = details.querySelector(".study-pack-picker-clear");
    if (clear) clear.disabled = count === 0;
  };
  updatePickerSummary();
  details.appendChild(summary);

  const panel = document.createElement("div");
  panel.className = "study-pack-picker-panel";
  const header = document.createElement("div");
  header.className = "study-pack-picker-header";
  const headerTitle = document.createElement("span");
  headerTitle.textContent = t("studyPack.menuLabel");
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "study-pack-picker-close";
  closeButton.setAttribute("aria-label", t("common.close"));
  closeButton.textContent = "×";
  closeButton.addEventListener("click", () => {
    details.open = false;
  });
  header.append(headerTitle, closeButton);
  panel.appendChild(header);
  selectionModel.groups.forEach((group) => {
    const groupEl = document.createElement("fieldset");
    groupEl.className = "study-pack-picker-group";
    const legend = document.createElement("legend");
    legend.textContent = group.label;
    groupEl.appendChild(legend);
    group.modes.forEach((mode) => {
      const item = document.createElement("label");
      item.className = "study-pack-picker-item";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = mode.value;
      checkbox.checked = mode.checked;
      const text = document.createElement("span");
      text.textContent = mode.label;
      checkbox.addEventListener("change", () => {
        state.selectedStudyPackModes = window.GEMMA_MANAGEMENT?.toggleStudyPackModeValue?.(
          state.selectedStudyPackModes,
          mode.value,
          checkbox.checked,
        ) || [];
        state.selectedStudyPackMode = state.selectedStudyPackModes[0] || "";
        updatePickerSummary();
      });
      item.append(checkbox, text);
      groupEl.appendChild(item);
    });
    panel.appendChild(groupEl);
  });
  const actions = document.createElement("div");
  actions.className = "study-pack-picker-actions";
  const clearButton = document.createElement("button");
  clearButton.type = "button";
  clearButton.className = "study-pack-picker-clear";
  clearButton.textContent = t("studyPack.clearSelection");
  clearButton.disabled = selectionModel.selectedCount === 0;
  clearButton.addEventListener("click", () => {
    state.selectedStudyPackModes = [];
    state.selectedStudyPackMode = "";
    panel.querySelectorAll(".study-pack-picker-item input").forEach((input) => {
      input.checked = false;
    });
    updatePickerSummary();
  });
  actions.appendChild(clearButton);
  panel.appendChild(actions);
  details.appendChild(panel);
  const closeOnOutsideClick = (event) => {
    if (!details.open || details.contains(event.target)) return;
    details.open = false;
  };
  details.addEventListener("toggle", () => {
    if (details.open) {
      document.addEventListener("pointerdown", closeOnOutsideClick);
    } else {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
    }
  });
  els.studyPackModeRow.appendChild(details);
  els.studyPackModeRow.hidden = false;
}

function renderWorkspace() {
  renderWorkspacePanel({
    activeFolder: activeFolder(),
    els,
    onFileSelectionChange: () => {
      saveWorkspacePrefs();
      renderWorkspace();
    },
    state,
    t,
  });
}

function openWorkspaceForPlugin(pluginId = "") {
  if (!activeFolder()) {
    createFolder(t("folder.new"));
  }
  state.workspaceOpen = true;
  render();
  window.requestAnimationFrame(() => {
    const target = pluginId === "fast-search"
      ? els.workspaceSearchRow
      : pluginId === "codegraph"
        ? els.workspaceCodegraphRow
        : els.workspacePanel;
    (target && !target.hidden ? target : els.workspacePanel)?.scrollIntoView({ block: "center" });
  });
}

function updateSessionTitle(session, prompt) {
  if (session.title !== "新規チャット" && session.title !== "New chat" && session.title !== t("chat.new")) return;
  const oneLine = prompt.replace(/\s+/g, " ").trim();
  session.title = oneLine.slice(0, 42) || t("chat.new");
}

const {
  downloadTextFile,
  escapeHtml,
  formatDuration: formatDurationValue,
  numberValue,
  slugForFilename,
  textSnippet,
  timestampForFilename,
} = window.GEMMA_UTILS || {};

const {
  translationBudget,
  isTranslationRequest,
  isTranslationInstructionLine,
  translationSourceText,
  translationTargetIsJapanese,
  translationNeedsQuality,
} = window.GEMMA_TRANSLATION || {};

const {
  isCasualQuickReplyRequest,
  isLocalDateTimeRequest,
  localDateTimeAnswer,
} = window.GEMMA_LOCAL_TOOLS || {};

const {
  isWeatherRequest,
  saveWeatherLocation,
  weatherCoordinatesForRequest,
  weatherLocationFromText,
} = window.GEMMA_WEATHER || {};

const {
  isImageGenerationRequest,
  extractImagePrompt,
  parseImageOptions,
} = window.GEMMA_IMAGE_TOOLS || {};

const {
  bindComposerEvents,
  renderPendingImages: renderPendingImagesView,
  resizePrompt: resizePromptView,
} = window.GEMMA_COMPOSER || {};

const {
  bindAsrUi,
  fetchAsrSetupStatus,
  fetchAsrStatus,
  formatMicGain,
  listAudioInputDevices,
  normalizeMicGain,
  normalizePartialIntervalSeconds,
  normalizePartialTranscriptionMode,
  renderAsrSettings,
  requestAsrSetup,
  startMicLevelMonitor,
} = window.GEMMA_ASR || {};

const {
  cleanCandidatePath,
  compactWorkspaceContent,
  extractCodeBlocks,
  extractJsonObject,
  inferSavePath: inferWorkspaceSavePath,
  inferSimpleTextSave: inferWorkspaceSimpleTextSave,
  isSaveCommand,
  lastAssistantMessage,
  normalizeWorkspacePlan,
  parseWorkspaceGeneration,
  previewSources: workspacePreviewSources,
  renderWorkspacePreviewContent: renderWorkspacePreviewContentView,
  renderWorkspacePanel,
  updateWorkspacePreviewSearch: updateWorkspacePreviewSearchView,
  uniquePath,
  validateFiles: validateWorkspaceFilesApi,
  workspaceContentSummary,
  workspaceContentTranscript,
  workspaceFileKindLabel,
  workspaceFileKindFromText: workspaceFileKindFromTextApi,
  workspaceFileMatchesKind,
  workspaceFormatBytes,
  workspaceTranscriptAction: buildWorkspaceTranscriptAction,
  writeFile: writeWorkspaceFileApi,
} = window.GEMMA_WORKSPACE || {};

const {
  renderTrainingControls: renderTrainingControlsView,
  renderTrainingSetOptions: renderTrainingSetOptionsView,
} = window.GEMMA_TRAINING || {};

const {
  applySearchBudget,
  normalizeSearchResults,
  renderWebSearchToggle,
  searchPayloadOptions,
  searchResultsFromEvent,
  searchResultsFromResponse,
  toggleWebSearch,
} = window.GEMMA_SEARCH || {};

function isWorkspaceBuildRequest(text) {
  if (!state.workspaceRoot) return false;
  if (isTranslationRequest(text)) return false;
  if (isStudyPackRewriteRequest(text) && !explicitlyRequestsWorkspaceSave(text)) return false;
  if (shouldKeepStudyPackReplyInChat(text)) return false;
  if (isWorkspaceLookupRequest(text)) return false;
  return /テトリス|ゲーム|サイト|アプリ|ページ|ツール|作って|つくって|作成|生成|構築|実装|修正|変更|保存|ファイル|html|css|javascript|コード|program|app|game|build|create|implement/i.test(text);
}

function explicitlyRequestsWorkspaceSave(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return false;
  return /(保存して|保存する|保存$|ファイルに保存|ファイルとして保存|書き出して|書き出し|ダウンロード|上書き|新規ファイル)/i.test(normalized);
}

function shouldKeepStudyPackReplyInChat(text) {
  return selectedStudyPackModes().length > 0 && !explicitlyRequestsWorkspaceSave(text);
}

function isStudyPackRewriteRequest(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return false;
  return /(リライト|書き直|書き換|言い換|推敲|添削|校正|読みやすく|読みやすい|論理チェック|論理の抜け|AIっぽさ|レポート向け|レポート添削|文章を整|文を整|rewrite|proofread|revise|polish)/i.test(normalized);
}

function hasExplicitWorkspaceLookupIntent(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return false;
  if (/\b[A-Za-z0-9_.-]+\.(txt|md|pdf|docx?|html|css|js|jsx|ts|tsx|py|json|csv)\b/i.test(normalized)) return true;
  return /(フォルダ|フォルダー|ディレクトリ|作業ディレクトリ|ローカル|ファイル|保存先|中身|一覧|検索|探|見つけ|どこにある|どこに保存|場所|入って|含ま|書か|記載|契約書|請求書|仕様書|見積書|領収書|議事録|資料|文書|テキスト|PDF|Word|folder|directory|file|where is|search|find|contain|contract|invoice|spec|receipt|minutes)/i.test(normalized);
}

function isCharacterPreferenceRequest(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return false;
  const asksPreference = /(好き|好み|趣味|嫌い|どこが好き|何が好き|どう思|覚えて|記憶)/.test(normalized);
  if (!asksPreference) return false;
  const characterName = state.character?.name ? String(state.character.name) : "";
  const userName = state.character?.userName ? String(state.character.userName) : "";
  const mentionsCharacter = Boolean(characterName && normalized.includes(characterName));
  const mentionsUserName = Boolean(userName && normalized.includes(userName));
  return mentionsCharacter || mentionsUserName || !hasExplicitWorkspaceLookupIntent(normalized);
}

function isWorkspaceLookupRequest(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return false;
  if (isCharacterPreferenceRequest(normalized)) return false;
  if (shouldKeepStudyPackReplyInChat(normalized)) return false;
  if (isStudyPackRewriteRequest(normalized) && !explicitlyRequestsWorkspaceSave(normalized)) return false;
  return hasExplicitWorkspaceLookupIntent(normalized)
    && /(フォルダ|フォルダー|PDF|pdf|どこにある|どこに保存|場所|ある|あります|入って|情報|内容|中身|本文|一覧|検索|探|教えて|おしえて|説明|要約|読んで|見つけ|含ま|書か|記載|where|search|find|contain|which)/i.test(normalized)
    && !/(保存|作って|つくって|作成|生成|構築|実装|修正|変更|write|save|create|build|implement)/i.test(normalized);
}

function shouldUseWorkspaceContextForChat(text, requestOptions = {}) {
  if (requestOptions.translationMode) return false;
  if (isStudyPackRewriteRequest(text) && !explicitlyRequestsWorkspaceSave(text)) return false;
  if (requestOptions.codingMode) return true;
  return isWorkspaceLookupRequest(text);
}

function isSimpleWorkspaceBuildRequest(text) {
  if (!isWorkspaceBuildRequest(text)) return false;
  if (/テトリス|本格|複雑|複数|認証|データベース|API|バックエンド|3D|画像生成|編集|修正|変更|大き|complex|database|backend/i.test(text)) {
    return false;
  }
  return /簡単|シンプル|小さ|小さい|軽く|試し|サンプル|test|simple|small|minimal|hello/i.test(text);
}

function modelForWorkspaceBuild(text) {
  if (state.composerModel) return state.composerModel;
  return isSimpleWorkspaceBuildRequest(text) ? fastChatModel() : modelForTask("coding");
}

function isSimpleReplyRequest(text) {
  const normalized = text.replace(/\s+/g, "").trim();
  if (!normalized || normalized.length > 24) return false;
  if (/[?？]|教えて|調べ|検索|説明|なぜ|どう|作っ|つくっ|生成|画像|コード|ファイル|保存|修正|実装|help|why|how|create|build/i.test(text)) {
    return false;
  }
  return /^(おはよ|おはよう|こんにちは|こんばんは|ありがとう|ありがと|どうも|了解|はい|うん|ok|OK|hi|hello|thanks|thankyou|goodmorning)/i.test(normalized);
}

function isLightweightChatRequest(text, hasImages = false) {
  if (hasImages || state.webSearch) return false;
  const normalized = text.replace(/\s+/g, "").trim();
  if (!normalized || normalized.length > 44) return false;
  if (isTranslationRequest(text) || isWorkspaceBuildRequest(text) || isWeatherRequest(text) || isImageGenerationRequest(text)) return false;
  if (/とは|って何|ってなに|誰|だれ|代表|社長|CEO|いつ|どこ|会社|製品|サービス|what is|who is|when|where/i.test(text)) return false;
  if (/教えて|調べ|検索|説明|理由|なぜ|比較|要約|分析|設計|実装|修正|コード|ファイル|保存|画像|添削|翻訳|translate|explain|why|how|code|file|image|search/i.test(text)) {
    return false;
  }
  return (
    isSimpleReplyRequest(text) ||
    isCasualQuickReplyRequest(text) ||
    /かな|かも|どうしよ|どうしよう|おすすめ|たべよう|食べよう|飲もう|ねむい|疲れた|つかれた|がんばる|頑張る/i.test(normalized)
  );
}

function effectiveResponseMode(text, codingMode) {
  if (codingMode) return "quality";
  const selected = state.responseMode;
  if (selected !== "auto") return selected;
  if (isTranslationRequest(text)) return translationNeedsQuality(text) ? "quality" : "fast";
  return isSimpleReplyRequest(text) ? "fast" : "balanced";
}

function effectiveThinkingMode(text, codingMode, responseMode) {
  const selected = state.thinkingMode;
  if (selected !== "auto") return selected;
  if (codingMode || responseMode === "quality") return "high";
  if (responseMode === "fast" || isSimpleReplyRequest(text)) return "low";
  return "medium";
}

function modeSystemSuffix(mode) {
  if (mode === "fast") {
    return "\n\n高速応答モード: 挨拶、雑談、短い相談は1文で自然に短く返してください。箇条書きや候補リストは、ユーザーが求めた時だけにしてください。";
  }
  if (mode === "quality") {
    return "\n\n精度優先モード: 必要な前提を確認し、抜け漏れがないように答えてください。ただし冗長な前置きは避けてください。";
  }
  return "";
}

function thinkingSystemSuffix(mode) {
  if (mode === "low") {
    return "\n\n思考量: 軽め。すぐ答え、必要最小限の確認だけ行ってください。";
  }
  if (mode === "high") {
    return "\n\n思考量: 深く。プログラム作成、設計、修正では要件・制約・破綻しやすい点を内部で確認してから、完成度を優先して答えてください。";
  }
  return "\n\n思考量: 標準。速度と正確さのバランスを取り、必要な範囲で確認して答えてください。";
}

function translationSystemSuffix(enabled) {
  if (!enabled) return "";
  return "\n\n翻訳モード: ユーザーが翻訳を求めた場合は、翻訳文だけを返してください。解説、前置き、箇条書き、候補の列挙は不要です。原文が箇条書きなら箇条書きを保ち、それ以外は自然な文章として訳してください。原文の全文を省略せず、要約しないでください。";
}

function factualSafetySystemSuffix(codingMode, translationMode) {
  if (codingMode || translationMode) return "";
  return [
    "",
    "",
    "事実確認ルール:",
    "- 固有名詞、会社、人物、製品、日付、数値、代表者、所在地などは推測で断定しないでください。",
    `- 学習セット、ユーザー提供文、Web検索結果、添付資料のどれにも根拠がない情報は「${t("training.uncertainAnswer")}」と答えてください。`,
    "- 似た言葉や一般知識から別の意味を作らないでください。",
    "- 学習セットにある事実は優先して使ってください。ただし、学習セットにない追加情報を補完しないでください。",
    "- 現在情報や外部確認が必要な質問では、Web検索を使うよう短く案内してください。",
  ].join("\n");
}

function translationSystemPrompt() {
  return [
    "You are a precise translation engine.",
    "Return only the translated text.",
    "Do not add explanations, bullets, labels, alternatives, or notes.",
    "Preserve the source structure when it is a list or multiline text.",
    "Translate the entire source text. Do not summarize, shorten, skip, or save it to a file.",
    "Do not leave source-language sentences untranslated.",
    "If the request says 英訳, translate into natural English.",
    "If the request says 和訳, translate into natural Japanese.",
    "If the request says 日本語に, translate into natural Japanese.",
    "If no target language is explicit, infer it from the request.",
  ].join("\n");
}

function lightweightChatSystemPrompt() {
  if (state.language === "en") {
    return [
      "You are a natural, lightweight casual assistant.",
      "Keep the active character name, speaking style, and memory unless they conflict with accuracy or safety.",
      "Reply directly in 1-2 short sentences.",
      "For everyday questions like meals, breaks, or mood, give a concrete suggestion.",
      "Do not preface that you are a language model, not an expert, or unable to do something.",
      "Do not use bullet points, option lists, bold text, or headings.",
    ].join("\n");
  }
  return [
    "あなたは日本語で自然に返す軽い雑談アシスタントです。",
    "有効なマイキャラの名前、話し方、記憶を保ってください。ただし正確性や安全性とぶつかる場合はそちらを優先してください。",
    "ユーザーの短い相談や雑談に、1〜2文で直接答えてください。",
    "食事、休憩、気分転換などの日常的な相談には、具体的に提案してください。",
    "自分が言語モデルであること、専門外であること、実行できないことを前置きしないでください。",
    "箇条書き、候補リスト、太字、見出しは使わないでください。",
  ].join("\n");
}

function buildSystemPrompt(basePrompt, codingMode, responseMode = "balanced", thinkingMode = "medium", translationMode = false) {
  const prompt = `${basePrompt}${modeSystemSuffix(responseMode)}${thinkingSystemSuffix(thinkingMode)}${translationSystemSuffix(translationMode)}${factualSafetySystemSuffix(codingMode, translationMode)}`;
  if (!codingMode) return prompt;
  return `${prompt}

フォルダー作業モード:
- ユーザーがアプリ、ゲーム、サイト、ツール作成を求めたら、実際に保存できる完全なファイル内容を出してください。
- 小さなブラウザゲームやデモは、まず自己完結した index.html 1ファイルにまとめてください。
- 参考リンク、解説、前置き、手順説明は出さないでください。
- 出力形式は、保存先の相対パス1行と、その直後の完全なコードブロックだけにしてください。
- 例:
  index.html
  \`\`\`html
  <!doctype html>
  ...
  \`\`\`
- ファイル名をコードブロックの中に入れないでください。
- コードブロックは必ず閉じてください。途中で終わる長さにしないでください。`;
}

function friendlyUncertainAnswer(content) {
  const normalized = String(content || "").replace(/\s+/g, "").replace(/[。.!！]+$/g, "");
  if (/^(確認できません|わかりません|分かりません|不明です|確認できない)$/.test(normalized)) {
    return characterUncertainAnswer();
  }
  if (String(content || "").trim() === t("training.uncertainAnswer")) return characterUncertainAnswer();
  return content;
}

function applyThinkingBudget(options) {
  if (options.thinkingMode === "low") {
    return {
      ...options,
      numPredict: options.codingMode ? Math.max(options.numPredict, 4096) : Math.min(options.numPredict, 128),
      numCtx: options.codingMode ? Math.max(options.numCtx, 8192) : Math.min(options.numCtx, 2048),
      historyTurns: options.codingMode ? Math.max(options.historyTurns, 4) : Math.min(options.historyTurns, 2),
      think: false,
    };
  }
  if (options.thinkingMode === "high") {
    return {
      ...options,
      progressLabel: options.codingMode ? options.progressLabel : t("progress.quality"),
      numPredict: options.codingMode ? Math.max(options.numPredict, 8192) : Math.max(options.numPredict, 512),
      numCtx: options.codingMode ? Math.max(options.numCtx, 12288) : Math.max(options.numCtx, 4096),
      historyTurns: options.codingMode ? Math.max(options.historyTurns, 8) : Math.max(options.historyTurns, 6),
      keepAlive: "30m",
      think: false,
    };
  }
  return {
    ...options,
    think: false,
  };
}

function externalLlmBaseUrlForRequest() {
  return state.externalLlmUrl || "";
}

function modelReasonText(reasonKey) {
  if (state.composerModel) return t("model.reasonManualModel");
  return t(reasonKey);
}

function chatRequestOptions(text, hasImages = false) {
  const translationMode = isTranslationRequest(text);
  const codingMode = !translationMode && isWorkspaceBuildRequest(text);
  const hasStudyPackSelection = selectedStudyPackModes().length > 0 || Boolean(selectedStudyPackMode());
  const lightweightMode = !hasStudyPackSelection && !codingMode && !translationMode && isLightweightChatRequest(text, hasImages);
  const mode = effectiveResponseMode(text, codingMode);
  const thinkingMode = effectiveThinkingMode(text, codingMode, mode);
  const maxTokens = numberValue(els.numPredict, 96);
  const contextSize = numberValue(els.numCtx, 2048);
  const historyTurns = numberValue(els.historyTurns, 4);
  if (lightweightMode) {
    return {
      codingMode,
      translationMode,
      responseMode: "fast",
      thinkingMode: "low",
      progressLabel: t("progress.lightweight"),
      modelReason: modelReasonText("model.reasonLightweight"),
      temperature: Math.min(numberValue(els.temperature, 0.7), 0.55),
      topP: 0.75,
      topK: 20,
      numPredict: 96,
      numCtx: 1024,
      historyTurns: 1,
      keepAlive: "30m",
      think: false,
      webSearch: false,
      fastModel: true,
    };
  }
  if (translationMode) {
    const budget = translationBudget(text, maxTokens);
    const translationModeLabel = translationNeedsQuality(text) ? "quality" : "fast";
    return {
      codingMode,
      translationMode,
      responseMode: translationModeLabel,
      thinkingMode: translationModeLabel === "quality" ? "medium" : "low",
      progressLabel: t("progress.translation"),
      modelReason: modelReasonText(translationModeLabel === "quality" ? "model.reasonTranslationQuality" : "model.reasonTranslation"),
      temperature: 0.1,
      topP: 0.7,
      topK: 10,
      numPredict: budget.numPredict,
      numCtx: budget.numCtx,
      historyTurns: 1,
      keepAlive: "30m",
      think: false,
      webSearch: false,
    };
  }
  if (mode === "fast") {
    return applyThinkingBudget({
      codingMode,
      translationMode,
      responseMode: mode,
      thinkingMode,
      progressLabel: t("progress.fast"),
      modelReason: modelReasonText("model.reasonFastMode"),
      temperature: Math.min(numberValue(els.temperature, 0.7), 0.5),
      topP: Math.min(numberValue(els.topP, 0.9), 0.8),
      topK: Math.min(numberValue(els.topK, 40), 20),
      numPredict: hasStudyPackSelection ? Math.max(maxTokens, 512) : Math.min(Math.max(maxTokens, 64), 128),
      numCtx: Math.min(Math.max(contextSize, 1024), 2048),
      historyTurns: 1,
      keepAlive: "30m",
      think: false,
      webSearch: false,
    });
  }
  if (mode === "quality") {
    return applyThinkingBudget({
      codingMode,
      translationMode,
      responseMode: mode,
      thinkingMode,
      progressLabel: codingMode ? t("progress.coding") : t("progress.quality"),
      modelReason: modelReasonText(codingMode ? "model.reasonCoding" : "model.reasonQualityMode"),
      temperature: numberValue(els.temperature, 0.7),
      topP: numberValue(els.topP, 0.9),
      topK: numberValue(els.topK, 40),
      numPredict: codingMode ? Math.max(maxTokens, 8192) : Math.max(maxTokens, 512),
      numCtx: codingMode ? Math.max(contextSize, 12288) : Math.max(contextSize, 4096),
      historyTurns: codingMode ? Math.max(historyTurns, 6) : Math.max(historyTurns, 8),
      keepAlive: codingMode ? "30m" : "20m",
      think: false,
      webSearch: state.webSearch,
    });
  }
  const searchBudget = applySearchBudget?.({
    codingMode,
    webSearch: state.webSearch,
    maxTokens,
    contextSize,
    historyTurns,
  }) || {
    numPredict: codingMode ? Math.max(maxTokens, 4096) : state.webSearch ? Math.max(maxTokens, 512) : Math.max(maxTokens, 256),
    numCtx: codingMode ? Math.max(contextSize, 8192) : state.webSearch ? Math.max(contextSize, 4096) : contextSize,
    historyTurns: codingMode ? Math.max(historyTurns, 6) : state.webSearch ? Math.min(Math.max(historyTurns, 3), 4) : historyTurns,
  };
  return applyThinkingBudget({
    codingMode,
    translationMode,
    responseMode: mode,
    thinkingMode,
    progressLabel: codingMode ? t("progress.coding") : state.webSearch ? t("progress.search") : t("progress.generating"),
    modelReason: modelReasonText(codingMode ? "model.reasonCoding" : state.webSearch ? "model.reasonWebSearch" : "model.reasonDefaultChat"),
    temperature: numberValue(els.temperature, 0.7),
    topP: numberValue(els.topP, 0.9),
    topK: numberValue(els.topK, 40),
    numPredict: hasStudyPackSelection ? Math.max(searchBudget.numPredict, 768) : searchBudget.numPredict,
    numCtx: hasStudyPackSelection ? Math.max(searchBudget.numCtx, 4096) : searchBudget.numCtx,
    historyTurns: searchBudget.historyTurns,
    keepAlive: codingMode ? "20m" : "15m",
    think: false,
    webSearch: state.webSearch,
  });
}

function workspaceBuilderSystemPrompt() {
  return `あなたはローカルフォルダー内にWebアプリを実装するコーディングエージェントです。
返答は次のどちらかの形式だけにしてください。説明文や参考リンクは禁止です。

形式A: JSONオブジェクト
{
  "summary": "短い作業概要",
  "files": [
    {"path": "index.html", "content": "完全なファイル内容"}
  ],
  "notes": ["任意の短い注意"]
}

形式B: ファイルパス行 + 完全なコードブロック
index.html
\`\`\`html
<!doctype html>
...
\`\`\`

要件:
- 小さなWebゲームやデモは、ユーザー指定がなければ index.html だけを生成してください。
- まず動く最小完成版を優先してください。見た目や演出を盛りすぎないでください。
- 1ファイルは原則250行以内にしてください。
- HTMLにはCSSとJavaScriptを含め、保存後にそのままブラウザーで開ける完成品にしてください。
- 未完成の省略、TODO、途中で切れたコード、外部ライブラリCDN依存は禁止です。
- ファイルパスは相対パスだけにしてください。
- JSONのエスケープに自信がない場合は、形式Bのコードブロック形式を優先してください。`;
}

function workspacePlanSystemPrompt() {
  return `あなたはローカルフォルダーに保存するWebアプリの実装計画を作るコーディングエージェントです。
返答はJSONオブジェクトだけにしてください。Markdown、説明文、コードは禁止です。

形式:
{
  "summary": "短い実装方針",
  "files": [
    {"path": "index.html", "purpose": "このファイルで実装する内容"}
  ]
}

要件:
- 小さなWebゲームやデモは、ユーザー指定がなければ index.html だけにしてください。
- まず動く最小完成版を優先してください。見た目や演出を盛りすぎないでください。
- 最大3ファイルまでにしてください。
- ファイルパスは相対パスだけにしてください。
- 画像や外部ライブラリが不要なら使わないでください。`;
}

function workspaceFileSystemPrompt() {
  return `あなたはローカルフォルダー内の1ファイルを完成させるコーディングエージェントです。
返答は「ファイルパス行 + 完全なコードブロック」だけにしてください。JSON、説明文、参考リンクは禁止です。

形式:
index.html
\`\`\`html
<!doctype html>
...
\`\`\`

要件:
- 指定された1ファイルだけを完全な内容で出力してください。
- 小さなWebゲームやデモの index.html は、CSSとJavaScriptを含む自己完結HTMLにしてください。
- まず動く最小完成版を優先してください。見た目や演出を盛りすぎないでください。
- 1ファイルは原則250行以内にしてください。
- 未完成の省略、TODO、途中で切れたコード、外部ライブラリCDN依存は禁止です。
- ゲームの場合は、最低限の操作、スコアまたは状態表示、リスタートを入れてください。
- ファイルパスは相対パスだけにしてください。`;
}

function simpleWorkspaceFileSystemPrompt() {
  return `あなたは短時間で小さなWebプログラムを完成させるコーディングエージェントです。
返答は「ファイルパス行 + 完全なコードブロック」だけにしてください。JSON、説明文、参考リンクは禁止です。

形式:
index.html
\`\`\`html
<!doctype html>
...
\`\`\`

要件:
- index.html 1ファイルだけを生成してください。
- HTML、CSS、JavaScriptを1ファイルに含め、保存後にブラウザーでそのまま動く完成品にしてください。
- ユーザーが種類を指定していない場合は、ボタンで操作できる小さなカウンターやメモなど、分かりやすい最小プログラムを作ってください。
- 80〜160行程度を目安にし、凝った演出や大きな機能は入れないでください。
- 未完成の省略、TODO、途中で切れたコード、外部ライブラリCDN依存は禁止です。`;
}

function simpleWorkspacePlan() {
  return {
    summary: "index.html 1ファイルで小さく動くWebプログラムを作成します。",
    files: [{ path: "index.html", purpose: "ブラウザーでそのまま動く最小構成のHTML/CSS/JavaScript" }],
  };
}

async function requestWorkspacePlan(userText, signal = null, model = modelForTask("coding")) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: "coding",
      model,
      llm_base_url: externalLlmBaseUrlForRequest(),
      system: workspacePlanSystemPrompt(),
      messages: [{ role: "user", content: userText }],
      temperature: 0.1,
      top_p: 0.7,
      top_k: 20,
      num_predict: 512,
      num_ctx: 4096,
      history_turns: 1,
      think: false,
      keep_alive: "20m",
      web_search: false,
      workspace: workspacePayload(),
    }),
    signal: combinedAbortSignal(signal, WORKSPACE_PLAN_TIMEOUT_MS),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "実装計画の作成に失敗しました。");
  }
  try {
    return normalizeWorkspacePlan(extractJsonObject(data.message?.content || ""));
  } catch {
    return normalizeWorkspacePlan(null);
  }
}

function localTetrisFiles() {
  return [
    {
      path: "index.html",
      content: `<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>シンプルWebテトリス</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #101417; color: #edf5ef; }
    main { display: grid; grid-template-columns: auto 180px; gap: 20px; align-items: start; padding: 20px; }
    canvas { background: #070a0c; border: 1px solid #2c3834; box-shadow: 0 18px 50px #0008; }
    aside { display: grid; gap: 14px; }
    h1 { margin: 0 0 6px; font-size: 24px; }
    .panel { border: 1px solid #2c3834; border-radius: 8px; background: #18201d; padding: 14px; }
    .score { font-size: 30px; font-weight: 800; }
    button { border: 0; border-radius: 8px; padding: 10px 12px; background: #46d88b; color: #062015; font-weight: 800; cursor: pointer; }
    p { margin: 6px 0; color: #a9b8b0; line-height: 1.5; }
    @media (max-width: 720px) { main { grid-template-columns: 1fr; } canvas { width: min(92vw, 320px); height: auto; } }
  </style>
</head>
<body>
  <main>
    <canvas id="board" width="300" height="600" aria-label="テトリス盤"></canvas>
    <aside>
      <section class="panel">
        <h1>Webテトリス</h1>
        <p>左右: ← →</p>
        <p>回転: ↑ / X</p>
        <p>落下: ↓ / Space</p>
      </section>
      <section class="panel">
        <p>スコア</p>
        <div class="score" id="score">0</div>
      </section>
      <button id="restart">リスタート</button>
    </aside>
  </main>
  <script>
    const canvas = document.getElementById("board");
    const ctx = canvas.getContext("2d");
    const scoreEl = document.getElementById("score");
    const cols = 10;
    const rows = 20;
    const size = 30;
    const colors = {
      I: "#67e8f9", O: "#fde047", T: "#c084fc", S: "#4ade80",
      Z: "#fb7185", J: "#60a5fa", L: "#fb923c"
    };
    const shapes = {
      I: [[1, 1, 1, 1]],
      O: [[1, 1], [1, 1]],
      T: [[0, 1, 0], [1, 1, 1]],
      S: [[0, 1, 1], [1, 1, 0]],
      Z: [[1, 1, 0], [0, 1, 1]],
      J: [[1, 0, 0], [1, 1, 1]],
      L: [[0, 0, 1], [1, 1, 1]]
    };
    let board, piece, score, dropTimer, lastTime, gameOver;

    function reset() {
      board = Array.from({ length: rows }, () => Array(cols).fill(""));
      score = 0;
      gameOver = false;
      scoreEl.textContent = score;
      piece = nextPiece();
      lastTime = 0;
      dropTimer = 0;
      requestAnimationFrame(loop);
    }

    function nextPiece() {
      const keys = Object.keys(shapes);
      const type = keys[Math.floor(Math.random() * keys.length)];
      return { type, shape: shapes[type].map(row => [...row]), x: 3, y: 0 };
    }

    function rotate(matrix) {
      return matrix[0].map((_, i) => matrix.map(row => row[i]).reverse());
    }

    function collides(test = piece) {
      for (let y = 0; y < test.shape.length; y++) {
        for (let x = 0; x < test.shape[y].length; x++) {
          if (!test.shape[y][x]) continue;
          const bx = test.x + x;
          const by = test.y + y;
          if (bx < 0 || bx >= cols || by >= rows || (by >= 0 && board[by][bx])) return true;
        }
      }
      return false;
    }

    function merge() {
      piece.shape.forEach((row, y) => row.forEach((cell, x) => {
        if (cell && piece.y + y >= 0) board[piece.y + y][piece.x + x] = piece.type;
      }));
    }

    function clearLines() {
      let cleared = 0;
      board = board.filter(row => {
        if (row.every(Boolean)) { cleared++; return false; }
        return true;
      });
      while (board.length < rows) board.unshift(Array(cols).fill(""));
      if (cleared) {
        score += [0, 100, 300, 500, 800][cleared];
        scoreEl.textContent = score;
      }
    }

    function drop() {
      piece.y++;
      if (collides()) {
        piece.y--;
        merge();
        clearLines();
        piece = nextPiece();
        if (collides()) gameOver = true;
      }
    }

    function drawCell(x, y, color) {
      ctx.fillStyle = color;
      ctx.fillRect(x * size + 1, y * size + 1, size - 2, size - 2);
    }

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      board.forEach((row, y) => row.forEach((type, x) => type && drawCell(x, y, colors[type])));
      piece.shape.forEach((row, y) => row.forEach((cell, x) => {
        if (cell) drawCell(piece.x + x, piece.y + y, colors[piece.type]);
      }));
      if (gameOver) {
        ctx.fillStyle = "#000b";
        ctx.fillRect(0, 250, canvas.width, 100);
        ctx.fillStyle = "#fff";
        ctx.font = "bold 28px system-ui";
        ctx.textAlign = "center";
        ctx.fillText("GAME OVER", canvas.width / 2, 310);
      }
    }

    function loop(time = 0) {
      if (gameOver) { draw(); return; }
      const delta = time - lastTime;
      lastTime = time;
      dropTimer += delta;
      if (dropTimer > 700) { drop(); dropTimer = 0; }
      draw();
      requestAnimationFrame(loop);
    }

    document.addEventListener("keydown", event => {
      if (gameOver) return;
      if (event.key === "ArrowLeft") {
        piece.x--;
        if (collides()) piece.x++;
      } else if (event.key === "ArrowRight") {
        piece.x++;
        if (collides()) piece.x--;
      } else if (event.key === "ArrowDown") {
        drop();
      } else if (event.key === "ArrowUp" || event.key.toLowerCase() === "x") {
        const next = { ...piece, shape: rotate(piece.shape) };
        if (!collides(next)) piece.shape = next.shape;
      } else if (event.code === "Space") {
        event.preventDefault();
        while (!collides()) piece.y++;
        piece.y--;
        drop();
      }
      draw();
    });
    document.getElementById("restart").addEventListener("click", reset);
    reset();
  </script>
</body>
</html>
`,
    },
  ];
}

function localWorkspaceTemplate(text) {
  if (/テトリス|tetris/i.test(text)) {
    return {
      summary: "ローカルテンプレートでWebテトリスを生成しました。",
      notes: ["Gemma生成を待たずに、自己完結のindex.htmlを保存します。"],
      files: localTetrisFiles(),
    };
  }
  return null;
}

function validationText(validation) {
  if (!validation || !Array.isArray(validation.results)) return "";
  return validation.results
    .filter((item) => !item.ok)
    .map((item) => `${item.path}: ${(item.errors || []).join(" / ")}`)
    .join("\n");
}

function combinedAbortSignal(primarySignal, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(new DOMException("timed out", "TimeoutError")), timeoutMs);
  const abort = () => {
    window.clearTimeout(timeoutId);
    controller.abort(primarySignal?.reason || new DOMException("aborted", "AbortError"));
  };
  if (primarySignal?.aborted) abort();
  else primarySignal?.addEventListener("abort", abort, { once: true });
  return controller.signal;
}

async function requestWorkspaceFiles(userText, previousFiles = [], validation = null, signal = null, model = modelForTask("coding")) {
  const correction = validation && !validation.ok
    ? `\n\n前回の生成には以下の検証エラーがあります。全ファイルを修正版として再出力してください。\n${validationText(validation)}\n\n前回ファイル:\n${JSON.stringify(previousFiles).slice(0, 60000)}`
    : "";
  const parseCorrection = validation?.parseError
    ? `\n\n前回の出力は保存形式として読み取れませんでした。\nエラー: ${validation.parseError}\nJSONにする場合は全ての改行と引用符を正しくエスケープしてください。難しい場合は、ファイルパス行と完全なコードブロック形式で再出力してください。`
    : "";
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: "coding",
      model,
      llm_base_url: externalLlmBaseUrlForRequest(),
      system: workspaceBuilderSystemPrompt(),
      messages: [
        {
          role: "user",
          content: `${userText}${correction}${parseCorrection}`,
        },
      ],
      temperature: 0.15,
      top_p: 0.8,
      top_k: 20,
      num_predict: 4096,
      num_ctx: 8192,
      history_turns: 1,
      think: false,
      keep_alive: "20m",
      web_search: false,
      workspace: workspacePayload(),
    }),
    signal: combinedAbortSignal(signal, WORKSPACE_FILE_TIMEOUT_MS),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "コード生成に失敗しました。");
  }
  return parseWorkspaceGeneration(data.message?.content || "");
}

async function requestWorkspaceFile(userText, plan, fileSpec, previousFile = null, validation = null, signal = null, model = modelForTask("coding"), options = {}) {
  const errors = validationText(validation);
  const repairBlock = previousFile || errors || validation?.parseError
    ? [
        "",
        "前回の生成を修正してください。",
        errors ? `検証エラー:\n${errors}` : "",
        validation?.parseError ? `保存形式エラー:\n${validation.parseError}` : "",
        previousFile ? `前回の ${fileSpec.path}:\n${previousFile.content.slice(0, 30000)}` : "",
      ].filter(Boolean).join("\n")
    : "";
  const content = [
    `元の依頼:\n${userText}`,
    "",
    `実装方針:\n${plan.summary}`,
    `生成対象:\n${fileSpec.path}`,
    `目的:\n${fileSpec.purpose || "このファイルを完成させる"}`,
    "",
    `全ファイル:\n${plan.files.map((file) => `- ${file.path}: ${file.purpose || ""}`).join("\n")}`,
    repairBlock,
    "",
    "上記の生成対象1ファイルだけを、保存できる完全なコードブロック形式で出力してください。",
  ].join("\n");
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: "coding",
      model,
      llm_base_url: externalLlmBaseUrlForRequest(),
      system: options.system || workspaceFileSystemPrompt(),
      messages: [{ role: "user", content }],
      temperature: options.temperature ?? 0.15,
      top_p: options.topP ?? 0.8,
      top_k: options.topK ?? 20,
      num_predict: options.numPredict ?? 4096,
      num_ctx: options.numCtx ?? 8192,
      history_turns: 1,
      think: false,
      keep_alive: options.keepAlive || "20m",
      web_search: false,
      workspace: workspacePayload(),
    }),
    signal: combinedAbortSignal(signal, options.timeoutMs || WORKSPACE_FILE_TIMEOUT_MS),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `${fileSpec.path} の生成に失敗しました。`);
  }
  const parsed = parseWorkspaceGeneration(data.message?.content || "");
  const exact = parsed.files.find((file) => file.path === fileSpec.path) || parsed.files[0];
  return {
    path: fileSpec.path,
    content: exact.content,
  };
}

async function saveGeneratedFiles(files) {
  const saved = [];
  for (const file of files) {
    const data = await writeWorkspaceFileApi({
      root: state.workspaceRoot,
      path: file.path,
      content: file.content,
    }).catch((error) => {
      throw new Error(error.message || `${file.path} を保存できませんでした。`);
    });
    saved.push({ path: data.path, size: data.size });
  }
  return saved;
}

async function validateGeneratedFiles(files) {
  return validateWorkspaceFilesApi({ root: state.workspaceRoot, files }).catch((error) => {
    throw new Error(error.message || "検証に失敗しました。");
  });
}

function buildWorkspaceResultMessage(savedFiles, validation, attempts, notes = []) {
  const lines = [
    validation.ok ? "保存と検証が完了しました。" : "保存しましたが、検証で問題が残っています。",
    ...savedFiles.map((file) => `- ${file.path} (${file.size}バイト)`),
    `検証: ${validation.ok ? "OK" : "要確認"}`,
    `試行回数: ${attempts}`,
  ];
  const errors = validationText(validation);
  if (errors) lines.push(`検証エラー:\n${errors}`);
  if (savedFiles.some((file) => /\.html?$/i.test(file.path))) {
    lines.push("下の「動作確認」からブラウザーで開けます。");
  }
  if (notes.length > 0) lines.push(`メモ:\n${notes.map((note) => `- ${note}`).join("\n")}`);
  return lines.join("\n");
}

async function handleWorkspaceBuild(text) {
  if (isTranslationRequest(text)) {
    await sendMessage(text);
    return;
  }

  let session = activeSession();
  if (!session) {
    newSession();
    session = activeSession();
  }

  session.messages.push({ role: "user", content: text });
  updateSessionTitle(session, text);
  state.busy = true;
  state.abortController = new AbortController();
  startProgressTimer(t("progress.workspace"));
  const progressMessage = {
    role: "assistant",
    content: "作業を開始しました。\n- 要件を整理中",
    streaming: true,
  };
  session.messages.push(progressMessage);
  saveSessions();
  render();

  let generated = null;
  let savedFiles = [];
  let validation = null;
  let plan = null;
  let attempts = 0;
  const simpleBuild = isSimpleWorkspaceBuildRequest(text);
  const maxAttempts = simpleBuild ? 2 : 3;
  let activeCodingModel = modelForWorkspaceBuild(text);
  let usedFallbackModel = false;
  const generationOptions = simpleBuild
    ? {
        system: simpleWorkspaceFileSystemPrompt(),
        temperature: 0.1,
        topP: 0.75,
        topK: 20,
        numPredict: 2048,
        numCtx: 4096,
        keepAlive: "30m",
        timeoutMs: SIMPLE_WORKSPACE_FILE_TIMEOUT_MS,
      }
    : {};
  const setBuildProgress = (lines) => {
    progressMessage.content = lines.join("\n");
    saveSessions();
    render();
  };

  try {
    for (attempts = 1; attempts <= maxAttempts; attempts += 1) {
      state.progressLabel = simpleBuild
        ? attempts === 1 ? "簡単生成中" : "短く自動修正中"
        : attempts === 1 ? "生成・保存中" : `自動修正中 ${attempts - 1}/2`;
      updateProgressTimer();
      try {
        if (!plan) {
          if (simpleBuild) {
            plan = simpleWorkspacePlan();
            setBuildProgress([
              `作業中: ${state.progressLabel}`,
              `- 試行 ${attempts}/${maxAttempts}`,
              `- ${activeCodingModel} で小さな index.html を生成中`,
              "- 計画生成を省略して短時間で保存します",
            ]);
          } else {
            setBuildProgress([
              `作業中: ${state.progressLabel}`,
              `- 試行 ${attempts}/${maxAttempts}`,
              `- ${activeCodingModel} で実装計画を作成中`,
              usedFallbackModel ? "- Coderが遅いため標準モデルへ自動切替済み" : null,
              "- 初回はモデル読み込みで数分かかることがあります",
            ].filter(Boolean));
            plan = await requestWorkspacePlan(text, state.abortController.signal, activeCodingModel);
          }
        }

        const generatedFiles = [];
        for (const [index, fileSpec] of plan.files.entries()) {
          const previousFile = generated?.files?.find((file) => file.path === fileSpec.path) || null;
          setBuildProgress([
            `作業中: ${state.progressLabel}`,
            `- 試行 ${attempts}/${maxAttempts}`,
            `- 計画: ${plan.summary}`,
            `- ${index + 1}/${plan.files.length} ${fileSpec.path} を生成中`,
            simpleBuild ? "- 簡単タスクのため短時間生成を使用中" : null,
            usedFallbackModel ? "- Coderが遅いため標準モデルへ自動切替済み" : null,
          ].filter(Boolean));
          const file = await requestWorkspaceFile(
            text,
            plan,
            fileSpec,
            previousFile,
            validation,
            state.abortController.signal,
            activeCodingModel,
            generationOptions,
          );
          generatedFiles.push(file);
        }
        generated = {
          summary: plan.summary,
          files: generatedFiles,
          notes: [simpleBuild
            ? `簡単生成: ${activeCodingModel} で1ファイル生成 → 保存 → 検証`
            : `段階生成: 計画作成 → ${generatedFiles.length}ファイル生成 → 保存 → 検証`],
        };
      } catch (error) {
        const fallback = fallbackCodingModel();
        if (
          error.name === "TimeoutError" &&
          attempts < maxAttempts &&
          !usedFallbackModel &&
          activeCodingModel !== fallback
        ) {
          activeCodingModel = fallback;
          usedFallbackModel = true;
          plan = null;
          validation = {
            ok: false,
            results: [],
            parseError: "前回のコード生成モデルが時間内に完了しませんでした。標準モデルで短い完成版を再生成してください。",
          };
          setBuildProgress([
            simpleBuild ? "簡単生成が時間内に完了しませんでした。" : "コード生成モデルが時間内に完了しませんでした。",
            `- 試行 ${attempts}/${maxAttempts}`,
            `- ${fallback} に自動切替して再試行します`,
          ]);
          continue;
        }
        if (attempts < maxAttempts && /生成結果を読み取れませんでした|JSON|コードブロック/.test(error.message)) {
          validation = { ok: false, results: [], parseError: error.message };
          setBuildProgress([
            "生成結果の形式を読み取れませんでした。",
            `- 試行 ${attempts}/${maxAttempts}`,
            "- コード用モデルに保存可能な形式で再出力を依頼します",
            error.message,
          ]);
          continue;
        }
        throw error;
      }
      setBuildProgress([
        `作業中: ${state.progressLabel}`,
        `- 試行 ${attempts}/${maxAttempts}`,
        `- ${generated.files.length}件のファイルを受信`,
        "- ローカルフォルダーへ保存中",
      ]);
      savedFiles = await saveGeneratedFiles(generated.files);
      setBuildProgress([
        `作業中: ${state.progressLabel}`,
        `- 試行 ${attempts}/${maxAttempts}`,
        `- ${savedFiles.length}件のファイルを保存`,
        "- 構文と未完成表現を検証中",
      ]);
      validation = await validateGeneratedFiles(savedFiles);
      if (validation.ok) break;
      setBuildProgress([
        "検証で問題を検出しました。",
        `- 試行 ${attempts}/${maxAttempts}`,
        "- コード用モデルに修正を依頼します",
        validationText(validation),
      ].filter(Boolean));
    }
    await loadWorkspace();
    for (const file of savedFiles) {
      state.selectedFiles.add(file.path);
    }
    saveWorkspacePrefs();
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    progressMessage.content = buildWorkspaceResultMessage(savedFiles, validation, attempts, generated?.notes || []);
    progressMessage.sources = workspacePreviewSources({
      root: state.workspaceRoot,
      files: savedFiles,
      label: t("chat.preview"),
    });
    progressMessage.durationSeconds = durationSeconds;
    progressMessage.runMeta = {
      model: activeCodingModel,
      modelLabel: shortModelName(activeCodingModel, "coding"),
      task: "coding",
      taskLabel: t("task.coding"),
      responseMode: simpleBuild ? "fast" : "quality",
      responseModeLabel: simpleBuild ? t("mode.fast") : t("mode.quality"),
      thinkingMode: simpleBuild ? "low" : "high",
    };
    delete progressMessage.streaming;
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    if (error.name === "AbortError") {
      progressMessage.content = "生成を停止しました。";
    } else if (error.name === "TimeoutError" || /timed out/i.test(error.message)) {
      progressMessage.content = simpleBuild
        ? [
            "簡単生成が2分以内に完了しなかったため停止しました。",
            "- 依頼をさらに具体化すると成功しやすくなります",
            "- 例: ボタンを押すと数字が増えるindex.htmlを作って",
          ].join("\n")
        : [
            "生成が時間内に完了しなかったため停止しました。",
            "- Coderが遅い場合は標準モデルへの自動切替を試します",
            "- それでも止まる場合は、依頼をさらに小さくしてください。例: まず画面だけ作る",
          ].join("\n");
    } else {
      progressMessage.content = `${t("error.prefix")}: ${error.message}`;
    }
    progressMessage.durationSeconds = durationSeconds;
    progressMessage.runMeta = {
      model: activeCodingModel,
      modelLabel: shortModelName(activeCodingModel, "coding"),
      task: "coding",
      taskLabel: t("task.coding"),
      responseMode: simpleBuild ? "fast" : "quality",
      responseModeLabel: simpleBuild ? t("mode.fast") : t("mode.quality"),
      thinkingMode: simpleBuild ? "low" : "high",
    };
    delete progressMessage.streaming;
  } finally {
    state.abortController = null;
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
  return true;
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    state.appInfo.version = data.appVersion || state.appInfo.version;
    state.appInfo.commit = data.appCommit || state.appInfo.commit;
    state.appInfo.searchCapabilities = data.searchCapabilities || state.appInfo.searchCapabilities;
    if (data.models) {
      state.serverModels.chat = data.models.chat || data.model || state.serverModels.chat;
      state.serverModels.coding = data.models.coding || data.codingModel || state.serverModels.coding;
      state.serverModels.translation = data.models.translation || data.translationModel || state.serverModels.translation;
    }
    state.serverModels.codingInstalled = data.codingModelInstalled !== false;
    if (Array.isArray(data.recommendedCodingModels)) {
      state.serverModels.recommendedCoding = data.recommendedCodingModels;
    }
    if (Array.isArray(data.pullableModels)) {
      state.serverModels.pullable = data.pullableModels;
      renderModelInstaller();
    }
    if (Array.isArray(data.availableModels) || state.serverModels.recommendedCoding.length > 0) {
      state.serverModels.available = data.availableModels || state.serverModels.available;
      syncModelInputs();
      renderModelInstaller();
    }
    els.statusDot.className = `status-dot ${data.ok && data.modelInstalled ? "ok" : "error"}`;
    const codingMissing = data.ok && data.codingModel && data.codingModelInstalled === false;
    els.statusText.textContent = data.ok && data.modelInstalled
      ? codingMissing ? t("status.codingMissing") : t("status.available")
      : t("status.modelMissing");
    renderSettingsMeta();
    if (!state.busy) renderMessages();
  } catch {
    state.appInfo.version = state.language === "en" ? "failed" : "取得失敗";
    state.appInfo.commit = "";
    els.statusDot.className = "status-dot error";
    els.statusText.textContent = t("status.offline");
    renderSettingsMeta();
    renderModelInstaller();
  }
}

async function readChatStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const parseEvent = (text) => {
    try {
      return JSON.parse(text);
    } catch {
      const preview = text.replace(/\s+/g, " ").slice(0, 120);
      throw new Error(preview ? `生成結果を読み取れませんでした。アプリまたはモデルサーバーを確認してください: ${preview}` : "生成結果を読み取れませんでした。");
    }
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      onEvent(parseEvent(trimmed));
    }
  }
  buffer += decoder.decode();
  const trimmed = buffer.trim();
  if (trimmed) onEvent(parseEvent(trimmed));
}

async function sendMessage(text) {
  let session = activeSession();
  if (!session) {
    newSession();
    session = activeSession();
  }

  const images = state.pendingImages.map((image) => image.base64);
  const imagePreviews = state.pendingImages.map((image) => image.preview);
  const pendingFiles = [...state.pendingFiles];
  const attachments = pendingFiles.map((file) => ({
    name: file.name,
    kind: file.kind,
    size: file.size,
    sizeLabel: file.sizeLabel,
  }));
  const requestOptions = chatRequestOptions(text, images.length > 0);
  const appliedStudyPackModes = [...(state.selectedStudyPackModes || [])];
  const appliedStudyPackSelections = selectedStudyPackModes();
  const appliedStudyPackModeLabel = studyPackModesDisplayLabel(appliedStudyPackSelections);
  const userMessage = { role: "user", content: text, images, imagePreviews, attachments };
  session.messages.push(userMessage);
  const memoryCandidate = window.GEMMA_CHARACTER?.memoryCandidateFromText?.(text, {
    mode: state.character?.memoryMode || "suggest",
  });
  if (memoryCandidate) openMemoryCandidate(memoryCandidate);
  state.pendingImages = [];
  state.pendingFiles = [];
  updateSessionTitle(session, text);
  state.busy = true;
  startProgressTimer(requestOptions.progressLabel, requestOptions.modelReason);
  saveSessions();
  render();

  let assistantMessage = null;
  let renderScheduled = false;
  let requestModel = "";
  const studyPackRunMeta = appliedStudyPackModeLabel ? { studyPackModeLabel: appliedStudyPackModeLabel } : {};
  let runMetaOverrides = { ...studyPackRunMeta };
  const scheduleStreamRender = () => {
    if (renderScheduled) return;
    renderScheduled = true;
    window.requestAnimationFrame(() => {
      renderScheduled = false;
      saveSessions();
      render();
    });
  };

  try {
    const attachmentResults = pendingFiles.length > 0 ? await extractAttachmentContents(pendingFiles) : [];
    const attachmentContext = attachmentContextFromResults(attachmentResults);
    const hasAttachmentFiles = pendingFiles.length > 0;
    const hasReadableAttachments = attachmentResults.some((item) => String(item.content || "").trim());
    const attachmentSources = attachmentSummarySources(attachmentResults);
    runMetaOverrides = hasAttachmentFiles
      ? { ...studyPackRunMeta, modelReason: "添付ファイルを優先", codeUnderstanding: false }
      : { ...studyPackRunMeta };
    if (attachmentResults.length > 0) {
      userMessage.attachments = attachmentResults.map((item) => ({
        name: item.name,
        kind: item.kind,
        size: item.size,
        sizeLabel: workspaceFormatBytes(item.size || 0),
        readable: Boolean(item.content && item.content.trim()),
        error: item.error || "",
        content: item.content || "",
      }));
    }
    if (hasAttachmentFiles && !hasReadableAttachments) {
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      const details = attachmentResults
        .map((item) => `- ${item.name}: ${item.error || "本文を抽出できませんでした"}`)
        .join("\n");
      pushAssistantReply(session, {
        content: applyCharacterToneToToolReply(
          `添付ファイルを読み取れなかったよ。\n${details}\n\n画像だけのPDFやスキャンPDFの場合は、「設定」→「プラグイン」→「画像文字読み取り（OCR）」を確認してね。`,
        ),
        durationSeconds,
        runMeta: attachmentRunMeta(requestOptions, "添付ファイルの読み取りに失敗"),
      });
      return;
    }
    if (hasAttachmentFiles && hasReadableAttachments && isAttachmentTranscriptRequest(text)) {
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      pushAssistantReply(session, {
        content: directAttachmentTranscriptAnswer(attachmentResults, attachmentReplyOptions()),
        sources: attachmentSummarySources(attachmentResults),
        durationSeconds,
        runMeta: attachmentRunMeta(requestOptions, "添付ファイルの文字起こしとして判定"),
      });
      return;
    }
    if (hasAttachmentFiles && hasReadableAttachments && isVagueAttachmentQuestion(text)) {
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      pushAssistantReply(session, {
        content: directAttachmentAnswer(attachmentResults, attachmentReplyOptions()),
        sources: attachmentSummarySources(attachmentResults),
        durationSeconds,
        runMeta: attachmentRunMeta(requestOptions, "短い添付質問として判定"),
      });
      return;
    }
    const previousAttachment = !hasAttachmentFiles
      ? lastReadableAttachment({ messages: session.messages.slice(0, -1) })
      : null;
    if (previousAttachment && isAttachmentFollowupRequest(text, attachmentReplyOptions())) {
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      const previousAttachmentResults = [{
        name: previousAttachment.name,
        kind: previousAttachment.kind,
        content: previousAttachment.content,
        size: previousAttachment.size,
      }];
      pushAssistantReply(session, {
        content: isAttachmentTranscriptRequest(text)
          ? directAttachmentTranscriptAnswer(previousAttachmentResults, attachmentReplyOptions())
          : directAttachmentAnswer(previousAttachmentResults, attachmentReplyOptions()),
        sources: attachmentSummarySources(previousAttachmentResults),
        durationSeconds,
        runMeta: attachmentRunMeta(requestOptions, "前回の添付ファイルへの追質問として判定"),
      });
      return;
    }
    const previousAttachmentReference = !hasAttachmentFiles
      ? lastAttachmentReference({ messages: session.messages.slice(0, -1) })
      : null;
    if (previousAttachmentReference && isAttachmentFollowupRequest(text, attachmentReplyOptions())) {
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      pushAssistantReply(session, {
        content: unreadablePreviousAttachmentAnswer(previousAttachmentReference, attachmentReplyOptions()),
        durationSeconds,
        runMeta: attachmentRunMeta(requestOptions, "前回の添付ファイルに本文が残っていないため再添付を案内"),
      });
      return;
    }
    const baseRequestSystem = requestOptions.translationMode
      ? translationSystemPrompt()
      : requestOptions.fastModel
        ? lightweightChatSystemPrompt()
        : buildSystemPrompt(
            els.systemPrompt.value,
            requestOptions.codingMode,
            requestOptions.responseMode,
            requestOptions.thinkingMode,
            requestOptions.translationMode,
          );
    const requestSystemWithTraining = `${requestOptions.translationMode ? "" : characterContextSystemPrompt()}${baseRequestSystem}${requestOptions.translationMode ? "" : studyPackContextSystemPrompt()}${trainingContextSystemPrompt()}`;
    const modelUserMessage = messageWithAttachmentContext(userMessage, attachmentContext);
    const requestMessages = requestOptions.translationMode || requestOptions.fastModel
      ? [modelUserMessage]
      : [...session.messages.slice(0, -1), modelUserMessage];
    const stream = true;
    const requestTask = requestOptions.translationMode ? "translation" : requestOptions.codingMode ? "coding" : "chat";
    requestModel = modelForRequestTask(requestTask, requestOptions);
    const shouldUseWorkspaceShortcuts = !hasAttachmentFiles;
    const shouldUseWorkspaceContext = shouldUseWorkspaceShortcuts && shouldUseWorkspaceContextForChat(text, requestOptions);
    const requestedFileKind = shouldUseWorkspaceContext ? workspaceFileKindFromText(text) : "";
    if (
      !requestOptions.codingMode &&
      !requestOptions.translationMode &&
      shouldUseWorkspaceContext &&
      requestedFileKind &&
      isWorkspaceLookupRequest(text) &&
      state.workspaceRoot &&
      !state.workspaceFiles.length
    ) {
      await loadWorkspace();
    }
    if (shouldUseWorkspaceContext && await handleWorkspaceFileKindContentRequest(text, requestOptions)) {
      return;
    }
    const workspaceRequest = shouldUseWorkspaceContext ? workspacePayload(text) : null;
    const localSearchSources = shouldUseWorkspaceContext ? await workspaceSearchSourcesForChat(workspaceRequest) : [];
    const codegraphSources = shouldUseWorkspaceContext ? codegraphSourcesForChat() : [];
    if (shouldUseWorkspaceContext && await handleWorkspaceSearchContentRequest(text, localSearchSources, requestOptions)) {
      return;
    }
    const fileKindAnswer = shouldUseWorkspaceContext ? workspaceFileKindAnswer(text) : null;
    if (!requestOptions.codingMode && !requestOptions.translationMode && shouldUseWorkspaceContext && isWorkspaceLookupRequest(text) && fileKindAnswer) {
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      session.messages.push({
        role: "assistant",
        content: fileKindAnswer.content,
        sources: fileKindAnswer.sources,
        durationSeconds,
        runMeta: {
          model: "local-fast-search",
          modelLabel: t("workspace.chatSearchModel"),
          task: "search",
          taskLabel: t("workspace.fastSearch"),
          responseMode: requestOptions.responseMode,
          responseModeLabel: responseModeLabel(requestOptions.responseMode),
          thinkingMode: requestOptions.thinkingMode,
          modelReason: t("model.reasonWorkspaceLookup"),
          codeUnderstanding: false,
        },
      });
      return;
    }
    if (!requestOptions.codingMode && !requestOptions.translationMode && shouldUseWorkspaceContext && isWorkspaceLookupRequest(text) && workspaceRequest?.searchQuery) {
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      session.messages.push({
        role: "assistant",
        content: workspaceSearchAnswer(workspaceRequest, localSearchSources),
        sources: localSearchSources,
        durationSeconds,
        runMeta: {
          model: "local-fast-search",
          modelLabel: t("workspace.chatSearchModel"),
          task: "search",
          taskLabel: t("workspace.fastSearch"),
          responseMode: requestOptions.responseMode,
          responseModeLabel: responseModeLabel(requestOptions.responseMode),
          thinkingMode: requestOptions.thinkingMode,
          modelReason: t("model.reasonWorkspaceLookup"),
          codeUnderstanding: false,
        },
      });
      return;
    }
    const payload = {
      task: requestTask,
      model: requestModel,
      llm_base_url: externalLlmBaseUrlForRequest(),
      stream,
      system: requestSystemWithTraining,
      messages: requestMessages,
      temperature: requestOptions.temperature,
      top_p: requestOptions.topP,
      top_k: requestOptions.topK,
      num_predict: requestOptions.numPredict,
      num_ctx: requestOptions.numCtx,
      history_turns: requestOptions.historyTurns,
      think: requestOptions.think,
      keep_alive: requestOptions.keepAlive,
      ...(searchPayloadOptions?.(requestOptions, 4) || {
        web_search: !requestOptions.codingMode && requestOptions.webSearch,
        search_results: 4,
      }),
      workspace: workspaceRequest,
    };
    state.abortController = new AbortController();
    if (stream) {
      assistantMessage = {
        role: "assistant",
        content: "",
        sources: [...attachmentSources, ...localSearchSources, ...codegraphSources],
        streaming: true,
      };
      session.messages.push(assistantMessage);
      saveSessions();
      render();
    }
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: state.abortController.signal,
    });

    if (stream && response.body) {
      if (!response.ok) {
        throw new Error("Request failed");
      }
      let streamSearchResults = [];
      await readChatStream(response, (event) => {
        if (!event.ok) {
          throw new Error(event.error || "Request failed");
        }
        streamSearchResults = searchResultsFromEvent?.(event, streamSearchResults) || streamSearchResults;
        if (event.type === "chunk" && event.content) {
          assistantMessage.content += event.content;
          scheduleStreamRender();
        }
        if (event.type === "done") {
          assistantMessage.content = event.message?.content || assistantMessage.content;
          streamSearchResults = searchResultsFromEvent?.(event, streamSearchResults) || streamSearchResults;
        }
      });
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      let content = friendlyUncertainAnswer(assistantMessage.content || "");
      if (hasAttachmentFiles && hasReadableAttachments && attachmentAnswerLooksBroken(content)) {
        content = isAttachmentTranscriptRequest(text)
          ? directAttachmentTranscriptAnswer(attachmentResults, attachmentReplyOptions())
          : directAttachmentAnswer(attachmentResults, attachmentReplyOptions());
      }
      let savedFiles = [];
      let saveError = "";
      if (requestOptions.codingMode) {
        try {
          savedFiles = await autoSaveGeneratedFiles(text, content);
        } catch (error) {
          saveError = error.message;
        }
      }
      const savedNote = savedFiles.length > 0
        ? `${state.language === "en" ? "Saved." : "保存しました。"}\n${savedFiles.map((file) => `- ${file.path} (${file.size} bytes)`).join("\n")}`
        : saveError
          ? `\n\n${t("workspace.saveError")}: ${saveError}`
          : "";
      assistantMessage.content = requestOptions.codingMode && savedFiles.length > 0 ? savedNote : `${content}${savedNote}`;
      assistantMessage.sources = requestOptions.codingMode
        ? workspacePreviewSources({ root: state.workspaceRoot, files: savedFiles, label: t("chat.preview") })
        : [...attachmentSources, ...localSearchSources, ...codegraphSources, ...(normalizeSearchResults?.(streamSearchResults) || streamSearchResults)];
      assistantMessage.durationSeconds = durationSeconds;
      assistantMessage.runMeta = messageRunMeta(requestOptions, requestModel, runMetaOverrides);
      delete assistantMessage.streaming;
      return;
    }

    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Request failed");
    }
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    let content = friendlyUncertainAnswer(data.message.content || "");
    if (hasAttachmentFiles && hasReadableAttachments && attachmentAnswerLooksBroken(content)) {
      content = isAttachmentTranscriptRequest(text)
        ? directAttachmentTranscriptAnswer(attachmentResults, attachmentReplyOptions())
        : directAttachmentAnswer(attachmentResults, attachmentReplyOptions());
    }
    let savedFiles = [];
    let saveError = "";
    if (requestOptions.codingMode) {
      try {
        savedFiles = await autoSaveGeneratedFiles(text, content);
      } catch (error) {
        saveError = error.message;
      }
    }
    const savedNote = savedFiles.length > 0
      ? `${state.language === "en" ? "Saved." : "保存しました。"}\n${savedFiles.map((file) => `- ${file.path} (${file.size} bytes)`).join("\n")}`
      : saveError
        ? `\n\n${t("workspace.saveError")}: ${saveError}`
        : "";
    session.messages.push({
      role: "assistant",
      content: requestOptions.codingMode && savedFiles.length > 0 ? savedNote : `${content}${savedNote}`,
      sources: requestOptions.codingMode
        ? workspacePreviewSources({ root: state.workspaceRoot, files: savedFiles, label: t("chat.preview") })
        : [...attachmentSources, ...localSearchSources, ...codegraphSources, ...(searchResultsFromResponse?.(data) || [])],
      durationSeconds,
      runMeta: messageRunMeta(requestOptions, data.model || requestModel, runMetaOverrides),
    });
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    if (error.name === "AbortError") {
      if (assistantMessage) {
        assistantMessage.content = assistantMessage.content
          ? `${assistantMessage.content}\n\n${state.language === "en" ? "(Stopped)" : "（停止しました）"}`
          : (state.language === "en" ? "Stopped." : "停止しました。");
        assistantMessage.durationSeconds = durationSeconds;
        assistantMessage.runMeta = messageRunMeta(requestOptions, requestModel, runMetaOverrides);
        delete assistantMessage.streaming;
      } else {
        session.messages.push({
          role: "assistant",
          content: state.language === "en" ? "Stopped." : "停止しました。",
          durationSeconds,
          runMeta: messageRunMeta(requestOptions, requestModel, runMetaOverrides),
        });
      }
    } else if (assistantMessage) {
      assistantMessage.content = assistantMessage.content
        ? `${assistantMessage.content}\n\n${t("error.prefix")}: ${error.message}`
        : `${t("error.prefix")}: ${error.message}`;
      assistantMessage.durationSeconds = durationSeconds;
      assistantMessage.runMeta = messageRunMeta(requestOptions, requestModel, runMetaOverrides);
      delete assistantMessage.streaming;
    } else {
      session.messages.push({
        role: "assistant",
        content: `${t("error.prefix")}: ${error.message}`,
        durationSeconds,
        runMeta: messageRunMeta(requestOptions, requestModel, runMetaOverrides),
      });
    }
  } finally {
    if (appliedStudyPackModes.length > 0 && appliedStudyPackModes.every((value, index) => state.selectedStudyPackModes?.[index] === value)) {
      state.selectedStudyPackModes = [];
      state.selectedStudyPackMode = "";
    }
    state.abortController = null;
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
}

async function generateImageFromChat(text) {
  const prompt = extractImagePrompt(text);
  if (!prompt || state.busy) return false;
  let session = activeSession();
  if (!session) {
    newSession();
    session = activeSession();
  }

  const options = parseImageOptions(text);
  session.messages.push({ role: "user", content: text });
  updateSessionTitle(session, prompt);
  state.busy = true;
  startProgressTimer(t("progress.image"));
  saveSessions();
  render();

  try {
    const response = await fetch("/api/image/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        negative: "blurry, low quality, deformed, extra fingers, text, watermark",
        sampler: "euler",
        scheduler: "normal",
        width: options.width,
        height: options.height,
        steps: options.steps,
        cfg: options.cfg,
        seed: options.seed,
        enhance_prompt: true,
        free_after_generate: true,
        timeout: 900,
      }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "画像生成に失敗しました");
    }
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    session.messages.push({
      role: "assistant",
      content: t("image.generated"),
      generatedImages: data.images || [],
      imageMeta: data.meta || null,
      durationSeconds,
    });
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    session.messages.push({
      role: "assistant",
      content: `${t("error.prefix")}: ${error.message}`,
      durationSeconds,
    });
  } finally {
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
  return true;
}

async function addImages(files) {
  const incoming = [...files];
  const acceptedImages = incoming.filter((file) => file.type.startsWith("image/")).slice(0, 4 - state.pendingImages.length);
  const acceptedFiles = incoming.filter((file) => !file.type.startsWith("image/") && supportedAttachmentFile(file)).slice(0, 4 - state.pendingFiles.length);
  for (const file of acceptedImages) {
    const dataUrl = await readFileAsDataUrl(file);
    const base64 = dataUrl.split(",", 2)[1] || "";
    state.pendingImages.push({
      name: file.name,
      preview: dataUrl,
      base64,
    });
  }
  for (const file of acceptedFiles) {
    const dataUrl = await readFileAsDataUrl(file);
    const base64 = dataUrl.split(",", 2)[1] || "";
    state.pendingFiles.push({
      name: file.name,
      mime: file.type || "",
      kind: attachmentKind(file),
      size: file.size || 0,
      sizeLabel: workspaceFormatBytes(file.size || 0),
      base64,
    });
  }
  render();
}

async function addImagesFromClipboard(event) {
  const items = [...(event.clipboardData?.items || [])];
  const imageFiles = items
    .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean);
  if (imageFiles.length === 0) return;
  event.preventDefault();
  event.stopPropagation();
  await addImages(imageFiles);
}

async function addImagesFromDocumentPaste(event) {
  if (event.target === els.prompt) return;
  await addImagesFromClipboard(event);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("画像を読み込めませんでした"));
    reader.readAsDataURL(file);
  });
}

function startProgressTimer(label = t("progress.generating"), reason = "") {
  stopProgressTimer();
  state.progressLabel = label;
  state.progressReason = reason;
  state.progressElapsedSeconds = 0;
  state.startedAt = Date.now();
  updateProgressTimer();
  state.timerId = window.setInterval(updateProgressTimer, 1000);
}

function stopProgressTimer() {
  if (state.timerId) {
    window.clearInterval(state.timerId);
    state.timerId = null;
  }
  state.startedAt = 0;
  state.progressReason = "";
  state.progressElapsedSeconds = 0;
  els.progressLine.hidden = true;
}

function updateProgressTimer() {
  if (!state.startedAt) return;
  const elapsedSeconds = Math.floor((Date.now() - state.startedAt) / 1000);
  state.progressElapsedSeconds = elapsedSeconds;
  els.progressLine.hidden = false;
  const reason = state.progressReason ? ` / ${state.progressReason}` : "";
  els.progressText.textContent = state.language === "en"
    ? `${state.progressLabel}... ${elapsedSeconds}s${reason}`
    : `${state.progressLabel}... ${elapsedSeconds}秒${reason}`;
  if (state.busy) renderMessages();
}

function formatDuration(seconds) {
  return formatDurationValue(seconds, state.language);
}

async function handleWeatherRequest(text) {
  if (!isWeatherRequest(text)) return false;
  let session = activeSession();
  if (!session) {
    newSession();
    session = activeSession();
  }
  const location = weatherLocationFromText(text);
  session.messages.push({ role: "user", content: text });
  updateSessionTitle(session, text);
  state.busy = true;
  startProgressTimer(t("progress.weather"));
  saveSessions();
  render();
  try {
    const coordinates = weatherCoordinatesForRequest?.({
      text,
      savedLocation: state.weatherLocation,
    });
    const response = await fetch("/api/weather", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text, location, coordinates }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "天気を取得できませんでした");
    }
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    session.messages.push({
      role: "assistant",
      content: characterizeToolAnswer(data.answer, { type: "weather" }),
      sources: [{ title: "Open-Meteo", url: "https://open-meteo.com/" }],
      durationSeconds,
    });
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    session.messages.push({
      role: "assistant",
      content: `${t("error.prefix")}: ${error.message}`,
      durationSeconds,
    });
  } finally {
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
  return true;
}

function handleLocalUtilityRequest(text) {
  if (!isLocalDateTimeRequest(text)) return false;
  let session = activeSession();
  if (!session) {
    newSession();
    session = activeSession();
  }
  session.messages.push({ role: "user", content: text });
  updateSessionTitle(session, text);
  session.messages.push({
    role: "assistant",
    content: characterizeToolAnswer(localDateTimeAnswer(text), { type: "local" }),
    durationSeconds: 0,
  });
  saveSessions();
  render();
  return true;
}

async function pickWorkspaceFolder() {
  return window.GEMMA_WORKSPACE?.pickFolderAction?.({
    els,
    state,
    t,
    onSaveWorkspacePrefs: saveWorkspacePrefs,
    onLoadWorkspace: loadWorkspace,
  });
}

async function loadWorkspace() {
  return window.GEMMA_WORKSPACE?.loadWorkspaceAction?.({
    els,
    state,
    t,
    onSaveWorkspacePrefs: saveWorkspacePrefs,
    onRender: render,
  });
}

async function saveWorkspaceFile() {
  return window.GEMMA_WORKSPACE?.saveWorkspaceFileAction?.({
    els,
    state,
    t,
    onLoadWorkspace: loadWorkspace,
  });
}

async function revealWorkspacePath() {
  return window.GEMMA_WORKSPACE?.revealWorkspacePathAction?.({ els, state, t });
}

async function saveWorkspaceTranscript(action, button = null) {
  const root = action?.root || state.workspaceRoot;
  if (!action?.savePath || !action?.content || !root) return;
  const originalLabel = button?.textContent || "";
  if (button) {
    button.disabled = true;
    button.textContent = t("workspace.transcriptSaving");
  }
  try {
    const data = await writeWorkspaceFileApi({
      root,
      path: action.savePath,
      content: action.content,
    });
    if (root === state.workspaceRoot) {
      await loadWorkspace();
      state.selectedFiles.add(data.path);
      saveWorkspacePrefs();
    }
    const session = activeSession();
    if (session) {
      session.messages.push({
        role: "assistant",
        content: t("workspace.transcriptSavedMessage", {
          path: data.path,
          size: data.size,
        }),
        runMeta: {
          model: "local",
          modelLabel: state.language === "en" ? "Local save" : "ローカル保存",
          task: "workspace",
          taskLabel: state.language === "en" ? "Workspace" : "フォルダー操作",
          responseMode: "fast",
          responseModeLabel: t("mode.fast"),
        },
      });
      saveSessions();
      render();
    }
    if (button) {
      button.classList.add("saved-flash");
      button.textContent = t("workspace.transcriptSaved");
      window.setTimeout(() => {
        button.classList.remove("saved-flash");
        button.disabled = false;
        button.textContent = originalLabel || t("workspace.saveTranscript");
      }, 1400);
    }
  } catch (error) {
    if (button) {
      button.disabled = false;
      button.textContent = originalLabel || t("workspace.saveTranscript");
    }
    window.alert(`${t("workspace.saveError")}: ${error.message || error}`);
  }
}

async function handleSimpleTextSave(text) {
  const spec = inferWorkspaceSimpleTextSave({
    text,
    hasWorkspace: Boolean(state.workspaceRoot),
  });
  if (!spec) return false;
  let session = activeSession();
  if (!session) {
    newSession();
    session = activeSession();
  }
  session.messages.push({ role: "user", content: text });
  updateSessionTitle(session, text);
  state.busy = true;
  startProgressTimer(t("progress.saving"));
  saveSessions();
  render();
  try {
    const data = await writeWorkspaceFileApi({
      root: state.workspaceRoot,
      path: spec.path,
      content: spec.content,
    }).catch((error) => {
      throw new Error(error.message || "ファイルを保存できませんでした");
    });
    await loadWorkspace();
    state.selectedFiles.add(data.path);
    saveWorkspacePrefs();
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    session.messages.push({
      role: "assistant",
      content: `${data.path} を保存しました（${data.size}バイト）。`,
      durationSeconds,
      runMeta: {
        model: "local",
        modelLabel: state.language === "en" ? "Local save" : "ローカル保存",
        task: "coding",
        taskLabel: t("task.coding"),
        responseMode: "fast",
        responseModeLabel: t("mode.fast"),
      },
    });
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    session.messages.push({
      role: "assistant",
      content: `${t("error.prefix")}: ${error.message}`,
      durationSeconds,
    });
  } finally {
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
  return true;
}

async function autoSaveGeneratedFiles(commandText, assistantText) {
  if (!state.workspaceRoot) return [];
  if (isTranslationRequest(commandText)) return [];
  const blocks = extractCodeBlocks(assistantText).filter((block) => block.content.trim());
  if (blocks.length === 0) return [];
  if (blocks.some((block) => !block.complete)) {
    throw new Error("コードが途中で終わったため保存しませんでした。もう一度生成してください。");
  }

  const savedFiles = [];
  const usedPaths = new Set();
  for (const block of blocks) {
    const inferredPath = inferWorkspaceSavePath({
      commandText,
      assistantText,
      codeBlock: block,
      currentPath: "",
    });
    if (!inferredPath) continue;
    const path = uniquePath(inferredPath, usedPaths);
    usedPaths.add(path);
    const data = await writeWorkspaceFileApi({
      root: state.workspaceRoot,
      path,
      content: block.content,
    }).catch((error) => {
      throw new Error(error.message || `${path} を保存できませんでした`);
    });
    savedFiles.push({ path: data.path, size: data.size });
  }

  if (savedFiles.length > 0) {
    await loadWorkspace();
    for (const file of savedFiles) {
      state.selectedFiles.add(file.path);
    }
    saveWorkspacePrefs();
  }
  return savedFiles;
}

async function handleSaveCommand(text) {
  const session = activeSession();
  if (isTranslationRequest(text)) return false;
  if (!session || !state.workspaceRoot || !isSaveCommand(text)) return false;

  const assistant = lastAssistantMessage(session);
  const blocks = extractCodeBlocks(assistant?.content || "");
  if (blocks.length === 0) return false;

  const block = blocks[blocks.length - 1];
  const path = inferWorkspaceSavePath({
    commandText: text,
    assistantText: assistant.content,
    codeBlock: block,
    currentPath: els.writePath.value.trim(),
  });
  session.messages.push({ role: "user", content: text });
  updateSessionTitle(session, text);

  if (!path) {
    els.writeContent.value = block.content;
    state.workspaceOpen = true;
    session.messages.push({
      role: "assistant",
      content: t("workspace.cannotInferSavePath"),
      durationSeconds: 0,
    });
    saveSessions();
    render();
    return true;
  }

  state.busy = true;
  startProgressTimer(t("progress.saving"));
  saveSessions();
  render();

  try {
    const data = await writeWorkspaceFileApi({
      root: state.workspaceRoot,
      path,
      content: block.content,
    }).catch((error) => {
      throw new Error(error.message || "ファイルを保存できませんでした");
    });
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    els.writePath.value = data.path;
    els.writeContent.value = block.content;
    session.messages.push({
      role: "assistant",
      content: t("workspace.savedTo", { path: data.path, size: data.size }),
      sources: workspacePreviewSources({
        root: state.workspaceRoot,
        files: [{ path: data.path, size: data.size }],
        label: t("chat.preview"),
      }),
      durationSeconds,
    });
    await loadWorkspace();
    state.selectedFiles.add(data.path);
    saveWorkspacePrefs();
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    session.messages.push({
      role: "assistant",
      content: `${t("workspace.saveError")}: ${error.message}`,
      durationSeconds,
    });
  } finally {
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
  return true;
}

els.composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = els.prompt.value.trim();
  if ((!text && state.pendingImages.length === 0 && state.pendingFiles.length === 0) || state.busy) return;
  els.prompt.value = "";
  resizePrompt();
  const hasPendingMedia = state.pendingImages.length > 0 || state.pendingFiles.length > 0;
  if (hasPendingMedia) {
    sendMessage(text || (state.pendingFiles.length > 0 ? (state.language === "en" ? "Read the attached file." : "添付ファイルを読んでください。") : (state.language === "en" ? "Describe this image." : "この画像を説明してください。")));
    return;
  }
  const previousAttachment = lastReadableAttachment(activeSession());
  const previousAttachmentReference = previousAttachment || lastAttachmentReference(activeSession());
  const shouldPreferAttachmentFollowup = previousAttachmentReference && isAttachmentFollowupRequest(text, attachmentReplyOptions());
  if (!shouldPreferAttachmentFollowup && await handleWorkspaceSourceFollowup(text)) return;
  const intent = window.GEMMA_ROUTER.classifySubmitIntent({
    text,
    hasImages: state.pendingImages.length > 0,
    isLocalUtilityRequest: (value) => isLocalDateTimeRequest(value),
    isWeatherRequest,
    isTranslationRequest,
    isImageGenerationRequest,
    isSimpleTextSaveRequest: (value) => Boolean(inferWorkspaceSimpleTextSave({
      text: value,
      hasWorkspace: Boolean(state.workspaceRoot),
    })),
    isSaveCommandRequest: (value) => Boolean(activeSession() && state.workspaceRoot && isSaveCommand(value)),
    isWorkspaceBuildRequest,
  });
  if (intent === "local" && handleLocalUtilityRequest(text)) return;
  if (intent === "weather" && (await handleWeatherRequest(text))) return;
  if (intent === "translation") {
    sendMessage(text);
    return;
  }
  if (intent === "image") {
    await generateImageFromChat(text);
    return;
  }
  if (intent === "simple-save" && (await handleSimpleTextSave(text))) return;
  if (intent === "save-command" && (await handleSaveCommand(text))) return;
  if (intent === "workspace-build") {
    await handleWorkspaceBuild(text);
    return;
  }
  sendMessage(text || (state.pendingFiles.length > 0 ? (state.language === "en" ? "Read the attached file." : "添付ファイルを読んでください。") : (state.language === "en" ? "Describe this image." : "この画像を説明してください。")));
});

els.stop.addEventListener("click", () => {
  if (!state.abortController) return;
  state.progressLabel = t("progress.stopping");
  updateProgressTimer();
  state.abortController.abort();
});

function setupManagementPanels() {
  window.GEMMA_MANAGEMENT?.setupManagementPanels?.({
    els,
    renderStudyPacksPanel,
    renderPluginsPanel,
  });
}

function renderStudyPacksPanel() {
  window.GEMMA_MANAGEMENT?.renderStudyPacksPanel?.({ state, t });
}

function renderPluginsPanel() {
  window.GEMMA_MANAGEMENT?.renderPluginsPanel?.({ state, els, t });
}

els.trainingExport?.addEventListener("click", exportTrainingData);
els.trainingSetCreate?.addEventListener("click", () => {
  const set = createTrainingSet(els.trainingSetName?.value || "");
  const folder = activeFolder();
  if (folder && !folder.trainingSetId) {
    folder.trainingSetId = set.id;
    saveFolders();
  }
  if (els.trainingSetName) els.trainingSetName.value = "";
  if (els.trainingStatus) els.trainingStatus.textContent = t("settings.trainingSetCreated", { name: set.name });
  render();
});
els.trainingSetSelect?.addEventListener("change", () => setActiveTrainingSet(els.trainingSetSelect.value));
els.trainingSetRename?.addEventListener("click", renameActiveTrainingSet);
els.trainingSetDelete?.addEventListener("click", deleteActiveTrainingSet);
els.systemPromptTemplate?.addEventListener("change", () => applySystemPromptTemplate(els.systemPromptTemplate.value));
els.systemPrompt?.addEventListener("input", () => {
  syncSystemPromptTemplate();
  saveSystemPromptSetting();
});
[
  [els.temperature, AUTO_SAVE_SETTING_KEYS.temperature],
  [els.topP, AUTO_SAVE_SETTING_KEYS.topP],
  [els.topK, AUTO_SAVE_SETTING_KEYS.topK],
  [els.numPredict, AUTO_SAVE_SETTING_KEYS.numPredict],
  [els.numCtx, AUTO_SAVE_SETTING_KEYS.numCtx],
  [els.historyTurns, AUTO_SAVE_SETTING_KEYS.historyTurns],
].forEach(([select, storageKey]) => {
  select?.addEventListener("change", () => saveSelectSetting(select, storageKey));
});
els.trainingExampleList?.addEventListener("click", (event) => {
  const button = event.target.closest(".training-example-save");
  if (!button?.dataset.exampleId) return;
  saveTrainingExampleEdit(button.dataset.exampleId, button);
});
els.workspaceTrainingSet?.addEventListener("change", () => applyTrainingSetToActiveFolder(els.workspaceTrainingSet.value));
els.workspaceCodegraphEnabled?.addEventListener("change", () => applyCodegraphToActiveFolder(els.workspaceCodegraphEnabled.checked));
els.workspaceCodegraphPrepare?.addEventListener("click", prepareCodegraphForActiveFolder);
els.workspaceSearchRun?.addEventListener("click", () => window.GEMMA_WORKSPACE?.searchWorkspaceAction?.({ els, state, t }));
els.workspaceSearchQuery?.addEventListener("input", () => {
  if (els.workspaceSearchStatus) delete els.workspaceSearchStatus.dataset.searchState;
  if (els.workspaceSearchResults) {
    els.workspaceSearchResults.hidden = true;
    els.workspaceSearchResults.innerHTML = "";
  }
  renderWorkspace();
});
els.workspaceSearchQuery?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  window.GEMMA_WORKSPACE?.searchWorkspaceAction?.({ els, state, t });
});
els.workspaceSearchResults?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-workspace-search-path]");
  if (!button) return;
  openWorkspaceSource({
    type: "workspace",
    path: button.dataset.workspaceSearchPath || "",
    line: button.dataset.workspaceSearchLine || "",
    snippet: button.querySelector("small")?.textContent || "",
  });
});
els.workspacePreviewSearch?.addEventListener("input", () => {
  state.workspacePreviewSearchIndex = 0;
  updateWorkspacePreviewSearch();
});
els.workspacePreviewSearch?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  updateWorkspacePreviewSearch({ jump: true, direction: event.shiftKey ? -1 : 1 });
});
els.workspacePreviewPrev?.addEventListener("click", () => updateWorkspacePreviewSearch({ jump: true, direction: -1 }));
els.workspacePreviewNext?.addEventListener("click", () => updateWorkspacePreviewSearch({ jump: true, direction: 1 }));
els.correctionClose?.addEventListener("click", closeCorrectionDialog);
els.correctionCancel?.addEventListener("click", closeCorrectionDialog);
els.correctionSave?.addEventListener("click", saveCorrectionDraft);
els.correctionModal?.addEventListener("click", (event) => {
  if (event.target === els.correctionModal) closeCorrectionDialog();
});
els.correctionText?.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeCorrectionDialog();
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    saveCorrectionDraft();
  }
});
els.characterSave?.addEventListener("click", saveCharacterSettings);
els.characterName?.addEventListener("input", () => {
  state.character.name = els.characterName.value || "Gemma";
  renderCharacterPreview();
});
els.characterUserName?.addEventListener("input", () => {
  state.character.userName = els.characterUserName.value || "";
  renderCharacterPreview();
});
els.characterSelfName?.addEventListener("input", () => {
  state.character.selfName = els.characterSelfName.value || "";
  renderCharacterPreview();
});
els.characterGender?.addEventListener("change", () => {
  state.character.gender = els.characterGender.value || "unspecified";
});
els.characterMemoryModeChoices?.forEach((input) => {
  input.addEventListener("change", () => {
    if (!input.checked) return;
    state.character.memoryMode = input.value;
    if (els.characterMemoryMode) els.characterMemoryMode.value = input.value;
  });
});
els.characterAvatarPick?.addEventListener("click", pickCharacterAvatarFile);
els.characterAvatarClear?.addEventListener("click", clearCharacterAvatar);
els.characterAvatarFile?.addEventListener("change", handleCharacterAvatarFileChange);
els.characterMemoryAdd?.addEventListener("click", addManualCharacterMemory);
els.characterMemoryFilters?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-memory-filter]");
  if (!button?.dataset.memoryFilter) return;
  state.characterMemoryFilter = button.dataset.memoryFilter;
  renderCharacterMemoryList();
});
els.characterMemorySearch?.addEventListener("input", () => {
  state.characterMemoryQuery = els.characterMemorySearch?.value || "";
  renderCharacterMemoryList();
});
els.characterMemoryList?.addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-memory-edit]");
  if (editButton?.dataset.memoryEdit) {
    const item = editButton.closest("[data-memory-id]");
    const editArea = item?.querySelector(".character-memory-edit");
    if (editArea) editArea.hidden = false;
    return;
  }
  const cancelButton = event.target.closest("[data-memory-cancel]");
  if (cancelButton?.dataset.memoryCancel) {
    const item = cancelButton.closest("[data-memory-id]");
    const editArea = item?.querySelector(".character-memory-edit");
    if (editArea) editArea.hidden = true;
    return;
  }
  const saveButton = event.target.closest("[data-memory-save]");
  if (saveButton?.dataset.memorySave) {
    saveCharacterMemoryEdit(saveButton.dataset.memorySave, saveButton);
    return;
  }
  const deleteButton = event.target.closest("[data-memory-delete]");
  if (deleteButton?.dataset.memoryDelete) {
    deleteCharacterMemory(deleteButton.dataset.memoryDelete);
  }
});
els.memoryCandidateClose?.addEventListener("click", closeMemoryCandidate);
els.memoryCandidateDiscard?.addEventListener("click", closeMemoryCandidate);
els.memoryCandidateSave?.addEventListener("click", saveMemoryCandidate);
els.memoryCandidateModal?.addEventListener("click", (event) => {
  if (event.target === els.memoryCandidateModal) closeMemoryCandidate();
});
els.memoryCandidateText?.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMemoryCandidate();
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    saveMemoryCandidate();
  }
});

function resizePrompt() {
  resizePromptView({ els });
}

bindComposerEvents({
  els,
  getEnterToSend: () => state.enterToSend,
  onResize: resizePrompt,
  onAddImages: addImages,
  onPromptPaste: addImagesFromClipboard,
  onDocumentPaste: addImagesFromDocumentPaste,
});

bindAsrUi?.({
  els,
  t,
  onResize: resizePrompt,
  getSelectedModel: () => state.asrModel || state.asrStatus?.recommendedModel || "",
  getMicGain: () => state.micGain,
  getMicDeviceId: () => state.micDeviceId,
  getPartialIntervalSeconds: () => state.partialIntervalSeconds,
  getPartialMode: () => state.partialMode,
});

window.GEMMA_SIDEBAR?.bindSidebarEvents?.({
  els,
  state,
  onRender: render,
});
els.undoDelete.addEventListener("click", restoreLastDeleted);
els.undoClose.addEventListener("click", hideUndo);

els.newFolder.addEventListener("click", async () => {
  createFolder(t("folder.new"));
  newSession();
  startFolderRename(activeFolder());
  render();
});

els.clearChat.addEventListener("click", () => {
  const session = activeSession();
  if (!session) return;
  session.messages = [];
  session.title = t("chat.new");
  saveSessions();
  render();
});

els.webSearchToggle.addEventListener("click", () => {
  toggleWebSearch(state);
  render();
});

els.workspaceClose.addEventListener("click", () => {
  state.workspaceOpen = false;
  render();
});

els.workspaceFolderTitle.addEventListener("blur", saveActiveFolderTitle);
els.workspaceFolderTitle.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    saveActiveFolderTitle();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  window.GEMMA_MANAGEMENT?.handleEscapeKey?.({ els, state, onRender: render });
});

els.workspacePick.addEventListener("click", pickWorkspaceFolder);
els.workspaceLoad.addEventListener("click", loadWorkspace);
els.writeFile.addEventListener("click", saveWorkspaceFile);
els.revealPath?.addEventListener("click", revealWorkspacePath);
els.weatherLocationUse?.addEventListener("click", useBrowserWeatherLocation);

window.GEMMA_MANAGEMENT?.bindManagementEvents?.({
  els,
  state,
  t,
  onOpenCharacter: renderCharacterPanel,
  onOpenSettings: (target = "") => {
    renderSettingsMeta();
    renderAsrSettingsPanel();
    const asrVisible = !els.settingsPanel.hidden || !els.asrPanel?.hidden;
    if (asrVisible) refreshAsrStatus();
    if (asrVisible) refreshAsrSetupStatus();
    if (asrVisible) refreshMicDevices();
    renderWeatherLocationStatus();
    if (target === "external-llm") {
      window.requestAnimationFrame(() => els.externalLlmSettings?.scrollIntoView({ block: "center" }));
    }
    if (target === "asr") {
      window.requestAnimationFrame(() => els.asrSettings?.scrollIntoView({ block: "center" }));
    }
  },
  onOpenWorkspace: openWorkspaceForPlugin,
  onMobileImport: importMobileChatJson,
  onMobilePendingImport: importPendingMobileChats,
  onPluginsChanged: render,
});

els.modelInstaller.addEventListener("click", (event) => {
  const button = event.target.closest("[data-model-pull]");
  if (!button) return;
  startModelPull(button.dataset.modelPull);
});
els.externalLlmUrl?.addEventListener("change", () => setExternalLlmUrl(els.externalLlmUrl.value));
els.externalLlmCheck?.addEventListener("click", checkExternalLlmServer);
els.externalLlmClear?.addEventListener("click", clearExternalLlmSettings);
els.externalLlmCopyModel?.addEventListener("click", copyExternalLlmModelName);
els.asrSettings?.addEventListener("click", (event) => {
  const refreshButton = event.target.closest("[data-asr-refresh]");
  if (refreshButton) {
    refreshAsrStatus();
    refreshAsrSetupStatus();
    return;
  }
  const setupButton = event.target.closest("[data-asr-setup]");
  if (setupButton) {
    startAsrSetup();
    return;
  }
  const micCheckButton = event.target.closest("[data-asr-mic-check]");
  if (micCheckButton) refreshMicDevices({ startMonitor: true });
  const micStopButton = event.target.closest("[data-asr-stop-mic]");
  if (micStopButton) {
    stopMicLevelPreview();
    return;
  }
  const openMicSettingsButton = event.target.closest("[data-asr-open-mic-settings]");
  if (openMicSettingsButton) {
    window.open(window.GEMMA_ASR?.CHROME_MIC_SETTINGS_URL || "chrome://settings/content/microphone", "_blank");
    setMicLevelMessage(t("settings.asrMicSettingsOpened"));
    return;
  }
  const copyMicSettingsButton = event.target.closest("[data-asr-copy-mic-settings]");
  if (copyMicSettingsButton) {
    const url = window.GEMMA_ASR?.CHROME_MIC_SETTINGS_URL || "chrome://settings/content/microphone";
    navigator.clipboard?.writeText(url)
      .then(() => setMicLevelMessage(t("settings.asrMicSettingsCopied")))
      .catch(() => setMicLevelMessage(t("settings.asrMicSettingsCopyFallback", { url })));
  }
});
els.asrSettings?.addEventListener("change", (event) => {
  const select = event.target.closest("[data-asr-model]");
  if (select) {
    setAsrModel(select.value);
    return;
  }
  const gain = event.target.closest("[data-asr-mic-gain]");
  if (gain) {
    setMicGain(gain.value, { render: false });
    if (stopMicLevelMonitor) startMicLevelPreview();
    return;
  }
  const device = event.target.closest("[data-asr-mic-device]");
  if (device) {
    setMicDevice(device.value);
    startMicLevelPreview();
    return;
  }
  const partialInterval = event.target.closest("[data-asr-partial-interval]");
  if (partialInterval) {
    setPartialIntervalSeconds(partialInterval.value);
    return;
  }
  const partialMode = event.target.closest("[data-asr-partial-mode]");
  if (partialMode) {
    setPartialMode(partialMode.value);
  }
});
els.asrSettings?.addEventListener("input", (event) => {
  const gain = event.target.closest("[data-asr-mic-gain]");
  if (!gain) return;
  setMicGain(gain.value, { render: false });
});

window.GEMMA_SETTINGS?.bindSettingsEvents?.({
  els,
  onThemeChange: setTheme,
  onLanguageChange: setLanguageFromControl,
  onResponseModeChange: setResponseMode,
  onComposerModelChange: setComposerModel,
  onThinkingModeChange: setThinkingMode,
  onModelOverrideChange: (task, value) => {
    setModelOverride(task, value);
    renderSettingsMeta();
    if (task !== "translation") renderMessages();
  },
  onEnterToSendChange: setEnterToSend,
});

ensureFolderData();
syncWorkspaceFromActiveFolder();
setupManagementPanels();
moveSettingsSections();
state.language = I18N[state.language] ? state.language : "ja";
restoreAutoSavedSettings();
applyI18n();
renderStudyPacksPanel();
renderPluginsPanel();
if (els.systemPrompt && allSystemPromptTemplateTexts().includes(els.systemPrompt.value)) {
  const templateId = detectSystemPromptTemplate(els.systemPrompt.value);
  els.systemPrompt.value = systemPromptTemplateText(templateId, state.language);
}
syncSystemPromptTemplate();
setTheme(state.theme);
setResponseMode(state.responseMode);
setThinkingMode(state.thinkingMode);
syncModelInputs();
renderSettingsMeta();
renderAsrSettingsPanel();
renderWeatherLocationStatus();
setEnterToSend(state.enterToSend);
resizePrompt();
refreshAsrStatus();
refreshAsrSetupStatus();

if (state.folders.length > 0 && sessionsForActiveFolder().length === 0) {
  newSession();
} else {
  selectFirstSessionInActiveFolder();
  render();
}

if (state.workspaceRoot) loadWorkspace();

checkHealth();
openInitialManagementPanelFromUrl();
setInterval(checkHealth, 10000);
