from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_reach_adapter as adapter


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
            "github": {"status": "ok", "active_backend": "gh"},
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
        test_doctor_cache_reuses_result_for_five_minutes,
        test_select_route_uses_exa_only_for_search,
        test_select_route_uses_channel_backend_for_non_web_channels,
        test_select_route_falls_back_to_tomos_when_channel_is_unavailable,
        test_doctor_cache_refreshes_at_five_minutes,
    ):
        test()
    print("agent reach adapter tests passed")
