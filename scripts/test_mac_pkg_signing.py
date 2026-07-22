#!/usr/bin/env python3
from pathlib import Path
import os
import shutil
import subprocess
import tempfile


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
    assert 'APP_PATH="$WORK_DIR/pkgroot/Applications/TOMOS AI.app"' in script
    assert 'make-mac-app.sh" "$APP_VERSION" "$APP_PATH"' in script
    assert 'pkgroot/Applications/Gemma4_12B' not in script


def test_pkg_rejects_adhoc_application_identity_before_building() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        scripts = temp / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts" / "make-mac-pkg.sh", scripts / "make-mac-pkg.sh")
        (scripts / "make-mac-app.sh").write_text(
            "#!/usr/bin/env bash\nprintf 'app-build\\n' >> \"$TOMOS_TEST_EVENTS\"\n",
            encoding="utf-8",
        )
        (temp / "dist").mkdir()
        events = temp / "events.log"
        environment = os.environ.copy()
        environment.update({
            "TOMOS_MAC_APPLICATION_IDENTITY": "-",
            "TOMOS_MAC_INSTALLER_IDENTITY": "Developer ID Installer: Fixture (TEAMID)",
            "TOMOS_TEST_EVENTS": str(events),
        })
        completed = subprocess.run(
            ["/bin/bash", str(scripts / "make-mac-pkg.sh"), "0.8.221"],
            cwd=temp,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        assert completed.returncode != 0
        assert "Developer ID Application" in completed.stderr
        assert not events.exists()


def test_pkg_verifies_developer_id_application_authority_with_fixture() -> None:
    script = (ROOT / "scripts" / "make-mac-pkg.sh").read_text(encoding="utf-8")
    assert 'codesign --verify --deep --strict --verbose=2 "$APP_PATH"' in script
    assert 'Authority=Developer ID Application:' in script
    assert 'TOMOS_MAC_APPLICATION_IDENTITY' in script


def test_notarization_script_verifies_every_release_gate() -> None:
    script = (ROOT / "scripts" / "notarize-mac-pkg.sh").read_text(encoding="utf-8")
    assert 'pkgutil --check-signature "$PKG_PATH"' in script
    assert 'notarytool submit "$PKG_PATH"' in script
    assert '--keychain-profile "$NOTARY_PROFILE"' in script
    assert "--wait" in script
    assert 'stapler staple "$PKG_PATH"' in script
    assert 'stapler validate "$PKG_PATH"' in script
    assert 'spctl -a -vv -t install "$PKG_PATH"' in script


def test_github_actions_builds_windows_only_and_keeps_mac_signing_local() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build-installers.yml").read_text(
        encoding="utf-8"
    )
    assert "windows-msi:" in workflow
    assert "make-windows-msi.py" in workflow
    assert "mac-pkg:" not in workflow
    assert "make-mac-pkg.sh" not in workflow


if __name__ == "__main__":
    test_pkg_build_requires_developer_id_installer()
    test_pkg_contains_signed_app_bundle_instead_of_legacy_folder()
    test_pkg_rejects_adhoc_application_identity_before_building()
    test_pkg_verifies_developer_id_application_authority_with_fixture()
    test_notarization_script_verifies_every_release_gate()
    test_github_actions_builds_windows_only_and_keeps_mac_signing_local()
    print("macOS PKG signing tests: OK")
