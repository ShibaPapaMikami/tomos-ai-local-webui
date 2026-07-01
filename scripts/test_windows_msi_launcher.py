#!/usr/bin/env python3
"""Regression tests for the Windows MSI launcher shortcuts."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WXS_PATH = ROOT / "dist" / "msi" / "Gemma4_12B.wxs"
WEB_BAT_PATH = ROOT / "Gemma4_12B_Web.bat"
ALL_START_BAT_PATH = ROOT / "Gemma4_12B_All_Start.bat"
WINDOWS_LAUNCHER_SOURCE = ROOT / "tools" / "windows-launcher" / "Gemma4Launcher.cs"


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
            encoding="utf-8",
            errors="replace",
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

    def test_windows_batch_launchers_stop_with_clear_ollama_requirement(self) -> None:
        for bat_path in (WEB_BAT_PATH, ALL_START_BAT_PATH):
            with self.subTest(bat=bat_path.name):
                text = bat_path.read_text(encoding="utf-8")
                self.assertIn(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe", text)
                self.assertIn(r"%ProgramFiles%\Ollama\ollama.exe", text)
                self.assertIn("set OLLAMA_EXE=", text)
                self.assertIn("Gemma4_12B cannot start without Ollama.", text)
                self.assertIn("Install Ollama first:", text)
                self.assertIn("https://ollama.com/download", text)
                self.assertIn("exit /b 1", text)

    def test_windows_launcher_blocks_with_single_ollama_requirement_message(self) -> None:
        text = WINDOWS_LAUNCHER_SOURCE.read_text(encoding="utf-8")
        self.assertIn("FindOllamaExecutable", text)
        self.assertIn("ShowOllamaRequiredMessage", text)
        self.assertIn("Ollama がインストールされていないため、Gemma4_12B は起動できません。", text)
        self.assertIn("https://ollama.com/download", text)
        self.assertIn("MessageBoxButtons.OK", text)
        self.assertNotIn("MessageBoxButtons.YesNo", text)

    def test_msi_launches_web_ui_after_initial_install(self) -> None:
        self.assertIn("<CustomAction", self.wxs)
        self.assertIn('Id="LaunchGemma4AfterInstall"', self.wxs)
        self.assertIn('FileRef="File_Gemma4_12B_Launcher_exe"', self.wxs)
        self.assertIn('ExeCommand="web"', self.wxs)
        self.assertIn('Return="asyncNoWait"', self.wxs)
        self.assertIn("<InstallExecuteSequence>", self.wxs)
        self.assertIn("<Custom", self.wxs)
        self.assertIn('Action="LaunchGemma4AfterInstall"', self.wxs)
        self.assertIn('Condition="NOT Installed AND NOT REMOVE"', self.wxs)


if __name__ == "__main__":
    unittest.main()
