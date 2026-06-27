(() => {
  const CHAT_STORAGE_KEY = "gemma4.mobileChat";
  const LEGACY_NOTES_KEY = "gemma4.mobileNotes";
  const AI_MODE_KEY = "gemma4.mobileAiMode";
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
  const aiDiagnostics = document.querySelector("#mobile-ai-diagnostics");
  const aiCandidates = document.querySelector("#mobile-ai-candidates");
  const importSummary = document.querySelector("#mobile-import-summary");

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
          status: "優先",
          detail: "WebGPU未検出のiPhone向け候補です。まず超小型/量子化モデルで返信速度を検証します。",
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

  async function generateAssistantReply(text) {
    const mode = localStorage.getItem(AI_MODE_KEY) || "auto";
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
    if (aiStatus) {
      aiStatus.textContent = `AI: ${capability.recommendation}`;
    }
    if (aiPlan) {
      aiPlan.textContent = capability.detail;
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
      const roleLabel = message.role === "assistant" ? "Gemma" : "あなた";
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
    assistantMessage.text = await generateAssistantReply(text);
    assistantMessage.createdAt = new Date().toISOString();
    saveMessages(messages);
    render();
  }

  sendButton?.addEventListener("click", sendMessage);
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
