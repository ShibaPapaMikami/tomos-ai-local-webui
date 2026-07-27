#!/usr/bin/env python3
"""実際のHTTP経路でTOMOS Desktopのsession guardを確認する。"""
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server.py"
GUARD_HOST = "127.0.0.1:54876"
GUARD_ORIGIN = "http://127.0.0.1:54876"
CHAT_BODY = json.dumps({"messages": [{"role": "user", "content": "session test"}]}).encode("utf-8")


@dataclass
class HttpResult:
    status: int
    body: bytes


class ServerFixture:
    def __init__(self, use_head_server: bool) -> None:
        self.use_head_server = use_head_server
        self.port = free_port()
        self.token = secrets.token_hex(32)
        self._tempdir = tempfile.TemporaryDirectory(prefix="tomos-desktop-session-")
        self.root = Path(self._tempdir.name)
        self.process: subprocess.Popen[bytes] | None = None
        self.source_process: subprocess.Popen[bytes] | None = None
        self.stdout = b""
        self.stderr = b""

    def __enter__(self) -> "ServerFixture":
        home = self.root / "home"
        cwd = self.root / "cwd"
        data = self.root / "data"
        for directory in (home, cwd, data):
            directory.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "XDG_DATA_HOME": str(data),
            "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GEMMA_DESKTOP_SESSION_TOKEN": self.token,
        }
        command = [
            sys.executable,
            "-B",
            str(SERVER),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
        ]
        stdin = None
        if self.use_head_server:
            self.source_process = subprocess.Popen(
                ["git", "show", "HEAD:server.py"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert self.source_process.stdout is not None
            command = [
                sys.executable,
                "-B",
                "-c",
                (
                    "import sys; source = sys.stdin.read(); "
                    "scope = {'__name__': '__main__', '__file__': 'server.py'}; "
                    "exec(compile(source, 'server.py', 'exec'), scope)"
                ),
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ]
            stdin = self.source_process.stdout
        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self.source_process and self.source_process.stdout:
            self.source_process.stdout.close()
        try:
            wait_for_health(self.port)
        except Exception:
            self.stop()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        if self.process is not None:
            try:
                self.stdout, self.stderr = self.process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.stdout, self.stderr = self.process.communicate(timeout=5)
        if self.source_process is not None:
            self.source_process.communicate(timeout=5)
        self._tempdir.cleanup()
        assert_port_released(self.port)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def assert_port_released(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))


def request(
    port: int,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
) -> HttpResult:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    try:
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in (headers or {}).items():
            connection.putheader(name, value)
        if body or method == "POST":
            if not any(name.lower() == "content-length" for name in (headers or {})):
                connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        return HttpResult(response.status, response.read())
    finally:
        connection.close()


def request_without_body(port: int, headers: dict[str, str]) -> bytes:
    request_head = ["POST /api/chat HTTP/1.1", *[f"{name}: {value}" for name, value in headers.items()]]
    with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
        connection.settimeout(3)
        connection.sendall(("\r\n".join(request_head) + "\r\n\r\n").encode("ascii"))
        chunks: list[bytes] = []
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)


def wait_for_health(port: int) -> None:
    deadline = time.monotonic() + 15
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            result = request(port, "GET", "/api/health", {"Host": GUARD_HOST})
            if result.status in {200, 503}:
                return
        except OSError as error:
            last_error = error
        time.sleep(0.1)
    raise AssertionError(f"server did not become ready: {last_error}")


def expect_fixed_forbidden(result: HttpResult, case: str) -> None:
    assert result.status == 403, f"{case}: expected 403, got {result.status}"
    assert json.loads(result.body) == {"ok": False, "error": "desktop_session_required"}, case


def assert_token_absent(token: str, sources: dict[str, bytes | str]) -> None:
    encoded_token = token.encode("ascii")
    for name, source in sources.items():
        value = source.encode("utf-8") if isinstance(source, str) else source
        assert encoded_token not in value, f"session token leaked through {name}"


def exercise_guard(use_head_server: bool) -> None:
    with ServerFixture(use_head_server) as fixture:
        health = request(fixture.port, "GET", "/api/health", {"Host": GUARD_HOST})
        assert health.status in {200, 503}, f"health status: {health.status}"

        wrong_host_get = request(
            fixture.port,
            "GET",
            "/api/context/memory/list",
            {"Host": "example.test:54876"},
        )
        expect_fixed_forbidden(wrong_host_get, "wrong Host GET")

        missing_headers = {
            "Host": GUARD_HOST,
            "Origin": GUARD_ORIGIN,
            "Content-Type": "application/json",
        }
        missing = request(fixture.port, "POST", "/api/chat", missing_headers, CHAT_BODY)
        expect_fixed_forbidden(missing, "missing token")

        wrong_token = request(
            fixture.port,
            "POST",
            "/api/chat",
            {**missing_headers, "X-TOMOS-Session": "0" * 64},
            CHAT_BODY,
        )
        expect_fixed_forbidden(wrong_token, "wrong token")

        wrong_host = request(
            fixture.port,
            "POST",
            "/api/chat",
            {**missing_headers, "Host": "127.0.0.1:9", "X-TOMOS-Session": fixture.token},
            CHAT_BODY,
        )
        expect_fixed_forbidden(wrong_host, "wrong Host")

        wrong_origin = request(
            fixture.port,
            "POST",
            "/api/chat",
            {**missing_headers, "Origin": "http://127.0.0.1:9", "X-TOMOS-Session": fixture.token},
            CHAT_BODY,
        )
        expect_fixed_forbidden(wrong_origin, "wrong Origin")

        plain_text = request(
            fixture.port,
            "POST",
            "/api/chat",
            {**missing_headers, "Content-Type": "text/plain", "X-TOMOS-Session": fixture.token},
            b"not json",
        )
        expect_fixed_forbidden(plain_text, "text/plain")

        no_body_response = request_without_body(
            fixture.port,
            {**missing_headers, "Content-Length": str(len(CHAT_BODY))},
        )
        assert b" 403 " in no_body_response, "missing token must be rejected before request body arrives"
        assert b"desktop_session_required" in no_body_response

        valid = request(
            fixture.port,
            "POST",
            "/api/chat",
            {**missing_headers, "X-TOMOS-Session": fixture.token},
            CHAT_BODY,
        )
        valid_payload = json.loads(valid.body)
        assert not (
            valid.status == 403 and valid_payload.get("error") == "desktop_session_required"
        ), "valid desktop request did not pass the guard"

        assert_token_absent(
            fixture.token,
            {
                "URL": f"http://127.0.0.1:{fixture.port}/api/health",
                "health response": health.body,
                "wrong-Host GET response": wrong_host_get.body,
                "forbidden response": missing.body,
                "wrong-token response": wrong_token.body,
                "wrong-Host response": wrong_host.body,
                "wrong-Origin response": wrong_origin.body,
                "text/plain response": plain_text.body,
                "bodyless forbidden response": no_body_response,
                "valid response": valid.body,
            },
        )
    assert_token_absent(fixture.token, {"server stdout": fixture.stdout, "server stderr": fixture.stderr})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--head-fixture",
        action="store_true",
        help="Run against git HEAD server.py to record the expected pre-guard RED failure.",
    )
    args = parser.parse_args()
    exercise_guard(args.head_fixture)
    print("desktop API session integration tests passed")


if __name__ == "__main__":
    main()
