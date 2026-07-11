# Agent-Reach診断連動アダプター Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent-Reachの診断結果に基づいてWeb、YouTube、GitHub、RSSの上流経路を選択し、失敗時は既存TOMOS処理へ一度だけ戻す。

**Architecture:** 新規`agent_reach_adapter.py`へ診断キャッシュ、経路選択、Exa実行、結果正規化を分離する。`server.py`は既存の取得関数をフォールバックとして保持し、アダプターの判断と診断情報だけをチャット処理へ接続する。

**Tech Stack:** Python 3.11標準ライブラリ、既存`agent-reach`、`mcporter`、`yt-dlp`、`gh`、`feedparser`、既存TOMOS HTTPサーバーとJavaScript UI。

## Global Constraints

- ルート`AGENTS.md`でInternet Layer変更が正式に許可されるまでコード実装を開始しない。
- Agent-Reach本体と`~/.agent-reach-venv`配下を変更しない。
- 対象はWeb、YouTube、GitHub、RSSだけとする。
- SNS、Cookie、ログイン情報、書き込み操作を扱わない。
- 外部調査結果を長期記憶へ自動保存しない。
- 実サイトを使う外部通信テストは、実行直前にユーザー承認を得る。
- `shell=True`を使わず、実行ファイルと引数を配列で渡す。
- 優先経路の失敗後に実行するフォールバックは一度だけとする。
- 実装はテスト先行で行い、各タスク完了時に関連テストを通す。

---

### Task 0: 実装許可ゲート

**Files:**
- Review: `AGENTS.md`
- Review: `docs/superpowers/specs/2026-07-11-agent-reach-diagnostic-routing-adapter-design.md`

**Interfaces:**
- Consumes: プロジェクト管理者による作業規則更新
- Produces: Internet Layerと4チャネル連携を変更できる明示的な実装許可

- [ ] **Step 1: 作業規則を確認する**

Run: `rg -n "Internet Layer|Web/GitHub/YouTube/RSS" AGENTS.md`

Expected: 現在の変更禁止行が表示される。

- [ ] **Step 2: プロジェクト管理者の更新を確認する**

Run: `git diff -- AGENTS.md && rg -n "Agent-Reach本体は変更しない|4チャネル" AGENTS.md`

Expected: Agent-Reach本体の変更禁止を維持しつつ、TOMOS側アダプターと4チャネル連携の変更許可が確認できる。

- [ ] **Step 3: ゲートを判定する**

禁止行が残っている場合はTask 1へ進まない。Codexが禁止を回避する目的で`AGENTS.md`を変更してはならない。

---

### Task 1: 診断スナップショットと経路選択

**Files:**
- Create: `agent_reach_adapter.py`
- Create: `scripts/test_agent_reach_adapter.py`

**Interfaces:**
- Consumes: `doctor_loader: Callable[[], dict[str, object]]`
- Produces: `DoctorCache.get(now: float | None = None) -> dict[str, object]`
- Produces: `select_route(channel: str, doctor: dict[str, object], intent: str = "read") -> RouteDecision`

- [ ] **Step 1: 失敗テストを書く**

```python
def test_doctor_cache_reuses_result_for_five_minutes():
    calls = []
    cache = adapter.DoctorCache(lambda: calls.append(True) or {"channels": {"web": {"status": "ok", "active_backend": "Jina Reader"}}})
    assert cache.get(now=100)["channels"]["web"]["active_backend"] == "Jina Reader"
    assert cache.get(now=399)["channels"]["web"]["active_backend"] == "Jina Reader"
    assert len(calls) == 1

def test_select_route_uses_exa_only_for_search():
    doctor = {"channels": {
        "web": {"status": "ok", "active_backend": "Jina Reader"},
        "exa_search": {"status": "ok", "active_backend": "Exa via mcporter"},
    }}
    assert adapter.select_route("web", doctor, intent="search").backend == "exa"
    assert adapter.select_route("web", doctor, intent="read").backend == "jina"
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 scripts/test_agent_reach_adapter.py`

Expected: `ModuleNotFoundError: No module named 'agent_reach_adapter'`。

- [ ] **Step 3: 最小実装を書く**

```python
from dataclasses import dataclass
import time

DOCTOR_CACHE_SECONDS = 300

@dataclass(frozen=True)
class RouteDecision:
    channel: str
    backend: str
    fallback: str
    reason: str

class DoctorCache:
    def __init__(self, loader):
        self.loader = loader
        self.value = None
        self.loaded_at = 0.0

    def get(self, now=None):
        current = time.monotonic() if now is None else now
        if self.value is None or current - self.loaded_at >= DOCTOR_CACHE_SECONDS:
            self.value = self.loader()
            self.loaded_at = current
        return self.value
```

`select_route`はWeb検索で`exa_search.active_backend`、Web本文で`web.active_backend`を参照する。YouTubeは`youtube`、GitHubは`github`、RSSは`rss`の`active_backend`を参照し、利用不可時は`tomos`を返す。

- [ ] **Step 4: テストを通す**

Run: `python3 scripts/test_agent_reach_adapter.py`

Expected: `agent reach adapter tests passed`。

- [ ] **Step 5: コミットする**

```bash
git add agent_reach_adapter.py scripts/test_agent_reach_adapter.py
git commit -m "Agent-Reach経路選択を追加する"
```

---

### Task 2: 許可済み実行とExa結果正規化

**Files:**
- Modify: `agent_reach_adapter.py`
- Modify: `scripts/test_agent_reach_adapter.py`

**Interfaces:**
- Consumes: `run_exa_search(query: str, limit: int, popen_factory=subprocess.Popen) -> list[dict[str, str]]`
- Produces: TOMOS共通結果`title`、`url`、`snippet`、`source`、`backend`、`routeReason`

- [ ] **Step 1: Exaコマンドと正規化の失敗テストを書く**

```python
def test_run_exa_search_uses_allowlisted_mcporter_command():
    def popen_factory(command, **kwargs):
        assert command[:2] == ["mcporter", "call"]
        assert "exa.web_search_exa" in command[2]
        return FakePopen(stdout=b'{"results":[{"title":"公式資料","url":"https://example.com/a","text":"本文"}]}')
    results = adapter.run_exa_search("公式資料", 3, popen_factory=popen_factory)
    assert results == [{
        "title": "公式資料", "url": "https://example.com/a", "snippet": "本文",
        "source": "agent-reach:web", "backend": "exa", "routeReason": "doctorで利用可能と確認",
    }]
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 scripts/test_agent_reach_adapter.py`

Expected: `AttributeError: module 'agent_reach_adapter' has no attribute 'run_exa_search'`。

- [ ] **Step 3: 実行器を実装する**

`mcporter`以外を受け取らず、タイムアウト20秒、出力2MB、結果最大10件とする。`subprocess.Popen`の出力を制限付きキューで段階的に読み、合計2MBを超えた時点でプロセスを停止する。読取終了は有界時間だけ待ち、解除不能な読取があっても呼出元を無期限停止させない。タイムアウト、非0終了、不正JSON、不正スキーマは日本語の`RouteExecutionError`へ変換する。

- [ ] **Step 4: 不正コマンド拒否テストを追加する**

```python
def test_execute_command_rejects_unlisted_binary():
    try:
        adapter.execute_allowed(["sh", "-c", "echo unsafe"])
    except adapter.RouteExecutionError:
        return
    raise AssertionError("許可されていない実行ファイルを拒否していません")
```

- [ ] **Step 5: テストを通してコミットする**

Run: `python3 scripts/test_agent_reach_adapter.py`

Expected: `agent reach adapter tests passed`。

```bash
git add agent_reach_adapter.py scripts/test_agent_reach_adapter.py
git commit -m "Exa検索結果をTOMOS形式へ変換する"
```

---

### Task 3: server.pyへ診断連動経路を接続

**Files:**
- Modify: `server.py:4951-4998`
- Modify: `server.py:5030-5159`
- Modify: `server.py:5938-5964`
- Modify: `scripts/test_server_helpers.py`

**Interfaces:**
- Consumes: `DoctorCache`、`select_route`、`run_exa_search`
- Produces: `internet_layer_context_results(..., diagnostics_out=None)`の既存結果と経路診断

診断取得は`[executable, "doctor", "--json"]`を使用し、JSON内の`active_backend`を経路選択へ渡す。

- [ ] **Step 1: 経路選択と一回フォールバックの失敗テストを書く**

```python
def test_web_search_uses_exa_then_tomos_once_on_failure():
    calls = []
    def failing_exa(query, limit):
        calls.append("exa")
        raise RuntimeError("exa unavailable")
    def tomos_search(query, limit):
        calls.append("tomos")
        return [{"title": "結果", "url": "https://example.com", "snippet": "本文"}]
    results, diagnostic = server.routed_web_search("質問", 4, failing_exa, tomos_search)
    assert calls == ["exa", "tomos"]
    assert diagnostic["fallback"] is True
    assert results[0]["title"] == "結果"
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -c 'import scripts.test_server_helpers as t; t.test_web_search_uses_exa_then_tomos_once_on_failure()'`

Expected: `AttributeError`で失敗する。

- [ ] **Step 3: 既存4チャネルへ経路判断を接続する**

Web検索は`routed_web_search`、URL本文は`web_reader_result`、YouTubeは`youtube_transcript_result`、GitHubは`github_repo_result`、RSSは`rss_feed_result`をフォールバックとして保持する。診断で利用不可の場合は優先経路を呼ばず、直接フォールバックへ進む。

- [ ] **Step 4: Agent-Reach未導入回帰テストを追加する**

```python
def test_missing_agent_reach_keeps_existing_web_search():
    decision = adapter.select_route("web", {"installed": False}, intent="search")
    assert decision.backend == "tomos"
    assert decision.fallback == ""
```

- [ ] **Step 5: 全サーバーテストを通してコミットする**

Run: `python3 scripts/test_server_helpers.py`

Expected: `server helper tests passed`。

```bash
git add server.py scripts/test_server_helpers.py agent_reach_adapter.py
git commit -m "Web調査をAgent-Reach診断へ接続する"
```

---

### Task 4: 使用経路を回答診断へ表示

**Files:**
- Modify: `server.py:4375-4435`
- Modify: `web/app.js`
- Modify: `web/i18n.js`
- Modify: `scripts/test-search-helpers.js`
- Modify: `scripts/test_server_helpers.py`

**Interfaces:**
- Consumes: `backend`、`routeReason`、`fallback`、`errorCode`
- Produces: 回答下診断「使用経路」「フォールバック」「確認方法」

- [ ] **Step 1: API診断形状の失敗テストを書く**

```python
def test_route_diagnostic_hides_raw_stderr():
    diagnostic = server.route_diagnostic("web", "exa", True, "/Users/name/.config/token")
    assert diagnostic["label"] == "使用経路"
    assert diagnostic["message"] == "Exaから現行Web検索へ切り替えました。"
    assert "/Users/" not in json.dumps(diagnostic, ensure_ascii=False)
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -c 'import scripts.test_server_helpers as t; t.test_route_diagnostic_hides_raw_stderr()'`

Expected: `AttributeError`で失敗する。

- [ ] **Step 3: 日本語診断を実装する**

成功時は`Jina`、`Exa`、`yt-dlp`、`gh`、`feedparser`の表示名だけを示す。フォールバック時は短い理由を示し、生の標準エラー、ローカルパス、Cookie、Tokenを表示しない。

- [ ] **Step 4: UIテストを追加して通す**

Run: `node scripts/test-search-helpers.js && python3 scripts/test_server_helpers.py`

Expected: 両方とも成功する。

- [ ] **Step 5: コミットする**

```bash
git add server.py web/app.js web/i18n.js scripts/test-search-helpers.js scripts/test_server_helpers.py
git commit -m "Web調査の使用経路を表示する"
```

---

### Task 5: 汎用Web調査回帰とリリース

**Files:**
- Create: `scripts/test-agent-reach-routing-smoke.py`
- Modify: `server.py`
- Modify: `Gemma4_12B_Web.command`
- Modify: `Gemma4_12B_全部起動.command`
- Modify: `Gemma4_12B_Web.bat`
- Modify: `Gemma4_12B_All_Start.bat`

**Interfaces:**
- Consumes: 4チャネルの統合結果
- Produces: 次のパッチバージョンとMac・Windows配布物

- [ ] **Step 1: ローカルスモークテストを書く**

スモークテストは外部通信をモックし、Web本文、Web検索、YouTube、GitHub、RSSの各結果に`backend`と`routeReason`があり、架空項目を追加せず、長期記憶保存関数を呼ばないことを検証する。

- [ ] **Step 2: 全テストを実行する**

```bash
python3 scripts/test_agent_reach_adapter.py
python3 scripts/test_server_helpers.py
python3 scripts/test-agent-reach-routing-smoke.py
node scripts/test-search-helpers.js
node scripts/test-pwa-assets.js
python3 -m py_compile server.py agent_reach_adapter.py
git diff --check
```

Expected: 全コマンドが終了コード0になる。

- [ ] **Step 3: 手動確認する**

Webページ要約、公式一覧、字幕付きYouTube、公開GitHub、RSSを各1件確認する。Agent-Reachを一時的に利用不可として同じ5件を再実行し、現行TOMOS経路へ一度だけ切り替わることを確認する。

- [ ] **Step 4: バージョンを同期する**

`server.py`と4起動ファイルを`0.8.218`へ更新し、`node scripts/test-pwa-assets.js`で一致を確認する。

- [ ] **Step 5: リリースする**

コミット前に`git status --short --branch`、`git diff`、`git diff --staged`を確認する。ファイル数、削除、変更行数の安全停止条件を満たした場合はユーザー承認を得る。承認後に`main`へプッシュし、Mac ZIP・PKG、Windows ZIP・MSIをGitHub Releaseへ添付する。
