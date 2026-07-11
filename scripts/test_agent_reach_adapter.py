from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_reach_adapter as adapter


class FakeResult:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_exa_search_uses_allowlisted_mcporter_command():
    def runner(command, **kwargs):
        assert command[:2] == ["mcporter", "call"]
        assert command[2] == 'exa.web_search_exa(query: "公式資料", numResults: 3)'
        assert kwargs == {"check": False, "capture_output": True, "timeout": 20}
        return FakeResult(
            0,
            '{"results":[{"title":"公式資料","url":"https://example.com/a","text":"本文"}]}'.encode(),
            b"",
        )

    results = adapter.run_exa_search("公式資料", 3, runner=runner)

    assert results == [{
        "title": "公式資料",
        "url": "https://example.com/a",
        "snippet": "本文",
        "source": "agent-reach:web",
        "backend": "exa",
        "routeReason": "doctorで利用可能と確認",
    }]


def test_execute_allowed_rejects_unlisted_binary():
    try:
        adapter.execute_allowed(["sh", "-c", "echo unsafe"])
    except adapter.RouteExecutionError:
        return
    raise AssertionError("許可されていない実行ファイルを拒否していません")


def test_run_exa_search_caps_results_at_ten():
    response = {
        "results": [
            {"title": f"資料{index}", "url": f"https://example.com/{index}", "text": "本文"}
            for index in range(12)
        ]
    }

    def runner(command, **kwargs):
        assert command[2].endswith("numResults: 10)")
        return FakeResult(0, str(response).replace("'", '"').encode(), b"")

    assert len(adapter.run_exa_search("上限", 99, runner=runner)) == 10


def test_run_exa_search_converts_execution_failure_to_route_error():
    def runner(command, **kwargs):
        return FakeResult(1, b"", "実行失敗".encode())

    try:
        adapter.run_exa_search("失敗", 1, runner=runner)
    except adapter.RouteExecutionError as error:
        assert "実行に失敗" in str(error)
        return
    raise AssertionError("実行失敗をRouteExecutionErrorへ変換していません")


def test_run_exa_search_rejects_output_over_two_megabytes():
    def runner(command, **kwargs):
        return FakeResult(0, b"x" * (2 * 1024 * 1024 + 1), b"")

    try:
        adapter.run_exa_search("大きい出力", 1, runner=runner)
    except adapter.RouteExecutionError as error:
        assert "出力上限" in str(error)
        return
    raise AssertionError("2MB超の出力を拒否していません")


def test_doctor_cache_reuses_result_for_five_minutes():
    calls = []
    cache = adapter.DoctorCache(
        lambda: calls.append(True)
        or {"channels": {"web": {"status": "ok", "active_backend": "Jina Reader"}}}
    )
    assert cache.get(now=100)["channels"]["web"]["active_backend"] == "Jina Reader"
    assert cache.get(now=399)["channels"]["web"]["active_backend"] == "Jina Reader"
    assert len(calls) == 1


def test_select_route_uses_exa_only_for_search():
    doctor = {
        "channels": {
            "web": {"status": "ok", "active_backend": "Jina Reader"},
            "exa_search": {"status": "ok", "active_backend": "Exa via mcporter"},
        }
    }
    assert adapter.select_route("web", doctor, intent="search").backend == "exa"
    assert adapter.select_route("web", doctor, intent="read").backend == "jina"


def test_select_route_uses_channel_backend_for_non_web_channels():
    doctor = {
        "channels": {
            "youtube": {"status": "ok", "active_backend": "yt-dlp"},
            "github": {"status": "ok", "active_backend": "gh CLI"},
            "rss": {"status": "ok", "active_backend": "feedparser"},
        }
    }
    assert adapter.select_route("youtube", doctor).backend == "youtube"
    assert adapter.select_route("github", doctor).backend == "github"
    assert adapter.select_route("rss", doctor).backend == "rss"


def test_select_route_falls_back_to_tomos_when_channel_is_unavailable():
    decision = adapter.select_route("web", {"installed": False}, intent="search")
    assert decision.backend == "tomos"
    assert decision.fallback == ""


def test_select_route_rejects_unsupported_active_backend():
    doctor = {
        "channels": {
            "web": {"status": "ok", "active_backend": "unsupported"},
        }
    }
    assert adapter.select_route("web", doctor).backend == "tomos"


def test_doctor_cache_refreshes_at_five_minutes():
    calls = []
    cache = adapter.DoctorCache(
        lambda: calls.append(len(calls)) or {"version": len(calls) - 1}
    )
    assert cache.get(now=100)["version"] == 0
    assert cache.get(now=400)["version"] == 1
    assert calls == [0, 1]


if __name__ == "__main__":
    for test in (
        test_run_exa_search_uses_allowlisted_mcporter_command,
        test_execute_allowed_rejects_unlisted_binary,
        test_run_exa_search_caps_results_at_ten,
        test_run_exa_search_converts_execution_failure_to_route_error,
        test_run_exa_search_rejects_output_over_two_megabytes,
        test_doctor_cache_reuses_result_for_five_minutes,
        test_select_route_uses_exa_only_for_search,
        test_select_route_uses_channel_backend_for_non_web_channels,
        test_select_route_falls_back_to_tomos_when_channel_is_unavailable,
        test_select_route_rejects_unsupported_active_backend,
        test_doctor_cache_refreshes_at_five_minutes,
    ):
        test()
    print("agent reach adapter tests passed")
