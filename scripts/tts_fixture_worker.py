#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import json
import sys
import time
import wave


def emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def silent_pcm(sample_rate: int = 24000, duration_ms: int = 120) -> bytes:
    return b"\0\0" * (sample_rate * duration_ms // 1000)


def silent_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(pcm)
    return buffer.getvalue()


def main() -> int:
    line = sys.stdin.readline()
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        return 2
    request_id = str(request.get("requestId") or "")
    if request.get("op") != "synthesize" or request.get("engine") != "fixture":
        emit({"type": "error", "requestId": request_id, "error": "fixture_engine_invalid"})
        return 0

    pcm = silent_pcm()
    if request.get("stream") is True:
        midpoint = len(pcm) // 2
        midpoint -= midpoint % 2
        chunks = [pcm[:midpoint], pcm[midpoint:]]
        emit({
            "type": "start",
            "requestId": request_id,
            "mimeType": "audio/pcm;codec=s16le",
            "sampleRate": 24000,
            "channels": 1,
        })
        for sequence, chunk in enumerate(chunks):
            emit({
                "type": "audio",
                "requestId": request_id,
                "sequence": sequence,
                "audioBase64": base64.b64encode(chunk).decode("ascii"),
            })
            time.sleep(0.08)
        emit({
            "type": "done",
            "requestId": request_id,
            "chunks": len(chunks),
            "durationMs": 120,
        })
        return 0

    emit({
        "ok": True,
        "requestId": request_id,
        "mimeType": "audio/wav",
        "audioBase64": base64.b64encode(silent_wav(pcm)).decode("ascii"),
        "durationMs": 120,
        "sampleRate": 24000,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
