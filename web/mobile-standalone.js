(() => {
  const CHAT_STORAGE_KEY = "gemma4.mobileChat";
  const LEGACY_NOTES_KEY = "gemma4.mobileNotes";
  const AI_MODE_KEY = "gemma4.mobileAiMode";
  const AI_MODEL_KEY = "gemma4.mobileAiModel";
  const AI_LAST_ERROR_KEY = "gemma4.mobileAiLastError";
  const AI_LAST_LOADED_KEY = "gemma4.mobileAiLastLoaded";
  const MOBILE_CHARACTER_PROFILE_KEY = "gemma4.mobileCharacterProfile";
  const PC_CONNECTION_KEY = "gemma4.mobilePcConnection";
  const pcHostInput = document.querySelector("#mobile-pc-host");
  const pcCodeInput = document.querySelector("#mobile-pc-code");
  const pcSaveButton = document.querySelector("#mobile-pc-save");
  const pcStatus = document.querySelector("#mobile-pc-status");
  const desktopNotice = document.querySelector("#mobile-desktop-notice");
  const input = document.querySelector("#mobile-chat-input");
  const sendButton = document.querySelector("#mobile-chat-send");
  const exportButton = document.querySelector("#mobile-chat-export");
  const sendPcButton = document.querySelector("#mobile-chat-send-pc");
  const markImportedButton = document.querySelector("#mobile-chat-mark-imported");
  const clearButton = document.querySelector("#mobile-chat-clear");
  const exportOutput = document.querySelector("#mobile-chat-export-output");
  const list = document.querySelector("#mobile-chat-list");
  const aiStatus = document.querySelector("#mobile-ai-status");
  const aiPlan = document.querySelector("#mobile-ai-plan");
  const aiModeSelect = document.querySelector("#mobile-ai-mode");
  const aiModelSelect = document.querySelector("#mobile-ai-model");
  const aiLoadButton = document.querySelector("#mobile-ai-load");
  const aiErrorCopyButton = document.querySelector("#mobile-ai-error-copy");
  const aiLoadStatus = document.querySelector("#mobile-ai-load-status");
  const aiErrorOutput = document.querySelector("#mobile-ai-error-output");
  const aiEnginePlan = document.querySelector("#mobile-ai-engine-plan");
  const aiDiagnostics = document.querySelector("#mobile-ai-diagnostics");
  const aiCandidates = document.querySelector("#mobile-ai-candidates");
  const importSummary = document.querySelector("#mobile-import-summary");
  const TRANSFORMERS_CDN_URL = "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2";
  const TRANSFORMERS_WASM_PATH = "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/";
  const TRANSFORMERS_V4_CDN_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.2.0/+esm";
  const TRANSFORMERS_V4_WASM_PATH = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.2.0/dist/";
  const MOBILE_BUILD_LABEL = "mobile30";
  const DEFAULT_WASM_EXPERIMENT_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct";
  const WASM_MODEL_CONFIGS = {
    "Xenova/distilgpt2": {
      task: "text-generation",
      label: "distilgpt2",
      prompt: (text) => `User: ${text}\nAssistant:`,
      options: {
        max_new_tokens: 48,
        do_sample: true,
        temperature: 0.7,
        repetition_penalty: 1.15,
        return_full_text: false,
      },
    },
    "Xenova/LaMini-Flan-T5-77M": {
      task: "text2text-generation",
      label: "LaMini-Flan-T5 77M",
      prompt: (text) => `短い日本語で返事してください。\n入力: ${text}\n返事:`,
      options: {
        max_new_tokens: 64,
      },
    },
    "HuggingFaceTB/SmolLM2-135M-Instruct": {
      task: "text-generation",
      label: "SmolLM2 135M Instruct",
      runtime: "huggingface-v4",
      cdnUrl: TRANSFORMERS_V4_CDN_URL,
      wasmPath: TRANSFORMERS_V4_WASM_PATH,
      prompt: (text, context = "") => {
        const character = loadMobileCharacterProfile();
        const name = character.name || "Gemma";
        const userName = character.userName || "ユーザー";
        const selfName = character.selfName || name;
        const personality = character.personality || "やさしく、短く、自然に答える";
        return `### 指示\nあなたは「${name}」です。相手は「${userName}」。自分の呼び方は「${selfName}」。性格: ${personality}。\n直近の会話を踏まえて、必ず自然な日本語だけで1〜2文で短く返してください。中国語、英語、記号列は使わないでください。\n\n### 直近の会話\n${context || "なし"}\n\n### ユーザー\n${text}\n\n### 返事\n`;
      },
      options: {
        max_new_tokens: 36,
        do_sample: true,
        temperature: 0.35,
        repetition_penalty: 1.25,
        return_full_text: false,
      },
      pipelineOptions: {
        dtype: "q4",
      },
      loadTimeoutMs: 180000,
      generationTimeoutMs: 45000,
    },
    "onnx-community/Qwen2.5-0.5B-Instruct": {
      task: "text-generation",
      label: "Qwen2.5 0.5B Instruct",
      runtime: "huggingface-v4",
      cdnUrl: TRANSFORMERS_V4_CDN_URL,
      wasmPath: TRANSFORMERS_V4_WASM_PATH,
      prompt: (text) => {
        const character = loadMobileCharacterProfile();
        const name = character.name || "Gemma";
        const userName = character.userName || "ユーザー";
        const selfName = character.selfName || name;
        const personality = character.personality || "やさしく、短く、自然に答える";
        return [
          "<|im_start|>system",
          `あなたは「${name}」です。自分の呼び方は「${selfName}」。相手は「${userName}」です。`,
          `性格と口調: ${personality}`,
          "日本語で、2文以内で、自然な会話として返してください。",
          "<|im_end|>",
          "<|im_start|>user",
          text,
          "<|im_end|>",
          "<|im_start|>assistant",
        ].join("\n");
      },
      options: {
        max_new_tokens: 80,
        do_sample: true,
        temperature: 0.55,
        repetition_penalty: 1.12,
        return_full_text: false,
      },
      pipelineOptions: {
        dtype: "q4",
      },
      loadTimeoutMs: 240000,
      generationTimeoutMs: 90000,
    },
  };
  const WASM_EXPERIMENT_MODELS = new Set(Object.keys(WASM_MODEL_CONFIGS));
  let transformersGenerator = null;
  let transformersLoadPromise = null;
  let transformersLoadedModel = "";

  function readJson(key, fallback) {
    try {
      return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    } catch {
      return fallback;
    }
  }

  function legacyNotesAsMessages() {
    const notes = readJson(LEGACY_NOTES_KEY, []);
    return notes.flatMap((note) => ([
      {
        id: `${note.id || note.createdAt || Date.now()}-user`,
        role: "user",
        text: String(note.text || ""),
        createdAt: note.createdAt || new Date().toISOString(),
        imported: Boolean(note.imported),
      },
      {
        id: `${note.id || note.createdAt || Date.now()}-assistant`,
        role: "assistant",
        text: "保存しました。PCに戻ったら、この内容を取り込めます。",
        createdAt: note.createdAt || new Date().toISOString(),
        imported: Boolean(note.imported),
      },
    ])).filter((message) => message.text.trim());
  }

  function loadMessages() {
    const messages = readJson(CHAT_STORAGE_KEY, null);
    if (Array.isArray(messages)) return messages;
    const migrated = legacyNotesAsMessages();
    if (migrated.length > 0) saveMessages(migrated);
    return migrated;
  }

  function saveMessages(messages) {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  }

  function recentConversationContext(messages = loadMessages(), limit = 4) {
    return messages
      .filter((message) => ["user", "assistant"].includes(message?.role) && String(message?.text || "").trim())
      .slice(-limit)
      .map((message) => {
        const role = message.role === "assistant" ? loadMobileCharacterProfile().name : "あなた";
        const text = String(message.text || "").replace(/\s+/g, " ").slice(0, 80);
        return `${role}: ${text}`;
      })
      .join("\n");
  }

  function normalizePcHost(value) {
    const raw = String(value || "").trim().replace(/\/+$/, "");
    if (!raw) return "";
    try {
      const url = new URL(raw);
      if (!["http:", "https:"].includes(url.protocol)) return "";
      return url.origin;
    } catch {
      return "";
    }
  }

  function loadPcConnection() {
    return readJson(PC_CONNECTION_KEY, { host: "", pairingCode: "", savedAt: "" });
  }

  function normalizeMobileCharacterProfile(profile = {}) {
    const compact = (value, max = 80) => String(value || "").trim().slice(0, max);
    return {
      name: compact(profile.name || "Gemma", 24) || "Gemma",
      userName: compact(profile.userName, 24),
      selfName: compact(profile.selfName, 24),
      gender: ["female", "male", "other"].includes(profile.gender) ? profile.gender : "",
      tonePreset: ["friendly", "calm", "teacher", "concise"].includes(profile.tonePreset) ? profile.tonePreset : "friendly",
      personality: compact(profile.personality, 100),
    };
  }

  function loadMobileCharacterProfile() {
    return normalizeMobileCharacterProfile(readJson(MOBILE_CHARACTER_PROFILE_KEY, {}));
  }

  function saveMobileCharacterProfile(value) {
    const profile = normalizeMobileCharacterProfile(value);
    localStorage.setItem(MOBILE_CHARACTER_PROFILE_KEY, JSON.stringify(profile));
    return profile;
  }

  function formatConnectionTime(value) {
    if (!value) return "";
    try {
      return new Intl.DateTimeFormat("ja-JP", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value));
    } catch {
      return "";
    }
  }

  function setPcStatus(title, detail = "", variant = "") {
    if (!pcStatus) return;
    pcStatus.className = `connection-state ${variant}`.trim();
    pcStatus.textContent = "";
    const titleEl = document.createElement("strong");
    const detailEl = document.createElement("span");
    titleEl.textContent = title;
    detailEl.textContent = detail;
    pcStatus.append(titleEl, detailEl);
  }

  function setAiLoadStatus(message, variant = "") {
    if (!aiLoadStatus) return;
    aiLoadStatus.textContent = message;
    aiLoadStatus.dataset.variant = variant;
  }

  function formatAiError(error) {
    if (!error) return "unknown error";
    const name = error.name ? `${error.name}: ` : "";
    const message = error.message || String(error);
    return `${name}${message}`;
  }

  function recordAiError(stage, error) {
    const model = selectedWasmModel();
    const runtime = transformersRuntimeConfig(model);
    const detail = {
      stage,
      message: formatAiError(error),
      at: new Date().toISOString(),
      userAgent: navigator.userAgent,
      model,
      runtime: runtime.runtime,
      cdn: runtime.cdnUrl,
      wasmPath: runtime.wasmPath,
    };
    localStorage.setItem(AI_LAST_ERROR_KEY, JSON.stringify(detail));
    showAiErrorOutput(JSON.stringify(detail, null, 2));
    return detail;
  }

  function showAiErrorOutput(message) {
    if (!aiErrorOutput) return;
    aiErrorOutput.hidden = false;
    aiErrorOutput.value = message;
    aiErrorOutput.focus();
    aiErrorOutput.select();
  }

  function clearStaleAiError() {
    const raw = localStorage.getItem(AI_LAST_ERROR_KEY) || "";
    if (!raw) return;
    try {
      const detail = JSON.parse(raw);
      const runtime = transformersRuntimeConfig(detail.model || selectedWasmModel());
      if (detail.cdn === runtime.cdnUrl && detail.wasmPath === runtime.wasmPath) return;
    } catch {
      // Malformed old error data should not block a fresh retry.
    }
    localStorage.removeItem(AI_LAST_ERROR_KEY);
    if (aiErrorOutput) {
      aiErrorOutput.value = "";
      aiErrorOutput.hidden = true;
    }
    setAiLoadStatus("古いAIエラー履歴をクリアしました。もう一度AIモデルを読み込んでください。");
  }

  async function copyAiLastError() {
    clearStaleAiError();
    const raw = localStorage.getItem(AI_LAST_ERROR_KEY) || "";
    const message = raw || "AIエラーはまだ記録されていません。";
    showAiErrorOutput(message);
    if (raw && navigator.share) {
      try {
        const file = new File([message], "tomos-ai-mobile-error.json", { type: "application/json" });
        const payload = navigator.canShare?.({ files: [file] })
          ? {
              title: "TOMOS AI スマホAIエラー",
              text: "TOMOS AI スマホAIエラー詳細",
              files: [file],
            }
          : {
              title: "TOMOS AI スマホAIエラー",
              text: message,
            };
        await navigator.share(payload);
        setAiLoadStatus("AIエラー詳細を共有しました。");
        return;
      } catch (error) {
        if (error.name === "AbortError") {
          setAiLoadStatus("共有をキャンセルしました。");
          return;
        }
        try {
          await navigator.share({
            title: "TOMOS AI スマホAIエラー",
            text: message,
          });
          setAiLoadStatus("AIエラー詳細を共有しました。");
          return;
        } catch (fallbackError) {
          console.warn("AI error share failed", fallbackError);
        }
      }
    }
    try {
      await navigator.clipboard?.writeText(message);
      setAiLoadStatus(
        raw && !navigator.share
          ? "共有APIが使えないためコピーしました。Safariで開き直すか、ホーム画面版から試してください。"
          : raw
            ? "AIエラー詳細をコピーしました。"
            : message,
      );
    } catch {
      setAiLoadStatus(message);
    }
  }

  function selectedWasmModel() {
    const stored = localStorage.getItem(AI_MODEL_KEY) || "";
    return WASM_EXPERIMENT_MODELS.has(stored) ? stored : DEFAULT_WASM_EXPERIMENT_MODEL;
  }

  function wasmModelConfig(model = selectedWasmModel()) {
    return WASM_MODEL_CONFIGS[model] || WASM_MODEL_CONFIGS[DEFAULT_WASM_EXPERIMENT_MODEL];
  }

  function transformersRuntimeConfig(model = selectedWasmModel()) {
    const config = wasmModelConfig(model);
    return {
      runtime: config.runtime || "xenova-v2",
      cdnUrl: config.cdnUrl || TRANSFORMERS_CDN_URL,
      wasmPath: config.wasmPath || TRANSFORMERS_WASM_PATH,
    };
  }

  function normalizeStoredWasmModel() {
    const stored = localStorage.getItem(AI_MODEL_KEY) || "";
    if (!stored || WASM_EXPERIMENT_MODELS.has(stored)) return;
    localStorage.setItem(AI_MODEL_KEY, DEFAULT_WASM_EXPERIMENT_MODEL);
    const rawError = localStorage.getItem(AI_LAST_ERROR_KEY) || "";
    if (rawError.includes(stored)) {
      localStorage.removeItem(AI_LAST_ERROR_KEY);
      if (aiErrorOutput) {
        aiErrorOutput.value = "";
        aiErrorOutput.hidden = true;
      }
    }
    setAiLoadStatus("廃止されたWASMモデル設定をリセットしました。AIモデルを読み込むを押してください。");
  }

  function resetTransformersModel() {
    transformersGenerator = null;
    transformersLoadPromise = null;
    transformersLoadedModel = "";
  }

  function withTimeout(promise, timeoutMs, message) {
    let timer = null;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(message)), timeoutMs);
    });
    return Promise.race([promise, timeout]).finally(() => {
      if (timer) clearTimeout(timer);
    });
  }

  function saveLoadedModelState(model) {
    localStorage.setItem(AI_LAST_LOADED_KEY, JSON.stringify({
      model,
      loadedAt: new Date().toISOString(),
    }));
  }

  function lastLoadedModelState() {
    return readJson(AI_LAST_LOADED_KEY, null);
  }

  function renderPcConnection() {
    const connection = loadPcConnection();
    if (pcHostInput && connection.host) pcHostInput.value = connection.host;
    if (pcCodeInput && connection.pairingCode) pcCodeInput.value = connection.pairingCode;
    if (connection.host) {
      const savedAt = formatConnectionTime(connection.savedAt);
      setPcStatus(
        "接続先を保存済み",
        `${connection.host} / コード ${connection.pairingCode || "未入力"}${savedAt ? ` / 保存 ${savedAt}` : ""}`,
        "saved",
      );
      return;
    }
    setPcStatus("PC未接続", "QRを読み取るか、PC URLと6桁コードを保存してください。");
  }

  function savePcConnection() {
    const host = normalizePcHost(pcHostInput?.value || "");
    const pairingCode = String(pcCodeInput?.value || "").replace(/\D/g, "").slice(0, 6);
    if (!host || pairingCode.length !== 6) {
      setPcStatus("保存できませんでした", "PC URLと6桁コードを確認してください。", "error");
      return null;
    }
    const connection = {
      host,
      pairingCode,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(PC_CONNECTION_KEY, JSON.stringify(connection));
    if (pcHostInput) pcHostInput.value = connection.host;
    if (pcCodeInput) pcCodeInput.value = connection.pairingCode;
    setPcStatus("接続先を保存しました", `${connection.host} / コード ${connection.pairingCode}`, "saved");
    return connection;
  }

  function savePcConnectionValue(host, pairingCode) {
    const normalizedHost = normalizePcHost(host);
    const normalizedCode = String(pairingCode || "").replace(/\D/g, "").slice(0, 6);
    if (!normalizedHost || normalizedCode.length !== 6) return null;
    const connection = {
      host: normalizedHost,
      pairingCode: normalizedCode,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(PC_CONNECTION_KEY, JSON.stringify(connection));
    return connection;
  }

  function applyConnectionParams() {
    const params = new URLSearchParams(window.location.search || "");
    const host = params.get("pcHost") || params.get("h") || window.location.origin || "";
    const pairingCode = params.get("pairingCode") || params.get("c") || "";
    const connection = savePcConnectionValue(host, pairingCode);
    if (!connection) return null;
    const profileParam = params.get("p") || "";
    if (profileParam) {
      try {
        saveMobileCharacterProfile(JSON.parse(profileParam));
      } catch {
        // Character profile is optional; keep pairing usable if it is malformed.
      }
    }
    if (pcHostInput) pcHostInput.value = connection.host;
    if (pcCodeInput) pcCodeInput.value = connection.pairingCode;
    setPcStatus("QRから接続先を保存しました", `${connection.host} / コード ${connection.pairingCode}`, "saved");
    return connection;
  }

  function exportPayload() {
    return {
      type: "gemma4-mobile-chat",
      version: "0.1.0",
      exportedAt: new Date().toISOString(),
      source: {
        mode: "smartphone-standalone",
        userAgent: navigator.userAgent,
      },
      messages: loadMessages().map((message) => ({
        id: message.id,
        role: message.role,
        text: message.text,
        createdAt: message.createdAt,
        imported: Boolean(message.imported),
      })),
    };
  }

  function showExportPayload() {
    if (!exportOutput) return;
    exportOutput.hidden = false;
    exportOutput.value = JSON.stringify(exportPayload(), null, 2);
    exportOutput.focus();
    exportOutput.select();
  }

  function mobileImportSummary(messages = loadMessages()) {
    const unimported = messages.filter((message) => !message.imported).length;
    return {
      total: messages.length,
      unimported,
      label: `未取り込み ${unimported}件 / 全${messages.length}件`,
    };
  }

  function markMessagesImported() {
    const messages = loadMessages();
    const nextMessages = messages.map((message) => ({ ...message, imported: true }));
    saveMessages(nextMessages);
    if (exportOutput && !exportOutput.hidden) {
      exportOutput.value = JSON.stringify(exportPayload(), null, 2);
    }
    render();
  }

  async function sendChatToPc() {
    const connection = loadPcConnection();
    if (!connection.host || !connection.pairingCode) {
      setPcStatus("PCへ送信できません", "先にPC URLと6桁コードを保存してください。", "error");
      return;
    }
    const payload = exportPayload();
    if (!payload.messages.some((message) => !message.imported)) {
      setPcStatus("送信する内容がありません", "未取り込みのチャットはありません。", "saved");
      return;
    }
    try {
      const response = await fetch(`${connection.host}/api/mobile/import-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pairingCode: connection.pairingCode,
          payload,
        }),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(mobileSendErrorMessage(result.error || `HTTP ${response.status}`));
      }
      markMessagesImported();
      if (result.duplicate) {
        setPcStatus("すでにPCへ送信済み", `${result.summary?.total || 0}件はPC側の取り込み待ちにあります。`, "sent");
        return;
      }
      setPcStatus("PCへ送信しました", `${result.summary?.total || 0}件をPC側の取り込み待ちに追加しました。`, "sent");
    } catch (error) {
      setPcStatus("PCへ送信できませんでした", mobileSendErrorMessage(error.message), "error");
    }
  }

  function mobileSendErrorMessage(error) {
    const message = String(error || "");
    if (message === "invalid_pairing_code") {
      return "6桁コードが期限切れか、PC側で新しいコードに更新されています。PCのスマホ接続QRをもう一度読み取ってください。";
    }
    if (message === "empty_payload") {
      return "送信するチャットがありません。先にスマホチャットで送信してください。";
    }
    if (message === "invalid_payload") {
      return "スマホチャットの保存形式を確認できませんでした。ページを再読み込みしてもう一度試してください。";
    }
    if (/Failed to fetch|NetworkError|Load failed/i.test(message)) {
      return "PCに接続できません。同じWi-Fiか、テザリング接続先、PC側サーバーの起動を確認してください。";
    }
    return message || "原因不明のエラーです。PCのスマホ接続QRをもう一度読み取ってください。";
  }

  function clearMessages() {
    const ok = window.confirm("スマホ内のチャット履歴を削除します。PCへ未取り込みの内容も消えます。削除しますか？");
    if (!ok) return;
    saveMessages([]);
    if (exportOutput) {
      exportOutput.value = "";
      exportOutput.hidden = true;
    }
    render();
  }

  function formatDate(value) {
    try {
      return new Intl.DateTimeFormat("ja-JP", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value));
    } catch {
      return "";
    }
  }

  function detectBrowserAiSupport() {
    if (window.LanguageModel) {
      return { available: true, type: "LanguageModel", factory: window.LanguageModel };
    }
    if (window.ai?.languageModel) {
      return { available: true, type: "ai.languageModel", factory: window.ai.languageModel };
    }
    return { available: false, type: "template", factory: null };
  }

  function isMobileUserAgent() {
    return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  }

  function renderDesktopNotice() {
    if (!desktopNotice) return;
    desktopNotice.hidden = isMobileUserAgent();
  }

  function detectStandaloneAiCapability() {
    const browserAi = detectBrowserAiSupport();
    const gpu = navigator.gpu;
    const memory = Number(navigator.deviceMemory || 0);
    const cores = Number(navigator.hardwareConcurrency || 0);
    const webAssembly = typeof WebAssembly === "object";
    const storage = navigator.storage?.estimate ? "available" : "unknown";
    const mobile = isMobileUserAgent();
    const webGpuReady = Boolean(gpu && webAssembly);
    const enoughMemoryHint = memory === 0 || memory >= 4;
    let recommendation = "記録モード";
    let detail = "この端末では、今はスマホ内に保存してPCへ取り込む運用が安定です。";
    if (browserAi.available) {
      recommendation = "Browser AI";
      detail = "ブラウザ組み込みAI候補を検出しました。まずこの経路で短い返信を試します。";
    } else if (webGpuReady && enoughMemoryHint) {
      recommendation = "WebGPU軽量モデル候補";
      detail = "WebGPUが使えるため、次フェーズでMediaPipe LLM InferenceまたはWebLLMの小型モデルを試せます。";
    } else if (webGpuReady) {
      recommendation = "WebGPU軽量モデル要注意";
      detail = "WebGPUはありますが、端末メモリが少ない可能性があります。小型モデル限定で検証します。";
    } else if (webAssembly && cores >= 4) {
      recommendation = "WASM軽量AI候補";
      detail = "WebAssemblyとCPU 4スレッド以上を検出しました。モデル本体は未導入なので、今の返信は記録モードです。";
    } else if (webAssembly) {
      recommendation = "WASM記録モード";
      detail = "WebAssemblyは使えますが、スマホ単体AIモデルはまだ読み込んでいません。軽量モデル導入までは記録モードで動きます。";
    }
    return {
      recommendation,
      detail,
      browserAiAvailable: browserAi.available,
      webGpuReady,
      webAssembly,
      cores,
      memory,
      items: [
        { label: "Browser AI", value: browserAi.available ? browserAi.type : "未検出" },
        { label: "WebGPU", value: gpu ? "対応候補" : "未検出" },
        { label: "WebAssembly", value: webAssembly ? "対応" : "未対応" },
        { label: "端末メモリ", value: memory ? `${memory}GB目安` : "取得不可" },
        { label: "CPUスレッド", value: cores ? `${cores}` : "取得不可" },
        { label: "Storage API", value: storage === "available" ? "確認可能" : "不明" },
        { label: "スマホ判定", value: mobile ? "スマホ/タブレット" : "PC/不明" },
      ],
    };
  }

  function standaloneAiCandidates(capability = detectStandaloneAiCapability()) {
    if (capability.browserAiAvailable) {
      return [
        {
          title: "Browser AI",
          status: "優先",
          detail: "ブラウザ組み込みAIを使います。モデルDLや外部APIなしで試せる可能性があります。",
          recommended: true,
        },
        {
          title: "Transformers.js WASM",
          status: "予備",
          detail: "組み込みAIが不安定な場合のWASM実験候補です。初回モデルDL容量を検証します。",
          recommended: false,
        },
      ];
    }
    if (capability.webGpuReady) {
      return [
        {
          title: "MediaPipe LLM Inference / WebGPU",
          status: "優先",
          detail: "WebGPUがある端末向けです。Gemma系のWeb用モデルを小さく試します。",
          recommended: true,
        },
        {
          title: "WebLLM / WebGPU",
          status: "代替",
          detail: "WebGPUでブラウザ内LLMを動かす候補です。モデルサイズと初回DLを比較します。",
          recommended: false,
        },
        {
          title: "Transformers.js WASM",
          status: "予備",
          detail: "WebGPU経路が重い場合のフォールバック候補です。",
          recommended: false,
        },
      ];
    }
    if (capability.webAssembly && capability.cores >= 4) {
      return [
        {
          title: "Transformers.js WASM",
          status: "未導入の候補",
          detail: "WebGPU未検出のiPhone向け候補です。AIチャット本体はまだ動かず、次に超小型/量子化モデルの読み込みを検証します。",
          recommended: true,
        },
        {
          title: "記録モード + PC取り込み",
          status: "安定",
          detail: "モデルDLが重い場合の常用モードです。スマホ内保存とPC取り込みは継続できます。",
          recommended: false,
        },
        {
          title: "MediaPipe / WebLLM",
          status: "保留",
          detail: "現状はWebGPU未検出のため、この端末では後回しです。",
          recommended: false,
        },
      ];
    }
    return [
      {
        title: "記録モード + PC取り込み",
        status: "優先",
        detail: "スマホ単体AIは保留し、チャット保存とPC取り込みを安定運用します。",
        recommended: true,
      },
    ];
  }

  function standaloneAiEnginePlan(capability = detectStandaloneAiCapability()) {
    if (capability.webAssembly && !capability.webGpuReady) {
      return [
        {
          title: "Transformers.js WASMを第一実験に固定",
          status: "次に実装",
          detail: "iPhoneでWebGPU未検出のため、外部APIなし・クラウド同期なしで、WASM量子化モデルの初回DL容量と返信速度を測ります。",
        },
        {
          title: "WebLLM / MediaPipe WebGPU",
          status: "後回し",
          detail: "WebGPUが検出できる端末で再評価します。今のiPhone実機では主経路にしません。",
        },
      ];
    }
    if (capability.webGpuReady) {
      return [
        {
          title: "WebGPU軽量モデル",
          status: "次に比較",
          detail: "MediaPipe LLM InferenceとWebLLMの小型モデルを比較します。WASMはフォールバックにします。",
        },
      ];
    }
    return [
      {
        title: "記録モード",
        status: "継続",
        detail: "端末内AIモデルは保留し、スマホ内保存とPC取り込みを安定運用します。",
      },
    ];
  }

  async function browserAiReply(text) {
    const support = detectBrowserAiSupport();
    if (!support.available) return "";
    const factory = support.factory;
    const session = await factory.create({
      systemPrompt:
        "あなたはスマホ単体で動く短い日本語チャット相手です。長くしすぎず、相手のメモや相談を受け止めて、次にできることを1つだけ提案してください。",
    });
    try {
      return String(await session.prompt(text)).trim();
    } finally {
      session.destroy?.();
    }
  }

  function templateAssistantReply(text) {
    const capability = detectStandaloneAiCapability();
    const prefix = capability.recommendation.includes("WASM")
      ? "端末はWASM軽量AI候補ですが、モデル本体はまだ未導入です。"
      : capability.recommendation.includes("WebGPU")
        ? "端末はWebGPU軽量モデル候補です。次フェーズでモデル読み込みを試します。"
        : "";
    if (/勉強|学習|ノート|覚え/i.test(text)) {
      return `${prefix ? `${prefix}\n` : ""}学習メモとして保存しました。あとでPCへ取り込む時に、学習ノートや記憶として整理できます。`;
    }
    if (/キャラ|記憶|覚えて/i.test(text)) {
      return `${prefix ? `${prefix}\n` : ""}キャラの記憶候補として保存しました。PC取り込み時に、キャラクター記憶へ追加できます。`;
    }
    return `${prefix ? `${prefix}\n` : ""}スマホ単体チャットに保存しました。PCへ取り込むと、PC側のAIで続きを扱えます。`;
  }

  function wasmExperimentalReply(text) {
    if (/勉強|学習|ノート|覚え/i.test(text)) {
      return "WASM実験モードです。モデル本体はまだ未導入なので、学習メモとしてスマホ内に保存し、PC取り込みで学習ノートへ回せます。";
    }
    return "WASM実験モードです。WebAssemblyは使えますが、軽量モデル本体はまだ未導入です。今はスマホ内保存とPC取り込みで会話を保持します。";
  }

  function localConversationReply(text, context = recentConversationContext()) {
    const message = String(text || "").trim();
    const character = loadMobileCharacterProfile();
    const name = character.name || "Gemma";
    const userName = character.userName ? `${character.userName}、` : "";
    const selfName = character.selfName ? `${character.selfName}は` : `${name}は`;
    const softener = character.tonePreset === "concise" ? "" : "ね";
    const teacher = character.tonePreset === "teacher";
    const calm = character.tonePreset === "calm";
    if (!message) return `${userName}送ってくれた内容を確認しました。もう少しだけ詳しく教えてください。`;
    if (/さっき|今の|それ|そのこと|続き/i.test(message) && context) {
      return `${userName}さっきの話の続きだね。${selfName}はその流れで聞いています。もう少しだけ詳しく教えてください。`;
    }
    if (/あなた(の)?名前|君(の)?名前|きみ(の)?名前|名前(は|を教えて)|誰(ですか|なの|だっけ)|なんて呼べば/i.test(message)) {
      const selfLabel = character.selfName ? `、自分のことは「${character.selfName}」` : "";
      return `${userName}${name}です${selfLabel}と呼びます。`;
    }
    if (/私(の)?名前|俺(の)?名前|僕(の)?名前|ぼく(の)?名前|わたし(の)?名前|なんて呼んで/i.test(message)) {
      if (character.userName) return `${userName}あなたのことは「${character.userName}」と呼びます。`;
      return `${name}には、あなたの呼び方がまだ保存されていません。PCのマイキャラ設定で「あなたをどう呼ぶか」を入れて、QRを読み直してください。`;
    }
    if (/おはよ|おはよう/i.test(message)) {
      return `${userName}おはよう。${selfName}ここにいます。今日もまずはひとつだけ進めていこう${softener}。`;
    }
    if (/元気|げんき|調子(は|どう)|どう(だ|ですか|かな)|大丈夫|だいじょうぶ/i.test(message)) {
      return calm
        ? `${userName}${selfName}は大丈夫です。声をかけてくれてありがとうございます。`
        : `${userName}${selfName}は元気だよ。声をかけてくれてありがとう${softener}。`;
    }
    if (/おやすみ|眠|寝る/i.test(message)) {
      return `${userName}おつかれさま。今日はここまでにして、ゆっくり休もう${softener}。`;
    }
    if (/疲れ|つかれ|しんど|だる/i.test(message)) {
      return calm
        ? `${userName}それはしんどかったですね。今は大きく進めなくて大丈夫です。まず少し休みましょう。`
        : `${userName}それはしんどい${softener}。今は大きく進めなくていいので、まず水分を取って少し休もう。`;
    }
    if (/不安|こわ|怖|心配/i.test(message)) {
      return `${userName}不安なんだ${softener}。まず何が一番気になっているか、ひとつだけ一緒に整理しよう。`;
    }
    if (/勉強|学習|宿題|試験|テスト/i.test(message)) {
      return teacher
        ? `${userName}勉強のことですね。まず範囲をひとつに絞って、5分だけ始めるのがよさそうです。`
        : `${userName}勉強のことだ${softener}。まず一番小さい範囲を決めて、5分だけ始めよう。`;
    }
    if (/ありがとう|助か/i.test(message)) {
      return `${userName}どういたしまして。続きも必要なら、そのまま話して大丈夫です。`;
    }
    if (message.length <= 12) {
      return `${userName}${message}、ですね。もう少し聞かせてください。今どんな感じですか？`;
    }
    const personalityHint = character.personality ? ` ${name}は「${character.personality}」の感じで受け止めます。` : "";
    return `${userName}話してくれてありがとう。${personalityHint}今は気持ちを整理して、次の一歩を小さくするのがよさそうです。`;
  }

  function sanitizeGeneratedText(value, prompt) {
    let text = String(value || "").trim();
    if (!text) return "";
    const promptText = String(prompt || "").trim();
    if (promptText && text.startsWith(promptText)) text = text.slice(promptText.length).trim();
    text = text
      .replace(/^Assistant:\s*/i, "")
      .replace(/^返事[:：]\s*/i, "")
      .replace(/\s+/g, " ")
      .trim();
    return text;
  }

  function isConversationLikeReply(reply, inputText) {
    const text = String(reply || "").trim();
    if (text.length < 2 || text.length > 240) return false;
    if (/C-suite|Editor in Chief|ESPN|Karavel|^[\s:・\-0-9.%/()A-Za-z|]+$/.test(text)) return false;
    if (/[一-龠]{6,}/.test(text) && !/[ぁ-んァ-ン]/.test(text)) return false;
    if (/[一-龠]{4,}[をにへとがのはもで]{0,2}[一-龠]{3,}/.test(text) && (text.match(/[ぁ-んァ-ン]/g) || []).length < 3) return false;
    if (/[,，].*[一-龠]{2,}.*[（(][^）)]*$/.test(text)) return false;
    if (/[（(][^）)]*$|^[^（(]*[）)]/.test(text)) return false;
    if (/[가-힣]{2,}|[\u0400-\u04ff]{2,}/.test(text)) return false;
    if (/(.)\1{5,}/.test(text)) return false;
    const symbolCount = (text.match(/[^\sぁ-んァ-ン一-龠A-Za-z0-9。、！？,.!?ー「」『』（）()]/g) || []).length;
    if (symbolCount > Math.max(4, text.length * 0.18)) return false;
    const inputLooksJapanese = /[ぁ-んァ-ン一-龠]/.test(String(inputText || ""));
    if (!inputLooksJapanese) return true;
    const japaneseChars = (text.match(/[ぁ-んァ-ン一-龠]/g) || []).length;
    const asciiLetters = (text.match(/[A-Za-z]/g) || []).length;
    const kanaChars = (text.match(/[ぁ-んァ-ン]/g) || []).length;
    return japaneseChars >= 4 && kanaChars >= 1 && japaneseChars >= asciiLetters;
  }

  function formatModelProgress(model, progress) {
    const status = progress?.status ? String(progress.status) : "loading";
    const file = progress?.file ? ` / ${progress.file}` : "";
    const loaded = Number(progress?.loaded || 0);
    const total = Number(progress?.total || 0);
    const progressValue = Number(progress?.progress || 0);
    let percent = "";
    if (Number.isFinite(progressValue) && progressValue > 0) {
      percent = ` ${Math.max(0, Math.min(100, Math.round(progressValue)))}%`;
    } else if (loaded > 0 && total > 0) {
      percent = ` ${Math.round((loaded / total) * 100)}%`;
    }
    return `${model}: ${status}${percent}${file}`;
  }

  async function loadTransformersPipeline() {
    const model = selectedWasmModel();
    const config = wasmModelConfig(model);
    const runtime = transformersRuntimeConfig(model);
    clearStaleAiError();
    if (transformersGenerator && transformersLoadedModel === model) return transformersGenerator;
    if (transformersLoadPromise) return transformersLoadPromise;
    setAiLoadStatus(`${model} を読み込み中です。初回はモデルDLに時間がかかります。`, "loading");
    if (aiLoadButton) aiLoadButton.disabled = true;
    transformersLoadPromise = import(runtime.cdnUrl)
      .catch((error) => {
        const detail = recordAiError("cdn_import", error);
        throw new Error(`${detail.stage}: ${detail.message}`);
      })
      .then(async ({ pipeline, env }) => {
        if (env) {
          env.allowLocalModels = false;
          env.useBrowserCache = false;
          if (runtime.runtime === "xenova-v2" && env.backends?.onnx?.wasm) {
            env.backends.onnx.wasm.wasmPaths = runtime.wasmPath;
            env.backends.onnx.wasm.numThreads = 1;
          }
        }
        const generator = await withTimeout(
          pipeline(config.task, model, {
            ...(config.pipelineOptions || { quantized: true }),
            progress_callback: (progress) => {
              setAiLoadStatus(formatModelProgress(model, progress), "loading");
            },
          }),
          config.loadTimeoutMs || 120000,
          "model_load_timeout",
        ).catch((error) => {
          const detail = recordAiError("model_pipeline", error);
          throw new Error(`${detail.stage}: ${detail.message}`);
        });
        transformersGenerator = generator;
        transformersLoadedModel = model;
        localStorage.removeItem(AI_LAST_ERROR_KEY);
        saveLoadedModelState(model);
        setAiLoadStatus(`${model} 読み込み完了。チャットできます。リロード後は再初期化が必要です。`, "ready");
        return generator;
      })
      .catch((error) => {
        transformersLoadPromise = null;
        const detail = recordAiError("load", error);
        setAiLoadStatus(`モデル読み込み失敗: ${detail.message}`, "error");
        throw error;
      })
      .finally(() => {
        if (aiLoadButton) aiLoadButton.disabled = false;
      });
    return transformersLoadPromise;
  }

  async function runTransformersReply(text, context = recentConversationContext()) {
    const generator = await loadTransformersPipeline();
    const model = selectedWasmModel();
    const config = wasmModelConfig(model);
    const prompt = config.prompt(text, context);
    setAiLoadStatus(`${model} で返信を生成中です。時間がかかる場合は自動で会話フォールバックへ戻します。`, "loading");
    const output = await withTimeout(
      generator(prompt, config.options),
      config.generationTimeoutMs || 45000,
      "generation_timeout",
    );
    const first = Array.isArray(output) ? output[0] : output;
    const generated = sanitizeGeneratedText(first?.generated_text, prompt);
    if (!isConversationLikeReply(generated, text)) {
      setAiLoadStatus(`${model} は読み込み成功。ただし会話品質が低いため、スマホ内の会話フォールバックで返信しました。`, "ready");
      return localConversationReply(text, context);
    }
    setAiLoadStatus(`${model} の返信生成が完了しました。`, "ready");
    return generated;
  }

  async function generateAssistantReply(text, context = recentConversationContext()) {
    const mode = localStorage.getItem(AI_MODE_KEY) || "auto";
    if (mode === "wasm-experimental") {
      if (transformersGenerator) {
        try {
          return await withTimeout(
            runTransformersReply(text, context),
            wasmModelConfig().chatTimeoutMs || 150000,
            "chat_timeout",
          );
        } catch (error) {
          console.warn("Transformers.js reply failed", error);
          setAiLoadStatus("スマホAIの返信が完了しなかったため、会話フォールバックで返しました。", "error");
          resetTransformersModel();
          return localConversationReply(text, context);
        }
      }
      if (transformersLoadPromise) {
        setAiLoadStatus("モデル読み込み中のため、今回は会話フォールバックで返しました。読み込み完了後にもう一度試してください。", "loading");
        return localConversationReply(text, context);
      }
      return wasmExperimentalReply(text);
    }
    if (mode !== "template") {
      try {
        const reply = await browserAiReply(text);
        if (reply) return reply;
      } catch (error) {
        console.warn("Browser AI reply failed", error);
      }
    }
    return templateAssistantReply(text);
  }

  function renderAiStatus() {
    const capability = detectStandaloneAiCapability();
    const mode = localStorage.getItem(AI_MODE_KEY) || "auto";
    if (aiModeSelect) aiModeSelect.value = mode;
    if (aiModelSelect) aiModelSelect.value = selectedWasmModel();
    if (aiStatus) {
      aiStatus.textContent = `AI: ${capability.recommendation} / 方式: ${aiModeLabel(mode)}`;
    }
    if (aiPlan) {
      aiPlan.textContent = capability.detail;
    }
    if (!transformersGenerator && !transformersLoadPromise && mode === "wasm-experimental") {
      const lastLoaded = lastLoadedModelState();
      const selected = selectedWasmModel();
      if (lastLoaded?.model === selected) {
        setAiLoadStatus(`${selected} は前回読み込み済みです。ページをリロードしたため、チャット前に再初期化が必要です。AIモデルを読み込むを押してください。`, "ready");
      }
    }
    if (!aiDiagnostics) return;
    aiDiagnostics.innerHTML = "";
    capability.items.forEach((item) => {
      const row = document.createElement("li");
      const label = document.createElement("strong");
      const value = document.createElement("span");
      label.textContent = item.label;
      value.textContent = item.value;
      row.append(label, value);
      aiDiagnostics.appendChild(row);
    });
    renderAiCandidates(capability);
    renderAiEnginePlan(capability);
  }

  function aiModeLabel(mode) {
    if (mode === "browser-ai") return "Browser AI";
    if (mode === "wasm-experimental") return "WASM実験";
    if (mode === "template") return "記録モード";
    return "自動選択";
  }

  function renderAiCandidates(capability = detectStandaloneAiCapability()) {
    if (!aiCandidates) return;
    aiCandidates.innerHTML = "";
    standaloneAiCandidates(capability).forEach((candidate) => {
      const row = document.createElement("li");
      if (candidate.recommended) row.classList.add("recommended");
      const title = document.createElement("strong");
      const detail = document.createElement("span");
      title.textContent = `${candidate.title} / ${candidate.status}`;
      detail.textContent = candidate.detail;
      row.append(title, detail);
      aiCandidates.appendChild(row);
    });
  }

  function renderAiEnginePlan(capability = detectStandaloneAiCapability()) {
    if (!aiEnginePlan) return;
    aiEnginePlan.innerHTML = "";
    standaloneAiEnginePlan(capability).forEach((candidate) => {
      const row = document.createElement("li");
      const title = document.createElement("strong");
      const detail = document.createElement("span");
      title.textContent = `${candidate.title} / ${candidate.status}`;
      detail.textContent = candidate.detail;
      row.append(title, detail);
      aiEnginePlan.appendChild(row);
    });
  }

  async function updateStorageDiagnostic() {
    if (!navigator.storage?.estimate || !aiDiagnostics) return;
    try {
      const estimate = await navigator.storage.estimate();
      const usedMb = Math.round(Number(estimate.usage || 0) / 1024 / 1024);
      const quotaMb = Math.round(Number(estimate.quota || 0) / 1024 / 1024);
      const row = document.createElement("li");
      const label = document.createElement("strong");
      const value = document.createElement("span");
      label.textContent = "保存容量";
      value.textContent = quotaMb ? `${usedMb}MB / ${quotaMb}MB` : "取得不可";
      row.append(label, value);
      aiDiagnostics.appendChild(row);
      return;
    } catch {
      // Storage quota is only diagnostic; keep the chat usable if unavailable.
    }
  }

  function render() {
    const messages = loadMessages();
    if (importSummary) importSummary.textContent = mobileImportSummary(messages).label;
    list.innerHTML = "";
    if (messages.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "まだチャットはありません。下の入力欄から送信できます。";
      list.appendChild(empty);
      return;
    }
    messages.forEach((message) => {
      const row = document.createElement("article");
      row.className = `message-row ${message.role === "assistant" ? "assistant" : "user"}`;
      const bubble = document.createElement("div");
      bubble.className = "message-bubble";
      const text = document.createElement("p");
      text.textContent = message.text;
      const meta = document.createElement("small");
      const roleLabel = message.role === "assistant" ? loadMobileCharacterProfile().name : "あなた";
      meta.textContent = `${roleLabel} / ${message.imported ? "取り込み済み" : "未取り込み"} / ${formatDate(message.createdAt)}`;
      bubble.append(text, meta);
      row.appendChild(bubble);
      list.appendChild(row);
    });
    list.lastElementChild?.scrollIntoView({ block: "end" });
  }

  async function sendMessage() {
    const text = String(input?.value || "").trim();
    if (!text) return;
    const now = new Date().toISOString();
    const idBase = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
    const messages = loadMessages();
    const contextBeforeReply = recentConversationContext(messages);
    messages.push({
      id: `${idBase}-user`,
      role: "user",
      text,
      createdAt: now,
      imported: false,
    });
    const assistantMessage = {
      id: `${idBase}-assistant`,
      role: "assistant",
      text: "考えています...",
      createdAt: new Date().toISOString(),
      imported: false,
    };
    messages.push(assistantMessage);
    saveMessages(messages);
    input.value = "";
    render();
    if (sendButton) sendButton.disabled = true;
    try {
      assistantMessage.text = await generateAssistantReply(text, contextBeforeReply);
    } catch (error) {
      console.warn("Mobile assistant reply failed", error);
      setAiLoadStatus("返信生成が完了しなかったため、スマホ内の会話フォールバックで返しました。", "error");
      assistantMessage.text = localConversationReply(text, contextBeforeReply);
    } finally {
      assistantMessage.createdAt = new Date().toISOString();
      saveMessages(messages);
      if (sendButton) sendButton.disabled = false;
      render();
    }
  }

  normalizeStoredWasmModel();
  if (document.querySelector("#mobile-app-version")) {
    document.querySelector("#mobile-app-version").textContent = `アプリ版 0.8.208 / スマホ版 ${MOBILE_BUILD_LABEL}`;
  }

  sendButton?.addEventListener("click", sendMessage);
  aiLoadButton?.addEventListener("click", () => {
    localStorage.setItem(AI_MODE_KEY, "wasm-experimental");
    if (aiModelSelect) localStorage.setItem(AI_MODEL_KEY, aiModelSelect.value || DEFAULT_WASM_EXPERIMENT_MODEL);
    renderAiStatus();
    loadTransformersPipeline().catch((error) => {
      console.warn("Transformers.js load failed", error);
      if (String(error?.message || error).includes("model_load_timeout")) {
        setAiLoadStatus("モデル読み込みが時間内に完了しませんでした。Qwen 0.5Bはこの端末では重すぎる可能性があります。チャットは会話フォールバックで続けます。", "error");
        return;
      }
      setAiLoadStatus("モデル読み込みに失敗しました。AIエラーを共有できます。チャットは会話フォールバックで続けます。", "error");
    });
  });
  aiErrorCopyButton?.addEventListener("click", copyAiLastError);
  aiModelSelect?.addEventListener("change", () => {
    localStorage.setItem(AI_MODEL_KEY, aiModelSelect.value || DEFAULT_WASM_EXPERIMENT_MODEL);
    resetTransformersModel();
    setAiLoadStatus("モデルを切り替えました。AIモデルを読み込むを押してください。");
    renderAiStatus();
  });
  aiModeSelect?.addEventListener("change", () => {
    localStorage.setItem(AI_MODE_KEY, aiModeSelect.value || "auto");
    renderAiStatus();
  });
  pcSaveButton?.addEventListener("click", savePcConnection);
  exportButton?.addEventListener("click", showExportPayload);
  sendPcButton?.addEventListener("click", sendChatToPc);
  markImportedButton?.addEventListener("click", markMessagesImported);
  clearButton?.addEventListener("click", clearMessages);
  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      sendMessage();
    }
  });

  if (!applyConnectionParams()) renderPcConnection();
  renderDesktopNotice();
  renderAiStatus();
  updateStorageDiagnostic();
  render();
})();
