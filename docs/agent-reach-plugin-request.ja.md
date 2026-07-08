# Agent-Reach担当への依頼文

## 依頼

TOMOS標準Markdown仕様に合わせて、Agent-Reach用の `PLUGIN.md` 初版を作成してください。

参照ファイル:

- `PLUGIN.md`
- `docs/plugin-template/PLUGIN.md`
- `docs/standard-markdown-specs.ja.md`
- `docs/agent-reach-plugin-handoff.ja.md`

## 作業範囲

- Agent-Reach用 `PLUGIN.md` の必須項目を埋める。
- 外部アクセス、データ参照範囲、無効時挙動、安全注意を明記する。
- TOMOS側がレビューできる形で、判断が必要な未確定項目を残す。

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

## 初期方針

- `pluginId`: `agent-reach`
- `displayName`: `Agent-Reach`
- `category`: `extension`
- 外部アクセスは初期OFFまたはユーザー確認必須にする。
- データ参照範囲は最小限にする。
- APIキー、秘密情報、個人情報、未確認の実データは保存しない。

## 禁止事項

- Agent-Reach本体コードを変更しない。
- Internet Layer実装を変更しない。
- Web/GitHub/YouTube/RSS連携処理を変更しない。
- プラグイン実行基盤を変更しない。
- 実在ユーザー、取引先、契約、未公開URLをサンプルにしない。

## 完了条件

- 必須10項目がすべて記入されている。
- 外部アクセスの初期状態とユーザー確認要否が分かる。
- TOMOS内データの参照範囲と参照禁止範囲が分かる。
- 無効時の表示と挙動が分かる。
- 個人情報、APIキー、秘密情報が含まれていない。
