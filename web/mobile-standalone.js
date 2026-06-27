(() => {
  const CHAT_STORAGE_KEY = "gemma4.mobileChat";
  const LEGACY_NOTES_KEY = "gemma4.mobileNotes";
  const AI_MODE_KEY = "gemma4.mobileAiMode";
  const PC_CONNECTION_KEY = "gemma4.mobilePcConnection";
  const pcHostInput = document.querySelector("#mobile-pc-host");
  const pcCodeInput = document.querySelector("#mobile-pc-code");
  const pcSaveButton = document.querySelector("#mobile-pc-save");
  const pcStatus = document.querySelector("#mobile-pc-status");
  const input = document.querySelector("#mobile-chat-input");
  const sendButton = document.querySelector("#mobile-chat-send");
  const exportButton = document.querySelector("#mobile-chat-export");
  const sendPcButton = document.querySelector("#mobile-chat-send-pc");
  const markImportedButton = document.querySelector("#mobile-chat-mark-imported");
  const clearButton = document.querySelector("#mobile-chat-clear");
  const exportOutput = document.querySelector("#mobile-chat-export-output");
  const list = document.querySelector("#mobile-chat-list");
  const aiStatus = document.querySelector("#mobile-ai-status");
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

  function renderPcConnection() {
    const connection = loadPcConnection();
    if (pcHostInput && connection.host) pcHostInput.value = connection.host;
    if (pcCodeInput && connection.pairingCode) pcCodeInput.value = connection.pairingCode;
    if (!pcStatus) return;
    pcStatus.textContent = connection.host
      ? `接続先: ${connection.host} / コード ${connection.pairingCode || "未入力"}`
      : "PC未接続";
  }

  function savePcConnection() {
    const host = normalizePcHost(pcHostInput?.value || "");
    const pairingCode = String(pcCodeInput?.value || "").replace(/\D/g, "").slice(0, 6);
    if (!host || pairingCode.length !== 6) {
      if (pcStatus) pcStatus.textContent = "PC URLと6桁コードを確認してください。";
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
    if (pcStatus) {
      pcStatus.textContent = `接続先を保存しました。PC: ${connection.host} / コード: ${connection.pairingCode}`;
    }
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
    if (pcStatus) {
      pcStatus.textContent = `QRから接続先を保存しました。PC: ${connection.host} / コード: ${connection.pairingCode}`;
    }
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
      if (pcStatus) pcStatus.textContent = "先にPC URLと6桁コードを保存してください。";
      return;
    }
    const payload = exportPayload();
    if (!payload.messages.some((message) => !message.imported)) {
      if (pcStatus) pcStatus.textContent = "未取り込みのチャットはありません。";
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
        throw new Error(result.error || `HTTP ${response.status}`);
      }
      markMessagesImported();
      if (pcStatus) pcStatus.textContent = `PCへ送信しました（${result.summary?.total || 0}件）`;
    } catch (error) {
      if (pcStatus) pcStatus.textContent = `PCへ送信できませんでした: ${error.message}`;
    }
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
    if (/勉強|学習|ノート|覚え/i.test(text)) {
      return "学習メモとして保存しました。あとでPCへ取り込む時に、学習ノートや記憶として整理できます。";
    }
    if (/キャラ|記憶|覚えて/i.test(text)) {
      return "キャラの記憶候補として保存しました。PC取り込み時に、キャラクター記憶へ追加できます。";
    }
    return "スマホ単体チャットに保存しました。今はAIなしの記録モードです。PCへ取り込むと、PC側のAIで続きを扱えます。";
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
    if (!aiStatus) return;
    const support = detectBrowserAiSupport();
    if (support.available) {
      aiStatus.textContent = `AI: ブラウザAI候補を検出 (${support.type})`;
      return;
    }
    aiStatus.textContent = "AI: 記録モード（このブラウザの軽量AIは未検出）";
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
  renderAiStatus();
  render();
})();
