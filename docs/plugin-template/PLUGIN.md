# Plugin PLUGIN Template

## 目的

このプラグインの基本仕様、権限、外部アクセス、データ参照範囲、安全ルールを定義する。

## 必須項目

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

## pluginId

`example-plugin`

## displayName

`Example Plugin`

## category

`extension`

候補:

- `app`
- `extension`
- `connector`
- `experiment`

## permissions

- `none`

## externalAccess

- status: `none`
- allowed: `none`
- userConfirmationRequired: `true`
- notes: 外部アクセスを追加する場合は別レビューを必須にする。

## dataAccessScope

- allowed:
  - `selectedFolderMetadata`
- denied:
  - `apiKeys`
  - `privateSecrets`
  - `fullLocalFilePaths`
  - `unconfirmedPersonalData`

## settings

- enabled: `false`
- userEditable: `true`

## userVisibleActions

- 状態を確認

## disabledBehavior

- 実行ボタンを無効化する。
- 既存データは削除しない。
- 無効理由を日本語で表示する。

## safetyNotes

- 個人情報、APIキー、秘密情報を保存しない。
- 外部送信が必要な場合は、送信先、送信内容、目的をUIで確認する。
- Agent-Reach本体コード、Internet Layer、Web/GitHub/YouTube/RSS連携処理にはこのテンプレートでは触れない。

## 任意項目

- version:
- owner:
- status:
- dependencies:
- designRefs:
- voiceRefs:
- memoryRefs:
- testPlan:
- releaseNotes:

## 禁止事項

- `externalAccess` 未定義のまま外部通信を行わない。
- `dataAccessScope` 未定義のままTOMOS内データを読む前提にしない。
- APIキー、認証情報、個人情報、秘密情報を書かない。
- プラグイン実行基盤の仕様変更をこのファイルだけで確定しない。

## 記入例

```md
## pluginId
agent-reach

## displayName
Agent-Reach

## category
extension

## permissions
- readConfiguredSources
- writeLocalDrafts

## externalAccess
- status: disabled-by-default
- allowed: none in initial template
- userConfirmationRequired: true

## dataAccessScope
- allowed: selectedFolderMetadata
- denied: apiKeys, privateSecrets, fullLocalFilePaths

## settings
- enabled: false

## userVisibleActions
- 接続状態を確認
- 下書きを作成

## disabledBehavior
- 実行ボタンを無効化する

## safetyNotes
- 外部送信前にユーザー確認を必須にする
```
