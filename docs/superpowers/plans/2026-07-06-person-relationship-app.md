# Person Relationship App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TOMOSに、友達・恋愛・家族・仕事の人物情報を登録し、相性メモと送り先別返信支援に使える `人物・関係メモ` アプリを追加する。

**Architecture:** 人物データはブラウザ内の純粋ロジック `web/person-relationship.js` に閉じ、UIは既存の管理パネル構造へ追加する。チャット返信支援では、選択した送り先の必要最小限の人物メモだけをsystem promptへ加える。Discord、LINE、Slack、メール連携は後段プラグインが参照するだけにし、このタスクでは外部送信しない。

**Tech Stack:** Vanilla JavaScript、localStorage、既存 `web/index.html` 管理パネル、既存 `web/app.js` state、Node.js helper tests。

---

## File Structure

- Create: `web/person-relationship.js`
  - 人物プロフィール、関係カテゴリ、返信支援文脈の純粋関数を提供する。
- Create: `scripts/test-person-relationship-helpers.js`
  - localStorageなしの正規化、保存、削除、返信支援文脈生成を検証する。
- Modify: `web/index.html`
  - 左メニュー、人物・関係メモパネル、チャット送り先セレクト、script読み込みを追加する。
- Modify: `web/app.js`
  - DOM参照、state、レンダリング、保存、送り先文脈のsystem prompt接続を追加する。
- Modify: `web/management.js`
  - `openManagementPanel` 対象に人物・関係メモパネルを追加する。
- Modify: `web/i18n.js`
  - 日本語/英語キーを追加する。
- Modify: `web/styles.css`
  - 人物カード、写真、関係バッジ、返信支援セレクトを既存管理UIに合わせて追加する。
- Modify: `web/sw.js`
  - `person-relationship.js` をPWAキャッシュ対象に追加する。
- Modify: `scripts/test-management-helpers.js`
  - パネル表示とscript読み込みの静的検証を追加する。
- Modify: `scripts/test-pwa-assets.js`
  - Service WorkerとHTML読み込みの検証を追加する。

## Task 1: Pure Person Relationship Module

**Files:**
- Create: `web/person-relationship.js`
- Create: `scripts/test-person-relationship-helpers.js`

- [ ] **Step 1: Write the failing test**

Add `scripts/test-person-relationship-helpers.js`:

```js
const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const storage = new Map();
const context = {
  window: {},
  localStorage: {
    getItem: (key) => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, String(value)),
  },
  crypto: { randomUUID: () => "person-fixed-id" },
  Date,
  console,
};

vm.createContext(context);
vm.runInContext(fs.readFileSync("web/person-relationship.js", "utf8"), context, { filename: "web/person-relationship.js" });

const api = context.window.GEMMA_PERSON_RELATIONSHIP;
assert.ok(api);
assert.deepEqual(api.relationshipCategories().map((item) => item.id), ["friend", "romantic", "family", "work"]);

const person = api.normalizePerson({
  name: "佐藤さん",
  nickname: "さと",
  relationshipCategory: "friend",
  personalityType: "ENFP",
  personalityTypeSource: "user_reported",
  likes: "映画",
  dislikes: "長文",
  conversationNotes: "短く明るく返す",
});

assert.equal(person.id, "person-fixed-id");
assert.equal(person.name, "佐藤さん");
assert.equal(person.relationshipCategory, "friend");
assert.equal(person.personalityTypeLabel, "性格タイプ: ENFP");
assert.equal(person.personalityTypeSource, "user_reported");

const saved = api.savePeople([person], context.localStorage);
assert.equal(saved.length, 1);
assert.equal(api.loadPeople(context.localStorage)[0].name, "佐藤さん");

const prompt = api.buildRecipientContextPrompt(person);
assert.match(prompt, /送り先: 佐藤さん/);
assert.match(prompt, /関係: 友達/);
assert.match(prompt, /会話の注意点: 短く明るく返す/);
assert.doesNotMatch(prompt, /血液型/);

const removed = api.deletePerson(saved, person.id);
assert.equal(removed.length, 0);

console.log("person relationship helper tests passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node scripts/test-person-relationship-helpers.js
```

Expected: FAIL because `web/person-relationship.js` does not exist.

- [ ] **Step 3: Implement the module**

Create `web/person-relationship.js` with these exported functions on `window.GEMMA_PERSON_RELATIONSHIP`:

```js
(() => {
  const STORAGE_KEY = "gemma4.personRelationship.people.v1";
  const CATEGORIES = [
    { id: "friend", label: "友達" },
    { id: "romantic", label: "恋愛" },
    { id: "family", label: "家族" },
    { id: "work", label: "仕事" },
  ];
  const TYPE_SOURCES = ["self_reported", "user_reported", "estimated", "unknown"];

  const text = (value) => String(value || "").trim();
  const nowIso = () => new Date().toISOString();
  const newId = () => globalThis.crypto?.randomUUID?.() || `person-${Date.now()}`;

  function relationshipCategories() {
    return CATEGORIES.map((item) => ({ ...item }));
  }

  function categoryLabel(id) {
    return CATEGORIES.find((item) => item.id === id)?.label || "友達";
  }

  function normalizePerson(input = {}) {
    const relationshipCategory = CATEGORIES.some((item) => item.id === input.relationshipCategory)
      ? input.relationshipCategory
      : "friend";
    const personalityType = text(input.personalityType).toUpperCase();
    const personalityTypeSource = TYPE_SOURCES.includes(input.personalityTypeSource)
      ? input.personalityTypeSource
      : "unknown";
    const createdAt = text(input.createdAt) || nowIso();
    const updatedAt = nowIso();
    return {
      id: text(input.id) || newId(),
      name: text(input.name) || "名前未設定",
      nickname: text(input.nickname),
      photo: text(input.photo),
      relationshipCategory,
      age: text(input.age),
      gender: text(input.gender),
      bloodType: text(input.bloodType),
      personalityType,
      personalityTypeSource,
      personalityTypeLabel: personalityType ? `性格タイプ: ${personalityType}` : "",
      likes: text(input.likes),
      dislikes: text(input.dislikes),
      conversationNotes: text(input.conversationNotes),
      relationshipMemo: text(input.relationshipMemo),
      createdAt,
      updatedAt,
      scopeType: text(input.scopeType) || "user",
      deletedAt: text(input.deletedAt),
    };
  }

  function loadPeople(storage = localStorage) {
    try {
      const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(parsed)
        ? parsed.map(normalizePerson).filter((person) => !person.deletedAt)
        : [];
    } catch {
      return [];
    }
  }

  function savePeople(people, storage = localStorage) {
    const normalized = Array.isArray(people) ? people.map(normalizePerson) : [];
    storage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    return normalized;
  }

  function upsertPerson(people, input) {
    const person = normalizePerson(input);
    const list = Array.isArray(people) ? people.filter((item) => item.id !== person.id) : [];
    return [person, ...list];
  }

  function deletePerson(people, id) {
    return (Array.isArray(people) ? people : []).filter((person) => person.id !== id);
  }

  function buildRecipientContextPrompt(person) {
    if (!person?.id) return "";
    const lines = [
      "返信先に合わせた文脈:",
      `送り先: ${person.name}`,
      person.nickname ? `呼び名: ${person.nickname}` : "",
      `関係: ${categoryLabel(person.relationshipCategory)}`,
      person.likes ? `好きなこと: ${person.likes}` : "",
      person.dislikes ? `苦手なこと: ${person.dislikes}` : "",
      person.conversationNotes ? `会話の注意点: ${person.conversationNotes}` : "",
      person.relationshipMemo ? `関係メモ: ${person.relationshipMemo}` : "",
      person.personalityType ? `性格タイプ参考: ${person.personalityType}` : "",
      "個人情報を断定せず、送信前にユーザーが調整できる返信案として出す。",
    ].filter(Boolean);
    return `\n\n${lines.join("\n")}`;
  }

  window.GEMMA_PERSON_RELATIONSHIP = {
    STORAGE_KEY,
    relationshipCategories,
    categoryLabel,
    normalizePerson,
    loadPeople,
    savePeople,
    upsertPerson,
    deletePerson,
    buildRecipientContextPrompt,
  };
})();
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
node scripts/test-person-relationship-helpers.js
```

Expected: PASS and prints `person relationship helper tests passed`.

- [ ] **Step 5: Commit**

```bash
git add web/person-relationship.js scripts/test-person-relationship-helpers.js
git commit -m "Add person relationship data helpers"
```

## Task 2: Management Panel UI

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/management.js`
- Modify: `web/i18n.js`
- Modify: `web/styles.css`
- Modify: `scripts/test-management-helpers.js`

- [ ] **Step 1: Write failing static checks**

Append to `scripts/test-management-helpers.js`:

```js
assert.match(indexHtml, /id="person-relationship-toggle"/);
assert.match(indexHtml, /id="person-relationship-panel"/);
assert.match(indexHtml, /id="person-list"/);
assert.match(indexHtml, /id="person-name"/);
assert.match(indexHtml, /src="\/person-relationship\.js\?v=0\.8\.206-tomos7"/);
assert.match(i18nJs, /"management\.personRelationship": "人物・関係メモ"/);
assert.match(stylesCss, /\.person-card/);

const personEls = {
  settingsPanel: { hidden: false },
  personRelationshipPanel: { hidden: true },
};
openManagementPanel({ els: personEls, panel: personEls.personRelationshipPanel });
assert.equal(personEls.personRelationshipPanel.hidden, false);
assert.equal(personEls.settingsPanel.hidden, true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node scripts/test-management-helpers.js
```

Expected: FAIL because the new panel and script are not present.

- [ ] **Step 3: Add HTML**

In `web/index.html`, add a left menu button near other app/settings buttons:

```html
<button class="ghost-button" id="person-relationship-toggle" type="button" data-i18n="management.personRelationship">人物・関係メモ</button>
```

Add the management panel:

```html
<section class="management-panel" id="person-relationship-panel" hidden>
  <div class="settings-header">
    <div>
      <strong data-i18n="management.personRelationship">人物・関係メモ</strong>
      <span data-i18n="management.personRelationshipHelp">友達、恋愛、家族、仕事の相手を登録し、返信支援に使います。</span>
    </div>
    <button class="ghost-button" id="person-relationship-close" type="button" data-i18n="common.close">閉じる</button>
  </div>
  <div class="management-panel-body person-relationship-body">
    <article class="management-card person-editor">
      <label>名前<input id="person-name" type="text" /></label>
      <label>呼び名<input id="person-nickname" type="text" /></label>
      <label>関係<select id="person-category"></select></label>
      <label>写真<input id="person-photo" type="text" placeholder="画像URLまたはdata URL" /></label>
      <label>年齢<input id="person-age" type="text" /></label>
      <label>性別<input id="person-gender" type="text" /></label>
      <label>血液型<input id="person-blood-type" type="text" /></label>
      <label>性格タイプ<input id="person-personality-type" type="text" placeholder="例: ENFP" /></label>
      <label>好きなこと<textarea id="person-likes" rows="2"></textarea></label>
      <label>苦手なこと<textarea id="person-dislikes" rows="2"></textarea></label>
      <label>会話の注意点<textarea id="person-conversation-notes" rows="3"></textarea></label>
      <label>自分との関係メモ<textarea id="person-relationship-memo" rows="3"></textarea></label>
      <div class="character-actions">
        <button class="ghost-button" id="person-clear" type="button">新規</button>
        <button class="ghost-button primary-action" id="person-save" type="button">保存</button>
      </div>
    </article>
    <div class="person-list" id="person-list"></div>
  </div>
</section>
```

Load the script before `app.js`:

```html
<script src="/person-relationship.js?v=0.8.206-tomos7"></script>
```

- [ ] **Step 4: Wire state and rendering in `web/app.js`**

Add state:

```js
people: window.GEMMA_PERSON_RELATIONSHIP?.loadPeople?.() || [],
selectedPersonId: "",
editingPersonId: "",
```

Add DOM refs:

```js
personRelationshipToggle: document.querySelector("#person-relationship-toggle"),
personRelationshipPanel: document.querySelector("#person-relationship-panel"),
personRelationshipClose: document.querySelector("#person-relationship-close"),
personList: document.querySelector("#person-list"),
personName: document.querySelector("#person-name"),
personNickname: document.querySelector("#person-nickname"),
personCategory: document.querySelector("#person-category"),
personPhoto: document.querySelector("#person-photo"),
personAge: document.querySelector("#person-age"),
personGender: document.querySelector("#person-gender"),
personBloodType: document.querySelector("#person-blood-type"),
personPersonalityType: document.querySelector("#person-personality-type"),
personLikes: document.querySelector("#person-likes"),
personDislikes: document.querySelector("#person-dislikes"),
personConversationNotes: document.querySelector("#person-conversation-notes"),
personRelationshipMemo: document.querySelector("#person-relationship-memo"),
personClear: document.querySelector("#person-clear"),
personSave: document.querySelector("#person-save"),
```

Add helpers:

```js
function renderPersonRelationshipPanel() {
  const api = window.GEMMA_PERSON_RELATIONSHIP;
  if (!api || !els.personList) return;
  if (els.personCategory) {
    els.personCategory.innerHTML = api.relationshipCategories()
      .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`)
      .join("");
  }
  els.personList.innerHTML = state.people.length
    ? state.people.map((person) => `
      <article class="person-card" data-person-id="${escapeHtml(person.id)}">
        <div class="person-card-photo">${person.photo ? `<img src="${escapeHtml(person.photo)}" alt="">` : escapeHtml(person.name.slice(0, 2))}</div>
        <div>
          <strong>${escapeHtml(person.name)}</strong>
          <span>${escapeHtml(api.categoryLabel(person.relationshipCategory))}</span>
          <small>${escapeHtml(person.conversationNotes || "会話メモなし")}</small>
        </div>
        <button class="ghost-button" type="button" data-person-edit="${escapeHtml(person.id)}">編集</button>
        <button class="ghost-button" type="button" data-person-delete="${escapeHtml(person.id)}">削除</button>
      </article>
    `).join("")
    : `<p class="management-note">まだ人物が登録されていません。</p>`;
}

function clearPersonEditor() {
  state.editingPersonId = "";
  [els.personName, els.personNickname, els.personPhoto, els.personAge, els.personGender, els.personBloodType,
    els.personPersonalityType, els.personLikes, els.personDislikes, els.personConversationNotes, els.personRelationshipMemo]
    .forEach((input) => { if (input) input.value = ""; });
  if (els.personCategory) els.personCategory.value = "friend";
}

function savePersonFromEditor() {
  const api = window.GEMMA_PERSON_RELATIONSHIP;
  if (!api) return;
  state.people = api.upsertPerson(state.people, {
    id: state.editingPersonId,
    name: els.personName?.value,
    nickname: els.personNickname?.value,
    relationshipCategory: els.personCategory?.value,
    photo: els.personPhoto?.value,
    age: els.personAge?.value,
    gender: els.personGender?.value,
    bloodType: els.personBloodType?.value,
    personalityType: els.personPersonalityType?.value,
    personalityTypeSource: els.personPersonalityType?.value ? "user_reported" : "unknown",
    likes: els.personLikes?.value,
    dislikes: els.personDislikes?.value,
    conversationNotes: els.personConversationNotes?.value,
    relationshipMemo: els.personRelationshipMemo?.value,
  });
  state.people = api.savePeople(state.people);
  clearPersonEditor();
  renderPersonRelationshipPanel();
}
```

- [ ] **Step 5: Wire management routing**

In `web/management.js`, ensure `openManagementPanel` can hide `personRelationshipPanel` by using the existing dynamic panel list or adding it to the hidden-panel list beside other panels. Add listeners in `web/app.js`:

```js
els.personRelationshipToggle?.addEventListener("click", () => {
  window.GEMMA_MANAGEMENT?.openManagementPanel?.({ els, panel: els.personRelationshipPanel });
  renderPersonRelationshipPanel();
});
els.personRelationshipClose?.addEventListener("click", () => {
  window.GEMMA_MANAGEMENT?.openManagementPanel?.({ els, panel: els.settingsPanel });
});
els.personSave?.addEventListener("click", savePersonFromEditor);
els.personClear?.addEventListener("click", clearPersonEditor);
els.personList?.addEventListener("click", (event) => {
  const editId = event.target.closest("[data-person-edit]")?.dataset.personEdit;
  const deleteId = event.target.closest("[data-person-delete]")?.dataset.personDelete;
  if (editId) {
    const person = state.people.find((item) => item.id === editId);
    if (!person) return;
    state.editingPersonId = person.id;
    if (els.personName) els.personName.value = person.name;
    if (els.personNickname) els.personNickname.value = person.nickname;
    if (els.personCategory) els.personCategory.value = person.relationshipCategory;
    if (els.personPhoto) els.personPhoto.value = person.photo;
    if (els.personAge) els.personAge.value = person.age;
    if (els.personGender) els.personGender.value = person.gender;
    if (els.personBloodType) els.personBloodType.value = person.bloodType;
    if (els.personPersonalityType) els.personPersonalityType.value = person.personalityType;
    if (els.personLikes) els.personLikes.value = person.likes;
    if (els.personDislikes) els.personDislikes.value = person.dislikes;
    if (els.personConversationNotes) els.personConversationNotes.value = person.conversationNotes;
    if (els.personRelationshipMemo) els.personRelationshipMemo.value = person.relationshipMemo;
  }
  if (deleteId) {
    state.people = window.GEMMA_PERSON_RELATIONSHIP.deletePerson(state.people, deleteId);
    state.people = window.GEMMA_PERSON_RELATIONSHIP.savePeople(state.people);
    renderPersonRelationshipPanel();
  }
});
```

- [ ] **Step 6: Add i18n and styles**

In `web/i18n.js`, add keys:

```js
"management.personRelationship": "人物・関係メモ",
"management.personRelationshipHelp": "友達、恋愛、家族、仕事の相手を登録し、返信支援に使います。",
```

In `web/styles.css`, add:

```css
.person-relationship-body {
  display: grid;
  grid-template-columns: minmax(280px, 420px) 1fr;
  gap: 16px;
}
.person-editor {
  display: grid;
  gap: 10px;
}
.person-list {
  display: grid;
  gap: 10px;
}
.person-card {
  display: grid;
  grid-template-columns: 48px 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
}
.person-card-photo {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: var(--surface-muted);
}
.person-card-photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
@media (max-width: 760px) {
  .person-relationship-body,
  .person-card {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 7: Run test to verify it passes**

Run:

```bash
node scripts/test-management-helpers.js
```

Expected: PASS and existing output remains `management helper tests passed`.

- [ ] **Step 8: Commit**

```bash
git add web/index.html web/app.js web/management.js web/i18n.js web/styles.css scripts/test-management-helpers.js
git commit -m "Add person relationship management panel"
```

## Task 3: Recipient-Aware Chat Reply Assistance

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `scripts/test-person-relationship-helpers.js`

- [ ] **Step 1: Add failing tests for recipient prompt**

Append to `scripts/test-person-relationship-helpers.js`:

```js
const recipient = api.normalizePerson({
  name: "田中さん",
  relationshipCategory: "work",
  likes: "結論から話すこと",
  conversationNotes: "敬語で、依頼内容を先に書く",
  relationshipMemo: "社外パートナー",
  age: "32",
  bloodType: "A",
});
const recipientPrompt = api.buildRecipientContextPrompt(recipient);
assert.match(recipientPrompt, /関係: 仕事/);
assert.match(recipientPrompt, /敬語で、依頼内容を先に書く/);
assert.doesNotMatch(recipientPrompt, /32/);
assert.doesNotMatch(recipientPrompt, /A/);
```

- [ ] **Step 2: Run test**

Run:

```bash
node scripts/test-person-relationship-helpers.js
```

Expected: PASS if Task 1 already excludes age and blood type from prompt. If it fails, update `buildRecipientContextPrompt` to exclude age, gender, bloodType, and photo.

- [ ] **Step 3: Add composer recipient selector**

In `web/index.html`, near composer controls, add:

```html
<select id="composer-recipient" title="送り先" aria-label="送り先">
  <option value="">送り先なし</option>
</select>
```

In `web/app.js`, add DOM ref:

```js
composerRecipient: document.querySelector("#composer-recipient"),
```

Add renderer:

```js
function renderComposerRecipients() {
  if (!els.composerRecipient) return;
  const current = state.selectedPersonId || "";
  els.composerRecipient.innerHTML = [
    `<option value="">送り先なし</option>`,
    ...state.people.map((person) => `<option value="${escapeHtml(person.id)}">${escapeHtml(person.name)}</option>`),
  ].join("");
  els.composerRecipient.value = state.people.some((person) => person.id === current) ? current : "";
}
```

Call `renderComposerRecipients()` after loading people, after saving/deleting people, and during initial render.

- [ ] **Step 4: Add recipient context to system prompt**

In `web/app.js`, add:

```js
function selectedRecipientContextPrompt() {
  const api = window.GEMMA_PERSON_RELATIONSHIP;
  if (!api || !state.selectedPersonId) return "";
  const person = state.people.find((item) => item.id === state.selectedPersonId);
  return person ? api.buildRecipientContextPrompt(person) : "";
}
```

In the `sendMessage` system prompt construction, append the selected recipient prompt beside character/study/training context:

```js
const requestSystemWithTraining = `${requestOptions.translationMode ? "" : characterContextSystemPrompt()}${selectedRecipientContextPrompt()}${baseRequestSystem}${requestOptions.useStudyPackContext ? studyPackContextSystemPrompt(text) : ""}${trainingContextSystemPrompt()}`;
```

Add listener:

```js
els.composerRecipient?.addEventListener("change", () => {
  state.selectedPersonId = els.composerRecipient.value || "";
});
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
node scripts/test-person-relationship-helpers.js
node scripts/test-management-helpers.js
```

Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/app.js scripts/test-person-relationship-helpers.js
git commit -m "Add recipient-aware reply context"
```

## Task 4: PWA Cache and Asset Tests

**Files:**
- Modify: `web/sw.js`
- Modify: `scripts/test-pwa-assets.js`

- [ ] **Step 1: Add failing assertions**

Append to `scripts/test-pwa-assets.js`:

```js
assert.match(indexHtml, /src="\/person-relationship\.js\?v=0\.8\.206-tomos7"/);
assert.match(swJs, /\/person-relationship\.js\?v=0\.8\.206-tomos7/);
assert.match(appJs, /composerRecipient/);
assert.match(appJs, /selectedRecipientContextPrompt/);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node scripts/test-pwa-assets.js
```

Expected: FAIL until `web/sw.js` includes the new script.

- [ ] **Step 3: Update Service Worker cache list**

In `web/sw.js`, add:

```js
"/person-relationship.js?v=0.8.206-tomos7",
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
node scripts/test-pwa-assets.js
```

Expected: PASS and existing PWA checks remain green.

- [ ] **Step 5: Commit**

```bash
git add web/sw.js scripts/test-pwa-assets.js
git commit -m "Cache person relationship app assets"
```

## Task 5: Manual QA

**Files:**
- Modify: `docs/manual-test-checklist.ja.md`

- [ ] **Step 1: Add checklist**

Add:

```md
## 人物・関係メモ

- [ ] 左メニューから「人物・関係メモ」を開ける
- [ ] 友達、恋愛、家族、仕事の人物を登録できる
- [ ] 写真、性格タイプ、会話注意点を保存できる
- [ ] 登録人物を編集、削除できる
- [ ] チャットの送り先に登録人物が表示される
- [ ] 送り先を選ぶと、その人に合わせた返信案になる
- [ ] 年齢、性別、血液型は返信支援プロンプトへ不要に渡されない
- [ ] 外部SNSへ自動送信されない
```

- [ ] **Step 2: Run all focused tests**

Run:

```bash
node scripts/test-person-relationship-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
```

Expected: all PASS.

- [ ] **Step 3: Run app smoke check**

Run:

```bash
./scripts/start-dev.sh
```

Expected: local app starts. Open the displayed URL and verify the manual checklist. Stop the server after verification.

- [ ] **Step 4: Commit**

```bash
git add docs/manual-test-checklist.ja.md
git commit -m "Document person relationship manual checks"
```

## Acceptance Criteria

- [ ] `人物・関係メモ` が左メニューから開ける
- [ ] 友達、恋愛、家族、仕事を登録できる
- [ ] 性格タイプは任意メモであり、公式診断として扱わない
- [ ] チャットで送り先を選べる
- [ ] 返信支援は人物メモ、関係カテゴリ、会話注意点だけを必要最小限で使う
- [ ] Discord、LINE、Slack、メールへ自動送信しない
- [ ] 人物データはプラグイン側に重複保存しない
- [ ] `node scripts/test-person-relationship-helpers.js` がPASS
- [ ] `node scripts/test-management-helpers.js` がPASS
- [ ] `node scripts/test-pwa-assets.js` がPASS

## Self-Review

- Spec coverage: `docs/person-relationship-app-roadmap.ja.md` の人物登録、4カテゴリ、相性メモ、返信支援、プラグイン境界、Local Context Core接続方針をTask 1からTask 5で扱っている。
- Placeholder scan: 実装者に判断を丸投げする未定義項目は残していない。
- Type consistency: `relationshipCategory`、`personalityTypeSource`、`selectedPersonId`、`buildRecipientContextPrompt` の名称を全タスクで統一している。
