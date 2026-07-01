# Windows Ollama Install Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows users who start Gemma4_12B without Ollama installed should get a clear Japanese prompt that opens the official Ollama download page, instead of stopping at a terminal error.

**Architecture:** Keep `.bat` as the runtime server launcher and improve `Gemma4_12B_Launcher.exe` as the user-facing preflight layer. The C# launcher checks for Ollama using PATH and standard Windows install paths, prompts the user, opens the official download page, and exits without starting the web server until Ollama is installed.

**Tech Stack:** C# Windows Forms launcher, Windows `.bat` files, Python unittest-based packaging regression tests.

---

### Task 1: Add launcher preflight test coverage

**Files:**
- Modify: `scripts/test_windows_msi_launcher.py`
- Test: `scripts/test_windows_msi_launcher.py`

- [ ] **Step 1: Write the failing test**

Add tests that read `tools/windows-launcher/Gemma4Launcher.cs` and assert the launcher contains the Ollama detection and install prompt behavior.

```python
WINDOWS_LAUNCHER_SOURCE = ROOT / "tools" / "windows-launcher" / "Gemma4Launcher.cs"

def test_windows_launcher_prompts_for_ollama_install_when_missing(self) -> None:
    text = WINDOWS_LAUNCHER_SOURCE.read_text(encoding="utf-8")
    self.assertIn("FindOllamaExecutable", text)
    self.assertIn("ShowOllamaInstallPrompt", text)
    self.assertIn("https://ollama.com/download", text)
    self.assertIn(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe", text)
    self.assertIn(r"%ProgramFiles%\Ollama\ollama.exe", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/test_windows_msi_launcher.py`

Expected: FAIL because `Gemma4Launcher.cs` does not yet contain `FindOllamaExecutable` or `ShowOllamaInstallPrompt`.

### Task 2: Implement the Windows launcher Ollama preflight

**Files:**
- Modify: `tools/windows-launcher/Gemma4Launcher.cs`
- Test: `scripts/test_windows_msi_launcher.py`

- [ ] **Step 1: Add helper methods**

Add `FindOllamaExecutable`, `FindOnPath`, and `ShowOllamaInstallPrompt` to `Program`. `ShowOllamaInstallPrompt` opens `https://ollama.com/download` when the user chooses Yes.

- [ ] **Step 2: Gate web/all startup**

Before starting `Gemma4_12B_Web.bat` or `Gemma4_12B_All_Start.bat`, call `FindOllamaExecutable`. If it returns empty, call `ShowOllamaInstallPrompt` and return `1`.

- [ ] **Step 3: Run tests**

Run: `python3 scripts/test_windows_msi_launcher.py`

Expected: PASS.

### Task 3: Verify packaging still stages the launcher

**Files:**
- Modify: none
- Test: `scripts/test_windows_msi_launcher.py`

- [ ] **Step 1: Confirm MSI XML generation still works**

Run: `python3 scripts/test_windows_msi_launcher.py`

Expected: PASS and generated WiX XML still points shortcuts at `Gemma4_12B_Launcher.exe`.

### Task 4: Report user-facing behavior

**Files:**
- Modify: none

- [ ] **Step 1: Summarize behavior**

Report that Windows users now get a Japanese dialog before the terminal launcher starts. If they click Yes, the official Ollama download page opens. After installing and opening Ollama once, they should rerun Gemma4_12B.
