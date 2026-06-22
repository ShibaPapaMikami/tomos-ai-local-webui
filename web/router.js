(() => {
  const INTENTS = {
    chat: "chat",
    image: "image",
    local: "local",
    saveCommand: "save-command",
    simpleSave: "simple-save",
    translation: "translation",
    weather: "weather",
    workspaceBuild: "workspace-build",
  };

  function classifySubmitIntent({
    text,
    hasImages,
    isImageGenerationRequest,
    isLocalUtilityRequest,
    isTranslationRequest,
    isWeatherRequest,
    isSimpleTextSaveRequest,
    isSaveCommandRequest,
    isWorkspaceBuildRequest,
  }) {
    if (!text) return INTENTS.chat;
    if (hasImages) return INTENTS.chat;
    if (isLocalUtilityRequest(text)) return INTENTS.local;
    if (isWeatherRequest(text)) return INTENTS.weather;
    if (isTranslationRequest(text)) return INTENTS.translation;
    if (isImageGenerationRequest(text)) return INTENTS.image;
    if (isSimpleTextSaveRequest(text)) return INTENTS.simpleSave;
    if (isSaveCommandRequest(text)) return INTENTS.saveCommand;
    if (isWorkspaceBuildRequest(text)) return INTENTS.workspaceBuild;
    return INTENTS.chat;
  }

  window.GEMMA_ROUTER = {
    classifySubmitIntent,
    INTENTS,
  };
})();
