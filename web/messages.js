(() => {
function renderGemmaMessages(deps) {
  const {
    activeSession,
    addCorrectionToTrainingSet,
    closeMemoryCandidate,
    editMemoryCandidate,
    els,
    escapeHtml,
    formatDuration,
    modelForTask,
    openWorkspaceSource,
    revealWorkspaceSource,
    saveMemoryCandidate,
    saveWorkspaceTranscript,
    state,
    t,
  } = deps;
  const character = state.character || {};
  const characterName = character.name || "Gemma";
  const session = activeSession();
  els.messages.innerHTML = "";
  els.chatTitle.textContent = session?.title || t("chat.new");
  els.chatMeta.textContent = `${t("task.chat")}: ${modelForTask("chat")} / ${t("task.coding")}: ${modelForTask("coding")}`;

  if (!session || session.messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <h2>TOMOS AI</h2>
      <div>${escapeHtml(t("chat.emptySubtitle"))}</div>
    `;
    els.messages.append(empty);
    return;
  }

  for (const [messageIndex, message] of session.messages.entries()) {
    const wrapper = document.createElement("article");
    wrapper.className = `message ${message.role}${message.streaming ? " streaming" : ""}`;
    const role = document.createElement("div");
    role.className = "message-role";
    if (message.role === "user") {
      role.textContent = t("chat.you");
    } else {
      role.append(createCharacterAvatar(character));
      const roleLabel = document.createElement("span");
      roleLabel.textContent = message.streaming ? `${characterName} ・ ${t("chat.generating")}` : characterName;
      role.append(roleLabel);
    }
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
    if (message.attachments && message.attachments.length > 0) {
      const attachments = document.createElement("div");
      attachments.className = "message-attachments";
      for (const attachment of message.attachments) {
        const item = document.createElement("div");
        item.className = `message-attachment${attachment.readable === false ? " unreadable" : ""}`;
        const kind = document.createElement("span");
        kind.className = "message-attachment-kind";
        kind.textContent = attachment.kind || "FILE";
        const body = document.createElement("span");
        body.className = "message-attachment-body";
        const label = document.createElement("span");
        label.textContent = attachment.name || t("composer.attachedFile");
        body.append(label);
        if (attachment.readable === false && attachment.error) {
          item.title = attachment.error;
          const note = document.createElement("small");
          note.className = "message-attachment-note";
          note.textContent = attachment.error;
          body.append(note);
        }
        item.append(kind, body);
        attachments.append(item);
      }
      wrapper.append(attachments);
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
      const workspaceSources = message.sources.filter((source) => source.type === "workspace");
      const externalSources = message.sources.filter((source) => source.type !== "workspace");
      if (workspaceSources.length > 0) {
        const workspaceGroup = document.createElement("div");
        workspaceGroup.className = "source-group";
        const title = document.createElement("div");
        title.className = "source-group-title";
        title.textContent = t("chat.workspaceSources");
        const sources = document.createElement("div");
        sources.className = "sources";
        for (const source of workspaceSources) {
          const sourceCard = document.createElement("span");
          sourceCard.className = "workspace-source-card";
          const chip = document.createElement("button");
          chip.type = "button";
          chip.className = "workspace-source";
          chip.title = source.snippet || "";
          chip.setAttribute("aria-label", t("workspace.openSource", { path: source.title || source.path || "" }));
          chip.addEventListener("click", () => openWorkspaceSource?.(source));
          const marker = document.createElement("span");
          marker.className = "workspace-source-marker";
          marker.textContent = source.sourceType === "codegraph" ? "⌘" : "⌕";
          marker.setAttribute("aria-hidden", "true");
          const body = document.createElement("span");
          body.className = "workspace-source-body";
          const labelRow = document.createElement("span");
          labelRow.className = "workspace-source-label-row";
          const label = document.createElement("span");
          label.className = "source-label";
          label.textContent = source.path || source.title || t("workspace.fastSearch");
          labelRow.append(label);
          if (source.line) {
            const line = document.createElement("span");
            line.className = "workspace-source-line";
            line.textContent = `L${source.line}`;
            labelRow.append(line);
          }
          body.append(labelRow);
          if (source.snippet) {
            const snippet = document.createElement("span");
            snippet.className = "workspace-source-snippet";
            snippet.textContent = source.snippet;
            body.append(snippet);
          }
          chip.append(marker, body);
          sourceCard.append(chip);
          if (source.path && source.sourceType !== "codegraph") {
            const reveal = document.createElement("button");
            reveal.type = "button";
            reveal.className = "workspace-source-reveal";
            reveal.textContent = "↗";
            reveal.title = t("workspace.revealSource", { path: source.path || source.title || "" });
            reveal.setAttribute("aria-label", t("workspace.revealSource", { path: source.path || source.title || "" }));
            reveal.addEventListener("click", (event) => {
              event.stopPropagation();
              revealWorkspaceSource?.(source);
            });
            sourceCard.append(reveal);
          }
          sources.append(sourceCard);
        }
        workspaceGroup.append(title, sources);
        wrapper.append(workspaceGroup);
      }
      if (externalSources.length > 0) {
        const externalGroup = document.createElement("div");
        externalGroup.className = "source-group";
        const title = document.createElement("div");
        title.className = "source-group-title";
        title.textContent = t("chat.webSources");
        const sources = document.createElement("div");
        sources.className = "sources";
      for (const [index, source] of externalSources.entries()) {
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        const labelText = source.type === "preview"
          ? source.title || t("chat.preview")
          : `[${index + 1}] ${source.title || source.url}`;
        if (source.type === "preview") {
          link.className = "preview-source";
        }
        link.classList.add("external-source");
        link.title = state.language === "en" ? "Open external link" : "外部リンクを開く";
        link.setAttribute("aria-label", `${labelText} ${state.language === "en" ? "external link" : "外部リンク"}`);
        const label = document.createElement("span");
        label.className = "source-label";
        label.textContent = labelText;
        const icon = document.createElement("span");
        icon.className = "external-source-icon";
        icon.textContent = "↗";
        icon.setAttribute("aria-hidden", "true");
        link.append(label, icon);
        sources.append(link);
      }
        externalGroup.append(title, sources);
        wrapper.append(externalGroup);
      }
    }
    if (Array.isArray(message.searchDiagnostics) && message.searchDiagnostics.length > 0) {
      const diagnostics = document.createElement("div");
      diagnostics.className = "search-diagnostics";
      for (const item of message.searchDiagnostics) {
        const row = document.createElement("div");
        row.className = "search-diagnostic";
        row.dataset.status = item.status || "info";
        const label = document.createElement("strong");
        label.textContent = item.label || (state.language === "en" ? "Research status" : "外部調査状態");
        const messageText = document.createElement("span");
        messageText.textContent = item.message || "";
        row.append(label, messageText);
        if (item.howToSucceed) {
          const help = document.createElement("small");
          help.textContent = item.howToSucceed;
          row.append(help);
        }
        if (item.error) {
          const error = document.createElement("small");
          error.textContent = item.error;
          row.append(error);
        }
        diagnostics.append(row);
      }
      wrapper.append(diagnostics);
    }
    if (message.role === "assistant" && typeof message.durationSeconds === "number") {
      const duration = document.createElement("div");
      duration.className = "message-duration";
      const details = [`${t("chat.duration")}: ${formatDuration(message.durationSeconds)}`];
      if (message.runMeta?.modelLabel) details.push(`${t("chat.model")}: ${message.runMeta.modelLabel}`);
      if (message.runMeta?.taskLabel) details.push(`${t("chat.task")}: ${message.runMeta.taskLabel}`);
      if (message.runMeta?.modelReason) details.push(`${t("chat.modelReason")}: ${message.runMeta.modelReason}`);
      if (message.runMeta?.studyPackModeLabel) details.push(`${t("chat.studyPackMode")}: ${message.runMeta.studyPackModeLabel}`);
      if (message.runMeta?.responseModeLabel) details.push(`${t("chat.mode")}: ${message.runMeta.responseModeLabel}`);
      if (message.runMeta?.codeUnderstanding) details.push(t("workspace.codeUnderstanding"));
      duration.textContent = details.join(" / ");
      wrapper.append(duration);
    }
    if (!message.streaming && message.content) {
      const actions = document.createElement("div");
      actions.className = "message-actions";
      actions.append(createCopyMessageButton(message, t));
      if (message.role === "assistant" && message.workspaceTranscript) {
        actions.append(createSaveTranscriptButton(message.workspaceTranscript, saveWorkspaceTranscript, t));
      }
      if (message.role === "assistant") {
        const correct = document.createElement("button");
        correct.type = "button";
        correct.textContent = t("training.correct");
        correct.title = t("training.correctTitle");
        correct.addEventListener("click", () => addCorrectionToTrainingSet(messageIndex));
        actions.append(correct);
      }
      wrapper.append(actions);
    }
    els.messages.append(wrapper);
  }
  if (state.memoryCandidate) {
    els.messages.append(createMemoryCandidateCard({
      candidate: state.memoryCandidate,
      closeMemoryCandidate,
      editMemoryCandidate,
      saveMemoryCandidate,
      t,
    }));
  }
  els.messages.scrollTop = els.messages.scrollHeight;
}

function createMemoryCandidateCard({ candidate, closeMemoryCandidate, editMemoryCandidate, saveMemoryCandidate, t }) {
  const wrapper = document.createElement("article");
  wrapper.className = "message assistant memory-candidate-message";
  const role = document.createElement("div");
  role.className = "message-role";
  role.textContent = t("character.memoryCandidate");
  const card = document.createElement("div");
  card.className = "memory-candidate-card";
  const text = document.createElement("p");
  text.textContent = candidate.text || "";
  const actions = document.createElement("div");
  actions.className = "memory-candidate-actions";
  const discard = document.createElement("button");
  discard.type = "button";
  discard.className = "ghost-button";
  discard.textContent = t("character.memoryDiscard");
  discard.addEventListener("click", closeMemoryCandidate);
  const edit = document.createElement("button");
  edit.type = "button";
  edit.className = "ghost-button";
  edit.textContent = t("character.memorySave");
  edit.addEventListener("click", editMemoryCandidate);
  const save = document.createElement("button");
  save.type = "button";
  save.className = "ghost-button primary-action";
  save.textContent = t("character.memoryQuickSave");
  save.addEventListener("click", () => saveMemoryCandidate(candidate.text || ""));
  actions.append(discard, edit, save);
  card.append(text, actions);
  wrapper.append(role, card);
  return wrapper;
}

function createCharacterAvatar(character = {}) {
  const avatar = document.createElement("span");
  avatar.className = "character-avatar";
  const src = String(character.avatar || "").trim();
  if (src) {
    const image = document.createElement("img");
    image.src = src;
    image.alt = "";
    avatar.append(image);
  } else {
    avatar.textContent = String(character.name || "G").trim().slice(0, 2).toUpperCase();
  }
  return avatar;
}

async function copyTextToClipboard(text) {
  const value = String(text || "");
  if (!value) return false;
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    document.body.append(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    textarea.remove();
    return ok;
  }
}

function createCopyMessageButton(message, t) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "icon-action copy-message";
  button.textContent = "⧉";
  button.title = t("chat.copy");
  button.setAttribute("aria-label", t("chat.copy"));
  button.addEventListener("click", async () => {
    const copied = await copyTextToClipboard(message.content || "");
    if (!copied) return;
    button.textContent = "✓";
    button.title = t("chat.copied");
    window.setTimeout(() => {
      button.textContent = "⧉";
      button.title = t("chat.copy");
    }, 1200);
  });
  return button;
}

function createSaveTranscriptButton(action, saveWorkspaceTranscript, t) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost-button";
  button.textContent = t("workspace.saveTranscript");
  button.title = t("workspace.saveTranscriptTitle", { path: action.savePath || "" });
  button.addEventListener("click", () => saveWorkspaceTranscript?.(action, button));
  return button;
}

window.GEMMA_MESSAGES = {
  renderMessages: renderGemmaMessages,
};
})();
