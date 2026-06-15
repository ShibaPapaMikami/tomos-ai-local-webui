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
  theme: localStorage.getItem("gemma4.theme") || "dark",
  responseMode: localStorage.getItem("gemma4.responseMode") || "auto",
  thinkingMode: localStorage.getItem("gemma4.thinkingMode") || "auto",
  modelOverrides: {
    chat: localStorage.getItem("gemma4.model.chat") || "",
    coding: localStorage.getItem("gemma4.model.coding") || "",
    translation: localStorage.getItem("gemma4.model.translation") || "",
  },
  serverModels: {
    chat: "gemma4:12b",
    coding: "gemma4:12b",
    translation: "gemma4:12b",
    available: [],
    recommendedCoding: [],
    codingInstalled: true,
  },
  appInfo: {
    version: "",
    commit: "",
  },
  enterToSend: localStorage.getItem("gemma4.enterToSend") === "true",
  lastDeleted: null,
  pendingImages: [],
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
  themeSelect: document.querySelector("#theme-select"),
  responseMode: document.querySelector("#response-mode"),
  composerResponseMode: document.querySelector("#composer-response-mode"),
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

function createFolder(name = "新規フォルダー") {
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
      name: "既定フォルダー",
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
    if (!folder.name) folder.name = "名称未設定";
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

function modelForTask(task) {
  if (state.modelOverrides[task]) return state.modelOverrides[task];
  return state.serverModels[task] || state.serverModels.chat || "";
}

function displayModelName(model, task = "chat") {
  if (!model) return "サーバー既定";
  const installed = state.serverModels.available.includes(model);
  if (model.includes("gemma-4-12B-coder-fable5")) {
    return `Gemma 4 Coder 12B Q4${installed ? "" : "（推奨・未取得）"}`;
  }
  if (model === state.serverModels.chat && task === "chat") return `${model}（通常既定）`;
  if (model === state.serverModels.coding && task === "coding") return `${model}（コード既定）`;
  if (model === state.serverModels.translation && task === "translation") return `${model}（翻訳既定）`;
  return model;
}

function renderModelSelect(select, task, models) {
  if (!select) return;
  const current = state.modelOverrides[task] || "";
  select.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = task === "translation" ? "サーバー自動" : "サーバー既定";
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

function syncModelInputs() {
  const available = state.serverModels.available;
  renderModelSelect(els.chatModel, "chat", [state.serverModels.chat, ...available]);
  renderModelSelect(els.codingModel, "coding", [state.serverModels.coding, ...state.serverModels.recommendedCoding, ...available]);
  renderModelSelect(els.translationModel, "translation", [state.serverModels.translation, ...available]);
}

function renderSettingsMeta() {
  if (!els.settingsMeta) return;
  const version = state.appInfo.version || "不明";
  const commit = state.appInfo.commit || "不明";
  const codingStatus = state.serverModels.codingInstalled ? "" : "（未取得）";
  els.settingsMeta.innerHTML = [
    `<div>アプリ版: ${escapeHtml(version)} / commit ${escapeHtml(commit)}</div>`,
    `<div>通常: ${escapeHtml(modelForTask("chat"))}</div>`,
    `<div>コード: ${escapeHtml(modelForTask("coding"))}${escapeHtml(codingStatus)}</div>`,
    `<div>翻訳: ${escapeHtml(modelForTask("translation"))}</div>`,
  ].join("");
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
  const target = kind === "folder" ? "フォルダー" : "チャット";
  els.undoText.textContent = `${target}「${label}」を削除しました。`;
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
  const ok = window.confirm(`「${folder.name}」と中のチャット${count}件を削除しますか？`);
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
  const ok = window.confirm(`「${session.title}」を削除しますか？`);
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
    const folder = createFolder("新規フォルダー");
    folderId = folder.id;
  }
  const session = {
    id: crypto.randomUUID(),
    title: "新規チャット",
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
    empty.textContent = "フォルダーなし";
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
      meta.textContent = folder.workspaceRoot ? "ローカル設定済み" : "ローカル未設定";
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
    addChat.textContent = "追加";
    addChat.title = "このフォルダーにチャットを追加";
    addChat.addEventListener("click", () => {
      state.editingFolderId = null;
      state.editingSessionId = null;
      state.activeFolderId = folder.id;
      syncWorkspaceFromActiveFolder();
      newSession(folder.id);
    });
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "編集";
    edit.title = "フォルダー名を変更";
    edit.addEventListener("click", () => startFolderRename(folder));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "削除";
    remove.title = "フォルダーを削除";
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
      sessionEdit.textContent = "編集";
      sessionEdit.title = "チャット名を変更";
      sessionEdit.addEventListener("click", () => startSessionRename(session));
      const sessionRemove = document.createElement("button");
      sessionRemove.type = "button";
      sessionRemove.textContent = "削除";
      sessionRemove.title = "チャットを削除";
      sessionRemove.addEventListener("click", () => deleteSession(session));
      sessionActions.append(sessionEdit, sessionRemove);
      sessionRow.append(sessionActions);
      sessionList.append(sessionRow);
    }

    if (sessions.length === 0) {
      const empty = document.createElement("div");
      empty.className = "folder-empty";
      empty.textContent = "チャットなし";
      sessionList.append(empty);
    }

    group.append(sessionList);
    els.folderList.append(group);
  }
}

function renderMessages() {
  const session = activeSession();
  els.messages.innerHTML = "";
  els.chatTitle.textContent = session?.title || "新規チャット";
  els.chatMeta.textContent = `通常: ${modelForTask("chat")} / コード: ${modelForTask("coding")}`;

  if (!session || session.messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <h2>Gemma 4 12B</h2>
      <div>Ollama経由のローカルチャット</div>
    `;
    els.messages.append(empty);
    return;
  }

  for (const message of session.messages) {
    const wrapper = document.createElement("article");
    wrapper.className = `message ${message.role}${message.streaming ? " streaming" : ""}`;
    const role = document.createElement("div");
    role.className = "message-role";
    role.textContent = message.role === "user" ? "あなた" : message.streaming ? "Gemma ・ 生成中" : "Gemma";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = message.content || (message.streaming ? "生成中..." : "");
    wrapper.append(role, bubble);
    if (message.streaming) {
      const status = document.createElement("div");
      status.className = "streaming-status";
      status.textContent = "逐次表示中 ・ ■ で停止";
      wrapper.append(status);
    }
    if (message.imagePreviews && message.imagePreviews.length > 0) {
      const images = document.createElement("div");
      images.className = "message-images";
      for (const preview of message.imagePreviews) {
        const image = document.createElement("img");
        image.src = preview;
        image.alt = "添付画像";
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
        image.alt = generated.filename || "生成画像";
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
        link.textContent = `[${index + 1}] ${source.title || source.url}`;
        sources.append(link);
      }
      wrapper.append(sources);
    }
    if (message.role === "assistant" && typeof message.durationSeconds === "number") {
      const duration = document.createElement("div");
      duration.className = "message-duration";
      duration.textContent = `所要時間: ${formatDuration(message.durationSeconds)}`;
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
  els.sidebarCollapse.textContent = state.sidebarHidden ? "サイドバーを表示" : "サイドバーを隠す";
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
  els.progressLine.hidden = !state.busy;
}

function renderPendingImages() {
  els.imageStrip.hidden = state.pendingImages.length === 0;
  els.imageStrip.innerHTML = "";
  for (const [index, image] of state.pendingImages.entries()) {
    const item = document.createElement("div");
    item.className = "pending-image";
    const preview = document.createElement("img");
    preview.src = image.preview;
    preview.alt = image.name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.title = "添付を削除";
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
  els.workspaceFolderName.textContent = folder?.name || "フォルダー未選択";
  els.workspaceFolderTitle.value = folder?.name || "";
  els.workspaceRoot.value = state.workspaceRoot;
  const selectedCount = state.selectedFiles.size;
  const fileCount = state.workspaceFiles.length;
  if (!state.workspaceRoot) {
    els.workspaceStatus.textContent = `${activeFolder()?.name || "フォルダー"} のローカルアクセスは未設定です。`;
  } else if (state.workspaceNote) {
    els.workspaceStatus.textContent = state.workspaceNote;
  } else {
    els.workspaceStatus.textContent = `${activeFolder()?.name || "フォルダー"}: ${fileCount}件のファイルを読み込み、${selectedCount}件を文脈に追加中。`;
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
    meta.textContent = `${Math.ceil(file.size / 1024)} KB${file.text ? "" : " バイナリ/大容量"}`;
    row.append(checkbox, name, meta);
    els.workspaceFiles.append(row);
  }
}

function updateSessionTitle(session, prompt) {
  if (session.title !== "新規チャット" && session.title !== "New chat") return;
  const oneLine = prompt.replace(/\s+/g, " ").trim();
  session.title = oneLine.slice(0, 42) || "新規チャット";
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

function isSimpleReplyRequest(text) {
  const normalized = text.replace(/\s+/g, "").trim();
  if (!normalized || normalized.length > 24) return false;
  if (/[?？]|教えて|調べ|検索|説明|なぜ|どう|作っ|つくっ|生成|画像|コード|ファイル|保存|修正|実装|help|why|how|create|build/i.test(text)) {
    return false;
  }
  return /^(おはよ|おはよう|こんにちは|こんばんは|ありがとう|ありがと|どうも|了解|はい|うん|ok|OK|hi|hello|thanks|thankyou|goodmorning)/i.test(normalized);
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
    return "\n\n高速応答モード: 挨拶や短い返事は1文で短く返してください。詳しい説明は求められた時だけにしてください。";
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
      progressLabel: options.codingMode ? options.progressLabel : "深く考えて生成中",
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

function chatRequestOptions(text) {
  const codingMode = isWorkspaceBuildRequest(text);
  const translationMode = isTranslationRequest(text) && !codingMode;
  const mode = effectiveResponseMode(text, codingMode);
  const thinkingMode = effectiveThinkingMode(text, codingMode, mode);
  const maxTokens = numberValue(els.numPredict, 96);
  const contextSize = numberValue(els.numCtx, 2048);
  const historyTurns = numberValue(els.historyTurns, 4);
  if (translationMode) {
    return {
      codingMode,
      translationMode,
      responseMode: "fast",
      thinkingMode: "low",
      progressLabel: "翻訳中",
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
      progressLabel: "高速生成中",
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
      progressLabel: codingMode ? "コード生成中" : "精度優先で生成中",
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
    progressLabel: codingMode ? "コード生成中" : state.webSearch ? "検索 + 生成中" : "生成中",
    temperature: numberValue(els.temperature, 0.7),
    topP: numberValue(els.topP, 0.9),
    topK: numberValue(els.topK, 40),
    numPredict: codingMode ? Math.max(maxTokens, 4096) : maxTokens,
    numCtx: codingMode ? Math.max(contextSize, 8192) : contextSize,
    historyTurns: codingMode ? Math.max(historyTurns, 6) : historyTurns,
    keepAlive: codingMode ? "20m" : "15m",
    think: false,
    webSearch: state.webSearch,
  });
}

function workspaceBuilderSystemPrompt() {
  return `あなたはローカルフォルダー内にWebアプリを実装するコーディングエージェントです。
返答はJSONオブジェクトだけにしてください。Markdown、説明、コードフェンスは禁止です。
スキーマ:
{
  "summary": "短い作業概要",
  "files": [
    {"path": "index.html", "content": "完全なファイル内容"}
  ],
  "notes": ["任意の短い注意"]
}
要件:
- 小さなWebゲームやデモは、ユーザー指定がなければ自己完結のHTML 1ファイルを優先してください。
- HTMLにはCSSとJavaScriptを含め、保存後にそのままブラウザーで開ける完成品にしてください。
- 未完成の省略、TODO、途中で切れたコード、外部ライブラリCDN依存は禁止です。
- ファイルパスは相対パスだけにしてください。`;
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

async function requestWorkspaceFiles(userText, previousFiles = [], validation = null, signal = null) {
  const correction = validation && !validation.ok
    ? `\n\n前回の生成には以下の検証エラーがあります。全ファイルを修正版として再出力してください。\n${validationText(validation)}\n\n前回ファイル:\n${JSON.stringify(previousFiles).slice(0, 60000)}`
    : "";
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: "coding",
      model: modelForTask("coding"),
      system: workspaceBuilderSystemPrompt(),
      messages: [
        {
          role: "user",
          content: `${userText}${correction}`,
        },
      ],
      temperature: 0.2,
      top_p: 0.85,
      top_k: 30,
      num_predict: 8192,
      num_ctx: 12288,
      history_turns: 1,
      think: false,
      keep_alive: "10m",
      web_search: false,
      workspace: {
        root: state.workspaceRoot,
        files: [...state.selectedFiles],
      },
    }),
    signal: combinedAbortSignal(signal, 180000),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "コード生成に失敗しました。");
  }
  const payload = extractJsonObject(data.message?.content || "");
  return {
    summary: String(payload.summary || "生成しました。"),
    notes: Array.isArray(payload.notes) ? payload.notes.map(String) : [],
    files: normalizeGeneratedFiles(payload),
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
  if (notes.length > 0) lines.push(`メモ:\n${notes.map((note) => `- ${note}`).join("\n")}`);
  return lines.join("\n");
}

function workspacePreviewSources(files) {
  if (!state.workspaceRoot) return [];
  return files
    .filter((file) => /\.html?$/i.test(file.path))
    .map((file) => ({
      title: `${file.path} をプレビュー`,
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
  startProgressTimer("生成・検証中");
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
  let attempts = 0;
  const setBuildProgress = (lines) => {
    progressMessage.content = lines.join("\n");
    saveSessions();
    render();
  };

  try {
    for (attempts = 1; attempts <= 3; attempts += 1) {
      state.progressLabel = attempts === 1 ? "生成・保存中" : `自動修正中 ${attempts - 1}/2`;
      updateProgressTimer();
      setBuildProgress([
        `作業中: ${state.progressLabel}`,
        `- 試行 ${attempts}/3`,
        `- ${modelForTask("coding")} でファイル内容を生成中`,
        "- 生成後に保存と検証を行います",
      ]);
      generated = await requestWorkspaceFiles(text, generated?.files || [], validation, state.abortController.signal);
      setBuildProgress([
        `作業中: ${state.progressLabel}`,
        `- 試行 ${attempts}/3`,
        `- ${generated.files.length}件のファイルを受信`,
        "- ローカルフォルダーへ保存中",
      ]);
      savedFiles = await saveGeneratedFiles(generated.files);
      setBuildProgress([
        `作業中: ${state.progressLabel}`,
        `- 試行 ${attempts}/3`,
        `- ${savedFiles.length}件のファイルを保存`,
        "- 構文と未完成表現を検証中",
      ]);
      validation = await validateGeneratedFiles(savedFiles);
      if (validation.ok) break;
      setBuildProgress([
        "検証で問題を検出しました。",
        `- 試行 ${attempts}/3`,
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
    delete progressMessage.streaming;
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    if (error.name === "AbortError") {
      progressMessage.content = "生成を停止しました。";
    } else if (error.name === "TimeoutError" || /timed out/i.test(error.message)) {
      progressMessage.content = [
        "生成が3分以内に完了しなかったため停止しました。",
        "- 依頼を少し小さく分けると成功しやすくなります",
        "- 例: まず index.html だけ作る → 次に見た目を改善する",
      ].join("\n");
    } else {
      progressMessage.content = `生成エラー: ${error.message}`;
    }
    progressMessage.durationSeconds = durationSeconds;
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
    if (Array.isArray(data.availableModels) || state.serverModels.recommendedCoding.length > 0) {
      state.serverModels.available = data.availableModels || state.serverModels.available;
      syncModelInputs();
    }
    els.statusDot.className = `status-dot ${data.ok && data.modelInstalled ? "ok" : "error"}`;
    const codingMissing = data.ok && data.codingModel && data.codingModelInstalled === false;
    els.statusText.textContent = data.ok && data.modelInstalled
      ? codingMissing ? "コード用モデル未取得" : "使用可能"
      : "モデル未取得";
    renderSettingsMeta();
    if (!state.busy) renderMessages();
  } catch {
    state.appInfo.version = "取得失敗";
    state.appInfo.commit = "";
    els.statusDot.className = "status-dot error";
    els.statusText.textContent = "オフライン";
    renderSettingsMeta();
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

  const requestOptions = chatRequestOptions(text);
  const images = state.pendingImages.map((image) => image.base64);
  const imagePreviews = state.pendingImages.map((image) => image.preview);
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
      : buildSystemPrompt(
          els.systemPrompt.value,
          requestOptions.codingMode,
          requestOptions.responseMode,
          requestOptions.thinkingMode,
          requestOptions.translationMode,
        );
    const requestMessages = requestOptions.translationMode ? [userMessage] : [...session.messages];
    const stream = !requestOptions.translationMode;
    const requestTask = requestOptions.translationMode ? "translation" : requestOptions.codingMode ? "coding" : "chat";
    const payload = {
      task: requestTask,
      model: modelForTask(requestOptions.translationMode ? "translation" : requestOptions.codingMode ? "coding" : "chat"),
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
        ? `保存しました。\n${savedFiles.map((file) => `- ${file.path} (${file.size}バイト)`).join("\n")}`
        : saveError
          ? `\n\n自動保存エラー: ${saveError}`
          : "";
      assistantMessage.content = requestOptions.codingMode && savedFiles.length > 0 ? savedNote : `${content}${savedNote}`;
      assistantMessage.sources = requestOptions.codingMode ? workspacePreviewSources(savedFiles) : streamSearchResults;
      assistantMessage.durationSeconds = durationSeconds;
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
      ? `保存しました。\n${savedFiles.map((file) => `- ${file.path} (${file.size}バイト)`).join("\n")}`
      : saveError
        ? `\n\n自動保存エラー: ${saveError}`
        : "";
    session.messages.push({
      role: "assistant",
      content: requestOptions.codingMode && savedFiles.length > 0 ? savedNote : `${content}${savedNote}`,
      sources: requestOptions.codingMode ? workspacePreviewSources(savedFiles) : data.search?.results || [],
      durationSeconds,
    });
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    if (error.name === "AbortError") {
      if (assistantMessage) {
        assistantMessage.content = assistantMessage.content
          ? `${assistantMessage.content}\n\n（停止しました）`
          : "停止しました。";
        assistantMessage.durationSeconds = durationSeconds;
        delete assistantMessage.streaming;
      } else {
        session.messages.push({
          role: "assistant",
          content: "停止しました。",
          durationSeconds,
        });
      }
    } else if (assistantMessage) {
      assistantMessage.content = assistantMessage.content
        ? `${assistantMessage.content}\n\nエラー: ${error.message}`
        : `エラー: ${error.message}`;
      assistantMessage.durationSeconds = durationSeconds;
      delete assistantMessage.streaming;
    } else {
      session.messages.push({
        role: "assistant",
        content: `エラー: ${error.message}`,
        durationSeconds,
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
  startProgressTimer("画像生成中");
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
      content: "画像を生成しました。",
      generatedImages: data.images || [],
      imageMeta: data.meta || null,
      durationSeconds,
    });
  } catch (error) {
    const durationSeconds = state.startedAt ? (Date.now() - state.startedAt) / 1000 : 0;
    session.messages.push({
      role: "assistant",
      content: `画像生成エラー: ${error.message}`,
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

function startProgressTimer(label = "生成中") {
  stopProgressTimer();
  state.progressLabel = label;
  state.startedAt = Date.now();
  updateProgressTimer();
  state.timerId = window.setInterval(updateProgressTimer, 250);
}

function stopProgressTimer() {
  if (state.timerId) {
    window.clearInterval(state.timerId);
    state.timerId = null;
  }
  state.startedAt = 0;
}

function updateProgressTimer() {
  if (!state.startedAt) return;
  const elapsedSeconds = Math.floor((Date.now() - state.startedAt) / 1000);
  els.progressText.textContent = `${state.progressLabel}... ${elapsedSeconds}秒`;
}

function formatDuration(seconds) {
  if (seconds < 10) return `${seconds.toFixed(1)}秒`;
  return `${Math.round(seconds)}秒`;
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
  startProgressTimer("天気取得中");
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
      content: `天気取得エラー: ${error.message}`,
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
  els.workspaceStatus.textContent = "フォルダー選択を待機中...";
  try {
    const response = await fetch("/api/workspace/pick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "フォルダー選択に失敗しました");
    }
    state.workspaceRoot = data.root;
    els.workspaceRoot.value = data.root;
    state.selectedFiles = new Set();
    saveWorkspacePrefs();
    await loadWorkspace();
  } catch (error) {
    els.workspaceStatus.textContent = `エラー: ${error.message}`;
  }
}

async function loadWorkspace() {
  const root = els.workspaceRoot.value.trim();
  if (!root) return;
  els.workspaceStatus.textContent = "フォルダーを読み込み中...";
  try {
    const response = await fetch("/api/workspace/tree", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "フォルダーを読み込めませんでした");
    }
    state.workspaceRoot = data.root;
    state.workspaceFiles = data.files || [];
    if (state.workspaceFiles.length === 0) {
      state.workspaceNote = "このフォルダーは空です。生成したファイルはここへ保存できます。";
    } else if (data.truncated) {
      state.workspaceNote = `${state.workspaceFiles.length}件を表示中です。件数が多いため一部を省略しました。`;
    } else {
      state.workspaceNote = "";
    }
    state.selectedFiles = new Set([...state.selectedFiles].filter((path) => state.workspaceFiles.some((file) => file.path === path)));
    saveWorkspacePrefs();
    render();
  } catch (error) {
    els.workspaceStatus.textContent = `エラー: ${error.message}`;
  }
}

async function saveWorkspaceFile() {
  const root = state.workspaceRoot;
  const path = els.writePath.value.trim();
  const content = els.writeContent.value;
  if (!root || !path) {
    els.workspaceStatus.textContent = "先にフォルダーを選択し、相対パスを入力してください。";
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
      throw new Error(data.error || "ファイルを保存できませんでした");
    }
    els.workspaceStatus.textContent = `${data.path} を保存しました（${data.size}バイト）。`;
    await loadWorkspace();
  } catch (error) {
    els.workspaceStatus.textContent = `エラー: ${error.message}`;
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
      content: "保存先ファイル名が判断できませんでした。保存欄にコードを入れました。保存先ファイルを入力して「ファイルを保存」を押してください。",
      durationSeconds: 0,
    });
    saveSessions();
    render();
    return true;
  }

  state.busy = true;
  startProgressTimer("保存中");
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
      content: `${data.path} に保存しました（${data.size}バイト）。`,
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
      content: `保存エラー: ${error.message}`,
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
  sendMessage(text || "この画像を説明してください。");
});

els.stop.addEventListener("click", () => {
  if (!state.abortController) return;
  state.progressLabel = "停止中";
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
  createFolder("新規フォルダー");
  newSession();
  startFolderRename(activeFolder());
  render();
});

els.clearChat.addEventListener("click", () => {
  const session = activeSession();
  if (!session) return;
  session.messages = [];
  session.title = "新規チャット";
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

els.themeSelect.addEventListener("change", () => setTheme(els.themeSelect.value));
els.responseMode.addEventListener("change", () => setResponseMode(els.responseMode.value));
els.composerResponseMode.addEventListener("change", () => setResponseMode(els.composerResponseMode.value));
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
