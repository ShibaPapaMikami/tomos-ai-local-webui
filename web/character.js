window.GEMMA_CHARACTER = (() => {
  const CHARACTER_KEY = "gemma4.character";
  const MEMORY_SETS_KEY = "gemma4.characterMemorySets";

  const DEFAULT_CHARACTER = {
    id: "default-character",
    name: "Gemma",
    userName: "",
    selfName: "",
    gender: "unspecified",
    avatar: "",
    personality: "やさしく、短く、自然に答える",
    tonePreset: "friendly",
    systemPromptAddon: "",
    memorySetId: "character-memory-default",
    memoryMode: "suggest",
    characterCoreEnabled: true,
  };

  const DEFAULT_MEMORY_SET = {
    id: "character-memory-default",
    characterId: "default-character",
    name: "Gemmaの記憶",
    memories: [],
  };

  function safeJson(key, fallback) {
    try {
      return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    } catch {
      return fallback;
    }
  }

  function normalizeCharacter(character = {}) {
    return {
      ...DEFAULT_CHARACTER,
      ...character,
      id: character.id || DEFAULT_CHARACTER.id,
      name: String(character.name || DEFAULT_CHARACTER.name).trim() || DEFAULT_CHARACTER.name,
      userName: String(character.userName || "").trim(),
      selfName: String(character.selfName || "").trim(),
      gender: ["unspecified", "female", "male", "other"].includes(character.gender)
        ? character.gender
        : DEFAULT_CHARACTER.gender,
      avatar: String(character.avatar || "").trim(),
      personality: String(character.personality || DEFAULT_CHARACTER.personality).trim(),
      tonePreset: ["friendly", "calm", "teacher", "concise"].includes(character.tonePreset)
        ? character.tonePreset
        : DEFAULT_CHARACTER.tonePreset,
      systemPromptAddon: String(character.systemPromptAddon || "").trim(),
      memoryMode: ["off", "suggest", "auto"].includes(character.memoryMode) ? character.memoryMode : "suggest",
      memorySetId: character.memorySetId || DEFAULT_CHARACTER.memorySetId,
      characterCoreEnabled: character.characterCoreEnabled !== false,
    };
  }

  function loadCharacter() {
    return normalizeCharacter(safeJson(CHARACTER_KEY, DEFAULT_CHARACTER));
  }

  function saveCharacter(character) {
    const normalized = normalizeCharacter(character);
    localStorage.setItem(CHARACTER_KEY, JSON.stringify(normalized));
    return normalized;
  }

  function normalizeMemoryText(text) {
    return String(text || "")
      .trim()
      .replace(/^ユーザーは(.{1,24})は(.{1,36})が(好き|苦手)$/u, "$1は$2が$3");
  }

  function normalizeMemorySet(set = {}, character = DEFAULT_CHARACTER) {
    const memories = Array.isArray(set.memories) ? set.memories : [];
    return {
      ...DEFAULT_MEMORY_SET,
      ...set,
      id: set.id || character.memorySetId || DEFAULT_MEMORY_SET.id,
      characterId: set.characterId || character.id || DEFAULT_CHARACTER.id,
      name: String(set.name || `${character.name || "Gemma"}の記憶`).trim(),
      memories: memories.map((memory) => ({
        id: memory.id || crypto.randomUUID(),
        text: normalizeMemoryText(memory.text),
        sourceSessionId: memory.sourceSessionId || "",
        sourceFolderId: memory.sourceFolderId || "",
        createdAt: memory.createdAt || new Date().toISOString(),
        updatedAt: memory.updatedAt || memory.createdAt || new Date().toISOString(),
        tags: Array.isArray(memory.tags) ? memory.tags : [],
        pinned: Boolean(memory.pinned),
      })).filter((memory) => memory.text),
    };
  }

  function loadMemorySets(character = loadCharacter()) {
    const sets = safeJson(MEMORY_SETS_KEY, [DEFAULT_MEMORY_SET]);
    const normalized = Array.isArray(sets) ? sets.map((set) => normalizeMemorySet(set, character)) : [];
    if (!normalized.some((set) => set.id === character.memorySetId)) {
      normalized.push(normalizeMemorySet({ id: character.memorySetId, name: `${character.name}の記憶` }, character));
    }
    return normalized;
  }

  function saveMemorySets(sets) {
    const normalized = Array.isArray(sets) ? sets.map((set) => normalizeMemorySet(set)) : [DEFAULT_MEMORY_SET];
    localStorage.setItem(MEMORY_SETS_KEY, JSON.stringify(normalized));
    return normalized;
  }

  function activeMemorySet(memorySets, character) {
    return memorySets.find((set) => set.id === character.memorySetId) || memorySets[0] || normalizeMemorySet({}, character);
  }

  function toneInstruction(tonePreset) {
    const map = {
      friendly: "親しみやすく、自然な口調で答えてください。",
      calm: "落ち着いた口調で、安心できるように答えてください。",
      teacher: "先生のように、短い例を交えて分かりやすく答えてください。",
      concise: "短く、要点だけを自然に答えてください。",
    };
    return map[tonePreset] || map.friendly;
  }

  function genderInstruction(gender) {
    const map = {
      female: "キャラクターの性別設定は女性です。表現の参考にしてください。",
      male: "キャラクターの性別設定は男性です。表現の参考にしてください。",
      other: "キャラクターの性別設定はその他です。表現の参考にしてください。",
    };
    return map[gender] || "";
  }

  function buildCharacterSystemPrompt(character, options = {}) {
    const normalized = normalizeCharacter(character);
    const lines = [
      "",
      "キャラクター設定:",
      `あなたの表示名は「${normalized.name}」です。`,
      normalized.userName ? `ユーザーの呼び方は「${normalized.userName}」です。自然な範囲でそう呼んでください。` : "",
      normalized.selfName ? `自分自身を指すときは「${normalized.selfName}」を自然な範囲で使ってください。` : "",
      genderInstruction(normalized.gender),
      normalized.personality ? `性格・口調: ${normalized.personality}` : "",
      toneInstruction(normalized.tonePreset),
      normalized.systemPromptAddon,
      "ただし、正確性・安全性・ユーザーの依頼達成を最優先してください。",
      "分からないことは作らず、分からないと伝えてください。",
      "あなたはAIであり、人間であるように装わないでください。",
    ].filter(Boolean);
    const basePrompt = `\n\n${lines.join("\n")}`;
    const adapter = normalized.characterCoreEnabled ? window.TOMOS_CHARACTER_CORE_ADAPTER : null;
    if (!adapter || typeof adapter.buildRuntimePromptAddition !== "function") {
      return basePrompt;
    }
    const addition = adapter.buildRuntimePromptAddition({
      ...options,
      character: normalized,
    });
    return `${basePrompt}${adapter.formatPromptAddition?.(addition) || ""}`;
  }

  function buildMemorySystemPrompt(memorySet) {
    const memories = Array.isArray(memorySet?.memories) ? memorySet.memories.filter((memory) => memory.text).slice(-12) : [];
    if (!memories.length) return "";
    return `\n\nキャラクター記憶:\n${memories.map((memory) => `- ${memory.text}`).join("\n")}\n記憶はユーザー支援のヒントです。根拠のない事実を補完しないでください。`;
  }

  function isSensitiveMemoryText(text) {
    return /(パスワード|api\s*キー|api[_ -]?key|住所|電話番号|クレカ|カード番号|銀行|認証|secret|token|暗証番号|マイナンバー|保険証|病気|診断|家族|恋人|性的|sexual|password|credit card|bank)/i.test(String(text || ""));
  }

  function explicitMemoryCandidateFromText(text) {
    const value = String(text || "").trim();
    if (!value || !/(覚えて|おぼえて|記憶して|保存しておいて)/.test(value)) return null;
    const cleaned = value
      .replace(/^(これを|これ|以下を|次を)?\s*(覚えて|おぼえて|記憶して|保存しておいて)[：:\s]*/u, "")
      .replace(/[。.!！]?\s*(覚えて|おぼえて|記憶して|保存しておいて)[。.!！]?$/u, "")
      .trim();
    const textValue = cleaned || value;
    if (isSensitiveMemoryText(textValue)) {
      return null;
    }
    return {
      id: crypto.randomUUID(),
      text: textValue,
    };
  }

  function autoMemoryCandidateFromText(text) {
    const value = String(text || "").trim();
    if (!value || value.length > 90 || isSensitiveMemoryText(value)) return null;
    const preferenceMemoryText = (subject, item, kind) => {
      const cleanSubject = String(subject || "").trim();
      const cleanItem = String(item || "").trim();
      if (!cleanItem) return "";
      return cleanSubject ? `${cleanSubject}は${cleanItem}が${kind}` : `ユーザーは${cleanItem}が${kind}`;
    };
    const rules = [
      {
        pattern: /^(?:(?:私は|わたしは|僕は|ぼくは|俺は|ユーザーは)\s*)?(?:([ぁ-んァ-ヶ一-龠A-Za-z0-9ー・\s]{1,24})は)?\s*([ぁ-んァ-ヶ一-龠A-Za-z0-9ー・\s]{1,32})が好き/u,
        build: (match) => preferenceMemoryText(match[1], match[2], "好き"),
      },
      {
        pattern: /^(?:(?:私は|わたしは|僕は|ぼくは|俺は|ユーザーは)\s*)?(?:([ぁ-んァ-ヶ一-龠A-Za-z0-9ー・\s]{1,24})は)?\s*([ぁ-んァ-ヶ一-龠A-Za-z0-9ー・\s]{1,32})が苦手/u,
        build: (match) => preferenceMemoryText(match[1], match[2], "苦手"),
      },
      {
        pattern: /(?:私の|わたしの|僕の|ぼくの|俺の)?名前は\s*([ぁ-んァ-ヶ一-龠A-Za-z0-9ー・\s]{1,24})/u,
        build: (match) => `ユーザーの名前は${match[1].trim()}`,
      },
      {
        pattern: /([ぁ-んァ-ヶ一-龠A-Za-z0-9ー・\s]{1,24})って呼んで/u,
        build: (match) => `ユーザーは${match[1].trim()}と呼ばれたい`,
      },
      {
        pattern: /(短く|詳しく|やさしく|例を多めに|箇条書きで|中学生にも分かる言葉で).{0,20}(説明|答え)/u,
        build: (match) => `ユーザーは${match[1].trim()}説明されることを好む`,
      },
      {
        pattern: /(英検|受験|試験|テスト|レポート|宿題|課題|Python|JavaScript|数学|英語|国語|理科|社会).{0,24}(勉強|学習|練習|提出|取り組ん)/u,
        build: (match) => `ユーザーは${match[1].trim()}に取り組んでいる`,
      },
    ];
    for (const rule of rules) {
      const match = value.match(rule.pattern);
      if (match) {
        const textValue = rule.build(match).replace(/\s+/g, " ").trim();
        if (textValue && !isSensitiveMemoryText(textValue)) {
          return { id: crypto.randomUUID(), text: textValue, automatic: true };
        }
      }
    }
    return null;
  }

  function memoryCandidateFromText(text, { mode = "suggest" } = {}) {
    return explicitMemoryCandidateFromText(text) || (mode === "auto" ? autoMemoryCandidateFromText(text) : null);
  }

  function classifyMemory(memory) {
    const source = `${memory?.text || ""} ${(memory?.tags || []).join(" ")}`.toLowerCase();
    const tagText = (memory?.tags || []).join(" ").toLowerCase();
    if (/(^|\s)(profile|あなたについて|about-you)(\s|$)/.test(tagText)) return "profile";
    if (/(^|\s)(preference|好み|preferences)(\s|$)/.test(tagText)) return "preference";
    if (/(^|\s)(study|勉強|目標|study-goal)(\s|$)/.test(tagText)) return "study";
    if (/(^|\s)(settings|設定|config)(\s|$)/.test(tagText)) return "settings";

    const scores = { profile: 0, preference: 0, study: 0, settings: 0 };
    const add = (category, pattern, points = 1) => {
      if (pattern.test(source)) scores[category] += points;
    };

    add("profile", /名前|呼び方|呼んで|ユーザーは|私は|出身|誕生日|年齢|学校|所属|profile|name|call me|from/, 2);
    add("preference", /好き|好む|嫌い|苦手|好み|スタイル|短く|詳しく|やさしく|例を|例つき|箇条書き|preference|prefer|like|dislike|style|brief|detailed/, 2);
    add("study", /勉強|学習|科目|授業|宿題|課題|レポート|目標|試験|テスト|英検|受験|提出|プロジェクト|study|goal|class|homework|assignment|exam|project/, 2);
    add("settings", /設定|モデル|テーマ|音声|マイク|速度|精度|表示|ui|web検索|検索|翻訳|画像生成|setting|mode|theme|voice|mic|speed|accuracy|display|search|translation/, 2);

    const priority = ["profile", "preference", "study", "settings"];
    return priority.reduce((best, category) => (scores[category] > scores[best] ? category : best), "profile");
  }

  function characterMemoryContextId(memorySetId, memoryId) {
    return `character:${String(memorySetId || DEFAULT_MEMORY_SET.id)}:${String(memoryId || "")}`;
  }

  function characterMemoryContextScope(character = DEFAULT_CHARACTER, memorySet = DEFAULT_MEMORY_SET) {
    const normalized = normalizeCharacter(character);
    const set = normalizeMemorySet(memorySet, normalized);
    return {
      scopeType: "character",
      scopeId: set.id,
      ownerType: "character",
      ownerId: normalized.id,
      visibility: "private",
      projectId: "",
    };
  }

  function characterMemoryType(memory) {
    const category = classifyMemory(memory);
    if (category === "preference" || category === "settings") return "preference";
    if (category === "study") return "activity";
    return "fact";
  }

  function characterMemoryToContextItem({ character = DEFAULT_CHARACTER, memorySet = DEFAULT_MEMORY_SET, memory = {} } = {}) {
    const normalized = normalizeCharacter(character);
    const set = normalizeMemorySet(memorySet, normalized);
    const memoryId = String(memory?.id || "").trim();
    const text = normalizeMemoryText(memory?.text || "");
    if (!memoryId || !text) return null;
    return {
      id: characterMemoryContextId(set.id, memoryId),
      text,
      memoryType: characterMemoryType(memory),
      sourceType: "character",
      sourceId: memoryId,
    };
  }

  function addMemory({ memorySets, character, text, sourceSessionId = "", sourceFolderId = "", createId = () => crypto.randomUUID(), nowIso = () => new Date().toISOString() }) {
    const value = normalizeMemoryText(text);
    if (!value) return memorySets;
    const nextSets = (Array.isArray(memorySets) && memorySets.length ? memorySets : loadMemorySets(character))
      .map((set) => ({ ...set, memories: [...set.memories] }));
    const set = nextSets.find((item) => item.id === character.memorySetId) || nextSets[0];
    if (set.memories.some((memory) => String(memory.text || "").trim() === value)) {
      return saveMemorySets(nextSets);
    }
    const now = nowIso();
    set.memories.push({
      id: createId(),
      text: value,
      sourceSessionId,
      sourceFolderId,
      createdAt: now,
      updatedAt: now,
      tags: [],
      pinned: false,
    });
    return saveMemorySets(nextSets);
  }

  function updateMemory({ memorySets, memorySetId, memoryId, text, nowIso = () => new Date().toISOString() }) {
    const value = String(text || "").trim();
    const nextSets = memorySets.map((set) => ({
      ...set,
      memories: set.memories.map((memory) => (
        set.id === memorySetId && memory.id === memoryId
          ? { ...memory, text: value, updatedAt: nowIso() }
          : memory
      )).filter((memory) => memory.text),
    }));
    return saveMemorySets(nextSets);
  }

  function deleteMemory({ memorySets, memorySetId, memoryId }) {
    const nextSets = memorySets.map((set) => ({
      ...set,
      memories: set.id === memorySetId ? set.memories.filter((memory) => memory.id !== memoryId) : set.memories,
    }));
    return saveMemorySets(nextSets);
  }

  return {
    DEFAULT_CHARACTER,
    DEFAULT_MEMORY_SET,
    activeMemorySet,
    addMemory,
    buildCharacterSystemPrompt,
    buildMemorySystemPrompt,
    characterMemoryContextId,
    characterMemoryContextScope,
    characterMemoryToContextItem,
    classifyMemory,
    isSensitiveMemoryText,
    deleteMemory,
    loadCharacter,
    loadMemorySets,
    memoryCandidateFromText,
    normalizeCharacter,
    saveCharacter,
    saveMemorySets,
    updateMemory,
  };
})();
