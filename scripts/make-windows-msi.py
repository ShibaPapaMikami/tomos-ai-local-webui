#!/usr/bin/env python3
"""Build a Windows MSI from the lightweight release payload.

Local macOS/Linux runs can use --no-build to verify staging and WiX XML.
The actual MSI build is intended to run on a Windows GitHub Actions runner
with WiX Toolset v4 installed.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
STAGING_ROOT = DIST / "msi-staging" / "Gemma4_12B"
WIX_DIR = DIST / "msi"
WXS_PATH = WIX_DIR / "Gemma4_12B.wxs"
WINDOWS_LAUNCHER_SOURCE = ROOT / "tools" / "windows-launcher" / "Gemma4Launcher.cs"
WINDOWS_LAUNCHER_EXE = "Gemma4_12B_Launcher.exe"

COMMON_FILES = [
    "server.py",
    "search_tools.py",
    "README.md",
    "README.ja.md",
    "README.en.md",
    "LICENSE",
]

COMMON_DIRS = [
    "web",
]

DOC_FILES = [
    "docs/install-students.ja.md",
    "docs/github-release-guide.ja.md",
    "docs/release-checklist.ja.md",
    "docs/native-installers.ja.md",
    "docs/study-pack-import-guide.ja.md",
]

SCRIPT_FILES = [
    "scripts/setup-mac.sh",
    "scripts/setup-windows.ps1",
    "scripts/start-dev.sh",
    "scripts/start-comfyui.sh",
    "scripts/asr_nemotron_runner.py",
    "scripts/asr_nemotron_worker.py",
    "scripts/setup-asr-mac.sh",
    "scripts/setup-asr-python311.sh",
    "scripts/setup-ocr-mac.sh",
    "scripts/smoke-tests.sh",
]

WINDOWS_FILES = [
    "Gemma4_12B_All_Start.bat",
    "Gemma4_12B_Web.bat",
    "Gemma4_12B_Stop_Heavy.bat",
    "ComfyUI_Start.bat",
    "Start_Windows.bat",
]


def find_csc() -> str | None:
    csc = shutil.which("csc")
    if csc:
        return csc

    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        windir / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe",
        windir / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def build_or_stub_windows_launcher(target_root: Path) -> None:
    if not WINDOWS_LAUNCHER_SOURCE.exists():
        raise SystemExit(f"Windows launcher source not found: {WINDOWS_LAUNCHER_SOURCE}")

    target = target_root / WINDOWS_LAUNCHER_EXE
    target.parent.mkdir(parents=True, exist_ok=True)

    if os.name != "nt":
        target.write_bytes(
            b"Gemma4_12B Windows launcher placeholder for MSI XML verification.\n"
        )
        return

    csc = find_csc()
    if not csc:
        raise SystemExit(
            "Windows launcher のビルドに必要な csc.exe が見つかりません。"
        )

    subprocess.run(
        [
            csc,
            "/nologo",
            "/target:winexe",
            "/optimize+",
            "/reference:System.Windows.Forms.dll",
            "/codepage:65001",
            f"/out:{target}",
            str(WINDOWS_LAUNCHER_SOURCE),
        ],
        check=True,
    )


def read_app_version() -> str:
    text = (ROOT / "server.py").read_text(encoding="utf-8")
    match = re.search(
        r'APP_VERSION = os\.environ\.get\("GEMMA_APP_VERSION", "([^"]+)"\)',
        text,
    )
    if not match:
        raise SystemExit("server.py から APP_VERSION を読めませんでした")
    return match.group(1)


def copy_file(rel_path: str, target_root: Path) -> None:
    source = ROOT / rel_path
    if not source.exists():
        return
    target = target_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_dir(rel_path: str, target_root: Path) -> None:
    source = ROOT / rel_path
    if not source.exists():
        return
    target = target_root / rel_path
    if target.exists():
        shutil.rmtree(target)
    ignore = shutil.ignore_patterns(
        "__pycache__",
        ".DS_Store",
        "node_modules",
        ".venv",
        ".venv-asr",
        ".git",
        "dist",
        "*.gguf",
        "*.safetensors",
    )
    shutil.copytree(source, target, ignore=ignore)


def stage_payload() -> None:
    if STAGING_ROOT.exists():
        shutil.rmtree(STAGING_ROOT)
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)

    for rel_path in COMMON_FILES + DOC_FILES + SCRIPT_FILES + WINDOWS_FILES:
        copy_file(rel_path, STAGING_ROOT)
    for rel_path in COMMON_DIRS:
        copy_dir(rel_path, STAGING_ROOT)
    build_or_stub_windows_launcher(STAGING_ROOT)


def wix_id(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned[:70]


def xml_path(path: Path) -> str:
    return html.escape(str(path).replace("/", "\\"), quote=True)


def emit_directory(path: Path, indent: str = "      ") -> tuple[list[str], list[str]]:
    lines: list[str] = []
    component_refs: list[str] = []

    for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        if child.is_dir():
            directory_id = wix_id(f"Dir_{child.relative_to(STAGING_ROOT)}")
            lines.append(f'{indent}<Directory Id="{directory_id}" Name="{html.escape(child.name)}">')
            child_lines, child_refs = emit_directory(child, indent + "  ")
            lines.extend(child_lines)
            lines.append(f"{indent}</Directory>")
            component_refs.extend(child_refs)
        elif child.is_file():
            rel = child.relative_to(STAGING_ROOT)
            component_id = wix_id(f"Cmp_{rel}")
            file_id = wix_id(f"File_{rel}")
            component_refs.append(component_id)
            lines.append(f'{indent}<Component Id="{component_id}" Guid="*">')
            lines.append(
                f'{indent}  <File Id="{file_id}" Source="{xml_path(child)}" KeyPath="yes" />'
            )
            lines.append(f"{indent}</Component>")

    return lines, component_refs


def generate_wxs(version: str) -> None:
    WIX_DIR.mkdir(parents=True, exist_ok=True)
    directory_lines, component_refs = emit_directory(STAGING_ROOT)
    shortcut_component_refs = [
        "Cmp_StartMenuShortcuts",
        "Cmp_DesktopShortcut",
    ]
    refs = "\n".join(
        f'      <ComponentRef Id="{component_id}" />'
        for component_id in component_refs + shortcut_component_refs
    )
    body = "\n".join(directory_lines)
    wxs = f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Package
    Name="Gemma4_12B"
    Manufacturer="Gemma4_12B Project"
    Version="{html.escape(version)}"
    UpgradeCode="7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1"
    Scope="perMachine">
    <MajorUpgrade DowngradeErrorMessage="A newer version of Gemma4_12B is already installed." />
    <MediaTemplate EmbedCab="yes" />
    <StandardDirectory Id="ProgramFilesFolder">
      <Directory Id="INSTALLFOLDER" Name="Gemma4_12B">
{body}
        <Component Id="Cmp_StartMenuShortcuts" Guid="*">
          <Shortcut
            Id="StartMenuWebShortcut"
            Directory="ApplicationProgramsFolder"
            Name="Gemma4 12B Web UI"
            Description="Gemma4 12B Web UIを起動"
            Target="[INSTALLFOLDER]Gemma4_12B_Launcher.exe"
            Arguments="web"
            WorkingDirectory="INSTALLFOLDER" />
          <Shortcut
            Id="StartMenuAllShortcut"
            Directory="ApplicationProgramsFolder"
            Name="Gemma4 12B 全部起動"
            Description="Gemma4 12B Web UIと周辺機能を起動"
            Target="[INSTALLFOLDER]Gemma4_12B_Launcher.exe"
            Arguments="all"
            WorkingDirectory="INSTALLFOLDER" />
          <Shortcut
            Id="StartMenuStopShortcut"
            Directory="ApplicationProgramsFolder"
            Name="Gemma4 12B 重い処理を停止"
            Description="Gemma4 12Bの重い処理を停止"
            Target="[INSTALLFOLDER]Gemma4_12B_Launcher.exe"
            Arguments="stop-heavy"
            WorkingDirectory="INSTALLFOLDER" />
          <RemoveFolder Id="RemoveApplicationProgramsFolder" Directory="ApplicationProgramsFolder" On="uninstall" />
          <RegistryValue Root="HKLM" Key="Software\\Gemma4_12B" Name="startMenuShortcuts" Type="integer" Value="1" KeyPath="yes" />
        </Component>
        <Component Id="Cmp_DesktopShortcut" Guid="*">
          <Shortcut
            Id="DesktopWebShortcut"
            Directory="DesktopFolder"
            Name="Gemma4 12B Web UI"
            Description="Gemma4 12B Web UIを起動"
            Target="[INSTALLFOLDER]Gemma4_12B_Launcher.exe"
            Arguments="web"
            WorkingDirectory="INSTALLFOLDER" />
          <RegistryValue Root="HKLM" Key="Software\\Gemma4_12B" Name="desktopShortcut" Type="integer" Value="1" KeyPath="yes" />
        </Component>
      </Directory>
    </StandardDirectory>
    <StandardDirectory Id="ProgramMenuFolder">
      <Directory Id="ApplicationProgramsFolder" Name="Gemma4 12B" />
    </StandardDirectory>
    <StandardDirectory Id="DesktopFolder" />
    <Feature Id="MainFeature" Title="Gemma4_12B" Level="1">
{refs}
    </Feature>
  </Package>
</Wix>
"""
    WXS_PATH.write_text(wxs, encoding="utf-8")


def build_msi(version: str) -> Path:
    wix = shutil.which("wix")
    if not wix:
        raise SystemExit(
            "WiX Toolset が見つかりません。Windowsで `dotnet tool install --global wix` を実行してください。"
        )
    out_path = DIST / f"Gemma4_12B-v{version}-windows.msi"
    subprocess.run([wix, "build", str(WXS_PATH), "-arch", "x64", "-out", str(out_path)], check=True)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", nargs="?", default="")
    parser.add_argument("--no-build", action="store_true", help="Stage files and generate WiX XML only.")
    args = parser.parse_args()

    version = args.version or read_app_version()
    version = version.removeprefix("v")
    DIST.mkdir(exist_ok=True)

    stage_payload()
    generate_wxs(version)

    print(f"Staged payload: {STAGING_ROOT}")
    print(f"Generated WiX source: {WXS_PATH}")

    if args.no_build:
        return 0

    out_path = build_msi(version)
    print(f"Created {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
