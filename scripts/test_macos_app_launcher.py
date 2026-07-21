#!/usr/bin/env python3
"""Behavior tests for the macOS application launcher."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "macos-app-launcher.sh"


@dataclass
class LauncherResult:
    open_count: int
    start_count: int
    dialog_text: str
    return_code: int


class MacosAppLauncherTests(unittest.TestCase):
    def run_launcher(self, health_sequence: list[bool]) -> LauncherResult:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            health_file = temp / "health-sequence"
            health_file.write_text(
                "\n".join("ok" if value else "fail" for value in health_sequence),
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
[ "$line" = "ok" ]
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

    def test_concurrent_launches_run_start_command_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            event_log = temp / "events.log"
            dialog_file = temp / "dialog.txt"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENT_LOG\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)

            self.write_command(bin_dir / "curl", "#!/usr/bin/env bash\nexit 1\n")
            self.write_command(bin_dir / "sleep", "#!/usr/bin/env bash\n/bin/sleep 0.02\n")
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
                    "TOMOS_TEST_DIALOG_FILE": str(dialog_file),
                    "TOMOS_TEST_EVENT_LOG": str(event_log),
                }
            )
            first = subprocess.Popen(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            for _ in range(100):
                if event_log.exists() and "start" in event_log.read_text(encoding="utf-8").splitlines():
                    break
                time.sleep(0.01)
            self.assertIsNone(first.poll())
            second = subprocess.Popen(["/bin/bash", str(LAUNCHER)], cwd=ROOT, env=environment)
            self.assertNotEqual(first.wait(), 0)
            self.assertNotEqual(second.wait(), 0)

            events = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []
            self.assertEqual(events.count("start"), 1)

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


if __name__ == "__main__":
    test_program = unittest.main(exit=False)
    if not test_program.result.wasSuccessful():
        raise SystemExit(1)
    print("macOS app launcher tests: OK")
