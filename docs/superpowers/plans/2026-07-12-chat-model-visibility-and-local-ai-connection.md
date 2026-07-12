# チャットモデル表示とローカルAI接続 実装計画

> **作業エージェント向け:** `superpowers:subagent-driven-development`（推奨）または `superpowers:executing-plans` を使用し、各作業をチェック単位で実行する。

**目的:** チャット欄へ表示するモデルの選択状態を明確にし、別のローカルAIへ接続する上級設定を学生にも誤解なく伝える。

**構成:** 既存の `web/settings.js` を表示候補とチェック状態の正とし、`web/app.js` のローカルストレージ保存後に同じ表示を再描画する。接続処理は既存の `/api/llm/check` とlocalhost制限を維持し、`web/index.html` と `web/i18n.js` の名称・説明・状態表示だけを学生向けに整理する。

**技術:** JavaScript、HTML、CSS、Python標準ライブラリ、Node.jsテスト、Python unittest形式テスト

## 全体制約

- 新しい依存関係を追加しない。
- Agent-Reach本体、外部API、SNS、Cookie、外部書き込みを変更しない。
- 接続先は `localhost`、`127.0.0.1`、`::1` に限定する。
- OpenAI互換APIは追加しない。
- 既存の `gemma4.composerModelVisibleModels` と `gemma4.externalLlmUrl` を維持する。
- 通常のTOMOS利用者は追加設定なしで標準Ollamaを使える状態を維持する。

---

### Task 1: モデル表示チェックを保存状態と一致させる

**ファイル:**
- 変更: `scripts/test-settings-helpers.js:145-175`
- 変更: `web/settings.js:557-584`
- 変更: `web/styles.css:3284-3304`

**境界:**
- 入力: `state.composerModelVisibleModels: string[]` と候補モデル一覧
- 出力: 保存済みモデルだけが `checked` と `is-selected` を持つチェック一覧

- [ ] **手順1: 保存状態を検証する失敗テストを書く**

`scripts/test-settings-helpers.js` の既存チェック表示テストを次の検証へ拡張する。

```js
const checkedVisibilityHtml = composerVisibilityEl.innerHTML;
assert.match(checkedVisibilityHtml, /data-composer-model-visible="qwen2\.5:3b" checked/);
assert.doesNotMatch(checkedVisibilityHtml, new RegExp(`data-composer-model-visible="${agenticCoder.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}" checked`));
assert.match(checkedVisibilityHtml, /class="is-selected"/);

const defaultVisibilityEl = new FakeElement("section");
renderComposerModelVisibility({
  composerModelLabel: (model) => model,
  els: { composerModelVisibility: defaultVisibilityEl },
  models: ["qwen2.5:3b", agenticCoder],
  state: { language: "ja", composerModelVisibleModels: [] },
});
assert.equal((defaultVisibilityEl.innerHTML.match(/ checked/g) || []).length, 2);
```

- [ ] **手順2: テストが失敗することを確認する**

実行: `node scripts/test-settings-helpers.js`

期待: `class="is-selected"` の検証で失敗する。

- [ ] **手順3: チェック済み行を明確に描画する**

`web/settings.js` の一覧生成を次の形に変更する。

```js
${uniqueModels.map((model) => {
  const isSelected = selected.has(model);
  return `
    <label class="${isSelected ? "is-selected" : ""}">
      <input type="checkbox" data-composer-model-visible="${model}" ${isSelected ? "checked" : ""} />
      <span>${composerModelLabel(model)}</span>
    </label>
  `;
}).join("")}
```

`web/styles.css` にチェック済み行の視認性を追加する。

```css
.composer-model-visibility-list label.is-selected {
  color: var(--text);
}

.composer-model-visibility-list label.is-selected span {
  font-weight: 800;
}
```

- [ ] **手順4: モデル表示テストを通す**

実行: `node scripts/test-settings-helpers.js`

期待: 終了コード0。

- [ ] **手順5: 作業1をコミットする**

```bash
git add scripts/test-settings-helpers.js web/settings.js web/styles.css
git commit -m "モデル表示の選択状態を明確にする"
```

---

### Task 2: ローカルAI接続画面を学生向けに整理する

**ファイル:**
- 変更: `scripts/test-model-selection.js:240-260`
- 変更: `web/index.html:120-180`
- 変更: `web/index.html:495-525`
- 変更: `web/i18n.js:657-684`
- 変更: `web/i18n.js:1633-1660`
- 変更: `web/styles.css` のローカルAI接続欄

**境界:**
- 入力: 言語設定と既存の接続先URL
- 出力: 「別のローカルAIを使う」タブ、標準状態、折りたたみ式詳細設定

- [ ] **手順1: 新しい名称と詳細設定を検証する失敗テストを書く**

`scripts/test-model-selection.js` に次を追加する。

```js
const indexHtml = fs.readFileSync("web/index.html", "utf8");
const i18nSource = fs.readFileSync("web/i18n.js", "utf8");
assert.match(indexHtml, /別のローカルAIを使う/);
assert.match(indexHtml, /<details class="external-llm-details">/);
assert.match(indexHtml, /TOMOS標準のローカルAIを使用中/);
assert.match(i18nSource, /"settings\.externalLlmTitle": "別のローカルAIを使う"/);
assert.match(i18nSource, /"settings\.externalLlmClear": "標準に戻す"/);
assert.doesNotMatch(indexHtml, />外部LLMサーバー接続</);
```

- [ ] **手順2: テストが失敗することを確認する**

実行: `node scripts/test-model-selection.js`

期待: 新名称が未実装のため失敗する。

- [ ] **手順3: 見出し、説明、詳細設定を変更する**

`web/index.html` の接続欄を次の構造へ変更する。

```html
<section class="external-llm-panel" id="external-llm-settings" aria-label="別のローカルAIを使う" data-i18n-aria-label="settings.externalLlmTitle">
  <div class="model-installer-title">
    <strong data-i18n="settings.externalLlmTitle">別のローカルAIを使う</strong>
    <span data-i18n="settings.externalLlmHelp">通常は設定不要です。このPCで別に起動しているOllamaやllama.cppをTOMOSで使う場合だけ設定します。</span>
  </div>
  <p class="external-llm-current" id="external-llm-status" data-i18n="settings.externalLlmStandard">TOMOS標準のローカルAIを使用中</p>
  <details class="external-llm-details">
    <summary data-i18n="settings.externalLlmDetails">詳細設定</summary>
    <label class="setting-field setting-wide">
      <span data-i18n="settings.externalLlmUrl">このPC内の接続先</span>
      <input id="external-llm-url" type="url" placeholder="http://127.0.0.1:8080" />
      <small data-i18n="settings.externalLlmUrlHelp">このPC内のlocalhostだけを使えます。空欄ならTOMOS標準のローカルAIを使います。</small>
    </label>
    <div class="external-llm-actions">
      <button class="ghost-button" id="external-llm-check" type="button" data-i18n="settings.externalLlmCheck">接続を確認</button>
      <button class="ghost-button" id="external-llm-clear" type="button" data-i18n="settings.externalLlmClear">標準に戻す</button>
    </div>
  </details>
</section>
```

既存の接続例と実験モデル案内は `details` の内側に残し、機能を削除しない。

- [ ] **手順4: 日本語と英語の表示文を更新する**

`web/i18n.js` に次のキーと対応する英語を定義する。

```js
"settings.externalLlmTitle": "別のローカルAIを使う",
"settings.externalLlmHelp": "通常は設定不要です。このPCで別に起動しているOllamaやllama.cppをTOMOSで使う場合だけ設定します。",
"settings.externalLlmStandard": "TOMOS標準のローカルAIを使用中",
"settings.externalLlmDetails": "詳細設定",
"settings.externalLlmUrl": "このPC内の接続先",
"settings.externalLlmUrlHelp": "このPC内のlocalhostだけを使えます。空欄ならTOMOS標準のローカルAIを使います。",
"settings.externalLlmClear": "標準に戻す",
```

- [ ] **手順5: 折りたたみ表示を既存UIへ合わせる**

`web/styles.css` に次を追加する。

```css
.external-llm-current {
  margin: 0;
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
}

.external-llm-details {
  border-top: 1px solid var(--line);
  padding-top: 8px;
}

.external-llm-details summary {
  cursor: pointer;
  color: var(--text);
  font-size: 12px;
  font-weight: 800;
}
```

- [ ] **手順6: 表示テストを通す**

実行: `node scripts/test-model-selection.js`

期待: 終了コード0。

- [ ] **手順7: 作業2をコミットする**

```bash
git add scripts/test-model-selection.js web/index.html web/i18n.js web/styles.css
git commit -m "ローカルAI接続画面を分かりやすくする"
```

---

### Task 3: 接続状態と標準復帰を検証する

**ファイル:**
- 変更: `scripts/test-model-selection.js`
- 変更: `web/app.js:2085-2150`

**境界:**
- 入力: `state.externalLlmUrl` と `/api/llm/check` の結果
- 出力: 標準使用中、確認待ち、接続済み、接続失敗の状態表示

- [ ] **手順1: 接続状態文言とlocalhost制限のテストを追加する**

`scripts/test-model-selection.js` に次を追加する。

```js
assert.match(i18nSource, /"settings\.externalLlmStandard": "TOMOS標準のローカルAIを使用中"/);
assert.match(i18nSource, /"settings\.externalLlmSaved": "設定を保存しました。接続を確認してください。"/);
assert.match(i18nSource, /"settings\.externalLlmError": "接続できませんでした。別のローカルAIがこのPCで起動しているか確認してください。"/);
```

- [ ] **手順2: テストが失敗することを確認する**

実行: `node scripts/test-model-selection.js`

期待: 新しい状態文言の検証で失敗する。

- [ ] **手順3: 標準状態と接続状態を描画する**

`web/app.js` の `renderExternalLlmSettings` を次の状態優先度に変更する。

```js
function renderExternalLlmSettings(message = "") {
  if (els.externalLlmUrl) els.externalLlmUrl.value = state.externalLlmUrl || "";
  if (!els.externalLlmStatus) return;
  els.externalLlmStatus.textContent = message
    || state.externalLlmStatus
    || (state.externalLlmUrl ? t("settings.externalLlmSaved") : t("settings.externalLlmStandard"));
}
```

`clearExternalLlmSettings` はURLと状態を消した後、標準状態を表示する。

```js
function clearExternalLlmSettings() {
  state.externalLlmUrl = "";
  localStorage.removeItem("gemma4.externalLlmUrl");
  state.externalLlmStatus = t("settings.externalLlmStandard");
  renderExternalLlmSettings();
}
```

- [ ] **手順4: 接続状態とサーバーテストを通す**

実行:

```bash
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
python3 scripts/test_server_helpers.py
python3 -m py_compile server.py
git diff --check
```

期待: すべて終了コード0。

- [ ] **手順5: PC幅とスマホ幅を手動確認する**

確認項目:

```text
PC: チェック済みモデル、標準状態、詳細設定の開閉が重ならない
スマホ: 見出し、説明、ボタン、URLが横にはみ出さない
標準状態: 詳細設定を開かなくても追加操作が不要だと分かる
別接続状態: 接続確認後にバージョンとモデル件数が表示される
```

- [ ] **手順6: 作業3をコミットする**

```bash
git add scripts/test-model-selection.js web/app.js
git commit -m "ローカルAIの接続状態を明確にする"
```

---

## 最終確認

- [ ] `git status --short --branch` で意図した変更だけを確認する。
- [ ] `git diff --check` を実行する。
- [ ] Node.jsの2テストとPythonの1テストを再実行する。
- [ ] バージョン更新や配布は、実装確認後に別作業として承認を得る。
