# Web調査の決定論的一覧回答 実装計画

> **実装担当者向け:** `superpowers:subagent-driven-development`（推奨）または`superpowers:executing-plans`を使い、各タスクを順番に実行する。各手順はチェックボックスで管理する。

**目標:** Web調査の一覧回答を、AIが事実項目を再生成しない決定論的な回答へ切り替える。

**構成:** `server.py`で根拠選択、候補抽出、回答組み立てを分離する。一覧回答だけAIの生ストリームをバッファし、完成済み本文と使用した出典だけを返す。

**技術:** Python標準ライブラリ、既存HTTPサーバー、既存`scripts/test_server_helpers.py`

## 共通制約

- Agent-Reach本体、Web検索取得方式、YouTube字幕処理は変更しない。
- 追加依存、外部API、クラウド保存を導入しない。
- 一覧項目は根拠本文の表記と順序を維持する。
- Web調査結果を長期記憶へ自動保存しない。
- 一覧以外のチャットでは既存ストリーミングを維持する。
- 実装完了版は`0.8.214`とする。

---

## Task 1: 根拠データと出典選択

**ファイル:**
- 変更: `server.py:1-45,3568-3945`
- テスト: `scripts/test_server_helpers.py:1077-1340,1859-1870`

**インターフェース:**
- 生成: `CompleteListEvidence`
- 生成: `build_complete_list_evidence(query, results) -> CompleteListEvidence`
- 利用: Task 2、Task 3

- [ ] **Step 1: 失敗するテストを書く**

```python
def complete_list_page(url: str, items: list[str]) -> dict[str, str]:
    return {
        "title": "Webページ本文: シリーズ一覧",
        "url": url,
        "source": "agent-reach:web",
        "snippet": "\n".join(f"- [{item}]({url}#{index})" for index, item in enumerate(items)),
    }


def test_complete_list_evidence_prefers_more_complete_trusted_source() -> None:
    official = complete_list_page("https://official.example/works", ["星の旅人", "星の旅人Z", "星の旅人ZZ"])
    encyclopedia = complete_list_page("https://ja.wikipedia.org/wiki/星の旅人", [f"星の旅人{i}" for i in range(12)])
    evidence = server.build_complete_list_evidence("全シリーズを箇条書きして", [official, encyclopedia])
    assert evidence.source_domain == "ja.wikipedia.org"
    assert len(evidence.candidates) == 12
    assert evidence.status == "source-backed"


def test_complete_list_evidence_rejects_navigation_pages() -> None:
    results = [
        complete_list_page("https://ja.wikipedia.org/wiki/星の旅人", ["星の旅人", "星の旅人Z", "星の旅人ZZ"]),
        complete_list_page("https://ja.wikipedia.org/w/index.php?title=特別:ログイン", ["ログイン", "アカウント作成"]),
    ]
    evidence = server.build_complete_list_evidence("全シリーズを箇条書きして", results)
    assert all("ログイン" not in item for item in evidence.candidates)
```

- [ ] **Step 2: REDを確認する**

実行: `python3 scripts/test_server_helpers.py`

期待: `AttributeError: module 'server' has no attribute 'build_complete_list_evidence'`

- [ ] **Step 3: 最小実装を書く**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CompleteListEvidence:
    query: str
    source_domain: str
    source_results: tuple[dict[str, str], ...]
    candidates: tuple[str, ...]
    status: str
    warnings: tuple[str, ...]


def build_complete_list_evidence(query: str, results: list[dict[str, str]]) -> CompleteListEvidence:
    groups = complete_list_source_groups(results)
    ranked = rank_complete_list_sources(groups)
    if not ranked:
        return CompleteListEvidence(query, "", (), (), "unavailable", ("根拠ページ本文を取得できませんでした。",))
    domain, source_results, candidates = ranked[0]
    status = "source-backed" if len(candidates) >= 3 else "partial" if candidates else "unavailable"
    unique_sources = tuple({result["url"]: result for result in source_results if result.get("url")}.values())
    warnings = ("候補が100件を超えたため、100件まで表示します。",) if len(candidates) > 100 else ()
    return CompleteListEvidence(query, domain, unique_sources, tuple(candidates[:100]), status, warnings)
```

同じTaskで次の補助関数を実装する。

```python
def complete_list_authority_band(domain: str) -> int:
    if any(marker in domain for marker in ("official", ".go.jp", ".gov", ".edu")):
        return 0
    if any(marker in domain for marker in ("wikipedia.org", "wiki", "encyclopedia")):
        return 1
    return 2


def complete_list_source_groups(results):
    groups = {}
    for order, result in enumerate(results):
        title = str(result.get("title") or "")
        source = str(result.get("source") or "")
        url = str(result.get("url") or "")
        if not (title.startswith("Webページ本文:") or source == "agent-reach:web"):
            continue
        if re.search(r"ログイン|アカウント作成|login|sign.?up|url短縮|youtube playlist", f"{title} {url}", re.I):
            continue
        domain = urllib.parse.urlparse(url).netloc.lower()
        if domain:
            groups.setdefault(domain, {"order": order, "results": []})["results"].append(result)
    return groups


def rank_complete_list_sources(groups):
    ranked = []
    for domain, group in groups.items():
        candidates = extract_grounded_list_candidates_from_results(group["results"])
        if candidates:
            ranked.append((domain, group["results"], candidates, complete_list_authority_band(domain), group["order"]))
    trusted = [item for item in ranked if item[3] <= 1]
    target = trusted or ranked
    return sorted(target, key=lambda item: (-len(item[2]), item[3], item[4]))


def structured_candidate_cells(line: str) -> list[str]:
    stripped = line.strip()
    if re.match(r"^(?:[*\-・•]|\d+[.)．、])\s+", stripped):
        return [stripped]
    if re.match(r"^#{1,6}\s+\[[^\]]+\]\((?:https?://|/)[^)]+\)$", stripped):
        return [stripped]
    if "|" in stripped and not re.fullmatch(r"[|:\-\s]+", stripped):
        return [cell.strip() for cell in stripped.split("|") if cell.strip()]
    return []
```

`extract_grounded_list_candidates_from_results()`は、各行を`structured_candidate_cells()`へ渡し、返されたセルだけを`clean_grounded_list_candidate()`で処理する。`augment_search_results_with_page_text()`では一覧依頼時の追跡リンク読込を停止し、検索結果から直接選んだ最大3ページだけを読む。既存の追跡リンク用関数はこの段階では削除しない。

- [ ] **Step 4: GREENを確認する**

実行: `python3 scripts/test_server_helpers.py`

期待: `server helper tests passed`

- [ ] **Step 5: コミットする**

```bash
git add server.py scripts/test_server_helpers.py
git commit -m "一覧回答の根拠選択を決定論化する"
```

## Task 2: 一覧本文・出典・診断の決定論化

**ファイル:**
- 変更: `server.py:3746-4065`
- テスト: `scripts/test_server_helpers.py:1231-1525,1866-1877`

**インターフェース:**
- 利用: `CompleteListEvidence`
- 生成: `render_complete_list_answer(character_intro, evidence) -> str`
- 生成: `public_search_results_for_answer(results, evidence) -> list[dict[str, str]]`
- 生成: `complete_list_diagnostic(evidence) -> dict[str, object]`
- 生成: `finalize_complete_list_answer(character_intro, results, evidence) -> tuple[str, list[dict[str, str]], dict[str, object]]`

- [ ] **Step 1: 失敗するテストを書く**

```python
def complete_list_test_evidence(items: list[str]) -> server.CompleteListEvidence:
    source = complete_list_page("https://official.example/works", items)
    return server.CompleteListEvidence(
        query="全シリーズを箇条書きして",
        source_domain="official.example",
        source_results=(source,),
        candidates=tuple(items),
        status="source-backed" if len(items) >= 3 else "partial",
        warnings=(),
    )


def test_render_complete_list_ignores_model_items_and_keeps_all_evidence() -> None:
    evidence = complete_list_test_evidence(["星の旅人", "星の旅人Z", "星の旅人ZZ"])
    content = server.render_complete_list_answer("星の旅人Xもあるよ。\n- 架空作品", evidence)
    assert "架空作品" not in content
    assert "星の旅人X" not in content
    assert "## 確認できた項目（3件）" in content
    assert content.count("\n- 星の旅人") == 3


def test_public_complete_list_sources_include_only_grounding_pages() -> None:
    evidence = complete_list_test_evidence(["星の旅人", "星の旅人Z", "星の旅人ZZ"])
    public = server.public_search_results_for_answer([{"url": "https://noise.example"}], evidence)
    assert public == list(evidence.source_results)
```

- [ ] **Step 2: REDを確認する**

実行: `python3 scripts/test_server_helpers.py`

期待: 新しいレンダラー未定義で失敗する。

- [ ] **Step 3: 最小実装を書く**

```python
def render_complete_list_answer(character_intro: str, evidence: CompleteListEvidence) -> str:
    intro = safe_complete_list_intro(character_intro, evidence) or "確認できた内容をまとめたよ。"
    if evidence.status == "unavailable":
        return f"{intro}\n\n## 確認できていない点\n- 一覧項目を抽出できませんでした。対象ページのURLを指定して再度お試しください。"
    lines = [intro, "", f"## 確認できた項目（{len(evidence.candidates)}件）"]
    lines.extend(f"- {item}" for item in evidence.candidates)
    note = "完全な一覧としては確認できませんでした。" if evidence.status == "partial" else "取得した根拠ページで確認できた項目だけを掲載しています。"
    lines.extend(["", "## 確認できていない点", f"- {note}"])
    lines.extend(f"- {warning}" for warning in evidence.warnings)
    return "\n".join(lines)


def public_search_results_for_answer(results, evidence):
    return list(evidence.source_results) if evidence else results


def safe_complete_list_intro(content: str, evidence: CompleteListEvidence) -> str:
    intro = next((part.strip() for part in re.split(r"\n\s*\n", content or "") if part.strip()), "")
    if not intro or len(intro) > 120 or len(intro.splitlines()) > 2:
        return ""
    if re.search(r"^\s*(?:#|[*\-・•]|\d+[.)．、])|\d", intro, re.M):
        return ""
    if any(normalized_fact_text(item) in normalized_fact_text(intro) for item in evidence.candidates):
        return ""
    return intro


def complete_list_diagnostic(evidence: CompleteListEvidence) -> dict[str, object]:
    status = "success" if evidence.status == "source-backed" else "warning" if evidence.status == "partial" else "error"
    return {
        "type": "complete-list-grounding",
        "status": status,
        "label": "一覧根拠",
        "message": f"単一の根拠ドメインから{len(evidence.candidates)}件を確認しました。",
        "sourceDomain": evidence.source_domain,
        "sourceCount": len(evidence.source_results),
        "candidateCount": len(evidence.candidates),
        "mode": "deterministic-complete-list",
    }


def finalize_complete_list_answer(character_intro, results, evidence):
    return (
        render_complete_list_answer(character_intro, evidence),
        public_search_results_for_answer(results, evidence),
        complete_list_diagnostic(evidence),
    )
```

`render_complete_list_answer()`は`partial`の場合に「完全な一覧としては確認できませんでした」を表示し、`evidence.warnings`も「確認できていない点」へ追加する。

- [ ] **Step 4: GREENを確認する**

実行: `python3 scripts/test_server_helpers.py`

期待: `server helper tests passed`

- [ ] **Step 5: コミットする**

```bash
git add server.py scripts/test_server_helpers.py
git commit -m "一覧回答を根拠から直接組み立てる"
```

## Task 3: チャットAPIとストリーミング

**ファイル:**
- 変更: `server.py:5480-5725`
- テスト: `scripts/test_server_helpers.py:1525-1575,1877-1885`

**インターフェース:**
- 利用: Task 1、Task 2の全インターフェース
- 生成: `should_buffer_complete_list_stream(use_web_search, query) -> bool`
- 生成: `emit_or_buffer_chat_chunk(chunk, buffer_output, parts, emit) -> None`

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_complete_list_stream_buffers_raw_model_chunks() -> None:
    emitted = []
    parts = []
    server.emit_or_buffer_chat_chunk("- 架空作品", True, parts, emitted.append)
    assert parts == ["- 架空作品"]
    assert emitted == []


def test_normal_web_stream_still_emits_model_chunks() -> None:
    emitted = []
    parts = []
    server.emit_or_buffer_chat_chunk("通常回答", False, parts, emitted.append)
    assert emitted == ["通常回答"]


def test_complete_list_finalizer_returns_same_content_for_both_api_modes() -> None:
    evidence = complete_list_test_evidence(["星の旅人", "星の旅人Z", "星の旅人ZZ"])
    first = server.finalize_complete_list_answer("まとめるね。", [], evidence)
    second = server.finalize_complete_list_answer("まとめるね。", [], evidence)
    assert first == second
    assert first[2]["mode"] == "deterministic-complete-list"
```

- [ ] **Step 2: REDを確認する**

実行: `python3 scripts/test_server_helpers.py`

期待: ストリーム補助関数未定義で失敗する。

- [ ] **Step 3: 最小実装を書く**

```python
def emit_or_buffer_chat_chunk(chunk, buffer_output, parts, emit):
    if not chunk:
        return
    parts.append(chunk)
    if not buffer_output:
        emit(chunk)


def should_buffer_complete_list_stream(use_web_search: bool, query: str) -> bool:
    return use_web_search and should_read_search_result_pages(query)
```

チャット処理では検索完了後に`complete_list_evidence`を1回だけ作る。一覧回答ではAIへ導入文1文だけを依頼し、生チャンクを送信しない。完了後に`render_complete_list_answer()`を呼び、完成本文を1回の`chunk`と`done`で送る。非ストリーミングも同じレンダラーを使う。`start`と`done`の`search.results`には`public_search_results_for_answer()`の結果を使い、診断へ`complete_list_diagnostic()`を追加する。旧`remove_unverified_list_items()`と`organize_mixed_list_categories()`は一覧回答で呼ばない。

診断では選択ドメイン、根拠ページ数、候補数、`deterministic-complete-list`を必ず返す。

- [ ] **Step 4: GREENと回帰を確認する**

実行:

```bash
python3 scripts/test_server_helpers.py
node scripts/test-search-helpers.js
node scripts/test-submit-classification.js
```

期待: すべて終了コード0。

- [ ] **Step 5: コミットする**

```bash
git add server.py scripts/test_server_helpers.py
git commit -m "一覧回答のストリームを完成後に送る"
```

## Task 4: 版更新・総合確認・公開

**ファイル:**
- 変更: `server.py:92`
- 変更: `web/index.html:29`
- 変更: `scripts/test-pwa-assets.js:247-248`
- 変更: `Gemma4_12B_All_Start.bat`
- 変更: `Gemma4_12B_Web.bat`
- 変更: `Gemma4_12B_Web.command`
- 変更: `Gemma4_12B_全部起動.command`

- [ ] **Step 1: アプリ版を`0.8.214`へ統一する**

実行:

```bash
rg -l '0\.8\.213' server.py web/index.html scripts/test-pwa-assets.js Gemma4_12B_All_Start.bat Gemma4_12B_Web.bat Gemma4_12B_Web.command Gemma4_12B_全部起動.command
```

表示された7ファイルの`0.8.213`だけを`0.8.214`へ変更する。

- [ ] **Step 2: 全検証を実行する**

```bash
python3 scripts/test_server_helpers.py
node scripts/test-search-helpers.js
node scripts/test-submit-classification.js
node scripts/test-pwa-assets.js
python3 -m py_compile server.py
git diff --check
```

期待: 全コマンド終了コード0、`server helper tests passed`を表示。

- [ ] **Step 3: ローカルAPIで手動確認する**

`python3 server.py --port 54876`で起動し、Web調査をONにして次を確認する。

- 「全シリーズを箇条書きして」で架空項目が出ない。
- 同じ質問を2回送り、一覧本文と件数が一致する。
- 出典欄に根拠として使った単一ドメインだけが出る。
- 通常のWeb調査とYouTube要約は従来どおり回答する。
- キャラクターの呼びかけと口調が維持される。

- [ ] **Step 4: 版更新を別コミットにする**

```bash
git add server.py web/index.html scripts/test-pwa-assets.js Gemma4_12B_All_Start.bat Gemma4_12B_Web.bat Gemma4_12B_Web.command Gemma4_12B_全部起動.command
git commit -m "アプリ版を0.8.214へ更新する"
```

- [ ] **Step 5: 公開後の一致を確認する**

```bash
git push origin main
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

期待: `main...origin/main`で未コミット差分がなく、2つのコミットIDが一致する。

## ロールバック

- 一覧回答の`build_complete_list_evidence()`と`finalize_complete_list_answer()`呼び出しを外す。
- ストリームの`buffer_output`を従来どおり`False`に戻す。
- 当面残している`remove_unverified_list_items()`と`organize_mixed_list_categories()`の呼び出しを復帰する。
- 版更新コミットと機能コミットを個別に`git revert`し、履歴は書き換えない。
