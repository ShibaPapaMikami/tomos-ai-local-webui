const fs = require("node:fs");
const assert = require("node:assert/strict");

const index = fs.readFileSync("web/index.html", "utf8");
assert.match(index, /rel="manifest" href="\/manifest\.webmanifest"/);
assert.match(index, /name="theme-color"/);
assert.match(index, /apple-mobile-web-app-capable/);
assert.match(index, /src="\/pwa\.js\?v=0\.8\.196"/);

const manifest = JSON.parse(fs.readFileSync("web/manifest.webmanifest", "utf8"));
assert.equal(manifest.name, "Gemma 4 12B");
assert.equal(manifest.display, "standalone");
assert.equal(manifest.start_url, "/mobile.html");
assert.ok(manifest.icons.some((icon) => icon.src === "/icons/icon-192.png" && icon.sizes === "192x192"));
assert.ok(manifest.icons.some((icon) => icon.src === "/icons/icon-512.png" && icon.sizes === "512x512"));

[
  "web/pwa.js",
  "web/sw.js",
  "web/offline.html",
  "web/mobile.html",
  "web/mobile-standalone.js",
  "web/icons/icon.svg",
  "web/icons/icon-192.png",
  "web/icons/icon-512.png",
  "web/apple-touch-icon.png",
  "web/apple-touch-icon-precomposed.png",
  "scripts/start-mobile-preview.sh",
  "scripts/start-mobile-sync.sh",
].forEach((path) => {
  assert.ok(fs.existsSync(path), `${path} should exist`);
});

const sw = fs.readFileSync("web/sw.js", "utf8");
assert.match(sw, /offline\.html/);
assert.match(sw, /mobile\.html/);
assert.match(sw, /manifest\.webmanifest/);

const mobileHtml = fs.readFileSync("web/mobile.html", "utf8");
assert.match(mobileHtml, /id="mobile-chat-input"/);
assert.match(mobileHtml, /id="mobile-chat-send"/);
assert.match(mobileHtml, /id="mobile-chat-list"/);
assert.match(mobileHtml, /id="mobile-pc-host"/);
assert.match(mobileHtml, /id="mobile-pc-code"/);
assert.match(mobileHtml, /id="mobile-pc-save"/);
assert.match(mobileHtml, /id="mobile-pc-status"/);
assert.match(mobileHtml, /id="mobile-chat-export"/);
assert.match(mobileHtml, /id="mobile-chat-send-pc"/);
assert.match(mobileHtml, /id="mobile-chat-mark-imported"/);
assert.match(mobileHtml, /id="mobile-chat-clear"/);
assert.match(mobileHtml, /id="mobile-import-summary"/);
assert.match(mobileHtml, /id="mobile-chat-export-output"/);
assert.match(mobileHtml, /src="\/mobile-standalone\.js\?v=0\.8\.196"/);

const mobileJs = fs.readFileSync("web/mobile-standalone.js", "utf8");
assert.match(mobileJs, /gemma4\.mobileChat/);
assert.match(mobileJs, /gemma4\.mobilePcConnection/);
assert.match(mobileJs, /savePcConnection/);
assert.match(mobileJs, /normalizePcHost/);
assert.match(mobileJs, /applyConnectionParams/);
assert.match(mobileJs, /pairingCode/);
assert.match(mobileJs, /params\.get\("c"\)/);
assert.match(mobileJs, /window\.location\.origin/);
assert.match(mobileJs, /QRから接続先を保存しました/);
assert.match(mobileJs, /接続先を保存しました/);
assert.match(mobileJs, /sendChatToPc/);
assert.match(mobileJs, /\/api\/mobile\/import-chat/);
assert.match(mobileJs, /gemma4\.mobileNotes/);
assert.match(mobileJs, /detectBrowserAiSupport/);
assert.match(mobileJs, /generateAssistantReply/);
assert.match(mobileJs, /LanguageModel/);
assert.match(mobileJs, /ai\.languageModel/);
assert.match(mobileJs, /gemma4\.mobileAiMode/);
assert.match(mobileJs, /exportPayload/);
assert.match(mobileJs, /gemma4-mobile-chat/);
assert.match(mobileJs, /mobileImportSummary/);
assert.match(mobileJs, /markMessagesImported/);
assert.match(mobileJs, /clearMessages/);
assert.match(mobileJs, /role:\s*"user"/);
assert.match(mobileJs, /role:\s*"assistant"/);
assert.match(mobileJs, /localStorage\.setItem/);

const mobilePreviewScript = fs.readFileSync("scripts/start-mobile-preview.sh", "utf8");
assert.match(mobilePreviewScript, /--host 0\.0\.0\.0/);
assert.match(mobilePreviewScript, /--static-only/);

const mobileSyncScript = fs.readFileSync("scripts/start-mobile-sync.sh", "utf8");
assert.match(mobileSyncScript, /--host 0\.0\.0\.0/);
assert.match(mobileSyncScript, /--mobile-sync-only/);

console.log("pwa asset tests passed");
