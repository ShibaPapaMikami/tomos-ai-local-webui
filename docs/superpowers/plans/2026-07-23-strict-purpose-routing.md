# Strict Purpose Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 明示用途では別用途モデルへ代替せず、自動選択だけに代替を限定する。

**Architecture:** `modelForPurpose()`を厳密な用途解決器にし、`modelForRequestTask()`は保存中の`composerPurpose`を最優先する。未導入時は空モデルを返し、UIが用途別案内を表示する。

**Tech Stack:** Vanilla JavaScript、localStorage、Node.jsテスト

## Global Constraints

- 新しい依存関係を追加しない。
- Qwen 2.5 3Bを自動選択しない。
- 既存のモデルダウンロード画面を再利用する。

---

### Task 1: 用途解決を厳密化

**Files:**
- Modify: `web/models.js`
- Modify: `scripts/test-model-selection.js`

**Interfaces:**
- Consumes: `gemmaModelForPurpose()`、`gemmaModelForRequestTask()`
- Produces: 明示用途と同一用途モデル、または空文字

- [x] **Step 1: Write failing tests**

Gemmaのみの環境で標準AIが空、Qwen3のみの環境でコード作業が空になることを検証する。

- [x] **Step 2: Verify failure**

Run: `node scripts/test-model-selection.js`

Expected: GemmaまたはQwen3へ代替してFAIL。

- [x] **Step 3: Implement strict routing**

`standard`、`coding`、`high-performance`ごとに同一用途の導入済みモデルだけを返す。`composerPurpose`が明示されているリクエストではこの結果をそのまま使う。

- [x] **Step 4: Verify**

Run: `node scripts/test-model-selection.js`

Expected: PASS。

### Task 2: 汎用ダウンロード案内

**Files:**
- Modify: `web/app.js`
- Modify: `web/settings.js`
- Modify: `web/i18n.js`
- Modify: `scripts/test-settings-helpers.js`

**Interfaces:**
- Consumes: `state.composerPurpose`
- Produces: 用途別の言語モデル画面と未導入メッセージ

- [x] **Step 1: Write failing tests**

未導入の全明示用途が選択可能で、用途別メッセージが存在することを検証する。

- [x] **Step 2: Implement generic guidance**

明示用途でモデルが空なら言語モデル画面を開く。送信時は選択用途に対応する案内文を表示する。

- [x] **Step 3: Run regression tests**

Run:

```sh
node scripts/test-settings-helpers.js
node scripts/test-model-selection.js
node scripts/test-pwa-assets.js
node --check web/models.js
node --check web/settings.js
node --check web/app.js
git diff --check
```

Expected: 全件PASS。

- [x] **Step 4: Commit**

ユーザーのGitHub反映承認後にコミットする。
