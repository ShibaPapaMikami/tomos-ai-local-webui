from dataclasses import dataclass
import json
import subprocess
import time
from typing import Callable


DOCTOR_CACHE_SECONDS = 300
COMMAND_TIMEOUT_SECONDS = 20
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_EXA_RESULTS = 10
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
    command: list[str], runner: Callable[..., object] = subprocess.run
) -> object:
    if (
        len(command) != 3
        or command[:2] != ["mcporter", "call"]
        or not command[2].startswith("exa.web_search_exa(")
    ):
        raise RouteExecutionError("許可されていない実行コマンドです")

    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RouteExecutionError("Exa検索の実行が20秒でタイムアウトしました") from error
    except OSError as error:
        raise RouteExecutionError("Exa検索の実行に失敗しました") from error

    stdout = _as_bytes(getattr(result, "stdout", b""))
    stderr = _as_bytes(getattr(result, "stderr", b""))
    if len(stdout) + len(stderr) > MAX_OUTPUT_BYTES:
        raise RouteExecutionError("Exa検索の出力上限を超えました")
    if getattr(result, "returncode", 1) != 0:
        raise RouteExecutionError("Exa検索の実行に失敗しました")
    return result


def run_exa_search(
    query: str, limit: int, runner: Callable[..., object] = subprocess.run
) -> list[dict[str, str]]:
    capped_limit = max(1, min(limit, MAX_EXA_RESULTS))
    call = (
        f"exa.web_search_exa(query: {json.dumps(query, ensure_ascii=False)}, "
        f"numResults: {capped_limit})"
    )
    result = execute_allowed(["mcporter", "call", call], runner=runner)
    output = _as_bytes(getattr(result, "stdout", b""))

    try:
        payload = json.loads(output.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RouteExecutionError("Exa検索結果の読み込みに失敗しました") from error

    raw_results = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(raw_results, list):
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


def _as_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode()
    return b""


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""
