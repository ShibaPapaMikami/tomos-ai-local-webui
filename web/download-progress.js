(() => {
  const DONE_VISIBLE_MS = 5000;

  function normalizeDownloadJob(job = {}) {
    const value = job.percent === null || job.percent === undefined || job.percent === ""
      ? Number.NaN
      : Number(job.percent);
    const percent = Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : null;
    return {
      id: String(job.id || ""),
      kind: String(job.kind || ""),
      label: String(job.label || ""),
      status: String(job.status || ""),
      percent,
      indeterminate: percent === null && ["queued", "running"].includes(String(job.status || "")),
      completedBytes: Math.max(0, Number(job.completedBytes) || 0),
      totalBytes: Math.max(0, Number(job.totalBytes) || 0),
      message: String(job.message || ""),
      startedAt: job.startedAt ?? null,
      finishedAt: job.finishedAt ?? null,
      retryAction: job.retryAction || null,
    };
  }

  function visibleDownloadJobs(jobs = [], now = Date.now()) {
    return jobs
      .map(normalizeDownloadJob)
      .filter((job) => {
        if (job.status === "error") return true;
        if (job.status !== "done") return ["queued", "running"].includes(job.status);
        return job.finishedAt && now - Number(job.finishedAt) * 1000 <= DONE_VISIBLE_MS;
      });
  }

  function formatDownloadBytes(bytes) {
    const value = Math.max(0, Number(bytes) || 0);
    if (value >= 1000 ** 3) return `${(value / 1000 ** 3).toFixed(1)} GB`;
    if (value >= 1000 ** 2) return `${(value / 1000 ** 2).toFixed(1)} MB`;
    if (value >= 1000) return `${Math.round(value / 1000)} KB`;
    return `${value} B`;
  }

  function renderDownloadPanel(root, jobs = [], now = Date.now()) {
    if (!root) return;
    const list = root.querySelector("[data-download-list]");
    if (!list) return;
    const visible = visibleDownloadJobs(jobs, now);
    root.hidden = visible.length === 0;
    list.innerHTML = "";
    visible.forEach((job) => {
      const item = document.createElement("section");
      item.className = "global-download-item";
      item.dataset.status = job.status;
      const heading = document.createElement("div");
      heading.className = "global-download-heading";
      const label = document.createElement("strong");
      label.textContent = job.label || "ダウンロード";
      const value = document.createElement("span");
      value.textContent = job.percent === null
        ? (job.status === "error" ? "エラー" : job.status === "done" ? "完了" : "処理中")
        : `${job.percent}%`;
      heading.append(label, value);
      const track = document.createElement("div");
      track.className = `global-download-track${job.indeterminate ? " is-indeterminate" : ""}`;
      track.setAttribute("role", "progressbar");
      track.setAttribute("aria-label", job.label || "ダウンロード");
      track.setAttribute("aria-valuemin", "0");
      track.setAttribute("aria-valuemax", "100");
      if (job.percent !== null) track.setAttribute("aria-valuenow", String(job.percent));
      const bar = document.createElement("span");
      if (job.percent !== null) bar.style.width = `${job.percent}%`;
      track.append(bar);
      const detail = document.createElement("small");
      const size = job.completedBytes && job.totalBytes
        ? `${formatDownloadBytes(job.completedBytes)} / ${formatDownloadBytes(job.totalBytes)}`
        : "";
      detail.textContent = [job.message, size].filter(Boolean).join(" ");
      item.append(heading, track, detail);
      if (job.status === "error" && job.retryAction) {
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "ghost-button global-download-retry";
        retry.dataset.downloadRetry = JSON.stringify(job.retryAction);
        retry.textContent = "再試行";
        item.append(retry);
      }
      list.append(item);
    });
  }

  function retryEndpoint(action = {}) {
    if (action.type === "model") return ["/api/models/pull", { model: action.id }];
    if (action.type === "asr") return ["/api/asr/setup", null];
    if (action.type === "ocr") return ["/api/ocr/setup", null];
    if (action.type === "internet-layer") return ["/api/internet-layer/setup", null];
    if (action.type === "study-pack") return ["/api/study-packs/note-article/install", null];
    return null;
  }

  function createDownloadMonitor({
    root,
    onJobs = () => {},
    fetchImpl = window.fetch.bind(window),
    intervalMs = 1500,
  } = {}) {
    let jobs = [];
    let timer = null;
    async function refresh() {
      try {
        const response = await fetchImpl("/api/downloads/status", { cache: "no-store" });
        const payload = await response.json();
        if (!response.ok || payload.ok === false) return;
        jobs = Array.isArray(payload.jobs) ? payload.jobs.map(normalizeDownloadJob) : [];
        renderDownloadPanel(root, jobs);
        onJobs(jobs);
      } catch {
        // The normal health indicator reports server connectivity.
      }
    }
    async function retry(action) {
      const target = retryEndpoint(action);
      if (!target) return;
      const [url, body] = target;
      await fetchImpl(url, {
        method: "POST",
        ...(body ? {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        } : {}),
      });
      await refresh();
    }
    root?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-download-retry]");
      if (!button) return;
      try {
        retry(JSON.parse(button.dataset.downloadRetry || "{}"));
      } catch {
        // Ignore malformed local UI data.
      }
    });
    refresh();
    timer = window.setInterval(refresh, intervalMs);
    return {
      refresh,
      stop() {
        if (timer) window.clearInterval(timer);
        timer = null;
      },
    };
  }

  window.GEMMA_DOWNLOADS = {
    DONE_VISIBLE_MS,
    createDownloadMonitor,
    formatDownloadBytes,
    normalizeDownloadJob,
    renderDownloadPanel,
    retryEndpoint,
    visibleDownloadJobs,
  };
})();
