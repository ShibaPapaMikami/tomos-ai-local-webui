const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const storage = new Map();
const context = {
  crypto: { randomUUID: () => "uuid-test" },
  localStorage: {
    getItem(key) {
      return storage.has(key) ? storage.get(key) : null;
    },
    setItem(key, value) {
      storage.set(key, String(value));
    },
  },
  window: {},
};

vm.createContext(context);
vm.runInContext(fs.readFileSync("web/character.js", "utf8"), context, { filename: "web/character.js" });

const {
  addMemory,
  buildCharacterSystemPrompt,
  buildMemorySystemPrompt,
  classifyMemory,
  deleteMemory,
  loadCharacter,
  loadMemorySets,
  memoryCandidateFromText,
  normalizeCharacter,
  saveCharacter,
  updateMemory,
} = context.window.GEMMA_CHARACTER;

assert.equal(loadCharacter().name, "Gemma");
const character = saveCharacter({
  name: "ミカ",
  userName: "三上さん",
  selfName: "私",
  gender: "female",
  personality: "やさしく短く答える",
  tonePreset: "teacher",
  memoryMode: "suggest",
});
assert.equal(character.name, "ミカ");
assert.equal(character.userName, "三上さん");
assert.equal(character.selfName, "私");
assert.equal(character.gender, "female");
assert.equal(normalizeCharacter({ memoryMode: "auto" }).memoryMode, "auto");
assert.equal(normalizeCharacter({ gender: "unknown" }).gender, "unspecified");
assert.match(buildCharacterSystemPrompt(character), /あなたの表示名は「ミカ」/);
assert.match(buildCharacterSystemPrompt(character), /ユーザーの呼び方は「三上さん」/);
assert.match(buildCharacterSystemPrompt(character), /自分自身を指すときは「私」/);
assert.match(buildCharacterSystemPrompt(character), /性別設定は女性/);
assert.match(buildCharacterSystemPrompt(character), /正確性・安全性/);

let sets = loadMemorySets(character);
assert.equal(sets.length, 1);
sets = addMemory({
  memorySets: sets,
  character,
  text: "ユーザーは短い説明を好む",
  createId: () => "memory-1",
  nowIso: () => "2026-06-19T00:00:00.000Z",
});
assert.equal(sets[0].memories.length, 1);
assert.match(buildMemorySystemPrompt(sets[0]), /ユーザーは短い説明を好む/);
sets = addMemory({
  memorySets: sets,
  character,
  text: "ユーザーは短い説明を好む",
  createId: () => "memory-duplicate",
  nowIso: () => "2026-06-19T00:30:00.000Z",
});
assert.equal(sets[0].memories.length, 1);
sets = addMemory({
  memorySets: sets,
  character,
  text: "ユーザーはまさふみはメロンとマンゴーが好き",
  createId: () => "memory-normalized",
  nowIso: () => "2026-06-19T00:40:00.000Z",
});
assert.equal(sets[0].memories[1].text, "まさふみはメロンとマンゴーが好き");

sets = updateMemory({
  memorySets: sets,
  memorySetId: sets[0].id,
  memoryId: "memory-1",
  text: "ユーザーは例つきの短い説明を好む",
  nowIso: () => "2026-06-19T01:00:00.000Z",
});
assert.equal(sets[0].memories[0].text, "ユーザーは例つきの短い説明を好む");

sets = deleteMemory({ memorySets: sets, memorySetId: sets[0].id, memoryId: "memory-1" });
assert.equal(sets[0].memories.length, 1);
assert.equal(sets[0].memories[0].id, "memory-normalized");

assert.equal(memoryCandidateFromText("これを覚えて: ユーザーの名前は三上").text, "ユーザーの名前は三上");
assert.equal(memoryCandidateFromText("ガンダムが好き", { mode: "auto" }).text, "ユーザーはガンダムが好き");
assert.equal(memoryCandidateFromText("まさふみはメロンとマンゴーが好きだよ", { mode: "auto" }).text, "まさふみはメロンとマンゴーが好き");
assert.equal(memoryCandidateFromText("ガンダムが好き", { mode: "suggest" }), null);
assert.equal(memoryCandidateFromText("APIキーはabcを覚えて"), null);
assert.equal(memoryCandidateFromText("今日の天気は？"), null);
assert.equal(classifyMemory({ text: "ユーザーの名前は三上" }), "profile");
assert.equal(classifyMemory({ text: "ガンダムが好き" }), "preference");
assert.equal(classifyMemory({ text: "Python課題を進めている" }), "study");
assert.equal(classifyMemory({ text: "高速モードとWeb検索をよく使う" }), "settings");
assert.equal(classifyMemory({ text: "分類よりタグを優先", tags: ["勉強"] }), "study");

console.log("character helper tests passed");
