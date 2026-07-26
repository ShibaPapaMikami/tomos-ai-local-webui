from pathlib import Path
import json
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "0.8.233"


def read_release_versions(root: Path) -> dict[str, str]:
    server = (root / "server.py").read_text(encoding="utf-8")
    server_version_match = re.search(r'GEMMA_APP_VERSION", "([^"]+)"', server)
    assert server_version_match is not None, "server.py must define GEMMA_APP_VERSION"
    cargo = tomllib.loads((root / "src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    tauri = json.loads((root / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    lock = tomllib.loads((root / "src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    desktop_package = next(
        (package for package in lock["package"] if package["name"] == "tomos-desktop"),
        None,
    )
    assert desktop_package is not None, "Cargo.lock must define tomos-desktop"
    return {
        "server": server_version_match.group(1),
        "cargo": cargo["package"]["version"],
        "tauri": tauri["version"],
        "cargo_lock": desktop_package["version"],
    }


def test_release_versions_match() -> None:
    versions = read_release_versions(ROOT)
    assert versions == {
        "server": EXPECTED,
        "cargo": EXPECTED,
        "tauri": EXPECTED,
        "cargo_lock": EXPECTED,
    }


if __name__ == "__main__":
    test_release_versions_match()
    print("desktop release version tests passed")
