# note記事作成教材パック Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** note公式エディタに貼り付けやすい記事を生成する教材パックを追加し、長い技術記事がコード生成へ誤分類されてコンテキスト上限を超える問題を防ぐ。

**Architecture:** 教材ルールはインポート可能な教材パックへ置き、利用者の修正例は既存の学習セットへ保存する。記事編集の意図判定とリクエスト予算はフロントエンド、バックエンド由来のコンテキスト超過メッセージの日本語化はサーバーで担当する。

**Tech Stack:** Vanilla JavaScript、Python標準ライブラリ、JSON、Markdown、Node.js helper tests、Python unittest

## Global Constraints

- noteへのログイン、投稿、外部API接続を追加しない。
- 個人名、会社名、ローカルパス、秘密情報を教材例へ入れない。
- 教材パック本体は読み取り専用とし、修正例は学習セットへ保存する。
- note記事モードでは履歴を1ターンへ絞る。
- 長文記事では`num_ctx`を12,288以上へ引き上げる。
- 明示的な保存依頼だけをワークスペース生成へ送る。

---

### Task 1: インポート可能なnote記事教材パック

**Files:**
- Create: `study-packs/note-article-writing-pack/pack.json`
- Create: `study-packs/note-article-writing-pack/README.md`
- Create: `study-packs/note-article-writing-pack/note-format-rules.md`
- Create: `study-packs/note-article-writing-pack/privacy-rules.md`
- Create: `study-packs/note-article-writing-pack/modes/rewrite-for-note.md`
- Create: `study-packs/note-article-writing-pack/modes/continue-series.md`
- Create: `study-packs/note-article-writing-pack/modes/paste-ready.md`
- Create: `study-packs/note-article-writing-pack/modes/prepublish-check.md`
- Create: `study-packs/note-article-writing-pack/examples/generic-technical-article.md`
- Test: `scripts/test-management-helpers.js`

**Interfaces:**
- Consumes: `buildImportedStudyPackDefinition({ manifest, fileMap })`
- Produces: pack id `note-article-writing` と4モード

- [ ] **Step 1: 失敗する教材パック検証を追加する**

`scripts/test-management-helpers.js`で`pack.json`を読み、ID、4モード、全`promptFile`の存在、プロンプト内の公開前チェック語を検証する。

```js
const notePack = JSON.parse(fs.readFileSync("study-packs/note-article-writing-pack/pack.json", "utf8"));
assert.equal(notePack.id, "note-article-writing");
assert.deepEqual(notePack.modes.map((mode) => mode.id), [
  "rewrite-for-note", "continue-series", "paste-ready", "prepublish-check",
]);
for (const mode of notePack.modes) {
  assert.ok(fs.existsSync(`study-packs/note-article-writing-pack/${mode.promptFile}`));
}
assert.ok(fs.existsSync("study-packs/note-article-writing-pack/examples/generic-technical-article.md"));
```

- [ ] **Step 2: REDを確認する**

Run: `node scripts/test-management-helpers.js`
Expected: FAIL with `ENOENT ... note-article-writing-pack/pack.json`

- [ ] **Step 3: 教材パックを作る**

`pack.json`は`visibility: "public"`、`version: "0.1.0"`とし、各モードはnote公式仕様、事実非追加、書式付き本文、個人パス一般化を指示する。貼り付け用モードの出力は「タイトル案」「note貼り付け用本文」「ハッシュタグ候補」に限定する。例文は架空のローカル画像整理ツールを題材にし、実在人物・企業・URLを含めない。

- [ ] **Step 4: GREENを確認する**

Run: `node scripts/test-management-helpers.js`
Expected: `management helper tests passed`

- [ ] **Step 5: 教材パックをコミットする**

```bash
git add study-packs/note-article-writing-pack scripts/test-management-helpers.js
git commit -m "note記事作成教材パックを追加する"
```

### Task 2: note記事編集の意図判定

**Files:**
- Modify: `web/management.js`
- Modify: `web/app.js`
- Test: `scripts/test-management-helpers.js`
- Test: `scripts/test-model-selection.js`

**Interfaces:**
- Produces: `isNoteArticleWritingRequest(text): boolean`
- Consumes: `shouldApplyStudyPackForText(text, options)`、`explicitlyRequestsWorkspaceSave(text)`

- [ ] **Step 1: 誤分類の回帰テストを書く**

次の本文が教材適用対象であり、コード生成除外判定を持つことをテストする。

```js
assert.equal(shouldApplyStudyPackForText(
  "以下のnote記事を貼り付け用に編集して。設定ファイルとコード例があります。",
  { hasSelection: true },
), true);
```

`scripts/test-model-selection.js`では`isNoteArticleWritingRequest`、`shouldKeepNoteArticleInChat`の定義と`isWorkspaceBuildRequest`からの呼び出しを静的検証する。

- [ ] **Step 2: REDを確認する**

Run: `node scripts/test-management-helpers.js && node scripts/test-model-selection.js`
Expected: FAIL because note記事判定が未実装

- [ ] **Step 3: 最小判定を実装する**

`isNoteArticleWritingRequest`は`note記事|ブログ記事|投稿記事`と`整える|編集|書き直す|続き|貼り付け|公開前`の組み合わせで判定する。`isWorkspaceBuildRequest`はnote記事判定かつ明示保存なしなら`false`を返す。`isStudyPackRewriteRequest`と`shouldApplyStudyPackForText`にも同じ意図語を追加する。

- [ ] **Step 4: GREENを確認する**

Run: `node scripts/test-management-helpers.js && node scripts/test-model-selection.js && node --check web/app.js && node --check web/management.js`
Expected: all pass

- [ ] **Step 5: 判定修正をコミットする**

```bash
git add web/app.js web/management.js scripts/test-management-helpers.js scripts/test-model-selection.js
git commit -m "note記事編集を通常チャットへ振り分ける"
```

### Task 3: 長文記事用コンテキスト予算

**Files:**
- Modify: `web/app.js`
- Test: `scripts/test-model-selection.js`

**Interfaces:**
- Produces: `noteArticleRequestBudget(text, baseContext): { numCtx, numPredict, historyTurns }`
- Consumes: `isNoteArticleWritingRequest(text)`

- [ ] **Step 1: 失敗する予算テストを書く**

`web/app.js`から純粋関数を抽出してVMで実行し、長文note記事で次を検証する。

```js
assert.deepEqual(noteArticleRequestBudget("note記事を整えて\n" + "本文".repeat(3000), 4096), {
  numCtx: 12288,
  numPredict: 2048,
  historyTurns: 1,
});
```

- [ ] **Step 2: REDを確認する**

Run: `node scripts/test-model-selection.js`
Expected: FAIL because `noteArticleRequestBudget` is missing

- [ ] **Step 3: 予算と適用経路を実装する**

note記事編集では`codingMode: false`、`historyTurns: 1`、`isolateUserMessage: true`を固定する。入力文字列が3,000文字以上なら`numCtx: 12288`、`numPredict: 2048`とし、短文では`numCtx: 4096`、`numPredict: 900`を使う。

- [ ] **Step 4: GREENを確認する**

Run: `node scripts/test-model-selection.js && node --check web/app.js`
Expected: all pass

- [ ] **Step 5: 長文予算をコミットする**

```bash
git add web/app.js scripts/test-model-selection.js
git commit -m "note長文記事のコンテキストを確保する"
```

### Task 4: コンテキスト超過の日本語化

**Files:**
- Modify: `server.py`
- Test: `scripts/test_server_helpers.py`

**Interfaces:**
- Consumes: `friendly_ollama_error(error_body: str) -> str`
- Produces: 利用者向け長文エラー

- [ ] **Step 1: 失敗するサーバーテストを書く**

```python
def test_context_size_error_is_friendly(self):
    body = '{"error":{"code":400,"message":"request (7994 tokens) exceeds the available context size (4096 tokens)","type":"exceed_context_size_error"}}'
    self.assertEqual(
        friendly_ollama_error(body),
        "文章が長いため一度に処理できませんでした。章ごとに分けるか、長文対応モードでもう一度お試しください。",
    )
```

- [ ] **Step 2: REDを確認する**

Run: `python3 -m unittest scripts.test_server_helpers.ServerHelperTests.test_context_size_error_is_friendly`
Expected: FAIL with raw JSON message

- [ ] **Step 3: 最小変換を実装する**

`friendly_ollama_error`で`exceed_context_size_error`または`exceeds the available context size`を検出し、上記の日本語だけを返す。トークン数や生JSONは返さない。

- [ ] **Step 4: GREENと全体回帰を確認する**

Run: `python3 -m unittest scripts.test_server_helpers && node scripts/test-management-helpers.js && node scripts/test-model-selection.js && node scripts/test-pwa-assets.js && node --check web/app.js && python3 -m py_compile server.py && git diff --check`
Expected: all pass

- [ ] **Step 5: エラー変換をコミットする**

```bash
git add server.py scripts/test_server_helpers.py
git commit -m "長文コンテキストエラーを分かりやすくする"
```

### Task 5: Blender記事による受け入れ確認

**Files:**
- Modify: `docs/superpowers/plans/2026-07-12-note-article-study-pack.md`

**Interfaces:**
- Consumes: Tasks 1-4の実装
- Produces: 実行結果を記録した完了チェック

- [x] **Step 1: 記事①②を使って判定と予算を確認する**

個人パスを含む入力をローカルテストへ渡し、`codingMode === false`、`numCtx >= 12288`、`historyTurns === 1`を確認する。外部送信は行わない。

- [x] **Step 2: 公開前チェックを確認する**

教材プロンプトへ`/Users/example/...`を含む一般化サンプルを渡し、個人パスを公開本文へ残さない指示が入ることを確認する。

- [x] **Step 3: 全検証を再実行する**

Run: `node scripts/test-management-helpers.js && node scripts/test-model-selection.js && node scripts/test-pwa-assets.js && python3 -m unittest scripts.test_server_helpers && node --check web/app.js && node --check web/management.js && python3 -m py_compile server.py && git diff --check`
Expected: all pass

**実行結果（2026-07-12）:** Blender記事相当の5,367文字のローカル文字列（設定ファイル、Pythonコード、個人パス形式、会社名、秘密情報を含む）をVMの既存要求経路へ渡した。保存なしでは`codingMode: false`、`numCtx: 12288`、`historyTurns: 1`、教材適用あり、ワークスペース保存なしを確認した。4モードすべての実行時教材プロンプトに、ローカルパス、会社名、秘密情報を公開本文へ残さず一般化または非出力にする指示が含まれた。`test-management-helpers`、`test-model-selection`、`test-pwa-assets`、構文確認、Pythonコンパイル、`git diff --check`は成功した。`python3 -m unittest scripts.test_server_helpers`はpytest形式のため0件終了し、同一の162関数をローカル実行して162/162件成功した。

**確定仕様:** 翻訳要求はnote記事より翻訳経路を優先する。長文note記事の`numCtx`下限は12,288。明示的な保存要求があるnote記事だけをワークスペース生成へ送る。

- [ ] **Step 4: 実装結果をコミットしてプッシュする**

```bash
git add docs/superpowers/plans/2026-07-12-note-article-study-pack.md
git commit -m "note記事教材パックの検証結果を記録する"
git push origin main
```
