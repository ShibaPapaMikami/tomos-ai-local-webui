const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const storage = new Map();
const context = {
  window: {},
  localStorage: {
    getItem: (key) => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, String(value)),
  },
  crypto: { randomUUID: () => "person-fixed-id" },
  Date,
  console,
};

vm.createContext(context);
vm.runInContext(fs.readFileSync("web/person-name-fortune.js", "utf8"), context, { filename: "web/person-name-fortune.js" });
vm.runInContext(fs.readFileSync("web/person-relationship.js", "utf8"), context, { filename: "web/person-relationship.js" });

const fortuneApi = context.window.TOMOS_NAME_FORTUNE;
assert.ok(fortuneApi);
const fiveGrids = fortuneApi.calculateFiveGrids({ lastName: "三上", firstName: "まさふみ" });
assert.equal(fiveGrids.ok, true);
assert.equal(fiveGrids.grids.heavenly, 6);
assert.equal(fiveGrids.grids.total, 14);
assert.equal(fortuneApi.calculateFiveGrids({ lastName: "未知", firstName: "文字" }).ok, false);
const nameOnlyGrids = fortuneApi.calculateFiveGrids({ name: "まさきさん" });
assert.equal(nameOnlyGrids.ok, true);
assert.equal(nameOnlyGrids.partial, true);
assert.equal(fortuneApi.compareFiveGrids({ name: "マサフミ" }, { name: "まさきさん" }).ok, true);
const etokuGrids = fortuneApi.calculateFiveGrids({ lastName: "江徳", firstName: "智揚" });
assert.equal(etokuGrids.ok, true);
assert.equal(etokuGrids.grids.heavenly, 20);
assert.equal(etokuGrids.grids.total, 44);
const noCloseFiveGrids = fortuneApi.compareFiveGrids(
  { lastName: "三上", firstName: "まさふみ" },
  { lastName: "江徳", firstName: "智揚" },
);
assert.equal(noCloseFiveGrids.title, "五格の距離あり");
assert.doesNotMatch(noCloseFiveGrids.detail, /0\/5/);
assert.match(noCloseFiveGrids.detail, /近い格なし/);

const api = context.window.GEMMA_PERSON_RELATIONSHIP;
assert.ok(api);
const etokuKanaDisplay = api.relationshipCompatibility(
  { lastName: "三上", firstName: "まさふみ", displayName: "マサフミ", personalityType: "INTJ-A" },
  { lastName: "江徳", firstName: "智揚", displayName: "えのりさん", relationshipCategory: "work", relationDetail: "direct_report" },
);
assert.notEqual(etokuKanaDisplay.items.find((item) => item.label === "姓名判断 五格").title, "判定保留");
assert.match(etokuKanaDisplay.items.find((item) => item.label === "姓名判断 五格").detail, /TOMOS標準五格/);
assert.deepEqual(JSON.parse(JSON.stringify(api.relationshipCategories().map((item) => item.id))), ["friend", "romantic", "family", "work"]);
assert.ok(api.relationshipDetails("family").some((item) => item.id === "child"));
assert.ok(api.relationshipDetails("romantic").some((item) => item.id === "spouse"));
assert.ok(api.relationshipDetails("family").some((item) => item.id === "spouse"));
assert.ok(api.genderOptions().some((item) => item.id === "female"));
assert.ok(api.bloodTypeOptions().some((item) => item.id === "AB"));
assert.ok(api.personalityTypes().some((item) => item.id === "ENFP"));
assert.ok(api.personalityTypes().some((item) => item.id === "ENFJ-A"));
assert.ok(api.personalityTypes().some((item) => item.id === "ENFJ-T"));
assert.equal(api.personalityTypes().find((item) => item.id === "ENFJ-A").label, "ENFJ-A　主人公");
assert.equal(api.personalityTypes().find((item) => item.id === "INTJ-T").label, "INTJ-T　建築家");
const selfAutoSummary = api.selfPersonalitySummary({ personalityType: "ENFJ-A", birthdate: "1976-10-05" });
assert.match(selfAutoSummary, /ENFJ-A（主人公）/);
assert.match(selfAutoSummary, /相手の気持ちを見ながら場を整え/);
assert.match(selfAutoSummary, /天秤座/);
assert.match(selfAutoSummary, /基本傾向/);
assert.match(selfAutoSummary, /強み/);
assert.match(selfAutoSummary, /注意点/);
assert.match(selfAutoSummary, /返信支援での使い方/);
assert.doesNotMatch(selfAutoSummary, /ライフパス/);
assert.ok(selfAutoSummary.length > 220);
const intjEnfpCompatibility = api.personalityCompatibility("INTJ-A", "ENFP-T");
const intjIstjCompatibility = api.personalityCompatibility("INTJ-A", "ISTJ-A");
const intjEsfpCompatibility = api.personalityCompatibility("INTJ-A", "ESFP-A");
const enfjIsfjCompatibility = api.personalityCompatibility("ENFJ-A", "ISFJ");
const entpIsfjCompatibility = api.personalityCompatibility("ENTP", "ISFJ");
assert.equal(intjEnfpCompatibility.label, "相性: 理想的な補完");
assert.match(intjEnfpCompatibility.detail, /会話補助の参考/);
assert.match(intjEnfpCompatibility.detail, /発想と実行の役割分担/);
assert.match(intjEnfpCompatibility.detail, /相手に送る文面では/);
assert.match(intjEnfpCompatibility.detail, /\n判定のもと: 16タイプ分類の4指標、心理機能名、TOMOS独自の会話補助ルール/);
assert.doesNotMatch(intjEnfpCompatibility.detail, /INTJ: Ni\/Te|ENFP: Ne\/Fi|主機能|補助機能/);
assert.equal(enfjIsfjCompatibility.label, "相性: 支え合いやすい");
assert.match(enfjIsfjCompatibility.detail, /気持ちへの配慮が通じやすい/);
assert.equal(entpIsfjCompatibility.label, "相性: すれ違い注意");
assert.match(entpIsfjCompatibility.detail, /注意ペア/);
assert.doesNotMatch(api.personalityCompatibility("ENFJ-A", "ENFJ").detail, /ENFJ: Fe\/Ni|主機能|補助機能|劣等機能/);
assert.equal(api.personalityCompatibility("INTJ-A", "INTJ-T").label, "相性: 似ている");
assert.notEqual(intjEnfpCompatibility.label, intjIstjCompatibility.label);
assert.notEqual(intjEnfpCompatibility.detail, intjEsfpCompatibility.detail);
assert.equal(typeof intjEnfpCompatibility.score, "number");
assert.equal(api.personalityCompatibility("", "ENFP-T").label, "相性: MBTI未設定");
const fullCompatibility = api.relationshipCompatibility(
  { name: "三上 まさふみ", birthdate: "1980-01-01", personalityType: "INTJ-A" },
  { name: "佐藤 花子", relationshipCategory: "family", relationDetail: "child", birthdate: "2010-07-05", personalityType: "ENFP", notes: "家族向けに短く明るく返す" },
);
assert.equal(fullCompatibility.label, "総合相性: かなり良い");
assert.match(fullCompatibility.detail, /相性診断結果/);
assert.match(fullCompatibility.detail, /相性度: \d+点/);
assert.match(fullCompatibility.detail, /なぜ相性がいいか/);
assert.match(fullCompatibility.detail, /相手の性格: ENFP（運動家）/);
assert.match(fullCompatibility.detail, /可能性を広げ/);
assert.match(fullCompatibility.detail, /自分はINTJ-A（建築家）/);
assert.match(fullCompatibility.detail, /生年月日では/);
assert.match(fullCompatibility.detail, /山羊座/);
assert.match(fullCompatibility.detail, /蟹座/);
assert.match(fullCompatibility.detail, /ライフパス/);
assert.match(fullCompatibility.detail, /姓名判断では/);
assert.match(fullCompatibility.detail, /五格/);
assert.match(fullCompatibility.detail, /注意点/);
assert.match(fullCompatibility.detail, /相性を高めるポイント/);
assert.match(fullCompatibility.detail, /二人だけのメッセージ/);
assert.match(fullCompatibility.detail, /佐藤 花子さん/);
assert.doesNotMatch(fullCompatibility.detail, /アイデア、気持ち、会話の広がり|優先順位、段取り、実行手順/);
assert.doesNotMatch(fullCompatibility.detail, /^3項目から見た参考相性です。$/);
assert.deepEqual(
  JSON.parse(JSON.stringify(fullCompatibility.items.map((item) => item.label))),
  ["MBTI", "生年月日", "姓名判断 五格"],
);
const birthdateItem = fullCompatibility.items.find((item) => item.key === "birthdate");
assert.equal(birthdateItem.title, "星座・数秘の接点が多い");
assert.match(birthdateItem.detail, /太陽星座: 山羊座\(土・活動宮\) × 蟹座\(水・活動宮\)/);
assert.match(birthdateItem.detail, /ライフパス: 2 × 6/);
assert.match(birthdateItem.detail, /会話では、予定や決めごとは具体的に/);
assert.match(birthdateItem.detail, /\n判定のもと: 太陽星座の元素・活動分類、数秘術のライフパス、TOMOS独自の会話補助ルール/);
assert.doesNotMatch(birthdateItem.detail, /バイオリズム|身体23日|感情28日|知性33日|統計学/);
assert.match(fullCompatibility.items.find((item) => item.key === "strokes").detail, /\n判定のもと: 姓名、TOMOS標準五格。文化的な姓名判断の参考であり、相性を断定しません。/);
assert.equal(fullCompatibility.items.some((item) => item.key === "relationship"), false);
assert.equal(fullCompatibility.items.some((item) => item.key === "memo"), false);
assert.equal(api.calculateAge("2000-07-06", new Date("2026-07-06T00:00:00+09:00")), "26");

const selfBiorhythm = api.biorhythmSelfModel("1980-01-01", new Date("2026-07-06T00:00:00+09:00"));
assert.equal(selfBiorhythm.months.length, 5);
assert.equal(selfBiorhythm.years.length, 3);
assert.deepEqual(JSON.parse(JSON.stringify(selfBiorhythm.months.map((item) => item.label))), ["2026年5月", "2026年6月", "2026年7月", "2026年8月", "2026年9月"]);
assert.deepEqual(JSON.parse(JSON.stringify(selfBiorhythm.years.map((item) => item.label))), ["2025年", "2026年", "2027年"]);
assert.ok(selfBiorhythm.months.every((item) => ["種まき", "開花", "収穫", "休息"].includes(item.phase)));
assert.ok(selfBiorhythm.months.every((item) => item.categories.health && item.categories.work && item.categories.study && item.categories.love));
assert.match(selfBiorhythm.months[2].categories.health.label, /健康/);
assert.doesNotMatch(JSON.stringify(selfBiorhythm.months), /身体|感情|知性/);
assert.match(selfBiorhythm.source, /セルフチェック用の参考/);
assert.equal(api.biorhythmPairMonthlyModel, undefined);

const person = api.normalizePerson({
  lastName: "佐藤",
  firstName: "花子",
  nickname: "さと",
  relationshipCategory: "family",
  relationDetail: "child",
  birthdate: "2010-07-05",
  gender: "female",
  bloodType: "A",
  personalityType: "ENFP",
  personalityTypeSource: "user_reported",
  notes: "家族向けに短く明るく返す",
});

assert.equal(person.id, "person-fixed-id");
assert.equal(person.name, "佐藤 花子");
assert.equal(person.lastName, "佐藤");
assert.equal(person.firstName, "花子");
assert.equal(person.relationshipCategory, "family");
assert.equal(person.relationDetail, "child");
assert.equal(person.gender, "female");
assert.equal(person.bloodType, "A");
assert.equal(person.personalityTypeLabel, "MBTI: ENFP");
assert.equal(person.personalityTypeSource, "user_reported");

const saved = api.savePeople([person], context.localStorage);
assert.equal(saved.length, 1);
assert.equal(api.loadPeople(context.localStorage)[0].name, "佐藤 花子");

const prompt = api.buildRecipientContextPrompt(person);
assert.match(prompt, /送り先: 佐藤 花子/);
assert.match(prompt, /関係: 子供/);
assert.match(prompt, /自分とのメモ: 家族向けに短く明るく返す/);
assert.match(prompt, /MBTI参考: ENFP/);
assert.doesNotMatch(prompt, /血液型/);
assert.doesNotMatch(prompt, /A/);
const peopleContextPrompt = api.buildPeopleContextPrompt(
  { lastName: "三上", firstName: "まさふみ", nickname: "まさふみ", birthdate: "1980-01-01", personalityType: "INTJ-A", personalitySummary: "先を読んで準備するが、説明が短くなりやすい", notes: "短い説明を好む" },
  [person],
);
assert.match(peopleContextPrompt, /人物・関係メモ:/);
assert.match(peopleContextPrompt, /自分: 三上 まさふみ/);
assert.match(peopleContextPrompt, /自分の性格総括: 先を読んで準備するが、説明が短くなりやすい/);
assert.match(peopleContextPrompt, /自分の今月バイオリズム:/);
assert.match(peopleContextPrompt, /今日の運勢や今月の流れを聞かれたら、このバイオリズムを根拠に答える/);
assert.match(peopleContextPrompt, /健康:/);
assert.match(peopleContextPrompt, /仕事:/);
assert.match(peopleContextPrompt, /学業:/);
assert.match(peopleContextPrompt, /恋愛:/);
assert.match(peopleContextPrompt, /登録人物 1: 佐藤 花子/);
assert.match(peopleContextPrompt, /生年月日: 2010-07-05/);
assert.match(peopleContextPrompt, /MBTI: ENFP/);
assert.match(peopleContextPrompt, /自分とのメモ: 家族向けに短く明るく返す/);
assert.match(peopleContextPrompt, /登録情報を聞かれたら、このメモを根拠に答える/);

const recipient = api.normalizePerson({
  lastName: "田中",
  firstName: "太郎",
  relationshipCategory: "work",
  relationDetail: "client",
  likes: "結論から話すこと",
  conversationNotes: "敬語で、依頼内容を先に書く",
  relationshipMemo: "社外パートナー",
  age: "32",
  bloodType: "A",
});
const recipientPrompt = api.buildRecipientContextPrompt(recipient);
assert.match(recipientPrompt, /関係: 取引先/);
assert.match(recipientPrompt, /敬語で、依頼内容を先に書く/);
assert.doesNotMatch(recipientPrompt, /32/);
assert.doesNotMatch(recipientPrompt, /A/);

const selfProfile = api.saveSelfProfile({
  lastName: "三上",
  firstName: "まさふみ",
  birthdate: "1980-01-01",
  personalityType: "INTJ-A",
  notes: "短い説明を好む",
}, context.localStorage);
assert.equal(selfProfile.name, "三上 まさふみ");
assert.match(selfProfile.personalitySummary, /INTJ-A（建築家）/);
assert.equal(api.loadSelfProfile(context.localStorage).personalityType, "INTJ-A");
assert.match(api.loadSelfProfile(context.localStorage).personalitySummary, /先を読んで構造化/);
assert.doesNotMatch(api.loadSelfProfile(context.localStorage).personalitySummary, /ライフパス/);

const map = api.relationshipMapModel(selfProfile, [person, recipient]);
assert.equal(map.center.label, "三上 まさふみ");
assert.equal(map.nodes.length, 2);
assert.equal(map.nodes[0].relation, "子供");
assert.equal(map.nodes[0].compatibility.label, "総合相性: かなり良い");
assert.equal(map.nodes[0].compatibility.items.length, 3);
assert.deepEqual(
  JSON.parse(JSON.stringify(map.nodes[0].compatibility.items.map((item) => item.mark))),
  ["◎", "◎", "◯"],
);
assert.equal(map.nodes[0].compatibility.items[0].source, "自分: INTJ-A / 相手: ENFP");
assert.equal(map.nodes[0].compatibility.items[1].source, "自分: 1980-01-01 / 相手: 2010-07-05");
assert.equal(map.nodes[0].compatibility.items[2].source, "自分: 三上 まさふみ / 相手: 佐藤 花子");
assert.equal(map.nodes[0].biorhythm, undefined);
assert.equal(map.nodes[1].compatibility.items[0].title, "MBTI未設定");
assert.deepEqual(
  JSON.parse(JSON.stringify(api.compatibilitySortOptions().map((item) => item.id))),
  ["total", "mbti", "birthdate", "strokes"],
);
const totalRanking = api.relationshipRankingModel(selfProfile, [recipient, person], "total");
assert.deepEqual(JSON.parse(JSON.stringify(totalRanking.nodes.map((node) => node.rank))), [1, 2]);
assert.equal(totalRanking.nodes[0].label, "佐藤 花子");
assert.equal(totalRanking.nodes[0].sortLabel, "総合");
assert.equal(totalRanking.nodes[0].sortMark, "◎");
const mbtiRanking = api.relationshipRankingModel(selfProfile, [recipient, person], "mbti");
assert.equal(mbtiRanking.nodes[0].label, "佐藤 花子");
assert.equal(mbtiRanking.nodes[0].sortLabel, "MBTI");
assert.equal(mbtiRanking.nodes[0].sortMark, "◎");
assert.equal(mbtiRanking.nodes[1].sortMark, "✗");

const removed = api.deletePerson(saved, person.id);
assert.equal(removed.length, 0);

console.log("person relationship helper tests passed");
