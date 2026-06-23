#!/usr/bin/env python3
"""Regression tests for the Windows MSI launcher shortcuts."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WXS_PATH = ROOT / "dist" / "msi" / "Gemma4_12B.wxs"


class WindowsMsiLauncherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(
            [sys.executable, "scripts/make-windows-msi.py", "--no-build"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        cls.wxs = WXS_PATH.read_text(encoding="utf-8")

    def test_launcher_exe_is_staged_for_windows_shortcuts(self) -> None:
        self.assertIn("Gemma4_12B_Launcher.exe", self.wxs)

    def test_shortcuts_target_launcher_exe_not_batch_files(self) -> None:
        self.assertIn('Target="[INSTALLFOLDER]Gemma4_12B_Launcher.exe"', self.wxs)
        self.assertIn('Arguments="web"', self.wxs)
        self.assertIn('Arguments="all"', self.wxs)
        self.assertIn('Arguments="stop-heavy"', self.wxs)
        self.assertNotIn('Target="[INSTALLFOLDER]Gemma4_12B_Web.bat"', self.wxs)
        self.assertNotIn('Target="[INSTALLFOLDER]Gemma4_12B_All_Start.bat"', self.wxs)
        self.assertNotIn('Target="[INSTALLFOLDER]Gemma4_12B_Stop_Heavy.bat"', self.wxs)


if __name__ == "__main__":
    unittest.main()
