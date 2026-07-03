window.TOMOS_CHARACTER_CORE_ADAPTER = (() => {
  const DEFAULT_RELATIONSHIP_STAGE = "default";
  const DEFAULT_SITUATION = "chat";
  const DEFAULT_EMOTION = "neutral";

  function textValue(value, fallback = "") {
    return String(value || fallback).trim();
  }

  function limitText(value, maxLength = 4000) {
    const text = textValue(value);
    if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength)}...`;
  }

  function normalizeArray(value) {
    return Array.isArray(value) ? value.filter(Boolean) : [];
  }

  function normalizeCorePromptResult(result) {
    if (!result || typeof result !== "object") {
      return { text: "", sections: [], warnings: [] };
    }
    return {
      text: limitText(result.text),
      sections: normalizeArray(result.sections),
      warnings: normalizeArray(result.warnings),
    };
  }

  function normalizeWarningList(result) {
    if (Array.isArray(result)) return result.filter(Boolean);
    if (result && Array.isArray(result.warnings)) return result.warnings.filter(Boolean);
    return [];
  }

  function mapCharacterProfile(character = {}) {
    return {
      id: textValue(character.id, "default-character"),
      name: textValue(character.name, "Gemma"),
      userName: textValue(character.userName),
      selfName: textValue(character.selfName),
      gender: textValue(character.gender, "unspecified"),
      tonePreset: textValue(character.tonePreset, "friendly"),
      personality: textValue(character.personality),
      systemPromptAddon: textValue(character.systemPromptAddon),
      memoryMode: textValue(character.memoryMode, "suggest"),
    };
  }

  function mapMemoryItems(memorySet = {}) {
    return normalizeArray(memorySet.memories)
      .filter((memory) => textValue(memory?.text))
      .slice(-12)
      .map((memory) => ({
        id: textValue(memory.id),
        text: limitText(memory.text, 1000),
        tags: normalizeArray(memory.tags).map((tag) => textValue(tag)).filter(Boolean),
        pinned: Boolean(memory.pinned),
      }));
  }

  function mapRecentMessages(messages = []) {
    return normalizeArray(messages)
      .slice(-8)
      .map((message) => ({
        role: textValue(message.role),
        content: limitText(message.content || message.text, 1200),
      }))
      .filter((message) => message.role && message.content);
  }

  function buildRuntimePromptInput(options = {}) {
    const conversationState = options.conversationState || {};
    return {
      character: mapCharacterProfile(options.character),
      memory: {
        items: mapMemoryItems(options.memorySet),
      },
      situation: textValue(conversationState.situation, DEFAULT_SITUATION),
      emotion: textValue(conversationState.emotion, DEFAULT_EMOTION),
      relationshipStage: textValue(conversationState.relationshipStage, DEFAULT_RELATIONSHIP_STAGE),
      recentMessages: mapRecentMessages(options.recentMessages),
    };
  }

  function buildRuntimePromptAddition(options = {}) {
    const core = window.TOMOS_CHARACTER_CORE || {};
    if (typeof core.buildRuntimePrompt !== "function") {
      return {
        source: "none",
        text: "",
        sections: [],
        warnings: [],
        reactionRule: null,
        input: buildRuntimePromptInput(options),
      };
    }

    const input = buildRuntimePromptInput(options);
    const prompt = normalizeCorePromptResult(core.buildRuntimePrompt(input));
    const voiceWarnings = typeof core.validateCharacterVoice === "function"
      ? normalizeWarningList(core.validateCharacterVoice(input.character))
      : [];
    const reactionRule = typeof core.resolveReactionRule === "function"
      ? core.resolveReactionRule({
        situation: input.situation,
        emotion: input.emotion,
        relationshipStage: input.relationshipStage,
      })
      : null;

    return {
      source: "character-core",
      text: prompt.text,
      sections: prompt.sections,
      warnings: [...prompt.warnings, ...voiceWarnings],
      reactionRule,
      input,
    };
  }

  function formatPromptAddition(addition) {
    const text = limitText(addition?.text);
    if (!text) return "";
    return `\n\ncharacter-core追加指示:\n${text}`;
  }

  return {
    buildRuntimePromptAddition,
    buildRuntimePromptInput,
    formatPromptAddition,
    mapCharacterProfile,
  };
})();
