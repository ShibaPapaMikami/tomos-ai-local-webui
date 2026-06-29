const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = {
  window: {},
  document: { createElement: () => ({ click() {}, remove() {} }), body: { append() {} } },
  URL: { createObjectURL: () => "", revokeObjectURL: () => {} },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/utils.js", "utf8"), context, { filename: "web/utils.js" });

const { normalizeJapaneseSpacing } = context.window.GEMMA_UTILS;

assert.equal(
  normalizeJapaneseSpacing("お守りの デザインと 販売ページの案です。こちらで最適な金額を検討し、 改めて共有します。"),
  "お守りのデザインと販売ページの案です。こちらで最適な金額を検討し、改めて共有します。",
);
assert.equal(
  normalizeJapaneseSpacing("URL: https://example.com/a b と version 1.2 は残す"),
  "URL: https://example.com/a b と version 1.2 は残す",
);
assert.equal(
  normalizeJapaneseSpacing("```js\nconst name = \"お守りの デザイン\";\n```\n本文は 社外向けです。"),
  "```js\nconst name = \"お守りの デザイン\";\n```\n本文は社外向けです。",
);
assert.equal(
  normalizeJapaneseSpacing("| 項目 | 内容 |\n| お守りの デザイン | OK |\n本文の 空白"),
  "| 項目 | 内容 |\n| お守りの デザイン | OK |\n本文の空白",
);

console.log("text format tests passed");
