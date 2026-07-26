import base64
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tts_engine import (  # noqa: E402
    cancel_tts_request,
    iter_tts_worker_events,
    normalize_tts_config,
    run_tts_worker,
    validate_tts_request,
    validate_worker_event,
    validate_worker_response,
)

ROOT = Path(__file__).resolve().parents[1]


def test_tts_defaults_to_off() -> None:
    config = normalize_tts_config({}, worker_path="")
    assert config["engine"] == "off"
    assert config["enabled"] is False
    assert config["ready"] is False
    assert config["reason"] == "not_configured"


def test_tts_request_rejects_long_text() -> None:
    result = validate_tts_request({
        "requestId": "tts-1",
        "text": "あ" * 1001,
        "voice": "default",
        "language": "ja",
    })
    assert result["ok"] is False
    assert result["error"] == "tts_text_too_long"


def test_tts_request_rejects_invalid_voice_and_language() -> None:
    assert validate_tts_request({
        "requestId": "tts-1",
        "text": "こんにちは",
        "voice": "../voice",
        "language": "ja",
    })["error"] == "tts_voice_invalid"
    assert validate_tts_request({
        "requestId": "tts-1",
        "text": "hello",
        "voice": "default",
        "language": "fr",
    })["error"] == "tts_language_invalid"


def test_worker_response_rejects_oversized_audio() -> None:
    result = validate_worker_response({
        "ok": True,
        "requestId": "tts-1",
        "mimeType": "audio/wav",
        "audioBase64": base64.b64encode(b"\0" * (10 * 1024 * 1024 + 1)).decode("ascii"),
        "durationMs": 1,
        "sampleRate": 24000,
    }, expected_request_id="tts-1")
    assert result["ok"] is False
    assert result["error"] == "tts_audio_too_large"


def test_worker_response_rejects_request_id_mismatch() -> None:
    result = validate_worker_response({
        "ok": True,
        "requestId": "tts-other",
        "mimeType": "audio/wav",
        "audioBase64": "UklGRg==",
        "durationMs": 1,
        "sampleRate": 24000,
    }, expected_request_id="tts-1")
    assert result["ok"] is False
    assert result["error"] == "tts_request_id_mismatch"


def test_worker_response_hides_private_error_details() -> None:
    result = validate_worker_response({
        "ok": False,
        "requestId": "tts-1",
        "error": "Traceback: /Users/private/model.py API_TOKEN=secret",
    }, expected_request_id="tts-1")
    assert result["ok"] is False
    assert result["error"] == "tts_worker_failed"


def test_worker_event_rejects_skipped_sequence() -> None:
    result = validate_worker_event({
        "type": "audio",
        "requestId": "tts-1",
        "sequence": 2,
        "audioBase64": "AAAAAA==",
    }, expected_request_id="tts-1", expected_sequence=1)
    assert result["ok"] is False
    assert result["error"] == "tts_stream_sequence_invalid"


def test_worker_event_rejects_odd_pcm_bytes() -> None:
    result = validate_worker_event({
        "type": "audio",
        "requestId": "tts-1",
        "sequence": 0,
        "audioBase64": base64.b64encode(b"\0").decode("ascii"),
    }, expected_request_id="tts-1", expected_sequence=0)
    assert result["ok"] is False
    assert result["error"] == "tts_stream_audio_invalid"


def test_stream_rejects_done_without_start() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        worker = Path(tmp) / "worker.py"
        worker.write_text(
            "import json, sys\n"
            "request = json.loads(sys.stdin.readline())\n"
            "print(json.dumps({'type':'done','requestId':request['requestId'],'chunks':0}))\n",
            encoding="utf-8",
        )
        config = normalize_tts_config({
            "GEMMA_TTS_ENGINE": "fixture",
            "GEMMA_TTS_WORKER_PYTHON": sys.executable,
        }, worker_path=str(worker))
        request = validate_tts_request({
            "requestId": "tts-no-start",
            "text": "テスト",
            "voice": "default",
            "language": "ja",
        })
        events = list(iter_tts_worker_events(config, request))
    assert events == [{
        "type": "error",
        "requestId": "tts-no-start",
        "error": "tts_stream_start_missing",
    }]


def test_stream_rejects_sequence_and_request_mismatch() -> None:
    cases = [
        (
            "{'type':'audio','requestId':request['requestId'],'sequence':1,'audioBase64':'AAAAAA=='}",
            "tts_stream_sequence_invalid",
        ),
        (
            "{'type':'audio','requestId':'other','sequence':0,'audioBase64':'AAAAAA=='}",
            "tts_request_id_mismatch",
        ),
    ]
    for event_expression, expected_error in cases:
        with tempfile.TemporaryDirectory() as tmp:
            worker = Path(tmp) / "worker.py"
            worker.write_text(
                "import json, sys\n"
                "request = json.loads(sys.stdin.readline())\n"
                "print(json.dumps({'type':'start','requestId':request['requestId'],"
                "'mimeType':'audio/pcm;codec=s16le','sampleRate':24000,'channels':1}), flush=True)\n"
                f"print(json.dumps({event_expression}), flush=True)\n",
                encoding="utf-8",
            )
            config = normalize_tts_config({
                "GEMMA_TTS_ENGINE": "fixture",
                "GEMMA_TTS_WORKER_PYTHON": sys.executable,
            }, worker_path=str(worker))
            request = validate_tts_request({
                "requestId": f"tts-{expected_error}",
                "text": "テスト",
                "voice": "default",
                "language": "ja",
            })
            events = list(iter_tts_worker_events(config, request))
        assert events[-1]["type"] == "error"
        assert events[-1]["error"] == expected_error


def test_cancel_targets_only_requested_worker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        worker = Path(tmp) / "worker.py"
        worker.write_text(
            "import json, sys, time\n"
            "request = json.loads(sys.stdin.readline())\n"
            "print(json.dumps({'type':'start','requestId':request['requestId'],"
            "'mimeType':'audio/pcm;codec=s16le','sampleRate':24000,'channels':1}), flush=True)\n"
            "time.sleep(10)\n",
            encoding="utf-8",
        )
        config = normalize_tts_config({
            "GEMMA_TTS_ENGINE": "fixture",
            "GEMMA_TTS_WORKER_PYTHON": sys.executable,
        }, worker_path=str(worker))
        requests = [
            validate_tts_request({
                "requestId": request_id,
                "text": "テスト",
                "voice": "default",
                "language": "ja",
            })
            for request_id in ("tts-cancel-a", "tts-cancel-b")
        ]
        results: list[list[dict[str, object]]] = [[], []]
        threads = [
            threading.Thread(
                target=lambda index=index: results[index].extend(
                    iter_tts_worker_events(config, requests[index], timeout_seconds=2)
                ),
                daemon=True,
            )
            for index in range(2)
        ]
        for thread in threads:
            thread.start()
        for _ in range(50):
            if cancel_tts_request("tts-cancel-a"):
                break
            time.sleep(0.02)
        else:
            raise AssertionError("first worker did not become cancellable")
        assert cancel_tts_request("tts-missing") is False
        assert cancel_tts_request("tts-cancel-b") is True
        for thread in threads:
            thread.join(timeout=3)
            assert not thread.is_alive()


def test_fixture_worker_round_trip() -> None:
    config = normalize_tts_config({
        "GEMMA_TTS_ENGINE": "fixture",
        "GEMMA_TTS_WORKER_PYTHON": sys.executable,
    }, worker_path=str(ROOT / "scripts" / "tts_fixture_worker.py"))
    request = validate_tts_request({
        "requestId": "tts-fixture-1",
        "text": "テスト",
        "voice": "default",
        "language": "ja",
    })
    assert config["ready"] is True
    assert request["ok"] is True

    response = run_tts_worker(config, request)
    assert response["ok"] is True
    assert response["requestId"] == "tts-fixture-1"
    assert response["audio"]["mimeType"] == "audio/wav"
    decoded = base64.b64decode(response["audio"]["base64"], validate=True)
    assert decoded.startswith(b"RIFF")
    assert len(decoded) <= 10 * 1024 * 1024

    events = list(iter_tts_worker_events(config, request))
    assert [event["type"] for event in events] == ["start", "audio", "audio", "done"]
    assert [event["sequence"] for event in events if event["type"] == "audio"] == [0, 1]


def run_tests() -> None:
    test_tts_defaults_to_off()
    test_tts_request_rejects_long_text()
    test_tts_request_rejects_invalid_voice_and_language()
    test_worker_response_rejects_oversized_audio()
    test_worker_response_rejects_request_id_mismatch()
    test_worker_response_hides_private_error_details()
    test_worker_event_rejects_skipped_sequence()
    test_worker_event_rejects_odd_pcm_bytes()
    test_stream_rejects_done_without_start()
    test_stream_rejects_sequence_and_request_mismatch()
    test_cancel_targets_only_requested_worker()
    test_fixture_worker_round_trip()
    print("tts engine tests passed")


if __name__ == "__main__":
    run_tests()
