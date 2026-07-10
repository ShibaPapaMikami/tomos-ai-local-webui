# Web一覧の対象カテゴリ整合 実装計画

> **エージェント担当者向け:** この計画は `superpowers:subagent-driven-development`（推奨）または `superpowers:executing-plans` を使い、チェック項目ごとに実装する。

**目標:** アニメシリーズ一覧にゲーム・書籍・商品などが混入せず、公式ページの作品カードを根拠として抽出できるようにする。

**構成:** `server.py` の既存一覧処理へ、入力文からの対象判定、見出し状態を使った候補除外、公式情報優先の順位付けを追加する。`scripts/test_server_helpers.py` で失敗を再現してから最小実装し、既存の決定的一覧応答を維持する。

**技術:** Python標準ライブラリ、既存の`assert`形式テスト、`dataclass`、正規表現

## 共通制約

- Agent-Reach本体、インターネットレイヤー導入処理、外部API連携は変更しない。
- 依存パッケージを追加しない。
- 特定作品名や特定サイト専用の正解辞書を実装しない。
- 公式サイトHTMLを直接解析する新しい取得経路を追加しない。
- 根拠にない項目をモデルに補完させない。
- キャラクターの口調と既存の決定的一覧表示を維持する。

---

### タスク1: 一覧意図と見出し単位の候補抽出

**ファイル:**
- 変更: `server.py:3811-3968`
- テスト: `scripts/test_server_helpers.py:1713-1777`

**インターフェース:**
- 入力: `query: str`、Web本文の`results: list[dict[str, str]]`
- 出力: `complete_list_intents(query) -> frozenset[str]`
- 出力: `complete_list_section_allowed(query, headings) -> bool`
- 変更: `extract_grounded_list_candidates_from_results(results, query="", limit=None) -> list[str]`

- [ ] **手順1: 単独リンク・太字の失敗テストを追加する**

```python
def test_extract_complete_list_reads_standalone_official_title_cards() -> None:
    result = complete_list_page("https://works-official.example/catalog", [])
    result["snippet"] = "\n".join([
        "## 映像作品",
        "[**星の旅人**](https://works-official.example/first)",
        "**星の旅人Z**",
        "[● 1970年代](https://works-official.example/1970)",
        "[公式YouTubeチャンネル](https://youtube.com/example)",
    ])
    assert server.extract_grounded_list_candidates_from_results(
        [result], query="アニメシリーズを一覧にして"
    ) == ["星の旅人", "星の旅人Z"]
```

- [ ] **手順2: 見出し除外と明示対象の失敗テストを追加する**

```python
def test_extract_complete_list_filters_sections_by_requested_kind() -> None:
    result = complete_list_page("https://works-official.example/catalog", [])
    result["snippet"] = "\n".join([
        "## 映像作品", "- 星の旅人", "- 星の旅人Z",
        "## ゲーム作品", "- 星の旅人バトル",
        "## 書籍作品", "- 星の旅人外伝",
        "## 関連項目", "- 架空出版社",
    ])
    assert server.extract_grounded_list_candidates_from_results(
        [result], query="アニメシリーズを一覧にして"
    ) == ["星の旅人", "星の旅人Z"]
    assert server.extract_grounded_list_candidates_from_results(
        [result], query="ゲームシリーズを一覧にして"
    ) == ["星の旅人バトル"]
```

- [ ] **手順3: 追加した2テストが正しい理由で失敗することを確認する**

実行: `python3 -c "import scripts.test_server_helpers as t; t.test_extract_complete_list_reads_standalone_official_title_cards(); t.test_extract_complete_list_filters_sections_by_requested_kind()"`

期待結果: 単独リンクが未抽出、または対象外見出しの候補が混入して`AssertionError`になる。

- [ ] **手順4: 最小実装を追加する**

```python
def complete_list_intents(query: str) -> frozenset[str]:
    text = str(query or "")
    intents = set()
    for intent, pattern in {
        "game": r"ゲーム|game",
        "book": r"漫画|マンガ|書籍|小説|comic|manga|book|novel",
        "product": r"商品|模型|玩具|グッズ|model|toy|goods",
        "series": r"シリーズ|アニメ|映像作品|TV|OVA|劇場|配信|series|anime",
    }.items():
        if re.search(pattern, text, re.IGNORECASE):
            intents.add(intent)
    return frozenset(intents or {"generic"})
```

`complete_list_section_allowed`は現在の第2・第3見出しを正規化し、脚注・出典・関連項目・外部リンクを常に除外する。`series`だけが指定された場合はゲーム・書籍・商品・その他の作品を除外する。他の明示対象も同じ規則で対象外区分を除外する。

`structured_candidate_cells`へ単独Markdownリンクと単独太字の判定を追加する。`clean_grounded_list_candidate`で内側の太字を外し、年代目次、チャンネル、取得メタデータを除外する。

- [ ] **手順5: 対象テストと既存抽出テストを実行する**

実行: `python3 -c "import scripts.test_server_helpers as t; t.test_extract_complete_list_reads_standalone_official_title_cards(); t.test_extract_complete_list_filters_sections_by_requested_kind(); t.test_extract_grounded_list_candidates_rejects_fragments_and_categories(); t.test_extract_grounded_list_candidates_reads_markdown_link_headings()"`

期待結果: 終了コード0。

---

### タスク2: 公式情報優先と入力文の引き回し

**ファイル:**
- 変更: `server.py:3945-4221`
- テスト: `scripts/test_server_helpers.py:1548-1591, 1669-1825`

**インターフェース:**
- 入力: タスク1の`extract_grounded_list_candidates_from_results(results, query, limit)`
- 変更: `rank_complete_list_sources(groups, query="")`
- 変更: `select_complete_list_grounding_results(results, query="", minimum_candidates=3)`
- 出力: `build_complete_list_evidence(query, results)`が公式情報由来の候補だけを保持する。

- [ ] **手順1: 既存の候補数優先テストを公式優先へ変更する**

```python
def test_complete_list_evidence_prefers_authority_before_candidate_count() -> None:
    official = complete_list_page(
        "https://works-official.example/works",
        ["星の旅人", "星の旅人Z", "星の旅人ZZ"],
    )
    encyclopedia = complete_list_page(
        "https://ja.wikipedia.org/wiki/星の旅人",
        [f"星の旅人{index}" for index in range(12)],
    )
    evidence = server.build_complete_list_evidence(
        "アニメの全シリーズを箇条書きして", [official, encyclopedia]
    )
    assert evidence.source_domain == "works-official.example"
    assert evidence.candidates == ("星の旅人", "星の旅人Z", "星の旅人ZZ")
```

- [ ] **手順2: 公式映像作品と非公式混在ページの回帰テストを追加する**

```python
def test_complete_list_evidence_uses_only_requested_official_sections() -> None:
    official = complete_list_page("https://works-official.example/catalog", [])
    official["snippet"] = "\n".join([
        "## 映像作品",
        "[**星の旅人**](https://works-official.example/first)",
        "**星の旅人Z**",
        "**星の旅人ZZ**",
        "## ゲーム作品", "- 星の旅人バトル",
    ])
    noisy = complete_list_page("https://ja.wikipedia.org/wiki/星の旅人", [
        "ゲーム 星の旅人モバイル", "漫画 星の旅人外伝", "架空出版社",
    ])
    evidence = server.build_complete_list_evidence(
        "アニメの全シリーズを箇条書きして", [noisy, official]
    )
    assert evidence.source_domain == "works-official.example"
    assert evidence.candidates == ("星の旅人", "星の旅人Z", "星の旅人ZZ")
```

- [ ] **手順3: 変更したテストが現行順位付けで失敗することを確認する**

実行: `python3 -c "import scripts.test_server_helpers as t; t.test_complete_list_evidence_prefers_authority_before_candidate_count(); t.test_complete_list_evidence_uses_only_requested_official_sections()"`

期待結果: `source_domain`がWikipediaになるか、対象外候補が混入して`AssertionError`になる。

- [ ] **手順4: 順位付けと全呼び出しへ入力文を渡す**

`rank_complete_list_sources`の並び順を次に変更する。

```python
sorted(trusted, key=lambda item: (item[3], -len(item[2]), item[4]))
```

`build_complete_list_evidence`、`select_complete_list_grounding_results`、`build_search_context_for_query`、`organize_mixed_list_categories`、`complete_list_grounding_instruction`から、抽出関数へ`query`を渡す。`unique_sources`の判定にも同じ`query`を使う。

- [ ] **手順5: タスク2の対象テストを実行する**

実行: `python3 -c "import scripts.test_server_helpers as t; t.test_complete_list_evidence_prefers_authority_before_candidate_count(); t.test_complete_list_evidence_uses_only_requested_official_sections(); t.test_select_complete_list_grounding_results_prefers_one_authoritative_domain(); t.test_complete_list_search_context_excludes_other_domain_categories()"`

期待結果: 終了コード0。

---

### タスク3: 全体回帰確認とアプリ版更新

**ファイル:**
- 変更: `server.py:93`
- 変更: `scripts/test_server_helpers.py:2280-2380`

**インターフェース:**
- 入力: タスク1・2の完成した一覧抽出処理
- 出力: `APP_VERSION = "0.8.215"`

- [ ] **手順1: 新しいテスト関数をスクリプト末尾の実行一覧へ追加する**

```python
test_extract_complete_list_reads_standalone_official_title_cards()
test_extract_complete_list_filters_sections_by_requested_kind()
test_complete_list_evidence_prefers_authority_before_candidate_count()
test_complete_list_evidence_uses_only_requested_official_sections()
```

- [ ] **手順2: 全サーバーヘルパーテストを実行する**

実行: `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/test_server_helpers.py`

期待結果: `server helper tests passed`。

- [ ] **手順3: 構文と差分を検証する**

実行: `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile server.py scripts/test_server_helpers.py`

期待結果: 終了コード0。

実行: `git diff --check`

期待結果: 出力なし、終了コード0。

- [ ] **手順4: アプリ版を更新する**

`server.py`の既定値を次へ変更する。

```python
APP_VERSION = os.environ.get("GEMMA_APP_VERSION", "0.8.215")
```

- [ ] **手順5: バージョン表示を確認する**

実行: `python3 -c "import server; assert server.APP_VERSION == '0.8.215'; print(server.APP_VERSION)"`

期待結果: `0.8.215`。

- [ ] **手順6: タスク単位で差分をレビューする**

実行: `git status --short --branch && git diff --stat && git diff --check`

期待結果: `server.py`と`scripts/test_server_helpers.py`のみが実装差分として表示され、空白エラーがない。
