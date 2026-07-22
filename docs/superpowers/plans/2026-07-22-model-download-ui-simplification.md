# 言語モデル画面整理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 言語モデル画面をおすすめ3用途に絞り、内部モデル名と削除操作を迷わず確認でき、定期更新でも折りたたみ状態が維持されるようにする。

**Architecture:** `web/settings.js` の描画ヘルパー内でおすすめカード、不要モデル管理、開閉状態を一元管理する。サーバー側モデル分類、取得済みモデル、既存保存キーは変更せず、表示対象だけを整理する。

**Tech Stack:** Vanilla JavaScript、HTML details/summary、Node.js assertion tests、既存TOMOS CSS

## Global Constraints

- 通常画面には「標準AI」「コード作業」「高性能AI」の3用途だけを表示する。
- 各おすすめカードに内部モデル名を常時表示する。
- 「内部モデル名を確認」「詳細モデルを表示」「実験モデルを表示」は削除する。
- 取得済みの非推奨モデルだけ「不要なモデルを削除」に表示する。
- モデル本体、取得状態、`gemma4.*` 保存キーは変更しない。
- 自動アンインストール、再ダウンロード、サーバー分類変更は行わない。
- コミット、push、公開はディレクター確認後に行う。

---

### Task 1: 期待する表示をテストで固定する

**Files:**
- Modify: `scripts/test-settings-helpers.js`
- Test: `scripts/test-settings-helpers.js`

**Interfaces:**
- Consumes: `window.GEMMA_SETTINGS.renderModelInstaller(deps)`
- Produces: おすすめカード、内部モデル名、不要モデル管理、削除された詳細導線の回帰テスト

- [x] **Step 1: 失敗するテストを追加する**

`renderModelInstaller` の出力HTMLに対して次を検証する。

```js
assert.match(installerHtml, /標準AI/);
assert.match(installerHtml, /コード作業/);
assert.match(installerHtml, /高性能AI/);
assert.match(installerHtml, /内部モデル:/);
assert.doesNotMatch(installerHtml, /内部モデル名を確認/);
assert.doesNotMatch(installerHtml, /詳細モデルを表示/);
assert.doesNotMatch(installerHtml, /実験モデルを表示/);
assert.match(installerHtml, /不要なモデルを削除/);
```

- [x] **Step 2: テストが失敗することを確認する**

Run: `node scripts/test-settings-helpers.js`

Expected: 現在残っている3種類の折りたたみ文言、または内部モデル名不足でFAIL。

- [x] **Step 3: 既存互換性のテストを残す**

HauhauCS/Huihuiが通常候補へ出ないこと、取得済みの場合だけ削除対象に出ること、未取得なら出ないことを既存assertで維持する。

---

### Task 2: おすすめカードへ内部モデル名を統合する

**Files:**
- Modify: `web/settings.js:244-430`
- Test: `scripts/test-settings-helpers.js`

**Interfaces:**
- Consumes: `recommendedCards: Array<{ role, item, help }>`
- Produces: `renderModelRow({ ..., recommended: true })` 内の内部モデル名表示

- [x] **Step 1: おすすめカードに内部モデル名を追加する**

`renderModelRow` のおすすめカードへ次の補足を追加する。

```js
if (recommended) {
  const internalName = document.createElement("small");
  internalName.className = "model-internal-name";
  internalName.textContent = `${language === "en" ? "Internal model" : "内部モデル"}: ${item.label || modelId}`;
  info.append(internalName);
}
```

- [x] **Step 2: 内部モデル名専用detailsを削除する**

`internal-model-details` の生成ブロックを削除する。おすすめカードの取得・アンインストール操作は変更しない。

- [x] **Step 3: テストを実行する**

Run: `node scripts/test-settings-helpers.js`

Expected: 内部モデル名の表示テストがPASSし、他の表示整理テストは未実装分だけFAIL。

---

### Task 3: 詳細・実験導線を削除し不要モデル管理へ統合する

**Files:**
- Modify: `web/settings.js:300-370`
- Modify: `web/i18n.js:316,1329`
- Modify: `web/index.html:500`
- Test: `scripts/test-settings-helpers.js`

**Interfaces:**
- Consumes: `pullable`, `recommendedIds`, `modelIsInstalled(model)`
- Produces: `hiddenInstalledItems` を内容とする `details[data-model-details-key="unused-models"]`

- [x] **Step 1: 通常の詳細モデルと実験モデルを削除する**

`detailItems` と `experimentalItems` の描画ブロックを削除する。モデル定義や取得済み状態は削除しない。

- [x] **Step 2: 取得済みの非推奨モデルだけを集約する**

おすすめ3用途以外で、Enterpriseではなく、取得済みのモデルを削除候補にする。

```js
const unusedInstalledItems = pullable.filter((item) => (
  item?.model
  && !isEnterpriseModel(item)
  && !recommendedIds.has(item.model)
  && modelIsInstalled(item.model)
));
```

同じモデルIDは1件に重複排除し、summaryを「不要なモデルを削除」にする。行にはアンインストール操作だけを表示し、新規ダウンロード操作は表示しない。

- [x] **Step 3: 画面説明を更新する**

`management.languageModelsNote` を次へ変更する。

```text
普段は自動（おすすめ）のままで使えます。実際のモデル名は各AIの欄で確認できます。
```

- [x] **Step 4: テストを実行する**

Run: `node scripts/test-settings-helpers.js`

Expected: PASS。

---

### Task 4: 定期再描画で開閉状態を維持する

**Files:**
- Modify: `web/settings.js:196-370`
- Test: `scripts/test-settings-helpers.js`

**Interfaces:**
- Produces: `modelDetailsOpenState(container): Set<string>` と `restoreModelDetailsOpenState(container, openKeys): void`

- [x] **Step 1: 失敗する状態維持テストを追加する**

描画前に `details[data-model-details-key="unused-models"]` をopenにし、再描画後もopenであることを検証する。

- [x] **Step 2: テストが失敗することを確認する**

Run: `node scripts/test-settings-helpers.js`

Expected: 再描画後のdetailsが閉じてFAIL。

- [x] **Step 3: 開閉状態の保存と復元を実装する**

```js
function modelDetailsOpenState(container) {
  return new Set([...container.querySelectorAll("details[data-model-details-key][open]")]
    .map((details) => details.dataset.modelDetailsKey));
}

function restoreModelDetailsOpenState(container, openKeys) {
  for (const details of container.querySelectorAll("details[data-model-details-key]")) {
    details.open = openKeys.has(details.dataset.modelDetailsKey);
  }
}
```

`renderModelInstaller` の冒頭で取得し、描画完了後に復元する。

- [x] **Step 4: テストを実行する**

Run: `node scripts/test-settings-helpers.js`

Expected: PASS。

---

### Task 5: チャット候補と画面資産を検証する

**Files:**
- Verify: `web/settings.js:700-815`
- Modify: `web/styles.css:3196-3435`
- Test: `scripts/test-model-selection.js`
- Test: `scripts/test-pwa-assets.js`

**Interfaces:**
- Consumes: `composerModelCandidates`, `renderComposerModelVisibility`
- Produces: 自動、おすすめ3用途だけのチャット候補

- [x] **Step 1: チャット候補テストを確認する**

HauhauCS、Huihui、実験・Enterprise・非推奨モデルが候補に入らず、標準AI、コード作業、高性能AIだけが候補になることを確認する。既存フィルターで不足する場合は、保存値を削除せず候補生成だけを3用途へ限定する。

内部モデル名が長い場合もカード内で折り返すCSSを追加する。

```css
.model-internal-name {
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

- [x] **Step 2: 関連テストと構文確認を実行する**

```bash
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-training-export.js
node scripts/test-character-helpers.js
node scripts/test-pwa-assets.js
node --check web/settings.js
node --check web/app.js
git diff --check
```

Expected: すべてPASS。

- [x] **Step 3: PC幅とモバイル幅で手動確認する**

確認項目:

- おすすめ3用途だけが通常表示される
- 内部モデル名がカード内で折り返される
- 不要モデル管理を開いたまま12秒以上待っても閉じない
- 未取得の非推奨モデルが表示されない
- チャット欄に自動と取得済みおすすめ用途だけが表示される

- [x] **Step 4: ディレクター確認用の差分を報告する**

変更ファイル、テスト結果、手動確認結果、残課題を報告する。コミット、push、公開は行わない。
