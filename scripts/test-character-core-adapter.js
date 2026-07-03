const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

function createContext(withCore = true) {
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
  if (withCore) {
    context.window.TOMOS_CHARACTER_CORE = {
      buildRuntimePrompt(input) {
        assert.equal(input.character.displayName, "しばぱぱ");
        assert.ok(input.character.voice.firstPerson);
        assert.equal(input.context.situation, "daily-chat");
        assert.equal(input.context.emotion, "calm");
        assert.equal(input.context.relationshipStage, "trusted");
        return {
          text: "CORE_PROMPT_TEXT",
          sections: [{ id: "voice", text: "CORE_SECTION" }],
          warnings: [{ code: "prompt.too_long", severity: "warning" }],
        };
      },
      validateCharacterVoice(profile, options) {
        assert.equal(profile.displayName, "しばぱぱ");
        assert.ok(Array.isArray(options.recentLines));
        return [{ code: "voice.too_formal", severity: "info" }];
      },
      resolveReactionRule(profile, state) {
        assert.equal(profile.displayName, "しばぱぱ");
        assert.equal(state.situation, "daily-chat");
        assert.equal(state.emotion, "calm");
        assert.equal(state.relationshipStage, "trusted");
        return { id: "reaction-smile" };
      },
    };
  }
  vm.createContext(context);
  vm.runInContext(fs.readFileSync("web/character-core-adapter.js", "utf8"), context, {
    filename: "web/character-core-adapter.js",
  });
  vm.runInContext(fs.readFileSync("web/character.js", "utf8"), context, { filename: "web/character.js" });
  return context;
}

const coreContext = createContext(true);
const corePrompt = coreContext.window.GEMMA_CHARACTER.buildCharacterSystemPrompt({
  name: "しばぱぱ",
  userName: "まさふみ",
  selfName: "ぼく",
  personality: "やさしい",
}, {
  conversationState: {
    situation: "daily-chat",
    emotion: "calm",
    relationshipStage: "trusted",
  },
  recentMessages: [{ role: "user", content: "おはよ" }],
});
assert.match(corePrompt, /あなたの表示名は「しばぱぱ」/);
assert.match(corePrompt, /character-core追加指示/);
assert.match(corePrompt, /CORE_PROMPT_TEXT/);
const mapped = coreContext.window.TOMOS_CHARACTER_CORE_ADAPTER.buildRuntimePromptInput({
  character: { name: "しばぱぱ", userName: "まさふみ", selfName: "ぼく" },
  conversationState: { situation: "daily-chat", emotion: "calm", relationshipStage: "trusted" },
  recentMessages: [{ role: "user", content: "おはよ" }],
});
assert.equal(mapped.character.displayName, "しばぱぱ");
assert.equal(mapped.character.preferredCallName, "まさふみ");
assert.equal(mapped.character.voice.firstPerson, "ぼく");
assert.equal(mapped.context.situation, "daily-chat");
assert.ok(mapped.context.recentLines.some((line) => line.includes("おはよ")));

const addition = coreContext.window.TOMOS_CHARACTER_CORE_ADAPTER.buildRuntimePromptAddition({
  character: { name: "しばぱぱ" },
  conversationState: { situation: "daily-chat", emotion: "calm", relationshipStage: "trusted" },
});
assert.equal(addition.source, "character-core");
assert.equal(addition.sections[0].id, "voice");
assert.equal(addition.warnings.length, 2);
assert.equal(addition.reactionRule.id, "reaction-smile");
assert.equal(addition.input.character.displayName, "しばぱぱ");
assert.equal(addition.input.context.project, "TOMOS AI");

const fallbackContext = createContext(false);
const fallbackPrompt = fallbackContext.window.GEMMA_CHARACTER.buildCharacterSystemPrompt({ name: "しばぱぱ" });
assert.match(fallbackPrompt, /あなたの表示名は「しばぱぱ」/);
assert.doesNotMatch(fallbackPrompt, /character-core追加指示/);
assert.doesNotMatch(fallbackPrompt, /CORE_PROMPT_TEXT/);

console.log("character-core adapter tests passed");
