(() => {
  const STROKES = {
    "一": 1, "乙": 1, "乃": 2, "二": 2, "人": 2, "入": 2, "八": 2, "九": 2, "十": 2, "七": 2,
    "三": 3, "上": 3, "下": 3, "大": 3, "小": 3, "子": 3, "山": 3, "川": 3, "土": 3,
    "千": 3, "久": 3, "丸": 3, "工": 3, "口": 3, "夕": 3, "女": 3, "也": 3, "々": 3,
    "中": 4, "水": 4, "木": 4, "火": 4, "月": 4, "日": 4, "文": 4, "方": 4,
    "井": 4, "今": 4, "元": 4, "内": 4, "円": 4, "太": 4, "友": 4, "仁": 4, "之": 4, "公": 4,
    "田": 5, "石": 5, "本": 5, "正": 5, "生": 5, "白": 5, "平": 5, "央": 5,
    "加": 5, "弘": 5, "司": 5, "未": 5, "由": 5, "世": 5, "市": 5, "北": 5, "史": 5, "広": 5,
    "伊": 6, "吉": 6, "西": 6, "安": 6, "光": 6, "成": 6, "早": 6, "朱": 6,
    "宇": 6, "江": 6, "池": 6, "竹": 6, "羽": 6, "百": 6, "有": 6, "守": 6, "圭": 6, "多": 6,
    "佐": 7, "花": 7, "村": 7, "杉": 7, "志": 7, "里": 7, "良": 7, "利": 7,
    "秀": 7, "宏": 7, "希": 7, "杏": 7, "那": 7, "佑": 7, "孝": 7, "克": 7, "妙": 7, "伯": 7,
    "林": 8, "松": 8, "金": 8, "長": 8, "岡": 8, "和": 8, "明": 8, "幸": 8,
    "英": 8, "佳": 8, "奈": 8, "知": 8, "直": 8, "典": 8, "季": 8, "昌": 8, "枝": 8, "宗": 8,
    "祝": 9, "南": 9, "前": 9, "星": 9, "美": 9, "音": 9, "香": 9, "亮": 9,
    "昭": 9, "俊": 9, "紀": 9, "則": 9, "祐": 9, "春": 9, "信": 9, "重": 9, "亮": 9,
    "高": 10, "原": 10, "島": 10, "宮": 10, "真": 10, "桃": 10, "夏": 10, "晃": 10,
    "哲": 10, "恵": 10, "倫": 10, "剛": 10, "修": 10, "浩": 10, "華": 10, "莉": 10, "紗": 10,
    "清": 11, "野": 11, "梅": 11, "彩": 11, "章": 11, "健": 11, "康": 11, "理": 11,
    "啓": 11, "悠": 11, "菜": 11, "隆": 11, "望": 11, "麻": 11, "梨": 11, "崇": 11, "隆": 11,
    "渡": 12, "森": 12, "朝": 12, "陽": 12, "結": 12, "貴": 12, "智": 12, "翔": 12,
    "雄": 12, "裕": 12, "絵": 12, "順": 12, "晶": 12, "晴": 12, "喜": 12, "勝": 12, "揚": 12,
    "鈴": 13, "園": 13, "愛": 13, "聖": 13, "新": 13, "義": 13, "稔": 13, "靖": 13,
    "誠": 13, "資": 13, "豊": 13, "楓": 13, "瑛": 13, "路": 13, "慎": 13, "誉": 13, "詩": 13,
    "遠": 14, "関": 14, "徳": 14, "輔": 14, "寛": 14, "綾": 14, "彰": 14, "静": 14,
    "緒": 14, "豪": 14, "慶": 15, "横": 15, "樹": 16, "橋": 16, "優": 17, "藤": 18,
    "麗": 19, "瀬": 19, "鶴": 21, "響": 22, "議": 20, "護": 20,
  };
  const KANA_STROKES = Object.fromEntries([
    ..."あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん",
    ..."アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン",
  ].map((char) => [char, 2]));
  const GOOD_NUMBERS = new Set([1, 3, 5, 6, 7, 8, 11, 13, 15, 16, 17, 18, 21, 23, 24, 25, 29, 31, 32, 33, 35, 37, 39, 41, 45, 47, 48, 52, 57, 61, 63, 65, 67, 68, 81]);

  const text = (value) => String(value || "").trim();
  const chars = (value) => [...text(value).replace(/\s+/g, "")];
  const charStroke = (char) => STROKES[char] || KANA_STROKES[char] || null;

  function splitName(input = {}) {
    let lastName = text(input.lastName);
    let firstName = text(input.firstName);
    const parts = text(input.name || input.displayName || input.nickname).split(/\s+/).filter(Boolean);
    if (lastName && firstName) return { lastName, firstName };
    if (!lastName && !firstName && parts.length >= 2) return { lastName: parts[0], firstName: parts.slice(1).join("") };
    if (!lastName && firstName && parts.length >= 2) lastName = parts[0];
    if (lastName && !firstName && parts.length >= 2) firstName = parts.slice(1).join("");
    if (lastName || firstName) return { lastName, firstName };
    if (parts.length >= 2) return { lastName: parts[0], firstName: parts.slice(1).join("") };
    return { lastName: "", firstName: parts[0] || "" };
  }

  function strokeTotal(value) {
    const unknown = [];
    let total = 0;
    for (const char of chars(value)) {
      const stroke = charStroke(char);
      if (stroke === null) {
        unknown.push(char);
      } else {
        total += stroke;
      }
    }
    return { total, unknown };
  }

  function gradeNumber(value) {
    if (!value) return { grade: "-", title: "未設定", score: null };
    if (GOOD_NUMBERS.has(value)) return { grade: "◎", title: "吉数", score: 2 };
    if (value % 2 === 1) return { grade: "○", title: "中庸", score: 1 };
    return { grade: "△", title: "注意", score: 0 };
  }

  function calculateFiveGrids(input = {}) {
    const { lastName, firstName } = splitName(input);
    const familyChars = chars(lastName);
    const givenChars = chars(firstName);
    const family = strokeTotal(lastName);
    const given = strokeTotal(firstName);
    const unknownChars = Array.from(new Set([...family.unknown, ...given.unknown]));
    const nameOnly = !familyChars.length && givenChars.length && !unknownChars.length;
    if (nameOnly) {
      const value = given.total;
      return {
        ok: true,
        partial: true,
        lastName,
        firstName,
        grids: { name: value, total: value },
        items: [{ key: "name", label: "名前", value, ...gradeNumber(value) }],
        score: gradeNumber(value).score ?? 0,
        unknownChars: [],
      };
    }
    if (!familyChars.length || !givenChars.length || unknownChars.length) {
      return {
        ok: false,
        lastName,
        firstName,
        unknownChars,
        error: !familyChars.length || !givenChars.length ? "姓と名が必要です。" : "未登録文字があります。",
      };
    }
    const lastFamily = charStroke(familyChars[familyChars.length - 1]) || 0;
    const firstGiven = charStroke(givenChars[0]) || 0;
    const phantomFamily = familyChars.length === 1 ? 1 : 0;
    const phantomGiven = givenChars.length === 1 ? 1 : 0;
    const grids = {
      heavenly: family.total + phantomFamily,
      personality: lastFamily + firstGiven,
      earthly: given.total + phantomGiven,
      outer: family.total + given.total - (lastFamily + firstGiven) + phantomFamily + phantomGiven,
      total: family.total + given.total,
    };
    const items = [
      { key: "heavenly", label: "天格", value: grids.heavenly },
      { key: "personality", label: "人格", value: grids.personality },
      { key: "earthly", label: "地格", value: grids.earthly },
      { key: "outer", label: "外格", value: grids.outer },
      { key: "total", label: "総格", value: grids.total },
    ].map((item) => ({ ...item, ...gradeNumber(item.value) }));
    const scores = items.map((item) => item.score).filter((score) => score !== null);
    const score = scores.reduce((sum, value) => sum + value, 0) / scores.length;
    return { ok: true, lastName, firstName, grids, items, score, unknownChars: [] };
  }

  function compareFiveGrids(selfInput = {}, otherInput = {}) {
    const self = calculateFiveGrids(selfInput);
    const other = calculateFiveGrids(otherInput);
    if (!self.ok || !other.ok) {
      const unknown = Array.from(new Set([...(self.unknownChars || []), ...(other.unknownChars || [])]));
      return {
        ok: false,
        grade: "-",
        title: "判定保留",
        detail: unknown.length ? `未登録文字: ${unknown.join("、")}` : "姓と名を分けて入れると五格を計算できます。",
        score: null,
        self,
        other,
      };
    }
    if (self.partial || other.partial) {
      const selfTotal = self.grids.total || self.grids.name || 0;
      const otherTotal = other.grids.total || other.grids.name || 0;
      const diff = Math.abs((selfTotal % 9) - (otherTotal % 9));
      if (diff <= 1) {
        return { ok: true, partial: true, grade: "○", title: "名前全体は近い", detail: `名前全体参考: ${selfTotal}画 / ${otherTotal}画`, score: 1, self, other };
      }
      return { ok: true, partial: true, grade: "△", title: "名前全体に差あり", detail: `名前全体参考: ${selfTotal}画 / ${otherTotal}画`, score: 0, self, other };
    }
    const closeItems = self.items.filter((item) => {
      const otherItem = other.items.find((candidate) => candidate.key === item.key);
      return otherItem && Math.abs(item.value - otherItem.value) <= 3;
    });
    const closeLabels = closeItems.map((item) => item.label).join("、");
    const detail = closeItems.length
      ? `近い格: ${closeLabels}`
      : "近い格なし。五格だけで相性を決めず、MBTIや関係メモも見てください。";
    if (closeItems.length >= 3) {
      return { ok: true, grade: "◎", title: "五格の接点が多い", detail, score: 2, self, other };
    }
    if (closeItems.length >= 1) {
      return { ok: true, grade: "○", title: "五格に一部接点", detail, score: 1, self, other };
    }
    return { ok: true, grade: "△", title: "五格の距離あり", detail, score: 0, self, other };
  }

  const api = {
    STROKES,
    charStroke,
    strokeTotal,
    calculateFiveGrids,
    compareFiveGrids,
  };
  globalThis.TOMOS_NAME_FORTUNE = api;
  if (globalThis.window) globalThis.window.TOMOS_NAME_FORTUNE = api;
})();
