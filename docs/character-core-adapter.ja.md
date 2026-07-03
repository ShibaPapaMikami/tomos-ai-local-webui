# character-core adapter 検証メモ

## 方針

TOMOS AI 側では `@tomos-ai/character-core` を本番Promptの全面置き換えには使わず、既存のキャラクターPromptへ追加する adapter として検証します。

## 差し込み位置

- 既存のキャラクターPrompt生成は `web/character.js` の `buildCharacterSystemPrompt()` が担当します。
- 既存の最終Prompt組み立ては `web/app.js` の `characterContextSystemPrompt()` が担当します。
- adapter は `web/character-core-adapter.js` に置き、`window.TOMOS_CHARACTER_CORE` が存在する場合だけ `buildRuntimePrompt()` の `text` を追加します。
- adapter 入力は `@tomos-ai/character-core` v0.1.0 の `RuntimePromptInput` に合わせ、`character.displayName` と `context` 配下へ変換します。
- TOMOS AI では npm 依存を増やさず、ブラウザ用の `web/tomos-character-core.js` が `window.TOMOS_CHARACTER_CORE` を提供します。
- `window.TOMOS_CHARACTER_CORE` が存在しない場合、既存動作は変えません。

## warning の扱い案

- `error` または `blocking`: 人間レビュー候補に回します。
- `warning`: 再生成または調整候補に回します。
- `info`: 診断ログとして保持します。

現時点では UI へ表示せず、adapter の戻り値として保持します。

## 会話状態の対応

adapter 入力は以下を標準値として扱います。

- `situation`: `chat`
- `emotion`: `neutral`
- `relationshipStage`: `default`

TOMOS 側の会話状態が整理できた段階で、画面状態から明示的に渡します。

## schema export の扱い

次版の `@tomos-ai/character-core` では、TOMOS 側 adapter で schema validation を使う可能性があります。

公開候補:

- `CharacterProfileSchema`
- `RuntimePromptInputSchema`
- `characterProfileJsonSchema`
- `runtimePromptInputJsonSchema`

これらを public API に含める場合、schema 変更は semver 管理対象です。必須項目の追加、型変更、enum 値の削除、JSON Schema の破壊的変更は major version 扱いにします。
