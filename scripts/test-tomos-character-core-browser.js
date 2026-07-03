const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = {
  crypto: { randomUUID: () => "uuid-test" },
  localStorage: {
    getItem() {
      return null;
    },
    setItem() {},
  },
  window: {},
};

vm.createContext(context);
vm.runInContext(fs.readFileSync("web/tomos-character-core.js", "utf8"), context, {
  filename: "web/tomos-character-core.js",
});
vm.runInContext(fs.readFileSync("web/character-core-adapter.js", "utf8"), context, {
  filename: "web/character-core-adapter.js",
});
vm.runInContext(fs.readFileSync("web/character.js", "utf8"), context, { filename: "web/character.js" });

assert.equal(typeof context.window.TOMOS_CHARACTER_CORE.buildRuntimePrompt, "function");
assert.ok(context.window.TOMOS_CHARACTER_CORE.characterProfileJsonSchema);
assert.ok(context.window.TOMOS_CHARACTER_CORE.runtimePromptInputJsonSchema);

const prompt = context.window.GEMMA_CHARACTER.buildCharacterSystemPrompt({
  id: "shibapapa",
  name: "しばぱぱ",
  userName: "まさふみ",
  selfName: "ぼく",
  personality: "やさしく短く返す",
  tonePreset: "friendly",
}, {
  conversationState: { situation: "daily-chat", emotion: "neutral", relationshipStage: "trusted" },
  recentMessages: [{ role: "user", content: "おはよ" }],
});

assert.match(prompt, /あなたの表示名は「しばぱぱ」/);
assert.match(prompt, /character-core追加指示/);
assert.match(prompt, /# Character Runtime Prompt/);
assert.match(prompt, /名前: しばぱぱ/);
assert.match(prompt, /一人称: ぼく/);
assert.match(prompt, /ユーザー発話: おはよ/);

const warnings = context.window.TOMOS_CHARACTER_CORE.validateCharacterVoice({
  id: "shibapapa",
  displayName: "しばぱぱ",
  preferredCallName: "まさふみ",
  voice: {
    firstPerson: "ぼく",
    speechStyle: "friendly",
    catchphrases: ["だよ"],
    maxCatchphraseUses: 1,
    ngActingRules: ["人間です"],
  },
}, {
  generatedText: "私は人間です。だよ。だよ。",
  recentLines: [],
});

assert.ok(warnings.some((warning) => warning.code === "VOICE_FIRST_PERSON_MISMATCH"));
assert.ok(warnings.some((warning) => warning.code === "CATCHPHRASE_OVERUSE"));
assert.ok(warnings.some((warning) => warning.code === "NG_ACTING_RULE_HIT"));

console.log("tomos character core browser tests passed");
