# TOMOS TauriデスクトップShell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 既存TOMOSをブラウザーで開かず、macOSのTauri専用ウィンドウで起動・終了できる最小デスクトップShellを作る。

**Architecture:** Tauriは既存の `server.py` を `127.0.0.1:54876` で子プロセス起動し、health成功後に同じ `web/` UIをWebViewへ表示する。最初のPoCではシステムPythonと既存Ollamaを使い、ブラウザー/PWA経路、保存キー、Pythonコード、モデル構成を変更しない。

**Tech Stack:** Rust 1.94、Cargo、Tauri 2、Tauri single-instance plugin、Python 3.11、既存HTML/CSS/JavaScript、Node.js既存テスト。

## Global Constraints

- 正本設計は `docs/superpowers/specs/2026-07-24-tomos-desktop-app-evolution-design.md`。
- 全体順序は `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`。
- Gate 0合格前にこの計画を実装しない。
- Tauri関連crateの取得は依存追加に該当するため、Directorの明示承認前に `cargo build`、`cargo test`、`cargo run` を実行しない。
- 初期対象はmacOSの開発用PoC。配布、署名、公証、MSI、Python同梱はこの計画へ入れない。
- Bundle IDは `com.shibapapastudio.tomos-ai`。
- アプリ名は `TOMOS AI`。
- 初期ウィンドウは `1280 × 820`、最小 `960 × 640`。
- 待受先は `127.0.0.1:54876`。localhost以外で待ち受けない。
- `server.py`、`web/app.js`、`web/models.js`、`web/settings.js`、`web/asr.js`、`web/management.js` を変更しない。
- `gemma4.*` localStorageキー、Knowledge、Memory、教材パック、Plugin権限を変更しない。
- `.command`、`.bat`、Mac PKG、Windows MSI、PWAを削除または置換しない。
- 任意shell実行、外部API、モデル取得、モデル削除、Memory自動保存を追加しない。
- ポートを使う別プロセスを自動停止しない。
- アプリ終了時は、アプリが生成したPython子プロセスだけを停止する。
- commitはDirectorが明示承認したTaskだけ実行する。

---

## Entry Gate A0: 依存追加承認

承認記録:

- 2026-07-24: Directorが `tauri 2`、`tauri-build 2`、`tauri-plugin-single-instance 2` のcrates.ioからの取得を承認。
- Phase 0 commit: `478e867e89664f7a8caa9d25d3d5ba098680f806`
- 確認済み環境: Rust `1.94.1`、Cargo `1.94.1`、Python `3.14.4`
- push、配布、署名、公証は未承認。

実装開始前に次を記録する。

```bash
git status --short --branch
git rev-parse HEAD
rustc --version
cargo --version
python3 --version
```

期待する基準:

```text
rustc 1.94.1
cargo 1.94.1
Python 3.14.4
```

時点差でpatch versionが変わっていても、Rust 1.85以上、Python 3.11以上なら続行できる。既存9テストが合格しないPythonでは進めず、インストールせず停止する。

Directorへ次を提示し、承認を得る。

```text
追加する依存:
- tauri 2
- tauri-build 2
- tauri-plugin-single-instance 2

取得元:
- crates.io

用途:
- TOMOS専用ウィンドウ
- 単一起動
- macOS/Windows共通Shell

この工程で行わないこと:
- npm依存追加
- Python依存追加
- モデル取得
- app配布
- 署名・公証
```

承認がない場合は、この計画文書以外を変更しない。

## File Map

- Create: `src-tauri/Cargo.toml` — Tauri ShellのRust依存とbinary定義。
- Create: `src-tauri/Cargo.lock` — Gate A0承認後の最初のCargo実行で生成し、依存versionを固定。
- Create: `src-tauri/build.rs` — Tauri設定をbuildへ反映。
- Create: `src-tauri/tauri.conf.json` — アプリ名、Bundle ID、ウィンドウ、CSP。
- Create: `src-tauri/capabilities/main.json` — main windowへ最小権限だけを許可。
- Create: `src-tauri/src/main.rs` — binary entrypoint。
- Create: `src-tauri/src/lib.rs` — Tauri lifecycle、single instance、WebView遷移。
- Create: `src-tauri/src/runtime.rs` — TOMOSサーバーの判定、起動、停止。
- Create: `web/desktop-starting.html` — 起動中と起動失敗だけを表示する静的画面。
- Create: `web/desktop-starting.js` — 固定エラーコードを日本語表示へ変換。
- Create: `scripts/test-desktop-shell-contract.py` — Tauri設定と安全境界の依存なし契約テスト。
- Modify: `.gitignore` — `src-tauri/target/` を除外。

## Public Contracts

### Rust

```rust
pub const TOMOS_HOST: &str = "127.0.0.1";
pub const TOMOS_PORT: u16 = 54876;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PortState {
    Free,
    TomosReady,
    Occupied,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RuntimeOwnership {
    Reused,
    Owned,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuntimeError {
    MissingResourceRoot,
    MissingPython,
    PortInUse,
    ServerExited,
    Timeout,
}

pub struct RuntimeSupervisor {
    child: std::sync::Mutex<Option<std::process::Child>>,
    ownership: std::sync::Mutex<Option<RuntimeOwnership>>,
}

impl RuntimeSupervisor {
    pub fn start(&self, resource_root: &std::path::Path) -> Result<RuntimeOwnership, RuntimeError>;
    pub fn stop_owned(&self);
}
```

### Startup page

```js
window.TOMOS_DESKTOP_STARTUP.showReady();
window.TOMOS_DESKTOP_STARTUP.showError("missing_python");
window.TOMOS_DESKTOP_STARTUP.showError("port_in_use");
window.TOMOS_DESKTOP_STARTUP.showError("server_exited");
window.TOMOS_DESKTOP_STARTUP.showError("timeout");
```

未定義コードは「TOMOSを起動できませんでした。診断情報を確認してください。」へ落とす。

---

### Task 1: Tauri Shellの安全契約をテストで固定する

**Files:**

- Create: `scripts/test-desktop-shell-contract.py`
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/capabilities/main.json`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: `web/` の既存静的資産、Bundle ID `com.shibapapastudio.tomos-ai`。
- Produces: Cargoからcompile可能なTauri projectと、権限を監視する依存なしテスト。

- [ ] **Step 1: 失敗する契約テストを書く**

`scripts/test-desktop-shell-contract.py` を次の内容で作る。

```python
from __future__ import annotations

import json
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
        TAURI_ROOT / "capabilities" / "main.json",
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


def test_tauri_window_and_bundle_contract() -> None:
    config = json.loads(read(TAURI_ROOT / "tauri.conf.json"))
    assert config["productName"] == "TOMOS AI"
    assert config["identifier"] == "com.shibapapastudio.tomos-ai"
    assert config["build"]["frontendDist"] == "../web"
    assert config["app"]["windows"] == []
    assert config["bundle"]["active"] is False


def test_capability_has_no_shell_or_external_write_permission() -> None:
    capability = json.loads(read(TAURI_ROOT / "capabilities" / "main.json"))
    permissions = set(capability["permissions"])
    assert capability["windows"] == ["main"]
    assert permissions == {"core:default"}


def test_git_ignores_rust_build_output() -> None:
    patterns = read(ROOT / ".gitignore").splitlines()
    assert "src-tauri/target/" in patterns


def main() -> None:
    tests = [
        test_required_files_exist,
        test_cargo_dependencies_are_minimal,
        test_tauri_window_and_bundle_contract,
        test_capability_has_no_shell_or_external_write_permission,
        test_git_ignores_rust_build_output,
    ]
    for test in tests:
        test()
    print("desktop shell contract tests passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
python3 scripts/test-desktop-shell-contract.py
```

期待結果: `missing desktop shell files` を含む `AssertionError` で失敗する。

- [ ] **Step 3: 最小Tauri projectを作る**

`src-tauri/Cargo.toml`:

```toml
[package]
name = "tomos-desktop"
version = "0.8.219"
description = "TOMOS AI desktop shell"
edition = "2021"

[lib]
name = "tomos_desktop_lib"
crate-type = ["lib", "cdylib", "staticlib"]

[[bin]]
name = "tomos-desktop"
path = "src/main.rs"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-single-instance = "2"
```

`src-tauri/build.rs`:

```rust
fn main() {
    tauri_build::build()
}
```

`src-tauri/tauri.conf.json`:

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "TOMOS AI",
  "version": "0.8.219",
  "identifier": "com.shibapapastudio.tomos-ai",
  "build": {
    "frontendDist": "../web"
  },
  "app": {
    "windows": [],
    "security": {
      "csp": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' http://127.0.0.1:54876"
    }
  },
  "bundle": {
    "active": false
  }
}
```

`src-tauri/capabilities/main.json`:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "main-capability",
  "description": "TOMOS main window with core window capabilities only",
  "windows": ["main"],
  "permissions": ["core:default"]
}
```

`.gitignore` のローカル状態除外へ次を追加する。

```gitignore
src-tauri/target/
```

`src-tauri/src/main.rs`:

```rust
fn main() {}
```

`src-tauri/src/lib.rs`:

```rust
// Runtime and lifecycle are added by the next test-first tasks.
```

- [ ] **Step 4: 設定契約テストを合格させる**

```bash
python3 scripts/test-desktop-shell-contract.py
```

期待結果:

```text
desktop shell contract tests passed
```

- [ ] **Step 5: 承認済みの場合だけTask単位でcommitする**

```bash
git add .gitignore scripts/test-desktop-shell-contract.py src-tauri/Cargo.toml src-tauri/build.rs src-tauri/tauri.conf.json src-tauri/capabilities/main.json src-tauri/src/main.rs src-tauri/src/lib.rs
git commit -m "test: define TOMOS desktop shell contract"
```

commit未承認なら実行せず、差分を次Taskへ保持する。

---

### Task 2: Runtime Supervisorをテスト先行で作る

**Files:**

- Modify: `src-tauri/src/runtime.rs`

**Interfaces:**

- Consumes: `TOMOS_RESOURCE_ROOT`、`TOMOS_PYTHON`、`server.py`、`GET /api/health`。
- Produces: `RuntimeSupervisor::start()`、`RuntimeSupervisor::stop_owned()`、`PortState`、`RuntimeError`。

- [ ] **Step 1: runtime単体テストを書く**

最初に `scripts/test-desktop-shell-contract.py` へ次を追加し、`main()` のtests配列にも登録する。

```python
def test_runtime_is_local_only_and_does_not_kill_unknown_processes() -> None:
    runtime = read(TAURI_ROOT / "src" / "runtime.rs")
    assert 'pub const TOMOS_HOST: &str = "127.0.0.1";' in runtime
    assert "pub const TOMOS_PORT: u16 = 54876;" in runtime
    assert "PortState::Occupied => return Err(RuntimeError::PortInUse)" in runtime
    assert "kill_port" not in runtime
    assert "pkill" not in runtime
    assert "killall" not in runtime
```

続けて `src-tauri/src/lib.rs` を次へ変更する。

```rust
pub mod runtime;
```

`src-tauri/src/runtime.rs` を作り、ファイル末尾へ実装より先に次のテストを書く。

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_tomos_health_payload() {
        let response = "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n{\"ok\":true,\"appVersion\":\"0.8.219\"}";
        assert_eq!(classify_health_response(response), PortState::TomosReady);
    }

    #[test]
    fn accepts_tomos_health_when_ollama_is_offline() {
        let response = "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n{\"ok\":false,\"appVersion\":\"0.8.219\",\"ollama\":\"offline\"}";
        assert_eq!(classify_health_response(response), PortState::TomosReady);
    }

    #[test]
    fn rejects_foreign_http_payload() {
        let response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nhello";
        assert_eq!(classify_health_response(response), PortState::Occupied);
    }

    #[test]
    fn rejects_error_health_payload() {
        let response = "HTTP/1.1 500 Internal Server Error\r\n\r\n{\"ok\":false,\"appVersion\":\"0.8.219\"}";
        assert_eq!(classify_health_response(response), PortState::Occupied);
    }

    #[test]
    fn maps_runtime_errors_to_fixed_codes() {
        assert_eq!(RuntimeError::MissingPython.code(), "missing_python");
        assert_eq!(RuntimeError::PortInUse.code(), "port_in_use");
        assert_eq!(RuntimeError::ServerExited.code(), "server_exited");
        assert_eq!(RuntimeError::Timeout.code(), "timeout");
    }
}
```

- [ ] **Step 2: PythonとRust testを実行し、失敗を確認する**

Entry Gate A0の依存追加承認後だけ実行する。

```bash
python3 scripts/test-desktop-shell-contract.py
cargo test --manifest-path src-tauri/Cargo.toml runtime::tests
```

期待結果:

- Pythonはruntime契約不足で失敗する。
- Rustは `classify_health_response`、`RuntimeError::code`、型定義が存在しないためcompile error。

- [ ] **Step 3: Runtime Supervisorを最小実装する**

`src-tauri/src/runtime.rs` を次の責務で実装する。

```rust
use std::env;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

pub const TOMOS_HOST: &str = "127.0.0.1";
pub const TOMOS_PORT: u16 = 54876;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PortState {
    Free,
    TomosReady,
    Occupied,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RuntimeOwnership {
    Reused,
    Owned,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuntimeError {
    MissingResourceRoot,
    MissingPython,
    PortInUse,
    ServerExited,
    Timeout,
}

impl RuntimeError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::MissingResourceRoot => "missing_resource_root",
            Self::MissingPython => "missing_python",
            Self::PortInUse => "port_in_use",
            Self::ServerExited => "server_exited",
            Self::Timeout => "timeout",
        }
    }
}

pub struct RuntimeSupervisor {
    child: Mutex<Option<Child>>,
    ownership: Mutex<Option<RuntimeOwnership>>,
}

impl Default for RuntimeSupervisor {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            ownership: Mutex::new(None),
        }
    }
}

pub fn resolve_resource_root() -> Result<PathBuf, RuntimeError> {
    if let Some(configured) = env::var_os("TOMOS_RESOURCE_ROOT") {
        let root = PathBuf::from(configured);
        if root.join("server.py").is_file() {
            return Ok(root);
        }
        return Err(RuntimeError::MissingResourceRoot);
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .ok_or(RuntimeError::MissingResourceRoot)?;
    if root.join("server.py").is_file() {
        Ok(root)
    } else {
        Err(RuntimeError::MissingResourceRoot)
    }
}

pub fn classify_health_response(response: &str) -> PortState {
    let compact = response.replace(' ', "");
    if (response.starts_with("HTTP/1.0 200") || response.starts_with("HTTP/1.1 200"))
        && compact.contains("\"appVersion\"")
    {
        PortState::TomosReady
    } else if response.starts_with("HTTP/") {
        PortState::Occupied
    } else {
        PortState::Occupied
    }
}

fn probe_port() -> PortState {
    let address = SocketAddr::from(([127, 0, 0, 1], TOMOS_PORT));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(250)) else {
        return PortState::Free;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(4)));
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: {TOMOS_HOST}:{TOMOS_PORT}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return PortState::Occupied;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return PortState::Occupied;
    }
    classify_health_response(&response)
}

impl RuntimeSupervisor {
    pub fn start(&self, resource_root: &Path) -> Result<RuntimeOwnership, RuntimeError> {
        match probe_port() {
            PortState::TomosReady => {
                *self.ownership.lock().expect("ownership lock") = Some(RuntimeOwnership::Reused);
                return Ok(RuntimeOwnership::Reused);
            }
            PortState::Occupied => return Err(RuntimeError::PortInUse),
            PortState::Free => {}
        }

        let python = env::var("TOMOS_PYTHON").unwrap_or_else(|_| "python3".to_string());
        let child = Command::new(&python)
            .arg("server.py")
            .arg("--host")
            .arg(TOMOS_HOST)
            .arg("--port")
            .arg(TOMOS_PORT.to_string())
            .current_dir(resource_root)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| {
                if error.kind() == std::io::ErrorKind::NotFound {
                    RuntimeError::MissingPython
                } else {
                    RuntimeError::ServerExited
                }
            })?;

        *self.child.lock().expect("child lock") = Some(child);
        *self.ownership.lock().expect("ownership lock") = Some(RuntimeOwnership::Owned);

        let deadline = Instant::now() + Duration::from_secs(30);
        while Instant::now() < deadline {
            {
                let mut child_guard = self.child.lock().expect("child lock");
                if let Some(child) = child_guard.as_mut() {
                    if child.try_wait().map_err(|_| RuntimeError::ServerExited)?.is_some() {
                        child_guard.take();
                        return Err(RuntimeError::ServerExited);
                    }
                }
            }
            if probe_port() == PortState::TomosReady {
                return Ok(RuntimeOwnership::Owned);
            }
            thread::sleep(Duration::from_millis(250));
        }

        self.stop_owned();
        Err(RuntimeError::Timeout)
    }

    pub fn stop_owned(&self) {
        let ownership = *self.ownership.lock().expect("ownership lock");
        if ownership != Some(RuntimeOwnership::Owned) {
            return;
        }
        if let Some(mut child) = self.child.lock().expect("child lock").take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *self.ownership.lock().expect("ownership lock") = None;
    }
}
```

health JSONは `appVersion` をTOMOS識別子として使う。Ollama停止時の `"ok": false` でも既存TOMOS serverを再利用し、UI上の既存エラー案内へ接続する。JSON parser crateは追加しない。

- [ ] **Step 4: runtime testを合格させる**

```bash
cargo test --manifest-path src-tauri/Cargo.toml runtime::tests
test -f src-tauri/Cargo.lock
```

期待結果: 5 tests passed。`src-tauri/Cargo.lock` が存在する。

- [ ] **Step 5: Python契約テストを進める**

```bash
python3 scripts/test-desktop-shell-contract.py
```

期待結果: runtimeのlocal-only契約は合格し、未作成のstartup pageまたはlifecycleで失敗する。

- [ ] **Step 6: 承認済みの場合だけTask単位でcommitする**

```bash
git add scripts/test-desktop-shell-contract.py src-tauri/Cargo.lock src-tauri/src/lib.rs src-tauri/src/runtime.rs
git commit -m "feat: add TOMOS desktop runtime supervisor"
```

---

### Task 3: Tauri lifecycleと単一起動を接続する

**Files:**

- Modify: `src-tauri/src/main.rs`
- Modify: `src-tauri/src/lib.rs`

**Interfaces:**

- Consumes: `runtime::resolve_resource_root()`、`RuntimeSupervisor`、main WebView window。
- Produces: server準備後のアプリ内遷移、既存window focus、owned child cleanup。

- [ ] **Step 1: lifecycle契約をPythonテストへ追加する**

`scripts/test-desktop-shell-contract.py` へ次を追加し、`main()` のtests配列にも登録する。

```python
def test_lifecycle_uses_single_instance_and_owned_cleanup() -> None:
    lib = read(TAURI_ROOT / "src" / "lib.rs")
    assert "tauri_plugin_single_instance::init" in lib
    assert 'get_webview_window("main")' in lib
    assert "RuntimeSupervisor::default()" in lib
    assert "supervisor.stop_owned()" in lib
    assert "WindowEvent::CloseRequested" in lib
    assert "app_handle.exit(0)" in lib
    assert "http://127.0.0.1:54876/" in lib
    assert 'WebviewWindowBuilder::new(app, "main"' in lib
    assert '.inner_size(1280.0, 820.0)' in lib
    assert '.min_inner_size(960.0, 640.0)' in lib
    assert '.on_navigation(|url|' in lib
    assert 'url.host_str() == Some("127.0.0.1")' in lib
    assert 'url.host_str() == Some("tauri.localhost")' in lib
    assert "open::that" not in lib
    assert "shell" not in lib.lower()
```

- [ ] **Step 2: 契約テストが失敗することを確認する**

```bash
python3 scripts/test-desktop-shell-contract.py
```

期待結果: `tauri_plugin_single_instance::init` のassertionで失敗する。

- [ ] **Step 3: binary entrypointを実装する**

`src-tauri/src/main.rs`:

```rust
fn main() {
    tomos_desktop_lib::run();
}
```

- [ ] **Step 4: lifecycleを実装する**

`src-tauri/src/lib.rs` は次の順序を満たす。

```rust
mod runtime;

use std::sync::Arc;
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};

use runtime::{resolve_resource_root, RuntimeSupervisor};

pub fn run() {
    let supervisor = Arc::new(RuntimeSupervisor::default());
    let setup_supervisor = Arc::clone(&supervisor);

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .setup(move |app| {
            let window = WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::App("desktop-starting.html".into()),
            )
            .title("TOMOS AI")
            .inner_size(1280.0, 820.0)
            .min_inner_size(960.0, 640.0)
            .center()
            .on_navigation(|url| {
                let bundled_asset = url.scheme() == "tauri"
                    || url.host_str() == Some("tauri.localhost");
                let tomos_local = url.scheme() == "http"
                    && url.host_str() == Some("127.0.0.1")
                    && url.port_or_known_default() == Some(54876);
                bundled_asset || tomos_local
            })
            .build()?;
            let runtime = Arc::clone(&setup_supervisor);
            tauri::async_runtime::spawn_blocking(move || {
                let result = resolve_resource_root().and_then(|root| runtime.start(&root));
                match result {
                    Ok(_) => {
                        let url = "http://127.0.0.1:54876/"
                            .parse()
                            .expect("valid TOMOS URL");
                        let _ = window.navigate(url);
                    }
                    Err(error) => {
                        let script = format!(
                            "window.TOMOS_DESKTOP_STARTUP && window.TOMOS_DESKTOP_STARTUP.showError({:?});",
                            error.code()
                        );
                        let _ = window.eval(&script);
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("TOMOS desktop app build failed");

    app.run(move |app_handle, event| {
        match event {
            RunEvent::WindowEvent {
                label,
                event: WindowEvent::CloseRequested { .. },
                ..
            } if label == "main" => {
                supervisor.stop_owned();
                app_handle.exit(0);
            }
            RunEvent::Exit | RunEvent::ExitRequested { .. } => {
                supervisor.stop_owned();
            }
            _ => {}
        }
    });
}
```

`RuntimeError::code()` を `pub` とし、`RuntimeSupervisor` は `Arc` 経由でsetup threadとexit handlerだけが共有する。Web UIへTauri commandは公開しない。

- [ ] **Step 5: RustとPythonテストを合格させる**

```bash
cargo test --manifest-path src-tauri/Cargo.toml
python3 scripts/test-desktop-shell-contract.py
```

期待結果:

- Rust unit testがすべて成功する。
- Python契約テストはstartup page不足以外で失敗しない。

- [ ] **Step 6: 承認済みの場合だけTask単位でcommitする**

```bash
git add src-tauri/src/main.rs src-tauri/src/lib.rs scripts/test-desktop-shell-contract.py
git commit -m "feat: connect TOMOS desktop lifecycle"
```

---

### Task 4: 起動中・失敗画面を追加する

**Files:**

- Create: `web/desktop-starting.html`
- Create: `web/desktop-starting.js`
- Modify: `scripts/test-desktop-shell-contract.py`

**Interfaces:**

- Consumes: `window.TOMOS_DESKTOP_STARTUP.showError(code)`。
- Produces: 技術語を抑えた固定日本語メッセージ。

- [ ] **Step 1: 表示契約を追加する**

`scripts/test-desktop-shell-contract.py` へ次を追加し、tests配列にも登録する。

```python
def test_startup_page_has_fixed_japanese_errors() -> None:
    html = read(ROOT / "web" / "desktop-starting.html")
    script = read(ROOT / "web" / "desktop-starting.js")
    assert 'id="desktop-startup-title"' in html
    assert 'id="desktop-startup-message"' in html
    assert "TOMOSを起動しています" in html
    assert '"missing_python"' in script
    assert '"port_in_use"' in script
    assert '"server_exited"' in script
    assert '"timeout"' in script
    assert "innerHTML" not in script
    assert "textContent" in script
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
python3 scripts/test-desktop-shell-contract.py
```

期待結果: `web/desktop-starting.html` 不足で失敗する。

- [ ] **Step 3: 起動画面を実装する**

`web/desktop-starting.html`:

```html
<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>TOMOS AI</title>
    <style>
      :root { color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      body { min-height: 100vh; margin: 0; display: grid; place-items: center; background: #f5f3ef; color: #24211d; }
      main { width: min(440px, calc(100vw - 48px)); text-align: center; }
      h1 { font-size: 24px; margin: 0 0 12px; }
      p { line-height: 1.7; margin: 0; }
    </style>
  </head>
  <body>
    <main>
      <h1 id="desktop-startup-title">TOMOSを起動しています</h1>
      <p id="desktop-startup-message">ローカルAIの準備を確認しています。</p>
    </main>
    <script src="./desktop-starting.js"></script>
  </body>
</html>
```

`web/desktop-starting.js`:

```js
(() => {
  const messages = {
    missing_resource_root: "TOMOSの実行環境を確認できませんでした。再インストールしてください。",
    missing_python: "TOMOSの実行環境を確認できませんでした。再インストールしてください。",
    port_in_use: "TOMOSが使う場所を別のアプリが使用しています。ほかのTOMOSを終了して、もう一度開いてください。",
    server_exited: "TOMOSを起動できませんでした。診断情報を確認してください。",
    timeout: "TOMOSの起動に時間がかかっています。Ollamaを確認して、もう一度開いてください。",
  };
  const title = document.querySelector("#desktop-startup-title");
  const message = document.querySelector("#desktop-startup-message");

  window.TOMOS_DESKTOP_STARTUP = {
    showReady() {
      title.textContent = "TOMOSを開いています";
      message.textContent = "準備ができました。";
    },
    showError(code) {
      title.textContent = "TOMOSを起動できませんでした";
      message.textContent = messages[code] || "TOMOSを起動できませんでした。診断情報を確認してください。";
    },
  };
})();
```

- [ ] **Step 4: 契約・構文テストを合格させる**

```bash
python3 scripts/test-desktop-shell-contract.py
node --check web/desktop-starting.js
cargo test --manifest-path src-tauri/Cargo.toml
```

期待結果:

```text
desktop shell contract tests passed
```

NodeとCargoは終了コード0。

- [ ] **Step 5: 承認済みの場合だけTask単位でcommitする**

```bash
git add web/desktop-starting.html web/desktop-starting.js scripts/test-desktop-shell-contract.py
git commit -m "feat: add TOMOS desktop startup screen"
```

---

### Task 5: macOS実機PoCと既存回帰を確認する

**Files:**

- Verify: `src-tauri/**`
- Verify: `web/desktop-starting.html`
- Verify: 既存テスト対象。
- Document: Gate A報告。

**Interfaces:**

- Consumes: Task 1から4のTauri Shell。
- Produces: Gate Aの合否、配布工程へ進める前の実機証拠。

- [ ] **Step 1: 全自動テストを実行する**

Entry Gate A0で依存追加が承認済みの場合だけCargoを実行する。

```bash
python3 scripts/test-desktop-shell-contract.py
cargo test --manifest-path src-tauri/Cargo.toml
node --check web/desktop-starting.js
node scripts/test-model-selection.js
node scripts/test-settings-helpers.js
node scripts/test-asr-helpers.js
node scripts/test-management-helpers.js
node scripts/test-pwa-assets.js
python3 scripts/test_server_helpers.py
python3 scripts/test_study_pack_manager.py
python3 scripts/test_context_core.py
python3 scripts/test_knowledge_layer.py
python3 -m py_compile server.py
git diff --check
```

期待結果: 全コマンド終了コード0。

- [ ] **Step 2: Tauri appを起動する**

```bash
cargo run --manifest-path src-tauri/Cargo.toml
```

期待結果:

- ブラウザーが開かない。
- `TOMOS AI` ウィンドウ内に既存チャット画面が表示される。
- health待機中は起動画面が表示される。

- [ ] **Step 3: 単一起動を確認する**

1つ目を起動したまま、別ターミナルで同じコマンドを実行する。

```bash
cargo run --manifest-path src-tauri/Cargo.toml
```

期待結果:

- 既存ウィンドウが前面へ戻る。
- `server.py` が増えない。
- 2つ目のアプリプロセスは終了する。

- [ ] **Step 4: 終了所有権を確認する**

1. TOMOSアプリを終了する。
2. アプリが起動した `server.py --port 54876` が終了していることを確認する。
3. 先に `.command` でTOMOSを起動してからTauri appを開く。
4. Tauri appを終了する。

期待結果:

- 自分で起動したserverだけを停止する。
- 先に存在した正規TOMOS serverは停止しない。

- [ ] **Step 5: ポート競合を確認する**

TOMOSではないローカルHTTP serverを54876で起動し、その後Tauri appを開く。

```bash
python3 -m http.server 54876 --bind 127.0.0.1
```

期待結果:

- 「TOMOSが使う場所を別のアプリが使用しています」と表示する。
- 競合serverを停止しない。
- 新しいTOMOS serverを起動しない。

確認後はテスト用HTTP serverだけを通常終了する。

- [ ] **Step 6: 既存画面を確認する**

Macアプリの `1280 × 820` と `960 × 640` で次を確認する。

- チャット送信と停止。
- Qwen3 4B、Agentic Coder v2、Gemma 4 12Bの既存表示。
- 設定、PC診断、音声入力、教材パック、Knowledge、Memory。
- 外部リンクがアプリ画面を置き換えない。
- ConsoleにTauri capability errorがない。

ブラウザー版とスマートフォンPWA `390 × 844` も既存基準で確認する。

- [ ] **Step 7: Gate Aを記録する**

```text
[Desktop Phase A / Gate A]
基準HEAD:
変更ファイル:
依存追加承認:
Rust tests:
既存9 tests:
Mac専用window:
ブラウザー自動起動なし:
単一起動:
owned server停止:
reused server維持:
ポート競合:
ブラウザーfallback:
スマートフォンPWA:
Console error:
未完了:
```

各項目へ `合格`、`不合格`、または実際のエラーを記入し、空欄を残さない。

- [ ] **Step 8: 承認済みの場合だけ最終commitする**

推奨commit:

```bash
git add .gitignore src-tauri web/desktop-starting.html web/desktop-starting.js scripts/test-desktop-shell-contract.py
git commit -m "feat: add TOMOS Tauri desktop shell"
```

commit、push、PKG作成、公開は別承認とする。

## Gate A

合格条件:

- Entry Gate A0の依存追加が明示承認されている。
- Python契約テストとRust testが合格する。
- 既存9本の基準テストと構文確認が合格する。
- macOSでブラウザーを開かずTOMOS専用windowを表示する。
- 単一起動、owned child停止、reused server維持、ポート競合保護が合格する。
- `.command`、`.bat`、PWA、保存キー、機能コードを変更していない。
- Tauri capabilityにshell、任意コマンド、外部書き込み権限がない。
- 配布、署名、公証、Python同梱を実行していない。

停止条件:

- Gate 0が未合格。
- 依存追加が未承認。
- `server.py` または既存Web機能の変更が必要になる。
- localhost以外の待受が必要になる。
- Tauriが別プロセスを停止する必要が生じる。
- 既存localStorageキーを変更しないと起動できない。
- Macでマイク、ファイル操作、外部リンクに重大回帰がある。

Gate A合格後だけ、マスター計画のPhase 1へ進む。Python同梱、localhost API token、保存移行、署名配布はDesktop Phase B以降の別計画で実装する。
