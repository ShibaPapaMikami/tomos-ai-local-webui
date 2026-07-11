from dataclasses import dataclass
import time


DOCTOR_CACHE_SECONDS = 300
_AVAILABLE_STATUSES = {"ok", "ready", "available"}


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


def _channel_is_available(doctor, channel):
    if doctor.get("installed") is False:
        return False
    channels = doctor.get("channels", {})
    status = channels.get(channel, {})
    if not isinstance(status, dict):
        return False
    return (
        status.get("status") in _AVAILABLE_STATUSES
        and bool(status.get("active_backend"))
    )


def select_route(channel, doctor, intent="read"):
    if channel == "web" and intent == "search":
        doctor_channel = "exa_search"
        backend = "exa"
    else:
        doctor_channel = channel
        backend = {
            "web": "jina",
            "youtube": "youtube",
            "github": "github",
            "rss": "rss",
        }.get(channel)

    if backend is not None and _channel_is_available(doctor, doctor_channel):
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
