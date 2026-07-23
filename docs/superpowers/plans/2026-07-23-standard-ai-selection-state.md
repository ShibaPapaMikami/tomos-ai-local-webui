# Standard AI Selection State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 標準AIが未導入でも選択状態を保持し、既存のダウンロード画面へ案内する。

**Architecture:** 表示用途`composerPurpose`と実モデルID`composerModel`を分離する。設定UIは用途を表示し、実行時は既存ルーターが導入済みモデルを解決する。

**Tech Stack:** Vanilla JavaScript、localStorage、Node.jsテスト

## Global Constraints

- Qwen 2.5 3Bを標準AIへ自動選択しない。
- 新しい依存関係を追加しない。
- 既存の言語モデル画面とダウンロード処理を再利用する。

---

### Task 1: 選択状態の保持

**Files:**
- Modify: `scripts/test-settings-helpers.js`
- Modify: `web/settings.js`
- Modify: `web/app.js`

**Interfaces:**
- Consumes: `renderComposerPurposeSelect()`、`setComposerPurpose()`
- Produces: `state.composerPurpose`、localStorageキー`gemma4.composerPurpose`

- [ ] **Step 1: Write the failing test**

`renderComposerPurposeSelect()`へ`selectedPurpose: "standard"`を渡し、モデル未導入でもselect値が`standard`になることを検証する。

- [ ] **Step 2: Run test to verify it fails**

Run: `node scripts/test-settings-helpers.js`

Expected: `standard`ではなく`auto`となりFAIL。

- [ ] **Step 3: Write minimal implementation**

`renderComposerPurposeSelect()`が明示用途を優先し、`app.js`が用途を保存する。標準AI未導入時は`languageModelsPanel`を開く。

- [ ] **Step 4: Run tests**

Run:

```sh
node scripts/test-settings-helpers.js
node scripts/test-model-selection.js
node --check web/settings.js
node --check web/app.js
git diff --check
```

Expected: 全件PASS。

- [ ] **Step 5: Commit**

ユーザーのGitHub反映承認後に対象ファイルをコミットする。
