from dataclasses import dataclass
import time
from typing import Callable


DOCTOR_CACHE_SECONDS = 300
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
