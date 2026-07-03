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
      displayName: textValue(character.name, "Gemma"),
      preferredCallName: textValue(character.userName) || undefined,
      role: "local-chat-character",
      personality: [textValue(character.personality)].filter(Boolean),
      voice: {
        firstPerson: textValue(character.selfName, textValue(character.name, "Gemma")),
        secondPerson: textValue(character.userName) || undefined,
        speechStyle: textValue(character.tonePreset, "friendly"),
        toneRules: [textValue(character.systemPromptAddon)].filter(Boolean),
        catchphrases: [],
        maxCatchphraseUses: 1,
        ngActingRules: [
          "設定にない一人称を使う",
          "直近会話と同じ文を繰り返す",
          "人間であるように装う",
        ],
      },
      relationship: {
        stage: DEFAULT_RELATIONSHIP_STAGE,
        summary: "TOMOS AI のローカルチャットでユーザーを支援する関係。",
      },
      idealReplies: [
        "短く自然に受け止めてから、必要な内容だけ答える。",
      ],
      avoidReplies: [
        "分からない情報を作る。",
        "キャラクター設定にない口調へ寄せる。",
      ],
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
    const recentMessages = mapRecentMessages(options.recentMessages);
    return {
      character: mapCharacterProfile(options.character),
      context: {
        project: "TOMOS AI",
        situation: textValue(conversationState.situation, DEFAULT_SITUATION),
        emotion: textValue(conversationState.emotion, DEFAULT_EMOTION),
        relationshipStage: textValue(conversationState.relationshipStage, DEFAULT_RELATIONSHIP_STAGE),
        userMessage: recentMessages[recentMessages.length - 1]?.content || "",
        recentLines: recentMessages.map((message) => `${message.role}: ${message.content}`),
        safetyNotes: mapMemoryItems(options.memorySet).map((memory) => memory.text),
      },
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
    const recentLines = input.context?.recentLines || [];
    const voiceWarnings = typeof core.validateCharacterVoice === "function"
      ? normalizeWarningList(core.validateCharacterVoice(input.character, { recentLines }))
      : [];
    const reactionRule = typeof core.resolveReactionRule === "function"
      ? core.resolveReactionRule(input.character, input.context)
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
