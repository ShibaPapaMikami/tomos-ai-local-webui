# TOMOS PLUGIN

## 目的

TOMOS本体に追加されるプラグインの権限、UI導線、データ参照範囲、安全ルールを定義する。

## 対象範囲

- TOMOS公式プラグイン
- 将来のAgent-Reach用プラグイン
- 教材、資料検索、契約書、音声、キャラクター、外部連携候補の仕様整理

## 必須項目

| 項目 | 説明 |
| --- | --- |
| `pluginId` | 一意のID。例: `agent-reach` |
| `displayName` | ユーザーに表示する名称 |
| `category` | `app`、`extension`、`connector`、`experiment` など |
| `permissions` | 必要な権限 |
| `externalAccess` | 外部アクセスの有無と範囲 |
| `dataAccessScope` | 参照できるTOMOS内データの範囲 |
| `settings` | ユーザーが変更できる設定 |
| `userVisibleActions` | 画面に出る操作 |
| `disabledBehavior` | 無効化時の挙動 |
| `safetyNotes` | 安全上の注意 |

## 任意項目

- `version`
- `owner`
- `status`
- `dependencies`
- `designRefs`
- `voiceRefs`
- `memoryRefs`
- `testPlan`
- `releaseNotes`

## 禁止事項

- APIキー、認証情報、個人情報、秘密情報を書かない。
- `externalAccess` が未定義のまま外部通信を前提にしない。
- `dataAccessScope` が未定義のままTOMOS内データを読む前提にしない。
- Agent-Reach本体コード、Internet Layer、Web/GitHub/YouTube/RSS連携処理をこのテンプレート作業で変更しない。
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
- notes: 外部アクセスを有効にする場合は別レビュー必須

## dataAccessScope
- allowed: selectedFolderMetadata
- denied: apiKeys, fullLocalFilePaths, privateSecrets

## settings
- enabled: false
- sourceSelection: user-confirmed only

## userVisibleActions
- 接続状態を確認
- 下書きを作成

## disabledBehavior
- メニューには表示しても実行ボタンは無効化する
- 既存データは削除しない

## safetyNotes
- 外部送信前にユーザー確認を必須にする
- 個人情報や秘密情報はサンプルに含めない
```

## 変更時の確認方法

- 必須10項目がすべてあるか確認する。
- 外部アクセスとデータアクセス範囲が明示されているか確認する。
- 無効化時の挙動が分かるか確認する。
- Agent-Reach担当が後で値を埋められる汎用テンプレートになっているか確認する。
