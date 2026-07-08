# Agent-Reach担当への報告

## 報告内容

TOMOS標準Markdown仕様に合わせて、Agent-Reach用 `PLUGIN.md` 初版を作るための受け入れ文書を追加しました。

## 追加済み文書

- `docs/agent-reach-plugin-handoff.ja.md`
- `docs/agent-reach-plugin-request.ja.md`

## Agent-Reach担当への依頼

`docs/agent-reach-plugin-request.ja.md` を確認し、Agent-Reach用 `PLUGIN.md` の初版を作成してください。

特に以下を必ず埋めてください。

- `pluginId`
- `displayName`
- `category`
- `permissions`
- `externalAccess`
- `dataAccessScope`
- `settings`
- `userVisibleActions`
- `disabledBehavior`
- `safetyNotes`

## 注意点

- Agent-Reach本体コードは変更しないでください。
- Internet Layer実装は変更しないでください。
- Web/GitHub/YouTube/RSS連携処理は変更しないでください。
- プラグイン実行基盤は変更しないでください。
- 個人情報、APIキー、秘密情報、未公開URLはサンプルに入れないでください。

## TOMOS側で確認すること

- 外部アクセスが初期OFFまたはユーザー確認必須になっている。
- TOMOS内データの参照範囲と参照禁止範囲が明確である。
- 無効時の表示と挙動がユーザーに分かる。
- Agent-Reach担当が未確定項目を明示している。
- 実装変更なしでレビューできる状態になっている。
