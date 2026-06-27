const fs = require("node:fs");
const assert = require("node:assert/strict");

const index = fs.readFileSync("web/index.html", "utf8");
const appJs = fs.readFileSync("web/app.js", "utf8");
assert.match(index, /rel="manifest" href="\/manifest\.webmanifest"/);
assert.match(index, /name="theme-color"/);
assert.match(index, /apple-mobile-web-app-capable/);
assert.match(index, /src="\/pwa\.js\?v=0\.8\.197-pwa1"/);
assert.match(index, /src="\/app\.js\?v=0\.8\.197-pwa1"/);
assert.match(appJs, /localStorage\.getItem\("gemma4\.theme"\) \|\| "light"/);
assert.match(appJs, /function openInitialManagementPanelFromUrl/);
assert.match(appJs, /window\.location\.pathname === "\/pc-mobile-connect"/);
assert.match(appJs, /panel !== "mobile-connect"/);
assert.match(appJs, /setSidebarSettingsMode\?\.\(\{ els, open: true \}\)/);
assert.doesNotMatch(appJs, /replaceState\(null, "", nextUrl\)/);

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
assert.match(sw, /mobile-chat-tools-1/);
assert.match(sw, /cache\.put\(event\.request/);

const mobileHtml = fs.readFileSync("web/mobile.html", "utf8");
assert.match(mobileHtml, /id="mobile-chat-input"/);
assert.match(mobileHtml, /id="mobile-chat-send"/);
assert.match(mobileHtml, /id="mobile-chat-list"/);
assert.match(mobileHtml, /id="mobile-desktop-notice"/);
assert.match(mobileHtml, /PC版のスマホ接続を開く/);
assert.match(mobileHtml, /\/pc-mobile-connect/);
assert.match(mobileHtml, /id="mobile-app-version"/);
assert.match(mobileHtml, /アプリ版 0\.8\.197/);
assert.match(mobileHtml, /id="mobile-ai-plan"/);
assert.match(mobileHtml, /id="mobile-ai-diagnostics"/);
assert.match(mobileHtml, /id="mobile-ai-candidates"/);
assert.match(mobileHtml, /id="mobile-pc-host"/);
assert.match(mobileHtml, /id="mobile-pc-code"/);
assert.match(mobileHtml, /id="mobile-pc-save"/);
assert.match(mobileHtml, /id="mobile-pc-status"/);
assert.match(mobileHtml, /connection-state/);
assert.match(mobileHtml, /id="mobile-chat-export"/);
assert.match(mobileHtml, /id="mobile-chat-send-pc"/);
assert.match(mobileHtml, /id="mobile-chat-mark-imported"/);
assert.match(mobileHtml, /id="mobile-chat-clear"/);
assert.match(mobileHtml, /id="mobile-import-summary"/);
assert.match(mobileHtml, /id="mobile-chat-export-output"/);
assert.match(mobileHtml, /src="\/pwa\.js\?v=0\.8\.197-pwa1"/);
assert.match(mobileHtml, /src="\/mobile-standalone\.js\?v=0\.8\.197-mobile1"/);

const offlineHtml = fs.readFileSync("web/offline.html", "utf8");
assert.match(offlineHtml, /PCに接続できません/);
assert.match(offlineHtml, /\/mobile\.html/);
assert.match(offlineHtml, /\/mobile-check\.html/);

const mobileJs = fs.readFileSync("web/mobile-standalone.js", "utf8");
assert.match(mobileJs, /gemma4\.mobileChat/);
assert.match(mobileJs, /gemma4\.mobilePcConnection/);
assert.match(mobileJs, /savePcConnection/);
assert.match(mobileJs, /normalizePcHost/);
assert.match(mobileJs, /applyConnectionParams/);
assert.match(mobileJs, /pairingCode/);
assert.match(mobileJs, /params\.get\("c"\)/);
assert.match(mobileJs, /window\.location\.origin/);
assert.match(mobileJs, /setPcStatus/);
assert.match(mobileJs, /接続先を保存済み/);
assert.match(mobileJs, /QRから接続先を保存しました/);
assert.match(mobileJs, /接続先を保存しました/);
assert.match(mobileJs, /PCへ送信しました/);
assert.match(mobileJs, /mobileSendErrorMessage/);
assert.match(mobileJs, /PCのスマホ接続QRをもう一度読み取ってください/);
assert.match(mobileJs, /sendChatToPc/);
assert.match(mobileJs, /\/api\/mobile\/import-chat/);
assert.match(mobileJs, /gemma4\.mobileNotes/);
assert.match(mobileJs, /detectBrowserAiSupport/);
assert.match(mobileJs, /isMobileUserAgent/);
assert.match(mobileJs, /renderDesktopNotice/);
assert.match(mobileJs, /detectStandaloneAiCapability/);
assert.match(mobileJs, /standaloneAiCandidates/);
assert.match(mobileJs, /renderAiCandidates/);
assert.match(mobileJs, /navigator\.gpu/);
assert.match(mobileJs, /navigator\.deviceMemory/);
assert.match(mobileJs, /MediaPipe LLM Inference/);
assert.match(mobileJs, /WebLLM/);
assert.match(mobileJs, /WASM軽量AI候補/);
assert.match(mobileJs, /モデル本体はまだ未導入/);
assert.match(mobileJs, /Transformers\.js WASM/);
assert.match(mobileJs, /WebGPU未検出のiPhone向け候補/);
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

[
  "Gemma4_12B_Web.command",
  "Gemma4_12B_全部起動.command",
  "Gemma4_12B_Web.bat",
  "Gemma4_12B_All_Start.bat",
].forEach((path) => {
  const launcher = fs.readFileSync(path, "utf8");
  assert.match(launcher, /0\.8\.197/, `${path} should use the current app version`);
  assert.doesNotMatch(launcher, /0\.8\.196/, `${path} should not pin the old app version`);
});

console.log("pwa asset tests passed");
