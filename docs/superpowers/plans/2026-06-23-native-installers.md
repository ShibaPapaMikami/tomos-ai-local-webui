# Native Installers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repeatable native installer generation for macOS `.pkg` and Windows `.msi` while keeping the existing ZIP release flow.

**Architecture:** Native installers are produced from the same app payload used by the ZIP archives. macOS installers are built locally with Apple command line tools; Windows installers are generated on a Windows GitHub Actions runner with WiX, so macOS developers do not need Windows tooling locally.

**Tech Stack:** Bash, Python 3, GitHub Actions, Apple `pkgbuild`, WiX Toolset.

---

### Task 1: Add macOS PKG Builder

**Files:**
- Create: `scripts/make-mac-pkg.sh`

- [ ] **Step 1: Build from the existing release archive**

Use `scripts/make-release-archives.sh` to create or refresh `dist/Gemma4_12B-v<version>-mac.zip`.

- [ ] **Step 2: Create a package root**

Unzip the mac archive into a temporary folder and place it under `Applications/Gemma4_12B` in a package root.

- [ ] **Step 3: Run pkgbuild**

Run:

```bash
bash scripts/make-mac-pkg.sh
```

Expected:

```text
作成しました:
- dist/Gemma4_12B-v<version>-mac.pkg
```

- [ ] **Step 4: Verify payload**

Run:

```bash
pkgutil --payload-files dist/Gemma4_12B-v<version>-mac.pkg | sed -n '1,40p'
```

Expected: files under `Applications/Gemma4_12B/`.

### Task 2: Add Windows MSI Builder

**Files:**
- Create: `scripts/make-windows-msi.py`

- [ ] **Step 1: Stage the Windows payload**

Copy the same safe release files used by the ZIP archive into `dist/msi-staging/Gemma4_12B`.

- [ ] **Step 2: Generate WiX source**

Generate `dist/msi/Gemma4_12B.wxs` from staged files. Each file gets its own component so WiX can install and uninstall cleanly.

- [ ] **Step 3: Build MSI when WiX is available**

Run on Windows:

```powershell
python scripts/make-windows-msi.py
```

Expected:

```text
Created dist\Gemma4_12B-v<version>-windows.msi
```

### Task 3: Add GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/build-installers.yml`

- [ ] **Step 1: macOS job**

Run `bash scripts/make-mac-pkg.sh` and upload `.pkg`.

- [ ] **Step 2: Windows job**

Install WiX with `dotnet tool install --global wix`, run `python scripts/make-windows-msi.py`, and upload `.msi`.

- [ ] **Step 3: Release support**

Allow manual workflow runs with an optional version input. When omitted, scripts read `server.py`.

### Task 4: Document Native Installer Releases

**Files:**
- Create: `docs/native-installers.ja.md`
- Modify: `docs/github-release-guide.ja.md`

- [ ] **Step 1: Explain installer roles**

Document that ZIPs remain the fallback, `.pkg` is for Mac, and `.msi` is built by GitHub Actions for Windows.

- [ ] **Step 2: Explain update flow**

Document that app version comes from `server.py`, old release assets remain attached to old tags, and each release should include ZIP + native installers.

- [ ] **Step 3: Explain model policy**

Document that installers do not bundle large models. Models are downloaded from the app UI.

### Task 5: Verify

**Files:**
- Test: shell syntax, local `.pkg` build, Python syntax.

- [ ] **Step 1: Run syntax checks**

```bash
bash -n scripts/make-mac-pkg.sh
python3 -m py_compile scripts/make-windows-msi.py
```

- [ ] **Step 2: Build Mac package**

```bash
bash scripts/make-mac-pkg.sh
```

- [ ] **Step 3: Inspect package payload**

```bash
pkgutil --payload-files dist/Gemma4_12B-v0.8.189-mac.pkg | sed -n '1,40p'
```

- [ ] **Step 4: Report MSI status**

MSI is verified through GitHub Actions on a Windows runner. Local macOS verification checks only source generation and Python syntax.
