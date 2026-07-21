#!/usr/bin/env python3
"""Integration tests for the TOMOS AI macOS application bundle."""

from __future__ import annotations

import ast
import os
import plistlib
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKE_APP = ROOT / "scripts" / "make-mac-app.sh"
MAKE_ARCHIVES = ROOT / "scripts" / "make-release-archives.sh"


class MacosAppBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.version = f"0.0.{os.getpid()}"
        cls.tag = f"v{cls.version}"
        cls.mac_zip = ROOT / "dist" / f"TOMOS_AI-{cls.tag}-mac.zip"
        cls.windows_zip = ROOT / "dist" / f"TOMOS_AI-{cls.tag}-windows.zip"
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.app_path = Path(cls.temp_dir.name) / "TOMOS AI.app"

        subprocess.run(
            ["/bin/bash", str(MAKE_ARCHIVES), cls.version],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        environment = os.environ.copy()
        environment["TOMOS_MAC_APPLICATION_IDENTITY"] = "-"
        subprocess.run(
            ["/bin/bash", str(MAKE_APP), cls.version, str(cls.app_path)],
            cwd=ROOT,
            env=environment,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()
        cls.mac_zip.unlink(missing_ok=True)
        cls.windows_zip.unlink(missing_ok=True)

    def test_release_archives_keep_launcher_mac_only(self) -> None:
        with zipfile.ZipFile(self.mac_zip) as archive:
            mac_files = archive.namelist()
        with zipfile.ZipFile(self.windows_zip) as archive:
            windows_files = archive.namelist()

        self.assertTrue(
            any(name.endswith("/scripts/macos-app-launcher.sh") for name in mac_files)
        )
        self.assertFalse(
            any(name.endswith("/scripts/macos-app-launcher.sh") for name in windows_files)
        )

    def test_failed_archive_build_keeps_existing_archives(self) -> None:
        version = f"0.0.atomic-{os.getpid()}"
        tag = f"v{version}"
        mac_archive = ROOT / "dist" / f"TOMOS_AI-{tag}-mac.zip"
        windows_archive = ROOT / "dist" / f"TOMOS_AI-{tag}-windows.zip"
        mac_archive.write_text("stale-mac", encoding="utf-8")
        windows_archive.write_text("stale-windows", encoding="utf-8")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                fake_zip = Path(temp_dir) / "zip"
                fake_zip.write_text(
                    "#!/usr/bin/env bash\n"
                    "output=\"$2\"\n"
                    "case \"$output\" in\n"
                    "  *windows*) exit 1 ;;\n"
                    "esac\n"
                    "printf 'replacement' > \"$output\"\n",
                    encoding="utf-8",
                )
                fake_zip.chmod(0o755)
                environment = os.environ.copy()
                environment["PATH"] = f"{temp_dir}:{environment['PATH']}"
                completed = subprocess.run(
                    ["/bin/bash", str(MAKE_ARCHIVES), version],
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(mac_archive.read_text(encoding="utf-8"), "stale-mac")
            self.assertEqual(windows_archive.read_text(encoding="utf-8"), "stale-windows")
        finally:
            mac_archive.unlink(missing_ok=True)
            windows_archive.unlink(missing_ok=True)

    def test_release_archive_excludes_python_bytecode(self) -> None:
        with zipfile.ZipFile(self.mac_zip) as archive:
            names = archive.namelist()
        self.assertFalse(any("/__pycache__/" in name or name.endswith((".pyc", ".pyo")) for name in names))

    def test_launch_paths_disable_python_bytecode_writes(self) -> None:
        app_launcher = (ROOT / "scripts" / "macos-app-launcher.sh").read_text(encoding="utf-8")
        web_launcher = (ROOT / "Gemma4_12B_Web.command").read_text(encoding="utf-8")
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", app_launcher)
        self.assertIn("python3 -B", app_launcher)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", web_launcher)
        self.assertIn("python3 -B server.py", web_launcher)

    def test_release_archive_contains_all_local_server_dependencies(self) -> None:
        tree = ast.parse((ROOT / "server.py").read_text(encoding="utf-8"))
        local_modules = {
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and (ROOT / f"{node.module.split('.', 1)[0]}.py").is_file()
        }

        with zipfile.ZipFile(self.mac_zip) as archive:
            archived_names = set(archive.namelist())

        for module in local_modules:
            self.assertTrue(
                any(name.endswith(f"/{module}.py") for name in archived_names),
                module,
            )
        self.assertTrue(
            any(name.endswith("/packages/local_context_core/__init__.py") for name in archived_names)
        )

    def test_release_archive_smoke_starts_packaged_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            with zipfile.ZipFile(self.mac_zip) as archive:
                archive.extractall(temp)
            release_root = temp / f"Gemma4_12B-{self.tag}-mac"
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            environment = os.environ.copy()
            environment.update({
                "HOME": str(temp / "home"),
                "PYTHONPATH": "",
                "GEMMA_APP_VERSION": self.version,
            })
            process = subprocess.Popen(
                [sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port)],
                cwd=release_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                for _ in range(40):
                    if process.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.2) as response:
                            payload = response.read().decode("utf-8")
                        self.assertIn(self.version, payload)
                        return
                    except OSError:
                        time.sleep(0.05)
                stdout, stderr = process.communicate(timeout=1)
                self.fail(f"配布アーカイブのserver.pyを起動できませんでした\nstdout:\n{stdout}\nstderr:\n{stderr}")
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=5)

    def test_make_app_rebuilds_archive_from_current_source(self) -> None:
        script = MAKE_APP.read_text(encoding="utf-8")
        self.assertIn('bash "$ROOT_DIR/scripts/make-release-archives.sh" "$APP_VERSION"', script)
        self.assertNotIn('if [ ! -f "$MAC_ZIP" ]', script)

    def test_generated_bundle_has_required_structure(self) -> None:
        executable = self.app_path / "Contents" / "MacOS" / "TOMOS AI"
        resources = self.app_path / "Contents" / "Resources"

        self.assertTrue(executable.is_file())
        self.assertTrue(os.access(executable, os.X_OK))
        self.assertTrue((resources / "Gemma4_12B" / "server.py").is_file())
        self.assertTrue((resources / "TOMOS.icns").is_file())
        self.assertTrue((self.app_path / "Contents" / "Info.plist").is_file())

    def test_generated_info_plist_matches_bundle_contract(self) -> None:
        with (self.app_path / "Contents" / "Info.plist").open("rb") as plist_file:
            info = plistlib.load(plist_file)

        self.assertEqual(info["CFBundleDisplayName"], "TOMOS AI")
        self.assertEqual(info["CFBundleExecutable"], "TOMOS AI")
        self.assertEqual(info["CFBundleIconFile"], "TOMOS")
        self.assertEqual(info["CFBundleIdentifier"], "com.shibapapastudio.tomos-ai")
        self.assertEqual(info["CFBundlePackageType"], "APPL")
        self.assertEqual(info["CFBundleShortVersionString"], self.version)
        self.assertEqual(info["CFBundleVersion"], self.version)
        self.assertEqual(info["LSMinimumSystemVersion"], "13.0")

    def test_generated_icon_is_icns(self) -> None:
        icon = self.app_path / "Contents" / "Resources" / "TOMOS.icns"
        self.assertGreater(icon.stat().st_size, 8)
        self.assertEqual(icon.read_bytes()[:4], b"icns")

    def test_generated_bundle_has_valid_adhoc_signature(self) -> None:
        completed = subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(self.app_path)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_generated_app_launch_keeps_signature_and_bundle_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            health_file = temp / "health"
            health_file.write_text(
                f"fail\nfail\n{{\"ok\": true, \"appVersion\": \"{self.version}\"}}\n",
                encoding="utf-8",
            )
            events = temp / "events"
            start_command = temp / "start.command"
            start_command.write_text(
                "#!/usr/bin/env bash\nprintf 'start\\n' >> \"$TOMOS_TEST_EVENTS\"\n",
                encoding="utf-8",
            )
            start_command.chmod(0o755)
            for name, content in {
                "curl": (
                    "#!/usr/bin/env bash\n"
                    "line=$(sed -n '1p' \"$TOMOS_TEST_HEALTH_FILE\")\n"
                    "sed -i '' '1d' \"$TOMOS_TEST_HEALTH_FILE\"\n"
                    "[ \"$line\" != fail ] || exit 1\n"
                    "printf '%s' \"$line\"\n"
                ),
                "sleep": "#!/usr/bin/env bash\nexit 0\n",
                "nohup": "#!/usr/bin/env bash\nexec \"$@\"\n",
                "osascript": "#!/usr/bin/env bash\nexit 0\n",
                "ps": "#!/usr/bin/env bash\nprintf 'bundle-test\\n'\n",
                "open-browser": "#!/usr/bin/env bash\nprintf 'open\\n' >> \"$TOMOS_TEST_EVENTS\"\n",
            }.items():
                command = bin_dir / name
                command.write_text(content, encoding="utf-8")
                command.chmod(0o755)
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{bin_dir}:{environment['PATH']}",
                "TOMOS_START_COMMAND": str(start_command),
                "TOMOS_OPEN_COMMAND": str(bin_dir / "open-browser"),
                "TOMOS_LOG_DIR": str(temp / "logs"),
                "TOMOS_APP_SUPPORT_DIR": str(temp / "Application Support" / "TOMOS AI"),
                "TOMOS_TEST_EVENTS": str(events),
                "TOMOS_TEST_HEALTH_FILE": str(health_file),
                "TOMOS_APP_VERSION": self.version,
            })
            completed = subprocess.run(
                [str(self.app_path / "Contents" / "MacOS" / "TOMOS AI")],
                cwd=ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(events.read_text(encoding="utf-8").splitlines(), ["start", "open"])
            self.assertFalse(any(path.name == "__pycache__" for path in self.app_path.rglob("__pycache__")))
            verified = subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(self.app_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(verified.returncode, 0, verified.stderr)

    def run_with_security_output(self, output: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            security = temp / "security"
            security.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$TOMOS_TEST_SECURITY_OUTPUT\"\n",
                encoding="utf-8",
            )
            security.chmod(0o755)
            environment = os.environ.copy()
            environment.pop("TOMOS_MAC_APPLICATION_IDENTITY", None)
            environment["PATH"] = f"{temp}:{environment['PATH']}"
            environment["TOMOS_TEST_SECURITY_OUTPUT"] = output
            return subprocess.run(
                ["/bin/bash", str(MAKE_APP), self.version, str(temp / "Identity.app")],
                cwd=ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

    def test_missing_developer_id_application_identity_stops_build(self) -> None:
        completed = self.run_with_security_output("0 valid identities found")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Developer ID Application証明書が見つかりません", completed.stderr)

    def test_multiple_developer_id_application_identities_stop_build(self) -> None:
        completed = self.run_with_security_output(
            '\n'.join(
                [
                    '1) AAAA "Developer ID Application: Example A (TEAMAAAA)"',
                    '2) BBBB "Developer ID Application: Example B (TEAMBBBB)"',
                    "2 valid identities found",
                ]
            )
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Developer ID Application証明書が複数あります", completed.stderr)


if __name__ == "__main__":
    unittest.main()
