from pathlib import Path
from contextlib import contextmanager
import re
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


EXPECTED_APP_VERSION = "0.8.221"


class FixedDoctorCache:
    def get(self):
        return {
            "installed": True,
            "channels": {
                "web": {"status": "ok", "active_backend": "Jina Reader"},
                "exa_search": {"status": "ok", "active_backend": "Exa via mcporter"},
                "youtube": {"status": "ok", "active_backend": "yt-dlp"},
                "github": {"status": "ok", "active_backend": "gh CLI"},
                "rss": {"status": "ok", "active_backend": "feedparser"},
            },
        }


class UnavailableDoctorCache:
    def get(self):
        return {"installed": False}


def unexpected_long_term_memory_save(*_args, **_kwargs):
    raise AssertionError("Web調査経路が長期記憶保存を呼び出しました")


@contextmanager
def block_long_term_memory_saves():
    names = ("context_memory_save_payload", "remember", "save_context_record")
    originals = {name: getattr(server, name) for name in names}
    try:
        for name in names:
            setattr(server, name, unexpected_long_term_memory_save)
        yield
    finally:
        for name, original in originals.items():
            setattr(server, name, original)


def assert_public_route(diagnostic, channel, backend):
    assert diagnostic == {
        "type": "route",
        "status": "success",
        "label": "使用経路",
        "message": f"{backend}を使用しました。",
        "howToSucceed": "利用可能な経路で確認しています。",
        "channel": channel,
        "backend": backend,
        "fallback": False,
        "errorCode": "",
    }


def assert_routed_result(
    query,
    channel,
    expected,
    reader,
    backend,
    cache=FixedDoctorCache(),
    diagnostic_backend=None,
):
    diagnostics = []
    results, error = server.internet_layer_context_results(
        query,
        [channel],
        doctor_cache=cache,
        diagnostics_out=diagnostics,
        **{f"{channel}_reader": reader},
    )
    assert error == ""
    assert results == [{
        **expected,
        "backend": backend.lower().replace("youtube字幕", "youtube"),
        "routeReason": cache.get().get("installed") is False
        and "doctorで利用不可のため現行TOMOS経路を使用"
        or "doctorで利用可能と確認",
    }]
    assert_public_route(diagnostics[0], channel, diagnostic_backend or backend)


def test_mocked_generic_web_routing():
    web_result = {
        "title": "Webページ本文: 公式ページ",
        "url": "https://example.com/article",
        "snippet": "確認済み本文",
        "source": "agent-reach:web",
    }
    youtube_result = {
        "title": "YouTube動画: 固定動画",
        "url": "https://www.youtube.com/watch?v=mock123",
        "snippet": "動画タイトル: 固定動画\n\n字幕抜粋:\n固定字幕",
        "source": "agent-reach:youtube",
        "videoId": "mock123",
    }
    github_result = {
        "title": "GitHubリポジトリ: openai/codex",
        "url": "https://github.com/openai/codex",
        "snippet": "リポジトリ: openai/codex",
        "source": "agent-reach:github",
    }
    rss_result = {
        "title": "RSSフィード: 固定フィード",
        "url": "https://example.com/feed.xml",
        "snippet": "RSS/Atom: 固定フィード\n- 固定記事",
        "source": "agent-reach:rss",
    }
    calls = []

    def web_reader(url):
        calls.append(("web", url))
        return web_result

    def youtube_reader(url, runner=None):
        calls.append(("youtube", url))
        return youtube_result

    def github_reader(repo, runner=None):
        calls.append(("github", repo))
        return github_result

    def rss_reader(url):
        calls.append(("rss", url))
        return rss_result

    assert_routed_result(
        "https://example.com/article を要約して",
        "web",
        web_result,
        web_reader,
        "Jina",
    )
    assert_routed_result(
        "https://www.youtube.com/watch?v=mock123 を分析して",
        "youtube",
        youtube_result,
        youtube_reader,
        "YouTube字幕",
    )
    assert_routed_result(
        "https://github.com/openai/codex を確認して",
        "github",
        github_result,
        github_reader,
        "GitHub",
    )
    assert_routed_result(
        "https://example.com/feed.xml のRSSを確認して",
        "rss",
        rss_result,
        rss_reader,
        "RSS",
    )

    assert calls == [
        ("web", "https://example.com/article"),
        ("youtube", "https://www.youtube.com/watch?v=mock123"),
        ("github", "openai/codex"),
        ("rss", "https://example.com/feed.xml"),
    ]


def test_mocked_web_search_route():
    expected = [{
        "title": "固定検索結果",
        "url": "https://example.com/search-result",
        "snippet": "固定検索本文",
        "source": "agent-reach:web",
    }]
    calls = []

    def exa_search(query, limit):
        calls.append(("exa", query, limit))
        return expected

    def tomos_search(*_args):
        raise AssertionError("優先経路が成功したためTOMOS検索を呼び出してはいけません")

    decision = server.RouteDecision("web", "exa", "tomos", "doctorで利用可能と確認")
    results, diagnostic = server.web_search_results_for_decision(
        decision, "固定検索", 3, exa_search, tomos_search
    )
    assert expected == [{
        "title": "固定検索結果",
        "url": "https://example.com/search-result",
        "snippet": "固定検索本文",
        "source": "agent-reach:web",
    }]
    assert results == [{
        **expected[0],
        "backend": "exa",
        "routeReason": "doctorで利用可能と確認",
    }]
    assert results[0] is not expected[0]
    assert calls == [("exa", "固定検索", 3)]
    assert_public_route(diagnostic, "web", "Exa")


def test_unavailable_routes_use_tomos_and_search_once():
    cache = UnavailableDoctorCache()
    cases = [
        ("web", "https://example.com/article を要約して", {"title": "Webページ本文: 固定", "url": "https://example.com/article", "snippet": "本文", "source": "agent-reach:web"}, "web_reader"),
        ("youtube", "https://www.youtube.com/watch?v=mock123 を分析して", {"title": "YouTube動画: 固定", "url": "https://www.youtube.com/watch?v=mock123", "snippet": "字幕", "source": "agent-reach:youtube"}, "youtube_reader"),
        ("github", "https://github.com/openai/codex を確認して", {"title": "GitHubリポジトリ: openai/codex", "url": "https://github.com/openai/codex", "snippet": "本文", "source": "agent-reach:github"}, "github_reader"),
        ("rss", "https://example.com/feed.xml のRSSを確認して", {"title": "RSSフィード: 固定", "url": "https://example.com/feed.xml", "snippet": "本文", "source": "agent-reach:rss"}, "rss_reader"),
    ]
    for channel, query, expected, reader_name in cases:
        reader = lambda *_args, result=expected, **_kwargs: result
        assert_routed_result(
            query,
            channel,
            expected,
            reader,
            "tomos",
            cache,
            "TOMOS標準検索",
        )

    calls = []
    expected = [{
        "title": "TOMOS結果",
        "url": "https://example.com",
        "snippet": "本文",
        "source": "agent-reach:web",
    }]
    decision = server.RouteDecision("web", "tomos", "", "doctorで利用不可のため現行TOMOS経路を使用")
    results, diagnostic = server.web_search_results_for_decision(
        decision,
        "固定検索",
        3,
        lambda *_args: (_ for _ in ()).throw(AssertionError("Exaを呼び出してはいけません")),
        lambda query, limit: calls.append((query, limit)) or expected,
    )
    assert calls == [("固定検索", 3)]
    assert expected == [{
        "title": "TOMOS結果",
        "url": "https://example.com",
        "snippet": "本文",
        "source": "agent-reach:web",
    }]
    assert results == [{
        **expected[0],
        "backend": "tomos",
        "routeReason": "doctorで利用不可のため現行TOMOS経路を使用",
    }]
    assert results[0] is not expected[0]
    assert_public_route(diagnostic, "web", "TOMOS標準検索")


def test_exa_failure_uses_tomos_once():
    calls = []
    expected = [{
        "title": "TOMOS結果",
        "url": "https://example.com",
        "snippet": "本文",
        "source": "agent-reach:web",
    }]
    decision = server.RouteDecision("web", "exa", "tomos", "doctorで利用可能と確認")
    results, diagnostic = server.web_search_results_for_decision(
        decision,
        "固定検索",
        3,
        lambda query, limit: calls.append(("exa", query, limit)) or (_ for _ in ()).throw(RuntimeError("失敗")),
        lambda query, limit: calls.append(("tomos", query, limit)) or expected,
    )
    assert calls == [("exa", "固定検索", 3), ("tomos", "固定検索", 3)]
    assert expected == [{
        "title": "TOMOS結果",
        "url": "https://example.com",
        "snippet": "本文",
        "source": "agent-reach:web",
    }]
    assert results == [{
        **expected[0],
        "backend": "tomos",
        "routeReason": "ExaからTOMOS標準検索へ切り替えました。",
    }]
    assert results[0] is not expected[0]
    assert diagnostic["fallback"] is True


def test_app_version_is_ready_for_release():
    assert server.APP_VERSION == EXPECTED_APP_VERSION
    root = Path(__file__).resolve().parents[1]
    for name in (
        "Gemma4_12B_Web.command",
        "Gemma4_12B_全部起動.command",
        "Gemma4_12B_Web.bat",
        "Gemma4_12B_All_Start.bat",
    ):
        launcher = (root / name).read_text(encoding="utf-8")
        match = re.search(r'(?:APP_VERSION="|set GEMMA_APP_VERSION=)([0-9]+\.[0-9]+\.[0-9]+)', launcher)
        assert match is not None
        assert match.group(1) == EXPECTED_APP_VERSION


def run_smoke_suite():
    originals = {
        name: getattr(server, name)
        for name in ("context_memory_save_payload", "remember", "save_context_record")
    }
    with block_long_term_memory_saves():
        test_mocked_generic_web_routing()
        test_mocked_web_search_route()
        test_unavailable_routes_use_tomos_and_search_once()
        test_exa_failure_uses_tomos_once()
        test_app_version_is_ready_for_release()
    assert all(getattr(server, name) is original for name, original in originals.items())


if __name__ == "__main__":
    run_smoke_suite()
    print("agent reach routing smoke tests passed")
