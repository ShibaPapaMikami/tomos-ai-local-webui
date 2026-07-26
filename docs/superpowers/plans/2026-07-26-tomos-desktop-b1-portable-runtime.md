# TOMOS Desktop B1 Portable Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apple Silicon版TOMOS `0.8.233`へPython 3.11と必要resourceを同梱し、開発リポジトリやsystem Pythonがない場所でも起動できるapp bundleを作る。

**Architecture:** 取得・検証、resource staging、Tauri runtime解決、app bundle生成を分離する。release時は固定SHA-256のPython artifactとallowlist化したTOMOS resourceだけをappへ入れ、RustはTauri resource directory内のPythonと`server.py`だけを起動する。

**Tech Stack:** Rust 1.94、Tauri 2、Python 3.11標準ライブラリ、Bash、macOS `codesign`・`file`・`shasum`

## Global Constraints

- 正本設計は `docs/superpowers/specs/2026-07-26-tomos-macos-portable-runtime-and-notarized-pkg-design.md`。
- 対象はmacOS 13以降、Apple Silicon `arm64`、TOMOS `0.8.233`。
- Python artifactはRelease `20260718`の`cpython-3.11.15+20260718-aarch64-apple-darwin-install_only.tar.gz`。
- SHA-256は`125587d03495bebdf30ec9e549a8469c97c0925d863ff401f24f157fd44d91d6`。
- system Python、PATH、`CARGO_MANIFEST_DIR`へ依存するrelease appを作らない。
- モデル、DB、ログ、`.git`、秘密情報をappへ入れない。
- 既存 `/Applications/TOMOS AI.app` を上書きしない。
- artifact downloadは明示済みURLだけを許可し、hash検証前に展開しない。
- commitはDirectorの明示承認後だけ実行する。

---

### Task 1: Version contractを`0.8.233`へ統一

**Files:**
- Modify: `server.py`
- Modify: `src-tauri/Cargo.toml`
- Modify: `src-tauri/tauri.conf.json`
- Modify: `scripts/test-agent-reach-routing-smoke.py`
- Modify: `Gemma4_12B_Web.command`
- Modify: `Gemma4_12B_全部起動.command`
- Modify: `Gemma4_12B_Web.bat`
- Modify: `Gemma4_12B_All_Start.bat`
- Test: `scripts/test-pwa-assets.js`
- Create: `scripts/test-desktop-release-version.py`

**Interfaces:**
- Consumes: 現在の`0.8.219`既定値とPhase 3 asset revision。
- Produces: `read_release_versions(root: Path) -> dict[str, str]`と、全実行経路で一致する`0.8.233`。

- [ ] **Step 1: 失敗するversion契約テストを書く**

```python
from pathlib import Path
import json
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "0.8.233"

def test_release_versions_match() -> None:
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    server_version = re.search(r'GEMMA_APP_VERSION", "([^"]+)"', server).group(1)
    cargo = tomllib.loads((ROOT / "src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    tauri = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert server_version == EXPECTED
    assert cargo["package"]["version"] == EXPECTED
    assert tauri["version"] == EXPECTED

if __name__ == "__main__":
    test_release_versions_match()
    print("desktop release version tests passed")
```

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test-desktop-release-version.py`

Expected: `0.8.219 != 0.8.233`で失敗。

- [ ] **Step 3: 既定versionだけを`0.8.233`へ更新する**

`server.py`、Cargo、Tauri config、4 launcher、既存version testを同じTaskで更新する。`0.8.233-tts-boundary`のPWA asset revisionは変更しない。

- [ ] **Step 4: GREENと既存asset契約を確認する**

Run:

```bash
python3 scripts/test-desktop-release-version.py
node scripts/test-pwa-assets.js
python3 scripts/test-agent-reach-routing-smoke.py
```

Expected: 3コマンドすべてexit 0。

- [ ] **Step 5: commit候補をDirectorへhandoffする**

```text
feat: align TOMOS desktop release version
```

---

### Task 2: 固定Python artifactの取得・検証を実装

**Files:**
- Create: `scripts/macos_python_runtime.py`
- Create: `scripts/fetch-macos-python-runtime.py`
- Create: `scripts/test_macos_python_runtime.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces:
  - `RuntimeArtifact(name: str, url: str, sha256: str, size: int)`
  - `verify_artifact(path: Path, artifact: RuntimeArtifact) -> None`
  - `extract_runtime(archive: Path, destination: Path) -> Path`
  - `build/macos-runtime/python/bin/python3`

- [ ] **Step 1: hash・size・path traversalの失敗テストを書く**

```python
def test_rejects_wrong_hash(tmp_path):
    archive = tmp_path / ARTIFACT.name
    archive.write_bytes(b"wrong")
    try:
        verify_artifact(archive, ARTIFACT)
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("wrong hash was accepted")

def test_rejects_unsafe_tar_member(tmp_path):
    archive = make_runtime_tar(tmp_path, member_name="../outside")
    try:
        extract_runtime(archive, tmp_path / "runtime")
    except ValueError as exc:
        assert "安全" in str(exc)
    else:
        raise AssertionError("unsafe tar member was accepted")
```

`make_runtime_tar(tmp_path, member_name)`は標準ライブラリ`tarfile`と`io.BytesIO`で1 memberのgzip tarを作るtest helperとして同じtest fileへ定義する。外部test依存は追加しない。

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_macos_python_runtime.py`

Expected: `ModuleNotFoundError: macos_python_runtime`。

- [ ] **Step 3: artifact定数と安全な検証・展開を実装する**

```python
ARTIFACT = RuntimeArtifact(
    name="cpython-3.11.15+20260718-aarch64-apple-darwin-install_only.tar.gz",
    url="https://github.com/astral-sh/python-build-standalone/releases/download/20260718/cpython-3.11.15%2B20260718-aarch64-apple-darwin-install_only.tar.gz",
    sha256="125587d03495bebdf30ec9e549a8469c97c0925d863ff401f24f157fd44d91d6",
    size=27241978,
)
```

tar memberは絶対path、`..`、symlink、hardlinkを拒否する。展開先を一時directoryへ作り、`python/bin/python3`とライセンスを確認してからatomic renameする。

- [ ] **Step 4: downloaderを実装する**

`fetch-macos-python-runtime.py`は`--archive-cache`と`--output`を受け取る。cacheがない場合だけ固定URLへ接続し、一時fileへdownloadしてからhashを検証する。redirect後のhostも`github.com`または`objects.githubusercontent.com`だけを許可する。

- [ ] **Step 5: GREENを確認する**

Run:

```bash
python3 scripts/test_macos_python_runtime.py
python3 -m py_compile scripts/macos_python_runtime.py scripts/fetch-macos-python-runtime.py
git diff --check
```

Expected: 全コマンドexit 0。

- [ ] **Step 6: 実artifact取得前Gate**

Directorの外部artifact実行承認記録と固定SHA-256を再確認する。承認済みの場合だけ次を実行する。

```bash
python3 scripts/fetch-macos-python-runtime.py \
  --archive-cache build/cache \
  --output build/macos-runtime/python
```

Expected: Python `3.11.x`、Mach-O `arm64`、hash一致を表示する。artifactの内容を実行するのはhashとCPU確認後だけ。

---

### Task 3: TOMOS resource stagingをallowlist化

**Files:**
- Create: `scripts/stage-macos-tomos-resources.py`
- Create: `scripts/test_macos_tomos_resources.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces:
  - `RESOURCE_FILES: tuple[str, ...]`
  - `stage_resources(root: Path, destination: Path) -> dict`
  - `build/macos-runtime/tomos/`
  - `build/macos-runtime/build-manifest.json`

- [ ] **Step 1: 必須file不足と禁止file混入のテストを書く**

```python
def test_manifest_requires_server_and_web():
    assert "server.py" in RESOURCE_FILES
    assert "web/index.html" in RESOURCE_FILES

def test_staged_tree_excludes_private_state(tmp_path):
    result = stage_fixture(tmp_path)
    names = set(result["files"])
    assert not any(name.startswith(".git/") for name in names)
    assert not any(name.endswith(".sqlite") for name in names)
    assert not any("/models/" in f"/{name}/" for name in names)
```

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_macos_tomos_resources.py`

Expected: staging module未作成で失敗。

- [ ] **Step 3: 明示的resource manifestを実装する**

Python moduleはserverの直接import graph、`packages/local_context_core/`、`web/`、実行に必要な`scripts/`だけを列挙する。directory一括copy時も`.git`、`__pycache__`、`.venv*`、`dist`、`models`、`.gemma4-data`、`data`、`*.sqlite`、logを拒否する。

- [ ] **Step 4: build manifestを生成する**

manifestへ`appVersion`、`architecture`、Python artifact情報、Bundle ID、PKG identifier、40文字の現在HEADを自動記録する。`git status --porcelain`が空でない場合は`--release`を拒否する。

- [ ] **Step 5: GREENを確認する**

Run:

```bash
python3 scripts/test_macos_tomos_resources.py
python3 scripts/stage-macos-tomos-resources.py --output build/macos-runtime/tomos
python3 -m py_compile build/macos-runtime/tomos/server.py
git diff --check
```

Expected: 全コマンドexit 0、禁止file 0件。

---

### Task 4: Rust runtimeをapp resource基準へ変更

**Files:**
- Modify: `src-tauri/src/runtime.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `scripts/test-desktop-shell-contract.py`

**Interfaces:**
- Produces:
  - `RuntimePaths { resource_root: PathBuf, python: PathBuf }`
  - `resolve_runtime_paths(resource_dir: &Path, development_override: Option<&Path>) -> Result<RuntimePaths, RuntimeError>`
  - `RuntimeError::InvalidBundledRuntime`

- [ ] **Step 1: bundle外pathと不足runtimeを拒否するRust testを書く**

```rust
#[test]
fn resolves_bundled_runtime_inside_resource_dir() {
    let fixture = RuntimeFixture::valid();
    let paths = resolve_runtime_paths(fixture.resources(), None).unwrap();
    assert!(paths.python.starts_with(fixture.resources()));
    assert!(paths.resource_root.starts_with(fixture.resources()));
}

#[test]
fn rejects_python_outside_resource_dir() {
    let fixture = RuntimeFixture::with_external_python();
    assert_eq!(
        resolve_runtime_paths(fixture.resources(), None),
        Err(RuntimeError::InvalidBundledRuntime)
    );
}
```

- [ ] **Step 2: REDを確認する**

Run: `cargo test --manifest-path src-tauri/Cargo.toml runtime::tests`

Expected: `resolve_runtime_paths`未定義でcompile失敗。

- [ ] **Step 3: release用path解決を実装する**

`app.path().resource_dir()`を`lib.rs`から渡す。`TOMOS_RESOURCE_ROOT`はdebug buildまたはtestだけで許可する。releaseでは`Resources/tomos/server.py`と`Resources/python/bin/python3`をcanonicalizeし、両方がresource directory内であることを確認する。

- [ ] **Step 4: Python起動を固定pathへ変更する**

`RuntimeSupervisor::start(&RuntimePaths)`へ変更し、`Command::new(&paths.python)`と`current_dir(&paths.resource_root)`を使用する。release buildから`python3` fallbackを削除する。

- [ ] **Step 5: GREENを確認する**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml
python3 scripts/test-desktop-shell-contract.py
cargo build --release --manifest-path src-tauri/Cargo.toml
```

Expected: Rust 7件以上を含め全件合格。

---

### Task 5: portable app bundle buildとGate B1

**Files:**
- Modify: `src-tauri/tauri.conf.json`
- Create: `scripts/build-macos-tauri-app.sh`
- Create: `scripts/test_macos_tauri_bundle.py`
- Modify: `src-tauri/Info.plist`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `build/macos-runtime/python`、`build/macos-runtime/tomos`。
- Produces: `dist/candidate/TOMOS AI.app`と`dist/candidate/build-manifest.json`。

- [ ] **Step 1: bundle resourceとInfo.plist契約テストを書く**

```python
def test_tauri_bundle_contains_portable_resources():
    config = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text())
    resources = config["bundle"]["resources"]
    assert resources["../build/macos-runtime/python/"] == "python/"
    assert resources["../build/macos-runtime/tomos/"] == "tomos/"
    assert config["bundle"]["targets"] == ["app"]
```

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_macos_tauri_bundle.py`

Expected: `resources`未定義で失敗。

- [ ] **Step 3: Tauri bundle設定とbuild scriptを実装する**

`bundle.resources`はsourceから配置先を固定できるmap形式にし、`"../build/macos-runtime/python/": "python/"`と`"../build/macos-runtime/tomos/": "tomos/"`を設定する。`targets`を`["app"]`、macOS minimumを`13.0`に固定する。build scriptはCPU、version、clean source、runtime hash、resource manifestを確認してから`cargo tauri build --bundles app`を実行し、成果物を`dist/candidate/`へコピーする。

- [ ] **Step 4: bundle静的検証を実装する**

`test_macos_tauri_bundle.py`はInfo.plist、Mach-O arm64、同梱Python、server、web、禁止file不在、build manifestのsource commit一致を検証する。

- [ ] **Step 5: Gate B1実機testを行う**

一時directoryへappをコピーし、PATHを空にした状態で起動する。health成功、専用window表示、二重起動1件、終了後port解放を確認する。既存`/Applications/TOMOS AI.app`は停止も上書きもしない。

- [ ] **Step 6: Gate B1判定**

Run:

```bash
python3 scripts/test_macos_tauri_bundle.py dist/candidate/TOMOS\ AI.app
codesign --verify --deep --strict --verbose=2 dist/candidate/TOMOS\ AI.app
git diff --check
```

Expected: ad-hoc候補の構造検証とGate B1実機項目が全件合格。合格後にマスター台帳のGate B1だけを`合格`へ更新する。
