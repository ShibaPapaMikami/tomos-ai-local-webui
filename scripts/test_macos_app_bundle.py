#!/usr/bin/env python3
"""Integration tests for the TOMOS AI macOS application bundle."""

from __future__ import annotations

import os
import plistlib
import subprocess
import tempfile
import unittest
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
