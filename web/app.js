const state = {
  folders: loadFolders(),
  sessions: loadSessions(),
  activeId: null,
  activeFolderId: localStorage.getItem("gemma4.activeFolderId") || null,
  busy: false,
  webSearch: false,
  startedAt: 0,
  timerId: null,
  abortController: null,
  progressLabel: "生成中",
  progressElapsedSeconds: 0,
  workspaceOpen: false,
  workspaceRoot: "",
  workspaceFiles: [],
  workspaceNote: "",
  selectedFiles: new Set(),
  editingFolderId: null,
  editingSessionId: null,
  sidebarQuery: "",
  sidebarHidden: localStorage.getItem("gemma4.sidebarHidden") === "true",
  sidebarWidth: Number(localStorage.getItem("gemma4.sidebarWidth")) || 268,
  language: localStorage.getItem("gemma4.language") || "ja",
  theme: localStorage.getItem("gemma4.theme") || "dark",
  responseMode: localStorage.getItem("gemma4.responseMode") || "auto",
  thinkingMode: localStorage.getItem("gemma4.thinkingMode") || "auto",
  modelOverrides: {
    chat: localStorage.getItem("gemma4.model.chat") || "",
    coding: localStorage.getItem("gemma4.model.coding") || "",
    translation: localStorage.getItem("gemma4.model.translation") || "",
  },
  composerModel: localStorage.getItem("gemma4.composerModel") || "",
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
  },
  enterToSend: localStorage.getItem("gemma4.enterToSend") === "true",
  lastDeleted: null,
  pendingImages: [],
};

const WORKSPACE_PLAN_TIMEOUT_MS = 120000;
const WORKSPACE_FILE_TIMEOUT_MS = 300000;
const SIMPLE_WORKSPACE_FILE_TIMEOUT_MS = 120000;

const SYSTEM_PROMPTS = {
  ja: "あなたは簡潔で有用なアシスタントです。前置きなしで自然に短く答えてください。箇条書きは、比較・手順・整理が必要な場合だけ使ってください。",
  en: "You are a concise and helpful assistant. Answer directly and naturally. Use bullet points only when comparison, steps, or structured explanation are useful.",
};

const I18N = {
  ja: {
    "brand.subtitle": "12B ローカル",
    "common.close": "閉じる",
    "common.settings": "設定",
    "common.send": "送信",
    "common.stop": "停止",
    "common.undo": "元に戻す",
    "sidebar.folderButton": "フォルダー",
    "sidebar.search": "検索",
    "sidebar.searchPlaceholder": "フォルダー / チャットを検索",
    "sidebar.treeTitle": "フォルダーとチャット",
    "sidebar.show": "サイドバーを表示",
    "sidebar.hide": "サイドバーを隠す",
    "sidebar.showShort": "サイドバー",
    "top.webSearch": "Web検索",
    "top.webSearchTitle": "Web検索を使う",
    "top.clear": "クリア",
    "top.clearTitle": "チャットをクリア",
    "settings.description": "応答の速さ、精度、文脈量を調整します。",
    "settings.versionChecking": "バージョン確認中",
    "settings.language": "表示言語",
    "settings.languageHelp": "UIの表示言語を切り替えます。会話内容や保存済みの名前は変更しません。",
    "settings.theme": "テーマ",
    "settings.themeHelp": "画面の配色を切り替えます。",
    "settings.responseMode": "応答モード",
    "settings.responseModeHelp": "高速は短文向け、精度優先は設計や調査向けです。自動では内容で切り替えます。",
    "settings.thinking": "思考量",
    "settings.thinkingHelp": "コード作成や修正では深めにすると破綻しにくくなりますが、時間は増えます。",
    "settings.chatModel": "通常チャットモデル",
    "settings.chatModelHelp": "迷ったらサーバー既定かGemma 4。速さ優先ならQwenを選びます。",
    "settings.codingModel": "コード生成モデル",
    "settings.codingModelHelp": "フォルダー作業用です。複雑なコードはGemma 4 Coder推奨。要ダウンロード表示なら先に取得が必要です。",
    "settings.translationModel": "翻訳モデル",
    "settings.translationModelHelp": "通常はサーバー自動で十分です。速さはQwen、高品質はGemma 4です。",
    "settings.systemPrompt": "システム指示",
    "settings.systemPromptHelp": "全ての返信に共通して効く基本ルールです。長くすると応答が少し重くなります。",
    "settings.temperature": "温度",
    "settings.temperatureHelp": "低いほど安定、高いほど表現に幅が出ます。",
    "settings.topPHelp": "候補語の広がりを確率で絞ります。通常は0.8〜0.95で十分です。",
    "settings.topKHelp": "候補語の数を制限します。小さいほど安定しやすくなります。",
    "settings.maxTokens": "最大トークン",
    "settings.maxTokensHelp": "1回の返信で生成できる長さです。コード生成では自動で増やします。",
    "settings.context": "コンテキスト",
    "settings.contextHelp": "モデルが一度に見られる文脈量です。大きいほど重くなります。",
    "settings.historyTurns": "記憶ターン",
    "settings.historyTurnsHelp": "過去の会話を何往復ぶん送るかです。増やすと文脈は保てますが遅くなります。",
    "settings.enterToSend": "Enterで送信",
    "settings.enterToSendHelp": "OFFではEnterは改行です。送信は↑ボタン、またはCmd/Ctrl + Enterを使います。日本語変換中は送信しません。",
    "settings.modelDownload": "モデルをダウンロード",
    "theme.dark": "ダーク",
    "theme.light": "ライト",
    "theme.green": "グリーン",
    "mode.auto": "自動",
    "mode.fast": "高速",
    "mode.balanced": "標準",
    "mode.quality": "精度優先",
    "mode.qualityShort": "精度",
    "thinking.low": "軽め",
    "thinking.high": "深く",
    "model.auto": "モデル自動",
    "model.serverDefault": "サーバー既定",
    "model.serverAuto": "サーバー自動",
    "model.missing": "未取得",
    "model.downloadRequired": "要ダウンロード",
    "model.installed": "取得済み",
    "model.downloading": "取得中",
    "model.download": "ダウンロード",
    "model.gemmaStandard": "推奨・標準",
    "model.gemmaCoding": "標準・すぐ使える",
    "model.gemmaTranslation": "高品質・遅め",
    "model.qwenFast": "高速・軽い",
    "model.qwenTranslation": "翻訳推奨・高速",
    "model.coderRecommended": "コード推奨",
    "task.chat": "チャット",
    "task.coding": "コード生成",
    "task.translation": "翻訳",
    "workspace.editFolder": "フォルダー編集",
    "workspace.selectedFolder": "選択中フォルダー",
    "workspace.noFolder": "フォルダー未選択",
    "workspace.folderName": "フォルダー名",
    "workspace.localFolder": "参照するローカルフォルダー",
    "workspace.pickFolderPlaceholder": "フォルダーを選択してください",
    "workspace.pickFolder": "フォルダーを選択",
    "workspace.reload": "再読込",
    "workspace.notConfigured": "{name} のローカルアクセスは未設定です。",
    "workspace.loaded": "{name}: {files}件のファイルを読み込み、{selected}件を文脈に追加中。",
    "workspace.empty": "このフォルダーは空です。生成したファイルはここへ保存できます。",
    "workspace.binary": " バイナリ/大容量",
    "workspace.savePath": "保存先ファイル",
    "workspace.writePlaceholder": "生成されたコードを貼り付けてから保存してください。",
    "workspace.saveFile": "ファイルを保存",
    "workspace.waitingPick": "フォルダー選択を待機中...",
    "workspace.loading": "フォルダーを読み込み中...",
    "workspace.saved": "{path} を保存しました（{size}バイト）。",
    "workspace.saveError": "保存エラー",
    "workspace.savedTo": "{path} に保存しました（{size}バイト）。",
    "workspace.cannotInferSavePath": "保存先ファイル名が判断できませんでした。保存欄にコードを入れました。保存先ファイルを入力して「ファイルを保存」を押してください。",
    "composer.attachImage": "画像を添付",
    "composer.removeAttachment": "添付を削除",
    "composer.attachedImage": "添付画像",
    "image.generated": "画像を生成しました。",
    "composer.placeholder": "Gemma 4 12B に送信。例: 赤いリンゴの画像を生成して",
    "composer.model": "使用モデル",
    "chat.new": "新規チャット",
    "chat.emptySubtitle": "Ollama経由のローカルチャット",
    "chat.you": "あなた",
    "chat.generatingRole": "Gemma ・ 生成中",
    "chat.generating": "生成中",
    "chat.streamingStatus": "{label} ・ {seconds}秒 ・ 順次表示中 ・ ■ で停止",
    "chat.duration": "所要時間",
    "chat.model": "モデル",
    "chat.task": "用途",
    "chat.mode": "モード",
    "chat.preview": "動作確認",
    "folder.new": "新規フォルダー",
    "folder.default": "既定フォルダー",
    "folder.untitled": "名称未設定",
    "folder.none": "フォルダーなし",
    "folder.localReady": "ローカル設定済み",
    "folder.localMissing": "ローカル未設定",
    "folder.add": "追加",
    "folder.addTitle": "このフォルダーにチャットを追加",
    "folder.edit": "編集",
    "folder.editTitle": "フォルダー名を変更",
    "folder.delete": "削除",
    "folder.deleteTitle": "フォルダーを削除",
    "folder.deleteConfirm": "「{name}」と中のチャット{count}件を削除しますか？",
    "chat.editTitle": "チャット名を変更",
    "chat.deleteTitle": "チャットを削除",
    "chat.none": "チャットなし",
    "chat.deleteConfirm": "「{name}」を削除しますか？",
    "undo.deleted": "{target}「{label}」を削除しました。",
    "status.checking": "確認中",
    "status.available": "使用可能",
    "status.codingMissing": "コード用モデル未取得",
    "status.modelMissing": "モデル未取得",
    "status.offline": "オフライン",
    "progress.generating": "生成中",
    "progress.fast": "高速生成中",
    "progress.quality": "精度優先で生成中",
    "progress.lightweight": "軽量モデルで生成中",
    "progress.translation": "翻訳中",
    "progress.coding": "コード生成中",
    "progress.search": "検索 + 生成中",
    "progress.workspace": "生成・検証中",
    "progress.image": "画像生成中",
    "progress.weather": "天気取得中",
    "progress.saving": "保存中",
    "progress.stopping": "停止中",
    "error.prefix": "エラー",
  },
  en: {
    "brand.subtitle": "12B local",
    "common.close": "Close",
    "common.settings": "Settings",
    "common.send": "Send",
    "common.stop": "Stop",
    "common.undo": "Undo",
    "sidebar.folderButton": "Folder",
    "sidebar.search": "Search",
    "sidebar.searchPlaceholder": "Search folders / chats",
    "sidebar.treeTitle": "Folders and chats",
    "sidebar.show": "Show sidebar",
    "sidebar.hide": "Hide sidebar",
    "sidebar.showShort": "Sidebar",
    "top.webSearch": "Web",
    "top.webSearchTitle": "Use web search",
    "top.clear": "Clear",
    "top.clearTitle": "Clear chat",
    "settings.description": "Tune response speed, accuracy, and context size.",
    "settings.versionChecking": "Checking version",
    "settings.language": "Display language",
    "settings.languageHelp": "Changes the UI language. Chat content and saved names are not translated.",
    "settings.theme": "Theme",
    "settings.themeHelp": "Switch the screen color theme.",
    "settings.responseMode": "Response mode",
    "settings.responseModeHelp": "Fast is for short replies; quality is for design and research. Auto switches by request.",
    "settings.thinking": "Reasoning effort",
    "settings.thinkingHelp": "Deeper is safer for coding and edits, but takes longer.",
    "settings.chatModel": "Chat model",
    "settings.chatModelHelp": "Use server default or Gemma 4 when unsure. Pick Qwen for speed.",
    "settings.codingModel": "Coding model",
    "settings.codingModelHelp": "Used for folder work. Gemma 4 Coder is recommended for complex code. Download it first if marked required.",
    "settings.translationModel": "Translation model",
    "settings.translationModelHelp": "Server auto is usually enough. Qwen is faster; Gemma 4 is higher quality.",
    "settings.systemPrompt": "System prompt",
    "settings.systemPromptHelp": "Base rules applied to every reply. Longer prompts can slow responses slightly.",
    "settings.temperature": "Temperature",
    "settings.temperatureHelp": "Lower is more stable; higher gives more variation.",
    "settings.topPHelp": "Limits candidate token spread by probability. 0.8-0.95 is usually enough.",
    "settings.topKHelp": "Limits the number of candidate tokens. Lower is more stable.",
    "settings.maxTokens": "Max tokens",
    "settings.maxTokensHelp": "Maximum length for one reply. Coding raises this automatically.",
    "settings.context": "Context",
    "settings.contextHelp": "How much context the model can see at once. Larger is heavier.",
    "settings.historyTurns": "History turns",
    "settings.historyTurnsHelp": "How many previous turns to send. More preserves context but slows down.",
    "settings.enterToSend": "Enter to send",
    "settings.enterToSendHelp": "Off means Enter inserts a newline. Use ↑ or Cmd/Ctrl + Enter to send. IME confirmation will not send.",
    "settings.modelDownload": "Download models",
    "theme.dark": "Dark",
    "theme.light": "Light",
    "theme.green": "Green",
    "mode.auto": "Auto",
    "mode.fast": "Fast",
    "mode.balanced": "Standard",
    "mode.quality": "Quality",
    "mode.qualityShort": "Quality",
    "thinking.low": "Light",
    "thinking.high": "Deep",
    "model.auto": "Model auto",
    "model.serverDefault": "Server default",
    "model.serverAuto": "Server auto",
    "model.missing": "not installed",
    "model.downloadRequired": "download required",
    "model.installed": "Installed",
    "model.downloading": "Downloading",
    "model.download": "Download",
    "model.gemmaStandard": "recommended standard",
    "model.gemmaCoding": "standard, ready to use",
    "model.gemmaTranslation": "higher quality, slower",
    "model.qwenFast": "fast and light",
    "model.qwenTranslation": "translation recommended, fast",
    "model.coderRecommended": "recommended for code",
    "task.chat": "Chat",
    "task.coding": "Coding",
    "task.translation": "Translation",
    "workspace.editFolder": "Folder settings",
    "workspace.selectedFolder": "Selected folder",
    "workspace.noFolder": "No folder selected",
    "workspace.folderName": "Folder name",
    "workspace.localFolder": "Local folder to access",
    "workspace.pickFolderPlaceholder": "Choose a folder",
    "workspace.pickFolder": "Choose folder",
    "workspace.reload": "Reload",
    "workspace.notConfigured": "Local access is not set for {name}.",
    "workspace.loaded": "{name}: loaded {files} files, {selected} added to context.",
    "workspace.empty": "This folder is empty. Generated files can be saved here.",
    "workspace.binary": " binary/large",
    "workspace.savePath": "Save path",
    "workspace.writePlaceholder": "Paste generated code here before saving.",
    "workspace.saveFile": "Save file",
    "workspace.waitingPick": "Waiting for folder selection...",
    "workspace.loading": "Loading folder...",
    "workspace.saved": "Saved {path} ({size} bytes).",
    "workspace.saveError": "Save error",
    "workspace.savedTo": "Saved to {path} ({size} bytes).",
    "workspace.cannotInferSavePath": "Could not determine the save path. I put the code in the save box. Enter a save path and press Save file.",
    "composer.attachImage": "Attach image",
    "composer.removeAttachment": "Remove attachment",
    "composer.attachedImage": "Attached image",
    "image.generated": "Image generated.",
    "composer.placeholder": "Message Gemma 4 12B. Example: generate an image of a red apple",
    "composer.model": "Model",
    "chat.new": "New chat",
    "chat.emptySubtitle": "Local chat through Ollama",
    "chat.you": "You",
    "chat.generatingRole": "Gemma ・ generating",
    "chat.generating": "Generating",
    "chat.streamingStatus": "{label} ・ {seconds}s ・ streaming ・ ■ to stop",
    "chat.duration": "Time",
    "chat.model": "Model",
    "chat.task": "Task",
    "chat.mode": "Mode",
    "chat.preview": "Preview",
    "folder.new": "New folder",
    "folder.default": "Default folder",
    "folder.untitled": "Untitled",
    "folder.none": "No folders",
    "folder.localReady": "Local access set",
    "folder.localMissing": "Local access not set",
    "folder.add": "Add",
    "folder.addTitle": "Add a chat to this folder",
    "folder.edit": "Edit",
    "folder.editTitle": "Rename folder",
    "folder.delete": "Delete",
    "folder.deleteTitle": "Delete folder",
    "folder.deleteConfirm": "Delete “{name}” and {count} chats inside it?",
    "chat.editTitle": "Rename chat",
    "chat.deleteTitle": "Delete chat",
    "chat.none": "No chats",
    "chat.deleteConfirm": "Delete “{name}”?",
    "undo.deleted": "Deleted {target} “{label}”.",
    "status.checking": "Checking",
    "status.available": "Available",
    "status.codingMissing": "Coding model missing",
    "status.modelMissing": "Model missing",
    "status.offline": "Offline",
    "progress.generating": "Generating",
    "progress.fast": "Fast generation",
    "progress.quality": "Generating with quality",
    "progress.lightweight": "Generating with lightweight model",
    "progress.translation": "Translating",
    "progress.coding": "Generating code",
    "progress.search": "Searching + generating",
    "progress.workspace": "Generating and validating",
    "progress.image": "Generating image",
    "progress.weather": "Getting weather",
    "progress.saving": "Saving",
    "progress.stopping": "Stopping",
    "error.prefix": "Error",
  },
};

const els = {
  sidebar: document.querySelector("#sidebar"),
  sidebarResizer: document.querySelector("#sidebar-resizer"),
  sidebarToggle: document.querySelector("#sidebar-toggle"),
  sidebarCollapse: document.querySelector("#sidebar-collapse"),
  sidebarSearch: document.querySelector("#sidebar-search"),
  messages: document.querySelector("#messages"),
  prompt: document.querySelector("#prompt"),
  composer: document.querySelector("#composer"),
  progressLine: document.querySelector("#progress-line"),
  progressText: document.querySelector("#progress-text"),
  imageStrip: document.querySelector("#image-strip"),
  imageInput: document.querySelector("#image-input"),
  attachImage: document.querySelector("#attach-image"),
  send: document.querySelector("#send"),
  stop: document.querySelector("#stop"),
  newFolder: document.querySelector("#new-folder"),
  folderList: document.querySelector("#folder-list"),
  sessionList: document.querySelector("#session-list"),
  chatTitle: document.querySelector("#chat-title"),
  chatMeta: document.querySelector("#chat-meta"),
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
  workspaceStatus: document.querySelector("#workspace-status"),
  workspaceFiles: document.querySelector("#workspace-files"),
  writePath: document.querySelector("#write-path"),
  writeContent: document.querySelector("#write-content"),
  writeFile: document.querySelector("#write-file"),
  undoToast: document.querySelector("#undo-toast"),
  undoText: document.querySelector("#undo-text"),
  undoDelete: document.querySelector("#undo-delete"),
  undoClose: document.querySelector("#undo-close"),
  settingsToggle: document.querySelector("#settings-toggle"),
  settingsClose: document.querySelector("#settings-close"),
  settingsPanel: document.querySelector("#settings-panel"),
  settingsMeta: document.querySelector("#settings-meta"),
  modelInstaller: document.querySelector("#model-installer"),
  languageSelect: document.querySelector("#language-select"),
  themeSelect: document.querySelector("#theme-select"),
  responseMode: document.querySelector("#response-mode"),
  composerResponseMode: document.querySelector("#composer-response-mode"),
  composerModel: document.querySelector("#composer-model"),
  thinkingMode: document.querySelector("#thinking-mode"),
  chatModel: document.querySelector("#chat-model"),
  codingModel: document.querySelector("#coding-model"),
  translationModel: document.querySelector("#translation-model"),
  systemPrompt: document.querySelector("#system-prompt"),
  temperature: document.querySelector("#temperature"),
  topP: document.querySelector("#top-p"),
  topK: document.querySelector("#top-k"),
  numPredict: document.querySelector("#num-predict"),
  numCtx: document.querySelector("#num-ctx"),
  historyTurns: document.querySelector("#history-turns"),
  enterToSend: document.querySelector("#enter-to-send"),
};

if (window.matchMedia("(max-width: 760px)").matches && localStorage.getItem("gemma4.sidebarHidden") === null) {
  state.sidebarHidden = true;
}

function t(key, params = {}) {
  const dictionary = I18N[state.language] || I18N.ja;
  let text = dictionary[key] || I18N.ja[key] || key;
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

function setLanguage(language) {
  const next = I18N[language] ? language : "ja";
  const currentPrompt = els.systemPrompt?.value || "";
  state.language = next;
  localStorage.setItem("gemma4.language", state.language);
  if (els.systemPrompt && Object.values(SYSTEM_PROMPTS).includes(currentPrompt)) {
    els.systemPrompt.value = SYSTEM_PROMPTS[state.language] || SYSTEM_PROMPTS.ja;
  }
  applyI18n();
  syncModelInputs();
  renderSettingsMeta();
  renderModelInstaller();
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

function saveSessions() {
  localStorage.setItem("gemma4.sessions", JSON.stringify(state.sessions));
}

function saveFolders() {
  localStorage.setItem("gemma4.folders", JSON.stringify(state.folders));
  localStorage.setItem("gemma4.activeFolderId", state.activeFolderId || "");
  localStorage.setItem("gemma4.foldersInitialized", "true");
}

function saveWorkspacePrefs() {
  const folder = activeFolder();
  if (!folder) return;
  folder.workspaceRoot = state.workspaceRoot;
  folder.selectedFiles = [...state.selectedFiles];
  saveFolders();
}

function createFolder(name = t("folder.new")) {
  const folder = {
    id: crypto.randomUUID(),
    name,
    workspaceRoot: "",
    selectedFiles: [],
    createdAt: Date.now(),
  };
  state.folders.unshift(folder);
  state.activeFolderId = folder.id;
  syncWorkspaceFromActiveFolder();
  saveFolders();
  return folder;
}

function activeFolder() {
  return state.folders.find((folder) => folder.id === state.activeFolderId) || state.folders[0] || null;
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
    if (!folder.name) folder.name = t("folder.untitled");
  }
  for (const session of state.sessions) {
    if (!session.folderId || !state.folders.some((folder) => folder.id === session.folderId)) {
      session.folderId = state.activeFolderId;
    }
  }
  saveFolders();
  saveSessions();
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

function normalizedSidebarQuery() {
  return state.sidebarQuery.trim().toLowerCase();
}

function visibleFolders() {
  const query = normalizedSidebarQuery();
  if (!query) return state.folders;
  return state.folders.filter((folder) => {
    if (folder.name.toLowerCase().includes(query)) return true;
    return sessionsForFolder(folder.id).some((session) => session.title.toLowerCase().includes(query));
  });
}

function visibleSessionsForFolder(folder) {
  const sessions = sessionsForFolder(folder.id);
  const query = normalizedSidebarQuery();
  if (!query) return sessions;
  if (folder.name.toLowerCase().includes(query)) return sessions;
  return sessions.filter((session) => session.title.toLowerCase().includes(query));
}

function selectFirstSessionInActiveFolder() {
  const sessions = sessionsForActiveFolder();
  state.activeId = sessions[0]?.id || null;
}

function setSidebarHidden(hidden) {
  state.sidebarHidden = hidden;
  localStorage.setItem("gemma4.sidebarHidden", String(hidden));
  render();
}

function setSidebarWidth(width) {
  state.sidebarWidth = Math.min(420, Math.max(220, Math.round(width)));
  localStorage.setItem("gemma4.sidebarWidth", String(state.sidebarWidth));
  document.documentElement.style.setProperty("--sidebar-width", `${state.sidebarWidth}px`);
}

function setTheme(theme) {
  state.theme = ["dark", "light", "green"].includes(theme) ? theme : "dark";
  document.body.dataset.theme = state.theme;
  localStorage.setItem("gemma4.theme", state.theme);
  if (els.themeSelect) els.themeSelect.value = state.theme;
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
  if (useComposer && state.composerModel) return state.composerModel;
  if (state.modelOverrides[task]) return state.modelOverrides[task];
  return state.serverModels[task] || state.serverModels.chat || "";
}

function fallbackCodingModel() {
  return state.serverModels.chat || "gemma4:12b";
}

function fastChatModel() {
  if (modelIsInstalled("qwen2.5:3b") || state.serverModels.translation === "qwen2.5:3b") return "qwen2.5:3b";
  return state.serverModels.chat || "gemma4:12b";
}

function modelIsInstalled(model) {
  return state.serverModels.available.includes(model);
}

function displayModelName(model, task = "chat") {
  if (!model) return t("model.serverDefault");
  const installed = modelIsInstalled(model);
  if (model.includes("gemma-4-12B-coder-fable5")) {
    return `Gemma 4 Coder 12B Q4 (${t("model.coderRecommended")}${installed ? "" : ` / ${t("model.downloadRequired")}`})`;
  }
  if (model === "gemma4:12b") {
    if (task === "coding") return `Gemma 4 12B (${t("model.gemmaCoding")})`;
    if (task === "translation") return `Gemma 4 12B (${t("model.gemmaTranslation")})`;
    return `Gemma 4 12B (${t("model.gemmaStandard")})`;
  }
  if (model === "qwen2.5:3b") {
    if (task === "translation") return `Qwen 2.5 3B (${t("model.qwenTranslation")})`;
    return `Qwen 2.5 3B (${t("model.qwenFast")})`;
  }
  if (model === "phi3:latest") return "Phi-3";
  if (model === "llama3:latest") return "Llama 3";
  if (model === "qwen3:4b") return "Qwen3 4B";
  return `${model}${installed ? "" : ` (${t("model.missing")})`}`;
}

function shortModelName(model, task = "chat") {
  return displayModelName(model, task).replace(/（[^）]*）/g, "").replace(/\s*\([^)]*\)/g, "");
}

function composerModelLabel(model) {
  if (!model) return t("model.auto");
  if (model.includes("gemma-4-12B-coder-fable5")) return "Coder";
  if (model === "gemma4:12b") return "Gemma 4";
  if (model === "qwen2.5:3b") return "Qwen";
  if (model === "phi3:latest") return "Phi-3";
  if (model === "llama3:latest") return "Llama";
  if (model === "qwen3:4b") return "Qwen3";
  return shortModelName(model);
}

function taskLabel(task) {
  if (task === "translation") return t("task.translation");
  if (task === "coding") return t("task.coding");
  return t("task.chat");
}

function responseModeLabel(mode) {
  return { auto: t("mode.auto"), fast: t("mode.fast"), balanced: t("mode.balanced"), quality: t("mode.quality") }[mode] || mode;
}

function messageRunMeta(requestOptions, model) {
  const task = requestOptions.translationMode ? "translation" : requestOptions.codingMode ? "coding" : "chat";
  return {
    model: model || modelForTask(task),
    modelLabel: shortModelName(model || modelForTask(task), task),
    task,
    taskLabel: taskLabel(task),
    responseMode: requestOptions.responseMode,
    responseModeLabel: responseModeLabel(requestOptions.responseMode),
    thinkingMode: requestOptions.thinkingMode,
  };
}

function modelForRequestTask(task, requestOptions) {
  if (state.composerModel) return state.composerModel;
  if (task === "chat" && requestOptions.fastModel) return fastChatModel();
  return modelForTask(task);
}

function renderModelSelect(select, task, models) {
  if (!select) return;
  const current = state.modelOverrides[task] || "";
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
  select.value = current;
}

function installedOrCurrent(models, task) {
  const current = state.modelOverrides[task];
  return models.filter((model) => model && (modelIsInstalled(model) || model === current || model === state.composerModel || state.serverModels.recommendedCoding.includes(model)));
}

function renderComposerModelSelect() {
  if (!els.composerModel) return;
  const models = installedOrCurrent([
    state.serverModels.chat,
    state.serverModels.coding,
    state.serverModels.translation,
    ...state.serverModels.recommendedCoding,
    "gemma4:12b",
    "qwen2.5:3b",
  ], "chat");
  const uniqueModels = [...new Set(models.filter(Boolean))];
  if (state.composerModel && !uniqueModels.includes(state.composerModel)) uniqueModels.unshift(state.composerModel);
  els.composerModel.innerHTML = "";
  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = t("model.auto");
  autoOption.title = state.language === "en"
    ? "Automatically chooses the chat, coding, or translation model by task"
    : "用途に応じて通常・コード・翻訳モデルを自動で使い分けます";
  els.composerModel.append(autoOption);
  for (const model of uniqueModels) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = composerModelLabel(model);
    option.title = displayModelName(model, "chat");
    els.composerModel.append(option);
  }
  els.composerModel.value = state.composerModel;
}

function syncModelInputs() {
  renderModelSelect(els.chatModel, "chat", installedOrCurrent([
    state.serverModels.chat,
    "gemma4:12b",
    "qwen2.5:3b",
  ], "chat"));
  renderModelSelect(els.codingModel, "coding", installedOrCurrent([
    state.serverModels.coding,
    ...state.serverModels.recommendedCoding,
    "gemma4:12b",
  ], "coding"));
  renderModelSelect(els.translationModel, "translation", installedOrCurrent([
    state.serverModels.translation,
    "qwen2.5:3b",
    "gemma4:12b",
  ], "translation"));
  renderComposerModelSelect();
}

function renderModelInstaller() {
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
  for (const item of pullable) {
    const model = item.model;
    const installed = modelIsInstalled(model);
    const job = state.modelPullJobs[model] || null;
    const row = document.createElement("div");
    row.className = "model-install-row";
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

async function refreshModelPullStatus() {
  try {
    const response = await fetch("/api/models/pull/status");
    const data = await response.json();
    if (response.ok && data.ok) {
      state.modelPullJobs = data.jobs || {};
      renderModelInstaller();
      const running = Object.values(state.modelPullJobs).some((job) => job.status === "running" || job.status === "queued");
      if (!running && state.modelPullTimer) {
        window.clearInterval(state.modelPullTimer);
        state.modelPullTimer = null;
        checkHealth();
      }
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
    const response = await fetch("/api/models/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || (state.language === "en" ? "Could not start model download." : "モデルのダウンロードを開始できませんでした。"));
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
  if (!els.settingsMeta) return;
  const unknown = state.language === "en" ? "unknown" : "不明";
  const version = state.appInfo.version || unknown;
  const commit = state.appInfo.commit || unknown;
  const codingStatus = state.serverModels.codingInstalled ? "" : ` (${t("model.missing")})`;
  const lines = [
    `<div>${state.language === "en" ? "App" : "アプリ版"}: ${escapeHtml(version)} / commit ${escapeHtml(commit)}</div>`,
    `<div>${t("task.chat")}: ${escapeHtml(modelForTask("chat"))}</div>`,
    `<div>${t("task.coding")}: ${escapeHtml(modelForTask("coding"))}${escapeHtml(codingStatus)}</div>`,
    `<div>${t("task.translation")}: ${escapeHtml(modelForTask("translation"))}</div>`,
  ];
  if (state.composerModel) {
    lines.push(`<div>${state.language === "en" ? "Composer fixed" : "チャット欄固定"}: ${escapeHtml(displayModelName(state.composerModel, "chat"))}</div>`);
  }
  const selectedCoding = modelForTask("coding");
  if (selectedCoding.includes("gemma-4-12B-coder-fable5") && !modelIsInstalled(selectedCoding)) {
    lines.push(`<div>${state.language === "en" ? "Download first" : "使うには先に実行"}: <code>ollama pull ${escapeHtml(selectedCoding)}</code></div>`);
  }
  els.settingsMeta.innerHTML = lines.join("");
}

function setEnterToSend(enabled) {
  state.enterToSend = Boolean(enabled);
  localStorage.setItem("gemma4.enterToSend", String(state.enterToSend));
  if (els.enterToSend) els.enterToSend.checked = state.enterToSend;
}

function openFolderEditor(folder) {
  state.editingFolderId = null;
  state.editingSessionId = null;
  state.activeFolderId = folder.id;
  state.workspaceOpen = true;
  syncWorkspaceFromActiveFolder();
  selectFirstSessionInActiveFolder();
  saveFolders();
  render();
  if (state.workspaceRoot) loadWorkspace();
  requestAnimationFrame(() => els.workspaceFolderTitle?.focus());
}

function saveActiveFolderTitle() {
  const folder = activeFolder();
  if (!folder) return;
  const name = els.workspaceFolderTitle.value.trim();
  if (!name) {
    els.workspaceFolderTitle.value = folder.name;
    return;
  }
  folder.name = name;
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
  const deleted = state.lastDeleted;
  if (!deleted) return;
  if (deleted.type === "folder") {
    state.folders.splice(Math.min(deleted.folderIndex, state.folders.length), 0, deleted.folder);
    state.sessions.push(...deleted.sessions);
    state.activeFolderId = deleted.folder.id;
    state.activeId = deleted.activeId || deleted.sessions[0]?.id || null;
    syncWorkspaceFromActiveFolder();
    saveFolders();
    saveSessions();
    if (state.workspaceRoot) loadWorkspace();
  }
  if (deleted.type === "session") {
    state.sessions.splice(Math.min(deleted.sessionIndex, state.sessions.length), 0, deleted.session);
    state.activeFolderId = deleted.session.folderId;
    state.activeId = deleted.session.id;
    saveSessions();
  }
  state.lastDeleted = null;
  hideUndo();
  render();
}

function commitFolderRename(folder, value) {
  state.editingFolderId = null;
  const name = value.trim();
  if (name) {
    folder.name = name;
    saveFolders();
  }
  render();
}

function commitSessionRename(session, value) {
  state.editingSessionId = null;
  const title = value.trim();
  if (title) {
    session.title = title;
    saveSessions();
  }
  render();
}

function startFolderRename(folder) {
  openFolderEditor(folder);
}

function startSessionRename(session) {
  state.editingFolderId = null;
  state.editingSessionId = session.id;
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
  state.lastDeleted = {
    type: "folder",
    folder: { ...folder, selectedFiles: [...(folder.selectedFiles || [])] },
    folderIndex: state.folders.findIndex((item) => item.id === folder.id),
    sessions: state.sessions.filter((session) => session.folderId === folder.id).map((session) => ({ ...session, messages: [...session.messages] })),
    activeId: state.activeId,
  };
  state.folders = state.folders.filter((item) => item.id !== folder.id);
  state.sessions = state.sessions.filter((session) => session.folderId !== folder.id);
  if (state.activeFolderId === folder.id) {
    state.activeFolderId = state.folders[0]?.id || null;
  }
  if (state.folders.length === 0) {
    state.activeFolderId = null;
    state.activeId = null;
    state.workspaceOpen = false;
  }
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
  state.lastDeleted = {
    type: "session",
    session: { ...session, messages: [...session.messages] },
    sessionIndex: state.sessions.findIndex((item) => item.id === session.id),
  };
  state.sessions = state.sessions.filter((item) => item.id !== session.id);
  if (state.activeId === session.id) {
    selectFirstSessionInActiveFolder();
  }
  saveSessions();
  render();
  showUndo("session", session.title);
}

function newSession(folderId = state.activeFolderId) {
  if (!folderId) {
    const folder = createFolder(t("folder.new"));
    folderId = folder.id;
  }
  const session = {
    id: crypto.randomUUID(),
    title: t("chat.new"),
    folderId,
    messages: [],
    createdAt: Date.now(),
  };
  state.sessions.unshift(session);
  state.activeFolderId = folderId;
  state.activeId = session.id;
  syncWorkspaceFromActiveFolder();
  saveSessions();
  saveFolders();
  render();
}

function activeSession() {
  return state.sessions.find((session) => session.id === state.activeId && session.folderId === state.activeFolderId);
}

function renderFolders() {
  els.folderList.innerHTML = "";
  if (visibleFolders().length === 0) {
    const empty = document.createElement("div");
    empty.className = "folder-empty sidebar-empty";
    empty.textContent = t("folder.none");
    els.folderList.append(empty);
    return;
  }
  for (const folder of visibleFolders()) {
    const group = document.createElement("div");
    group.className = `folder-group${folder.id === state.activeFolderId ? " active" : ""}`;

    const row = document.createElement("div");
    row.className = `folder-item${folder.id === state.activeFolderId ? " active" : ""}`;

    if (state.editingFolderId === folder.id) {
      const input = document.createElement("input");
      input.className = "rename-input";
      input.dataset.folderEdit = folder.id;
      input.value = folder.name;
      input.addEventListener("blur", () => commitFolderRename(folder, input.value));
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") commitFolderRename(folder, input.value);
        if (event.key === "Escape") {
          state.editingFolderId = null;
          render();
        }
      });
      row.append(input);
    } else {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "item-main";
      const name = document.createElement("span");
      name.className = "folder-name";
      name.textContent = folder.name;
      const meta = document.createElement("small");
      meta.textContent = folder.workspaceRoot ? t("folder.localReady") : t("folder.localMissing");
      button.append(name, meta);
      button.addEventListener("click", async () => {
        state.editingFolderId = null;
        state.editingSessionId = null;
        state.workspaceOpen = false;
        state.activeFolderId = folder.id;
        syncWorkspaceFromActiveFolder();
        selectFirstSessionInActiveFolder();
        saveFolders();
        render();
        if (state.workspaceRoot) await loadWorkspace();
      });
      row.append(button);
    }

    const actions = document.createElement("div");
    actions.className = "item-actions";
    const addChat = document.createElement("button");
    addChat.type = "button";
    addChat.className = "item-action-primary";
    addChat.textContent = t("folder.add");
    addChat.title = t("folder.addTitle");
    addChat.addEventListener("click", () => {
      state.editingFolderId = null;
      state.editingSessionId = null;
      state.activeFolderId = folder.id;
      syncWorkspaceFromActiveFolder();
      newSession(folder.id);
    });
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = t("folder.edit");
    edit.title = t("folder.editTitle");
    edit.addEventListener("click", () => startFolderRename(folder));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = t("folder.delete");
    remove.title = t("folder.deleteTitle");
    remove.addEventListener("click", () => deleteFolder(folder));
    actions.append(addChat, edit, remove);
    row.append(actions);

    group.append(row);

    const sessionList = document.createElement("div");
    sessionList.className = "folder-session-list";
    const sessions = visibleSessionsForFolder(folder);
    for (const session of sessions) {
      const sessionRow = document.createElement("div");
      sessionRow.className = `session-item${session.id === state.activeId ? " active" : ""}`;

      if (state.editingSessionId === session.id) {
        const input = document.createElement("input");
        input.className = "rename-input";
        input.dataset.sessionEdit = session.id;
        input.value = session.title;
        input.addEventListener("blur", () => commitSessionRename(session, input.value));
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") commitSessionRename(session, input.value);
          if (event.key === "Escape") {
            state.editingSessionId = null;
            render();
          }
        });
        sessionRow.append(input);
      } else {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "item-main";
        button.textContent = session.title;
        button.addEventListener("click", async () => {
          state.editingFolderId = null;
          state.editingSessionId = null;
          state.activeFolderId = folder.id;
          state.activeId = session.id;
          syncWorkspaceFromActiveFolder();
          saveFolders();
          render();
          if (state.workspaceRoot) await loadWorkspace();
        });
        sessionRow.append(button);
      }

      const sessionActions = document.createElement("div");
      sessionActions.className = "item-actions";
      const sessionEdit = document.createElement("button");
      sessionEdit.type = "button";
      sessionEdit.textContent = t("folder.edit");
      sessionEdit.title = t("chat.editTitle");
      sessionEdit.addEventListener("click", () => startSessionRename(session));
      const sessionRemove = document.createElement("button");
      sessionRemove.type = "button";
      sessionRemove.textContent = t("folder.delete");
      sessionRemove.title = t("chat.deleteTitle");
      sessionRemove.addEventListener("click", () => deleteSession(session));
      sessionActions.append(sessionEdit, sessionRemove);
      sessionRow.append(sessionActions);
      sessionList.append(sessionRow);
    }

    if (sessions.length === 0) {
      const empty = document.createElement("div");
      empty.className = "folder-empty";
      empty.textContent = t("chat.none");
      sessionList.append(empty);
    }

    group.append(sessionList);
    els.folderList.append(group);
  }
}

function renderMessages() {
  const session = activeSession();
  els.messages.innerHTML = "";
  els.chatTitle.textContent = session?.title || t("chat.new");
  els.chatMeta.textContent = `${t("task.chat")}: ${modelForTask("chat")} / ${t("task.coding")}: ${modelForTask("coding")}`;

  if (!session || session.messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <h2>Gemma 4 12B</h2>
      <div>${escapeHtml(t("chat.emptySubtitle"))}</div>
    `;
    els.messages.append(empty);
    return;
  }

  for (const message of session.messages) {
    const wrapper = document.createElement("article");
    wrapper.className = `message ${message.role}${message.streaming ? " streaming" : ""}`;
    const role = document.createElement("div");
    role.className = "message-role";
    role.textContent = message.role === "user" ? t("chat.you") : message.streaming ? t("chat.generatingRole") : "Gemma";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = message.content || (message.streaming ? `${t("chat.generating")}...` : "");
    wrapper.append(role, bubble);
    if (message.streaming) {
      const status = document.createElement("div");
      status.className = "streaming-status";
      const elapsed = state.progressElapsedSeconds || 0;
      status.textContent = t("chat.streamingStatus", { label: state.progressLabel, seconds: elapsed });
      wrapper.append(status);
    }
    if (message.imagePreviews && message.imagePreviews.length > 0) {
      const images = document.createElement("div");
      images.className = "message-images";
      for (const preview of message.imagePreviews) {
        const image = document.createElement("img");
        image.src = preview;
        image.alt = t("composer.attachedImage");
        images.append(image);
      }
      wrapper.append(images);
    }
    if (message.generatedImages && message.generatedImages.length > 0) {
      const images = document.createElement("div");
      images.className = "generated-images";
      for (const generated of message.generatedImages) {
        const link = document.createElement("a");
        link.href = generated.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        const image = document.createElement("img");
        image.src = generated.url;
        image.alt = generated.filename || (state.language === "en" ? "Generated image" : "生成画像");
        link.append(image);
        images.append(link);
      }
      wrapper.append(images);
    }
    if (message.imageMeta) {
      const meta = document.createElement("div");
      meta.className = "image-meta";
      const details = [
        `${message.imageMeta.width}×${message.imageMeta.height}`,
        `Steps ${message.imageMeta.steps}`,
        `CFG ${message.imageMeta.cfg}`,
        `Seed ${message.imageMeta.seed}`,
      ];
      if (message.imageMeta.prompt) {
        details.push(`Prompt: ${message.imageMeta.prompt}`);
      }
      meta.textContent = details.join(" / ");
      wrapper.append(meta);
    }
    if (message.sources && message.sources.length > 0) {
      const sources = document.createElement("div");
      sources.className = "sources";
      for (const [index, source] of message.sources.entries()) {
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        if (source.type === "preview") {
          link.className = "preview-source";
          link.textContent = source.title || t("chat.preview");
        } else {
          link.textContent = `[${index + 1}] ${source.title || source.url}`;
        }
        sources.append(link);
      }
      wrapper.append(sources);
    }
    if (message.role === "assistant" && typeof message.durationSeconds === "number") {
      const duration = document.createElement("div");
      duration.className = "message-duration";
      const details = [`${t("chat.duration")}: ${formatDuration(message.durationSeconds)}`];
      if (message.runMeta?.modelLabel) details.push(`${t("chat.model")}: ${message.runMeta.modelLabel}`);
      if (message.runMeta?.taskLabel) details.push(`${t("chat.task")}: ${message.runMeta.taskLabel}`);
      if (message.runMeta?.responseModeLabel) details.push(`${t("chat.mode")}: ${message.runMeta.responseModeLabel}`);
      duration.textContent = details.join(" / ");
      wrapper.append(duration);
    }
    els.messages.append(wrapper);
  }
  els.messages.scrollTop = els.messages.scrollHeight;
}

function render() {
  document.documentElement.style.setProperty("--sidebar-width", `${state.sidebarWidth}px`);
  document.body.dataset.theme = state.theme;
  document.body.classList.toggle("sidebar-hidden", state.sidebarHidden);
  els.sidebarToggle.hidden = !state.sidebarHidden;
  els.sidebarCollapse.textContent = state.sidebarHidden ? t("sidebar.show") : t("sidebar.hide");
  renderFolders();
  renderMessages();
  renderWorkspace();
  els.send.disabled = false;
  els.send.hidden = state.busy;
  els.stop.hidden = !state.busy;
  els.stop.disabled = !state.abortController;
  renderPendingImages();
  els.webSearchToggle.classList.toggle("active", state.webSearch);
  els.webSearchToggle.setAttribute("aria-pressed", String(state.webSearch));
  els.progressLine.hidden = true;
}

function renderPendingImages() {
  els.imageStrip.hidden = state.pendingImages.length === 0;
  els.imageStrip.innerHTML = "";
  for (const [index, image] of state.pendingImages.entries()) {
    const item = document.createElement("div");
    item.className = "pending-image";
    const preview = document.createElement("img");
    preview.src = image.preview;
    preview.alt = image.name || t("composer.attachedImage");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.title = t("composer.removeAttachment");
    remove.addEventListener("click", () => {
      state.pendingImages.splice(index, 1);
      render();
    });
    item.append(preview, remove);
    els.imageStrip.append(item);
  }
}

function renderWorkspace() {
  els.workspacePanel.hidden = !state.workspaceOpen;
  const folder = activeFolder();
  els.workspaceFolderName.textContent = folder?.name || t("workspace.noFolder");
  els.workspaceFolderTitle.value = folder?.name || "";
  els.workspaceRoot.value = state.workspaceRoot;
  const selectedCount = state.selectedFiles.size;
  const fileCount = state.workspaceFiles.length;
  if (!state.workspaceRoot) {
    els.workspaceStatus.textContent = t("workspace.notConfigured", { name: activeFolder()?.name || t("sidebar.folderButton") });
  } else if (state.workspaceNote) {
    els.workspaceStatus.textContent = state.workspaceNote;
  } else {
    els.workspaceStatus.textContent = t("workspace.loaded", { name: activeFolder()?.name || t("sidebar.folderButton"), files: fileCount, selected: selectedCount });
  }
  els.workspaceFiles.innerHTML = "";
  for (const file of state.workspaceFiles) {
    const row = document.createElement("label");
    row.className = `workspace-file${file.text ? "" : " disabled"}`;
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.disabled = !file.text;
    checkbox.checked = state.selectedFiles.has(file.path);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedFiles.add(file.path);
      } else {
        state.selectedFiles.delete(file.path);
      }
      saveWorkspacePrefs();
      renderWorkspace();
    });
    const name = document.createElement("span");
    name.textContent = file.path;
    const meta = document.createElement("small");
    meta.textContent = `${Math.ceil(file.size / 1024)} KB${file.text ? "" : t("workspace.binary")}`;
    row.append(checkbox, name, meta);
    els.workspaceFiles.append(row);
  }
}

function updateSessionTitle(session, prompt) {
  if (session.title !== "新規チャット" && session.title !== "New chat" && session.title !== t("chat.new")) return;
  const oneLine = prompt.replace(/\s+/g, " ").trim();
  session.title = oneLine.slice(0, 42) || t("chat.new");
}

function numberValue(input, fallback) {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function isWorkspaceBuildRequest(text) {
  if (!state.workspaceRoot) return false;
  return /テトリス|ゲーム|サイト|アプリ|ページ|ツール|作って|つくって|作成|生成|構築|実装|修正|変更|保存|ファイル|html|css|javascript|コード|program|app|game|build|create|implement/i.test(text);
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
  if (/教えて|調べ|検索|説明|理由|なぜ|比較|要約|分析|設計|実装|修正|コード|ファイル|保存|画像|添削|翻訳|translate|explain|why|how|code|file|image|search/i.test(text)) {
    return false;
  }
  return (
    isSimpleReplyRequest(text) ||
    isCasualQuickReplyRequest(text) ||
    /かな|かも|どうしよ|どうしよう|おすすめ|たべよう|食べよう|飲もう|ねむい|疲れた|つかれた|がんばる|頑張る/i.test(normalized)
  );
}

function isTranslationRequest(text) {
  return /英訳|和訳|翻訳|訳して|translate/i.test(text);
}

function effectiveResponseMode(text, codingMode) {
  if (codingMode) return "quality";
  const selected = state.responseMode;
  if (selected !== "auto") return selected;
  if (isTranslationRequest(text)) return "fast";
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
  return "\n\n翻訳モード: ユーザーが翻訳を求めた場合は、翻訳文だけを返してください。解説、前置き、箇条書き、候補の列挙は不要です。原文が箇条書きなら箇条書きを保ち、それ以外は自然な文章として訳してください。";
}

function translationSystemPrompt() {
  return [
    "You are a precise translation engine.",
    "Return only the translated text.",
    "Do not add explanations, bullets, labels, alternatives, or notes.",
    "Preserve the source structure when it is a list or multiline text.",
    "If the request says 英訳, translate into natural English.",
    "If the request says 和訳, translate into natural Japanese.",
    "If no target language is explicit, infer it from the request.",
  ].join("\n");
}

function lightweightChatSystemPrompt() {
  if (state.language === "en") {
    return [
      "You are a natural, lightweight casual assistant.",
      "Reply directly in 1-2 short sentences.",
      "For everyday questions like meals, breaks, or mood, give a concrete suggestion.",
      "Do not preface that you are a language model, not an expert, or unable to do something.",
      "Do not use bullet points, option lists, bold text, or headings.",
    ].join("\n");
  }
  return [
    "あなたは日本語で自然に返す軽い雑談アシスタントです。",
    "ユーザーの短い相談や雑談に、1〜2文で直接答えてください。",
    "食事、休憩、気分転換などの日常的な相談には、具体的に提案してください。",
    "自分が言語モデルであること、専門外であること、実行できないことを前置きしないでください。",
    "箇条書き、候補リスト、太字、見出しは使わないでください。",
  ].join("\n");
}

function buildSystemPrompt(basePrompt, codingMode, responseMode = "balanced", thinkingMode = "medium", translationMode = false) {
  const prompt = `${basePrompt}${modeSystemSuffix(responseMode)}${thinkingSystemSuffix(thinkingMode)}${translationSystemSuffix(translationMode)}`;
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

function chatRequestOptions(text, hasImages = false) {
  const codingMode = isWorkspaceBuildRequest(text);
  const translationMode = isTranslationRequest(text) && !codingMode;
  const lightweightMode = !codingMode && !translationMode && isLightweightChatRequest(text, hasImages);
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
    return {
      codingMode,
      translationMode,
      responseMode: "fast",
      thinkingMode: "low",
      progressLabel: t("progress.translation"),
      temperature: 0.1,
      topP: 0.7,
      topK: 10,
      numPredict: Math.min(Math.max(maxTokens, 128), 192),
      numCtx: 2048,
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
      temperature: Math.min(numberValue(els.temperature, 0.7), 0.5),
      topP: Math.min(numberValue(els.topP, 0.9), 0.8),
      topK: Math.min(numberValue(els.topK, 40), 20),
      numPredict: Math.min(Math.max(maxTokens, 64), 128),
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
  return applyThinkingBudget({
    codingMode,
    translationMode,
    responseMode: mode,
    thinkingMode,
    progressLabel: codingMode ? t("progress.coding") : state.webSearch ? t("progress.search") : t("progress.generating"),
    temperature: numberValue(els.temperature, 0.7),
    topP: numberValue(els.topP, 0.9),
    topK: numberValue(els.topK, 40),
    numPredict: codingMode ? Math.max(maxTokens, 4096) : state.webSearch ? Math.max(maxTokens, 512) : maxTokens,
    numCtx: codingMode ? Math.max(contextSize, 8192) : state.webSearch ? Math.max(contextSize, 4096) : contextSize,
    historyTurns: codingMode ? Math.max(historyTurns, 6) : state.webSearch ? Math.min(Math.max(historyTurns, 3), 4) : historyTurns,
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

function extractJsonObject(text) {
  const trimmed = text.trim().replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
  const first = trimmed.indexOf("{");
  const last = trimmed.lastIndexOf("}");
  if (first < 0 || last <= first) {
    throw new Error("GemmaがJSONを返しませんでした。");
  }
  return JSON.parse(trimmed.slice(first, last + 1));
}

function extractFilesFromCodeBlocks(text) {
  const files = [];
  const pattern = /(?:^|\n)\s*([A-Za-z0-9_.\/-]+\.[A-Za-z0-9]+)\s*\n```[A-Za-z0-9_-]*\n([\s\S]*?)```/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const path = cleanCandidatePath(match[1]);
    const content = match[2].replace(/\s+$/g, "\n");
    if (path && content.trim()) files.push({ path, content });
  }
  if (files.length === 0) {
    throw new Error("保存できるコードブロックが見つかりませんでした。");
  }
  return {
    summary: "コードブロックからファイルを生成しました。",
    notes: ["JSONが不完全な場合は、コードブロック形式から保存します。"],
    files,
  };
}

function parseWorkspaceGeneration(text) {
  try {
    const payload = extractJsonObject(text);
    return {
      summary: String(payload.summary || "生成しました。"),
      notes: Array.isArray(payload.notes) ? payload.notes.map(String) : [],
      files: normalizeGeneratedFiles(payload),
    };
  } catch (jsonError) {
    try {
      return extractFilesFromCodeBlocks(text);
    } catch {
      throw new Error(`生成結果を読み取れませんでした: ${jsonError.message}`);
    }
  }
}

function normalizeGeneratedFiles(payload) {
  if (!payload || !Array.isArray(payload.files)) {
    throw new Error("GemmaのJSONにfiles配列がありません。");
  }
  const files = payload.files
    .map((file) => ({
      path: cleanCandidatePath(String(file.path || "")),
      content: String(file.content || ""),
    }))
    .filter((file) => file.path && file.content.trim());
  if (files.length === 0) {
    throw new Error("保存できるファイルが生成されませんでした。");
  }
  return files;
}

function normalizeWorkspacePlan(payload) {
  const fallback = {
    summary: "index.html に自己完結のWebアプリを作成します。",
    files: [{ path: "index.html", purpose: "CSSとJavaScriptを含む完成版のHTML" }],
  };
  if (!payload || !Array.isArray(payload.files)) return fallback;
  const files = payload.files
    .slice(0, 3)
    .map((file) => ({
      path: cleanCandidatePath(String(file.path || "")),
      purpose: String(file.purpose || "このファイルを実装します。").trim(),
    }))
    .filter((file) => file.path);
  if (files.length === 0) return fallback;
  return {
    summary: String(payload.summary || "段階的にファイルを生成します。").trim(),
    files,
  };
}

async function requestWorkspacePlan(userText, signal = null, model = modelForTask("coding")) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: "coding",
      model,
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
      workspace: {
        root: state.workspaceRoot,
        files: [...state.selectedFiles],
      },
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
      workspace: {
        root: state.workspaceRoot,
        files: [...state.selectedFiles],
      },
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
      workspace: {
        root: state.workspaceRoot,
        files: [...state.selectedFiles],
      },
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
    const response = await fetch("/api/workspace/write", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root: state.workspaceRoot, path: file.path, content: file.content }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `${file.path} を保存できませんでした。`);
    }
    saved.push({ path: data.path, size: data.size });
  }
  return saved;
}

async function validateGeneratedFiles(files) {
  const response = await fetch("/api/workspace/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ root: state.workspaceRoot, files }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "検証に失敗しました。");
  }
  return data;
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

function workspacePreviewSources(files) {
  if (!state.workspaceRoot) return [];
  return files
    .filter((file) => /\.html?$/i.test(file.path))
    .map((file) => ({
      type: "preview",
      title: `${t("chat.preview")}: ${file.path}`,
      url: `/api/workspace/preview?root=${encodeURIComponent(state.workspaceRoot)}&path=${encodeURIComponent(file.path)}`,
    }));
}

async function handleWorkspaceBuild(text) {
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
    progressMessage.sources = workspacePreviewSources(savedFiles);
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
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      onEvent(JSON.parse(trimmed));
    }
  }
  buffer += decoder.decode();
  const trimmed = buffer.trim();
  if (trimmed) onEvent(JSON.parse(trimmed));
}

async function sendMessage(text) {
  let session = activeSession();
  if (!session) {
    newSession();
    session = activeSession();
  }

  const images = state.pendingImages.map((image) => image.base64);
  const imagePreviews = state.pendingImages.map((image) => image.preview);
  const requestOptions = chatRequestOptions(text, images.length > 0);
  const userMessage = { role: "user", content: text, images, imagePreviews };
  session.messages.push(userMessage);
  state.pendingImages = [];
  updateSessionTitle(session, text);
  state.busy = true;
  startProgressTimer(requestOptions.progressLabel);
  saveSessions();
  render();

  let assistantMessage = null;
  let renderScheduled = false;
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
    const requestSystem = requestOptions.translationMode
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
    const requestMessages = requestOptions.translationMode || requestOptions.fastModel ? [userMessage] : [...session.messages];
    const stream = !requestOptions.translationMode;
    const requestTask = requestOptions.translationMode ? "translation" : requestOptions.codingMode ? "coding" : "chat";
    const requestModel = modelForRequestTask(requestTask, requestOptions);
    const payload = {
      task: requestTask,
      model: requestModel,
      stream,
      system: requestSystem,
      messages: requestMessages,
      temperature: requestOptions.temperature,
      top_p: requestOptions.topP,
      top_k: requestOptions.topK,
      num_predict: requestOptions.numPredict,
      num_ctx: requestOptions.numCtx,
      history_turns: requestOptions.historyTurns,
      think: requestOptions.think,
      keep_alive: requestOptions.keepAlive,
      web_search: requestOptions.codingMode ? false : requestOptions.webSearch,
      search_results: 4,
      workspace: requestOptions.translationMode
        ? null
        : {
            root: state.workspaceRoot,
            files: [...state.selectedFiles],
          },
    };
    state.abortController = new AbortController();
    if (stream) {
      assistantMessage = {
        role: "assistant",
        content: "",
        sources: [],
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
        if (event.search?.results) {
          streamSearchResults = event.search.results;
        }
        if (event.type === "chunk" && event.content) {
          assistantMessage.content += event.content;
          scheduleStreamRender();
        }
        if (event.type === "done") {
          assistantMessage.content = event.message?.content || assistantMessage.content;
          streamSearchResults = event.search?.results || streamSearchResults;
        }
      });
      const durationSeconds = (Date.now() - state.startedAt) / 1000;
      const content = assistantMessage.content || "";
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
      assistantMessage.sources = requestOptions.codingMode ? workspacePreviewSources(savedFiles) : streamSearchResults;
      assistantMessage.durationSeconds = durationSeconds;
      assistantMessage.runMeta = messageRunMeta(requestOptions, requestModel);
      delete assistantMessage.streaming;
      return;
    }

    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Request failed");
    }
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    const content = data.message.content || "";
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
      sources: requestOptions.codingMode ? workspacePreviewSources(savedFiles) : data.search?.results || [],
      durationSeconds,
      runMeta: messageRunMeta(requestOptions, data.model || requestModel),
    });
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    if (error.name === "AbortError") {
      if (assistantMessage) {
        assistantMessage.content = assistantMessage.content
          ? `${assistantMessage.content}\n\n${state.language === "en" ? "(Stopped)" : "（停止しました）"}`
          : (state.language === "en" ? "Stopped." : "停止しました。");
        assistantMessage.durationSeconds = durationSeconds;
        assistantMessage.runMeta = messageRunMeta(requestOptions, requestModel);
        delete assistantMessage.streaming;
      } else {
        session.messages.push({
          role: "assistant",
          content: state.language === "en" ? "Stopped." : "停止しました。",
          durationSeconds,
          runMeta: messageRunMeta(requestOptions, requestModel),
        });
      }
    } else if (assistantMessage) {
      assistantMessage.content = assistantMessage.content
        ? `${assistantMessage.content}\n\n${t("error.prefix")}: ${error.message}`
        : `${t("error.prefix")}: ${error.message}`;
      assistantMessage.durationSeconds = durationSeconds;
      assistantMessage.runMeta = messageRunMeta(requestOptions, requestModel);
      delete assistantMessage.streaming;
    } else {
      session.messages.push({
        role: "assistant",
        content: `${t("error.prefix")}: ${error.message}`,
        durationSeconds,
        runMeta: messageRunMeta(requestOptions, requestModel),
      });
    }
  } finally {
    state.abortController = null;
    state.busy = false;
    stopProgressTimer();
    saveSessions();
    render();
  }
}

function isImageGenerationRequest(text) {
  const normalized = text.trim();
  return (
    /^画像生成\s*[:：]/.test(normalized) ||
    /画像を?(生成|作成|つくって|作って|描いて)/.test(normalized) ||
    /(生成|作成|つくって|作って|描いて).{0,12}画像/.test(normalized) ||
    /^(draw|generate|create)\s+.*\b(image|picture|photo)\b/i.test(normalized)
  );
}

function extractImagePrompt(text) {
  let prompt = text.trim();
  prompt = prompt.replace(/^画像生成\s*[:：]\s*/i, "");
  prompt = prompt.replace(/^画像を?(生成|作成|つくって|作って|描いて)\s*[:：]?\s*/i, "");
  prompt = prompt.replace(/(?:の)?画像を?(生成|作成|つくって|作って|描いて)(して)?[。.!！]*$/i, "");
  prompt = prompt.replace(/^(draw|generate|create)\s+/i, "");
  prompt = prompt.replace(/\b(image|picture|photo)\b/gi, "");
  return prompt.replace(/\s+/g, " ").trim() || text.trim();
}

function parseImageOptions(text) {
  const size = text.match(/(\d{2,4})\s*[x×]\s*(\d{2,4})/i);
  const steps = text.match(/steps?\s*[:=]\s*(\d+)/i) || text.match(/ステップ\s*[:=]?\s*(\d+)/);
  const seed = text.match(/seed\s*[:=]\s*(-?\d+)/i) || text.match(/シード\s*[:=]?\s*(-?\d+)/);
  return {
    width: size ? size[1] : 512,
    height: size ? size[2] : 512,
    steps: steps ? steps[1] : 8,
    cfg: 7,
    seed: seed ? seed[1] : -1,
  };
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
  const accepted = [...files].filter((file) => file.type.startsWith("image/")).slice(0, 4 - state.pendingImages.length);
  for (const file of accepted) {
    const dataUrl = await readFileAsDataUrl(file);
    const base64 = dataUrl.split(",", 2)[1] || "";
    state.pendingImages.push({
      name: file.name,
      preview: dataUrl,
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

function startProgressTimer(label = t("progress.generating")) {
  stopProgressTimer();
  state.progressLabel = label;
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
  state.progressElapsedSeconds = 0;
}

function updateProgressTimer() {
  if (!state.startedAt) return;
  const elapsedSeconds = Math.floor((Date.now() - state.startedAt) / 1000);
  state.progressElapsedSeconds = elapsedSeconds;
  els.progressText.textContent = state.language === "en"
    ? `${state.progressLabel}... ${elapsedSeconds}s`
    : `${state.progressLabel}... ${elapsedSeconds}秒`;
  if (state.busy) renderMessages();
}

function formatDuration(seconds) {
  const suffix = state.language === "en" ? "s" : "秒";
  if (seconds < 10) return `${seconds.toFixed(1)}${suffix}`;
  return `${Math.round(seconds)}${suffix}`;
}

function isLocalDateTimeRequest(text) {
  const normalized = text.replace(/\s+/g, "").toLowerCase();
  if (!normalized) return false;
  return (
    /(いま|今|現在|今の).{0,6}(時間|時刻)|何時/.test(normalized) ||
    /(今日|本日|現在).{0,6}(日付|何日|曜日)|何曜日/.test(normalized) ||
    /^(time|date|today|whattime|whatday)\??$/i.test(normalized)
  );
}

function normalizeShortReply(text) {
  return text.replace(/[!！?？。、〜~ー－—\s]/g, "").toLowerCase();
}

function isCasualQuickReplyRequest(text) {
  const normalized = normalizeShortReply(text);
  if (normalized.length > 24) return false;
  return (
    /^(つかれた|疲れた|なんかつかれた|なんか疲れた|しんどい|ねむい|眠い|ねむ)$/.test(normalized) ||
    /^(わかった|了解|りょうかい|ok|おけ|なるほど|たしかに|そうだね|そうですね)$/.test(normalized) ||
    /^(ok|おけ)?(がんばる|頑張る)(ね|よ)?$/.test(normalized) ||
    /^(おそい|遅い|おそかった|遅かった|まだ|ながい|長い)$/.test(normalized)
  );
}

function localDateTimeAnswer(text) {
  const now = new Date();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "local";
  const date = new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(now);
  const weekday = new Intl.DateTimeFormat("ja-JP", { weekday: "long" }).format(now);
  const time = new Intl.DateTimeFormat("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(now);
  const normalized = text.replace(/\s+/g, "");
  if (/曜日/.test(normalized) && !/(時間|時刻|何時)/.test(normalized)) {
    return `今日は${date}（${weekday}）です。`;
  }
  if (/(日付|何日|today|date)/i.test(normalized) && !/(時間|時刻|何時|time)/i.test(normalized)) {
    return `今日は${date}（${weekday}）です。`;
  }
  return `現在時刻は ${date}（${weekday}） ${time}（${timeZone}）です。`;
}

function isWeatherRequest(text) {
  return /(天気|気温|降水|雨|晴れ|曇り|weather|temperature|forecast)/i.test(text);
}

function weatherLocationFromText(text) {
  const normalized = text.replace(/\s+/g, " ").trim();
  const explicit = normalized.match(/(.+?)(?:の|で|における)(?:今日|現在|今|明日|週間)?(?:の)?(?:天気|気温|降水|weather|forecast)/i);
  if (explicit) {
    const location = explicit[1]
      .replace(/^(今日|現在|今|明日|本日|いま)\s*/i, "")
      .replace(/^(今日の|現在の|今の|明日の)/, "")
      .trim();
    if (location && !/^(今日|現在|今|明日|本日|いま)$/.test(location)) return location;
  }
  const trailing = normalized.match(/(?:天気|気温|降水|weather|forecast).{0,8}(?: in | at | for )([A-Za-z\s.-]+)$/i);
  if (trailing?.[1]) return trailing[1].trim();
  return "";
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
    const response = await fetch("/api/weather", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text, location }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "天気を取得できませんでした");
    }
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    session.messages.push({
      role: "assistant",
      content: data.answer,
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
    content: localDateTimeAnswer(text),
    durationSeconds: 0,
  });
  saveSessions();
  render();
  return true;
}

async function pickWorkspaceFolder() {
  els.workspaceStatus.textContent = t("workspace.waitingPick");
  try {
    const response = await fetch("/api/workspace/pick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || (state.language === "en" ? "Could not choose folder." : "フォルダー選択に失敗しました"));
    }
    state.workspaceRoot = data.root;
    els.workspaceRoot.value = data.root;
    state.selectedFiles = new Set();
    saveWorkspacePrefs();
    await loadWorkspace();
  } catch (error) {
    els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message}`;
  }
}

async function loadWorkspace() {
  const root = els.workspaceRoot.value.trim();
  if (!root) return;
  els.workspaceStatus.textContent = t("workspace.loading");
  try {
    const response = await fetch("/api/workspace/tree", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || (state.language === "en" ? "Could not load folder." : "フォルダーを読み込めませんでした"));
    }
    state.workspaceRoot = data.root;
    state.workspaceFiles = data.files || [];
    if (state.workspaceFiles.length === 0) {
      state.workspaceNote = t("workspace.empty");
    } else if (data.truncated) {
      state.workspaceNote = state.language === "en"
        ? `Showing ${state.workspaceFiles.length} files. Some were omitted because there are many files.`
        : `${state.workspaceFiles.length}件を表示中です。件数が多いため一部を省略しました。`;
    } else {
      state.workspaceNote = "";
    }
    state.selectedFiles = new Set([...state.selectedFiles].filter((path) => state.workspaceFiles.some((file) => file.path === path)));
    saveWorkspacePrefs();
    render();
  } catch (error) {
    els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message}`;
  }
}

async function saveWorkspaceFile() {
  const root = state.workspaceRoot;
  const path = els.writePath.value.trim();
  const content = els.writeContent.value;
  if (!root || !path) {
    els.workspaceStatus.textContent = state.language === "en"
      ? "Choose a folder and enter a relative path first."
      : "先にフォルダーを選択し、相対パスを入力してください。";
    return;
  }
  try {
    const response = await fetch("/api/workspace/write", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root, path, content }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || (state.language === "en" ? "Could not save file." : "ファイルを保存できませんでした"));
    }
    els.workspaceStatus.textContent = t("workspace.saved", { path: data.path, size: data.size });
    await loadWorkspace();
  } catch (error) {
    els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message}`;
  }
}

function isSaveCommand(text) {
  const normalized = text.trim().toLowerCase();
  return /保存|書き込|ファイルにして|作成して|反映して|save|write/.test(normalized);
}

function lastAssistantMessage(session) {
  for (let index = session.messages.length - 1; index >= 0; index -= 1) {
    if (session.messages[index].role === "assistant") {
      return session.messages[index];
    }
  }
  return null;
}

const LANGUAGE_EXTENSIONS = {
  html: "html",
  css: "css",
  javascript: "js",
  js: "js",
  mjs: "mjs",
  typescript: "ts",
  ts: "ts",
  tsx: "tsx",
  jsx: "jsx",
  json: "json",
  python: "py",
  py: "py",
  markdown: "md",
  md: "md",
  svg: "svg",
  text: "txt",
  txt: "txt",
};

function cleanCandidatePath(path) {
  return path
    .replace(/^\.?\//, "")
    .replace(/[)、。,:：;；\]\[)"'」』]+$/g, "")
    .trim();
}

function pathFromText(text) {
  const pattern = /(?:^|[\s`"'「『(（])([A-Za-z0-9_.\/-]+\.(?:html|css|js|mjs|ts|tsx|jsx|json|md|py|txt|svg))/gi;
  let match = pattern.exec(text);
  let candidate = "";
  while (match) {
    candidate = cleanCandidatePath(match[1]);
    match = pattern.exec(text);
  }
  return candidate;
}

function parseCodeFenceInfo(info) {
  const parts = info.trim().split(/\s+/).filter(Boolean);
  let language = "";
  let path = "";
  for (const part of parts) {
    const cleaned = cleanCandidatePath(part);
    if (!path && /\.[a-z0-9]+$/i.test(cleaned)) {
      path = cleaned;
      continue;
    }
    if (!language && LANGUAGE_EXTENSIONS[cleaned.toLowerCase()]) {
      language = cleaned.toLowerCase();
    }
  }
  return { language, path };
}

function splitLeadingPathFromContent(content) {
  const normalized = content.replace(/^\s+/, "");
  const lineBreak = normalized.indexOf("\n");
  if (lineBreak < 0) return { path: "", content };
  const firstLine = cleanCandidatePath(normalized.slice(0, lineBreak));
  if (!/\.[a-z0-9]+$/i.test(firstLine)) return { path: "", content };
  return {
    path: firstLine,
    content: normalized.slice(lineBreak + 1).replace(/^\s+/, ""),
  };
}

function extractCodeBlocks(text) {
  const blocks = [];
  const pattern = /```([^\n`]*)\n([\s\S]*?)```/g;
  let match = pattern.exec(text);
  let completedEnd = 0;
  while (match) {
    const info = parseCodeFenceInfo(match[1]);
    const before = text.slice(Math.max(0, match.index - 240), match.index);
    const split = splitLeadingPathFromContent(match[2]);
    blocks.push({
      language: info.language,
      path: info.path || pathFromText(before) || split.path,
      content: split.content.trim(),
      complete: true,
    });
    completedEnd = pattern.lastIndex;
    match = pattern.exec(text);
  }
  const lastFence = text.indexOf("```", completedEnd);
  if (lastFence >= 0) {
    const afterFence = text.slice(lastFence + 3);
    const firstBreak = afterFence.indexOf("\n");
    if (firstBreak >= 0) {
      const info = parseCodeFenceInfo(afterFence.slice(0, firstBreak));
      const before = text.slice(Math.max(0, lastFence - 240), lastFence);
      const split = splitLeadingPathFromContent(afterFence.slice(firstBreak + 1));
      blocks.push({
        language: info.language,
        path: info.path || pathFromText(before) || split.path,
        content: split.content.trim(),
        complete: false,
      });
    }
  }
  return blocks;
}

function inferSavePath(commandText, assistantText, codeBlock, useCurrentPath = true) {
  const currentPath = els.writePath.value.trim();
  if (useCurrentPath && currentPath) return currentPath;
  if (codeBlock.path) return codeBlock.path;

  const combined = `${commandText}\n${assistantText}`;
  const explicit = pathFromText(combined);
  if (explicit) return explicit;

  const language = codeBlock.language;
  const content = codeBlock.content.trimStart();
  if (language === "html" || content.startsWith("<!doctype html") || content.startsWith("<html")) return "index.html";
  if (language === "css") return "styles.css";
  if (language === "javascript" || language === "js") return "app.js";
  if (language === "python" || language === "py") return "main.py";
  if (language === "json") return "data.json";
  return "";
}

function uniquePath(path, usedPaths) {
  if (!usedPaths.has(path)) return path;
  const dot = path.lastIndexOf(".");
  const base = dot >= 0 ? path.slice(0, dot) : path;
  const ext = dot >= 0 ? path.slice(dot) : "";
  let index = 2;
  let candidate = `${base}-${index}${ext}`;
  while (usedPaths.has(candidate)) {
    index += 1;
    candidate = `${base}-${index}${ext}`;
  }
  return candidate;
}

async function autoSaveGeneratedFiles(commandText, assistantText) {
  if (!state.workspaceRoot) return [];
  const blocks = extractCodeBlocks(assistantText).filter((block) => block.content.trim());
  if (blocks.length === 0) return [];
  if (blocks.some((block) => !block.complete)) {
    throw new Error("コードが途中で終わったため保存しませんでした。もう一度生成してください。");
  }

  const savedFiles = [];
  const usedPaths = new Set();
  for (const block of blocks) {
    const inferredPath = inferSavePath(commandText, assistantText, block, false);
    if (!inferredPath) continue;
    const path = uniquePath(inferredPath, usedPaths);
    usedPaths.add(path);
    const response = await fetch("/api/workspace/write", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root: state.workspaceRoot, path, content: block.content }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `${path} を保存できませんでした`);
    }
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
  if (!session || !state.workspaceRoot || !isSaveCommand(text)) return false;

  const assistant = lastAssistantMessage(session);
  const blocks = extractCodeBlocks(assistant?.content || "");
  if (blocks.length === 0) return false;

  const block = blocks[blocks.length - 1];
  const path = inferSavePath(text, assistant.content, block);
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
    const response = await fetch("/api/workspace/write", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root: state.workspaceRoot, path, content: block.content }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "ファイルを保存できませんでした");
    }
    const durationSeconds = (Date.now() - state.startedAt) / 1000;
    els.writePath.value = data.path;
    els.writeContent.value = block.content;
    session.messages.push({
      role: "assistant",
      content: t("workspace.savedTo", { path: data.path, size: data.size }),
      sources: workspacePreviewSources([{ path: data.path, size: data.size }]),
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
  if ((!text && state.pendingImages.length === 0) || state.busy) return;
  els.prompt.value = "";
  resizePrompt();
  if (text && state.pendingImages.length === 0 && handleLocalUtilityRequest(text)) return;
  if (text && state.pendingImages.length === 0 && (await handleWeatherRequest(text))) return;
  if (text && state.pendingImages.length === 0 && isImageGenerationRequest(text)) {
    await generateImageFromChat(text);
    return;
  }
  if (text && state.pendingImages.length === 0 && (await handleSaveCommand(text))) return;
  if (text && state.pendingImages.length === 0 && isWorkspaceBuildRequest(text)) {
    await handleWorkspaceBuild(text);
    return;
  }
  sendMessage(text || (state.language === "en" ? "Describe this image." : "この画像を説明してください。"));
});

els.stop.addEventListener("click", () => {
  if (!state.abortController) return;
  state.progressLabel = t("progress.stopping");
  updateProgressTimer();
  state.abortController.abort();
});

const PROMPT_MIN_HEIGHT = 34;
const PROMPT_MAX_HEIGHT = 160;

function resizePrompt() {
  els.prompt.style.height = "0px";
  const nextHeight = els.prompt.value
    ? Math.min(PROMPT_MAX_HEIGHT, Math.max(PROMPT_MIN_HEIGHT, els.prompt.scrollHeight))
    : PROMPT_MIN_HEIGHT;
  els.prompt.style.height = `${nextHeight}px`;
  els.prompt.style.overflowY = nextHeight >= PROMPT_MAX_HEIGHT ? "auto" : "hidden";
}

els.prompt.addEventListener("input", resizePrompt);
els.prompt.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.isComposing) return;
  const shortcutSend = event.metaKey || event.ctrlKey;
  const plainEnterSend = state.enterToSend && !event.shiftKey && !event.altKey;
  if (!shortcutSend && !plainEnterSend) return;
  event.preventDefault();
  els.composer.requestSubmit();
});

els.attachImage.addEventListener("click", () => {
  els.imageInput.click();
});

els.imageInput.addEventListener("change", async () => {
  await addImages(els.imageInput.files || []);
  els.imageInput.value = "";
});

els.prompt.addEventListener("paste", addImagesFromClipboard);
document.addEventListener("paste", addImagesFromDocumentPaste);

els.sidebarSearch.addEventListener("input", () => {
  state.sidebarQuery = els.sidebarSearch.value;
  render();
});

els.sidebarResizer.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  els.sidebarResizer.setPointerCapture(event.pointerId);
  document.body.classList.add("resizing-sidebar");
  const onMove = (moveEvent) => setSidebarWidth(moveEvent.clientX);
  const onUp = () => {
    document.body.classList.remove("resizing-sidebar");
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
});

els.sidebarToggle.addEventListener("click", () => setSidebarHidden(false));
els.sidebarCollapse.addEventListener("click", () => setSidebarHidden(!state.sidebarHidden));
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
  state.webSearch = !state.webSearch;
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
  if (event.key === "Escape" && !els.settingsPanel.hidden) {
    els.settingsPanel.hidden = true;
    return;
  }
  if (event.key === "Escape" && state.workspaceOpen) {
    state.workspaceOpen = false;
    render();
  }
});

els.workspacePick.addEventListener("click", pickWorkspaceFolder);
els.workspaceLoad.addEventListener("click", loadWorkspace);
els.writeFile.addEventListener("click", saveWorkspaceFile);

els.settingsToggle.addEventListener("click", () => {
  els.settingsPanel.hidden = !els.settingsPanel.hidden;
  renderSettingsMeta();
});
els.settingsClose.addEventListener("click", () => {
  els.settingsPanel.hidden = true;
});

els.modelInstaller.addEventListener("click", (event) => {
  const button = event.target.closest("[data-model-pull]");
  if (!button) return;
  startModelPull(button.dataset.modelPull);
});

els.themeSelect.addEventListener("change", () => setTheme(els.themeSelect.value));
els.languageSelect.addEventListener("change", () => setLanguageFromControl(els.languageSelect.value));
els.responseMode.addEventListener("change", () => setResponseMode(els.responseMode.value));
els.composerResponseMode.addEventListener("change", () => setResponseMode(els.composerResponseMode.value));
els.composerModel.addEventListener("change", () => setComposerModel(els.composerModel.value));
els.thinkingMode.addEventListener("change", () => setThinkingMode(els.thinkingMode.value));
els.chatModel.addEventListener("change", () => {
  setModelOverride("chat", els.chatModel.value);
  renderSettingsMeta();
  renderMessages();
});
els.codingModel.addEventListener("change", () => {
  setModelOverride("coding", els.codingModel.value);
  renderSettingsMeta();
  renderMessages();
});
els.translationModel.addEventListener("change", () => {
  setModelOverride("translation", els.translationModel.value);
  renderSettingsMeta();
});
els.enterToSend.addEventListener("change", () => setEnterToSend(els.enterToSend.checked));

ensureFolderData();
syncWorkspaceFromActiveFolder();
state.language = I18N[state.language] ? state.language : "ja";
applyI18n();
if (els.systemPrompt && Object.values(SYSTEM_PROMPTS).includes(els.systemPrompt.value)) {
  els.systemPrompt.value = SYSTEM_PROMPTS[state.language] || SYSTEM_PROMPTS.ja;
}
setTheme(state.theme);
setResponseMode(state.responseMode);
setThinkingMode(state.thinkingMode);
syncModelInputs();
renderSettingsMeta();
setEnterToSend(state.enterToSend);
resizePrompt();

if (state.folders.length > 0 && sessionsForActiveFolder().length === 0) {
  newSession();
} else {
  selectFirstSessionInActiveFolder();
  render();
}

if (state.workspaceRoot) loadWorkspace();

checkHealth();
setInterval(checkHealth, 10000);
