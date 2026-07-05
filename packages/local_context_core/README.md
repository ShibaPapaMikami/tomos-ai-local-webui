# Local Context Core

ローカル長期記憶の共通基盤です。
UI、キャラクター、アプリ固有の画面に依存しない形で、記憶・検索用文脈・削除を扱います。

## 目的

- TOMOSのマイキャラ記憶
- Dating reality showのキャラクター記憶
- 契約書管理や会社資料検索
- 教材パックや学習セットの補助文脈

上記のような別プロジェクトでも、同じ考え方で長期記憶を扱えるようにします。

## 基本型

- `scopeType`: `character` / `project` / `app` / `company` など
- `scopeId`: 記憶の所属先ID
- `ownerType`: `user` / `character` など
- `ownerId`: 所有者ID
- `sensitivity`: `normal` / `protected`

`protected` は通常会話へ自動で混ぜず、必要な場面で明示的に参照するための区分です。

## 主な関数

- `remember(item, scope=...)`
- `forget(record, reason=...)`
- `profile(records, scope=...)`
- `build_context(records, query=..., scope=...)`
- `save_context_record(db_path, record)`
- `list_context_records(db_path, scope=...)`
- `update_context_record(db_path, record_id, text)`
- `forget_context_record(db_path, record_id, reason=...)`

## 互換性

既存コード向けに、ルートの `context_core.py` はこのパッケージを再エクスポートします。
既存の `import context_core` はそのまま使えます。

## 配布方針

現時点では、このパッケージを個別のGitHubリポジトリとして公開しません。
TOMOS AI本体リポジトリ内の共通パッケージとして管理します。

他プロジェクトで使う場合は、まずTOMOS AI本体リポジトリから以下を取り込んでください。

- `packages/local_context_core/`
- 必要に応じて互換用の `context_core.py`

将来的にAPI、保存形式、protected記憶の扱いが安定した段階で、独立リポジトリ化やパッケージ配布を検討します。
