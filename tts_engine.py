from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from collections.abc import Iterator


ALLOWED_ENGINES = {"off", "vibevoice", "qwen3-tts", "fixture"}
ALLOWED_LANGUAGES = {"ja", "en", "auto"}
ALLOWED_MIME_TYPES = {"audio/wav", "audio/mpeg", "audio/ogg"}
ALLOWED_SAMPLE_RATES = {16000, 22050, 24000, 44100, 48000}
VOICE_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_CHUNK_BYTES = 1024 * 1024
MAX_WORKER_LINE_BYTES = 15 * 1024 * 1024
PUBLIC_WORKER_ERROR_CODES = {
    "tts_audio_invalid",
    "tts_audio_too_large",
    "tts_request_id_mismatch",
    "tts_stream_incomplete",
    "tts_worker_failed",
    "tts_worker_timeout",
    "tts_worker_unavailable",
}

_ACTIVE_PROCESSES: dict[str, subprocess.Popen[str]] = {}
_ACTIVE_LOCK = threading.Lock()


def _error(code: str) -> dict[str, object]:
    return {"ok": False, "error": code}


def _public_worker_error(value: object) -> str:
    code = value if isinstance(value, str) else ""
    return code if code in PUBLIC_WORKER_ERROR_CODES else "tts_worker_failed"


def _executable_file(path_value: str) -> bool:
    path = Path(path_value)
    return path.is_file() and os.access(path, os.X_OK)


def normalize_tts_config(env: dict[str, str], worker_path: str = "") -> dict[str, object]:
    requested_engine = str(env.get("GEMMA_TTS_ENGINE", "off") or "off").strip().lower()
    if requested_engine not in ALLOWED_ENGINES:
        return {
            "engine": "off",
            "enabled": False,
            "ready": False,
            "supportsStreaming": False,
            "supportsCancel": True,
            "reason": "invalid_engine",
            "workerPath": "",
            "workerPython": sys.executable,
        }

    configured_worker = str(worker_path or env.get("GEMMA_TTS_WORKER", "") or "").strip()
    configured_python = str(env.get("GEMMA_TTS_WORKER_PYTHON", "") or "").strip()
    worker_python = configured_python or sys.executable
    enabled = requested_engine != "off"
    worker_ready = bool(configured_worker and Path(configured_worker).is_file())
    python_ready = _executable_file(worker_python)
    ready = enabled and worker_ready and python_ready
    reason = ""
    if not enabled:
        reason = "not_configured"
    elif not worker_ready:
        reason = "worker_not_found"
    elif not python_ready:
        reason = "worker_python_invalid"

    return {
        "engine": requested_engine,
        "enabled": enabled,
        "ready": ready,
        "supportsStreaming": requested_engine in {"fixture", "vibevoice"},
        "supportsCancel": True,
        "reason": reason,
        "workerPath": configured_worker,
        "workerPython": worker_python,
    }


def validate_tts_request(payload: dict[str, object]) -> dict[str, object]:
    request_id = payload.get("requestId")
    text = payload.get("text")
    voice = payload.get("voice", "default")
    language = payload.get("language", "ja")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        return _error("tts_request_id_invalid")
    if not isinstance(text, str) or not text.strip():
        return _error("tts_text_required")
    if len(text) > 1000:
        return _error("tts_text_too_long")
    if not isinstance(voice, str) or not VOICE_PATTERN.fullmatch(voice):
        return _error("tts_voice_invalid")
    if language not in ALLOWED_LANGUAGES:
        return _error("tts_language_invalid")
    return {
        "ok": True,
        "requestId": request_id,
        "text": text,
        "voice": voice,
        "language": language,
    }


def _decode_audio(value: object, max_bytes: int, error_code: str) -> tuple[bytes | None, dict[str, object] | None]:
    if not isinstance(value, str):
        return None, _error("tts_audio_invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None, _error("tts_audio_invalid")
    if len(decoded) > max_bytes:
        return None, _error(error_code)
    return decoded, None


def validate_worker_response(payload: dict[str, object], expected_request_id: str) -> dict[str, object]:
    if payload.get("requestId") != expected_request_id:
        return _error("tts_request_id_mismatch")
    if payload.get("ok") is not True:
        return _error(_public_worker_error(payload.get("error")))
    mime_type = payload.get("mimeType")
    if mime_type not in ALLOWED_MIME_TYPES:
        return _error("tts_mime_type_invalid")
    _, decode_error = _decode_audio(payload.get("audioBase64"), MAX_AUDIO_BYTES, "tts_audio_too_large")
    if decode_error:
        return decode_error
    sample_rate = payload.get("sampleRate")
    if not isinstance(sample_rate, int) or sample_rate not in ALLOWED_SAMPLE_RATES:
        return _error("tts_sample_rate_invalid")
    duration_ms = payload.get("durationMs")
    if not isinstance(duration_ms, (int, float)) or duration_ms < 0:
        return _error("tts_duration_invalid")
    return {
        "ok": True,
        "requestId": expected_request_id,
        "audio": {
            "mimeType": mime_type,
            "base64": payload["audioBase64"],
            "durationMs": duration_ms,
            "sampleRate": sample_rate,
        },
    }


def validate_worker_event(
    payload: dict[str, object],
    expected_request_id: str,
    expected_sequence: int,
) -> dict[str, object]:
    if payload.get("requestId") != expected_request_id:
        return _error("tts_request_id_mismatch")
    event_type = payload.get("type")
    if event_type not in {"start", "audio", "done", "error"}:
        return _error("tts_stream_event_invalid")
    if event_type == "start":
        if payload.get("mimeType") != "audio/pcm;codec=s16le":
            return _error("tts_stream_mime_type_invalid")
        if payload.get("sampleRate") not in ALLOWED_SAMPLE_RATES or payload.get("channels") != 1:
            return _error("tts_stream_format_invalid")
    elif event_type == "audio":
        if payload.get("sequence") != expected_sequence:
            return _error("tts_stream_sequence_invalid")
        audio_bytes, decode_error = _decode_audio(
            payload.get("audioBase64"),
            MAX_CHUNK_BYTES,
            "tts_stream_chunk_too_large",
        )
        if decode_error:
            return decode_error
        if audio_bytes is None or len(audio_bytes) % 2 != 0:
            return _error("tts_stream_audio_invalid")
    elif event_type == "done":
        if not isinstance(payload.get("chunks"), int) or payload["chunks"] != expected_sequence:
            return _error("tts_stream_chunk_count_invalid")
    elif not isinstance(payload.get("error"), str):
        return _error("tts_stream_error_invalid")
    elif event_type == "error":
        payload = {**payload, "error": _public_worker_error(payload.get("error"))}
    return {"ok": True, **payload}


def _worker_command(config: dict[str, object]) -> list[str] | None:
    worker_path = str(config.get("workerPath") or "")
    worker_python = str(config.get("workerPython") or sys.executable)
    if not Path(worker_path).is_file() or not _executable_file(worker_python):
        return None
    return [worker_python, worker_path]


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _register_process(request_id: str, process: subprocess.Popen[str]) -> bool:
    with _ACTIVE_LOCK:
        if request_id in _ACTIVE_PROCESSES:
            return False
        _ACTIVE_PROCESSES[request_id] = process
        return True


def _unregister_process(request_id: str, process: subprocess.Popen[str]) -> None:
    with _ACTIVE_LOCK:
        if _ACTIVE_PROCESSES.get(request_id) is process:
            _ACTIVE_PROCESSES.pop(request_id, None)


def _start_worker(config: dict[str, object], request: dict[str, object], stream: bool) -> subprocess.Popen[str] | None:
    command = _worker_command(config)
    if command is None:
        return None
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError:
        return None
    request_id = str(request["requestId"])
    if not _register_process(request_id, process):
        _terminate_process(process)
        return None
    worker_request = {
        "op": "synthesize",
        "requestId": request_id,
        "engine": config["engine"],
        "text": request["text"],
        "voice": request["voice"],
        "language": request["language"],
        "stream": stream,
    }
    try:
        assert process.stdin is not None
        process.stdin.write(json.dumps(worker_request, ensure_ascii=False) + "\n")
        process.stdin.close()
    except (BrokenPipeError, OSError, ValueError):
        _terminate_process(process)
        _unregister_process(request_id, process)
        return None
    return process


def _read_stream_bounded(
    stream: object,
    limit: int,
    result: list[str],
    overflow: threading.Event,
    process: subprocess.Popen[str],
) -> None:
    chunks: list[str] = []
    total = 0
    while True:
        chunk = stream.read(64 * 1024)
        if not chunk:
            break
        if total <= limit:
            remaining = limit + 1 - total
            chunks.append(chunk[:remaining])
        total += len(chunk.encode("utf-8"))
        if total > limit:
            overflow.set()
            _terminate_process(process)
            break
    result.append("".join(chunks))


def _drain_stream(stream: object) -> None:
    while stream.read(64 * 1024):
        pass


def run_tts_worker(
    config: dict[str, object],
    request: dict[str, object],
    timeout_seconds: int = 60,
) -> dict[str, object]:
    process = _start_worker(config, request, stream=False)
    if process is None:
        return _error("tts_worker_unavailable")
    request_id = str(request["requestId"])
    try:
        assert process.stdout is not None
        assert process.stderr is not None
        stdout_result: list[str] = []
        stdout_overflow = threading.Event()
        stdout_thread = threading.Thread(
            target=_read_stream_bounded,
            args=(process.stdout, MAX_WORKER_LINE_BYTES, stdout_result, stdout_overflow, process),
            daemon=True,
        )
        stderr_thread = threading.Thread(target=_drain_stream, args=(process.stderr,), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        process.wait(timeout=timeout_seconds)
        stdout_thread.join(timeout=3)
        stderr_thread.join(timeout=3)
        if stdout_overflow.is_set():
            return _error("tts_worker_response_invalid")
        if process.returncode != 0:
            return _error("tts_worker_failed")
        if not stdout_result:
            return _error("tts_worker_response_invalid")
        stdout = stdout_result[0]
        lines = stdout.splitlines()
        if len(lines) != 1 or len(lines[0].encode("utf-8")) > MAX_WORKER_LINE_BYTES:
            return _error("tts_worker_response_invalid")
        try:
            payload = json.loads(lines[0])
        except (json.JSONDecodeError, TypeError):
            return _error("tts_worker_response_invalid")
        if not isinstance(payload, dict):
            return _error("tts_worker_response_invalid")
        return validate_worker_response(payload, request_id)
    except subprocess.TimeoutExpired:
        _terminate_process(process)
        return _error("tts_worker_timeout")
    finally:
        _unregister_process(request_id, process)


def iter_tts_worker_events(
    config: dict[str, object],
    request: dict[str, object],
    timeout_seconds: int = 60,
) -> Iterator[dict[str, object]]:
    process = _start_worker(config, request, stream=True)
    request_id = str(request["requestId"])
    if process is None:
        yield {"type": "error", "requestId": request_id, "error": "tts_worker_unavailable"}
        return
    line_queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=1)
    reader_stopped = threading.Event()
    assert process.stdout is not None
    assert process.stderr is not None

    def read_lines() -> None:
        try:
            while True:
                line = process.stdout.readline(MAX_WORKER_LINE_BYTES + 2)
                if not line:
                    break
                kind = "line"
                if len(line.encode("utf-8")) > MAX_WORKER_LINE_BYTES:
                    kind = "oversized"
                while not reader_stopped.is_set():
                    try:
                        line_queue.put((kind, line), timeout=0.1)
                        break
                    except queue.Full:
                        continue
                if kind == "oversized":
                    break
        finally:
            while not reader_stopped.is_set():
                try:
                    line_queue.put(("eof", ""), timeout=0.1)
                    break
                except queue.Full:
                    continue

    threading.Thread(target=read_lines, daemon=True).start()
    threading.Thread(target=_drain_stream, args=(process.stderr,), daemon=True).start()
    deadline = time.monotonic() + timeout_seconds
    expected_sequence = 0
    total_bytes = 0
    seen_start = False
    terminal_event: dict[str, object] | None = None
    failed = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                yield {"type": "error", "requestId": request_id, "error": "tts_worker_timeout"}
                break
            try:
                kind, line = line_queue.get(timeout=remaining)
            except queue.Empty:
                yield {"type": "error", "requestId": request_id, "error": "tts_worker_timeout"}
                failed = True
                break
            if kind == "eof":
                process.wait(timeout=3)
                if terminal_event is None:
                    yield {"type": "error", "requestId": request_id, "error": "tts_stream_incomplete"}
                    failed = True
                elif process.returncode != 0:
                    yield {"type": "error", "requestId": request_id, "error": "tts_worker_failed"}
                    failed = True
                else:
                    yield terminal_event
                break
            if kind == "oversized":
                yield {"type": "error", "requestId": request_id, "error": "tts_worker_line_too_large"}
                failed = True
                break
            if terminal_event is not None:
                yield {"type": "error", "requestId": request_id, "error": "tts_stream_terminal_invalid"}
                failed = True
                break
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                yield {"type": "error", "requestId": request_id, "error": "tts_worker_response_invalid"}
                failed = True
                break
            if not isinstance(payload, dict):
                yield {"type": "error", "requestId": request_id, "error": "tts_worker_response_invalid"}
                failed = True
                break
            result = validate_worker_event(payload, request_id, expected_sequence)
            if not result["ok"]:
                yield {"type": "error", "requestId": request_id, "error": result["error"]}
                failed = True
                break
            event_type = str(result["type"])
            if event_type == "start":
                if seen_start:
                    yield {"type": "error", "requestId": request_id, "error": "tts_stream_start_invalid"}
                    failed = True
                    break
                seen_start = True
            elif event_type == "audio":
                if not seen_start:
                    yield {"type": "error", "requestId": request_id, "error": "tts_stream_start_missing"}
                    failed = True
                    break
                decoded = base64.b64decode(str(result["audioBase64"]), validate=True)
                total_bytes += len(decoded)
                if total_bytes > MAX_AUDIO_BYTES:
                    yield {"type": "error", "requestId": request_id, "error": "tts_audio_too_large"}
                    failed = True
                    break
                expected_sequence += 1
            elif event_type == "done":
                if not seen_start:
                    yield {"type": "error", "requestId": request_id, "error": "tts_stream_start_missing"}
                    failed = True
                    break
                terminal_event = result
                continue
            elif event_type == "error":
                terminal_event = result
                continue
            yield result
    except subprocess.TimeoutExpired:
        _terminate_process(process)
    finally:
        reader_stopped.set()
        if failed or process.poll() is None:
            _terminate_process(process)
        _unregister_process(request_id, process)


def cancel_tts_request(request_id: str) -> bool:
    with _ACTIVE_LOCK:
        process = _ACTIVE_PROCESSES.get(request_id)
    if process is None:
        return False
    _terminate_process(process)
    _unregister_process(request_id, process)
    return True
