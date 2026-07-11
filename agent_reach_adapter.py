from dataclasses import dataclass
import json
from queue import Empty, Full, Queue
import subprocess
from threading import Event, Thread
import time
from typing import Callable


DOCTOR_CACHE_SECONDS = 300
COMMAND_TIMEOUT_SECONDS = 20
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_EXA_RESULTS = 10
READ_CHUNK_BYTES = 64 * 1024
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
    if (
        len(command) != 3
        or command[:2] != ["mcporter", "call"]
        or not command[2].startswith("exa.web_search_exa(")
    ):
        raise RouteExecutionError("許可されていない実行コマンドです")

    try:
        process = popen_factory(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
    if not isinstance(raw_results, list) or any(
        not isinstance(item, dict) for item in raw_results
    ):
        raise RouteExecutionError("Exa検索結果の形式が不正です")

    return [
        {
            "title": _as_text(item.get("title")),
            "url": _as_text(item.get("url")),
            "snippet": _as_text(item.get("text")),
            "source": "agent-reach:web",
            "backend": "exa",
            "routeReason": "doctorで利用可能と確認",
        }
        for item in raw_results[:MAX_EXA_RESULTS]
        if isinstance(item, dict)
    ]


def _read_process_output(process: object) -> tuple[bytes, bytes]:
    events: Queue[tuple[bool, bytes | None]] = Queue(maxsize=4)
    stopped = Event()
    threads = [
        Thread(target=_read_stream, args=(stream, is_stderr, events, stopped), daemon=True)
        for is_stderr, stream in ((False, getattr(process, "stdout", None)), (True, getattr(process, "stderr", None)))
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
    output = [bytearray(), bytearray()]
    total = 0
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
            total += len(chunk)
            if total > MAX_OUTPUT_BYTES:
                raise _OutputLimitExceeded()
            output[is_stderr].extend(chunk)

        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as error:
            raise _CommandTimedOut() from error
        return bytes(output[0]), bytes(output[1])
    finally:
        stopped.set()


def _read_stream(stream, is_stderr: bool, events: Queue, stopped: Event) -> None:
    if stream is None:
        _put_event(events, (is_stderr, None), stopped)
        return
    while not stopped.is_set():
        chunk = stream.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        _put_event(events, (is_stderr, chunk), stopped)
    _put_event(events, (is_stderr, None), stopped)


def _put_event(events: Queue, event: tuple[bool, bytes | None], stopped: Event) -> None:
    while not stopped.is_set():
        try:
            events.put(event, timeout=0.1)
            return
        except Full:
            continue


def _stop_process(process: object) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""
