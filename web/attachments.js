(function () {
  function attachmentKind(file) {
    const name = String(file?.name || "").toLowerCase();
    const type = String(file?.type || "").toLowerCase();
    if (type === "application/pdf" || name.endsWith(".pdf")) return "PDF";
    if (name.endsWith(".docx")) return "DOCX";
    if (type.startsWith("text/") || name.endsWith(".txt") || name.endsWith(".md")) return "TEXT";
    return "";
  }

  function supportedAttachmentFile(file) {
    return Boolean(attachmentKind(file));
  }

  async function readJsonResponse(response, fallbackMessage) {
    const raw = await response.text();
    if (!raw.trim()) return {};
    try {
      return JSON.parse(raw);
    } catch {
      const preview = raw.replace(/\s+/g, " ").slice(0, 120);
      throw new Error(preview ? `${fallbackMessage}: ${preview}` : fallbackMessage);
    }
  }

  async function extractAttachmentContents(files) {
    const results = [];
    for (const file of files) {
      try {
        const response = await fetch("/api/attachment/read", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: file.name,
            mime: file.mime || "",
            base64: file.base64,
          }),
        });
        const data = await readJsonResponse(response, "添付ファイルの読み取りに失敗しました");
        if (!response.ok || !data.ok) throw new Error(data.error || "Attachment read failed");
        results.push({
          name: data.name || file.name,
          kind: data.kind || file.kind,
          content: data.content || "",
          size: data.size || file.size || 0,
        });
      } catch (error) {
        results.push({
          name: file.name,
          kind: file.kind,
          content: "",
          error: String(error.message || "").includes("HTTP/")
            ? "添付ファイルの読み取りに失敗しました。アプリを再起動してもう一度お試しください。"
            : (error.message || "添付ファイルの読み取りに失敗しました"),
          size: file.size || 0,
        });
      }
    }
    return results;
  }

  function attachmentContextFromResults(results) {
    const usable = results.filter((item) => item.content && item.content.trim());
    const failed = results.filter((item) => item.error || !String(item.content || "").trim());
    const lines = [];
    if (usable.length > 0) {
      lines.push("添付ファイルの内容です。回答では、この内容を最優先の根拠として使ってください。本文にないことは作らないでください。");
      usable.forEach((item, index) => {
        lines.push(`\n[${index + 1}] ${item.name} (${item.kind || "file"})\n${item.content}`);
      });
    }
    if (failed.length > 0) {
      lines.push("\n読み取れなかった添付ファイル:");
      failed.forEach((item) => lines.push(`- ${item.name}: ${item.error || "本文を抽出できませんでした"}`));
    }
    return lines.join("\n").trim();
  }

  function isVagueAttachmentQuestion(text) {
    const normalized = String(text || "")
      .trim()
      .replace(/\s+/g, "")
      .replace(/[？?。.!！]+$/g, "");
    if (!normalized) return true;
    if (normalized.length > 18) return false;
    return /^(これ|これは|これ何|これは何|なにこれ|何これ|内容|概要|要約|説明して|教えて)$/.test(normalized);
  }

  function isAttachmentTranscriptRequest(text) {
    const normalized = String(text || "")
      .trim()
      .replace(/\s+/g, "");
    return /(文字起こし|書き起こし|全文|本文をそのまま|そのまま表示|原文|テキスト化|テキストにして)/i.test(normalized);
  }

  function messageWithAttachmentContext(message, attachmentContext) {
    if (!attachmentContext) return message;
    const question = String(message.content || "").trim();
    const instruction = isAttachmentTranscriptRequest(question)
      ? [
          "ユーザーは添付ファイルの文字起こしを求めています。",
          "要約せず、読み取れた本文をできるだけそのまま表示してください。",
          "本文にない補足や推測は追加しないでください。",
        ].join("\n")
      : isVagueAttachmentQuestion(question)
      ? [
          "ユーザーは添付ファイルについて短く質問しています。",
          "添付ファイルの種類、件名、主な内容、重要な点を日本語で簡潔に説明してください。",
          "キャラクターの名前・呼び方・口調は維持してください。",
          "本文にないことは作らないでください。",
        ].join("\n")
      : [
          "ユーザーは添付ファイルについて質問しています。",
          "添付ファイル本文を最優先の根拠として、質問に答えてください。",
          "キャラクターの名前・呼び方・口調は維持してください。",
          "本文にないことは作らないでください。",
        ].join("\n");
    return {
      ...message,
      content: `${instruction}\n\nユーザーの質問:\n${question || "添付ファイルの内容を教えて"}\n\n---\n${attachmentContext}`.trim(),
    };
  }

  function attachmentPreviewLines(content, limit = 5) {
    const seen = new Set();
    return String(content || "")
      .split(/\r?\n+/)
      .map((line) => line.replace(/\s+/g, " ").trim())
      .filter((line) => {
        if (!line || line.length < 6) return false;
        if (seen.has(line)) return false;
        seen.add(line);
        return true;
      })
      .slice(0, limit);
  }

  function attachmentSummarySources(results) {
    return (Array.isArray(results) ? results : [])
      .filter((item) => String(item.content || "").trim())
      .slice(0, 4)
      .map((item) => ({
        type: "attachment",
        title: item.name,
        path: item.name,
        line: "",
        snippet: attachmentPreviewLines(item.content, 2).join(" / ").slice(0, 180),
        sourceKind: String(item.kind || "file").toLowerCase(),
      }));
  }

  function attachmentAnswerLooksBroken(content) {
    const normalized = String(content || "").replace(/\s+/g, "").trim();
    if (!normalized) return true;
    if (normalized.length <= 8) return true;
    return /^(この|これ|提示|ご|はい|了解|わかりました)[。.!！]?$/.test(normalized);
  }

  function lastReadableAttachment(session) {
    const messages = Array.isArray(session?.messages) ? session.messages : [];
    for (let messageIndex = messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
      const attachments = Array.isArray(messages[messageIndex]?.attachments) ? messages[messageIndex].attachments : [];
      for (let attachmentIndex = attachments.length - 1; attachmentIndex >= 0; attachmentIndex -= 1) {
        const attachment = attachments[attachmentIndex];
        if (String(attachment?.content || "").trim()) return attachment;
      }
    }
    return null;
  }

  function lastAttachmentReference(session) {
    const messages = Array.isArray(session?.messages) ? session.messages : [];
    for (let messageIndex = messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
      const message = messages[messageIndex] || {};
      const attachments = Array.isArray(message.attachments) ? message.attachments : [];
      for (let attachmentIndex = attachments.length - 1; attachmentIndex >= 0; attachmentIndex -= 1) {
        const attachment = attachments[attachmentIndex];
        if (attachment?.name) return attachment;
      }
      const sources = Array.isArray(message.sources) ? message.sources : [];
      const attachmentSource = sources.find((source) => source?.type === "attachment" && source?.title);
      if (attachmentSource) {
        return {
          name: attachmentSource.title,
          kind: attachmentSource.sourceKind || "file",
          content: "",
        };
      }
    }
    return null;
  }

  function applyTone(text, options = {}) {
    return typeof options.toneReply === "function" ? options.toneReply(text) : text;
  }

  function directAttachmentAnswer(results, options = {}) {
    const usable = (Array.isArray(results) ? results : []).filter((item) => String(item.content || "").trim());
    if (!usable.length) return "";
    const item = usable[0];
    const lines = attachmentPreviewLines(item.content, 6);
    const kind = item.kind || attachmentKind(item) || "ファイル";
    const title = lines[0] || item.name;
    const detailLines = lines.slice(1, 5);
    const multiFileNote = usable.length > 1 ? `ほかにも${usable.length - 1}件の添付ファイルを読めるよ。\n` : "";
    const details = detailLines.length
      ? `\n\n本文の先頭から見ると、主な内容はこんな感じだよ。\n${detailLines.map((line) => `- ${line}`).join("\n")}`
      : "";
    return applyTone(
      `${kind}「${item.name}」を読んだよ。\n${multiFileNote}内容は「${title}」に関するファイルだよ。${details}`,
      options,
    );
  }

  function directAttachmentTranscriptAnswer(results, options = {}) {
    const usable = (Array.isArray(results) ? results : []).filter((item) => String(item.content || "").trim());
    if (!usable.length) return "";
    const item = usable[0];
    const limit = 18000;
    const compactContent = typeof options.compactContent === "function"
      ? options.compactContent
      : (value) => String(value || "");
    const text = compactContent(item.content || "");
    const truncated = text.length > limit;
    const body = truncated ? `${text.slice(0, limit).trim()}\n\n...（長いため先頭だけ表示しています）` : text;
    const multiFileNote = usable.length > 1 ? `\n\n※ ほかにも${usable.length - 1}件の添付ファイルがあります。` : "";
    return applyTone(
      `「${item.name}」を文字起こししたよ。\n\n${body}${multiFileNote}`,
      options,
    );
  }

  function unreadablePreviousAttachmentAnswer(attachment, options = {}) {
    const name = attachment?.name ? `「${attachment.name}」` : "その添付ファイル";
    return applyTone(
      `${name}は前の会話に表示されているけれど、本文データがこの履歴には残っていないよ。\n\n文字起こしするには、同じPDFをもう一度このチャットに添付して「文字起こしして」と送ってね。`,
      options,
    );
  }

  function isAttachmentFollowupRequest(text, options = {}) {
    const normalized = String(text || "").trim();
    if (!normalized) return false;
    if (typeof options.isCharacterPreference === "function" && options.isCharacterPreference(normalized)) return false;
    return isAttachmentTranscriptRequest(normalized)
      || isVagueAttachmentQuestion(normalized)
      || /(添付|PDF|ファイル|資料|文書|さっき|前回|これ|それ|この).{0,16}(内容|中身|本文|要約|説明|読んで|教えて|おしえて|文字起こし|全文|原文)/i.test(normalized)
      || /^(どんな内容|どんな中身|内容[は？?]*|中身[は？?]*|要約|要約して|読んで|見せて|何が書いて)/.test(normalized);
  }

  window.GEMMA_ATTACHMENTS = {
    attachmentKind,
    supportedAttachmentFile,
    extractAttachmentContents,
    attachmentContextFromResults,
    isVagueAttachmentQuestion,
    isAttachmentTranscriptRequest,
    messageWithAttachmentContext,
    attachmentPreviewLines,
    attachmentSummarySources,
    attachmentAnswerLooksBroken,
    lastReadableAttachment,
    lastAttachmentReference,
    directAttachmentAnswer,
    directAttachmentTranscriptAnswer,
    unreadablePreviousAttachmentAnswer,
    isAttachmentFollowupRequest,
  };
})();
