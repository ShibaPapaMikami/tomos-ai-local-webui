const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/sidebar.js", "utf8"), context, { filename: "web/sidebar.js" });

const {
  createFolderInState,
  createSessionInState,
  deleteFolderFromState,
  deleteSessionFromState,
  renameFolderInState,
  renameSessionInState,
  restoreDeletedToState,
  selectFolderInState,
  selectSessionInState,
  shouldCloseMobileSidebar,
  shouldStartSidebarHidden,
  startSessionRenameInState,
  visibleFolders,
  visibleSessionsForFolder,
} = context.window.GEMMA_SIDEBAR;

function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

const state = {
  sidebarQuery: "",
  folders: [
    { id: "folder-1", name: "英語" },
    { id: "folder-2", name: "Python課題" },
  ],
};
const sessions = [
  { id: "chat-1", folderId: "folder-1", title: "翻訳練習" },
  { id: "chat-2", folderId: "folder-1", title: "発音メモ" },
  { id: "chat-3", folderId: "folder-2", title: "テトリス" },
];
const sessionsForFolder = (folderId) => sessions.filter((session) => session.folderId === folderId);

assert.equal(
  shouldStartSidebarHidden({ isMobile: true, storedValue: "false" }),
  true,
  "mobile should start with the sidebar drawer closed even after desktop use",
);
assert.equal(
  shouldStartSidebarHidden({ isMobile: false, storedValue: "false" }),
  false,
  "desktop should keep the stored visible sidebar state",
);
assert.equal(
  shouldStartSidebarHidden({ isMobile: false, storedValue: "true" }),
  true,
  "desktop should keep the stored hidden sidebar state",
);
assert.equal(
  shouldCloseMobileSidebar({
    isMobile: true,
    sidebarHidden: false,
    targetInsideSidebar: false,
    targetInsideToggle: false,
  }),
  true,
  "mobile sidebar should close when tapping outside the drawer",
);
assert.equal(
  shouldCloseMobileSidebar({
    isMobile: true,
    sidebarHidden: false,
    targetInsideSidebar: true,
    targetInsideToggle: false,
  }),
  false,
  "mobile sidebar should stay open when tapping inside the drawer",
);
assert.equal(
  shouldCloseMobileSidebar({
    isMobile: false,
    sidebarHidden: false,
    targetInsideSidebar: false,
    targetInsideToggle: false,
  }),
  false,
  "desktop sidebar should not close from outside click",
);

const folderCreation = createFolderInState({
  state,
  name: "新規",
  createId: () => "folder-new",
  now: () => 1000,
});

assert.equal(folderCreation.activeFolderId, "folder-new");
assert.deepEqual(plain(folderCreation.folders.map((folder) => folder.id)), ["folder-new", "folder-1", "folder-2"]);
assert.deepEqual(plain(folderCreation.folder), {
  id: "folder-new",
  name: "新規",
  workspaceRoot: "",
  selectedFiles: [],
  trainingSetId: "",
  createdAt: 1000,
});

let idIndex = 0;
const ids = ["folder-auto", "chat-auto"];
const sessionCreationWithoutFolder = createSessionInState({
  state: { folders: [], sessions: [], activeFolderId: null },
  folderName: "自動フォルダー",
  sessionTitle: "新規チャット",
  createId: () => ids[idIndex++],
  now: () => 2000,
});

assert.equal(sessionCreationWithoutFolder.activeFolderId, "folder-auto");
assert.equal(sessionCreationWithoutFolder.activeId, "chat-auto");
assert.deepEqual(plain(sessionCreationWithoutFolder.folders.map((folder) => folder.id)), ["folder-auto"]);
assert.deepEqual(plain(sessionCreationWithoutFolder.sessions.map((session) => session.id)), ["chat-auto"]);
assert.equal(sessionCreationWithoutFolder.sessions[0].folderId, "folder-auto");

const sessionCreationWithFolder = createSessionInState({
  state: { folders: state.folders, sessions, activeFolderId: "folder-1" },
  folderId: "folder-2",
  folderName: "未使用",
  sessionTitle: "追加チャット",
  createId: () => "chat-new",
  now: () => 3000,
});

assert.equal(sessionCreationWithFolder.activeFolderId, "folder-2");
assert.equal(sessionCreationWithFolder.activeId, "chat-new");
assert.deepEqual(plain(sessionCreationWithFolder.folders.map((folder) => folder.id)), ["folder-1", "folder-2"]);
assert.deepEqual(plain(sessionCreationWithFolder.sessions.map((session) => session.id)), ["chat-new", "chat-1", "chat-2", "chat-3"]);
assert.equal(sessionCreationWithFolder.sessions[0].folderId, "folder-2");

const folderRename = renameFolderInState({
  state,
  folderId: "folder-1",
  value: " 英語の練習 ",
});

assert.equal(folderRename.changed, true);
assert.equal(folderRename.editingFolderId, null);
assert.equal(folderRename.folders[0].name, "英語の練習");
assert.equal(folderRename.folders[1].name, "Python課題");

const blankFolderRename = renameFolderInState({
  state,
  folderId: "folder-1",
  value: "   ",
});

assert.equal(blankFolderRename.changed, false);
assert.equal(blankFolderRename.folders[0].name, "英語");

const sessionRename = renameSessionInState({
  state: { sessions },
  sessionId: "chat-1",
  value: " 翻訳チェック ",
});

assert.equal(sessionRename.changed, true);
assert.equal(sessionRename.editingSessionId, null);
assert.equal(sessionRename.sessions[0].title, "翻訳チェック");
assert.equal(sessionRename.sessions[1].title, "発音メモ");

const blankSessionRename = renameSessionInState({
  state: { sessions },
  sessionId: "chat-1",
  value: "",
});

assert.equal(blankSessionRename.changed, false);
assert.equal(blankSessionRename.sessions[0].title, "翻訳練習");

const folderSelection = selectFolderInState({
  state: {
    sessions,
  },
  folderId: "folder-1",
  openWorkspace: true,
});

assert.deepEqual(plain(folderSelection), {
  activeFolderId: "folder-1",
  activeId: "chat-1",
  editingFolderId: null,
  editingSessionId: null,
  workspaceOpen: true,
});

const emptyFolderSelection = selectFolderInState({
  state: {
    sessions,
  },
  folderId: "folder-empty",
  openWorkspace: false,
});

assert.equal(emptyFolderSelection.activeFolderId, "folder-empty");
assert.equal(emptyFolderSelection.activeId, null);
assert.equal(emptyFolderSelection.workspaceOpen, false);

assert.deepEqual(
  plain(selectSessionInState({ folderId: "folder-2", sessionId: "chat-3" })),
  {
    activeFolderId: "folder-2",
    activeId: "chat-3",
    editingFolderId: null,
    editingSessionId: null,
  },
);

assert.deepEqual(
  plain(startSessionRenameInState({ sessionId: "chat-2" })),
  {
    editingFolderId: null,
    editingSessionId: "chat-2",
  },
);

assert.deepEqual(
  visibleFolders({ state, sessionsForFolder }).map((folder) => folder.id),
  ["folder-1", "folder-2"],
);

state.sidebarQuery = "英語";
assert.deepEqual(
  visibleFolders({ state, sessionsForFolder }).map((folder) => folder.id),
  ["folder-1"],
);
assert.deepEqual(
  visibleSessionsForFolder({ state, folder: state.folders[0], sessionsForFolder }).map((session) => session.id),
  ["chat-1", "chat-2"],
);

state.sidebarQuery = "テトリス";
assert.deepEqual(
  visibleFolders({ state, sessionsForFolder }).map((folder) => folder.id),
  ["folder-2"],
);
assert.deepEqual(
  visibleSessionsForFolder({ state, folder: state.folders[1], sessionsForFolder }).map((session) => session.id),
  ["chat-3"],
);

const folderDeletion = deleteFolderFromState({
  state: {
    ...state,
    activeFolderId: "folder-1",
    activeId: "chat-1",
    workspaceOpen: true,
    folders: [
      { id: "folder-1", name: "英語", selectedFiles: ["memo.md"] },
      { id: "folder-2", name: "Python課題" },
    ],
    sessions,
  },
  folder: { id: "folder-1", name: "英語", selectedFiles: ["memo.md"] },
});

assert.deepEqual(folderDeletion.folders.map((folder) => folder.id), ["folder-2"]);
assert.deepEqual(folderDeletion.sessions.map((session) => session.id), ["chat-3"]);
assert.equal(folderDeletion.activeFolderId, "folder-2");
assert.equal(folderDeletion.lastDeleted.type, "folder");
assert.deepEqual(folderDeletion.lastDeleted.sessions.map((session) => session.id), ["chat-1", "chat-2"]);
assert.deepEqual(plain(folderDeletion.lastDeleted.folder.selectedFiles), ["memo.md"]);

const sessionDeletion = deleteSessionFromState({
  state: {
    activeId: "chat-2",
    sessions,
  },
  session: sessions[1],
});

assert.deepEqual(sessionDeletion.sessions.map((session) => session.id), ["chat-1", "chat-3"]);
assert.equal(sessionDeletion.shouldSelectFirstSession, true);
assert.equal(sessionDeletion.lastDeleted.type, "session");
assert.equal(sessionDeletion.lastDeleted.session.id, "chat-2");

const folderRestore = restoreDeletedToState({
  state: {
    folders: folderDeletion.folders,
    sessions: folderDeletion.sessions,
    lastDeleted: folderDeletion.lastDeleted,
  },
});

assert.deepEqual(plain(folderRestore.folders.map((folder) => folder.id)), ["folder-1", "folder-2"]);
assert.deepEqual(plain(folderRestore.sessions.map((session) => session.id)), ["chat-3", "chat-1", "chat-2"]);
assert.equal(folderRestore.activeFolderId, "folder-1");
assert.equal(folderRestore.activeId, "chat-1");
assert.equal(folderRestore.lastDeleted, null);
assert.equal(folderRestore.shouldSaveFolders, true);
assert.equal(folderRestore.shouldSaveSessions, true);

const sessionRestore = restoreDeletedToState({
  state: {
    sessions: sessionDeletion.sessions,
    lastDeleted: sessionDeletion.lastDeleted,
  },
});

assert.deepEqual(plain(sessionRestore.sessions.map((session) => session.id)), ["chat-1", "chat-2", "chat-3"]);
assert.equal(sessionRestore.activeFolderId, "folder-1");
assert.equal(sessionRestore.activeId, "chat-2");
assert.equal(sessionRestore.lastDeleted, null);
assert.equal(sessionRestore.shouldSaveFolders, false);
assert.equal(sessionRestore.shouldSaveSessions, true);

console.log("sidebar helper tests passed");
