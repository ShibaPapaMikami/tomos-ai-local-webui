const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const context = { window: {}, console, setTimeout, clearTimeout };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/download-progress.js", "utf8"), context, {
  filename: "web/download-progress.js",
});

const {
  normalizeDownloadJob,
  visibleDownloadJobs,
  formatDownloadBytes,
} = context.window.GEMMA_DOWNLOADS;

const running = normalizeDownloadJob({
  id: "model:qwen",
  kind: "model",
  label: "標準AI",
  status: "running",
  percent: 42.4,
  completedBytes: 2100000000,
  totalBytes: 5000000000,
});
assert.equal(running.percent, 42);
assert.equal(running.indeterminate, false);
assert.equal(formatDownloadBytes(running.completedBytes), "2.1 GB");

const unknown = normalizeDownloadJob({ id: "asr:setup", status: "running", percent: null });
assert.equal(unknown.percent, null);
assert.equal(unknown.indeterminate, true);

const now = 100000;
const visible = visibleDownloadJobs([
  { id: "running", status: "running" },
  { id: "recent", status: "done", finishedAt: (now - 4000) / 1000 },
  { id: "old", status: "done", finishedAt: (now - 6000) / 1000 },
  { id: "error", status: "error", finishedAt: 1 },
], now);
assert.deepEqual(Array.from(visible, (job) => job.id), ["running", "recent", "error"]);

console.log("download progress tests passed");
