window.TOMOS_CHARACTER_CORE = (() => {
  const FIRST_PERSON_CANDIDATES = ["俺", "僕", "私", "わたし", "あたし", "オラ", "われ", "吾輩"];

  const characterProfileJsonSchema = {
    title: "CharacterProfile",
    type: "object",
    required: ["id", "displayName", "voice"],
    properties: {
      id: { type: "string", minLength: 1 },
      displayName: { type: "string", minLength: 1 },
      preferredCallName: { type: "string" },
      role: { type: "string" },
      personality: { type: "array", items: { type: "string" } },
      voice: {
        type: "object",
        required: ["firstPerson", "speechStyle"],
        properties: {
          firstPerson: { type: "string", minLength: 1 },
          secondPerson: { type: "string" },
          speechStyle: { type: "string", minLength: 1 },
          toneRules: { type: "array", items: { type: "string" } },
          catchphrases: { type: "array", items: { type: "string" } },
          maxCatchphraseUses: { type: "number" },
          ngActingRules: { type: "array", items: { type: "string" } },
        },
      },
      relationship: { type: "object" },
      idealReplies: { type: "array", items: { type: "string" } },
      avoidReplies: { type: "array", items: { type: "string" } },
      reactionRules: { type: "array", items: { type: "object" } },
    },
  };

  const runtimePromptInputJsonSchema = {
    title: "RuntimePromptInput",
    type: "object",
    required: ["character"],
    properties: {
      character: characterProfileJsonSchema,
      context: {
        type: "object",
        properties: {
          project: { type: "string" },
          situation: { type: "string" },
          emotion: { type: "string" },
          relationshipStage: { type: "string" },
          userMessage: { type: "string" },
          recentLines: { type: "array", items: { type: "string" } },
          safetyNotes: { type: "array", items: { type: "string" } },
        },
      },
    },
  };

  function textValue(value, fallback = "") {
    return String(value || fallback).trim();
  }

  function listValue(value) {
    return Array.isArray(value) ? value.map((item) => textValue(item)).filter(Boolean) : [];
  }

  function normalizeLine(text = "") {
    return textValue(text).replace(/\s+/g, "").replace(/[「」『』"'.、。！？!?]/g, "").trim();
  }

  function schemaWarnings(character) {
    const warnings = [];
    if (!textValue(character?.id)) warnings.push(warning("NG_ACTING_RULE_HIT", "character schema warning: id is required", "id", "id"));
    if (!textValue(character?.displayName)) warnings.push(warning("NG_ACTING_RULE_HIT", "character schema warning: displayName is required", "displayName", "displayName"));
    if (!textValue(character?.voice?.firstPerson)) warnings.push(warning("NG_ACTING_RULE_HIT", "character schema warning: voice.firstPerson is required", "voice.firstPerson", "voice.firstPerson"));
    if (!textValue(character?.voice?.speechStyle)) warnings.push(warning("NG_ACTING_RULE_HIT", "character schema warning: voice.speechStyle is required", "voice.speechStyle", "voice.speechStyle"));
    return warnings;
  }

  function warning(code, message, evidence = "", path = "") {
    return { code, message, severity: "warning", evidence, path };
  }

  function checkCatchphraseRepetition(text, catchphrases = [], maxUses = 1) {
    const value = textValue(text);
    return listValue(catchphrases).flatMap((phrase) => {
      const count = value.split(phrase).length - 1;
      return count > maxUses ? [{ phrase, count, maxUses }] : [];
    });
  }

  function validateCharacterVoice(character, options = {}) {
    const warnings = schemaWarnings(character);
    if (warnings.length) return warnings;

    const text = textValue(options.generatedText);
    if (!text) return warnings;

    const firstPerson = character.voice.firstPerson;
    const otherFirstPerson = FIRST_PERSON_CANDIDATES.filter((candidate) => candidate !== firstPerson);
    const firstPersonMismatch = otherFirstPerson.find((candidate) => text.includes(candidate));
    if (firstPersonMismatch && !text.includes(firstPerson)) {
      warnings.push(warning("VOICE_FIRST_PERSON_MISMATCH", `設定と異なる一人称「${firstPersonMismatch}」が使われています。`, firstPersonMismatch, "voice.firstPerson"));
    }

    const callName = textValue(character.preferredCallName);
    if (callName && new RegExp(`${callName}(は|です|だ|だよ|って)`).test(text)) {
      warnings.push(warning("VOICE_CALL_NAME_MISMATCH", "呼ばれ方を自称として使っている可能性があります。", callName, "preferredCallName"));
    }

    checkCatchphraseRepetition(text, character.voice.catchphrases || [], character.voice.maxCatchphraseUses ?? 1)
      .forEach((item) => warnings.push(warning("CATCHPHRASE_OVERUSE", `口癖「${item.phrase}」が上限${item.maxUses}回を超えています。`, `${item.phrase}:${item.count}`, "voice.catchphrases")));

    const normalizedText = normalizeLine(text);
    if (listValue(options.recentLines).some((line) => normalizeLine(line) === normalizedText)) {
      warnings.push(warning("REPEATED_LINE", "直近発話と同じ本文を繰り返しています。", text));
    }

    const ngRule = listValue(character.voice.ngActingRules).find((rule) => text.includes(rule));
    if (ngRule) {
      warnings.push(warning("NG_ACTING_RULE_HIT", "NG演技ルールに触れています。", ngRule, "voice.ngActingRules"));
    }

    const leakage = listValue(options.otherCharacterVoiceHints).find((hint) => text.includes(hint));
    if (leakage) {
      warnings.push(warning("CHARACTER_VOICE_LEAKAGE", "他キャラの口調が混ざっている可能性があります。", leakage));
    }

    return warnings;
  }

  function matchScore(value, expected) {
    if (!expected || expected === "any") return 1;
    return value === expected ? 3 : -100;
  }

  function resolveReactionRule(character, context = {}) {
    const rules = Array.isArray(character?.reactionRules) ? character.reactionRules : [];
    const scored = rules
      .map((rule) => ({
        rule,
        score:
          matchScore(context.situation, rule.situation)
          + matchScore(context.emotion, rule.emotion)
          + matchScore(context.relationshipStage, rule.relationshipStage)
          + Number(rule.priority || 0),
      }))
      .filter((item) => item.score > -50)
      .sort((a, b) => b.score - a.score || textValue(a.rule.id).localeCompare(textValue(b.rule.id)));

    return scored[0]?.rule || {
      id: "default_reaction",
      situation: "any",
      emotion: "any",
      relationshipStage: "any",
      priority: 0,
      instruction: "相手の発話を一度受け止め、キャラクターらしい短い反応を返す。",
    };
  }

  function joinList(items, fallback = "なし") {
    const values = listValue(items);
    return values.length ? values.join(" / ") : fallback;
  }

  function section(key, title, content) {
    return { key, title, content };
  }

  function formatTuningItems(label, items) {
    const values = listValue(items);
    return values.length ? `${label}:\n${values.map((item) => `- ${item}`).join("\n")}` : `${label}: なし`;
  }

  function renderSection(item) {
    return `## ${item.title}\n${item.content}`;
  }

  function buildRuntimePrompt(input) {
    const character = input?.character || {};
    const context = input?.context || {};
    const warnings = validateCharacterVoice(character);
    const reaction = resolveReactionRule(character, context);

    const sections = [
      section("identity", "Identity", [
        `名前: ${textValue(character.displayName, "未設定")}`,
        `呼ばれ方: ${textValue(character.preferredCallName, character.displayName || "未設定")}`,
        `役割: ${textValue(character.role, "未設定")}`,
      ].join("\n")),
      section("voice", "Voice", [
        `一人称: ${textValue(character.voice?.firstPerson, "未設定")}`,
        `二人称: ${textValue(character.voice?.secondPerson, "未設定")}`,
        `話し方: ${textValue(character.voice?.speechStyle, "未設定")}`,
        `口癖: ${joinList(character.voice?.catchphrases)}`,
      ].join("\n")),
      section("relationship", "Relationship", [
        `関係段階: ${textValue(context.relationshipStage, character.relationship?.stage || "未設定")}`,
        `距離感: ${textValue(character.relationship?.summary, "未設定")}`,
      ].join("\n")),
      section("reaction", "Reaction Rule", reaction.instruction),
      section("examples", "Examples", [
        formatTuningItems("理想返答", character.idealReplies),
        formatTuningItems("避けたい返答", character.avoidReplies),
      ].join("\n")),
      section("context", "Context", [
        `状況: ${textValue(context.situation, "未設定")}`,
        `感情: ${textValue(context.emotion, "未設定")}`,
        `ユーザー発話: ${textValue(context.userMessage, "なし")}`,
        `直近会話: ${listValue(context.recentLines).length ? listValue(context.recentLines).join(" / ") : "なし"}`,
      ].join("\n")),
      section("output_rules", "Output Rules", [
        "- キャラクター設定にない一人称・二人称を使わない。",
        "- 口癖は自然な場面で短く使い、連続させない。",
        "- NG演技ルールに触れる振る舞いを避ける。",
      ].join("\n")),
    ];

    return {
      text: ["# Character Runtime Prompt", "", sections.map(renderSection).join("\n\n")].join("\n"),
      sections,
      warnings,
    };
  }

  return {
    CharacterProfileSchema: characterProfileJsonSchema,
    RuntimePromptInputSchema: runtimePromptInputJsonSchema,
    buildRuntimePrompt,
    characterProfileJsonSchema,
    resolveReactionRule,
    runtimePromptInputJsonSchema,
    validateCharacterVoice,
  };
})();
