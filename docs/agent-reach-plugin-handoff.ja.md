# Agent-Reach PLUGIN.md Handoff

## 目的

Agent-Reach担当がTOMOS標準の `PLUGIN.md` を埋めるために、最低限必要な項目だけを共有する。

この文書は仕様共有用であり、Agent-Reach本体コード、Internet Layer、Web/GitHub/YouTube/RSS連携処理、プラグイン実行基盤は変更しない。

## 参照するテンプレート

- TOMOS本体用: `PLUGIN.md`
- プラグイン用: `docs/plugin-template/PLUGIN.md`
- 標準仕様: `docs/standard-markdown-specs.ja.md`

## Agent-Reach担当が埋める必須項目

| 項目 | 記入する内容 |
| --- | --- |
| `pluginId` | 一意のID。例: `agent-reach` |
| `displayName` | ユーザーに表示する名前 |
| `category` | `app`、`extension`、`connector`、`experiment` など |
| `permissions` | 必要な権限。未確定なら `none` または `review-required` |
| `externalAccess` | 外部アクセスの有無、許可範囲、ユーザー確認要否 |
| `dataAccessScope` | TOMOS内で参照できるデータ範囲と参照禁止範囲 |
| `settings` | ユーザーが変更できる設定 |
| `userVisibleActions` | UIに表示する操作 |
| `disabledBehavior` | OFF、未設定、権限不足、未接続時の挙動 |
| `safetyNotes` | 安全上の注意、外部送信前確認、保存禁止情報 |

## 初期値の推奨

```md
## pluginId
agent-reach

## displayName
Agent-Reach

## category
extension

## permissions
- review-required

## externalAccess
- status: disabled-by-default
- allowed: none in initial template
- userConfirmationRequired: true

## dataAccessScope
- allowed: selectedFolderMetadata
- denied: apiKeys, privateSecrets, fullLocalFilePaths, unconfirmedPersonalData

## settings
- enabled: false
- userEditable: true

## userVisibleActions
- 状態を確認

## disabledBehavior
- 実行ボタンを無効化する
- 既存データは削除しない
- 無効理由を日本語で表示する

## safetyNotes
- 外部送信前にユーザー確認を必須にする
- 個人情報、APIキー、秘密情報を保存しない
```

## 記入時の禁止事項

- 個人情報、APIキー、秘密情報を書かない。
- 実在ユーザー、実在取引先、実在契約、未公開URLをサンプルにしない。
- `externalAccess` 未定義のまま外部通信を前提にしない。
- `dataAccessScope` 未定義のままTOMOS内データ参照を前提にしない。
- この文書だけでAgent-Reach本体、Internet Layer、外部連携処理、実行基盤を変更しない。

## TOMOS側の確認観点

- 必須10項目がすべて記入されている。
- 外部アクセスが初期OFFまたはユーザー確認必須になっている。
- データ参照範囲と参照禁止範囲が明確である。
- 無効時の挙動がユーザーに分かる。
- 個人情報、APIキー、秘密情報がサンプルに含まれていない。

