const fs = require("node:fs");
const assert = require("node:assert/strict");

const index = fs.readFileSync("web/index.html", "utf8");
const appJs = fs.readFileSync("web/app.js", "utf8");
assert.match(index, /rel="manifest" href="\/manifest\.webmanifest"/);
assert.match(index, /rel="icon" href="\/icons\/icon\.svg" type="image\/svg\+xml"/);
assert.match(index, /name="theme-color"/);
assert.match(index, /apple-mobile-web-app-capable/);
assert.match(index, /src="\/pwa\.js\?v=0\.8\.207-tomos51"/);
assert.match(index, /src="\/person-name-fortune\.js\?v=0\.8\.207-tomos51"/);
assert.match(index, /src="\/person-relationship\.js\?v=0\.8\.207-tomos51"/);
assert.match(index, /src="\/app\.js\?v=0\.8\.207-tomos51"/);
assert.match(appJs, /localStorage\.getItem\("gemma4\.theme"\) \|\| "light"/);
assert.match(appJs, /function openInitialManagementPanelFromUrl/);
assert.match(appJs, /function isWorkspaceCountRequest/);
assert.match(appJs, /countRequest: isWorkspaceCountRequest\(text\)/);
assert.match(appJs, /uniquePathCount = new Set/);
assert.match(appJs, /一致するファイルは\$\{uniquePathCount\}件あるよ/);
assert.match(appJs, /window\.location\.pathname === "\/pc-mobile-connect"/);
assert.match(appJs, /panel !== "mobile-connect"/);
assert.match(appJs, /setSidebarSettingsMode\?\.\(\{ els, open: true \}\)/);
assert.doesNotMatch(appJs, /replaceState\(null, "", nextUrl\)/);
assert.match(appJs, /composerRecipient/);
assert.match(appJs, /selectedRecipientContextPrompt/);

const manifest = JSON.parse(fs.readFileSync("web/manifest.webmanifest", "utf8"));
assert.equal(manifest.name, "TOMOS AI");
assert.equal(manifest.short_name, "TOMOS AI");
assert.equal(manifest.display, "standalone");
assert.equal(manifest.start_url, "/mobile.html");
assert.ok(manifest.icons.some((icon) => icon.src === "/icons/icon-192.png" && icon.sizes === "192x192"));
assert.ok(manifest.icons.some((icon) => icon.src === "/icons/icon-512.png" && icon.sizes === "512x512"));

[
  "web/pwa.js",
  "web/sw.js",
  "web/offline.html",
  "web/reset-cache.html",
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
assert.match(sw, /gemma4-pwa-0\.8\.207-tomos51/);
assert.match(sw, /\/person-name-fortune\.js\?v=0\.8\.207-tomos51/);
assert.match(sw, /\/person-relationship\.js\?v=0\.8\.207-tomos51/);
assert.match(sw, /cache\.put\(event\.request/);
const pwaJs = fs.readFileSync("web/pwa.js", "utf8");
assert.match(pwaJs, /\/sw\.js\?v=0\.8\.207-tomos51/);

const mobileHtml = fs.readFileSync("web/mobile.html", "utf8");
assert.match(mobileHtml, /rel="icon" href="\/icons\/icon\.svg" type="image\/svg\+xml"/);
assert.match(mobileHtml, /id="mobile-chat-input"/);
assert.match(mobileHtml, /id="mobile-chat-send"/);
assert.match(mobileHtml, /id="mobile-chat-list"/);
assert.match(mobileHtml, /id="mobile-desktop-notice"/);
assert.match(mobileHtml, /PC版のスマホ接続を開く/);
assert.match(mobileHtml, /\/pc-mobile-connect/);
assert.match(mobileHtml, /id="mobile-app-version"/);
assert.match(mobileHtml, /アプリ版 0\.8\.207/);
assert.match(mobileHtml, /id="mobile-ai-plan"/);
assert.match(mobileHtml, /id="mobile-ai-mode"/);
assert.match(mobileHtml, /id="mobile-ai-model"/);
assert.match(mobileHtml, /id="mobile-ai-engine-plan"/);
assert.match(mobileHtml, /id="mobile-ai-load"/);
assert.match(mobileHtml, /id="mobile-ai-load-status"/);
assert.match(mobileHtml, /id="mobile-ai-error-copy"/);
assert.match(mobileHtml, /id="mobile-ai-error-output"/);
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
assert.match(mobileHtml, /src="\/pwa\.js\?v=0\.8\.207-tomos51"/);
assert.match(mobileHtml, /Xenova\/LaMini-Flan-T5-77M/);
assert.match(mobileHtml, /HuggingFaceTB\/SmolLM2-135M-Instruct/);
assert.match(mobileHtml, /onnx-community\/Qwen2\.5-0\.5B-Instruct/);
assert.match(mobileHtml, /src="\/mobile-standalone\.js\?v=0\.8\.207-tomos51"/);

const offlineHtml = fs.readFileSync("web/offline.html", "utf8");
assert.match(offlineHtml, /rel="icon" href="\/icons\/icon\.svg" type="image\/svg\+xml"/);
assert.match(offlineHtml, /PCに接続できません/);
assert.match(offlineHtml, /\/mobile\.html/);
assert.match(offlineHtml, /\/mobile-check\.html/);

const mobileCheckHtml = fs.readFileSync("web/mobile-check.html", "utf8");
assert.match(mobileCheckHtml, /rel="icon" href="\/icons\/icon\.svg" type="image\/svg\+xml"/);

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
assert.match(mobileJs, /すでにPCへ送信済み/);
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
assert.match(mobileJs, /standaloneAiEnginePlan/);
assert.match(mobileJs, /Transformers\.js WASMを第一実験に固定/);
assert.match(mobileJs, /loadTransformersPipeline/);
assert.match(mobileJs, /cdn\.jsdelivr\.net\/npm\/@xenova\/transformers/);
assert.match(mobileJs, /Xenova\/distilgpt2/);
assert.match(mobileJs, /Xenova\/LaMini-Flan-T5-77M/);
assert.match(mobileJs, /onnx-community\/Qwen2\.5-0\.5B-Instruct/);
assert.match(mobileJs, /Qwen2\.5 0\.5B Instruct/);
assert.match(mobileJs, /DEFAULT_WASM_EXPERIMENT_MODEL = "HuggingFaceTB\/SmolLM2-135M-Instruct"/);
assert.match(mobileJs, /HuggingFaceTB\/SmolLM2-135M-Instruct/);
assert.match(mobileJs, /SmolLM2 135M Instruct/);
assert.match(mobileJs, /@huggingface\/transformers@4\.2\.0\/\+esm/);
assert.match(mobileJs, /huggingface-v4/);
assert.match(mobileJs, /dtype:\s*"q4"/);
assert.match(mobileJs, /transformersRuntimeConfig/);
assert.match(mobileJs, /wasmModelConfig/);
assert.match(mobileJs, /text2text-generation/);
assert.match(mobileJs, /gemma4\.mobileAiModel/);
assert.match(mobileJs, /selectedWasmModel/);
assert.match(mobileJs, /normalizeStoredWasmModel/);
assert.match(mobileJs, /廃止されたWASMモデル設定をリセットしました/);
assert.match(mobileJs, /quantized:\s*true/);
assert.match(mobileJs, /wasmPaths/);
assert.match(mobileJs, /numThreads\s*=\s*1/);
assert.match(mobileJs, /copyAiLastError/);
assert.match(mobileJs, /showAiErrorOutput/);
assert.match(mobileJs, /useBrowserCache\s*=\s*false/);
assert.match(mobileJs, /navigator\.share/);
assert.match(mobileJs, /navigator\.canShare/);
assert.match(mobileJs, /tomos-ai-mobile-error\.json/);
assert.match(mobileJs, /共有APIが使えないためコピーしました/);
assert.match(mobileJs, /AIエラー詳細を共有しました/);
assert.match(mobileJs, /runTransformersReply/);
assert.match(mobileJs, /localConversationReply/);
assert.match(mobileJs, /gemma4\.mobileCharacterProfile/);
assert.match(mobileJs, /normalizeMobileCharacterProfile/);
assert.match(mobileJs, /saveMobileCharacterProfile/);
assert.match(mobileJs, /loadMobileCharacterProfile/);
assert.match(mobileJs, /params\.get\("p"\)/);
assert.match(mobileJs, /あなた\(の\)\?名前/);
assert.match(mobileJs, /あなたの呼び方がまだ保存されていません/);
assert.match(mobileJs, /sanitizeGeneratedText/);
assert.match(mobileJs, /isConversationLikeReply/);
assert.match(mobileJs, /会話品質が低いため/);
assert.match(mobileJs, /gemma4\.mobileAiLastError/);
assert.match(mobileJs, /gemma4\.mobileAiLastLoaded/);
assert.match(mobileJs, /formatAiError/);
assert.match(mobileJs, /clearStaleAiError/);
assert.match(mobileJs, /古いAIエラー履歴をクリアしました/);
assert.match(mobileJs, /withTimeout/);
assert.match(mobileJs, /model_load_timeout/);
assert.match(mobileJs, /chat_timeout/);
assert.match(mobileJs, /generation_timeout/);
assert.match(mobileJs, /Qwen 0\.5Bはこの端末では重すぎる可能性があります/);
assert.match(mobileJs, /スマホAIの返信が完了しなかったため/);
assert.match(mobileJs, /MOBILE_BUILD_LABEL = "mobile30"/);
assert.match(mobileJs, /スマホ版 \$\{MOBILE_BUILD_LABEL\}/);
assert.match(mobileJs, /recentConversationContext/);
assert.match(mobileJs, /### 直近の会話/);
assert.match(mobileJs, /contextBeforeReply/);
assert.match(mobileJs, /さっきの話の続きだね/);
assert.match(mobileJs, /formatModelProgress/);
assert.match(mobileJs, /progressValue/);
assert.match(mobileJs, /中国語、英語、記号列は使わないでください/);
assert.match(mobileJs, /\[一-龠\]\{6,\}/);
assert.match(mobileJs, /元気\|げんき/);
assert.match(mobileJs, /声をかけてくれてありがとう/);
assert.match(mobileJs, /\[（\(]\[\^）\)]\*\$/);
assert.match(mobileJs, /モデル読み込み中のため、今回は会話フォールバックで返しました/);
assert.match(mobileJs, /読み込み完了。チャットできます/);
assert.match(mobileJs, /前回読み込み済みです/);
assert.match(mobileJs, /返信生成が完了しなかったため/);
assert.match(mobileJs, /renderAiCandidates/);
assert.match(mobileJs, /navigator\.gpu/);
assert.match(mobileJs, /navigator\.deviceMemory/);
assert.match(mobileJs, /MediaPipe LLM Inference/);
assert.match(mobileJs, /WebLLM/);
assert.match(mobileJs, /WASM軽量AI候補/);
assert.match(mobileJs, /モデル本体はまだ未導入/);
assert.match(mobileJs, /未導入の候補/);
assert.match(mobileJs, /Transformers\.js WASM/);
assert.match(mobileJs, /WebGPU未検出のiPhone向け候補/);
assert.match(mobileJs, /generateAssistantReply/);
assert.match(mobileJs, /LanguageModel/);
assert.match(mobileJs, /ai\.languageModel/);
assert.match(mobileJs, /gemma4\.mobileAiMode/);
assert.match(mobileJs, /wasm-experimental/);
assert.match(mobileJs, /WASM実験モード/);
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
  assert.match(launcher, /0\.8\.207/, `${path} should use the current app version`);
  assert.doesNotMatch(launcher, /0\.8\.196/, `${path} should not pin the old app version`);
});

const resetCacheHtml = fs.readFileSync("web/reset-cache.html", "utf8");
assert.match(resetCacheHtml, /\/\?v=0\.8\.207-tomos51&reset=1/);
assert.doesNotMatch(resetCacheHtml, /tomos1/);

console.log("pwa asset tests passed");
