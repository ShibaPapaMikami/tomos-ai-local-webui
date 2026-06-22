const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const source = fs.readFileSync("web/router.js", "utf8");
const context = { window: {}, console };
vm.createContext(context);
vm.runInContext(source, context, { filename: "web/router.js" });

const { classifySubmitIntent } = context.window.GEMMA_ROUTER;

function classify(text, overrides = {}) {
  return classifySubmitIntent({
    text,
    hasImages: false,
    isLocalUtilityRequest: () => false,
    isWeatherRequest: () => false,
    isTranslationRequest: () => false,
    isImageGenerationRequest: () => false,
    isSimpleTextSaveRequest: () => false,
    isSaveCommandRequest: () => false,
    isWorkspaceBuildRequest: () => false,
    ...overrides,
  });
}

assert.equal(
  classify("三上昌史についてというテキストファイルをtestフォルダに保存して", {
    isSimpleTextSaveRequest: () => true,
    isWorkspaceBuildRequest: () => true,
  }),
  "simple-save",
);

assert.equal(
  classify("翻訳して\nhello", {
    isTranslationRequest: () => true,
    isWorkspaceBuildRequest: () => true,
  }),
  "translation",
);

assert.equal(
  classify("赤いリンゴの画像を生成して", {
    isImageGenerationRequest: () => true,
    isWorkspaceBuildRequest: () => true,
  }),
  "image",
);

assert.equal(
  classify("フォルダー内にシンプルなWebテトリスを作って", {
    isWorkspaceBuildRequest: () => true,
  }),
  "workspace-build",
);

assert.equal(
  classify("何時から何時まで？", {
    isLocalUtilityRequest: () => true,
    isWeatherRequest: () => true,
  }),
  "local",
);

assert.equal(
  classify("今日の新潟市の天気は？", {
    isWeatherRequest: () => true,
    isWorkspaceBuildRequest: () => true,
  }),
  "weather",
);

assert.equal(
  classify("前のコードをindex.htmlとして保存して", {
    isSaveCommandRequest: () => true,
    isWorkspaceBuildRequest: () => true,
  }),
  "save-command",
);

assert.equal(
  classify("画像を説明して", {
    hasImages: true,
    isImageGenerationRequest: () => true,
  }),
  "chat",
);

console.log("router tests passed");
