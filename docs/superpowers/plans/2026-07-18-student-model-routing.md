# 学生向けモデル構成と用途別ルーティング 実装計画

> **実装担当へ:** `superpowers:subagent-driven-development` または `superpowers:executing-plans` を使い、チェックボックス単位で実装する。

**目的:** Qwen3 4BをTOMOSのCore AIにし、コード、高性能会話、実験、Enterpriseを学生にも分かる用途へ整理する。

**設計:** サーバー側のモデル定義を唯一の分類元にし、画面はモデルIDではなく用途を先に表示する。既存モデルは削除せず、通常利用できるモデルの保存値は維持する。学生向け非表示モデルを選択中の場合だけ自動選択へ一度移行し、ルーターを段階的にCore AI優先へ切り替える。

**技術:** Python標準ライブラリ、Ollama、JavaScript、既存Nodeテスト。

## 共通制約

- 依存追加をしない。
- モデル本体をアプリへ同梱しない。
- `gemma4.*` の既存保存キーを変更しない。
- 取得済みモデルの削除、アンインストール、再ダウンロードを行わない。
- `gemma4:12b`、`gemma4:12b-mlx`、`qwen2.5:3b`、Qwen3 4B、Agentic Coder v2の明示選択は維持する。
- HauhauCSまたはHuihuiが選択中の場合だけ、その選択値を空文字の `自動（おすすめ）` へ一度移行する。モデル本体は削除しない。
- 起動スクリプトの既存Gemma既定値は互換フォールバックとして残す。Qwen3 4Bが取得済みなら画面側ルーターでCore AIを優先する。
- Core AIは `hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL` とする。
- Developer AIは既存の `Agentic Coder v2` とし、全学生へ必須ダウンロードさせない。
- `Gemma 4 12B` とMLX版は任意の高性能モデルにする。
- 実験モデル、大人モード用モデル、制限を弱めたモデルは自動選択しない。
- `ZONOS2`、Enterpriseモデル、Agent-Reach本体は変更しない。
- 契約書、社内資料、外部送信前確認は原文根拠を維持し、実験モデルへ振り分けない。

---

## 変更ファイル

- `server.py`: モデル分類、初期候補、PC診断の推奨モデル。
- `web/app.js`: 画像添付の有無をモデルルーターへ渡し、画像対応モデル未取得時に案内する。
- `web/models.js`: Core AI、Developer AI、高性能モデルの選択規則。
- `web/settings.js`: 用途別カード、通常画面から隠すモデル、重複表示の解消。
- `scripts/test-model-selection.js`: 自動選択と表示分類の回帰テスト。
- `scripts/test-settings-helpers.js`: 設定画面と既存保存値の回帰テスト。
- `scripts/test_server_helpers.py`: PC診断とサーバー側モデル定義の回帰テスト。
- `docs/install-students.ja.md`: 学生向けの取得手順。
- `docs/release-checklist.ja.md`: リリース前のモデル分類確認。
- `docs/manual-test-checklist.ja.md`: 実機確認項目。
- `web/index.html`、`web/sw.js`、`web/pwa.js`、`web/mobile.html`、`web/reset-cache.html`: 既存方式で画面資産の版を揃える。

### Task 1: サーバー側モデル分類を確定する

**ファイル:**

- 変更: `server.py`
- テスト: `scripts/test_server_helpers.py`
- テスト: `scripts/test-model-selection.js`

**入力:** `PULLABLE_MODELS`、`QWEN3_2507_MODEL`、`AGENTIC_CODER_MODEL`。

**出力:** 各モデルの `role`、`tier`、`defaultVisible`、`allowAutoSelect`、`defaultInstall`。

- [ ] **手順1: 失敗する分類テストを追加する**

`scripts/test-model-selection.js` に次の期待値を追加する。

```js
assert.match(serverSource, /"role": "core"/);
assert.match(serverSource, /"tier": "required"/);
assert.match(serverSource, /"role": "developer"/);
assert.match(serverSource, /"defaultInstall": False/);
assert.match(serverSource, /"role": "high-performance"/);
assert.match(serverSource, /"allowAutoSelect": False/);
```

- [ ] **手順2: テストが失敗することを確認する**

実行:

```bash
node scripts/test-model-selection.js
```

期待結果: 新しい `role` または `tier` がないため失敗する。

- [ ] **手順3: `PULLABLE_MODELS` に分類を追加する**

`QWEN3_2507_MODEL` と `AGENTIC_CODER_MODEL` の定義を `PULLABLE_MODELS` より前へ移し、現在の後方にある重複定義を削除する。

最低限、次の形へ揃える。

```python
{
    "model": QWEN3_2507_MODEL,
    "label": "Qwen3 4B Instruct 2507",
    "purpose": "標準チャット・資料検索・学習パック",
    "family": "Qwen系",
    "role": "core",
    "tier": "required",
    "defaultVisible": True,
    "allowAutoSelect": True,
    "defaultInstall": True,
}
```

```python
{
    "model": AGENTIC_CODER_MODEL,
    "label": "Agentic Coder v2",
    "purpose": "コード生成・修正・レビュー",
    "family": "Developer AI",
    "role": "developer",
    "tier": "important",
    "defaultVisible": False,
    "allowAutoSelect": True,
    "defaultInstall": False,
}
```

`Gemma 4 12B` とMLX版には `role: "high-performance"`、`tier: "important"`、`defaultInstall: False` を付ける。`HauhauCS` と `Huihui Abliterated` には `role: "developer-hidden"`、`defaultVisible: False`、`allowAutoSelect: False`、`pullable: False` を付ける。

- [ ] **手順4: サーバー側テストを通す**

実行:

```bash
python3 scripts/test_server_helpers.py
node scripts/test-model-selection.js
```

期待結果: 全件成功。

### Task 2: Core AI優先のモデルルーターへ変更する

**ファイル:**

- 変更: `web/models.js`
- 変更: `web/app.js`
- テスト: `scripts/test-model-selection.js`

**入力:** 利用可能モデル、用途、ユーザーの明示選択。

**出力:** Core AI、Developer AI、高性能モデルのいずれか1つのモデルIDと、旧選択値を安全に自動選択へ戻す移行結果。

- [ ] **手順1: ルーティングの失敗テストを追加する**

次の条件をテストする。

```js
assert.equal(modelForTask("chat", coreOptions), qwen2507);
assert.equal(modelForTask("translation", coreOptions), qwen2507);
assert.equal(modelForTask("coding", coderInstalledOptions), agenticCoder);
assert.equal(modelForTask("coding", coderMissingOptions), qwen2507);
assert.equal(modelForRequestTask("chat", {}, explicitGemmaOptions), "gemma4:12b-mlx");
assert.equal(modelForRequestTask("chat", { hasImages: true }, visionOptions), "gemma4:12b-mlx");
assert.equal(safeSavedModel(hauhauBalanced), "");
assert.equal(safeSavedModel(huihuiAbliterated), "");
assert.equal(safeSavedModel("gemma4:12b"), "gemma4:12b");
```

さらに、`HauhauCS`、`Huihui Abliterated`、実験モデルが明示選択なしで返らないこと、`serverModels.chat` がGemmaでもQwen3 4Bが取得済みならCore AIを返すことを確認する。

- [ ] **手順2: テストが失敗することを確認する**

実行:

```bash
node scripts/test-model-selection.js
```

期待結果: 現在はチャットでMLX版を先に返すため失敗する。

- [ ] **手順3: Core AI選択ヘルパーを追加する**

`web/models.js` 内で次の責務を持つヘルパーを作る。

```js
function gemmaCoreModel(options = {}) {
  const serverModels = options.serverModels || {};
  const installed = typeof options.modelIsInstalled === "function"
    ? options.modelIsInstalled
    : (model) => gemmaModelIsInstalled(model, serverModels);
  const qwen2507 = "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL";
  if (installed(qwen2507) || serverModels.chat === qwen2507) return qwen2507;
  if (installed("qwen2.5:3b")) return "qwen2.5:3b";
  return serverModels.chat || "gemma4:12b";
}
```

学生向け非表示モデルの判定と保存値移行には、次の責務を持つヘルパーを追加する。

```js
function gemmaIsStudentHiddenModel(model = "") {
  const value = String(model || "");
  return value.includes("Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced")
    || value.includes("Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated");
}

function gemmaSafeSavedModel(model = "") {
  const value = String(model || "").trim();
  return gemmaIsStudentHiddenModel(value) ? "" : value;
}
```

両方を `window.GEMMA_MODELS` から `isStudentHiddenModel`、`safeSavedModel` として公開する。

`web/app.js` の初期化時に、次の保存値へ `gemmaSafeSavedModel()` を適用する。

- `gemma4.composerModel`
- `gemma4.model.chat`
- `gemma4.model.coding`
- `gemma4.model.translation`
- `gemma4.composerModelVisibleModels` の各モデルID

変更があった場合だけ同じ既存キーへ安全な値を書き戻し、`gemma4.studentModelRoutingV1Migrated` を `true` にする。新しいモデル設定キーへ複製しない。通常利用できるモデルの保存値は変更しない。移行の戻り値を `state.studentModelRoutingMigrated` に保持し、設定画面の案内にだけ使う。

ルーター側も毎回 `gemmaIsStudentHiddenModel()` を確認し、localStorageが手動変更されていても非表示モデルを返さない。移行が発生した場合は設定画面に一度だけ `以前のモデル設定を安全な自動選択へ切り替えました。` と表示する。

`gemmaModelForTask()` は、ユーザーの明示選択と用途別上書きを最優先し、その次に通常チャット、翻訳、資料検索をCore AIへ、コードを取得済みのAgentic Coderへ振り分ける。Developer AI未取得時はCore AIへ一度だけ戻す。

ただし、明示選択または用途別上書きが学生向け非表示モデルの場合は優先せず、Core AIへ戻す。

`gemmaModelForRequestTask()` は `requestOptions.hasImages === true` の場合だけ、取得済みのMLX版、通常版の順に画像対応モデルを返す。どちらも未取得なら空文字を返し、Core AIへ画像を送らない。

`web/app.js` では画像配列を確定した直後に、次のようにルーターへ渡す。

```js
const requestOptions = {
  ...chatRequestOptions(noteArticleText, images.length > 0),
  hasImages: images.length > 0,
};
```

画像添付時にルーターが空文字を返した場合はAPIを呼ばず、`画像を読むには高性能AIを追加してください。` と表示する。

- [ ] **手順4: ルーティングテストと構文確認を通す**

実行:

```bash
node scripts/test-model-selection.js
node --check web/models.js
node --check web/app.js
```

期待結果: 全件成功。

### Task 3: 設定画面を用途別の3分類へ整理する

**ファイル:**

- 変更: `web/settings.js`
- テスト: `scripts/test-settings-helpers.js`
- テスト: `scripts/test-model-selection.js`

**入力:** サーバーから受け取るモデル分類と取得状態。

**出力:** `標準AI`、`コード作業`、`高性能AI` の3つの表示と、閉じた実験枠。

- [ ] **手順1: 表示テストを先に変更する**

次を確認する。

```js
assert.match(installerHtml, /標準AI/);
assert.match(installerHtml, /コード作業/);
assert.match(installerHtml, /高性能AI/);
assert.doesNotMatch(installerHtml, /翻訳AIモデル/);
assert.doesNotMatch(installerHtml, /HauhauCS/);
assert.doesNotMatch(installerHtml, /Huihui/);
assert.match(migratedInstallerHtml, /以前のモデル設定を安全な自動選択へ切り替えました。/);
```

- [ ] **手順2: テストが失敗することを確認する**

実行:

```bash
node scripts/test-settings-helpers.js
node scripts/test-model-selection.js
```

期待結果: 現在はQwen 2.5が軽量用と翻訳用で重複し、HauhauCSが候補へ残るため失敗する。

- [ ] **手順3: おすすめカードを3つにする**

`renderModelInstaller()` のカードを次へ整理する。

```js
const recommendedCards = [
  { role: "標準AI", item: qwen2507, help: "チャット・資料検索・学習向け" },
  { role: "コード作業", item: agenticCoder, help: "必要な人だけ追加" },
  { role: "高性能AI", item: highPerformance, help: "高品質会話・画像理解向け" },
].filter((card) => card.item?.model);
```

翻訳カードを削除し、翻訳はCore AIへ統合する。`HauhauCS` と `Huihui Abliterated` は通常一覧、詳細一覧、初期チェック候補から外す。既に取得済みでも、自動選択や通常のチャット欄へ復帰させない。

モデル一覧から外すだけでOllama上のモデルを削除しない。`composerModelVisibleModels` に残っている非表示モデルIDは移行処理で除外し、設定画面を再表示しても復帰させない。

`state.studentModelRoutingMigrated === true` の場合だけ、モデル取得欄の先頭に `以前のモデル設定を安全な自動選択へ切り替えました。` と表示する。次回起動時に新しい移行がなければ表示しない。

- [ ] **手順4: 設定画面テストを通す**

実行:

```bash
node scripts/test-settings-helpers.js
node scripts/test-model-selection.js
node --check web/settings.js
```

期待結果: 全件成功。

### Task 4: PC診断と学生向け案内を新しい分類へ合わせる

**ファイル:**

- 変更: `server.py`
- 変更: `docs/install-students.ja.md`
- 変更: `docs/release-checklist.ja.md`
- 変更: `docs/manual-test-checklist.ja.md`
- テスト: `scripts/test_server_helpers.py`

**入力:** メモリ容量、Apple Silicon判定、取得済みモデル。

**出力:** Core AIを中心にしたPC診断と学生向け説明。

- [ ] **手順1: PC診断テストを変更する**

12GB以上では `standard` がQwen3 4B、Agentic Coder取得済みの場合だけ `coding` がAgentic Coder、24GB以上ではGemmaを「任意の高性能候補」として案内することを確認する。

- [ ] **手順2: `pc_diagnostics_recommendation()` を変更する**

標準モデルをCore AIへ統一する。24GB以上でもGemmaを自動の標準へせず、追加候補として説明する。12GB未満でQwen3 4Bが未取得の場合だけ、既存のQwen 2.5 3Bを移行用の軽量フォールバックにする。

- [ ] **手順3: 学生向け文書を用途名へ変更する**

`docs/install-students.ja.md` は「まず標準AIを取得」「コード作業をする人だけDeveloper AIを追加」「高性能AIは任意」とする。リリース確認には、重複翻訳カードがないこと、Enterpriseモデルが学生画面へ出ないこと、実験モデルが自動選択されないことを追加する。

- [ ] **手順4: サーバーと文書差分を確認する**

実行:

```bash
python3 scripts/test_server_helpers.py
python3 -m py_compile server.py
git diff --check
```

期待結果: 全件成功し、文書に古い `qwen2.5-coder:14b` が残らない。

### Task 5: 画面資産の版更新と実機確認を行う

**ファイル:**

- 変更: `web/index.html`
- 変更: `web/sw.js`
- 変更: `web/pwa.js`
- 変更: `web/mobile.html`
- 変更: `web/reset-cache.html`
- 変更: 関連する資産版テスト

**入力:** Task 1からTask 4までの完成状態。

**出力:** キャッシュ更新後も同じモデル分類が表示されるTOMOS。

- [ ] **手順1: 既存の資産版を1つ進める**

`settings.js` と `models.js` を参照する全画面、Service Worker、資産版テストを同じ値へ揃える。

- [ ] **手順2: 自動テストを実行する**

```bash
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test_server_helpers.py
node --check web/models.js
node --check web/settings.js
python3 -m py_compile server.py
git diff --check
```

期待結果: 全件成功。

- [ ] **手順3: PC画面を確認する**

確認項目:

- 初期表示が `標準AI`、`コード作業`、`高性能AI` の3分類になっている。
- Qwen 2.5の翻訳カードが重複していない。
- HauhauCSとHuihuiが学生向け一覧へ出ない。
- HauhauCSまたはHuihuiが旧設定で選択中でも、自動選択へ一度移行し、モデル本体は削除されない。
- Gemma、Qwen 2.5、Qwen3 4B、Agentic Coderの通常の明示選択値は維持される。
- 起動スクリプトがGemmaを既定値としていても、Qwen3 4B取得済みの通常チャットはCore AIを使う。
- Agentic Coder未取得でも通常チャットが止まらない。
- 画像添付は取得済みのGemmaへ送られ、未取得時は追加案内が出る。
- 実験モデルとEnterpriseモデルが自動選択されない。

- [ ] **手順4: モバイル幅を確認する**

3分類の名前、取得状態、操作ボタンが重ならず、横スクロールを発生させない。

## 今回実装しないもの

- Gemma 4 E4B、E2B、Ornith 9Bのダウンロード追加。
- ZONOS2のインストール、起動、音声生成。
- GLM-5、gpt-oss、DeepSeekへの外部接続。
- HauhauCS、Huihuiの削除やアンインストール。
- 起動スクリプトの既存Gemmaフォールバック削除。
- Agent-Reach本体と外部サービス認証。

## 完了条件

- 通常チャット、資料検索、教材パックがCore AIを既定候補にする。
- コード作業は取得済みのAgentic Coder v2を使い、未取得でもCore AIへ戻れる。
- Gemma 4 12Bは任意の高性能モデルとして選べる。
- 学生向け画面に不要なモデル、実験モデル、Enterpriseモデルが並ばない。
- 通常モデルの既存保存値、取得済みモデル、ローカルチャットが壊れない。
- 学生向け非表示モデルの旧選択値だけが自動選択へ一度移行し、同じモデルが再び自動選択されない。
