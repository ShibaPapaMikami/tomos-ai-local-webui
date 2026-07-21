#!/usr/bin/env python3
"""Behavior tests for the macOS application launcher."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import time
import threading
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "macos-app-launcher.sh"
HEALTHY_TOMOS = '{"ok": true, "appVersion": "0.8.220"}'


@dataclass
class LauncherResult:
    open_count: int
    start_count: int
    dialog_text: str
    return_code: int


class MacosAppLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app_support_dir = tempfile.TemporaryDirectory()
        self._original_app_support_dir = os.environ.get("TOMOS_APP_SUPPORT_DIR")
        os.environ["TOMOS_APP_SUPPORT_DIR"] = self.app_support_dir.name

    def tearDown(self) -> None:
        if self._original_app_support_dir is None:
            os.environ.pop("TOMOS_APP_SUPPORT_DIR", None)
        else:
            os.environ["TOMOS_APP_SUPPORT_DIR"] = self._original_app_support_dir
        self.app_support_dir.cleanup()

    def run_launcher(self, health_sequence: list[bool | str]) -> LauncherResult:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            health_file = temp / "health-sequence"
            health_file.write_text(
                "\n".join(HEALTHY_TOMOS if value is True else "fail" if value is False else value for value in health_sequence),
                encoding="utf-8",
            )
            event_log = temp / "events.log"
            dialog_file = temp / "dialog.txt"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)

            self.write_command(
                bin_dir / "curl",
                """#!/usr/bin/env bash
line=$(sed -n '1p' "$TOMOS_TEST_HEALTH_FILE")
if [ -s "$TOMOS_TEST_HEALTH_FILE" ]; then
  sed -i '' '1d' "$TOMOS_TEST_HEALTH_FILE"
fi
if [ "$line" = "fail" ] || [ -z "$line" ]; then
  exit 1
fi
[ "$line" = "http-404" ] && { printf 'HTTP/1.1 404 Not Found\\r\\n\\r\\n{}'; exit 0; }
[ "$line" = "ok" ] && line="$TOMOS_TEST_HEALTHY"
printf '%s' "$line"
""",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(
                bin_dir / "nohup",
                "#!/usr/bin/env bash\nexec \"$@\"\n",
            )
            self.write_command(
                bin_dir / "osascript",
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > \"$TOMOS_TEST_DIALOG_FILE\"\n",
            )
            open_command = bin_dir / "open-browser"
            self.write_command(
                open_command,
                "#!/usr/bin/env bash\nprintf 'open\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{bin_dir}:{environment['PATH']}",
                    "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                    "TOMOS_START_COMMAND": str(start_command),
                    "TOMOS_OPEN_COMMAND": str(open_command),
                    "TOMOS_LOG_DIR": str(temp / "logs"),
                    "TOMOS_TEST_DIALOG_FILE": str(dialog_file),
                    "TOMOS_TEST_EVENT_LOG": str(event_log),
                    "TOMOS_TEST_HEALTH_FILE": str(health_file),
                    "TOMOS_TEST_HEALTHY": HEALTHY_TOMOS,
                    "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
                }
            )
            completed = subprocess.run(
                ["/bin/bash", str(LAUNCHER)],
                cwd=ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []
            return LauncherResult(
                open_count=events.count("open"),
                start_count=events.count("start"),
                dialog_text=dialog_file.read_text(encoding="utf-8") if dialog_file.exists() else "",
                return_code=completed.returncode,
            )

    def write_command(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def write_process_fingerprint_command(self, bin_dir: Path) -> None:
        self.write_command(
            bin_dir / "ps",
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  *pgid=*) printf '%s\\n' \"$2\" ;;\n"
            "  *) printf '%s\\n' \"$TOMOS_TEST_PROCESS_FINGERPRINT\" ;;\n"
            "esac\n",
        )

    def run_with_tcp_listener(self, response: bytes | None) -> LauncherResult:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            event_log = temp / "events.log"
            dialog_file = temp / "dialog.txt"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.settimeout(0.05)
            port = listener.getsockname()[1]
            stop = threading.Event()

            def serve() -> None:
                while not stop.is_set():
                    try:
                        connection, _ = listener.accept()
                    except TimeoutError:
                        continue
                    with connection:
                        if response is not None:
                            connection.sendall(response)
                        else:
                            time.sleep(0.15)

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(
                bin_dir / "osascript",
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > \"$TOMOS_TEST_DIALOG_FILE\"\n",
            )
            open_command = bin_dir / "open-browser"
            self.write_command(open_command, "#!/usr/bin/env bash\nprintf 'open\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n")
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{bin_dir}:{environment['PATH']}",
                "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                "TOMOS_WEB_URL": f"http://127.0.0.1:{port}",
                "TOMOS_START_COMMAND": str(start_command),
                "TOMOS_OPEN_COMMAND": str(open_command),
                "TOMOS_LOG_DIR": str(temp / "logs"),
                "TOMOS_TEST_EVENT_LOG": str(event_log),
                "TOMOS_TEST_DIALOG_FILE": str(dialog_file),
                "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
            })
            try:
                completed = subprocess.run(
                    ["/bin/bash", str(LAUNCHER)],
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            finally:
                stop.set()
                listener.close()
                worker.join(timeout=1)
            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []
            return LauncherResult(
                open_count=events.count("open"),
                start_count=events.count("start"),
                dialog_text=dialog_file.read_text(encoding="utf-8") if dialog_file.exists() else "",
                return_code=completed.returncode,
            )

    def test_stale_lock_with_dead_owner_starts_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            health_file = temp / "health-sequence"
            health_file.write_text("fail\nfail\nok\n", encoding="utf-8")
            event_log = temp / "events.log"
            log_dir = temp / "logs"
            lock_dir = log_dir / "launcher.lock"
            lock_dir.mkdir(parents=True)
            (lock_dir / "owner").write_text("99999999|unavailable\n", encoding="utf-8")
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)

            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                "[ \"$line\" != fail ] && printf '%s' \"$TOMOS_TEST_HEALTHY\"\n"
                "[ \"$line\" != fail ]\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            open_command = bin_dir / "open-browser"
            self.write_command(
                open_command,
                "#!/usr/bin/env bash\nprintf 'open\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{bin_dir}:{environment['PATH']}",
                    "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                    "TOMOS_START_COMMAND": str(start_command),
                    "TOMOS_OPEN_COMMAND": str(open_command),
                    "TOMOS_LOG_DIR": str(log_dir),
                    "TOMOS_TEST_EVENT_LOG": str(event_log),
                    "TOMOS_TEST_HEALTH_FILE": str(health_file),
                    "TOMOS_TEST_HEALTHY": HEALTHY_TOMOS,
                    "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
                }
            )
            completed = subprocess.run(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []

            self.assertEqual(completed.returncode, 0)
            self.assertEqual(events.count("start"), 1)
            self.assertEqual(events.count("open"), 1)

    def test_live_pid_with_mismatched_fingerprint_starts_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            health_file = temp / "health-sequence"
            health_file.write_text("fail\nfail\nok\n", encoding="utf-8")
            event_log = temp / "events.log"
            log_dir = temp / "logs"
            lock_dir = log_dir / "launcher.lock"
            lock_dir.mkdir(parents=True)
            (lock_dir / "owner").write_text(f"{os.getpid()}|different\n", encoding="utf-8")
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)

            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                "[ \"$line\" != fail ] && printf '%s' \"$TOMOS_TEST_HEALTHY\"\n"
                "[ \"$line\" != fail ]\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            open_command = bin_dir / "open-browser"
            self.write_command(
                open_command,
                "#!/usr/bin/env bash\nprintf 'open\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{bin_dir}:{environment['PATH']}",
                    "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                    "TOMOS_START_COMMAND": str(start_command),
                    "TOMOS_OPEN_COMMAND": str(open_command),
                    "TOMOS_LOG_DIR": str(log_dir),
                    "TOMOS_TEST_EVENT_LOG": str(event_log),
                    "TOMOS_TEST_HEALTH_FILE": str(health_file),
                    "TOMOS_TEST_HEALTHY": HEALTHY_TOMOS,
                    "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
                }
            )
            completed = subprocess.run(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []

            self.assertEqual(completed.returncode, 0)
            self.assertEqual(events.count("start"), 1)
            self.assertEqual(events.count("open"), 1)

    def test_matching_live_owner_does_not_recover_expired_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            health_file = temp / "health-sequence"
            health_file.write_text("fail\n" * 32, encoding="utf-8")
            event_log = temp / "events.log"
            log_dir = temp / "logs"
            lock_dir = log_dir / "launcher.lock"
            lock_dir.mkdir(parents=True)
            owner = f"{os.getpid()}|matching\n"
            (lock_dir / "owner").write_text(owner, encoding="utf-8")
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)

            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                "[ \"$line\" != fail ] && printf '%s' \"$TOMOS_TEST_HEALTHY\"\n"
                "[ \"$line\" != fail ]\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(bin_dir / "ps", "#!/usr/bin/env bash\nprintf 'matching\\n'\n")
            open_command = bin_dir / "open-browser"
            self.write_command(open_command, "#!/usr/bin/env bash\nexit 0\n")

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{bin_dir}:{environment['PATH']}",
                    "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                    "TOMOS_START_COMMAND": str(start_command),
                    "TOMOS_OPEN_COMMAND": str(open_command),
                    "TOMOS_LOG_DIR": str(log_dir),
                    "TOMOS_LOCK_STALE_SECONDS": "0",
                    "TOMOS_TEST_EVENT_LOG": str(event_log),
                    "TOMOS_TEST_HEALTH_FILE": str(health_file),
                    "TOMOS_TEST_HEALTHY": HEALTHY_TOMOS,
                }
            )
            completed = subprocess.run(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(events.count("start"), 0)

    def test_recent_invalid_owner_lock_does_not_start_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            health_file = temp / "health-sequence"
            health_file.write_text("fail\n" * 32, encoding="utf-8")
            event_log = temp / "events.log"
            log_dir = temp / "logs"
            lock_dir = log_dir / "launcher.lock"
            lock_dir.mkdir(parents=True)
            (lock_dir / "owner").write_text("starting\n", encoding="utf-8")
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)

            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                "[ \"$line\" != fail ] && printf '%s' \"$TOMOS_TEST_HEALTHY\"\n"
                "[ \"$line\" != fail ]\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            open_command = bin_dir / "open-browser"
            self.write_command(open_command, "#!/usr/bin/env bash\nexit 0\n")

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{bin_dir}:{environment['PATH']}",
                    "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                    "TOMOS_START_COMMAND": str(start_command),
                    "TOMOS_OPEN_COMMAND": str(open_command),
                    "TOMOS_LOG_DIR": str(log_dir),
                    "TOMOS_TEST_EVENT_LOG": str(event_log),
                    "TOMOS_TEST_HEALTH_FILE": str(health_file),
                    "TOMOS_TEST_HEALTHY": HEALTHY_TOMOS,
                }
            )
            completed = subprocess.run(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(events.count("start"), 0)

    def test_concurrent_successful_launches_start_and_open_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            event_log = temp / "events.log"
            ready_file = temp / "server-ready"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\n"
                "printf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n"
                "/bin/sleep 0.05\n"
                "touch \"$TOMOS_TEST_READY_FILE\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)

            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "[ -f \"$TOMOS_TEST_READY_FILE\" ] || exit 1\n"
                "printf '%s' \"$TOMOS_TEST_HEALTHY\"\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\n/bin/sleep 0.01\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            open_command = bin_dir / "open-browser"
            self.write_command(
                open_command,
                "#!/usr/bin/env bash\nprintf 'open\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{bin_dir}:{environment['PATH']}",
                    "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                    "TOMOS_START_COMMAND": str(start_command),
                    "TOMOS_OPEN_COMMAND": str(open_command),
                    "TOMOS_LOG_DIR": str(temp / "logs"),
                    "TOMOS_TEST_EVENT_LOG": str(event_log),
                    "TOMOS_TEST_READY_FILE": str(ready_file),
                    "TOMOS_TEST_HEALTHY": HEALTHY_TOMOS,
                    "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
                }
            )
            first = subprocess.Popen(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            for _ in range(100):
                if event_log.exists() and "start" in event_log.read_text(encoding="utf-8").splitlines():
                    break
                time.sleep(0.01)
            self.assertIsNone(first.poll())
            second = subprocess.Popen(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            self.assertEqual(first.wait(), 0)
            self.assertEqual(second.wait(), 0)

            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []
            self.assertEqual(events.count("start"), 1)
            self.assertEqual(events.count("open"), 1)

    def test_running_server_only_opens_browser(self) -> None:
        result = self.run_launcher(health_sequence=[True])
        self.assertEqual(result.return_code, 0)
        self.assertEqual(result.open_count, 1)
        self.assertEqual(result.start_count, 0)

    def test_stopped_server_starts_once_then_opens_browser(self) -> None:
        result = self.run_launcher(health_sequence=[False, False, True])
        self.assertEqual(result.return_code, 0)
        self.assertEqual(result.start_count, 1)
        self.assertEqual(result.open_count, 1)

    def test_start_timeout_shows_japanese_error_without_opening(self) -> None:
        result = self.run_launcher(health_sequence=[False] * 5)
        self.assertNotEqual(result.return_code, 0)
        self.assertEqual(result.open_count, 0)
        self.assertIn("TOMOS AIを起動できませんでした", result.dialog_text)

    def test_old_server_is_not_reused_as_tomos(self) -> None:
        result = self.run_launcher(
            health_sequence=['{"ok": true, "appVersion": "0.8.219"}', HEALTHY_TOMOS]
        )
        self.assertNotEqual(result.return_code, 0)
        self.assertEqual(result.start_count, 0)
        self.assertEqual(result.open_count, 0)
        self.assertIn("別のTOMOS", result.dialog_text)

    def test_reachable_404_is_not_reused_or_started(self) -> None:
        result = self.run_launcher(health_sequence=["http-404"])
        self.assertNotEqual(result.return_code, 0)
        self.assertEqual(result.start_count, 0)
        self.assertEqual(result.open_count, 0)
        self.assertIn("別のTOMOS", result.dialog_text)

    def test_reachable_invalid_json_is_not_reused_or_started(self) -> None:
        result = self.run_launcher(health_sequence=["not-json"])
        self.assertNotEqual(result.return_code, 0)
        self.assertEqual(result.start_count, 0)
        self.assertEqual(result.open_count, 0)
        self.assertIn("別のTOMOS", result.dialog_text)

    def test_non_http_tcp_listener_is_not_reused_or_started(self) -> None:
        result = self.run_with_tcp_listener(b"not an http response\n")
        self.assertNotEqual(result.return_code, 0)
        self.assertEqual(result.start_count, 0)
        self.assertEqual(result.open_count, 0)
        self.assertIn("別のTOMOS", result.dialog_text)

    def test_unresponsive_tcp_listener_is_not_reused_or_started(self) -> None:
        result = self.run_with_tcp_listener(None)
        self.assertNotEqual(result.return_code, 0)
        self.assertEqual(result.start_count, 0)
        self.assertEqual(result.open_count, 0)
        self.assertIn("別のTOMOS", result.dialog_text)

    def test_timeout_terminates_only_the_process_started_by_launcher(self) -> None:
        script = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("STARTED_PROCESS_PID=$!", script)
        self.assertIn("os.setsid()", script)
        self.assertIn('kill -TERM -- "-$STARTED_PROCESS_PGID"', script)
        self.assertNotIn("pkill", script)

    def test_timeout_cleans_started_process_group_without_touching_unrelated_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            health_file = temp / "health-sequence"
            health_file.write_text("fail\n" * 40, encoding="utf-8")
            child_pid_file = temp / "child.pid"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\n"
                "/bin/sleep 60 &\n"
                "printf '%s\\n' \"$!\" > \"$TOMOS_TEST_CHILD_PID\"\n"
                "wait\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)
            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                "[ \"$line\" != fail ] && printf '%s' \"$line\"\n"
                "[ \"$line\" != fail ]\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\n/bin/sleep 0.01\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            open_command = bin_dir / "open-browser"
            self.write_command(open_command, "#!/usr/bin/env bash\nexit 0\n")
            unrelated = subprocess.Popen(["/bin/sleep", "60"])
            try:
                environment = os.environ.copy()
                environment.update({
                    "PATH": f"{bin_dir}:{environment['PATH']}",
                    "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                    "TOMOS_START_COMMAND": str(start_command),
                    "TOMOS_OPEN_COMMAND": str(open_command),
                    "TOMOS_LOG_DIR": str(temp / "logs"),
                    "TOMOS_TEST_HEALTH_FILE": str(health_file),
                    "TOMOS_TEST_CHILD_PID": str(child_pid_file),
                    "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
                })
                completed = subprocess.run(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
                self.assertNotEqual(completed.returncode, 0)
                child_pid = int(child_pid_file.read_text(encoding="utf-8"))
                for _ in range(50):
                    try:
                        os.kill(child_pid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.01)
                else:
                    self.fail("ランチャーが開始した子プロセスが残っています")
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_timeout_cleans_group_when_start_parent_exits_before_child(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            health_file = temp / "health-sequence"
            health_file.write_text("fail\n" * 40, encoding="utf-8")
            child_pid_file = temp / "child.pid"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\n"
                "/bin/sleep 60 &\n"
                "printf '%s\\n' \"$!\" > \"$TOMOS_TEST_CHILD_PID\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)
            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                "[ \"$line\" != fail ] && printf '%s' \"$line\"\n"
                "[ \"$line\" != fail ]\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\n/bin/sleep 0.01\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            open_command = bin_dir / "open-browser"
            self.write_command(open_command, "#!/usr/bin/env bash\nexit 0\n")
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{bin_dir}:{environment['PATH']}",
                "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                "TOMOS_START_COMMAND": str(start_command),
                "TOMOS_OPEN_COMMAND": str(open_command),
                "TOMOS_LOG_DIR": str(temp / "logs"),
                "TOMOS_TEST_HEALTH_FILE": str(health_file),
                "TOMOS_TEST_CHILD_PID": str(child_pid_file),
                "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
            })
            completed = subprocess.run(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            self.assertNotEqual(completed.returncode, 0)
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
            for _ in range(50):
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.01)
            else:
                os.kill(child_pid, 15)
                self.fail("親終了後に残った子プロセスをcleanupできませんでした")

    def test_launcher_migrates_legacy_variable_data_before_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            self.write_process_fingerprint_command(bin_dir)
            health_file = temp / "health-sequence"
            health_file.write_text(f"fail\nfail\n{HEALTHY_TOMOS}\n", encoding="utf-8")
            legacy_root = temp / "legacy"
            legacy_data = legacy_root / ".gemma4-data" / "context"
            legacy_data.mkdir(parents=True)
            (legacy_data / "context.sqlite").write_text("legacy", encoding="utf-8")
            support_root = temp / "Application Support" / "TOMOS AI"
            event_log = temp / "events.log"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\n"
                "test -f \"$TOMOS_APP_SUPPORT_DIR/.gemma4-data/context/context.sqlite\"\n"
                "printf 'migrated\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)
            self.write_command(
                bin_dir / "curl",
                "#!/usr/bin/env bash\n"
                "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                "[ \"$line\" != fail ] && printf '%s' \"$line\"\n"
                "[ \"$line\" != fail ]\n",
            )
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")
            self.write_command(bin_dir / "nohup", "#!/usr/bin/env bash\nexec \"$@\"\n")
            self.write_command(bin_dir / "osascript", "#!/usr/bin/env bash\nexit 0\n")
            open_command = bin_dir / "open-browser"
            self.write_command(open_command, "#!/usr/bin/env bash\nexit 0\n")
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{bin_dir}:{environment['PATH']}",
                "TOMOS_RESOURCE_ROOT": str(temp / "resources"),
                "TOMOS_START_COMMAND": str(start_command),
                "TOMOS_OPEN_COMMAND": str(open_command),
                "TOMOS_LOG_DIR": str(temp / "logs"),
                "TOMOS_LEGACY_ROOT": str(legacy_root),
                "TOMOS_APP_SUPPORT_DIR": str(support_root),
                "TOMOS_TEST_EVENT_LOG": str(event_log),
                "TOMOS_TEST_HEALTH_FILE": str(health_file),
                "TOMOS_TEST_PROCESS_FINGERPRINT": "test-fingerprint",
            })
            completed = subprocess.run(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(events, ["migrated"])


if __name__ == "__main__":
    test_program = unittest.main(exit=False)
    if not test_program.result.wasSuccessful():
        raise SystemExit(1)
    print("macOS app launcher tests: OK")
