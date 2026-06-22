(function () {
  const PROMPT_MIN_HEIGHT = 34;
  const PROMPT_MAX_HEIGHT = 160;
  const PENDING_NAME_LIMIT = 10;

  function truncateMiddle(value, limit = PENDING_NAME_LIMIT) {
    const text = String(value || "").trim();
    const chars = Array.from(text);
    if (chars.length <= limit) return text;
    if (limit <= 4) return `${chars.slice(0, limit).join("")}…`;
    const extIndex = text.lastIndexOf(".");
    const extension = extIndex > 0 ? text.slice(extIndex) : "";
    const extChars = Array.from(extension);
    if (extension && extChars.length < limit - 2) {
      const headCount = Math.max(2, limit - extChars.length - 1);
      return `${Array.from(text.slice(0, extIndex)).slice(0, headCount).join("")}…${extension}`;
    }
    const headCount = Math.ceil((limit - 1) / 2);
    const tailCount = Math.floor((limit - 1) / 2);
    return `${chars.slice(0, headCount).join("")}…${chars.slice(chars.length - tailCount).join("")}`;
  }

  function renderPendingImages({ state, els, t, onRemoveImage, onRemoveFile }) {
    els.imageStrip.hidden = state.pendingImages.length === 0 && state.pendingFiles.length === 0;
    els.imageStrip.innerHTML = "";
    for (const [index, image] of state.pendingImages.entries()) {
      const item = document.createElement("div");
      item.className = "pending-image";
      const preview = document.createElement("img");
      preview.src = image.preview;
      preview.alt = image.name || t("composer.attachedImage");
      item.title = image.name || t("composer.attachedImage");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.title = t("composer.removeAttachment");
      remove.addEventListener("click", () => onRemoveImage(index));
      item.append(preview, remove);
      els.imageStrip.append(item);
    }
    for (const [index, file] of state.pendingFiles.entries()) {
      const item = document.createElement("div");
      item.className = "pending-file";
      const badge = document.createElement("span");
      badge.className = "pending-file-badge";
      badge.textContent = file.kind || "FILE";
      const body = document.createElement("span");
      body.className = "pending-file-body";
      const name = document.createElement("strong");
      const fullName = file.name || t("composer.attachedFile");
      name.textContent = truncateMiddle(fullName);
      name.title = fullName;
      item.title = fullName;
      const size = document.createElement("small");
      size.textContent = file.sizeLabel || "";
      body.append(name, size);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.title = t("composer.removeAttachment");
      remove.addEventListener("click", () => onRemoveFile(index));
      item.append(badge, body, remove);
      els.imageStrip.append(item);
    }
  }

  function resizePrompt({ els }) {
    els.prompt.style.height = "0px";
    const nextHeight = els.prompt.value
      ? Math.min(PROMPT_MAX_HEIGHT, Math.max(PROMPT_MIN_HEIGHT, els.prompt.scrollHeight))
      : PROMPT_MIN_HEIGHT;
    els.prompt.style.height = `${nextHeight}px`;
    els.prompt.style.overflowY = nextHeight >= PROMPT_MAX_HEIGHT ? "auto" : "hidden";
    els.composer.classList.toggle("multiline", nextHeight > PROMPT_MIN_HEIGHT + 4);
  }

  function bindComposerEvents({ els, getEnterToSend, onResize, onAddImages, onPromptPaste, onDocumentPaste }) {
    els.prompt.addEventListener("input", onResize);
    els.prompt.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.isComposing) return;
      const shortcutSend = event.metaKey || event.ctrlKey;
      const plainEnterSend = getEnterToSend() && !event.shiftKey && !event.altKey;
      if (!shortcutSend && !plainEnterSend) return;
      event.preventDefault();
      els.composer.requestSubmit();
    });

    els.attachImage.addEventListener("click", () => {
      els.imageInput.click();
    });

    els.imageInput.addEventListener("change", async () => {
      await onAddImages(els.imageInput.files || []);
      els.imageInput.value = "";
    });

    els.prompt.addEventListener("paste", onPromptPaste);
    document.addEventListener("paste", onDocumentPaste);
  }

  window.GEMMA_COMPOSER = {
    bindComposerEvents,
    renderPendingImages,
    resizePrompt,
  };
})();
