#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pkg_build_requires_developer_id_installer() -> None:
    script = (ROOT / "scripts" / "make-mac-pkg.sh").read_text(encoding="utf-8")
    assert "TOMOS_MAC_INSTALLER_IDENTITY" in script
    assert 'Developer ID Installer:' in script
    assert "sort -u" in script
    assert '--sign "$SIGNING_IDENTITY"' in script
    assert 'pkgutil --check-signature "$OUT_PKG"' in script


def test_pkg_contains_signed_app_bundle_instead_of_legacy_folder() -> None:
    script = (ROOT / "scripts" / "make-mac-pkg.sh").read_text(encoding="utf-8")
    assert 'make-mac-app.sh" "$APP_VERSION" "$WORK_DIR/pkgroot/Applications/TOMOS AI.app"' in script
    assert 'pkgroot/Applications/Gemma4_12B' not in script


def test_notarization_script_verifies_every_release_gate() -> None:
    script = (ROOT / "scripts" / "notarize-mac-pkg.sh").read_text(encoding="utf-8")
    assert 'pkgutil --check-signature "$PKG_PATH"' in script
    assert 'notarytool submit "$PKG_PATH"' in script
    assert '--keychain-profile "$NOTARY_PROFILE"' in script
    assert "--wait" in script
    assert 'stapler staple "$PKG_PATH"' in script
    assert 'stapler validate "$PKG_PATH"' in script
    assert 'spctl -a -vv -t install "$PKG_PATH"' in script


if __name__ == "__main__":
    test_pkg_build_requires_developer_id_installer()
    test_pkg_contains_signed_app_bundle_instead_of_legacy_folder()
    test_notarization_script_verifies_every_release_gate()
    print("macOS PKG signing tests: OK")
