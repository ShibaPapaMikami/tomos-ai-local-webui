# PWA Install Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** スマホでホーム画面追加できるPWAの最小土台を追加する。

**Architecture:** 既存の `web/` 静的配信に `manifest.webmanifest`、`sw.js`、`offline.html`、`pwa.js`、アイコンを追加する。既存アプリの動作を変えず、Service Workerは静的ファイルのキャッシュとオフライン時の最低限画面だけを担当する。

**Tech Stack:** HTML/CSS/JavaScript、Web App Manifest、Service Worker、既存Python静的サーバー。

---

### Task 1: PWA Asset Contract

**Files:**
- Create: `scripts/test-pwa-assets.js`
- Modify: `web/index.html`
- Create: `web/manifest.webmanifest`
- Create: `web/pwa.js`
- Create: `web/sw.js`
- Create: `web/offline.html`
- Create: `web/icons/icon.svg`
- Create: `web/icons/icon-192.png`
- Create: `web/icons/icon-512.png`

- [ ] **Step 1: Write the failing test**

Create `scripts/test-pwa-assets.js` that asserts:

```js
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
assert.equal(manifest.start_url, "/?source=pwa");
assert.ok(manifest.icons.some((icon) => icon.src === "/icons/icon-192.png" && icon.sizes === "192x192"));
assert.ok(manifest.icons.some((icon) => icon.src === "/icons/icon-512.png" && icon.sizes === "512x512"));

["web/pwa.js", "web/sw.js", "web/offline.html", "web/icons/icon.svg", "web/icons/icon-192.png", "web/icons/icon-512.png"].forEach((path) => {
  assert.ok(fs.existsSync(path), `${path} should exist`);
});

const sw = fs.readFileSync("web/sw.js", "utf8");
assert.match(sw, /offline\.html/);
assert.match(sw, /manifest\.webmanifest/);

console.log("pwa asset tests passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node scripts/test-pwa-assets.js`
Expected: FAIL because PWA files are not present.

- [ ] **Step 3: Add PWA files and index hooks**

Add manifest, Service Worker, offline page, registration script, and icons under `web/`. Update `web/index.html` head with manifest/meta/icon links and add `pwa.js` before `app.js`.

- [ ] **Step 4: Run verification**

Run:

```bash
node scripts/test-pwa-assets.js
node --check web/pwa.js
node --check web/sw.js
node scripts/test-mobile-css.js
node scripts/test-management-helpers.js
python3 -m py_compile server.py
git diff --check
```

Expected: all commands pass.
