# Task 3 実施記録

## RED

- `test_complete_list_stream_buffers_raw_model_chunks` を追加した直後、`emit_or_buffer_chat_chunk` 未定義により失敗を確認した。

## GREEN

- 指定のPythonテスト、検索補助テスト、送信分類テスト、構文検査、差分検査が成功した。

## 変更

- 一覧Web調査ではモデルの生チャンクを保持し、finalizerの完成本文を1回だけ送信する。
- 非ストリーミングも同じfinalizerを使用し、根拠出典と一覧診断を返す。
- 通常Web調査、YouTube、通常チャットの生チャンク送信は維持する。

## コミット

- `一覧回答のストリームを完成後に送る`（このTask 3コミット）

## 懸念点

- HTTPハンドラーの実通信テストは行わず、ストリーム送信の分岐は補助関数テストと既存回帰テストで確認した。

## レビュー指摘の修正

- 決定論的一覧回答の対象を一般Webページに限定し、YouTube/GitHub直接URL、選択済みの専用チャンネル、非Webの`agent-reach`結果sourceを除外した。
- REDで専用チャンネル判定の不足と、「YouTube動画を調べて、紹介作品を全て一覧」の生チャンク集約を確認した。
- ローカルHTTPの`/api/chat`テストで、一般Web一覧の`start → 完成本文1 chunk → done`、非ストリームとの本文・根拠出典・診断の一致、YouTube一覧のモデル生2 chunk維持を確認した。

## 追加検証

- `scripts/test_server_helpers.py`、`scripts/test-search-helpers.js`、`scripts/test-submit-classification.js`、`py_compile`、`git diff --check` はすべて終了コード0。

## レビュー指摘対応結果

- 専用チャンネル判定テストとHTTPイベント列テストを末尾の実行一覧へ登録した。
- 一般Web一覧でストリーム完了イベントと非ストリーム応答の本文、`search.results`、`search.diagnostics`全体を直接比較するようにした。
- HTTPテストを共通投稿補助関数とケース表で整理し、YouTube、GitHub、RSS、通常チャットの生chunkと実イベント列を`/api/chat`経由で確認するようにした。
