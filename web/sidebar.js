(() => {
function normalizedSidebarQuery(state) {
  return String(state?.sidebarQuery || "").trim().toLowerCase();
}

function visibleFolders({ state, sessionsForFolder }) {
  const query = normalizedSidebarQuery(state);
  if (!query) return state.folders;
  return state.folders.filter((folder) => {
    if (folder.name.toLowerCase().includes(query)) return true;
    return sessionsForFolder(folder.id).some((session) => session.title.toLowerCase().includes(query));
  });
}

function visibleSessionsForFolder({ state, folder, sessionsForFolder }) {
  const sessions = sessionsForFolder(folder.id);
  const query = normalizedSidebarQuery(state);
  if (!query) return sessions;
  if (folder.name.toLowerCase().includes(query)) return sessions;
  return sessions.filter((session) => session.title.toLowerCase().includes(query));
}

function sidebarIcon(type) {
  const icon = document.createElement("span");
  icon.className = `sidebar-item-icon ${type === "chat" ? "chat-icon" : "folder-icon"}`;
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = type === "chat"
    ? '<svg viewBox="0 0 24 24"><path d="M5 6.5h14v9H9l-4 3v-12Z"></path></svg>'
    : '<svg viewBox="0 0 24 24"><path d="M3.5 6.5h6l1.7 2h9.3v8.8a1.7 1.7 0 0 1-1.7 1.7H5.2a1.7 1.7 0 0 1-1.7-1.7V6.5Z"></path><path d="M3.5 8.5h17"></path></svg>';
  return icon;
}

function toggleFolderCollapsed({ folderId, state, onSaveCollapsedFolders, onRender }) {
  if (!state.collapsedFolderIds) state.collapsedFolderIds = new Set();
  if (state.collapsedFolderIds.has(folderId)) {
    state.collapsedFolderIds.delete(folderId);
  } else {
    state.collapsedFolderIds.add(folderId);
  }
  onSaveCollapsedFolders?.();
  onRender?.();
}

function setSidebarHidden({ hidden, state, onRender }) {
  state.sidebarHidden = hidden;
  localStorage.setItem("gemma4.sidebarHidden", String(hidden));
  onRender?.();
}

function shouldStartSidebarHidden({ isMobile, storedValue }) {
  if (isMobile) return true;
  return storedValue === "true";
}

function shouldCloseMobileSidebar({
  isMobile,
  sidebarHidden,
  targetInsideSidebar,
  targetInsideToggle,
}) {
  return Boolean(isMobile && !sidebarHidden && !targetInsideSidebar && !targetInsideToggle);
}

function shouldHideSidebarAfterManagementOpen({ isMobile, sidebarHidden }) {
  return Boolean(isMobile && !sidebarHidden);
}

function setSidebarWidth({ state, width }) {
  state.sidebarWidth = Math.min(420, Math.max(220, Math.round(width)));
  localStorage.setItem("gemma4.sidebarWidth", String(state.sidebarWidth));
  document.documentElement.style.setProperty("--sidebar-width", `${state.sidebarWidth}px`);
}

function applySidebarLayout({ els, state, t }) {
  document.documentElement.style.setProperty("--sidebar-width", `${state.sidebarWidth}px`);
  document.body.classList.toggle("sidebar-hidden", state.sidebarHidden);
  els.sidebarToggle.hidden = !state.sidebarHidden;
  const collapseLabel = state.sidebarHidden ? t("sidebar.show") : t("sidebar.hide");
  els.sidebarCollapse?.setAttribute("aria-label", collapseLabel);
  els.sidebarCollapse?.setAttribute("title", collapseLabel);
}

function bindSidebarEvents({ els, state, onRender }) {
  els.sidebarSearch?.addEventListener("input", () => {
    state.sidebarQuery = els.sidebarSearch.value;
    onRender?.();
  });

  els.sidebarResizer?.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    els.sidebarResizer.setPointerCapture(event.pointerId);
    document.body.classList.add("resizing-sidebar");
    const onMove = (moveEvent) => setSidebarWidth({ state, width: moveEvent.clientX });
    const onUp = () => {
      document.body.classList.remove("resizing-sidebar");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  });

  els.sidebarToggle?.addEventListener("click", () => setSidebarHidden({ hidden: false, state, onRender }));
  els.sidebarCollapse?.addEventListener("click", () => setSidebarHidden({ hidden: !state.sidebarHidden, state, onRender }));

  document.addEventListener("pointerdown", (event) => {
    const target = event.target;
    if (shouldCloseMobileSidebar({
      isMobile: window.matchMedia("(max-width: 760px)").matches,
      sidebarHidden: state.sidebarHidden,
      targetInsideSidebar: Boolean(els.sidebar?.contains(target)),
      targetInsideToggle: Boolean(els.sidebarToggle?.contains(target)),
    })) {
      setSidebarHidden({ hidden: true, state, onRender });
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && window.matchMedia("(max-width: 760px)").matches && !state.sidebarHidden) {
      setSidebarHidden({ hidden: true, state, onRender });
    }
  });
}

function createFolderInState({
  state,
  name,
  createId = () => crypto.randomUUID(),
  now = () => Date.now(),
}) {
  const folder = {
    id: createId(),
    name,
    workspaceRoot: "",
    selectedFiles: [],
    trainingSetId: "",
    createdAt: now(),
  };
  return {
    activeFolderId: folder.id,
    folder,
    folders: [folder, ...state.folders],
  };
}

function createSessionInState({
  state,
  folderId = state.activeFolderId,
  folderName,
  sessionTitle,
  createId = () => crypto.randomUUID(),
  now = () => Date.now(),
}) {
  let folders = state.folders;
  let activeFolderId = folderId;
  let createdFolder = null;
  if (!activeFolderId) {
    const folderState = createFolderInState({ state, name: folderName, createId, now });
    folders = folderState.folders;
    activeFolderId = folderState.activeFolderId;
    createdFolder = folderState.folder;
  }
  const session = {
    id: createId(),
    title: sessionTitle,
    folderId: activeFolderId,
    messages: [],
    createdAt: now(),
  };
  return {
    activeFolderId,
    activeId: session.id,
    createdFolder,
    folders,
    session,
    sessions: [session, ...state.sessions],
  };
}

function renameFolderInState({ state, folderId, value }) {
  const name = String(value || "").trim();
  return {
    changed: Boolean(name),
    editingFolderId: null,
    folders: name
      ? state.folders.map((folder) => (folder.id === folderId ? { ...folder, name } : folder))
      : state.folders,
  };
}

function renameSessionInState({ state, sessionId, value }) {
  const title = String(value || "").trim();
  return {
    changed: Boolean(title),
    editingSessionId: null,
    sessions: title
      ? state.sessions.map((session) => (session.id === sessionId ? { ...session, title } : session))
      : state.sessions,
  };
}

function selectFolderInState({ state, folderId, openWorkspace = false }) {
  const firstSession = state.sessions.find((session) => session.folderId === folderId);
  return {
    activeFolderId: folderId,
    activeId: firstSession?.id || null,
    editingFolderId: null,
    editingSessionId: null,
    workspaceOpen: Boolean(openWorkspace),
  };
}

function selectSessionInState({ folderId, sessionId }) {
  return {
    activeFolderId: folderId,
    activeId: sessionId,
    editingFolderId: null,
    editingSessionId: null,
  };
}

function startSessionRenameInState({ sessionId }) {
  return {
    editingFolderId: null,
    editingSessionId: sessionId,
  };
}

function deleteFolderFromState({ state, folder }) {
  const deletedSessions = state.sessions
    .filter((session) => session.folderId === folder.id)
    .map((session) => ({ ...session, messages: Array.isArray(session.messages) ? [...session.messages] : [] }));
  const folders = state.folders.filter((item) => item.id !== folder.id);
  const sessions = state.sessions.filter((session) => session.folderId !== folder.id);
  let activeFolderId = state.activeFolderId;
  let activeId = state.activeId;
  let workspaceOpen = state.workspaceOpen;
  if (activeFolderId === folder.id) {
    activeFolderId = folders[0]?.id || null;
  }
  if (folders.length === 0) {
    activeFolderId = null;
    activeId = null;
    workspaceOpen = false;
  }
  return {
    activeFolderId,
    activeId,
    folders,
    lastDeleted: {
      type: "folder",
      folder: { ...folder, selectedFiles: [...(folder.selectedFiles || [])] },
      folderIndex: state.folders.findIndex((item) => item.id === folder.id),
      sessions: deletedSessions,
      activeId: state.activeId,
    },
    sessions,
    workspaceOpen,
  };
}

function deleteSessionFromState({ state, session }) {
  return {
    lastDeleted: {
      type: "session",
      session: { ...session, messages: Array.isArray(session.messages) ? [...session.messages] : [] },
      sessionIndex: state.sessions.findIndex((item) => item.id === session.id),
    },
    sessions: state.sessions.filter((item) => item.id !== session.id),
    shouldSelectFirstSession: state.activeId === session.id,
  };
}

function restoreDeletedToState({ state }) {
  const deleted = state.lastDeleted;
  if (!deleted) return null;
  if (deleted.type === "folder") {
    const folders = [...state.folders];
    folders.splice(Math.min(deleted.folderIndex, folders.length), 0, deleted.folder);
    return {
      activeFolderId: deleted.folder.id,
      activeId: deleted.activeId || deleted.sessions?.[0]?.id || null,
      folders,
      lastDeleted: null,
      sessions: [...state.sessions, ...(deleted.sessions || [])],
      shouldSaveFolders: true,
      shouldSaveSessions: true,
      shouldSyncWorkspace: true,
      shouldLoadWorkspace: true,
    };
  }
  if (deleted.type === "session") {
    const sessions = [...state.sessions];
    sessions.splice(Math.min(deleted.sessionIndex, sessions.length), 0, deleted.session);
    return {
      activeFolderId: deleted.session.folderId,
      activeId: deleted.session.id,
      lastDeleted: null,
      sessions,
      shouldSaveFolders: false,
      shouldSaveSessions: true,
      shouldSyncWorkspace: false,
      shouldLoadWorkspace: false,
    };
  }
  return null;
}

function renderGemmaSidebar(deps) {
  const {
    commitFolderRename,
    commitSessionRename,
    deleteFolder,
    deleteSession,
    els,
    loadWorkspace,
    newSession,
    saveCollapsedFolders,
    render,
    saveFolders,
    startFolderRename,
    startSessionRename,
    state,
    syncWorkspaceFromActiveFolder,
    t,
  } = deps;
  els.folderList.innerHTML = "";
  const folders = visibleFolders({ state, sessionsForFolder });
  if (folders.length === 0) {
    const empty = document.createElement("div");
    empty.className = "folder-empty sidebar-empty";
    empty.textContent = t("folder.none");
    els.folderList.append(empty);
    return;
  }
  for (const folder of folders) {
    const group = document.createElement("div");
    group.className = `folder-group${folder.id === state.activeFolderId ? " active" : ""}`;

    const row = document.createElement("div");
    const sessions = visibleSessionsForFolder({ state, folder, sessionsForFolder });
    const hasQuery = Boolean(normalizedSidebarQuery(state));
    const collapsed = !hasQuery && Boolean(state.collapsedFolderIds?.has(folder.id));
    row.className = `folder-item${folder.id === state.activeFolderId ? " active" : ""}${collapsed ? " collapsed" : ""}`;

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
      const collapse = document.createElement("button");
      collapse.type = "button";
      collapse.className = "folder-collapse";
      collapse.setAttribute("aria-expanded", String(!collapsed));
      collapse.setAttribute("aria-label", collapsed ? t("folder.expand") : t("folder.collapse"));
      collapse.title = collapsed ? t("folder.expand") : t("folder.collapse");
      collapse.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>';
      collapse.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleFolderCollapsed({
          folderId: folder.id,
          state,
          onSaveCollapsedFolders: saveCollapsedFolders,
          onRender: render,
        });
      });
      const button = document.createElement("button");
      button.type = "button";
      button.className = "item-main";
      const content = document.createElement("span");
      content.className = "item-content";
      const name = document.createElement("span");
      name.className = "folder-name";
      name.textContent = folder.name;
      const meta = document.createElement("small");
      const metaParts = [folder.workspaceRoot ? t("folder.localReady") : t("folder.localMissing")];
      if (folder.trainingSetId) metaParts.push(t("folder.trainingReady"));
      if (sessions.length > 0) metaParts.push(t("folder.chatCount", { count: sessions.length }));
      meta.textContent = metaParts.join(" / ");
      content.append(name, meta);
      button.append(sidebarIcon("folder"), content);
      button.addEventListener("click", async () => {
        Object.assign(state, selectFolderInState({ state, folderId: folder.id, openWorkspace: false }));
        syncWorkspaceFromActiveFolder();
        saveFolders();
        render();
        if (state.workspaceRoot) await loadWorkspace();
      });
      row.append(collapse, button);
    }

    const actions = document.createElement("div");
    actions.className = "item-actions";
    const addChat = document.createElement("button");
    addChat.type = "button";
    addChat.className = "item-action-primary";
    addChat.textContent = t("folder.add");
    addChat.title = t("folder.addTitle");
    addChat.addEventListener("click", () => {
      Object.assign(state, selectFolderInState({ state, folderId: folder.id, openWorkspace: state.workspaceOpen }));
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
    sessionList.className = `folder-session-list${collapsed ? " collapsed" : ""}`;
    sessionList.hidden = collapsed;
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
        const title = document.createElement("span");
        title.className = "session-title";
        title.textContent = session.title;
        button.append(sidebarIcon("chat"), title);
        button.addEventListener("click", async () => {
          Object.assign(state, selectSessionInState({ folderId: folder.id, sessionId: session.id }));
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

window.GEMMA_SIDEBAR = {
  applySidebarLayout,
  bindSidebarEvents,
  createFolderInState,
  createSessionInState,
  deleteFolderFromState,
  deleteSessionFromState,
  renderFolders: renderGemmaSidebar,
  renameFolderInState,
  renameSessionInState,
  restoreDeletedToState,
  selectFolderInState,
  selectSessionInState,
  setSidebarHidden,
  setSidebarWidth,
  shouldCloseMobileSidebar,
  shouldHideSidebarAfterManagementOpen,
  shouldStartSidebarHidden,
  startSessionRenameInState,
  visibleFolders,
  visibleSessionsForFolder,
};
})();
