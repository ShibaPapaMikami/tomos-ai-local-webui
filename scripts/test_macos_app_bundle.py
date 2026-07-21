#!/usr/bin/env python3
"""Contract tests for the TOMOS AI macOS application bundle."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bundle_script_declares_required_structure() -> None:
    script = (ROOT / "scripts" / "make-mac-app.sh").read_text(encoding="utf-8")
    assert "Contents/MacOS" in script
    assert "Contents/Resources/Gemma4_12B" in script
    assert "Contents/Info.plist" in script
    assert "com.shibapapastudio.tomos-ai" in script
    assert "Developer ID Application:" in script
    assert 'codesign --force --options runtime --timestamp' in script
    assert "sips -s format icns" in script


def test_release_archive_contains_launcher_source() -> None:
    script = (ROOT / "scripts" / "make-release-archives.sh").read_text(encoding="utf-8")
    assert 'copy_if_exists "scripts/macos-app-launcher.sh"' in script


if __name__ == "__main__":
    test_bundle_script_declares_required_structure()
    test_release_archive_contains_launcher_source()
    print("macOS app bundle tests: OK")
