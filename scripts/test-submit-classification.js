const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console };
vm.createContext(context);

for (const file of [
  "web/translation.js",
  "web/local-tools.js",
  "web/weather.js",
  "web/image-tools.js",
  "web/workspace.js",
  "web/router.js",
]) {
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
}

const { classifySubmitIntent } = context.window.GEMMA_ROUTER;
const { isTranslationRequest } = context.window.GEMMA_TRANSLATION;
const { isLocalDateTimeRequest } = context.window.GEMMA_LOCAL_TOOLS;
const { isWeatherRequest } = context.window.GEMMA_WEATHER;
const { isImageGenerationRequest } = context.window.GEMMA_IMAGE_TOOLS;
const {
  inferSimpleTextSave,
  isSaveCommand,
} = context.window.GEMMA_WORKSPACE;
const appSource = fs.readFileSync("web/app.js", "utf8");
assert.match(
  appSource,
  /if \(hasSelectedNoteArticlePack\(\) && !isTranslationRequest\(text\)\) \{\s*sendMessage\(text\);\s*return;/,
);

function workspaceBuildRequest(text) {
  if (isTranslationRequest(text)) return false;
  if (workspaceLookupRequest(text)) return false;
  return /テトリス|ゲーム|サイト|アプリ|ページ|ツール|作って|つくって|作成|生成|構築|実装|修正|変更|保存|ファイル|html|css|javascript|コード|program|app|game|build|create|implement/i.test(text);
}

function workspaceLookupRequest(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return false;
  return /(ファイル|フォルダ|フォルダー|中身|どこ|場所|検索|探|含ま|書か|記載|契約書|請求書|仕様書|見積書|領収書|議事録|folder|file|where|search|find|contain|which|contract|invoice|spec|receipt|minutes)/i.test(normalized)
    && /(どこ|場所|ある|あります|入って|中身|検索|探|教えて|見つけ|含ま|書か|記載|where|search|find|contain|which)/i.test(normalized)
    && !/(保存|作って|つくって|作成|生成|構築|実装|修正|変更|write|save|create|build|implement)/i.test(normalized);
}

function classify(text, { hasImages = false, hasWorkspace = true, hasActiveSession = true, notePackSelected = false } = {}) {
  if (notePackSelected && !isTranslationRequest(text)) return "chat";
  return classifySubmitIntent({
    text,
    hasImages,
    isLocalUtilityRequest: isLocalDateTimeRequest,
    isWeatherRequest,
    isTranslationRequest,
    isImageGenerationRequest,
    isSimpleTextSaveRequest: (value) => Boolean(inferSimpleTextSave({ text: value, hasWorkspace })),
    isSaveCommandRequest: (value) => Boolean(hasActiveSession && hasWorkspace && isSaveCommand(value)),
    isWorkspaceBuildRequest: workspaceBuildRequest,
  });
}

assert.equal(classify("三上昌史についてというテキストファイルをtestフォルダに保存して"), "simple-save");
assert.equal(classify("hello.txtにhelloと記載して保存して"), "simple-save");
assert.equal(classify("フォルダー内にシンプルなWebテトリスを作って"), "workspace-build");
assert.equal(classify("gundamファイルはどこ？"), "chat");
assert.equal(classify("gundamはどのファイルにある？"), "chat");
assert.equal(classify("契約書を探して"), "chat");
assert.equal(classify("請求書はどこ？"), "chat");
assert.equal(classify("翻訳して\nhello"), "translation");
assert.equal(classify("日本語にやくして\nHello"), "translation");
assert.equal(classify("今日の新潟市の天気は？"), "weather");
assert.equal(classify("赤いリンゴの画像を生成して"), "image");
assert.equal(classify("いま何時？"), "local");
assert.equal(classify("何時から何時まで？"), "chat");
assert.equal(classify("画像を説明して", { hasImages: true }), "chat");
assert.equal(classify(
  `長文のnote記事を変換して\n${"本文です。".repeat(300)}\nファイルに同じ行と記載して保存します。`,
  { notePackSelected: true },
), "chat");

console.log("submit classification tests passed");
