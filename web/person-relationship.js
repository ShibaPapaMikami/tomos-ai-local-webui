(() => {
  const STORAGE_KEY = "gemma4.personRelationship.people.v1";
  const SELF_STORAGE_KEY = "gemma4.personRelationship.self.v1";
  const CATEGORIES = [
    { id: "friend", label: "友達" },
    { id: "romantic", label: "恋愛" },
    { id: "family", label: "家族" },
    { id: "work", label: "仕事" },
  ];
  const RELATION_DETAILS = [
    { id: "friend", label: "友人", category: "friend" },
    { id: "best_friend", label: "親友", category: "friend" },
    { id: "acquaintance", label: "知人", category: "friend" },
    { id: "partner", label: "恋人", category: "romantic" },
    { id: "spouse", label: "配偶者", category: "romantic" },
    { id: "former_partner", label: "元恋人", category: "romantic" },
    { id: "child", label: "子供", category: "family" },
    { id: "parent", label: "親", category: "family" },
    { id: "sibling", label: "兄弟姉妹", category: "family" },
    { id: "relative", label: "親族", category: "family" },
    { id: "coworker", label: "同僚", category: "work" },
    { id: "manager", label: "上司", category: "work" },
    { id: "direct_report", label: "部下", category: "work" },
    { id: "client", label: "取引先", category: "work" },
    { id: "other", label: "その他", category: "friend" },
  ];
  const GENDERS = [
    { id: "", label: "未設定" },
    { id: "female", label: "女性" },
    { id: "male", label: "男性" },
    { id: "other", label: "その他" },
    { id: "private", label: "回答しない" },
  ];
  const BLOOD_TYPES = [
    { id: "", label: "未設定" },
    { id: "A", label: "A" },
    { id: "B", label: "B" },
    { id: "O", label: "O" },
    { id: "AB", label: "AB" },
    { id: "unknown", label: "不明" },
  ];
  const BASE_PERSONALITY_TYPES = [
    "", "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
  ];
  const PERSONALITY_TYPES = BASE_PERSONALITY_TYPES.flatMap((type) => (
    type ? [type, `${type}-A`, `${type}-T`] : [""]
  ));
  const PERSONALITY_TYPE_NAMES = {
    INTJ: "建築家",
    INTP: "論理学者",
    ENTJ: "指揮官",
    ENTP: "討論者",
    INFJ: "提唱者",
    INFP: "仲介者",
    ENFJ: "主人公",
    ENFP: "運動家",
    ISTJ: "管理者",
    ISFJ: "擁護者",
    ESTJ: "幹部",
    ESFJ: "領事",
    ISTP: "巨匠",
    ISFP: "冒険家",
    ESTP: "起業家",
    ESFP: "エンターテイナー",
  };
  const PERSONALITY_TYPE_DESCRIPTIONS = {
    INTJ: "先を読んで構造化し、計画や優先順位に落とし込みやすい",
    INTP: "仕組みや理由を深く考え、筋道を大切にしやすい",
    ENTJ: "目的に向けて判断し、人や物事を前へ進めやすい",
    ENTP: "新しい案を出し、議論しながら可能性を広げやすい",
    INFJ: "先の意味を読み、人の気持ちや背景を大切にしやすい",
    INFP: "自分や相手の価値観を大切にし、納得感を重視しやすい",
    ENFJ: "相手の気持ちを見ながら場を整え、人を支えやすい",
    ENFP: "新しい可能性を広げ、人の気持ちや価値観を大切にしながら動きやすい",
    ISTJ: "経験や手順を大切にし、安定して物事を進めやすい",
    ISFJ: "相手をよく見て、現実的な配慮や支援を続けやすい",
    ESTJ: "基準や段取りを整え、決めたことを実行に移しやすい",
    ESFJ: "周囲との調和を見ながら、実務的に人を支えやすい",
    ISTP: "状況を冷静に見て、必要な手段を選びやすい",
    ISFP: "自分の感覚や相手へのやさしさを大切にしやすい",
    ESTP: "現場で判断し、すぐ行動しながら流れを作りやすい",
    ESFP: "場を明るくし、今の気持ちや体験を大切にしやすい",
  };
  const PERSONALITY_FUNCTION_STACKS = {
    INTJ: ["Ni", "Te", "Fi", "Se"],
    INTP: ["Ti", "Ne", "Si", "Fe"],
    ENTJ: ["Te", "Ni", "Se", "Fi"],
    ENTP: ["Ne", "Ti", "Fe", "Si"],
    INFJ: ["Ni", "Fe", "Ti", "Se"],
    INFP: ["Fi", "Ne", "Si", "Te"],
    ENFJ: ["Fe", "Ni", "Se", "Ti"],
    ENFP: ["Ne", "Fi", "Te", "Si"],
    ISTJ: ["Si", "Te", "Fi", "Ne"],
    ISFJ: ["Si", "Fe", "Ti", "Ne"],
    ESTJ: ["Te", "Si", "Ne", "Fi"],
    ESFJ: ["Fe", "Si", "Ne", "Ti"],
    ISTP: ["Ti", "Se", "Ni", "Fe"],
    ISFP: ["Fi", "Se", "Ni", "Te"],
    ESTP: ["Se", "Ti", "Fe", "Ni"],
    ESFP: ["Se", "Fi", "Te", "Ni"],
  };
  const PERSONALITY_RELATION_PAIRS = {
    ideal: new Set([
      "ENFJ:INFP",
      "ENFP:INFJ",
      "ENFP:INTJ",
      "ENTJ:INTP",
      "ENTP:INFJ",
      "ESFJ:ISFP",
      "ESFP:ISFJ",
      "ESTJ:ISTP",
      "ESTP:ISFJ",
    ]),
    strong: new Set([
      "ENFJ:INFJ",
      "ENFJ:ISFJ",
      "ENFP:ENTP",
      "ENTJ:INTJ",
      "ENTP:INTJ",
      "ESFJ:ISFJ",
      "ESFP:ESTP",
      "ESTJ:ISTJ",
      "INFP:INFJ",
      "ISFP:ISTP",
    ]),
    careful: new Set([
      "ENFJ:ISTP",
      "ENFP:ISTJ",
      "ENTJ:ISFP",
      "ENTP:ISFJ",
      "ESFJ:INTP",
      "ESFP:INTJ",
      "ESTJ:INFP",
      "ESTP:INFJ",
    ]),
  };
  const PERSONALITY_RELATION_CONFIG = {
    ideal: { grade: "◎", label: "相性: 理想的な補完", score: 2, description: "会話補助の参考として、補完しやすい組み合わせです" },
    strong: { grade: "○", label: "相性: 支え合いやすい", score: 1, description: "会話補助の参考として、安定しやすい組み合わせです" },
    careful: { grade: "△", label: "相性: すれ違い注意", score: 0, description: "会話補助の参考として、確認を増やしたい組み合わせです" },
  };
  const PERSONALITY_FUNCTION_ROLES = ["主機能", "補助機能", "第三機能", "劣等機能"];
  const PERSONALITY_FUNCTION_NOTES = {
    Ni: "先を読む直感",
    Ne: "可能性を広げる直感",
    Si: "経験を積み重ねる感覚",
    Se: "今の状況をつかむ感覚",
    Ti: "筋道を整理する思考",
    Te: "結果へ進める思考",
    Fi: "自分の価値観を大切にする感情",
    Fe: "場の気持ちを整える感情",
  };
  const PERSONALITY_LETTER_NOTES = {
    E: "外向",
    I: "内向",
    S: "現実",
    N: "直感",
    T: "論理",
    F: "感情",
    J: "計画",
    P: "柔軟",
  };
  const PERSONALITY_TEMPERAMENT_NOTES = {
    NT: "戦略や仕組みを重視",
    NF: "意味や人の気持ちを重視",
    SJ: "安定や手順を重視",
    SP: "現場感や即応を重視",
  };
  const PERSONALITY_COMPATIBILITY_SOURCE_NOTE = "MBTIは医学・心理診断ではなく、会話の参考にするための16タイプ分類です";
  const COMPATIBILITY_SORT_OPTIONS = [
    { id: "total", label: "総合" },
    { id: "mbti", label: "MBTI" },
    { id: "birthdate", label: "生年月日" },
    { id: "strokes", label: "姓名判断 五格" },
  ];
  const ZODIAC_SIGNS = [
    { id: "aquarius", label: "水瓶座", startMonth: 1, startDay: 20, element: "air", elementLabel: "風", modality: "fixed", modalityLabel: "不動宮" },
    { id: "pisces", label: "魚座", startMonth: 2, startDay: 19, element: "water", elementLabel: "水", modality: "mutable", modalityLabel: "柔軟宮" },
    { id: "aries", label: "牡羊座", startMonth: 3, startDay: 21, element: "fire", elementLabel: "火", modality: "cardinal", modalityLabel: "活動宮" },
    { id: "taurus", label: "牡牛座", startMonth: 4, startDay: 20, element: "earth", elementLabel: "土", modality: "fixed", modalityLabel: "不動宮" },
    { id: "gemini", label: "双子座", startMonth: 5, startDay: 21, element: "air", elementLabel: "風", modality: "mutable", modalityLabel: "柔軟宮" },
    { id: "cancer", label: "蟹座", startMonth: 6, startDay: 22, element: "water", elementLabel: "水", modality: "cardinal", modalityLabel: "活動宮" },
    { id: "leo", label: "獅子座", startMonth: 7, startDay: 23, element: "fire", elementLabel: "火", modality: "fixed", modalityLabel: "不動宮" },
    { id: "virgo", label: "乙女座", startMonth: 8, startDay: 23, element: "earth", elementLabel: "土", modality: "mutable", modalityLabel: "柔軟宮" },
    { id: "libra", label: "天秤座", startMonth: 9, startDay: 23, element: "air", elementLabel: "風", modality: "cardinal", modalityLabel: "活動宮" },
    { id: "scorpio", label: "蠍座", startMonth: 10, startDay: 24, element: "water", elementLabel: "水", modality: "fixed", modalityLabel: "不動宮" },
    { id: "sagittarius", label: "射手座", startMonth: 11, startDay: 23, element: "fire", elementLabel: "火", modality: "mutable", modalityLabel: "柔軟宮" },
    { id: "capricorn", label: "山羊座", startMonth: 12, startDay: 22, element: "earth", elementLabel: "土", modality: "cardinal", modalityLabel: "活動宮" },
  ];
  const COMPLEMENTARY_ZODIAC_ELEMENTS = new Set(["air:fire", "earth:water"]);
  const TENSION_ZODIAC_ELEMENTS = new Set(["air:earth", "fire:water"]);
  const LIFE_PATH_GROUPS = [
    [1, 3, 5],
    [2, 6, 9],
    [4, 8],
    [7, 11, 22, 33],
  ];
  const TYPE_SOURCES = ["self_reported", "user_reported", "estimated", "unknown"];

  const text = (value) => String(value || "").trim();
  const nowIso = () => new Date().toISOString();
  const newId = () => globalThis.crypto?.randomUUID?.() || `person-${Date.now()}`;

  function relationshipCategories() {
    return CATEGORIES.map((item) => ({ ...item }));
  }

  function categoryLabel(id) {
    return CATEGORIES.find((item) => item.id === id)?.label || "友達";
  }

  function relationshipDetails(category = "") {
    return RELATION_DETAILS.filter((item) => (
      !category
      || item.category === category
      || (item.id === "spouse" && (category === "family" || category === "romantic"))
      || item.id === "other"
    ))
      .map((item) => ({ ...item }));
  }

  function relationDetailLabel(id) {
    return RELATION_DETAILS.find((item) => item.id === id)?.label || "";
  }

  function genderLabel(id) {
    return GENDERS.find((item) => item.id === id)?.label || "";
  }

  function optionList(list) {
    return list.map((item) => typeof item === "string" ? { id: item, label: item || "未設定" } : { ...item });
  }

  function personalityTypeOptions() {
    return PERSONALITY_TYPES.map((type) => {
      if (!type) return { id: "", label: "未設定" };
      const baseType = type.split("-", 1)[0];
      const name = PERSONALITY_TYPE_NAMES[baseType] || "";
      return { id: type, label: name ? `${type}　${name}` : type };
    });
  }

  function splitName(input = {}) {
    const lastName = text(input.lastName);
    const firstName = text(input.firstName);
    if (lastName || firstName) return { lastName, firstName };
    const name = text(input.name);
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return { lastName: parts[0], firstName: parts.slice(1).join(" ") };
    return { lastName: name, firstName: "" };
  }

  function fullName(input = {}) {
    const lastName = text(input.lastName);
    const firstName = text(input.firstName);
    const combined = [lastName, firstName].filter(Boolean).join(" ");
    return text(input.displayName) || combined || text(input.name) || "名前未設定";
  }

  function normalizeBirthdate(value) {
    const raw = text(value);
    return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : "";
  }

  function calculateAge(birthdate, today = new Date()) {
    const normalized = normalizeBirthdate(birthdate);
    if (!normalized) return "";
    const [year, month, day] = normalized.split("-").map(Number);
    let age = today.getFullYear() - year;
    const currentMonth = today.getMonth() + 1;
    const currentDay = today.getDate();
    if (currentMonth < month || (currentMonth === month && currentDay < day)) age -= 1;
    return age >= 0 && age < 130 ? String(age) : "";
  }

  function normalizeGender(value) {
    const id = text(value);
    return GENDERS.some((item) => item.id === id) ? id : "";
  }

  function normalizeBloodType(value) {
    const id = text(value).toUpperCase();
    return BLOOD_TYPES.some((item) => item.id === id) ? id : "";
  }

  function normalizePersonalityType(value) {
    const id = text(value).toUpperCase();
    return PERSONALITY_TYPES.includes(id) ? id : "";
  }

  function basePersonalityType(value) {
    return normalizePersonalityType(value).split("-", 1)[0] || "";
  }

  function personalityTemperament(type) {
    if (!type) return "";
    if (type[1] === "N") return type[2] === "T" ? "NT" : "NF";
    return type[3] === "J" ? "SJ" : "SP";
  }

  function personalitySharedLetters(self, other) {
    return [...self].filter((char, index) => char === other[index]);
  }

  function formatFunctions(functions) {
    return functions.length ? functions.join("、") : "なし";
  }

  function personalityPairKey(self, other) {
    return [self, other].sort().join(":");
  }

  function personalityRelationKind(self, other) {
    const key = personalityPairKey(self, other);
    return Object.entries(PERSONALITY_RELATION_PAIRS)
      .find(([, pairs]) => pairs.has(key))?.[0] || "";
  }

  function personalityFunctionRole(functionName, stack) {
    const index = stack.indexOf(functionName);
    return PERSONALITY_FUNCTION_ROLES[index] || "";
  }

  function personalityStackSummary(type, stack) {
    const top = stack.slice(0, 2).join("/");
    return `${type}: ${top || "未設定"}`;
  }

  function personalitySharedFunctionDetail(selfStack, otherStack) {
    const sharedAll = selfStack.filter((fn) => otherStack.includes(fn));
    if (!sharedAll.length) return "共通機能: なし。";
    const details = sharedAll.map((fn) => {
      const selfRole = personalityFunctionRole(fn, selfStack);
      const otherRole = personalityFunctionRole(fn, otherStack);
      const note = PERSONALITY_FUNCTION_NOTES[fn] || "";
      return `${fn}(${selfRole}/${otherRole}${note ? `・${note}` : ""})`;
    });
    return `共通機能: ${details.join("、")}。`;
  }

  function personalityLetterDetail(self, other) {
    const shared = personalitySharedLetters(self, other).map((letter) => PERSONALITY_LETTER_NOTES[letter] || letter);
    return shared.length ? `共通傾向: ${shared.join("、")}。` : "共通傾向は少なめです。";
  }

  function personalityTemperamentDetail(type) {
    const temperament = personalityTemperament(type);
    return temperament ? `${temperament}(${PERSONALITY_TEMPERAMENT_NOTES[temperament] || "気質"})` : "未設定";
  }

  function personalityTypeLabel(typeValue) {
    const normalized = normalizePersonalityType(typeValue);
    const base = basePersonalityType(typeValue);
    if (!base) return "";
    const name = PERSONALITY_TYPE_NAMES[base] || "";
    return `${normalized || base}${name ? `（${name}）` : ""}`;
  }

  function personalityTypeDescription(typeValue) {
    return PERSONALITY_TYPE_DESCRIPTIONS[basePersonalityType(typeValue)] || "";
  }

  function personalitySourceDetail() {
    return "\n判定のもと: 16タイプ分類の4指標、心理機能名、TOMOS独自の会話補助ルール。MBTIは医学・心理診断ではなく、会話補助の参考として見てください。";
  }

  function personalityRelationReadableDetail(kind, sharedAll = []) {
    if (kind === "ideal") {
      return "会話補助の参考では、発想と実行の役割分担がしやすく、相手の得意なところを補いやすい関係です。相手に送る文面では、結論だけでなく理由や選択肢も添えると、相手が動きやすくなります。";
    }
    if (kind === "strong") {
      const sharedCare = sharedAll.includes("Fe") ? "気持ちへの配慮が通じやすいです。" : "考え方の入口が近く、話を合わせやすいです。";
      return `安定しやすい組み合わせです。${sharedCare}ただし、近いぶん遠慮や思い込みが出やすいので、希望は短く確認すると安心です。相手に送る文面では、やさしい前置きと具体的なお願いをセットにすると伝わりやすくなります。`;
    }
    if (kind === "careful") {
      return "会話補助の参考では、注意ペアとして扱います。大事にするポイントがずれやすいので、目的、期限、気持ちを先に確認するとすれ違いを減らせます。相手に送る文面では、断定を避けて確認形にすると受け取られやすくなります。";
    }
    return "";
  }

  function compatibilityMark(grade) {
    if (grade === "◎") return "◎";
    if (grade === "○" || grade === "◯") return "◯";
    if (grade === "△") return "△";
    return "✗";
  }

  function sourceValue(value) {
    return text(value) || "未設定";
  }

  function profileNameSource(profile = {}) {
    const name = [text(profile.lastName), text(profile.firstName)].filter(Boolean).join(" ");
    return sourceValue(name || profile.displayName || profile.name);
  }

  function withCompatibilityMark(item = {}) {
    return { ...item, mark: compatibilityMark(item.grade) };
  }

  function personalityCompatibility(selfType, otherType) {
    const self = basePersonalityType(selfType);
    const other = basePersonalityType(otherType);
    if (!self || !other) {
      return { grade: "-", label: "相性: MBTI未設定", detail: "自分と相手のMBTIを入れると表示されます。", score: null };
    }
    const selfStack = PERSONALITY_FUNCTION_STACKS[self] || [];
    const otherStack = PERSONALITY_FUNCTION_STACKS[other] || [];
    const selfTop = selfStack.slice(0, 2);
    const otherTop = otherStack.slice(0, 2);
    const sharedTop = selfTop.filter((fn) => otherTop.includes(fn));
    const sharedAll = selfStack.filter((fn) => otherStack.includes(fn));
    const sharedLetters = personalitySharedLetters(self, other);
    const sameTemperament = personalityTemperament(self) === personalityTemperament(other);
    const intuitiveThinkFeelComplement = self[1] === "N" && other[1] === "N" && self[2] !== other[2];
    const inverseStack = selfStack[0] === otherStack[3] && selfStack[1] === otherStack[2];
    const relationKind = personalityRelationKind(self, other);
    if (self === other) {
      return {
        grade: "○",
        label: "相性: 似ている",
        detail: `同じタイプです。考え方や反応が近く、話は通じやすいです。一方で、迷うポイントも似やすいので、予定や気持ちは言葉で確認すると安心です。相手に送る文面では、分かっている前提にしすぎず、要点を一つずつ書くと安定します。${personalitySourceDetail()}`,
        score: 1,
      };
    }
    if (relationKind) {
      const config = PERSONALITY_RELATION_CONFIG[relationKind];
      return {
        grade: config.grade,
        label: config.label,
        detail: `${personalityRelationReadableDetail(relationKind, sharedAll)}${personalitySourceDetail()}`,
        score: config.score,
      };
    }
    if (inverseStack) {
      return {
        grade: "△",
        label: "相性: 刺激が強い",
        detail: `得意なことと苦手なことが入れ替わりやすい関係です。刺激にはなりますが、言い方が強く見えやすいので、依頼や断り方をやわらかくすると安定します。相手に送る文面では、正しさより先に背景と気持ちを添えると衝突を減らせます。${personalitySourceDetail()}`,
        score: 0,
      };
    }
    if (sharedTop.length >= 2) {
      return {
        grade: "◎",
        label: "相性: 判断が近い",
        detail: `ものごとの見方が近く、判断の前提を共有しやすい関係です。話は早い一方、同じ方向に偏ることがあるので、別視点も一度確認すると安心です。相手に送る文面では、短く結論を出してから補足を加えると伝わりやすくなります。${personalitySourceDetail()}`,
        score: 2,
      };
    }
    if (sharedTop.length === 1) {
      return {
        grade: "○",
        label: "相性: 通じる部分あり",
        detail: `考え方に通じる部分があります。全部が同じではないので、結論だけでなく理由も添えると伝わりやすくなります。相手に送る文面では、共通点に触れてからお願いや相談を書くと自然です。${personalitySourceDetail()}`,
        score: 1,
      };
    }
    if (intuitiveThinkFeelComplement) {
      return {
        grade: "○",
        label: "相性: 発想と感情の補完",
        detail: `大きな方向性の話は合いやすく、論理面と気持ち面で役割分担しやすい関係です。正しさだけでなく、相手がどう受け取るかも確認すると安定します。相手に送る文面では、提案と気づかいを同じ文の中に入れるとバランスが良くなります。${personalitySourceDetail()}`,
        score: 1,
      };
    }
    if (sameTemperament) {
      return {
        grade: "○",
        label: "相性: 気質が近い",
        detail: `関心を持つポイントが近く、会話の前提を合わせやすい関係です。慣れるほど省略が増えやすいので、大事なことは明確に伝えると安心です。相手に送る文面では、共有している前提と今回の目的を分けて書くと誤解が減ります。${personalitySourceDetail()}`,
        score: 1,
      };
    }
    if (sharedLetters.length >= 2) {
      return {
        grade: "○",
        label: "相性: 安定しやすい",
        detail: `共通する好みがあり、無理なく合わせやすい関係です。違う部分は先に希望を聞くと、やりとりがスムーズになります。相手に送る文面では、まず合わせられる点を示してから相談すると受け止められやすくなります。${personalitySourceDetail()}`,
        score: 1,
      };
    }
    if (sharedLetters.length === 1) {
      return {
        grade: "△",
        label: "相性: 違いを活かす",
        detail: `共通点は少なめですが、役割を分けると強みになります。相手に合わせて、目的、期限、希望する温度感を先に伝えると安定します。相手に送る文面では、確認したいことを箇条書きにするとすれ違いを減らせます。${personalitySourceDetail()}`,
        score: 0,
      };
    }
    return {
      grade: "△",
      label: "相性: 調整が必要",
      detail: `見方が大きく違うため、短い言葉だけだと誤解が起きやすい関係です。目的、期限、気持ちをはっきり伝えるとすれ違いを減らせます。相手に送る文面では、急がせず、確認してほしい点を一つずつ分けると安定します。${personalitySourceDetail()}`,
      score: 0,
    };
  }

  function parseBirthdateParts(value) {
    const normalized = normalizeBirthdate(value);
    if (!normalized) return null;
    const [year, month, day] = normalized.split("-").map(Number);
    return { year, month, day, normalized };
  }

  function zodiacSign(month, day) {
    let sign = ZODIAC_SIGNS[ZODIAC_SIGNS.length - 1];
    for (const candidate of ZODIAC_SIGNS) {
      if (month > candidate.startMonth || (month === candidate.startMonth && day >= candidate.startDay)) {
        sign = candidate;
      }
    }
    return sign;
  }

  function reduceLifePathNumber(value) {
    let current = value;
    while (current > 9 && ![11, 22, 33].includes(current)) {
      current = String(current).split("").reduce((sum, digit) => sum + Number(digit), 0);
    }
    return current;
  }

  function lifePathNumber(parts) {
    if (!parts) return null;
    const sum = parts.normalized.replace(/-/g, "").split("")
      .reduce((total, digit) => total + Number(digit), 0);
    return reduceLifePathNumber(sum);
  }

  function elementPair(selfElement, otherElement) {
    return [selfElement, otherElement].sort().join(":");
  }

  function sameLifePathGroup(selfNumber, otherNumber) {
    return LIFE_PATH_GROUPS.some((group) => group.includes(selfNumber) && group.includes(otherNumber));
  }

  function birthdateProfile(parts) {
    const sign = zodiacSign(parts.month, parts.day);
    return { sign, lifePath: lifePathNumber(parts) };
  }

  function signPersonalityHint(sign) {
    if (!sign) return "";
    const elementHints = {
      fire: "熱量や勢いが出やすく、動きながら流れを作りやすい傾向があります。",
      earth: "現実感や継続性を大切にし、着実に整える力が出やすい傾向があります。",
      air: "対話、調整、発想の切り替えを使いながら、関係や場を整えやすい傾向があります。",
      water: "感情や空気の変化を受け取り、相手の気持ちに寄り添いやすい傾向があります。",
    };
    return `${sign.label}は${sign.elementLabel}の星座なので、${elementHints[sign.element] || "自分の動き方を知る参考になります"}`;
  }

  function isLegacyAutoPersonalitySummary(value) {
    const source = text(value);
    if (!source) return false;
    return /ライフパス|返信では、強みを活かしつつ、説明不足や思い込みが出ないように補助します。/.test(source);
  }

  function selfPersonalitySummary(profile = {}) {
    const typeLabel = personalityTypeLabel(profile.personalityType);
    const description = personalityTypeDescription(profile.personalityType);
    const parts = parseBirthdateParts(profile.birthdate);
    const birthSummary = parts ? birthdateProfile(parts) : null;
    const lines = [];
    if (typeLabel && description) {
      lines.push(`基本傾向: ${typeLabel}は、${description}タイプとして扱います。人との関係では、相手が何を感じているか、場がどう動いているかを見ながら、自然に調整役へ回りやすいです。`);
    } else if (typeLabel) {
      lines.push(`基本傾向: ${typeLabel}を、会話補助のための性格タイプとして扱います。`);
    } else {
      lines.push("基本傾向: MBTIが未設定なので、性格面は自分のメモを優先して扱います。");
    }
    if (birthSummary) {
      lines.push(`生年月日の参考: ${signPersonalityHint(birthSummary.sign)}これは占いとして断定するものではなく、会話の温度感やタイミングを考えるための補助情報です。`);
    }
    lines.push("強み: 周囲の反応を見ながら、言葉の強さ、順番、雰囲気を整えられる点です。相手を励ましたり、関係を前に進めたりする場面で力を発揮しやすいです。");
    lines.push("注意点: 相手に合わせすぎると、自分の本音や疲れを後回しにしやすくなります。返信では、やさしさだけでなく、自分の希望や確認したいことも短く入れると安定します。");
    lines.push("返信支援での使い方: 家族や仕事相手には、まず安心感を出し、その後に要件を整理する文面が合いやすいです。大切な相手には、感謝、気づいたこと、次にどうしたいかを入れると自然に伝わります。");
    return lines.join("\n");
  }

  function datePartsFromDate(date = new Date()) {
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return { year, month, day, normalized: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}` };
  }

  function datePartsFromYearMonth(year, month, day = 15) {
    const target = new Date(year, month - 1, day);
    return datePartsFromDate(target);
  }

  function offsetMonthParts(baseDate = new Date(), offset = 0) {
    const target = new Date(baseDate.getFullYear(), baseDate.getMonth() + offset, 15);
    return datePartsFromDate(target);
  }

  function offsetYearParts(baseDate = new Date(), offset = 0) {
    const target = new Date(baseDate.getFullYear() + offset, 6, 1);
    return datePartsFromDate(target);
  }

  function monthLabel(parts) {
    return `${parts.year}年${parts.month}月`;
  }

  function yearLabel(parts) {
    return `${parts.year}年`;
  }

  function daysBetweenDateParts(start, end) {
    const startMs = Date.UTC(start.year, start.month - 1, start.day);
    const endMs = Date.UTC(end.year, end.month - 1, end.day);
    return Math.floor((endMs - startMs) / 86400000);
  }

  function biorhythmWave(days, period) {
    return Math.sin((2 * Math.PI * days) / period);
  }

  function biorhythmSlope(days, period) {
    return Math.cos((2 * Math.PI * days) / period);
  }

  function biorhythmLabel(value) {
    if (Math.abs(value) <= 0.15) return "切替";
    if (value >= 0.45) return "高調";
    if (value <= -0.45) return "低調";
    return "中間";
  }

  function biorhythmProfile(parts, baseParts = datePartsFromDate()) {
    const days = daysBetweenDateParts(parts, baseParts);
    const rhythms = [
      { key: "physical", label: "身体23日", value: biorhythmWave(days, 23), slope: biorhythmSlope(days, 23) },
      { key: "emotional", label: "感情28日", value: biorhythmWave(days, 28), slope: biorhythmSlope(days, 28) },
      { key: "intellectual", label: "知性33日", value: biorhythmWave(days, 33), slope: biorhythmSlope(days, 33) },
    ];
    return {
      baseDate: baseParts.normalized,
      days,
      rhythms: rhythms.map((item) => ({
        ...item,
        percent: Math.round(item.value * 100),
        phase: biorhythmLabel(item.value),
      })),
    };
  }

  function biorhythmSummary(profile) {
    return profile.rhythms
      .map((item) => `${item.label}${item.phase}(${item.percent >= 0 ? "+" : ""}${item.percent})`)
      .join("、");
  }

  function biorhythmSelfMark(average) {
    if (average >= 0.45) return "◎";
    if (average >= 0.1) return "◯";
    if (average >= -0.25) return "△";
    return "✗";
  }

  function biorhythmMarkTitle(mark) {
    if (mark === "◎") return "かなり良い";
    if (mark === "◯") return "安定";
    if (mark === "△") return "注意";
    return "休息優先";
  }

  function biorhythmDimensionMap(profile) {
    return profile.rhythms.reduce((result, item) => ({
      ...result,
      [item.key]: `${item.phase} ${item.percent >= 0 ? "+" : ""}${item.percent}`,
    }), {});
  }

  const BIORHYTHM_CATEGORY_CONFIG = [
    { key: "health", label: "健康", rhythmKeys: ["physical"], advice: { seed: "体調を整え始める時期です。睡眠、食事、軽い運動を戻すと次につながります。", bloom: "体力を使いやすい時期です。予定を入れるなら無理のない範囲で動きやすいです。", harvest: "整えた習慣を回収する時期です。疲れを残さないようにメンテナンスも入れてください。", rest: "休息を優先する時期です。無理な予定や夜更かしを避けると安定します。" } },
    { key: "work", label: "仕事", rhythmKeys: ["intellectual", "physical"], advice: { seed: "企画、準備、調査に向く時期です。大きく広げる前に段取りを整えると良いです。", bloom: "実行しやすい時期です。提案、交渉、集中作業を進めやすい流れです。", harvest: "成果の確認や仕組み化に向く時期です。契約、振り返り、改善に使いやすいです。", rest: "守りを優先する時期です。新規拡大より、整理、確認、リスク回避が向いています。" } },
    { key: "study", label: "学業", rhythmKeys: ["intellectual", "emotional"], advice: { seed: "学び始めや復習計画に向く時期です。小さく始めると続けやすいです。", bloom: "理解と集中を伸ばしやすい時期です。課題、試験対策、読解を進めやすいです。", harvest: "覚えた内容をまとめる時期です。ノート整理、発表、アウトプットに向いています。", rest: "詰め込みより回復が必要な時期です。短時間学習や復習中心にすると安定します。" } },
    { key: "love", label: "恋愛", rhythmKeys: ["emotional", "physical"], advice: { seed: "関係の土台を作る時期です。軽い連絡や自然な会話から始めると良いです。", bloom: "気持ちを伝えやすい時期です。会う、誘う、感謝を言葉にする行動が向いています。", harvest: "関係を深める時期です。約束、確認、感謝を形にすると安定します。", rest: "距離感を整える時期です。無理に詰めず、自分の気持ちを休ませると良いです。" } },
  ];

  function biorhythmPhase(score, slope = 0) {
    if (score >= 0.45) return "開花";
    if (score <= -0.45) return "休息";
    return slope >= 0 ? "種まき" : "収穫";
  }

  function biorhythmPhaseKey(phase) {
    if (phase === "開花") return "bloom";
    if (phase === "収穫") return "harvest";
    if (phase === "休息") return "rest";
    return "seed";
  }

  function biorhythmDomain(profile, config) {
    const rhythms = config.rhythmKeys
      .map((key) => profile.rhythms.find((item) => item.key === key))
      .filter(Boolean);
    const score = rhythms.reduce((sum, item) => sum + item.value, 0) / rhythms.length;
    const slope = rhythms.reduce((sum, item) => sum + item.slope, 0) / rhythms.length;
    const phase = biorhythmPhase(score, slope);
    return {
      key: config.key,
      label: config.label,
      phase,
      score,
      detail: config.advice[biorhythmPhaseKey(phase)],
    };
  }

  function biorhythmCategoryMap(profile) {
    return BIORHYTHM_CATEGORY_CONFIG.reduce((result, config) => ({
      ...result,
      [config.key]: biorhythmDomain(profile, config),
    }), {});
  }

  function biorhythmOverallPhase(categories) {
    const values = Object.values(categories);
    const score = values.reduce((sum, item) => sum + item.score, 0) / values.length;
    return biorhythmPhase(score, score);
  }

  function biorhythmSelfPeriod(birthParts, targetParts, label) {
    const profile = biorhythmProfile(birthParts, targetParts);
    const categories = biorhythmCategoryMap(profile);
    const phase = biorhythmOverallPhase(categories);
    return {
      label,
      mark: phase,
      phase,
      title: phase,
      score: Object.values(categories).reduce((sum, item) => sum + item.score, 0) / Object.values(categories).length,
      categories,
    };
  }

  function biorhythmSelfModel(birthdate, baseDate = new Date()) {
    const parts = parseBirthdateParts(birthdate);
    if (!parts) {
      return {
        ok: false,
        months: [],
        years: [],
        source: "判定のもと: 生年月日、身体23日・感情28日・知性33日のバイオリズム。科学的予測ではなく、セルフチェック用の参考です。",
      };
    }
    const months = [-2, -1, 0, 1, 2].map((offset) => {
      const target = offsetMonthParts(baseDate, offset);
      return biorhythmSelfPeriod(parts, datePartsFromYearMonth(target.year, target.month, 15), monthLabel(target));
    });
    const years = [-1, 0, 1].map((offset) => {
      const target = offsetYearParts(baseDate, offset);
      return biorhythmSelfPeriod(parts, datePartsFromYearMonth(target.year, 7, 1), yearLabel(target));
    });
    return {
      ok: true,
      birthdate: parts.normalized,
      months,
      years,
      source: "判定のもと: 生年月日、身体23日・感情28日・知性33日のバイオリズム。科学的予測ではなく、セルフチェック用の参考です。",
    };
  }

  function biorhythmSelfContextLines(birthdate, baseDate = new Date()) {
    const model = biorhythmSelfModel(birthdate, baseDate);
    if (!model.ok) return [];
    const currentMonth = model.months[2] || model.months.find(Boolean);
    if (!currentMonth) return [];
    const categoryLines = ["health", "work", "study", "love"].map((key) => {
      const item = currentMonth.categories?.[key];
      return item ? `${item.label}: ${item.phase} - ${item.detail}` : "";
    }).filter(Boolean);
    return [
      `自分の今月バイオリズム: ${currentMonth.label} / 総合: ${currentMonth.phase}`,
      "今日の運勢や今月の流れを聞かれたら、このバイオリズムを根拠に答える。",
      ...categoryLines,
      model.source,
    ];
  }

  function birthdateCompatibility(selfBirthdate, otherBirthdate) {
    const self = parseBirthdateParts(selfBirthdate);
    const other = parseBirthdateParts(otherBirthdate);
    if (!self || !other) {
      return { key: "birthdate", label: "生年月日", grade: "-", title: "未設定", detail: "自分と相手の生年月日を入れると表示されます。", score: null };
    }
    const selfProfile = birthdateProfile(self);
    const otherProfile = birthdateProfile(other);
    let rawScore = 0;
    if (selfProfile.sign.id === otherProfile.sign.id) rawScore += 2.2;
    else if (selfProfile.sign.element === otherProfile.sign.element) rawScore += 2;
    else if (COMPLEMENTARY_ZODIAC_ELEMENTS.has(elementPair(selfProfile.sign.element, otherProfile.sign.element))) rawScore += 1.6;
    else if (TENSION_ZODIAC_ELEMENTS.has(elementPair(selfProfile.sign.element, otherProfile.sign.element))) rawScore += 0.2;
    else rawScore += 0.8;
    if (selfProfile.sign.modality === otherProfile.sign.modality) rawScore += 0.8;
    if (selfProfile.lifePath === otherProfile.lifePath) rawScore += 1;
    else if (sameLifePathGroup(selfProfile.lifePath, otherProfile.lifePath)) rawScore += 0.8;
    else if (selfProfile.lifePath % 2 === otherProfile.lifePath % 2) rawScore += 0.4;
    else rawScore += 0.2;
    const signDetail = `太陽星座: ${selfProfile.sign.label}(${selfProfile.sign.elementLabel}・${selfProfile.sign.modalityLabel}) × ${otherProfile.sign.label}(${otherProfile.sign.elementLabel}・${otherProfile.sign.modalityLabel})。`;
    const lifePathDetail = `ライフパス: ${selfProfile.lifePath} × ${otherProfile.lifePath}。`;
    const elementAdvice = selfProfile.sign.element === otherProfile.sign.element
      ? "価値観やテンポが近く、話の流れを合わせやすい組み合わせです。"
      : COMPLEMENTARY_ZODIAC_ELEMENTS.has(elementPair(selfProfile.sign.element, otherProfile.sign.element))
        ? "得意な方向が補い合いやすく、相手にない視点を足しやすい組み合わせです。"
        : "反応の仕方に差が出やすいので、前提を短く共有すると安定します。";
    const lifePathAdvice = selfProfile.lifePath === otherProfile.lifePath
      ? "数秘では同じライフパスなので、大事にする流れが重なりやすいです。"
      : sameLifePathGroup(selfProfile.lifePath, otherProfile.lifePath)
        ? "数秘では近いグループなので、動き方や関心が寄りやすいです。"
        : "数秘では違いが出やすいため、相手の判断ペースを確認すると安心です。";
    const detail = `${signDetail}${lifePathDetail}${elementAdvice}${lifePathAdvice}会話では、予定や決めごとは具体的に、気持ちの話は急がず確認すると使いやすいです。\n判定のもと: 太陽星座の元素・活動分類、数秘術のライフパス、TOMOS独自の会話補助ルール。占術・数秘は科学的な相性判定ではなく、会話のきっかけとして扱います。`;
    if (rawScore >= 3) {
      return { key: "birthdate", label: "生年月日", grade: "◎", title: "星座・数秘の接点が多い", detail, score: 2 };
    }
    if (rawScore >= 2) {
      return { key: "birthdate", label: "生年月日", grade: "○", title: "星座・数秘の接点あり", detail, score: 1 };
    }
    return { key: "birthdate", label: "生年月日", grade: "△", title: "星座・数秘の違いあり", detail, score: 0 };
  }

  function nameFortuneInput(person = {}) {
    return {
      lastName: person.lastName,
      firstName: person.firstName,
      displayName: person.displayName,
      nickname: person.nickname,
      name: person.name,
    };
  }

  function strokeCompatibility(selfPerson, otherPerson) {
    const engine = globalThis.TOMOS_NAME_FORTUNE || globalThis.window?.TOMOS_NAME_FORTUNE;
    if (!engine?.compareFiveGrids) {
      return { key: "strokes", label: "姓名判断 五格", grade: "-", title: "未読込", detail: "五格計算エンジンを読み込むと表示されます。", score: null };
    }
    const result = engine.compareFiveGrids(nameFortuneInput(selfPerson), nameFortuneInput(otherPerson));
    return {
      key: "strokes",
      label: "姓名判断 五格",
      grade: result.grade,
      title: result.title,
      detail: result.ok
        ? `${result.detail}。五格が近い場合は、名前から見た印象や距離感が似やすい参考として扱います。五格が離れている場合も、相性そのものを決めるものではなく、呼び方や言葉の温度感を調整する目安にしてください。\n判定のもと: 姓名、TOMOS標準五格。文化的な姓名判断の参考であり、相性を断定しません。`
        : `${result.detail}\n判定のもと: 姓名、TOMOS標準五格。文化的な姓名判断の参考であり、相性を断定しません。`,
      score: result.score,
      fortune: result,
    };
  }

  function relationshipCategoryCompatibility(person) {
    const category = person.relationshipCategory;
    const relation = relationDetailLabel(person.relationDetail) || categoryLabel(category);
    if (category === "family" || category === "romantic") {
      return {
        key: "relationship",
        label: "関係",
        grade: "◎",
        title: relation,
        detail: "距離が近い関係なので、言葉の温度感が大切です。説明しすぎるより、短くても相手を気にかけていることが伝わる文面が向いています。お願いや確認は、責める言い方ではなく相談形にすると安定します。\n判定のもと: 登録された関係カテゴリと詳細関係。",
        score: 2,
      };
    }
    if (category === "friend") {
      return {
        key: "relationship",
        label: "関係",
        grade: "○",
        title: relation,
        detail: "自然な会話を作りやすい関係です。重くなりすぎない言い方にしつつ、相手にしてほしいことがある場合は最後に一つだけ明確に書くと伝わりやすいです。\n判定のもと: 登録された関係カテゴリと詳細関係。",
        score: 1,
      };
    }
    return {
      key: "relationship",
      label: "関係",
      grade: "○",
      title: relation,
      detail: "目的や前提をそろえるとやりとりしやすい関係です。仕事や用件のある相手には、結論、理由、期限の順に書くと相手が判断しやすくなります。\n判定のもと: 登録された関係カテゴリと詳細関係。",
      score: 1,
    };
  }

  function memoCompatibility(person) {
    if (text(person.notes)) {
      return {
        key: "memo",
        label: "会話メモ",
        grade: "◎",
        title: "配慮しやすい",
        detail: "自分との関係メモがあるため、相手の好きな話し方、苦手な言い方、注意点を返信支援に反映しやすい状態です。実際の文面では、このメモを最優先の配慮として扱います。\n判定のもと: 自分との関係メモ。",
        score: 2,
      };
    }
    return {
      key: "memo",
      label: "会話メモ",
      grade: "-",
      title: "未設定",
      detail: "好きな話し方や注意点が未設定です。相手が短文を好む、強い言い方が苦手、先に結論がほしいなどを入れると、返信支援の精度が上がります。\n判定のもと: 自分との関係メモ。",
      score: null,
    };
  }

  function compatibilityScore(item) {
    return typeof item.score === "number" ? item.score : null;
  }

  function compatibilitySortOptions() {
    return COMPATIBILITY_SORT_OPTIONS.map((item) => ({ ...item }));
  }

  function compatibilitySortOption(sortKey = "total") {
    return COMPATIBILITY_SORT_OPTIONS.find((item) => item.id === sortKey) || COMPATIBILITY_SORT_OPTIONS[0];
  }

  function compatibilityPoint(score) {
    if (typeof score !== "number") return 0;
    return Math.max(45, Math.min(95, Math.round(55 + score * 20)));
  }

  function compatibilityPointLabel(point) {
    if (point >= 85) return "とても相性の良い組み合わせ";
    if (point >= 75) return "安定しやすい組み合わせ";
    if (point >= 65) return "歩み寄りで伸びる組み合わせ";
    return "工夫すると良くなる組み合わせ";
  }

  function relationshipTheme(other) {
    if (other.relationshipCategory === "romantic" || other.relationDetail === "spouse" || other.relationDetail === "partner") {
      return {
        bond: "お互いを大切にしながら、安心感を育てやすい関係です。",
        action: "二人の時間を丁寧に作る",
        message: "急いで正解を出すより、日々の小さな気持ちを言葉にすると関係が深まりやすいです。",
      };
    }
    if (other.relationshipCategory === "family") {
      return {
        bond: "近い距離だからこそ、支え合いながら信頼を育てやすい関係です。",
        action: "感謝とお願いを短く伝える",
        message: "分かってくれるはずで終わらせず、ありがとうと本音を少しずつ言葉にすると安定します。",
      };
    }
    if (other.relationshipCategory === "work") {
      return {
        bond: "役割を分けることで、現実的に成果を出しやすい関係です。",
        action: "目的、期限、次の一手をそろえる",
        message: "相手の強みを先に認めてから相談すると、協力関係を作りやすいです。",
      };
    }
    return {
      bond: "自然な会話の中で、お互いの良さを見つけやすい関係です。",
      action: "近況を聞き、相手の変化に気づく",
      message: "軽い言葉でも、相手を見ていることが伝わると距離が縮まりやすいです。",
    };
  }

  function relationshipCaution(selfType, otherType) {
    const selfBase = basePersonalityType(selfType);
    const otherBase = basePersonalityType(otherType);
    if (selfBase && otherBase && selfBase[2] === "F" && otherBase[2] === "F") {
      return "ただし、お互いに相手を優先しすぎる傾向があります。「本当は疲れている」「少し寂しい」といった気持ちを我慢すると、気づかないうちに距離ができることがあります。";
    }
    if (selfBase && otherBase && selfBase[2] === "T" && otherBase[2] === "T") {
      return "ただし、正しさや効率を優先しすぎると、気持ちの確認が後回しになりやすいです。大事な話ほど、結論の前に相手の受け止め方を確認すると安定します。";
    }
    if (selfBase && otherBase && selfBase[3] !== otherBase[3]) {
      return "ただし、予定の決め方や動くタイミングに差が出やすいです。片方が急ぎ、片方が様子を見たい時は、期限と自由度を先にそろえるとすれ違いを減らせます。";
    }
    return "ただし、近い関係ほど言わなくても伝わると思い込みやすいです。小さな違和感をためず、短い言葉で確認することが長続きの秘訣です。";
  }

  function relationshipBirthdateNarrative(self, other) {
    const selfParts = parseBirthdateParts(self.birthdate);
    const otherParts = parseBirthdateParts(other.birthdate);
    if (!selfParts || !otherParts) return "";
    const selfProfile = birthdateProfile(selfParts);
    const otherProfile = birthdateProfile(otherParts);
    return `生年月日では、自分は${selfProfile.sign.label}でライフパス${selfProfile.lifePath}、${other.name}さんは${otherProfile.sign.label}でライフパス${otherProfile.lifePath}です。星座や数秘の見方では、気持ちの向きや動くテンポを知る参考になります。`;
  }

  function relationshipStrokeNarrative(strokeItem) {
    if (!strokeItem?.fortune?.ok) return "";
    return `姓名判断では「${strokeItem.title}」です。${strokeItem.fortune.detail}という見方なので、名前から受ける印象や距離感にも接点を見つけやすい関係として扱います。`;
  }

  function relationshipTotalDetail(self, other, items, scoredCount, average) {
    const otherType = personalityTypeLabel(other.personalityType);
    const selfType = personalityTypeLabel(self.personalityType);
    const otherDescription = personalityTypeDescription(other.personalityType);
    const selfDescription = personalityTypeDescription(self.personalityType);
    const mbtiItem = items.find((item) => item.key === "mbti");
    const birthdateItem = items.find((item) => item.key === "birthdate");
    const strokeItem = items.find((item) => item.key === "strokes");
    const point = compatibilityPoint(average);
    const theme = relationshipTheme(other);
    const birthdateNarrative = relationshipBirthdateNarrative(self, other);
    const strokeNarrative = relationshipStrokeNarrative(strokeItem);
    if (otherType && selfType) {
      return [
        "相性診断結果",
        `相性度: ${point}点（${compatibilityPointLabel(point)}）`,
        `${self.name || "あなた"}と${other.name}さんは、${theme.bond}`,
        "なぜ相性がいいか",
        `相手の性格: ${otherType}は、${otherDescription}タイプとして扱います。`,
        `自分は${selfType}で、${selfDescription}タイプとして扱います。`,
        `${other.name}さんの良さと自分の強みが重なることで、ただ合わせるだけではなく、足りない部分を補いやすい関係です。`,
        birthdateNarrative,
        strokeNarrative,
        "注意点",
        relationshipCaution(self.personalityType, other.personalityType),
        "相性を高めるポイント",
        `・${theme.action}`,
        "・感謝を言葉にする",
        "・本音を我慢せず短く伝える",
        "二人だけのメッセージ",
        theme.message,
        `判定メモ: MBTIは「${mbtiItem?.title || "未設定"}」、生年月日は「${birthdateItem?.title || "未設定"}」、姓名判断は「${strokeItem?.title || "未設定"}」。${scoredCount}項目から見た会話補助用の参考相性です。`,
      ].join("\n");
    }
    if (otherType) {
      return [
        "相性診断結果",
        `相性度: ${point}点（${compatibilityPointLabel(point)}）`,
        `${other.name}さんは、${otherDescription}タイプとして扱います。`,
        "自分のMBTIも入れると、どの点が合いやすく、どこを補うとよいかをもう少し具体化できます。",
        `${scoredCount}項目から見た会話補助用の参考相性です。`,
      ].join("\n");
    }
    return `相性診断結果\n相性度: ${point}点（${compatibilityPointLabel(point)}）\n${scoredCount}項目から見た会話補助用の参考相性です。相手のMBTIを入れると、性格面からの説明を追加できます。`;
  }

  function relationshipCompatibility(selfProfile, person) {
    const self = normalizeSelfProfile(selfProfile);
    const other = normalizePerson(person);
    const mbti = personalityCompatibility(self.personalityType, other.personalityType);
    const items = [
      {
        key: "mbti",
        label: "MBTI",
        grade: mbti.grade,
        title: mbti.label.replace(/^相性: /, ""),
        detail: mbti.detail,
        score: typeof mbti.score === "number" ? mbti.score : null,
        source: `自分: ${sourceValue(self.personalityType)} / 相手: ${sourceValue(other.personalityType)}`,
      },
      {
        ...birthdateCompatibility(self.birthdate, other.birthdate),
        source: `自分: ${sourceValue(self.birthdate)} / 相手: ${sourceValue(other.birthdate)}`,
      },
      {
        ...strokeCompatibility(self, other),
        source: `自分: ${profileNameSource(self)} / 相手: ${profileNameSource(other)}`,
      },
    ].map(withCompatibilityMark);
    const scores = items.map(compatibilityScore).filter((score) => score !== null);
    if (!scores.length) {
      return { grade: "-", mark: compatibilityMark("-"), score: null, label: "総合相性: 情報不足", detail: "プロフィールを入れると多面的に表示されます。", items };
    }
    const average = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    const detail = relationshipTotalDetail(self, other, items, scores.length, average);
    if (average >= 1.6) {
      return { grade: "◎", mark: compatibilityMark("◎"), score: average, label: "総合相性: かなり良い", detail, items };
    }
    if (average >= 0.9) {
      return { grade: "○", mark: compatibilityMark("○"), score: average, label: "総合相性: 安定しやすい", detail, items };
    }
    return { grade: "△", mark: compatibilityMark("△"), score: average, label: "総合相性: 工夫すると良い", detail, items };
  }

  function legacyNotes(input = {}) {
    const notes = text(input.notes);
    if (notes) return notes;
    return [
      text(input.relationshipMemo),
      text(input.likes) ? `好きなこと: ${text(input.likes)}` : "",
      text(input.dislikes) ? `苦手なこと: ${text(input.dislikes)}` : "",
      text(input.conversationNotes) ? `会話の注意点: ${text(input.conversationNotes)}` : "",
    ].filter(Boolean).join("\n");
  }

  function defaultDetailForCategory(category) {
    return relationshipDetails(category)[0]?.id || "other";
  }

  function normalizePerson(input = {}) {
    const relationshipCategory = CATEGORIES.some((item) => item.id === input.relationshipCategory)
      ? input.relationshipCategory
      : "friend";
    const relationDetail = RELATION_DETAILS.some((item) => item.id === input.relationDetail)
      ? input.relationDetail
      : defaultDetailForCategory(relationshipCategory);
    const names = splitName(input);
    const birthdate = normalizeBirthdate(input.birthdate);
    const personalityType = normalizePersonalityType(input.personalityType);
    const personalityTypeSource = TYPE_SOURCES.includes(input.personalityTypeSource)
      ? input.personalityTypeSource
      : "unknown";
    const createdAt = text(input.createdAt) || nowIso();
    const displayName = fullName({ ...input, ...names });
    return {
      id: text(input.id) || newId(),
      firstName: names.firstName,
      lastName: names.lastName,
      displayName,
      name: displayName,
      nickname: text(input.nickname),
      photo: text(input.photo),
      relationshipCategory,
      relationDetail,
      birthdate,
      age: calculateAge(birthdate) || text(input.age),
      gender: normalizeGender(input.gender),
      bloodType: normalizeBloodType(input.bloodType),
      personalityType,
      personalityTypeSource,
      personalityTypeLabel: personalityType ? `MBTI: ${personalityType}` : "",
      notes: legacyNotes(input),
      relationshipMemo: legacyNotes(input),
      createdAt,
      updatedAt: nowIso(),
      scopeType: text(input.scopeType) || "user",
      deletedAt: text(input.deletedAt),
    };
  }

  function normalizeSelfProfile(input = {}) {
    const names = splitName(input);
    const birthdate = normalizeBirthdate(input.birthdate);
    const displayName = fullName({ ...input, ...names, name: text(input.name) || "自分" });
    return {
      id: "self",
      firstName: names.firstName,
      lastName: names.lastName,
      displayName,
      name: displayName,
      nickname: text(input.nickname),
      birthdate,
      age: calculateAge(birthdate) || text(input.age),
      gender: normalizeGender(input.gender),
      bloodType: normalizeBloodType(input.bloodType),
      personalityType: normalizePersonalityType(input.personalityType),
      personalitySummary: (() => {
        const summary = text(input.personalitySummary) || text(input.personalitySummaryMemo);
        return summary && !isLegacyAutoPersonalitySummary(summary) ? summary : selfPersonalitySummary(input);
      })(),
      notes: text(input.notes) || text(input.relationshipMemo),
      updatedAt: nowIso(),
    };
  }

  function loadPeople(storage = localStorage) {
    try {
      const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(parsed)
        ? parsed.map(normalizePerson).filter((person) => !person.deletedAt)
        : [];
    } catch {
      return [];
    }
  }

  function savePeople(people, storage = localStorage) {
    const normalized = Array.isArray(people) ? people.map(normalizePerson) : [];
    storage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    return normalized;
  }

  function loadSelfProfile(storage = localStorage) {
    try {
      return normalizeSelfProfile(JSON.parse(storage.getItem(SELF_STORAGE_KEY) || "{}"));
    } catch {
      return normalizeSelfProfile({});
    }
  }

  function saveSelfProfile(profile, storage = localStorage) {
    const normalized = normalizeSelfProfile(profile);
    storage.setItem(SELF_STORAGE_KEY, JSON.stringify(normalized));
    return normalized;
  }

  function upsertPerson(people, input) {
    const person = normalizePerson(input);
    const list = Array.isArray(people) ? people.filter((item) => item.id !== person.id) : [];
    return [person, ...list];
  }

  function deletePerson(people, id) {
    return (Array.isArray(people) ? people : []).filter((person) => person.id !== id);
  }

  function buildRecipientContextPrompt(person) {
    if (!person?.id) return "";
    const lines = [
      "返信先に合わせた文脈:",
      `送り先: ${person.name}`,
      person.nickname ? `呼び名: ${person.nickname}` : "",
      `関係: ${relationDetailLabel(person.relationDetail) || categoryLabel(person.relationshipCategory)}`,
      person.notes ? `自分とのメモ: ${person.notes}` : "",
      person.personalityType ? `MBTI参考: ${person.personalityType}` : "",
      "個人情報を断定せず、送信前にユーザーが調整できる返信案として出す。",
    ].filter(Boolean);
    return `\n\n${lines.join("\n")}`;
  }

  function personContextLine(person, index) {
    const normalized = normalizePerson(person);
    const lines = [
      `登録人物 ${index + 1}: ${normalized.name}`,
      normalized.nickname ? `呼び名: ${normalized.nickname}` : "",
      `関係: ${relationDetailLabel(normalized.relationDetail) || categoryLabel(normalized.relationshipCategory)}`,
      normalized.birthdate ? `生年月日: ${normalized.birthdate}` : "",
      normalized.gender ? `性別: ${genderLabel(normalized.gender)}` : "",
      normalized.bloodType ? `血液型: ${normalized.bloodType}` : "",
      normalized.personalityType ? `MBTI: ${normalized.personalityType}` : "",
      normalized.notes ? `自分とのメモ: ${normalized.notes}` : "",
    ].filter(Boolean);
    return lines.join("\n");
  }

  function buildPeopleContextPrompt(selfProfile, people = []) {
    const persons = (Array.isArray(people) ? people : []).map(normalizePerson);
    const self = normalizeSelfProfile(selfProfile || {});
    if (!persons.length && !self.name && !self.birthdate && !self.personalityType && !self.personalitySummary && !self.notes) return "";
    const selfLines = [
      `自分: ${self.name || "自分"}`,
      self.nickname ? `呼び名: ${self.nickname}` : "",
      self.birthdate ? `生年月日: ${self.birthdate}` : "",
      ...biorhythmSelfContextLines(self.birthdate),
      self.gender ? `性別: ${genderLabel(self.gender)}` : "",
      self.bloodType ? `血液型: ${self.bloodType}` : "",
      self.personalityType ? `MBTI: ${self.personalityType}` : "",
      self.personalitySummary ? `自分の性格総括: ${self.personalitySummary}` : "",
      self.notes ? `自分メモ: ${self.notes}` : "",
    ].filter(Boolean);
    const lines = [
      "人物・関係メモ:",
      "登録情報を聞かれたら、このメモを根拠に答える。登録されていない情報は推測せず、未登録と答える。",
      ...selfLines,
      ...persons.slice(0, 30).flatMap((person, index) => ["", personContextLine(person, index)]),
    ].filter((line) => line !== null && line !== undefined);
    return `\n\n${lines.join("\n")}`;
  }

  function relationshipMapModel(selfProfile, people = []) {
    const self = normalizeSelfProfile(selfProfile);
    const persons = (Array.isArray(people) ? people : []).map(normalizePerson);
    return {
      center: { id: "self", label: self.displayName || "自分", personalityType: self.personalityType },
      nodes: persons.map((person) => ({
        id: person.id,
        label: person.name,
        relation: relationDetailLabel(person.relationDetail) || categoryLabel(person.relationshipCategory),
        category: person.relationshipCategory,
        personalityType: person.personalityType,
        compatibility: relationshipCompatibility(self, person),
      })),
    };
  }

  function compatibilitySortMetric(node, sortKey = "total") {
    if (sortKey === "total") {
      return {
        label: "総合",
        mark: node.compatibility?.mark || compatibilityMark(node.compatibility?.grade),
        score: compatibilityScore(node.compatibility),
      };
    }
    const item = node.compatibility?.items?.find((entry) => entry.key === sortKey);
    return {
      label: item?.label || compatibilitySortOption(sortKey).label,
      mark: item?.mark || compatibilityMark(item?.grade),
      score: compatibilityScore(item),
    };
  }

  function relationshipRankingModel(selfProfile, people = [], sortKey = "total") {
    const option = compatibilitySortOption(sortKey);
    const model = relationshipMapModel(selfProfile, people);
    const rankedNodes = model.nodes
      .map((node, index) => {
        const metric = compatibilitySortMetric(node, option.id);
        return {
          ...node,
          sortKey: option.id,
          sortLabel: metric.label,
          sortMark: metric.mark,
          sortScore: metric.score,
          originalIndex: index,
        };
      })
      .sort((a, b) => {
        const aScore = typeof a.sortScore === "number" ? a.sortScore : -1;
        const bScore = typeof b.sortScore === "number" ? b.sortScore : -1;
        if (bScore !== aScore) return bScore - aScore;
        return a.originalIndex - b.originalIndex;
      })
      .map((node, index) => ({ ...node, rank: index + 1 }));
    return { ...model, sort: option, nodes: rankedNodes };
  }

  window.GEMMA_PERSON_RELATIONSHIP = {
    STORAGE_KEY,
    SELF_STORAGE_KEY,
    relationshipCategories,
    relationshipDetails,
    categoryLabel,
    relationDetailLabel,
    genderOptions: () => optionList(GENDERS),
    bloodTypeOptions: () => optionList(BLOOD_TYPES),
    personalityTypes: personalityTypeOptions,
    compatibilitySortOptions,
    personalityCompatibility,
    relationshipCompatibility,
    biorhythmSelfModel,
    calculateAge,
    normalizePerson,
    normalizeSelfProfile,
    selfPersonalitySummary,
    loadPeople,
    savePeople,
    loadSelfProfile,
    saveSelfProfile,
    upsertPerson,
    deletePerson,
    buildRecipientContextPrompt,
    buildPeopleContextPrompt,
    relationshipMapModel,
    relationshipRankingModel,
  };
})();
