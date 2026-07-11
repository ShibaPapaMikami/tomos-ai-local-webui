from dataclasses import dataclass
import json
import os
from queue import Empty, Full, Queue
import re
import signal
import subprocess
from threading import Condition, Event, Thread
import time
from typing import Callable


DOCTOR_CACHE_SECONDS = 300
COMMAND_TIMEOUT_SECONDS = 20
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_EXA_RESULTS = 10
READ_CHUNK_BYTES = 64 * 1024
READER_JOIN_TIMEOUT_SECONDS = 1
_OUTPUT_LIMIT_MARKER = object()
_EXA_CALL_PATTERN = re.compile(
    r'exa\.web_search_exa\(query: (?P<query>"(?:\\.|[^"\\])*"), '
    r'numResults: (?P<limit>[1-9]|10)\)'
)
_AVAILABLE_STATUSES = {"ok", "ready", "available"}
_ALLOWED_BACKENDS = {
    "web": {"Jina Reader": "jina"},
    "exa_search": {"Exa via mcporter": "exa"},
    "youtube": {"yt-dlp": "youtube"},
    "github": {"gh CLI": "github"},
    "rss": {"feedparser": "rss"},
}


@dataclass(frozen=True)
class RouteDecision:
    channel: str
    backend: str
    fallback: str
    reason: str


class RouteExecutionError(RuntimeError):
    pass


class _OutputLimitExceeded(Exception):
    pass


class _CommandTimedOut(Exception):
    pass


class DoctorCache:
    def __init__(self, loader: Callable[[], dict[str, object]]) -> None:
        self.loader: Callable[[], dict[str, object]] = loader
        self.value: dict[str, object] | None = None
        self.loaded_at = 0.0

    def get(self, now: float | None = None) -> dict[str, object]:
        current = time.monotonic() if now is None else now
        if self.value is None or current - self.loaded_at >= DOCTOR_CACHE_SECONDS:
            self.value = self.loader()
            self.loaded_at = current
        return self.value


def _normalized_backend(
    doctor: dict[str, object], channel: str
) -> str | None:
    if doctor.get("installed") is False:
        return None
    channels = doctor.get("channels", {})
    if not isinstance(channels, dict):
        return None
    status = channels.get(channel, {})
    if not isinstance(status, dict):
        return None
    if status.get("status") not in _AVAILABLE_STATUSES:
        return None
    active_backend = status.get("active_backend")
    if not isinstance(active_backend, str):
        return None
    return _ALLOWED_BACKENDS.get(channel, {}).get(active_backend)


def select_route(
    channel: str, doctor: dict[str, object], intent: str = "read"
) -> RouteDecision:
    if channel == "web" and intent == "search":
        doctor_channel = "exa_search"
    else:
        doctor_channel = channel

    backend = _normalized_backend(doctor, doctor_channel)
    if backend is not None:
        return RouteDecision(
            channel=channel,
            backend=backend,
            fallback="tomos",
            reason="doctorで利用可能と確認",
        )

    return RouteDecision(
        channel=channel,
        backend="tomos",
        fallback="",
        reason="doctorで利用不可のため現行TOMOS経路を使用",
    )


def execute_allowed(
    command: list[str], popen_factory: Callable[..., object] = subprocess.Popen
) -> tuple[bytes, bytes]:
    if len(command) != 3 or command[:2] != ["mcporter", "call"]:
        raise RouteExecutionError("許可されていない実行コマンドです")
    if not isinstance(command[2], str):
        raise RouteExecutionError("許可されていない実行コマンドです")
    match = _EXA_CALL_PATTERN.fullmatch(command[2])
    if match is None:
        raise RouteExecutionError("許可されていない実行コマンドです")
    try:
        query = json.loads(match.group("query"))
    except json.JSONDecodeError as error:
        raise RouteExecutionError("許可されていない実行コマンドです") from error
    if not isinstance(query, str):
        raise RouteExecutionError("許可されていない実行コマンドです")

    try:
        process_options = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        if os.name == "posix":
            process_options["start_new_session"] = True
        elif os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        process = popen_factory(
            command,
            **process_options,
        )
    except OSError as error:
        raise RouteExecutionError("Exa検索の実行に失敗しました") from error

    try:
        stdout, stderr = _read_process_output(process)
    except _OutputLimitExceeded as error:
        _stop_process(process)
        raise RouteExecutionError("Exa検索の出力上限を超えました")
    except _CommandTimedOut as error:
        _stop_process(process)
        raise RouteExecutionError("Exa検索の実行が20秒でタイムアウトしました") from error

    if getattr(process, "returncode", 1) != 0:
        raise RouteExecutionError("Exa検索の実行に失敗しました")
    return stdout, stderr


def run_exa_search(
    query: str, limit: int, popen_factory: Callable[..., object] = subprocess.Popen
) -> list[dict[str, str]]:
    capped_limit = max(1, min(limit, MAX_EXA_RESULTS))
    call = (
        f"exa.web_search_exa(query: {json.dumps(query, ensure_ascii=False)}, "
        f"numResults: {capped_limit})"
    )
    output, _ = execute_allowed(["mcporter", "call", call], popen_factory=popen_factory)

    try:
        payload = json.loads(output.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RouteExecutionError("Exa検索結果の読み込みに失敗しました") from error

    if not isinstance(payload, dict) or "results" not in payload:
        raise RouteExecutionError("Exa検索結果の形式が不正です")
    raw_results = payload["results"]
    if not isinstance(raw_results, list):
        raise RouteExecutionError("Exa検索結果の形式が不正です")

    normalized_results: list[dict[str, str]] = []
    for item in raw_results[:MAX_EXA_RESULTS]:
        if not isinstance(item, dict):
            raise RouteExecutionError("Exa検索結果の形式が不正です")
        title = _required_text(item, "title")
        url = _required_text(item, "url")
        snippet = _required_text(item, "text")
        normalized_results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "source": "agent-reach:web",
            "backend": "exa",
            "routeReason": "doctorで利用可能と確認",
        })

    return normalized_results


class _OutputBudget:
    def __init__(self) -> None:
        self.condition = Condition()
        self.available = MAX_OUTPUT_BYTES
        self.committed = 0
        self.probe_active = False

    def reserve(self, stopped: Event) -> tuple[int, bool] | None:
        with self.condition:
            while not stopped.is_set():
                if self.available > 0:
                    size = min(READ_CHUNK_BYTES, self.available)
                    self.available -= size
                    return size, False
                if self.committed >= MAX_OUTPUT_BYTES and not self.probe_active:
                    self.probe_active = True
                    return 1, True
                self.condition.wait(timeout=0.05)
        return None

    def complete(self, reserved: int, actual: int, probe: bool) -> None:
        with self.condition:
            if probe:
                self.probe_active = False
            else:
                self.available += reserved - actual
                self.committed += actual
            self.condition.notify_all()


def _read_process_output(process: object) -> tuple[bytes, bytes]:
    events: Queue[tuple[bool, object]] = Queue(maxsize=4)
    stopped = Event()
    budget = _OutputBudget()
    threads = [
        Thread(
            target=_read_stream,
            args=(stream, is_stderr, events, stopped, budget),
            daemon=True,
        )
        for is_stderr, stream in ((False, getattr(process, "stdout", None)), (True, getattr(process, "stderr", None)))
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
    output = [bytearray(), bytearray()]
    complete = 0
    try:
        while complete < len(threads):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _CommandTimedOut()
            try:
                is_stderr, chunk = events.get(timeout=min(remaining, 0.1))
            except Empty:
                continue
            if chunk is None:
                complete += 1
                continue
            if chunk is _OUTPUT_LIMIT_MARKER:
                raise _OutputLimitExceeded()
            if not isinstance(chunk, bytes):
                raise _OutputLimitExceeded()
            output[is_stderr].extend(chunk)

        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as error:
            raise _CommandTimedOut() from error
        return bytes(output[0]), bytes(output[1])
    except (_OutputLimitExceeded, _CommandTimedOut):
        _stop_process(process)
        raise
    finally:
        stopped.set()
        budget.condition.acquire()
        budget.condition.notify_all()
        budget.condition.release()
        for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None)):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        for thread in threads:
            thread.join(timeout=READER_JOIN_TIMEOUT_SECONDS)


def _read_stream(
    stream,
    is_stderr: bool,
    events: Queue,
    stopped: Event,
    budget: _OutputBudget,
) -> None:
    if stream is None:
        _put_event(events, (is_stderr, None), stopped)
        return
    while not stopped.is_set():
        reservation = budget.reserve(stopped)
        if reservation is None:
            break
        reserved, probe = reservation
        chunk = stream.read(reserved)
        budget.complete(reserved, len(chunk), probe)
        if probe and chunk:
            _put_event(events, (is_stderr, _OUTPUT_LIMIT_MARKER), stopped)
            return
        if not chunk:
            break
        _put_event(events, (is_stderr, chunk), stopped)
    _put_event(events, (is_stderr, None), stopped)


def _put_event(events: Queue, event: tuple[bool, object], stopped: Event) -> None:
    while not stopped.is_set():
        try:
            events.put(event, timeout=0.1)
            return
        except Full:
            continue


def _stop_process(process: object) -> None:
    parent_stopped = process.poll() is not None
    pid = getattr(process, "pid", None)
    if parent_stopped and not isinstance(pid, int):
        return
    if os.name == "nt" and isinstance(pid, int):
        if not _stop_windows_process_tree(process):
            if not parent_stopped:
                process.terminate()
    elif os.name == "posix" and isinstance(pid, int):
        try:
            os.killpg(pid, signal.SIGTERM)
            if parent_stopped:
                os.killpg(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            if not parent_stopped:
                process.terminate()
    else:
        process.terminate()
    if parent_stopped:
        return
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        if os.name == "posix" and isinstance(pid, int):
            try:
                os.killpg(pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                process.kill()
        else:
            process.kill()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


def _stop_windows_process_tree(
    process: object,
    runner: Callable[..., object] = subprocess.run,
) -> bool:
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int):
        process.terminate()
        return False
    try:
        result = runner(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return getattr(result, "returncode", 1) == 0


def _required_text(item: dict[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RouteExecutionError("Exa検索結果の形式が不正です")
    return value
