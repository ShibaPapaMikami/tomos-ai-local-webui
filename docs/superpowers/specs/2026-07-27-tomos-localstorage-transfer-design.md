# TOMOS localStorage明示移行設計

## 決定

Desktop B3へ、旧ブラウザー版からアプリ版へlocalStorageを移す明示export/import機能を追加する。

```text
旧ブラウザー版で「設定を書き出す」
  -> JSON fileを利用者が保存
  -> アプリ版でfileを選択
  -> 反映対象と除外対象をpreview
  -> 利用者が承認
  -> allowlist対象だけをlocalStorageへ反映
```

WebKitアプリ領域、ブラウザーprofile、ファイルシステムを自動探索しない。JSON fileをserverへ送信しない。

## 境界

### 対象

- 会話一覧とfolder構成
- 教材パックとtraining setの表示設定
- characterと人物関係設定
- 画面、応答、音声入力、モデル選択の設定

### 対象外

- API key、password、session token、Cookie、secret
- workspace path、選択file path
- microphone device ID
- 外部LLM URL
- plugin認証・mobile接続情報
- allowlistにない将来または未知のkey

## allowlist

次のkeyだけをexport/importできる。

```text
gemma4.sessions
gemma4.folders
gemma4.activeFolderId
gemma4.foldersInitialized
gemma4.collapsedFolderIds
gemma4.trainingSets
gemma4.activeTrainingSetId
gemma4.studyPacks
gemma4.importedStudyPackDefinitions
gemma4.selectedStudyPackModes
gemma4.character
gemma4.characterMemorySets
gemma4.personRelationship.people.v1
gemma4.personRelationship.self.v1
gemma4.theme
gemma4.language
gemma4.responseMode
gemma4.thinkingMode
gemma4.enterToSend
gemma4.sidebarHidden
gemma4.sidebarWidth
gemma4.weatherLocation
gemma4.asrModel
gemma4.asrPartialMode
gemma4.asrPartialModeMigratedToLocal
gemma4.asrPartialIntervalSeconds
gemma4.micGain
gemma4.composerModel
gemma4.composerModelVisibleModels
gemma4.model.chat
gemma4.model.coding
gemma4.model.translation
gemma4.showExperimentalModels
```

prefix一致は使わず、完全一致だけを許可する。

## file形式

```json
{
  "type": "tomos-local-storage-export",
  "version": 1,
  "exportedAt": "2026-07-27T00:00:00.000Z",
  "values": {
    "gemma4.theme": "light"
  }
}
```

- `type`と`version`が一致しないfileは反映しない。
- `values`は文字列valueだけを受け付ける。
- 未知keyはpreviewの除外件数へ数えるが、値は画面へ表示しない。
- preview時点ではlocalStorageを書き換えない。

## UI

管理画面の「古いTOMOSデータ」セクション内に、次を置く。

- `ブラウザー版の設定を書き出す`
- `書き出したファイルを選択`
- 対象件数、除外件数、file作成日時
- `選択した設定を取り込む`
- 独立した成功・失敗status

export前に「会話や設定がfileへ含まれます」と表示する。import前に「現在のアプリ設定へ上書きされます」と表示する。ボタン内だけで完了を通知しない。

## 反映と失敗

- importの承認時に、現在のallowlist対象keyをmemory snapshotへ保持する。
- allowlist対象を順に反映する。
- 途中で例外が発生した場合はsnapshotへ戻す。
- 成功後は再読込を案内する。
- import file、本文、値をserver log、Memory、Knowledgeへ保存しない。

## テスト

- allowlist以外をexportしない。
- 未知key、token系key、非文字列valueをimportしない。
- previewだけではwrite 0件。
- 承認後だけallowlist対象を反映する。
- write失敗時に元のlocalStorageへ戻る。
- 成功・失敗statusが独立表示される。
- `1280×820`、`960×640`、`390×844`で横overflowがない。

## Gate B3

Gate B3は、DB・directory移行に加えて次が合格した時だけ完了とする。

- 旧ブラウザー側の明示exportができる。
- アプリ側で選択fileをpreviewできる。
- 未知keyが反映されない。
- 利用者の承認前にlocalStorageが変化しない。
- 失敗時に既存設定が維持される。
