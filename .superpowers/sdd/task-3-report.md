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
