(function () {
  const TRAINING_SETS_KEY = "gemma4.trainingSets";
  const ACTIVE_TRAINING_SET_KEY = "gemma4.activeTrainingSetId";

  function loadTrainingSets(storage = window.localStorage) {
    try {
      const sets = JSON.parse(storage.getItem(TRAINING_SETS_KEY) || "[]");
      return Array.isArray(sets) ? sets : [];
    } catch {
      return [];
    }
  }

  function saveTrainingSets({ sets, activeTrainingSetId, storage = window.localStorage }) {
    storage.setItem(TRAINING_SETS_KEY, JSON.stringify(sets));
    storage.setItem(ACTIVE_TRAINING_SET_KEY, activeTrainingSetId || "");
  }

  function createTrainingSetRecord(name, { defaultName, createId, now }) {
    const trimmed = String(name || "").trim() || defaultName;
    const timestamp = now();
    return {
      id: createId(),
      name: trimmed,
      examples: [],
      createdAt: timestamp,
      updatedAt: timestamp,
    };
  }

  function createAndSelectTrainingSet({ sets, name, defaultName, createId, now }) {
    const set = createTrainingSetRecord(name, { defaultName, createId, now });
    return {
      set,
      sets: [set, ...sets],
      activeTrainingSetId: set.id,
    };
  }

  function trainingSetById(sets, id) {
    return sets.find((set) => set.id === id) || null;
  }

  function activeTrainingSet(sets, activeTrainingSetId) {
    return trainingSetById(sets, activeTrainingSetId) || sets[0] || null;
  }

  function normalizeTrainingSets({ sets, folders, activeTrainingSetId, defaultName, createId, now }) {
    for (const set of sets) {
      if (!set.id) set.id = createId();
      if (!set.name) set.name = defaultName;
      if (!Array.isArray(set.examples)) set.examples = [];
      if (!set.createdAt) set.createdAt = now();
      if (!set.updatedAt) set.updatedAt = set.createdAt;
    }
    for (const folder of folders) {
      if (folder.trainingSetId && !trainingSetById(sets, folder.trainingSetId)) {
        folder.trainingSetId = "";
      }
    }
    return activeTrainingSetId && trainingSetById(sets, activeTrainingSetId)
      ? activeTrainingSetId
      : sets[0]?.id || "";
  }

  function removeTrainingSet(sets, id) {
    return sets.filter((set) => set.id !== id);
  }

  function clearFolderTrainingSet(folders, id) {
    for (const folder of folders) {
      if (folder.trainingSetId === id) folder.trainingSetId = "";
    }
  }

  function deleteTrainingSetAndSelectNext({ sets, folders, id }) {
    const deleted = trainingSetById(sets, id);
    const nextSets = removeTrainingSet(sets, id);
    clearFolderTrainingSet(folders, id);
    return {
      deletedName: deleted?.name || "",
      sets: nextSets,
      activeTrainingSetId: nextSets[0]?.id || "",
    };
  }

  function renameTrainingSet({ set, name, now }) {
    const trimmed = String(name || "").trim();
    if (!set || !trimmed) return false;
    set.name = trimmed;
    set.updatedAt = now();
    return true;
  }

  function setFolderTrainingSet({ folder, trainingSetId }) {
    if (!folder) return false;
    folder.trainingSetId = trainingSetId || "";
    return true;
  }

  function updateTrainingExample({ set, exampleId, assistant, nowIso, now }) {
    const example = set?.examples?.find((item) => item.id === exampleId);
    const corrected = String(assistant || "").trim();
    if (!set || !example || !corrected) return false;
    example.assistant = corrected;
    example.updatedAt = nowIso();
    set.updatedAt = now();
    return true;
  }

  function addCorrectionExample({ set, draft, assistant, createId, nowIso, now }) {
    const corrected = String(assistant || "").trim();
    if (!set || !draft || !corrected) return false;
    set.examples.unshift({
      id: createId(),
      user: draft.user,
      assistant: corrected,
      originalAssistant: draft.originalAssistant,
      task: draft.task,
      sourceSessionId: draft.sourceSessionId,
      sourceSessionTitle: draft.sourceSessionTitle,
      createdAt: nowIso(),
    });
    set.updatedAt = now();
    return true;
  }

  function saveCorrectionToSet({
    sets,
    selectedSetId,
    draft,
    assistant,
    defaultName,
    createId,
    nowIso,
    now,
  }) {
    let nextSets = sets;
    let set = trainingSetById(nextSets, selectedSetId || draft?.setId);
    if (!set) {
      const created = createAndSelectTrainingSet({
        sets: nextSets,
        name: defaultName,
        defaultName,
        createId,
        now,
      });
      nextSets = created.sets;
      set = created.set;
    }
    const saved = addCorrectionExample({
      set,
      draft,
      assistant,
      createId,
      nowIso,
      now,
    });
    if (!saved) return null;
    return {
      set,
      sets: nextSets,
      activeTrainingSetId: set.id,
    };
  }

  function applyTrainingSetSelection(state, activeTrainingSetId) {
    state.activeTrainingSetId = activeTrainingSetId || "";
    return state.activeTrainingSetId;
  }

  function applyCreatedTrainingSet(state, result) {
    state.trainingSets = result.sets;
    state.activeTrainingSetId = result.activeTrainingSetId;
    return result.set || trainingSetById(result.sets, result.activeTrainingSetId);
  }

  function applyDeletedTrainingSet(state, result) {
    state.trainingSets = result.sets;
    state.activeTrainingSetId = result.activeTrainingSetId;
    return result.deletedName || "";
  }

  function applyCorrectionSaveResult(state, result) {
    state.trainingSets = result.sets;
    state.activeTrainingSetId = result.activeTrainingSetId;
    return result.set;
  }

  function correctionDraftFromMessage({ session, messageIndex, cleanContent }) {
    if (!session) return null;
    const assistant = session.messages[messageIndex];
    let user = null;
    for (let index = messageIndex - 1; index >= 0; index -= 1) {
      if (session.messages[index]?.role === "user") {
        user = session.messages[index];
        break;
      }
    }
    if (!user || !assistant || assistant.role !== "assistant") return null;
    return {
      assistantContent: assistant.content || "",
      draft: {
        user: cleanContent(user),
        originalAssistant: assistant.content || "",
        task: assistant.runMeta?.task || "chat",
        sourceSessionId: session.id,
        sourceSessionTitle: session.title,
      },
    };
  }

  function openCorrectionDialog({ els, sets, set, draft, assistantContent, t }) {
    if (!set || !draft) return;
    renderTrainingSetOptions({
      select: els.correctionTrainingSet,
      sets,
      value: set.id,
      includeNone: false,
      t,
    });
    els.correctionText.value = assistantContent || "";
    els.correctionModal.hidden = false;
    requestAnimationFrame(() => {
      els.correctionText.focus();
      els.correctionText.setSelectionRange(0, els.correctionText.value.length);
    });
  }

  function closeCorrectionDialog({ els }) {
    if (els.correctionText) els.correctionText.value = "";
    if (els.correctionTrainingSet) els.correctionTrainingSet.innerHTML = "";
    if (els.correctionModal) els.correctionModal.hidden = true;
  }

  function cleanTrainingContent(message) {
    const content = String(message?.content || "").trim();
    if (!content || message?.streaming) return "";
    if (Array.isArray(message?.images) && message.images.length > 0) return "";
    if (Array.isArray(message?.imagePreviews) && message.imagePreviews.length > 0) return "";
    return content;
  }

  function shouldSkipTrainingAssistant(content) {
    return /^(エラー|生成エラー|保存エラー|Error|Request failed|timed out)/i.test(String(content || "").trim());
  }

  function sessionsForTrainingScope({ scope, sessions, activeFolderId, activeSessionId }) {
    if (scope === "all") return Array.isArray(sessions) ? sessions : [];
    if (scope === "folder") {
      return (sessions || []).filter((session) => session.folderId === activeFolderId);
    }
    const session = (sessions || []).find((item) => item.id === activeSessionId);
    return session ? [session] : [];
  }

  function buildTrainingExamplesFromSessions({
    sessions,
    scope,
    systemPrompt,
    language,
    folderNameForSession,
    nowIso,
  }) {
    const examples = [];
    for (const session of sessions) {
      for (let index = 0; index < session.messages.length - 1; index += 1) {
        const user = session.messages[index];
        const assistant = session.messages[index + 1];
        if (user?.role !== "user" || assistant?.role !== "assistant") continue;
        const userContent = cleanTrainingContent(user);
        const assistantContent = cleanTrainingContent(assistant);
        if (!userContent || !assistantContent || shouldSkipTrainingAssistant(assistantContent)) continue;
        examples.push({
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: userContent },
            { role: "assistant", content: assistantContent },
          ],
          metadata: {
            app: "Gemma4_12B",
            format: "messages-jsonl-v1",
            scope,
            language,
            folder: folderNameForSession(session),
            session: session.title,
            task: assistant.runMeta?.task || "chat",
            model: assistant.runMeta?.model || "",
            mode: assistant.runMeta?.responseMode || "",
            durationSeconds: assistant.durationSeconds || null,
            exportedAt: nowIso(),
          },
        });
      }
    }
    return examples;
  }

  function buildTrainingExamplesFromSet({ set, systemPrompt, nowIso }) {
    if (!set) return [];
    return (set.examples || [])
      .filter((example) => example?.user && example?.assistant)
      .map((example) => ({
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: example.user },
          { role: "assistant", content: example.assistant },
        ],
        metadata: {
          app: "Gemma4_12B",
          format: "messages-jsonl-v1",
          scope: "set",
          trainingSet: set.name,
          task: example.task || "chat",
          sourceSession: example.sourceSessionTitle || "",
          createdAt: example.createdAt || null,
          exportedAt: nowIso(),
        },
      }));
  }

  function trainingExportFilenameScope({ scope, activeSet, activeFolder, activeSession, slugForFilename }) {
    if (scope === "set") return slugForFilename(activeSet?.name, "set");
    if (scope === "folder") return slugForFilename(activeFolder?.name, "folder");
    if (scope === "active") return slugForFilename(activeSession?.title, "chat");
    return slugForFilename(scope, "all");
  }

  function createTrainingExport({
    scope,
    examples,
    activeSet,
    activeFolder,
    activeSession,
    slugForFilename,
    timestampForFilename,
  }) {
    if (!Array.isArray(examples) || examples.length === 0) return null;
    const filenameScope = trainingExportFilenameScope({
      scope,
      activeSet,
      activeFolder,
      activeSession,
      slugForFilename,
    });
    return {
      count: examples.length,
      filename: `gemma4-training-${filenameScope}-${timestampForFilename()}.jsonl`,
      jsonl: `${examples.map((example) => JSON.stringify(example)).join("\n")}\n`,
    };
  }

  function buildTrainingContextPrompt({ set, t, textSnippet, maxExamples = 4 }) {
    const examples = (set?.examples || []).slice(0, maxExamples);
    if (!set || examples.length === 0) return "";
    const lines = [
      "",
      "",
      `学習セット「${set.name}」: このフォルダーの確認済みメモです。下の修正例に含まれる事実を優先してください。`,
      `修正例にない固有名詞、人物名、代表者、日付、数値、サービス内容は補完しないでください。不明な場合は「${t("training.uncertainAnswer")}」と答えてください。`,
      "これは即時の参照ヒントです。十分な例が集まったら学習用ファイルとして書き出し、ファインチューニングに使えます。",
    ];
    examples.forEach((example, index) => {
      lines.push(
        `例${index + 1} ユーザー: ${textSnippet(example.user)}`,
        `例${index + 1} 正しい回答: ${textSnippet(example.assistant)}`,
      );
    });
    return lines.join("\n");
  }

  function renderTrainingSetOptions({ select, sets, value, includeNone = false, t }) {
    if (!select) return;
    select.innerHTML = "";
    if (includeNone) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = t("settings.trainingSetNone");
      select.append(option);
    }
    for (const set of sets) {
      const option = document.createElement("option");
      option.value = set.id;
      option.textContent = `${set.name} (${t("settings.trainingSetSummary", { count: set.examples?.length || 0 })})`;
      select.append(option);
    }
    select.value = value || "";
  }

  function updateTrainingExportScopeLabel({ select, set, t }) {
    if (!select) return;
    const option = [...select.options].find((item) => item.value === "set");
    if (!option) return;
    option.textContent = set
      ? t("settings.trainingScopeSetNamed", { name: set.name })
      : t("settings.trainingScopeSet");
  }

  function renderTrainingExamples({ list, details, set, t }) {
    if (!list) return;
    list.innerHTML = "";
    const examples = set?.examples || [];
    const summary = details?.querySelector("summary");
    if (summary) {
      summary.textContent = t("settings.trainingExamplesWithCount", { count: examples.length });
    }
    if (!set || examples.length === 0) {
      const empty = document.createElement("p");
      empty.className = "training-empty";
      empty.textContent = t("settings.trainingExamplesEmpty");
      list.append(empty);
      return;
    }
    for (const [index, example] of examples.entries()) {
      const item = document.createElement("details");
      item.className = "training-example";
      item.open = index < 3;
      const title = document.createElement("summary");
      const titleText = document.createElement("strong");
      titleText.textContent = `${index + 1}. ${example.sourceSessionTitle || set.name}`;
      const titleMeta = document.createElement("small");
      titleMeta.textContent = [
        example.task ? `${t("settings.trainingExampleTask")}: ${example.task}` : "",
        example.createdAt ? `${t("settings.trainingExampleSavedAt")}: ${example.createdAt}` : "",
      ].filter(Boolean).join(" / ");
      title.append(titleText, titleMeta);
      const userLabel = document.createElement("span");
      userLabel.textContent = t("settings.trainingExampleUser");
      const user = document.createElement("pre");
      user.textContent = example.user || "";
      const originalLabel = document.createElement("span");
      originalLabel.textContent = t("settings.trainingExampleOriginal");
      const original = document.createElement("pre");
      original.textContent = example.originalAssistant || t("settings.trainingExampleNoOriginal");
      const assistantLabel = document.createElement("span");
      assistantLabel.textContent = t("settings.trainingExampleAssistant");
      const assistant = document.createElement("textarea");
      assistant.rows = 4;
      assistant.dataset.exampleId = example.id;
      assistant.textContent = example.assistant || "";
      assistant.value = example.assistant || "";
      const info = document.createElement("div");
      info.className = "training-example-info";
      const infoRows = [
        [t("settings.trainingExampleSource"), example.sourceSessionTitle || ""],
        [t("settings.trainingExampleTask"), example.task || ""],
        [t("settings.trainingExampleSavedAt"), example.createdAt || ""],
        [t("settings.trainingExampleNote"), example.note || ""],
      ].filter(([, value]) => value);
      for (const [label, value] of infoRows) {
        const row = document.createElement("small");
        row.textContent = `${label}: ${value}`;
        info.append(row);
      }
      const save = document.createElement("button");
      save.className = "ghost-button training-example-save";
      save.type = "button";
      save.dataset.exampleId = example.id;
      save.textContent = t("settings.trainingExampleSave");
      item.append(title, userLabel, user, assistantLabel, assistant, originalLabel, original, info, save);
      list.append(item);
    }
  }

  function renderTrainingControls({
    els,
    sets,
    activeSet,
    activeTrainingSetId,
    folderTrainingSetId,
    folders,
    t,
  }) {
    renderTrainingSetOptions({
      select: els.trainingSetSelect,
      sets,
      value: activeTrainingSetId,
      includeNone: false,
      t,
    });
    renderTrainingSetOptions({
      select: els.workspaceTrainingSet,
      sets,
      value: folderTrainingSetId || "",
      includeNone: true,
      t,
    });
    if (els.trainingSetRename) els.trainingSetRename.disabled = !activeSet;
    if (els.trainingSetDelete) els.trainingSetDelete.disabled = !activeSet;
    if (els.trainingSetSummary) {
      const appliedFolders = folders
        .filter((folder) => folder.trainingSetId === activeSet?.id)
        .map((folder) => folder.name)
        .filter(Boolean)
        .join(" / ");
      els.trainingSetSummary.textContent = activeSet
        ? `${activeSet.name}: ${t("settings.trainingSetSummary", { count: activeSet.examples?.length || 0 })}${appliedFolders ? ` / ${appliedFolders}` : ""}`
        : t("training.noSet");
    }
    updateTrainingExportScopeLabel({
      select: els.trainingExportScope,
      set: activeSet,
      t,
    });
    renderTrainingExamples({
      list: els.trainingExampleList,
      details: els.trainingExamples,
      set: activeSet,
      t,
    });
  }

  window.GEMMA_TRAINING = {
    activeTrainingSet,
    buildTrainingExamplesFromSessions,
    buildTrainingExamplesFromSet,
    buildTrainingContextPrompt,
    cleanTrainingContent,
    closeCorrectionDialog,
    correctionDraftFromMessage,
    createTrainingExport,
    createAndSelectTrainingSet,
    deleteTrainingSetAndSelectNext,
    loadTrainingSets,
    normalizeTrainingSets,
    renameTrainingSet,
    renderTrainingExamples,
    renderTrainingControls,
    renderTrainingSetOptions,
    openCorrectionDialog,
    applyCorrectionSaveResult,
    applyCreatedTrainingSet,
    applyDeletedTrainingSet,
    applyTrainingSetSelection,
    saveCorrectionToSet,
    saveTrainingSets,
    setFolderTrainingSet,
    shouldSkipTrainingAssistant,
    sessionsForTrainingScope,
    trainingSetById,
    trainingExportFilenameScope,
    updateTrainingExample,
    updateTrainingExportScopeLabel,
  };
})();
