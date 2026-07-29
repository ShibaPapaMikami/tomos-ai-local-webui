const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("web/local-storage-transfer.js", "utf8");
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context, { filename: "web/local-storage-transfer.js" });

const {
  TOMOS_LOCAL_STORAGE_EXPORT_TYPE,
  TOMOS_LOCAL_STORAGE_EXPORT_VERSION,
  TOMOS_LOCAL_STORAGE_MAX_IMPORT_BYTES,
  TOMOS_LOCAL_STORAGE_ALLOWED_KEYS,
  buildTomosLocalStorageExport,
  previewTomosLocalStorageImport,
  applyTomosLocalStorageImport,
} = context.window.TOMOS_LOCAL_STORAGE_TRANSFER;

const EXPECTED_ALLOWED_KEYS = [
  "gemma4.sessions",
  "gemma4.folders",
  "gemma4.activeFolderId",
  "gemma4.foldersInitialized",
  "gemma4.collapsedFolderIds",
  "gemma4.trainingSets",
  "gemma4.activeTrainingSetId",
  "gemma4.studyPacks",
  "gemma4.importedStudyPackDefinitions",
  "gemma4.selectedStudyPackModes",
  "gemma4.character",
  "gemma4.characterMemorySets",
  "gemma4.personRelationship.people.v1",
  "gemma4.personRelationship.self.v1",
  "gemma4.theme",
  "gemma4.language",
  "gemma4.responseMode",
  "gemma4.thinkingMode",
  "gemma4.enterToSend",
  "gemma4.sidebarHidden",
  "gemma4.sidebarWidth",
  "gemma4.weatherLocation",
  "gemma4.asrModel",
  "gemma4.asrPartialMode",
  "gemma4.asrPartialModeMigratedToLocal",
  "gemma4.asrPartialIntervalSeconds",
  "gemma4.micGain",
  "gemma4.composerModel",
  "gemma4.composerModelVisibleModels",
  "gemma4.model.chat",
  "gemma4.model.coding",
  "gemma4.model.translation",
  "gemma4.showExperimentalModels",
];

assert.equal(TOMOS_LOCAL_STORAGE_EXPORT_TYPE, "tomos-local-storage-export");
assert.equal(TOMOS_LOCAL_STORAGE_EXPORT_VERSION, 1);
assert.equal(TOMOS_LOCAL_STORAGE_MAX_IMPORT_BYTES, 10 * 1024 * 1024);
assert.deepEqual(Array.from(TOMOS_LOCAL_STORAGE_ALLOWED_KEYS), EXPECTED_ALLOWED_KEYS);

function memoryStorage(entries = {}, options = {}) {
  const data = new Map(Object.entries(entries));
  const operations = [];
  let setCount = 0;
  let removeCount = 0;
  return {
    data,
    operations,
    getItem(key) {
      operations.push(["get", key]);
      if (options.failGetKey === key) throw new Error("private get failure");
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      operations.push(["set", key, value]);
      setCount += 1;
      if (options.failSetCounts?.includes(setCount)) throw new Error("private set failure");
      data.set(key, String(value));
    },
    removeItem(key) {
      operations.push(["remove", key]);
      removeCount += 1;
      if (options.failRemoveCounts?.includes(removeCount)) throw new Error("private remove failure");
      data.delete(key);
    },
  };
}

const exportStorage = memoryStorage({
  "gemma4.theme": "light",
  "gemma4.sessions": "[{\"id\":\"safe\"}]",
  "gemma4.theme.child": "prefix-must-not-match",
  "gemma4.sessionToken": "secret-token-value",
  "gemma4.workspacePath": "/Users/private/workspace",
  "gemma4.microphoneDeviceId": "private-device-id",
  "gemma4.externalLlmUrl": "https://private.example.test",
  "gemma4.plugin.auth": "private-plugin-value",
  "gemma4.mobile.connection": "private-mobile-value",
  "gemma4.language": 42,
});
const exported = buildTomosLocalStorageExport(
  exportStorage,
  "2026-07-27T00:00:00.000Z",
);
assert.deepEqual(JSON.parse(JSON.stringify(exported)), {
  type: "tomos-local-storage-export",
  version: 1,
  exportedAt: "2026-07-27T00:00:00.000Z",
  values: {
    "gemma4.sessions": "[{\"id\":\"safe\"}]",
    "gemma4.theme": "light",
  },
});
assert.deepEqual(Object.keys(exported), ["type", "version", "exportedAt", "values"]);
assert.doesNotMatch(
  JSON.stringify(exported),
  /prefix-must-not-match|secret-token-value|private-device-id|private-plugin-value|private-mobile-value|private\.example|Users\/private/,
);

const importPayload = {
  type: "tomos-local-storage-export",
  version: 1,
  exportedAt: "2026-07-27T00:00:00.000Z",
  values: {
    "gemma4.theme": "dark",
    "gemma4.language": "ja",
    "gemma4.unknownFutureKey": "unknown-value",
    "gemma4.sessionToken": "token-value",
    "gemma4.workspacePath": "/private/path",
    "gemma4.microphoneDeviceId": "device-value",
    "gemma4.externalLlmUrl": "https://external.example.test",
    "gemma4.plugin.auth": "plugin-value",
    "gemma4.mobile.connection": "mobile-value",
    "gemma4.responseMode": { invalid: "not-a-string" },
  },
};
const preview = previewTomosLocalStorageImport(importPayload);
assert.deepEqual(JSON.parse(JSON.stringify(preview)), {
  status: "ready",
  acceptedKeys: ["gemma4.language", "gemma4.theme"],
  rejectedCount: 8,
  exportedAt: "2026-07-27T00:00:00.000Z",
});
assert.doesNotMatch(
  JSON.stringify(preview),
  /dark|unknown-value|token-value|private\/path|device-value|external\.example|plugin-value|mobile-value|not-a-string/,
);

[
  null,
  [],
  {
    type: "wrong-type",
    version: 1,
    exportedAt: "2026-07-27T00:00:00.000Z",
    values: {},
  },
  {
    type: "tomos-local-storage-export",
    version: 2,
    exportedAt: "2026-07-27T00:00:00.000Z",
    values: {},
  },
  {
    type: "tomos-local-storage-export",
    version: 1,
    exportedAt: "not-a-date",
    values: {},
  },
  {
    type: "tomos-local-storage-export",
    version: 1,
    exportedAt: "2026-07-27T00:00:00.000Z",
    values: [],
  },
  {
    type: "tomos-local-storage-export",
    version: 1,
    exportedAt: "2026-07-27T00:00:00.000Z",
    values: {},
    unexpected: true,
  },
].forEach((payload) => {
  assert.deepEqual(JSON.parse(JSON.stringify(previewTomosLocalStorageImport(payload))), {
    status: "invalid",
    acceptedKeys: [],
    rejectedCount: 0,
    exportedAt: "",
  });
});

const unapprovedStorage = memoryStorage({ "gemma4.theme": "light" });
assert.deepEqual(
  JSON.parse(JSON.stringify(applyTomosLocalStorageImport(unapprovedStorage, preview, false))),
  { status: "not-approved", importedCount: 0 },
);
assert.deepEqual(unapprovedStorage.operations, []);

const applyStorage = memoryStorage({ "gemma4.theme": "light" });
assert.deepEqual(
  JSON.parse(JSON.stringify(applyTomosLocalStorageImport(applyStorage, preview, true))),
  { status: "completed", importedCount: 2 },
);
assert.equal(applyStorage.data.get("gemma4.theme"), "dark");
assert.equal(applyStorage.data.get("gemma4.language"), "ja");

const rollbackPreview = previewTomosLocalStorageImport({
  type: "tomos-local-storage-export",
  version: 1,
  exportedAt: "2026-07-27T00:00:00.000Z",
  values: {
    "gemma4.language": "en",
    "gemma4.responseMode": "precise",
    "gemma4.theme": "dark",
  },
});
const rollbackStorage = memoryStorage(
  {
    "gemma4.language": "ja",
    "gemma4.theme": "light",
  },
  { failSetCounts: [2] },
);
assert.deepEqual(
  JSON.parse(JSON.stringify(applyTomosLocalStorageImport(rollbackStorage, rollbackPreview, true))),
  { status: "rolled-back", importedCount: 0 },
);
assert.equal(rollbackStorage.data.get("gemma4.language"), "ja");
assert.equal(rollbackStorage.data.get("gemma4.theme"), "light");
assert.equal(rollbackStorage.data.has("gemma4.responseMode"), false);
assert.ok(
  rollbackStorage.operations.some(([operation, key]) => operation === "remove" && key === "gemma4.responseMode"),
  "a key that did not exist before import must be removed during rollback",
);

const rollbackFailureStorage = memoryStorage(
  {
    "gemma4.language": "ja",
    "gemma4.theme": "light",
  },
  { failSetCounts: [2, 3] },
);
assert.deepEqual(
  JSON.parse(JSON.stringify(
    applyTomosLocalStorageImport(rollbackFailureStorage, rollbackPreview, true),
  )),
  { status: "rollback-failed", importedCount: 0 },
);

const snapshotFailureStorage = memoryStorage(
  { "gemma4.theme": "light" },
  { failGetKey: "gemma4.language" },
);
assert.deepEqual(
  JSON.parse(JSON.stringify(
    applyTomosLocalStorageImport(snapshotFailureStorage, preview, true),
  )),
  { status: "snapshot-failed", importedCount: 0 },
);
assert.equal(
  snapshotFailureStorage.operations.some(([operation]) => operation === "set" || operation === "remove"),
  false,
);

console.log("local storage transfer tests passed");
