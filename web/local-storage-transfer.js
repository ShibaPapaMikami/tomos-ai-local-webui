window.TOMOS_LOCAL_STORAGE_TRANSFER = (() => {
  const TOMOS_LOCAL_STORAGE_EXPORT_TYPE = "tomos-local-storage-export";
  const TOMOS_LOCAL_STORAGE_EXPORT_VERSION = 1;
  const TOMOS_LOCAL_STORAGE_MAX_IMPORT_BYTES = 10 * 1024 * 1024;
  const TOMOS_LOCAL_STORAGE_ALLOWED_KEYS = Object.freeze([
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
  ]);
  const allowedKeySet = new Set(TOMOS_LOCAL_STORAGE_ALLOWED_KEYS);
  const acceptedValuesByPreview = new WeakMap();

  function isRecord(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function isExactIsoDate(value) {
    if (typeof value !== "string") return false;
    const timestamp = Date.parse(value);
    return Number.isFinite(timestamp) && new Date(timestamp).toISOString() === value;
  }

  function invalidPreview() {
    return {
      status: "invalid",
      acceptedKeys: [],
      rejectedCount: 0,
      exportedAt: "",
    };
  }

  function buildTomosLocalStorageExport(storage, nowIso) {
    if (!storage || typeof storage.getItem !== "function" || !isExactIsoDate(nowIso)) {
      throw new Error("local_storage_export_invalid");
    }
    const values = {};
    TOMOS_LOCAL_STORAGE_ALLOWED_KEYS.forEach((key) => {
      const value = storage.getItem(key);
      if (typeof value === "string") values[key] = value;
    });
    return {
      type: TOMOS_LOCAL_STORAGE_EXPORT_TYPE,
      version: TOMOS_LOCAL_STORAGE_EXPORT_VERSION,
      exportedAt: nowIso,
      values,
    };
  }

  function previewTomosLocalStorageImport(payload) {
    if (!isRecord(payload)) return invalidPreview();
    const envelopeKeys = Object.keys(payload).sort();
    const expectedEnvelopeKeys = ["exportedAt", "type", "values", "version"];
    if (
      envelopeKeys.length !== expectedEnvelopeKeys.length
      || envelopeKeys.some((key, index) => key !== expectedEnvelopeKeys[index])
      || payload.type !== TOMOS_LOCAL_STORAGE_EXPORT_TYPE
      || payload.version !== TOMOS_LOCAL_STORAGE_EXPORT_VERSION
      || !isExactIsoDate(payload.exportedAt)
      || !isRecord(payload.values)
    ) {
      return invalidPreview();
    }

    const acceptedValues = new Map();
    let rejectedCount = 0;
    Object.entries(payload.values).forEach(([key, value]) => {
      if (allowedKeySet.has(key) && typeof value === "string") {
        acceptedValues.set(key, value);
      } else {
        rejectedCount += 1;
      }
    });
    const acceptedKeys = Array.from(acceptedValues.keys()).sort();
    const preview = {
      status: "ready",
      acceptedKeys,
      rejectedCount,
      exportedAt: payload.exportedAt,
    };
    acceptedValuesByPreview.set(preview, acceptedValues);
    return preview;
  }

  function applyTomosLocalStorageImport(storage, preview, approved) {
    if (approved !== true) return { status: "not-approved", importedCount: 0 };
    const acceptedValues = isRecord(preview) ? acceptedValuesByPreview.get(preview) : null;
    if (
      !storage
      || typeof storage.getItem !== "function"
      || typeof storage.setItem !== "function"
      || typeof storage.removeItem !== "function"
      || preview?.status !== "ready"
      || !(acceptedValues instanceof Map)
    ) {
      return { status: "invalid", importedCount: 0 };
    }

    const acceptedKeys = Array.from(acceptedValues.keys()).sort();
    const snapshot = new Map();
    try {
      acceptedKeys.forEach((key) => {
        const value = storage.getItem(key);
        snapshot.set(key, {
          existed: value !== null,
          value,
        });
      });
    } catch {
      return { status: "snapshot-failed", importedCount: 0 };
    }

    try {
      acceptedKeys.forEach((key) => {
        storage.setItem(key, acceptedValues.get(key));
      });
      return { status: "completed", importedCount: acceptedKeys.length };
    } catch {
      let rollbackFailed = false;
      acceptedKeys.forEach((key) => {
        const original = snapshot.get(key);
        try {
          if (original.existed) {
            storage.setItem(key, original.value);
          } else {
            storage.removeItem(key);
          }
        } catch {
          rollbackFailed = true;
        }
      });
      return {
        status: rollbackFailed ? "rollback-failed" : "rolled-back",
        importedCount: 0,
      };
    }
  }

  return {
    TOMOS_LOCAL_STORAGE_EXPORT_TYPE,
    TOMOS_LOCAL_STORAGE_EXPORT_VERSION,
    TOMOS_LOCAL_STORAGE_MAX_IMPORT_BYTES,
    TOMOS_LOCAL_STORAGE_ALLOWED_KEYS,
    buildTomosLocalStorageExport,
    previewTomosLocalStorageImport,
    applyTomosLocalStorageImport,
  };
})();
