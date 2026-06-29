(function () {
  const escapeHtml = window.GEMMA_UTILS?.escapeHtml || ((value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char])));

  const LANGUAGE_EXTENSIONS = {
    html: "html",
    css: "css",
    javascript: "js",
    js: "js",
    mjs: "mjs",
    typescript: "ts",
    ts: "ts",
    tsx: "tsx",
    jsx: "jsx",
    json: "json",
    python: "py",
    py: "py",
    markdown: "md",
    md: "md",
    svg: "svg",
    text: "txt",
    txt: "txt",
  };

  function workspaceFileKindLabel(kind) {
    const labels = {
      pdf: "PDF",
      word: "Word",
      text: "テキスト",
      html: "HTML",
      image: "画像",
    };
    return labels[kind] || kind;
  }

  function workspaceFormatBytes(bytes) {
    const value = Number(bytes);
    if (!Number.isFinite(value) || value <= 0) return "";
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
  }

  function workspaceFileMatchesKind(file, kind) {
    const path = String(file?.path || "");
    const fileKind = String(file?.kind || "").toLowerCase();
    const extension = path.split(".").pop()?.toLowerCase() || "";
    if (kind === "pdf") return fileKind === "pdf" || extension === "pdf";
    if (kind === "word") return fileKind === "word" || ["doc", "docx"].includes(extension);
    if (kind === "text") return fileKind === "text" || ["txt", "md"].includes(extension);
    if (kind === "html") return ["html", "htm"].includes(extension);
    if (kind === "image") return ["png", "jpg", "jpeg", "gif", "webp", "heic"].includes(extension);
    return false;
  }

  function workspaceFileKindFromText(text, options = {}) {
    const normalized = String(text || "").trim();
    const hasLookupIntent = options.hasLookupIntent || (() => true);
    const isExcludedRequest = options.isExcludedRequest || (() => false);
    if (!normalized || !hasLookupIntent(normalized)) return "";
    if (isExcludedRequest(normalized)) return "";
    const patterns = [
      { kind: "pdf", pattern: /\bpdf\b|ＰＤＦ|PDF|pdfファイル|PDFファイル/i },
      { kind: "word", pattern: /\bdocx?\b|ワード|word|Word|Wordファイル|文書ファイル/i },
      { kind: "text", pattern: /\btxt\b|テキスト|text|Text|txtファイル/i },
      { kind: "html", pattern: /\bhtml?\b|HTML|htmlファイル/i },
      { kind: "image", pattern: /\b(png|jpe?g|gif|webp|heic)\b|画像|写真/i },
    ];
    const asksExistence = /(ある|あります|入って|存在|含ま|一覧|どれ|どこ|探|検索|見つけ|情報|内容|中身|教えて|おしえて|説明|要約|読んで|file|find|search|contain|exist)/i.test(normalized);
    if (!asksExistence) return "";
    return patterns.find((item) => item.pattern.test(normalized))?.kind || "";
  }

  function compactWorkspaceContent(content) {
    return String(content || "")
      .replace(/\r/g, "")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function workspaceContentLines(content) {
    return compactWorkspaceContent(content)
      .split("\n")
      .map((line) => line.replace(/\s+/g, " ").trim())
      .filter(Boolean);
  }

  function isWorkspaceMetadataLine(line) {
    const text = String(line || "").trim();
    if (!text) return true;
    if (/^https?:\/\//i.test(text)) return true;
    if (/mail\.google\.com|permthid=|simpl=msg|view=pt/i.test(text)) return true;
    if (/^\f/.test(text)) return true;
    if (/^\d+\/\d+$/.test(text)) return true;
    if (/^(To|Cc|Bcc|From|件名|Subject):/i.test(text)) return true;
    if (/^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/.test(text)) return true;
    if (/<[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}>/.test(text)) return true;
    if (/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/.test(text) && text.length < 220) return true;
    if ((text.match(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g) || []).length >= 2) return true;
    if (/^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,} <[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}>/.test(text)) return true;
    if (/^[-–—]+$/.test(text)) return true;
    if (/^\d{4}\/\d{2}\/\d{1,2}\s+\d{1,2}:\d{2}/.test(text) && text.length < 90) return true;
    if (/^\d{4}\s*年?\s*\d{1,2}\s*月?\s*\d{1,2}\s*日?$/.test(text)) return true;
    if (/^[\d年月日:：\s]+$/.test(text)) return true;
    if (/^(facebook|Twitter|X|他、各種SNS|【東京オフィス】|【新潟本社|【フィリピン|【Tokyo Office】|【Niigata|【Manila)/i.test(text)) return true;
    if (/^(株式会社|代表取締役CEO|〒|\d+F|12F Jaka Bldg)/.test(text) && text.length < 90) return true;
    if (/添付.*\.(docx|pdf|xlsx|pptx)$/i.test(text)) return true;
    return false;
  }

  function meaningfulWorkspaceLines(content, options = {}) {
    const limit = Number(options.limit || 80);
    const lines = workspaceContentLines(content);
    return lines
      .filter((line) => !isWorkspaceMetadataLine(line))
      .filter((line) => line.length >= 3)
      .slice(0, limit);
  }

  function workspaceContentTranscript(content, options = {}) {
    const limit = Number(options.limit || 5000);
    const lineLimit = Number(options.lineLimit || 200);
    const withNotice = options.withNotice !== false;
    const lines = meaningfulWorkspaceLines(content, { limit: lineLimit });
    const transcript = lines.join("\n");
    if (transcript) {
      return transcript.length > limit
        ? `${transcript.slice(0, limit).trim()}${withNotice ? "\n\n...（長いため先頭だけ表示しています）" : ""}`
        : transcript;
    }
    const fallback = compactWorkspaceContent(content);
    return fallback.length > limit
      ? `${fallback.slice(0, limit).trim()}${withNotice ? "\n\n...（長いため先頭だけ表示しています）" : ""}`
      : fallback;
  }

  function workspaceTranscriptSavePath(path) {
    const value = String(path || "transcript.pdf").trim() || "transcript.pdf";
    const slashIndex = value.lastIndexOf("/");
    const directory = slashIndex >= 0 ? value.slice(0, slashIndex + 1) : "";
    const filename = slashIndex >= 0 ? value.slice(slashIndex + 1) : value;
    const dotIndex = filename.lastIndexOf(".");
    const basename = dotIndex > 0 ? filename.slice(0, dotIndex) : filename;
    return `${directory}${basename}_文字起こし.txt`;
  }

  function workspaceTranscriptAction({ root, path, content } = {}) {
    const transcript = workspaceContentTranscript(content || "", {
      limit: 50000,
      lineLimit: 2000,
      withNotice: false,
    }).trim();
    if (!root || !path || !transcript) return null;
    return {
      root,
      sourcePath: path,
      savePath: workspaceTranscriptSavePath(path),
      content: transcript,
    };
  }

  function renderWorkspacePreviewContent(target, content, activeLine = "") {
    if (!target) return;
    const targetLine = Number(activeLine);
    const lines = String(content || "").split(/\r?\n/);
    target.innerHTML = lines.map((line, index) => {
      const lineNumber = index + 1;
      const activeClass = Number.isFinite(targetLine) && targetLine === lineNumber ? " active" : "";
      return `<span class="workspace-preview-line${activeClass}" data-line="${lineNumber}"><span class="workspace-preview-line-number">${lineNumber}</span><span class="workspace-preview-line-text">${escapeHtml(line || " ")}</span></span>`;
    }).join("");
    if (Number.isFinite(targetLine)) {
      window.requestAnimationFrame(() => {
        target.querySelector(".workspace-preview-line.active")?.scrollIntoView({ block: "center" });
      });
    }
  }

  function updateWorkspacePreviewSearch({
    contentTarget,
    searchInput,
    countTarget,
    previousButton,
    nextButton,
    state,
    t,
    jump = false,
    direction = 0,
  } = {}) {
    if (!contentTarget || !searchInput || !state) return;
    const translate = typeof t === "function" ? t : (key) => key;
    const query = searchInput.value.trim().toLowerCase();
    const rows = [...contentTarget.querySelectorAll(".workspace-preview-line")];
    const matches = [];
    for (const row of rows) {
      const text = row.textContent.toLowerCase();
      const matched = Boolean(query && text.includes(query));
      row.classList.toggle("match", matched);
      row.classList.remove("current-match");
      if (matched) matches.push(row);
    }
    if (matches.length === 0) {
      state.workspacePreviewSearchIndex = 0;
    } else if (direction) {
      state.workspacePreviewSearchIndex = (state.workspacePreviewSearchIndex + direction + matches.length) % matches.length;
    } else {
      state.workspacePreviewSearchIndex = Math.min(state.workspacePreviewSearchIndex, matches.length - 1);
    }
    const current = matches[state.workspacePreviewSearchIndex] || null;
    current?.classList.add("current-match");
    if (countTarget) {
      countTarget.textContent = query && matches.length
        ? translate("workspace.previewSearchPosition", { current: state.workspacePreviewSearchIndex + 1, count: matches.length })
        : query
          ? translate("workspace.previewSearchCount", { count: 0 })
          : "";
    }
    if (previousButton) previousButton.disabled = matches.length === 0;
    if (nextButton) nextButton.disabled = matches.length === 0;
    if (jump && current) {
      current.scrollIntoView({ block: "center" });
    }
  }

  function workspaceContentTitle(lines) {
    const title = lines.find((line) => (
      /について|ご相談|お願い|報告|資料|契約書|請求書|仕様書/.test(line)
      && line.length >= 8
      && line.length <= 120
    ));
    const fallback = title || lines.find((line) => line.length >= 8 && line.length <= 120) || "";
    return fallback
      .replace(/^\d{4}\/\d{2}\/\d{2}\s+\d{1,2}:\d{2}\s*/g, "")
      .replace(/^Gugenka®?\s+メール\s*-\s*/i, "")
      .replace(/\s{2,}/g, " ")
      .trim();
  }

  function pickWorkspaceSentences(lines) {
    const text = lines.join("\n");
    const sentences = text
      .replace(/\n+/g, "。")
      .split(/(?<=[。！？!?])\s*/)
      .map((sentence) => sentence.replace(/\s+/g, " ").trim())
      .filter((sentence) => sentence.length >= 12 && sentence.length <= 180)
      .filter((sentence) => !isWorkspaceMetadataLine(sentence));
    const priority = [
      /相談|お願い|依頼|確認/,
      /遅延|懸念|リスク|問題|影響/,
      /サーバー|構成|進捗|提案|対応|巻き返し/,
      /返信|回答|すすめて|進めて|確認の上/,
    ];
    const picked = [];
    priority.forEach((pattern) => {
      const found = sentences.find((sentence) => pattern.test(sentence) && !picked.includes(sentence));
      if (found) picked.push(found);
    });
    sentences.forEach((sentence) => {
      if (picked.length < 5 && !picked.includes(sentence)) picked.push(sentence);
    });
    return picked.slice(0, 5);
  }

  function workspaceContentSummary(content) {
    const text = compactWorkspaceContent(content);
    if (!text) return "";
    const lines = meaningfulWorkspaceLines(text);
    if (lines.length) {
      const title = workspaceContentTitle(lines);
      const sentences = pickWorkspaceSentences(lines);
      const output = [];
      if (title) output.push(`概要: ${title}`);
      if (sentences.length) {
        output.push("主な内容:");
        sentences.forEach((sentence) => output.push(`- ${sentence}`));
      }
      const summary = output.join("\n");
      if (summary.trim()) return summary.length > 1400 ? `${summary.slice(0, 1400).trim()}...` : summary;
    }
    const paragraphs = text
      .split(/\n\s*\n/)
      .map((item) => item.replace(/\s+/g, " ").trim())
      .filter(Boolean);
    const picked = paragraphs.slice(0, 4).join("\n\n");
    const fallback = text.replace(/\s+/g, " ").slice(0, 1200).trim();
    const summary = picked || fallback;
    return summary.length > 1400 ? `${summary.slice(0, 1400).trim()}...` : summary;
  }

  function cleanCandidatePath(path) {
    return path
      .replace(/^\.?\//, "")
      .replace(/[)、。,:：;；\]\[)"'」』]+$/g, "")
      .trim();
  }

  function pathFromText(text) {
    const pattern = /(?:^|[\s`"'「『(（])([A-Za-z0-9_.\/-]+\.(?:html|css|js|mjs|ts|tsx|jsx|json|md|py|txt|svg))/gi;
    let match = pattern.exec(text);
    let candidate = "";
    while (match) {
      candidate = cleanCandidatePath(match[1]);
      match = pattern.exec(text);
    }
    return candidate;
  }

  function parseCodeFenceInfo(info) {
    const parts = info.trim().split(/\s+/).filter(Boolean);
    let language = "";
    let path = "";
    for (const part of parts) {
      const cleaned = cleanCandidatePath(part);
      if (!path && /\.[a-z0-9]+$/i.test(cleaned)) {
        path = cleaned;
        continue;
      }
      if (!language && LANGUAGE_EXTENSIONS[cleaned.toLowerCase()]) {
        language = cleaned.toLowerCase();
      }
    }
    return { language, path };
  }

  function splitLeadingPathFromContent(content) {
    const normalized = content.replace(/^\s+/, "");
    const lineBreak = normalized.indexOf("\n");
    if (lineBreak < 0) return { path: "", content };
    const firstLine = cleanCandidatePath(normalized.slice(0, lineBreak));
    if (!/\.[a-z0-9]+$/i.test(firstLine)) return { path: "", content };
    return {
      path: firstLine,
      content: normalized.slice(lineBreak + 1).replace(/^\s+/, ""),
    };
  }

  function extractCodeBlocks(text) {
    const blocks = [];
    const pattern = /```([^\n`]*)\n([\s\S]*?)```/g;
    let match = pattern.exec(text);
    let completedEnd = 0;
    while (match) {
      const info = parseCodeFenceInfo(match[1]);
      const before = text.slice(Math.max(0, match.index - 240), match.index);
      const split = splitLeadingPathFromContent(match[2]);
      blocks.push({
        language: info.language,
        path: info.path || pathFromText(before) || split.path,
        content: split.content.trim(),
        complete: true,
      });
      completedEnd = pattern.lastIndex;
      match = pattern.exec(text);
    }
    const lastFence = text.indexOf("```", completedEnd);
    if (lastFence >= 0) {
      const afterFence = text.slice(lastFence + 3);
      const firstBreak = afterFence.indexOf("\n");
      if (firstBreak >= 0) {
        const info = parseCodeFenceInfo(afterFence.slice(0, firstBreak));
        const before = text.slice(Math.max(0, lastFence - 240), lastFence);
        const split = splitLeadingPathFromContent(afterFence.slice(firstBreak + 1));
        blocks.push({
          language: info.language,
          path: info.path || pathFromText(before) || split.path,
          content: split.content.trim(),
          complete: false,
        });
      }
    }
    return blocks;
  }

  function inferSavePath({ commandText, assistantText, codeBlock, currentPath = "" }) {
    if (currentPath) return currentPath;
    if (codeBlock.path) return codeBlock.path;

    const combined = `${commandText}\n${assistantText}`;
    const explicit = pathFromText(combined);
    if (explicit) return explicit;

    const language = codeBlock.language;
    const content = codeBlock.content.trimStart();
    if (language === "html" || content.startsWith("<!doctype html") || content.startsWith("<html")) return "index.html";
    if (language === "css") return "styles.css";
    if (language === "javascript" || language === "js") return "app.js";
    if (language === "python" || language === "py") return "main.py";
    if (language === "json") return "data.json";
    return "";
  }

  function uniquePath(path, usedPaths) {
    if (!usedPaths.has(path)) return path;
    const dot = path.lastIndexOf(".");
    const base = dot >= 0 ? path.slice(0, dot) : path;
    const ext = dot >= 0 ? path.slice(dot) : "";
    let index = 2;
    let candidate = `${base}-${index}${ext}`;
    while (usedPaths.has(candidate)) {
      index += 1;
      candidate = `${base}-${index}${ext}`;
    }
    return candidate;
  }

  function isSaveCommand(text) {
    const normalized = String(text || "").trim().toLowerCase();
    return /保存|書き込|ファイルにして|作成して|反映して|save|write/.test(normalized);
  }

  function inferSimpleTextSave({ text, hasWorkspace }) {
    if (!hasWorkspace || !isSaveCommand(text)) return null;
    if (/プログラム|アプリ|ゲーム|html|javascript|コード|サイト|web/i.test(text)) return null;
    const contentMatch = text.match(/[「『"']([^「」『』"']{1,500})[」』"']\s*(?:と|を)?\s*(?:記載|書い|入力|保存)/)
      || text.match(/[A-Za-z0-9_.\/-]+\.(?:txt|text|md)\s*に\s*([^「」『』"'\n]{1,200}?)\s*(?:と|を)?\s*(?:記載|書い|入力|保存)/i)
      || text.match(/(.{1,200}?)\s*という\s*(?:テキスト|txt|text|メモ|markdown|md)?\s*ファイル(?:を|に)?[^。.!！？\n]{0,80}?(?:保存|作成|つくって|作って)/i)
      || text.match(/(?:フォルダ(?:ー)?に|ファイルに)?\s*([A-Za-z0-9ぁ-んァ-ヶ一-龠ー、。,.!?！？\s]{1,200}?)\s*(?:と|を)?\s*(?:記載|書い|入力)(?:された|した|して)?/);
    if (!contentMatch) return null;
    const content = contentMatch[1].trim();
    if (!content || content.length > 500) return null;
    let path = "";
    const pathMatch = text.match(/([A-Za-z0-9_.\/-]+\.(?:txt|text|md))/i);
    if (pathMatch) {
      path = cleanCandidatePath(pathMatch[1]).replace(/\.text$/i, ".txt");
    }
    if (!path || path === ".txt" || path === ".text") {
      const safeName = content
        .normalize("NFKC")
        .replace(/[\\/:*?"<>|#%&{}$!'@+`=\s]+/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, 40);
      path = `${safeName || "memo"}.txt`;
    }
    return { path, content: `${content}\n` };
  }

  function lastAssistantMessage(session) {
    for (let index = session.messages.length - 1; index >= 0; index -= 1) {
      if (session.messages[index].role === "assistant") {
        return session.messages[index];
      }
    }
    return null;
  }

  function previewSources({ root, files, label = "Preview" }) {
    if (!root) return [];
    return files
      .filter((file) => /\.html?$/i.test(file.path))
      .map((file) => ({
        type: "preview",
        title: `${label}: ${file.path}`,
        url: `/api/workspace/preview?root=${encodeURIComponent(root)}&path=${encodeURIComponent(file.path)}`,
      }));
  }

  function extractJsonObject(text) {
    const trimmed = String(text || "").trim().replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
    const first = trimmed.indexOf("{");
    const last = trimmed.lastIndexOf("}");
    if (first < 0 || last <= first) {
      throw new Error("GemmaがJSONを返しませんでした。");
    }
    const candidate = trimmed.slice(first, last + 1);
    try {
      return JSON.parse(candidate);
    } catch (error) {
      const repaired = candidate
        .replace(/([{,]\s*)([A-Za-z_$][\w$-]*)(\s*:)/g, '$1"$2"$3')
        .replace(/,\s*([}\]])/g, "$1");
      try {
        return JSON.parse(repaired);
      } catch {
        throw error;
      }
    }
  }

  function normalizeGeneratedFiles(payload) {
    if (!payload || !Array.isArray(payload.files)) {
      throw new Error("GemmaのJSONにfiles配列がありません。");
    }
    const files = payload.files
      .map((file) => ({
        path: cleanCandidatePath(String(file.path || "")),
        content: String(file.content || ""),
      }))
      .filter((file) => file.path && file.content.trim());
    if (files.length === 0) {
      throw new Error("保存できるファイルが生成されませんでした。");
    }
    return files;
  }

  function extractFilesFromCodeBlocks(text) {
    const files = [];
    const pattern = /(?:^|\n)\s*([A-Za-z0-9_.\/-]+\.[A-Za-z0-9]+)\s*\n```[A-Za-z0-9_-]*\n([\s\S]*?)```/g;
    let match;
    while ((match = pattern.exec(String(text || ""))) !== null) {
      const path = cleanCandidatePath(match[1]);
      const content = match[2].replace(/\s+$/g, "\n");
      if (path && content.trim()) files.push({ path, content });
    }
    if (files.length === 0) {
      throw new Error("保存できるコードブロックが見つかりませんでした。");
    }
    return {
      summary: "コードブロックからファイルを生成しました。",
      notes: ["JSONが不完全な場合は、コードブロック形式から保存します。"],
      files,
    };
  }

  function parseWorkspaceGeneration(text) {
    try {
      const payload = extractJsonObject(text);
      return {
        summary: String(payload.summary || "生成しました。"),
        notes: Array.isArray(payload.notes) ? payload.notes.map(String) : [],
        files: normalizeGeneratedFiles(payload),
      };
    } catch (jsonError) {
      try {
        return extractFilesFromCodeBlocks(text);
      } catch {
        throw new Error(`生成結果を読み取れませんでした: ${jsonError.message}`);
      }
    }
  }

  function normalizeWorkspacePlan(payload) {
    const fallback = {
      summary: "index.html に自己完結のWebアプリを作成します。",
      files: [{ path: "index.html", purpose: "CSSとJavaScriptを含む完成版のHTML" }],
    };
    if (!payload || !Array.isArray(payload.files)) return fallback;
    const files = payload.files
      .slice(0, 3)
      .map((file) => ({
        path: cleanCandidatePath(String(file.path || "")),
        purpose: String(file.purpose || "このファイルを実装します。").trim(),
      }))
      .filter((file) => file.path);
    if (files.length === 0) return fallback;
    return {
      summary: String(payload.summary || "段階的にファイルを生成します。").trim(),
      files,
    };
  }

  async function postWorkspaceJson(endpoint, payload) {
    let response;
    try {
      response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      throw new Error(`ローカルサーバーに接続できませんでした。起動ファイルで再起動してください: ${error.message || error}`);
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      const detail = data.error || `${response.status} ${response.statusText}`.trim();
      throw new Error(detail || "ローカルサーバーがエラーを返しました。");
    }
    return data;
  }

  function pickFolder() {
    return postWorkspaceJson("/api/workspace/pick", {});
  }

  function loadTree(root) {
    return postWorkspaceJson("/api/workspace/tree", { root });
  }

  function writeFile({ root, path, content }) {
    return postWorkspaceJson("/api/workspace/write", { root, path, content });
  }

  function revealPath({ root, path }) {
    return postWorkspaceJson("/api/workspace/reveal", { root, path });
  }

  async function validateFiles({ root, files }) {
    const response = await fetch("/api/workspace/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root, files }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "");
    }
    return data;
  }

  function prepareCodegraph({ root }) {
    return postWorkspaceJson("/api/workspace/codegraph/init", { root });
  }

  function readCodegraph({ root }) {
    return postWorkspaceJson("/api/workspace/codegraph/read", { root });
  }

  function searchWorkspace({ root, query }) {
    return postWorkspaceJson("/api/workspace/search", { root, query });
  }

  function formatCodegraphFiles({ summary, t }) {
    const files = Array.isArray(summary?.files) ? summary.files.slice(0, 8) : [];
    if (files.length === 0) {
      return `<small>${escapeHtml(t("workspace.codeUnderstandingNoFiles"))}</small>`;
    }
    const rows = files.map((file) => {
      const symbols = Array.isArray(file.symbols) && file.symbols.length > 0
        ? ` / ${escapeHtml(file.symbols.slice(0, 3).join(", "))}`
        : "";
      return `<li><span>${escapeHtml(file.path || "")}</span><small>${escapeHtml(file.language || "Code")}${symbols}</small></li>`;
    }).join("");
    const more = Number(summary?.stats?.files || files.length) > files.length
      ? `<small>${escapeHtml(t("workspace.codeUnderstandingMore", { count: Number(summary.stats.files) - files.length }))}</small>`
      : "";
    return `<strong>${escapeHtml(t("workspace.codeUnderstandingFiles"))}</strong><ul>${rows}</ul>${more}`;
  }

  function codegraphStatusText({ folder, t }) {
    const codegraph = folder?.plugins?.codegraph || {};
    if (!codegraph.enabled) return t("workspace.codeUnderstandingOff");
    if (codegraph.status === "ready") {
      return t("workspace.codeUnderstandingReady", { files: codegraph.files || 0 });
    }
    if (codegraph.status === "error") {
      return t("workspace.codeUnderstandingError", { error: codegraph.error || "" });
    }
    if (codegraph.status === "running") return t("workspace.codeUnderstandingPreparing");
    return t("workspace.codeUnderstandingNotReady");
  }

  function searchCapabilityText({ state, t }) {
    const capabilities = state.appInfo?.searchCapabilities || {};
    const parts = [];
    if (capabilities.text) parts.push(t("settings.searchText"));
    if (capabilities.docx) parts.push(t("settings.searchWord"));
    if (capabilities.pdf) {
      parts.push(t("settings.searchPdfReady", { backend: capabilities.pdfBackend || "PDF" }));
    } else if (capabilities.filenameFallback) {
      parts.push(t("workspace.searchPdfFilenameOnlyShort"));
    }
    if (capabilities.imageOcr) {
      parts.push(t("settings.searchImageOcr"));
    } else {
      parts.push(t("workspace.searchImageOcrUnsupported"));
    }
    return t("workspace.searchCapabilitiesSummary", { capabilities: parts.join(" / ") });
  }

  function formatSearchResults({ data, t }) {
    const results = Array.isArray(data?.results) ? data.results : [];
    if (results.length === 0) {
      return `<small>${escapeHtml(t("workspace.searchNoResults"))}</small>`;
    }
    const rows = results.slice(0, 20).map((item) => {
      const path = escapeHtml(item.path || "");
      const line = escapeHtml(item.line || "");
      const preview = escapeHtml(item.preview || "");
      const label = line ? `${path}:${line}` : path;
      const sourceKind = String(item.sourceKind || "text").toLowerCase();
      const sourceLabel = sourceKind === "pdf"
        ? t("workspace.searchSourcePdf")
        : sourceKind === "docx"
          ? t("workspace.searchSourceWord")
          : sourceKind === "html"
            ? t("workspace.searchSourceHtml")
            : t("workspace.searchSourceText");
      const matchLabel = item.matchType === "filename"
        ? t("workspace.searchMatchFilename")
        : t("workspace.searchMatchBody");
      return `<li><button type="button" data-workspace-search-path="${path}" data-workspace-search-line="${line}"><span>${label}</span><span class="workspace-search-badges"><em>${escapeHtml(sourceLabel)}</em><em>${escapeHtml(matchLabel)}</em></span><small>${preview}</small></button></li>`;
    }).join("");
    const more = results.length > 20
      ? `<small>${escapeHtml(t("workspace.searchMore", { count: results.length - 20 }))}</small>`
      : "";
    const pdfUnreadable = Number(data?.pdfUnreadable || 0);
    const pdfNote = pdfUnreadable > 0
      ? `<small class="workspace-search-note">${escapeHtml(t("workspace.searchPdfUnreadable", {
        count: pdfUnreadable,
        backend: data?.pdfBackend || "PDF",
      }))}</small>`
      : "";
    return `<ul>${rows}</ul>${more}${pdfNote}`;
  }

  function renderWorkspacePanel({ activeFolder, els, onFileSelectionChange, state, t }) {
    els.workspacePanel.hidden = !state.workspaceOpen;
    els.workspaceFolderName.textContent = activeFolder?.name || t("workspace.noFolder");
    els.workspaceFolderTitle.value = activeFolder?.name || "";
    els.workspaceRoot.value = state.workspaceRoot;
    const codegraphInstalled = Boolean(state.plugins?.codegraph?.installed);
    if (els.workspaceCodegraphRow) {
      els.workspaceCodegraphRow.hidden = !codegraphInstalled;
    }
    if (els.workspaceCodegraphEnabled) {
      els.workspaceCodegraphEnabled.checked = Boolean(activeFolder?.plugins?.codegraph?.enabled);
    }
    if (els.workspaceCodegraphPrepare) {
      els.workspaceCodegraphPrepare.disabled = !codegraphInstalled || !state.workspaceRoot || !activeFolder?.plugins?.codegraph?.enabled;
    }
    if (els.workspaceCodegraphStatus) {
      els.workspaceCodegraphStatus.textContent = codegraphStatusText({ folder: activeFolder, t });
    }
    if (els.workspaceCodegraphFiles) {
      const summary = activeFolder?.plugins?.codegraph?.summary;
      els.workspaceCodegraphFiles.hidden = !summary || activeFolder?.plugins?.codegraph?.status !== "ready";
      els.workspaceCodegraphFiles.innerHTML = summary ? formatCodegraphFiles({ summary, t }) : "";
    }
    const fastSearchInstalled = Boolean(state.plugins?.["fast-search"]?.installed);
    if (els.workspaceSearchRow) {
      els.workspaceSearchRow.hidden = !fastSearchInstalled;
    }
    if (els.workspaceSearchStatus && fastSearchInstalled && !els.workspaceSearchStatus.dataset.searchState) {
      els.workspaceSearchStatus.textContent = searchCapabilityText({ state, t });
    }
    const selectedCount = state.selectedFiles.size;
    const fileCount = state.workspaceFiles.length;
    if (!state.workspaceRoot) {
      els.workspaceStatus.textContent = t("workspace.notConfigured", { name: activeFolder?.name || t("sidebar.folderButton") });
    } else if (state.workspaceNote) {
      els.workspaceStatus.textContent = state.workspaceNote;
    } else {
      els.workspaceStatus.textContent = t("workspace.loaded", { name: activeFolder?.name || t("sidebar.folderButton"), files: fileCount, selected: selectedCount });
    }
    els.workspaceFiles.innerHTML = "";
    for (const file of state.workspaceFiles) {
      const selectable = Boolean(file.text);
      const kind = String(file.kind || "").toLowerCase();
      const typeLabel = kind === "pdf"
        ? " / PDF本文"
        : kind === "docx"
          ? " / Word本文"
          : selectable
            ? ""
            : t("workspace.binary");
      const row = document.createElement("label");
      row.className = `workspace-file${selectable ? "" : " disabled"}`;
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.disabled = !selectable;
      checkbox.checked = state.selectedFiles.has(file.path);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          state.selectedFiles.add(file.path);
        } else {
          state.selectedFiles.delete(file.path);
        }
        onFileSelectionChange();
      });
      const name = document.createElement("span");
      name.textContent = file.path;
      const meta = document.createElement("small");
      meta.textContent = `${Math.ceil(file.size / 1024)} KB${typeLabel}`;
      row.append(checkbox, name, meta);
      els.workspaceFiles.append(row);
    }
  }

  async function pickFolderAction({
    els,
    state,
    t,
    onSaveWorkspacePrefs,
    onLoadWorkspace,
  } = {}) {
    els.workspaceStatus.textContent = t("workspace.waitingPick");
    try {
      const data = await pickFolder();
      state.workspaceRoot = data.root;
      els.workspaceRoot.value = data.root;
      state.selectedFiles = new Set();
      onSaveWorkspacePrefs?.();
      await onLoadWorkspace?.();
    } catch (error) {
      const fallback = state.language === "en" ? "Could not choose folder." : "フォルダー選択に失敗しました";
      els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message || fallback}`;
    }
  }

  async function loadWorkspaceAction({
    els,
    state,
    t,
    onSaveWorkspacePrefs,
    onRender,
  } = {}) {
    const root = els.workspaceRoot.value.trim();
    if (!root) return;
    els.workspaceStatus.textContent = t("workspace.loading");
    try {
      const data = await loadTree(root);
      state.workspaceRoot = data.root;
      state.workspaceFiles = data.files || [];
      if (state.workspaceFiles.length === 0) {
        state.workspaceNote = t("workspace.empty");
      } else if (data.truncated) {
        state.workspaceNote = state.language === "en"
          ? `Showing ${state.workspaceFiles.length} files. Some were omitted because there are many files.`
          : `${state.workspaceFiles.length}件を表示中です。件数が多いため一部を省略しました。`;
      } else {
        state.workspaceNote = "";
      }
      state.selectedFiles = new Set([...state.selectedFiles].filter((path) => state.workspaceFiles.some((file) => file.path === path)));
      onSaveWorkspacePrefs?.();
      onRender?.();
    } catch (error) {
      const fallback = state.language === "en" ? "Could not load folder." : "フォルダーを読み込めませんでした";
      els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message || fallback}`;
    }
  }

  async function saveWorkspaceFileAction({
    els,
    state,
    t,
    onLoadWorkspace,
  } = {}) {
    const root = state.workspaceRoot;
    const path = els.writePath.value.trim();
    const content = els.writeContent.value;
    if (!root || !path) {
      els.workspaceStatus.textContent = state.language === "en"
        ? "Choose a folder and enter a relative path first."
        : "先にフォルダーを選択し、相対パスを入力してください。";
      return;
    }
    try {
      const data = await writeFile({ root, path, content });
      els.workspaceStatus.textContent = t("workspace.saved", { path: data.path, size: data.size });
      await onLoadWorkspace?.();
    } catch (error) {
      const fallback = state.language === "en" ? "Could not save file." : "ファイルを保存できませんでした";
      els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message || fallback}`;
    }
  }

  async function revealWorkspacePathAction({ els, state, t } = {}) {
    const root = state.workspaceRoot;
    const path = els.writePath.value.trim();
    if (!root) {
      els.workspaceStatus.textContent = state.language === "en"
        ? "Choose a folder first."
        : "先にフォルダーを選択してください。";
      return;
    }
    try {
      const data = await revealPath({ root, path });
      els.workspaceStatus.textContent = t("workspace.revealed", { path: data.path || root });
    } catch (error) {
      const fallback = state.language === "en" ? "Could not open the folder." : "フォルダーを開けませんでした";
      els.workspaceStatus.textContent = `${t("error.prefix")}: ${error.message || fallback}`;
    }
  }

  async function searchWorkspaceAction({ els, state, t } = {}) {
    const root = state.workspaceRoot;
    const query = els.workspaceSearchQuery?.value.trim() || "";
    if (!root) {
      if (els.workspaceSearchStatus) els.workspaceSearchStatus.textContent = t("workspace.searchPickFolder");
      return;
    }
    if (!query) {
      if (els.workspaceSearchStatus) els.workspaceSearchStatus.textContent = t("workspace.searchEmptyQuery");
      return;
    }
    if (els.workspaceSearchStatus) els.workspaceSearchStatus.textContent = t("workspace.searching");
    if (els.workspaceSearchStatus) els.workspaceSearchStatus.dataset.searchState = "searching";
    if (els.workspaceSearchResults) {
      els.workspaceSearchResults.hidden = true;
      els.workspaceSearchResults.innerHTML = "";
    }
    try {
      const data = await searchWorkspace({ root, query });
      if (els.workspaceSearchStatus) {
        els.workspaceSearchStatus.textContent = t("workspace.searchDone", {
          count: Array.isArray(data.results) ? data.results.length : 0,
          scanned: data.scanned || 0,
        });
        els.workspaceSearchStatus.dataset.searchState = "done";
      }
      if (els.workspaceSearchResults) {
        els.workspaceSearchResults.hidden = false;
        els.workspaceSearchResults.innerHTML = formatSearchResults({ data, t });
      }
    } catch (error) {
      const fallback = state.language === "en" ? "Could not search this folder." : "フォルダー内検索に失敗しました";
      if (els.workspaceSearchStatus) {
        els.workspaceSearchStatus.textContent = `${t("error.prefix")}: ${error.message || fallback}`;
        els.workspaceSearchStatus.dataset.searchState = "error";
      }
    }
  }

  window.GEMMA_WORKSPACE = {
    cleanCandidatePath,
    compactWorkspaceContent,
    extractCodeBlocks,
    extractFilesFromCodeBlocks,
    extractJsonObject,
    formatSearchResults,
    inferSavePath,
    inferSimpleTextSave,
    isSaveCommand,
    lastAssistantMessage,
    loadTree,
    normalizeGeneratedFiles,
    normalizeWorkspacePlan,
    parseWorkspaceGeneration,
    pathFromText,
    pickFolder,
    previewSources,
    prepareCodegraph,
    pickFolderAction,
    renderWorkspacePreviewContent,
    renderWorkspacePanel,
    revealPath,
    readCodegraph,
    revealWorkspacePathAction,
    loadWorkspaceAction,
    saveWorkspaceFileAction,
    searchWorkspace,
    searchWorkspaceAction,
    uniquePath,
    updateWorkspacePreviewSearch,
    validateFiles,
    workspaceContentSummary,
    workspaceContentTranscript,
    workspaceFileKindLabel,
    workspaceFileKindFromText,
    workspaceFileMatchesKind,
    workspaceFormatBytes,
    workspaceTranscriptAction,
    workspaceTranscriptSavePath,
    writeFile,
  };
})();
