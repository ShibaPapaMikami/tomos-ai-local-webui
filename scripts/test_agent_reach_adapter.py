from pathlib import Path
import io
import os
import subprocess
import sys
import threading
import time


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_reach_adapter as adapter


class FakePopen:
    def __init__(
        self,
        stdout=b"",
        stderr=b"",
        returncode=0,
        times_out=False,
        terminate_hangs=False,
    ):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = None
        self._planned_returncode = returncode
        self.times_out = times_out
        self.terminate_hangs = terminate_hangs
        self.waited = False
        self.terminated = False
        self.killed = False

    @property
    def stopped(self):
        return self.waited or self.terminated or self.killed

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.waited = True
        if self.times_out or (self.terminated and self.terminate_hangs and not self.killed):
            raise subprocess.TimeoutExpired("mcporter", timeout)
        self.returncode = self._planned_returncode
        return self.returncode

    def terminate(self):
        self.terminated = True
        if not self.terminate_hangs:
            self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def expect_route_error(action):
    try:
        action()
    except adapter.RouteExecutionError:
        return
    raise AssertionError("RouteExecutionErrorを送出していません")


def test_run_exa_search_uses_allowlisted_mcporter_command():
    process = FakePopen(
        '{"results":[{"title":"公式資料","url":"https://example.com/a","text":"本文"}]}'.encode()
    )

    def popen_factory(command, **kwargs):
        assert command[:2] == ["mcporter", "call"]
        assert command[2] == 'exa.web_search_exa(query: "公式資料", numResults: 3)'
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.PIPE
        if os.name == "posix":
            assert kwargs["start_new_session"] is True
        elif os.name == "nt":
            assert kwargs["creationflags"] == subprocess.CREATE_NEW_PROCESS_GROUP
        return process

    results = adapter.run_exa_search("公式資料", 3, popen_factory=popen_factory)

    assert results == [{
        "title": "公式資料",
        "url": "https://example.com/a",
        "snippet": "本文",
        "source": "agent-reach:web",
        "backend": "exa",
        "routeReason": "doctorで利用可能と確認",
    }]
    assert process.stopped


def test_execute_allowed_rejects_unlisted_binary():
    try:
        adapter.execute_allowed(["sh", "-c", "echo unsafe"])
    except adapter.RouteExecutionError:
        return
    raise AssertionError("許可されていない実行ファイルを拒否していません")


def test_execute_allowed_rejects_malformed_mcporter_expression():
    def should_not_start(*_args, **_kwargs):
        raise AssertionError("不正な式でプロセスを開始しました")

    malformed = [
        ["mcporter", "call", 'exa.web_search_exa(query: "質問", numResults: 11)'],
        ["mcporter", "call", 'exa.web_search_exa(query: "質問", numResults: 1); unsafe()'],
        ["mcporter", "call", 'exa.web_search_exa(query: invalid, numResults: 1)'],
    ]
    for command in malformed:
        expect_route_error(
            lambda command=command: adapter.execute_allowed(command, popen_factory=should_not_start)
        )

    expect_route_error(
        lambda: adapter.execute_allowed(
            ["mcporter", "call", 1], popen_factory=should_not_start
        )
    )


def test_run_exa_search_caps_results_at_ten():
    response = {
        "results": [
            {"title": f"資料{index}", "url": f"https://example.com/{index}", "text": "本文"}
            for index in range(12)
        ]
    }

    def popen_factory(command, **kwargs):
        assert command[2].endswith("numResults: 10)")
        return FakePopen(str(response).replace("'", '"').encode())

    assert len(adapter.run_exa_search("上限", 99, popen_factory=popen_factory)) == 10


def test_run_exa_search_converts_execution_failure_to_route_error():
    process = FakePopen(stderr="実行失敗".encode(), returncode=1)

    expect_route_error(
        lambda: adapter.run_exa_search("失敗", 1, popen_factory=lambda *_args, **_kwargs: process)
    )
    assert process.stopped


def test_run_exa_search_rejects_output_over_two_megabytes():
    process = FakePopen(stdout=b"x" * (2 * 1024 * 1024 + 1))

    expect_route_error(
        lambda: adapter.run_exa_search("大きい出力", 1, popen_factory=lambda *_args, **_kwargs: process)
    )
    assert process.terminated


def test_run_exa_search_rejects_combined_output_over_two_megabytes():
    half = 1024 * 1024
    process = FakePopen(stdout=b"x" * half, stderr=b"y" * (half + 1))

    expect_route_error(
        lambda: adapter.run_exa_search("合算上限", 1, popen_factory=lambda *_args, **_kwargs: process)
    )
    assert process.terminated


def test_run_exa_search_stops_process_on_timeout_and_invalid_json():
    timeout_process = FakePopen(times_out=True, terminate_hangs=True)
    invalid_json_process = FakePopen(stdout=b"{")

    expect_route_error(
        lambda: adapter.run_exa_search("タイムアウト", 1, popen_factory=lambda *_args, **_kwargs: timeout_process)
    )
    expect_route_error(
        lambda: adapter.run_exa_search("不正JSON", 1, popen_factory=lambda *_args, **_kwargs: invalid_json_process)
    )
    assert timeout_process.terminated
    assert timeout_process.killed
    assert timeout_process.stdout.closed
    assert timeout_process.stderr.closed
    assert invalid_json_process.stopped


def test_timeout_waits_for_reader_threads_to_finish():
    class SlowCloseStream:
        def __init__(self):
            self.closed = False
            self.release = threading.Event()

        def read(self, _size):
            self.release.wait()
            time.sleep(1.1)
            return b""

        def close(self):
            self.closed = True
            self.release.set()

    process = FakePopen(times_out=True)
    process.stdout = SlowCloseStream()
    created = []
    original_thread = adapter.Thread
    original_timeout = adapter.COMMAND_TIMEOUT_SECONDS
    original_join_timeout = adapter.READER_JOIN_TIMEOUT_SECONDS

    def tracking_thread(*args, **kwargs):
        thread = original_thread(*args, **kwargs)
        created.append(thread)
        return thread

    try:
        adapter.Thread = tracking_thread
        adapter.COMMAND_TIMEOUT_SECONDS = 0.01
        adapter.READER_JOIN_TIMEOUT_SECONDS = 2
        expect_route_error(
            lambda: adapter.run_exa_search(
                "タイムアウト",
                1,
                popen_factory=lambda *_args, **_kwargs: process,
            )
        )
    finally:
        adapter.Thread = original_thread
        adapter.COMMAND_TIMEOUT_SECONDS = original_timeout
        adapter.READER_JOIN_TIMEOUT_SECONDS = original_join_timeout

    assert created
    assert all(not thread.is_alive() for thread in created)


def test_timeout_does_not_hang_on_uninterruptible_reader():
    class StubbornStream:
        def __init__(self):
            self.closed = False

        def read(self, _size):
            time.sleep(1)
            return b""

        def close(self):
            self.closed = True

    process = FakePopen(times_out=True)
    process.stdout = StubbornStream()
    created = []
    original_thread = adapter.Thread
    original_timeout = adapter.COMMAND_TIMEOUT_SECONDS
    original_join_timeout = adapter.READER_JOIN_TIMEOUT_SECONDS

    def tracking_thread(*args, **kwargs):
        thread = original_thread(*args, **kwargs)
        created.append(thread)
        return thread

    started = time.monotonic()
    try:
        adapter.Thread = tracking_thread
        adapter.COMMAND_TIMEOUT_SECONDS = 0.01
        adapter.READER_JOIN_TIMEOUT_SECONDS = 0.05
        expect_route_error(
            lambda: adapter.run_exa_search(
                "解除不能",
                1,
                popen_factory=lambda *_args, **_kwargs: process,
            )
        )
    finally:
        adapter.Thread = original_thread
        adapter.COMMAND_TIMEOUT_SECONDS = original_timeout
        adapter.READER_JOIN_TIMEOUT_SECONDS = original_join_timeout

    assert time.monotonic() - started < 0.5
    assert created
    assert all(thread.daemon for thread in created)


def test_windows_process_tree_uses_taskkill():
    process = FakePopen(times_out=True)
    process.pid = 1234
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return type("Result", (), {"returncode": 0})()

    assert adapter._stop_windows_process_tree(process, runner=runner) is True

    assert calls == [(
        ["taskkill", "/PID", "1234", "/T", "/F"],
        {"check": False, "capture_output": True, "timeout": 2},
    )]


def test_windows_process_tree_reports_taskkill_failure():
    process = FakePopen(times_out=True)
    process.pid = 1234

    def runner(_command, **_kwargs):
        return type("Result", (), {"returncode": 1})()

    assert adapter._stop_windows_process_tree(process, runner=runner) is False


def test_stopped_parent_still_terminates_posix_process_group():
    if os.name != "posix":
        return
    process = FakePopen(returncode=0)
    process.returncode = 0
    process.pid = 4321
    calls = []
    original_killpg = adapter.os.killpg

    try:
        adapter.os.killpg = lambda pid, sig: calls.append((pid, sig))
        adapter._stop_process(process)
    finally:
        adapter.os.killpg = original_killpg

    assert calls == [
        (4321, adapter.signal.SIGTERM),
        (4321, adapter.signal.SIGKILL),
    ]


def test_run_exa_search_rejects_invalid_results_schema():
    for payload in (
        b"[]",
        b"{}",
        b'{"results":{}}',
        b'{"results":[1]}',
        b'{"results":[{}]}',
        b'{"results":[{"title":"","url":"https://example.com","text":"body"}]}',
        b'{"results":[{"title":"title","url":1,"text":"body"}]}',
        b'{"results":[{"title":"title","url":"https://example.com","text":null}]}',
    ):
        process = FakePopen(stdout=payload)
        expect_route_error(
            lambda: adapter.run_exa_search("不正形式", 1, popen_factory=lambda *_args, **_kwargs: process)
        )
        assert process.stopped


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
        test_execute_allowed_rejects_malformed_mcporter_expression,
        test_run_exa_search_caps_results_at_ten,
        test_run_exa_search_converts_execution_failure_to_route_error,
        test_run_exa_search_rejects_output_over_two_megabytes,
        test_run_exa_search_rejects_combined_output_over_two_megabytes,
        test_run_exa_search_stops_process_on_timeout_and_invalid_json,
        test_timeout_waits_for_reader_threads_to_finish,
        test_timeout_does_not_hang_on_uninterruptible_reader,
        test_windows_process_tree_uses_taskkill,
        test_windows_process_tree_reports_taskkill_failure,
        test_stopped_parent_still_terminates_posix_process_group,
        test_run_exa_search_rejects_invalid_results_schema,
        test_doctor_cache_reuses_result_for_five_minutes,
        test_select_route_uses_exa_only_for_search,
        test_select_route_uses_channel_backend_for_non_web_channels,
        test_select_route_falls_back_to_tomos_when_channel_is_unavailable,
        test_select_route_rejects_unsupported_active_backend,
        test_doctor_cache_refreshes_at_five_minutes,
    ):
        test()
    print("agent reach adapter tests passed")
