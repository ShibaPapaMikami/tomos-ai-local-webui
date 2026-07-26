from __future__ import annotations

import json
import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TAURI_ROOT = ROOT / "src-tauri"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_files_exist() -> None:
    required = [
        TAURI_ROOT / "Cargo.toml",
        TAURI_ROOT / "build.rs",
        TAURI_ROOT / "tauri.conf.json",
        TAURI_ROOT / "Info.plist",
        TAURI_ROOT / "capabilities" / "main.json",
        TAURI_ROOT / "icons" / "icon.png",
        TAURI_ROOT / "src" / "main.rs",
        TAURI_ROOT / "src" / "lib.rs",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing desktop shell files: {missing}"


def test_cargo_dependencies_are_minimal() -> None:
    cargo = read(TAURI_ROOT / "Cargo.toml")
    assert 'tauri = { version = "2"' in cargo
    assert 'tauri-build = { version = "2"' in cargo
    assert 'tauri-plugin-single-instance = "2"' in cargo
    assert "tauri-plugin-shell" not in cargo
    assert "reqwest" not in cargo
    assert "[features]" in cargo
    assert "development-runtime-override = []" in cargo


def test_tauri_window_and_bundle_contract() -> None:
    config = json.loads(read(TAURI_ROOT / "tauri.conf.json"))
    assert config["productName"] == "TOMOS AI"
    assert config["identifier"] == "com.shibapapastudio.tomos-ai"
    assert config["build"]["frontendDist"] == "../web"
    assert config["app"]["windows"] == []
    assert config["bundle"]["active"] is True


def test_macos_bundle_declares_microphone_usage() -> None:
    with (TAURI_ROOT / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    assert info["NSMicrophoneUsageDescription"] == (
        "音声入力と文字起こしのためにマイクを使用します。"
    )


def test_capability_has_no_shell_or_external_write_permission() -> None:
    capability = json.loads(read(TAURI_ROOT / "capabilities" / "main.json"))
    permissions = set(capability["permissions"])
    assert capability["windows"] == ["main"]
    assert permissions == {"core:default"}


def test_git_ignores_rust_build_output() -> None:
    patterns = read(ROOT / ".gitignore").splitlines()
    assert "src-tauri/target/" in patterns
    assert "src-tauri/gen/schemas/" in patterns


def test_runtime_is_local_only_and_does_not_kill_unknown_processes() -> None:
    runtime = read(TAURI_ROOT / "src" / "runtime.rs")
    assert 'pub const TOMOS_HOST: &str = "127.0.0.1";' in runtime
    assert "pub const TOMOS_PORT: u16 = 54876;" in runtime
    assert "pub struct RuntimePaths" in runtime
    assert "pub server: PathBuf" in runtime
    assert "pub fn resolve_runtime_paths(" in runtime
    assert "InvalidBundledRuntime" in runtime
    assert 'join("tomos")' in runtime
    assert 'join("python/bin/python3")' in runtime
    assert "Command::new(&paths.python)" in runtime
    assert ".arg(&paths.server)" in runtime
    assert ".current_dir(&paths.resource_root)" in runtime
    assert "TOMOS_PYTHON" not in runtime
    assert "CARGO_MANIFEST_DIR" not in runtime
    assert "debug_assertions" not in runtime
    assert '#[cfg(feature = "development-runtime-override")]' in runtime
    assert "PortState::Occupied => return Err(RuntimeError::PortInUse)" in runtime
    assert "kill_port" not in runtime
    assert "pkill" not in runtime
    assert "killall" not in runtime


def test_lifecycle_uses_single_instance_and_owned_cleanup() -> None:
    lib = read(TAURI_ROOT / "src" / "lib.rs")
    compact = "".join(lib.split())
    assert "tauri_plugin_single_instance::init" in lib
    assert "SECOND_INSTANCE_FOCUS_DELAY_MS" in lib
    assert "refocus_after_second_instance(window)" in lib
    assert "Duration::from_millis(SECOND_INSTANCE_FOCUS_DELAY_MS)" in lib
    assert "PageLoadEvent::Finished" in lib
    assert "runtime_started.swap(true, Ordering::SeqCst)" in lib
    assert ".on_page_load(move |window, payload|" in lib
    assert 'get_webview_window("main")' in lib
    assert "RuntimeSupervisor::default()" in lib
    assert "app.path().resource_dir()" in compact
    assert "resolve_runtime_paths(&resource_dir, development_override.as_deref())" in lib
    assert "debug_assertions" not in lib
    assert '#[cfg(feature = "development-runtime-override")]' in lib
    assert "supervisor.stop_owned()" in lib
    assert "WindowEvent::CloseRequested" in lib
    assert "WindowEvent::Destroyed" in lib
    assert "app_handle.exit(0)" in lib
    assert "http://127.0.0.1:54876/" in lib
    assert 'WebviewWindowBuilder::new(app,"main"' in compact
    assert ".inner_size(1280.0, 820.0)" in lib
    assert ".min_inner_size(960.0, 640.0)" in lib
    assert ".on_navigation(|url|" in lib
    assert 'url.host_str() == Some("127.0.0.1")' in lib
    assert 'url.host_str() == Some("tauri.localhost")' in lib
    assert "open::that" not in lib
    assert "shell" not in lib.lower()


def test_startup_page_has_fixed_japanese_errors() -> None:
    html = read(ROOT / "web" / "desktop-starting.html")
    script = read(ROOT / "web" / "desktop-starting.js")
    assert 'id="desktop-startup-title"' in html
    assert 'id="desktop-startup-message"' in html
    assert "TOMOSを起動しています" in html
    assert 'const reinstallMessage = "TOMOSの実行環境を確認できませんでした。再インストールしてください。"' in script
    assert '"invalid_bundled_runtime": reinstallMessage' in script
    assert '"missing_resource_root": reinstallMessage' in script
    assert '"missing_python"' in script
    assert '"port_in_use"' in script
    assert '"server_exited"' in script
    assert '"timeout"' in script
    assert "innerHTML" not in script
    assert "textContent" in script


def main() -> None:
    tests = [
        test_required_files_exist,
        test_cargo_dependencies_are_minimal,
        test_tauri_window_and_bundle_contract,
        test_macos_bundle_declares_microphone_usage,
        test_capability_has_no_shell_or_external_write_permission,
        test_git_ignores_rust_build_output,
        test_runtime_is_local_only_and_does_not_kill_unknown_processes,
        test_lifecycle_uses_single_instance_and_owned_cleanup,
        test_startup_page_has_fixed_japanese_errors,
    ]
    for test in tests:
        test()
    print("desktop shell contract tests passed")


if __name__ == "__main__":
    main()
