const fs = require("node:fs");
const assert = require("node:assert/strict");

const css = fs.readFileSync("web/styles.css", "utf8");

function mobileRule(selector) {
  const mediaStart = css.indexOf("@media (max-width: 760px)");
  assert.notEqual(mediaStart, -1, "mobile media query should exist");
  const mobileCss = css.slice(mediaStart);
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const blocks = [...mobileCss.matchAll(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`, "g"))]
    .map((match) => match[1]);
  assert.ok(blocks.length > 0, `${selector} should have a mobile rule`);
  return blocks.join("\n");
}

const sidebarRule = mobileRule(".sidebar");
assert.match(sidebarRule, /position:\s*fixed;/, "mobile sidebar should behave as a drawer");
assert.match(sidebarRule, /width:\s*min\(286px,\s*86vw\);/, "mobile sidebar should fit narrow screens");

const topbarRule = mobileRule(".topbar");
assert.match(topbarRule, /grid-template-columns:\s*auto minmax\(0,\s*1fr\) auto;/, "mobile topbar should keep controls from squeezing title text");

const composerRule = mobileRule(".composer");
assert.match(composerRule, /position:\s*sticky;/, "mobile composer should stay pinned to the viewport bottom");
assert.match(composerRule, /bottom:\s*0;/, "mobile composer should be anchored to the bottom");
assert.match(composerRule, /padding-bottom:\s*calc\(10px \+ env\(safe-area-inset-bottom,\s*0px\)\);/, "mobile composer should account for iPhone safe area");

const composerBoxRule = mobileRule(".composer-box");
assert.match(composerBoxRule, /grid-template-columns:\s*auto minmax\(0,\s*1fr\) auto auto;/, "mobile composer controls should fit four compact columns");
assert.match(composerBoxRule, /"attach mode voice send"/, "mobile composer should hide the wide model selector from the main row");

console.log("mobile css tests passed");
