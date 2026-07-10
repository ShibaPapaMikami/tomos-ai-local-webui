# Task 2 実装報告

## 作業対象

- `server.py` のTask 2順位付けと入力文引き回し
- `scripts/test_server_helpers.py` のTask 2テスト
- 本報告書

## 実装内容

- 公式ドメインの権威帯を候補数より先に比較するよう変更。
- `rank_complete_list_sources`、`select_complete_list_grounding_results`へ`query`を追加。
- `build_complete_list_evidence`、`build_search_context_for_query`、`organize_mixed_list_categories`、`complete_list_grounding_instruction`から抽出処理へ同じ`query`を引き回し。
- `unique_sources`の候補有無判定も同じ`query`を使用。
- 既存の候補数優先テストを公式優先テストへ置換し、公式映像作品だけを保持する回帰テストを追加。

## TDD記録

1. Task 2の2テストを実装前に追加。
2. 次のコマンドを実行し、現行の候補数優先順位による`AssertionError`を確認。

```text
python3 -c "import scripts.test_server_helpers as t; t.test_complete_list_evidence_prefers_authority_before_candidate_count(); t.test_complete_list_evidence_uses_only_requested_official_sections()"
終了コード: 1
失敗理由: Wikipediaが候補数優先で選ばれ、公式ドメイン期待値に一致しない。
```

3. 公式優先順位と入力文の引き回しを最小実装。

## 検証

```text
python3 -c "import scripts.test_server_helpers as t; t.test_complete_list_evidence_prefers_authority_before_candidate_count(); t.test_complete_list_evidence_uses_only_requested_official_sections(); t.test_select_complete_list_grounding_results_prefers_one_authoritative_domain(); t.test_complete_list_search_context_excludes_other_domain_categories()"
終了コード: 0
```

## 変更境界

- Task 2に必要な`server.py`、テスト、報告書だけを変更。
- 既存の計画書差分は変更・ステージしない。
- 依存追加、外部API、production変更は行っていない。

## 懸念

- 全体テストはTask 2の対象外として未実行。対象4テストで確認した。
